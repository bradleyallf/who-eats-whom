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
          (
            SELECT o.raw->>'image_url'
            FROM observations o
            WHERE o.taxon_id = s.taxon_id
              AND o.raw->>'image_url' IS NOT NULL
              AND o.raw->>'image_url' <> ''
            LIMIT 1
          ) AS image_url
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
        SELECT taxon_id, scientific_name, common_name, iconic_taxon_name
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
        "wikipedia_summary": None,
      }
    ]
  }


@app.get("/api/v1/food-web/summary", tags=["data"])
async def food_web_summary(
  request: Request,
  etl_version: Optional[str] = Query(None, description="Override ETL version; defaults to latest."),
):
  pool = await get_pg_pool(request)
  cache = await get_redis_cache(request)
  version_info = await resolve_etl_version_id(pool, etl_version)
  cache_key = f"v{version_info['version']}:summary"

  async def producer():
    async with pool.connection() as conn:
      async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT COUNT(*) AS total_species FROM species")
        total_species = (await cur.fetchone())["total_species"]

        await cur.execute(
          """
          SELECT
            COUNT(DISTINCT predator_taxon_id) AS predator_species,
            COUNT(DISTINCT prey_taxon_id) AS prey_species,
            COALESCE(SUM(interaction_count), 0) AS total_interactions
          FROM predator_prey_aggregates
          WHERE etl_version_id = %s
          """,
          (version_info["id"],),
        )
        aggregates = dict(await cur.fetchone())

    neo4j_metrics: Dict[str, Any] = {}
    driver: Optional[AsyncGraphDatabase] = request.app.state.neo4j_driver
    if driver:
      async with driver.session() as session:
        nodes_result = await session.run(
          "MATCH (s:Species {etl_version: $etl}) RETURN count(s) AS species",
          etl=version_info["version"],
        )
        edges_result = await session.run(
          "MATCH ()-[r:EATS {etl_version: $etl}]->() RETURN count(r) AS relationships",
          etl=version_info["version"],
        )
        top_predators_result = await session.run(
          """
          MATCH (pred:Species)-[r:EATS {etl_version:$etl}]->(:Species)
          RETURN pred.taxon_id AS taxon_id,
                 pred.scientific_name AS scientific_name,
                 SUM(r.interaction_count) AS total_interactions
          ORDER BY total_interactions DESC
          LIMIT 5
          """,
          etl=version_info["version"],
        )
        nodes_record = await nodes_result.single()
        edges_record = await edges_result.single()
        top_predators = await top_predators_result.data()
        neo4j_metrics = {
          "species_nodes": nodes_record["species"] if nodes_record else 0,
          "edges": edges_record["relationships"] if edges_record else 0,
          "top_predators": top_predators,
        }

    return {
      "etl_version": version_info["version"],
      "postgres": {
        "total_species": total_species,
        "predator_species": aggregates["predator_species"],
        "prey_species": aggregates["prey_species"],
        "total_interactions": aggregates["total_interactions"],
      },
      "neo4j": neo4j_metrics or None,
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

# ============================================================
# Validation Endpoints — Author: Aurav Khetarpal
# ============================================================

from pydantic import BaseModel
import secrets

# Pydantic model

class ValidatorCreate(BaseModel):
    """Admin uses this to add a new validator."""
    email: str
    name: str
    role: Optional[str] = "validator"


class VoteSubmission(BaseModel):
    """Validator submits a vote on a flagged record."""
    queue_id: int
    validator_id: int
    decision: str  # ai_prediction, user_species, cannot_determine, all_incorrect
    selected_species: Optional[str] = None  # which species they picked
    notes: Optional[str] = None

# Helper Functions

async def check_consensus(
    pool,
    queue_id: int
) -> None:
    """
    After each vote, check if consensus has been reached.
    Consensus = 2 of 3 validators picked the same species.
    Updates validation_queue status accordingly.
    """
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:

            # Get all votes for this record
            await cur.execute(
                """
                SELECT decision, selected_species, COUNT(*) as count
                FROM validation_votes
                WHERE queue_id = %s
                GROUP BY decision, selected_species
                ORDER BY count DESC
                """,
                (queue_id,)
            )
            vote_groups = await cur.fetchall()

            # Get total vote count
            await cur.execute(
                "SELECT COUNT(*) as total FROM validation_votes WHERE queue_id = %s",
                (queue_id,)
            )
            total_votes = (await cur.fetchone())["total"]

            # Check if any species has 2+ votes (majority)
            consensus_species = None
            consensus_reached = False

            for group in vote_groups:
                if group["count"] >= 2:
                    consensus_species = group["selected_species"]
                    consensus_reached = True
                    break

            # Determine new status
            if consensus_reached:
                new_status = "consensus"
            elif total_votes >= 3:
                # All 3 voted but no majority
                new_status = "no_consensus"
            else:
                # Still waiting for more votes
                new_status = "in_progress"

            # Update validation_queue
            await cur.execute(
                """
                UPDATE validation_queue
                SET
                    vote_count = %s,
                    consensus_species = %s,
                    consensus_reached = %s,
                    validation_status = %s,
                    consensus_at = CASE WHEN %s THEN NOW() ELSE NULL END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    total_votes,
                    consensus_species,
                    consensus_reached,
                    new_status,
                    consensus_reached,
                    queue_id,
                )
            )
        await conn.commit()

# Validator Management Endpoints

@app.post("/api/v1/validators", tags=["validation"])
async def create_validator(
    request: Request,
    body: ValidatorCreate,
):
    """
    Admin endpoint to add a new validator.
    Generates an auth token for the validator to use.
    """
    pool = await get_pg_pool(request)

    # Generate a secure random token for this validator
    auth_token = secrets.token_urlsafe(32)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:

            # Check if email already exists
            await cur.execute(
                "SELECT id FROM validators WHERE email = %s",
                (body.email,)
            )
            existing = await cur.fetchone()
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Validator with email {body.email} already exists."
                )

            # Insert new validator
            await cur.execute(
                """
                INSERT INTO validators (email, name, role, auth_token)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, name, role, auth_token, created_at
                """,
                (body.email, body.name, body.role, auth_token)
            )
            validator = await cur.fetchone()
        await conn.commit()

    return {
        "message": "Validator created successfully.",
        "validator": dict(validator),
        "note": "Share the auth_token with the validator for login."
    }


@app.get("/api/v1/validators", tags=["validation"])
async def list_validators(request: Request):
    """
    Admin endpoint to list all validators.
    """
    pool = await get_pg_pool(request)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT
                    id, email, name, role, is_active,
                    created_at,
                    (
                        SELECT COUNT(*)
                        FROM validation_votes vv
                        WHERE vv.validator_id = v.id
                    ) as total_votes
                FROM validators v
                ORDER BY created_at DESC
                """
            )
            validators = await cur.fetchall()

    return {"results": [dict(v) for v in validators]}

# Queue Endpoints

@app.get("/api/v1/validation/queue", tags=["validation"])
async def get_validation_queue(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    severity: Optional[str] = Query(None, description="Filter by flag_severity"),
):
    """
    Returns paginated list of AI-flagged records pending review.
    Ordered by lowest confidence first (most uncertain first).
    Optionally filter by severity: near_miss, moderate, distant, detection_failure
    """
    pool = await get_pg_pool(request)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:

            # Build WHERE clause
            conditions = ["validation_status IN ('pending', 'in_progress')"]
            params: List[Any] = []

            if severity:
                conditions.append("flag_severity = %s")
                params.append(severity)

            where_clause = " AND ".join(conditions)
            params.extend([limit, offset])

            await cur.execute(
                f"""
                SELECT
                    id,
                    image_id,
                    observation_id,
                    photo_url,
                    user_species,
                    user_common_name,
                    ai_top1_species,
                    ai_top1_score,
                    ai_top2_score,
                    confidence_gap,
                    same_species,
                    topk_predictions,
                    flag_reason,
                    flag_severity,
                    pred_prey,
                    vote_count,
                    validation_status,
                    created_at
                FROM validation_queue
                WHERE {where_clause}
                ORDER BY ai_top1_score ASC NULLS LAST
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = await cur.fetchall()

            # Get counts by status
            await cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE validation_status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE validation_status = 'in_progress') as in_progress,
                    COUNT(*) FILTER (WHERE validation_status = 'consensus') as consensus,
                    COUNT(*) FILTER (WHERE validation_status = 'no_consensus') as no_consensus
                FROM validation_queue
                """
            )
            counts = dict(await cur.fetchone())

            return {
                "counts": counts,
                "limit": limit,
                "offset": offset,
                "results": [dict(row) for row in rows],
            }


@app.get("/api/v1/validation/queue/{queue_id}", tags=["validation"])
async def get_queue_record(
    request: Request,
    queue_id: int,
):
    """
    Returns a single flagged record by id,
    including all votes submitted so far.
    """
    pool = await get_pg_pool(request)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:

            # Get the record
            await cur.execute(
                """
                SELECT * FROM validation_queue WHERE id = %s
                """,
                (queue_id,)
            )
            record = await cur.fetchone()
            if not record:
                raise HTTPException(
                    status_code=404,
                    detail=f"No record found for id: {queue_id}"
                )

            # Get all votes for this record
            await cur.execute(
                """
                SELECT
                    vv.id,
                    vv.decision,
                    vv.selected_species,
                    vv.notes,
                    vv.voted_at,
                    v.name as validator_name
                FROM validation_votes vv
                JOIN validators v ON v.id = vv.validator_id
                WHERE vv.queue_id = %s
                ORDER BY vv.voted_at
                """,
                (queue_id,)
            )
            votes = await cur.fetchall()

    return {
        "record": dict(record),
        "votes": [dict(v) for v in votes],
    }

# Voting Endpoint

@app.post("/api/v1/validation/vote", tags=["validation"])
async def submit_vote(
    request: Request,
    body: VoteSubmission,
):
    """
    Submit a validator's vote on a flagged record.

    Decision options:
    - ai_prediction: validator picks one of the 5 AI predictions
      (must provide selected_species)
    - user_species: validator agrees with original iNaturalist user
    - cannot_determine: not enough info to decide
    - all_incorrect: none of the options are correct

    After each vote, consensus is automatically checked.
    Consensus = 2 of 3 validators pick the same species.
    """
    valid_decisions = {
        "ai_prediction",
        "user_species",
        "cannot_determine",
        "all_incorrect",
    }
    if body.decision not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision. Must be one of: {valid_decisions}"
        )

    # If picking an AI prediction, must provide selected_species
    if body.decision == "ai_prediction" and not body.selected_species:
        raise HTTPException(
            status_code=400,
            detail="selected_species is required when decision is ai_prediction"
        )

    pool = await get_pg_pool(request)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:

            # Check queue record exists
            await cur.execute(
                "SELECT id, vote_count FROM validation_queue WHERE id = %s",
                (body.queue_id,)
            )
            record = await cur.fetchone()
            if not record:
                raise HTTPException(
                    status_code=404,
                    detail=f"No record found for queue_id: {body.queue_id}"
                )

            # Check validator exists and is active
            await cur.execute(
                "SELECT id FROM validators WHERE id = %s AND is_active = TRUE",
                (body.validator_id,)
            )
            validator = await cur.fetchone()
            if not validator:
                raise HTTPException(
                    status_code=404,
                    detail=f"Validator {body.validator_id} not found or inactive"
                )

            # Check validator hasn't already voted on this record
            await cur.execute(
                """
                SELECT id FROM validation_votes
                WHERE queue_id = %s AND validator_id = %s
                """,
                (body.queue_id, body.validator_id)
            )
            existing_vote = await cur.fetchone()
            if existing_vote:
                raise HTTPException(
                    status_code=400,
                    detail="Validator has already voted on this record"
                )

            # Check record hasn't already reached consensus
            await cur.execute(
                "SELECT validation_status FROM validation_queue WHERE id = %s",
                (body.queue_id,)
            )
            status_row = await cur.fetchone()
            if status_row["validation_status"] == "consensus":
                raise HTTPException(
                    status_code=400,
                    detail="This record has already reached consensus"
                )

            # Determine selected species based on decision
            selected_species = None
            if body.decision == "ai_prediction":
                selected_species = body.selected_species
            elif body.decision == "user_species":
                # Get user species from queue record
                await cur.execute(
                    "SELECT user_species FROM validation_queue WHERE id = %s",
                    (body.queue_id,)
                )
                queue_row = await cur.fetchone()
                selected_species = queue_row["user_species"]

            # Insert vote
            await cur.execute(
                """
                INSERT INTO validation_votes (
                    queue_id,
                    validator_id,
                    decision,
                    selected_species,
                    notes
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING id, queue_id, decision, selected_species, voted_at
                """,
                (
                    body.queue_id,
                    body.validator_id,
                    body.decision,
                    selected_species,
                    body.notes,
                )
            )
            vote = await cur.fetchone()
        await conn.commit()

    # Check consensus after vote is saved
    await check_consensus(pool, body.queue_id)

    return {
        "message": "Vote submitted successfully.",
        "vote": dict(vote),
    }

# Stats Endpoint

@app.get("/api/v1/validation/stats", tags=["validation"])
async def get_validation_stats(request: Request):
    """
    Returns overall validation progress statistics.
    Useful for showing progress on the dashboard.
    """
    pool = await get_pg_pool(request)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:

            # Overall queue stats
            await cur.execute(
                """
                SELECT
                    COUNT(*) as total_records,
                    COUNT(*) FILTER (WHERE validation_status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE validation_status = 'in_progress') as in_progress,
                    COUNT(*) FILTER (WHERE validation_status = 'consensus') as consensus,
                    COUNT(*) FILTER (WHERE validation_status = 'no_consensus') as no_consensus,
                    COUNT(*) FILTER (WHERE validation_status = 'escalated') as escalated
                FROM validation_queue
                """
            )
            queue_stats = dict(await cur.fetchone())

            # Total votes cast
            await cur.execute("SELECT COUNT(*) as total_votes FROM validation_votes")
            vote_stats = dict(await cur.fetchone())

            # Severity breakdown
            await cur.execute(
                """
                SELECT flag_severity, COUNT(*) as count
                FROM validation_queue
                GROUP BY flag_severity
                ORDER BY count DESC
                """
            )
            severity_breakdown = [dict(r) for r in await cur.fetchall()]

    return {
        "queue": queue_stats,
        "votes": vote_stats,
        "severity_breakdown": severity_breakdown,
        "progress_percentage": round(
            queue_stats["consensus"] / queue_stats["total_records"] * 100, 1
        ) if queue_stats["total_records"] > 0 else 0,
    }


