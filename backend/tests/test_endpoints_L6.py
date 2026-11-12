"""
Endpoint tests for the Who Eats Whom backend (FastAPI) -- Layer 6: Food web summary.

  Layer 6: Food Web Summary Endpoint
    GET /api/v1/food-web/summary

Conventions used throughout this file:
  * Tests call the API in-process through FastAPI's TestClient, so no separate
    server needs to be started.
  * Nothing is faked and nothing is written. The tests run against the real
    Postgres, Neo4j and Redis configured through the same environment variables
    the app reads (POSTGRES_DSN, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    REDIS_URL). Tests only ever read.
  * If Postgres or Neo4j is not configured, the tests that need them are skipped.
  * The endpoint gets "locations" from Postgres and "interactions", "edges" and
    "taxa" from Neo4j. So the expected values in these tests come from read-only
    queries on those same two databases (SQL for locations, Cypher for the rest).
  * Tests that need a service to be missing (L6-013, L6-016, L6-017, L6-018 and
    L6-026) start the real app with that environment variable unset, the same
    way the Layer 1 tests do. Nothing is replaced with a fake. In those tests
    Redis is always unset as well, so the app never reads from or writes to the
    real cache. Without that, a response with zeros in it could be saved in Redis
    and served to other tests for the next 300 seconds.
  * The other tests use the real Redis. The summary is cached for 300 seconds, so
    if the data was reloaded in the last five minutes, a test that compares the
    answer with the database can see the older cached numbers. Wait for the cache
    to expire (or clear it) and run again.
  * Test names follow the plain-English test IDs, e.g. test_L6_009_...
    covers test case L6-009.

Not tested (the real data / the setup cannot support them):
  L6-002 (needs empty databases), L6-007 (only one version, so scoping cannot be
  shown), L6-008 (needs no research-grade rows, but 6,681 exist), L6-012 (needs
  an empty Neo4j), L6-014 (needs Neo4j to go down), L6-015 (needs Neo4j to return
  a null sum), L6-019 (needs an empty etl_versions table), L6-022 (needs a cold
  cache), L6-023 (cannot prove the second request skipped the databases), L6-024
  (only one version, so no separate cache entries), L6-025 (needs a cold cache and
  a 300-second wait), L6-027 (needs Redis to go down), L6-028 (needs a new
  version to be loaded), L6-029, L6-034 and L6-035 (frontend tests, they need a
  browser), L6-030 (needs the API to return null), L6-031 (needs the API to
  return a 500), L6-032 (needs the API to hang) and L6-033 (needs the API to
  fail).

Run all tests - python -m pytest backend/tests/ -v
Run one test - python -m pytest backend/tests/test_endpoints_L6.py::{name of the test} -v
"""
import psycopg

import pytest

from fastapi.testclient import TestClient
from neo4j import GraphDatabase

import backend.main as main_module
from backend.main import app


# The real service settings, read once when this file is imported (before any
# test patches anything). They come from the same environment variables the app
# reads. None means the variable is not set.
REAL_POSTGRES_DSN = main_module.POSTGRES_DSN
REAL_NEO4J = {
  "uri": main_module.NEO4J_URI,
  "user": main_module.NEO4J_USER,
  "password": main_module.NEO4J_PASSWORD,
}

URL = "/api/v1/food-web/summary"

# The four fields every response must have (L6-001).
METRIC_FIELDS = {"interactions", "edges", "taxa", "locations"}

# The Postgres table the locations count is read from.
OBSERVATIONS_TABLE = "observations"


# ---------- Helpers ----------

def require_real_services():
  """Skip the test unless Postgres and Neo4j are both configured."""
  if not REAL_POSTGRES_DSN or not all(REAL_NEO4J.values()):
    pytest.skip(
      "POSTGRES_DSN, NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD must be set; "
      "start the services and export the env vars"
    )


@pytest.fixture()
def client():
  """
  A fresh start of the real app (real Postgres, Neo4j and Redis) for each test
  that uses it. Skips the tests if Postgres or Neo4j is not configured.

  It is not shared between tests on purpose: lifespan_summary starts the same
  `app` object with some services unset, which replaces the connections stored in
  app.state and closes them afterwards. A client kept alive across those tests
  would be left with a closed or missing Postgres pool (a 503).
  """
  require_real_services()
  with TestClient(app) as test_client:
    yield test_client


def lifespan_summary(monkeypatch, postgres=False, neo4j=False):
  """
  Start the real app with only the chosen services configured and return the
  GET /api/v1/food-web/summary response.

  Sets the module-level constants in backend.main (None means "env var not
  set"), then starts the app with `with TestClient(app)` so startup and shutdown
  both run. A service that is switched on connects to the real one. Redis is
  always switched off, so nothing is read from or written to the real cache.

  Args:
    monkeypatch: pytest's monkeypatch fixture (undoes the patches after the test).
    postgres: True to use the real POSTGRES_DSN, False for unset.
    neo4j: True to use the real NEO4J_URI, NEO4J_USER and NEO4J_PASSWORD, False
      for unset.

  Returns:
    The Response from GET /api/v1/food-web/summary.
  """
  monkeypatch.setattr("backend.main.POSTGRES_DSN", REAL_POSTGRES_DSN if postgres else None)
  monkeypatch.setattr("backend.main.NEO4J_URI", REAL_NEO4J["uri"] if neo4j else None)
  monkeypatch.setattr("backend.main.NEO4J_USER", REAL_NEO4J["user"] if neo4j else None)
  monkeypatch.setattr("backend.main.NEO4J_PASSWORD", REAL_NEO4J["password"] if neo4j else None)
  monkeypatch.setattr("backend.main.REDIS_URL", None)

  with TestClient(app) as test_client:
    return test_client.get(URL)


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


def active_versions():
  """
  Read-only: [(id, version name), ...] of the ACTIVE_ETL_VERSIONS that exist in
  etl_versions, in id order. These are what the endpoint reads by default.
  """
  rows = real_query(
    "SELECT id, version FROM etl_versions WHERE version = ANY(%s) ORDER BY id",
    (main_module.ACTIVE_ETL_VERSIONS,),
  )
  if not rows:
    pytest.skip("none of ACTIVE_ETL_VERSIONS exist in etl_versions")
  return rows


def active_ids():
  """The etl_versions ids the endpoint reads by default."""
  return [row[0] for row in active_versions()]


def db_location_stats(version_ids):
  """
  Read-only: counts from the real Postgres for the given versions, as a
  dictionary with:
    countries       - different place_country_name values among research-grade
                      rows that have one (this is what "locations" must equal)
    rows_with_country - research-grade rows that have a country
    research_without_country - research-grade rows with a null or empty country
    not_research    - rows that are not research grade
  """
  has_country = "coalesce(raw->>'place_country_name', '') <> ''"
  research = "quality_grade = 'research'"
  rows = real_query(
    f"""
    SELECT
      count(DISTINCT raw->>'place_country_name') FILTER (WHERE {research} AND {has_country}),
      count(*) FILTER (WHERE {research} AND {has_country}),
      count(*) FILTER (WHERE {research} AND NOT ({has_country})),
      count(*) FILTER (WHERE quality_grade IS DISTINCT FROM 'research')
    FROM {OBSERVATIONS_TABLE}
    WHERE etl_version_id = ANY(%s)
    """,
    (version_ids,),
  )
  countries, rows_with_country, research_without_country, not_research = rows[0]
  return {
    "countries": countries,
    "rows_with_country": rows_with_country,
    "research_without_country": research_without_country,
    "not_research": not_research,
  }


def graph_totals():
  """
  Read-only: the three numbers the endpoint takes from Neo4j, as a dictionary
  with interactions (the sum of interaction_count over all EATS relationships),
  edges (the number of EATS relationships) and taxa (the number of distinct
  nodes).
  """
  interactions = graph_query(
    "MATCH ()-[r:EATS]->() RETURN coalesce(sum(r.interaction_count), 0) AS n"
  )[0]["n"]
  edges = graph_query("MATCH ()-[r:EATS]->() RETURN count(r) AS n")[0]["n"]
  taxa = graph_query("MATCH (n) RETURN count(DISTINCT n) AS n")[0]["n"]
  return {"interactions": interactions, "edges": edges, "taxa": taxa}


def get_summary(client, **params):
  """Call the endpoint, check it returned 200, and return the response body."""
  resp = client.get(URL, params=params)
  assert resp.status_code == 200
  return resp.json()


def is_whole_number(value):
  """True for an int (but not True/False, which Python also counts as int)."""
  return isinstance(value, int) and not isinstance(value, bool)


# =========================================================================
# Feature: Basic response shape
# =========================================================================

def test_L6_001_returns_all_four_metric_fields(client):
  """
  L6-001: GET /api/v1/food-web/summary returns 200 with interactions, edges,
  taxa and locations, each a number.
  """
  body = get_summary(client)

  assert METRIC_FIELDS.issubset(body.keys()), (
    f"missing fields: {METRIC_FIELDS - body.keys()}"
  )
  for field in METRIC_FIELDS:
    assert is_whole_number(body[field]), f"{field} is {body[field]!r}, not a number"


# L6-002 (all four fields are 0 with empty databases) is not tested: it needs
# empty databases.


def test_L6_003_all_four_fields_are_non_negative_integers(client):
  """
  L6-003: interactions, edges, taxa and locations are whole numbers of 0 or
  more, never negative.
  """
  body = get_summary(client)

  for field in METRIC_FIELDS:
    assert is_whole_number(body[field]), f"{field} is {body[field]!r}, not an integer"
    assert body[field] >= 0, f"{field} is negative: {body[field]}"


# =========================================================================
# Feature: Postgres (locations)
# =========================================================================

def test_L6_004_locations_only_counts_research_grade_observations(client):
  """
  L6-004: locations is the number of different countries among research-grade
  observations only (checked against a separate query on the database). The
  test is skipped if every observation is research grade, since the rule could
  not show.
  """
  stats = db_location_stats(active_ids())
  if stats["not_research"] == 0:
    pytest.skip("every observation is research grade")

  body = get_summary(client)

  assert body["locations"] == stats["countries"]


def test_L6_005_locations_excludes_null_or_empty_place_country_name(client):
  """
  L6-005: observations whose place_country_name is null or empty are not
  counted in locations. The test is skipped if every research-grade observation
  has a country, since the rule could not show.
  """
  stats = db_location_stats(active_ids())
  if stats["research_without_country"] == 0:
    pytest.skip("every research-grade observation has a place_country_name")

  body = get_summary(client)

  assert body["locations"] == stats["countries"]


def test_L6_006_locations_is_distinct_country_count_not_observation_count(client):
  """
  L6-006: locations is the number of different countries, not the number of
  observations. There must be more research-grade observations with a country
  than there are countries, so the two numbers differ.
  """
  stats = db_location_stats(active_ids())
  if stats["rows_with_country"] <= stats["countries"]:
    pytest.skip("every country has only one research-grade observation")

  body = get_summary(client)

  assert body["locations"] == stats["countries"]
  assert body["locations"] < stats["rows_with_country"]


# L6-007 (locations scoped to the current ETL version) is not tested: only one
# version exists, so scoping cannot be shown.
# L6-008 (locations is 0 with no research-grade rows) is not tested: it needs no
# research-grade rows, but 6,681 exist.


# =========================================================================
# Feature: Neo4j (interactions, edges, taxa)
# =========================================================================

def test_L6_009_interactions_is_sum_of_interaction_count_over_all_eats(client):
  """
  L6-009: interactions equals the sum of r.interaction_count over every EATS
  relationship in Neo4j.
  """
  expected = graph_totals()["interactions"]

  body = get_summary(client)

  assert body["interactions"] == expected


def test_L6_010_edges_is_total_number_of_eats_relationships(client):
  """
  L6-010: edges equals the exact number of EATS relationships in Neo4j.
  """
  expected = graph_totals()["edges"]

  body = get_summary(client)

  assert body["edges"] == expected


def test_L6_011_taxa_is_total_distinct_nodes_in_graph(client):
  """
  L6-011: taxa equals the number of distinct nodes in the Neo4j graph.
  """
  expected = graph_totals()["taxa"]

  body = get_summary(client)

  assert body["taxa"] == expected


# L6-012 (all Neo4j counts are 0 when Neo4j is empty), L6-014 (Neo4j goes down
# after the app starts) and L6-015 (Neo4j returns a null sum) are not tested:
# they need an empty Neo4j, Neo4j going down, or Neo4j returning a null.


def test_L6_013_neo4j_not_configured_returns_zeros_not_500(monkeypatch):
  """
  L6-013: with Neo4j not configured, the response is 200 (not 500), and
  interactions, edges and taxa are all 0. locations is still there.
  """
  require_real_services()

  resp = lifespan_summary(monkeypatch, postgres=True)

  body = resp.json()

  assert resp.status_code == 200
  assert body["interactions"] == 0
  assert body["edges"] == 0
  assert body["taxa"] == 0
  assert is_whole_number(body["locations"])


# =========================================================================
# Feature: Both databases failing simultaneously
# =========================================================================

def test_L6_016_both_postgres_and_neo4j_unavailable_returns_503(monkeypatch):
  """
  L6-016: with no POSTGRES_DSN and no NEO4J_URI, the response is 503 with
  {detail: "Postgres connection is not configured."}.
  """
  resp = lifespan_summary(monkeypatch)

  assert resp.status_code == 503
  assert resp.json() == {"detail": "Postgres connection is not configured."}


def test_L6_017_postgres_up_neo4j_down_still_returns_valid_response(monkeypatch):
  """
  L6-017: with Postgres connected and Neo4j not configured, the response is 200
  with interactions, edges and taxa at 0 and locations at the real value (the
  number of countries in the database).
  """
  require_real_services()
  expected_locations = db_location_stats(active_ids())["countries"]

  resp = lifespan_summary(monkeypatch, postgres=True)

  assert resp.status_code == 200
  assert resp.json() == {
    "interactions": 0,
    "edges": 0,
    "taxa": 0,
    "locations": expected_locations,
  }


def test_L6_018_neo4j_up_postgres_down_returns_503(monkeypatch):
  """
  L6-018: with Neo4j connected and Postgres not configured, the response is 503.
  Postgres is required, Neo4j is optional.
  """
  require_real_services()

  resp = lifespan_summary(monkeypatch, neo4j=True)

  assert resp.status_code == 503


# =========================================================================
# Feature: ETL version
# =========================================================================

# L6-019 (no ETL version at all) is not tested: it needs an empty etl_versions
# table.


def test_L6_020_explicit_etl_version_param_is_accepted(client):
  """
  L6-020: GET /api/v1/food-web/summary?etl_version=<a real version> returns 200
  with locations counted for that version's observations.
  """
  version_id, version = active_versions()[0]
  expected_locations = db_location_stats([version_id])["countries"]

  body = get_summary(client, etl_version=version)

  assert body["locations"] == expected_locations


def test_L6_021_non_existent_etl_version_returns_404(client):
  """
  L6-021: GET /api/v1/food-web/summary?etl_version=doesnotexist returns 404 with
  {detail: "No ETL version found. Load data first."}.
  """
  resp = client.get(URL, params={"etl_version": "doesnotexist"})

  assert resp.status_code == 404
  assert resp.json() == {"detail": "No ETL version found. Load data first."}


# =========================================================================
# Feature: Redis cache behavior
# =========================================================================

# L6-022 to L6-025 and L6-027 to L6-028 are not tested: they need a cold cache,
# a 300-second wait, a second ETL version, Redis going down, or a way to prove
# the second request skipped the databases.


def test_L6_026_redis_not_configured_falls_back_to_the_databases(monkeypatch):
  """
  L6-026: with REDIS_URL not set, the response is 200 and every number comes
  from the live databases (checked against Neo4j and Postgres).
  """
  require_real_services()
  expected = graph_totals()
  expected["locations"] = db_location_stats(active_ids())["countries"]

  resp = lifespan_summary(monkeypatch, postgres=True, neo4j=True)

  assert resp.status_code == 200
  assert resp.json() == {
    "interactions": expected["interactions"],
    "edges": expected["edges"],
    "taxa": expected["taxa"],
    "locations": expected["locations"],
  }


# =========================================================================
# Feature: Frontend consumption (InteractiveFoodWeb.tsx)
# =========================================================================

# L6-029 to L6-035 are not tested here: they are frontend tests (they need a
# browser, or the API to return null, a 500, hang, or fail).
