"""SKG table DDL and confidence aggregation helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import duckdb

from polisyos.ir.analytics.literature import EvidenceStrength

SKG_DDL = """
CREATE TABLE IF NOT EXISTS ac_skg_articles (
    openalex_id        VARCHAR PRIMARY KEY,
    doi                VARCHAR,
    title              VARCHAR NOT NULL,
    year               INTEGER,
    cited_by_count     INTEGER DEFAULT 0,
    extraction_json    VARCHAR NOT NULL,
    context_json       VARCHAR,
    extraction_ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retracted          BOOLEAN DEFAULT FALSE,
    skg_version        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ac_skg_variables (
    canonical_name     VARCHAR PRIMARY KEY,
    display_name       VARCHAR NOT NULL,
    parent_name        VARCHAR,
    mention_count      INTEGER DEFAULT 0,
    first_seen_ts      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ac_skg_edges (
    edge_id            VARCHAR PRIMARY KEY,
    src                VARCHAR NOT NULL,
    dst                VARCHAR NOT NULL,
    direction          VARCHAR NOT NULL,
    n_articles         INTEGER DEFAULT 1,
    article_refs       VARCHAR NOT NULL,
    evidence_strength  VARCHAR NOT NULL,
    confidence         DOUBLE NOT NULL,
    scope_conditions   VARCHAR DEFAULT '[]',
    meta_effect_size   DOUBLE,
    candidate_layer    VARCHAR DEFAULT 'candidate',
    quality_signals_json VARCHAR DEFAULT '{}',
    updated_ts         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ac_skg_edge_evidence (
    edge_id            VARCHAR NOT NULL,
    claim_id           VARCHAR NOT NULL,
    openalex_id        VARCHAR NOT NULL,
    src                VARCHAR NOT NULL,
    dst                VARCHAR NOT NULL,
    direction          VARCHAR NOT NULL,
    evidence_strength  VARCHAR NOT NULL,
    confidence         DOUBLE NOT NULL,
    design_family      VARCHAR,
    design_quality_tier INTEGER,
    skg_version        INTEGER NOT NULL,
    PRIMARY KEY (edge_id, claim_id, openalex_id)
);

CREATE TABLE IF NOT EXISTS ac_skg_family_edges (
    family_edge_id            VARCHAR PRIMARY KEY,
    src_family                VARCHAR NOT NULL,
    dst_family                VARCHAR NOT NULL,
    direction                 VARCHAR NOT NULL,
    n_articles                INTEGER DEFAULT 1,
    n_claims                  INTEGER DEFAULT 1,
    article_refs              VARCHAR NOT NULL,
    claim_refs                VARCHAR NOT NULL,
    evidence_strength         VARCHAR NOT NULL,
    confidence                DOUBLE NOT NULL,
    direction_histogram_json  VARCHAR DEFAULT '{}',
    design_tier_histogram_json VARCHAR DEFAULT '{}',
    design_family_histogram_json VARCHAR DEFAULT '{}',
    candidate_layer           VARCHAR DEFAULT 'family',
    quality_signals_json      VARCHAR DEFAULT '{}',
    updated_ts                TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ac_skg_parameters (
    param_id           VARCHAR PRIMARY KEY,
    canonical_name     VARCHAR NOT NULL,
    openalex_id        VARCHAR NOT NULL,
    parameter_json     VARCHAR NOT NULL,
    context_json       VARCHAR
);

CREATE TABLE IF NOT EXISTS ac_skg_simulation_parameters (
    numeric_id              VARCHAR PRIMARY KEY,
    openalex_id             VARCHAR NOT NULL,
    canonical_name          VARCHAR NOT NULL,
    estimate_type           VARCHAR NOT NULL,
    point_estimate          DOUBLE NOT NULL,
    estimate_sign           VARCHAR,
    unit                    VARCHAR,
    evidence_strength       VARCHAR,
    confidence_interval_json VARCHAR DEFAULT '[]',
    std_error               DOUBLE,
    linked_claim_ids_json   VARCHAR DEFAULT '[]',
    linked_edges_json       VARCHAR DEFAULT '[]',
    context_json            VARCHAR,
    source_layer            VARCHAR DEFAULT 'simulation_ready',
    uncertainty_source      VARCHAR DEFAULT '',
    quality_flags_json      VARCHAR DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS ac_skg_canonization_cache (
    raw_name           VARCHAR PRIMARY KEY,
    canonical_name     VARCHAR NOT NULL,
    approved           BOOLEAN DEFAULT FALSE,
    created_ts         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ac_skg_versions (
    version_id         INTEGER PRIMARY KEY,
    created_ts         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    n_articles         INTEGER,
    n_edges            INTEGER,
    n_variables        INTEGER,
    description        VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_ac_skg_edges_src ON ac_skg_edges(src);
CREATE INDEX IF NOT EXISTS idx_ac_skg_edges_dst ON ac_skg_edges(dst);
CREATE INDEX IF NOT EXISTS idx_ac_skg_edges_confidence ON ac_skg_edges(confidence);
CREATE INDEX IF NOT EXISTS idx_ac_skg_edge_evidence_edge ON ac_skg_edge_evidence(edge_id);
CREATE INDEX IF NOT EXISTS idx_ac_skg_edge_evidence_article ON ac_skg_edge_evidence(openalex_id);
CREATE INDEX IF NOT EXISTS idx_ac_skg_family_edges_src ON ac_skg_family_edges(src_family);
CREATE INDEX IF NOT EXISTS idx_ac_skg_family_edges_dst ON ac_skg_family_edges(dst_family);
CREATE INDEX IF NOT EXISTS idx_ac_skg_params_name ON ac_skg_parameters(canonical_name);
CREATE INDEX IF NOT EXISTS idx_ac_skg_params_article ON ac_skg_parameters(openalex_id);
CREATE INDEX IF NOT EXISTS idx_ac_skg_sim_params_name ON ac_skg_simulation_parameters(canonical_name);
CREATE INDEX IF NOT EXISTS idx_ac_skg_sim_params_article ON ac_skg_simulation_parameters(openalex_id);
CREATE INDEX IF NOT EXISTS idx_ac_skg_articles_year ON ac_skg_articles(year);
CREATE INDEX IF NOT EXISTS idx_ac_skg_articles_retracted ON ac_skg_articles(retracted);

CREATE TABLE IF NOT EXISTS ac_skg_context_attributes (
    attr_id            VARCHAR PRIMARY KEY,
    openalex_id        VARCHAR NOT NULL,
    canonical_name     VARCHAR NOT NULL,
    attribute_value     DOUBLE,
    value_qualitative  VARCHAR,
    unit               VARCHAR,
    country_code       VARCHAR,
    time_period        VARCHAR,
    measurement_method VARCHAR,
    confidence         DOUBLE DEFAULT 0.5,
    evidence_span_count INTEGER DEFAULT 0,
    skg_version        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ac_skg_moderation_edges (
    moderation_id      VARCHAR PRIMARY KEY,
    base_cause         VARCHAR NOT NULL,
    base_effect        VARCHAR NOT NULL,
    moderator          VARCHAR NOT NULL,
    base_claim_id      VARCHAR,
    direction_of_mod   VARCHAR,
    interaction_coeff  DOUBLE,
    interaction_pvalue DOUBLE,
    evidence_count     INTEGER DEFAULT 1,
    confidence         DOUBLE DEFAULT 0.5,
    match_quality      VARCHAR DEFAULT '',
    alignment_source   VARCHAR DEFAULT '',
    source_refs        VARCHAR DEFAULT '[]',
    skg_version        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ac_skg_context_profiles (
    profile_id         VARCHAR PRIMARY KEY,
    context_id         VARCHAR NOT NULL,
    context_label      VARCHAR,
    profile_json       VARCHAR NOT NULL,
    n_source_articles  INTEGER DEFAULT 0,
    n_external_sources INTEGER DEFAULT 0,
    skg_version        INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ac_skg_ctx_attr_article ON ac_skg_context_attributes(openalex_id);
CREATE INDEX IF NOT EXISTS idx_ac_skg_ctx_attr_name ON ac_skg_context_attributes(canonical_name);
CREATE INDEX IF NOT EXISTS idx_ac_skg_mod_edges_cause ON ac_skg_moderation_edges(base_cause);
CREATE INDEX IF NOT EXISTS idx_ac_skg_mod_edges_effect ON ac_skg_moderation_edges(base_effect);
CREATE INDEX IF NOT EXISTS idx_ac_skg_mod_edges_moderator ON ac_skg_moderation_edges(moderator);
CREATE INDEX IF NOT EXISTS idx_ac_skg_ctx_profiles_context ON ac_skg_context_profiles(context_id);

CREATE TABLE IF NOT EXISTS ac_skg_transport_scores (
    transport_id            VARCHAR PRIMARY KEY,
    edge_id                 VARCHAR NOT NULL,
    target_context_id       VARCHAR NOT NULL,
    base_confidence         DOUBLE NOT NULL,
    generic_penalty         DOUBLE DEFAULT 0.0,
    context_match_reward    DOUBLE DEFAULT 0.0,
    transport_confidence    DOUBLE NOT NULL,
    match_mode              VARCHAR DEFAULT '',
    matched_moderators_json VARCHAR DEFAULT '[]',
    skg_version             INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ac_skg_transport_edge ON ac_skg_transport_scores(edge_id);
CREATE INDEX IF NOT EXISTS idx_ac_skg_transport_target ON ac_skg_transport_scores(target_context_id);
"""


EVIDENCE_WEIGHTS: dict[str, float] = {
    EvidenceStrength.RCT.value: 1.0,
    EvidenceStrength.META_ANALYSIS.value: 0.95,
    EvidenceStrength.QUASI_NATURAL.value: 0.7,
    EvidenceStrength.QUASI_NATURAL_EVENT.value: 0.60,
    EvidenceStrength.PANEL_FE.value: 0.50,
    EvidenceStrength.STRUCTURAL.value: 0.45,
    EvidenceStrength.OBSERVATIONAL.value: 0.30,
    EvidenceStrength.CROSS_SECTIONAL.value: 0.20,
    EvidenceStrength.THEORETICAL.value: 0.15,
    EvidenceStrength.UNKNOWN.value: 0.15,
}


def aggregate_edge_confidence(articles: Iterable[tuple[str, float]]) -> float:
    """Aggregate edge confidence so one strong RCT dominates many weak studies."""
    rows = list(articles)
    if not rows:
        return 0.0

    quality_score = max(
        EVIDENCE_WEIGHTS.get(str(strength), EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value])
        * max(0.0, min(1.0, float(extraction_confidence)))
        for strength, extraction_confidence in rows
    )

    replication_bonus = min(0.3, 0.1 * math.log2(max(1, len(rows))))
    return min(1.0, quality_score + replication_bonus)


def ensure_skg_schema(con: duckdb.DuckDBPyConnection) -> None:
    for stmt in SKG_DDL.strip().split(";"):
        sql = stmt.strip()
        if sql:
            con.execute(sql)


def next_skg_version(con: duckdb.DuckDBPyConnection, *, description: str = "") -> int:
    ensure_skg_schema(con)
    row = con.execute("SELECT COALESCE(MAX(version_id), 0) + 1 FROM ac_skg_versions").fetchone()
    version_id = int(row[0]) if row else 1
    con.execute(
        """
        INSERT INTO ac_skg_versions(version_id, created_ts, n_articles, n_edges, n_variables, description)
        VALUES (?, ?, 0, 0, 0, ?)
        """,
        [version_id, datetime.now(UTC).isoformat(), description],
    )
    return version_id


def finalize_skg_version(
    con: duckdb.DuckDBPyConnection,
    *,
    version_id: int,
    n_articles: int,
    n_edges: int,
    n_variables: int,
) -> None:
    ensure_skg_schema(con)
    con.execute(
        """
        UPDATE ac_skg_versions
        SET n_articles = ?, n_edges = ?, n_variables = ?
        WHERE version_id = ?
        """,
        [int(n_articles), int(n_edges), int(n_variables), int(version_id)],
    )


def hash_edge_id(src: str, dst: str, direction: str) -> str:
    import hashlib

    payload = f"{src}|{dst}|{direction}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_param_id(canonical_name: str, openalex_id: str) -> str:
    import hashlib

    payload = f"{canonical_name}|{openalex_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_context_attr_id(canonical_name: str, openalex_id: str, country_code: str) -> str:
    import hashlib

    payload = f"ctx_attr|{canonical_name}|{openalex_id}|{country_code}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_moderation_edge_id(base_cause: str, base_effect: str, moderator: str) -> str:
    import hashlib

    payload = f"mod_edge|{base_cause}|{base_effect}|{moderator}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_transport_score_id(edge_id: str, target_context_id: str) -> str:
    import hashlib

    payload = f"transport|{edge_id}|{target_context_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_context_profile_id(context_id: str, time_period: str) -> str:
    import hashlib

    payload = f"ctx_prof|{context_id}|{time_period}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def parent_canonical_name(canonical_name: str) -> str | None:
    if "." not in canonical_name:
        return None
    return canonical_name.rsplit(".", 1)[0]


def edge_strength_rank(strength: str) -> int:
    ranking = {
        EvidenceStrength.RCT.value: 8,
        EvidenceStrength.META_ANALYSIS.value: 7,
        EvidenceStrength.QUASI_NATURAL.value: 6,
        EvidenceStrength.QUASI_NATURAL_EVENT.value: 5,
        EvidenceStrength.PANEL_FE.value: 4,
        EvidenceStrength.STRUCTURAL.value: 3,
        EvidenceStrength.OBSERVATIONAL.value: 2,
        EvidenceStrength.CROSS_SECTIONAL.value: 1,
        EvidenceStrength.THEORETICAL.value: 1,
        EvidenceStrength.UNKNOWN.value: 0,
    }
    return ranking.get(strength, 0)


def strongest_strength(values: Iterable[str]) -> str:
    best = EvidenceStrength.UNKNOWN.value
    best_rank = -1
    for value in values:
        rank = edge_strength_rank(str(value))
        if rank > best_rank:
            best_rank = rank
            best = str(value)
    return best


def normalize_strength(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in EVIDENCE_WEIGHTS:
        return text
    if text == "rct":
        return EvidenceStrength.RCT.value
    if text in {"meta", "meta-analysis", "metaanalysis"}:
        return EvidenceStrength.META_ANALYSIS.value
    if text in {"quasi_natural_event", "event_study", "quasi_experimental_other"}:
        return EvidenceStrength.QUASI_NATURAL_EVENT.value
    if text in {"panel_fe", "system_gmm", "gmm"}:
        return EvidenceStrength.PANEL_FE.value
    if text in {"structural", "structural_model", "time_series_cointegration"}:
        return EvidenceStrength.STRUCTURAL.value
    if text in {"cross_sectional", "ols_cross_sectional"}:
        return EvidenceStrength.CROSS_SECTIONAL.value
    if text in {"observational", "ols"}:
        return EvidenceStrength.OBSERVATIONAL.value
    return EvidenceStrength.UNKNOWN.value


__all__ = [
    "SKG_DDL",
    "EVIDENCE_WEIGHTS",
    "aggregate_edge_confidence",
    "ensure_skg_schema",
    "next_skg_version",
    "finalize_skg_version",
    "hash_edge_id",
    "hash_param_id",
    "hash_context_attr_id",
    "hash_moderation_edge_id",
    "hash_transport_score_id",
    "hash_context_profile_id",
    "parent_canonical_name",
    "strongest_strength",
    "normalize_strength",
]
