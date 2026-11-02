"""Load normalized Who Eats Whom observations from the iNaturalist API into PostgreSQL.

There is no CSV seeding and no ETL-version tracking any more. Everything comes
from the API, and the scheduler's progress is stored in ``scheduler_state``.
Predator/prey aggregates are computed by the Neo4j loader, not here.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg

OBS_ID_RE = re.compile(r"/observations/(\d+)")

DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://whodba:whopass@localhost:5433/who_eats_whom_scheduler"
)

SOURCE = "iNaturalist API"

# Row name in scheduler_state, and the date used if that row is missing.
SCHEDULER_NAME = "inat_import"
EPOCH_START = datetime(1645, 8, 26, tzinfo=timezone.utc)

ROLE_FIELD = 'field:id meant for "eater" or organism being eaten?'
PARTNER_URL_FIELD = 'field:url for "partner" observation'

ROLE_MAPPING = {
    "eater": "eater",
    "predator": "eater",
    "thing being eaten": "thing being eaten",
    "organism being eaten": "thing being eaten",
    "prey": "thing being eaten",
}


def extract_observation_id(url: Optional[str]) -> Optional[int]:
    """Extract the numeric observation ID from an iNaturalist observation URL."""
    match = OBS_ID_RE.search(url or "")
    return int(match.group(1)) if match else None


def canonical_role(raw_value: Optional[str]) -> Optional[str]:
    """Convert a raw role value to "eater" / "thing being eaten".

    Returns None for missing or unrecognized values (never defaults to eater).
    """
    normalized = (raw_value or "").strip().lower()
    return ROLE_MAPPING.get(normalized)


def parse_timestamp(value) -> Optional[datetime]:
    """Parse iNaturalist timestamps (ISO 8601, CSV style, or date-only) into UTC-aware datetimes."""
    if not value:
        return None
    s = str(value).strip()

    dt = None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S %z"):
            try:
                dt = datetime.strptime(s, fmt)
                break
            except ValueError:
                continue

    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def observed_timestamp(row: Dict[str, Any]) -> Optional[datetime]:
    # Fall back to the date if the timestamp is missing OR unparseable.
    return parse_timestamp(row.get("time_observed_at")) or parse_timestamp(row.get("observed_on"))


# ---------------------------------------------------------------------------
# Scheduler state
# ---------------------------------------------------------------------------

def get_last_fetched() -> datetime:
    """Return the last successful fetch time (EPOCH_START if never run)."""
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_fetched FROM scheduler_state WHERE name = %s",
                (SCHEDULER_NAME,),
            )
            row = cur.fetchone()
    return row[0] if row else EPOCH_START


def set_last_fetched(value: datetime) -> None:
    """Store the last successful fetch time."""
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scheduler_state (name, last_fetched)
                VALUES (%s, %s)
                ON CONFLICT (name)
                DO UPDATE SET last_fetched = EXCLUDED.last_fetched,
                              updated_at = NOW()
                """,
                (SCHEDULER_NAME, value),
            )


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def filter_valid_rows(
    rows: List[Dict[str, Any]],
) -> List[Tuple[Dict[str, Any], str]]:
    """Keep rows that have id, taxon_id, url and a recognized role.

    Returns (row, canonical_role) pairs. Rows with a missing/unknown role are
    skipped so they can never be misclassified as eaters.
    """
    valid = []
    skipped_missing = 0
    skipped_role = 0

    for row in rows:
        if not (row.get("id") and row.get("taxon_id") and row.get("url")):
            skipped_missing += 1
            continue

        role = canonical_role(row.get(ROLE_FIELD))
        if role is None:
            skipped_role += 1
            print(f"Skipping observation {row.get('id')}: no recognized role information.")
            continue

        valid.append((row, role))

    if skipped_missing:
        print(f"Skipped observations with missing required fields: {skipped_missing}")
    if skipped_role:
        print(f"Skipped observations with missing/unrecognized role: {skipped_role}")

    return valid


def upsert_species(cur: psycopg.Cursor, rows: List[Dict[str, Any]]) -> None:
    """Insert or update species referenced by the rows (de-duplicated by taxon_id).

    Must run before insert_observations() so the taxon_id foreign key is satisfied.
    """
    species_records = {}

    for row in rows:
        taxon_id = row.get("taxon_id")
        if not taxon_id:
            continue

        species_records[taxon_id] = (
            int(taxon_id),
            row.get("scientific_name"),
            row.get("common_name"),
            row.get("iconic_taxon_name"),
            row.get("taxon_rank"),
            row.get("taxon_kingdom_name"),
            row.get("taxon_phylum_name"),
            row.get("taxon_class_name"),
            row.get("taxon_order_name"),
            row.get("taxon_family_name"),
            row.get("taxon_genus_name"),
            row.get("wikipedia_summary"),
            row.get("wikipedia_url"),
            row.get("image_url"),
            row.get("species_license_code"),
            row.get("species_attribution"),
        )

    if not species_records:
        return

    cur.executemany(
        """
        INSERT INTO species (
            taxon_id, scientific_name, common_name, iconic_taxon_name,
            taxon_rank, kingdom, phylum, class_name, order_name,
            family_name, genus_name, wikipedia_summary, wikipedia_url,
            image_url, license_code, attribution
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (taxon_id)
        DO UPDATE SET
            scientific_name = EXCLUDED.scientific_name,
            common_name = EXCLUDED.common_name,
            iconic_taxon_name = EXCLUDED.iconic_taxon_name,
            taxon_rank = EXCLUDED.taxon_rank,
            kingdom = EXCLUDED.kingdom,
            phylum = EXCLUDED.phylum,
            class_name = EXCLUDED.class_name,
            order_name = EXCLUDED.order_name,
            family_name = EXCLUDED.family_name,
            genus_name = EXCLUDED.genus_name,
            wikipedia_summary = EXCLUDED.wikipedia_summary,
            wikipedia_url = EXCLUDED.wikipedia_url,
            image_url = EXCLUDED.image_url,
            license_code = EXCLUDED.license_code,
            attribution = EXCLUDED.attribution,
            updated_at = NOW()
        """,
        list(species_records.values()),
    )


def insert_observations(
    cur: psycopg.Cursor,
    valid: List[Tuple[Dict[str, Any], str]],
    updated_due_to: Optional[str] = None,
) -> int:
    """Insert or update observations (idempotent on observation_id)."""
    records = []

    for row, role in valid:
        lat = row.get("latitude")
        lon = row.get("longitude")

        records.append((
            int(row["id"]),
            observed_timestamp(row),
            float(lat) if lat not in (None, "") else None,
            float(lon) if lon not in (None, "") else None,
            row.get("place_guess"),
            row.get("quality_grade"),
            row.get("description"),
            role,
            int(row["taxon_id"]),
            row["url"],
            row.get("observation_image_url"),
            row.get("photo_license_code"),
            row.get("photo_attribution"),
            row.get("inat_pulled_at"),
            row.get("inat_api_call"),
            SOURCE,
            updated_due_to,
            json.dumps(row, default=str),
        ))

    if records:
        cur.executemany(
            """
            INSERT INTO observations (
                observation_id, observed_at, latitude, longitude,
                place_guess, quality_grade, description, role, taxon_id,
                iNaturalist_url, image_url, photo_license_code,
                photo_attribution, inat_pulled_at, inat_api_call,
                source, updated_due_to, raw
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (observation_id)
            DO UPDATE SET
                observed_at = EXCLUDED.observed_at,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                place_guess = EXCLUDED.place_guess,
                quality_grade = EXCLUDED.quality_grade,
                description = EXCLUDED.description,
                role = EXCLUDED.role,
                taxon_id = EXCLUDED.taxon_id,
                iNaturalist_url = EXCLUDED.iNaturalist_url,
                image_url = EXCLUDED.image_url,
                photo_license_code = EXCLUDED.photo_license_code,
                photo_attribution = EXCLUDED.photo_attribution,
                inat_pulled_at = EXCLUDED.inat_pulled_at,
                inat_api_call = EXCLUDED.inat_api_call,
                source = EXCLUDED.source,
                updated_due_to = EXCLUDED.updated_due_to,
                raw = EXCLUDED.raw,
                updated_at = NOW()
            """,
            records,
        )

    print(f"Inserted/updated observations: {len(records)}")
    return len(records)


def load_records_to_postgres(
        rows: List[Dict[str, Any]],
        updated_due_to: Optional[str] = None,
) -> int:
    """Load one batch of normalized observations in a single transaction.

    Order: species first (FK), then observations. Returns the number of
    observations written.
    """
    if not rows:
        print("No records to load into PostgreSQL.")
        return 0

    valid = filter_valid_rows(rows)
    if not valid:
        return 0

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            upsert_species(cur, [row for row, _ in valid])
            count = insert_observations(cur, valid, updated_due_to)
        conn.commit()

    return count