"""Public causal resolve transport module API."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
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
from polisyos.ir.registry.refs import (
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
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.academic import PreparedSKGRead
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

from .transport_resolution_inputs import (
    InvalidTransportInput,
    _build_dataset_registry,
    _coerce_path,
    _LoopDatasetRegistry,
    _normalize_transport_solver_mode,
    _NullDatasetRegistry,
    _NullSKG,
    _resolve_allow_degraded_transport,
    _resolve_causal_graph,
    _resolve_context_profile,
    _resolve_context_year,
    _resolve_or_build_capability_contract,
    _resolve_pag_identification_policy,
    _resolve_pag_max_dag_samples,
    _resolve_pag_seed,
    _resolve_pag_threshold,
    _resolve_query_outcome,
    _resolve_query_outcome_for_blocking,
    _resolve_query_treatment,
    _resolve_query_treatment_for_blocking,
    _resolve_transport_execution_inputs,
    _resolve_transport_privacy_context,
    _resolve_transport_solver_mode,
    _resolve_treatment_value,
    _transport_execution_profile,
)
from .transport_resolution_inputs import (
    build_skg_query as _build_skg_query_impl,
)
from .transport_resolution_results import (
    _build_adjacency,
    _build_blocking_transportability_result,
    _build_final_result,
    _build_infeasible_result,
    _build_proxy_quantity_or_gap,
    _finalize_transport_loop_result,
    _invalid_transport_input_outcome,
    _legal_constraints_to_s_nodes,
    _proxy_validity_score,
    _suggest_data_collection,
)

logger = get_logger(__name__)

_TRANSPORT_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_TRANSPORT_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_TRANSPORT_NUMERIC_PARSE_ERRORS = (TypeError, ValueError, OverflowError)

MAX_ROUNDS = 3
PROXY_FALLBACK_THRESHOLD = 0.3
_SERIOUS_TRANSPORT_PROFILES: frozenset[str] = frozenset({"research", "governed", "production"})


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
        "params.transport_required",
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

    @staticmethod
    def _record_proxy_fallback(
        *,
        variable: str,
        fallback: tuple[
            PStarZResult | None,
            DataGap | None,
            dict[str, Any] | None,
            float | None,
            bool,
            list[str],
        ],
        p_star_values: dict[str, PStarZResult],
        data_gaps: list[DataGap],
        proxy_penalties: dict[str, float],
        proxy_validity: dict[str, dict[str, Any]],
        requires_expert_review: bool,
        expert_review_reasons: list[str],
    ) -> bool:
        (
            proxy_value,
            data_gap,
            proxy_validity_value,
            proxy_penalty,
            proxy_requires_expert_review,
            proxy_expert_review_reasons,
        ) = fallback
        if proxy_validity_value is not None:
            proxy_validity[variable] = proxy_validity_value
        if proxy_requires_expert_review:
            requires_expert_review = True
            for reason in proxy_expert_review_reasons:
                if reason not in expert_review_reasons:
                    expert_review_reasons.append(reason)
        if proxy_value is not None:
            p_star_values[variable] = proxy_value
        if proxy_penalty is not None:
            proxy_penalties[variable] = proxy_penalty
        if data_gap is not None:
            data_gaps.append(data_gap)
        return requires_expert_review

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
        normalized_solver_mode = _normalize_transport_solver_mode(solver_mode)
        _resolve_treatment_value(policy_spec)
        try:
            cached_registry = self._cached_dataset_registry()
            prev_s_node_set: set[tuple[str, str, str]] = set()
            legal_mapping_review_reasons: list[str] = []
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
                    expert_review_reasons=legal_mapping_review_reasons,
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
                requires_expert_review = bool(legal_mapping_review_reasons)
                expert_review_reasons = list(legal_mapping_review_reasons)
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
                        fallback = _build_proxy_quantity_or_gap(
                            variable=z_var,
                            target_context=target_context,
                            outcome=query_outcome,
                            adjacency=adjacency,
                            proxy_chain=proxy_chain,
                            condition_on=condition_on,
                            proxy_threshold=self._proxy_threshold,
                            validate_proxy_fn=validate_proxy,
                            compose_confidence_harmonic_fn=compose_confidence_harmonic,
                        )
                        requires_expert_review = self._record_proxy_fallback(
                            variable=z_var,
                            fallback=fallback,
                            p_star_values=p_star_values,
                            data_gaps=data_gaps,
                            proxy_penalties=proxy_penalties,
                            proxy_validity=proxy_validity,
                            requires_expert_review=requires_expert_review,
                            expert_review_reasons=expert_review_reasons,
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

    def prepare_cache_input(
        self,
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> PreparedSKGRead | None:
        """Bind cache lookup to the selected academic source database."""
        del ctx
        db_path_raw = state.params.get("skg_db_path")
        if not isinstance(db_path_raw, str) or not db_path_raw.strip():
            return None
        db_path = Path(db_path_raw)
        index_dir_raw = state.params.get("skg_index_dir")
        index_dir = Path(str(index_dir_raw)) if index_dir_raw else db_path.parent
        return SKGQuery.prepare_read(db_path=db_path, index_dir=index_dir)

    @staticmethod
    def _missing_report_outcome(
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> NodeOutcome:
        try:
            _resolve_query_treatment_for_blocking(state, None)
            _resolve_query_outcome_for_blocking(state, None)
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)
        if _is_serious_transport_profile(state):
            return _persist_blocking_transportability_result(
                ctx=ctx,
                state=state,
                reason="missing_causal_report",
                message=(
                    "No causal report artifact found; persisted unsupported "
                    "transportability result for serious workflow traceability."
                ),
            )
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

    @staticmethod
    def _bind_privacy_context(
        ctx: ExecutionContext,
        privacy_context: TransportPrivacyContext | None,
        input_refs: list[InputRef],
    ) -> TransportPrivacyContext | None:
        if privacy_context is None:
            return None
        return privacy_context.model_copy(
            update={
                "store": ctx.store,
                "inputs": tuple([*privacy_context.inputs, *input_refs]),
            }
        )

    @staticmethod
    def _select_skg_query(
        ctx: ExecutionContext,
        state: ExperimentState,
    ) -> tuple[SKGQuery | _NullSKG, bool] | None:
        prepared_read = ctx.prepared_skg_read
        configured_skg_path = state.params.get("skg_db_path")
        if prepared_read is not None and isinstance(configured_skg_path, str):
            if not prepared_read.matches_path(configured_skg_path):
                return None
            return prepared_read.query, False
        skg_query = _build_skg_query(
            db_path=configured_skg_path,
            index_dir=state.params.get("skg_index_dir"),
        )
        return skg_query, isinstance(skg_query, SKGQuery)

    @staticmethod
    def _missing_context_outcome(
        *,
        ctx: ExecutionContext,
        state: ExperimentState,
        causal_report: CausalEffectReport,
        report_ref: CausalEffectReportRef,
        source_context: ContextProfile | None,
        target_context: ContextProfile | None,
    ) -> NodeOutcome:
        if _is_serious_transport_profile(state):
            return _persist_blocking_transportability_result(
                ctx=ctx,
                state=state,
                reason="missing_source_or_target_context",
                message=(
                    "Missing source/target context profile; persisted unsupported "
                    "transportability result for serious workflow traceability."
                ),
                causal_report=causal_report,
                report_ref=report_ref,
                source_context=source_context,
                target_context=target_context,
            )
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

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        report_ref_raw = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
        if report_ref_raw is None:
            return self._missing_report_outcome(ctx, state)

        try:
            report_ref = CausalEffectReportRef.model_validate(
                report_ref_raw.model_dump(mode="json")
            )
            causal_report = load_causal_effect_report(
                _ensure_ir_artifact_store(ctx.store), report_ref
            )
        except _TRANSPORT_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message=f"Failed to load CausalEffectReport: {exc}",
                ),
            )

        try:
            treatment = _resolve_query_treatment(state, causal_report)
            outcome = _resolve_query_outcome(state, causal_report)
            source_context = _resolve_context_profile(state.params.get("source_context"))
            target_context = _resolve_context_profile(state.params.get("target_context"))
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)
        if source_context is None or target_context is None:
            return self._missing_context_outcome(
                ctx=ctx,
                state=state,
                causal_report=causal_report,
                report_ref=report_ref,
                source_context=source_context,
                target_context=target_context,
            )

        graph = _resolve_causal_graph(ctx, state)
        if graph is None:
            if _is_serious_transport_profile(state):
                return _persist_blocking_transportability_result(
                    ctx=ctx,
                    state=state,
                    reason="missing_causal_graph",
                    message=(
                        "No causal graph available; persisted unsupported "
                        "transportability result for serious workflow traceability."
                    ),
                    causal_report=causal_report,
                    report_ref=report_ref,
                    source_context=source_context,
                    target_context=target_context,
                )
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

        try:
            resolved_inputs = _resolve_transport_execution_inputs(
                state,
                causal_report,
                graph,
                privacy_context_resolver=_resolve_transport_privacy_context,
            )
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)
        treatment = resolved_inputs.query_treatment
        outcome = resolved_inputs.query_outcome
        policy_spec = resolved_inputs.policy_spec
        pag_identification_policy = resolved_inputs.pag_identification_policy
        pag_max_dag_samples = resolved_inputs.pag_max_dag_samples
        pag_threshold = resolved_inputs.pag_threshold
        pag_seed = resolved_inputs.pag_seed
        transport_solver_mode = resolved_inputs.solver_mode
        allow_degraded_transport = resolved_inputs.allow_degraded_transport
        normalization_warnings = resolved_inputs.normalization_warnings
        capability_contract, capability_ref = _resolve_or_build_capability_contract(ctx, state)
        input_refs = [InputRef(artifact_id=report_ref.artifact_id, role="causal_report")]
        privacy_context = self._bind_privacy_context(
            ctx,
            resolved_inputs.privacy_context,
            input_refs,
        )

        dataset_registry = _build_dataset_registry(state.params.get("dataset_registry_db_path"))
        skg_selection = self._select_skg_query(ctx, state)
        if skg_selection is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="Prepared SKG source path does not match transport selector input.",
                ),
            )
        skg_query, owns_skg_query = skg_selection
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
        except InvalidTransportInput as exc:
            return _invalid_transport_input_outcome(state, exc)
        finally:
            if owns_skg_query and isinstance(skg_query, SKGQuery):
                skg_query.close()

        transport_result = transport_result.model_copy(
            update={
                "warnings": [*transport_result.warnings, *normalization_warnings],
            }
        )

        transport_ref = persist_transportability_result(
            _ensure_ir_artifact_store(ctx.store),
            transport_result,
            inputs=input_refs,
        )
        updated_report = causal_report.model_copy(update={"transport_result": transport_result})
        updated_report_ref = persist_causal_effect_report(
            _ensure_ir_artifact_store(ctx.store),
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


def _persist_blocking_transportability_result(
    *,
    ctx: ExecutionContext,
    state: ExperimentState,
    reason: str,
    message: str,
    causal_report: CausalEffectReport | None = None,
    report_ref: CausalEffectReportRef | None = None,
    source_context: ContextProfile | None = None,
    target_context: ContextProfile | None = None,
) -> NodeOutcome:
    capability_contract, capability_ref = _resolve_or_build_capability_contract(ctx, state)
    input_refs: list[InputRef] = []
    if report_ref is not None:
        input_refs.append(InputRef(artifact_id=report_ref.artifact_id, role="causal_report"))

    transport_result = _build_blocking_transportability_result(
        state=state,
        reason=reason,
        message=message,
        causal_report=causal_report,
        source_context=source_context,
        target_context=target_context,
    )
    transport_ref = persist_transportability_result(
        _ensure_ir_artifact_store(ctx.store),
        transport_result,
        inputs=input_refs,
    )

    artifacts = [capability_ref, transport_ref]
    new_state = branch_state(state, write_paths=_SPEC.state_writes).state
    new_state.params["transportability_status"] = transport_result.status.value
    new_state.params["transportability_transport_mode"] = transport_result.transport_mode.value
    new_state.params["transportability_identification_engine"] = (
        transport_result.identification_engine
    )
    new_state.params["transportability_capability_hash"] = (
        capability_contract.dependency_fingerprint
    )
    new_state.params["transportability_degradation_policy"] = capability_contract.degradation_policy
    new_state.params.pop("transportability_id_confidence_under_pag", None)
    new_state.params["transportability_warning"] = f"{reason}: {message}"
    new_state.params["transport_required"] = True
    new_state.artifacts_index[ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF] = capability_ref
    new_state.causal_capability_contract_ref = capability_ref
    new_state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF] = transport_ref

    if causal_report is not None and report_ref is not None:
        updated_report = causal_report.model_copy(update={"transport_result": transport_result})
        updated_report_ref = persist_causal_effect_report(
            _ensure_ir_artifact_store(ctx.store),
            updated_report,
            inputs=[
                InputRef(artifact_id=report_ref.artifact_id, role="causal_report_prev"),
                InputRef(artifact_id=transport_ref.artifact_id, role="transportability_result"),
            ],
        )
        new_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = updated_report_ref
        artifacts.append(updated_report_ref)

    profile = _transport_execution_profile(state)
    return NodeOutcome(
        status="ok",
        state=new_state,
        artifacts=artifacts,
        events=[
            NodeEvent(
                level="warn",
                code="transportability.blocked_prerequisite",
                message=message,
                attrs={"reason": reason, "execution_profile": profile or "unknown"},
            )
        ],
    )


def _is_serious_transport_profile(state: ExperimentState) -> bool:
    return _transport_execution_profile(state) in _SERIOUS_TRANSPORT_PROFILES


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


def _build_skg_query(db_path: Any, index_dir: Any) -> SKGQuery | _NullSKG:
    return _build_skg_query_impl(db_path, index_dir, query_type=SKGQuery)


__all__ = ["ResolutionState", "RunTransportabilityNode", "TransportabilityResolutionLoop"]
