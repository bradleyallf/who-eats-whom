"""
Endpoint tests for the Who Eats Whom backend (FastAPI).

The tests are organized by layer, with one section per layer below:

  Layer 1: Infrastructure & Config (/health,  /api/v1/version, CORS, Postgres unavailable (any endpoint))
  
  Layer 2: ETL Version Resolution

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

Run all tests - python -m pytest backend/tests/ -v
Run one test - python -m pytest backend/tests/test_endpoints.py::{name of the test} -v
"""
import importlib
from datetime import datetime

from fastapi.testclient import TestClient

import backend.main as main_module
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

# ---------- /api/v1/version ----------
#
# backend.main sets APP_VERSION once, at import time:
#
#   APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
#
# Patching the constant would not test that line (the "fall back to 0.1.0"
# case would just compare the patched value to itself). So these tests set or
# unset the real APP_VERSION env var and then reload backend.main, which
# re-runs the os.getenv line. The module is reloaded again afterwards so
# later tests see the original configuration.
 
def version_response(monkeypatch, app_version=None):
  """
  Call GET /api/v1/version with APP_VERSION set (or unset) in the environment.
 
  Sets or removes the APP_VERSION env var, reloads backend.main so the
  os.getenv("APP_VERSION", "0.1.0") line runs again, sends the request, and
  then restores the environment and reloads the module once more so other
  tests are not affected.
 
  Args:
    monkeypatch: pytest's monkeypatch fixture (used to set/unset the env var
      and to undo that afterwards).
    app_version: value for APP_VERSION, or None to leave it unset.
 
  Returns:
    The Response from GET /api/v1/version.
  """
  if app_version is None:
    monkeypatch.delenv("APP_VERSION", raising=False)
  else:
    monkeypatch.setenv("APP_VERSION", app_version)
 
  importlib.reload(main_module)
  try:
    return TestClient(main_module.app).get("/api/v1/version")
  finally:
    monkeypatch.undo()
    importlib.reload(main_module)
 
 
def test_L1_007_version_returns_value_from_env_var(monkeypatch):
  """
  L1-007: With APP_VERSION=2.0.0, GET /api/v1/version returns 200 and
  {version: "2.0.0"}.
  """
  resp = version_response(monkeypatch, app_version="2.0.0")
 
  assert resp.status_code == 200
  assert resp.json() == {"version": "2.0.0"}
 
 
def test_L1_008_version_falls_back_to_default_when_env_var_unset(monkeypatch):
  """
  L1-008: With APP_VERSION unset, GET /api/v1/version returns 200 and the
  default {version: "0.1.0"}.
  """
  resp = version_response(monkeypatch)
 
  assert resp.status_code == 200
  assert resp.json() == {"version": "0.1.0"}
 
 
def test_L1_009_version_is_a_string_not_a_number(monkeypatch):
  """
  L1-009: With APP_VERSION=2.0.0, the version field in the JSON body is the
  string "2.0.0", not the number 2.0.
  """
  resp = version_response(monkeypatch, app_version="2.0.0")
 
  version = resp.json()["version"]
 
  assert resp.status_code == 200
  assert isinstance(version, str)
  assert version == "2.0.0"
  assert version != 2.0

# ---------- CORS ----------
#
# backend.main builds its list of allowed origins and adds the CORS
# middleware when the module is imported:
#
#   allowed_origins_env = os.getenv("CORS_ALLOW_ORIGINS")
#   app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, ...)
#
# Like APP_VERSION, this is fixed at import time, so these tests set or unset
# the real CORS_ALLOW_ORIGINS env var, reload backend.main to rebuild the app
# with the new middleware settings, and restore everything afterwards.
#
# A browser-style cross-origin request is simulated by sending an Origin
# header. CORSMiddleware answers an allowed origin by echoing it back in the
# Access-Control-Allow-Origin response header, and leaves the header out for a
# disallowed origin.
 
DEFAULT_CORS_ORIGINS = ["http://localhost:4200", "http://127.0.0.1:4200"]
 
 
def cors_response(monkeypatch, origin, cors_origins=None):
  """
  Call GET /health with an Origin header, using the given CORS_ALLOW_ORIGINS.
 
  Sets or removes the CORS_ALLOW_ORIGINS env var, reloads backend.main so the
  app is rebuilt with matching CORS middleware, sets empty service handles on
  the new app's state (the lifespan is not run, and /health reads them), sends
  the request, then restores the environment and reloads the module again so
  other tests are not affected.
 
  Args:
    monkeypatch: pytest's monkeypatch fixture (used to set/unset the env var
      and to undo that afterwards).
    origin: value for the request's Origin header.
    cors_origins: raw value for CORS_ALLOW_ORIGINS (e.g. "https://a.com,
      https://b.com"), or None to leave it unset so the defaults apply.
 
  Returns:
    The Response from GET /health.
  """
  if cors_origins is None:
    monkeypatch.delenv("CORS_ALLOW_ORIGINS", raising=False)
  else:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", cors_origins)
 
  importlib.reload(main_module)
  try:
    cors_app = main_module.app
    cors_app.state.pg_pool = None
    cors_app.state.neo4j_driver = None
    cors_app.state.redis_cache = main_module.RedisCache(None)
    return TestClient(cors_app).get("/health", headers={"Origin": origin})
  finally:
    monkeypatch.undo()
    importlib.reload(main_module)
 
 
def allow_origin_header(resp):
  """
  Return the Access-Control-Allow-Origin header of a response, or None if the
  header is absent. (Header names are case-insensitive.)
  """
  return resp.headers.get("access-control-allow-origin")
 
 
def test_L1_010_cors_allows_default_localhost_origin(monkeypatch):
  """
  L1-010: With CORS_ALLOW_ORIGINS unset, a request from the default origin
  http://localhost:4200 gets that origin echoed in Access-Control-Allow-Origin.
  """
  resp = cors_response(monkeypatch, "http://localhost:4200")
 
  assert resp.status_code == 200
  assert allow_origin_header(resp) == "http://localhost:4200"
 
 
def test_L1_011_cors_allows_default_127_0_0_1_origin(monkeypatch):
  """
  L1-011: With CORS_ALLOW_ORIGINS unset, a request from the default origin
  http://127.0.0.1:4200 gets that origin echoed back.
  """
  resp = cors_response(monkeypatch, "http://127.0.0.1:4200")
 
  assert resp.status_code == 200
  assert allow_origin_header(resp) == "http://127.0.0.1:4200"
 
 
def test_L1_012_cors_blocks_unlisted_origin(monkeypatch):
  """
  L1-012: A request from an origin not in the allowed list (http://evil.com)
  gets no Access-Control-Allow-Origin header, so a browser would block it.
  """
  resp = cors_response(monkeypatch, "http://evil.com")
 
  assert allow_origin_header(resp) is None
 
 
def test_L1_013_cors_custom_origin_from_env_var_is_allowed(monkeypatch):
  """
  L1-013: With CORS_ALLOW_ORIGINS=https://myapp.com, a request from
  https://myapp.com gets that origin echoed back.
  """
  resp = cors_response(
    monkeypatch,
    "https://myapp.com",
    cors_origins="https://myapp.com",
  )
 
  assert resp.status_code == 200
  assert allow_origin_header(resp) == "https://myapp.com"
 
 
def test_L1_014_cors_multiple_custom_origins_each_work(monkeypatch):
  """
  L1-014: With CORS_ALLOW_ORIGINS=https://a.com,https://b.com, each origin
  tested on its own gets exactly that origin back (not the other one, and not
  a combined value).
  """
  for origin in ("https://a.com", "https://b.com"):
    resp = cors_response(
      monkeypatch,
      origin,
      cors_origins="https://a.com,https://b.com",
    )
 
    assert resp.status_code == 200
    assert allow_origin_header(resp) == origin
 
 
def test_L1_015_cors_whitespace_in_env_var_is_handled(monkeypatch):
  """
  L1-015: With CORS_ALLOW_ORIGINS=" https://a.com , https://b.com " (spaces
  around the entries), the spaces are stripped and both origins still work.
  """
  for origin in ("https://a.com", "https://b.com"):
    resp = cors_response(
      monkeypatch,
      origin,
      cors_origins=" https://a.com , https://b.com ",
    )
 
    assert resp.status_code == 200
    assert allow_origin_header(resp) == origin
 
 
def test_L1_016_cors_custom_origins_replace_defaults(monkeypatch):
  """
  L1-016: Setting CORS_ALLOW_ORIGINS replaces the default list instead of
  adding to it. With only https://myapp.com configured, a request from the
  former default http://localhost:4200 gets no Access-Control-Allow-Origin
  header (and neither does the 127.0.0.1 default).
  """
  for default_origin in DEFAULT_CORS_ORIGINS:
    resp = cors_response(
      monkeypatch,
      default_origin,
      cors_origins="https://myapp.com",
    )
 
    assert allow_origin_header(resp) is None

# ---------- Postgres unavailable (503) ----------
#
# Every data endpoint starts with get_pg_pool(), which raises
# HTTPException(503, "Postgres connection is not configured.") when
# app.state.pg_pool is None. With POSTGRES_DSN unset, lifespan sets it to None.

POSTGRES_NOT_CONFIGURED_DETAIL = "Postgres connection is not configured."


def get_with_postgres_unset(monkeypatch, path):
  """
  Run the real lifespan with POSTGRES_DSN (and every other service env var)
  unset, then send GET to the given path.

  Args:
    monkeypatch: pytest's monkeypatch fixture (undoes patches after the test).
    path: URL path including any query string, e.g. "/api/v1/species".

  Returns:
    The Response from GET <path>.
  """
  monkeypatch.setattr("backend.main.POSTGRES_DSN", None)
  monkeypatch.setattr("backend.main.NEO4J_URI", TEST_NEO4J_ENV["neo4j_uri"])
  monkeypatch.setattr("backend.main.NEO4J_USER", TEST_NEO4J_ENV["neo4j_user"])
  monkeypatch.setattr("backend.main.NEO4J_PASSWORD", TEST_NEO4J_ENV["neo4j_password"])
  monkeypatch.setattr("backend.main.REDIS_URL", TEST_REDIS_URL)

  monkeypatch.setattr("backend.main.AsyncConnectionPool", FakeLifespanConnectionPool)
  monkeypatch.setattr("backend.main.AsyncGraphDatabase", FakeLifespanGraphDatabase)

  with TestClient(app) as client:
    return client.get(path)


def test_L1_017_data_endpoint_returns_503_when_postgres_not_configured(
  monkeypatch,
):
  """
  L1-017: With POSTGRES_DSN unset, GET /api/v1/species returns 503 and
  {detail: "Postgres connection is not configured."}.
  """
  resp = get_with_postgres_unset(monkeypatch, "/api/v1/species")

  assert resp.status_code == 503
  assert resp.json() == {"detail": POSTGRES_NOT_CONFIGURED_DETAIL}


def test_L1_018_503_is_consistent_across_postgres_dependent_endpoints(
  monkeypatch,
):
  """
  L1-018: With POSTGRES_DSN unset, each Postgres-dependent endpoint returns
  503 with the same error message.

  Query strings are included where an endpoint rejects the request before it
  reaches the Postgres check: /api/v1/predator-prey returns 400 unless a
  predator or prey id is given, and /api/v1/locations/search returns 422
  unless q has at least 2 characters.
  """
  paths = [
    "/api/v1/species",
    "/api/v1/species/search?q=ra",
    "/api/v1/species/41641",
    "/api/v1/food-web/summary",
    "/api/v1/interactions",
    "/api/v1/predator-prey?predator=41641",
    "/api/v1/locations/search?q=ra",
  ]

  for path in paths:
    resp = get_with_postgres_unset(monkeypatch, path)

    assert resp.status_code == 503, f"{path} returned {resp.status_code}"
    assert resp.json() == {"detail": POSTGRES_NOT_CONFIGURED_DETAIL}, (
      f"{path} returned a different error body"
    )

# =========================================================================
# Layer 2: ETL Version Resolution -- default version (no etl_version param)
#
# Every data endpoint calls resolve_etl_version_id(pool, etl_version) first.
# With no etl_version query parameter it reads every version named in
# ACTIVE_ETL_VERSIONS (default "local-dev,2026-08-26-api"):
#
#   SELECT id, version FROM etl_versions WHERE version = ANY(%s) ORDER BY id
#
# and returns {"ids": [...], "version": "a+b"} (names joined with "+"). It
# raises 404 "No ETL version found. Load data first." when no rows come back.
# /api/v1/species is used to observe the result: its response body carries the
# resolved label in "etl_version".
#
# NOTE: the plain-English cases L2-001 and L2-003 describe "latest by
# loaded_at". The current code no longer does that (that logic is the
# commented-out block above resolve_etl_version_id), so those two tests check
# the current ACTIVE_ETL_VERSIONS behaviour instead.
#
# The fake pool below cannot run SQL. It emulates only the etl_versions lookup
# (filter by the requested names, order by id) and records every query so tests
# can inspect what the app asked for.
#
# Fake class names are prefixed with "FakeEtl" to distinguish them from the
# Layer 1 fakes.
# =========================================================================

NO_ETL_VERSION_DETAIL = "No ETL version found. Load data first."


class FakeEtlRedisCache:
  """Stand-in for RedisCache: never has a cached value, so producers always run."""

  client = None

  async def get_json(self, key):
    return None

  async def set_json(self, key, value, ttl_seconds=None):
    pass

  async def close(self):
    pass


class FakeEtlCursor:
  """
  Stand-in for a psycopg cursor. Answers the etl_versions lookup from the
  pool's in-memory rows (filtered by the requested names, ordered by id) and
  returns no rows for any other query (e.g. the species listing).
  """

  def __init__(self, pool):
    self.pool = pool
    self.rows = []

  async def __aenter__(self):
    return self

  async def __aexit__(self, *exc_info):
    return False

  async def execute(self, sql, params=None):
    self.pool.executed.append((sql, params))
    if "FROM etl_versions" in sql:
      names = params[0]
      matching = [v for v in self.pool.etl_versions if v["version"] in names]
      matching.sort(key=lambda v: v["id"])
      self.rows = [{"id": v["id"], "version": v["version"]} for v in matching]
    else:
      self.rows = []

  async def fetchall(self):
    return self.rows

  async def fetchone(self):
    return self.rows[0] if self.rows else None


class FakeEtlConnection:
  """Stand-in for a pooled connection; hands out FakeEtlCursor objects."""

  def __init__(self, pool):
    self.pool = pool

  async def __aenter__(self):
    return self

  async def __aexit__(self, *exc_info):
    return False

  def cursor(self, *args, **kwargs):
    return FakeEtlCursor(self.pool)


class FakeEtlConnectionPool:
  """
  Stand-in for AsyncConnectionPool backed by an in-memory etl_versions table.

  Attributes:
    etl_versions: list of {"id", "version", "loaded_at"} dicts (the table).
    executed: every (sql, params) the app ran, in order.
  """

  def __init__(self, etl_versions):
    self.etl_versions = etl_versions
    self.executed = []

  def connection(self):
    return FakeEtlConnection(self)

  async def close(self):
    pass


def etl_version_row(version_id, version, loaded_at=None):
  """Build one row of the fake etl_versions table."""
  return {"id": version_id, "version": version, "loaded_at": loaded_at}


def etl_lookups(pool):
  """Return the (sql, params) of every etl_versions lookup the app ran."""
  return [
    (sql, params) for sql, params in pool.executed if "FROM etl_versions" in sql
  ]


def species_with_etl_versions(monkeypatch, etl_versions, active_versions=None):
  """
  Run the real lifespan with every service env var unset, swap in a fake
  Postgres pool holding the given etl_versions rows, and send
  GET /api/v1/species with no etl_version parameter.

  Args:
    monkeypatch: pytest's monkeypatch fixture (undoes patches after the test).
    etl_versions: list of rows made with etl_version_row().
    active_versions: list to use for ACTIVE_ETL_VERSIONS, or None to keep the
      module default.

  Returns:
    (response, pool): the Response from GET /api/v1/species and the fake pool,
    so tests can inspect the queries the app ran.
  """
  monkeypatch.setattr("backend.main.POSTGRES_DSN", None)
  monkeypatch.setattr("backend.main.NEO4J_URI", None)
  monkeypatch.setattr("backend.main.NEO4J_USER", None)
  monkeypatch.setattr("backend.main.NEO4J_PASSWORD", None)
  monkeypatch.setattr("backend.main.REDIS_URL", None)
  if active_versions is not None:
    monkeypatch.setattr("backend.main.ACTIVE_ETL_VERSIONS", active_versions)

  pool = FakeEtlConnectionPool(etl_versions)
  with TestClient(app) as client:
    # Lifespan has run (pg_pool is None); install the fakes before the request.
    app.state.pg_pool = pool
    app.state.redis_cache = FakeEtlRedisCache()
    return client.get("/api/v1/species"), pool


def test_L2_001_no_param_uses_active_etl_versions(monkeypatch):
  """
  L2-001 (adapted): with two versions loaded and only "v-new" in
  ACTIVE_ETL_VERSIONS, GET /api/v1/species with no etl_version parameter
  returns 200 with etl_version "v-new", and the app asked Postgres for exactly
  the active names (the unlisted "v-old" is ignored).
  """
  etl_versions = [
    etl_version_row(1, "v-old", datetime(2026, 1, 1)),
    etl_version_row(2, "v-new", datetime(2026, 2, 1)),
  ]

  resp, pool = species_with_etl_versions(
    monkeypatch, etl_versions, active_versions=["v-new"]
  )

  assert resp.status_code == 200
  assert resp.json()["etl_version"] == "v-new"
  assert [params for _, params in etl_lookups(pool)] == [(["v-new"],)]


def test_L2_001b_all_active_versions_are_read_together(monkeypatch):
  """
  Extra branch: with both versions in ACTIVE_ETL_VERSIONS, the response label
  joins them with "+" and both ids are passed on to the species query.
  """
  etl_versions = [
    etl_version_row(1, "v-old", datetime(2026, 1, 1)),
    etl_version_row(2, "v-new", datetime(2026, 2, 1)),
  ]

  resp, pool = species_with_etl_versions(
    monkeypatch, etl_versions, active_versions=["v-old", "v-new"]
  )

  species_queries = [
    params for sql, params in pool.executed if "FROM species" in sql
  ]

  assert resp.status_code == 200
  assert resp.json()["etl_version"] == "v-old+v-new"
  assert species_queries[0][0] == [1, 2]


def test_L2_002_no_etl_versions_returns_404(monkeypatch):
  """
  L2-002: with the etl_versions table empty, GET /api/v1/species returns 404
  and {detail: "No ETL version found. Load data first."}.
  """
  resp, _ = species_with_etl_versions(monkeypatch, [])

  assert resp.status_code == 404
  assert resp.json() == {"detail": NO_ETL_VERSION_DETAIL}


def test_L2_002b_versions_exist_but_none_are_active_returns_404(monkeypatch):
  """
  Extra branch: versions are loaded but none of them is named in
  ACTIVE_ETL_VERSIONS. The lookup finds no rows, so the endpoint returns the
  same 404 (even though the table is not empty).
  """
  etl_versions = [etl_version_row(1, "v-unlisted", datetime(2026, 1, 1))]

  resp, _ = species_with_etl_versions(
    monkeypatch, etl_versions, active_versions=["v-listed"]
  )

  assert resp.status_code == 404
  assert resp.json() == {"detail": NO_ETL_VERSION_DETAIL}


def species_with_active_versions_env(monkeypatch, etl_versions, env_value=None):
  """
  Like species_with_etl_versions, but first sets (or unsets) the real
  ACTIVE_ETL_VERSIONS env var and reloads backend.main, so the line that parses
  the env var runs again. Restores the environment and reloads the module
  afterwards so other tests are not affected.

  Args:
    monkeypatch: pytest's monkeypatch fixture.
    etl_versions: list of rows made with etl_version_row().
    env_value: value for ACTIVE_ETL_VERSIONS, or None to leave it unset.

  Returns:
    (response, pool), as returned by species_with_etl_versions.
  """
  if env_value is None:
    monkeypatch.delenv("ACTIVE_ETL_VERSIONS", raising=False)
  else:
    monkeypatch.setenv("ACTIVE_ETL_VERSIONS", env_value)

  importlib.reload(main_module)
  try:
    return species_with_etl_versions(monkeypatch, etl_versions)
  finally:
    monkeypatch.undo()
    importlib.reload(main_module)


def test_L2_003_default_active_versions_when_env_var_unset(monkeypatch):
  """
  L2-003 (current behaviour): with ACTIVE_ETL_VERSIONS unset, the default
  "local-dev,2026-08-26-api" is used. A request with no etl_version parameter
  asks Postgres for those two names, and the label joins them with "+".
  """
  etl_versions = [
    etl_version_row(1, "local-dev"),
    etl_version_row(2, "2026-08-26-api"),
  ]

  resp, pool = species_with_active_versions_env(monkeypatch, etl_versions)

  assert resp.status_code == 200
  assert resp.json()["etl_version"] == "local-dev+2026-08-26-api"
  assert [params for _, params in etl_lookups(pool)] == [
    (["local-dev", "2026-08-26-api"],)
  ]