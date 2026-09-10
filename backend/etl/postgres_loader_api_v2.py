"""Load normalized Who Eats Whom observations from the iNaturalist API into PostgreSQL.

This loader is used for incremental updates.

The original CSV-based postgres_loader.py is kept separately for
initial database seeding from observations.csv.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
# from typing import Any, Dict, List, Optional

from typing import Any, Dict, List, Optional, Tuple

import psycopg


DSN = os.getenv(
    "POSTGRES_DSN",
    "postgresql://whodba:whopass@localhost:5433/who_eats_whom"
)

# The API is the source for incremental updates.
SOURCE = "iNaturalist API"

ROLE_FIELD = 'field:id meant for "eater" or organism being eaten?'
PARTNER_URL_FIELD = 'field:url for "partner" observation'

ROLE_MAPPING = {
    "eater": "eater",
    "predator": "eater",
    "thing being eaten": "thing being eaten",
    "organism being eaten": "thing being eaten",
    "prey": "thing being eaten",
}


def is_confirmed_eater(raw_value: Optional[str]) -> bool:
    """Return True only when the role is explicitly recognized as an eater.

    Missing, blank, or unrecognized role values are NOT treated as eaters.
    This prevents observations with missing role information from being
    incorrectly used as predators.
    """
    normalized = (raw_value or "").strip().lower()
    return ROLE_MAPPING.get(normalized) == "eater"


def canonical_role(raw_value: Optional[str]) -> Optional[str]:
    """Convert a recognized role to the database's canonical role.

    Returns None for missing or unrecognized roles instead of defaulting
    them to 'eater'.
    """
    normalized = (raw_value or "").strip().lower()
    return ROLE_MAPPING.get(normalized)


def parse_timestamp(value: str | None) -> Optional[datetime]:
    """Convert an iNaturalist timestamp into a Python datetime."""
    if not value:
        return None

    for fmt in (
        "%Y-%m-%d %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def ensure_etl_version(
    cur: psycopg.Cursor,
    version: str,
    row_count: int,
    notes: str = "",
) -> int:
    """Create or update the ETL version for an API load."""

    cur.execute(
        """
        INSERT INTO etl_versions (
            version,
            source_csv,
            row_count,
            notes
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (version)
        DO UPDATE SET
            loaded_at = NOW(),
            source_csv = EXCLUDED.source_csv,
            row_count = EXCLUDED.row_count,
            notes = EXCLUDED.notes
        RETURNING id
        """,
        (
            version,
            SOURCE,
            row_count,
            notes,
        ),
    )

    return cur.fetchone()[0]


def upsert_species(
    cur: psycopg.Cursor,
    rows: List[Dict[str, Any]],
) -> None:
    """Insert or update species records before observations are inserted."""

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
            row.get("license_code"),
            row.get("attribution"),
        )

    if not species_records:
        return

    cur.executemany(
        """
        INSERT INTO species (
            taxon_id,
            scientific_name,
            common_name,
            iconic_taxon_name,
            taxon_rank,
            kingdom,
            phylum,
            class_name,
            order_name,
            family_name,
            genus_name,
            wikipedia_summary,
            wikipedia_url,
            image_url,
            license_code,
            attribution
        )
        VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
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
    rows: List[Dict[str, Any]],
    etl_version_id: int,
) -> int:
    """Insert or update observations.

    Observations with no recognized role are skipped rather than being
    incorrectly classified as predators/eaters.
    """

    observation_records = []

    skipped_no_role = 0
    skipped_missing_required = 0

    for row in rows:

        observation_id = row.get("id")
        taxon_id = row.get("taxon_id")
        url = row.get("url")

        if not (observation_id and taxon_id and url):
            skipped_missing_required += 1
            continue

        raw_role = row.get(ROLE_FIELD)
        role = canonical_role(raw_role)

        # IMPORTANT:
        # Do not allow missing/unknown role information to become "eater".
        if role is None:
            skipped_no_role += 1

            print(
                f"Skipping observation {observation_id}: "
                f"no recognized role information."
            )

            continue

        observation_records.append(
            (
                int(observation_id),

                parse_timestamp(
                    row.get("time_observed_at")
                    or row.get("observed_on")
                ),

                float(row["latitude"])
                if row.get("latitude") not in (None, "")
                else None,

                float(row["longitude"])
                if row.get("longitude") not in (None, "")
                else None,

                row.get("place_guess"),
                row.get("quality_grade"),
                row.get("description"),

                role,

                int(taxon_id),
                url,
                etl_version_id,

                json.dumps(row),
            )
        )

    if observation_records:
        cur.executemany(
            """
            INSERT INTO observations (
                observation_id,
                observed_at,
                latitude,
                longitude,
                place_guess,
                quality_grade,
                description,
                role,
                taxon_id,
                iNaturalist_url,
                etl_version_id,
                raw
            )
            VALUES (
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            )
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
                etl_version_id = EXCLUDED.etl_version_id,
                raw = EXCLUDED.raw,
                updated_at = NOW()
            """,
            observation_records,
        )

    print(f"Inserted/updated observations: {len(observation_records)}")

    if skipped_no_role:
        print(
            f"Skipped observations with missing/unrecognized role: "
            f"{skipped_no_role}"
        )

    if skipped_missing_required:
        print(
            f"Skipped observations with missing required fields: "
            f"{skipped_missing_required}"
        )

    return len(observation_records)


def load_records_to_postgres(
    rows: List[Dict[str, Any]],
    etl_version: str,
    notes: str = "",
) -> None:
    """Load normalized observations from update_observations.py into PostgreSQL.

    Order:
        1. Create ETL version
        2. Upsert species
        3. Insert observations

    Interaction/aggregate processing will be added later after the
    entire PostgreSQL database can be searched for partner observations.
    """

    if not rows:
        print("No records to load into PostgreSQL.")
        return

    print("Loading new observations into PostgreSQL...")

    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:

            # ---------------------------------
            # 1. ETL version
            # ---------------------------------
            etl_version_id = ensure_etl_version(
                cur,
                version=etl_version,
                row_count=len(rows),
                notes=notes,
            )

            # ---------------------------------
            # 2. Species FIRST
            # ---------------------------------
            upsert_species(cur, rows)

            # ---------------------------------
            # 3. Observations SECOND
            # ---------------------------------
            inserted_count = insert_observations(
                cur,
                rows,
                etl_version_id,
            )

            # ---------------------------------
            # 4. Build interactions
            # ---------------------------------
            interactions = build_interactions(
                cur,
                rows,
            )

            # ---------------------------------
            # 5. Insert aggregate edges
            # ---------------------------------
            insert_aggregates(
                cur,
                interactions,
                etl_version_id,
            )


        conn.commit()

    print(
        f"PostgreSQL load complete. "
        f"Processed {inserted_count} observations."
    )

# new
def build_interactions(
    cur: psycopg.Cursor,
    rows: List[Dict[str, Any]],
) -> List[Tuple[int, int, datetime | None]]:
    """Find predator/prey interactions using the entire PostgreSQL database.

    The API batch may contain only one side of an interaction. Therefore,
    partner observations are looked up in PostgreSQL rather than only
    searching the current API batch.

    Returns:
        Tuples containing:
            (predator_taxon_id, prey_taxon_id, predator_observed_at)
    """

    interactions = []

    for row in rows:

        # Only explicitly confirmed eaters can be predators.
        if not is_confirmed_eater(row.get(ROLE_FIELD)):
            continue

        partner_url = (row.get(PARTNER_URL_FIELD) or "").strip()

        if not partner_url:
            continue

        predator_taxon_id = row.get("taxon_id")

        if not predator_taxon_id:
            continue

        # Search the ENTIRE observations table for the partner.
        cur.execute(
            """
            SELECT
                taxon_id,
                role,
                observed_at
            FROM observations
            WHERE iNaturalist_url = %s
            """,
            (partner_url,),
        )

        partner = cur.fetchone()

        if not partner:
            print(
                f"Partner observation not found in PostgreSQL: "
                f"{partner_url}"
            )
            continue

        prey_taxon_id, prey_role, prey_observed_at = partner

        # The partner must actually be classified as prey.
        if prey_role != "thing being eaten":
            print(
                f"Skipping interaction for observation {row.get('id')}: "
                f"partner is not classified as prey."
            )
            continue

        predator_observed_at = parse_timestamp(
            row.get("time_observed_at")
            or row.get("observed_on")
        )

        interactions.append(
            (
                int(predator_taxon_id),
                int(prey_taxon_id),
                predator_observed_at,
            )
        )

    print(f"Interactions found: {len(interactions)}")

    return interactions

# neww

def insert_aggregates(
    cur: psycopg.Cursor,
    interactions: List[Tuple[int, int, Optional[datetime]]],
    etl_version_id: int,
) -> None:
    """Insert or update predator/prey aggregate edges."""

    aggregates = {}

    for predator_taxon_id, prey_taxon_id, observed_at in interactions:

        key = (predator_taxon_id, prey_taxon_id)

        if key not in aggregates:
            aggregates[key] = {
                "count": 0,
                "latest": None,
            }

        aggregates[key]["count"] += 1

        current_latest = aggregates[key]["latest"]

        if observed_at and (
            current_latest is None
            or observed_at > current_latest
        ):
            aggregates[key]["latest"] = observed_at

    payloads = [
        (
            predator_taxon_id,
            prey_taxon_id,
            data["count"],
            data["latest"],
            etl_version_id,
        )
        for (predator_taxon_id, prey_taxon_id), data
        in aggregates.items()
    ]

    if not payloads:
        print("No predator/prey aggregates to insert.")
        return

    cur.executemany(
        """
        INSERT INTO predator_prey_aggregates (
            predator_taxon_id,
            prey_taxon_id,
            interaction_count,
            latest_observation_at,
            etl_version_id
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (
            predator_taxon_id,
            prey_taxon_id,
            etl_version_id
        )
        DO UPDATE SET
            interaction_count =
                predator_prey_aggregates.interaction_count
                + EXCLUDED.interaction_count,
            latest_observation_at = GREATEST(
                COALESCE(
                    predator_prey_aggregates.latest_observation_at,
                    EXCLUDED.latest_observation_at
                ),
                EXCLUDED.latest_observation_at
            ),
            updated_at = NOW()
        """,
        payloads,
    )

    print(f"Inserted/updated aggregate edges: {len(payloads)}")
