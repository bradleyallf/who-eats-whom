-- Who Eats Whom Postgres schema (v3: no ETL versions, no aggregates table)
-- Aggregate predator/prey counts are now computed by the Neo4j loader.

CREATE TABLE IF NOT EXISTS species (
  taxon_id BIGINT PRIMARY KEY,
  scientific_name TEXT NOT NULL,
  common_name TEXT,
  iconic_taxon_name TEXT,
  taxon_rank TEXT,
  kingdom TEXT,
  phylum TEXT,
  class_name TEXT,
  order_name TEXT,
  family_name TEXT,
  genus_name TEXT,
  wikipedia_summary TEXT,
  wikipedia_url TEXT,
  image_url TEXT,            -- species photo
  license_code TEXT,         -- license of the species photo
  attribution TEXT,          -- credit for the species photo
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS observations (
  observation_id BIGINT PRIMARY KEY,
  observed_at TIMESTAMPTZ,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  place_guess TEXT,
  quality_grade TEXT,
  description TEXT,
  role TEXT NOT NULL CHECK (role IN ('eater', 'thing being eaten')),
  taxon_id BIGINT NOT NULL REFERENCES species (taxon_id),
  iNaturalist_url TEXT NOT NULL,

  -- Observation photo
  image_url TEXT,
  photo_license_code TEXT,
  photo_attribution TEXT,

  -- When / by which run this row was pulled from iNaturalist
  inat_pulled_at TIMESTAMPTZ,
  inat_api_call TEXT,

  source TEXT,               -- e.g. 'iNaturalist API'
  updated_due_to TEXT,       -- optional: why the row was last updated

  raw JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tracks how far the scheduler has gotten (one row per named job).
CREATE TABLE IF NOT EXISTS scheduler_state (
  name TEXT PRIMARY KEY,
  last_fetched TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed: first run pulls everything from this very old date up to now.
INSERT INTO scheduler_state (name, last_fetched)
VALUES ('inat_import', '1645-08-26 00:00:00+00')
ON CONFLICT (name) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_observations_role ON observations (role);
CREATE INDEX IF NOT EXISTS idx_observations_taxon ON observations (taxon_id);