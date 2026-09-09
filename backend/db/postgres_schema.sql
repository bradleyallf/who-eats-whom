-- Who Eats Whom Postgres logical schema (Phase 2)

CREATE TABLE IF NOT EXISTS etl_versions (
  id BIGSERIAL PRIMARY KEY,
  version TEXT NOT NULL UNIQUE,
  source_csv TEXT NOT NULL,
  loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  row_count INTEGER NOT NULL DEFAULT 0,
  notes TEXT
);

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
  image_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE species ADD COLUMN IF NOT EXISTS wikipedia_summary TEXT;
ALTER TABLE species ADD COLUMN IF NOT EXISTS wikipedia_url TEXT;
ALTER TABLE species ADD COLUMN IF NOT EXISTS image_url TEXT;

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
  etl_version_id BIGINT NOT NULL REFERENCES etl_versions (id),
  raw JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS predator_prey_aggregates (
  predator_taxon_id BIGINT NOT NULL REFERENCES species (taxon_id),
  prey_taxon_id BIGINT NOT NULL REFERENCES species (taxon_id),
  interaction_count INTEGER NOT NULL DEFAULT 0,
  latest_observation_at TIMESTAMPTZ,
  etl_version_id BIGINT NOT NULL REFERENCES etl_versions (id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (predator_taxon_id, prey_taxon_id, etl_version_id)
);

CREATE INDEX IF NOT EXISTS idx_observations_role ON observations (role);
CREATE INDEX IF NOT EXISTS idx_observations_taxon ON observations (taxon_id);
CREATE INDEX IF NOT EXISTS idx_predator_prey_counts ON predator_prey_aggregates (interaction_count DESC);
