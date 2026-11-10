"""ETL that pushes species + predator/prey relationships into Neo4j.

Reads the species and observations tables out of Postgres, works out the
predator/prey pairs and their counts from the observations themselves, and
mirrors them into Neo4j. There are no ETL versions: every run recomputes the
edges from the whole observations table, so a prey or predator that arrives in
a later scheduler pull is picked up automatically.

Every load is stamped with a run_id. After the species and edges are upserted,
anything in Neo4j that was NOT part of this load (a species or predator/prey
pair that no longer exists in Postgres) is deleted, so the graph always mirrors
Postgres.

Normally this is called from fetch_observations.update_database() at the end of
every scheduler run, through load_graph(). It can still be run by hand:

    python neo4j_loader_scheduler.py --dsn <postgres dsn> --uri bolt://localhost:7687 \
        --user neo4j --password <password>
"""

from __future__ import annotations

import argparse
import uuid
from typing import Any, Dict, List, Optional, Tuple

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


# Upsert Species nodes into Neo4j, stamped with this load's run_id.
def load_species(tx, species_payload: List[Dict[str, Any]], run_id: str) -> None:
  tx.run(
    """
    UNWIND $species AS row
    MERGE (s:Species {taxon_id: row.taxon_id})
    SET s.scientific_name = row.scientific_name,
        s.common_name = row.common_name,
        s.iconic_taxon_name = row.iconic_taxon_name,
        s.taxon_rank = row.taxon_rank,
        s.run_id = $run_id,
        s.updated_at = datetime()
    """,
    species=species_payload,
    run_id=run_id,
  )


# Upsert EATS relationships between Species nodes, stamped with this load's run_id.
def load_edges(tx, edge_payload: List[Dict[str, Any]], run_id: str) -> None:
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
        r.run_id = $run_id,
        r.updated_at = datetime()
    """,
    edges=edge_payload,
    run_id=run_id,
  )


def prune_graph(tx, run_id: str) -> Tuple[int, int]:
  """Delete EATS edges and Species nodes that were not part of this load.

  Returns (edges removed, species nodes removed).
  """
  edges_removed = tx.run(
    """
    MATCH ()-[r:EATS]->()
    WHERE r.run_id IS NULL OR r.run_id <> $run_id
    DELETE r
    RETURN count(*) AS removed
    """,
    run_id=run_id,
  ).single()["removed"]

  species_removed = tx.run(
    """
    MATCH (s:Species)
    WHERE s.run_id IS NULL OR s.run_id <> $run_id
    DETACH DELETE s
    RETURN count(*) AS removed
    """,
    run_id=run_id,
  ).single()["removed"]

  return edges_removed, species_removed


def load_graph(dsn: str, uri: str, user: str, password: str) -> Tuple[int, int]:
  """Rebuild the Neo4j graph from Postgres.

  Reads every species and recomputes every predator/prey edge, upserts them
  into Neo4j, then removes anything from an earlier load that is no longer in
  Postgres. Safe to run repeatedly. If Postgres has no species the function
  returns without touching Neo4j, so an empty database can never wipe the graph.

  Returns:
    (number of species loaded, number of edges loaded)
  """
  with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
      species_payload = fetch_species(cur)
      edge_payload = fetch_edges(cur)

  if not species_payload:
    print("No species found in Postgres; nothing to load into Neo4j.")
    return 0, 0

  run_id = uuid.uuid4().hex

  with GraphDatabase.driver(uri, auth=(user, password)) as driver:
    with driver.session(database="neo4j") as session:
      session.execute_write(load_species, species_payload, run_id)
      if edge_payload:
        session.execute_write(load_edges, edge_payload, run_id)
      # Only reached if both loads succeeded.
      edges_removed, species_removed = session.execute_write(prune_graph, run_id)

  print(f"Loaded {len(species_payload)} species and {len(edge_payload)} edges into Neo4j from Postgres.")
  print(f"Removed {edges_removed} stale edges and {species_removed} stale species nodes.")
  return len(species_payload), len(edge_payload)


def main() -> None:
  args = parse_args()
  load_graph(args.dsn, args.uri, args.user, args.password)


if __name__ == "__main__":
  main()