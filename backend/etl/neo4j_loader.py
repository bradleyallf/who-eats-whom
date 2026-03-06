"""ETL stub that pushes species + predator/prey relationships into Neo4j."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from neo4j import GraphDatabase

ROLE_FIELD = 'field:id meant for "eater" or organism being eaten?'
PARTNER_URL_FIELD = 'field:url for "partner" observation'

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = REPO_ROOT / "observations.csv"


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Load predator/prey graph into Neo4j.")
  parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to observations CSV.")
  parser.add_argument("--etl-version", required=True, help="Version string shared with Postgres ETL.")
  parser.add_argument("--uri", required=True, help="Neo4j bolt URI, e.g. bolt://neo4j:7687")
  parser.add_argument("--user", required=True, help="Neo4j username.")
  parser.add_argument("--password", required=True, help="Neo4j password.")
  return parser.parse_args()


def read_rows(csv_path: Path) -> List[Dict[str, Any]]:
  with csv_path.open("r", encoding="utf-8") as handle:
    return list(csv.DictReader(handle))


def build_species_payload(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
  species: Dict[str, Dict[str, Any]] = {}
  for row in rows:
    taxon_id = row.get("taxon_id")
    if not taxon_id:
      continue
    species[taxon_id] = {
      "taxon_id": int(taxon_id),
      "scientific_name": row.get("scientific_name"),
      "common_name": row.get("common_name"),
      "iconic_taxon_name": row.get("iconic_taxon_name"),
      "taxon_rank": row.get("taxon_rank"),
    }
  return list(species.values())


def parse_timestamp(value: Optional[str]) -> Optional[str]:
  if not value:
    return None
  for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S %z", "%Y-%m-%d"):
    try:
      return datetime.strptime(value, fmt).isoformat()
    except ValueError:
      continue
  return None


def build_interaction_payload(rows: List[Dict[str, Any]], etl_version: str) -> List[Dict[str, Any]]:
  lookup = {row.get("url", "").strip(): row for row in rows if row.get("url")}
  aggregates: Dict[Tuple[int, int], Dict[str, Any]] = defaultdict(lambda: {"count": 0, "last_seen_at": None})

  for row in rows:
    role = (row.get(ROLE_FIELD) or "").strip().lower()
    if role != "eater":
      continue
    partner_url = (row.get(PARTNER_URL_FIELD) or "").strip()
    partner = lookup.get(partner_url)
    if not partner:
      continue
    predator_taxon = row.get("taxon_id")
    prey_taxon = partner.get("taxon_id")
    if not (predator_taxon and prey_taxon):
      continue
    key = (int(predator_taxon), int(prey_taxon))
    aggregates[key]["count"] += 1
    observed_at = parse_timestamp(row.get("time_observed_at") or row.get("observed_on"))
    current = aggregates[key]["last_seen_at"]
    if observed_at and (current is None or observed_at > current):
      aggregates[key]["last_seen_at"] = observed_at

  payload = []
  for (predator_taxon_id, prey_taxon_id), data in aggregates.items():
    payload.append(
      {
        "predator_taxon_id": predator_taxon_id,
        "prey_taxon_id": prey_taxon_id,
        "interaction_count": data["count"],
        "last_seen_at": data["last_seen_at"],
        "etl_version": etl_version,
      }
    )
  return payload


def load_species(tx, species_payload: List[Dict[str, Any]], etl_version: str) -> None:
  tx.run(
    """
    UNWIND $species AS row
    MERGE (s:Species {taxon_id: row.taxon_id})
    SET s.scientific_name = row.scientific_name,
        s.common_name = row.common_name,
        s.iconic_taxon_name = row.iconic_taxon_name,
        s.taxon_rank = row.taxon_rank,
        s.etl_version = $etl_version,
        s.updated_at = datetime()
    """,
    species=species_payload,
    etl_version=etl_version,
  )


def load_edges(tx, edge_payload: List[Dict[str, Any]]) -> None:
  tx.run(
    """
    UNWIND $edges AS edge
    MATCH (pred:Species {taxon_id: edge.predator_taxon_id})
    MATCH (prey:Species {taxon_id: edge.prey_taxon_id})
    MERGE (pred)-[r:EATS {etl_version: edge.etl_version}]->(prey)
    SET r.interaction_count = edge.interaction_count,
        r.last_seen_at = CASE
          WHEN edge.last_seen_at IS NULL THEN r.last_seen_at
          ELSE datetime(edge.last_seen_at)
        END,
        r.updated_at = datetime()
    """,
    edges=edge_payload,
  )


def main() -> None:
  args = parse_args()
  rows = read_rows(args.csv)
  if not rows:
    raise SystemExit("No rows found in CSV.")

  species_payload = build_species_payload(rows)
  edge_payload = build_interaction_payload(rows, args.etl_version)

  driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
  with driver.session(database="neo4j") as session:
    if species_payload:
      session.execute_write(load_species, species_payload, args.etl_version)
    if edge_payload:
      session.execute_write(load_edges, edge_payload)
  driver.close()
  print(f"Loaded {len(species_payload)} species and {len(edge_payload)} edges into Neo4j.")


if __name__ == "__main__":
  main()
