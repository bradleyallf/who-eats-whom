-- ============================================================
-- Who Eats Whom - Validation System Schema
-- Author: Aurav Khetarpal (Summer 2026)
-- ============================================================

-- ============================================================
-- TABLE 1: validators
-- Stores expert validators who can review flagged records
-- Admin manually adds validators for now, OAuth added later
-- ============================================================
CREATE TABLE IF NOT EXISTS validators (

  -- Auto-generated unique identifier
  id BIGSERIAL PRIMARY KEY,

  -- Validator's email address - used for login identification
  email TEXT NOT NULL UNIQUE,

  -- Validator's full name for display
  name TEXT NOT NULL,

  -- Role - validator or admin
  role TEXT NOT NULL DEFAULT 'validator' CHECK (
    role IN ('validator', 'admin')
  ),

  -- Simple token for authentication until OAuth is implemented
  auth_token TEXT UNIQUE,

  -- Whether this validator account is active
  is_active BOOLEAN NOT NULL DEFAULT TRUE,

  -- Timestamp of when validator was added
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Timestamp of last update
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

-- Index to speed up login lookup by email
CREATE INDEX IF NOT EXISTS idx_validators_email
  ON validators (email);

-- Index to speed up token authentication
CREATE INDEX IF NOT EXISTS idx_validators_token
  ON validators (auth_token);


-- ============================================================
-- TABLE 2: images
-- Stores Cloudinary image URLs for fast retrieval
-- Images are downloaded from iNaturalist S3 and uploaded
-- to Cloudinary once - never fetched from iNaturalist again
-- ============================================================
CREATE TABLE IF NOT EXISTS images (

  -- Auto-generated unique identifier
  id BIGSERIAL PRIMARY KEY,

  -- iNaturalist photo ID extracted from image_id
  -- e.g. 171703626 from obs_102691691_photo_171703626
  photo_id TEXT NOT NULL UNIQUE,

  -- iNaturalist observation ID
  observation_id TEXT,

  -- Original iNaturalist S3 URL (kept for reference)
  inaturalist_url TEXT,

  -- Cloudinary public ID for the uploaded image
  cloudinary_public_id TEXT,

  -- Cloudinary URL for fast CDN retrieval (this is what frontend uses)
  cloudinary_url TEXT,

  -- Cloudinary thumbnail URL for list views
  cloudinary_thumbnail_url TEXT,

  -- Image format e.g. jpeg, jpg, png
  image_format TEXT,

  -- Whether image was successfully uploaded to Cloudinary
  upload_status TEXT NOT NULL DEFAULT 'pending' CHECK (
    upload_status IN ('pending', 'uploaded', 'failed')
  ),

  -- Timestamp of when image was uploaded to Cloudinary
  uploaded_at TIMESTAMPTZ,

  -- Timestamp of when this record was inserted
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

-- Index to speed up lookups by photo_id
CREATE INDEX IF NOT EXISTS idx_images_photo_id
  ON images (photo_id);

-- Index to filter by upload status
CREATE INDEX IF NOT EXISTS idx_images_upload_status
  ON images (upload_status);


-- ============================================================
-- TABLE 3: validation_queue
-- Stores AI-flagged records from BioVerify pipeline
-- Each record needs votes from 3 validators
-- ============================================================
CREATE TABLE IF NOT EXISTS validation_queue (

  -- Auto-generated unique identifier
  id BIGSERIAL PRIMARY KEY,

  -- Unique image identifier from BioVerify
  -- e.g. obs_102691691_photo_171703626
  image_id TEXT NOT NULL UNIQUE,

  -- iNaturalist observation number extracted from image_id
  observation_id TEXT,

  -- Foreign key to images table for fast Cloudinary retrieval
  image_record_id BIGINT REFERENCES images (id),

  -- Original iNaturalist photo URL (fallback if Cloudinary not ready)
  photo_url TEXT,

  -- Species name the iNaturalist citizen scientist provided
  user_species TEXT,

  -- Common name of user identified species
  user_common_name TEXT,

  -- BioCLIP2 top-1 predicted species name
  ai_top1_species TEXT,

  -- Confidence score for the top-1 prediction (0 to 1)
  ai_top1_score FLOAT,

  -- Confidence score for the second-ranked prediction
  ai_top2_score FLOAT,

  -- Difference between top-1 and top-2 score
  -- Small gap means model was uncertain between two options
  confidence_gap FLOAT,

  -- Whether BioCLIP2 top-1 prediction matched the user label
  same_species BOOLEAN,

  -- All 5 BioCLIP2 predictions with scores stored as JSON
  -- Used to show all 5 options to validator on dashboard
  topk_predictions JSONB,

  -- Human readable explanation of why this record was flagged
  flag_reason TEXT,

  -- How biologically wrong the prediction was
  flag_severity TEXT CHECK (flag_severity IN (
    'near_miss',
    'moderate',
    'distant',
    'detection_failure'
  )),

  -- Whether this organism is the predator or prey
  pred_prey TEXT,

  -- How many validators have voted on this record (max 3)
  vote_count INTEGER NOT NULL DEFAULT 0,

  -- The species consensus reached by majority vote
  -- Populated when 2 of 3 validators agree
  consensus_species TEXT,

  -- Whether consensus has been reached (2 of 3 agree)
  consensus_reached BOOLEAN NOT NULL DEFAULT FALSE,

  -- Final validation status of this record
  validation_status TEXT NOT NULL DEFAULT 'pending' CHECK (
    validation_status IN (
      'pending',       -- not yet reviewed by anyone
      'in_progress',   -- 1 or 2 votes received, waiting for more
      'consensus',     -- 2 of 3 validators agreed
      'no_consensus',  -- all 3 voted but no majority reached
      'escalated'      -- flagged for further review
    )
  ),

  -- Timestamp of when consensus was reached
  consensus_at TIMESTAMPTZ,

  -- Timestamp of when this record was inserted
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Timestamp of last update
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

-- Index to speed up filtering by status
CREATE INDEX IF NOT EXISTS idx_validation_status
  ON validation_queue (validation_status);

-- Index to speed up lookups by image_id
CREATE INDEX IF NOT EXISTS idx_validation_image_id
  ON validation_queue (image_id);

-- Index to surface most uncertain records first
CREATE INDEX IF NOT EXISTS idx_validation_confidence_gap
  ON validation_queue (confidence_gap ASC NULLS LAST);

-- Index to find records still needing votes
CREATE INDEX IF NOT EXISTS idx_validation_vote_count
  ON validation_queue (vote_count);


-- ============================================================
-- TABLE 4: validation_votes
-- Each validator submits one vote per record
-- A record gets up to 3 votes total
-- Consensus = 2 of 3 validators pick the same species
-- ============================================================
CREATE TABLE IF NOT EXISTS validation_votes (

  -- Auto-generated unique identifier
  id BIGSERIAL PRIMARY KEY,

  -- Which flagged record this vote is for
  queue_id BIGINT NOT NULL REFERENCES validation_queue (id),

  -- Which validator submitted this vote
  validator_id BIGINT NOT NULL REFERENCES validators (id),

  -- The validator's chosen species from the 8 options:
  -- one of the 5 AI predictions, user species,
  -- cannot_determine, or all_incorrect
  selected_species TEXT,

  -- The type of decision made
  decision TEXT NOT NULL CHECK (decision IN (
    'ai_prediction',     -- validator picked one of the 5 AI predictions
    'user_species',      -- validator agrees with original iNaturalist user
    'cannot_determine',  -- not enough info to decide
    'all_incorrect'      -- none of the options are correct
  )),

  -- Optional free text notes from the validator
  notes TEXT,

  -- Timestamp of when this vote was submitted
  voted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()

);

-- Prevent a validator from voting twice on the same record
CREATE UNIQUE INDEX IF NOT EXISTS idx_votes_unique_per_validator
  ON validation_votes (queue_id, validator_id);

-- Index to count votes per record quickly
CREATE INDEX IF NOT EXISTS idx_votes_queue_id
  ON validation_votes (queue_id);

-- Index to see all votes by a specific validator
CREATE INDEX IF NOT EXISTS idx_votes_validator_id
  ON validation_votes (validator_id);


-- ============================================================
-- TABLE 5: validator_assignments
-- Tracks which records are assigned to which validators
-- Random assignment ensures fair distribution
-- ============================================================
CREATE TABLE IF NOT EXISTS validator_assignments (

  -- Auto-generated unique identifier
  id BIGSERIAL PRIMARY KEY,

  -- Which flagged record is assigned
  queue_id BIGINT NOT NULL REFERENCES validation_queue (id),

  -- Which validator it is assigned to
  validator_id BIGINT NOT NULL REFERENCES validators (id),

  -- Whether this validator has completed their review
  completed BOOLEAN NOT NULL DEFAULT FALSE,

  -- Timestamp of when assignment was made
  assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Timestamp of when validator completed their review
  completed_at TIMESTAMPTZ

);

-- Prevent assigning same record to same validator twice
CREATE UNIQUE INDEX IF NOT EXISTS idx_assignments_unique
  ON validator_assignments (queue_id, validator_id);

-- Index to find all assignments for a validator
CREATE INDEX IF NOT EXISTS idx_assignments_validator
  ON validator_assignments (validator_id);

-- Index to find all assignments for a record
CREATE INDEX IF NOT EXISTS idx_assignments_queue
  ON validator_assignments (queue_id);