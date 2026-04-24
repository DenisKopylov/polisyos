"""Stage: load merged academic records into DuckDB and build indexes."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import duckdb

from polisyos.academic.batch.claim_ids import stable_claim_id
from polisyos.academic.knowledge.canonical_resolver import CanonicalVariableResolver
from polisyos.academic.knowledge.skg_store import (
    aggregate_edge_confidence,
    ensure_skg_schema,
    finalize_skg_version,
    hash_context_attr_id,
    hash_edge_id,
    hash_moderation_edge_id,
    hash_param_id,
    next_skg_version,
    normalize_strength,
    parent_canonical_name,
    strongest_strength,
)
from polisyos.academic.knowledge.types import WorkRecord
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.common.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from polisyos.academic.batch.config import AcademicBatchConfig

logger = get_logger(__name__)

_DESIGN_TIER_BY_FAMILY: dict[str, int | None] = {
    "rct": 1,
    "iv": 1,
    "did": 1,
    "rdd": 1,
    "synthetic_control": 1,
    "meta_analysis": 1,
    "event_study": 2,
    "quasi_experimental_other": 2,
    "quasi_experimental_did": 2,
    "quasi_experimental_rdd": 2,
    "panel_fe": 3,
    "structural_model": 3,
    "time_series_cointegration": 3,
    "ols": 4,
    "ols_cross_sectional": 4,
    "review": None,
    "review_meta_analysis": 1,
    "review_narrative": None,
    "theoretical": None,
    "unclear": None,
}

_DDL = """
CREATE TABLE IF NOT EXISTS ac_works (
    id              VARCHAR PRIMARY KEY,
    title           VARCHAR NOT NULL,
    doi             VARCHAR,
    abstract        VARCHAR,
    year            INTEGER,
    publication_date VARCHAR,
    language        VARCHAR,
    work_type       VARCHAR,
    is_retracted    BOOLEAN DEFAULT FALSE,
    cited_by_count  INTEGER DEFAULT 0,
    fwci            DOUBLE,
    citation_percentile DOUBLE,
    citation_top_1  BOOLEAN DEFAULT FALSE,
    citation_top_10 BOOLEAN DEFAULT FALSE,
    journal         VARCHAR,
    source_id       VARCHAR,
    is_oa           BOOLEAN DEFAULT FALSE,
    has_fulltext    BOOLEAN DEFAULT FALSE,
    full_text_url   VARCHAR,
    trust_score     FLOAT DEFAULT 0.0,
    study_design    VARCHAR
);

CREATE TABLE IF NOT EXISTS ac_work_concepts (
    work_id         VARCHAR NOT NULL,
    topic_id        VARCHAR,
    concept         VARCHAR NOT NULL,
    level           INTEGER,
    score           FLOAT,
    PRIMARY KEY (work_id, topic_id, concept)
);

CREATE TABLE IF NOT EXISTS ac_parameter_estimates (
    id              VARCHAR PRIMARY KEY,
    work_id         VARCHAR NOT NULL,
    variable_name   VARCHAR,
    estimate        DOUBLE NOT NULL,
    ci_low          DOUBLE,
    ci_high         DOUBLE,
    std_error       DOUBLE,
    unit            VARCHAR,
    domain          VARCHAR,
    study_design    VARCHAR,
    sample_size     BIGINT,
    country         VARCHAR,
    period_start    INTEGER,
    period_end      INTEGER,
    trust_score     FLOAT DEFAULT 0.0,
    raw_context     VARCHAR
);

CREATE TABLE IF NOT EXISTS ac_causal_claims_raw (
    id                        VARCHAR PRIMARY KEY,
    work_id                   VARCHAR NOT NULL,
    cause                     VARCHAR NOT NULL,
    effect                    VARCHAR NOT NULL,
    direction                 VARCHAR,
    strength                  VARCHAR,
    claim_text                VARCHAR,
    claim_explicitness        VARCHAR,
    design_family_hint        VARCHAR,
    source_basis              VARCHAR,
    claim_extraction_confidence FLOAT DEFAULT 0.0,
    strong_design_evidence    BOOLEAN DEFAULT FALSE,
    design_quality_tier       INTEGER,
    publish_to_graph          BOOLEAN DEFAULT FALSE,
    publish_blockers          VARCHAR DEFAULT '',
    span_contamination_detected BOOLEAN DEFAULT FALSE,
    mechanism                 VARCHAR,
    domain                    VARCHAR,
    trust_score               FLOAT DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ac_claim_adjudications (
    claim_id                   VARCHAR PRIMARY KEY,
    work_id                    VARCHAR NOT NULL,
    cause                      VARCHAR NOT NULL,
    effect                     VARCHAR NOT NULL,
    claim_type                 VARCHAR,
    design_family              VARCHAR,
    causal_credibility         VARCHAR,
    risk_of_bias               VARCHAR,
    support_status             VARCHAR,
    source_basis               VARCHAR,
    paper_asserts_score        FLOAT DEFAULT 0.0,
    claim_validity_score       FLOAT DEFAULT 0.0,
    adjudication_confidence    FLOAT DEFAULT 0.0,
    claim_extraction_confidence FLOAT DEFAULT 0.0,
    publishable_edge           BOOLEAN DEFAULT FALSE,
    strong_design_evidence     BOOLEAN DEFAULT FALSE,
    design_quality_tier        INTEGER,
    publish_blockers           VARCHAR DEFAULT '',
    consensus_passes           INTEGER DEFAULT 1,
    consensus_stability        FLOAT DEFAULT 1.0,
    claim_type_confidence      FLOAT,
    design_family_confidence   FLOAT,
    direction_confidence       FLOAT,
    intra_paper_contradiction  BOOLEAN DEFAULT FALSE,
    adjudication_notes         VARCHAR
);

CREATE TABLE IF NOT EXISTS ac_causal_claims (
    id              VARCHAR PRIMARY KEY,
    work_id         VARCHAR NOT NULL,
    cause           VARCHAR NOT NULL,
    effect          VARCHAR NOT NULL,
    direction       VARCHAR,
    strength        VARCHAR,
    design_family_hint VARCHAR,
    claim_extraction_confidence FLOAT DEFAULT 0.0,
    strong_design_evidence BOOLEAN DEFAULT FALSE,
    design_quality_tier INTEGER,
    publish_blockers VARCHAR DEFAULT '',
    candidate_layer  VARCHAR DEFAULT 'candidate',
    mechanism       VARCHAR,
    domain          VARCHAR,
    trust_score     FLOAT DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ac_runs (
    run_id          VARCHAR PRIMARY KEY,
    pass_name       VARCHAR,
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    config_json     VARCHAR,
    status          VARCHAR
);

CREATE TABLE IF NOT EXISTS ac_topics (
    topic_id          VARCHAR PRIMARY KEY,
    display_name      VARCHAR,
    policy_block      VARCHAR,
    policy_subblock   VARCHAR,
    source_file       VARCHAR,
    works_count       BIGINT,
    cited_by_count    BIGINT,
    score_core        INTEGER,
    score_domain      INTEGER,
    score_context     INTEGER
);

CREATE TABLE IF NOT EXISTS ac_topic_selections (
    run_id            VARCHAR NOT NULL,
    topic_id          VARCHAR NOT NULL,
    work_id           VARCHAR NOT NULL,
    rank              INTEGER,
    selection_score   DOUBLE,
    batch_origin      VARCHAR,
    selected_at       TIMESTAMP,
    PRIMARY KEY (run_id, topic_id, work_id)
);

CREATE TABLE IF NOT EXISTS ac_article_extractions (
    extraction_id      VARCHAR PRIMARY KEY,
    run_id             VARCHAR NOT NULL,
    work_id            VARCHAR NOT NULL,
    extraction_mode    VARCHAR,
    extraction_json    VARCHAR NOT NULL,
    context_json       VARCHAR,
    confidence         FLOAT,
    token_prompt       INTEGER DEFAULT 0,
    token_completion   INTEGER DEFAULT 0,
    cost_usd           DOUBLE DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ac_boundary_conditions (
    boundary_id        VARCHAR PRIMARY KEY,
    work_id            VARCHAR NOT NULL,
    variable           VARCHAR,
    operator           VARCHAR,
    threshold_value    VARCHAR,
    scope_text         VARCHAR,
    confidence         FLOAT DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS ac_ingest_errors (
    error_id           VARCHAR PRIMARY KEY,
    run_id             VARCHAR,
    stage              VARCHAR,
    topic_id           VARCHAR,
    work_id            VARCHAR,
    error_code         VARCHAR,
    error_message      VARCHAR,
    payload_ref        VARCHAR,
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_ac_works_year ON ac_works(year);
CREATE INDEX IF NOT EXISTS idx_ac_works_trust ON ac_works(trust_score);
CREATE INDEX IF NOT EXISTS idx_ac_concepts_work ON ac_work_concepts(work_id);
CREATE INDEX IF NOT EXISTS idx_ac_concepts_topic_id ON ac_work_concepts(topic_id);
CREATE INDEX IF NOT EXISTS idx_ac_concepts_concept ON ac_work_concepts(concept);
CREATE INDEX IF NOT EXISTS idx_ac_estimates_work ON ac_parameter_estimates(work_id);
CREATE INDEX IF NOT EXISTS idx_ac_estimates_var ON ac_parameter_estimates(variable_name);
CREATE INDEX IF NOT EXISTS idx_ac_estimates_domain ON ac_parameter_estimates(domain);
CREATE INDEX IF NOT EXISTS idx_ac_claims_raw_work ON ac_causal_claims_raw(work_id);
CREATE INDEX IF NOT EXISTS idx_ac_claims_raw_cause ON ac_causal_claims_raw(cause);
CREATE INDEX IF NOT EXISTS idx_ac_claims_raw_effect ON ac_causal_claims_raw(effect);
CREATE INDEX IF NOT EXISTS idx_ac_claim_adjudications_work ON ac_claim_adjudications(work_id);
CREATE INDEX IF NOT EXISTS idx_ac_claim_adjudications_publishable ON ac_claim_adjudications(publishable_edge);
CREATE INDEX IF NOT EXISTS idx_ac_claims_work ON ac_causal_claims(work_id);
CREATE INDEX IF NOT EXISTS idx_ac_claims_cause ON ac_causal_claims(cause);
CREATE INDEX IF NOT EXISTS idx_ac_claims_effect ON ac_causal_claims(effect);
CREATE INDEX IF NOT EXISTS idx_topic_sel_topic_rank ON ac_topic_selections(topic_id, rank);
CREATE INDEX IF NOT EXISTS idx_topic_sel_work ON ac_topic_selections(work_id);
CREATE INDEX IF NOT EXISTS idx_article_extractions_work ON ac_article_extractions(work_id);
CREATE INDEX IF NOT EXISTS idx_article_extractions_mode ON ac_article_extractions(extraction_mode);
CREATE INDEX IF NOT EXISTS idx_boundary_work ON ac_boundary_conditions(work_id);
CREATE INDEX IF NOT EXISTS idx_runs_pass_status ON ac_runs(pass_name, status);
"""


def _stable_hash(*parts: str, size: int = 24) -> str:
    canon = "|".join(parts)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:size]


def _supporting_span_signature(
    *, supporting_span_ids: Iterable[str] | None, claim_text: str
) -> tuple[str, ...]:
    items = tuple(
        sorted({str(item).strip() for item in (supporting_span_ids or []) if str(item).strip()})
    )
    if items:
        return items
    text = str(claim_text or "").strip().lower()
    return (text[:64],) if text else ()


def _validate_json_column(value: object, *, expected_type: type, field_name: str) -> str:
    if isinstance(value, expected_type):
        return json.dumps(value, ensure_ascii=False)
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{field_name} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, expected_type):
        raise ValueError(
            f"{field_name} must encode {expected_type.__name__}, got {type(parsed).__name__}"
        )
    return json.dumps(parsed, ensure_ascii=False)


def _design_quality_tier_from_family(design_family: str | None) -> int | None:
    clean = str(design_family or "").strip().lower()
    return _DESIGN_TIER_BY_FAMILY.get(clean)


def _claim_id(record_id: str, claim: dict) -> str:
    explicit = str(claim.get("claim_id") or "").strip()
    if explicit:
        return explicit
    return stable_claim_id(
        work_id=record_id,
        cause=str(claim.get("cause") or ""),
        effect=str(claim.get("effect") or ""),
        claim_text=str(claim.get("claim_text") or ""),
        direction=str(claim.get("direction") or ""),
        supporting_span_ids=_supporting_span_signature(
            supporting_span_ids=claim.get("supporting_span_ids")
            if isinstance(claim.get("supporting_span_ids"), list)
            else [],
            claim_text=str(claim.get("claim_text") or ""),
        ),
    )


def _load_claim_adjudications(path: Path | None) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    if path is None or not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            claim_id = str(row.get("claim_id") or "")
            if claim_id:
                rows[claim_id] = row
    return rows


def _load_rows_grouped_by_openalex_id(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if path is None or not path.exists():
        return grouped
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            openalex_id = str(row.get("openalex_id") or "").strip()
            if openalex_id:
                grouped[openalex_id].append(row)
    return grouped


def _legacy_strength_from_adjudication(adjudication: dict) -> str:
    design = str(adjudication.get("design_family") or "").strip().lower()
    credibility = str(adjudication.get("causal_credibility") or "").strip().lower()
    if design == "rct":
        return "rct"
    if design in {"iv", "did", "rdd", "synthetic_control"}:
        return "quasi_natural"
    if design in {
        "event_study",
        "quasi_experimental_other",
        "quasi_experimental_did",
        "quasi_experimental_rdd",
    }:
        return "quasi_natural_event"
    if design == "meta_analysis":
        return "meta_analysis"
    if design in {"panel_fe", "system_gmm", "gmm"}:
        return "panel_fe"
    if design in {"structural_model", "time_series_cointegration"}:
        return "structural"
    if design == "ols":
        return "observational"
    if design == "ols_cross_sectional":
        return "cross_sectional"
    if credibility in {"strong", "moderate", "weak"}:
        return "theoretical" if credibility == "weak" else "observational"
    return "unknown"


@dataclass
class GraphStats:
    """Graph stats public type."""

    works: int = 0
    concepts: int = 0
    estimates: int = 0
    raw_claims: int = 0
    claim_adjudications: int = 0
    claims: int = 0
    runs: int = 0
    topics: int = 0
    topic_selections: int = 0
    article_extractions: int = 0
    boundary_conditions: int = 0
    ingest_errors: int = 0
    skg_articles: int = 0
    skg_variables: int = 0
    skg_edges: int = 0
    skg_edge_evidence: int = 0
    skg_family_edges: int = 0
    skg_parameters: int = 0
    skg_simulation_parameters: int = 0
    skg_context_attributes: int = 0
    skg_moderation_edges: int = 0
    skg_context_profiles: int = 0
    skg_transport_scores: int = 0
    skg_versions: int = 0
    json_validation_failures: int = 0


def _init_schema(con: duckdb.DuckDBPyConnection) -> None:
    # Recreate tables on each load to keep schema deterministic across versions.
    con.execute("DROP TABLE IF EXISTS ac_ingest_errors")
    con.execute("DROP TABLE IF EXISTS ac_boundary_conditions")
    con.execute("DROP TABLE IF EXISTS ac_article_extractions")
    con.execute("DROP TABLE IF EXISTS ac_topic_selections")
    con.execute("DROP TABLE IF EXISTS ac_topics")
    con.execute("DROP TABLE IF EXISTS ac_runs")
    con.execute("DROP TABLE IF EXISTS ac_causal_claims")
    con.execute("DROP TABLE IF EXISTS ac_claim_adjudications")
    con.execute("DROP TABLE IF EXISTS ac_causal_claims_raw")
    con.execute("DROP TABLE IF EXISTS ac_parameter_estimates")
    con.execute("DROP TABLE IF EXISTS ac_work_concepts")
    con.execute("DROP TABLE IF EXISTS ac_works")
    con.execute("DROP TABLE IF EXISTS ac_skg_context_profiles")
    con.execute("DROP TABLE IF EXISTS ac_skg_transport_scores")
    con.execute("DROP TABLE IF EXISTS ac_skg_moderation_edges")
    con.execute("DROP TABLE IF EXISTS ac_skg_context_attributes")
    con.execute("DROP TABLE IF EXISTS ac_skg_simulation_parameters")
    con.execute("DROP TABLE IF EXISTS ac_skg_parameters")
    con.execute("DROP TABLE IF EXISTS ac_skg_contested_edges")
    con.execute("DROP TABLE IF EXISTS ac_skg_family_edges")
    con.execute("DROP TABLE IF EXISTS ac_skg_edge_evidence")
    con.execute("DROP TABLE IF EXISTS ac_skg_edges")
    con.execute("DROP TABLE IF EXISTS ac_skg_variables")
    con.execute("DROP TABLE IF EXISTS ac_skg_articles")
    con.execute("DROP TABLE IF EXISTS ac_skg_versions")
    for stmt in _DDL.strip().split(";"):
        sql = stmt.strip()
        if sql:
            con.execute(sql)
    ensure_skg_schema(con)


def _truncate(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DELETE FROM ac_ingest_errors")
    con.execute("DELETE FROM ac_boundary_conditions")
    con.execute("DELETE FROM ac_article_extractions")
    con.execute("DELETE FROM ac_topic_selections")
    con.execute("DELETE FROM ac_topics")
    con.execute("DELETE FROM ac_runs")
    con.execute("DELETE FROM ac_causal_claims")
    con.execute("DELETE FROM ac_claim_adjudications")
    con.execute("DELETE FROM ac_causal_claims_raw")
    con.execute("DELETE FROM ac_parameter_estimates")
    con.execute("DELETE FROM ac_work_concepts")
    con.execute("DELETE FROM ac_works")
    con.execute("DELETE FROM ac_skg_context_attributes")
    con.execute("DELETE FROM ac_skg_moderation_edges")
    con.execute("DELETE FROM ac_skg_context_profiles")
    con.execute("DELETE FROM ac_skg_transport_scores")
    con.execute("DELETE FROM ac_skg_parameters")
    con.execute("DELETE FROM ac_skg_simulation_parameters")
    con.execute("DELETE FROM ac_skg_contested_edges")
    con.execute("DELETE FROM ac_skg_family_edges")
    con.execute("DELETE FROM ac_skg_edge_evidence")
    con.execute("DELETE FROM ac_skg_edges")
    con.execute("DELETE FROM ac_skg_variables")
    con.execute("DELETE FROM ac_skg_articles")
    con.execute("DELETE FROM ac_skg_versions")


def _flush_all(
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    work_batch: list[tuple],
    concept_batch: list[tuple],
    estimate_batch: list[tuple],
    raw_claim_batch: list[tuple],
    claim_adjudication_batch: list[tuple],
    claim_batch: list[tuple],
    topic_batch: list[tuple],
    topic_sel_batch: list[tuple],
    extraction_batch: list[tuple],
    boundary_batch: list[tuple],
    ingest_error_batch: list[tuple],
) -> None:
    if work_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_works "
            "("
            "id, title, doi, abstract, year, publication_date, language, work_type, is_retracted, "
            "cited_by_count, fwci, citation_percentile, citation_top_1, citation_top_10, "
            "journal, source_id, is_oa, has_fulltext, full_text_url, trust_score, study_design"
            ") "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            work_batch,
        )
        stats.works += len(work_batch)
        work_batch.clear()

    if concept_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_work_concepts "
            "(work_id, topic_id, concept, level, score) VALUES (?, ?, ?, ?, ?)",
            concept_batch,
        )
        stats.concepts += len(concept_batch)
        concept_batch.clear()

    if estimate_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_parameter_estimates "
            "(id, work_id, variable_name, estimate, ci_low, ci_high, "
            "std_error, unit, domain, study_design, sample_size, "
            "country, period_start, period_end, trust_score, raw_context) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            estimate_batch,
        )
        stats.estimates += len(estimate_batch)
        estimate_batch.clear()

    if raw_claim_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_causal_claims_raw "
            "("
            "id, work_id, cause, effect, direction, strength, claim_text, claim_explicitness, "
            "design_family_hint, source_basis, claim_extraction_confidence, strong_design_evidence, "
            "design_quality_tier, publish_to_graph, publish_blockers, span_contamination_detected, "
            "mechanism, domain, trust_score"
            ") "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            raw_claim_batch,
        )
        stats.raw_claims += len(raw_claim_batch)
        raw_claim_batch.clear()

    if claim_adjudication_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_claim_adjudications "
            "("
            "claim_id, work_id, cause, effect, claim_type, design_family, causal_credibility, "
            "risk_of_bias, support_status, source_basis, paper_asserts_score, claim_validity_score, "
            "adjudication_confidence, claim_extraction_confidence, publishable_edge, "
            "strong_design_evidence, design_quality_tier, publish_blockers, consensus_passes, "
            "consensus_stability, claim_type_confidence, design_family_confidence, "
            "direction_confidence, intra_paper_contradiction, adjudication_notes"
            ") "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            claim_adjudication_batch,
        )
        stats.claim_adjudications += len(claim_adjudication_batch)
        claim_adjudication_batch.clear()

    if claim_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_causal_claims "
            "("
            "id, work_id, cause, effect, direction, strength, design_family_hint, "
            "claim_extraction_confidence, strong_design_evidence, design_quality_tier, "
            "publish_blockers, candidate_layer, mechanism, domain, trust_score"
            ") "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            claim_batch,
        )
        stats.claims += len(claim_batch)
        claim_batch.clear()

    if topic_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_topics "
            "(topic_id, display_name, policy_block, policy_subblock, source_file, works_count, cited_by_count, score_core, score_domain, score_context) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            topic_batch,
        )
        stats.topics += len(topic_batch)
        topic_batch.clear()

    if topic_sel_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_topic_selections "
            "(run_id, topic_id, work_id, rank, selection_score, batch_origin, selected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            topic_sel_batch,
        )
        stats.topic_selections += len(topic_sel_batch)
        topic_sel_batch.clear()

    if extraction_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_article_extractions "
            "(extraction_id, run_id, work_id, extraction_mode, extraction_json, context_json, confidence, token_prompt, token_completion, cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            extraction_batch,
        )
        stats.article_extractions += len(extraction_batch)
        extraction_batch.clear()

    if boundary_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_boundary_conditions "
            "(boundary_id, work_id, variable, operator, threshold_value, scope_text, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            boundary_batch,
        )
        stats.boundary_conditions += len(boundary_batch)
        boundary_batch.clear()

    if ingest_error_batch:
        con.executemany(
            "INSERT OR REPLACE INTO ac_ingest_errors "
            "(error_id, run_id, stage, topic_id, work_id, error_code, error_message, payload_ref) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ingest_error_batch,
        )
        stats.ingest_errors += len(ingest_error_batch)
        ingest_error_batch.clear()


def _infer_edge_strength(claim: dict) -> str:
    design = str(claim.get("design_family_hint") or "").strip().lower()
    if design == "rct":
        return "rct"
    if design in {"iv", "did", "rdd", "synthetic_control"}:
        return "quasi_natural"
    if design in {
        "event_study",
        "quasi_experimental_other",
        "quasi_experimental_did",
        "quasi_experimental_rdd",
    }:
        return "quasi_natural_event"
    if design in {"panel_fe", "system_gmm", "gmm"}:
        return "panel_fe"
    if design in {"structural_model", "time_series_cointegration"}:
        return "structural"
    if design == "ols":
        return "observational"
    if design == "ols_cross_sectional":
        return "cross_sectional"
    if design in {"theoretical", "review", "review_narrative", "review_meta_analysis"}:
        return "theoretical"
    explicit = str(claim.get("evidence_strength") or "").strip().lower()
    if explicit:
        return normalize_strength(explicit)
    strength = str(claim.get("strength") or "").strip().lower()
    if strength in {"strong", "very_strong"}:
        return "quasi_natural"
    if strength in {"moderate"}:
        return "observational"
    if strength in {"weak"}:
        return "theoretical"
    return "unknown"


def _choose_moderation_representative(
    current: dict[str, object] | None, candidate: dict[str, object]
) -> dict[str, object]:
    if current is None:
        return candidate
    current_confidence = float(current.get("confidence") or 0.0)
    candidate_confidence = float(candidate.get("confidence") or 0.0)
    if candidate_confidence > current_confidence:
        return candidate
    if candidate_confidence < current_confidence:
        return current
    current_has_interaction = int(current.get("quantitative_interaction") is not None)
    candidate_has_interaction = int(candidate.get("quantitative_interaction") is not None)
    if candidate_has_interaction > current_has_interaction:
        return candidate
    return current


def _edge_quality_summary(payload: dict[str, object]) -> dict[str, object]:
    tiers = sorted(
        {
            int(tier)
            for tier in payload.get("design_tiers", [])
            if isinstance(tier, int) and tier > 0
        }
    )
    hints = sorted(
        {str(hint).strip() for hint in payload.get("design_family_hints", []) if str(hint).strip()}
    )
    blockers = sorted(
        {
            str(blocker).strip()
            for blocker in payload.get("publish_blockers", [])
            if str(blocker).strip()
        }
    )
    claim_confidences = [
        float(value)
        for value in payload.get("claim_confidences", [])
        if isinstance(value, (int, float))
    ]
    strong_flags = [bool(flag) for flag in payload.get("strong_design_flags", [])]
    claim_ids = sorted(
        {
            str(claim_id).strip()
            for claim_id in payload.get("claim_ids", [])
            if str(claim_id).strip()
        }
    )
    confidence_summary: dict[str, float | None]
    if claim_confidences:
        confidence_summary = {
            "min": round(min(claim_confidences), 6),
            "max": round(max(claim_confidences), 6),
            "mean": round(sum(claim_confidences) / len(claim_confidences), 6),
        }
    else:
        confidence_summary = {"min": None, "max": None, "mean": None}
    strong_count = sum(1 for flag in strong_flags if flag)
    return {
        "graph_layer": "candidate",
        "claim_ids": claim_ids,
        "design_quality_tiers": tiers,
        "design_family_hints": hints,
        "claim_extraction_confidence": confidence_summary,
        "publish_blockers": blockers,
        "strong_design_evidence": {
            "count": strong_count,
            "share_pct": round((strong_count / max(1, len(strong_flags))) * 100.0, 3)
            if strong_flags
            else 0.0,
            "all": bool(strong_flags) and all(strong_flags),
            "any": any(strong_flags),
        },
    }


def _materialize_skg(
    *,
    con: duckdb.DuckDBPyConnection,
    stats: GraphStats,
    skg_version_id: int,
    skg_articles_batch: list[tuple],
    variable_mentions: dict[str, int],
    variable_display: dict[str, str],
    skg_parameter_batch: list[tuple],
    edge_accumulator: dict[tuple[str, str, str], dict[str, object]],
    edge_evidence_batch: list[tuple],
    simulation_parameter_batch: list[tuple],
    context_attr_batch: list[tuple],
    moderation_edge_batch: list[tuple],
) -> None:
    if skg_articles_batch:
        con.executemany(
            """
            INSERT OR REPLACE INTO ac_skg_articles(
                openalex_id, doi, title, year, cited_by_count,
                extraction_json, context_json, retracted, skg_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            skg_articles_batch,
        )
        stats.skg_articles = len(skg_articles_batch)

    resolver = CanonicalVariableResolver.from_connection(con)
    variable_rows: list[tuple] = []
    for canonical_name, mention_count in variable_mentions.items():
        resolution = resolver.resolve(canonical_name)
        resolver.persist_resolution(con, resolution)
        approved_canonical_name = (
            str(resolution.canonical_name or "").strip() if resolution.approved else None
        )
        variable_rows.append(
            (
                canonical_name,
                canonical_name,
                variable_display.get(canonical_name, canonical_name),
                parent_canonical_name(canonical_name),
                approved_canonical_name,
                parent_canonical_name(approved_canonical_name) if approved_canonical_name else None,
                bool(approved_canonical_name),
                str(resolution.method or ""),
                float(resolution.confidence or 0.0),
                int(mention_count),
            )
        )
    if variable_rows:
        con.executemany(
            """
            INSERT OR REPLACE INTO ac_skg_variables(
                canonical_name,
                normalized_name,
                display_name,
                parent_name,
                approved_canonical_name,
                approved_parent_name,
                is_approved_canonical,
                resolution_method,
                resolution_confidence,
                mention_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            variable_rows,
        )
        stats.skg_variables = len(variable_rows)

    if skg_parameter_batch:
        validated_parameter_rows: list[tuple] = []
        for row in skg_parameter_batch:
            param_id, canonical_name, openalex_id, parameter_json, context_json = row
            try:
                validated_parameter_rows.append(
                    (
                        param_id,
                        canonical_name,
                        openalex_id,
                        _validate_json_column(
                            parameter_json, expected_type=dict, field_name="parameter_json"
                        ),
                        _validate_json_column(
                            context_json, expected_type=dict, field_name="context_json"
                        ),
                    )
                )
            except ValueError as exc:
                stats.json_validation_failures += 1
                logger.warning("Skipping malformed ac_skg_parameters row {}: {}", param_id, exc)
        con.executemany(
            """
            INSERT OR REPLACE INTO ac_skg_parameters(
                param_id, canonical_name, openalex_id, parameter_json, context_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            validated_parameter_rows,
        )
        stats.skg_parameters = len(validated_parameter_rows)

    edge_rows: list[tuple] = []
    for (src, dst, direction), payload in edge_accumulator.items():
        article_refs = sorted(set(payload["article_refs"]))  # type: ignore[index]
        evidence_samples = payload["evidence_samples"]  # type: ignore[index]
        scope_conditions = sorted(set(payload["scope_conditions"]))  # type: ignore[index]
        effect_sizes = payload["effect_sizes"]  # type: ignore[index]

        confidence = aggregate_edge_confidence(evidence_samples)  # type: ignore[arg-type]
        best_strength = strongest_strength([str(sample[0]) for sample in evidence_samples])  # type: ignore[misc]
        effect_size_values = [float(v) for v in effect_sizes if isinstance(v, (int, float))]
        meta_effect_size = (
            float(sum(effect_size_values) / len(effect_size_values)) if effect_size_values else None
        )

        try:
            edge_rows.append(
                (
                    hash_edge_id(src, dst, direction),
                    src,
                    dst,
                    direction,
                    len(article_refs),
                    _validate_json_column(
                        article_refs, expected_type=list, field_name="article_refs"
                    ),
                    best_strength,
                    confidence,
                    _validate_json_column(
                        scope_conditions, expected_type=list, field_name="scope_conditions"
                    ),
                    meta_effect_size,
                    "candidate",
                    _validate_json_column(
                        _edge_quality_summary(payload),
                        expected_type=dict,
                        field_name="quality_signals_json",
                    ),
                )
            )
        except ValueError as exc:
            stats.json_validation_failures += 1
            logger.warning(
                "Skipping malformed ac_skg_edges row {} -> {} [{}]: {}", src, dst, direction, exc
            )

    if edge_rows:
        con.executemany(
            """
            INSERT OR REPLACE INTO ac_skg_edges(
                edge_id, src, dst, direction, n_articles, article_refs,
                evidence_strength, confidence, scope_conditions, meta_effect_size,
                candidate_layer, quality_signals_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            edge_rows,
        )
        stats.skg_edges = len(edge_rows)

    if edge_evidence_batch:
        con.executemany(
            """
            INSERT OR REPLACE INTO ac_skg_edge_evidence(
                edge_id, claim_id, openalex_id, src, dst, direction,
                evidence_strength, confidence, design_family, design_quality_tier, skg_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            edge_evidence_batch,
        )
        stats.skg_edge_evidence = len(edge_evidence_batch)

    if simulation_parameter_batch:
        validated_simulation_rows: list[tuple] = []
        for row in simulation_parameter_batch:
            (
                numeric_id,
                openalex_id,
                canonical_name,
                estimate_type,
                point_estimate,
                estimate_sign,
                unit,
                evidence_strength,
                confidence_interval_json,
                std_error,
                linked_claim_ids_json,
                linked_edges_json,
                context_json,
                source_layer,
                uncertainty_source,
                quality_flags_json,
            ) = row
            try:
                validated_simulation_rows.append(
                    (
                        numeric_id,
                        openalex_id,
                        canonical_name,
                        estimate_type,
                        point_estimate,
                        estimate_sign,
                        unit,
                        evidence_strength,
                        _validate_json_column(
                            confidence_interval_json,
                            expected_type=list,
                            field_name="confidence_interval_json",
                        ),
                        std_error,
                        _validate_json_column(
                            linked_claim_ids_json,
                            expected_type=list,
                            field_name="linked_claim_ids_json",
                        ),
                        _validate_json_column(
                            linked_edges_json, expected_type=list, field_name="linked_edges_json"
                        ),
                        _validate_json_column(
                            context_json, expected_type=dict, field_name="context_json"
                        ),
                        source_layer,
                        uncertainty_source,
                        _validate_json_column(
                            quality_flags_json, expected_type=list, field_name="quality_flags_json"
                        ),
                    )
                )
            except ValueError as exc:
                stats.json_validation_failures += 1
                logger.warning(
                    "Skipping malformed ac_skg_simulation_parameters row {}: {}", numeric_id, exc
                )
        con.executemany(
            """
            INSERT OR REPLACE INTO ac_skg_simulation_parameters(
                numeric_id, openalex_id, canonical_name, estimate_type, point_estimate,
                estimate_sign, unit, evidence_strength, confidence_interval_json,
                std_error, linked_claim_ids_json, linked_edges_json, context_json,
                source_layer, uncertainty_source, quality_flags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            validated_simulation_rows,
        )
        stats.skg_simulation_parameters = len(validated_simulation_rows)

    if context_attr_batch:
        con.executemany(
            """
            INSERT OR REPLACE INTO ac_skg_context_attributes(
                attr_id, openalex_id, canonical_name, attribute_value,
                value_qualitative, unit, country_code, time_period,
                measurement_method, confidence, evidence_span_count, skg_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            context_attr_batch,
        )
        stats.skg_context_attributes = len(context_attr_batch)

    if moderation_edge_batch:
        con.executemany(
            """
            INSERT OR REPLACE INTO ac_skg_moderation_edges(
                moderation_id, base_cause, base_effect, moderator, base_claim_id,
                direction_of_mod, interaction_coeff, interaction_pvalue,
                evidence_count, confidence, match_quality, alignment_source, source_refs, skg_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            moderation_edge_batch,
        )
        stats.skg_moderation_edges = len(moderation_edge_batch)

    finalize_skg_version(
        con,
        version_id=skg_version_id,
        n_articles=stats.skg_articles,
        n_edges=stats.skg_edges,
        n_variables=stats.skg_variables,
    )
    stats.skg_versions = 1


def load_graph(
    *,
    records: Iterable[WorkRecord],
    db_path: Path,
    insert_batch_size: int = 10_000,
    run_id: str = "",
    pass_name: str = "",
    config_json: str = "",
    topics_catalog_path: Path | None = None,
    ingest_errors_path: Path | None = None,
    claim_adjudications_path: Path | None = None,
    simulation_ready_numeric_path: Path | None = None,
) -> GraphStats:
    """Load records into DuckDB tables (without creating indexes)."""
    stats = GraphStats()
    con = duckdb.connect(str(db_path))

    try:
        _init_schema(con)
        _truncate(con)
        skg_version_id = next_skg_version(
            con,
            description=f"run_id={run_id or 'adhoc'}; pass={pass_name or 'unknown'}",
        )

        # Register run row.
        if run_id:
            con.execute(
                "INSERT OR REPLACE INTO ac_runs (run_id, pass_name, started_at, finished_at, config_json, status) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    run_id,
                    pass_name,
                    datetime.now(UTC).isoformat(),
                    datetime.now(UTC).isoformat(),
                    config_json,
                    "ok",
                ],
            )
            stats.runs = 1

        # Preload topics catalog when present.
        topic_batch: list[tuple] = []
        if topics_catalog_path and topics_catalog_path.exists():
            with open(topics_catalog_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    topic_batch.append(
                        (
                            str(row.get("topic_id") or ""),
                            str(row.get("display_name") or ""),
                            str(row.get("policy_block") or ""),
                            str(row.get("policy_subblock") or ""),
                            str(row.get("source_file") or ""),
                            int(row.get("works_count") or 0),
                            int(row.get("cited_by_count") or 0),
                            int(row.get("score_core") or 0),
                            int(row.get("score_domain") or 0),
                            int(row.get("score_context") or 0),
                        )
                    )

        claim_adjudications = _load_claim_adjudications(claim_adjudications_path)
        simulation_numeric_file_present = bool(
            simulation_ready_numeric_path is not None and simulation_ready_numeric_path.exists()
        )
        simulation_numeric_rows = _load_rows_grouped_by_openalex_id(simulation_ready_numeric_path)
        work_batch: list[tuple] = []
        concept_batch: list[tuple] = []
        estimate_batch: list[tuple] = []
        raw_claim_batch: list[tuple] = []
        claim_adjudication_batch: list[tuple] = []
        claim_batch: list[tuple] = []
        topic_sel_batch: list[tuple] = []
        extraction_batch: list[tuple] = []
        boundary_batch: list[tuple] = []
        ingest_error_batch: list[tuple] = []
        topic_seen: set[str] = {str(t[0]) for t in topic_batch if t and t[0]}
        skg_articles_batch: list[tuple] = []
        skg_parameter_batch: list[tuple] = []
        simulation_parameter_batch: list[tuple] = []
        variable_mentions: defaultdict[str, int] = defaultdict(int)
        variable_display: dict[str, str] = {}
        edge_accumulator: dict[tuple[str, str, str], dict[str, object]] = {}
        edge_evidence_batch: list[tuple] = []
        context_attr_batch: list[tuple] = []
        moderation_edge_accumulator: dict[tuple[str, str, str], dict[str, object]] = {}

        for record in records:
            work_batch.append(
                (
                    record.id,
                    record.title,
                    record.doi,
                    record.abstract,
                    record.year,
                    record.publication_date,
                    record.language,
                    record.work_type,
                    record.is_retracted,
                    record.cited_by_count,
                    record.fwci,
                    record.citation_normalized_percentile,
                    record.citation_is_top_1_percent,
                    record.citation_is_top_10_percent,
                    record.journal,
                    record.source_id,
                    record.is_oa,
                    record.has_fulltext,
                    record.full_text_url,
                    record.trust_score,
                    record.study_design,
                )
            )

            for concept_data in record.concepts:
                if isinstance(concept_data, dict):
                    topic_id = str(concept_data.get("id") or "")
                    if topic_id and "/" in topic_id:
                        topic_id = topic_id.rsplit("/", 1)[-1]
                    concept_batch.append(
                        (
                            record.id,
                            topic_id,
                            concept_data.get("display_name", ""),
                            concept_data.get("level"),
                            concept_data.get("score"),
                        )
                    )

            for i, est in enumerate(record.estimates):
                eid = _stable_hash(record.id, str(i), str(est.value), est.variable_hint)
                estimate_batch.append(
                    (
                        eid,
                        record.id,
                        est.variable_hint,
                        est.value,
                        est.ci_low,
                        est.ci_high,
                        est.std_error,
                        est.unit,
                        "",
                        record.study_design,
                        int(record.metadata.get("sample_size"))
                        if record.metadata.get("sample_size")
                        else None,
                        str(record.context_profile.get("context_id") or ""),
                        None,
                        None,
                        record.trust_score,
                        est.context_snippet[:500],
                    )
                )

            for i, claim in enumerate(record.causal_claims):
                if isinstance(claim, dict):
                    if bool(record.is_retracted):
                        continue
                    cid = _claim_id(record.id, claim)
                    design_tier = (
                        int(claim.get("design_quality_tier"))
                        if claim.get("design_quality_tier") is not None
                        else None
                    )
                    raw_claim_batch.append(
                        (
                            cid,
                            record.id,
                            claim.get("cause", ""),
                            claim.get("effect", ""),
                            claim.get("direction", ""),
                            claim.get("strength", ""),
                            claim.get("claim_text", ""),
                            claim.get("claim_explicitness", ""),
                            claim.get("design_family_hint", ""),
                            claim.get("source_basis", ""),
                            float(
                                claim.get("claim_extraction_confidence")
                                or record.extraction_confidence
                                or 0.0
                            ),
                            bool(claim.get("strong_design_evidence") or False),
                            design_tier,
                            bool(claim.get("publish_to_graph") or False),
                            "; ".join(
                                str(v)
                                for v in (claim.get("publish_blockers") or [])
                                if str(v).strip()
                            ),
                            bool(claim.get("span_contamination_detected") or False),
                            claim.get("mechanism", ""),
                            claim.get("domain", ""),
                            record.trust_score,
                        )
                    )
                    adjudication = claim_adjudications.get(cid)
                    publishable = bool(claim.get("publish_to_graph") or False)
                    published_strength = str(claim.get("strength") or "")
                    published_trust = float(record.trust_score)
                    if adjudication:
                        adjudicated_design_family = str(
                            adjudication.get("design_family") or ""
                        ).strip()
                        recalculated_tier = _design_quality_tier_from_family(
                            adjudicated_design_family
                        )
                        if recalculated_tier is not None:
                            design_tier = recalculated_tier
                        claim_adjudication_batch.append(
                            (
                                cid,
                                record.id,
                                claim.get("cause", ""),
                                claim.get("effect", ""),
                                str(adjudication.get("claim_type") or ""),
                                str(adjudication.get("design_family") or ""),
                                str(adjudication.get("causal_credibility") or ""),
                                str(adjudication.get("risk_of_bias") or ""),
                                str(adjudication.get("support_status") or ""),
                                str(adjudication.get("source_basis") or ""),
                                float(adjudication.get("paper_asserts_causality_score") or 0.0),
                                float(adjudication.get("claim_validity_score") or 0.0),
                                float(adjudication.get("adjudication_confidence") or 0.0),
                                float(
                                    claim.get("claim_extraction_confidence")
                                    or record.extraction_confidence
                                    or 0.0
                                ),
                                bool(adjudication.get("publishable_edge") or False),
                                bool(claim.get("strong_design_evidence") or False),
                                design_tier,
                                "; ".join(
                                    str(v)
                                    for v in (claim.get("publish_blockers") or [])
                                    if str(v).strip()
                                ),
                                int(adjudication.get("consensus_passes") or 1),
                                float(adjudication.get("consensus_stability") or 0.0),
                                float(adjudication.get("claim_type_confidence"))
                                if adjudication.get("claim_type_confidence") is not None
                                else None,
                                float(adjudication.get("design_family_confidence"))
                                if adjudication.get("design_family_confidence") is not None
                                else None,
                                float(adjudication.get("direction_confidence"))
                                if adjudication.get("direction_confidence") is not None
                                else None,
                                bool(adjudication.get("intra_paper_contradiction") or False),
                                str(adjudication.get("adjudication_notes") or ""),
                            )
                        )
                        publishable = bool(adjudication.get("publishable_edge") or False)
                        published_strength = _legacy_strength_from_adjudication(adjudication)
                        published_trust = float(
                            adjudication.get("claim_validity_score") or published_trust
                        )
                    elif any(
                        key in claim
                        for key in (
                            "claim_type",
                            "design_family_hint",
                            "strong_design_evidence",
                            "publish_to_graph",
                            "publish_blockers",
                        )
                    ):
                        claim_adjudication_batch.append(
                            (
                                cid,
                                record.id,
                                claim.get("cause", ""),
                                claim.get("effect", ""),
                                str(claim.get("claim_type") or ""),
                                str(claim.get("design_family_hint") or ""),
                                "strong"
                                if bool(claim.get("strong_design_evidence") or False)
                                else "weak",
                                "unclear",
                                "supported" if publishable else "insufficient_evidence",
                                str(claim.get("source_basis") or ""),
                                float(
                                    claim.get("claim_extraction_confidence")
                                    or record.extraction_confidence
                                    or 0.0
                                ),
                                float(
                                    claim.get("claim_extraction_confidence")
                                    or record.extraction_confidence
                                    or 0.0
                                ),
                                float(
                                    claim.get("claim_extraction_confidence")
                                    or record.extraction_confidence
                                    or 0.0
                                ),
                                float(
                                    claim.get("claim_extraction_confidence")
                                    or record.extraction_confidence
                                    or 0.0
                                ),
                                publishable,
                                bool(claim.get("strong_design_evidence") or False),
                                design_tier,
                                "; ".join(
                                    str(v)
                                    for v in (claim.get("publish_blockers") or [])
                                    if str(v).strip()
                                ),
                                1,
                                1.0,
                                None,
                                None,
                                1.0,
                                False,
                                "; ".join(
                                    str(v)
                                    for v in (claim.get("publish_blockers") or [])
                                    if str(v).strip()
                                ),
                            )
                        )

                    if publishable:
                        claim_batch.append(
                            (
                                cid,
                                record.id,
                                claim.get("cause", ""),
                                claim.get("effect", ""),
                                claim.get("direction", ""),
                                published_strength,
                                str(claim.get("design_family_hint") or ""),
                                float(
                                    claim.get("claim_extraction_confidence")
                                    or record.extraction_confidence
                                    or 0.0
                                ),
                                bool(claim.get("strong_design_evidence") or False),
                                design_tier,
                                "; ".join(
                                    str(v)
                                    for v in (claim.get("publish_blockers") or [])
                                    if str(v).strip()
                                ),
                                "candidate",
                                claim.get("mechanism", ""),
                                claim.get("domain", ""),
                                published_trust,
                            )
                        )

            for i, bnd in enumerate(record.boundary_conditions):
                if not isinstance(bnd, dict):
                    continue
                bid = _stable_hash(record.id, "boundary", str(i), str(bnd.get("scope_text", "")))
                boundary_batch.append(
                    (
                        bid,
                        record.id,
                        str(bnd.get("variable") or ""),
                        str(bnd.get("operator") or ""),
                        str(bnd.get("threshold_value") or ""),
                        str(bnd.get("scope_text") or ""),
                        float(bnd.get("confidence") or 0.0),
                    )
                )

            extraction_id = _stable_hash(record.id, record.extraction_mode, run_id)
            extraction_payload = {
                "estimates": [e.model_dump(mode="json") for e in record.estimates],
                "causal_claims": record.causal_claims,
                "boundary_conditions": record.boundary_conditions,
                "study_design": record.study_design,
                "method_signal_score": record.method_signal_score,
                "paper_kind": record.metadata.get("paper_kind"),
                "heterogeneity_results": record.metadata.get("heterogeneity_results", []),
                "external_validity_assessment": record.metadata.get(
                    "external_validity_assessment", ""
                ),
                "reconciliation_diagnostics": record.metadata.get("reconciliation_diagnostics", {}),
                "metadata": record.metadata,
                "context_attributes": record.metadata.get("context_attributes", []),
                "moderation_edges": record.metadata.get("moderation_edges", []),
            }
            extraction_batch.append(
                (
                    extraction_id,
                    run_id,
                    record.id,
                    record.extraction_mode,
                    json.dumps(extraction_payload, ensure_ascii=False),
                    json.dumps(record.context_profile, ensure_ascii=False),
                    float(record.extraction_confidence),
                    int(record.token_count_prompt),
                    int(record.token_count_completion),
                    float(record.extraction_cost_usd + record.screening_cost_usd),
                )
            )

            skg_articles_batch.append(
                (
                    record.id,
                    record.doi,
                    record.title,
                    record.year,
                    record.cited_by_count,
                    json.dumps(extraction_payload, ensure_ascii=False),
                    json.dumps(record.context_profile, ensure_ascii=False),
                    bool(record.is_retracted),
                    skg_version_id,
                )
            )

            if bool(record.is_retracted):
                continue

            for est in record.estimates:
                canonical = str(est.variable_hint or "").strip()
                if not canonical:
                    continue
                variable_mentions[canonical] += 1
                variable_display.setdefault(canonical, canonical)
                skg_parameter_batch.append(
                    (
                        hash_param_id(canonical, record.id),
                        canonical,
                        record.id,
                        json.dumps(est.model_dump(mode="json"), ensure_ascii=False),
                        json.dumps(record.context_profile, ensure_ascii=False),
                    )
                )

            numeric_rows_for_record = (
                simulation_numeric_rows.get(record.id)
                if simulation_numeric_file_present
                else (
                    simulation_numeric_rows.get(record.id)
                    or (record.metadata.get("simulation_ready_numeric_estimates") or [])
                )
            )
            for numeric in numeric_rows_for_record or []:
                if not isinstance(numeric, dict):
                    continue
                numeric_id = str(numeric.get("numeric_id") or "").strip()
                canonical = str(
                    numeric.get("canonical_name") or numeric.get("parameter_name") or ""
                ).strip()
                point_estimate = numeric.get("point_estimate")
                if not numeric_id or not canonical or not isinstance(point_estimate, (int, float)):
                    continue
                simulation_parameter_batch.append(
                    (
                        numeric_id,
                        record.id,
                        canonical,
                        str(numeric.get("estimate_type") or ""),
                        float(point_estimate),
                        str(numeric.get("estimate_sign") or ""),
                        str(numeric.get("unit") or ""),
                        str(numeric.get("evidence_strength") or ""),
                        json.dumps(numeric.get("confidence_interval") or [], ensure_ascii=False),
                        float(numeric["std_error"])
                        if numeric.get("std_error") is not None
                        else None,
                        json.dumps(numeric.get("linked_claim_ids") or [], ensure_ascii=False),
                        json.dumps(
                            numeric.get("linked_edge_ids")
                            or numeric.get("linked_edge_pairs")
                            or [],
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            numeric.get("source_context") or record.context_profile,
                            ensure_ascii=False,
                        ),
                        str(numeric.get("source_layer") or "simulation_ready"),
                        str(numeric.get("uncertainty_source") or ""),
                        json.dumps(numeric.get("quality_flags") or [], ensure_ascii=False),
                    )
                )

            for t in record.source_topics:
                if t.topic_id and t.topic_id not in topic_seen:
                    topic_seen.add(t.topic_id)
                    topic_batch.append(
                        (
                            t.topic_id,
                            t.topic_display_name,
                            t.policy_block,
                            t.policy_subblock,
                            t.source_file,
                            0,
                            0,
                            0,
                            0,
                            0,
                        )
                    )
                topic_sel_batch.append(
                    (
                        run_id,
                        t.topic_id,
                        record.id,
                        t.rank,
                        t.selection_score,
                        t.batch_origin,
                        t.selected_at or None,
                    )
                )

            claim_lookup: dict[str, tuple[str, str]] = {}
            for claim_raw in record.causal_claims or []:
                if not isinstance(claim_raw, dict):
                    continue
                claim_id = str(claim_raw.get("claim_id") or "").strip()
                cause = str(claim_raw.get("cause") or "").strip()
                effect = str(claim_raw.get("effect") or "").strip()
                if claim_id and cause and effect:
                    claim_lookup[claim_id] = (cause, effect)

            # Extract Track B/C data from extraction payload
            for ctx_attr_raw in extraction_payload.get("context_attributes") or []:
                if not isinstance(ctx_attr_raw, dict):
                    continue
                canonical_name = str(
                    ctx_attr_raw.get("canonical_name") or ctx_attr_raw.get("attribute_name") or ""
                ).strip()
                if not canonical_name:
                    continue
                for cc in ctx_attr_raw.get("country_codes") or [""]:
                    context_attr_batch.append(
                        (
                            hash_context_attr_id(canonical_name, record.id, str(cc)),
                            record.id,
                            canonical_name,
                            float(ctx_attr_raw["value"])
                            if ctx_attr_raw.get("value") is not None
                            else None,
                            str(ctx_attr_raw.get("value_qualitative") or "") or None,
                            str(ctx_attr_raw.get("unit") or "") or None,
                            str(cc) if cc else None,
                            str(ctx_attr_raw.get("time_period") or "") or None,
                            str(ctx_attr_raw.get("measurement_method") or "") or None,
                            float(ctx_attr_raw.get("confidence") or 0.5),
                            len(ctx_attr_raw.get("evidence_spans") or []),
                            skg_version_id,
                        )
                    )

            for mod_edge_raw in extraction_payload.get("moderation_edges") or []:
                if not isinstance(mod_edge_raw, dict):
                    continue
                base_claim_id = str(mod_edge_raw.get("base_claim_id") or "").strip()
                if base_claim_id and base_claim_id in claim_lookup:
                    base_cause, base_effect = claim_lookup[base_claim_id]
                else:
                    base_cause = str(mod_edge_raw.get("base_cause") or "").strip()
                    base_effect = str(mod_edge_raw.get("base_effect") or "").strip()
                moderator = str(mod_edge_raw.get("moderator") or "").strip()
                if not base_cause or not base_effect or not moderator:
                    continue
                key = (base_cause, base_effect, moderator)
                candidate = {
                    "base_claim_id": base_claim_id or None,
                    "direction_of_moderation": str(
                        mod_edge_raw.get("direction_of_moderation") or ""
                    )
                    or None,
                    "quantitative_interaction": (
                        float(mod_edge_raw["quantitative_interaction"])
                        if mod_edge_raw.get("quantitative_interaction") is not None
                        else None
                    ),
                    "interaction_pvalue": (
                        float(mod_edge_raw["interaction_pvalue"])
                        if mod_edge_raw.get("interaction_pvalue") is not None
                        else None
                    ),
                    "confidence": float(mod_edge_raw.get("confidence") or 0.5),
                    "match_quality": str(mod_edge_raw.get("match_quality") or ""),
                    "alignment_source": str(mod_edge_raw.get("alignment_source") or ""),
                }
                payload = moderation_edge_accumulator.get(key)
                representative = _choose_moderation_representative(
                    None if payload is None else payload.get("representative"),  # type: ignore[arg-type]
                    candidate,
                )
                if payload is None:
                    moderation_edge_accumulator[key] = {
                        "representative": representative,
                        "source_refs": {record.id},
                        "evidence_count": int(mod_edge_raw.get("evidence_count") or 1),
                        "confidence": float(candidate["confidence"]),
                    }
                    continue
                payload["representative"] = representative
                payload["source_refs"].add(record.id)  # type: ignore[union-attr]
                payload["evidence_count"] = int(payload.get("evidence_count") or 0) + int(
                    mod_edge_raw.get("evidence_count") or 1
                )
                payload["confidence"] = max(
                    float(payload.get("confidence") or 0.0), float(candidate["confidence"])
                )

            if len(work_batch) >= insert_batch_size:
                _flush_all(
                    con,
                    stats,
                    work_batch,
                    concept_batch,
                    estimate_batch,
                    raw_claim_batch,
                    claim_adjudication_batch,
                    claim_batch,
                    topic_batch,
                    topic_sel_batch,
                    extraction_batch,
                    boundary_batch,
                    ingest_error_batch,
                )

            for claim in record.causal_claims:
                if not isinstance(claim, dict):
                    continue
                if bool(record.is_retracted):
                    continue
                cid = _claim_id(record.id, claim)
                adjudication = claim_adjudications.get(cid)
                publishable = bool(claim.get("publish_to_graph") or False)
                if adjudication is not None:
                    publishable = bool(adjudication.get("publishable_edge") or False)
                if not publishable:
                    continue
                src = str(claim.get("cause") or "").strip()
                dst = str(claim.get("effect") or "").strip()
                if not src or not dst:
                    continue

                direction = str(claim.get("direction") or "mixed").strip().lower()
                key = (src, dst, direction)
                edge_id = hash_edge_id(src, dst, direction)
                if key not in edge_accumulator:
                    edge_accumulator[key] = {
                        "article_refs": [],
                        "evidence_samples": [],
                        "scope_conditions": [],
                        "effect_sizes": [],
                        "claim_ids": [],
                        "design_tiers": [],
                        "design_family_hints": [],
                        "claim_confidences": [],
                        "publish_blockers": [],
                        "strong_design_flags": [],
                    }
                payload = edge_accumulator[key]
                payload["article_refs"].append(record.id)  # type: ignore[index]
                confidence_value = (
                    float(adjudication.get("claim_validity_score") or record.extraction_confidence)
                    if adjudication is not None
                    else float(record.extraction_confidence)
                )
                sample_size = (
                    int(record.metadata.get("sample_size"))
                    if record.metadata.get("sample_size") not in (None, "")
                    else None
                )
                payload["evidence_samples"].append(  # type: ignore[index]
                    (
                        _legacy_strength_from_adjudication(adjudication)
                        if adjudication is not None
                        else _infer_edge_strength(claim),
                        confidence_value,
                        record.year,
                        sample_size,
                        str(claim.get("source_basis") or "fulltext"),
                        bool(record.is_retracted),
                        record.fwci,
                    )
                )
                payload["scope_conditions"].extend(claim.get("scope_conditions") or [])  # type: ignore[index]
                payload["effect_sizes"].append(claim.get("effect_size"))  # type: ignore[index]
                payload["claim_ids"].append(cid)  # type: ignore[index]
                if claim.get("design_quality_tier") is not None:
                    payload["design_tiers"].append(int(claim.get("design_quality_tier")))  # type: ignore[index]
                design_hint = str(claim.get("design_family_hint") or "").strip()
                if design_hint:
                    payload["design_family_hints"].append(design_hint)  # type: ignore[index]
                payload["claim_confidences"].append(
                    float(
                        claim.get("claim_extraction_confidence")
                        or record.extraction_confidence
                        or 0.0
                    )
                )  # type: ignore[index]
                payload["publish_blockers"].extend(claim.get("publish_blockers") or [])  # type: ignore[index]
                payload["strong_design_flags"].append(
                    bool(claim.get("strong_design_evidence") or False)
                )  # type: ignore[index]
                edge_evidence_batch.append(
                    (
                        edge_id,
                        cid,
                        record.id,
                        src,
                        dst,
                        direction,
                        (
                            _legacy_strength_from_adjudication(adjudication)
                            if adjudication is not None
                            else _infer_edge_strength(claim)
                        ),
                        confidence_value,
                        str(claim.get("design_family_hint") or ""),
                        int(claim.get("design_quality_tier"))
                        if claim.get("design_quality_tier") is not None
                        else None,
                        skg_version_id,
                    )
                )

                variable_mentions[src] += 1
                variable_mentions[dst] += 1
                variable_display.setdefault(src, src)
                variable_display.setdefault(dst, dst)

        # ingest errors (optional)
        if ingest_errors_path and ingest_errors_path.exists():
            with open(ingest_errors_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        continue
                    ingest_error_batch.append(
                        (
                            _stable_hash(
                                str(row.get("run_id") or run_id),
                                str(row.get("stage") or ""),
                                str(row.get("topic_id") or ""),
                                str(row.get("work_id") or ""),
                                str(row.get("error_code") or ""),
                            ),
                            str(row.get("run_id") or run_id),
                            str(row.get("stage") or ""),
                            str(row.get("topic_id") or ""),
                            str(row.get("work_id") or ""),
                            str(row.get("error_code") or ""),
                            str(row.get("error_message") or ""),
                            str(row.get("payload_ref") or ""),
                        )
                    )

        _flush_all(
            con,
            stats,
            work_batch,
            concept_batch,
            estimate_batch,
            raw_claim_batch,
            claim_adjudication_batch,
            claim_batch,
            topic_batch,
            topic_sel_batch,
            extraction_batch,
            boundary_batch,
            ingest_error_batch,
        )

        moderation_edge_batch = [
            (
                hash_moderation_edge_id(base_cause, base_effect, moderator),
                base_cause,
                base_effect,
                moderator,
                payload["representative"].get("base_claim_id"),  # type: ignore[index]
                payload["representative"].get("direction_of_moderation"),  # type: ignore[index]
                payload["representative"].get("quantitative_interaction"),  # type: ignore[index]
                payload["representative"].get("interaction_pvalue"),  # type: ignore[index]
                int(payload.get("evidence_count") or 1),
                float(payload.get("confidence") or 0.5),
                payload["representative"].get("match_quality"),  # type: ignore[index]
                payload["representative"].get("alignment_source"),  # type: ignore[index]
                json.dumps(sorted(payload["source_refs"]), ensure_ascii=False),  # type: ignore[index]
                skg_version_id,
            )
            for (base_cause, base_effect, moderator), payload in moderation_edge_accumulator.items()
        ]

        _materialize_skg(
            con=con,
            stats=stats,
            skg_version_id=skg_version_id,
            skg_articles_batch=skg_articles_batch,
            variable_mentions=dict(variable_mentions),
            variable_display=variable_display,
            skg_parameter_batch=skg_parameter_batch,
            edge_accumulator=edge_accumulator,
            edge_evidence_batch=edge_evidence_batch,
            simulation_parameter_batch=simulation_parameter_batch,
            context_attr_batch=context_attr_batch,
            moderation_edge_batch=moderation_edge_batch,
        )

        # finalize run row timestamps
        if run_id:
            con.execute(
                "UPDATE ac_runs SET finished_at = ?, status = ? WHERE run_id = ?",
                [datetime.now(UTC).isoformat(), "ok", run_id],
            )

        con.execute("CHECKPOINT")
    finally:
        con.close()
    return stats


def build_indexes(db_path: Path) -> None:
    """Create secondary indexes after load stage."""
    con = duckdb.connect(str(db_path))
    try:
        for stmt in _INDEXES.strip().split(";"):
            sql = stmt.strip()
            if sql:
                con.execute(sql)
        con.execute("CHECKPOINT")
    finally:
        con.close()


def run_graph_load(config: AcademicBatchConfig) -> GraphStats:
    """Run graph load."""
    started_at = datetime.now(UTC).isoformat()

    def _iter_records() -> Iterable[WorkRecord]:
        with open(config.merged_records_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield WorkRecord.model_validate_json(line)

    cfg_json = json.dumps(
        {
            "target_per_topic": config.target_per_topic,
            "selected_unique_budget": config.selected_unique_budget,
            "usable_fulltext_target": config.usable_fulltext_target,
            "pass_name": config.pass_name,
            "run_id": config.run_id,
            "llm_gate_enabled": config.llm_gate_enabled,
            "llm_gate_mode": config.llm_gate_mode,
            "numeric_precision_mode": config.numeric_precision_mode,
            "claim_adjudication_passes": config.claim_adjudication_passes,
        },
        ensure_ascii=False,
    )

    stats = load_graph(
        records=_iter_records(),
        db_path=config.db_path,
        insert_batch_size=config.graph_insert_batch,
        run_id=config.run_id,
        pass_name=config.pass_name,
        config_json=cfg_json,
        topics_catalog_path=config.topics_catalog_path
        if config.topics_catalog_path.exists()
        else None,
        ingest_errors_path=config.ingest_errors_path
        if config.ingest_errors_path.exists()
        else None,
        claim_adjudications_path=(
            config.claim_adjudications_path if config.claim_adjudications_path.exists() else None
        ),
        simulation_ready_numeric_path=(
            config.simulation_ready_numeric_path
            if config.simulation_ready_numeric_path.exists()
            else None
        ),
    )
    write_stage_manifest(
        manifest_path=config.manifests_dir / "graph_load.json",
        stage="graph_load",
        status="ok",
        metrics={
            "works": stats.works,
            "concepts": stats.concepts,
            "estimates": stats.estimates,
            "raw_claims": stats.raw_claims,
            "claim_adjudications": stats.claim_adjudications,
            "claims": stats.claims,
            "runs": stats.runs,
            "topics": stats.topics,
            "topic_selections": stats.topic_selections,
            "article_extractions": stats.article_extractions,
            "boundary_conditions": stats.boundary_conditions,
            "ingest_errors": stats.ingest_errors,
            "skg_articles": stats.skg_articles,
            "skg_variables": stats.skg_variables,
            "skg_edges": stats.skg_edges,
            "skg_edge_evidence": stats.skg_edge_evidence,
            "skg_family_edges": stats.skg_family_edges,
            "skg_parameters": stats.skg_parameters,
            "skg_simulation_parameters": stats.skg_simulation_parameters,
            "skg_versions": stats.skg_versions,
            "json_validation_failures": stats.json_validation_failures,
        },
        artifacts=[config.db_path],
        started_at=started_at,
    )
    return stats


def run_graph_index(config: AcademicBatchConfig) -> None:
    """Run graph index."""
    started_at = datetime.now(UTC).isoformat()
    build_indexes(config.db_path)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "graph_index.json",
        stage="graph_index",
        status="ok",
        metrics={},
        artifacts=[config.db_path],
        started_at=started_at,
    )


# Backward-compatible helper used by existing tests.
def build_graph(
    *,
    records: Iterable[WorkRecord],
    db_path: Path,
    insert_batch_size: int = 10_000,
    claim_adjudications_path: Path | None = None,
) -> GraphStats:
    """Build graph."""
    stats = load_graph(
        records=records,
        db_path=db_path,
        insert_batch_size=insert_batch_size,
        claim_adjudications_path=claim_adjudications_path,
    )
    build_indexes(db_path)
    return stats
