"""
Endpoint tests for the Who Eats Whom backend (FastAPI) -- Layer 5: Predator-prey.

  Layer 5: Predator-Prey Endpoint
    GET /api/v1/predator-prey

Conventions used throughout this file:
  * Tests call the API in-process through FastAPI's TestClient, so no separate
    server needs to be started.
  * Nothing is faked and nothing is written. The tests run against the real
    Postgres, Neo4j and Redis configured through the same environment variables
    the app reads (POSTGRES_DSN, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    REDIS_URL). Tests only ever read.
  * If any of those are not set, every test in this file is skipped.
  * This endpoint reads its pairs from Neo4j (EATS relationships between
    Species nodes), not from Postgres. So the expected values in these tests
    come from read-only Cypher queries on the real Neo4j. Postgres is only used
    for the ETL version label (L5-010) and for the species names (L5-028 and
    L5-029).
  * Where a test needs a particular kind of predator (one with many prey, one
    whose prey have different counts, one that is also prey of something else),
    it first asks Neo4j for one, so it keeps working when your data changes. If
    the graph has no such species, the test is skipped and says why.
  * Test names follow the plain-English test IDs, e.g. test_L5_024_...
    covers test case L5-024.

Not tested (the real data / the endpoint cannot support them):
  L5-011 (no aggregate has a null latest_observation_at), L5-017 (no pair exists
  in two versions), L5-019 (no predator has 100+ prey; the most is 39), L5-025
  (needs an empty etl_versions table), L5-026 (only one version exists locally)
  and L5-031 (the expectation is wrong: 39 aggregates have predator = prey, so a
  species can be both predator and prey in the same pair).

Differences from the plain-English cases:
  * The species ids come from Neo4j instead of the fixed 41641, 12345 and 99999
    in the plain-English cases, except in the validation cases (L5-005, L5-006,
    L5-007, L5-008, L5-022, L5-023, L5-027) where the id does not matter.
  * L5-021 expects "at most 500" results. It is tested as exactly
    min(500, number of prey the predator has), which is stricter and works for
    any data size.
  * L5-018 and L5-024 compare interaction_count values only, not which prey
    comes first, because the endpoint has no tie-breaker: pairs with the same
    count can come back in any order.
  * L5-026 and L5-017 would also not hold if more versions were loaded: the
    endpoint only uses etl_version to check that the version exists and to label
    the response. Its Cypher query does not filter pairs by version.

Run all tests - python -m pytest backend/tests/ -v
Run one test - python -m pytest backend/tests/test_endpoints_L5.py::{name of the test} -v
"""
import psycopg

import pytest

from fastapi.testclient import TestClient
from neo4j import GraphDatabase

import backend.main as main_module
from backend.main import app


# The real service addresses, read once when this file is imported. They come
# from the same env vars the app uses. None means not set.
REAL_POSTGRES_DSN = main_module.POSTGRES_DSN
REAL_NEO4J = {
  "uri": main_module.NEO4J_URI,
  "user": main_module.NEO4J_USER,
  "password": main_module.NEO4J_PASSWORD,
}

URL = "/api/v1/predator-prey"

# Used only where the id does not matter (the request is rejected before any
# data is read).
ANY_TAXON = 41641

# Fields every result must have (L5-009).
REQUIRED_FIELDS = {
  "predator_taxon_id",
  "predator_scientific_name",
  "prey_taxon_id",
  "prey_scientific_name",
  "interaction_count",
  "latest_observation_at",
}


# ---------- Helpers ----------

@pytest.fixture(scope="module")
def client():
  """
  One real app (real Postgres, Neo4j and Redis) shared by every test in this
  file. Skips the tests if the connection settings are not set.
  """
  if not REAL_POSTGRES_DSN or not all(REAL_NEO4J.values()):
    pytest.skip(
      "POSTGRES_DSN, NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD must be set; "
      "start the services and export the env vars"
    )
  with TestClient(app) as test_client:
    yield test_client


def real_query(sql, params=None):
  """Read-only: run one SELECT against the real Postgres and return all rows."""
  with psycopg.connect(REAL_POSTGRES_DSN) as conn:
    return conn.execute(sql, params).fetchall()


def graph_query(cypher, **params):
  """
  Read-only: run one Cypher query against the real Neo4j and return the rows as
  a list of dictionaries. It runs in a read transaction, so it cannot write.
  """
  auth = (REAL_NEO4J["user"], REAL_NEO4J["password"])
  with GraphDatabase.driver(REAL_NEO4J["uri"], auth=auth) as driver:
    with driver.session() as session:
      return session.execute_read(lambda tx: tx.run(cypher, params).data())


def expected_etl_label():
  """The etl_version text the endpoint reports: the active versions joined by +."""
  rows = real_query(
    "SELECT version FROM etl_versions WHERE version = ANY(%s) ORDER BY id",
    (main_module.ACTIVE_ETL_VERSIONS,),
  )
  if not rows:
    pytest.skip("none of ACTIVE_ETL_VERSIONS exist in etl_versions")
  return "+".join(row[0] for row in rows)


def busiest_predator():
  """
  Read-only: (predator taxon id, number of different prey) of the predator with
  the most different prey.
  """
  rows = graph_query(
    """
    MATCH (p:Species)-[:EATS]->(q:Species)
    RETURN p.taxon_id AS taxon, count(DISTINCT q) AS n
    ORDER BY n DESC, taxon
    LIMIT 1
    """
  )
  if not rows:
    pytest.skip("the graph has no EATS relationships")
  return rows[0]["taxon"], rows[0]["n"]


def busiest_prey():
  """
  Read-only: (prey taxon id, number of different predators) of the prey with the
  most different predators.
  """
  rows = graph_query(
    """
    MATCH (p:Species)-[:EATS]->(q:Species)
    RETURN q.taxon_id AS taxon, count(DISTINCT p) AS n
    ORDER BY n DESC, taxon
    LIMIT 1
    """
  )
  if not rows:
    pytest.skip("the graph has no EATS relationships")
  return rows[0]["taxon"], rows[0]["n"]


def predator_with_varied_counts():
  """
  Read-only: the taxon id of the predator with the most prey among those whose
  prey do not all have the same interaction_count, so ordering can be checked.
  """
  rows = graph_query(
    """
    MATCH (p:Species)-[r:EATS]->(:Species)
    WITH p.taxon_id AS taxon, collect(DISTINCT r.interaction_count) AS counts, count(*) AS n
    WHERE size(counts) >= 2
    RETURN taxon
    ORDER BY n DESC, taxon
    LIMIT 1
    """
  )
  if not rows:
    pytest.skip("no predator has prey with different interaction counts")
  return rows[0]["taxon"]


def graph_pair_counts(predator_taxon_id):
  """Read-only: the interaction_count of every prey of one predator, as a list."""
  rows = graph_query(
    """
    MATCH (:Species {taxon_id: $taxon})-[r:EATS]->(:Species)
    RETURN r.interaction_count AS count
    """,
    taxon=predator_taxon_id,
  )
  return [row["count"] for row in rows]


def graph_prey_ids(predator_taxon_id):
  """Read-only: the set of taxon ids that one predator eats."""
  rows = graph_query(
    """
    MATCH (:Species {taxon_id: $taxon})-[:EATS]->(q:Species)
    RETURN q.taxon_id AS taxon
    """,
    taxon=predator_taxon_id,
  )
  return {row["taxon"] for row in rows}


def graph_predator_ids(prey_taxon_id):
  """Read-only: the set of taxon ids that eat one prey."""
  rows = graph_query(
    """
    MATCH (p:Species)-[:EATS]->(:Species {taxon_id: $taxon})
    RETURN p.taxon_id AS taxon
    """,
    taxon=prey_taxon_id,
  )
  return {row["taxon"] for row in rows}


def real_pair():
  """
  Read-only: (predator taxon id, prey taxon id, interaction_count) of the pair
  with the highest count where the two species are different.
  """
  rows = graph_query(
    """
    MATCH (p:Species)-[r:EATS]->(q:Species)
    WHERE p.taxon_id <> q.taxon_id
    RETURN p.taxon_id AS predator, q.taxon_id AS prey, r.interaction_count AS count
    ORDER BY count DESC, predator, prey
    LIMIT 1
    """
  )
  if not rows:
    pytest.skip("the graph has no pair of two different species")
  return rows[0]["predator"], rows[0]["prey"], rows[0]["count"]


def taxon_in_both_roles():
  """
  Read-only: the taxon id of a species that eats something and is also eaten by
  something, both times by a different species (the one with the most such
  links).
  """
  rows = graph_query(
    """
    MATCH (a:Species)-[:EATS]->(t:Species)-[:EATS]->(b:Species)
    WHERE a.taxon_id <> t.taxon_id AND t.taxon_id <> b.taxon_id
    RETURN t.taxon_id AS taxon, count(*) AS n
    ORDER BY n DESC, taxon
    LIMIT 1
    """
  )
  if not rows:
    pytest.skip("no species is both a predator and a prey of other species")
  return rows[0]["taxon"]


def species_without_pair_with(predator_taxon_id):
  """
  Read-only: the taxon id of a species that exists in the graph but is not eaten
  by the given predator (and is not the predator itself).
  """
  rows = graph_query(
    """
    MATCH (s:Species)
    WHERE s.taxon_id <> $taxon
      AND NOT (:Species {taxon_id: $taxon})-[:EATS]->(s)
    RETURN s.taxon_id AS taxon
    ORDER BY taxon
    LIMIT 1
    """,
    taxon=predator_taxon_id,
  )
  if not rows:
    pytest.skip("the predator eats every species in the graph")
  return rows[0]["taxon"]


def unused_taxon_id():
  """Read-only: a taxon id bigger than every Species node, so it has no pairs."""
  rows = graph_query("MATCH (s:Species) RETURN max(s.taxon_id) + 1 AS taxon")
  if not rows or rows[0]["taxon"] is None:
    pytest.skip("the graph has no Species nodes")
  return rows[0]["taxon"]


def db_scientific_names(taxon_ids):
  """Read-only: {taxon_id: scientific_name} from the Postgres species table."""
  rows = real_query(
    "SELECT taxon_id, scientific_name FROM species WHERE taxon_id = ANY(%s)",
    (list(taxon_ids),),
  )
  return {row[0]: row[1] for row in rows}


def get_pairs(client, **params):
  """Call the endpoint, check it returned 200, and return the results list."""
  resp = client.get(URL, params=params)
  assert resp.status_code == 200
  return resp.json()["results"]


# =========================================================================
# Feature: Basic validation
# =========================================================================

def test_L5_001_request_with_no_filters_returns_400(client):
  """
  L5-001: GET /api/v1/predator-prey with no predator and no prey returns 400
  with {detail: "Provide predator or prey taxon id to filter results."}.
  """
  resp = client.get(URL)

  assert resp.status_code == 400
  assert resp.json() == {
    "detail": "Provide predator or prey taxon id to filter results."
  }


def test_L5_002_request_with_only_predator_param_is_accepted(client):
  """
  L5-002: GET /api/v1/predator-prey?predator=<a predator> returns 200 and a
  results array. The predator with the most prey is used, so the array is not
  empty.
  """
  predator, _ = busiest_predator()

  resp = client.get(URL, params={"predator": predator})

  assert resp.status_code == 200
  assert isinstance(resp.json()["results"], list)
  assert resp.json()["results"]


def test_L5_003_request_with_only_prey_param_is_accepted(client):
  """
  L5-003: GET /api/v1/predator-prey?prey=<a prey> returns 200 and a results
  array. The prey with the most predators is used, so the array is not empty.
  """
  prey, _ = busiest_prey()

  resp = client.get(URL, params={"prey": prey})

  assert resp.status_code == 200
  assert isinstance(resp.json()["results"], list)
  assert resp.json()["results"]


def test_L5_004_request_with_both_predator_and_prey_params_is_accepted(client):
  """
  L5-004: predator and prey together return 200, and every result is that
  predator eating that prey. A real pair of two different species is used.
  """
  predator, prey, _ = real_pair()

  results = get_pairs(client, predator=predator, prey=prey)

  assert results
  assert all(item["predator_taxon_id"] == predator for item in results)
  assert all(item["prey_taxon_id"] == prey for item in results)


def test_L5_005_non_numeric_predator_param_is_rejected(client):
  """
  L5-005: GET /api/v1/predator-prey?predator=fox returns 422.
  """
  resp = client.get(URL, params={"predator": "fox"})

  assert resp.status_code == 422


def test_L5_006_non_numeric_prey_param_is_rejected(client):
  """
  L5-006: GET /api/v1/predator-prey?prey=fox returns 422.
  """
  resp = client.get(URL, params={"prey": "fox"})

  assert resp.status_code == 422


def test_L5_007_negative_predator_param_returns_empty_list_gracefully(client):
  """
  L5-007: GET /api/v1/predator-prey?predator=-1 returns 200 with an empty
  results array, or 422. It must not crash.
  """
  resp = client.get(URL, params={"predator": -1})

  assert resp.status_code in (200, 422)
  if resp.status_code == 200:
    assert resp.json()["results"] == []


def test_L5_008_zero_as_predator_param_returns_empty_list_gracefully(client):
  """
  L5-008: GET /api/v1/predator-prey?predator=0 returns 200 and an empty results
  array, not a 400 and not a crash. 0 is a number, so it counts as a filter.
  """
  resp = client.get(URL, params={"predator": 0})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


# =========================================================================
# Feature: Response shape
# =========================================================================

def test_L5_009_each_result_contains_all_required_fields(client):
  """
  L5-009: every result has predator_taxon_id, predator_scientific_name,
  prey_taxon_id, prey_scientific_name, interaction_count and
  latest_observation_at. The predator with the most prey is used.
  """
  predator, _ = busiest_predator()

  results = get_pairs(client, predator=predator, limit=500)

  assert results
  for item in results:
    assert REQUIRED_FIELDS.issubset(item.keys()), (
      f"missing fields in {item}: {REQUIRED_FIELDS - item.keys()}"
    )


def test_L5_010_response_always_includes_etl_version_field(client):
  """
  L5-010: the response has an etl_version text at the top level, and it is the
  label of the active versions (joined by +), the same one the other endpoints
  report.
  """
  predator, _ = busiest_predator()

  resp = client.get(URL, params={"predator": predator})

  body = resp.json()

  assert resp.status_code == 200
  assert isinstance(body["etl_version"], str)
  assert body["etl_version"] == expected_etl_label()


# L5-011 (a null latest_observation_at) is not tested: no aggregate in the data
# has a null latest_observation_at.


def test_L5_012_no_matching_pairs_returns_empty_list_not_404(client):
  """
  L5-012: a predator that has no pairs returns 200 and {etl_version: string,
  results: []}, not a 404. A taxon id bigger than every species in the graph is
  used.
  """
  resp = client.get(URL, params={"predator": unused_taxon_id()})

  body = resp.json()

  assert resp.status_code == 200
  assert isinstance(body["etl_version"], str)
  assert body["results"] == []


# =========================================================================
# Feature: Filtering behavior
# =========================================================================

def test_L5_013_filter_by_predator_returns_only_pairs_where_taxon_is_predator(client):
  """
  L5-013: for a species that is a predator in some pairs and a prey in others,
  predator=<it> returns only the pairs where it is the predator (the prey it
  eats, checked against Neo4j), and none where it is the prey.
  """
  taxon = taxon_in_both_roles()
  eaten_by = graph_predator_ids(taxon) - {taxon}

  results = get_pairs(client, predator=taxon, limit=500)

  assert eaten_by, "the chosen species should be prey of another species"
  assert results
  assert all(item["predator_taxon_id"] == taxon for item in results)
  assert {item["prey_taxon_id"] for item in results} == graph_prey_ids(taxon)


def test_L5_014_filter_by_prey_returns_only_pairs_where_taxon_is_prey(client):
  """
  L5-014: for a species that is a predator in some pairs and a prey in others,
  prey=<it> returns only the pairs where it is the prey (the predators that eat
  it, checked against Neo4j), and none where it is the predator.
  """
  taxon = taxon_in_both_roles()
  eats = graph_prey_ids(taxon) - {taxon}

  results = get_pairs(client, prey=taxon, limit=500)

  assert eats, "the chosen species should be a predator of another species"
  assert results
  assert all(item["prey_taxon_id"] == taxon for item in results)
  assert {item["predator_taxon_id"] for item in results} == graph_predator_ids(taxon)


def test_L5_015_filter_by_both_returns_only_that_specific_pair(client):
  """
  L5-015: predator and prey together return exactly that pair, once, with the
  interaction_count that Neo4j has for it. A real pair of two different species
  is used.
  """
  predator, prey, count = real_pair()

  results = get_pairs(client, predator=predator, prey=prey)

  assert len(results) == 1
  assert results[0]["predator_taxon_id"] == predator
  assert results[0]["prey_taxon_id"] == prey
  assert results[0]["interaction_count"] == count


def test_L5_016_filter_by_both_where_pair_does_not_exist_returns_empty_list(client):
  """
  L5-016: predator and prey together where that predator does not eat that prey
  return 200 and an empty results array. Both are real species in the graph.
  """
  predator, _ = busiest_predator()
  not_prey = species_without_pair_with(predator)

  resp = client.get(URL, params={"predator": predator, "prey": not_prey})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


# L5-017 (the same pair in two ETL versions) is not tested: no pair exists in
# two versions.


# =========================================================================
# Feature: Ordering and limit
# =========================================================================

def test_L5_018_results_are_ordered_by_interaction_count_descending(client):
  """
  L5-018: the pair with the highest interaction_count comes first. A predator
  whose prey have different counts is used. The counts that come back must be
  exactly the counts in Neo4j, from highest to lowest.
  """
  predator = predator_with_varied_counts()

  results = get_pairs(client, predator=predator, limit=500)

  counts = [item["interaction_count"] for item in results]
  expected = sorted(graph_pair_counts(predator), reverse=True)[:500]

  assert len(set(counts)) > 1
  assert counts == sorted(counts, reverse=True)
  assert counts == expected


# L5-019 (default limit of 100) is not tested: no predator has 100 or more prey
# (the most is 39), so the cap can never be reached.


def test_L5_020_custom_limit_is_respected(client):
  """
  L5-020: limit=10 returns exactly 10 results. The predator with the most prey
  is used.
  """
  predator, total = busiest_predator()
  if total < 10:
    pytest.skip("no predator has 10 different prey")

  results = get_pairs(client, predator=predator, limit=10)

  assert len(results) == 10


def test_L5_021_maximum_limit_of_500_is_accepted(client):
  """
  L5-021: limit=500 returns 200 and at most 500 results (all of them if the
  predator has fewer prey than that). The predator with the most prey is used.
  """
  predator, total = busiest_predator()

  results = get_pairs(client, predator=predator, limit=500)

  assert 0 < len(results) <= 500
  assert len(results) == min(500, total)


def test_L5_022_limit_above_500_is_rejected(client):
  """
  L5-022: GET /api/v1/predator-prey?predator=41641&limit=501 returns 422.
  """
  resp = client.get(URL, params={"predator": ANY_TAXON, "limit": 501})

  assert resp.status_code == 422


def test_L5_023_limit_of_0_is_rejected(client):
  """
  L5-023: GET /api/v1/predator-prey?predator=41641&limit=0 returns 422.
  """
  resp = client.get(URL, params={"predator": ANY_TAXON, "limit": 0})

  assert resp.status_code == 422


def test_L5_024_limit_of_1_returns_the_pair_with_highest_count(client):
  """
  L5-024: limit=1 returns exactly 1 result, and its interaction_count is the
  highest the predator has in Neo4j. A predator whose prey have different counts
  is used, so a wrong pick would show.
  """
  predator = predator_with_varied_counts()

  results = get_pairs(client, predator=predator, limit=1)

  assert len(results) == 1
  assert results[0]["interaction_count"] == max(graph_pair_counts(predator))


# =========================================================================
# Feature: ETL version
# =========================================================================

# L5-025 (no ETL version at all) and L5-026 (pairs from v1 only) are not
# tested: L5-025 needs an empty etl_versions table, and L5-026 needs a second
# version (only one exists locally).


def test_L5_027_non_existent_etl_version_returns_404(client):
  """
  L5-027: GET /api/v1/predator-prey?predator=41641&etl_version=doesnotexist
  returns 404 with {detail: "No ETL version found. Load data first."}.
  """
  resp = client.get(
    URL, params={"predator": ANY_TAXON, "etl_version": "doesnotexist"}
  )

  assert resp.status_code == 404
  assert resp.json() == {"detail": "No ETL version found. Load data first."}


# =========================================================================
# Feature: Data integrity
# =========================================================================

def test_L5_028_predator_scientific_name_matches_species_table(client):
  """
  L5-028: predator_scientific_name in every result equals scientific_name in
  the Postgres species table for predator_taxon_id. The predator with the most
  prey is used.
  """
  predator, _ = busiest_predator()

  results = get_pairs(client, predator=predator, limit=500)

  names = db_scientific_names({item["predator_taxon_id"] for item in results})

  assert results
  for item in results:
    assert item["predator_scientific_name"] == names[item["predator_taxon_id"]], (
      f"predator {item['predator_taxon_id']} name does not match the species table"
    )


def test_L5_029_prey_scientific_name_matches_species_table(client):
  """
  L5-029: prey_scientific_name in every result equals scientific_name in the
  Postgres species table for prey_taxon_id. The predator with the most prey is
  used.
  """
  predator, _ = busiest_predator()

  results = get_pairs(client, predator=predator, limit=500)

  names = db_scientific_names({item["prey_taxon_id"] for item in results})

  assert results
  for item in results:
    assert item["prey_scientific_name"] == names[item["prey_taxon_id"]], (
      f"prey {item['prey_taxon_id']} name does not match the species table"
    )


def test_L5_030_interaction_count_is_always_a_positive_integer(client):
  """
  L5-030: every result has an interaction_count that is a whole number of 1 or
  more. The predator with the most prey is used.
  """
  predator, _ = busiest_predator()

  results = get_pairs(client, predator=predator, limit=500)

  assert results
  for item in results:
    count = item["interaction_count"]
    assert isinstance(count, int) and not isinstance(count, bool), (
      f"interaction_count {count!r} is not an integer"
    )
    assert count >= 1, f"interaction_count {count} is less than 1"


# L5-031 (a species cannot be both predator and prey in the same pair) is not
# tested: the expectation is wrong, because 39 aggregates have predator = prey.