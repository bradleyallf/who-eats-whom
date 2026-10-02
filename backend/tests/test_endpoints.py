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
    return FakeConnection(
      self.row,
      self.rows,
      self.fetchone_rows,
    )


class FakeNeo4jResult:
  def __init__(self, record):
    self.record = record

  async def single(self):
    return self.record


class FakeNeo4jSession:
  async def __aenter__(self):
    return self

  async def __aexit__(self, *args):
    return False

  async def run(self, query, **params):
    if "sum(r.interaction_count)" in query:
      return FakeNeo4jResult({"observations": 120})

    if "count(r) AS edges" in query:
      return FakeNeo4jResult({"edges": 45})

    return FakeNeo4jResult({"taxa": 30})


class FakeNeo4jDriver:
  def session(self):
    return FakeNeo4jSession()


ETL_VERSION = {
  "id": 1,
  "version": "test-version",
  "loaded_at": None,
}


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


def observation(**overrides):
  row = {
    "observation_id": 1001,
    "observed_at": None,
    "latitude": 40.744,
    "longitude": -74.032,
    "place_guess": "Hoboken, NJ, USA",
    "quality_grade": "research",
    "description": None,
    "role": "eater",
    "taxon_id": 41641,
    "iNaturalist_url": "https://www.inaturalist.org/observations/1001",
    "etl_version_id": 1,
    "raw": {},
    "image_url": None,
    "photo_license_code": None,
    "photo_attribution": None,
    "scientific_name": "Vulpes vulpes",
    "common_name": "Red Fox",
    "iconic_taxon_name": "Mammalia",
  }

  row.update(overrides)
  return row


def make_client(db_row=None, db_rows=None, fetchone_rows=None):
  app.state.pg_pool = FakePool(
    db_row,
    db_rows,
    fetchone_rows,
  )
  app.state.neo4j_driver = None
  app.state.redis_cache = RedisCache(None)
  return TestClient(app)


def get_interactions(rows, query=""):
  client = make_client(
    db_rows=rows,
    fetchone_rows=[ETL_VERSION],
  )

  return client.get(f"/api/v1/interactions{query}")


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
  assert resp.json() == {
    "detail": "Provide predator or prey taxon id to filter results."
  }


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
  rows = [
    {"place_guess": "Raleigh, North Carolina, USA"},
    {"place_guess": "Raleigh, North Carolina, United States"},
  ]

  resp = make_client(
    db_rows=rows,
    fetchone_rows=[ETL_VERSION],
  ).get("/api/v1/locations/search?q=Raleigh")

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
  row = observation(
    observation_id=12345,
    latitude=35.7796,
    longitude=-78.6382,
    place_guess="Raleigh, North Carolina",
    description="Red fox observation",
    image_url="https://example.com/fox.jpg",
    photo_license_code="cc-by",
    photo_attribution="(c) Jane Doe",
    iNaturalist_url=(
      "https://www.inaturalist.org/observations/12345"
    ),
  )

  resp = make_client(
    db_rows=[row],
    fetchone_rows=[ETL_VERSION],
  ).get("/api/v1/interactions")

  assert resp.status_code == 200
  assert resp.json()["etl_version"] == "test-version"
  assert len(resp.json()["results"]) == 1
  assert resp.json()["results"][0]["id"] == 12345
  assert resp.json()["results"][0]["taxon"]["name"] == "Vulpes vulpes"


def test_10_interactions_accepts_filters():
  row = observation(
    observation_id=54321,
    latitude=35.7796,
    longitude=-78.6382,
    place_guess="Raleigh, North Carolina",
    description="Fox eating prey",
    iNaturalist_url=(
      "https://www.inaturalist.org/observations/54321"
    ),
  )

  resp = make_client(
    db_rows=[row],
    fetchone_rows=[ETL_VERSION],
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
  location_row = {
    "location_count": 5,
  }

  resp = make_client(
    db_row=location_row,
    fetchone_rows=[ETL_VERSION, location_row],
  ).get("/api/v1/food-web/summary")

  assert resp.status_code == 200
  assert resp.json() == {
    "observations": 0,
    "edges": 0,
    "taxa": 0,
    "locations": 5,
  }


def test_12_species_search_without_image_has_no_photo():
  rows = [
    {
      "taxon_id": 4637,
      "scientific_name": "Ardea herodias",
      "common_name": "Great Blue Heron",
      "iconic_taxon_name": "Aves",
      "image_url": None,
      "license_code": None,
      "attribution": None,
    }
  ]

  resp = make_client(
    db_rows=rows,
  ).get("/api/v1/species/search?q=heron")

  assert resp.status_code == 200
  assert resp.json() == {
    "results": [
      {
        "taxon_id": 4637,
        "scientific_name": "Ardea herodias",
        "common_name": "Great Blue Heron",
        "iconic_taxon_name": "Aves",
      }
    ]
  }


def test_13_species_search_with_no_matches_returns_empty_list():
  resp = make_client(
    db_rows=[],
  ).get("/api/v1/species/search?q=zebra")

  assert resp.status_code == 200
  assert resp.json() == {"results": []}


def test_14_species_detail_with_missing_fields_returns_nulls():
  coyote = {
    "taxon_id": 42069,
    "scientific_name": "Canis latrans",
    "common_name": "Coyote",
    "iconic_taxon_name": "Mammalia",
    "wikipedia_summary": None,
    "wikipedia_url": None,
    "image_url": None,
    "license_code": None,
    "attribution": None,
  }

  resp = make_client(
    db_row=coyote,
  ).get("/api/v1/species/42069")

  assert resp.status_code == 200
  assert resp.json() == {"results": [coyote]}


def test_15_species_detail_rejects_non_numeric_id():
  resp = make_client().get("/api/v1/species/red-fox")

  assert resp.status_code == 422


def test_16_interactions_includes_role_and_partner_url():
  row = observation(
    role="thing being eaten",
    raw={
      'field:url for "partner" observation':
        "https://www.inaturalist.org/observations/2002"
    },
  )

  resp = get_interactions([row])

  ofvs = resp.json()["results"][0]["ofvs"]

  assert resp.status_code == 200
  assert [
    (ofv["field_id"], ofv["value"])
    for ofv in ofvs
  ] == [
    (12795, "thing being eaten"),
    (
      12796,
      "https://www.inaturalist.org/observations/2002",
    ),
  ]


def test_17_interactions_only_shows_licensed_photos():
  licensed = observation(
    observation_id=1001,
    image_url="https://example.com/1001.jpg",
    photo_license_code="CC-BY",
    photo_attribution="(c) naturalist1",
  )

  unlicensed = observation(
    observation_id=1002,
    image_url="https://example.com/1002.jpg",
    photo_license_code=None,
  )

  resp = get_interactions([
    licensed,
    unlicensed,
  ])

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert results[0]["photos"] == [
    {
      "attribution": "(c) naturalist1",
      "flags": [],
      "hidden": False,
      "id": 1001,
      "license_code": "cc-by",
      "original_dimensions": {
        "width": 0,
        "height": 0,
      },
      "url": "https://example.com/1001.jpg",
    }
  ]
  assert results[1]["photos"] == []


def test_18_interactions_builds_map_coordinates():
  with_location = observation(
    observation_id=1001,
    latitude=40.744,
    longitude=-74.032,
  )

  without_location = observation(
    observation_id=1002,
    latitude=None,
    longitude=None,
  )

  resp = get_interactions([
    with_location,
    without_location,
  ])

  results = resp.json()["results"]

  assert resp.status_code == 200
  assert results[0]["geojson"] == {
    "type": "Point",
    "coordinates": [-74.032, 40.744],
  }
  assert results[1]["geojson"] is None


def test_19_interactions_with_invalid_ids_returns_empty_list():
  resp = get_interactions(
    [observation()],
    query="?ids=abc,xyz",
  )

  assert resp.status_code == 200
  assert resp.json() == {
    "etl_version": "test-version",
    "results": [],
  }


def test_20_interactions_returns_404_when_no_data_is_loaded():
  resp = make_client(
    db_row=None,
  ).get("/api/v1/interactions")

  assert resp.status_code == 404
  assert resp.json() == {
    "detail": "No ETL version found. Load data first."
  }


def test_21_food_web_summary_includes_neo4j_counts():
  client = make_client(
    fetchone_rows=[
      ETL_VERSION,
      {"location_count": 12},
    ],
  )

  app.state.neo4j_driver = FakeNeo4jDriver()

  resp = client.get("/api/v1/food-web/summary")

  assert resp.status_code == 200
  assert resp.json() == {
    "observations": 120,
    "edges": 45,
    "taxa": 30,
    "locations": 12,
  }