"""Effective-independence graph annotation for evidence portfolios.

The graph is a W8.F bridge over the W4.B evidence-line and independence-map
contracts. It preserves raw evidence lines as diagnostic facts while reporting
hard collapse, feature-flagged graded dependence, scarcity paths, and separate
support/counterevidence mass.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

EFFECTIVE_INDEPENDENCE_GRAPH_SCHEMA_VERSION = (
    "policyos.evidence.portfolio.effective_independence_graph.v1"
)
EFFECTIVE_INDEPENDENCE_GRAPH_CONTRACT_ID = "policy_design_case.effective_independence_graph.v1"
GRADED_INDEPENDENCE_FEATURE_FLAG = "policy_design_case.graded_independence_weights"
PAIRWISE_MODEL_FORMULA = "D(a,b)=min(0.95,sum(weight_c*overlap_c));I(a,b)=1-D(a,b)"
MAX_PARTIAL_DEPENDENCE = 0.95

EVIDENCE_LINE_IDENTITY_DIMENSIONS = (
    "claim_ids",
    "strand",
    "polarity",
    "source_refs",
    "primary_source",
    "retrieval_path",
    "legal_authority",
    "author_institution_sponsor",
    "dataset_corpus_snapshot_subject_pool",
    "preprocessing",
    "transformation_lineage",
    "method_family",
    "identification_strategy",
    "assumptions",
    "proof_reuse_status",
    "llm_generation_path",
    "simulation_dgp",
    "participation_sample_frame",
    "concept_spine",
    "jurisdiction",
    "time_roles",
)

_VALID_CONFIG_STATUSES = frozenset({"provisional", "validated", "deprecated", "withdrawn"})
_VALID_SCARCITY_STATUSES = frozenset(
    {"not_rare_domain", "scarcity_structural", "scarcity_remediable"}
)
_COUNTEREVIDENCE_TOKENS = frozenset(
    {
        "conflict",
        "counter",
        "counterevidence",
        "counter_evidence",
        "contradict",
        "contradictory",
        "disconfirm",
        "disconfirming",
        "negative_control",
        "opposes",
        "rebuttal",
        "refute",
        "refuting",
    }
)
_CONTEXT_TOKENS = frozenset({"context", "context_only", "neutral", "background"})
_EMPTY_SIMULATION_MARKERS = frozenset({"", "none", "not_applicable", "not_simulated"})


@dataclass
class EffectiveIndependenceGraphError(ValueError):
    """Fail-closed effective-independence graph contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def build_effective_independence_graph(
    evidence_lines: Iterable[Mapping[str, Any]],
    *,
    portfolio_designs: Iterable[Mapping[str, Any]],
    graph_id: str,
    producer_execution_started_at: str | datetime | None = None,
    feature_flags: Mapping[str, bool] | None = None,
    graded_independence_config: Mapping[str, Any] | None = None,
    rare_domain_context: Mapping[str, Any] | None = None,
    independence_map_ref: str | None = None,
    pdc_graph_ref: str | None = None,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
) -> dict[str, Any]:
    """Build a W8.F effective-independence graph from W4.B evidence lines.

    Args:
        evidence_lines: Evidence-line records produced by portfolio producers.
        portfolio_designs: Predeclared portfolio designs used by W4.B validation.
        graph_id: Stable graph identifier.
        producer_execution_started_at: Producer execution time for predeclaration checks.
        feature_flags: Feature flags controlling graded pairwise calculus.
        graded_independence_config: Governed graded-calculus weights.
        rare_domain_context: Optional rare-domain scarcity classification.
        independence_map_ref: Optional W4.B independence-map reference.
        pdc_graph_ref: Optional RuntimePolicyDesignCase graph reference.
        evidence_ref: Optional persisted evidence artifact reference.
        runtime_event_ref: Optional runtime event reference.

    Returns:
        Validated effective-independence graph payload.
    """

    portfolio_rows = tuple(portfolio_designs)
    del producer_execution_started_at
    lines = _normalize_evidence_line_records(
        evidence_lines,
        portfolio_designs=portfolio_rows,
    )

    normalized_graph_id = _required_text(
        graph_id,
        "graph_id",
        "policy_design_effective_independence_graph_id_missing",
    )
    identities = [_line_identity(line, ordinal=index) for index, line in enumerate(lines)]
    hard_edges = _hard_collapse_edges(identities)
    hard_clusters = _hard_collapse_clusters(identities, hard_edges)
    graded = _graded_calculus(
        identities,
        hard_edges=hard_edges,
        feature_flags=feature_flags,
        governed_config=graded_independence_config,
    )
    mass_report = _mass_report(
        identities,
        hard_clusters=hard_clusters,
        pairwise_dependencies=graded["pairwise_dependencies"],
        graded_enabled=bool(graded["enabled"]),
    )
    scarcity_path = _scarcity_path(
        rare_domain_context,
        effective_support_mass=float(mass_report["graded_effective_support_mass"]),
    )
    if scarcity_path["status"] != "not_rare_domain":
        deficits = list(mass_report["limiting_deficits"])
        if scarcity_path["status"] not in deficits:
            deficits.append(str(scarcity_path["status"]))
        mass_report["limiting_deficits"] = deficits

    payload: dict[str, Any] = {
        "schema_version": EFFECTIVE_INDEPENDENCE_GRAPH_SCHEMA_VERSION,
        "contract_id": EFFECTIVE_INDEPENDENCE_GRAPH_CONTRACT_ID,
        "graph_id": normalized_graph_id,
        "claim_ids": _sorted_unique(
            claim_id
            for identity in identities
            for claim_id in _as_tuple(identity["identity_dimensions"]["claim_ids"])
        ),
        "portfolio_ids": _sorted_unique(line.get("portfolio_id") for line in lines),
        "raw_evidence_line_count": len(lines),
        "hard_effective_line_count": len(hard_clusters),
        "identity_dimensions": list(EVIDENCE_LINE_IDENTITY_DIMENSIONS),
        "evidence_line_identities": identities,
        "hard_collapse_clusters": hard_clusters,
        "graded_calculus": graded,
        "mass_report": mass_report,
        "scarcity_path": scarcity_path,
        "counterevidence_policy": {
            "collapse_across_support": "forbidden",
            "support_mass_field": "mass_report.graded_effective_support_mass",
            "counterevidence_mass_field": ("mass_report.graded_effective_counterevidence_mass"),
        },
        "raw_count_display_policy": {
            "raw_count_authority": "diagnostic_only",
            "must_display_with": [
                "hard_effective_line_count",
                "graded_effective_support_mass",
                "hard_collapse_clusters",
                "scarcity_path",
            ],
        },
    }
    if independence_map_ref is not None:
        payload["independence_map_ref"] = str(independence_map_ref)
    if pdc_graph_ref is not None:
        payload["pdc_graph_ref"] = str(pdc_graph_ref)
    if evidence_ref is not None:
        payload["evidence_ref"] = str(evidence_ref)
    if runtime_event_ref is not None:
        payload["runtime_event_ref"] = str(runtime_event_ref)
    return validate_effective_independence_graph_record(payload)


def validate_effective_independence_graph_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one effective-independence graph record."""

    if not isinstance(record, Mapping):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_graph_invalid",
            "Effective-independence graph must be a mapping.",
        )
    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_effective_independence_schema_version_missing",
    )
    if schema_version != EFFECTIVE_INDEPENDENCE_GRAPH_SCHEMA_VERSION:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_schema_version_invalid",
            "Effective-independence graph must use the W8.F schema version.",
            "schema_version",
        )
    normalized["schema_version"] = EFFECTIVE_INDEPENDENCE_GRAPH_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id")) or EFFECTIVE_INDEPENDENCE_GRAPH_CONTRACT_ID
    )
    normalized["graph_id"] = _required_text(
        record.get("graph_id") or record.get("effective_independence_graph_id"),
        "graph_id",
        "policy_design_effective_independence_graph_id_missing",
    )
    raw_count = _required_nonnegative_int(
        record.get("raw_evidence_line_count"),
        "raw_evidence_line_count",
        "policy_design_effective_independence_raw_count_missing",
    )
    hard_count = _required_nonnegative_int(
        record.get("hard_effective_line_count"),
        "hard_effective_line_count",
        "policy_design_effective_independence_hard_count_missing",
    )
    if hard_count > raw_count:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_hard_count_exceeds_raw",
            "Hard effective line count cannot exceed raw evidence-line count.",
            "hard_effective_line_count",
        )
    normalized["raw_evidence_line_count"] = raw_count
    normalized["hard_effective_line_count"] = hard_count
    clusters = _validate_hard_clusters(record.get("hard_collapse_clusters"))
    if len(clusters) != hard_count:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_cluster_count_mismatch",
            "Hard effective line count must equal hard collapse cluster count.",
            "hard_collapse_clusters",
        )
    normalized["hard_collapse_clusters"] = clusters
    normalized["graded_calculus"] = _validate_graded_calculus(
        record.get("graded_calculus"),
        raw_count=raw_count,
    )
    normalized["mass_report"] = _validate_mass_report(
        record.get("mass_report"),
        raw_count=raw_count,
        hard_count=hard_count,
    )
    normalized["scarcity_path"] = _validate_scarcity_path(
        record.get("scarcity_path"),
        effective_support_mass=float(normalized["mass_report"]["graded_effective_support_mass"]),
    )
    policy = record.get("counterevidence_policy")
    if not isinstance(policy, Mapping) or policy.get("collapse_across_support") != "forbidden":
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_counterevidence_policy_missing",
            "Counterevidence must be preserved separately from support.",
            "counterevidence_policy",
        )
    normalized["counterevidence_policy"] = dict(policy)
    return normalized


def annotate_pdc_graph_with_effective_independence(
    pdc_graph: Mapping[str, Any],
    effective_independence_graph: Mapping[str, Any],
) -> dict[str, Any]:
    """Annotate a RuntimePolicyDesignCase-like graph with W8.F refs.

    The helper intentionally accepts mappings because W8.A's final graph type is
    a sibling phase. This keeps W8.F a separate writer while giving the graph
    compiler a deterministic bridge to consume.
    """

    if not isinstance(pdc_graph, Mapping):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_pdc_graph_invalid",
            "PDC graph must be a mapping.",
            "pdc_graph",
        )
    graph = validate_effective_independence_graph_record(effective_independence_graph)
    graph_ref = str(graph["graph_id"])
    claim_ids = set(_text_values(graph.get("claim_ids")))
    summary = {
        "graph_id": graph_ref,
        "hard_effective_line_count": graph["hard_effective_line_count"],
        "graded_effective_support_mass": graph["mass_report"]["graded_effective_support_mass"],
        "graded_effective_counterevidence_mass": graph["mass_report"][
            "graded_effective_counterevidence_mass"
        ],
        "scarcity_status": graph["scarcity_path"]["status"],
        "raw_count_authority": graph["mass_report"]["raw_count_authority"],
    }

    annotated = _deep_copy_mapping(pdc_graph)
    refs = _unique((*_text_values(annotated.get("effective_independence_graph_refs")), graph_ref))
    annotated["effective_independence_graph_refs"] = list(refs)
    summaries = list(_mapping_sequence(annotated.get("effective_independence_summaries")))
    if not any(item.get("graph_id") == graph_ref for item in summaries):
        summaries.append(summary)
    annotated["effective_independence_summaries"] = summaries
    annotated["effective_independence_authority"] = {
        "authoritative_for": ["effective_independence_graph_annotation"],
        "may_not_use_for": ["claim_authority", "projection_authority"],
    }

    claims = annotated.get("claims")
    if isinstance(claims, Sequence) and not isinstance(claims, str):
        annotated["claims"] = [
            _annotate_claim(claim, graph_ref=graph_ref, claim_ids=claim_ids, summary=summary)
            for claim in claims
        ]
    claim_graph = annotated.get("claim_graph")
    if isinstance(claim_graph, Mapping):
        claim_graph_copy = dict(claim_graph)
        graph_claims = claim_graph_copy.get("claims")
        if isinstance(graph_claims, Sequence) and not isinstance(graph_claims, str):
            claim_graph_copy["claims"] = [
                _annotate_claim(
                    claim,
                    graph_ref=graph_ref,
                    claim_ids=claim_ids,
                    summary=summary,
                )
                for claim in graph_claims
            ]
        annotated["claim_graph"] = claim_graph_copy
    return annotated


def _line_identity(line: Mapping[str, Any], *, ordinal: int) -> dict[str, Any]:
    line_id = evidence_line_record_id(line)
    polarity = _line_polarity(line)
    dimensions = {
        "claim_ids": _text_values(line.get("claim_ids") or line.get("claim_id")),
        "strand": _required_text(
            line.get("evidence_strand") or line.get("strand"),
            "evidence_strand",
            "policy_design_effective_independence_strand_missing",
        ),
        "polarity": polarity,
        "source_refs": _values_from_line(
            line,
            "source_refs",
            "source_ref",
            ("source_lineage", "source_ref"),
            ("source_lineage", "source_id"),
            ("source_lineage", "lineage_refs"),
        ),
        "primary_source": _first_text_from_line(
            line,
            "primary_source",
            "primary_source_ref",
            ("source_lineage", "primary_source"),
            ("source_lineage", "source_id"),
        ),
        "retrieval_path": _values_from_line(
            line,
            "retrieval_path",
            "retrieval_path_ref",
            ("source_lineage", "retrieval_path"),
            ("llm_generation_path", "retrieval_ref"),
        ),
        "legal_authority": _values_from_line(
            line,
            "controlling_legal_instrument",
            "legal_authority",
            "legal_authority_refs",
            "legal_instrument_ref",
        ),
        "controlling_legal_instrument": _values_from_line(
            line,
            "controlling_legal_instrument",
            "legal_instrument_ref",
        ),
        "author_institution_sponsor": _values_from_line(
            line,
            "author_ids",
            "author_pool",
            "institution_ids",
            "institution_pool",
            "sponsor_ids",
            "sponsor",
        ),
        "dataset_corpus_snapshot_subject_pool": _values_from_line(
            line,
            "dataset_id",
            "dataset_ids",
            "corpus_ancestry",
            "snapshot_id",
            "snapshot_ref",
            "subject_pool",
            "subject_pool_id",
            ("source_lineage", "corpus_id"),
            ("source_lineage", "corpus_ancestry"),
        ),
        "snapshot": _values_from_line(
            line,
            "snapshot_id",
            "snapshot_ref",
            ("source_lineage", "snapshot_id"),
            ("source_lineage", "snapshot_ref"),
        ),
        "preprocessing": _values_from_line(
            line,
            "preprocessing",
            "preprocessing_ref",
            "preprocessing_pipeline_id",
            "preprocessing_pipeline_ref",
            ("source_lineage", "preprocessing"),
        ),
        "transformation_lineage": _values_from_line(
            line,
            "transformation_lineage",
            "transformation_refs",
            "lineage_transform_refs",
            ("source_lineage", "transformation_lineage"),
        ),
        "method_family": _values_from_line(
            line,
            "method_family",
            ("method", "method_family"),
            ("method", "family"),
        )
        or _method_family_from_method_id(line),
        "identification_strategy": _values_from_line(
            line,
            "identification_strategy_id",
            "identification_strategy",
            "identification_ref",
            ("method", "identification_strategy"),
        ),
        "assumptions": _values_from_line(
            line,
            "method_assumptions",
            "assumptions",
            "assumption_refs",
            ("simulation_dgp", "assumption_family"),
        ),
        "proof_reuse_status": _values_from_line(
            line,
            "proof_reuse_status",
            "proof_reuse_ref",
        ),
        "underlying_study": _values_from_line(
            line,
            "underlying_study_id",
            "study_id",
            "source_family_independence_tag",
        ),
        "llm_generation_path": _values_from_line(
            line,
            "llm_model",
            "llm_prompt_ref",
            "llm_retrieval_ref",
            ("llm_generation_path", "model"),
            ("llm_generation_path", "prompt_ref"),
            ("llm_generation_path", "retrieval_ref"),
        ),
        "simulation_dgp": _values_from_line(
            line,
            "simulation_dgp",
            "dgp_ref",
            "calibration_ref",
            ("simulation_dgp", "dgp_ref"),
            ("simulation_dgp", "calibration_ref"),
            ("simulation_dgp", "assumption_family"),
        ),
        "participation_sample_frame": _values_from_line(
            line,
            "participation_sample_frame",
            "sample_frame",
            "sample_frame_ref",
        ),
        "concept_spine": _values_from_line(
            line,
            "concept_spine",
            "concept_spine_ref",
            "concept_spine_refs",
        ),
        "jurisdiction": _values_from_line(
            line,
            "jurisdiction",
            "jurisdiction_id",
            "jurisdiction_refs",
        ),
        "time_roles": _values_from_line(
            line,
            "time_roles",
            "observation_time",
            "publication_time",
            "retrieval_time",
            "legal_valid_time",
            "transaction_time",
        ),
    }
    for dimension in EVIDENCE_LINE_IDENTITY_DIMENSIONS:
        dimensions.setdefault(dimension, ())
    return {
        "line_id": line_id,
        "ordinal": ordinal,
        "claim_ids": list(_as_tuple(dimensions["claim_ids"])),
        "strand": dimensions["strand"],
        "polarity": polarity,
        "quality": _line_quality(line),
        "identity_dimensions": _jsonable_dimensions(dimensions),
        "evidence_ref": _text(line.get("evidence_ref")),
        "runtime_event_ref": _text(line.get("runtime_event_ref")),
    }


def _normalize_evidence_line_records(
    records: Iterable[Mapping[str, Any]],
    *,
    portfolio_designs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    portfolio_index = _portfolio_design_index(portfolio_designs)
    normalized: list[dict[str, Any]] = []
    seen_line_ids: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise EffectiveIndependenceGraphError(
                "policy_design_effective_independence_line_invalid",
                "Effective-independence graph evidence lines must be mappings.",
                f"evidence_lines[{index}]",
            )
        line = dict(record)
        line_id = evidence_line_record_id(line)
        if line_id in seen_line_ids:
            raise EffectiveIndependenceGraphError(
                "policy_design_effective_independence_line_id_duplicate",
                "Evidence line ids must be unique within an effective-independence graph.",
                f"evidence_lines[{index}].line_id",
            )
        seen_line_ids.add(line_id)
        line["line_id"] = line_id
        claim_ids = _text_values(line.get("claim_ids") or line.get("claim_id"))
        if not claim_ids:
            raise EffectiveIndependenceGraphError(
                "policy_design_effective_independence_claim_ref_missing",
                "Evidence line must bind at least one claim.",
                f"evidence_lines[{index}].claim_ids",
            )
        line["claim_ids"] = list(claim_ids)
        line["portfolio_id"] = _required_text(
            line.get("portfolio_id")
            or line.get("portfolio_design_id")
            or line.get("portfolio_ref"),
            f"evidence_lines[{index}].portfolio_id",
            "policy_design_effective_independence_portfolio_id_missing",
        )
        line["evidence_strand"] = _required_text(
            line.get("evidence_strand") or line.get("strand"),
            f"evidence_lines[{index}].evidence_strand",
            "policy_design_effective_independence_strand_missing",
        )
        _validate_portfolio_binding(line, portfolio_index=portfolio_index, index=index)
        normalized.append(line)
    return normalized


def evidence_line_record_id(record: Mapping[str, Any]) -> str:
    """Return the stable identity for a W8.F evidence line."""

    return _required_text(
        record.get("line_id")
        or record.get("evidence_line_id")
        or record.get("record_id")
        or record.get("id"),
        "line_id",
        "policy_design_effective_independence_line_id_missing",
    )


def _portfolio_design_index(
    portfolio_designs: Sequence[Mapping[str, Any]],
) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for design in portfolio_designs:
        if not isinstance(design, Mapping):
            continue
        portfolio_id = _text(
            design.get("portfolio_id")
            or design.get("portfolio_design_id")
            or design.get("design_id")
            or design.get("record_id")
        )
        if portfolio_id is None:
            continue
        index[portfolio_id] = set(
            _text_values(
                design.get("claim_ids")
                or design.get("major_claim_ids")
                or design.get("claim_id")
                or design.get("major_claim_id")
            )
        )
    return index


def _validate_portfolio_binding(
    line: Mapping[str, Any],
    *,
    portfolio_index: Mapping[str, set[str]],
    index: int,
) -> None:
    if not portfolio_index:
        return
    portfolio_id = str(line["portfolio_id"])
    if portfolio_id not in portfolio_index:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_portfolio_binding_missing",
            "Evidence line must bind a supplied portfolio design.",
            f"evidence_lines[{index}].portfolio_id",
        )
    allowed_claims = portfolio_index[portfolio_id]
    line_claims = set(_text_values(line.get("claim_ids") or line.get("claim_id")))
    if allowed_claims and line_claims.isdisjoint(allowed_claims):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_claim_binding_missing",
            "Evidence line claims must overlap the bound portfolio design.",
            f"evidence_lines[{index}].claim_ids",
        )


def _hard_collapse_edges(identities: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for left_index, left in enumerate(identities):
        for right in identities[left_index + 1 :]:
            if not _same_context(left, right, require_same_polarity=True):
                continue
            reasons = _hard_collapse_reasons(left, right)
            if not reasons:
                continue
            edges.append(
                {
                    "line_ids": [left["line_id"], right["line_id"]],
                    "collapse_reasons": reasons,
                }
            )
    return edges


def _hard_collapse_reasons(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> list[dict[str, Any]]:
    left_dims = _identity_dimensions(left)
    right_dims = _identity_dimensions(right)
    reasons: list[dict[str, Any]] = []
    study_overlap = _overlap_values(left_dims, right_dims, "underlying_study")
    if study_overlap:
        reasons.append(
            _collapse_reason(
                "same_study_reported_multiple_times",
                "underlying_study",
                study_overlap,
            )
        )
    primary_overlap = _overlap_values(left_dims, right_dims, "primary_source")
    if primary_overlap:
        reasons.append(_collapse_reason("same_primary_source", "primary_source", primary_overlap))
    if (
        _overlap_values(left_dims, right_dims, "snapshot")
        and _overlap_values(left_dims, right_dims, "preprocessing")
        and _overlap_values(left_dims, right_dims, "identification_strategy")
    ):
        reasons.append(
            _collapse_reason(
                "same_snapshot_preprocessing_identification",
                "snapshot_preprocessing_identification",
                _sorted_unique(
                    (
                        *_overlap_values(left_dims, right_dims, "snapshot"),
                        *_overlap_values(left_dims, right_dims, "preprocessing"),
                        *_overlap_values(left_dims, right_dims, "identification_strategy"),
                    )
                ),
            )
        )
    if _is_legal_context(left, right):
        legal_overlap = _overlap_values(left_dims, right_dims, "legal_authority")
        if legal_overlap:
            reasons.append(
                _collapse_reason(
                    "same_controlling_legal_instrument",
                    "legal_authority",
                    legal_overlap,
                )
            )
    if _is_simulation_context(left_dims, right_dims):
        dgp_overlap = _overlap_values(left_dims, right_dims, "simulation_dgp")
        assumption_overlap = _overlap_values(left_dims, right_dims, "assumptions")
        if dgp_overlap and assumption_overlap:
            reasons.append(
                _collapse_reason(
                    "same_dgp_calibration_assumption_family",
                    "simulation_dgp",
                    _sorted_unique((*dgp_overlap, *assumption_overlap)),
                )
            )
    if _same_llm_generation_path(left_dims, right_dims):
        reasons.append(
            _collapse_reason(
                "same_llm_model_prompt_retrieval",
                "llm_generation_path",
                _overlap_values(left_dims, right_dims, "llm_generation_path"),
            )
        )
    return reasons


def _hard_collapse_clusters(
    identities: Sequence[Mapping[str, Any]],
    hard_edges: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    parent = {str(identity["line_id"]): str(identity["line_id"]) for identity in identities}

    def find(line_id: str) -> str:
        parent.setdefault(line_id, line_id)
        if parent[line_id] != line_id:
            parent[line_id] = find(parent[line_id])
        return parent[line_id]

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in hard_edges:
        line_ids = _text_values(edge.get("line_ids"))
        if len(line_ids) == 2:
            union(line_ids[0], line_ids[1])

    identity_by_id = {str(identity["line_id"]): identity for identity in identities}
    groups: dict[str, list[str]] = {}
    for identity in identities:
        line_id = str(identity["line_id"])
        groups.setdefault(find(line_id), []).append(line_id)

    reasons_by_pair = {
        tuple(_text_values(edge.get("line_ids"))): list(
            _mapping_sequence(edge.get("collapse_reasons"))
        )
        for edge in hard_edges
    }
    clusters: list[dict[str, Any]] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda line_id: int(identity_by_id[line_id]["ordinal"]))
        representative = max(
            ordered,
            key=lambda line_id: (
                float(identity_by_id[line_id]["quality"]),
                -int(identity_by_id[line_id]["ordinal"]),
            ),
        )
        collapse_reasons: list[dict[str, Any]] = []
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1 :]:
                for reason in reasons_by_pair.get((left, right), ()):
                    if reason not in collapse_reasons:
                        collapse_reasons.append(dict(reason))
        cluster_index = len(clusters) + 1
        cluster = {
            "cluster_id": f"effective-hard-cluster-{cluster_index}",
            "line_ids": ordered,
            "raw_line_count": len(ordered),
            "effective_line_count": 1,
            "representative_line_id": representative,
            "claim_ids": _sorted_unique(
                claim_id
                for line_id in ordered
                for claim_id in _as_tuple(
                    identity_by_id[line_id]["identity_dimensions"]["claim_ids"]
                )
            ),
            "strand": identity_by_id[representative]["identity_dimensions"]["strand"],
            "polarity": identity_by_id[representative]["polarity"],
            "collapse_reasons": collapse_reasons,
        }
        clusters.append(cluster)
    return sorted(clusters, key=lambda cluster: min(_text_values(cluster.get("line_ids"))))


def _graded_calculus(
    identities: Sequence[Mapping[str, Any]],
    *,
    hard_edges: Sequence[Mapping[str, Any]],
    feature_flags: Mapping[str, bool] | None,
    governed_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    flags = dict(feature_flags or {})
    enabled = bool(flags.get(GRADED_INDEPENDENCE_FEATURE_FLAG, False))
    config = _validate_governed_config(governed_config) if enabled else dict(governed_config or {})
    weights = _weights_from_config(config) if enabled else {}
    hard_pairs = {tuple(_text_values(edge.get("line_ids"))) for edge in hard_edges}
    pairwise: list[dict[str, Any]] = []
    if enabled:
        for left_index, left in enumerate(identities):
            for right in identities[left_index + 1 :]:
                pairwise.append(
                    _pairwise_dependency(
                        left,
                        right,
                        weights=weights,
                        hard_pairs=hard_pairs,
                    )
                )
    return {
        "enabled": enabled,
        "feature_flag": GRADED_INDEPENDENCE_FEATURE_FLAG,
        "feature_flag_enabled": enabled,
        "authority_posture": "advisory_only" if enabled else "strict_hard_collapse_only",
        "governed_config": config if config else {"status": "not_configured"},
        "pairwise_model": PAIRWISE_MODEL_FORMULA,
        "pairwise_dependencies": pairwise,
        "may_not_use_for": ["support_inflation", "claim_authority_without_closeout"],
    }


def _pairwise_dependency(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    weights: Mapping[str, float],
    hard_pairs: set[tuple[str, ...]],
) -> dict[str, Any]:
    line_pair = (str(left["line_id"]), str(right["line_id"]))
    reverse_pair = (line_pair[1], line_pair[0])
    if not _same_context(left, right, require_same_polarity=False):
        return {
            "line_ids": list(line_pair),
            "collapse_eligible": False,
            "exclusion_reason": "different_claim_or_strand",
            "dependence_score": 0.0,
            "independence_score": 1.0,
            "overlap_contributions": [],
        }
    if left["polarity"] != right["polarity"]:
        return {
            "line_ids": list(line_pair),
            "collapse_eligible": False,
            "exclusion_reason": "counterevidence_preserved_separately",
            "dependence_score": 0.0,
            "independence_score": 1.0,
            "overlap_contributions": [],
        }
    hard_collapsed = line_pair in hard_pairs or reverse_pair in hard_pairs
    if hard_collapsed:
        return {
            "line_ids": list(line_pair),
            "collapse_eligible": True,
            "hard_collapse": True,
            "dependence_score": 1.0,
            "independence_score": 0.0,
            "overlap_contributions": [],
        }
    left_dims = _identity_dimensions(left)
    right_dims = _identity_dimensions(right)
    contributions: list[dict[str, Any]] = []
    dependence = 0.0
    for dimension, weight in weights.items():
        overlap = _overlap_score(left_dims.get(dimension), right_dims.get(dimension))
        if overlap <= 0.0:
            continue
        contribution = _round_float(weight * overlap)
        dependence += contribution
        contributions.append(
            {
                "dimension": dimension,
                "weight": _round_float(weight),
                "overlap": _round_float(overlap),
                "contribution": contribution,
            }
        )
    dependence = _round_float(min(MAX_PARTIAL_DEPENDENCE, dependence))
    return {
        "line_ids": list(line_pair),
        "collapse_eligible": True,
        "hard_collapse": False,
        "dependence_score": dependence,
        "independence_score": _round_float(1.0 - dependence),
        "overlap_contributions": contributions,
    }


def _mass_report(
    identities: Sequence[Mapping[str, Any]],
    *,
    hard_clusters: Sequence[Mapping[str, Any]],
    pairwise_dependencies: Sequence[Mapping[str, Any]],
    graded_enabled: bool,
) -> dict[str, Any]:
    cluster_by_line: dict[str, Mapping[str, Any]] = {}
    for cluster in hard_clusters:
        for line_id in _text_values(cluster.get("line_ids")):
            cluster_by_line[line_id] = cluster
    pair_independence = {
        tuple(_text_values(pair.get("line_ids"))): float(pair.get("independence_score", 1.0))
        for pair in pairwise_dependencies
    }
    ordered = sorted(
        identities,
        key=lambda identity: (-float(identity["quality"]), int(identity["ordinal"])),
    )
    selected_by_polarity: dict[str, list[str]] = {
        "support": [],
        "counterevidence": [],
        "context": [],
    }
    represented_clusters: set[str] = set()
    contributions: list[dict[str, Any]] = []
    mass_by_polarity = {"support": 0.0, "counterevidence": 0.0, "context": 0.0}
    for identity in ordered:
        line_id = str(identity["line_id"])
        polarity = str(identity["polarity"])
        cluster = cluster_by_line.get(line_id)
        cluster_id = str(cluster.get("cluster_id")) if cluster else line_id
        quality = float(identity["quality"])
        if cluster_id in represented_clusters and cluster.get("representative_line_id") != line_id:
            novelty = 0.0
        else:
            novelty = 1.0
            if graded_enabled and selected_by_polarity.get(polarity):
                novelty = min(
                    _pair_independence_score(line_id, selected, pair_independence)
                    for selected in selected_by_polarity[polarity]
                )
            represented_clusters.add(cluster_id)
            selected_by_polarity.setdefault(polarity, []).append(line_id)
        mass = _round_float(quality * novelty)
        mass_by_polarity[polarity] = _round_float(mass_by_polarity.get(polarity, 0.0) + mass)
        contributions.append(
            {
                "line_id": line_id,
                "polarity": polarity,
                "quality": _round_float(quality),
                "novelty": _round_float(novelty),
                "mass": mass,
                "formula": "quality(a) * novelty(a | S)",
            }
        )

    support_line_ids = _line_ids_by_polarity(identities, "support")
    counter_line_ids = _line_ids_by_polarity(identities, "counterevidence")
    context_line_ids = _line_ids_by_polarity(identities, "context")
    deficits: list[str] = []
    if len(identities) > len(hard_clusters):
        deficits.append("dependent_evidence_collapsed")
    if not support_line_ids:
        deficits.append("no_support_evidence")
    return {
        "raw_evidence_line_count": len(identities),
        "raw_support_line_count": len(support_line_ids),
        "raw_counterevidence_line_count": len(counter_line_ids),
        "raw_context_line_count": len(context_line_ids),
        "hard_effective_support_count": _hard_count_by_polarity(hard_clusters, "support"),
        "hard_effective_counterevidence_count": _hard_count_by_polarity(
            hard_clusters, "counterevidence"
        ),
        "hard_effective_context_count": _hard_count_by_polarity(hard_clusters, "context"),
        "graded_effective_support_mass": _round_float(mass_by_polarity["support"]),
        "graded_effective_counterevidence_mass": _round_float(mass_by_polarity["counterevidence"]),
        "graded_effective_context_mass": _round_float(mass_by_polarity["context"]),
        "line_contributions": contributions,
        "support_line_ids": support_line_ids,
        "counterevidence_line_ids": counter_line_ids,
        "context_line_ids": context_line_ids,
        "limiting_deficits": deficits,
        "raw_count_authority": "diagnostic_only",
        "aggregation_formula": "sum_a quality(a) * novelty(a | S)",
    }


def _scarcity_path(
    context: Mapping[str, Any] | None,
    *,
    effective_support_mass: float,
) -> dict[str, Any]:
    if context is None:
        return {
            "status": "not_rare_domain",
            "support_inflation_allowed": False,
            "effective_support_mass_after_scarcity": _round_float(effective_support_mass),
            "authority_effect": "none",
            "closeout_path": "none",
        }
    status = (
        _text(context.get("scarcity_kind"))
        or _text(context.get("status"))
        or (
            "scarcity_structural"
            if bool(context.get("is_rare_domain", False))
            else "not_rare_domain"
        )
    )
    after = _round_float(
        _float_or_default(
            context.get("effective_support_mass_after_scarcity"),
            default=effective_support_mass,
        )
    )
    path = {
        "status": status,
        "support_inflation_allowed": False,
        "effective_support_mass_after_scarcity": after,
        "authority_effect": _scarcity_authority_effect(status),
        "closeout_path": _scarcity_closeout_path(status),
    }
    for key in (
        "limitation_ref",
        "accepted_deficit_ref",
        "monitoring_plan_ref",
        "next_acquisition_action_ref",
        "minimum_effective_independent_evidence_count",
        "review_status",
    ):
        if key in context:
            path[key] = context[key]
    return path


def _validate_hard_clusters(value: object) -> list[dict[str, Any]]:
    rows = list(_mapping_sequence(value))
    if value is None:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_clusters_missing",
            "Effective-independence graph must include hard collapse clusters.",
            "hard_collapse_clusters",
        )
    normalized: list[dict[str, Any]] = []
    for index, cluster in enumerate(rows):
        row = dict(cluster)
        row["cluster_id"] = _required_text(
            row.get("cluster_id"),
            f"hard_collapse_clusters[{index}].cluster_id",
            "policy_design_effective_independence_cluster_id_missing",
        )
        row["line_ids"] = list(_text_values(row.get("line_ids")))
        if not row["line_ids"]:
            raise EffectiveIndependenceGraphError(
                "policy_design_effective_independence_cluster_line_ids_missing",
                "Hard collapse clusters must name their evidence lines.",
                f"hard_collapse_clusters[{index}].line_ids",
            )
        row["raw_line_count"] = _required_nonnegative_int(
            row.get("raw_line_count"),
            f"hard_collapse_clusters[{index}].raw_line_count",
            "policy_design_effective_independence_cluster_raw_count_missing",
        )
        if row["raw_line_count"] != len(row["line_ids"]):
            raise EffectiveIndependenceGraphError(
                "policy_design_effective_independence_cluster_raw_count_mismatch",
                "Hard cluster raw count must match its line ids.",
                f"hard_collapse_clusters[{index}].raw_line_count",
            )
        row["effective_line_count"] = _required_nonnegative_int(
            row.get("effective_line_count"),
            f"hard_collapse_clusters[{index}].effective_line_count",
            "policy_design_effective_independence_cluster_effective_count_missing",
        )
        if row["raw_line_count"] > 1 and not row.get("collapse_reasons"):
            raise EffectiveIndependenceGraphError(
                "policy_design_effective_independence_collapse_reasons_missing",
                "Hard-collapsed clusters must report collapse reasons.",
                f"hard_collapse_clusters[{index}].collapse_reasons",
            )
        normalized.append(row)
    return normalized


def _validate_graded_calculus(value: object, *, raw_count: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_graded_calculus_missing",
            "Effective-independence graph must include graded calculus posture.",
            "graded_calculus",
        )
    row = dict(value)
    row["enabled"] = bool(row.get("enabled", False))
    row["feature_flag"] = _required_text(
        row.get("feature_flag"),
        "graded_calculus.feature_flag",
        "policy_design_effective_independence_feature_flag_missing",
    )
    row["pairwise_model"] = _required_text(
        row.get("pairwise_model"),
        "graded_calculus.pairwise_model",
        "policy_design_effective_independence_pairwise_model_missing",
    )
    pairs = list(_mapping_sequence(row.get("pairwise_dependencies")))
    if row["enabled"] and raw_count > 1 and not pairs:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_pairwise_dependencies_missing",
            "Enabled graded calculus must report pairwise dependencies.",
            "graded_calculus.pairwise_dependencies",
        )
    row["pairwise_dependencies"] = pairs
    return row


def _validate_mass_report(
    value: object,
    *,
    raw_count: int,
    hard_count: int,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_mass_report_missing",
            "Effective-independence graph must include a mass report.",
            "mass_report",
        )
    row = dict(value)
    if (
        _required_nonnegative_int(
            row.get("raw_evidence_line_count"),
            "mass_report.raw_evidence_line_count",
            "policy_design_effective_independence_mass_raw_count_missing",
        )
        != raw_count
    ):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_mass_raw_count_mismatch",
            "Mass report raw count must match graph raw count.",
            "mass_report.raw_evidence_line_count",
        )
    hard_total = sum(
        _required_nonnegative_int(
            row.get(key),
            f"mass_report.{key}",
            f"policy_design_effective_independence_{key}_missing",
        )
        for key in (
            "hard_effective_support_count",
            "hard_effective_counterevidence_count",
            "hard_effective_context_count",
        )
    )
    if hard_total != hard_count:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_mass_hard_count_mismatch",
            "Mass report hard polarity counts must match hard effective line count.",
            "mass_report",
        )
    for key in (
        "graded_effective_support_mass",
        "graded_effective_counterevidence_mass",
        "graded_effective_context_mass",
    ):
        row[key] = _required_nonnegative_float(
            row.get(key),
            f"mass_report.{key}",
            f"policy_design_effective_independence_{key}_missing",
        )
    if row["graded_effective_support_mass"] > _required_nonnegative_int(
        row.get("raw_support_line_count"),
        "mass_report.raw_support_line_count",
        "policy_design_effective_independence_raw_support_count_missing",
    ):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_support_mass_exceeds_raw",
            "Graded support mass cannot exceed raw support line count.",
            "mass_report.graded_effective_support_mass",
        )
    row["raw_count_authority"] = _required_text(
        row.get("raw_count_authority"),
        "mass_report.raw_count_authority",
        "policy_design_effective_independence_raw_count_authority_missing",
    )
    if row["raw_count_authority"] != "diagnostic_only":
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_raw_count_authority_invalid",
            "Raw evidence-line count must remain diagnostic-only.",
            "mass_report.raw_count_authority",
        )
    row["limiting_deficits"] = list(_text_values(row.get("limiting_deficits")))
    return row


def _validate_scarcity_path(value: object, *, effective_support_mass: float) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_scarcity_missing",
            "Effective-independence graph must include scarcity path.",
            "scarcity_path",
        )
    row = dict(value)
    status = _required_text(
        row.get("status"),
        "scarcity_path.status",
        "policy_design_effective_independence_scarcity_status_missing",
    )
    if status not in _VALID_SCARCITY_STATUSES:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_scarcity_status_invalid",
            "Scarcity status is not recognized.",
            "scarcity_path.status",
        )
    if bool(row.get("support_inflation_allowed", True)):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_scarcity_support_inflation",
            "Scarcity cannot inflate independent support.",
            "scarcity_path.support_inflation_allowed",
        )
    after = _required_nonnegative_float(
        row.get("effective_support_mass_after_scarcity"),
        "scarcity_path.effective_support_mass_after_scarcity",
        "policy_design_effective_independence_scarcity_mass_missing",
    )
    if after > effective_support_mass:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_scarcity_support_inflation",
            "Scarcity cannot increase effective support mass.",
            "scarcity_path.effective_support_mass_after_scarcity",
        )
    if status == "scarcity_structural" and not any(
        _text(row.get(key))
        for key in ("limitation_ref", "accepted_deficit_ref", "monitoring_plan_ref")
    ):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_structural_scarcity_surface_missing",
            "Structural scarcity must surface a limitation, accepted deficit, or monitor.",
            "scarcity_path",
        )
    if status == "scarcity_remediable" and not _text(row.get("next_acquisition_action_ref")):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_remediable_scarcity_action_missing",
            "Remediable scarcity must point to a next acquisition action.",
            "scarcity_path.next_acquisition_action_ref",
        )
    row["status"] = status
    row["support_inflation_allowed"] = False
    row["effective_support_mass_after_scarcity"] = after
    return row


def _validate_governed_config(config: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config, Mapping):
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_graded_config_missing",
            "Enabled graded independence requires governed config.",
            "graded_independence_config",
        )
    normalized = dict(config)
    for key in ("owner", "version", "status"):
        normalized[key] = _required_text(
            normalized.get(key),
            f"graded_independence_config.{key}",
            f"policy_design_effective_independence_graded_config_{key}_missing",
        )
    if normalized["status"] not in _VALID_CONFIG_STATUSES:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_graded_config_status_invalid",
            "Governed graded-independence config status is not recognized.",
            "graded_independence_config.status",
        )
    if not isinstance(normalized.get("weights"), Mapping) or not normalized["weights"]:
        raise EffectiveIndependenceGraphError(
            "policy_design_effective_independence_graded_weights_missing",
            "Governed graded-independence config must include weights.",
            "graded_independence_config.weights",
        )
    normalized["weights"] = dict(normalized["weights"])
    return normalized


def _weights_from_config(config: Mapping[str, Any]) -> dict[str, float]:
    weights: dict[str, float] = {}
    raw = config.get("weights")
    if not isinstance(raw, Mapping):
        return weights
    for dimension, value in raw.items():
        dimension_name = str(dimension).strip()
        if dimension_name not in EVIDENCE_LINE_IDENTITY_DIMENSIONS:
            continue
        weight = _required_nonnegative_float(
            value,
            f"graded_independence_config.weights.{dimension_name}",
            "policy_design_effective_independence_graded_weight_invalid",
        )
        if weight > 0.0:
            weights[dimension_name] = weight
    return weights


def _collapse_reason(reason_code: str, dimension: str, values: Iterable[str]) -> dict[str, Any]:
    return {
        "reason_code": reason_code,
        "dimension": dimension,
        "values": _sorted_unique(values),
        "collapse_policy": "strict_hard_collapse",
    }


def _annotate_claim(
    claim: object,
    *,
    graph_ref: str,
    claim_ids: set[str],
    summary: Mapping[str, Any],
) -> object:
    if not isinstance(claim, Mapping):
        return claim
    row = dict(claim)
    local_claim_ids = set(
        _text_values(row.get("claim_ids") or row.get("claim_id") or row.get("id"))
    )
    if claim_ids and local_claim_ids and claim_ids.isdisjoint(local_claim_ids):
        return row
    row["effective_independence_refs"] = list(
        _unique((*_text_values(row.get("effective_independence_refs")), graph_ref))
    )
    row["effective_independence_summary"] = dict(summary)
    return row


def _same_context(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    require_same_polarity: bool,
) -> bool:
    left_dims = _identity_dimensions(left)
    right_dims = _identity_dimensions(right)
    if require_same_polarity and left.get("polarity") != right.get("polarity"):
        return False
    claim_overlap = set(_as_tuple(left_dims.get("claim_ids"))).intersection(
        _as_tuple(right_dims.get("claim_ids"))
    )
    return bool(claim_overlap) and left_dims.get("strand") == right_dims.get("strand")


def _is_legal_context(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_dims = _identity_dimensions(left)
    right_dims = _identity_dimensions(right)
    return (left_dims.get("strand") == "legal" and right_dims.get("strand") == "legal") or bool(
        _overlap_values(left_dims, right_dims, "controlling_legal_instrument")
    )


def _is_simulation_context(
    left_dims: Mapping[str, Any],
    right_dims: Mapping[str, Any],
) -> bool:
    left_values = {
        value.lower() for value in _as_tuple(left_dims.get("simulation_dgp"))
    } - _EMPTY_SIMULATION_MARKERS
    right_values = {
        value.lower() for value in _as_tuple(right_dims.get("simulation_dgp"))
    } - _EMPTY_SIMULATION_MARKERS
    return bool(left_values and right_values)


def _same_llm_generation_path(
    left_dims: Mapping[str, Any],
    right_dims: Mapping[str, Any],
) -> bool:
    left_values = tuple(value for value in _as_tuple(left_dims.get("llm_generation_path")) if value)
    right_values = tuple(
        value for value in _as_tuple(right_dims.get("llm_generation_path")) if value
    )
    if len(left_values) < 3 or len(right_values) < 3:
        return False
    return left_values == right_values and not {"none", "not_applicable"}.intersection(
        {value.lower() for value in left_values}
    )


def _identity_dimensions(identity: Mapping[str, Any]) -> dict[str, Any]:
    value = identity.get("identity_dimensions")
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _line_quality(line: Mapping[str, Any]) -> float:
    for key in ("quality_score", "quality", "evidence_quality", "method_quality"):
        value = line.get(key)
        if value is None:
            continue
        try:
            quality = float(value)
        except (TypeError, ValueError):
            continue
        return _round_float(max(0.0, min(1.0, quality)))
    return 1.0


def _line_polarity(line: Mapping[str, Any]) -> str:
    value = _clean_text(
        line.get("polarity")
        or line.get("evidence_polarity")
        or line.get("stance")
        or line.get("support_polarity")
        or line.get("direction")
    ).lower()
    normalized = value.replace("-", "_").replace(" ", "_")
    if normalized in _COUNTEREVIDENCE_TOKENS or any(
        token in normalized for token in _COUNTEREVIDENCE_TOKENS
    ):
        return "counterevidence"
    if normalized in _CONTEXT_TOKENS:
        return "context"
    return "support"


def _line_ids_by_polarity(
    identities: Sequence[Mapping[str, Any]],
    polarity: str,
) -> list[str]:
    return sorted(
        str(identity["line_id"]) for identity in identities if identity["polarity"] == polarity
    )


def _hard_count_by_polarity(
    hard_clusters: Sequence[Mapping[str, Any]],
    polarity: str,
) -> int:
    return sum(1 for cluster in hard_clusters if cluster.get("polarity") == polarity)


def _pair_independence_score(
    line_id: str,
    selected_line_id: str,
    pair_independence: Mapping[tuple[str, ...], float],
) -> float:
    return pair_independence.get(
        (line_id, selected_line_id),
        pair_independence.get((selected_line_id, line_id), 1.0),
    )


def _overlap_values(
    left_dims: Mapping[str, Any],
    right_dims: Mapping[str, Any],
    dimension: str,
) -> tuple[str, ...]:
    left = set(_as_tuple(left_dims.get(dimension)))
    right = set(_as_tuple(right_dims.get(dimension)))
    return tuple(sorted(left.intersection(right)))


def _overlap_score(left: object, right: object) -> float:
    left_values = set(_as_tuple(left))
    right_values = set(_as_tuple(right))
    if not left_values or not right_values:
        return 0.0
    return len(left_values.intersection(right_values)) / len(left_values.union(right_values))


def _method_family_from_method_id(line: Mapping[str, Any]) -> tuple[str, ...]:
    method_id = _text(line.get("method_id") or line.get("method_ref"))
    if method_id is None:
        return ()
    parts = [part for part in method_id.split(".") if part]
    if len(parts) >= 2:
        return (parts[-2],)
    return (method_id,)


def _values_from_line(line: Mapping[str, Any], *paths: str | tuple[str, str]) -> tuple[str, ...]:
    values: list[str] = []
    for path in paths:
        if isinstance(path, str):
            values.extend(_text_values(line.get(path)))
            continue
        current: object = line
        for key in path:
            if not isinstance(current, Mapping):
                current = None
                break
            current = current.get(key)
        values.extend(_text_values(current))
    return tuple(dict.fromkeys(values))


def _first_text_from_line(line: Mapping[str, Any], *paths: str | tuple[str, str]) -> str | None:
    values = _values_from_line(line, *paths)
    return values[0] if values else None


def _jsonable_dimensions(dimensions: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key, value in dimensions.items():
        if isinstance(value, tuple):
            payload[key] = list(value)
        elif isinstance(value, list | str | int | float | bool) or value is None:
            payload[key] = value
        elif isinstance(value, Mapping):
            payload[key] = {str(inner_key): inner_value for inner_key, inner_value in value.items()}
        else:
            payload[key] = str(value)
    if "underlying_study" not in payload:
        payload["underlying_study"] = []
    return payload


def _mapping_sequence(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, Mapping))


def _deep_copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, Mapping):
            copied[str(key)] = _deep_copy_mapping(item)
        elif isinstance(item, list):
            copied[str(key)] = [
                _deep_copy_mapping(element) if isinstance(element, Mapping) else element
                for element in item
            ]
        else:
            copied[str(key)] = item
    return copied


def _scarcity_authority_effect(status: str | None) -> str:
    if status == "scarcity_structural":
        return "lower_authority_or_limitation"
    if status == "scarcity_remediable":
        return "additional_acquisition_required"
    return "none"


def _scarcity_closeout_path(status: str | None) -> str:
    if status == "scarcity_structural":
        return "lower_authority_closeout_or_reviewed_single_line_deficit"
    if status == "scarcity_remediable":
        return "remediate_before_stronger_closeout"
    return "none"


def _required_nonnegative_int(value: object, field: str, code: str) -> int:
    if isinstance(value, bool) or value is None:
        raise EffectiveIndependenceGraphError(
            code,
            f"Effective-independence graph must include {field}.",
            field,
        )
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise EffectiveIndependenceGraphError(
            code,
            f"Effective-independence graph must include integer {field}.",
            field,
        ) from exc
    if count < 0:
        raise EffectiveIndependenceGraphError(
            code,
            f"Effective-independence graph {field} cannot be negative.",
            field,
        )
    return count


def _required_nonnegative_float(value: object, field: str, code: str) -> float:
    if isinstance(value, bool) or value is None:
        raise EffectiveIndependenceGraphError(
            code,
            f"Effective-independence graph must include {field}.",
            field,
        )
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EffectiveIndependenceGraphError(
            code,
            f"Effective-independence graph must include numeric {field}.",
            field,
        ) from exc
    if number < 0.0:
        raise EffectiveIndependenceGraphError(
            code,
            f"Effective-independence graph {field} cannot be negative.",
            field,
        )
    return number


def _float_or_default(value: object, *, default: float) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, number)


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise EffectiveIndependenceGraphError(
            code,
            f"Effective-independence graph must include {field}.",
            field,
        )
    return text


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _text(value: object) -> str | None:
    text = _clean_text(value)
    return text or None


def _text_values(value: object) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(value, str):
        text = _text(value)
        if text is not None:
            values.append(text)
    elif isinstance(value, Mapping):
        for key in sorted(value):
            item = value[key]
            if isinstance(item, Mapping | list | tuple | set):
                values.extend(_text_values(item))
            else:
                text = _text(item) or _text(key)
                if text is not None:
                    values.append(text)
    elif isinstance(value, list | tuple | set):
        for item in value:
            values.extend(_text_values(item))
    return tuple(dict.fromkeys(values))


def _as_tuple(value: object) -> tuple[str, ...]:
    return _text_values(value)


def _sorted_unique(values: Iterable[object]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _round_float(value: float) -> float:
    return round(float(value), 6)
