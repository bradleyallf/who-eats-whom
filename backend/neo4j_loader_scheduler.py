"""ETL that pushes species + predator/prey relationships into Neo4j.

Reads the species and observations tables out of Postgres, works out the
predator/prey pairs and their counts from the observations themselves, and
mirrors them into Neo4j. There are no ETL versions: every run recomputes the
edges from the whole observations table, so a prey or predator that arrives in
a later scheduler pull is picked up automatically.

Run the scheduler (fetch_observations) first so Postgres is up to date.
"""

from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

import psycopg
from neo4j import GraphDatabase

# Must match postgres_loader_api_v2.py
PARTNER_URL_FIELD = 'field:url for "partner" observation'


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
    description="Load predator/prey graph into Neo4j from Postgres."
  )
  parser.add_argument("--dsn", required=True, help="Postgres connection string to read from.")
  parser.add_argument("--uri", required=True, help="Neo4j bolt URI, e.g. bolt://localhost:7687")
  parser.add_argument("--user", required=True, help="Neo4j username.")
  parser.add_argument("--password", required=True, help="Neo4j password.")
  return parser.parse_args()


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


def fetch_edges(cur: psycopg.Cursor) -> List[Dict[str, Any]]:
  # Each eater observation stores its partner's iNaturalist URL in raw JSON.
  # The observation ID is pulled out of that URL and joined to observations
  # by primary key, so differences in URL formatting don't matter. The partner
  # must be a "thing being eaten", and an observation linked to itself is
  # ignored. Pairs are counted per (predator taxon, prey taxon).
  cur.execute(
    """
    SELECT
      eater.taxon_id AS predator_taxon_id,
      partner.taxon_id AS prey_taxon_id,
      COUNT(*) AS interaction_count,
      MAX(eater.observed_at) AS latest_observation_at
    FROM observations AS eater
    JOIN observations AS partner
      ON partner.observation_id =
         (substring(eater.raw ->> %s from '/observations/([0-9]+)'))::bigint
    WHERE eater.role = 'eater'
      AND partner.role = 'thing being eaten'
      AND eater.observation_id <> partner.observation_id
    GROUP BY eater.taxon_id, partner.taxon_id
    """,
    (PARTNER_URL_FIELD,),
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
      }
    )
  return payload


# Upsert Species nodes into Neo4j.
def load_species(tx, species_payload: List[Dict[str, Any]]) -> None:
  tx.run(
    """
    UNWIND $species AS row
    MERGE (s:Species {taxon_id: row.taxon_id})
    SET s.scientific_name = row.scientific_name,
        s.common_name = row.common_name,
        s.iconic_taxon_name = row.iconic_taxon_name,
        s.taxon_rank = row.taxon_rank,
        s.updated_at = datetime()
    """,
    species=species_payload,
  )


# Upsert EATS relationships between Species nodes.
def load_edges(tx, edge_payload: List[Dict[str, Any]]) -> None:
  tx.run(
    """
    UNWIND $edges AS edge
    MATCH (pred:Species {taxon_id: edge.predator_taxon_id})
    MATCH (prey:Species {taxon_id: edge.prey_taxon_id})
    MERGE (pred)-[r:EATS]->(prey)
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
      species_payload = fetch_species(cur)
      edge_payload = fetch_edges(cur)

  if not species_payload:
    raise SystemExit("No species found in Postgres. Run the scheduler first.")

  driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
  with driver.session(database="neo4j") as session:
    session.execute_write(load_species, species_payload)
    if edge_payload:
      session.execute_write(load_edges, edge_payload)
  driver.close()
  print(f"Loaded {len(species_payload)} species and {len(edge_payload)} edges into Neo4j from Postgres.")


if __name__ == "__main__":
  main()