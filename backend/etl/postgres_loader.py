"""ETL stub that loads Who Eats Whom observations into Postgres."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg

ROLE_FIELD = 'field:id meant for "eater" or organism being eaten?'
PARTNER_URL_FIELD = 'field:url for "partner" observation'

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = REPO_ROOT / "observations.csv"

ROLE_MAPPING = {
  "eater": "eater",
  "predator": "eater",
  "thing being eaten": "thing being eaten",
  "organism being eaten": "thing being eaten",
  "prey": "thing being eaten",
}


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Load observations.csv into Postgres.")
  parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to observations CSV.")
  parser.add_argument("--etl-version", required=True, help="Version label for this load (e.g. 2024-11-24).")
  parser.add_argument("--dsn", required=True, help="Postgres connection string.")
  parser.add_argument("--notes", default="", help="Optional notes stored alongside etl_version.")
  return parser.parse_args()


def read_rows(csv_path: Path) -> List[Dict[str, Any]]:
  with csv_path.open("r", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    return [row for row in reader]


def canonical_role(raw_value: Optional[str]) -> str:
  normalized = (raw_value or "").strip().lower()
  return ROLE_MAPPING.get(normalized, "eater")

def is_confirmed_eater(raw_value: Optional[str]) -> bool:
  """Strict check used only when building predator/prey pairs. Unlike
  canonical_role(), a blank or unrecognized role field is NOT treated as an
  eater here -- it's excluded entirely, matching the old CSV-based Neo4j
  loader's behavior of dropping anything that isn't a recognized eater
  value, so missing data can't silently fabricate an interaction."""
  normalized = (raw_value or "").strip().lower()
  return ROLE_MAPPING.get(normalized) == "eater"


def parse_timestamp(value: str | None) -> Optional[datetime]:
  if not value:
    return None
  for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d"):
    try:
      return datetime.strptime(value, fmt)
    except ValueError:
      continue
  return None


def ensure_etl_version(cur: psycopg.Cursor, version: str, csv_path: Path, row_count: int, notes: str) -> int:
  cur.execute(
    """
    INSERT INTO etl_versions (version, source_csv, row_count, notes)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (version)
    DO UPDATE SET
      loaded_at = NOW(),
      source_csv = EXCLUDED.source_csv,
      row_count = EXCLUDED.row_count,
      notes = EXCLUDED.notes
    RETURNING id
    """,
    (version, str(csv_path), row_count, notes),
  )
  etl_version_id = cur.fetchone()[0]
  return etl_version_id


def upsert_species(cur: psycopg.Cursor, rows: List[Dict[str, Any]]) -> None:
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
    )

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
      image_url
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (taxon_id) DO UPDATE SET
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
      updated_at = NOW()
    """,
    list(species_records.values()),
  )


def build_interactions(rows: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
  lookup = {row.get("url", "").strip(): row for row in rows if row.get("url")}
  interactions = []
  for row in rows:
    role = is_confirmed_eater(row.get(ROLE_FIELD))
    if not role:
      continue
    partner_url = (row.get(PARTNER_URL_FIELD) or "").strip()
    if not partner_url:
      continue
    partner = lookup.get(partner_url)
    if not partner:
      continue
    interactions.append((row, partner))
  return interactions


def insert_observations(cur: psycopg.Cursor, rows: List[Dict[str, Any]], etl_version_id: int) -> None:
  observation_records = []
  for row in rows:
    observation_id = row.get("id")
    taxon_id = row.get("taxon_id")
    url = row.get("url")
    if not (observation_id and taxon_id and url):
      continue
    observation_records.append(
      (
        int(observation_id),
        parse_timestamp(row.get("time_observed_at") or row.get("observed_on")),
        float(row["latitude"]) if row.get("latitude") else None,
        float(row["longitude"]) if row.get("longitude") else None,
        row.get("place_guess"),
        row.get("quality_grade"),
        row.get("description"),
        canonical_role(row.get(ROLE_FIELD)),
        int(taxon_id),
        url,
        etl_version_id,
        json.dumps(row),
      )
    )

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
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (observation_id) DO UPDATE SET
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


def insert_aggregates(cur: psycopg.Cursor, interactions: List[Tuple[Dict[str, Any], Dict[str, Any]]], etl_version_id: int) -> None:
  aggregates: Dict[Tuple[int, int], Dict[str, Any]] = defaultdict(lambda: {"count": 0, "latest": None})
  for predator, prey in interactions:
    predator_taxon = predator.get("taxon_id")
    prey_taxon = prey.get("taxon_id")
    if not (predator_taxon and prey_taxon):
      continue
    observed_at = parse_timestamp(predator.get("time_observed_at") or predator.get("observed_on"))
    key = (int(predator_taxon), int(prey_taxon))
    aggregates[key]["count"] += 1
    current_latest = aggregates[key]["latest"]
    if observed_at and (current_latest is None or observed_at > current_latest):
      aggregates[key]["latest"] = observed_at

  payloads = [
    (pred, prey, data["count"], data["latest"], etl_version_id) for (pred, prey), data in aggregates.items()
  ]

  cur.executemany(
    """
    INSERT INTO predator_prey_aggregates (
      predator_taxon_id,
      prey_taxon_id,
      interaction_count,
      latest_observation_at,
      etl_version_id
    ) VALUES (%s,%s,%s,%s,%s)
    ON CONFLICT (predator_taxon_id, prey_taxon_id, etl_version_id) DO UPDATE SET
      interaction_count = EXCLUDED.interaction_count,
      latest_observation_at = GREATEST(
        COALESCE(predator_prey_aggregates.latest_observation_at, EXCLUDED.latest_observation_at),
        EXCLUDED.latest_observation_at
      ),
      updated_at = NOW()
    """,
    payloads,
  )


def main() -> None:
  args = parse_args()
  rows = read_rows(args.csv)
  if not rows:
    raise SystemExit("No rows found in CSV.")

  with psycopg.connect(args.dsn) as conn:
    with conn.cursor() as cur:
      etl_version_id = ensure_etl_version(cur, args.etl_version, args.csv, len(rows), args.notes)
      upsert_species(cur, rows)
      insert_observations(cur, rows, etl_version_id)
      interactions = build_interactions(rows)
      insert_aggregates(cur, interactions, etl_version_id)
    conn.commit()
  print(f"Loaded {len(rows)} rows for version {args.etl_version}")


if __name__ == "__main__":
  main()
