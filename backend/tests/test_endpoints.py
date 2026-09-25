from fastapi.testclient import TestClient

from backend.cache import RedisCache
from backend.main import APP_VERSION, app


class FakeCursor:
  def __init__(self, row, rows, fetchone_rows):
    self.row = row
    self.rows = rows or []
    self.fetchone_rows = fetchone_rows or []

  async def __aenter__(self):
    return self

  async def __aexit__(self, *args):
    return False

  async def execute(self, *args):
    pass

  async def fetchone(self):
    if self.fetchone_rows:
      return self.fetchone_rows.pop(0)
    return self.row

  async def fetchall(self):
    return self.rows


class FakeConnection(FakeCursor):
  def cursor(self, **kwargs):
    return FakeCursor(
      self.row,
      self.rows,
      self.fetchone_rows,
    )


class FakePool:
  def __init__(self, row, rows, fetchone_rows):
    self.row = row
    self.rows = rows or []
    self.fetchone_rows = fetchone_rows or []

  def connection(self):
    return FakeConnection(self.row, self.rows, self.fetchone_rows,)


RED_FOX = {
  "taxon_id": 41641,
  "scientific_name": "Vulpes vulpes",
  "common_name": "Red Fox",
  "iconic_taxon_name": "Mammalia",
  "wikipedia_summary": "The red fox is the largest of the true foxes.",
  "wikipedia_url": "https://en.wikipedia.org/wiki/Red_fox",
  "image_url": "https://example.com/fox.jpg",
  "license_code": "cc-by",
  "attribution": "(c) Jane Doe",
}


def make_client(db_row=None, db_rows=None, fetchone_rows=None):
  app.state.pg_pool = FakePool(db_row, db_rows, fetchone_rows,)
  app.state.neo4j_driver = None
  app.state.redis_cache = RedisCache(None)
  return TestClient(app)


def test_1_health_check_is_ok():
  resp = make_client().get("/health")

  assert resp.status_code == 200
  assert resp.json()["status"] == "ok"


def test_2_version_endpoint_returns_app_version():
  resp = make_client().get("/api/v1/version")

  assert resp.status_code == 200
  assert resp.json() == {"version": APP_VERSION}


def test_3_species_detail_returns_species_info():
  resp = make_client(db_row=RED_FOX).get("/api/v1/species/41641")

  assert resp.status_code == 200
  assert resp.json() == {"results": [RED_FOX]}


def test_4_unknown_species_returns_404():
  resp = make_client(db_row=None).get("/api/v1/species/999999")

  assert resp.status_code == 404
  assert resp.json() == {"detail": "Species not found."}


def test_5_predator_prey_without_filter_returns_400():
  resp = make_client().get("/api/v1/predator-prey")

  assert resp.status_code == 400
  assert resp.json() == {"detail": "Provide predator or prey taxon id to filter results."}


def test_6_species_search_rejects_one_letter_query():
  resp = make_client().get("/api/v1/species/search?q=f")

  assert resp.status_code == 422


def test_7_species_search_returns_matching_species():
  rows = [
    {
      "taxon_id": 41641,
      "scientific_name": "Vulpes vulpes",
      "common_name": "Red Fox",
      "iconic_taxon_name": "Mammalia",
      "image_url": "https://example.com/fox.jpg",
      "license_code": "cc-by",
      "attribution": "(c) Jane Doe",
    }
  ]

  resp = make_client(db_rows=rows).get(
    "/api/v1/species/search?q=fox"
  )

  assert resp.status_code == 200
  assert resp.json() == {
    "results": [
      {
        "taxon_id": 41641,
        "scientific_name": "Vulpes vulpes",
        "common_name": "Red Fox",
        "iconic_taxon_name": "Mammalia",
        "default_photo": {
          "square_url": "https://example.com/fox.jpg",
          "small_url": "https://example.com/fox.jpg",
          "url": "https://example.com/fox.jpg",
          "license_code": "cc-by",
          "attribution": "(c) Jane Doe",
        },
      }
    ]
}


def test_8_location_search_returns_matching_locations():

  etl_version = {
    "id": 1,
    "version": "test-version",
    "loaded_at": None,
  }

  rows = [
    {"place_guess": "Raleigh, North Carolina, USA"},
    {"place_guess": "Raleigh, North Carolina, United States"},
  ]

  resp = make_client(db_rows=rows, fetchone_rows=[etl_version],).get(
    "/api/v1/locations/search?q=Raleigh"
  )

  assert resp.status_code == 200
  assert resp.json() == {
    "results": [
      {
        "id": "Raleigh, North Carolina, USA",
        "name": "Raleigh, North Carolina, USA",
        "display_name": "Raleigh, North Carolina, USA",
        "place_type_name": None,
      },
      {
        "id": "Raleigh, North Carolina, United States",
        "name": "Raleigh, North Carolina, United States",
        "display_name": "Raleigh, North Carolina, United States",
        "place_type_name": None,
      },
    ]
}


def test_9_interactions_returns_observations():
  etl_version = {
    "id": 1,
    "version": "test-version",
    "loaded_at": None,
  }

  observation = {
    "observation_id": 12345,
    "observed_at": None,
    "latitude": 35.7796,
    "longitude": -78.6382,
    "place_guess": "Raleigh, North Carolina",
    "quality_grade": "research",
    "description": "Red fox observation",
    "role": "eater",
    "taxon_id": 41641,
    "iNaturalist_url": "https://www.inaturalist.org/observations/12345",
    "etl_version_id": 1,
    "raw": {},
    "image_url": "https://example.com/fox.jpg",
    "photo_license_code": "cc-by",
    "photo_attribution": "(c) Jane Doe",
    "scientific_name": "Vulpes vulpes",
    "common_name": "Red Fox",
    "iconic_taxon_name": "Mammalia",
  }

  resp = make_client(
    db_rows=[observation],
    fetchone_rows=[etl_version],
  ).get("/api/v1/interactions")

  assert resp.status_code == 200
  assert resp.json()["etl_version"] == "test-version"
  assert len(resp.json()["results"]) == 1
  assert resp.json()["results"][0]["id"] == 12345
  assert resp.json()["results"][0]["taxon"]["name"] == "Vulpes vulpes"



def test_10_interactions_accepts_filters():
  etl_version = {
    "id": 1,
    "version": "test-version",
    "loaded_at": None,
  }

  observation = {
    "observation_id": 54321,
    "observed_at": None,
    "latitude": 35.7796,
    "longitude": -78.6382,
    "place_guess": "Raleigh, North Carolina",
    "quality_grade": "research",
    "description": "Fox eating prey",
    "role": "eater",
    "taxon_id": 41641,
    "iNaturalist_url": "https://www.inaturalist.org/observations/54321",
    "etl_version_id": 1,
    "raw": {},
    "image_url": None,
    "photo_license_code": None,
    "photo_attribution": None,
    "scientific_name": "Vulpes vulpes",
    "common_name": "Red Fox",
    "iconic_taxon_name": "Mammalia",
  }

  resp = make_client(
    db_rows=[observation],
    fetchone_rows=[etl_version],
  ).get(
    "/api/v1/interactions"
    "?taxon_id=41641"
    "&role=predator"
    "&year=2026"
    "&location=Raleigh"
  )

  assert resp.status_code == 200
  assert resp.json()["etl_version"] == "test-version"
  assert len(resp.json()["results"]) == 1
  assert resp.json()["results"][0]["id"] == 54321


def test_11_food_web_summary_returns_summary():
  etl_version = {
    "id": 1,
    "version": "test-version",
    "loaded_at": None,
  }

  location_row = {
    "location_count": 5,
  }

  resp = make_client(
    db_row=location_row,
    fetchone_rows=[etl_version, location_row],
  ).get("/api/v1/food-web/summary")

  assert resp.status_code == 200
  assert resp.json() == {
    "observations": 0,
    "edges": 0,
    "taxa": 0,
    "locations": 5,
  }
