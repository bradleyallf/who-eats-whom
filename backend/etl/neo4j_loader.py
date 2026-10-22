"""ETL stub that pushes species + predator/prey relationships into Neo4j.

This loader no longer reads observations.csv directly. It queries Postgres
instead. postgres_loader.py must be run first for a given --etl-version. This
script reads the resulting species and observations rows out of Postgres,
works out the predator/prey pairs from the observations itself, and mirrors
them into Neo4j.
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

import psycopg
from neo4j import GraphDatabase

# Must match postgres_loader.py
ROLE_FIELD = 'field:id meant for "eater" or organism being eaten?'
PARTNER_URL_FIELD = 'field:url for "partner" observation'
# Role values that postgres_loader.py maps to "eater" (ROLE_MAPPING keys)
EATER_VALUES = ["eater", "predator"]

def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Load predator/prey graph into Neo4j from Postgres."
  )
  parser.add_argument("--dsn", required=True, help="Postgres connection string to read from.")
  parser.add_argument(
    "--etl-version",
    required=True,
    nargs="+",
    help="One or more version names previously loaded into Postgres. "
    "Use the same names as ACTIVE_ETL_VERSIONS, e.g. --etl-version local-dev 2026-08-26-api",
  )
  parser.add_argument("--uri", required=True, help="Neo4j bolt URI, e.g. bolt://neo4j:7687")
  parser.add_argument("--user", required=True, help="Neo4j username.")
  parser.add_argument("--password", required=True, help="Neo4j password.")
  return parser.parse_args()


def fetch_etl_versions(cur: psycopg.Cursor, versions: List[str]) -> Dict[str, Any]:
  """Return {"ids": [...], "version": "a+b"}, the same label main.py reports."""
  cur.execute(
    "SELECT id, version FROM etl_versions WHERE version = ANY(%s) ORDER BY id",
    (versions,),
  )
  rows = cur.fetchall()
  missing = [v for v in versions if v not in {row[1] for row in rows}]
  if missing:
    raise SystemExit(f"No etl_versions row for {missing!r}. Load them into Postgres first.")
  return {"ids": [row[0] for row in rows], "version": "+".join(row[1] for row in rows)}

# Gets all species including the ones that have no predator/prey relationships
def fetch_species(cur: psycopg.Cursor) -> List[Dict[str, Any]]:
  cur.execute(
    """
    SELECT
        taxon_id,
        scientific_name,
        common_name,
        iconic_taxon_name,
        taxon_rank
    FROM species;
    """
  )
  columns = [desc.name for desc in cur.description]
  return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_edges(
  cur: psycopg.Cursor, etl_version_ids: List[int], etl_version: str
) -> List[Dict[str, Any]]:
  cur.execute(
    # Same rules as postgres_loader.build_interactions, except that the partner
    # may be in a different version, as long as it is one of the versions passed
    # in. A self-link is ignored. Pairs are counted per (predator taxon,
    # prey taxon).
    """
    SELECT
      eater.taxon_id AS predator_taxon_id,
      partner.taxon_id AS prey_taxon_id,
      COUNT(*) AS interaction_count,
      MAX(eater.observed_at) AS latest_observation_at
    FROM observations AS eater
    JOIN observations AS partner
      ON partner.iNaturalist_url = btrim(eater.raw ->> %s)
    WHERE eater.etl_version_id = ANY(%s)
      AND partner.etl_version_id = ANY(%s)
      AND lower(btrim(eater.raw ->> %s)) = ANY(%s)
      AND partner.observation_id <> eater.observation_id
    GROUP BY eater.taxon_id, partner.taxon_id
    """,
    (PARTNER_URL_FIELD, etl_version_ids, etl_version_ids, ROLE_FIELD, EATER_VALUES),
  )
  columns = [desc.name for desc in cur.description]
  payload = []
  for row in cur.fetchall():
    record = dict(zip(columns, row))
    last_seen_at: Optional[str] = (
      record["latest_observation_at"].isoformat() if record["latest_observation_at"] else None
    )
    payload.append(
      {
        "predator_taxon_id": record["predator_taxon_id"],
        "prey_taxon_id": record["prey_taxon_id"],
        "interaction_count": record["interaction_count"],
        "last_seen_at": last_seen_at,
        "etl_version": etl_version,
      }
    )
  return payload

# Upsert Species nodes into Neo4j. Same as previous script
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

# Upsert EATS relationships between Species nodes. Same as previous script
def load_edges(tx, edge_payload: List[Dict[str, Any]]) -> None:
  tx.run(
    """
    UNWIND $edges AS edge
    MATCH (pred:Species {taxon_id: edge.predator_taxon_id})
    MATCH (prey:Species {taxon_id: edge.prey_taxon_id})
    MERGE (pred)-[r:EATS]->(prey)
    SET r.etl_version = edge.etl_version,
        r.interaction_count = edge.interaction_count,
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

  with psycopg.connect(args.dsn) as conn:
    with conn.cursor() as cur:
      etl_versions = fetch_etl_versions(cur, args.etl_version)
      species_payload = fetch_species(cur)
      edge_payload = fetch_edges(cur, etl_versions["ids"], etl_versions["version"])

  if not species_payload:
    raise SystemExit(
      f"No species found in Postgres for etl_version {args.etl_version!r}. "
    )

  driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
  with driver.session(database="neo4j") as session:
    session.execute_write(load_species, species_payload, args.etl_version)
    if edge_payload:
      session.execute_write(load_edges, edge_payload)
  driver.close()
  print(f"Loaded {len(species_payload)} species and {len(edge_payload)} edges into Neo4j from Postgres.")


if __name__ == "__main__":
  main()
