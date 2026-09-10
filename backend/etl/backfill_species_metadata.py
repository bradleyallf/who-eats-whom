"""
One-time backfill of Wikipedia information and representative species
images for existing species in Postgres.

The script:
1. Gets all taxon IDs currently in the species table.
2. Fetches taxa from the iNaturalist API in batches of up to 30 IDs per
   request (iNaturalist's own recommended practice -- see
   https://www.inaturalist.org/pages/api+recommended+practices -- fetching
   4,753 species one at a time would take ~100 minutes at their 1 req/sec
   guidance; batching cuts that to a few minutes).
3. Extracts Wikipedia information and each taxon's default photo.
4. Updates the corresponding species rows in Postgres.

Run this after the species table already contains the existing taxa using
python3 -u backend/etl/backfill_species_metadata.py --dsn postgresql://whodba:whopass@localhost:5433/who_eats_whom --delay 1.0
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg


INATURALIST_TAXA_URL = "https://api.inaturalist.org/v1/taxa/{}"
BATCH_SIZE = 30


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
        help="Delay between iNaturalist requests in seconds (per batch, not per species).",
    )

    return parser.parse_args()


def chunk(items: List[int], size: int) -> List[List[int]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def fetch_taxa_batch(taxon_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Fetch a batch of taxa from iNaturalist in a single request.
    Returns a dict keyed by taxon_id, since the response order/completeness
    isn't guaranteed to match the request (e.g. deleted/inactive taxa may
    be silently omitted)."""

    ids_param = ",".join(str(t) for t in taxon_ids)
    url = INATURALIST_TAXA_URL.format(ids_param)

    try:
        request = Request(
            url,
            headers={"User-Agent": "Who-Eats-Whom/1.0"},
        )

        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

    except (HTTPError, URLError, TimeoutError) as exc:
        print(f"  ERROR fetching batch {taxon_ids}: {exc}")
        return {}

    results = data.get("results", [])

    if not results:
        print(f"  No iNaturalist results for batch {taxon_ids}")
        return {}

    return {taxon["id"]: taxon for taxon in results if "id" in taxon}


def get_species_metadata(
    taxon: Dict[str, Any],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extract Wikipedia information and the representative
    species image from an iNaturalist taxon response.
    """

    wikipedia_summary = taxon.get("wikipedia_summary")
    wikipedia_url = taxon.get("wikipedia_url")

    default_photo = taxon.get("default_photo") or {}

    image_url = (
        default_photo.get("medium_url")
        or default_photo.get("small_url")
        or default_photo.get("square_url")
        or default_photo.get("url")
    )
    license_code = default_photo.get("license_code")
    attribution = default_photo.get("attribution")

    return (
        wikipedia_summary,
        wikipedia_url,
        image_url,
        license_code,
        attribution
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

            for batch_index, batch_ids in enumerate(batches, start=1):
                print(f"[batch {batch_index}/{len(batches)}] Fetching {len(batch_ids)} taxa...")

                taxa_by_id = fetch_taxa_batch(batch_ids)

                for taxon_id in batch_ids:
                    taxon = taxa_by_id.get(taxon_id)

                    if taxon is None:
                        print(f"  MISSING taxon {taxon_id} (not returned by this batch)")
                        failed += 1
                        continue

                    (
                        wikipedia_summary,
                        wikipedia_url,
                        image_url,
                        license_code,
                        attribution,
                    ) = get_species_metadata(taxon)

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


                # One delay per batch (not per species)
                time.sleep(args.delay)

            conn.commit()

            print()
            print("Backfill complete.")
            print(f"Successful: {successful}")
            print(f"Failed:     {failed}")


if __name__ == "__main__":
    main()