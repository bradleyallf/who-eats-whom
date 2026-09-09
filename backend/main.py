import json
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from neo4j import AsyncGraphDatabase

from .cache import RedisCache

EATER_FIELD_ID = 12795
PARTNER_FIELD_ID = 12796
ROLE_FIELD = 'field:id meant for "eater" or organism being eaten?'
PARTNER_URL_FIELD = 'field:url for "partner" observation'
ROLE_MAPPING = {
  "eater": "eater",
  "predator": "eater",
  "thing being eaten": "thing being eaten",
  "organism being eaten": "thing being eaten",
  "prey": "thing being eaten",
}

APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
POSTGRES_DSN = os.getenv("POSTGRES_DSN")
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
REDIS_URL = os.getenv("REDIS_URL")
DEFAULT_CACHE_TTL = int(os.getenv("API_CACHE_TTL", "300"))


def parse_raw_payload(raw: Any) -> Dict[str, Any]:
  if not raw:
    return {}
  if isinstance(raw, dict):
    return raw
  try:
    return json.loads(raw)
  except (TypeError, json.JSONDecodeError):
    return {}


def canonical_role_value(value: Optional[str]) -> str:
  normalized = (value or "").strip().lower()
  return ROLE_MAPPING.get(normalized, "eater")


def build_photo_payload(raw: Dict[str, Any], observation_id: int) -> List[Dict[str, Any]]:
  image_url = raw.get("image_url") or raw.get("photo_url")
  if not image_url:
    return []
  return [
    {
      "attribution": raw.get("user_name") or "",
      "flags": [],
      "hidden": False,
      "id": observation_id,
      "license_code": (raw.get("license") or "").lower(),
      "original_dimensions": {"width": 0, "height": 0},
      "url": image_url,
    }
  ]


def build_user_stub(raw: Dict[str, Any]) -> Dict[str, Any]:
  return {
    "created_at": raw.get("created_at") or "",
    "id": raw.get("user_id") or 0,
    "login": raw.get("user_login") or "",
    "spam": False,
    "suspended": False,
    "uuid": raw.get("user_uuid") or raw.get("uuid") or str(raw.get("user_id") or ""),
  }


def build_observation_payload(row: Dict[str, Any]) -> Dict[str, Any]:
  raw = parse_raw_payload(row.get("raw"))
  role_value = canonical_role_value(row.get("role") or raw.get(ROLE_FIELD) or "eater")
  partner_url = raw.get(PARTNER_URL_FIELD) or ""
  observation_id = row["observation_id"]
  taxon_id = row["taxon_id"]
  latitude = row.get("latitude")
  longitude = row.get("longitude")

  primary_ofv = {
    "datatype": "text",
    "field_id": EATER_FIELD_ID,
    "id": observation_id * 10,
    "name": "Feeding interaction role",
    "name_ci": "feeding interaction role",
    "user": build_user_stub(raw),
    "user_id": raw.get("user_id") or 0,
    "uuid": raw.get("uuid") or str(observation_id),
    "value": role_value,
    "value_ci": role_value.lower(),
  }
  ofvs = [primary_ofv]
  if partner_url:
    ofvs.append(
      {
        "datatype": "text",
        "field_id": PARTNER_FIELD_ID,
        "id": observation_id * 10 + 1,
        "name": "Partner observation URL",
        "name_ci": "partner observation url",
        "user": build_user_stub(raw),
        "user_id": raw.get("user_id") or 0,
        "uuid": f"{observation_id}-partner",
        "value": partner_url,
        "value_ci": partner_url.lower(),
      }
    )

  geojson = None
  if latitude is not None and longitude is not None:
    geojson = {"type": "Point", "coordinates": [longitude, latitude]}

  return {
    "community_taxon_id": taxon_id,
    "created_at": raw.get("created_at") or (row.get("observed_at").isoformat() if row.get("observed_at") else None),
    "description": row.get("description"),
    "ofvs": ofvs,
    "taxon": {
      "id": taxon_id,
      "name": row.get("scientific_name"),
      "preferred_common_name": row.get("common_name"),
      "iconic_taxon_name": row.get("iconic_taxon_name"),
      "default_photo": {
        "id": taxon_id,
        "square_url": raw.get("image_url"),
        "url": raw.get("image_url"),
        "medium_url": raw.get("image_url"),
        "small_url": raw.get("image_url"),
      }
      if raw.get("image_url")
      else None,
    },
    "id": observation_id,
    "uri": row.get("inaturalist_url") or row.get("iNaturalist_url") or raw.get("url"),
    "photos": build_photo_payload(raw, observation_id),
    "uuid": raw.get("uuid") or str(observation_id),
    "place_country_name": raw.get("place_country_name"),
    "place_state_name": raw.get("place_state_name"),
    "place_county_name": raw.get("place_county_name"),
    "place_town_name": raw.get("place_town_name"),
    "geojson": geojson,
    "location": raw.get("location"),
    "latitude": latitude,
    "longitude": longitude,
    "positional_accuracy": raw.get("public_positional_accuracy"),
  }


@asynccontextmanager
async def lifespan(app: FastAPI):
  pg_pool = AsyncConnectionPool(conninfo=POSTGRES_DSN, min_size=1, max_size=5) if POSTGRES_DSN else None
  neo4j_driver = (
    AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD)) if NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD else None
  )
  redis_cache = RedisCache(REDIS_URL)

  app.state.pg_pool = pg_pool
  app.state.neo4j_driver = neo4j_driver
  app.state.redis_cache = redis_cache

  yield

  if pg_pool:
    await pg_pool.close()
  if neo4j_driver:
    await neo4j_driver.close()
  await redis_cache.close()


app = FastAPI(
  title="Who Eats Whom API",
  version=APP_VERSION,
  docs_url="/api/docs",
  openapi_url="/api/openapi.json",
  lifespan=lifespan,
)

allowed_origins_env = os.getenv("CORS_ALLOW_ORIGINS")
allowed_origins = (
  [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]
  if allowed_origins_env
  else ["http://localhost:4200", "http://127.0.0.1:4200"]
)
app.add_middleware(
  CORSMiddleware,
  allow_origins=allowed_origins,
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


async def get_pg_pool(request: Request) -> AsyncConnectionPool:
  pool: Optional[AsyncConnectionPool] = request.app.state.pg_pool
  if not pool:
    raise HTTPException(status_code=503, detail="Postgres connection is not configured.")
  return pool


async def get_redis_cache(request: Request) -> RedisCache:
  return request.app.state.redis_cache


async def resolve_etl_version_id(pool: AsyncConnectionPool, requested_version: Optional[str]) -> Dict[str, Any]:
  async with pool.connection() as conn:
    async with conn.cursor(row_factory=dict_row) as cur:
      if requested_version:
        await cur.execute(
          """
          SELECT id, version, loaded_at
          FROM etl_versions
          WHERE version = %s
          """,
          (requested_version,),
        )
      else:
        await cur.execute(
          """
          SELECT id, version, loaded_at
          FROM etl_versions
          ORDER BY loaded_at DESC
          LIMIT 1
          """
        )
      row = await cur.fetchone()
      if not row:
        raise HTTPException(status_code=404, detail="No ETL version found. Load data first.")
      return dict(row)


async def resolve_taxon_condition(
  pool: AsyncConnectionPool,
  taxon_id: Optional[int] = None,
  taxon_name: Optional[str] = None,
) -> Tuple[Optional[str], List[Any]]:
  """
  Return a (sql_condition, params) tuple for filtering observations by taxon,
  expanding higher-level taxa (order/family/genus) to include all descendants.
  """
  if not taxon_id and not taxon_name:
    return None, []

  async with pool.connection() as conn:
    async with conn.cursor(row_factory=dict_row) as cur:
      if taxon_id:
        await cur.execute(
          "SELECT scientific_name, order_name, family_name, genus_name FROM species WHERE taxon_id = %s",
          (taxon_id,),
        )
        row = await cur.fetchone()
      else:
        like = f"%{taxon_name.strip()}%"
        await cur.execute(
          """
          SELECT taxon_id, scientific_name, order_name, family_name, genus_name
          FROM species
          WHERE scientific_name ILIKE %s OR common_name ILIKE %s
          LIMIT 1
          """,
          (like, like),
        )
        row = await cur.fetchone()
        if row:
          taxon_id = row["taxon_id"]

  if not row:
    if taxon_name:
      like = f"%{taxon_name.strip()}%"
      return "(s.scientific_name ILIKE %s OR s.common_name ILIKE %s)", [like, like]
    return "o.taxon_id = %s", [taxon_id]

  sci = (row.get("scientific_name") or "").strip()
  order_name = (row.get("order_name") or "").strip()
  family_name = (row.get("family_name") or "").strip()
  genus_name = (row.get("genus_name") or "").strip()

  # Detect order-level taxon: scientific name matches its own order name
  if order_name and sci == order_name:
    return "s.order_name = %s", [order_name]
  # Detect family-level taxon
  if family_name and sci == family_name:
    return "s.family_name = %s", [family_name]
  # Detect genus-level taxon
  if genus_name and sci == genus_name:
    return "s.genus_name = %s", [genus_name]

  return "o.taxon_id = %s", [taxon_id]


async def cached_response(cache: RedisCache, key: str, producer, ttl: int = DEFAULT_CACHE_TTL):
  cached = await cache.get_json(key)
  if cached is not None:
    return cached
  payload = await producer()
  await cache.set_json(key, payload, ttl_seconds=ttl)
  return payload


@app.get("/health", tags=["system"])
async def health_check(request: Request):
  """Lightweight probe used by load balancers and orchestration layers."""
  pg_pool = request.app.state.pg_pool
  neo4j_driver = request.app.state.neo4j_driver
  redis_cache: RedisCache = request.app.state.redis_cache
  return {
    "status": "ok",
    "postgres": bool(pg_pool),
    "neo4j": bool(neo4j_driver),
    "redis": bool(redis_cache and redis_cache.client),
  }


@app.get("/api/v1/version", tags=["system"])
async def api_version():
  """Expose the server version for clients and smoke tests."""
  return {"version": APP_VERSION}


@app.get("/api/v1/species", tags=["data"])
async def list_species(
  request: Request,
  limit: int = Query(50, ge=1, le=200),
  offset: int = Query(0, ge=0),
  etl_version: Optional[str] = Query(None, description="Override ETL version; defaults to latest."),
):
  pool = await get_pg_pool(request)
  cache = await get_redis_cache(request)
  version_info = await resolve_etl_version_id(pool, etl_version)
  cache_key = f"v{version_info['version']}:species:{limit}:{offset}"

  async def producer():
    async with pool.connection() as conn:
      async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
          """
          SELECT
            s.taxon_id,
            s.scientific_name,
            s.common_name,
            COALESCE(SUM(CASE WHEN p.predator_taxon_id = s.taxon_id THEN p.interaction_count END), 0) AS predator_events,
            COALESCE(SUM(CASE WHEN p.prey_taxon_id = s.taxon_id THEN p.interaction_count END), 0) AS prey_events
          FROM species AS s
          LEFT JOIN predator_prey_aggregates AS p
            ON p.etl_version_id = %s AND (p.predator_taxon_id = s.taxon_id OR p.prey_taxon_id = s.taxon_id)
          GROUP BY s.taxon_id, s.scientific_name, s.common_name
          ORDER BY predator_events DESC
          LIMIT %s OFFSET %s
          """,
          (version_info["id"], limit, offset),
        )
        rows = await cur.fetchall()
        records = [dict(row) for row in rows]
        return {
          "etl_version": version_info["version"],
          "results": records,
        }

  return await cached_response(cache, cache_key, producer)


@app.get("/api/v1/species/search", tags=["data"])
async def search_species(
  request: Request,
  q: str = Query(..., min_length=2, description="Search text for common or scientific name."),
  limit: int = Query(25, ge=1, le=50),
):
  pool = await get_pg_pool(request)
  search_term = f"%{q.strip()}%"

  async with pool.connection() as conn:
    async with conn.cursor(row_factory=dict_row) as cur:
      await cur.execute(
        """
        SELECT
          s.taxon_id,
          s.scientific_name,
          s.common_name,
          s.iconic_taxon_name,
          s.image_url
        FROM species s
        WHERE s.scientific_name ILIKE %s OR s.common_name ILIKE %s
        ORDER BY COALESCE(s.common_name, s.scientific_name)
        LIMIT %s
        """,
        (search_term, search_term, limit),
      )
      rows = await cur.fetchall()
      results = []
      for row in rows:
        r = dict(row)
        image_url = r.pop("image_url", None)
        if image_url:
          r["default_photo"] = {"square_url": image_url, "small_url": image_url, "url": image_url}
        results.append(r)
      return {"results": results}


@app.get("/api/v1/species/{taxon_id}", tags=["data"])
async def species_detail(request: Request, taxon_id: int):
  pool = await get_pg_pool(request)
  async with pool.connection() as conn:
    async with conn.cursor(row_factory=dict_row) as cur:
      await cur.execute(
        """
        SELECT taxon_id, scientific_name, common_name, iconic_taxon_name,
        wikipedia_summary, wikipedia_url, image_url
        FROM species
        WHERE taxon_id = %s
        """,
        (taxon_id,),
      )
      row = await cur.fetchone()
      if not row:
        raise HTTPException(status_code=404, detail="Species not found.")

  return {
    "results": [
      {
        "taxon_id": row["taxon_id"],
        "scientific_name": row["scientific_name"],
        "common_name": row["common_name"],
        "iconic_taxon_name": row["iconic_taxon_name"],
        "wikipedia_summary": row["wikipedia_summary"],
        "wikipedia_url": row["wikipedia_url"],
        "image_url": row["image_url"],
      }
    ]
  }

# Old food-web/summary endpoint

# @app.get("/api/v1/food-web/summary", tags=["data"])
# async def food_web_summary(
#   request: Request,
#   etl_version: Optional[str] = Query(None, description="Override ETL version; defaults to latest."),
# ):
#   pool = await get_pg_pool(request)
#   cache = await get_redis_cache(request)
#   version_info = await resolve_etl_version_id(pool, etl_version)
#   cache_key = f"v{version_info['version']}:summary"

#   async def producer():
#     async with pool.connection() as conn:
#       async with conn.cursor(row_factory=dict_row) as cur:
#         await cur.execute("SELECT COUNT(*) AS total_species FROM species")
#         total_species = (await cur.fetchone())["total_species"]

#         await cur.execute(
#           """
#           SELECT
#             COUNT(DISTINCT predator_taxon_id) AS predator_species,
#             COUNT(DISTINCT prey_taxon_id) AS prey_species,
#             COALESCE(SUM(interaction_count), 0) AS total_interactions
#           FROM predator_prey_aggregates
#           WHERE etl_version_id = %s
#           """,
#           (version_info["id"],),
#         )
#         aggregates = dict(await cur.fetchone())

#     neo4j_metrics: Dict[str, Any] = {}
#     driver: Optional[AsyncGraphDatabase] = request.app.state.neo4j_driver
#     if driver:
#       async with driver.session() as session:
#         nodes_result = await session.run(
#           "MATCH (s:Species {etl_version: $etl}) RETURN count(s) AS species",
#           etl=version_info["version"],
#         )
#         edges_result = await session.run(
#           "MATCH ()-[r:EATS {etl_version: $etl}]->() RETURN count(r) AS relationships",
#           etl=version_info["version"],
#         )
#         top_predators_result = await session.run(
#           """
#           MATCH (pred:Species)-[r:EATS {etl_version:$etl}]->(:Species)
#           RETURN pred.taxon_id AS taxon_id,
#                  pred.scientific_name AS scientific_name,
#                  SUM(r.interaction_count) AS total_interactions
#           ORDER BY total_interactions DESC
#           LIMIT 5
#           """,
#           etl=version_info["version"],
#         )
#         nodes_record = await nodes_result.single()
#         edges_record = await edges_result.single()
#         top_predators = await top_predators_result.data()
#         neo4j_metrics = {
#           "species_nodes": nodes_record["species"] if nodes_record else 0,
#           "edges": edges_record["relationships"] if edges_record else 0,
#           "top_predators": top_predators,
#         }

#     return {
#       "etl_version": version_info["version"],
#       "postgres": {
#         "total_species": total_species,
#         "predator_species": aggregates["predator_species"],
#         "prey_species": aggregates["prey_species"],
#         "total_interactions": aggregates["total_interactions"],
#       },
#       "neo4j": neo4j_metrics or None,
#     }

#   return await cached_response(cache, cache_key, producer)




# New food-web/summary endpoint to get the summary statistics which appear at the top of the page in the Interactive food web - BY Shriya

@app.get("/api/v1/food-web/summary", tags=["data"])
async def food_web_summary(
  request: Request,
  etl_version: Optional[str] = Query(None, description="Override ETL version; defaults to latest."),
):
  pool = await get_pg_pool(request)
  cache = await get_redis_cache(request)
  version_info = await resolve_etl_version_id(pool, etl_version)
  cache_key = f"v{version_info['version']}:summary:flat"

  async def producer():
    # Locations come from Postgres since Neo4j has no location data
    async with pool.connection() as conn:
      async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
          """
          SELECT COUNT(DISTINCT raw->>'place_country_name') AS location_count
          FROM observations
          WHERE etl_version_id = %s
            AND quality_grade = 'research'
            AND raw->>'place_country_name' IS NOT NULL
            AND raw->>'place_country_name' <> ''
          """,
          (version_info["id"],),
        )
        location_row = await cur.fetchone()
        locations = location_row["location_count"] if location_row else 0

    # Observations, edges, taxa come from Neo4j via Cypher
    driver: Optional[AsyncGraphDatabase] = request.app.state.neo4j_driver
    observations = 0
    edges = 0
    taxa = 0
    if driver:
      async with driver.session() as session:
        obs_result = await session.run(
          "MATCH ()-[r:EATS]->() RETURN sum(r.interaction_count) AS observations"
        )
        obs_record = await obs_result.single()
        observations = obs_record["observations"] if obs_record and obs_record["observations"] else 0

        edges_result = await session.run(
          "MATCH ()-[r:EATS]->() RETURN count(r) AS edges"
        )
        edges_record = await edges_result.single()
        edges = edges_record["edges"] if edges_record else 0

        taxa_result = await session.run(
          """
          MATCH (n) RETURN count(DISTINCT n) AS taxa;
          """
        )
        taxa_record = await taxa_result.single()
        taxa = taxa_record["taxa"] if taxa_record else 0

    return {
      "observations": observations,
      "edges": edges,
      "taxa": taxa,
      "locations": locations,
    }

  return await cached_response(cache, cache_key, producer)


@app.get("/api/v1/predator-prey", tags=["data"])
async def predator_prey_edges(
  request: Request,
  predator_taxon_id: Optional[int] = Query(None, alias="predator"),
  prey_taxon_id: Optional[int] = Query(None, alias="prey"),
  limit: int = Query(100, ge=1, le=500),
  etl_version: Optional[str] = Query(None),
):
  if predator_taxon_id is None and prey_taxon_id is None:
    raise HTTPException(status_code=400, detail="Provide predator or prey taxon id to filter results.")

  pool = await get_pg_pool(request)
  version_info = await resolve_etl_version_id(pool, etl_version)

  conditions = ["agg.etl_version_id = %s"]
  params: list[Any] = [version_info["id"]]
  if predator_taxon_id is not None:
    conditions.append("agg.predator_taxon_id = %s")
    params.append(predator_taxon_id)
  if prey_taxon_id is not None:
    conditions.append("agg.prey_taxon_id = %s")
    params.append(prey_taxon_id)
  params.append(limit)

  where_clause = " AND ".join(conditions)

  async with pool.connection() as conn:
    async with conn.cursor(row_factory=dict_row) as cur:
      await cur.execute(
        f"""
        SELECT
          agg.predator_taxon_id,
          predator.scientific_name AS predator_scientific_name,
          agg.prey_taxon_id,
          prey.scientific_name AS prey_scientific_name,
          agg.interaction_count,
          agg.latest_observation_at
        FROM predator_prey_aggregates AS agg
        JOIN species AS predator ON predator.taxon_id = agg.predator_taxon_id
        JOIN species AS prey ON prey.taxon_id = agg.prey_taxon_id
        WHERE {where_clause}
        ORDER BY agg.interaction_count DESC
        LIMIT %s
        """,
        params,
      )
      fetched_rows = await cur.fetchall()
      rows = [dict(row) for row in fetched_rows]
      return {
        "etl_version": version_info["version"],
        "results": rows,
      }


@app.get("/api/v1/locations/search", tags=["data"])
async def location_search(
  request: Request,
  q: str = Query(..., min_length=2),
  limit: int = Query(10, ge=1, le=25),
  etl_version: Optional[str] = Query(None),
):
  pool = await get_pg_pool(request)
  version_info = await resolve_etl_version_id(pool, etl_version)
  like_value = f"%{q.strip()}%"

  async with pool.connection() as conn:
    async with conn.cursor(row_factory=dict_row) as cur:
      await cur.execute(
        """
        SELECT DISTINCT place_guess
        FROM observations
        WHERE etl_version_id = %s
          AND place_guess IS NOT NULL
          AND place_guess <> ''
          AND place_guess ILIKE %s
        ORDER BY place_guess
        LIMIT %s
        """,
        (version_info["id"], like_value, limit),
      )
      rows = await cur.fetchall()
      results = []
      for row in rows:
        place_name = row["place_guess"]
        if not place_name:
          continue
        results.append(
          {
            "id": place_name,
            "name": place_name,
            "display_name": place_name,
            "place_type_name": None,
          }
        )
      return {"results": results}


@app.get("/api/v1/interactions", tags=["data"])
async def interaction_search(
  request: Request,
  taxon_id: Optional[int] = Query(None, description="Filter by iNaturalist taxon id."),
  taxon_name: Optional[str] = Query(None, description="Filter by common or scientific name."),
  role: Optional[str] = Query(None, description="eater or thing being eaten"),
  year: Optional[int] = Query(None, ge=1800, le=2100),
  location: Optional[str] = Query(None, description="Free-text location filter."),
  ids: Optional[str] = Query(None, description="Comma separated observation ids."),
  limit: int = Query(200, ge=1, le=500),
  offset: int = Query(0, ge=0),
  etl_version: Optional[str] = Query(None),
):
  pool = await get_pg_pool(request)
  version_info = await resolve_etl_version_id(pool, etl_version)
  conditions: List[str] = ["o.etl_version_id = %s"]
  params: List[Any] = [version_info["id"]]

  if ids:
    id_list = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    if not id_list:
      return {"etl_version": version_info["version"], "results": []}
    conditions.append("o.observation_id = ANY(%s)")
    params.append(id_list)

  if taxon_id or taxon_name:
    taxon_cond, taxon_params = await resolve_taxon_condition(pool, taxon_id=taxon_id, taxon_name=taxon_name)
    if taxon_cond:
      conditions.append(taxon_cond)
      params.extend(taxon_params)

  if role:
    conditions.append("o.role = %s")
    params.append(canonical_role_value(role))

  if year:
    conditions.append("EXTRACT(YEAR FROM o.observed_at) = %s")
    params.append(year)

  if location:
    like_location = f"%{location.strip()}%"
    conditions.append("(o.place_guess ILIKE %s OR (o.raw->>'place_guess') ILIKE %s)")
    params.extend([like_location, like_location])

  where_clause = " AND ".join(conditions)
  params.extend([limit, offset])

  async with pool.connection() as conn:
    async with conn.cursor(row_factory=dict_row) as cur:
      await cur.execute(
        f"""
        SELECT
          o.observation_id,
          o.observed_at,
          o.latitude,
          o.longitude,
          o.place_guess,
          o.quality_grade,
          o.description,
          o.role,
          o.taxon_id,
          o.iNaturalist_url,
          o.etl_version_id,
          o.raw,
          s.scientific_name,
          s.common_name,
          s.iconic_taxon_name
        FROM observations AS o
        JOIN species AS s ON s.taxon_id = o.taxon_id
        WHERE {where_clause}
        ORDER BY o.observed_at DESC NULLS LAST, o.observation_id DESC
        LIMIT %s OFFSET %s
        """,
        params,
      )
      rows = await cur.fetchall()
      payload = [build_observation_payload(dict(row)) for row in rows]
      return {
        "etl_version": version_info["version"],
        "results": payload,
      }


if __name__ == "__main__":
  import uvicorn

  uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=8000,
    reload=os.getenv("RELOAD", "false").lower() == "true",
  )


