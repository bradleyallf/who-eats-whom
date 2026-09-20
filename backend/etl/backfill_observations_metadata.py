"""
One-time backfill of licensed photo metadata for existing
observations in Postgres.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg


INATURALIST_OBSERVATIONS_URL = (
    "https://api.inaturalist.org/v1/observations/{}"
)

BATCH_SIZE = 30

ALLOWED_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa",
    "cc-by-nd",
    "cc-by-nc",
    "cc-by-nc-sa",
    "cc-by-nc-nd",
    "pd",
    "gfdl",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill licensed photo metadata for observations in Postgres."
    )
    parser.add_argument(
        "--dsn",
        required=True,
        help="Postgres connection string.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between iNaturalist requests in seconds.",
    )
    parser.add_argument(
        "--log-dir",
        default="inat_logs",
        help="Directory where iNaturalist API pull logs are stored.",
    )
    return parser.parse_args()


def chunk(items: List[int], size: int) -> List[List[int]]:
    return [
        items[i : i + size]
        for i in range(0, len(items), size)
    ]


def get_next_pull_number(log_dir: Path) -> int:
    """Return the next available iNaturalist pull number."""
    log_dir.mkdir(parents=True, exist_ok=True)

    pull_numbers = []

    for path in log_dir.glob("iNat_pull_*.json"):
        try:
            number = int(
                path.stem.replace("iNat_pull_", "")
            )
            pull_numbers.append(number)
        except ValueError:
            continue

    if not pull_numbers:
        return 1

    return max(pull_numbers) + 1


def is_empty_observation(observation: Dict[str, Any]) -> bool:
    """Return True if every value in the observation is null/empty."""
    if not observation:
        return True

    return all(
        value is None
        or value == ""
        or value == []
        or value == {}
        for value in observation.values()
    )


def fetch_json(
    url: str,
    max_retries: int = 3,
) -> Optional[Dict[str, Any]]:
    for attempt in range(1, max_retries + 1):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "Who-Eats-Whom/1.0"
                },
            )

            with urlopen(request, timeout=30) as response:
                return json.loads(
                    response.read().decode("utf-8")
                )

        except (
            HTTPError,
            URLError,
            TimeoutError,
            RemoteDisconnected,
        ) as exc:
            print(
                f"  ERROR fetching URL "
                f"(attempt {attempt}/{max_retries}): {exc}"
            )

            if attempt < max_retries:
                wait_time = 2 ** (attempt - 1)

                print(
                    f"  Retrying in {wait_time} seconds..."
                )

                time.sleep(wait_time)

    print(
        f"  FAILED after {max_retries} attempts: {url}"
    )

    return None


def fetch_observations_batch(
    observation_ids: List[int],
) -> Optional[Dict[str, Any]]:
    """Fetch a batch of observations and return the raw API response."""
    ids_param = ",".join(
        str(observation_id)
        for observation_id in observation_ids
    )

    url = INATURALIST_OBSERVATIONS_URL.format(
        ids_param
    )

    return fetch_json(url)


def find_allowed_photo(
    photos: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return the first photo with an allowed license."""
    for photo in photos:
        license_code = (
            photo.get("license_code") or ""
        ).lower()

        if license_code in ALLOWED_LICENSES:
            return photo

    return None


def write_api_log(
    log_path: Path,
    pull_id: str,
    timestamp: str,
    url: str,
    observation_ids: List[int],
    response: Optional[Dict[str, Any]],
) -> None:
    """Write the raw iNaturalist API response and pull metadata."""
    log_data = {
        "pull_id": pull_id,
        "timestamp": timestamp,
        "api": "iNaturalist",
        "endpoint": url,
        "observation_ids": observation_ids,
        "response": response,
    }

    with log_path.open(
        "w",
        encoding="utf-8",
    ) as log_file:
        json.dump(
            log_data,
            log_file,
            indent=2,
            ensure_ascii=False,
        )


def main() -> None:
    args = parse_args()

    log_dir = Path(args.log_dir)
    next_pull_number = get_next_pull_number(log_dir)

    print(
        f"Starting iNaturalist backfill."
    )
    print(
        f"Logs will be stored in: {log_dir}"
    )

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT observation_id
                FROM observations
                WHERE observation_id IS NOT NULL
                ORDER BY observation_id;
                """
            )

            rows = cur.fetchall()

            observation_ids = [
                row[0]
                for row in rows
                if row[0] is not None
            ]

            batches = chunk(
                observation_ids,
                BATCH_SIZE,
            )

            print(
                f"Found {len(observation_ids)} observations "
                f"with valid observation IDs "
                f"({len(batches)} batches of up to "
                f"{BATCH_SIZE})."
            )

            successful = 0
            failed = 0
            licensed_photos = 0
            no_allowed_photo = 0
            empty_observations = 0

            for batch_index, batch_ids in enumerate(
                batches,
                start=1,
            ):
                pull_id = (
                    f"iNat_pull_{next_pull_number:02d}"
                )

                next_pull_number += 1

                pulled_at = datetime.now(
                    timezone.utc
                )

                pulled_at_string = (
                    pulled_at.isoformat()
                )

                print(
                    f"[batch {batch_index}/{len(batches)}] "
                    f"{pull_id}: Fetching "
                    f"{len(batch_ids)} observations..."
                )

                ids_param = ",".join(
                    str(observation_id)
                    for observation_id in batch_ids
                )

                url = INATURALIST_OBSERVATIONS_URL.format(
                    ids_param
                )

                response = fetch_observations_batch(
                    batch_ids
                )

                log_path = (
                    log_dir / f"{pull_id}.json"
                )

                write_api_log(
                    log_path=log_path,
                    pull_id=pull_id,
                    timestamp=pulled_at_string,
                    url=url,
                    observation_ids=batch_ids,
                    response=response,
                )

                print(
                    f"  Saved API response to {log_path}"
                )

                if response is None:
                    failed += len(batch_ids)
                    time.sleep(args.delay)
                    continue

                results = response.get(
                    "results",
                    [],
                )

                obs_by_id = {
                    observation["id"]: observation
                    for observation in results
                    if "id" in observation
                }

                for observation_id in batch_ids:
                    observation = obs_by_id.get(
                        observation_id
                    )

                    if observation is None:
                        print(
                            f"  MISSING observation "
                            f"{observation_id} "
                            f"(not returned by this batch)"
                        )

                        failed += 1
                        continue

                    if is_empty_observation(
                        observation
                    ):
                        print(
                            f"  EMPTY observation "
                            f"{observation_id} - skipped"
                        )

                        empty_observations += 1
                        continue

                    photos = observation.get(
                        "photos",
                        [],
                    )

                    photo = find_allowed_photo(
                        photos
                    )

                    if photo is None:
                        image_url = None
                        license_code = None
                        attribution = None

                        no_allowed_photo += 1

                        print(
                            f"    Observation "
                            f"{observation_id}: "
                            f"no allowed licensed "
                            f"photo found"
                        )

                    else:
                        image_url = photo.get(
                            "url"
                        )

                        license_code = (
                            photo.get(
                                "license_code"
                            )
                            or None
                        )

                        if license_code:
                            license_code = (
                                license_code.lower()
                            )

                        attribution = photo.get(
                            "attribution"
                        )

                        licensed_photos += 1

                    cur.execute(
                        """
                        UPDATE observations
                        SET
                            image_url = %s,
                            photo_license_code = %s,
                            photo_attribution = %s,
                            inat_pulled_at = %s,
                            inat_api_call = %s,
                            updated_at = NOW()
                        WHERE observation_id = %s;
                        """,
                        (
                            image_url,
                            license_code,
                            attribution,
                            pulled_at,
                            pull_id,
                            observation_id,
                        ),
                    )

                    successful += 1

                time.sleep(args.delay)

            conn.commit()

            print()
            print("Backfill complete.")
            print(
                f"Successful:               {successful}"
            )
            print(
                f"Failed:                   {failed}"
            )
            print(
                f"Empty observations:       "
                f"{empty_observations}"
            )
            print(
                f"Licensed photos selected: "
                f"{licensed_photos}"
            )
            print(
                f"No allowed photo:         "
                f"{no_allowed_photo}"
            )


if __name__ == "__main__":
    main()