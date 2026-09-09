"""ETL stub that pushes species + predator/prey relationships into Neo4j.

This loader no longer reads observations.csv directly. It queries postgres instead. postgres_loader.py must be run first for a given
--etl-version, and this script reads the resulting species and
predator_prey_aggregates rows out of Postgres and mirrors them into Neo4j..
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

import psycopg
from neo4j import GraphDatabase


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Load predator/prey graph into Neo4j from Postgres."
  )
  parser.add_argument("--dsn", required=True, help="Postgres connection string to read from.")
  parser.add_argument(
    "--etl-version",
    required=True,
    help="Version string previously loaded into Postgres via postgres_loader.py.",
  )
  parser.add_argument("--uri", required=True, help="Neo4j bolt URI, e.g. bolt://neo4j:7687")
  parser.add_argument("--user", required=True, help="Neo4j username.")
  parser.add_argument("--password", required=True, help="Neo4j password.")
  return parser.parse_args()


def fetch_etl_version_id(cur: psycopg.Cursor, version: str) -> int:
  cur.execute("SELECT id FROM etl_versions WHERE version = %s", (version,))
  row = cur.fetchone()
  if row is None:
    raise SystemExit(
      f"No etl_versions row for {version!r}. Run postgres_loader.py --etl-version "
      f"{version} first."
    )
  return row[0]

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


def fetch_aggregates(
  cur: psycopg.Cursor, etl_version_id: int, etl_version: str
) -> List[Dict[str, Any]]:
  cur.execute(
    #Relationships are versioned, so only load aggregates produced by the requested ETL run
    """
    SELECT predator_taxon_id, prey_taxon_id, interaction_count, latest_observation_at
    FROM predator_prey_aggregates
    WHERE etl_version_id = %s
    """,
    (etl_version_id,),
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

  with psycopg.connect(args.dsn) as conn:
    with conn.cursor() as cur:
      etl_version_id = fetch_etl_version_id(cur, args.etl_version)
      species_payload = fetch_species(cur)
      edge_payload = fetch_aggregates(cur, etl_version_id, args.etl_version)

  if not species_payload:
    raise SystemExit(
      f"No species found in Postgres for etl_version {args.etl_version!r}. "
      f"Did postgres_loader.py actually produce any predator/prey pairs?"
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
