"""
One-time backfill of licensed photo metadata for existing
observations in Postgres.
"""
from __future__ import annotations

import argparse
import json
import time
from http.client import RemoteDisconnected
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg


INATURALIST_OBSERVATIONS_URL = "https://api.inaturalist.org/v1/observations/{}"
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
    "gfdl"
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill licensed photo metadata for observations in Postgres."
    )
    parser.add_argument("--dsn", required=True, help="Postgres connection string.")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between iNaturalist requests in seconds (per batch, not per observation).",
    )
    return parser.parse_args()


def chunk(items: List[int], size: int) -> List[List[int]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_json(url: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
    for attempt in range(1, max_retries + 1):
        try:
            request = Request(
                url,
                headers={"User-Agent": "Who-Eats-Whom/1.0"},
            )
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, RemoteDisconnected) as exc:
            print(
                f"  ERROR fetching URL "
                f"(attempt {attempt}/{max_retries}): {exc}"
            )

            if attempt < max_retries:
                wait_time = 2 ** (attempt - 1)
                print(f"  Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

    print(f"  FAILED after {max_retries} attempts: {url}")
    return None


def fetch_observations_batch(
    observation_ids: List[int],
) -> Dict[int, Dict[str, Any]]:
    """Fetch a batch of observations from iNaturalist in a single request."""
    ids_param = ",".join(str(o) for o in observation_ids)
    url = INATURALIST_OBSERVATIONS_URL.format(ids_param)

    data = fetch_json(url)

    if data is None:
        return {}

    results = data.get("results", [])

    if not results:
        print(f"  No iNaturalist results for batch {observation_ids}")
        return {}

    return {
        obs["id"]: obs
        for obs in results
        if "id" in obs
    }


def find_allowed_photo(
    photos: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return the first photo with an allowed license."""
    for photo in photos:
        license_code = (photo.get("license_code") or "").lower()

        if license_code in ALLOWED_LICENSES:
            return photo

    return None


def main() -> None:
    args = parse_args()

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT observation_id
                FROM observations
                WHERE raw->>'image_url' IS NOT NULL
                  AND raw->>'image_url' <> ''
                ORDER BY observation_id;
                """
            )

            rows = cur.fetchall()
            observation_ids = [row[0] for row in rows]
            batches = chunk(observation_ids, BATCH_SIZE)

            print(
                f"Found {len(observation_ids)} observations with a stored image "
                f"({len(batches)} batches of up to {BATCH_SIZE})."
            )

            successful = 0
            failed = 0
            licensed_photos = 0
            no_allowed_photo = 0

            for batch_index, batch_ids in enumerate(batches, start=1):
                print(
                    f"[batch {batch_index}/{len(batches)}] "
                    f"Fetching {len(batch_ids)} observations..."
                )

                obs_by_id = fetch_observations_batch(batch_ids)

                for observation_id in batch_ids:
                    observation = obs_by_id.get(observation_id)

                    if observation is None:
                        print(
                            f"  MISSING observation {observation_id} "
                            f"(not returned by this batch)"
                        )
                        failed += 1
                        continue

                    photos = observation.get("photos", [])
                    photo = find_allowed_photo(photos)

                    if photo is None:
                        image_url = None
                        license_code = None
                        attribution = None
                        no_allowed_photo += 1

                        print(
                            f"    Observation {observation_id}: "
                            f"no allowed licensed photo found"
                        )
                    else:
                        image_url = photo.get("url")

                        license_code = (
                            photo.get("license_code") or None
                        )

                        if license_code:
                            license_code = license_code.lower()

                        attribution = photo.get("attribution")

                        licensed_photos += 1

                    cur.execute(
                        """
                        UPDATE observations
                        SET
                            image_url = %s,
                            photo_license_code = %s,
                            photo_attribution = %s,
                            updated_at = NOW()
                        WHERE observation_id = %s;
                        """,
                        (
                            image_url,
                            license_code,
                            attribution,
                            observation_id,
                        ),
                    )

                    successful += 1

                time.sleep(args.delay)

            conn.commit()

            print()
            print("Backfill complete.")
            print(f"Successful:               {successful}")
            print(f"Failed:                   {failed}")
            print(f"Licensed photos selected: {licensed_photos}")
            print(f"No allowed photo:         {no_allowed_photo}")


if __name__ == "__main__":
    main()