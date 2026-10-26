"""
Endpoint tests for the Who Eats Whom backend (FastAPI).

The tests are organized by layer, with one section per layer below:

  Layer 1: Infrastructure & Config (/health,  /api/v1/version, CORS, Postgres unavailable (any endpoint))

  Layer 2: ETL Version Resolution

Conventions used throughout this file:
  * Tests call the API in-process through FastAPI's TestClient, so no separate
    server needs to be started.
  * Nothing is faked and nothing is written. Tests that need a service use the
    real one (Postgres, Neo4j, Redis), configured through the same environment
    variables the app reads (POSTGRES_DSN, NEO4J_URI, NEO4J_USER,
    NEO4J_PASSWORD, REDIS_URL). Tests only ever read from the database.
  * Tests that need a service which is not configured are skipped, so start
    your services and export those variables before running.
  * FastAPI's lifespan is exercised through TestClient so the tests cover
    the environment-variable configuration and startup logic in
    backend/main.py.
  * Test names follow the plain-English test IDs, e.g. test_L1_002_...
    covers test case L1-002.

Run all tests - python -m pytest backend/tests/ -v
Run one test - python -m pytest backend/tests/test_endpoints_L1_L2.py::{name of the test} -v
"""
import psycopg

from concurrent.futures import ThreadPoolExecutor

import pytest
import importlib

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.main import app


# The real service settings, read once when this file is imported (before any
# test patches anything). They come from the same environment variables the app
# reads. A value of None means that variable is not set in your environment.
REAL_POSTGRES_DSN = main_module.POSTGRES_DSN
REAL_NEO4J = {
  "neo4j_uri": main_module.NEO4J_URI,
  "neo4j_user": main_module.NEO4J_USER,
  "neo4j_password": main_module.NEO4J_PASSWORD,
}
REAL_REDIS_URL = main_module.REDIS_URL


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
# Where a test says a service is "set", it uses the real value from your
# environment (so the real service must be running). Where a test says a
# service is "unset", the app is given None for it and nothing connects.
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


def require_real_services():
  """Skip the test unless Postgres, Neo4j and Redis are all configured."""
  if not (
    REAL_POSTGRES_DSN
    and all(REAL_NEO4J.values())
    and REAL_REDIS_URL
  ):
    pytest.skip(
      "POSTGRES_DSN, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD and REDIS_URL "
      "must all be set (and the services running)"
    )


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
  set"), then starts the app with `with TestClient(app)` so startup and
  shutdown both run. Nothing is replaced with a fake: a value that is passed in
  is used to connect to the real service.

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

  with TestClient(app) as client:
    return client.get("/health")


def test_L1_001_lifespan_all_env_vars_set(monkeypatch):
  """
  L1-001 via lifespan: with POSTGRES_DSN, all three Neo4j vars and REDIS_URL
  set, startup creates all three services and /health reports all True.
  """
  require_real_services()

  resp = lifespan_health(
    monkeypatch,
    postgres_dsn=REAL_POSTGRES_DSN,
    redis_url=REAL_REDIS_URL,
    **REAL_NEO4J,
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
    redis_url=REAL_REDIS_URL,
    **REAL_NEO4J,
  )

  assert resp.status_code == 200
  assert resp.json() == {
      "status": "ok",
      "postgres": False,
      "neo4j": True,
      "redis": True,
    }


def test_L1_003_lifespan_neo4j_uri_not_set(monkeypatch):
  """
  L1-003 via lifespan: with NEO4J_URI unset (user and password still set),
  no driver is created, and /health returns 200 with neo4j: False.
  """
  resp = lifespan_health(
    monkeypatch,
    postgres_dsn=REAL_POSTGRES_DSN,
    redis_url=REAL_REDIS_URL,
    neo4j_user=REAL_NEO4J["neo4j_user"],
    neo4j_password=REAL_NEO4J["neo4j_password"],
  )

  assert resp.status_code == 200
  assert resp.json() == {
      "status": "ok",
      "postgres": True,
      "neo4j": False,
      "redis": True,
    }


def test_L1_003b_lifespan_neo4j_partial_credentials_is_not_connected(
  monkeypatch,
):
  """
  Extra branch: lifespan only builds the Neo4j driver when NEO4J_URI,
  NEO4J_USER and NEO4J_PASSWORD are ALL set. With the URI and user set but
  the password missing, /health must still return 200 with neo4j: False.
  """
  if not (REAL_NEO4J["neo4j_uri"] and REAL_NEO4J["neo4j_user"]):
    pytest.skip("NEO4J_URI and NEO4J_USER must be set")

  resp = lifespan_health(
    monkeypatch,
    postgres_dsn=REAL_POSTGRES_DSN,
    redis_url=REAL_REDIS_URL,
    neo4j_uri=REAL_NEO4J["neo4j_uri"],
    neo4j_user=REAL_NEO4J["neo4j_user"],
  )

  assert resp.status_code == 200
  assert resp.json() == {
      "status": "ok",
      "postgres": True,
      "neo4j": False,
      "redis": True,
    }


def test_L1_004_lifespan_redis_url_not_set(monkeypatch):
  """
  L1-004 via lifespan: with REDIS_URL unset, RedisCache(None) has no client,
  and /health returns 200 with redis: False.
  """
  resp = lifespan_health(
    monkeypatch,
    postgres_dsn=REAL_POSTGRES_DSN,
    **REAL_NEO4J,
  )

  assert resp.status_code == 200
  assert resp.json() == {
      "status": "ok",
      "postgres": True,
      "neo4j": True,
      "redis": False,
    }


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
            postgres_dsn=REAL_POSTGRES_DSN if postgres else None,
            neo4j_uri=REAL_NEO4J["neo4j_uri"] if neo4j else None,
            neo4j_user=REAL_NEO4J["neo4j_user"] if neo4j else None,
            neo4j_password=REAL_NEO4J["neo4j_password"] if neo4j else None,
            redis_url=REAL_REDIS_URL if redis else None,
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
  unset, then send GET to the given path. With nothing configured, the app
  connects to nothing, so no fakes are needed.

  Args:
    monkeypatch: pytest's monkeypatch fixture (undoes patches after the test).
    path: URL path including any query string, e.g. "/api/v1/species".

  Returns:
    The Response from GET <path>.
  """
  monkeypatch.setattr("backend.main.POSTGRES_DSN", None)
  monkeypatch.setattr("backend.main.NEO4J_URI", None)
  monkeypatch.setattr("backend.main.NEO4J_USER", None)
  monkeypatch.setattr("backend.main.NEO4J_PASSWORD", None)
  monkeypatch.setattr("backend.main.REDIS_URL", None)

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
# Layer 2: ETL Version Resolution -- resolve_etl_version_id
#
# Every data endpoint calls resolve_etl_version_id(pool, etl_version) first:
#
#   names = [etl_version] if etl_version else ACTIVE_ETL_VERSIONS
#   SELECT id, version FROM etl_versions WHERE version = ANY(%s) ORDER BY id
#
# It returns {"ids": [...], "version": "a+b"} (names joined with "+") and
# raises 404 "No ETL version found. Load data first." when no rows come back.
#
#   - No etl_version parameter (or an empty one): every version named in
#     ACTIVE_ETL_VERSIONS is read together. ACTIVE_ETL_VERSIONS is parsed from
#     the env var of the same name when backend.main is imported
#     (default "local-dev,2026-08-26-api").
#   - etl_version=<name>: only that version is read, even if it is not active.
#     A name that matches no row (unknown, whitespace-only, very long, unicode,
#     or containing SQL) gives the 404 above.
#
# /api/v1/species is the endpoint used to observe the result, because its body
# carries the resolved label in "etl_version". L2-008 also sends the override
# to interactions, predator-prey, locations/search and food-web/summary. The
# last two do not return etl_version, so for them the test can only check that
# the request succeeds.
#
# How the tests are built:
#   - They run against the real services your app uses (the same environment
#     variables as the app: POSTGRES_DSN, etc.), through the real FastAPI
#     lifespan. Nothing is faked and nothing is written: tests only read.
#   - Expected values come from reading etl_versions directly, so the tests
#     still pass when the loaded versions change.
#   - If POSTGRES_DSN is not set, the tests skip.
#
# Not tested (they need data changed or a service to fail):
#   L2-002, L2-003, L2-010, L2-011, L2-012 (need specific etl_versions rows)
#   and L2-013 (Postgres going down). L2-001b and L2-001c (two active versions,
#   default env var) are also dropped: they depended on seeded versions.
#
# Differences from the plain-English cases:
#   - The code selects versions by name (ACTIVE_ETL_VERSIONS), not by latest
#     loaded_at, so L2-001 and L2-006 are adapted to "active version".
#   - L2-014 checks the real etl_versions rows before and after the request.
#   - L2-017 shows that resolution keeps no shared state between interleaved
#     requests.
# =========================================================================

NO_ETL_VERSION_DETAIL = "No ETL version found. Load data first."


# ---------- Read-only helpers ----------

@pytest.fixture
def real_database():
  """Skip the test unless the real database is configured."""
  if not REAL_POSTGRES_DSN:
    pytest.skip("POSTGRES_DSN is not set; start the services and export the env vars")
  yield


def real_etl_versions():
  """Read-only: the (id, version) rows currently in etl_versions, ordered by id."""
  with psycopg.connect(REAL_POSTGRES_DSN) as conn:
    return conn.execute("SELECT id, version FROM etl_versions ORDER BY id").fetchall()


def active_version_label():
  """
  The etl_version label the app should report when no version is requested: the
  names in ACTIVE_ETL_VERSIONS that exist in etl_versions, ordered by id, joined
  with "+".
  """
  active = set(main_module.ACTIVE_ETL_VERSIONS)
  label = "+".join(v for _, v in real_etl_versions() if v in active)
  if not label:
    pytest.skip("none of ACTIVE_ETL_VERSIONS exist in etl_versions")
  return label


def any_real_version_name():
  """The name of one version that really exists in etl_versions."""
  versions = real_etl_versions()
  if not versions:
    pytest.skip("etl_versions is empty")
  return versions[0][1]


def get_from_real_app(path, params=None):
  """Run the real lifespan (real Postgres, Neo4j and Redis) and send one GET."""
  with TestClient(app) as client:
    return client.get(path, params=params)


# ---------- Feature: Default version (no etl_version param) ----------
# L2-003 (latest version by loaded_at, not id) and L2-011 (identical loaded_at)
# are not tested: the current code never reads loaded_at, and testing them would
# mean inserting rows.


def test_L2_001_returns_active_etl_version_when_none_specified(real_database):
  """
  L2-001 (adapted): GET /api/v1/species with no etl_version parameter returns
  200 and an etl_version equal to the active versions that exist in the
  database, joined with "+".
  """
  resp = get_from_real_app("/api/v1/species")

  assert resp.status_code == 200
  assert resp.json()["etl_version"] == active_version_label()


# ---------- Feature: Explicit version override (etl_version param) ----------
def test_L2_004_explicit_valid_version_returns_data_for_that_version(real_database):
  """
  L2-004: GET /api/v1/species?etl_version=<a version that exists> returns 200
  and reports exactly that version.
  """
  name = any_real_version_name()

  resp = get_from_real_app("/api/v1/species", {"etl_version": name})

  assert resp.status_code == 200
  assert resp.json()["etl_version"] == name


def test_L2_005_explicit_version_that_does_not_exist_returns_404(real_database):
  """
  L2-005: GET /api/v1/species?etl_version=does-not-exist returns 404 and
  {detail: "No ETL version found. Load data first."}.
  """
  resp = get_from_real_app("/api/v1/species", {"etl_version": "does-not-exist"})

  assert resp.status_code == 404
  assert resp.json() == {"detail": NO_ETL_VERSION_DETAIL}


def test_L2_006_empty_string_etl_version_falls_back_to_default(real_database):
  """
  L2-006: GET /api/v1/species?etl_version= (empty string) is treated as "no
  override": the active versions are used and the response is 200, not 404.
  """
  resp = get_from_real_app("/api/v1/species", {"etl_version": ""})

  assert resp.status_code == 200
  assert resp.json()["etl_version"] == active_version_label()


def test_L2_007_whitespace_etl_version_returns_404_not_500(real_database):
  """
  L2-007: GET /api/v1/species?etl_version=%20%20%20 (spaces only) is not empty,
  so it is looked up as a literal version name, matches nothing, and returns the
  404. It does not fall back to the active versions and does not crash.
  """
  resp = get_from_real_app("/api/v1/species", {"etl_version": "   "})

  assert resp.status_code == 404
  assert resp.json() == {"detail": NO_ETL_VERSION_DETAIL}


# One row per endpoint: (path, extra query params, does the body include
# etl_version?). locations/search and food-web/summary do not return the field,
# so for them the test can only check that the request succeeds.
ETL_VERSION_ENDPOINTS = [
  ("/api/v1/species", {}, True),
  ("/api/v1/interactions", {}, True),
  ("/api/v1/predator-prey", {"predator": 1}, True),
  ("/api/v1/locations/search", {"q": "Ra"}, False),
  ("/api/v1/food-web/summary", {}, False),
]


@pytest.mark.parametrize(
  "path, extra_params, returns_version", ETL_VERSION_ENDPOINTS
)
def test_L2_008_etl_version_param_works_on_every_endpoint(
  real_database, path, extra_params, returns_version
):
  """
  L2-008: ?etl_version=<a version that exists> is accepted by every endpoint
  that takes it. Each returns 200 (never 500), and the endpoints that include
  etl_version in their body report that version.
  """
  name = any_real_version_name()

  resp = get_from_real_app(path, {**extra_params, "etl_version": name})

  assert resp.status_code == 200
  if returns_version:
    assert resp.json()["etl_version"] == name


# Feature: ETL version consistency across endpoints

def test_L2_009_response_includes_etl_version_field(real_database):
  """
  L2-009: GET /api/v1/species with the default version returns a body that
  contains an etl_version field equal to the version that was used.
  """
  resp = get_from_real_app("/api/v1/species")

  assert resp.status_code == 200
  assert "etl_version" in resp.json()
  assert resp.json()["etl_version"] == active_version_label()


def test_L2_014_special_characters_in_version_are_passed_as_a_parameter(real_database):
  """
  L2-014: a version string containing SQL (v1'; DROP TABLE etl_versions;--)
  returns 404, and afterwards etl_versions still exists with the same rows.
  The check reads the real table before and after the request.
  """
  injection = "v1'; DROP TABLE etl_versions;--"
  rows_before = real_etl_versions()

  resp = get_from_real_app("/api/v1/species", {"etl_version": injection})

  assert resp.status_code == 404
  assert resp.json() == {"detail": NO_ETL_VERSION_DETAIL}
  assert real_etl_versions() == rows_before


def test_L2_015_very_long_version_string_returns_404(real_database):
  """
  L2-015: a 500-character etl_version returns 404 and does not crash.
  """
  resp = get_from_real_app("/api/v1/species", {"etl_version": "v" * 500})

  assert resp.status_code == 404
  assert resp.json() == {"detail": NO_ETL_VERSION_DETAIL}


def test_L2_016_unicode_version_string_returns_404(real_database):
  """
  L2-016: an etl_version with unicode characters (ҠҊ1) returns 404 and does
  not crash.
  """
  resp = get_from_real_app("/api/v1/species", {"etl_version": "ҠҊ1"})

  assert resp.status_code == 404
  assert resp.json() == {"detail": NO_ETL_VERSION_DETAIL}


def test_L2_017_concurrent_requests_resolve_same_version(real_database):
  """
  L2-017: 10 simultaneous requests to /api/v1/species with no etl_version
  parameter all return 200 with the same etl_version, through the real
  connection pool.
  """
  with TestClient(app) as client:
    with ThreadPoolExecutor(max_workers=10) as executor:
      responses = list(
        executor.map(lambda _: client.get("/api/v1/species"), range(10))
      )

  assert [r.status_code for r in responses] == [200] * 10
  assert {r.json()["etl_version"] for r in responses} == {active_version_label()}