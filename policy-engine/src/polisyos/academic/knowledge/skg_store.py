"""SKG table DDL and confidence aggregation helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
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
    canonical_name           VARCHAR PRIMARY KEY,
    normalized_name          VARCHAR NOT NULL,
    display_name             VARCHAR NOT NULL,
    parent_name              VARCHAR,
    approved_canonical_name  VARCHAR,
    approved_parent_name     VARCHAR,
    is_approved_canonical    BOOLEAN DEFAULT FALSE,
    resolution_method        VARCHAR DEFAULT '',
    resolution_confidence    DOUBLE DEFAULT 0.0,
    mention_count            INTEGER DEFAULT 0,
    first_seen_ts            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

CREATE TABLE IF NOT EXISTS ac_skg_contested_edges (
    contested_edge_id         VARCHAR PRIMARY KEY,
    src_family                VARCHAR NOT NULL,
    dst_family                VARCHAR NOT NULL,
    n_articles                INTEGER DEFAULT 1,
    n_claims                  INTEGER DEFAULT 1,
    article_refs              VARCHAR NOT NULL,
    claim_refs                VARCHAR NOT NULL,
    dominant_direction        VARCHAR DEFAULT '',
    resolution_status         VARCHAR NOT NULL,
    runtime_support           VARCHAR NOT NULL,
    evidence_strength         VARCHAR NOT NULL,
    confidence                DOUBLE NOT NULL,
    positive_weight           DOUBLE DEFAULT 0.0,
    negative_weight           DOUBLE DEFAULT 0.0,
    mixed_weight              DOUBLE DEFAULT 0.0,
    dominant_direction_agreement DOUBLE DEFAULT 0.0,
    strongest_dissent_strength VARCHAR DEFAULT '',
    strongest_dissent_year    INTEGER,
    direction_histogram_json  VARCHAR DEFAULT '{}',
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

CREATE TABLE IF NOT EXISTS ac_skg_variable_synonyms (
    synonym            VARCHAR NOT NULL,
    canonical_name     VARCHAR NOT NULL,
    method             VARCHAR NOT NULL DEFAULT 'manual',
    confidence         DOUBLE DEFAULT 1.0,
    approved           BOOLEAN DEFAULT FALSE,
    created_ts         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (synonym, canonical_name)
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
CREATE INDEX IF NOT EXISTS idx_ac_skg_variables_approved ON ac_skg_variables(approved_canonical_name);
CREATE INDEX IF NOT EXISTS idx_ac_skg_variables_is_approved ON ac_skg_variables(is_approved_canonical);
CREATE INDEX IF NOT EXISTS idx_ac_skg_family_edges_src ON ac_skg_family_edges(src_family);
CREATE INDEX IF NOT EXISTS idx_ac_skg_family_edges_dst ON ac_skg_family_edges(dst_family);
CREATE INDEX IF NOT EXISTS idx_ac_skg_contested_edges_src ON ac_skg_contested_edges(src_family);
CREATE INDEX IF NOT EXISTS idx_ac_skg_contested_edges_dst ON ac_skg_contested_edges(dst_family);
CREATE INDEX IF NOT EXISTS idx_ac_skg_params_name ON ac_skg_parameters(canonical_name);
CREATE INDEX IF NOT EXISTS idx_ac_skg_params_article ON ac_skg_parameters(openalex_id);
CREATE INDEX IF NOT EXISTS idx_ac_skg_sim_params_name ON ac_skg_simulation_parameters(canonical_name);
CREATE INDEX IF NOT EXISTS idx_ac_skg_sim_params_article ON ac_skg_simulation_parameters(openalex_id);
CREATE INDEX IF NOT EXISTS idx_ac_skg_articles_year ON ac_skg_articles(year);
CREATE INDEX IF NOT EXISTS idx_ac_skg_articles_retracted ON ac_skg_articles(retracted);
CREATE INDEX IF NOT EXISTS idx_ac_skg_variable_synonyms_synonym ON ac_skg_variable_synonyms(synonym);
CREATE INDEX IF NOT EXISTS idx_ac_skg_variable_synonyms_canonical ON ac_skg_variable_synonyms(canonical_name);

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

# Minimum confidence floor for aggregate_edge_confidence, keyed by
# the strongest evidence type present among the evidence items.
# This prevents the noisy-OR formula from producing unreasonably low
# confidence when multiplicative penalty factors (temporal decay,
# missing sample size, low extraction confidence) stack up.
#
# Floors are meaningful only for strong designs (panel_fe+).
# Weaker evidence types use 0.0 so quality differentiation
# (e.g. abstract-only penalty, temporal decay) is preserved.
_CONFIDENCE_FLOOR: dict[str, float] = {
    EvidenceStrength.RCT.value: 0.55,
    EvidenceStrength.META_ANALYSIS.value: 0.55,
    EvidenceStrength.QUASI_NATURAL.value: 0.45,
    EvidenceStrength.QUASI_NATURAL_EVENT.value: 0.40,
    EvidenceStrength.PANEL_FE.value: 0.35,
    EvidenceStrength.STRUCTURAL.value: 0.30,
    EvidenceStrength.OBSERVATIONAL.value: 0.0,
    EvidenceStrength.CROSS_SECTIONAL.value: 0.0,
    EvidenceStrength.THEORETICAL.value: 0.0,
    EvidenceStrength.UNKNOWN.value: 0.0,
}

ABSTRACT_ONLY_PENALTY = 0.5
TEMPORAL_HALF_LIFE_YEARS = 20.0
TEMPORAL_FLOOR = 0.30
CITATION_IMPACT_ENABLED = True
CITATION_IMPACT_CAP = 1.15


@dataclass(frozen=True)
class ArticleEvidence:
    """Article evidence public type."""
    strength: str
    extraction_confidence: float
    publication_year: int | None = None
    sample_size: int | None = None
    source_basis: str = "fulltext"
    retracted: bool = False
    fwci: float | None = None


@dataclass(frozen=True)
class WeightedDirectionSummary:
    """Weighted direction summary data model."""
    dominant_direction: str
    agreement_score: float
    is_contested: bool
    direction_weights: dict[str, float]
    strongest_dissent_strength: str = ""
    strongest_dissent_year: int | None = None


def _coerce_article_evidence(row: ArticleEvidence | tuple[Any, ...]) -> ArticleEvidence:
    if isinstance(row, ArticleEvidence):
        return row
    if len(row) == 2:
        strength, extraction_confidence = row
        return ArticleEvidence(
            strength=str(strength),
            extraction_confidence=float(extraction_confidence or 0.0),
        )
    if len(row) == 4:
        strength, extraction_confidence, publication_year, retracted = row
        return ArticleEvidence(
            strength=str(strength),
            extraction_confidence=float(extraction_confidence or 0.0),
            publication_year=int(publication_year) if publication_year not in (None, "") else None,
            retracted=bool(retracted),
        )
    if len(row) >= 7:
        strength, extraction_confidence, publication_year, sample_size, source_basis, retracted, fwci = row[:7]
        return ArticleEvidence(
            strength=str(strength),
            extraction_confidence=float(extraction_confidence or 0.0),
            publication_year=int(publication_year) if publication_year not in (None, "") else None,
            sample_size=int(sample_size) if sample_size not in (None, "") else None,
            source_basis=str(source_basis or "fulltext"),
            retracted=bool(retracted),
            fwci=float(fwci) if fwci not in (None, "") else None,
        )
    raise ValueError(f"Unsupported article evidence row: {row!r}")


def _temporal_weight(pub_year: int | None, *, current_year: int | None = None) -> float:
    if pub_year is None:
        return 0.85
    reference_year = current_year or datetime.now(UTC).year
    age = max(0, int(reference_year) - int(pub_year))
    decay = 0.5 ** (age / TEMPORAL_HALF_LIFE_YEARS)
    return max(TEMPORAL_FLOOR, float(decay))


def _sample_size_factor(sample_size: int | None) -> float:
    if sample_size is None or int(sample_size) <= 0:
        return 0.7
    n = int(sample_size)
    if n < 100:
        return 0.6
    if n < 500:
        return 0.8
    if n < 5000:
        return 0.9
    return 1.0


def _citation_factor(fwci: float | None) -> float:
    if not CITATION_IMPACT_ENABLED or fwci is None:
        return 1.0
    return min(CITATION_IMPACT_CAP, max(0.5, float(fwci)))


def _effective_evidence_weight(evidence: ArticleEvidence) -> float:
    if evidence.retracted:
        return 0.0
    base = EVIDENCE_WEIGHTS.get(str(evidence.strength), EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value])
    weight = (
        base
        * _temporal_weight(evidence.publication_year)
        * _sample_size_factor(evidence.sample_size)
        * max(0.0, min(1.0, float(evidence.extraction_confidence)))
        * _citation_factor(evidence.fwci)
    )
    if str(evidence.source_basis or "").strip().lower() == "abstract_only":
        _strong_evidence_types = {
            EvidenceStrength.RCT.value,
            EvidenceStrength.QUASI_NATURAL.value,
            EvidenceStrength.META_ANALYSIS.value,
        }
        if str(evidence.strength or "").strip() in _strong_evidence_types:
            weight *= 0.75  # reduced penalty for strong designs
        else:
            weight *= ABSTRACT_ONLY_PENALTY
    return min(0.99, max(0.0, float(weight)))


def aggregate_edge_confidence(articles: Iterable[ArticleEvidence | tuple[Any, ...]]) -> float:
    """Aggregate edge confidence using evidence-weighted noisy-OR with strength floor.

    The noisy-OR formula ``1 - prod(1 - w_i)`` can yield unreasonably low
    confidence when multiplicative penalty factors stack up (temporal decay,
    missing sample size, fallback extraction confidence).  We apply a minimum
    floor based on the strongest evidence type present so that, e.g., a single
    RCT never scores below 0.55 regardless of penalty stacking.
    """
    rows = [_coerce_article_evidence(row) for row in articles]
    valid = [row for row in rows if not row.retracted]
    if not valid:
        return 0.0

    weights = [_effective_evidence_weight(row) for row in valid]
    if not weights:
        return 0.0
    combined = 1.0 - math.prod(1.0 - min(weight, 0.99) for weight in weights)

    # Determine floor from strongest evidence type present
    strongest_base = max(
        EVIDENCE_WEIGHTS.get(str(row.strength), 0.0) for row in valid
    )
    # Find the matching floor key
    floor = 0.10
    for strength_key, base_weight in EVIDENCE_WEIGHTS.items():
        if abs(base_weight - strongest_base) < 1e-6:
            floor = _CONFIDENCE_FLOOR.get(strength_key, 0.10)
            break
    # Multi-article bonus: +0.06 per extra article, cap at +0.30
    n_bonus = min(0.30, 0.06 * max(0, len(valid) - 1))
    floor = min(0.95, floor + n_bonus)

    return min(1.0, max(floor, combined))


def weighted_direction_summary(
    direction_evidence: dict[str, Iterable[ArticleEvidence | tuple[Any, ...]]],
) -> WeightedDirectionSummary:
    """Weighted direction summary helper."""
    direction_weights: dict[str, float] = {}
    dissent_strength = EvidenceStrength.UNKNOWN.value
    dissent_year: int | None = None
    for direction, items in direction_evidence.items():
        rows = [_coerce_article_evidence(item) for item in items]
        total_weight = sum(_effective_evidence_weight(row) for row in rows)
        direction_weights[str(direction)] = float(total_weight)

    total = sum(direction_weights.values())
    if total <= 0.0:
        return WeightedDirectionSummary(
            dominant_direction="unknown",
            agreement_score=0.0,
            is_contested=False,
            direction_weights=direction_weights,
        )

    dominant_direction = max(
        direction_weights.items(),
        key=lambda item: (item[1], item[0]),
    )[0]
    agreement = float(direction_weights[dominant_direction] / total)
    significant = [direction for direction, weight in direction_weights.items() if (weight / total) > 0.15]
    is_contested = len(significant) > 1

    if is_contested:
        non_dominant: list[ArticleEvidence] = []
        for direction, items in direction_evidence.items():
            if direction == dominant_direction:
                continue
            non_dominant.extend(_coerce_article_evidence(item) for item in items)
        if non_dominant:
            strongest = max(non_dominant, key=lambda row: (_effective_evidence_weight(row), edge_strength_rank(row.strength)))
            dissent_strength = strongest.strength
            dissent_year = strongest.publication_year

    return WeightedDirectionSummary(
        dominant_direction=dominant_direction,
        agreement_score=agreement,
        is_contested=is_contested,
        direction_weights={key: round(value, 6) for key, value in direction_weights.items()},
        strongest_dissent_strength=dissent_strength if is_contested else "",
        strongest_dissent_year=dissent_year if is_contested else None,
    )


def ensure_skg_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Ensure skg schema helper."""
    for stmt in SKG_DDL.strip().split(";"):
        sql = stmt.strip()
        if sql:
            con.execute(sql)
    for table_name, column_name, column_sql in (
        ("ac_skg_contested_edges", "positive_weight", "DOUBLE DEFAULT 0.0"),
        ("ac_skg_contested_edges", "negative_weight", "DOUBLE DEFAULT 0.0"),
        ("ac_skg_contested_edges", "mixed_weight", "DOUBLE DEFAULT 0.0"),
        ("ac_skg_contested_edges", "dominant_direction_agreement", "DOUBLE DEFAULT 0.0"),
        ("ac_skg_contested_edges", "strongest_dissent_strength", "VARCHAR DEFAULT ''"),
        ("ac_skg_contested_edges", "strongest_dissent_year", "INTEGER"),
    ):
        try:
            exists = con.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = ? AND column_name = ?
                LIMIT 1
                """,
                [table_name, column_name],
            ).fetchone()
        except duckdb.Error:
            exists = None
        if not exists:
            con.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def next_skg_version(con: duckdb.DuckDBPyConnection, *, description: str = "") -> int:
    """Next skg version helper."""
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
    """Finalize skg version helper."""
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
    """Hash edge ID helper."""
    import hashlib

    payload = f"{src}|{dst}|{direction}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_param_id(canonical_name: str, openalex_id: str) -> str:
    """Hash param ID helper."""
    import hashlib

    payload = f"{canonical_name}|{openalex_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_contested_edge_id(src_family: str, dst_family: str) -> str:
    """Hash contested edge ID helper."""
    import hashlib

    payload = f"contested|{src_family}|{dst_family}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_context_attr_id(canonical_name: str, openalex_id: str, country_code: str) -> str:
    """Hash context attr ID helper."""
    import hashlib

    payload = f"ctx_attr|{canonical_name}|{openalex_id}|{country_code}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_moderation_edge_id(base_cause: str, base_effect: str, moderator: str) -> str:
    """Hash moderation edge ID helper."""
    import hashlib

    payload = f"mod_edge|{base_cause}|{base_effect}|{moderator}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_transport_score_id(edge_id: str, target_context_id: str) -> str:
    """Hash transport score ID helper."""
    import hashlib

    payload = f"transport|{edge_id}|{target_context_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def hash_context_profile_id(context_id: str, time_period: str) -> str:
    """Hash context profile ID helper."""
    import hashlib

    payload = f"ctx_prof|{context_id}|{time_period}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def parent_canonical_name(canonical_name: str) -> str | None:
    """Parent canonical name helper."""
    if "." not in canonical_name:
        return None
    return canonical_name.rsplit(".", 1)[0]


def edge_strength_rank(strength: str) -> int:
    """Edge strength rank helper."""
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
    """Strongest strength helper."""
    best = EvidenceStrength.UNKNOWN.value
    best_rank = -1
    for value in values:
        rank = edge_strength_rank(str(value))
        if rank > best_rank:
            best_rank = rank
            best = str(value)
    return best


def normalize_strength(value: Any) -> str:
    """Normalize strength helper."""
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
    "ABSTRACT_ONLY_PENALTY",
    "ArticleEvidence",
    "WeightedDirectionSummary",
    "aggregate_edge_confidence",
    "weighted_direction_summary",
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
