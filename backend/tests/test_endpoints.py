"""
Endpoint tests for the Who Eats Whom backend (FastAPI).

The tests are organized by layer, with one section per layer below:

  Layer 1: Infrastructure & Config (/health)
  (more layers will be added as new sections further down)

Conventions used throughout this file:
  * Tests call the API in-process through FastAPI's TestClient, so no real
    server or backing service needs to be running.
  * External services are replaced with fakes so the tests do not connect to
    real Postgres or Neo4j instances.
  * FastAPI's lifespan is exercised through TestClient so the tests cover
    the environment-variable configuration and startup logic in
    backend/main.py.
  * Test names follow the plain-English test IDs, e.g. test_L1_002_...
    covers test case L1-002.
"""
from fastapi.testclient import TestClient

from backend.cache import RedisCache
from backend.main import app


# =========================================================================
# Layer 1: Infrastructure & Config -- /health
#
# /health must ALWAYS return HTTP 200 with the keys status, postgres, neo4j
# and redis, regardless of which backing services are configured.
#
# The service flags reflect whether the corresponding service handle was
# successfully created during the FastAPI lifespan:
#
#   postgres -> bool(pg_pool)
#   neo4j    -> bool(neo4j_driver)
#   redis    -> bool(redis_cache and redis_cache.client)
#
# These tests exercise the real FastAPI lifespan so that the environment
# variable -> app.state configuration logic in backend/main.py is tested.
# Postgres and Neo4j connections are replaced with fakes so no real
# external services are required.
#
# The tests cover the required L1-001 through L1-006 cases, along with
# additional Neo4j configuration edge cases.
# =========================================================================

# Keys every /health response must contain (L1-006).
REQUIRED_KEYS = {"status", "postgres", "neo4j", "redis"}

# ---------- Lifespan / environment-variable test helpers ----------
#
# backend.main reads environment variables at import time into module
# constants, so these tests monkeypatch those constants rather than
# os.environ. `with TestClient(app)` runs the FastAPI lifespan, which
# creates the service handles stored in app.state.
#
# Postgres and Neo4j are replaced with fake implementations so startup
# does not attempt to connect to real services.
#
# Fake class names are prefixed with "FakeLifespan" to distinguish them
# from any fakes used by tests for other layers in this file.

class FakeLifespanConnectionPool:
  """
  Stand-in for psycopg_pool.AsyncConnectionPool.

  Accepts any constructor arguments and provides the async close() that
  lifespan calls on shutdown, so no real Postgres connection is attempted.
  """

  def __init__(self, *args, **kwargs):
    self.kwargs = kwargs

  async def close(self):
    """No-op shutdown hook called by lifespan teardown."""
    pass


class FakeLifespanNeo4jDriver:
  """Stand-in for a Neo4j driver; only needs the async close() on shutdown."""

  async def close(self):
    """No-op shutdown hook called by lifespan teardown."""
    pass


class FakeLifespanGraphDatabase:
  """Stand-in for neo4j.AsyncGraphDatabase, returning a fake driver."""

  @staticmethod
  def driver(uri, auth=None):
    """Return a fake driver instead of connecting to the given URI."""
    return FakeLifespanNeo4jDriver()


# Sample env values used by the lifespan tests.
TEST_POSTGRES_DSN = "postgresql://user:pw@localhost:5432/db"
TEST_NEO4J_ENV = {
  "neo4j_uri": "bolt://localhost:7687",
  "neo4j_user": "neo4j",
  "neo4j_password": "pw",
}
TEST_REDIS_URL = "redis://localhost:6379/0"  # from_url is lazy, no connection


def lifespan_health(
  monkeypatch,
  postgres_dsn=None,
  neo4j_uri=None,
  neo4j_user=None,
  neo4j_password=None,
  redis_url=None,
):
  """
  Run the real lifespan with the given "env vars" and return the /health
  response.

  Sets the module-level constants in backend.main (None means "env var not
  set"), swaps AsyncConnectionPool and AsyncGraphDatabase for fakes, then
  starts the app with `with TestClient(app)` so startup and shutdown both run.

  Args:
    monkeypatch: pytest's monkeypatch fixture (undoes patches after the test).
    postgres_dsn: value for POSTGRES_DSN, or None for unset.
    neo4j_uri: value for NEO4J_URI, or None for unset.
    neo4j_user: value for NEO4J_USER, or None for unset.
    neo4j_password: value for NEO4J_PASSWORD, or None for unset.
    redis_url: value for REDIS_URL, or None for unset.

  Returns:
    The Response from GET /health.
  """
  monkeypatch.setattr("backend.main.POSTGRES_DSN", postgres_dsn)
  monkeypatch.setattr("backend.main.NEO4J_URI", neo4j_uri)
  monkeypatch.setattr("backend.main.NEO4J_USER", neo4j_user)
  monkeypatch.setattr("backend.main.NEO4J_PASSWORD", neo4j_password)
  monkeypatch.setattr("backend.main.REDIS_URL", redis_url)
  monkeypatch.setattr(
    "backend.main.AsyncConnectionPool", FakeLifespanConnectionPool
  )
  monkeypatch.setattr(
    "backend.main.AsyncGraphDatabase", FakeLifespanGraphDatabase
  )

  with TestClient(app) as client:
    return client.get("/health")


def test_L1_001_lifespan_all_env_vars_set(monkeypatch):
  """
  L1-001 via lifespan: with POSTGRES_DSN, all three Neo4j vars and REDIS_URL
  set, startup creates all three services and /health reports all True.
  """
  resp = lifespan_health(
    monkeypatch,
    postgres_dsn=TEST_POSTGRES_DSN,
    redis_url=TEST_REDIS_URL,
    **TEST_NEO4J_ENV,
  )

  assert resp.status_code == 200
  assert resp.json() == {
    "status": "ok",
    "postgres": True,
    "neo4j": True,
    "redis": True,
  }


def test_L1_002_lifespan_postgres_dsn_not_set(monkeypatch):
  """
  L1-002 via lifespan: with POSTGRES_DSN unset, no pool is created, and
  /health returns 200 with postgres: False.
  """
  resp = lifespan_health(
    monkeypatch,
    redis_url=TEST_REDIS_URL,
    **TEST_NEO4J_ENV,
  )

  assert resp.status_code == 200
  assert resp.json()["postgres"] is False


def test_L1_003_lifespan_neo4j_uri_not_set(monkeypatch):
  """
  L1-003 via lifespan: with NEO4J_URI unset (user and password still set),
  no driver is created, and /health returns 200 with neo4j: False.
  """
  resp = lifespan_health(
    monkeypatch,
    postgres_dsn=TEST_POSTGRES_DSN,
    redis_url=TEST_REDIS_URL,
    neo4j_user="neo4j",
    neo4j_password="pw",
  )

  assert resp.status_code == 200
  assert resp.json()["neo4j"] is False


def test_L1_003b_lifespan_neo4j_partial_credentials_is_not_connected(
  monkeypatch,
):
  """
  Extra branch: lifespan only builds the Neo4j driver when NEO4J_URI,
  NEO4J_USER and NEO4J_PASSWORD are ALL set. With the URI and user set but
  the password missing, /health must still return 200 with neo4j: False.
  """
  resp = lifespan_health(
    monkeypatch,
    postgres_dsn=TEST_POSTGRES_DSN,
    redis_url=TEST_REDIS_URL,
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
  )

  assert resp.status_code == 200
  assert resp.json()["neo4j"] is False


def test_L1_004_lifespan_redis_url_not_set(monkeypatch):
  """
  L1-004 via lifespan: with REDIS_URL unset, RedisCache(None) has no client,
  and /health returns 200 with redis: False.
  """
  resp = lifespan_health(
    monkeypatch,
    postgres_dsn=TEST_POSTGRES_DSN,
    **TEST_NEO4J_ENV,
  )

  assert resp.status_code == 200
  assert resp.json()["redis"] is False


def test_L1_005_lifespan_no_env_vars_set(monkeypatch):
  """
  L1-005 via lifespan: with no env vars at all, startup still succeeds and
  /health returns 200, status "ok", with all three service flags False.
  """
  resp = lifespan_health(monkeypatch)

  assert resp.status_code == 200
  assert resp.json() == {
    "status": "ok",
    "postgres": False,
    "neo4j": False,
    "redis": False,
  }

def test_L1_006_lifespan_response_always_contains_required_keys(monkeypatch):
    configurations = [
        (postgres, neo4j, redis)
        for postgres in [True, False]
        for neo4j in [True, False]
        for redis in [True, False]
    ]

    for postgres, neo4j, redis in configurations:
        response = lifespan_health(
            monkeypatch,
            postgres_dsn=TEST_POSTGRES_DSN if postgres else None,
            neo4j_uri=TEST_NEO4J_ENV["neo4j_uri"] if neo4j else None,
            neo4j_user=TEST_NEO4J_ENV["neo4j_user"] if neo4j else None,
            neo4j_password=TEST_NEO4J_ENV["neo4j_password"] if neo4j else None,
            redis_url=TEST_REDIS_URL if redis else None,
        )

        assert response.status_code == 200
        data = response.json()

        assert REQUIRED_KEYS.issubset(data.keys())