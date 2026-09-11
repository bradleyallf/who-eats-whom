"""
One-time backfill of Wikipedia information and representative species
images for existing species in Postgres.

The script:
1. Gets all taxon IDs currently in the species table.
2. Fetches taxa from the iNaturalist API in batches of up to 30 IDs per
   request.
3. Extracts Wikipedia information and a licensed representative species
   image.
4. For images, it tries sources in this order:
      a. default_photo
      b. taxon_photos
      c. observation photos
5. Only photos with an allowed license are stored.
6. If the default photo and taxon photos do not have an allowed photo,
   the script searches iNaturalist observations for an allowed photo.
7. If no usable photo is found anywhere, the image fields are stored NULL.
8. Temporary network failures are retried up to 3 times.

Run this after the species table already contains the existing taxa using:

python3 -u backend/etl/backfill_species_metadata.py \
    --dsn postgresql://whodba:whopass@localhost:5433/who_eats_whom \
    --delay 1.0
"""

from __future__ import annotations

import argparse
import json
import time
from http.client import RemoteDisconnected
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg


INATURALIST_TAXA_URL = "https://api.inaturalist.org/v1/taxa/{}"
INATURALIST_OBSERVATIONS_URL = "https://api.inaturalist.org/v1/observations"

BATCH_SIZE = 30

# Licenses that the project currently allows.
ALLOWED_LICENSES = {
    "cc0",
    "cc-by",
    "cc-by-sa",
    "cc-by-nc",
    "cc-by-nc-sa",
}

# Number of observations to request when looking for a fallback image.
OBSERVATIONS_PER_PAGE = 50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill Wikipedia and image metadata for species in Postgres."
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

    return parser.parse_args()


def chunk(items: List[int], size: int) -> List[List[int]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_json(
    url: str,
    max_retries: int = 3,
) -> Optional[Dict[str, Any]]:
    """
    Fetch JSON from a URL with retries for temporary network failures.
    """

    for attempt in range(1, max_retries + 1):
        try:
            request = Request(
                url,
                headers={"User-Agent": "Who-Eats-Whom/1.0"},
            )

            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))

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
                print(f"  Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

    print(f"  FAILED after {max_retries} attempts: {url}")

    return None


def fetch_taxa_batch(
    taxon_ids: List[int],
    max_retries: int = 3,
) -> Dict[int, Dict[str, Any]]:
    """
    Fetch a batch of taxa from iNaturalist in a single request.

    Returns a dictionary keyed by taxon_id.
    """

    ids_param = ",".join(str(t) for t in taxon_ids)
    url = INATURALIST_TAXA_URL.format(ids_param)

    data = fetch_json(url, max_retries=max_retries)

    if data is None:
        return {}

    results = data.get("results", [])

    if not results:
        print(f"  No iNaturalist results for batch {taxon_ids}")
        return {}

    return {
        taxon["id"]: taxon
        for taxon in results
        if "id" in taxon
    }


def is_usable_photo(photo: Dict[str, Any]) -> bool:
    """
    Return True if the photo has a license that the project allows.
    """

    return photo.get("license_code") in ALLOWED_LICENSES


def get_photo_metadata(
    photo: Dict[str, Any],
) -> Optional[tuple[str, str, Optional[str]]]:
    """
    Extract image URL, license, and attribution from a usable photo.

    Returns:
        (image_url, license_code, attribution)

    or None if the photo is not usable.
    """

    if not is_usable_photo(photo):
        return None

    image_url = (
        photo.get("medium_url")
        or photo.get("small_url")
        or photo.get("square_url")
        or photo.get("url")
    )

    license_code = photo.get("license_code")
    attribution = photo.get("attribution")

    if not image_url or not license_code:
        return None

    return (
        image_url,
        license_code,
        attribution,
    )


def find_observation_photo(
    taxon_id: int,
    max_retries: int = 3,
) -> Optional[tuple[str, str, Optional[str]]]:
    """
    Search iNaturalist observations for a usable photo belonging to
    the exact taxon.

    The observations API can filter observations by:
      - taxon_id
      - photos
      - photo_license

    We request all currently allowed licenses in the query.

    The taxon_id filter can include descendant taxa, so we additionally
    verify that the observation's returned taxon ID exactly matches the
    species we are processing.
    """

    # iNaturalist's API uses uppercase license names in query parameters.
    photo_licenses = ",".join(
        license_code.upper()
        for license_code in sorted(ALLOWED_LICENSES)
    )

    params = [
        ("taxon_id", str(taxon_id)),
        ("has[]", "photos"),
        ("photo_license", photo_licenses),
        ("per_page", str(OBSERVATIONS_PER_PAGE)),
        ("page", "1"),
        ("order_by", "created_at"),
        ("order", "desc"),
    ]

    url = f"{INATURALIST_OBSERVATIONS_URL}?{urlencode(params)}"

    data = fetch_json(url, max_retries=max_retries)

    if data is None:
        return None

    observations = data.get("results", [])

    for observation in observations:
        observation_taxon = observation.get("taxon") or {}

        # taxon_id can include descendant taxa, so require an exact match.
        if observation_taxon.get("id") != taxon_id:
            continue

        for photo in observation.get("photos", []):
            metadata = get_photo_metadata(photo)

            if metadata is not None:
                return metadata

    return None


def get_species_metadata(
    taxon: Dict[str, Any],
    max_retries: int = 3,
) -> tuple[
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
]:
    """
    Extract Wikipedia information and a licensed representative
    species image.

    Image search order:
        1. default_photo
        2. taxon_photos
        3. observation photos
    """

    wikipedia_summary = taxon.get("wikipedia_summary")
    wikipedia_url = taxon.get("wikipedia_url")

    taxon_id = taxon.get("id")

    # ---------------------------------------------------------
    # 1. Try default_photo
    # ---------------------------------------------------------

    default_photo = taxon.get("default_photo") or {}

    metadata = get_photo_metadata(default_photo)

    if metadata is not None:
        image_url, license_code, attribution = metadata

        return (
            wikipedia_summary,
            wikipedia_url,
            image_url,
            license_code,
            attribution,
        )

    # ---------------------------------------------------------
    # 2. Try taxon_photos
    # ---------------------------------------------------------

    for taxon_photo in taxon.get("taxon_photos", []):
        candidate = taxon_photo.get("photo") or {}

        metadata = get_photo_metadata(candidate)

        if metadata is not None:
            image_url, license_code, attribution = metadata

            return (
                wikipedia_summary,
                wikipedia_url,
                image_url,
                license_code,
                attribution,
            )

    # ---------------------------------------------------------
    # 3. Try observation photos
    # ---------------------------------------------------------

    if taxon_id is not None:
        print(
            f"    No licensed default/taxon photo for taxon {taxon_id}; "
            f"searching observations..."
        )

        metadata = find_observation_photo(
            taxon_id,
            max_retries=max_retries,
        )

        if metadata is not None:
            image_url, license_code, attribution = metadata

            print(
                f"    Found licensed observation photo "
                f"({license_code}) for taxon {taxon_id}"
            )

            return (
                wikipedia_summary,
                wikipedia_url,
                image_url,
                license_code,
                attribution,
            )

    # ---------------------------------------------------------
    # 4. No usable photo found
    # ---------------------------------------------------------

    return (
        wikipedia_summary,
        wikipedia_url,
        None,
        None,
        None,
    )


def main() -> None:
    args = parse_args()

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:

            # Get every species already present in Postgres.
            cur.execute(
                """
                SELECT taxon_id
                FROM species
                ORDER BY taxon_id;
                """
            )

            taxon_ids = [row[0] for row in cur.fetchall()]
            batches = chunk(taxon_ids, BATCH_SIZE)

            print(
                f"Found {len(taxon_ids)} species in Postgres "
                f"({len(batches)} batches of up to {BATCH_SIZE})."
            )

            successful = 0
            failed = 0
            observation_fallbacks = 0

            for batch_index, batch_ids in enumerate(batches, start=1):

                print(
                    f"[batch {batch_index}/{len(batches)}] "
                    f"Fetching {len(batch_ids)} taxa..."
                )

                taxa_by_id = fetch_taxa_batch(batch_ids)

                for taxon_id in batch_ids:

                    taxon = taxa_by_id.get(taxon_id)

                    if taxon is None:
                        print(
                            f"  MISSING taxon {taxon_id} "
                            f"(not returned by this batch)"
                        )

                        failed += 1
                        continue

                    (
                        wikipedia_summary,
                        wikipedia_url,
                        image_url,
                        license_code,
                        attribution,
                    ) = get_species_metadata(taxon)

                    if image_url is not None:
                        print(
                            f"  Taxon {taxon_id}: "
                            f"using {license_code} image"
                        )
                    else:
                        print(
                            f"  Taxon {taxon_id}: "
                            f"no usable image found"
                        )

                    cur.execute(
                        """
                        UPDATE species
                        SET
                            wikipedia_summary = %s,
                            wikipedia_url = %s,
                            image_url = %s,
                            license_code = %s,
                            attribution = %s,
                            updated_at = NOW()
                        WHERE taxon_id = %s;
                        """,
                        (
                            wikipedia_summary,
                            wikipedia_url,
                            image_url,
                            license_code,
                            attribution,
                            taxon_id,
                        ),
                    )

                    successful += 1

                # One delay per batch.
                time.sleep(args.delay)

            conn.commit()

            print()
            print("Backfill complete.")
            print(f"Successful:            {successful}")
            print(f"Failed:                {failed}")
            print(f"Observation fallbacks: {observation_fallbacks}")


if __name__ == "__main__":
    main()