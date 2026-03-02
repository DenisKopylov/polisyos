from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.academic.knowledge.skg_query import SKGQuery
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.datasets.knowledge.proxy_resolver import resolve_proxy
from polisyos.datasets.knowledge.registry import DatasetRegistry
from polisyos.datasets.knowledge.types import PStarZResult
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.causal_ensemble import load_causal_model_ensemble
from polisyos.ir.analytics.causal_graph import CausalGraphModel, load_causal_graph_model
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.transportability import (
    DataGap,
    SelectionDiagram,
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
    build_selection_diagram,
    persist_transportability_result,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.refs import CausalEffectReportRef, CausalGraphModelRef, CausalModelEnsembleRef
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
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_CAUSAL_ENSEMBLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)

MAX_ROUNDS = 3
PROXY_FALLBACK_THRESHOLD = 0.3

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
        "params.dataset_registry_db_path",
        "params.legal_kg_db_path",
        "params.skg_db_path",
        "params.skg_index_dir",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_ENSEMBLE_REF}",
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
    ],
    state_writes=[
        "params.transportability_status",
        "params.transportability_id_confidence_under_pag",
        "params.transportability_warning",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_TRANSPORTABILITY_RESULT_REF}",
    ],
    produces=[ARTIFACT_TRANSPORTABILITY_RESULT_REF, ARTIFACT_CAUSAL_REPORT_REF],
)


class ResolutionState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    round: int
    s_nodes: list[SNode] = Field(default_factory=list)
    legal_s_nodes: list[SNode] = Field(default_factory=list)
    data_gaps: list[DataGap] = Field(default_factory=list)
    hard_constraints: list[LegalConstraint] = Field(default_factory=list)
    p_star_values: dict[str, PStarZResult] = Field(default_factory=dict)
    proxy_penalties: dict[str, float] = Field(default_factory=dict)
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


class TransportabilityResolutionLoop:
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
    ) -> TransportabilityResult:
        prev_s_node_set: set[tuple[str, str, str]] = set()
        state: ResolutionState | None = None
        tr_result: TransportabilityResult | None = None
        diagram: SelectionDiagram | None = None

        for round_num in range(1, self._max_rounds + 1):
            context_diagram = build_selection_diagram(source_context, target_context, causal_graph)
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
                return _build_infeasible_result(
                    source_context=source_context,
                    target_context=target_context,
                    hard_constraints=hard_constraints,
                    query_treatment=query_treatment,
                    query_outcome=query_outcome,
                )

            all_s_nodes = context_s_nodes + legal_s_nodes
            diagram = SelectionDiagram(
                base_graph=causal_graph,
                s_nodes=all_s_nodes,
                source_context=source_context,
                target_context=target_context,
                context_distance=source_context.distance_to(target_context),
            )
            tr_payload = CheckTransportability.pure_step(
                {
                    "selection_diagram": diagram.model_dump(mode="json"),
                    "query_treatment": query_treatment,
                    "query_outcome": query_outcome,
                },
                {
                    "pag_identification_policy": pag_identification_policy,
                    "pag_max_dag_samples": pag_max_dag_samples,
                    "pag_threshold": pag_threshold,
                    "pag_seed": pag_seed if pag_seed is not None else 0,
                },
            )
            tr_result = TransportabilityResult.model_validate(tr_payload["transport_result"])

            p_star_values: dict[str, PStarZResult] = {}
            data_gaps: list[DataGap] = []
            proxy_penalties: dict[str, float] = {}

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

                    p_star = self._datasets.compute_p_star_z(
                        canonical_var=z_var,
                        country_code=target_context.context_id,
                        year=_resolve_context_year(target_context),
                        condition_on=condition_on,
                    )
                    if p_star.value is not None:
                        p_star_values[z_var] = p_star
                        if p_star.is_proxy:
                            proxy_penalties[z_var] = max(0.0, min(1.0, 1.0 - p_star.confidence))
                        continue

                    proxy_chain = resolve_proxy(
                        target_var=z_var,
                        target_context=target_context.context_id,
                        dataset_registry=self._datasets,
                        skg_query=self._skg,
                    )
                    if (
                        proxy_chain.proxies
                        and proxy_chain.best_single_confidence > self._proxy_threshold
                    ):
                        best = proxy_chain.proxies[0]
                        conditional_penalty = 0.1 if condition_on else 0.0
                        confidence = max(
                            0.0,
                            min(1.0, best.effective_confidence - conditional_penalty),
                        )
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
                                f"{target_context.context_id}, "
                                f"{target_context.time_period}"
                            ),
                            available_proxies=proxy_chain.proxies,
                            best_proxy_confidence=proxy_chain.best_single_confidence,
                            gap_impact=(
                                "transport_confidence reduced due to missing target quantity"
                            ),
                            suggested_action=_suggest_data_collection(z_var),
                        )
                    )

            proxy_introduced_vars = {var for var, value in p_star_values.items() if value.is_proxy}
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
                converged=converged,
                feasible=True,
            )
            if converged:
                break

        if tr_result is None or state is None or diagram is None:
            return TransportabilityResult(
                query=f"P*({query_outcome}|do({query_treatment}))",
                status=TransportabilityStatus.NON_TRANSPORTABLE,
                base_confidence=0.0,
                final_confidence=0.0,
                feasible=False,
                warnings=["Transportability resolution failed unexpectedly."],
                source_context_id=source_context.context_id,
                target_context_id=target_context.context_id,
            )
        return _build_final_result(tr_result=tr_result, state=state, diagram=diagram)


@dataclass(frozen=True)
class RunTransportabilityNode:
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
        except Exception as exc:
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
            new_state = state.model_copy(deep=True)
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
                            "Missing source/target context profile; "
                            "transportability check skipped."
                        ),
                    )
                ],
            )

        graph = _resolve_causal_graph(ctx, state)
        if graph is None:
            new_state = state.model_copy(deep=True)
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
            )
        finally:
            if isinstance(skg_query, SKGQuery):
                skg_query.close()

        input_refs = [InputRef(artifact_id=report_ref.artifact_id, role="causal_report")]
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

        new_state = state.model_copy(deep=True)
        new_state.params["transportability_status"] = transport_result.status.value
        if transport_result.id_confidence_under_pag is not None:
            new_state.params["transportability_id_confidence_under_pag"] = (
                transport_result.id_confidence_under_pag
            )
        else:
            new_state.params.pop("transportability_id_confidence_under_pag", None)
        new_state.params.pop("transportability_warning", None)
        new_state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF] = transport_ref
        new_state.artifacts_index[ARTIFACT_CAUSAL_REPORT_REF] = updated_report_ref

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[transport_ref, updated_report_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Transportability resolved: "
                        f"status={transport_result.status.value}, "
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
    if state.data_gaps:
        warnings.append(
            f"Missing target quantities for {len(state.data_gaps)} variable(s); added data_gaps."
        )

    return tr_result.model_copy(
        update={
            "final_confidence": confidence,
            "data_gaps": list(state.data_gaps),
            "p_star_values": dict(state.p_star_values),
            "legal_s_nodes": list(state.legal_s_nodes),
            "resolution_rounds": state.round,
            "feasible": state.feasible,
            "proxy_penalties": dict(state.proxy_penalties),
            "source_context_id": diagram.source_context.context_id,
            "target_context_id": diagram.target_context.context_id,
            "warnings": warnings,
            "algorithm_version": tr_result.algorithm_version,
        }
    )


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
        status=TransportabilityStatus.NON_TRANSPORTABLE,
        base_confidence=0.0,
        context_distance_penalty=0.0,
        data_availability_penalty=0.0,
        final_confidence=0.0,
        algorithm_version="simplified_tr_v2",
        feasible=False,
        hard_legal_constraints=[item.constraint_id for item in hard_constraints],
        warnings=[
            f"HARD legal constraint blocks transportability: {item.description}"
            for item in hard_constraints
        ],
        source_context_id=source_context.context_id,
        target_context_id=target_context.context_id,
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
        except Exception:
            return None
    return None


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
    except Exception:
        return 100
    if parsed < 1:
        return 1
    return min(parsed, 500)


def _resolve_pag_threshold(state: ExperimentState) -> float:
    raw = state.params.get("pag_threshold")
    try:
        parsed = float(raw) if raw is not None else 0.5
    except Exception:
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
        except Exception:
            pass
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
    except Exception:
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
        except Exception:
            pass

    for key in (ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF, "causal_graph_ref"):
        ref_raw = state.artifacts_index.get(key)
        if ref_raw is None:
            continue
        try:
            graph_ref = CausalGraphModelRef.model_validate(ref_raw.model_dump(mode="json"))
            return load_causal_graph_model(ctx.store, graph_ref)
        except Exception:
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
    except Exception:
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


def _suggest_data_collection(var: str) -> str:
    return (
        f"Collect or map target-context data for '{var}' "
        "or register a higher-confidence proxy in dataset alignments."
    )


__all__ = ["ResolutionState", "TransportabilityResolutionLoop", "RunTransportabilityNode"]
