-- DuckDB World Materialization v1.0 (Fabric World Graph)
--
-- Contract file for Phase 10 (E2.3).
-- This DDL is the single source of truth for DuckDB "world" schema layout.
--
-- Policy:
-- - Do not change without updating:
--   - policy-engine/docs/contracts/E2_3_FABRIC_WORLD_DUCKDB_MATERIALIZATION_V1_0.md
-- - Any breaking change requires a versioned migration plan.

CREATE SCHEMA IF NOT EXISTS world;

-- ------------------------------------------------------------
-- Meta: applied world fact segments
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS world._meta_world_segments (
    segment_id            VARCHAR PRIMARY KEY,
    segment_sha256        VARCHAR NOT NULL,
    row_count             INTEGER NOT NULL,
    applied_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    facts_inserted        INTEGER,
    nodes_touched         INTEGER,
    edges_inserted        INTEGER,
    projections_updated   INTEGER,
    notes                 VARCHAR
);

-- ------------------------------------------------------------
-- Optional: raw world facts index (debuggable event sourcing view)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS world.world_facts (
    fact_id          VARCHAR PRIMARY KEY,
    schema_version   VARCHAR NOT NULL,
    subject_id       VARCHAR NOT NULL,
    predicate_id     VARCHAR NOT NULL,
    object_value     VARCHAR,
    target_id        VARCHAR,
    valid_time       VARCHAR,
    tx_time          VARCHAR NOT NULL,
    provenance_json  VARCHAR NOT NULL,
    trust_json       VARCHAR,
    legal_json       VARCHAR,
    segment_id       VARCHAR,
    inserted_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_world_facts_subject
    ON world.world_facts(subject_id);
CREATE INDEX IF NOT EXISTS idx_world_facts_predicate
    ON world.world_facts(predicate_id);
CREATE INDEX IF NOT EXISTS idx_world_facts_target
    ON world.world_facts(target_id);

-- ------------------------------------------------------------
-- Canonical nodes/edges
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS world.world_nodes (
    node_id      VARCHAR PRIMARY KEY,
    kind         VARCHAR NOT NULL,
    label        VARCHAR,
    artifact_id  VARCHAR,
    props_ref    VARCHAR,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_world_nodes_kind
    ON world.world_nodes(kind);

CREATE TABLE IF NOT EXISTS world.world_edges (
    edge_id         VARCHAR PRIMARY KEY,
    src_id          VARCHAR NOT NULL,
    predicate_id    VARCHAR NOT NULL,
    kind            VARCHAR NOT NULL,
    dst_id          VARCHAR NOT NULL,
    valid_time      VARCHAR,
    tx_time         VARCHAR NOT NULL,
    provenance_json VARCHAR NOT NULL,
    trust_json      VARCHAR,
    legal_json      VARCHAR,
    segment_id      VARCHAR,
    inserted_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_world_edges_kind
    ON world.world_edges(kind);
CREATE INDEX IF NOT EXISTS idx_world_edges_src_kind
    ON world.world_edges(src_id, kind);
CREATE INDEX IF NOT EXISTS idx_world_edges_dst_kind
    ON world.world_edges(dst_id, kind);

-- ------------------------------------------------------------
-- Projections: events
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS world.world_events (
    event_id         VARCHAR PRIMARY KEY,
    event_kind       VARCHAR NOT NULL,
    agent_id         VARCHAR NOT NULL,
    agent_type       VARCHAR,
    agent_label      VARCHAR,
    activity_id      VARCHAR,
    activity_type    VARCHAR,
    activity_label   VARCHAR,
    started_at       TIMESTAMP,
    ended_at         TIMESTAMP,
    evidence_ref     VARCHAR,
    provenance_ref   VARCHAR,
    props_json       VARCHAR,
    meta_artifact_id VARCHAR,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_world_events_kind
    ON world.world_events(event_kind);

-- ------------------------------------------------------------
-- Projections: documents
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS world.doc_sources (
    doc_source_id  VARCHAR PRIMARY KEY,
    canonical_url  VARCHAR,
    official_id    VARCHAR,
    jurisdiction   VARCHAR,
    language       VARCHAR,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_doc_sources_canonical_url
    ON world.doc_sources(canonical_url);

CREATE TABLE IF NOT EXISTS world.doc_versions (
    doc_version_id   VARCHAR PRIMARY KEY,
    doc_source_id    VARCHAR NOT NULL,
    retrieved_at     TIMESTAMP,
    mime             VARCHAR,
    license          VARCHAR,
    jurisdiction     VARCHAR,
    language         VARCHAR,
    raw_ref          VARCHAR NOT NULL,
    normalized_ref   VARCHAR,
    structure_ref    VARCHAR,
    chunks_ref       VARCHAR,
    props_json       VARCHAR,
    meta_artifact_id VARCHAR,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_doc_versions_source
    ON world.doc_versions(doc_source_id);

CREATE TABLE IF NOT EXISTS world.doc_fragments (
    fragment_id      VARCHAR PRIMARY KEY,
    doc_version_id   VARCHAR NOT NULL,
    anchor_kind      VARCHAR NOT NULL,
    anchor_path      VARCHAR,
    offset_start     BIGINT,
    offset_end       BIGINT,
    page_start       BIGINT,
    page_end         BIGINT,
    text_hash        VARCHAR NOT NULL,
    quote_preview    VARCHAR,
    props_json       VARCHAR,
    meta_artifact_id VARCHAR,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_doc_fragments_doc_version
    ON world.doc_fragments(doc_version_id);

-- ------------------------------------------------------------
-- Projections: claims
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS world.claims (
    claim_id         VARCHAR PRIMARY KEY,
    predicate_id     VARCHAR NOT NULL,
    subject_id       VARCHAR,
    subject_text     VARCHAR,
    value_text       VARCHAR NOT NULL,
    value_decimal    VARCHAR,
    unit_id          VARCHAR,
    confidence       VARCHAR,
    source_kind      VARCHAR,
    jurisdiction     VARCHAR,
    domain           VARCHAR,
    valid_from       TIMESTAMP,
    valid_to         TIMESTAMP,
    qualifiers_json  VARCHAR,
    props_json       VARCHAR,
    meta_artifact_id VARCHAR,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_claims_predicate
    ON world.claims(predicate_id);
CREATE INDEX IF NOT EXISTS idx_claims_subject
    ON world.claims(subject_id);

CREATE TABLE IF NOT EXISTS world.claim_citations (
    claim_id    VARCHAR NOT NULL,
    fragment_id VARCHAR NOT NULL,
    edge_id     VARCHAR,
    PRIMARY KEY (claim_id, fragment_id)
);

CREATE INDEX IF NOT EXISTS idx_claim_citations_claim
    ON world.claim_citations(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_citations_fragment
    ON world.claim_citations(fragment_id);

-- ------------------------------------------------------------
-- Projections: conflicts (placeholder schema)
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS world.conflict_sets (
    conflict_set_id  VARCHAR PRIMARY KEY,
    kind             VARCHAR,
    props_json       VARCHAR,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS world.conflict_members (
    conflict_set_id  VARCHAR NOT NULL,
    claim_id         VARCHAR NOT NULL,
    edge_id          VARCHAR,
    PRIMARY KEY (conflict_set_id, claim_id)
);

CREATE INDEX IF NOT EXISTS idx_conflict_members_claim
    ON world.conflict_members(claim_id);

