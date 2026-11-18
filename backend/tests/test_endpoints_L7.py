"""
Endpoint tests for the Who Eats Whom backend (FastAPI) -- Layer 7: Locations search.

  Layer 7: Locations Search Endpoint
    GET /api/v1/locations/search

Conventions used throughout this file:
  * Tests call the API in-process through FastAPI's TestClient, so no separate
    server needs to be started.
  * Nothing is faked and nothing is written. The tests run against the real
    Postgres configured through the same environment variable the app reads
    (POSTGRES_DSN). Tests only ever read.
  * If POSTGRES_DSN is not set, every test in this file is skipped.
  * The endpoint returns the different place_guess values (from the observations
    table) that contain the search text, sorted by place_guess. So the search
    texts in these tests are taken from real place_guess values in the database. If
    the database has no value that suits a test, the test is skipped and says why.
  * Only the versions in ACTIVE_ETL_VERSIONS are counted, the same as the
    endpoint.
  * Test names follow the plain-English test IDs, e.g. test_L7_009_...
    covers test case L7-009.

Not tested (the real data / the setup cannot support them):
  L7-026 (needs an empty etl_versions table) and L7-027 (needs two versions, and
  the endpoint reads every active version, not only the latest one).

Differences from the plain-English cases:
  * The search text (q) must now have at least 3 characters (min_length=3 in the
    endpoint, and spaces around it do not count). So:
      - L7-003 is tested as: 3 characters are accepted and 2 characters are
        rejected (422).
  * L7-019, L7-020 and L7-021 (limits) need a search text that matches enough
    places. The test looks for one in the database, and checks the exact number
    expected (for example exactly 10, not "at most 10").
  * L7-012 compares with the order the database gives for place_guess, not with
    Python's own sorting, which orders accents, capitals and punctuation
    differently.
  * L7-028 is tested with the one version that exists: the results must be
    exactly the places that version has.

Run all tests - python -m pytest backend/tests/ -v
Run one test - python -m pytest backend/tests/test_endpoints_L7.py::{name of the test} -v
"""
import psycopg

import pytest

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.main import app


# The real Postgres address, read once when this file is imported. It comes from
# the same POSTGRES_DSN env var the app uses. None means it is not set.
REAL_POSTGRES_DSN = main_module.POSTGRES_DSN

URL = "/api/v1/locations/search"

# Used where the text only needs to be valid (3 characters).
VALID_Q = "Ral"

# The largest limit the endpoint accepts.
MAX_LIMIT = 25

# Fields every result must have (L7-005).
REQUIRED_FIELDS = {"id", "name", "display_name", "place_type_name"}


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


def plain(text):
  """True if a text has no characters that ILIKE treats specially."""
  return not any(char in text for char in "%_\\")


def db_search(term, version_ids, limit=MAX_LIMIT):
  """
  Read-only: the different place_guess values that contain the text (ignoring
  case), in the order the database sorts them, as a list. This is what the
  endpoint should return (without the ids and fields).
  """
  rows = real_query(
    """
    SELECT DISTINCT place_guess
    FROM observations
    WHERE etl_version_id = ANY(%s)
      AND place_guess IS NOT NULL
      AND place_guess <> ''
      AND place_guess ILIKE %s
    ORDER BY place_guess
    LIMIT %s
    """,
    (version_ids, f"%{term}%", limit),
  )
  return [row[0] for row in rows]


def count_matches(term, version_ids=None):
  """Read-only: how many different place_guess values contain the text."""
  rows = real_query(
    """
    SELECT count(DISTINCT place_guess)
    FROM observations
    WHERE etl_version_id = ANY(%s)
      AND place_guess IS NOT NULL
      AND place_guess <> ''
      AND place_guess ILIKE %s
    """,
    (version_ids or active_ids(), f"%{term}%"),
  )
  return rows[0][0]


def candidate_places():
  """
  Read-only: the 60 place_guess values with the most observations that have no
  special ILIKE characters, most observations first, as (place, observation count).
  """
  rows = real_query(
    """
    SELECT place_guess, count(*)
    FROM observations
    WHERE etl_version_id = ANY(%s) AND coalesce(place_guess, '') <> ''
    GROUP BY place_guess
    ORDER BY count(*) DESC, place_guess
    LIMIT 60
    """,
    (active_ids(),),
  )
  return [(place, total) for place, total in rows if plain(place)]


def find_term(position, min_matches=1):
  """
  Read-only: look through the real places for a search text that
    - has at least 3 characters and no special ILIKE characters,
    - matches between min_matches and 25 different places (so every match fits
      in one response),
    - and sits where position says in the place it came from: "start" (the place
      begins with it but is longer), "middle" (it is somewhere after the first
      character), or "any".
  Returns (place it came from, search text, number of places it matches).
  """
  for place, _ in candidate_places():
    parts = [part.strip() for part in place.split(",")]
    slices = [place[i : i + 6].strip() for i in range(1, max(len(place) - 5, 1), 3)]
    for term in parts + slices:
      if len(term) < 3 or not plain(term):
        continue
      found_at = place.lower().find(term.lower())
      if position == "start" and not (found_at == 0 and len(term) < len(place)):
        continue
      if position == "middle" and found_at <= 0:
        continue
      matches = count_matches(term)
      if min_matches <= matches <= MAX_LIMIT:
        return place, term, matches
  pytest.skip(f"no place_guess gives a search text for position={position!r}")


def broad_term(min_matches):
  """
  Read-only: the 3-character search text that matches the most different places,
  as (text, number of places it matches). Skips if even the best one matches
  fewer than min_matches.
  """
  rows = real_query(
    """
    SELECT left(place_guess, 3), count(DISTINCT place_guess)
    FROM observations
    WHERE etl_version_id = ANY(%s) AND coalesce(place_guess, '') <> ''
    GROUP BY 1
    ORDER BY 2 DESC, 1
    LIMIT 10
    """,
    (active_ids(),),
  )
  best = None
  for prefix, _ in rows:
    if prefix != prefix.strip() or len(prefix) != 3 or not plain(prefix):
      continue
    matches = count_matches(prefix)
    if best is None or matches > best[1]:
      best = (prefix, matches)
  if best is None or best[1] < min_matches:
    pytest.skip(f"no 3-character text matches {min_matches} different places")
  return best


def get_locations(client, **params):
  """Call the endpoint, check it returned 200, and return the results list."""
  resp = client.get(URL, params=params)
  assert resp.status_code == 200
  return resp.json()["results"]


def names_of(results):
  """The place names from a results list, in order."""
  return [item["name"] for item in results]


# =========================================================================
# Feature: Basic validation
# =========================================================================

def test_L7_001_missing_q_param_is_rejected(client):
  """
  L7-001: GET /api/v1/locations/search with no q returns 422.
  """
  resp = client.get(URL)

  assert resp.status_code == 422


def test_L7_002_q_param_with_one_character_is_rejected(client):
  """
  L7-002: GET /api/v1/locations/search?q=R returns 422.
  """
  resp = client.get(URL, params={"q": "R"})

  assert resp.status_code == 422


def test_L7_003_q_param_needs_at_least_three_characters(client):
  """
  L7-003 (updated): q with three characters is accepted (200), and q with two
  characters ("Ra") is rejected (422), since the endpoint now needs at least 3.
  """
  accepted = client.get(URL, params={"q": VALID_Q})
  rejected = client.get(URL, params={"q": "Ra"})

  assert accepted.status_code == 200
  assert rejected.status_code == 422


def test_L7_004_empty_q_param_is_rejected(client):
  """
  L7-004: GET /api/v1/locations/search?q= returns 422.
  """
  resp = client.get(URL, params={"q": ""})

  assert resp.status_code == 422


# =========================================================================
# Feature: Response shape
# =========================================================================

def test_L7_005_each_result_contains_all_required_fields(client):
  """
  L7-005: every result has id, name, display_name and place_type_name. A search
  text taken from a real place is used, so there are results.
  """
  _, term, _ = find_term("any")

  results = get_locations(client, q=term)

  assert results
  for item in results:
    assert REQUIRED_FIELDS.issubset(item.keys()), (
      f"missing fields in {item}: {REQUIRED_FIELDS - item.keys()}"
    )


def test_L7_006_place_type_name_is_always_null(client):
  """
  L7-006: place_type_name is null on every result, never filled in.
  """
  _, term, _ = find_term("any")

  results = get_locations(client, q=term)

  assert results
  assert all(item["place_type_name"] is None for item in results)


def test_L7_007_id_and_name_and_display_name_are_identical(client):
  """
  L7-007: id, name and display_name are the same text on every result.
  """
  _, term, _ = find_term("any")

  results = get_locations(client, q=term)

  assert results
  for item in results:
    assert item["id"] == item["name"] == item["display_name"], (
      f"id, name and display_name differ in {item}"
    )


def test_L7_008_no_matches_returns_empty_list_not_404(client):
  """
  L7-008: GET /api/v1/locations/search?q=zzznomatch returns 200 and
  {results: []}.
  """
  resp = client.get(URL, params={"q": "zzznomatch"})

  assert resp.status_code == 200
  assert resp.json() == {"results": []}


# =========================================================================
# Feature: Search behavior
# =========================================================================

def test_L7_009_search_is_case_insensitive(client):
  """
  L7-009: the same text in lower case, as it is, and in upper case returns
  identical results. A search text taken from a real place is used, so there are
  results.
  """
  _, term, _ = find_term("any")

  as_is = client.get(URL, params={"q": term}).json()
  lower = client.get(URL, params={"q": term.lower()}).json()
  upper = client.get(URL, params={"q": term.upper()}).json()

  assert as_is["results"]
  assert lower == as_is
  assert upper == as_is


def test_L7_010_search_matches_partial_place_guess_strings(client):
  """
  L7-010: a real place whose start matches the search text appears in the
  results, even though the text is only part of it. Every result contains the
  text.
  """
  place, term, _ = find_term("start")

  results = get_locations(client, q=term, limit=MAX_LIMIT)

  names = names_of(results)

  assert place in names
  assert all(term.lower() in name.lower() for name in names)


def test_L7_011_search_matches_middle_of_string_not_just_start(client):
  """
  L7-011: a real place that has the search text somewhere after its first
  character appears in the results. Every result contains the text.
  """
  place, term, _ = find_term("middle")

  results = get_locations(client, q=term, limit=MAX_LIMIT)

  names = names_of(results)

  assert place in names
  assert all(term.lower() in name.lower() for name in names)


def test_L7_012_results_are_returned_in_alphabetical_order(client):
  """
  L7-012: results come back in the order the database sorts place_guess. A text
  that matches at least 3 places is used, so the order can show.
  """
  _, term, _ = find_term("any", min_matches=3)

  results = get_locations(client, q=term, limit=MAX_LIMIT)

  assert len(results) >= 3
  assert names_of(results) == db_search(term, active_ids())


def test_L7_013_results_are_distinct_duplicates_appear_once(client):
  """
  L7-013: a place that has many observations appears only once. The place with
  the most observations (at least 2) whose full text matches few enough places
  to fit in one response is used.
  """
  for place, total in candidate_places():
    if total >= 2 and count_matches(place) <= MAX_LIMIT:
      break
  else:
    pytest.skip("no place with 2 or more observations gives a search that fits one response")

  names = names_of(get_locations(client, q=place, limit=MAX_LIMIT))

  assert names.count(place) == 1
  assert len(names) == len(set(names))

# Test is skipped because no observation has a null place_guess
# def test_L7_014_null_place_guess_is_excluded(client):
#   """
#   L7-014: a null place_guess never appears in the results. The test is skipped if
#   no observation has a null place_guess. (A null value can never match a search
#   of 3 or more characters, so this confirms the behavior but could not catch the
#   filter being removed.)
#   """
#   nulls = real_query(
#     "SELECT count(*) FROM observations WHERE etl_version_id = ANY(%s) AND place_guess IS NULL",
#     (active_ids(),),
#   )[0][0]
#   if nulls == 0:
#     pytest.skip("no observation has a null place_guess")
#   _, term, _ = find_term("any")

#   results = get_locations(client, q=term, limit=MAX_LIMIT)

#   assert results
#   assert all(item["name"] is not None for item in results)
#   assert all(item["id"] is not None for item in results)


def test_L7_015_empty_string_place_guess_is_excluded(client):
  """
  L7-015: an empty place_guess never appears in the results. The test is skipped
  if no observation has an empty place_guess. (An empty value can never match a
  search of 3 or more characters, so this confirms the behavior but could not
  catch the filter being removed.)
  """
  empties = real_query(
    "SELECT count(*) FROM observations WHERE etl_version_id = ANY(%s) AND place_guess = ''",
    (active_ids(),),
  )[0][0]
  if empties == 0:
    pytest.skip("no observation has an empty place_guess")
  _, term, _ = find_term("any")

  results = get_locations(client, q=term, limit=MAX_LIMIT)

  assert results
  assert all(item["name"] != "" for item in results)
  assert all(item["id"] != "" for item in results)


def test_L7_016_search_with_special_characters_does_not_crash(client):
  """
  L7-016: GET /api/v1/locations/search?q=St.%20John%27s returns 200 and a
  results list.
  """
  resp = client.get(URL, params={"q": "St. John's"})

  assert resp.status_code == 200
  assert isinstance(resp.json()["results"], list)


def test_L7_017_search_with_sql_injection_attempt_is_handled_safely(client):
  """
  L7-017: a search for text that tries to delete the observations table returns
  200 and an empty list, and the table still has the same number of rows.
  """
  count_before = real_query("SELECT count(*) FROM observations")[0][0]

  resp = client.get(URL, params={"q": "'; DROP TABLE observations;--"})

  assert resp.status_code == 200
  assert resp.json()["results"] == []
  assert real_query("SELECT count(*) FROM observations")[0][0] == count_before


def test_L7_018_search_with_unicode_characters_works_correctly(client):
  """
  L7-018: GET /api/v1/locations/search?q=München returns 200 and a results list.
  """
  resp = client.get(URL, params={"q": "München"})

  assert resp.status_code == 200
  assert isinstance(resp.json()["results"], list)


# =========================================================================
# Feature: Limit
# =========================================================================

def test_L7_019_default_limit_is_10(client):
  """
  L7-019: with no limit, 10 results come back. A 3-character text that matches
  more than 10 different places is used.
  """
  term, _ = broad_term(min_matches=11)

  results = get_locations(client, q=term)

  assert len(results) == 10


def test_L7_020_custom_limit_is_respected(client):
  """
  L7-020: limit=5 returns exactly 5 results. A 3-character text that matches at
  least 5 different places is used.
  """
  term, _ = broad_term(min_matches=5)

  results = get_locations(client, q=term, limit=5)

  assert len(results) == 5


def test_L7_021_maximum_limit_of_25_is_accepted(client):
  """
  L7-021: limit=25 returns 200 and at most 25 results (all of them if the text
  matches fewer). The 3-character text that matches the most places is used.
  """
  term, matches = broad_term(min_matches=1)

  results = get_locations(client, q=term, limit=25)

  assert 0 < len(results) <= 25
  assert len(results) == min(25, matches)


def test_L7_022_limit_above_25_is_rejected(client):
  """
  L7-022: GET /api/v1/locations/search?q=Ral&limit=26 returns 422.
  """
  resp = client.get(URL, params={"q": VALID_Q, "limit": 26})

  assert resp.status_code == 422


def test_L7_023_limit_of_0_is_rejected(client):
  """
  L7-023: GET /api/v1/locations/search?q=Ral&limit=0 returns 422.
  """
  resp = client.get(URL, params={"q": VALID_Q, "limit": 0})

  assert resp.status_code == 422


def test_L7_024_negative_limit_is_rejected(client):
  """
  L7-024: GET /api/v1/locations/search?q=Ral&limit=-1 returns 422.
  """
  resp = client.get(URL, params={"q": VALID_Q, "limit": -1})

  assert resp.status_code == 422


def test_L7_025_non_numeric_limit_is_rejected(client):
  """
  L7-025: GET /api/v1/locations/search?q=Ral&limit=abc returns 422.
  """
  resp = client.get(URL, params={"q": VALID_Q, "limit": "abc"})

  assert resp.status_code == 422


# =========================================================================
# Feature: ETL version scoping
# =========================================================================

# L7-026 (no ETL version at all) and L7-027 (results from the latest version
# only) are not tested: L7-026 needs an empty etl_versions table, and L7-027
# needs two versions (and the endpoint reads every active version, not only the
# latest).


def test_L7_028_explicit_etl_version_param_scopes_results_to_that_version(client):
  """
  L7-028: GET /api/v1/locations/search?q=<text>&etl_version=<a real version>
  returns exactly the places that version has (checked against the database).
  Only one version exists locally, so this cannot show another version being
  left out.
  """
  version_id, version = active_versions()[0]
  _, term, _ = find_term("any")

  results = get_locations(client, q=term, etl_version=version, limit=MAX_LIMIT)

  assert results
  assert names_of(results) == db_search(term, [version_id])


def test_L7_029_non_existent_etl_version_returns_404(client):
  """
  L7-029: GET /api/v1/locations/search?q=Ral&etl_version=doesnotexist returns 404
  with {detail: "No ETL version found. Load data first."}.
  """
  resp = client.get(URL, params={"q": VALID_Q, "etl_version": "doesnotexist"})

  assert resp.status_code == 404
  assert resp.json() == {"detail": "No ETL version found. Load data first."}