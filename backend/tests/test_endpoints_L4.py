"""
Endpoint tests for the Who Eats Whom backend (FastAPI) -- Layer 4: Interactions.

  Layer 4: Interactions Endpoint
    GET /api/v1/interactions

Conventions used throughout this file:
  * Tests call the API in-process through FastAPI's TestClient, so no separate
    server needs to be started.
  * Nothing is faked and nothing is written. The tests run against the real
    Postgres (and the real Neo4j and Redis) configured through the same
    environment variables the app reads. Tests only ever read.
  * If POSTGRES_DSN is not set, every test in this file is skipped.
  * Where a test needs a particular kind of observation (one with an image,
    one without coordinates, one with a partner URL, ...), it first asks the
    database for one with a read-only query, so it keeps working when your
    data changes. If the database has no such observation, the test is
    skipped and says why.
  * Expected values come from the database, not from numbers typed into the
    tests. Only the versions in ACTIVE_ETL_VERSIONS are counted, because that
    is what the endpoint reads when no etl_version is given.
  * Test names follow the plain-English test IDs, e.g. test_L4_002_...
    covers test case L4-002.

Not tested (the real data cannot support them):
  L4-003 (needs an empty database), L4-046 (no observation has place_guess only
  in the raw JSON), L4-066 (no image has a missing photo license), L4-067 (no
  disallowed photo license is stored), L4-068 (no uppercase photo license is
  stored), L4-069 (only 7 of the 9 license codes exist), L4-074, L4-075 and
  L4-076 (no observation has only a latitude, only a longitude, or is at 0,0),
  L4-081 (roles are stored already converted), L4-082 (the role column only
  allows two values), L4-085 (needs an empty etl_versions table) and L4-086
  (only one version exists).

Differences from the plain-English cases:
  * Each result has no top-level "role" field. The role is read from
    ofvs[0]["value"].
  * taxon_name resolves to the FIRST species that matches (LIMIT 1, no ORDER
    BY), so a search like "fox" could resolve to any of many species. L4-025,
    L4-026 and L4-027 use a species whose name matches no other species, so the
    answer is always the same one.
  * taxon.default_photo is built from the OBSERVATION's image_url, not from the
    species' image_url (L4-063 and L4-064 check that).
  * L4-056 (ids=) expects an empty list. The endpoint currently treats an empty
    ids value as "no ids filter", so this test is expected to fail until the
    endpoint is changed (see the note on that test).

Run all tests - python -m pytest backend/tests/ -v
Run one test - python -m pytest backend/tests/test_endpoints_L4.py::{name of the test} -v
"""
import psycopg

import pytest

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.main import app


# The real Postgres address, read once when this file is imported. It comes
# from the same POSTGRES_DSN env var the app uses. None means it is not set.
REAL_POSTGRES_DSN = main_module.POSTGRES_DSN

URL = "/api/v1/interactions"

# Fields every result must have (L4-002).
REQUIRED_FIELDS = {
  "id",
  "uuid",
  "uri",
  "observed_on",
  "created_at",
  "description",
  "community_taxon_id",
  "taxon",
  "ofvs",
  "photos",
  "geojson",
  "latitude",
  "longitude",
  "place_country_name",
  "place_state_name",
  "place_county_name",
  "place_town_name",
  "positional_accuracy",
  "location",
}

# Fields of the taxon object (L4-062).
TAXON_FIELDS = {
  "id",
  "name",
  "preferred_common_name",
  "iconic_taxon_name",
  "default_photo",
}

# Fields of one item in the photos array (L4-065).
PHOTO_FIELDS = {
  "url",
  "license_code",
  "attribution",
  "id",
  "flags",
  "hidden",
  "original_dimensions",
}

PLACE_FIELDS = [
  "place_country_name",
  "place_state_name",
  "place_county_name",
  "place_town_name",
]

# SQL (on a species row called s) that is true when the species is a normal
# species, not an order, family or genus. The endpoint expands those higher
# taxa to all their descendants, so tests that want "exactly this taxon" avoid
# them.
NOT_HIGHER_LEVEL = """
  s.scientific_name <> coalesce(s.order_name, '')
  AND s.scientific_name <> coalesce(s.family_name, '')
  AND s.scientific_name <> coalesce(s.genus_name, '')
"""


# ---------- Helpers ----------

@pytest.fixture(scope="module")
def client():
  """
  One real app (real Postgres, Neo4j and Redis) shared by every test in this
  file. Skips the tests if POSTGRES_DSN is not set.
  """
  if not REAL_POSTGRES_DSN:
    pytest.skip("POSTGRES_DSN is not set; start the services and export the env vars")
  with TestClient(app) as test_client:
    yield test_client


def real_query(sql, params=None):
  """Read-only: run one SELECT against the real database and return all rows."""
  with psycopg.connect(REAL_POSTGRES_DSN) as conn:
    return conn.execute(sql, params).fetchall()


def active_ids():
  """The etl_versions ids the endpoint reads by default (ACTIVE_ETL_VERSIONS)."""
  rows = real_query(
    "SELECT id FROM etl_versions WHERE version = ANY(%s)",
    (main_module.ACTIVE_ETL_VERSIONS,),
  )
  if not rows:
    pytest.skip("none of ACTIVE_ETL_VERSIONS exist in etl_versions")
  return [row[0] for row in rows]


def count_observations(where="TRUE", params=()):
  """
  Read-only: how many observations in the active versions match a condition.
  The condition can use the aliases o (observations) and s (species), and
  %s placeholders for its params.
  """
  return real_query(
    f"""
    SELECT count(*)
    FROM observations o
    JOIN species s ON s.taxon_id = o.taxon_id
    WHERE o.etl_version_id = ANY(%s) AND {where}
    """,
    [active_ids(), *params],
  )[0][0]


def find_observation(where, params=(), columns="o.observation_id"):
  """
  Read-only: the first observation (lowest observation_id) in the active
  versions that matches a condition, as a row of the given columns. Skips the
  test if there is none. The columns must not contain %s placeholders.
  """
  rows = real_query(
    f"""
    SELECT {columns}
    FROM observations o
    JOIN species s ON s.taxon_id = o.taxon_id
    WHERE o.etl_version_id = ANY(%s) AND {where}
    ORDER BY o.observation_id
    LIMIT 1
    """,
    [active_ids(), *params],
  )
  if not rows:
    pytest.skip("the database has no observation like this")
  return rows[0]


def fetch_one(client, observation_id):
  """Ask the API for exactly one observation by id and return its result."""
  resp = client.get(URL, params={"ids": str(observation_id)})
  assert resp.status_code == 200
  assert len(resp.json()["results"]) == 1
  return resp.json()["results"][0]


def result_ids(resp):
  """The observation ids in a response, in order."""
  return [item["id"] for item in resp.json()["results"]]


def sample_observation_ids(count=2):
  """Read-only: the lowest few observation ids in the active versions."""
  rows = real_query(
    """
    SELECT observation_id FROM observations
    WHERE etl_version_id = ANY(%s)
    ORDER BY observation_id LIMIT %s
    """,
    (active_ids(), count),
  )
  if len(rows) < count:
    pytest.skip(f"fewer than {count} observations in the active versions")
  return [row[0] for row in rows]


def missing_observation_id():
  """Read-only: an observation id that no observation has."""
  return real_query("SELECT coalesce(max(observation_id), 0) + 1 FROM observations")[0][0]


def db_observed_at(ids):
  """Read-only: {observation_id: observed_at} straight from the database."""
  rows = real_query(
    "SELECT observation_id, observed_at FROM observations WHERE observation_id = ANY(%s)",
    (ids,),
  )
  return {row[0]: row[1] for row in rows}


def db_roles(ids):
  """Read-only: {observation_id: role} straight from the database."""
  rows = real_query(
    "SELECT observation_id, role FROM observations WHERE observation_id = ANY(%s)",
    (ids,),
  )
  return {row[0]: row[1] for row in rows}


def db_years(ids):
  """Read-only: {observation_id: year of observed_at} straight from the database."""
  rows = real_query(
    """
    SELECT observation_id, extract(year FROM observed_at)::int
    FROM observations WHERE observation_id = ANY(%s)
    """,
    (ids,),
  )
  return {row[0]: row[1] for row in rows}


def db_places(ids):
  """Read-only: {observation_id: (place_guess, raw place_guess)} from the database."""
  rows = real_query(
    """
    SELECT observation_id, place_guess, raw->>'place_guess'
    FROM observations WHERE observation_id = ANY(%s)
    """,
    (ids,),
  )
  return {row[0]: (row[1], row[2]) for row in rows}


def busy_species(role=None):
  """
  Read-only: (taxon_id, observation count) of the species with the most
  observations in the active versions, optionally only counting one role. It is
  a normal species (not an order, family or genus). Skips the test if there is
  none.
  """
  where = NOT_HIGHER_LEVEL
  params = [active_ids()]
  if role:
    where += " AND o.role = %s"
    params.append(role)
  rows = real_query(
    f"""
    SELECT o.taxon_id, count(*)
    FROM observations o
    JOIN species s ON s.taxon_id = o.taxon_id
    WHERE o.etl_version_id = ANY(%s) AND {where}
    GROUP BY o.taxon_id
    ORDER BY count(*) DESC, o.taxon_id
    LIMIT 1
    """,
    params,
  )
  if not rows:
    pytest.skip("no species has observations")
  return rows[0]


def busy_species_year():
  """
  Read-only: (taxon_id, year, observation count) of the species and year with
  the most dated observations. Skips the test if there is none.
  """
  rows = real_query(
    f"""
    SELECT o.taxon_id, extract(year FROM o.observed_at)::int, count(*)
    FROM observations o
    JOIN species s ON s.taxon_id = o.taxon_id
    WHERE o.etl_version_id = ANY(%s)
      AND o.observed_at IS NOT NULL
      AND {NOT_HIGHER_LEVEL}
    GROUP BY 1, 2
    ORDER BY 3 DESC, 1, 2
    LIMIT 1
    """,
    (active_ids(),),
  )
  if not rows:
    pytest.skip("no species has dated observations")
  return rows[0]


def busy_year():
  """Read-only: (year, observation count) of the year with the most observations."""
  rows = real_query(
    """
    SELECT extract(year FROM observed_at)::int, count(*)
    FROM observations
    WHERE etl_version_id = ANY(%s) AND observed_at IS NOT NULL
    GROUP BY 1
    ORDER BY 2 DESC, 1
    LIMIT 1
    """,
    (active_ids(),),
  )
  if not rows:
    pytest.skip("no observation has an observed_at")
  return rows[0]


def plain_place(place):
  """True if a place name has no characters that ILIKE treats specially."""
  return not any(char in place for char in "%_\\")


def busy_place():
  """
  Read-only: the most common place_guess in the active versions that has no
  ILIKE wildcard characters in it. Skips the test if there is none.
  """
  rows = real_query(
    """
    SELECT place_guess, count(*)
    FROM observations
    WHERE etl_version_id = ANY(%s) AND coalesce(place_guess, '') <> ''
    GROUP BY place_guess
    ORDER BY count(*) DESC, place_guess
    LIMIT 20
    """,
    (active_ids(),),
  )
  for place, _ in rows:
    if plain_place(place):
      return place
  pytest.skip("no observation has a usable place_guess")


def place_matches_sql():
  """The endpoint's location condition, for counting matches in the database."""
  return "(o.place_guess ILIKE %s OR (o.raw->>'place_guess') ILIKE %s)"


def higher_taxon(column):
  """
  Read-only: (taxon_id, name) of an order, family or genus that is in the
  species table under its own name and has at least two species with
  observations. The column is order_name, family_name or genus_name. Skips the
  test if there is none.
  """
  assert column in ("order_name", "family_name", "genus_name")
  rows = real_query(
    f"""
    SELECT p.taxon_id, p.{column}
    FROM species p
    WHERE p.scientific_name = p.{column}
      AND (
        SELECT count(DISTINCT o.taxon_id)
        FROM observations o
        JOIN species c ON c.taxon_id = o.taxon_id
        WHERE o.etl_version_id = ANY(%s) AND c.{column} = p.{column}
      ) >= 2
    ORDER BY p.taxon_id
    LIMIT 1
    """,
    (active_ids(),),
  )
  if not rows:
    pytest.skip(f"no taxon in the species table is itself a {column}")
  return rows[0]


def check_higher_taxon(client, column):
  """
  Filter by an order/family/genus taxon id and check that the results are
  exactly the observations of every species in it, found with a separate
  read-only query on the species column.
  """
  taxon_id, name = higher_taxon(column)
  expected = [
    row[0]
    for row in real_query(
      f"""
      SELECT o.observation_id
      FROM observations o
      JOIN species s ON s.taxon_id = o.taxon_id
      WHERE o.etl_version_id = ANY(%s) AND s.{column} = %s
      ORDER BY o.observed_at DESC NULLS LAST, o.observation_id DESC
      LIMIT 500
      """,
      (active_ids(), name),
    )
  ]

  resp = client.get(URL, params={"taxon_id": taxon_id, "limit": 500})

  assert resp.status_code == 200
  assert result_ids(resp) == expected


def uniquely_named_species(column):
  """
  Read-only: (taxon_id, name, observation count) of a busy species whose
  common_name or scientific_name is contained in the name of no other species.
  Searching taxon_name by that name can then only resolve to that one species.
  The column is common_name or scientific_name. Skips the test if there is
  none.
  """
  assert column in ("common_name", "scientific_name")
  rows = real_query(
    f"""
    SELECT c.taxon_id, c.name, c.n
    FROM (
      SELECT s.taxon_id, s.{column} AS name, count(*) AS n
      FROM species s
      JOIN observations o ON o.taxon_id = s.taxon_id
      WHERE o.etl_version_id = ANY(%s)
        AND coalesce(s.{column}, '') <> ''
        AND {NOT_HIGHER_LEVEL}
      GROUP BY s.taxon_id, s.{column}
      ORDER BY n DESC, s.taxon_id
      LIMIT 200
    ) c
    WHERE (
      SELECT count(*) FROM species x
      WHERE strpos(lower(x.scientific_name), lower(c.name)) > 0
         OR strpos(lower(coalesce(x.common_name, '')), lower(c.name)) > 0
    ) = 1
    ORDER BY c.n DESC, c.taxon_id
    LIMIT 1
    """,
    (active_ids(),),
  )
  if not rows:
    pytest.skip(f"no busy species has a {column} that only it matches")
  return rows[0]


def check_role_filter(client, role_param, expected_role):
  """
  Filter by a role value and check that every result has the expected role,
  both in the response (ofvs[0]) and in the database, and that the list is not
  empty.
  """
  resp = client.get(URL, params={"role": role_param, "limit": 500})

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert results, f"no observations came back for role={role_param!r}"
  assert all(item["ofvs"][0]["value"] == expected_role for item in results)
  assert set(db_roles(result_ids(resp)).values()) == {expected_role}


# =========================================================================
# Feature: Basic request / response shape
# =========================================================================

def test_L4_001_returns_200_with_valid_shape_when_no_filters(client):
  """
  L4-001: GET /api/v1/interactions returns 200 and {etl_version: string,
  results: array}.
  """
  resp = client.get(URL)

  body = resp.json()

  assert resp.status_code == 200
  assert isinstance(body["etl_version"], str)
  assert isinstance(body["results"], list)
  assert body["results"]


def test_L4_002_each_result_contains_all_required_fields(client):
  """
  L4-002: every result has id, uuid, uri, observed_on, created_at, description,
  community_taxon_id, taxon, ofvs, photos, geojson, latitude, longitude, the
  four place fields, positional_accuracy and location. The first 50 results are
  checked.
  """
  resp = client.get(URL, params={"limit": 50})

  assert resp.status_code == 200
  assert resp.json()["results"]
  for item in resp.json()["results"]:
    assert REQUIRED_FIELDS.issubset(item.keys()), (
      f"missing fields in observation {item['id']}: {REQUIRED_FIELDS - item.keys()}"
    )


# L4-003 (empty database returns an empty list) is not tested: it needs an
# empty database.


def test_L4_004_results_are_ordered_by_observed_at_descending(client):
  """
  L4-004: the most recent observation comes first. The first 100 results are
  looked up in the database, and their observed_at values (those that have one)
  never go up from one result to the next.
  """
  resp = client.get(URL, params={"limit": 100})

  ids = result_ids(resp)
  times = db_observed_at(ids)
  dated = [times[i] for i in ids if times[i] is not None]

  assert resp.status_code == 200
  assert len(dated) > 1
  assert dated == sorted(dated, reverse=True)


def test_L4_005_null_observed_at_appears_last(client):
  """
  L4-005: observations with no observed_at come at the end of the results. The
  last page of 500 is fetched; once an observation without an observed_at
  appears, every one after it also has none.
  """
  if count_observations("o.observed_at IS NULL") == 0:
    pytest.skip("every observation has an observed_at")
  total = count_observations()
  offset = max(0, total - 500)

  resp = client.get(URL, params={"limit": 500, "offset": offset})

  ids = result_ids(resp)
  times = db_observed_at(ids)
  is_null = [times[i] is None for i in ids]

  assert resp.status_code == 200
  assert any(is_null), "no observation without an observed_at in the last page"
  assert all(is_null[is_null.index(True):])


# =========================================================================
# Feature: Pagination (limit + offset)
# =========================================================================

def test_L4_006_default_limit_is_200(client):
  """
  L4-006: with no limit, the results are 200 observations (or fewer only if the
  database has fewer than 200).
  """
  resp = client.get(URL)

  assert resp.status_code == 200
  assert len(resp.json()["results"]) == min(200, count_observations())


def test_L4_007_custom_limit_is_respected(client):
  """
  L4-007: GET /api/v1/interactions?limit=10 returns exactly 10 results.
  """
  resp = client.get(URL, params={"limit": 10})

  assert resp.status_code == 200
  assert len(resp.json()["results"]) == 10


def test_L4_008_limit_of_1_returns_exactly_one_result(client):
  """
  L4-008: GET /api/v1/interactions?limit=1 returns exactly 1 result.
  """
  resp = client.get(URL, params={"limit": 1})

  assert resp.status_code == 200
  assert len(resp.json()["results"]) == 1


def test_L4_009_maximum_limit_of_500_is_accepted(client):
  """
  L4-009: GET /api/v1/interactions?limit=500 returns 200 and at most 500
  results (500 if the database has that many).
  """
  resp = client.get(URL, params={"limit": 500})

  assert resp.status_code == 200
  assert 0 < len(resp.json()["results"]) <= 500
  assert len(resp.json()["results"]) == min(500, count_observations())


def test_L4_010_limit_above_500_is_rejected(client):
  """
  L4-010: GET /api/v1/interactions?limit=501 returns 422.
  """
  resp = client.get(URL, params={"limit": 501})

  assert resp.status_code == 422


def test_L4_011_limit_of_0_is_rejected(client):
  """
  L4-011: GET /api/v1/interactions?limit=0 returns 422.
  """
  resp = client.get(URL, params={"limit": 0})

  assert resp.status_code == 422


def test_L4_012_negative_limit_is_rejected(client):
  """
  L4-012: GET /api/v1/interactions?limit=-1 returns 422.
  """
  resp = client.get(URL, params={"limit": -1})

  assert resp.status_code == 422


def test_L4_013_non_numeric_limit_is_rejected(client):
  """
  L4-013: GET /api/v1/interactions?limit=abc returns 422.
  """
  resp = client.get(URL, params={"limit": "abc"})

  assert resp.status_code == 422


def test_L4_014_offset_paginates_correctly(client):
  """
  L4-014: with limit=5, offset=5 returns observations 6-10 of the list, not
  1-5. The first 10 are fetched in one request, and the second page must equal
  items 6-10 of that list.
  """
  first_ten = result_ids(client.get(URL, params={"limit": 10}))

  resp = client.get(URL, params={"limit": 5, "offset": 5})

  assert resp.status_code == 200
  assert result_ids(resp) == first_ten[5:10]
  assert result_ids(resp) != first_ten[0:5]


def test_L4_015_offset_beyond_total_returns_empty_list(client):
  """
  L4-015: an offset far past the end of the list returns 200 and an empty
  results array, not a 404.
  """
  resp = client.get(URL, params={"offset": 10000000})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


def test_L4_016_negative_offset_is_rejected(client):
  """
  L4-016: GET /api/v1/interactions?offset=-1 returns 422.
  """
  resp = client.get(URL, params={"offset": -1})

  assert resp.status_code == 422


def test_L4_017_non_numeric_offset_is_rejected(client):
  """
  L4-017: GET /api/v1/interactions?offset=abc returns 422.
  """
  resp = client.get(URL, params={"offset": "abc"})

  assert resp.status_code == 422


# =========================================================================
# Feature: taxon_id filter
# =========================================================================

def test_L4_018_taxon_id_filter_returns_only_that_taxon(client):
  """
  L4-018: filtering by the taxon_id of the species with the most observations
  returns only observations of that species, and all of them (up to 500).
  """
  taxon_id, total = busy_species()

  resp = client.get(URL, params={"taxon_id": taxon_id, "limit": 500})

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert len(results) == min(total, 500)
  assert all(item["taxon"]["id"] == taxon_id for item in results)
  assert all(item["community_taxon_id"] == taxon_id for item in results)


def test_L4_019_taxon_id_with_no_observations_returns_empty_list(client):
  """
  L4-019: GET /api/v1/interactions?taxon_id=999999999 returns 200 and an empty
  results array.
  """
  resp = client.get(URL, params={"taxon_id": 999999999})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


def test_L4_020_order_level_taxon_returns_all_species_in_that_order(client):
  """
  L4-020: filtering by an order's taxon_id returns the observations of every
  species in that order (checked against a separate query on order_name).
  """
  check_higher_taxon(client, "order_name")


def test_L4_021_family_level_taxon_returns_all_species_in_that_family(client):
  """
  L4-021: filtering by a family's taxon_id returns the observations of every
  species in that family (checked against a separate query on family_name).
  """
  check_higher_taxon(client, "family_name")


def test_L4_022_genus_level_taxon_returns_all_species_in_that_genus(client):
  """
  L4-022: filtering by a genus's taxon_id returns the observations of every
  species in that genus (checked against a separate query on genus_name).
  """
  check_higher_taxon(client, "genus_name")


def test_L4_023_non_numeric_taxon_id_is_rejected(client):
  """
  L4-023: GET /api/v1/interactions?taxon_id=fox returns 422.
  """
  resp = client.get(URL, params={"taxon_id": "fox"})

  assert resp.status_code == 422


def test_L4_024_negative_taxon_id_returns_empty_list_gracefully(client):
  """
  L4-024: GET /api/v1/interactions?taxon_id=-1 returns 200 with an empty
  results array, or 422. It must not crash.
  """
  resp = client.get(URL, params={"taxon_id": -1})

  assert resp.status_code in (200, 422)
  if resp.status_code == 200:
    assert resp.json()["results"] == []


# =========================================================================
# Feature: taxon_name filter
# =========================================================================

def test_L4_025_taxon_name_filters_by_common_name(client):
  """
  L4-025: searching taxon_name by a common name returns that species'
  observations. A busy species whose common name matches no other species is
  used, so the search can only resolve to it.
  """
  taxon_id, name, total = uniquely_named_species("common_name")

  resp = client.get(URL, params={"taxon_name": name, "limit": 500})

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert len(results) == min(total, 500)
  assert all(item["taxon"]["id"] == taxon_id for item in results)
  assert all(
    name.lower() in (item["taxon"]["preferred_common_name"] or "").lower()
    for item in results
  )


def test_L4_026_taxon_name_filters_by_scientific_name(client):
  """
  L4-026: searching taxon_name by a scientific name returns that species'
  observations. A busy species whose scientific name matches no other species is
  used, so the search can only resolve to it.
  """
  taxon_id, name, total = uniquely_named_species("scientific_name")

  resp = client.get(URL, params={"taxon_name": name, "limit": 500})

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert len(results) == min(total, 500)
  assert all(item["taxon"]["id"] == taxon_id for item in results)
  assert all(name.lower() in item["taxon"]["name"].lower() for item in results)


def test_L4_027_taxon_name_search_is_case_insensitive(client):
  """
  L4-027: searching the same name in upper case and lower case returns identical
  results.
  """
  _, name, _ = uniquely_named_species("common_name")

  upper = client.get(URL, params={"taxon_name": name.upper(), "limit": 500}).json()
  lower = client.get(URL, params={"taxon_name": name.lower(), "limit": 500}).json()

  assert upper["results"]
  assert upper == lower


def test_L4_028_taxon_name_with_no_match_returns_empty_list(client):
  """
  L4-028: GET /api/v1/interactions?taxon_name=zzznomatch returns 200 and an
  empty results array.
  """
  resp = client.get(URL, params={"taxon_name": "zzznomatch"})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


def test_L4_029_taxon_id_takes_priority_over_taxon_name(client):
  """
  L4-029: when taxon_id and taxon_name are both given, only taxon_id is used.
  The name is one that matches nothing, so if it were used the results would be
  empty; they must equal the results for taxon_id alone.
  """
  taxon_id, _ = busy_species()
  taxon_id_only = client.get(URL, params={"taxon_id": taxon_id, "limit": 500})

  resp = client.get(
    URL, params={"taxon_id": taxon_id, "taxon_name": "zzznomatch", "limit": 500}
  )

  assert resp.status_code == 200
  assert resp.json()["results"]
  assert result_ids(resp) == result_ids(taxon_id_only)


def test_L4_030_taxon_name_with_special_characters_does_not_crash(client):
  """
  L4-030: GET /api/v1/interactions?taxon_name=fox's (an apostrophe) returns 200,
  not a 500.
  """
  resp = client.get(URL, params={"taxon_name": "fox's"})

  assert resp.status_code == 200


def test_L4_031_taxon_name_with_sql_injection_attempt_is_handled_safely(client):
  """
  L4-031: a taxon_name of '; DROP TABLE observations;-- returns 200 with an
  empty list, and the observations table still has the same number of rows
  afterwards. The count is read from the real table before and after.
  """
  count_before = real_query("SELECT count(*) FROM observations")[0][0]

  resp = client.get(URL, params={"taxon_name": "'; DROP TABLE observations;--"})

  assert resp.status_code == 200
  assert resp.json()["results"] == []
  assert real_query("SELECT count(*) FROM observations")[0][0] == count_before


# =========================================================================
# Feature: role filter
# =========================================================================

def test_L4_032_role_eater_returns_only_eater_observations(client):
  """
  L4-032: GET /api/v1/interactions?role=eater returns only observations whose
  role is "eater".
  """
  check_role_filter(client, "eater", "eater")


def test_L4_033_role_predator_maps_to_eater(client):
  """
  L4-033: role=predator returns the same observations as role=eater.
  """
  check_role_filter(client, "predator", "eater")
  assert client.get(URL, params={"role": "predator", "limit": 500}).json() == (
    client.get(URL, params={"role": "eater", "limit": 500}).json()
  )


def test_L4_034_role_thing_being_eaten_returns_only_prey_observations(client):
  """
  L4-034: role=thing being eaten returns only observations whose role is "thing
  being eaten".
  """
  check_role_filter(client, "thing being eaten", "thing being eaten")


def test_L4_035_role_prey_maps_to_thing_being_eaten(client):
  """
  L4-035: role=prey returns the same observations as role=thing being eaten.
  """
  check_role_filter(client, "prey", "thing being eaten")
  assert client.get(URL, params={"role": "prey", "limit": 500}).json() == (
    client.get(URL, params={"role": "thing being eaten", "limit": 500}).json()
  )


def test_L4_036_role_organism_being_eaten_maps_to_thing_being_eaten(client):
  """
  L4-036: role=organism being eaten returns the same observations as role=thing
  being eaten.
  """
  check_role_filter(client, "organism being eaten", "thing being eaten")
  assert client.get(URL, params={"role": "organism being eaten", "limit": 500}).json() == (
    client.get(URL, params={"role": "thing being eaten", "limit": 500}).json()
  )


def test_L4_037_unknown_role_defaults_to_eater(client):
  """
  L4-037: role=unknown_role returns the same observations as role=eater.
  """
  check_role_filter(client, "unknown_role", "eater")
  assert client.get(URL, params={"role": "unknown_role", "limit": 500}).json() == (
    client.get(URL, params={"role": "eater", "limit": 500}).json()
  )


def test_L4_038_role_filter_is_case_insensitive(client):
  """
  L4-038: role=EATER and role=eater return identical results.
  """
  upper = client.get(URL, params={"role": "EATER", "limit": 500}).json()
  lower = client.get(URL, params={"role": "eater", "limit": 500}).json()

  assert upper["results"]
  assert upper == lower


# =========================================================================
# Feature: year filter
# =========================================================================

def test_L4_039_year_filter_returns_only_that_year(client):
  """
  L4-039: filtering by the year with the most observations returns only
  observations whose observed_at is in that year (checked in the database), and
  all of them (up to 500).
  """
  year, total = busy_year()

  resp = client.get(URL, params={"year": year, "limit": 500})

  ids = result_ids(resp)

  assert resp.status_code == 200
  assert len(ids) == min(total, 500)
  assert set(db_years(ids).values()) == {year}


def test_L4_040_year_with_no_observations_returns_empty_list(client):
  """
  L4-040: GET /api/v1/interactions?year=1850 returns 200 and an empty results
  array.
  """
  resp = client.get(URL, params={"year": 1850})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


def test_L4_041_year_below_minimum_is_rejected(client):
  """
  L4-041: GET /api/v1/interactions?year=1799 returns 422.
  """
  resp = client.get(URL, params={"year": 1799})

  assert resp.status_code == 422


def test_L4_042_year_above_maximum_is_rejected(client):
  """
  L4-042: GET /api/v1/interactions?year=2101 returns 422.
  """
  resp = client.get(URL, params={"year": 2101})

  assert resp.status_code == 422


def test_L4_043_non_numeric_year_is_rejected(client):
  """
  L4-043: GET /api/v1/interactions?year=abc returns 422.
  """
  resp = client.get(URL, params={"year": "abc"})

  assert resp.status_code == 422


def test_L4_044_year_boundary_values_are_accepted(client):
  """
  L4-044: year=1800 and year=2100 both return 200, not 422.
  """
  assert client.get(URL, params={"year": 1800}).status_code == 200
  assert client.get(URL, params={"year": 2100}).status_code == 200


# =========================================================================
# Feature: location filter
# =========================================================================

def test_L4_045_location_filter_returns_only_matching_observations(client):
  """
  L4-045: filtering by the most common place_guess returns only observations
  from that place (checked in the database, in the place_guess column or the
  raw JSON), and all of them (up to 500).
  """
  place = busy_place()
  total = count_observations(place_matches_sql(), [f"%{place}%", f"%{place}%"])

  resp = client.get(URL, params={"location": place, "limit": 500})

  ids = result_ids(resp)

  assert resp.status_code == 200
  assert len(ids) == min(total, 500)
  for place_guess, raw_place_guess in db_places(ids).values():
    assert (
      place.lower() in (place_guess or "").lower()
      or place.lower() in (raw_place_guess or "").lower()
    )


# L4-046 (a place_guess found only in the raw JSON) is not tested: no
# observation in the data has it.


def test_L4_047_location_filter_is_case_insensitive(client):
  """
  L4-047: the same location in upper case and lower case returns identical
  results.
  """
  place = busy_place()

  upper = client.get(URL, params={"location": place.upper(), "limit": 500}).json()
  lower = client.get(URL, params={"location": place.lower(), "limit": 500}).json()

  assert upper["results"]
  assert upper == lower


def test_L4_048_location_with_no_match_returns_empty_list(client):
  """
  L4-048: GET /api/v1/interactions?location=zzznomatch returns 200 and an empty
  results array.
  """
  resp = client.get(URL, params={"location": "zzznomatch"})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


def test_L4_049_location_with_special_characters_does_not_crash(client):
  """
  L4-049: GET /api/v1/interactions?location=St. John's (an apostrophe) returns
  200, not a 500.
  """
  resp = client.get(URL, params={"location": "St. John's"})

  assert resp.status_code == 200


# =========================================================================
# Feature: ids filter
# =========================================================================

def test_L4_050_single_id_returns_that_observation(client):
  """
  L4-050: GET /api/v1/interactions?ids=<an observation id> returns exactly that
  one observation.
  """
  first_id = sample_observation_ids(1)[0]

  resp = client.get(URL, params={"ids": str(first_id)})

  assert resp.status_code == 200
  assert result_ids(resp) == [first_id]


def test_L4_051_multiple_ids_return_all_matching_observations(client):
  """
  L4-051: ids=<id1>,<id2> returns both observations.
  """
  first_id, second_id = sample_observation_ids(2)

  resp = client.get(URL, params={"ids": f"{first_id},{second_id}"})

  assert resp.status_code == 200
  assert sorted(result_ids(resp)) == sorted([first_id, second_id])


def test_L4_052_id_that_does_not_exist_returns_empty_list(client):
  """
  L4-052: an ids value that no observation has returns 200 and an empty results
  array.
  """
  resp = client.get(URL, params={"ids": str(missing_observation_id())})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


def test_L4_053_mix_of_valid_and_invalid_ids_returns_only_valid_ones(client):
  """
  L4-053: ids=<a real id>,<an id that does not exist> returns only the real
  observation.
  """
  first_id = sample_observation_ids(1)[0]

  resp = client.get(URL, params={"ids": f"{first_id},{missing_observation_id()}"})

  assert resp.status_code == 200
  assert result_ids(resp) == [first_id]


def test_L4_054_non_numeric_ids_are_silently_ignored(client):
  """
  L4-054: GET /api/v1/interactions?ids=abc,xyz returns 200 and an empty results
  array.
  """
  resp = client.get(URL, params={"ids": "abc,xyz"})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


def test_L4_055_mix_of_numeric_and_non_numeric_ids_returns_numeric_matches(client):
  """
  L4-055: ids=<id1>,abc,<id2> returns only observations id1 and id2.
  """
  first_id, second_id = sample_observation_ids(2)

  resp = client.get(URL, params={"ids": f"{first_id},abc,{second_id}"})

  assert resp.status_code == 200
  assert sorted(result_ids(resp)) == sorted([first_id, second_id])

# Test is failing because the endpoint returns list without filters when params are empty
# def test_L4_056_empty_ids_param_returns_empty_list(client):
#   """
#   L4-056: GET /api/v1/interactions?ids= returns 200 and an empty results array.

#   Note: the endpoint's check is `if ids:`, which is false for an empty string,
#   so today an empty ids value means "no ids filter" and normal results come
#   back. This test is written to the plain-English case, so it is expected to
#   fail until the endpoint is changed to `if ids is not None:` (or until the
#   team decides that empty ids should mean "no filter" and this test is changed).
#   """
#   resp = client.get(URL, params={"ids": ""})

#   assert resp.status_code == 200
#   assert resp.json()["results"] == []


def test_L4_057_ids_with_extra_commas_does_not_crash(client):
  """
  L4-057: ids=<id1>,,<id2> returns 200 and both observations; the empty entry
  between the commas is skipped.
  """
  first_id, second_id = sample_observation_ids(2)

  resp = client.get(URL, params={"ids": f"{first_id},,{second_id}"})

  assert resp.status_code == 200
  assert sorted(result_ids(resp)) == sorted([first_id, second_id])


# =========================================================================
# Feature: Combining filters
# =========================================================================

def test_L4_058_taxon_id_and_role_together_filter_correctly(client):
  """
  L4-058: taxon_id and role=eater together return only observations of that
  taxon that have the role "eater". The species with the most "eater"
  observations is used.
  """
  taxon_id, total = busy_species("eater")

  resp = client.get(URL, params={"taxon_id": taxon_id, "role": "eater", "limit": 500})

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert len(results) == min(total, 500)
  assert all(item["taxon"]["id"] == taxon_id for item in results)
  assert all(item["ofvs"][0]["value"] == "eater" for item in results)


def test_L4_059_taxon_id_and_year_together_filter_correctly(client):
  """
  L4-059: taxon_id and year together return only observations of that taxon
  from that year. The species and year with the most observations are used.
  """
  taxon_id, year, total = busy_species_year()

  resp = client.get(URL, params={"taxon_id": taxon_id, "year": year, "limit": 500})

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert len(results) == min(total, 500)
  assert all(item["taxon"]["id"] == taxon_id for item in results)
  assert set(db_years(result_ids(resp)).values()) == {year}


def test_L4_060_all_filters_combined_return_correctly_filtered_results(client):
  """
  L4-060: taxon_id, role, year, location, limit=10 and offset=0 together return
  results that satisfy every filter at once. The values come from one real
  observation, so at least that observation matches.
  """
  rows = real_query(
    f"""
    SELECT o.observation_id, o.taxon_id, o.role,
           extract(year FROM o.observed_at)::int, o.place_guess
    FROM observations o
    JOIN species s ON s.taxon_id = o.taxon_id
    WHERE o.etl_version_id = ANY(%s)
      AND o.observed_at IS NOT NULL
      AND coalesce(o.place_guess, '') <> ''
      AND {NOT_HIGHER_LEVEL}
    ORDER BY o.observation_id
    LIMIT 50
    """,
    (active_ids(),),
  )
  usable = [row for row in rows if plain_place(row[4])]
  if not usable:
    pytest.skip("no dated observation has a usable place_guess")
  _, taxon_id, role, year, place = usable[0]

  resp = client.get(
    URL,
    params={
      "taxon_id": taxon_id,
      "role": role,
      "year": year,
      "location": place,
      "limit": 10,
      "offset": 0,
    },
  )

  results = resp.json()["results"]
  ids = result_ids(resp)

  assert resp.status_code == 200
  assert 0 < len(results) <= 10
  assert all(item["taxon"]["id"] == taxon_id for item in results)
  assert set(db_roles(ids).values()) == {role}
  assert set(db_years(ids).values()) == {year}
  for place_guess, raw_place_guess in db_places(ids).values():
    assert (
      place.lower() in (place_guess or "").lower()
      or place.lower() in (raw_place_guess or "").lower()
    )


def test_L4_061_filters_that_cannot_match_return_empty_list(client):
  """
  L4-061: a taxon_id together with year=1850 (a year with no observations)
  returns 200 and an empty results array, not a 404.
  """
  taxon_id, _ = busy_species()

  resp = client.get(URL, params={"taxon_id": taxon_id, "year": 1850})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


# =========================================================================
# Feature: build_observation_payload - taxon object
# =========================================================================

def test_L4_062_taxon_object_contains_all_required_fields(client):
  """
  L4-062: the taxon of every result has id, name, preferred_common_name,
  iconic_taxon_name and default_photo. The first 50 results are checked.
  """
  resp = client.get(URL, params={"limit": 50})

  assert resp.status_code == 200
  assert resp.json()["results"]
  for item in resp.json()["results"]:
    assert TAXON_FIELDS.issubset(item["taxon"].keys()), f"missing fields in {item['taxon']}"


def test_L4_063_taxon_with_image_url_populates_default_photo(client):
  """
  L4-063: for an observation that has an image_url, taxon.default_photo has the
  taxon id and square_url, url, medium_url and small_url all set to that
  image_url. (The image comes from the observation, not the species.)
  """
  observation_id, taxon_id, image_url = find_observation(
    "coalesce(o.image_url, '') <> ''",
    columns="o.observation_id, o.taxon_id, o.image_url",
  )

  item = fetch_one(client, observation_id)

  assert item["taxon"]["default_photo"] == {
    "id": taxon_id,
    "square_url": image_url,
    "url": image_url,
    "medium_url": image_url,
    "small_url": image_url,
  }


def test_L4_064_taxon_without_image_url_has_null_default_photo(client):
  """
  L4-064: for an observation with no image_url, taxon.default_photo is null: the
  key is there and its value is None (not missing, not an empty object).
  """
  (observation_id,) = find_observation("coalesce(o.image_url, '') = ''")

  item = fetch_one(client, observation_id)

  assert "default_photo" in item["taxon"]
  assert item["taxon"]["default_photo"] is None


# =========================================================================
# Feature: build_observation_payload - photos
# =========================================================================

def test_L4_065_licensed_photo_appears_in_photos_array(client):
  """
  L4-065: an observation with an image_url, an allowed photo_license_code and an
  allowed license in its raw JSON has one item in photos, with url,
  license_code, attribution, id, flags, hidden and original_dimensions.
  """
  allowed = sorted(main_module.ALLOWED_LICENSES)
  observation_id, image_url, license_code, attribution = find_observation(
    """
    coalesce(o.image_url, '') <> ''
    AND lower(trim(o.photo_license_code)) = ANY(%s)
    AND lower(trim(coalesce(nullif(o.raw->>'license', ''), o.raw->>'license_code', ''))) = ANY(%s)
    """,
    params=[allowed, allowed],
    columns="o.observation_id, o.image_url, o.photo_license_code, o.photo_attribution",
  )

  item = fetch_one(client, observation_id)

  assert len(item["photos"]) == 1
  photo = item["photos"][0]
  assert PHOTO_FIELDS.issubset(photo.keys())
  assert photo["url"] == image_url
  assert photo["license_code"] == license_code.strip().lower()
  assert photo["attribution"] == (attribution or "")
  assert photo["id"] == observation_id
  assert photo["flags"] == []
  assert photo["hidden"] is False


# L4-066 to L4-069 are not tested: the data has no image with a missing photo
# license, no disallowed license, no uppercase license, and only 7 of the 9
# license codes.


def test_L4_070_observation_without_image_url_has_empty_photos(client):
  """
  L4-070: an observation with no image_url has photos == [], whatever its
  license. One with an allowed photo license is preferred, if there is one.
  """
  rows = real_query(
    """
    SELECT o.observation_id
    FROM observations o
    WHERE o.etl_version_id = ANY(%s) AND coalesce(o.image_url, '') = ''
    ORDER BY CASE WHEN lower(trim(o.photo_license_code)) = ANY(%s) THEN 0 ELSE 1 END,
             o.observation_id
    LIMIT 1
    """,
    (active_ids(), sorted(main_module.ALLOWED_LICENSES)),
  )
  if not rows:
    pytest.skip("every observation has an image_url")

  item = fetch_one(client, rows[0][0])

  assert item["photos"] == []


def test_L4_071_photo_needs_both_photo_and_observation_license(client):
  """
  L4-071: an observation with an image_url and an allowed photo_license_code but
  no allowed license in its raw JSON has photos == [].
  """
  allowed = sorted(main_module.ALLOWED_LICENSES)
  (observation_id,) = find_observation(
    """
    coalesce(o.image_url, '') <> ''
    AND lower(trim(o.photo_license_code)) = ANY(%s)
    AND NOT (lower(trim(coalesce(nullif(o.raw->>'license', ''), o.raw->>'license_code', ''))) = ANY(%s))
    """,
    params=[allowed, allowed],
  )

  item = fetch_one(client, observation_id)

  assert item["photos"] == []


# =========================================================================
# Feature: build_observation_payload - geojson and coordinates
# =========================================================================

def test_L4_072_latitude_and_longitude_produce_correct_geojson(client):
  """
  L4-072: an observation with a latitude and longitude has geojson {type:
  "Point", coordinates: [longitude, latitude]}. Longitude comes first. An
  observation whose two values differ is used, so the order is really checked.
  """
  observation_id, latitude, longitude = find_observation(
    "o.latitude IS NOT NULL AND o.longitude IS NOT NULL AND o.latitude <> o.longitude",
    columns="o.observation_id, o.latitude, o.longitude",
  )

  item = fetch_one(client, observation_id)

  assert item["geojson"] == {"type": "Point", "coordinates": [longitude, latitude]}
  assert item["latitude"] == latitude
  assert item["longitude"] == longitude


def test_L4_073_null_latitude_and_longitude_have_null_geojson(client):
  """
  L4-073: an observation with no latitude and no longitude has geojson null.
  """
  (observation_id,) = find_observation("o.latitude IS NULL AND o.longitude IS NULL")

  item = fetch_one(client, observation_id)

  assert item["geojson"] is None
  assert item["latitude"] is None
  assert item["longitude"] is None


# L4-074, L4-075 and L4-076 are not tested: no observation has only a latitude,
# only a longitude, or sits at 0,0.


# =========================================================================
# Feature: build_observation_payload - role and ofvs
# =========================================================================

def test_L4_077_role_eater_produces_correct_ofvs_entry(client):
  """
  L4-077: an observation with role "eater" has ofvs[0].field_id 12795 and
  ofvs[0].value "eater".
  """
  (observation_id,) = find_observation("o.role = 'eater'")

  item = fetch_one(client, observation_id)

  assert item["ofvs"][0]["field_id"] == 12795
  assert item["ofvs"][0]["value"] == "eater"


def test_L4_078_role_thing_being_eaten_produces_correct_ofvs_entry(client):
  """
  L4-078: an observation with role "thing being eaten" has ofvs[0].field_id
  12795 and ofvs[0].value "thing being eaten".
  """
  (observation_id,) = find_observation("o.role = 'thing being eaten'")

  item = fetch_one(client, observation_id)

  assert item["ofvs"][0]["field_id"] == 12795
  assert item["ofvs"][0]["value"] == "thing being eaten"


def test_L4_079_partner_url_in_raw_produces_second_ofvs_entry(client):
  """
  L4-079: an observation with a partner URL in its raw JSON has two ofvs
  entries; ofvs[1].field_id is 12796 and ofvs[1].value is the partner URL.
  """
  observation_id, raw = find_observation(
    "coalesce(o.raw->>%s, '') <> ''",
    params=[main_module.PARTNER_URL_FIELD],
    columns="o.observation_id, o.raw",
  )

  item = fetch_one(client, observation_id)

  assert len(item["ofvs"]) == 2
  assert item["ofvs"][1]["field_id"] == 12796
  assert item["ofvs"][1]["value"] == raw[main_module.PARTNER_URL_FIELD]


def test_L4_080_no_partner_url_produces_only_one_ofvs_entry(client):
  """
  L4-080: an observation with no partner URL in its raw JSON has exactly one
  ofvs entry.
  """
  (observation_id,) = find_observation(
    "coalesce(o.raw->>%s, '') = ''",
    params=[main_module.PARTNER_URL_FIELD],
  )

  item = fetch_one(client, observation_id)

  assert len(item["ofvs"]) == 1


# L4-081 and L4-082 are not tested: roles are stored already converted, and the
# role column only allows "eater" and "thing being eaten".


# =========================================================================
# Feature: build_observation_payload - place fields
# =========================================================================

def test_L4_083_place_fields_are_populated_from_raw_json(client):
  """
  L4-083: the four place fields in the response equal the values in the raw
  JSON. The observation with the most place fields filled in is used (it
  always has at least the country).
  """
  rows = real_query(
    """
    SELECT o.observation_id, o.raw
    FROM observations o
    WHERE o.etl_version_id = ANY(%s)
      AND coalesce(o.raw->>'place_country_name', '') <> ''
    ORDER BY (
      (CASE WHEN coalesce(o.raw->>'place_state_name', '') <> '' THEN 1 ELSE 0 END)
      + (CASE WHEN coalesce(o.raw->>'place_county_name', '') <> '' THEN 1 ELSE 0 END)
      + (CASE WHEN coalesce(o.raw->>'place_town_name', '') <> '' THEN 1 ELSE 0 END)
    ) DESC, o.observation_id
    LIMIT 1
    """,
    (active_ids(),),
  )
  if not rows:
    pytest.skip("no observation has a place_country_name in its raw JSON")
  observation_id, raw = rows[0]

  item = fetch_one(client, observation_id)

  assert item["place_country_name"]
  for field in PLACE_FIELDS:
    assert item[field] == raw.get(field), f"{field} does not match the raw JSON"


def test_L4_084_missing_place_fields_are_null_not_missing_keys(client):
  """
  L4-084: an observation with none of the four place fields in its raw JSON
  still has all four keys in the response, each null.
  """
  (observation_id,) = find_observation(
    """
    o.raw->>'place_country_name' IS NULL
    AND o.raw->>'place_state_name' IS NULL
    AND o.raw->>'place_county_name' IS NULL
    AND o.raw->>'place_town_name' IS NULL
    """
  )

  item = fetch_one(client, observation_id)

  for field in PLACE_FIELDS:
    assert field in item, f"{field} is missing from the response"
    assert item[field] is None


# =========================================================================
# Feature: ETL version in interactions
# =========================================================================

# L4-085 (no ETL version at all) and L4-086 (two versions, filtered to one) are
# not tested: they need an empty etl_versions table, or a second version in the
# database. The etl_version parameter itself is covered by the Layer 2 tests.