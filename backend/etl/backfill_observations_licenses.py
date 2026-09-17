"""
One-time backfill of real photo license/attribution metadata for existing
observations in Postgres.
"""
from __future__ import annotations
 
import argparse
import json
import re
import time
from http.client import RemoteDisconnected
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
 
import psycopg
 
 
INATURALIST_OBSERVATIONS_URL = "https://api.inaturalist.org/v1/observations/{}"
BATCH_SIZE = 30
PHOTO_ID_PATTERN = re.compile(r"/photos/(\d+)/")
 
 
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill real photo license/attribution for observations in Postgres."
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
            request = Request(url, headers={"User-Agent": "Who-Eats-Whom/1.0"})
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, RemoteDisconnected) as exc:
            print(f"  ERROR fetching URL (attempt {attempt}/{max_retries}): {exc}")
            if attempt < max_retries:
                wait_time = 2 ** (attempt - 1)
                print(f"  Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
    print(f"  FAILED after {max_retries} attempts: {url}")
    return None
 
 
def fetch_observations_batch(observation_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Fetch a batch of observations from iNaturalist in a single request.
    Returns a dict keyed by observation_id."""
    ids_param = ",".join(str(o) for o in observation_ids)
    url = INATURALIST_OBSERVATIONS_URL.format(ids_param)
 
    data = fetch_json(url)
    if data is None:
        return {}
 
    results = data.get("results", [])
    if not results:
        print(f"  No iNaturalist results for batch {observation_ids}")
        return {}
 
    return {obs["id"]: obs for obs in results if "id" in obs}
 
 
def extract_photo_id(image_url: Optional[str]) -> Optional[str]:
    if not image_url:
        return None
    match = PHOTO_ID_PATTERN.search(image_url)
    return match.group(1) if match else None
 
 
def find_matching_photo(
    photos: List[Dict[str, Any]], target_photo_id: Optional[str]
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Returns (photo, matched_exactly). Falls back to the first photo in
    the list if no exact id match is found, so we still get *some*
    license/attribution rather than nothing -- but callers should log when
    matched_exactly is False, since the fallback may describe a different
    photo than the one actually displayed."""
    if not photos:
        return None, False
 
    if target_photo_id:
        for photo in photos:
            if str(photo.get("id")) == target_photo_id:
                return photo, True
 
    return photos[0], False
 
 
def main() -> None:
    args = parse_args()
 
    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT observation_id, raw->>'image_url' AS image_url
                FROM observations
                WHERE raw->>'image_url' IS NOT NULL
                  AND raw->>'image_url' <> ''
                ORDER BY observation_id;
                """
            )
            rows = cur.fetchall()
            image_url_by_obs_id = {row[0]: row[1] for row in rows}
            observation_ids = list(image_url_by_obs_id.keys())
            batches = chunk(observation_ids, BATCH_SIZE)
 
            print(
                f"Found {len(observation_ids)} observations with a stored image "
                f"({len(batches)} batches of up to {BATCH_SIZE})."
            )
 
            successful = 0
            failed = 0
            fallback_matches = 0
            no_license = 0
 
            for batch_index, batch_ids in enumerate(batches, start=1):
                print(f"[batch {batch_index}/{len(batches)}] Fetching {len(batch_ids)} observations...")
 
                obs_by_id = fetch_observations_batch(batch_ids)
 
                for observation_id in batch_ids:
                    observation = obs_by_id.get(observation_id)
 
                    if observation is None:
                        print(f"  MISSING observation {observation_id} (not returned by this batch)")
                        failed += 1
                        continue
 
                    stored_image_url = image_url_by_obs_id.get(observation_id)
                    target_photo_id = extract_photo_id(stored_image_url)
                    photos = observation.get("photos", [])
 
                    photo, matched_exactly = find_matching_photo(photos, target_photo_id)
 
                    if photo is None:
                        license_code = None
                        attribution = None
                        no_license += 1
                    else:
                        license_code = (photo.get("license_code") or None)
                        if license_code:
                            license_code = license_code.lower()
                        attribution = photo.get("attribution")
                        if not matched_exactly:
                            fallback_matches += 1
                            print(
                                f"    Observation {observation_id}: no exact photo id match "
                                f"(target={target_photo_id}); using first photo as fallback"
                            )
                        if not license_code:
                            no_license += 1
 
                    cur.execute(
                        """
                        UPDATE observations
                        SET
                            photo_license_code = %s,
                            photo_attribution = %s,
                            updated_at = NOW()
                        WHERE observation_id = %s;
                        """,
                        (license_code, attribution, observation_id),
                    )
 
                    successful += 1
 
                time.sleep(args.delay)
 
            conn.commit()
 
            print()
            print("Backfill complete.")
            print(f"Successful:               {successful}")
            print(f"Failed:                   {failed}")
            print(f"Fallback (no exact match): {fallback_matches}")
            print(f"No license (unlicensed):  {no_license}")
 
 
if __name__ == "__main__":
    main()