"""Rank, explain, and package Foundry catalog candidates for planners and authoring tools."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass, replace
from typing import Any, Literal

from polisyos.common.timestamps import utc_now
from polisyos.core.contracts.execution_plan import (
    BudgetSpec,
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
from polisyos.foundry.methods.consensus import (
    ConsensusTarget,
    CrossMethodConsensus,
    SupportsConsensusTarget,
    run_cross_method_consensus,
)
from polisyos.foundry.methods.cost_model import CostBudget, CostEstimate
from polisyos.foundry.methods.linker import check_linkable
from polisyos.foundry.methods.plan_optimizer import MethodCostModel
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

AdvisorCostPolicy = Literal["ignore", "annotate", "filter", "pareto"]
AdvisorDominanceMode = Literal["point", "robust"]
AdvisorOptimizationStatus = Literal[
    "PARETO_OPTIMAL",
    "INFEASIBLE_BUDGET",
    "NO_CANDIDATES",
    "NO_COST_MODEL",
    "ALL_COSTS_UNKNOWN",
    "COST_MODEL_OUT_OF_SCOPE",
    "NO_ACCURACY_ESTIMATE",
    "COST_MODEL_UNCERTAIN",
    "DEGRADED_NO_COST_MODEL",
    "ANNOTATED",
    "FILTERED",
]
CostBoundType = Literal[
    "EXACT_BOUND",
    "CALIBRATED_PROBABILISTIC_BOUND",
    "HEURISTIC_POINT_ESTIMATE",
    "UNKNOWN",
]
_COST_CERTIFIER_VERSION = "advisor-budget-certificate.v1"


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
    cost_policy: AdvisorCostPolicy = "ignore"
    cost_budget: CostBudget | BudgetSpec | Mapping[str, Any] | None = None
    risk_delta: float = 0.05
    return_certificate: bool = False
    dominance_mode: AdvisorDominanceMode = "point"
    allow_heuristic_cost_estimate: bool = True
    require_declared_accuracy_estimate: bool = False
    require_cross_method_consensus: bool = False
    minimum_consensus_methods: int = 2


@dataclass(frozen=True, slots=True)
class AdvisorValuePolicy:
    """Monotone scalar value policy applied only after Pareto frontier construction."""

    accuracy_weight: float = 1.0
    compute_weight: float = 0.0
    spend_weight: float = 0.0
    slack_weight: float = 0.0

    def value(self, score: CandidateScore) -> float:
        value = self.accuracy_weight * float(score.accuracy)
        value -= self.compute_weight * float(score.compute_upper)
        value -= self.spend_weight * float(score.spend_upper)
        if score.budget_slack is not None:
            value += self.slack_weight * float(score.budget_slack)
        return float(value)


@dataclass(frozen=True, slots=True)
class CandidateScore:
    """Cost/value score vector for one advisor candidate."""

    method_id: str
    accuracy: float
    accuracy_lower: float
    accuracy_upper: float
    advisor_score: float
    truthfulness_depth_score: int
    cost: CostEstimate
    spend_upper: float
    spend_lower: float
    compute_upper: float
    compute_lower: float
    budget_slack: float | None
    feasible: bool
    violations: tuple[str, ...] = ()
    constraint_violations: dict[str, float] = field(default_factory=dict)
    rank: int = 0
    bound_type: CostBoundType = "UNKNOWN"
    cost_known: bool = True
    cost_out_of_scope: bool = False
    accuracy_known: bool = True


@dataclass(frozen=True, slots=True)
class BudgetCertificate:
    """Optimization-style certificate for cost-aware method advice."""

    certificate_id: str
    selected_method_id: str | None
    budget: dict[str, object]
    estimated_cost_point: float
    estimated_cost_upper: float
    estimated_compute_upper: float | None
    slack_lower_bound: float | None
    feasible: bool
    confidence: float | None
    delta: float | None
    bound_type: CostBoundType
    cost_model_version: str
    cost_model_hash: str | None
    calibration_scope: str | None
    assumptions: tuple[str, ...]
    frontier_method_ids: tuple[str, ...]
    dominated_method_ids: tuple[str, ...]
    infeasible_method_ids: tuple[str, ...]
    constraint_violations: dict[str, float]
    proof_obligations: tuple[str, ...]
    verifier_version: str = _COST_CERTIFIER_VERSION
    created_at: str = field(default_factory=lambda: utc_now().isoformat())


@dataclass(frozen=True, slots=True)
class AdvisorOptimizationResult:
    """SciPy OptimizeResult-style surface for the cost-aware advisor layer."""

    x: str | None
    success: bool
    status: AdvisorOptimizationStatus
    message: str
    fun: float | None
    pareto_front: tuple[CandidateScore, ...]
    candidates: tuple[CandidateScore, ...]
    certificate: BudgetCertificate | None
    nfev: int
    maxcv: float
    diagnostics: dict[str, object] = field(default_factory=dict)


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
    advisor_optimization: AdvisorOptimizationResult | None = None
    cross_method_consensus: CrossMethodConsensus | None = None


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
    cost_policy: AdvisorCostPolicy | None = None,
    budget: CostBudget | BudgetSpec | Mapping[str, Any] | None = None,
    risk_delta: float | None = None,
    value_policy: AdvisorValuePolicy
    | Callable[[CandidateScore], float]
    | Mapping[str, float]
    | None = None,
    return_certificate: bool | None = None,
    method_cost_model: MethodCostModel | None = None,
    consensus_results: Sequence[SupportsConsensusTarget | ConsensusTarget | Mapping[str, Any]]
    | None = None,
) -> MethodAdvisorResult:
    """Answer “which methods apply to my problem?” with ranked code-facing artifacts."""
    if (
        cost_policy is not None
        or budget is not None
        or risk_delta is not None
        or return_certificate is not None
    ):
        query = replace(
            query,
            cost_policy=cost_policy if cost_policy is not None else query.cost_policy,
            cost_budget=budget if budget is not None else query.cost_budget,
            risk_delta=risk_delta if risk_delta is not None else query.risk_delta,
            return_certificate=(
                return_certificate if return_certificate is not None else query.return_certificate
            ),
        )
    if query.cost_policy != "ignore" and query.cost_policy not in {
        "annotate",
        "filter",
        "pareto",
    }:
        raise ValueError(f"Unknown advisor cost_policy: {query.cost_policy!r}")
    if query.dominance_mode not in {"point", "robust"}:
        raise ValueError(f"Unknown advisor dominance_mode: {query.dominance_mode!r}")
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
    advisor_optimization: AdvisorOptimizationResult | None = None
    cost_lookup: dict[str, CandidateScore] = {}
    if query.cost_policy != "ignore":
        scored_entries, advisor_optimization, cost_lookup = _apply_advisor_cost_policy(
            scored_entries,
            query=query,
            method_cost_model=method_cost_model,
            value_policy=value_policy,
        )
    candidate_recommended = tuple(entry for entry, _ in scored_entries[: max(0, int(query.limit))])
    consensus_input = tuple(consensus_results or ())
    cross_method_consensus = (
        None
        if consensus_results is None and not query.require_cross_method_consensus
        else run_cross_method_consensus(query, consensus_input)
    )
    if query.require_cross_method_consensus and cross_method_consensus is not None:
        insufficient = len(consensus_input) < max(
            2, int(query.minimum_consensus_methods)
        ) or cross_method_consensus.status in {"not_enough_methods", "not_comparable", "not_run"}
        if insufficient or not cross_method_consensus.recommendation_allowed:
            cross_method_consensus = replace(
                cross_method_consensus,
                recommendation_allowed=False,
                developer_message=(
                    f"{cross_method_consensus.developer_message}; strict_phase5_consensus_required"
                ),
                remediation=tuple(
                    dict.fromkeys(
                        (
                            *cross_method_consensus.remediation,
                            "Run at least two comparable methods before issuing analyst-facing advice.",
                        )
                    )
                ),
            )
    recommended = (
        ()
        if cross_method_consensus is not None and not cross_method_consensus.recommendation_allowed
        else candidate_recommended
    )
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
    payload_rows = method_selection_payload(recommended, score_lookup=score_lookup)
    if cost_lookup:
        _annotate_payload_with_costs(payload_rows, cost_lookup)
    payload = tuple(payload_rows)
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
        recommended=candidate_recommended,
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
        cross_method_consensus=cross_method_consensus,
        score_trace=score_trace,
        advisor_optimization=advisor_optimization,
    )


def advise_methods_for_analyst(
    catalog: MethodCatalogSnapshot,
    query: MethodAdvisorQuery,
    *,
    history: SelectionHistoryStore | None = None,
    runtime_predictor: RuntimePredictor | None = None,
    budget: CostBudget | BudgetSpec | Mapping[str, Any] | None = None,
    risk_delta: float | None = None,
    value_policy: AdvisorValuePolicy
    | Callable[[CandidateScore], float]
    | Mapping[str, float]
    | None = None,
    return_certificate: bool | None = None,
    method_cost_model: MethodCostModel | None = None,
    consensus_results: Sequence[SupportsConsensusTarget | ConsensusTarget | Mapping[str, Any]]
    | None = None,
) -> MethodAdvisorResult:
    """Strict Phase-5 advisor surface for analyst-facing recommendations."""

    effective_budget = budget if budget is not None else query.cost_budget
    analyst_query = replace(
        query,
        require_cross_method_consensus=True,
        minimum_consensus_methods=max(2, int(query.minimum_consensus_methods)),
        cost_policy="pareto" if effective_budget is not None else "annotate",
        cost_budget=effective_budget,
    )
    return advise_methods(
        catalog,
        analyst_query,
        history=history,
        runtime_predictor=runtime_predictor,
        budget=effective_budget,
        risk_delta=risk_delta,
        value_policy=value_policy,
        return_certificate=return_certificate,
        method_cost_model=method_cost_model,
        consensus_results=consensus_results,
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


@dataclass(frozen=True, slots=True)
class _ResolvedAdvisorBudget:
    spend_limit: float | None
    spend_unit: str
    compute_limit_ms: float | None
    run_limit_ms: float | None
    compile_limit_ms: float | None
    memory_limit_mb: float | None
    cost_per_ms: float
    payload: dict[str, object]

    @property
    def has_constraints(self) -> bool:
        return any(
            value is not None
            for value in (
                self.spend_limit,
                self.compute_limit_ms,
                self.run_limit_ms,
                self.compile_limit_ms,
                self.memory_limit_mb,
            )
        )


def _apply_advisor_cost_policy(
    scored_entries: Sequence[tuple[MethodCatalogEntry, float]],
    *,
    query: MethodAdvisorQuery,
    method_cost_model: MethodCostModel | None,
    value_policy: AdvisorValuePolicy
    | Callable[[CandidateScore], float]
    | Mapping[str, float]
    | None,
) -> tuple[
    list[tuple[MethodCatalogEntry, float]],
    AdvisorOptimizationResult,
    dict[str, CandidateScore],
]:
    budget = _resolve_advisor_budget(query)
    if not scored_entries:
        result = AdvisorOptimizationResult(
            x=None,
            success=False,
            status="NO_CANDIDATES",
            message="No candidate methods were available for cost-aware advice.",
            fun=None,
            pareto_front=(),
            candidates=(),
            certificate=None,
            nfev=0,
            maxcv=0.0,
            diagnostics={"cost_policy": query.cost_policy, "budget": budget.payload},
        )
        return [], result, {}
    if (
        query.cost_policy in {"filter", "pareto"}
        and not query.allow_heuristic_cost_estimate
        and not any(_declared_cost_metadata(entry) is not None for entry, _ in scored_entries)
    ):
        result = AdvisorOptimizationResult(
            x=None,
            success=False,
            status="NO_COST_MODEL",
            message=(
                "No declared cost estimates are available and heuristic cost estimates "
                "are disabled for this advisor query."
            ),
            fun=None,
            pareto_front=(),
            candidates=(),
            certificate=None,
            nfev=0,
            maxcv=0.0,
            diagnostics={"cost_policy": query.cost_policy, "budget": budget.payload},
        )
        return [], result, {}
    if (
        query.cost_policy in {"filter", "pareto"}
        and query.require_declared_accuracy_estimate
        and not any(_declared_accuracy_metadata(entry) is not None for entry, _ in scored_entries)
    ):
        result = AdvisorOptimizationResult(
            x=None,
            success=False,
            status="NO_ACCURACY_ESTIMATE",
            message="No declared accuracy estimates are available for cost-value selection.",
            fun=None,
            pareto_front=(),
            candidates=(),
            certificate=None,
            nfev=0,
            maxcv=0.0,
            diagnostics={"cost_policy": query.cost_policy, "budget": budget.payload},
        )
        return [], result, {}
    candidates = tuple(
        _candidate_score_from_entry(
            entry=entry,
            advisor_score=score,
            rank=index + 1,
            query=query,
            budget=budget,
            method_cost_model=method_cost_model,
        )
        for index, (entry, score) in enumerate(scored_entries)
    )
    cost_lookup = {candidate.method_id: candidate for candidate in candidates}
    if query.cost_policy in {"filter", "pareto"} and all(
        not candidate.cost_known for candidate in candidates
    ):
        certificate = _build_budget_certificate(
            selected=None,
            frontier=(),
            candidates=candidates,
            budget=budget,
            delta=query.risk_delta,
        )
        result = AdvisorOptimizationResult(
            x=None,
            success=False,
            status="ALL_COSTS_UNKNOWN",
            message="All candidates have unknown cost bounds; no budget-feasible choice is certified.",
            fun=None,
            pareto_front=(),
            candidates=candidates,
            certificate=certificate,
            nfev=len(candidates),
            maxcv=max((_max_constraint_violation(item) for item in candidates), default=0.0),
            diagnostics=_cost_policy_diagnostics(
                candidates=candidates,
                frontier=(),
                budget=budget,
                cost_policy=query.cost_policy,
            ),
        )
        return [], result, cost_lookup

    if query.cost_policy == "annotate":
        selected = candidates[0]
        certificate = (
            _build_budget_certificate(
                selected=selected,
                frontier=(),
                candidates=candidates,
                budget=budget,
                delta=query.risk_delta,
            )
            if query.return_certificate
            else None
        )
        result = AdvisorOptimizationResult(
            x=selected.method_id,
            success=True,
            status="ANNOTATED",
            message="Cost estimates were attached without filtering or Pareto pruning.",
            fun=None,
            pareto_front=(),
            candidates=candidates,
            certificate=certificate,
            nfev=len(candidates),
            maxcv=_max_constraint_violation(selected),
            diagnostics={"cost_policy": query.cost_policy, "budget": budget.payload},
        )
        return list(scored_entries), result, cost_lookup

    feasible = tuple(candidate for candidate in candidates if candidate.feasible)
    if feasible and all(candidate.cost_out_of_scope for candidate in feasible):
        certificate = _build_budget_certificate(
            selected=None,
            frontier=(),
            candidates=candidates,
            budget=budget,
            delta=query.risk_delta,
        )
        result = AdvisorOptimizationResult(
            x=None,
            success=False,
            status="COST_MODEL_OUT_OF_SCOPE",
            message="All budget-feasible candidates are outside their declared cost scope.",
            fun=None,
            pareto_front=(),
            candidates=candidates,
            certificate=certificate,
            nfev=len(candidates),
            maxcv=max((_max_constraint_violation(item) for item in candidates), default=0.0),
            diagnostics=_cost_policy_diagnostics(
                candidates=candidates,
                frontier=(),
                budget=budget,
                cost_policy=query.cost_policy,
            ),
        )
        return [], result, cost_lookup
    if not feasible:
        certificate = _build_budget_certificate(
            selected=None,
            frontier=(),
            candidates=candidates,
            budget=budget,
            delta=query.risk_delta,
        )
        result = AdvisorOptimizationResult(
            x=None,
            success=False,
            status="INFEASIBLE_BUDGET",
            message="No candidate satisfies the declared budget bound.",
            fun=None,
            pareto_front=(),
            candidates=candidates,
            certificate=certificate,
            nfev=len(candidates),
            maxcv=max((_max_constraint_violation(item) for item in candidates), default=0.0),
            diagnostics=_cost_policy_diagnostics(
                candidates=candidates,
                frontier=(),
                budget=budget,
                cost_policy=query.cost_policy,
            ),
        )
        return [], result, cost_lookup

    if query.cost_policy == "filter":
        feasible_ids = {candidate.method_id for candidate in feasible}
        filtered_entries = [
            (entry, score) for entry, score in scored_entries if entry.fqn in feasible_ids
        ]
        selected = feasible[0]
        certificate = _build_budget_certificate(
            selected=selected,
            frontier=feasible,
            candidates=candidates,
            budget=budget,
            delta=query.risk_delta,
        )
        result = AdvisorOptimizationResult(
            x=selected.method_id,
            success=True,
            status="FILTERED",
            message="Over-budget candidates were filtered before returning advisor rankings.",
            fun=None,
            pareto_front=feasible,
            candidates=candidates,
            certificate=certificate,
            nfev=len(candidates),
            maxcv=_max_constraint_violation(selected),
            diagnostics=_cost_policy_diagnostics(
                candidates=candidates,
                frontier=feasible,
                budget=budget,
                cost_policy=query.cost_policy,
            ),
        )
        return filtered_entries, result, cost_lookup

    frontier = _pareto_front(feasible, dominance_mode=query.dominance_mode)
    selected = _select_frontier_candidate(frontier, value_policy=value_policy)
    frontier_ids = {candidate.method_id for candidate in frontier}
    ordered_frontier_ids = [selected.method_id] + [
        candidate.method_id for candidate in frontier if candidate.method_id != selected.method_id
    ]
    order_lookup = {method_id: index for index, method_id in enumerate(ordered_frontier_ids)}
    frontier_entries = [
        (entry, score) for entry, score in scored_entries if entry.fqn in frontier_ids
    ]
    frontier_entries.sort(key=lambda item: order_lookup[item[0].fqn])
    fun = _evaluate_value_policy(selected, value_policy)
    certificate = _build_budget_certificate(
        selected=selected,
        frontier=frontier,
        candidates=candidates,
        budget=budget,
        delta=query.risk_delta,
    )
    result = AdvisorOptimizationResult(
        x=selected.method_id,
        success=True,
        status="PARETO_OPTIMAL",
        message=(
            "Selected method is budget-feasible and Pareto efficient under declared estimates."
        ),
        fun=fun,
        pareto_front=frontier,
        candidates=candidates,
        certificate=certificate,
        nfev=len(candidates),
        maxcv=_max_constraint_violation(selected),
        diagnostics=_cost_policy_diagnostics(
            candidates=candidates,
            frontier=frontier,
            budget=budget,
            cost_policy=query.cost_policy,
        ),
    )
    return frontier_entries, result, cost_lookup


def pareto_advise_methods(
    catalog: MethodCatalogSnapshot,
    query: MethodAdvisorQuery,
    *,
    history: SelectionHistoryStore | None = None,
    runtime_predictor: RuntimePredictor | None = None,
    value_policy: AdvisorValuePolicy
    | Callable[[CandidateScore], float]
    | Mapping[str, float]
    | None = None,
    method_cost_model: MethodCostModel | None = None,
) -> AdvisorOptimizationResult:
    """Return only the cost-aware Pareto optimization result for a finite candidate set."""
    result = advise_methods(
        catalog,
        replace(query, cost_policy="pareto"),
        history=history,
        runtime_predictor=runtime_predictor,
        value_policy=value_policy,
        method_cost_model=method_cost_model,
    )
    if result.advisor_optimization is None:
        raise RuntimeError("Pareto advisor did not produce an optimization result.")
    return result.advisor_optimization


def _candidate_score_from_entry(
    *,
    entry: MethodCatalogEntry,
    advisor_score: float,
    rank: int,
    query: MethodAdvisorQuery,
    budget: _ResolvedAdvisorBudget,
    method_cost_model: MethodCostModel | None,
) -> CandidateScore:
    cost = _estimate_method_cost(entry, query=query, method_cost_model=method_cost_model)
    bound_type = _normalize_bound_type(cost.bound_type)
    cost_known = bound_type != "UNKNOWN" and math.isfinite(cost.upper_bound(delta=query.risk_delta))
    cost_out_of_scope = _cost_estimate_out_of_scope(cost)
    accuracy, accuracy_lower, accuracy_upper, accuracy_known = _advisor_accuracy_interval(
        entry,
        advisor_score,
        require_declared=query.require_declared_accuracy_estimate,
    )
    compute_upper = float(cost.compute_upper_bound(delta=query.risk_delta))
    compute_lower = _compute_lower_bound(cost, delta=query.risk_delta)
    spend_upper = _spend_upper(cost, budget=budget, delta=query.risk_delta)
    spend_lower = _spend_lower(cost, budget=budget, delta=query.risk_delta)
    budget_slack = None
    violations: list[str] = []
    constraint_violations: dict[str, float] = {}
    if not cost_known:
        violations.append("cost_unknown")
        constraint_violations["cost_unknown"] = float("inf")
    if cost_out_of_scope:
        constraint_violations["cost_model_out_of_scope"] = 0.0
    if not accuracy_known:
        violations.append("accuracy_unknown")
        constraint_violations["accuracy_unknown"] = float("inf")
    if budget.spend_limit is not None:
        budget_slack = float(budget.spend_limit - spend_upper)
        violation = spend_upper - budget.spend_limit
        if violation > 0.0:
            violations.append("spend_limit")
            constraint_violations["spend_limit"] = float(violation)
    if budget.compute_limit_ms is not None:
        violation = compute_upper - budget.compute_limit_ms
        if budget_slack is None:
            budget_slack = float(budget.compute_limit_ms - compute_upper)
        if violation > 0.0:
            violations.append("compute_limit")
            constraint_violations["compute_limit"] = float(violation)
    vector = cost.resource_vector(delta=query.risk_delta)
    for label, limit, actual_key in (
        ("run_limit", budget.run_limit_ms, "run_ms"),
        ("compile_limit", budget.compile_limit_ms, "compile_ms"),
        ("memory_limit", budget.memory_limit_mb, "memory_mb"),
    ):
        if limit is None:
            continue
        violation = float(vector[actual_key]) - float(limit)
        if violation > 0.0:
            violations.append(label)
            constraint_violations[label] = float(violation)

    return CandidateScore(
        method_id=entry.fqn,
        accuracy=accuracy,
        accuracy_lower=accuracy_lower,
        accuracy_upper=accuracy_upper,
        advisor_score=float(advisor_score),
        truthfulness_depth_score=_truthfulness_depth_score(entry.truthfulness_tier),
        cost=cost,
        spend_upper=float(spend_upper),
        spend_lower=float(spend_lower),
        compute_upper=float(compute_upper),
        compute_lower=float(compute_lower),
        budget_slack=budget_slack,
        feasible=not violations,
        violations=tuple(violations),
        constraint_violations=constraint_violations,
        rank=int(rank),
        bound_type=bound_type,
        cost_known=cost_known,
        cost_out_of_scope=cost_out_of_scope,
        accuracy_known=accuracy_known,
    )


def _estimate_method_cost(
    entry: MethodCatalogEntry,
    *,
    query: MethodAdvisorQuery,
    method_cost_model: MethodCostModel | None,
) -> CostEstimate:
    declared = _declared_cost_metadata(entry)
    if declared is not None:
        return _cost_estimate_from_metadata(entry, declared)
    if not query.allow_heuristic_cost_estimate:
        return _unknown_method_cost(entry)

    model = method_cost_model or MethodCostModel()
    n_obs = _cost_model_n_obs(entry, query)
    estimated_ms, complexity_class = model.estimate(entry.fqn, {"observations": (n_obs,)})
    total_ms = max(0, int(math.ceil(estimated_ms)))
    return CostEstimate(
        point=float(total_ms),
        unit="ms",
        components={"estimated_ms": float(total_ms)},
        estimated_compile_ms=0,
        estimated_run_ms=total_ms,
        estimated_total_ms=total_ms,
        estimated_memory_mb=0,
        estimated_flops=0,
        confidence="low",
        lower=float(total_ms),
        upper=float(total_ms),
        bound_type="HEURISTIC_POINT_ESTIMATE",
        estimator_version="foundry.methods.MethodCostModel.v1",
        assumptions=[
            "Method-level heuristic from FQN complexity class and observed-row proxy; "
            "no calibrated coverage guarantee."
        ],
        valid_for={
            "method_fqn": entry.fqn,
            "n_obs": n_obs,
            "complexity_class": complexity_class,
        },
        includes_advisor_overhead=False,
    )


def _unknown_method_cost(entry: MethodCatalogEntry) -> CostEstimate:
    return CostEstimate(
        point=0.0,
        unit="ms",
        components={},
        estimated_compile_ms=0,
        estimated_run_ms=0,
        estimated_total_ms=0,
        estimated_memory_mb=0,
        estimated_flops=0,
        confidence="low",
        lower=0.0,
        upper=0.0,
        bound_type="UNKNOWN",
        estimator_version="none",
        assumptions=[f"No cost estimate is declared for {entry.fqn}."],
        valid_for={"method_fqn": entry.fqn},
        includes_advisor_overhead=False,
    )


def _declared_cost_metadata(entry: MethodCatalogEntry) -> Mapping[str, Any] | None:
    for source in (entry.capability_matrix, entry.dependency_posture, entry.effect_semantics):
        nested = source.get("advisor_cost") or source.get("cost_estimate")
        if isinstance(nested, Mapping):
            return nested
        if any(key in source for key in ("estimated_total_ms", "total_ms", "cost_ms")):
            return source
    return None


def _cost_estimate_from_metadata(
    entry: MethodCatalogEntry,
    metadata: Mapping[str, Any],
) -> CostEstimate:
    total_ms = _metadata_float(
        metadata,
        "estimated_total_ms",
        "total_ms",
        "cost_ms",
        "estimated_ms",
    )
    run_ms = _metadata_float(metadata, "estimated_run_ms", "run_ms")
    compile_ms = _metadata_float(metadata, "estimated_compile_ms", "compile_ms")
    if total_ms is None:
        total_ms = float((run_ms or 0.0) + (compile_ms or 0.0))
    if run_ms is None:
        run_ms = max(float(total_ms) - float(compile_ms or 0.0), 0.0)
    if compile_ms is None:
        compile_ms = max(float(total_ms) - float(run_ms or 0.0), 0.0)
    memory_mb = _metadata_float(metadata, "estimated_memory_mb", "memory_mb") or 0.0
    flops = _metadata_float(metadata, "estimated_flops", "flops") or 0.0
    upper = _metadata_float(metadata, "upper_ms", "total_ms_upper", "upper")
    lower = _metadata_float(metadata, "lower_ms", "total_ms_lower", "lower")
    coverage_confidence = _metadata_float(metadata, "coverage_confidence", "confidence_level")
    delta = _metadata_float(metadata, "delta")
    bound_type = _normalize_bound_type(str(metadata.get("bound_type", "HEURISTIC_POINT_ESTIMATE")))
    assumptions_raw = metadata.get("assumptions", ())
    assumptions = (
        tuple(str(item) for item in assumptions_raw)
        if isinstance(assumptions_raw, Sequence) and not isinstance(assumptions_raw, str)
        else (str(assumptions_raw),)
        if assumptions_raw
        else ()
    )
    raw_components = metadata.get("components", {})
    components = raw_components if isinstance(raw_components, Mapping) else {}
    raw_valid_for = metadata.get("valid_for", {})
    valid_for = dict(raw_valid_for) if isinstance(raw_valid_for, Mapping) else {}
    valid_for.setdefault("method_fqn", entry.fqn)
    if metadata.get("out_of_scope") is not None:
        valid_for["out_of_scope"] = bool(metadata.get("out_of_scope"))
    return CostEstimate(
        point=float(total_ms),
        unit=str(metadata.get("unit", "ms")),
        components={
            str(key): float(value)
            for key, value in components.items()
            if isinstance(value, int | float)
        },
        estimated_compile_ms=max(0, int(math.ceil(compile_ms))),
        estimated_run_ms=max(0, int(math.ceil(run_ms))),
        estimated_total_ms=max(0, int(math.ceil(total_ms))),
        estimated_memory_mb=max(0, int(math.ceil(memory_mb))),
        estimated_flops=max(0, int(math.ceil(flops))),
        confidence=str(metadata.get("confidence", "low"))
        if str(metadata.get("confidence", "low")) in {"low", "medium", "high"}
        else "low",
        lower=lower if lower is not None else float(total_ms),
        upper=upper if upper is not None else float(total_ms),
        coverage_confidence=coverage_confidence,
        delta=delta,
        bound_type=bound_type,
        calibration_scope=(
            None
            if metadata.get("calibration_scope") is None
            else str(metadata.get("calibration_scope"))
        ),
        estimator_version=str(metadata.get("estimator_version", "catalog.advisor_cost.v1")),
        estimator_hash=(
            None if metadata.get("estimator_hash") is None else str(metadata.get("estimator_hash"))
        ),
        assumptions=list(assumptions),
        valid_for=valid_for,
        includes_advisor_overhead=bool(metadata.get("includes_advisor_overhead", False)),
    )


def _metadata_float(metadata: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _cost_model_n_obs(entry: MethodCatalogEntry, query: MethodAdvisorQuery) -> int:
    if query.data is not None and query.data.n_obs is not None:
        return max(1, int(query.data.n_obs))
    if entry.typical_min_obs is not None:
        return max(1, int(entry.typical_min_obs))
    return 1000


def _resolve_advisor_budget(query: MethodAdvisorQuery) -> _ResolvedAdvisorBudget:
    raw_budget = query.cost_budget
    cost_per_ms = _budget_float(raw_budget, "cost_per_ms") or COST_PER_MS
    spend_limit = _budget_float(raw_budget, "spend_limit", "run_budget_usd")
    spend_unit = str(_budget_raw(raw_budget, "spend_unit", "unit") or "USD")
    compute_limit_ms = _budget_float(
        raw_budget,
        "compute_limit",
        "compute_limit_ms",
        "max_total_ms",
        "max_wall_time_ms",
    )
    if compute_limit_ms is None and query.runtime_budget_ms is not None:
        compute_limit_ms = float(query.runtime_budget_ms)
    if spend_limit is None and compute_limit_ms is not None:
        spend_limit = compute_limit_ms
        spend_unit = "ms"
    run_limit_ms = _budget_float(raw_budget, "max_run_ms", "run_limit_ms")
    compile_limit_ms = _budget_float(raw_budget, "max_compile_ms", "compile_limit_ms")
    memory_limit_mb = _budget_float(raw_budget, "max_memory_mb", "memory_limit_mb")
    payload: dict[str, object] = {
        "spend_limit": spend_limit,
        "spend_unit": spend_unit,
        "compute_limit_ms": compute_limit_ms,
        "run_limit_ms": run_limit_ms,
        "compile_limit_ms": compile_limit_ms,
        "memory_limit_mb": memory_limit_mb,
        "cost_per_ms": cost_per_ms,
    }
    if raw_budget is not None:
        payload["source_type"] = type(raw_budget).__name__
    return _ResolvedAdvisorBudget(
        spend_limit=spend_limit,
        spend_unit=spend_unit,
        compute_limit_ms=compute_limit_ms,
        run_limit_ms=run_limit_ms,
        compile_limit_ms=compile_limit_ms,
        memory_limit_mb=memory_limit_mb,
        cost_per_ms=cost_per_ms,
        payload=payload,
    )


def _budget_raw(budget: Any, *names: str) -> Any:
    if budget is None:
        return None
    for name in names:
        value = budget.get(name) if isinstance(budget, Mapping) else getattr(budget, name, None)
        if value is not None:
            return value
    return None


def _budget_float(budget: Any, *names: str) -> float | None:
    value = _budget_raw(budget, *names)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _spend_upper(cost: CostEstimate, *, budget: _ResolvedAdvisorBudget, delta: float) -> float:
    upper = float(cost.upper_bound(delta=delta))
    if budget.spend_unit.upper() == "USD" and cost.unit == "ms":
        return upper * float(budget.cost_per_ms)
    return upper


def _spend_lower(cost: CostEstimate, *, budget: _ResolvedAdvisorBudget, delta: float) -> float:
    lower = float(cost.lower_bound(delta=delta))
    if budget.spend_unit.upper() == "USD" and cost.unit == "ms":
        return lower * float(budget.cost_per_ms)
    return lower


def _compute_lower_bound(cost: CostEstimate, *, delta: float) -> float:
    if cost.unit == "ms":
        return float(cost.lower_bound(delta=delta))
    return float(cost.estimated_total_ms)


def _advisor_accuracy(entry: MethodCatalogEntry, advisor_score: float) -> float:
    return float(
        _truthfulness_depth_score(entry.truthfulness_tier) * 1000.0
        + _implementation_depth_score(entry.implementation_depth_tier) * 100.0
        + advisor_score
    )


def _declared_accuracy_metadata(entry: MethodCatalogEntry) -> Mapping[str, Any] | None:
    for source in (entry.capability_matrix, entry.effect_semantics, entry.shape_semantics):
        nested = source.get("advisor_accuracy") or source.get("accuracy_estimate")
        if isinstance(nested, Mapping):
            return nested
        if any(key in source for key in ("accuracy", "accuracy_point", "accuracy_lower")):
            return source
    return None


def _advisor_accuracy_interval(
    entry: MethodCatalogEntry,
    advisor_score: float,
    *,
    require_declared: bool,
) -> tuple[float, float, float, bool]:
    fallback = _advisor_accuracy(entry, advisor_score)
    metadata = _declared_accuracy_metadata(entry)
    if metadata is None:
        return fallback, fallback, fallback, not require_declared
    point = _metadata_float(metadata, "accuracy", "accuracy_point", "point")
    lower = _metadata_float(metadata, "accuracy_lower", "lower")
    upper = _metadata_float(metadata, "accuracy_upper", "upper")
    if point is None:
        point = fallback
    if lower is None:
        lower = point
    if upper is None:
        upper = point
    return float(point), float(lower), float(upper), True


def _cost_estimate_out_of_scope(cost: CostEstimate) -> bool:
    return bool(cost.valid_for.get("out_of_scope") or cost.valid_for.get("in_scope") is False)


def _pareto_front(
    candidates: Sequence[CandidateScore],
    *,
    dominance_mode: AdvisorDominanceMode = "point",
) -> tuple[CandidateScore, ...]:
    frontier: list[CandidateScore] = []
    for candidate in candidates:
        if any(
            other is not candidate and _dominates(other, candidate, dominance_mode=dominance_mode)
            for other in candidates
        ):
            continue
        frontier.append(candidate)
    frontier.sort(
        key=lambda item: (-item.accuracy, item.spend_upper, item.compute_upper, item.method_id)
    )
    return tuple(frontier)


def _dominates(
    left: CandidateScore,
    right: CandidateScore,
    *,
    dominance_mode: AdvisorDominanceMode = "point",
) -> bool:
    if dominance_mode == "robust":
        return _robustly_dominates(left, right)
    weakly_better = (
        left.accuracy >= right.accuracy
        and left.compute_upper <= right.compute_upper
        and left.spend_upper <= right.spend_upper
    )
    strictly_better = (
        left.accuracy > right.accuracy
        or left.compute_upper < right.compute_upper
        or left.spend_upper < right.spend_upper
    )
    return weakly_better and strictly_better


def _robustly_dominates(left: CandidateScore, right: CandidateScore) -> bool:
    weakly_better = (
        left.accuracy_lower >= right.accuracy_upper
        and left.compute_upper <= right.compute_lower
        and left.spend_upper <= right.spend_lower
    )
    strictly_better = (
        left.accuracy_lower > right.accuracy_upper
        or left.compute_upper < right.compute_lower
        or left.spend_upper < right.spend_lower
    )
    return weakly_better and strictly_better


def _select_frontier_candidate(
    frontier: Sequence[CandidateScore],
    *,
    value_policy: AdvisorValuePolicy
    | Callable[[CandidateScore], float]
    | Mapping[str, float]
    | None,
) -> CandidateScore:
    if not frontier:
        raise ValueError("Cannot select from an empty Pareto frontier.")
    if value_policy is not None:
        return max(
            frontier,
            key=lambda item: (
                _evaluate_value_policy(item, value_policy),
                item.accuracy,
                -item.spend_upper,
                item.method_id,
            ),
        )
    scored = [
        (
            _normalized_frontier_knee_score(candidate, frontier),
            candidate.accuracy,
            -candidate.spend_upper,
            candidate.method_id,
            candidate,
        )
        for candidate in frontier
    ]
    scored.sort(reverse=True)
    return scored[0][4]


def _evaluate_value_policy(
    candidate: CandidateScore,
    value_policy: AdvisorValuePolicy
    | Callable[[CandidateScore], float]
    | Mapping[str, float]
    | None,
) -> float | None:
    if value_policy is None:
        return None
    if isinstance(value_policy, AdvisorValuePolicy):
        return value_policy.value(candidate)
    if isinstance(value_policy, Mapping):
        policy = AdvisorValuePolicy(
            accuracy_weight=float(value_policy.get("accuracy_weight", 1.0)),
            compute_weight=float(value_policy.get("compute_weight", 0.0)),
            spend_weight=float(value_policy.get("spend_weight", 0.0)),
            slack_weight=float(value_policy.get("slack_weight", 0.0)),
        )
        return policy.value(candidate)
    return float(value_policy(candidate))


def _normalized_frontier_knee_score(
    candidate: CandidateScore,
    frontier: Sequence[CandidateScore],
) -> float:
    accuracies = [item.accuracy for item in frontier]
    spends = [item.spend_upper for item in frontier]
    computes = [item.compute_upper for item in frontier]
    slacks = [item.budget_slack for item in frontier if item.budget_slack is not None]
    score = _normalize(candidate.accuracy, accuracies)
    score += 1.0 - _normalize(candidate.spend_upper, spends)
    score += 1.0 - _normalize(candidate.compute_upper, computes)
    if candidate.budget_slack is not None and slacks:
        score += _normalize(candidate.budget_slack, slacks)
    return float(score)


def _normalize(value: float, values: Sequence[float]) -> float:
    lo = min(values)
    hi = max(values)
    if math.isclose(lo, hi):
        return 1.0
    return (float(value) - lo) / (hi - lo)


def _build_budget_certificate(
    *,
    selected: CandidateScore | None,
    frontier: Sequence[CandidateScore],
    candidates: Sequence[CandidateScore],
    budget: _ResolvedAdvisorBudget,
    delta: float,
) -> BudgetCertificate:
    representative = selected or min(
        candidates,
        key=lambda item: (item.spend_upper, item.compute_upper, item.method_id),
        default=None,
    )
    if representative is None:
        estimated_cost_point = 0.0
        estimated_cost_upper = 0.0
        estimated_compute_upper = None
        slack_lower_bound = None
        bound_type: CostBoundType = "UNKNOWN"
        assumptions: tuple[str, ...] = ()
        cost_model_version = "unknown"
        cost_model_hash = None
        calibration_scope = None
        confidence = None
    else:
        estimated_cost_point = _spend_point(representative.cost, budget=budget)
        estimated_cost_upper = float(representative.spend_upper)
        estimated_compute_upper = float(representative.compute_upper)
        slack_lower_bound = representative.budget_slack
        bound_type = representative.bound_type
        assumptions = tuple(representative.cost.assumptions)
        cost_model_version = representative.cost.estimator_version
        cost_model_hash = representative.cost.estimator_hash
        calibration_scope = representative.cost.calibration_scope
        confidence = _certificate_confidence(representative, delta)
    frontier_ids = tuple(item.method_id for item in frontier)
    infeasible_ids = tuple(item.method_id for item in candidates if not item.feasible)
    dominated_ids = tuple(
        item.method_id
        for item in candidates
        if item.feasible and item.method_id not in set(frontier_ids)
    )
    constraint_violations = {
        f"{candidate.method_id}:{name}": float(value)
        for candidate in candidates
        for name, value in candidate.constraint_violations.items()
    }
    certificate_id = _budget_certificate_id(
        selected_id=None if selected is None else selected.method_id,
        budget=budget,
        candidates=candidates,
        frontier_ids=frontier_ids,
    )
    return BudgetCertificate(
        certificate_id=certificate_id,
        selected_method_id=None if selected is None else selected.method_id,
        budget=budget.payload,
        estimated_cost_point=estimated_cost_point,
        estimated_cost_upper=estimated_cost_upper,
        estimated_compute_upper=estimated_compute_upper,
        slack_lower_bound=slack_lower_bound,
        feasible=bool(selected is not None and selected.feasible),
        confidence=confidence,
        delta=delta if confidence is not None else None,
        bound_type=bound_type,
        cost_model_version=cost_model_version,
        cost_model_hash=cost_model_hash,
        calibration_scope=calibration_scope,
        assumptions=assumptions,
        frontier_method_ids=frontier_ids,
        dominated_method_ids=dominated_ids,
        infeasible_method_ids=infeasible_ids,
        constraint_violations=constraint_violations,
        proof_obligations=_budget_proof_obligations(bound_type),
    )


def _certificate_confidence(candidate: CandidateScore, delta: float) -> float | None:
    if candidate.bound_type == "CALIBRATED_PROBABILISTIC_BOUND":
        return candidate.cost.coverage_confidence or (1.0 - float(delta))
    if candidate.bound_type == "EXACT_BOUND":
        return 1.0
    return None


def _spend_point(cost: CostEstimate, *, budget: _ResolvedAdvisorBudget) -> float:
    point = float(cost.point if cost.point is not None else cost.estimated_total_ms)
    if budget.spend_unit.upper() == "USD" and cost.unit == "ms":
        return point * float(budget.cost_per_ms)
    return point


def _budget_proof_obligations(bound_type: CostBoundType) -> tuple[str, ...]:
    if bound_type == "EXACT_BOUND":
        return (
            "CostEstimate.upper_bound(delta) must be a deterministic upper bound.",
            "Budget and cost units must be comparable.",
        )
    if bound_type == "CALIBRATED_PROBABILISTIC_BOUND":
        return (
            "CostEstimate.upper_bound(delta) must be calibrated on the declared scope.",
            "The problem must be inside the calibration scope.",
            "Multiple-candidate claims require joint calibration or union-bound delta allocation.",
        )
    return (
        "Estimate is heuristic; no deterministic or probabilistic budget-feasibility guarantee.",
        "Budget and cost units must be comparable.",
    )


def _budget_certificate_id(
    *,
    selected_id: str | None,
    budget: _ResolvedAdvisorBudget,
    candidates: Sequence[CandidateScore],
    frontier_ids: Sequence[str],
) -> str:
    payload = {
        "selected": selected_id,
        "budget": budget.payload,
        "candidates": [
            {
                "method_id": item.method_id,
                "spend_upper": item.spend_upper,
                "compute_upper": item.compute_upper,
                "feasible": item.feasible,
            }
            for item in candidates
        ],
        "frontier": list(frontier_ids),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _cost_policy_diagnostics(
    *,
    candidates: Sequence[CandidateScore],
    frontier: Sequence[CandidateScore],
    budget: _ResolvedAdvisorBudget,
    cost_policy: AdvisorCostPolicy,
) -> dict[str, object]:
    feasible = [item for item in candidates if item.feasible]
    infeasible = [item for item in candidates if not item.feasible]
    cheapest = min(candidates, key=lambda item: (item.spend_upper, item.method_id), default=None)
    cheapest_point = None if cheapest is None else _spend_point(cheapest.cost, budget=budget)
    highest_accuracy_over_budget = max(
        infeasible,
        key=lambda item: (item.accuracy, -item.spend_upper, item.method_id),
        default=None,
    )
    relaxations = _closest_feasible_relaxations(infeasible, budget=budget)
    return {
        "cost_policy": cost_policy,
        "budget": budget.payload,
        "candidate_count": len(candidates),
        "feasible_count": len(feasible),
        "frontier_count": len(frontier),
        "infeasible_method_ids": [item.method_id for item in infeasible],
        "unknown_cost_method_ids": [item.method_id for item in candidates if not item.cost_known],
        "out_of_scope_method_ids": [
            item.method_id for item in candidates if item.cost_out_of_scope
        ],
        "min_required_budget_point": cheapest_point,
        "min_required_budget_upper": None if cheapest is None else cheapest.spend_upper,
        "closest_feasible_relaxations": relaxations,
        "cheapest_candidate": None if cheapest is None else cheapest.method_id,
        "highest_accuracy_over_budget_candidate": (
            None if highest_accuracy_over_budget is None else highest_accuracy_over_budget.method_id
        ),
    }


def _closest_feasible_relaxations(
    candidates: Sequence[CandidateScore],
    *,
    budget: _ResolvedAdvisorBudget,
) -> list[dict[str, object]]:
    rows: list[tuple[float, str, dict[str, object]]] = []
    for candidate in candidates:
        if not candidate.constraint_violations:
            continue
        required: dict[str, float] = {}
        if "spend_limit" in candidate.constraint_violations:
            required[f"{budget.spend_unit}_limit"] = float(candidate.spend_upper)
        if "compute_limit" in candidate.constraint_violations:
            required["compute_limit_ms"] = float(candidate.compute_upper)
        if "run_limit" in candidate.constraint_violations:
            required["run_limit_ms"] = float(candidate.cost.resource_vector()["run_ms"])
        if "compile_limit" in candidate.constraint_violations:
            required["compile_limit_ms"] = float(candidate.cost.resource_vector()["compile_ms"])
        if "memory_limit" in candidate.constraint_violations:
            required["memory_limit_mb"] = float(candidate.cost.resource_vector()["memory_mb"])
        finite_violations = [
            value
            for value in candidate.constraint_violations.values()
            if math.isfinite(float(value))
        ]
        distance = sum(max(float(value), 0.0) for value in finite_violations)
        if not finite_violations and candidate.constraint_violations:
            distance = float("inf")
        rows.append(
            (
                distance,
                candidate.method_id,
                {
                    "method_id": candidate.method_id,
                    "violations": dict(candidate.constraint_violations),
                    "required_budget": required,
                    "estimated_cost_upper": candidate.spend_upper,
                    "estimated_compute_upper_ms": candidate.compute_upper,
                },
            )
        )
    rows.sort(key=lambda item: (item[0], item[1]))
    return [row for _, _, row in rows[:3]]


def _max_constraint_violation(candidate: CandidateScore) -> float:
    return max(candidate.constraint_violations.values(), default=0.0)


def _normalize_bound_type(value: str) -> CostBoundType:
    if value in {
        "EXACT_BOUND",
        "CALIBRATED_PROBABILISTIC_BOUND",
        "HEURISTIC_POINT_ESTIMATE",
        "UNKNOWN",
    }:
        return value  # type: ignore[return-value]
    return "UNKNOWN"


def _annotate_payload_with_costs(
    payload: list[dict[str, object]],
    cost_lookup: Mapping[str, CandidateScore],
) -> None:
    for item in payload:
        fqn = item.get("fqn")
        if not isinstance(fqn, str) or fqn not in cost_lookup:
            continue
        score = cost_lookup[fqn]
        item["cost_estimate"] = {
            "point": score.cost.point,
            "unit": score.cost.unit,
            "spend_upper": score.spend_upper,
            "compute_upper_ms": score.compute_upper,
            "budget_slack": score.budget_slack,
            "feasible": score.feasible,
            "violations": list(score.violations),
            "bound_type": score.bound_type,
            "cost_known": score.cost_known,
            "cost_out_of_scope": score.cost_out_of_scope,
        }


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
        if entry.simulator_regime_schema:
            item["simulator_regime_schema"] = dict(entry.simulator_regime_schema)
        if entry.summary_schema_ref:
            item["summary_schema_ref"] = entry.summary_schema_ref
        if entry.identifiable_target:
            item["identifiable_target"] = dict(entry.identifiable_target)
        if entry.coverage_contract:
            item["coverage_contract"] = dict(entry.coverage_contract)
        if entry.diagnostic_contract:
            item["diagnostic_contract"] = dict(entry.diagnostic_contract)
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
    if query.cost_policy != "ignore" or query.cost_budget is not None or query.return_certificate:
        payload["cost"] = {
            "cost_policy": query.cost_policy,
            "cost_budget": _jsonable(query.cost_budget),
            "risk_delta": query.risk_delta,
            "return_certificate": query.return_certificate,
            "dominance_mode": query.dominance_mode,
            "allow_heuristic_cost_estimate": query.allow_heuristic_cost_estimate,
            "require_declared_accuracy_estimate": query.require_declared_accuracy_estimate,
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


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value]
    return str(value)


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
    "AdvisorOptimizationResult",
    "AdvisorValuePolicy",
    "BudgetCertificate",
    "CalibratedRegretCertificate",
    "CandidateScore",
    "ConfidenceSequence",
    "CrossMethodConsensus",
    "DataCharacteristics",
    "MethodAdvisorQuery",
    "MethodAdvisorResult",
    "MethodLossProfile",
    "MethodScoreTraceEntry",
    "MethodSelectionCriteria",
    "advise_methods",
    "advise_methods_for_analyst",
    "attach_advisor_execution_context",
    "authoring_catalog_payload",
    "build_advisor_execution_context",
    "compute_voi",
    "method_selection_payload",
    "pareto_advise_methods",
    "rank_method_catalog_entries",
    "suggest_adapter_methods",
    "suggest_alternative_methods",
    "suggest_plan_node_alternatives",
]
