"""Remove observations from Postgres that no longer qualify on iNaturalist.

The incremental scheduler only upserts what iNaturalist currently returns, so
an observation that later loses research grade or leaves the who-eats-whom
project is never touched again and its old row stays. This step fixes that:

    1. Fetch the IDs of every observation that currently qualifies
       (research grade, who-eats-whom project). IDs only, so it is cheap.
    2. Compare with the IDs stored in Postgres.
    3. Delete stored observations that are not on the current list, plus any
       species left with no observations.

Safety checks (nothing is deleted if one fails):
    * iNaturalist returned no IDs at all.
    * The number of IDs fetched does not match the total iNaturalist reports,
      which would mean the listing was cut short.
    * More than 5% of stored observations (minimum 25) would be deleted.

It is called from fetch_observations.update_database() after the Postgres load
and before the Neo4j load. It can also be run by hand:

    python prune_stale_observations.py --dry-run    # list stale observations only
    python prune_stale_observations.py              # delete them
    python prune_stale_observations.py --force      # skip the 5% limit
"""

import argparse
import time

import psycopg
import requests

from postgres_loader_api_v2 import DSN

INATURALIST_OBSERVATIONS_URL = "https://api.inaturalist.org/v1/observations"
HEADERS = {"User-Agent": "Who-Eats-Whom/1.0"}
PER_PAGE = 200
PAUSE_SECONDS = 1.0

# Safety limits.
MAX_DELETE_FRACTION = 0.05   # refuse to delete more than 5% of stored observations...
MIN_DELETE_ALLOWED = 25      # ...but always allow at least this many
TOTAL_TOLERANCE_FRACTION = 0.01
TOTAL_TOLERANCE_MIN = 10


class PruneAborted(Exception):
    """Raised when a safety check fails. Nothing has been deleted."""


def _get(url, params, timeout=60, max_retries=5):
    """GET with exponential backoff for network errors, 429s and 5xx responses."""
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                url, params=params, headers=HEADERS, timeout=timeout
            )
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(
                    f"HTTP {response.status_code}", response=response
                )
            response.raise_for_status()
            return response

        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            if status and 400 <= status < 500 and status != 429:
                raise
            if attempt == max_retries:
                raise
            wait = 2 ** attempt
            print(f"  Request failed ({exc.__class__.__name__}); "
                  f"retry {attempt}/{max_retries - 1} in {wait}s...")
            time.sleep(wait)


def fetch_current_ids():
    """Return (set of IDs, total reported by iNaturalist) for every observation
    that currently qualifies: research grade and in the who-eats-whom project.

    Observations without an eater/prey role are included here, since they still
    qualify on iNaturalist; they simply were never stored in Postgres.
    """
    ids = set()
    total_reported = None
    last_id = 0

    while True:
        params = {
            "project_id": "who-eats-whom",
            "quality_grade": "research",
            "order_by": "id",
            "order": "asc",
            "id_above": last_id,
            "per_page": PER_PAGE,
            "only_id": "true",  # IDs only; if ignored, full records still work
        }

        data = _get(INATURALIST_OBSERVATIONS_URL, params).json()

        if total_reported is None:
            total_reported = data.get("total_results")

        results = data.get("results", [])
        if not results:
            break

        ids.update(r["id"] for r in results)
        last_id = max(r["id"] for r in results)

        if len(results) < PER_PAGE:
            break

        time.sleep(PAUSE_SECONDS)

    return ids, total_reported


def fetch_stored_ids():
    """Return the set of observation IDs currently stored in Postgres."""
    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute("SELECT observation_id FROM observations")
        return {row[0] for row in cur.fetchall()}


def find_stale(stored, current, total_reported, force=False):
    """Return the sorted list of stored IDs that no longer qualify.

    Raises PruneAborted if a safety check fails.
    """
    if not current:
        raise PruneAborted(
            "iNaturalist returned no observations; refusing to delete anything."
        )

    if total_reported is not None:
        tolerance = max(
            TOTAL_TOLERANCE_MIN, int(TOTAL_TOLERANCE_FRACTION * total_reported)
        )
        if abs(len(current) - total_reported) > tolerance:
            raise PruneAborted(
                f"Fetched {len(current)} IDs but iNaturalist reports "
                f"{total_reported}; the list looks incomplete."
            )

    stale = stored - current

    limit = max(MIN_DELETE_ALLOWED, int(MAX_DELETE_FRACTION * len(stored)))
    if len(stale) > limit and not force:
        raise PruneAborted(
            f"{len(stale)} observations would be deleted (limit {limit}). "
            f"Run with --force if that is expected."
        )

    return sorted(stale)


def delete_stale(stale_ids):
    """Delete the given observations, then any species with no observations left.

    Returns (observations deleted, species deleted). One transaction.
    """
    if not stale_ids:
        return 0, 0

    with psycopg.connect(DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM observations WHERE observation_id = ANY(%s)",
            (stale_ids,),
        )
        deleted_observations = cur.rowcount

        cur.execute(
            """
            DELETE FROM species s
            WHERE NOT EXISTS (
                SELECT 1 FROM observations o WHERE o.taxon_id = s.taxon_id
            )
            """
        )
        deleted_species = cur.rowcount

        conn.commit()

    return deleted_observations, deleted_species


def prune_stale_observations(dry_run=False, force=False):
    """Remove stored observations that no longer qualify. Returns how many were deleted."""
    print("Checking stored observations against iNaturalist...")

    stored = fetch_stored_ids()
    current, total_reported = fetch_current_ids()
    print(f"  Stored in Postgres: {len(stored)}")
    print(f"  Currently eligible on iNaturalist: {len(current)} "
          f"(includes observations with no eater/prey role, which are never stored)")

    stale = find_stale(stored, current, total_reported, force=force)

    if not stale:
        print("  No stale observations.")
        return 0

    print(f"  {len(stale)} stale observations (no longer research grade or in the project):")
    for obs_id in stale[:50]:
        print(f"    https://www.inaturalist.org/observations/{obs_id}")
    if len(stale) > 50:
        print(f"    ... and {len(stale) - 50} more")

    if dry_run:
        print("  Dry run: nothing deleted.")
        return 0

    deleted_observations, deleted_species = delete_stale(stale)
    print(f"  Deleted {deleted_observations} observations and "
          f"{deleted_species} species left with no observations.")
    return deleted_observations


def main():
    parser = argparse.ArgumentParser(
        description="Remove observations that no longer qualify on iNaturalist."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="List stale observations without deleting anything.")
    parser.add_argument("--force", action="store_true",
                        help="Skip the 5%% deletion limit.")
    args = parser.parse_args()

    try:
        prune_stale_observations(dry_run=args.dry_run, force=args.force)
    except PruneAborted as exc:
        raise SystemExit(f"Aborted, nothing deleted: {exc}")


if __name__ == "__main__":
    main()