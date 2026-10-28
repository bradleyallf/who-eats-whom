"""
Endpoint tests for the Who Eats Whom backend (FastAPI) -- Layer 3: Species.

  Layer 3: Species Endpoints
    GET /api/v1/species              (paginated list)
    GET /api/v1/species/search       (search by name)
    GET /api/v1/species/{taxon_id}   (one species)

Conventions used throughout this file:
  * Tests call the API in-process through FastAPI's TestClient, so no separate
    server needs to be started.
  * Nothing is faked and nothing is written. The tests run against the real
    Postgres (and the real Neo4j and Redis) configured through the same
    environment variables the app reads (POSTGRES_DSN, NEO4J_URI, NEO4J_USER,
    NEO4J_PASSWORD, REDIS_URL). Tests only ever read.
  * If POSTGRES_DSN is not set, every test in this file is skipped.
  * Where a test needs a particular kind of species (one with no interactions,
    one without an image, one without a common name), it first asks the
    database for one with a read-only query, so it keeps working when your
    data changes.
  * Test names follow the plain-English test IDs, e.g. test_L3_002_...
    covers test case L3-002.

Not tested (the real data cannot support them):
  L3-016 (needs an empty database) and L3-041 (no species has every optional
  field null).

Real values used: taxon 4956 (Ardea herodias) for the single-species tests,
and the searches "fox" and "Vulpes".

Run all tests - python -m pytest backend/tests/ -v
Run one test - python -m pytest backend/tests/test_endpoints_L3.py::{name of the test} -v
"""
import psycopg

import pytest

from fastapi.testclient import TestClient

import backend.main as main_module
from backend.main import app


# The real Postgres address, read once when this file is imported. It comes
# from the same POSTGRES_DSN env var the app uses. None means it is not set.
REAL_POSTGRES_DSN = main_module.POSTGRES_DSN

# A species that exists in the real data (Ardea herodias, the great blue heron).
KNOWN_TAXON_ID = 4956

# Fields every item in the /api/v1/species list must have (L3-015).
LIST_FIELDS = {
  "taxon_id",
  "scientific_name",
  "common_name",
  "predator_events",
  "prey_events",
}

# Fields the single-species response must have (L3-035).
DETAIL_FIELDS = {
  "taxon_id",
  "scientific_name",
  "common_name",
  "wikipedia_summary",
  "wikipedia_url",
  "image_url",
  "license_code",
  "attribution",
}

# Keys of the default_photo object returned for a species with an image (L3-027).
PHOTO_KEYS = {"square_url", "small_url", "url", "license_code", "attribution"}


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


# =========================================================================
# Feature: GET /api/v1/species (paginated list)
# =========================================================================

def test_L3_001_returns_paginated_list_with_default_limit(client):
  """
  L3-001: GET /api/v1/species returns 200, a results array with at most 50
  items (the default limit), and an etl_version field.
  """
  resp = client.get("/api/v1/species")

  assert resp.status_code == 200
  assert "etl_version" in resp.json()
  assert 0 < len(resp.json()["results"]) <= 50


def test_L3_002_custom_limit_is_respected(client):
  """
  L3-002: GET /api/v1/species?limit=10 returns exactly 10 items.
  """
  resp = client.get("/api/v1/species", params={"limit": 10})

  assert resp.status_code == 200
  assert len(resp.json()["results"]) == 10


def test_L3_003_limit_of_1_returns_exactly_one_species(client):
  """
  L3-003: GET /api/v1/species?limit=1 returns exactly 1 item.
  """
  resp = client.get("/api/v1/species", params={"limit": 1})

  assert resp.status_code == 200
  assert len(resp.json()["results"]) == 1


def test_L3_004_maximum_limit_of_200_is_respected(client):
  """
  L3-004: GET /api/v1/species?limit=200 returns 200 and at most 200 items.
  """
  resp = client.get("/api/v1/species", params={"limit": 200})

  assert resp.status_code == 200
  assert 0 < len(resp.json()["results"]) <= 200


def test_L3_005_limit_above_200_is_rejected(client):
  """
  L3-005: GET /api/v1/species?limit=201 returns 422.
  """
  resp = client.get("/api/v1/species", params={"limit": 201})

  assert resp.status_code == 422


def test_L3_006_limit_of_0_is_rejected(client):
  """
  L3-006: GET /api/v1/species?limit=0 returns 422.
  """
  resp = client.get("/api/v1/species", params={"limit": 0})

  assert resp.status_code == 422


def test_L3_007_negative_limit_is_rejected(client):
  """
  L3-007: GET /api/v1/species?limit=-1 returns 422.
  """
  resp = client.get("/api/v1/species", params={"limit": -1})

  assert resp.status_code == 422


def test_L3_008_non_numeric_limit_is_rejected(client):
  """
  L3-008: GET /api/v1/species?limit=abc returns 422.
  """
  resp = client.get("/api/v1/species", params={"limit": "abc"})

  assert resp.status_code == 422


def test_L3_009_offset_paginates_correctly(client):
  """
  L3-009: with limit=5, offset=5 returns species 6-10 of the list, not species
  1-5. The first 10 species are fetched in one request, and the second page
  must equal items 6-10 of that list.

  Note: this assumes the list has a stable order. If species with the same
  predator_events could come back in a different order from one query to the
  next, this test would be flaky, and the fix would be a tie-breaker (such as
  taxon_id) in the endpoint's ORDER BY.
  """
  first_ten = client.get("/api/v1/species", params={"limit": 10}).json()["results"]

  resp = client.get("/api/v1/species", params={"limit": 5, "offset": 5})

  assert resp.status_code == 200
  second_page_ids = [item["taxon_id"] for item in resp.json()["results"]]
  assert second_page_ids == [item["taxon_id"] for item in first_ten[5:10]]
  assert second_page_ids != [item["taxon_id"] for item in first_ten[0:5]]


def test_L3_010_offset_beyond_total_returns_empty_list(client):
  """
  L3-010: an offset far past the end of the list returns 200 and an empty
  results array, not a 404.
  """
  resp = client.get("/api/v1/species", params={"offset": 1000000})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


def test_L3_011_negative_offset_is_rejected(client):
  """
  L3-011: GET /api/v1/species?offset=-1 returns 422.
  """
  resp = client.get("/api/v1/species", params={"offset": -1})

  assert resp.status_code == 422


def test_L3_012_non_numeric_offset_is_rejected(client):
  """
  L3-012: GET /api/v1/species?offset=abc returns 422.
  """
  resp = client.get("/api/v1/species", params={"offset": "abc"})

  assert resp.status_code == 422


def test_L3_013_results_are_ordered_by_predator_events_descending(client):
  """
  L3-013: in the first 200 species, predator_events never goes up from one item
  to the next, so the species with the most predator events comes first.
  """
  resp = client.get("/api/v1/species", params={"limit": 200})

  events = [item["predator_events"] for item in resp.json()["results"]]

  assert resp.status_code == 200
  assert events == sorted(events, reverse=True)
  assert events[0] > 0


def test_L3_014_species_with_no_interactions_has_zero_counts_not_null(client):
  """
  L3-014: a species that has no rows in predator_prey_aggregates shows up in
  the list with predator_events 0 and prey_events 0, not null. The species is
  found with a read-only query, then looked for page by page in the list.
  """
  rows = real_query(
    """
    SELECT s.taxon_id
    FROM species s
    WHERE NOT EXISTS (
      SELECT 1 FROM predator_prey_aggregates a
      WHERE a.predator_taxon_id = s.taxon_id OR a.prey_taxon_id = s.taxon_id
    )
    LIMIT 1
    """
  )
  if not rows:
    pytest.skip("every species has at least one aggregate")
  wanted_taxon_id = rows[0][0]

  found = None
  offset = 0
  while found is None:
    page = client.get(
      "/api/v1/species", params={"limit": 200, "offset": offset}
    ).json()["results"]
    if not page:
      break
    found = next((item for item in page if item["taxon_id"] == wanted_taxon_id), None)
    offset += 200

  assert found is not None, f"taxon {wanted_taxon_id} was not in the species list"
  assert found["predator_events"] == 0
  assert found["prey_events"] == 0


def test_L3_015_each_result_contains_required_fields(client):
  """
  L3-015: every item in the list has taxon_id, scientific_name, common_name,
  predator_events and prey_events.
  """
  resp = client.get("/api/v1/species", params={"limit": 50})

  assert resp.status_code == 200
  assert resp.json()["results"]
  for item in resp.json()["results"]:
    assert LIST_FIELDS.issubset(item.keys()), f"missing fields in {item}"


# L3-016 (empty database returns an empty list) is not tested: it needs an
# empty database.


# =========================================================================
# Feature: GET /api/v1/species/search
# =========================================================================

def test_L3_017_search_by_common_name_returns_matching_species(client):
  """
  L3-017: GET /api/v1/species/search?q=fox returns 200 and results that include
  species whose common_name contains "fox".
  """
  resp = client.get("/api/v1/species/search", params={"q": "fox"})

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert any("fox" in (item["common_name"] or "").lower() for item in results)


def test_L3_018_search_by_scientific_name_returns_matching_species(client):
  """
  L3-018: GET /api/v1/species/search?q=Vulpes returns 200 and results that
  include species whose scientific_name contains "Vulpes".
  """
  resp = client.get("/api/v1/species/search", params={"q": "Vulpes"})

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert any("vulpes" in item["scientific_name"].lower() for item in results)


def test_L3_019_search_is_case_insensitive(client):
  """
  L3-019: searching FOX, fox and Fox returns identical results.
  """
  bodies = [
    client.get("/api/v1/species/search", params={"q": q}).json()
    for q in ("FOX", "fox", "Fox")
  ]

  assert bodies[0]["results"]
  assert bodies[0] == bodies[1] == bodies[2]


def test_L3_020_search_with_one_character_is_rejected(client):
  """
  L3-020: GET /api/v1/species/search?q=f returns 422.
  """
  resp = client.get("/api/v1/species/search", params={"q": "f"})

  assert resp.status_code == 422


def test_L3_021_search_with_three_characters_is_accepted(client):
  """
  L3-021 (adapted): the minimum search length is now 3, so GET
  /api/v1/species/search?q=fox returns 200, and q=fo is rejected with 422.
  """
  assert client.get("/api/v1/species/search", params={"q": "fox"}).status_code == 200
  assert client.get("/api/v1/species/search", params={"q": "fo"}).status_code == 422


def test_L3_022_search_with_no_matches_returns_empty_list(client):
  """
  L3-022: GET /api/v1/species/search?q=zzznomatch returns 200 and an empty
  results array, not a 404.
  """
  resp = client.get("/api/v1/species/search", params={"q": "zzznomatch"})

  assert resp.status_code == 200
  assert resp.json()["results"] == []


def test_L3_023_search_respects_limit_param(client):
  """
  L3-023: GET /api/v1/species/search?q=fox&limit=5 returns at most 5 results.
  """
  resp = client.get("/api/v1/species/search", params={"q": "fox", "limit": 5})

  assert resp.status_code == 200
  assert 0 < len(resp.json()["results"]) <= 5


def test_L3_024_search_limit_above_50_is_rejected(client):
  """
  L3-024: GET /api/v1/species/search?q=fox&limit=51 returns 422.
  """
  resp = client.get("/api/v1/species/search", params={"q": "fox", "limit": 51})

  assert resp.status_code == 422


def test_L3_025_search_limit_of_0_is_rejected(client):
  """
  L3-025: GET /api/v1/species/search?q=fox&limit=0 returns 422.
  """
  resp = client.get("/api/v1/species/search", params={"q": "fox", "limit": 0})

  assert resp.status_code == 422


def test_L3_026_missing_q_param_is_rejected(client):
  """
  L3-026: GET /api/v1/species/search with no q parameter returns 422.
  """
  resp = client.get("/api/v1/species/search")

  assert resp.status_code == 422


def test_L3_027_species_with_image_returns_default_photo_object(client):
  """
  L3-027: a species that has an image_url comes back with a default_photo
  object containing square_url, small_url, url, license_code and attribution.
  The "fox" search is used; most species in the data have an image.
  """
  resp = client.get("/api/v1/species/search", params={"q": "fox"})

  with_photo = [item for item in resp.json()["results"] if "default_photo" in item]

  assert resp.status_code == 200
  assert with_photo, "no fox species came back with a default_photo"
  for item in with_photo:
    assert PHOTO_KEYS.issubset(item["default_photo"].keys())


def test_L3_028_species_without_image_has_no_default_photo_key(client):
  """
  L3-028: a species whose image_url is empty comes back with no default_photo
  key at all (not null, not an empty object). The species is found with a
  read-only query, then searched for by its scientific name.
  """
  rows = real_query(
    """
    SELECT taxon_id, scientific_name FROM species
    WHERE coalesce(image_url, '') = '' LIMIT 1
    """
  )
  if not rows:
    pytest.skip("every species has an image_url")
  taxon_id, scientific_name = rows[0]

  resp = client.get(
    "/api/v1/species/search", params={"q": scientific_name, "limit": 50}
  )

  match = next(
    (item for item in resp.json()["results"] if item["taxon_id"] == taxon_id), None
  )

  assert resp.status_code == 200
  assert match is not None, f"{scientific_name} was not found by its own name"
  assert "default_photo" not in match


def test_L3_029_search_results_are_ordered_alphabetically(client):
  """
  L3-029: GET /api/v1/species/search?q=fox returns results sorted alphabetically
  by common_name, falling back to scientific_name when there is no common name.
  """
  resp = client.get("/api/v1/species/search", params={"q": "fox", "limit": 50})

  names = [
    (item["common_name"] or item["scientific_name"])
    for item in resp.json()["results"]
  ]

  assert resp.status_code == 200
  assert len(names) > 1
  assert names == sorted(names)


def test_L3_030_null_common_name_falls_back_to_scientific_name_for_ordering(client):
  """
  L3-030: species with no common_name are sorted by scientific_name, mixed in
  with named species. The genus of an unnamed species is found with a read-only
  query and searched for; the results must be in order by
  (common_name or scientific_name).
  """
  rows = real_query(
    """
    SELECT taxon_id, scientific_name FROM species
    WHERE coalesce(common_name, '') = '' AND length(split_part(scientific_name, ' ', 1)) >= 3
    LIMIT 1
    """
  )
  if not rows:
    pytest.skip("every species has a common_name")
  taxon_id, scientific_name = rows[0]
  genus = scientific_name.split(" ")[0]

  resp = client.get("/api/v1/species/search", params={"q": genus, "limit": 50})

  results = resp.json()["results"]
  names = [(item["common_name"] or item["scientific_name"]) for item in results]

  assert resp.status_code == 200
  assert any(item["taxon_id"] == taxon_id for item in results)
  assert names == sorted(names)


def test_L3_031_search_with_special_characters_does_not_crash(client):
  """
  L3-031: GET /api/v1/species/search?q=fo'ox (an apostrophe) returns 200, not a
  500.
  """
  resp = client.get("/api/v1/species/search", params={"q": "fo'ox"})

  assert resp.status_code == 200


def test_L3_032_search_with_sql_injection_attempt_is_handled_safely(client):
  """
  L3-032: a search for '; DROP TABLE species;-- returns 200 with an empty list
  or 422, and the species table still has the same number of rows afterwards.
  The count is read from the real table before and after.
  """
  count_before = real_query("SELECT count(*) FROM species")[0][0]

  resp = client.get(
    "/api/v1/species/search", params={"q": "'; DROP TABLE species;--"}
  )

  assert resp.status_code in (200, 422)
  if resp.status_code == 200:
    assert resp.json()["results"] == []
  assert real_query("SELECT count(*) FROM species")[0][0] == count_before


def test_L3_033_search_with_unicode_characters_works(client):
  """
  L3-033: GET /api/v1/species/search?q=ñoño returns 200, not a 500.
  """
  resp = client.get("/api/v1/species/search", params={"q": "ñoño"})

  assert resp.status_code == 200


def test_L3_034_search_with_only_whitespace_is_rejected_or_empty(client):
  """
  L3-034: a search for spaces only returns 422, or 200 with an empty results
  array. It must not crash.
  """
  resp = client.get("/api/v1/species/search", params={"q": "   "})

  assert resp.status_code in (200, 422)
  if resp.status_code == 200:
    assert resp.json()["results"] == []


# =========================================================================
# Feature: GET /api/v1/species/{taxon_id}
# =========================================================================

def test_L3_035_returns_full_species_detail_for_valid_taxon_id(client):
  """
  L3-035: GET /api/v1/species/4956 returns 200 and a results array with one
  item containing all the species fields.
  """
  resp = client.get(f"/api/v1/species/{KNOWN_TAXON_ID}")

  assert resp.status_code == 200
  assert len(resp.json()["results"]) == 1
  assert DETAIL_FIELDS.issubset(resp.json()["results"][0].keys())


def test_L3_036_returns_404_for_taxon_id_that_does_not_exist(client):
  """
  L3-036: GET /api/v1/species/999999999 returns 404 and
  {detail: "Species not found."}.
  """
  resp = client.get("/api/v1/species/999999999")

  assert resp.status_code == 404
  assert resp.json() == {"detail": "Species not found."}


def test_L3_037_non_numeric_taxon_id_is_rejected(client):
  """
  L3-037: GET /api/v1/species/red-fox returns 422.
  """
  resp = client.get("/api/v1/species/red-fox")

  assert resp.status_code == 422


def test_L3_038_negative_taxon_id_is_rejected_or_not_found(client):
  """
  L3-038: GET /api/v1/species/-1 returns 422 or 404, not a 500.
  """
  resp = client.get("/api/v1/species/-1")

  assert resp.status_code in (404, 422)


def test_L3_039_zero_taxon_id_returns_404(client):
  """
  L3-039: GET /api/v1/species/0 returns 404, since no species has taxon_id 0.
  """
  resp = client.get("/api/v1/species/0")

  assert resp.status_code == 404


def test_L3_040_very_large_taxon_id_returns_404_gracefully(client):
  """
  L3-040: GET /api/v1/species/99999999999999999 returns 404 or 422, not a 500.
  """
  resp = client.get("/api/v1/species/99999999999999999")

  assert resp.status_code in (404, 422)


# L3-041 (a species with every optional field null still returns all the keys)
# is not tested: no species in the data has every optional field null.


def test_L3_042_response_is_always_wrapped_in_results_array(client):
  """
  L3-042: GET /api/v1/species/4956 returns {results: [ {...} ]}, a list with a
  single object, never a bare object.
  """
  resp = client.get(f"/api/v1/species/{KNOWN_TAXON_ID}")

  body = resp.json()

  assert resp.status_code == 200
  assert isinstance(body["results"], list)
  assert isinstance(body["results"][0], dict)


def test_L3_043_taxon_id_in_response_matches_requested_taxon_id(client):
  """
  L3-043: GET /api/v1/species/4956 returns an item whose taxon_id is 4956, not
  a different species.
  """
  resp = client.get(f"/api/v1/species/{KNOWN_TAXON_ID}")

  assert resp.status_code == 200
  assert resp.json()["results"][0]["taxon_id"] == KNOWN_TAXON_ID