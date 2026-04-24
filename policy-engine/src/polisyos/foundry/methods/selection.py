"""Rank, explain, and package Foundry catalog candidates for planners and authoring tools."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from polisyos.core.contracts.execution_plan import (
    MethodCatalogEntry,
    MethodCatalogSnapshot,
    MethodDagNode,
)
from polisyos.core.observability.truthfulness import (
    parse_truthfulness_tier,
    reconcile_truthfulness_tiers,
    truthfulness_depth,
)
from polisyos.foundry.methods.base import parse_fqn
from polisyos.foundry.methods.catalog_snapshot import build_method_capability_matrix
from polisyos.foundry.methods.linker import check_linkable
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.selection_history import (
    ADVISOR_EXECUTION_CONTEXT_PARAM,
    AdvisorExecutionContext,
    RuntimePredictor,
    SelectionHistoryStore,
    fit_runtime_predictor_from_history,
    get_global_selection_history,
)
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope

_FIDELITY_ORDER = {"low": 0, "medium": 1, "high": 2}
_IMPLEMENTATION_DEPTH = {
    "heuristic_baseline": 0,
    "structural_scoring": 1,
    "frontier_trainable": 2,
    "production_method": 3,
}

COST_PER_MS: float = 0.001
"""Default cost per millisecond for VOI / budget calculations."""

_DEFAULT_REGRET_CONFIDENCE = 0.95
_REGRET_STATUS_VALID = "VALID"
_REGRET_STATUS_AMBIGUOUS = "AMBIGUOUS_RANK"
_REGRET_STATUS_BROKEN = "BROKEN"
_REGRET_STATUS_RETRAIN = "RETRAIN_REQUIRED"
_REGRET_STATUS_INSUFFICIENT = "INSUFFICIENT_LOGGING"
_SHIFT_NONE = "NONE"
_SHIFT_POSSIBLE = "POSSIBLE"
_SHIFT_DETECTED = "DETECTED"
_TIER_SOURCE_STATIC = "static_catalog"
_COMPARATOR_SPEC = "best_feasible_method_in_highest_admissible_tier_in_hindsight"
_MIN_LOGGING_SUFFICIENCY = 0.35
_SHIFT_POSSIBLE_THRESHOLD = 0.18
_SHIFT_DETECTED_THRESHOLD = 0.30
_TIER_SOURCE_RUNTIME = "runtime_validated"


@dataclass(frozen=True, slots=True)
class MethodLossProfile:
    """Decision-theoretic proxy loss used by the advisor regret certificate."""

    profile_id: str
    coverage_weight: float
    tier_weight: float
    time_weight: float
    failure_weight: float
    coverage_floor: float | None = None
    runtime_budget_ms: float | None = None


@dataclass(frozen=True, slots=True)
class ConfidenceSequence:
    """Time-uniform proxy interval used for runtime regret diagnostics."""

    lower: float
    estimate: float
    upper: float
    confidence_level: float
    observations: int
    estimator: str
    anytime_valid: bool = True


@dataclass(frozen=True, slots=True)
class ActiveSetSummary:
    """Availability and logging sufficiency summary for advisor diagnostics."""

    catalog_size: int
    feasible_count: int
    comparator_count: int
    mean_available_actions: float
    exploration_floor: float | None
    logging_sufficiency: float


@dataclass(frozen=True, slots=True)
class CalibratedRegretCertificate:
    """Typed verdict-quality surface for advisor rankings."""

    loss_profile_id: str
    tier_source: str
    comparator_spec: str
    assumption_class: str
    confidence_level: float
    horizon_observations: int
    certified_regret_upper: float | None
    observed_regret_cs: ConfidenceSequence | None
    top1_vs_top2_gap_cs: ConfidenceSequence | None
    ope_estimator: str
    ope_bias_budget: float
    active_set_summary: ActiveSetSummary
    shift_status: str
    status: str
    trigger_reason: str
    evidence_artifact_ref: str | None = None
    query_fingerprint: str | None = None


_LOSS_PROFILE_LIBRARY: dict[str, MethodLossProfile] = {
    "balanced": MethodLossProfile(
        profile_id="balanced",
        coverage_weight=0.35,
        tier_weight=0.20,
        time_weight=0.20,
        failure_weight=0.25,
    ),
    "coverage_strict": MethodLossProfile(
        profile_id="coverage_strict",
        coverage_weight=0.45,
        tier_weight=0.25,
        time_weight=0.10,
        failure_weight=0.20,
    ),
    "latency_sensitive": MethodLossProfile(
        profile_id="latency_sensitive",
        coverage_weight=0.20,
        tier_weight=0.15,
        time_weight=0.40,
        failure_weight=0.25,
    ),
}


@dataclass(frozen=True, slots=True)
class DataCharacteristics:
    """
    Characteristics of the analysis dataset for data-aware method scoring.

    When provided to ``rank_method_catalog_entries()``, methods whose
    ``typical_min_obs`` exceeds the available observations are penalised.
    Instrument/running-variable availability is used to boost or penalise
    methods that require them.
    """

    n_obs: int | None = None
    """Total number of observations available."""
    n_units: int | None = None
    """Number of cross-sectional units (for panel data)."""
    n_periods: int | None = None
    """Number of time periods (for panel/time-series data)."""
    has_instrument: bool = False
    """Whether a valid instrumental variable is available."""
    has_running_variable: bool = False
    """Whether a forcing/running variable is available (for RDD)."""
    is_panel: bool = False
    """Whether the data has a panel structure (unit × time)."""
    treatment_is_binary: bool | None = None
    """True = binary treatment; False = continuous; None = unknown."""
    outcome_is_continuous: bool | None = None
    """True = continuous outcome; False = discrete; None = unknown."""


@dataclass(frozen=True, slots=True)
class MethodSelectionCriteria:
    """Preferences used when planners or docs rank candidate methods."""

    preferred_kind: str | None = None
    preferred_family: str | None = None
    preferred_variant: str | None = None
    family_prefixes: tuple[str, ...] = ()
    preferred_execution_backends: tuple[str, ...] = ()
    required_data_modalities: tuple[str, ...] = ()
    preferred_data_modalities: tuple[str, ...] = ()
    preferred_determinism_tier: str | None = None
    minimum_fidelity_tier: str | None = None
    runnable_only: bool = True
    exclude_fqns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "family_prefixes", _normalize_tokens(self.family_prefixes))
        object.__setattr__(
            self,
            "preferred_execution_backends",
            _normalize_tokens(self.preferred_execution_backends),
        )
        object.__setattr__(
            self,
            "required_data_modalities",
            _normalize_tokens(self.required_data_modalities),
        )
        object.__setattr__(
            self,
            "preferred_data_modalities",
            _normalize_tokens(self.preferred_data_modalities),
        )
        object.__setattr__(self, "exclude_fqns", _normalize_tokens(self.exclude_fqns))


@dataclass(frozen=True, slots=True)
class MethodAdvisorQuery:
    """Structured query for the method advisor surface."""

    criteria: MethodSelectionCriteria = field(default_factory=MethodSelectionCriteria)
    data: DataCharacteristics | None = None
    runtime_budget_ms: float | None = None
    limit: int = 5
    runnable_only: bool = True
    loss_profile_id: str = "balanced"
    coverage_floor: float | None = None
    confidence_level: float = _DEFAULT_REGRET_CONFIDENCE


@dataclass(frozen=True, slots=True)
class MethodAdvisorResult:
    """Machine-readable advisor answer for planners, docs, and CLIs."""

    query: MethodAdvisorQuery
    recommended: tuple[MethodCatalogEntry, ...]
    payload: tuple[dict[str, object], ...]
    capability_matrix: tuple[dict[str, object], ...]
    family_summary: tuple[dict[str, object], ...]
    calibrated_regret_certificate: CalibratedRegretCertificate | None = None
    score_trace: tuple[MethodScoreTraceEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class MethodScoreTraceEntry:
    """One ranked candidate emitted for advisor diagnostics and telemetry."""

    rank: int
    fqn: str
    advisor_score: float
    truthfulness_tier: str | None
    truthfulness_depth_score: int
    execution_backend: str
    family: str
    variant: str
    runnable: bool


@dataclass(frozen=True, slots=True)
class MethodRankKey:
    """Lexicographic key with truthfulness as the primary ranking dimension."""

    truthfulness_depth: int
    score_rest: float
    fqn: str


def advise_methods(
    catalog: MethodCatalogSnapshot,
    query: MethodAdvisorQuery,
    *,
    history: SelectionHistoryStore | None = None,
    runtime_predictor: RuntimePredictor | None = None,
) -> MethodAdvisorResult:
    """Answer “which methods apply to my problem?” with ranked code-facing artifacts."""
    criteria = query.criteria
    if query.runnable_only and not criteria.runnable_only:
        criteria = MethodSelectionCriteria(
            preferred_kind=criteria.preferred_kind,
            preferred_family=criteria.preferred_family,
            preferred_variant=criteria.preferred_variant,
            family_prefixes=criteria.family_prefixes,
            preferred_execution_backends=criteria.preferred_execution_backends,
            required_data_modalities=criteria.required_data_modalities,
            preferred_data_modalities=criteria.preferred_data_modalities,
            preferred_determinism_tier=criteria.preferred_determinism_tier,
            minimum_fidelity_tier=criteria.minimum_fidelity_tier,
            runnable_only=True,
            exclude_fqns=criteria.exclude_fqns,
        )

    history, runtime_predictor = _resolve_evidence_sources(history, runtime_predictor)
    enriched_entries = tuple(
        _apply_truthfulness_overlay(entry, history) for entry in catalog.entries
    )
    scored_entries = _rank_entries_with_scores(
        enriched_entries,
        criteria,
        data=query.data,
        history=history,
        runtime_predictor=runtime_predictor,
        runtime_budget_ms=query.runtime_budget_ms,
    )
    recommended = tuple(entry for entry, _ in scored_entries[: max(0, int(query.limit))])
    score_trace = tuple(
        MethodScoreTraceEntry(
            rank=index + 1,
            fqn=entry.fqn,
            advisor_score=float(score),
            truthfulness_tier=entry.truthfulness_tier,
            truthfulness_depth_score=_truthfulness_depth_score(entry.truthfulness_tier),
            execution_backend=entry.execution_backend,
            family=entry.family,
            variant=entry.variant,
            runnable=bool(entry.runnable),
        )
        for index, (entry, score) in enumerate(scored_entries)
    )
    score_lookup = {entry.fqn: score for entry, score in scored_entries}
    payload = tuple(method_selection_payload(recommended, score_lookup=score_lookup))
    enriched_catalog = catalog.model_copy(update={"entries": list(enriched_entries)})
    capability_rows = build_method_capability_matrix(
        enriched_catalog, runnable_only=query.runnable_only
    )
    capability_lookup = {row["fqn"]: row for row in capability_rows}
    family_summary = tuple(
        {
            "family": family,
            "count": len(entries),
            "truthfulness_tiers": sorted({entry.truthfulness_tier for entry in entries}),
            "deepest_truthfulness_tier": _deepest_truthfulness_tier(entries),
            "truthfulness_depth_score": max(
                (_truthfulness_depth_score(entry.truthfulness_tier) for entry in entries),
                default=0,
            ),
            "implementation_depth_tiers": sorted(
                {entry.implementation_depth_tier for entry in entries}
            ),
            "deepest_implementation_depth_tier": _deepest_implementation_depth_tier(entries),
            "catalog_depth_score": max(
                (_implementation_depth_score(entry.implementation_depth_tier) for entry in entries),
                default=0,
            ),
            "frontier_method_count": sum(
                1 for entry in entries if entry.implementation_depth_tier == "frontier_trainable"
            ),
        }
        for family, entries in sorted(_group_by_family(recommended).items())
    )
    certificate = _build_calibrated_regret_certificate(
        catalog_size=len(catalog.entries),
        query=query,
        scored_entries=scored_entries,
        recommended=recommended,
        history=history,
        runtime_predictor=runtime_predictor,
    )
    return MethodAdvisorResult(
        query=query,
        recommended=recommended,
        payload=payload,
        capability_matrix=tuple(
            capability_lookup[entry.fqn] for entry in recommended if entry.fqn in capability_lookup
        ),
        family_summary=family_summary,
        calibrated_regret_certificate=certificate,
        score_trace=score_trace,
    )


def build_advisor_execution_context(
    result: MethodAdvisorResult,
    *,
    selected_fqn: str | None = None,
    selection_propensity: float | None = None,
    shadow_loss_estimates: Mapping[str, float] | None = None,
) -> AdvisorExecutionContext | None:
    """Build typed execution telemetry from an advisor result."""

    if not result.score_trace and not result.recommended:
        return None
    ordered_fqns = tuple(item.fqn for item in result.score_trace) or tuple(
        entry.fqn for entry in result.recommended
    )
    if not ordered_fqns:
        return None
    selected_fqn = selected_fqn or ordered_fqns[0]
    score_vector = {item.fqn: float(item.advisor_score) for item in result.score_trace}
    rank_lookup = {item.fqn: int(item.rank) for item in result.score_trace}
    certificate = result.calibrated_regret_certificate
    return AdvisorExecutionContext(
        query_fingerprint=(
            _query_fingerprint(result.query)
            if certificate is None or not certificate.query_fingerprint
            else certificate.query_fingerprint
        ),
        loss_profile_id=(
            result.query.loss_profile_id if certificate is None else certificate.loss_profile_id
        ),
        candidate_fqns=ordered_fqns,
        selected_rank=rank_lookup.get(selected_fqn),
        selection_propensity=selection_propensity,
        advisor_score_vector=score_vector,
        shadow_loss_estimates={
            str(fqn): _clip_unit(loss) for fqn, loss in (shadow_loss_estimates or {}).items()
        },
    )


def attach_advisor_execution_context(
    params: Mapping[str, Any] | None,
    result: MethodAdvisorResult,
    *,
    selected_fqn: str | None = None,
    selection_propensity: float | None = None,
    shadow_loss_estimates: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Attach advisor telemetry to dispatch params under the reserved internal key."""

    payload = dict(params or {})
    context = build_advisor_execution_context(
        result,
        selected_fqn=selected_fqn,
        selection_propensity=selection_propensity,
        shadow_loss_estimates=shadow_loss_estimates,
    )
    if context is not None:
        payload[ADVISOR_EXECUTION_CONTEXT_PARAM] = context.model_dump(mode="json")
    return payload


def rank_method_catalog_entries(
    entries: Iterable[MethodCatalogEntry],
    criteria: MethodSelectionCriteria,
    *,
    limit: int | None = None,
    data: DataCharacteristics | None = None,
    history: SelectionHistoryStore | None = None,
    runtime_predictor: RuntimePredictor | None = None,
    runtime_budget_ms: float | None = None,
) -> list[MethodCatalogEntry]:
    """Score and sort catalog entries for planners, CLIs, and authoring flows."""
    ranked = _rank_entries_with_scores(
        entries,
        criteria,
        data=data,
        history=history,
        runtime_predictor=runtime_predictor,
        runtime_budget_ms=runtime_budget_ms,
    )
    if limit is None:
        return [entry for entry, _ in ranked]
    return [entry for entry, _ in ranked[: max(0, int(limit))]]


def _rank_entries_with_scores(
    entries: Iterable[MethodCatalogEntry],
    criteria: MethodSelectionCriteria,
    *,
    data: DataCharacteristics | None = None,
    history: SelectionHistoryStore | None = None,
    runtime_predictor: RuntimePredictor | None = None,
    runtime_budget_ms: float | None = None,
) -> list[tuple[MethodCatalogEntry, float]]:
    """Score and sort catalog entries, preserving score trace for diagnostics."""
    history, runtime_predictor = _resolve_evidence_sources(history, runtime_predictor)

    use_evidence = history is not None or (
        runtime_predictor is not None and runtime_budget_ms is not None
    )
    scored: list[tuple[MethodRankKey, MethodCatalogEntry]] = []
    for raw_entry in entries:
        entry = _apply_truthfulness_overlay(raw_entry, history)
        if entry.fqn in criteria.exclude_fqns:
            continue
        if criteria.runnable_only and entry.runnable is False:
            continue
        if criteria.required_data_modalities and not set(
            criteria.required_data_modalities
        ).issubset(set(entry.data_modalities)):
            continue
        if criteria.minimum_fidelity_tier is not None:
            required_rank = _FIDELITY_ORDER.get(criteria.minimum_fidelity_tier, -1)
            entry_rank = _FIDELITY_ORDER.get(entry.fidelity_tier, -1)
            if entry_rank < required_rank:
                continue
        if use_evidence:
            score = _score_entry_v2(
                entry,
                criteria,
                history=history,
                runtime_predictor=runtime_predictor,
                runtime_budget_ms=runtime_budget_ms,
                data=data,
            )
        else:
            score = _score_entry(entry, criteria)
        if data is not None:
            score += _score_data_characteristics(entry, data)
        if score > float("-inf"):
            scored.append(
                (
                    MethodRankKey(
                        truthfulness_depth=_truthfulness_depth_score(entry.truthfulness_tier),
                        score_rest=score,
                        fqn=entry.fqn,
                    ),
                    entry,
                )
            )

    scored.sort(key=lambda item: (-item[0].truthfulness_depth, -item[0].score_rest, item[0].fqn))
    return [(entry, rank_key.score_rest) for rank_key, entry in scored]


def suggest_alternative_methods(
    catalog: MethodCatalogSnapshot,
    *,
    target_entry: MethodCatalogEntry | None = None,
    target_fqn: str | None = None,
    limit: int = 3,
) -> list[MethodCatalogEntry]:
    """Recommend drop-in alternatives when a target catalog entry is unsuitable or unavailable."""
    resolved_target = target_entry
    if resolved_target is None and target_fqn:
        resolved_target = next(
            (entry for entry in catalog.entries if entry.fqn == target_fqn), None
        )

    if resolved_target is not None:
        preferred_modalities = tuple(resolved_target.data_modalities)
        family_prefixes = _family_prefixes(resolved_target.family)
        criteria = MethodSelectionCriteria(
            preferred_kind=resolved_target.kind,
            preferred_family=resolved_target.family,
            preferred_variant=resolved_target.variant,
            family_prefixes=family_prefixes,
            preferred_execution_backends=(resolved_target.execution_backend,),
            required_data_modalities=(),
            preferred_data_modalities=preferred_modalities,
            preferred_determinism_tier=resolved_target.determinism_tier,
            minimum_fidelity_tier=resolved_target.fidelity_tier,
            runnable_only=True,
            exclude_fqns=(resolved_target.fqn,),
        )
        return rank_method_catalog_entries(catalog.entries, criteria, limit=limit)

    family = None
    variant = None
    if target_fqn:
        try:
            namespace, name, _ = parse_fqn(target_fqn)
            family = namespace
            variant = name
        except ValueError:
            family = None
            variant = None
    criteria = MethodSelectionCriteria(
        preferred_family=family,
        preferred_variant=variant,
        family_prefixes=_family_prefixes(family),
        runnable_only=True,
    )
    return rank_method_catalog_entries(catalog.entries, criteria, limit=limit)


def method_selection_payload(
    entries: Sequence[MethodCatalogEntry],
    *,
    score_lookup: Mapping[str, float] | None = None,
) -> list[dict[str, object]]:
    """Serialize ranked catalog entries into an LLM- and UI-friendly payload."""
    payload: list[dict[str, object]] = []
    for entry in entries:
        item: dict[str, object] = {
            "fqn": entry.fqn,
            "kind": entry.kind,
            "family": entry.family,
            "variant": entry.variant,
            "execution_backend": entry.execution_backend,
            "data_modalities": list(entry.data_modalities),
            "fidelity_tier": entry.fidelity_tier,
            "determinism_tier": entry.determinism_tier,
            "truthfulness_tier": entry.truthfulness_tier,
            "truthfulness_depth_score": _truthfulness_depth_score(entry.truthfulness_tier),
            "implementation_depth_tier": entry.implementation_depth_tier,
            "implementation_depth_score": _implementation_depth_score(
                entry.implementation_depth_tier
            ),
            "declared_truthfulness_tier": entry.declared_truthfulness_tier,
            "runtime_truthfulness_tier": entry.runtime_truthfulness_tier,
            "effective_truthfulness_tier": entry.effective_truthfulness_tier,
            "truthfulness_status": entry.truthfulness_status,
            "truthfulness_scope": entry.truthfulness_scope,
            "truthfulness_evidence_ref": entry.truthfulness_evidence_ref,
            "runnable": entry.runnable,
            "disabled_reasons": list(entry.disabled_reasons),
            "dependency_posture": dict(entry.dependency_posture),
        }
        if score_lookup is not None and entry.fqn in score_lookup:
            item["advisor_score"] = float(score_lookup[entry.fqn])
        if entry.implementation_depth_notes:
            item["implementation_depth_notes"] = entry.implementation_depth_notes
        if entry.truthfulness_notes:
            item["truthfulness_notes"] = entry.truthfulness_notes
        # Include rich semantic fields when non-empty to enrich LLM context
        if entry.description:
            item["description"] = entry.description
        if entry.when_to_use:
            item["when_to_use"] = entry.when_to_use
        if entry.when_not_to_use:
            item["when_not_to_use"] = entry.when_not_to_use
        if entry.citations:
            item["citations"] = list(entry.citations)
        if entry.assumptions:
            item["assumptions"] = list(entry.assumptions)
        if entry.prerequisites:
            item["prerequisites"] = list(entry.prerequisites)
        if entry.diagnostic_checks:
            item["diagnostic_checks"] = list(entry.diagnostic_checks)
        if entry.typical_min_obs is not None:
            item["typical_min_obs"] = entry.typical_min_obs
        if entry.output_interpretation:
            item["output_interpretation"] = entry.output_interpretation
        payload.append(item)
    return payload


def suggest_adapter_methods(
    catalog: MethodCatalogSnapshot,
    *,
    source_fqn: str | None = None,
    target_fqn: str | None = None,
    source_signature: Any = None,
    target_signature: Any = None,
    limit: int = 3,
    registry: MethodRegistry | None = None,
    exclude_fqns: Sequence[str] = (),
) -> list[MethodCatalogEntry]:
    """Find runnable adapter methods that can bridge source and target signatures."""
    reg = registry or MethodRegistry.get_instance()
    source_sig = source_signature or _signature_for_fqn(reg, source_fqn)
    target_sig = target_signature or _signature_for_fqn(reg, target_fqn)
    if source_sig is None or target_sig is None:
        return []

    excluded = set(_normalize_tokens(exclude_fqns))
    if source_fqn:
        excluded.add(str(source_fqn))
    if target_fqn:
        excluded.add(str(target_fqn))

    ranked: list[tuple[float, MethodCatalogEntry]] = []
    for entry in catalog.entries:
        if entry.fqn in excluded:
            continue
        if entry.runnable is False:
            continue
        candidate_sig = _signature_for_fqn(reg, entry.fqn)
        if candidate_sig is None:
            continue
        if not check_linkable(source_sig, candidate_sig):
            continue
        if not check_linkable(candidate_sig, target_sig):
            continue
        score = _adapter_score(
            entry,
            source_signature=source_sig,
            candidate_signature=candidate_sig,
            target_signature=target_sig,
        )
        ranked.append((score, entry))

    ranked.sort(key=lambda item: (-item[0], item[1].fqn))
    return [entry for _, entry in ranked[: max(0, int(limit))]]


def suggest_plan_node_alternatives(
    catalog: MethodCatalogSnapshot,
    *,
    node: MethodDagNode,
    plan_nodes: Sequence[MethodDagNode],
    target_entry: MethodCatalogEntry | None = None,
    target_fqn: str | None = None,
    limit: int = 3,
    registry: MethodRegistry | None = None,
) -> list[MethodCatalogEntry]:
    """Re-rank substitutes for a DAG node using upstream and downstream compatibility."""
    candidate_limit = max(int(limit) * 8, 24)
    candidates = suggest_alternative_methods(
        catalog,
        target_entry=target_entry,
        target_fqn=target_fqn,
        limit=candidate_limit,
    )
    if not candidates:
        return []

    reg = registry or MethodRegistry.get_instance()
    node_by_id = {item.node_id: item for item in plan_nodes}
    downstream_nodes = tuple(
        item for item in plan_nodes if node.node_id in set(item.depends_on or [])
    )
    upstream_signatures = tuple(
        signature
        for signature in (
            _signature_for_node(reg, node_by_id.get(dep_id)) for dep_id in node.depends_on or []
        )
        if signature is not None
    )
    downstream_signatures = tuple(
        signature
        for signature in (_signature_for_node(reg, item) for item in downstream_nodes)
        if signature is not None
    )
    target_signature = _signature_for_fqn(reg, node.method_fqn)

    rescored: list[tuple[float, MethodCatalogEntry]] = []
    for index, candidate in enumerate(candidates):
        score = float(len(candidates) - index)
        score += _plan_node_score(
            reg,
            candidate,
            node=node,
            upstream_signatures=upstream_signatures,
            downstream_signatures=downstream_signatures,
            target_signature=target_signature,
        )
        rescored.append((score, candidate))
    rescored.sort(key=lambda item: (-item[0], item[1].fqn))
    return [entry for _, entry in rescored[: max(0, int(limit))]]


def authoring_catalog_payload(
    catalog: MethodCatalogSnapshot,
    *,
    limit_families: int = 12,
    per_family: int = 2,
) -> dict[str, Any]:
    """Build a compact family-centric snapshot for catalog authoring and prompting."""
    ranked = rank_method_catalog_entries(
        catalog.entries,
        MethodSelectionCriteria(runnable_only=True),
    )
    grouped: dict[str, list[MethodCatalogEntry]] = defaultdict(list)
    for entry in ranked:
        grouped[entry.family].append(entry)

    families: list[dict[str, Any]] = []
    for family in sorted(
        grouped,
        key=lambda item: (
            grouped[item][0].kind,
            item,
        ),
    ):
        if len(families) >= max(1, int(limit_families)):
            break
        sample = grouped[family][: max(1, int(per_family))]
        families.append(
            {
                "family": family,
                "kind": sample[0].kind,
                "data_modalities": sorted(
                    {modality for entry in sample for modality in entry.data_modalities}
                ),
                "methods": method_selection_payload(sample),
            }
        )

    unavailable = [entry for entry in catalog.entries if entry.runnable is False]
    return {
        "source_schema_version": catalog.schema_version,
        "snapshot_id": catalog.snapshot_id,
        "runnable_method_count": sum(1 for entry in catalog.entries if entry.runnable),
        "unavailable_method_count": len(unavailable),
        "capability_matrix_rows": len(build_method_capability_matrix(catalog, runnable_only=False)),
        "recommended_families": families,
        "notable_unavailable_families": sorted(
            {entry.family for entry in unavailable[: max(1, int(limit_families))]}
        ),
    }


def _group_by_family(entries: Sequence[MethodCatalogEntry]) -> dict[str, list[MethodCatalogEntry]]:
    grouped: dict[str, list[MethodCatalogEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.family].append(entry)
    return grouped


def _apply_truthfulness_overlay(
    entry: MethodCatalogEntry,
    history: SelectionHistoryStore | None,
) -> MethodCatalogEntry:
    if history is None:
        return entry
    record = history.latest_record_for(entry.fqn)
    if record is None:
        return entry
    runtime_tier = parse_truthfulness_tier(record.runtime_truthfulness_tier)
    if runtime_tier is None:
        return entry
    effective_tier, status = reconcile_truthfulness_tiers(
        entry.declared_truthfulness_tier,
        runtime_tier,
    )
    truthfulness_scope = record.truthfulness_scope or entry.truthfulness_scope
    updated_capability_matrix = dict(entry.capability_matrix)
    updated_capability_matrix.update(
        {
            "truthfulness_tier": effective_tier.value,
            "runtime_truthfulness_tier": runtime_tier.value,
            "effective_truthfulness_tier": effective_tier.value,
            "truthfulness_status": status.value,
            "truthfulness_scope": truthfulness_scope,
            "truthfulness_evidence_ref": record.truthfulness_evidence_ref,
        }
    )
    return entry.model_copy(
        update={
            "truthfulness_tier": effective_tier.value,
            "runtime_truthfulness_tier": runtime_tier.value,
            "effective_truthfulness_tier": effective_tier.value,
            "truthfulness_status": status.value,
            "truthfulness_scope": truthfulness_scope,
            "truthfulness_evidence_ref": record.truthfulness_evidence_ref,
            "capability_matrix": updated_capability_matrix,
        }
    )


def _truthfulness_depth_score(truthfulness_tier: str | None) -> int:
    depth = truthfulness_depth(truthfulness_tier)
    if depth > 0:
        return depth
    return _IMPLEMENTATION_DEPTH.get(str(truthfulness_tier or "").strip(), 0)


def _implementation_depth_score(implementation_depth_tier: str | None) -> int:
    return _IMPLEMENTATION_DEPTH.get(str(implementation_depth_tier or "").strip(), 0)


def _deepest_truthfulness_tier(entries: Sequence[MethodCatalogEntry]) -> str:
    best = max(
        entries,
        key=lambda entry: (
            _truthfulness_depth_score(entry.truthfulness_tier),
            entry.truthfulness_tier,
        ),
        default=None,
    )
    if best is None:
        return "unverified"
    return best.truthfulness_tier


def _deepest_implementation_depth_tier(entries: Sequence[MethodCatalogEntry]) -> str:
    best = max(
        entries,
        key=lambda entry: (
            _implementation_depth_score(entry.implementation_depth_tier),
            entry.implementation_depth_tier,
        ),
        default=None,
    )
    if best is None:
        return "heuristic_baseline"
    return best.implementation_depth_tier


def _score_entry(entry: MethodCatalogEntry, criteria: MethodSelectionCriteria) -> float:
    score = 0.0

    if criteria.preferred_kind is not None:
        if entry.kind != criteria.preferred_kind:
            score -= 25.0
        else:
            score += 25.0

    if criteria.preferred_family is not None:
        if entry.family == criteria.preferred_family:
            score += 100.0
        elif entry.family.startswith(criteria.preferred_family):
            score += 60.0

    if criteria.preferred_variant is not None:
        if entry.variant == criteria.preferred_variant or entry.name == criteria.preferred_variant:
            score += 70.0

    family_prefix_bonus = 0.0
    for idx, prefix in enumerate(criteria.family_prefixes):
        if entry.family.startswith(prefix):
            family_prefix_bonus = max(family_prefix_bonus, 30.0 - float(idx))
    score += family_prefix_bonus

    if criteria.preferred_execution_backends:
        if entry.execution_backend in criteria.preferred_execution_backends:
            order = criteria.preferred_execution_backends.index(entry.execution_backend)
            score += 18.0 - float(order)
        else:
            score -= 8.0

    if criteria.preferred_data_modalities:
        overlap = set(criteria.preferred_data_modalities) & set(entry.data_modalities)
        score += 8.0 * float(len(overlap))

    if criteria.preferred_determinism_tier is not None:
        if entry.determinism_tier == criteria.preferred_determinism_tier:
            score += 6.0

    if criteria.minimum_fidelity_tier is not None:
        score += float(_FIDELITY_ORDER.get(entry.fidelity_tier, 0))

    if entry.runnable:
        score += 20.0
    score -= float(len(entry.disabled_reasons))
    return score


def _score_entry_v2(
    entry: MethodCatalogEntry,
    criteria: MethodSelectionCriteria,
    *,
    history: SelectionHistoryStore | None = None,
    runtime_predictor: RuntimePredictor | None = None,
    runtime_budget_ms: float | None = None,
    data: DataCharacteristics | None = None,
) -> float:
    """Score with evidence conditioning. Falls back to ``_score_entry`` when no history."""
    score = _score_entry(entry, criteria)

    if history is not None:
        sr = history.success_rate(entry.fqn)
        if sr is not None:
            score += 30.0 * sr
            score -= 15.0 * (1.0 - sr)
        quantiles = history.quality_quantiles(entry.fqn)
        if quantiles is not None:
            score += 20.0 * quantiles[1]  # median quality bonus

    if runtime_predictor is not None and runtime_budget_ms is not None:
        n_obs = data.n_obs if data and data.n_obs else 1000
        predicted = runtime_predictor.predict_ms(entry.fqn, n_obs)
        if predicted > runtime_budget_ms:
            score -= 50.0
        else:
            score += 10.0 * (1.0 - predicted / runtime_budget_ms)

    return score


def _score_data_characteristics(
    entry: MethodCatalogEntry,
    data: DataCharacteristics,
) -> float:
    """
    Adjust score based on observed data characteristics.

    Rewards methods that are well-suited to the available data;
    penalises methods whose requirements cannot be met.
    """
    score = 0.0

    # Penalise methods that need more observations than we have
    if data.n_obs is not None and entry.typical_min_obs is not None:
        if data.n_obs < entry.typical_min_obs:
            # Scale penalty: worse the further below minimum
            ratio = data.n_obs / max(entry.typical_min_obs, 1)
            score -= 20.0 * (1.0 - ratio)

    # IV methods: boost when instrument is available, penalise when not
    _iv_tags = {"iv", "instrumental_variable", "2sls", "gmm"}
    entry_tags = {t.lower() for t in entry.tags}
    is_iv_method = bool(_iv_tags & entry_tags) or "iv" in entry.family.lower()
    if is_iv_method:
        if data.has_instrument:
            score += 15.0
        else:
            score -= 20.0

    # RDD methods: boost when running variable available, penalise when not
    _rdd_tags = {"rdd", "regression_discontinuity", "kink_design"}
    is_rdd_method = bool(_rdd_tags & entry_tags) or "rdd" in entry.family.lower()
    if is_rdd_method:
        if data.has_running_variable:
            score += 15.0
        else:
            score -= 20.0

    # Panel methods: boost when panel structure available
    _panel_tags = {"panel", "did", "difference_in_differences", "fixed_effects"}
    is_panel_method = bool(_panel_tags & entry_tags) or "panel" in entry.family.lower()
    if is_panel_method and data.is_panel:
        score += 8.0

    # Cross-section methods: slight boost when only cross-section available
    _cross_section_tags = {"cross_section", "cross_sectional"}
    is_cs_method = bool(_cross_section_tags & entry_tags)
    if is_cs_method and not data.is_panel:
        score += 4.0

    return score


def _resolve_evidence_sources(
    history: SelectionHistoryStore | None,
    runtime_predictor: RuntimePredictor | None,
) -> tuple[SelectionHistoryStore | None, RuntimePredictor | None]:
    if history is not None or runtime_predictor is not None:
        return history, runtime_predictor
    default_history = get_global_selection_history()
    if len(default_history) == 0:
        return None, None
    return default_history, fit_runtime_predictor_from_history(default_history)


def _resolve_loss_profile(query: MethodAdvisorQuery) -> MethodLossProfile:
    base = _LOSS_PROFILE_LIBRARY.get(query.loss_profile_id, _LOSS_PROFILE_LIBRARY["balanced"])
    return MethodLossProfile(
        profile_id=base.profile_id,
        coverage_weight=base.coverage_weight,
        tier_weight=base.tier_weight,
        time_weight=base.time_weight,
        failure_weight=base.failure_weight,
        coverage_floor=query.coverage_floor,
        runtime_budget_ms=query.runtime_budget_ms,
    )


def _query_fingerprint(query: MethodAdvisorQuery) -> str:
    payload = {
        "criteria": {
            "preferred_kind": query.criteria.preferred_kind,
            "preferred_family": query.criteria.preferred_family,
            "preferred_variant": query.criteria.preferred_variant,
            "family_prefixes": list(query.criteria.family_prefixes),
            "preferred_execution_backends": list(query.criteria.preferred_execution_backends),
            "required_data_modalities": list(query.criteria.required_data_modalities),
            "preferred_data_modalities": list(query.criteria.preferred_data_modalities),
            "preferred_determinism_tier": query.criteria.preferred_determinism_tier,
            "minimum_fidelity_tier": query.criteria.minimum_fidelity_tier,
            "runnable_only": query.criteria.runnable_only,
            "exclude_fqns": list(query.criteria.exclude_fqns),
        },
        "data": None if query.data is None else asdict(query.data),
        "runtime_budget_ms": query.runtime_budget_ms,
        "limit": query.limit,
        "runnable_only": query.runnable_only,
        "loss_profile_id": query.loss_profile_id,
        "coverage_floor": query.coverage_floor,
        "confidence_level": query.confidence_level,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _build_calibrated_regret_certificate(
    *,
    catalog_size: int,
    query: MethodAdvisorQuery,
    scored_entries: Sequence[tuple[MethodCatalogEntry, float]],
    recommended: Sequence[MethodCatalogEntry],
    history: SelectionHistoryStore | None,
    runtime_predictor: RuntimePredictor | None,
) -> CalibratedRegretCertificate:
    confidence_level = min(max(float(query.confidence_level), 0.5), 0.999)
    loss_profile = _resolve_loss_profile(query)
    query_fingerprint = _query_fingerprint(query)
    feasible_entries = tuple(entry for entry, _ in scored_entries)
    feasible_fqns = {entry.fqn for entry in feasible_entries}
    comparator_entries = _highest_tier_entries(feasible_entries)
    relevant_records = _relevant_records(
        history,
        feasible_fqns,
        query_fingerprint=query_fingerprint,
        loss_profile_id=loss_profile.profile_id,
    )
    active_set_summary = _summarize_active_set(
        catalog_size=catalog_size,
        feasible_count=len(feasible_entries),
        comparator_count=len(comparator_entries),
        records=relevant_records,
    )
    ope_estimator = _ope_estimator(relevant_records)
    bias_budget = _ope_bias_budget(ope_estimator, active_set_summary.logging_sufficiency)
    tier_source = _tier_source(feasible_entries, relevant_records)

    if not recommended:
        return CalibratedRegretCertificate(
            loss_profile_id=loss_profile.profile_id,
            tier_source=tier_source,
            comparator_spec=_COMPARATOR_SPEC,
            assumption_class=_assumption_class(
                history=history,
                runtime_predictor=runtime_predictor,
                shift_status=_SHIFT_NONE,
            ),
            confidence_level=confidence_level,
            horizon_observations=0,
            certified_regret_upper=None,
            observed_regret_cs=None,
            top1_vs_top2_gap_cs=None,
            ope_estimator=ope_estimator,
            ope_bias_budget=bias_budget,
            active_set_summary=active_set_summary,
            shift_status=_SHIFT_NONE,
            status=_REGRET_STATUS_INSUFFICIENT,
            trigger_reason="no_feasible_methods",
            evidence_artifact_ref=_history_artifact_ref(history),
            query_fingerprint=query_fingerprint,
        )

    loss_stats = {
        entry.fqn: _loss_stats_for_method(
            entry=entry,
            query=query,
            profile=loss_profile,
            records=relevant_records,
            confidence_level=confidence_level,
        )
        for entry in feasible_entries
    }
    top1 = recommended[0]
    comparator = _best_comparator_entry(comparator_entries, loss_stats)
    regret_cs = _regret_confidence_sequence(
        selected_stats=loss_stats.get(top1.fqn),
        comparator_stats=loss_stats.get(comparator.fqn) if comparator is not None else None,
        confidence_level=confidence_level,
    )
    gap_cs = None
    if len(recommended) >= 2:
        gap_cs = _gap_confidence_sequence(
            first_stats=loss_stats.get(recommended[0].fqn),
            second_stats=loss_stats.get(recommended[1].fqn),
            confidence_level=confidence_level,
        )
    shift_status = _detect_shift(
        loss_samples=_loss_samples_for_method(
            top1.fqn,
            query=query,
            profile=loss_profile,
            records=relevant_records,
        )
    )
    assumption_class = _assumption_class(
        history=history,
        runtime_predictor=runtime_predictor,
        shift_status=shift_status,
    )
    certified_upper = _certified_regret_upper(
        horizon_observations=0 if regret_cs is None else regret_cs.observations,
        confidence_level=confidence_level,
        catalog_size=catalog_size,
        active_set_summary=active_set_summary,
        assumption_class=assumption_class,
        bias_budget=bias_budget,
    )
    status, trigger_reason = _certificate_status(
        regret_cs=regret_cs,
        gap_cs=gap_cs,
        shift_status=shift_status,
        logging_sufficiency=active_set_summary.logging_sufficiency,
        certified_regret_upper=certified_upper,
    )
    return CalibratedRegretCertificate(
        loss_profile_id=loss_profile.profile_id,
        tier_source=tier_source,
        comparator_spec=_COMPARATOR_SPEC,
        assumption_class=assumption_class,
        confidence_level=confidence_level,
        horizon_observations=0 if regret_cs is None else regret_cs.observations,
        certified_regret_upper=certified_upper,
        observed_regret_cs=regret_cs,
        top1_vs_top2_gap_cs=gap_cs,
        ope_estimator=ope_estimator,
        ope_bias_budget=bias_budget,
        active_set_summary=active_set_summary,
        shift_status=shift_status,
        status=status,
        trigger_reason=trigger_reason,
        evidence_artifact_ref=_history_artifact_ref(history),
        query_fingerprint=query_fingerprint,
    )


@dataclass(frozen=True, slots=True)
class _LossStats:
    mean: float
    lower: float
    upper: float
    observations: int


def _highest_tier_entries(entries: Sequence[MethodCatalogEntry]) -> tuple[MethodCatalogEntry, ...]:
    if not entries:
        return ()
    highest = max(_truthfulness_depth_score(entry.truthfulness_tier) for entry in entries)
    return tuple(
        entry for entry in entries if _truthfulness_depth_score(entry.truthfulness_tier) == highest
    )


def _best_comparator_entry(
    entries: Sequence[MethodCatalogEntry],
    loss_stats: Mapping[str, _LossStats | None],
) -> MethodCatalogEntry | None:
    ranked: list[tuple[float, float, str, MethodCatalogEntry]] = []
    for entry in entries:
        stats = loss_stats.get(entry.fqn)
        if stats is None:
            continue
        ranked.append((stats.mean, stats.upper, entry.fqn, entry))
    if ranked:
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        return ranked[0][3]
    return entries[0] if entries else None


def _relevant_records(
    history: SelectionHistoryStore | None,
    feasible_fqns: set[str],
    *,
    query_fingerprint: str,
    loss_profile_id: str,
) -> list[Any]:
    if history is None:
        return []
    relevant = []
    for record in history.all_records():
        if record.method_fqn in feasible_fqns:
            relevant.append(record)
            continue
        if feasible_fqns.intersection(record.shadow_loss_estimates):
            relevant.append(record)
    exact_query = [record for record in relevant if record.query_fingerprint == query_fingerprint]
    if exact_query:
        return exact_query
    matching_profile = [
        record for record in relevant if record.loss_profile_id in {None, loss_profile_id}
    ]
    if matching_profile:
        return matching_profile
    return relevant


def _summarize_active_set(
    *,
    catalog_size: int,
    feasible_count: int,
    comparator_count: int,
    records: Sequence[Any],
) -> ActiveSetSummary:
    candidate_sizes = [len(record.candidate_fqns) for record in records if record.candidate_fqns]
    mean_available_actions = (
        sum(candidate_sizes) / len(candidate_sizes) if candidate_sizes else float(feasible_count)
    )
    propensities = [
        float(record.selection_propensity)
        for record in records
        if record.selection_propensity is not None
    ]
    logging_signals = [
        1.0
        if (
            record.candidate_fqns
            and record.realized_loss_components
            and (record.selection_propensity is not None or bool(record.shadow_loss_estimates))
        )
        else 0.0
        for record in records
    ]
    logging_sufficiency = sum(logging_signals) / len(logging_signals) if logging_signals else 0.0
    return ActiveSetSummary(
        catalog_size=int(catalog_size),
        feasible_count=int(feasible_count),
        comparator_count=int(comparator_count),
        mean_available_actions=float(mean_available_actions),
        exploration_floor=min(propensities) if propensities else None,
        logging_sufficiency=float(logging_sufficiency),
    )


def _assumption_class(
    *,
    history: SelectionHistoryStore | None,
    runtime_predictor: RuntimePredictor | None,
    shift_status: str,
) -> str:
    if shift_status in {_SHIFT_POSSIBLE, _SHIFT_DETECTED}:
        return "piecewise_stationary"
    if runtime_predictor is not None and runtime_predictor.is_fitted:
        return "stationary_linear"
    return "stationary_regression_oracle"


def _tier_source(
    entries: Sequence[MethodCatalogEntry],
    records: Sequence[Any],
) -> str:
    if any(entry.runtime_truthfulness_tier for entry in entries):
        return _TIER_SOURCE_RUNTIME
    if any(record.runtime_truthfulness_tier for record in records):
        return _TIER_SOURCE_RUNTIME
    return _TIER_SOURCE_STATIC


def _ope_estimator(records: Sequence[Any]) -> str:
    if any(record.shadow_loss_estimates for record in records):
        return "shadow_replay"
    if any(
        record.selection_propensity is not None and record.realized_loss_components
        for record in records
    ):
        return "ips"
    return "empirical_proxy"


def _ope_bias_budget(ope_estimator: str, logging_sufficiency: float) -> float:
    if ope_estimator == "shadow_replay":
        return 0.0
    if ope_estimator == "ips":
        return max(0.0, 0.10 * (1.0 - logging_sufficiency))
    return max(0.15, 0.40 * (1.0 - logging_sufficiency))


def _loss_stats_for_method(
    *,
    entry: MethodCatalogEntry,
    query: MethodAdvisorQuery,
    profile: MethodLossProfile,
    records: Sequence[Any],
    confidence_level: float,
) -> _LossStats | None:
    losses = _loss_samples_for_method(entry.fqn, query=query, profile=profile, records=records)
    if not losses:
        return None
    mean = sum(losses) / len(losses)
    radius = _bounded_anytime_radius(len(losses), confidence_level)
    return _LossStats(
        mean=float(mean),
        lower=max(0.0, float(mean - radius)),
        upper=min(1.0, float(mean + radius)),
        observations=len(losses),
    )


def _loss_samples_for_method(
    fqn: str,
    *,
    query: MethodAdvisorQuery,
    profile: MethodLossProfile,
    records: Sequence[Any],
) -> list[float]:
    losses: list[float] = []
    for record in records:
        if record.method_fqn == fqn:
            direct = _loss_from_record(record, query=query, profile=profile)
            if direct is not None:
                losses.append(direct)
        shadow = record.shadow_loss_estimates.get(fqn)
        if shadow is not None:
            losses.append(_clip_unit(shadow))
    return losses


def _loss_from_record(
    record: Any,
    *,
    query: MethodAdvisorQuery,
    profile: MethodLossProfile,
) -> float | None:
    components = dict(record.realized_loss_components)
    coverage_shortfall = components.get("coverage_shortfall")
    if coverage_shortfall is None and record.output_quality is not None:
        coverage_shortfall = 1.0 - _clip_unit(record.output_quality)
        if profile.coverage_floor is not None:
            deficit = max(profile.coverage_floor - _clip_unit(record.output_quality), 0.0)
            denom = max(profile.coverage_floor, 1.0e-6)
            coverage_shortfall = deficit / denom

    tier_violation = components.get("tier_violation", 0.0)
    runtime_overrun = components.get("runtime_overrun")
    if (
        runtime_overrun is None
        and query.runtime_budget_ms is not None
        and query.runtime_budget_ms > 0
    ):
        runtime_overrun = (
            max(float(record.latency_ms) - query.runtime_budget_ms, 0.0) / query.runtime_budget_ms
        )
    if runtime_overrun is None:
        runtime_overrun = 0.0
    failure_penalty = components.get("failure_penalty")
    if failure_penalty is None:
        failure_penalty = 0.0 if record.success else 1.0

    seen_signal = (
        coverage_shortfall is not None
        or bool(components)
        or query.runtime_budget_ms is not None
        or not record.success
    )
    if not seen_signal:
        return None
    return _clip_unit(
        profile.coverage_weight
        * _clip_unit(0.0 if coverage_shortfall is None else coverage_shortfall)
        + profile.tier_weight * _clip_unit(tier_violation)
        + profile.time_weight * _clip_unit(runtime_overrun)
        + profile.failure_weight * _clip_unit(failure_penalty)
    )


def _bounded_anytime_radius(observations: int, confidence_level: float) -> float:
    if observations <= 0:
        return 1.0
    delta = max(1.0 - confidence_level, 1.0e-9)
    loglog = math.log(max(math.log2(float(observations) + 1.0), 1.0) + 1.0)
    return math.sqrt((math.log(2.0 / delta) + 1.5 * loglog) / (2.0 * observations))


def _regret_confidence_sequence(
    *,
    selected_stats: _LossStats | None,
    comparator_stats: _LossStats | None,
    confidence_level: float,
) -> ConfidenceSequence | None:
    if selected_stats is None or comparator_stats is None:
        return None
    horizon = min(selected_stats.observations, comparator_stats.observations)
    if horizon <= 0:
        return None
    estimate = (selected_stats.mean - comparator_stats.mean) * horizon
    lower = (selected_stats.lower - comparator_stats.upper) * horizon
    upper = (selected_stats.upper - comparator_stats.lower) * horizon
    return ConfidenceSequence(
        lower=float(lower),
        estimate=float(estimate),
        upper=float(upper),
        confidence_level=confidence_level,
        observations=horizon,
        estimator="empirical_hoeffding_anytime_proxy",
    )


def _gap_confidence_sequence(
    *,
    first_stats: _LossStats | None,
    second_stats: _LossStats | None,
    confidence_level: float,
) -> ConfidenceSequence | None:
    if first_stats is None or second_stats is None:
        return None
    observations = min(first_stats.observations, second_stats.observations)
    if observations <= 0:
        return None
    estimate = second_stats.mean - first_stats.mean
    lower = second_stats.lower - first_stats.upper
    upper = second_stats.upper - first_stats.lower
    return ConfidenceSequence(
        lower=float(lower),
        estimate=float(estimate),
        upper=float(upper),
        confidence_level=confidence_level,
        observations=observations,
        estimator="empirical_hoeffding_anytime_proxy",
    )


def _detect_shift(loss_samples: Sequence[float]) -> str:
    if len(loss_samples) < 8:
        return _SHIFT_NONE
    split = max(3, len(loss_samples) // 3)
    baseline = loss_samples[:-split]
    recent = loss_samples[-split:]
    if not baseline or not recent:
        return _SHIFT_NONE
    delta = abs((sum(recent) / len(recent)) - (sum(baseline) / len(baseline)))
    if delta >= _SHIFT_DETECTED_THRESHOLD:
        return _SHIFT_DETECTED
    if delta >= _SHIFT_POSSIBLE_THRESHOLD:
        return _SHIFT_POSSIBLE
    return _SHIFT_NONE


def _certified_regret_upper(
    *,
    horizon_observations: int,
    confidence_level: float,
    catalog_size: int,
    active_set_summary: ActiveSetSummary,
    assumption_class: str,
    bias_budget: float,
) -> float | None:
    if horizon_observations <= 0:
        return None
    delta = max(1.0 - confidence_level, 1.0e-9)
    d_eff = 4.0 if assumption_class == "stationary_linear" else 3.0
    context_term = d_eff * math.sqrt(
        horizon_observations * math.log((1.0 + horizon_observations) / delta)
    )
    if assumption_class == "piecewise_stationary":
        context_term *= 1.25
    sleeping_term = math.sqrt(
        max(active_set_summary.mean_available_actions, 1.0)
        * horizon_observations
        * math.log(max(float(catalog_size), 2.0) / delta)
    )
    return min(
        float(horizon_observations),
        float(context_term + sleeping_term + bias_budget),
    )


def _certificate_status(
    *,
    regret_cs: ConfidenceSequence | None,
    gap_cs: ConfidenceSequence | None,
    shift_status: str,
    logging_sufficiency: float,
    certified_regret_upper: float | None,
) -> tuple[str, str]:
    if regret_cs is None or certified_regret_upper is None:
        return _REGRET_STATUS_INSUFFICIENT, "insufficient_loss_observations"
    if logging_sufficiency < _MIN_LOGGING_SUFFICIENCY:
        return _REGRET_STATUS_INSUFFICIENT, "logging_sufficiency_below_threshold"
    if regret_cs.lower > certified_regret_upper:
        return _REGRET_STATUS_BROKEN, "observed_lower_regret_exceeds_certified_upper"
    if shift_status == _SHIFT_DETECTED:
        return _REGRET_STATUS_RETRAIN, "non_stationarity_detected"
    if gap_cs is not None and gap_cs.lower <= 0.0 <= gap_cs.upper:
        return _REGRET_STATUS_AMBIGUOUS, "top1_vs_top2_gap_crosses_zero"
    if shift_status == _SHIFT_POSSIBLE:
        return _REGRET_STATUS_RETRAIN, "possible_distribution_shift"
    return _REGRET_STATUS_VALID, "certificate_within_bound"


def _history_artifact_ref(history: SelectionHistoryStore | None) -> str | None:
    if history is None or history.persist_path is None:
        return None
    return str(history.persist_path)


def _clip_unit(value: float | int) -> float:
    return min(max(float(value), 0.0), 1.0)


def _family_prefixes(family: str | None) -> tuple[str, ...]:
    if not family:
        return ()
    parts = [part for part in str(family).split(".") if part]
    prefixes = [".".join(parts[:idx]) for idx in range(len(parts), 0, -1)]
    return _normalize_tokens(prefixes)


def _normalize_tokens(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result)


def _signature_for_node(
    registry: MethodRegistry,
    node: MethodDagNode | None,
):
    if node is None:
        return None
    return _signature_for_fqn(registry, node.method_fqn)


def _signature_for_fqn(registry: MethodRegistry, fqn: str | None):
    if not fqn:
        return None
    try:
        return registry.get(fqn).signature
    except Exception:
        return None


def _plan_node_score(
    registry: MethodRegistry,
    candidate: MethodCatalogEntry,
    *,
    node: MethodDagNode,
    upstream_signatures: Sequence[Any],
    downstream_signatures: Sequence[Any],
    target_signature: Any,
) -> float:
    candidate_signature = _signature_for_fqn(registry, candidate.fqn)
    if candidate_signature is None:
        return float("-inf")

    score = 0.0
    if (
        target_signature is not None
        and candidate_signature.input_slot_names == target_signature.input_slot_names
    ):
        score += 18.0
    if (
        target_signature is not None
        and candidate_signature.output_slot_names == target_signature.output_slot_names
    ):
        score += 18.0

    if node.backend:
        if candidate.execution_backend == str(node.backend):
            score += 12.0
        else:
            score -= 4.0

    requested_reads = {slot for slot in node.reads_slots if slot}
    requested_writes = {slot for slot in node.writes_slots if slot}
    score += 2.0 * len(requested_reads & set(candidate_signature.input_slot_names))
    score += 2.0 * len(requested_writes & set(candidate_signature.output_slot_names))

    if upstream_signatures:
        compatible_upstream = sum(
            1 for signature in upstream_signatures if check_linkable(signature, candidate_signature)
        )
        if compatible_upstream == len(upstream_signatures):
            score += 42.0
        else:
            score -= 25.0 * float(len(upstream_signatures) - compatible_upstream)

    if downstream_signatures:
        compatible_downstream = sum(
            1
            for signature in downstream_signatures
            if check_linkable(candidate_signature, signature)
        )
        if compatible_downstream == len(downstream_signatures):
            score += 38.0
        else:
            score -= 22.0 * float(len(downstream_signatures) - compatible_downstream)

    return score


def _adapter_score(
    entry: MethodCatalogEntry,
    *,
    source_signature: Any,
    candidate_signature: Any,
    target_signature: Any,
) -> float:
    score = 0.0
    if entry.kind == "pure":
        score += 8.0
    elif entry.kind == "simulation":
        score -= 12.0
    elif entry.kind == "mechanism":
        score -= 18.0

    score += 6.0 * len(
        set(candidate_signature.input_slot_names) & set(source_signature.output_slot_names)
    )
    score += 6.0 * len(
        set(candidate_signature.output_slot_names) & set(target_signature.input_slot_names)
    )
    score -= 1.5 * float(
        abs(len(candidate_signature.input_slot_names) - len(source_signature.output_slot_names))
    )
    score -= 1.5 * float(
        abs(len(candidate_signature.output_slot_names) - len(target_signature.input_slot_names))
    )
    if entry.determinism_tier == "library_deterministic":
        score += 4.0
    if entry.execution_backend == "numpy":
        score += 3.0
    return score


def compute_voi(
    current_uncertainty: UncertaintyEnvelope,
    method_expected_reduction: float,
    method_cost_ms: float,
    decision_value: float,
    *,
    cost_per_ms: float = COST_PER_MS,
) -> float:
    """Compute Value of Information for running an additional method.

    ``VOI = P(changes_decision) * decision_value - cost``

    where ``P = min(1.0, method_expected_reduction / ci_width)``
    and ``cost = method_cost_ms * cost_per_ms``.

    Returns positive VOI when expected information gain outweighs cost.
    """
    ci_width = current_uncertainty.ci_width
    if ci_width <= 0:
        return -method_cost_ms * cost_per_ms
    p_changes = min(1.0, method_expected_reduction / ci_width)
    return p_changes * decision_value - method_cost_ms * cost_per_ms


__all__ = [
    "COST_PER_MS",
    "ActiveSetSummary",
    "CalibratedRegretCertificate",
    "ConfidenceSequence",
    "DataCharacteristics",
    "MethodAdvisorQuery",
    "MethodAdvisorResult",
    "MethodLossProfile",
    "MethodScoreTraceEntry",
    "MethodSelectionCriteria",
    "advise_methods",
    "attach_advisor_execution_context",
    "authoring_catalog_payload",
    "build_advisor_execution_context",
    "compute_voi",
    "method_selection_payload",
    "rank_method_catalog_entries",
    "suggest_adapter_methods",
    "suggest_alternative_methods",
    "suggest_plan_node_alternatives",
]
