"""Public causal resolve transport module API."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.data_forge.read_api.academic import SKGQuery
from polisyos.data_forge.read_api.catalog import (
    DatasetRegistry,
    PStarZResult,
    compose_confidence_harmonic,
    resolve_proxy,
    validate_proxy,
)
from polisyos.foundry.methods.catalog.causal.capabilities import (
    build_causal_capability_contract,
)
from polisyos.foundry.methods.catalog.causal.transport_engine import solve_transportability
from polisyos.ir.analytics.alignment_certification import (
    AlignmentCertificate,
    AlignmentCertificateType,
    AlignmentCertificationPolicy,
    OuterObjectiveResult,
    compute_outer_objective,
    run_outer_search,
)
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_capabilities import (
    CausalCapabilityContract,
    load_causal_capability_contract,
    persist_causal_capability_contract,
)
from polisyos.ir.analytics.causal_ensemble import load_causal_model_ensemble
from polisyos.ir.analytics.causal_graph import CausalGraphModel, load_causal_graph_model
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.partial_identification import compute_manski_bounds
from polisyos.ir.analytics.privacy_transportability import (
    TransportPrivacyContext,
    apply_transport_privacy_context,
    coerce_transport_privacy_context,
)
from polisyos.ir.analytics.transportability import (
    DataGap,
    SelectionDiagram,
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
    build_selection_diagram,
    persist_transportability_result,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.refs import (
    CausalCapabilityContractRef,
    CausalEffectReportRef,
    CausalGraphModelRef,
    CausalModelEnsembleRef,
)
from polisyos.lex.api import evaluate_transport_constraints
from polisyos.lex.legal_evaluation.transport_constraints import (
    ConstraintSeverity,
    LegalConstraint,
    LegalConstraintSet,
    LegalToDAGMapping,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)

logger = get_logger(__name__)

_TRANSPORT_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_TRANSPORT_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_TRANSPORT_NUMERIC_PARSE_ERRORS = (TypeError, ValueError, OverflowError)

MAX_ROUNDS = 3
PROXY_FALLBACK_THRESHOLD = 0.3
_VALID_TRANSPORT_SOLVER_MODES: frozenset[str] = frozenset(
    {"auto", "simplified", "symbolic", "symbolic_y0", "symbolic_r", "full_auto"}
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_transportability@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Transportability",
    description=(
        "Resolve transportability through three-graph closure "
        "(context/SKG + datasets + legal constraints)."
    ),
    tags=["builtin", "causal", "transportability"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.source_context",
        "params.target_context",
        "params.query_treatment",
        "params.query_outcome",
        "params.policy_spec",
        "params.pag_identification_policy",
        "params.pag_max_dag_samples",
        "params.pag_threshold",
        "params.pag_seed",
        "params.transport_solver_mode",
        "params.allow_degraded_transport",
        "params.privacy_context",
        "params.dp_utility_manifest",
        "params.privacy_transport_certificate",
        "params.workflow_id",
        "params.dataset_registry_db_path",
        "params.legal_kg_db_path",
        "params.skg_db_path",
        "params.skg_index_dir",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENSEMBLE_REF}",
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
    ],
    state_writes=[
        "causal_capability_contract_ref",
        "params.transportability_status",
        "params.transportability_transport_mode",
        "params.transportability_identification_engine",
        "params.transportability_id_confidence_under_pag",
        "params.transportability_capability_hash",
        "params.transportability_degradation_policy",
        "params.transportability_warning",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF}",
        f"artifacts_index.{ARTIFACT_TRANSPORTABILITY_RESULT_REF}",
    ],
    produces=[
        ARTIFACT_TRANSPORTABILITY_RESULT_REF,
        ARTIFACT_CAUSAL_REPORT_REF,
        ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ],
)


class ResolutionState(BaseModel):
    """Immutable snapshot of one transportability-resolution loop iteration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    round: int
    s_nodes: list[SNode] = Field(default_factory=list)
    legal_s_nodes: list[SNode] = Field(default_factory=list)
    data_gaps: list[DataGap] = Field(default_factory=list)
    hard_constraints: list[LegalConstraint] = Field(default_factory=list)
    p_star_values: dict[str, PStarZResult] = Field(default_factory=dict)
    proxy_penalties: dict[str, float] = Field(default_factory=dict)
    proxy_validity: dict[str, dict[str, Any]] = Field(default_factory=dict)
    requires_expert_review: bool = False
    expert_review_reasons: list[str] = Field(default_factory=list)
    converged: bool = False
    feasible: bool = True


class _NullDatasetRegistry:
    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> list[Any]:
        del canonical_var, country_code, year_range
        return []

    def compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        *,
        condition_on: dict[str, float] | None = None,
    ) -> PStarZResult:
        del country_code, year
        return PStarZResult(
            canonical_variable=canonical_var,
            value=None,
            dataset_id=None,
            raw_variable=None,
            is_proxy=False,
            confidence=0.0,
            penalty_breakdown={"missing_registry": 1.0},
            is_conditional=bool(condition_on),
            condition_on=condition_on or {},
        )


class _NullSKG:
    def query_claims(self, *, cause: str, effect: str, min_trust: float = 0.0) -> list[Any]:
        del cause, effect, min_trust
        return []


class _LoopDatasetRegistry:
    """Per-run cached view over dataset lookups used by resolution loop."""

    def __init__(
        self,
        *,
        find_cached: Callable[[str, str, tuple[int, int] | None], list[Any]],
        p_star_cached: Callable[[str, str, int, dict[str, float] | None], PStarZResult],
    ) -> None:
        self._find_cached = find_cached
        self._p_star_cached = p_star_cached

    def find_datasets_for_variable(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None = None,
    ) -> list[Any]:
        return self._find_cached(canonical_var, country_code, year_range)

    def compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        *,
        condition_on: dict[str, float] | None = None,
    ) -> PStarZResult:
        return self._p_star_cached(canonical_var, country_code, year, condition_on)


class TransportabilityResolutionLoop:
    """Resolve transportability across datasets, SKG evidence, and legal rules.

    The loop caches expensive lookups across rounds, accumulates S-nodes and
    data gaps, and determines whether the workflow can proceed with direct
    transport, degraded transport, or expert-review escalation.
    """

    MAX_ROUNDS: int = MAX_ROUNDS

    def __init__(
        self,
        *,
        dataset_registry: DatasetRegistry | _NullDatasetRegistry,
        legal_kg_db_path: Path | None,
        skg_query: SKGQuery | _NullSKG,
        max_rounds: int = MAX_ROUNDS,
        proxy_threshold: float = PROXY_FALLBACK_THRESHOLD,
    ) -> None:
        self._datasets = dataset_registry
        self._legal_kg_db_path = legal_kg_db_path
        self._skg = skg_query
        self._max_rounds = min(MAX_ROUNDS, max(1, int(max_rounds)))
        self._proxy_threshold = max(0.0, min(1.0, float(proxy_threshold)))
        self._distance_cache: dict[tuple[str, str], float] = {}
        self._find_datasets_cache: dict[
            tuple[str, str, tuple[int, int] | None], tuple[Any, ...]
        ] = {}
        self._p_star_cache: dict[
            tuple[str, str, int, tuple[tuple[str, float], ...]], PStarZResult
        ] = {}

    def _cache_clear(self) -> None:
        self._distance_cache.clear()
        self._find_datasets_cache.clear()
        self._p_star_cache.clear()

    @staticmethod
    def _normalize_condition_key(
        condition_on: dict[str, float] | None,
    ) -> tuple[tuple[str, float], ...]:
        if not condition_on:
            return ()
        normalized: list[tuple[str, float]] = []
        for key, value in sorted(condition_on.items(), key=lambda item: str(item[0])):
            normalized.append((str(key), float(value)))
        return tuple(normalized)

    def _cached_context_distance(
        self,
        *,
        source_context: ContextProfile,
        target_context: ContextProfile,
    ) -> float:
        key = (source_context.context_id, target_context.context_id)
        cached = self._distance_cache.get(key)
        if cached is not None:
            return cached
        distance = float(source_context.distance_to(target_context))
        self._distance_cache[key] = distance
        return distance

    def _cached_find_datasets(
        self,
        canonical_var: str,
        country_code: str,
        year_range: tuple[int, int] | None,
    ) -> list[Any]:
        key = (canonical_var, country_code, year_range)
        cached = self._find_datasets_cache.get(key)
        if cached is not None:
            return list(cached)
        matches = self._datasets.find_datasets_for_variable(
            canonical_var=canonical_var,
            country_code=country_code,
            year_range=year_range,
        )
        frozen = tuple(matches)
        self._find_datasets_cache[key] = frozen
        return list(frozen)

    def _cached_compute_p_star_z(
        self,
        canonical_var: str,
        country_code: str,
        year: int,
        condition_on: dict[str, float] | None,
    ) -> PStarZResult:
        condition_key = self._normalize_condition_key(condition_on)
        key = (canonical_var, country_code, int(year), condition_key)
        cached = self._p_star_cache.get(key)
        if cached is not None:
            return cached

        # Prime dataset lookup cache for the same year-slice used by compute_p_star_z.
        self._cached_find_datasets(canonical_var, country_code, (int(year), int(year)))

        result = self._datasets.compute_p_star_z(
            canonical_var=canonical_var,
            country_code=country_code,
            year=int(year),
            condition_on=condition_on,
        )
        self._p_star_cache[key] = result
        return result

    def _cached_dataset_registry(self) -> _LoopDatasetRegistry:
        return _LoopDatasetRegistry(
            find_cached=self._cached_find_datasets,
            p_star_cached=self._cached_compute_p_star_z,
        )

    def resolve(
        self,
        *,
        source_context: ContextProfile,
        target_context: ContextProfile,
        causal_graph: CausalGraphModel,
        query_treatment: str,
        query_outcome: str,
        policy_spec: Mapping[str, Any] | None = None,
        pag_identification_policy: str | None = None,
        pag_max_dag_samples: int = 100,
        pag_threshold: float = 0.5,
        pag_seed: int | None = None,
        solver_mode: str = "auto",
        allow_degraded_transport: bool = False,
        capability_contract: CausalCapabilityContract | None = None,
        privacy_context: TransportPrivacyContext | None = None,
    ) -> TransportabilityResult:
        self._cache_clear()
        normalized_solver_mode = (
            solver_mode.strip().lower()
            if isinstance(solver_mode, str) and solver_mode.strip()
            else "auto"
        )
        if normalized_solver_mode not in _VALID_TRANSPORT_SOLVER_MODES:
            normalized_solver_mode = "auto"
        try:
            cached_registry = self._cached_dataset_registry()
            prev_s_node_set: set[tuple[str, str, str]] = set()
            state: ResolutionState | None = None
            tr_result: TransportabilityResult | None = None
            diagram: SelectionDiagram | None = None

            for round_num in range(1, self._max_rounds + 1):
                context_diagram = build_selection_diagram(
                    source_context,
                    target_context,
                    causal_graph,
                )
                context_s_nodes = list(context_diagram.s_nodes)
                legal_constraint_set = _evaluate_legal_constraints(
                    target_context=target_context,
                    policy_spec=policy_spec,
                    causal_graph=causal_graph,
                    legal_kg_db_path=self._legal_kg_db_path,
                )
                hard_constraints = list(legal_constraint_set.hard_constraints)
                legal_s_nodes = _legal_constraints_to_s_nodes(
                    mappings=legal_constraint_set.legal_dag_mappings,
                    causal_graph=causal_graph,
                )
                if hard_constraints:
                    return _finalize_transport_loop_result(
                        _build_infeasible_result(
                            source_context=source_context,
                            target_context=target_context,
                            hard_constraints=hard_constraints,
                            query_treatment=query_treatment,
                            query_outcome=query_outcome,
                        ),
                        privacy_context=privacy_context,
                    )

                all_s_nodes = context_s_nodes + legal_s_nodes
                diagram = SelectionDiagram(
                    base_graph=causal_graph,
                    s_nodes=all_s_nodes,
                    source_context=source_context,
                    target_context=target_context,
                    context_distance=self._cached_context_distance(
                        source_context=source_context,
                        target_context=target_context,
                    ),
                )
                tr_payload = _run_transport_solver(
                    diagram=diagram,
                    query_treatment=query_treatment,
                    query_outcome=query_outcome,
                    solver_mode=normalized_solver_mode,
                    allow_degraded_transport=allow_degraded_transport,
                    capability_contract=capability_contract,
                    pag_identification_policy=pag_identification_policy,
                    pag_max_dag_samples=pag_max_dag_samples,
                    pag_threshold=pag_threshold,
                    pag_seed=pag_seed if pag_seed is not None else 0,
                    privacy_context=None,
                )
                tr_result = TransportabilityResult.model_validate(tr_payload["transport_result"])

                p_star_values: dict[str, PStarZResult] = {}
                data_gaps: list[DataGap] = []
                proxy_penalties: dict[str, float] = {}
                proxy_validity: dict[str, dict[str, Any]] = {}
                requires_expert_review = False
                expert_review_reasons: list[str] = []
                adjacency = _build_adjacency(causal_graph)

                formula = tr_result.transport_formula
                if formula is not None:
                    details_lookup = {item.name: item for item in formula.stratification_details}
                    for z_var in formula.stratification_variables:
                        detail = details_lookup.get(z_var)
                        condition_on: dict[str, float] | None = None
                        if detail is not None and detail.requires_conditional:
                            condition_on = {
                                (
                                    detail.condition_on_treatment or query_treatment
                                ): _resolve_treatment_value(policy_spec)
                            }

                        p_star = self._cached_compute_p_star_z(
                            canonical_var=z_var,
                            country_code=target_context.context_id,
                            year=_resolve_context_year(target_context),
                            condition_on=condition_on,
                        )
                        if p_star.value is not None:
                            p_star_values[z_var] = p_star
                            if p_star.is_proxy:
                                proxy_penalties[z_var] = max(
                                    0.0,
                                    min(1.0, 1.0 - p_star.confidence),
                                )
                            continue

                        proxy_chain = resolve_proxy(
                            target_var=z_var,
                            target_context=target_context.context_id,
                            dataset_registry=cached_registry,
                            skg_query=self._skg,
                        )
                        if (
                            proxy_chain.proxies
                            and proxy_chain.best_single_confidence > self._proxy_threshold
                        ):
                            best = proxy_chain.proxies[0]
                            checklist = validate_proxy(
                                proxy=best.proxy_variable,
                                target=z_var,
                                outcome=query_outcome,
                                adjacency=adjacency,
                                correlation_matrix={
                                    (best.proxy_variable, z_var): best.base_correlation
                                },
                            )
                            proxy_validity[z_var] = checklist.model_dump(mode="json")
                            validity_score = _proxy_validity_score(checklist)
                            conditional_penalty = 0.1 if condition_on else 0.0
                            confidence = compose_confidence_harmonic(
                                best.effective_confidence,
                                validity_score,
                            )
                            confidence = max(
                                0.0,
                                min(1.0, confidence - conditional_penalty),
                            )
                            if checklist.requires_expert_review or not checklist.overall_valid:
                                requires_expert_review = True
                                joined_violations = (
                                    "; ".join(checklist.violations) or "validation_failed"
                                )
                                reason = f"proxy_validation:{z_var}:{best.proxy_variable}:{joined_violations}"
                                if reason not in expert_review_reasons:
                                    expert_review_reasons.append(reason)
                            p_star_values[z_var] = PStarZResult(
                                canonical_variable=z_var,
                                value=None,
                                dataset_id=best.proxy_dataset_id,
                                raw_variable=best.proxy_raw_name,
                                is_proxy=True,
                                proxy_chain=[f"{best.proxy_variable} -> {z_var}"],
                                confidence=confidence,
                                penalty_breakdown={
                                    "proxy": max(0.0, 1.0 - best.effective_confidence),
                                    "proxy_validity": max(0.0, 1.0 - validity_score),
                                    **(
                                        {"conditional_proxy": conditional_penalty}
                                        if condition_on
                                        else {}
                                    ),
                                },
                                is_conditional=condition_on is not None,
                                condition_on=condition_on or {},
                            )
                            proxy_penalties[z_var] = max(0.0, min(1.0, 1.0 - confidence))
                            continue

                        data_gaps.append(
                            DataGap(
                                required_variable=z_var,
                                required_context=(
                                    f"{target_context.context_id}, {target_context.time_period}"
                                ),
                                available_proxies=proxy_chain.proxies,
                                best_proxy_confidence=proxy_chain.best_single_confidence,
                                gap_impact=(
                                    "transport_confidence reduced due to missing target quantity"
                                ),
                                suggested_action=_suggest_data_collection(z_var),
                            )
                        )

                proxy_introduced_vars = {
                    var for var, value in p_star_values.items() if value.is_proxy
                }
                filtered_context_nodes = [
                    node
                    for node in context_s_nodes
                    if node.target_variable not in proxy_introduced_vars
                ]
                merged_nodes = filtered_context_nodes + legal_s_nodes
                current_s_set = {
                    (node.target_variable, node.context_dimension, node.origin.value)
                    for node in merged_nodes
                }
                converged = (current_s_set == prev_s_node_set) or (round_num >= self._max_rounds)
                prev_s_node_set = current_s_set

                state = ResolutionState(
                    round=round_num,
                    s_nodes=filtered_context_nodes,
                    legal_s_nodes=legal_s_nodes,
                    data_gaps=data_gaps,
                    hard_constraints=hard_constraints,
                    p_star_values=p_star_values,
                    proxy_penalties=proxy_penalties,
                    proxy_validity=proxy_validity,
                    requires_expert_review=requires_expert_review,
                    expert_review_reasons=expert_review_reasons,
                    converged=converged,
                    feasible=True,
                )
                if converged:
                    break

            if tr_result is None or state is None or diagram is None:
                return _finalize_transport_loop_result(
                    TransportabilityResult(
                        query=f"P*({query_outcome}|do({query_treatment}))",
                        status=TransportabilityStatus.UNSUPPORTED,
                        transport_mode=TransportMode.NONE,
                        base_confidence=0.0,
                        final_confidence=0.0,
                        feasible=False,
                        warnings=["Transportability resolution failed unexpectedly."],
                        source_context_id=source_context.context_id,
                        target_context_id=target_context.context_id,
                        identification_engine="simplified_legacy",
                        identification_trace=["resolution_loop:unexpected_failure"],
                        unsupported_reason="resolution_loop_unexpected_failure",
                    ),
                    privacy_context=privacy_context,
                )
            return _finalize_transport_loop_result(
                _build_final_result(tr_result=tr_result, state=state, diagram=diagram),
                privacy_context=privacy_context,
            )
        finally:
            # Per-run cache isolation.
            self._cache_clear()


def _run_transport_solver(
    *,
    diagram: SelectionDiagram,
    query_treatment: str,
    query_outcome: str,
    solver_mode: str,
    allow_degraded_transport: bool,
    capability_contract: CausalCapabilityContract | None,
    pag_identification_policy: str | None,
    pag_max_dag_samples: int,
    pag_threshold: float,
    pag_seed: int,
    privacy_context: TransportPrivacyContext | None,
) -> dict[str, Any]:
    result = solve_transportability(
        selection_diagram=diagram,
        query_treatment=query_treatment,
        query_outcome=query_outcome,
        solver_mode=solver_mode,
        allow_degraded_transport=allow_degraded_transport,
        capability_contract=capability_contract,
        pag_identification_policy=pag_identification_policy,
        pag_max_dag_samples=pag_max_dag_samples,
        pag_threshold=pag_threshold,
        pag_seed=pag_seed,
        privacy_context=privacy_context,
    )
    return {"transport_result": result.model_dump(mode="json")}


def _resolve_transport_privacy_context(
    params: Mapping[str, Any],
) -> TransportPrivacyContext | None:
    for candidate in (
        params.get("privacy_context"),
        params.get("dp_utility_manifest"),
        params.get("privacy_transport_certificate"),
    ):
        context = coerce_transport_privacy_context(candidate)
        if context is not None:
            return context
    return None


def _finalize_transport_loop_result(
    result: TransportabilityResult,
    *,
    privacy_context: TransportPrivacyContext | None,
) -> TransportabilityResult:
    return apply_transport_privacy_context(result, privacy_context)


@dataclass(frozen=True)
class RunTransportabilityNode:
    """Execute the transportability resolution loop for the active workflow.

    Consumes causal reports, contexts, legal constraints, and capability
    metadata, then persists a ``TransportabilityResult`` together with any
    updated causal report or capability contract artifacts.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        report_ref_raw = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
        if report_ref_raw is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No causal report artifact found; skip transportability.",
                    )
                ],
            )

        try:
            report_ref = CausalEffectReportRef.model_validate(
                report_ref_raw.model_dump(mode="json")
            )
            causal_report = load_causal_effect_report(ctx.store, report_ref)
        except _TRANSPORT_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message=f"Failed to load CausalEffectReport: {exc}",
                ),
            )

        source_context = _resolve_context_profile(state.params.get("source_context"))
        target_context = _resolve_context_profile(state.params.get("target_context"))
        if source_context is None or target_context is None:
            new_state = branch_state(state, write_paths=_SPEC.state_writes).state
            new_state.params["transportability_warning"] = (
                "missing_source_or_target_context: transportability skipped"
            )
            return NodeOutcome(
                status="skip",
                state=new_state,
                events=[
                    NodeEvent(
                        level="warn",
                        message=(
                            "Missing source/target context profile; transportability check skipped."
                        ),
                    )
                ],
            )

        graph = _resolve_causal_graph(ctx, state)
        if graph is None:
            new_state = branch_state(state, write_paths=_SPEC.state_writes).state
            new_state.params["transportability_warning"] = (
                "missing_causal_graph: transportability skipped"
            )
            return NodeOutcome(
                status="skip",
                state=new_state,
                events=[
                    NodeEvent(
                        level="warn",
                        message="No causal graph available; transportability check skipped.",
                    )
                ],
            )

        treatment = _resolve_query_treatment(state, causal_report)
        outcome = _resolve_query_outcome(state, causal_report)
        policy_spec_raw = state.params.get("policy_spec")
        policy_spec = policy_spec_raw if isinstance(policy_spec_raw, Mapping) else None
        pag_identification_policy = _resolve_pag_identification_policy(state, graph)
        pag_max_dag_samples = _resolve_pag_max_dag_samples(state)
        pag_threshold = _resolve_pag_threshold(state)
        pag_seed = _resolve_pag_seed(state, graph)
        transport_solver_mode = _resolve_transport_solver_mode(state)
        try:
            allow_degraded_transport = _resolve_allow_degraded_transport(state)
        except ValueError as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=str(exc),
                    details={"execution_profile": state.execution_profile},
                ),
            )
        capability_contract, capability_ref = _resolve_or_build_capability_contract(ctx, state)
        input_refs = [InputRef(artifact_id=report_ref.artifact_id, role="causal_report")]
        privacy_context = _resolve_transport_privacy_context(state.params)
        if privacy_context is not None:
            privacy_context = privacy_context.model_copy(
                update={
                    "store": ctx.store,
                    "inputs": tuple([*privacy_context.inputs, *input_refs]),
                }
            )

        dataset_registry = _build_dataset_registry(state.params.get("dataset_registry_db_path"))
        skg_query = _build_skg_query(
            db_path=state.params.get("skg_db_path"),
            index_dir=state.params.get("skg_index_dir"),
        )
        legal_kg_db_path = _coerce_path(state.params.get("legal_kg_db_path"))

        loop = TransportabilityResolutionLoop(
            dataset_registry=dataset_registry,
            legal_kg_db_path=legal_kg_db_path,
            skg_query=skg_query,
            max_rounds=MAX_ROUNDS,
            proxy_threshold=PROXY_FALLBACK_THRESHOLD,
        )

        try:
            transport_result = loop.resolve(
                source_context=source_context,
                target_context=target_context,
                causal_graph=graph,
                query_treatment=treatment,
                query_outcome=outcome,
                policy_spec=policy_spec,
                pag_identification_policy=pag_identification_policy,
                pag_max_dag_samples=pag_max_dag_samples,
                pag_threshold=pag_threshold,
                pag_seed=pag_seed,
                solver_mode=transport_solver_mode,
                allow_degraded_transport=allow_degraded_transport,
                capability_contract=capability_contract,
                privacy_context=privacy_context,
            )
        finally:
            if isinstance(skg_query, SKGQuery):
                skg_query.close()

        transport_ref = persist_transportability_result(
            ctx.store,
            transport_result,
            inputs=input_refs,
        )
        updated_report = causal_report.model_copy(update={"transport_result": transport_result})
        updated_report_ref = persist_causal_effect_report(
            ctx.store,
            updated_report,
            inputs=[
                InputRef(artifact_id=report_ref.artifact_id, role="causal_report_prev"),
                InputRef(artifact_id=transport_ref.artifact_id, role="transportability_result"),
            ],
        )

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.params["transportability_status"] = transport_result.status.value
        new_state.params["transportability_transport_mode"] = transport_result.transport_mode.value
        new_state.params["transportability_identification_engine"] = (
            transport_result.identification_engine
        )
        new_state.params["transportability_capability_hash"] = (
            capability_contract.dependency_fingerprint
        )
        new_state.params["transportability_degradation_policy"] = (
            capability_contract.degradation_policy
        )
        if transport_result.id_confidence_under_pag is not None:
            new_state.params["transportability_id_confidence_under_pag"] = (
                transport_result.id_confidence_under_pag
            )
        else:
            new_state.params.pop("transportability_id_confidence_under_pag", None)
        new_state.params.pop("transportability_warning", None)
        new_state.artifacts_index[ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF] = capability_ref
        new_state.causal_capability_contract_ref = capability_ref
        new_state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF] = transport_ref
        new_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = updated_report_ref

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[capability_ref, transport_ref, updated_report_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Transportability resolved: "
                        f"status={transport_result.status.value}, "
                        f"mode={transport_result.transport_mode.value}, "
                        f"engine={transport_result.identification_engine}, "
                        f"rounds={transport_result.resolution_rounds}, "
                        f"feasible={transport_result.feasible}"
                    ),
                )
            ],
        )


def _build_final_result(
    *,
    tr_result: TransportabilityResult,
    state: ResolutionState,
    diagram: SelectionDiagram,
) -> TransportabilityResult:
    confidence = float(tr_result.final_confidence)
    for penalty in state.proxy_penalties.values():
        confidence *= 1.0 - max(0.0, min(1.0, float(penalty)))
    for _ in state.data_gaps:
        confidence *= 0.7
    confidence = max(0.0, min(1.0, confidence))

    warnings = list(tr_result.warnings)
    search_events = list(tr_result.search_events)
    metadata = dict(tr_result.metadata)
    if state.data_gaps:
        warnings.append(
            f"Missing target quantities for {len(state.data_gaps)} variable(s); added data_gaps."
        )
    if tr_result.lagged_edge_count > 0:
        time_warning = (
            "time_stationarity_warning: lagged transport path detected; "
            "assumes_time_stationarity=True."
        )
        if time_warning not in warnings:
            warnings.append(time_warning)

    outer = _run_alignment_outer_search(
        tr_result=tr_result,
        state=state,
        diagram=diagram,
    )
    if outer["truncated"]:
        for token in ("outer_search_truncated", "search_budget_exhausted"):
            if token not in search_events:
                search_events.append(token)
        warnings.append("Bounded alignment outer-search truncated due to budget/time limit.")

    partial_identification = None
    if tr_result.status is TransportabilityStatus.UNSUPPORTED:
        partial_identification = _build_manski_fallback(tr_result=tr_result, state=state)
        if partial_identification.is_informative:
            warnings.append("partial_identification_informative:manski_bounds")
            tr_result = tr_result.model_copy(
                update={
                    "status": TransportabilityStatus.BOUNDED_NON_IDENTIFIED,
                    "transport_mode": TransportMode.BOUNDS_ONLY,
                    "identification_engine": "bounds_only",
                    "unsupported_reason": None,
                }
            )
        else:
            warnings.append("partial_identification_non_informative:manski_bounds")

    metadata["lineage_three_graph"] = _build_three_graph_lineage(tr_result=tr_result, state=state)
    metadata["alignment_outer_search"] = {
        "configs_evaluated": int(outer["configs_evaluated"]),
        "best_score": float(outer["best_score"]),
        "truncated": bool(outer["truncated"]),
    }
    identification_trace = list(tr_result.identification_trace)
    identification_trace.append(f"outer_search_configs_evaluated:{outer['configs_evaluated']}")
    if outer["truncated"]:
        identification_trace.append("outer_search_truncated")
        identification_trace.append("search_budget_exhausted")

    update_payload: dict[str, Any] = {
        "final_confidence": confidence,
        "data_gaps": list(state.data_gaps),
        "p_star_values": dict(state.p_star_values),
        "legal_s_nodes": list(state.legal_s_nodes),
        "resolution_rounds": state.round,
        "feasible": state.feasible,
        "proxy_penalties": dict(state.proxy_penalties),
        "proxy_validity": dict(state.proxy_validity),
        "requires_expert_review": bool(state.requires_expert_review),
        "expert_review_reasons": list(state.expert_review_reasons),
        "source_context_id": diagram.source_context.context_id,
        "target_context_id": diagram.target_context.context_id,
        "warnings": warnings,
        "algorithm_version": tr_result.algorithm_version,
        "outer_search_truncated": bool(outer["truncated"]),
        "search_budget_exhausted": bool(outer["truncated"]),
        "outer_search_configs_evaluated": int(outer["configs_evaluated"]),
        "outer_search_best_score": float(outer["best_score"]),
        "search_events": search_events,
        "lagged_edges_in_query": bool(tr_result.lagged_edge_count > 0),
        "time_stationarity_warning": (
            "Lagged transport path detected; assumes_time_stationarity=True."
            if tr_result.lagged_edge_count > 0
            else None
        ),
        "metadata": metadata,
        "identification_trace": identification_trace,
    }
    if partial_identification is not None:
        update_payload["partial_identification_result"] = partial_identification
    return tr_result.model_copy(update=update_payload)


def _run_alignment_outer_search(
    *,
    tr_result: TransportabilityResult,
    state: ResolutionState,
    diagram: SelectionDiagram,
) -> dict[str, Any]:
    certificates = _build_alignment_certificates(state)
    formula = tr_result.transport_formula
    required_count = 0
    if formula is not None and formula.stratification_variables:
        required_count = len(formula.stratification_variables)
    elif state.p_star_values:
        required_count = len(state.p_star_values)
    elif state.data_gaps:
        required_count = len(state.data_gaps)

    coverage = 1.0
    if required_count > 0:
        coverage = len(state.p_star_values) / float(required_count)
    coverage = max(0.0, min(1.0, coverage))

    conflict_norm = min(
        1.0,
        (float(diagram.context_distance) * 0.6)
        + (len(state.legal_s_nodes) * 0.1)
        + (len(state.data_gaps) * 0.15),
    )

    def _evaluator(
        policy: AlignmentCertificationPolicy,
        lambda_conflict: float,
    ) -> OuterObjectiveResult:
        active = [cert for cert in certificates if cert.cert_type in set(policy.allowed_types)]
        cert_result = policy.validate_chain(active[: policy.max_chain_length])
        effective_coverage = coverage * cert_result.effective_confidence
        score = compute_outer_objective(
            coverage_queries=effective_coverage,
            irreducible_conflict_norm=conflict_norm,
            lambda_conflict=lambda_conflict,
        )
        return OuterObjectiveResult(
            score=score,
            coverage=effective_coverage,
            conflict_norm=conflict_norm,
            lambda_conflict=lambda_conflict,
            config=policy,
            is_feasible=cert_result.passed,
        )

    type_configs = None
    if required_count <= 2:
        cert_types = tuple(
            sorted(
                {cert.cert_type for cert in certificates},
                key=lambda item: item.value,
            )
        ) or (AlignmentCertificateType.EXACT,)
        type_configs = (cert_types,)

    result = run_outer_search(_evaluator, type_configs=type_configs)
    return {
        "truncated": result.truncated,
        "configs_evaluated": result.configs_evaluated,
        "best_score": result.best_score,
    }


def _build_alignment_certificates(state: ResolutionState) -> list[AlignmentCertificate]:
    certificates: list[AlignmentCertificate] = []
    for variable, p_star in sorted(state.p_star_values.items()):
        cert_type = (
            AlignmentCertificateType.PROXY_BUNDLE
            if p_star.is_proxy
            else AlignmentCertificateType.EXACT
        )
        evidence: list[str] = []
        if p_star.dataset_id:
            evidence.append(f"dataset:{p_star.dataset_id}")
        if p_star.raw_variable:
            evidence.append(f"raw_var:{p_star.raw_variable}")
        certificates.append(
            AlignmentCertificate(
                cert_type=cert_type,
                source_variable=variable,
                target_variable=variable,
                confidence=max(0.0, min(1.0, float(p_star.confidence))),
                evidence_refs=evidence,
            )
        )
    if certificates:
        return certificates
    return [
        AlignmentCertificate(
            cert_type=AlignmentCertificateType.TEXT_CONCEPT_MAP,
            source_variable="transport_query",
            target_variable="transport_query",
            confidence=0.6,
            evidence_refs=["fallback:contextual_alignment"],
        )
    ]


def _build_manski_fallback(
    *,
    tr_result: TransportabilityResult,
    state: ResolutionState,
):
    confidences = [float(item.confidence) for item in state.p_star_values.values()]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    half_width = max(0.2, 0.5 - (0.3 * avg_conf))
    outcome_support = (0.5 - half_width, 0.5 + half_width)
    uplift = 0.1 * avg_conf
    outcome_conditioned = [max(0.0, 0.5 - uplift), min(1.0, 0.5 + uplift)]
    treatment_probs = [0.5, 0.5]
    fallback = compute_manski_bounds(
        outcome_conditioned=outcome_conditioned,
        treatment_probs=treatment_probs,
        outcome_support=outcome_support,
    )
    return fallback.model_copy(
        update={
            "assumptions_used": list(fallback.assumptions_used)
            + [f"transport_status={tr_result.status.value}"],
        }
    )


def _build_three_graph_lineage(
    *,
    tr_result: TransportabilityResult,
    state: ResolutionState,
) -> dict[str, Any]:
    dataset_lineage = []
    for variable, value in sorted(state.p_star_values.items()):
        dataset_lineage.append(
            {
                "variable": variable,
                "dataset_id": value.dataset_id,
                "raw_variable": value.raw_variable,
                "proxy_chain": list(value.proxy_chain),
                "confidence": float(value.confidence),
                "ci_low": value.ci_low,
                "ci_high": value.ci_high,
                "std_error": value.std_error,
                "imputation_method": value.imputation_method,
                "uncertainty_sources": list(value.uncertainty_sources),
                "data_support_year": value.data_support_year,
                "data_support_country": value.data_support_country,
            }
        )
    legal_lineage = [
        {
            "constraint_id": node.legal_constraint_id,
            "target_variable": node.target_variable,
            "origin": node.origin.value,
        }
        for node in state.legal_s_nodes
    ]
    return {
        "article": {
            "query": tr_result.query,
            "source_context_id": tr_result.source_context_id,
            "target_context_id": tr_result.target_context_id,
        },
        "dataset": dataset_lineage,
        "legal": legal_lineage,
        "all_layers_present": bool(tr_result.query and dataset_lineage and legal_lineage),
    }


def _build_infeasible_result(
    *,
    source_context: ContextProfile,
    target_context: ContextProfile,
    hard_constraints: list[LegalConstraint],
    query_treatment: str,
    query_outcome: str,
) -> TransportabilityResult:
    return TransportabilityResult(
        query=f"P*({query_outcome}|do({query_treatment}))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        base_confidence=0.0,
        context_distance_penalty=0.0,
        data_availability_penalty=0.0,
        final_confidence=0.0,
        algorithm_version="trso_v2",
        feasible=False,
        hard_legal_constraints=[item.constraint_id for item in hard_constraints],
        warnings=[
            f"HARD legal constraint blocks transportability: {item.description}"
            for item in hard_constraints
        ],
        source_context_id=source_context.context_id,
        target_context_id=target_context.context_id,
        identification_engine="simplified_legacy",
        identification_trace=["resolution_loop:hard_legal_constraint"],
        unsupported_reason="hard_legal_constraint",
    )


def _evaluate_legal_constraints(
    *,
    target_context: ContextProfile,
    policy_spec: Mapping[str, Any] | None,
    causal_graph: CausalGraphModel,
    legal_kg_db_path: Path | None,
) -> LegalConstraintSet:
    if not policy_spec:
        return LegalConstraintSet(
            jurisdiction=target_context.context_id,
            policy_domain="",
            hard_constraints=[],
            soft_constraints=[],
            data_license_constraints=[],
            legal_dag_mappings=[],
        )
    domain = str(policy_spec.get("domain", ""))
    return evaluate_transport_constraints(
        jurisdiction=target_context.context_id,
        policy_domain=domain,
        policy_spec=dict(policy_spec),
        causal_graph=causal_graph.model_dump(mode="json"),
        legal_kg_db_path=legal_kg_db_path,
    )


def _legal_constraints_to_s_nodes(
    *,
    mappings: list[LegalToDAGMapping],
    causal_graph: CausalGraphModel,
) -> list[SNode]:
    graph_nodes = set(causal_graph.nodes)
    nodes: list[SNode] = []
    seen: set[tuple[str, str]] = set()
    for mapping in mappings:
        constraint = mapping.legal_constraint
        severity = "high" if constraint.severity == ConstraintSeverity.HARD else "medium"
        delta = 1.0 if constraint.severity == ConstraintSeverity.HARD else 0.4
        target_var = _pick_legal_target_variable(mapping, graph_nodes)
        if target_var is None:
            continue
        key = (target_var, constraint.constraint_id)
        if key in seen:
            continue
        seen.add(key)
        nodes.append(
            SNode(
                target_variable=target_var,
                context_dimension="legal_constraint",
                source_value="unconstrained",
                target_value=constraint.constraint_id,
                delta=delta,
                severity=severity,  # type: ignore[arg-type]
                origin=SNodeOrigin.LEGAL,
                legal_constraint_id=constraint.constraint_id,
            )
        )
    return nodes


def _pick_legal_target_variable(
    mapping: LegalToDAGMapping,
    graph_nodes: set[str],
) -> str | None:
    candidate = mapping.new_node_name
    if candidate and candidate in graph_nodes:
        return candidate
    for src, dst in mapping.affected_edges:
        if dst in graph_nodes:
            return dst
        if src in graph_nodes:
            return src
    return None


def _resolve_query_treatment(state: ExperimentState, report: CausalEffectReport) -> str:
    raw = state.params.get("query_treatment")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    for key in ("query_treatment", "treatment", "treatment_name"):
        value = report.method_params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    value = report.metadata.get("query_treatment")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "treatment"


def _resolve_query_outcome(state: ExperimentState, report: CausalEffectReport) -> str:
    raw = state.params.get("query_outcome")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    for key in ("query_outcome", "outcome", "outcome_name"):
        value = report.method_params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "outcome"


def _resolve_treatment_value(policy_spec: Mapping[str, Any] | None) -> float:
    if not policy_spec:
        return 1.0
    for key in ("query_treatment_value", "treatment_value", "value", "dose"):
        raw = policy_spec.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return 1.0


def _resolve_context_year(context: ContextProfile) -> int:
    if context.publication_year is not None:
        return int(context.publication_year)
    token = (context.time_period or "").strip()
    for chunk in token.replace("/", "-").split("-"):
        chunk = chunk.strip()
        if len(chunk) == 4 and chunk.isdigit():
            return int(chunk)
    return 2020


def _resolve_context_profile(raw: Any) -> ContextProfile | None:
    if isinstance(raw, ContextProfile):
        return raw
    if isinstance(raw, Mapping):
        try:
            return ContextProfile.model_validate(raw)
        except _TRANSPORT_VALIDATION_ERRORS:
            return None
    return None


def _resolve_transport_solver_mode(state: ExperimentState) -> str:
    raw = state.params.get("transport_solver_mode")
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token in _VALID_TRANSPORT_SOLVER_MODES:
            return token
    return "auto"


def _resolve_allow_degraded_transport(state: ExperimentState) -> bool:
    raw = state.params.get("allow_degraded_transport")
    profile = (
        str(state.execution_profile or state.params.get("execution_profile") or "").strip().lower()
    )
    if isinstance(raw, bool):
        if raw and profile in {"research", "governed", "production"}:
            raise ValueError(
                "allow_degraded_transport is forbidden outside the dev execution profile"
            )
        return raw
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token in {"1", "true", "yes", "on"}:
            if profile in {"research", "governed", "production"}:
                raise ValueError(
                    "allow_degraded_transport is forbidden outside the dev execution profile"
                )
            return True
        if token in {"0", "false", "no", "off"}:
            return False
    workflow_id = str(state.params.get("workflow_id", "")).strip().lower()
    if workflow_id == "scientist_causal_full":
        return False
    return False


def _resolve_or_build_capability_contract(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> tuple[CausalCapabilityContract, CausalCapabilityContractRef]:
    raw_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF)
    if raw_ref is not None:
        try:
            ref = CausalCapabilityContractRef.model_validate(raw_ref.model_dump(mode="json"))
            return load_causal_capability_contract(ctx.store, ref), ref
        except _TRANSPORT_LOAD_ERRORS:
            logger.debug(
                "Failed to load causal capability contract from ref %s, rebuilding",
                raw_ref,
                exc_info=True,
            )
    contract = build_causal_capability_contract()
    ref = persist_causal_capability_contract(ctx.store, contract)
    return contract, ref


def _resolve_pag_identification_policy(state: ExperimentState, graph: CausalGraphModel) -> str:
    raw = state.params.get("pag_identification_policy")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().lower()
    if graph.graph_type.value == "pag":
        return "probabilistic"
    return "conservative"


def _resolve_pag_max_dag_samples(state: ExperimentState) -> int:
    raw = state.params.get("pag_max_dag_samples")
    try:
        parsed = int(raw) if raw is not None else 100
    except _TRANSPORT_NUMERIC_PARSE_ERRORS:
        return 100
    if parsed < 1:
        return 1
    return min(parsed, 500)


def _resolve_pag_threshold(state: ExperimentState) -> float:
    raw = state.params.get("pag_threshold")
    try:
        parsed = float(raw) if raw is not None else 0.5
    except _TRANSPORT_NUMERIC_PARSE_ERRORS:
        return 0.5
    if parsed < 0.0:
        return 0.0
    if parsed > 1.0:
        return 1.0
    return parsed


def _resolve_pag_seed(state: ExperimentState, graph: CausalGraphModel) -> int:
    raw = state.params.get("pag_seed")
    if raw is not None:
        try:
            return int(raw)
        except _TRANSPORT_NUMERIC_PARSE_ERRORS:
            logger.debug(
                "Failed to parse pag_seed override; deriving deterministic seed", exc_info=True
            )
    payload = f"{state.run_id}|{graph.model_dump_json(exclude_none=False, by_alias=True)}"
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16) % (2**31 - 1)


def _build_graph_ref_from_artifact_id(artifact_id: str) -> CausalGraphModelRef | None:
    try:
        return CausalGraphModelRef.model_validate(
            {
                "artifact_id": artifact_id,
                "kind": "ir.causal_graph_model",
                "media_type": "application/json",
            }
        )
    except _TRANSPORT_VALIDATION_ERRORS:
        return None


def _resolve_causal_graph(ctx: ExecutionContext, state: ExperimentState) -> CausalGraphModel | None:
    ensemble_ref_raw = state.artifacts_index.get(ARTIFACT_CAUSAL_ENSEMBLE_REF)
    if ensemble_ref_raw is not None:
        try:
            ensemble_ref = CausalModelEnsembleRef.model_validate(
                ensemble_ref_raw.model_dump(mode="json")
            )
            ensemble = load_causal_model_ensemble(ctx.store, ensemble_ref)
            if ensemble.consensus_graph_ref:
                consensus_ref = _build_graph_ref_from_artifact_id(ensemble.consensus_graph_ref)
                if consensus_ref is not None:
                    return load_causal_graph_model(ctx.store, consensus_ref)
        except _TRANSPORT_LOAD_ERRORS:
            logger.debug(
                "Failed to load causal graph from ensemble ref %s; trying fallback refs",
                ensemble_ref_raw,
                exc_info=True,
            )

    for key in (ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF, "causal_graph_ref"):
        ref_raw = state.artifacts_index.get(key)
        if ref_raw is None:
            continue
        try:
            graph_ref = CausalGraphModelRef.model_validate(ref_raw.model_dump(mode="json"))
            return load_causal_graph_model(ctx.store, graph_ref)
        except _TRANSPORT_LOAD_ERRORS:
            continue
    return None


def _build_dataset_registry(raw_path: Any) -> DatasetRegistry | _NullDatasetRegistry:
    path = _coerce_path(raw_path)
    if path is None or not path.exists():
        return _NullDatasetRegistry()
    return DatasetRegistry(path)


def _build_skg_query(db_path: Any, index_dir: Any) -> SKGQuery | _NullSKG:
    db = _coerce_path(db_path)
    if db is None or not db.exists():
        return _NullSKG()
    index = _coerce_path(index_dir) or db.parent
    try:
        return SKGQuery(db_path=db, index_dir=index)
    except _TRANSPORT_LOAD_ERRORS:
        return _NullSKG()


def _coerce_path(raw: Any) -> Path | None:
    if raw is None:
        return None
    if isinstance(raw, Path):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return Path(text)
    return None


def _build_adjacency(graph: CausalGraphModel) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {str(node): set() for node in graph.nodes}
    for edge in graph.edges:
        src = str(edge.src).strip()
        dst = str(edge.dst).strip()
        if not src or not dst:
            continue
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set())
    return adjacency


def _proxy_validity_score(checklist: Any) -> float:
    checks = [
        bool(getattr(checklist, "relevance_check", False)),
        bool(getattr(checklist, "exclusion_check", False)),
        bool(getattr(checklist, "non_collider_check", False)),
        bool(getattr(checklist, "completeness_check", False)),
    ]
    passed = sum(1 for item in checks if item)
    score = passed / max(1, len(checks))
    return max(0.2, min(1.0, float(score)))


def _suggest_data_collection(var: str) -> str:
    return (
        f"Collect or map target-context data for '{var}' "
        "or register a higher-confidence proxy in dataset alignments."
    )


__all__ = ["ResolutionState", "RunTransportabilityNode", "TransportabilityResolutionLoop"]
