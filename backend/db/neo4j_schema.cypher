// Who Eats Whom Neo4j schema (Phase 2)

// Species nodes, keyed by iNaturalist taxon id.
CREATE CONSTRAINT species_taxon_id IF NOT EXISTS
FOR (s:Species)
REQUIRE s.taxon_id IS UNIQUE;

// Each load is tagged with etl_version to make cache keys deterministic.
CREATE INDEX species_etl_version IF NOT EXISTS
FOR (s:Species)
ON (s.etl_version);

// Predator-prey relationships with aggregated weights.
CREATE INDEX eats_etl_version IF NOT EXISTS
FOR ()-[r:EATS]-()
ON (r.etl_version);

// Example relationship payload:
// (:Species {taxon_id: 44705})-[:EATS {etl_version: '2024-11-24', interaction_count: 5, last_seen_at: datetime()}]->(:Species {taxon_id: 37932});
