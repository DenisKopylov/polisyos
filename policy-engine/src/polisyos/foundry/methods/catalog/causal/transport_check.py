"""Public causal transport check module API."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    EdgeMark,
    GraphType,
    PAGIdentificationPolicy,
)
from polisyos.ir.analytics.causal import ProofBundle
from polisyos.ir.analytics.negative_certificate import (
    negative_certificate_from_transport_result,
)
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SNode,
    SNodeRole,
    StratificationVariable,
    TransportabilityResult,
    TransportabilityStatus,
    TransportFormula,
    TransportMode,
)

from .transport_engine import solve_transportability


class EliminationResult(BaseModel):
    """Elimination result data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    can_eliminate: bool
    method: str
    adj_var: str | None = None
    role: SNodeRole | None = None
    requires_conditional: bool = False


@foundry_method(
    namespace="causal.transport",
    version="1.0.0",
    tags={"causal", "transportability"},
)
class CheckTransportability:
    """Legacy simplified transportability shim delegated through the canonical engine."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="check_transportability",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="selection_diagram",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("graph", "json"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="transport_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact", "json"),
                )
            }
        ),
        parameters=(
            ParameterSpec(name="pag_identification_policy", default="probabilistic"),
            ParameterSpec(name="pag_max_dag_samples", default=100),
            ParameterSpec(name="pag_threshold", default=0.5),
            ParameterSpec(name="pag_seed", default=0),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Legacy simplified transportability fallback delegated through "
            "the canonical transport engine."
        ),
        assumptions={
            "algorithm_version": "trso_v2",
            "fallback": "explicit simplified_legacy path only",
        },
        tags=frozenset({"causal", "transportability"}),
        when_to_use="Check whether causal effect P*(Y|do(X)) is transportable from source to target context; simplified fallback path",
        when_not_to_use="Symbolic identification required (use SymbolicIdentify); query is purely observational with no context shift",
        output_interpretation="TransportabilityResult: IDENTIFIED = effect is transportable. UNSUPPORTED = cannot transport without additional target-context data. Blocking S-nodes indicate what is needed.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        selection_diagram = SelectionDiagram.model_validate(state["selection_diagram"])
        result = solve_transportability(
            selection_diagram=selection_diagram,
            query_treatment=str(state["query_treatment"]),
            query_outcome=str(state["query_outcome"]),
            solver_mode="simplified",
            allow_degraded_transport=True,
            pag_identification_policy=params.get("pag_identification_policy"),
            pag_max_dag_samples=int(params.get("pag_max_dag_samples", 100) or 100),
            pag_threshold=float(params.get("pag_threshold", 0.5) or 0.5),
            pag_seed=int(params.get("pag_seed", 0) or 0),
        )
        payload: dict[str, Any] = {"transport_result": result.model_dump(mode="json")}
        if result.status is TransportabilityStatus.IDENTIFIED:
            payload["proof_bundle"] = ProofBundle(
                proof_status="identified",
                proof_stratum="A1_extended",
                theorem_family=str(result.algorithm_version or "transportability"),
                completeness_regime="complete",
                implementation_coverage="transportability_solver",
                query_ref=str(result.query or ""),
                proof_trace=list(result.identification_trace),
                assumptions=[],
                metadata={
                    "status": result.status.value,
                    "transport_mode": result.transport_mode.value,
                },
            ).model_dump(mode="json")
            return payload

        negative_certificate = negative_certificate_from_transport_result(
            result=result,
            treatment=str(state["query_treatment"]),
            outcome=str(state["query_outcome"]),
        )
        payload["proof_bundle"] = ProofBundle(
            proof_status="non_identified",
            proof_stratum="A1_extended",
            theorem_family=str(result.algorithm_version or "transportability"),
            completeness_regime="complete",
            implementation_coverage="transportability_solver",
            query_ref=str(result.query or ""),
            negative_certificate_summary=negative_certificate.to_summary(),
            proof_trace=list(result.identification_trace),
            assumptions=[],
            metadata={
                "status": result.status.value,
                "transport_mode": result.transport_mode.value,
                "blocking_type": negative_certificate.blocking_type.value,
            },
        ).model_dump(mode="json")
        payload["negative_certificate"] = negative_certificate.model_dump(mode="json")
        if negative_certificate.bounds_bundle is not None:
            payload["bounds_bundle"] = negative_certificate.bounds_bundle.model_dump(mode="json")
        if negative_certificate.recovery_plan is not None:
            payload["recovery_plan"] = negative_certificate.recovery_plan.model_dump(mode="json")
        return payload


def _legacy_pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        selection_diagram = SelectionDiagram.model_validate(state["selection_diagram"])
        query_treatment = str(state["query_treatment"])
        query_outcome = str(state["query_outcome"])
        graph = selection_diagram.base_graph

        policy = _resolve_pag_policy(
            raw=params.get("pag_identification_policy"),
            graph_type=graph.graph_type,
        )
        if graph.graph_type is GraphType.PAG and policy is PAGIdentificationPolicy.PROBABILISTIC:
            pag_max_dag_samples = max(1, int(params.get("pag_max_dag_samples", 100) or 100))
            pag_threshold = float(params.get("pag_threshold", 0.5) or 0.5)
            if pag_threshold < 0.0:
                pag_threshold = 0.0
            if pag_threshold > 1.0:
                pag_threshold = 1.0
            pag_seed = int(params.get("pag_seed", 0) or 0)
            result = _evaluate_pag_probabilistic(
                selection_diagram=selection_diagram,
                query_treatment=query_treatment,
                query_outcome=query_outcome,
                dag_sample_cap=pag_max_dag_samples,
                threshold=pag_threshold,
                seed=pag_seed,
            )
            return {"transport_result": result.model_dump(mode="json")}

        result = _evaluate_single_graph(
            selection_diagram=selection_diagram,
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            graph=graph,
            algorithm_version="simplified_tr_v2",
        )
        return {"transport_result": result.model_dump(mode="json")}


def _resolve_pag_policy(
    *,
    raw: Any,
    graph_type: GraphType,
) -> PAGIdentificationPolicy:
    if raw is None:
        if graph_type is GraphType.PAG:
            return PAGIdentificationPolicy.PROBABILISTIC
        return PAGIdentificationPolicy.CONSERVATIVE
    try:
        return PAGIdentificationPolicy(str(raw))
    except Exception:
        if graph_type is GraphType.PAG:
            return PAGIdentificationPolicy.PROBABILISTIC
        return PAGIdentificationPolicy.CONSERVATIVE


def _evaluate_pag_probabilistic(
    *,
    selection_diagram: SelectionDiagram,
    query_treatment: str,
    query_outcome: str,
    dag_sample_cap: int,
    threshold: float,
    seed: int,
) -> TransportabilityResult:
    dag_candidates = _sample_dag_candidates_from_pag(
        graph=selection_diagram.base_graph,
        sample_cap=dag_sample_cap,
        seed=seed,
    )
    if not dag_candidates:
        return TransportabilityResult(
            query=f"P*({query_outcome}|do({query_treatment}))",
            status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            base_confidence=0.0,
            context_distance_penalty=0.0,
            data_availability_penalty=0.0,
            final_confidence=0.0,
            algorithm_version="simplified_tr_v2_pag_probabilistic",
            pag_identification_policy=PAGIdentificationPolicy.PROBABILISTIC,
            id_confidence_under_pag=0.0,
            pag_dag_sample_size=0,
            pag_transportable_count=0,
            warnings=[
                "PAG probabilistic identification could not derive any acyclic DAG candidate.",
            ],
            source_context_id=selection_diagram.source_context.context_id,
            target_context_id=selection_diagram.target_context.context_id,
            identification_engine="simplified_legacy",
            identification_trace=["pag_probabilistic:no_dag_candidates"],
            unsupported_reason="pag_dag_sampling_failed",
        )

    evaluated: list[TransportabilityResult] = []
    for dag_graph in dag_candidates:
        evaluated.append(
            _evaluate_single_graph(
                selection_diagram=selection_diagram,
                query_treatment=query_treatment,
                query_outcome=query_outcome,
                graph=dag_graph,
                algorithm_version="simplified_tr_v2",
            )
        )

    total = len(evaluated)
    transportable_count = sum(
        1 for item in evaluated if item.status is not TransportabilityStatus.UNSUPPORTED
    )
    direct_count = sum(
        1
        for item in evaluated
        if item.status is TransportabilityStatus.IDENTIFIED
        and item.transport_mode is TransportMode.DIRECT
    )
    id_confidence = float(transportable_count / total)

    if direct_count == total:
        final_status = TransportabilityStatus.IDENTIFIED
        final_mode = TransportMode.DIRECT
    elif id_confidence >= threshold:
        final_status = TransportabilityStatus.IDENTIFIED
        final_mode = TransportMode.TRANSPORT_FORMULA
    else:
        final_status = TransportabilityStatus.UNSUPPORTED
        final_mode = TransportMode.NONE

    representative = _choose_representative_result(
        results=evaluated,
        status=final_status,
    )
    unsupported = sorted({case for item in evaluated for case in item.unsupported_cases})
    required_target_data = sorted({key for item in evaluated for key in item.required_target_data})
    blocking = (
        list(representative.blocking_s_nodes)
        if final_status is TransportabilityStatus.UNSUPPORTED
        else []
    )
    warnings = list(representative.warnings)
    warnings.append(
        (
            "PAG probabilistic identification: "
            f"{transportable_count}/{total} sampled DAGs transportable "
            f"(threshold={threshold:.3f})."
        )
    )

    return representative.model_copy(
        update={
            "status": final_status,
            "transport_mode": final_mode,
            "transport_formula": (
                representative.transport_formula
                if final_status is not TransportabilityStatus.UNSUPPORTED
                else None
            ),
            "blocking_s_nodes": blocking,
            "final_confidence": float(representative.final_confidence) * id_confidence,
            "algorithm_version": "simplified_tr_v2_pag_probabilistic",
            "unsupported_cases": unsupported,
            "required_target_data": required_target_data,
            "warnings": warnings,
            "pag_identification_policy": PAGIdentificationPolicy.PROBABILISTIC,
            "id_confidence_under_pag": id_confidence,
            "pag_dag_sample_size": total,
            "pag_transportable_count": transportable_count,
            "identification_engine": "simplified_legacy",
            "identification_trace": list(representative.identification_trace)
            + [f"pag_probabilistic:{transportable_count}/{total}"],
            "unsupported_reason": representative.unsupported_reason,
        }
    )


def _choose_representative_result(
    *,
    results: list[TransportabilityResult],
    status: TransportabilityStatus,
) -> TransportabilityResult:
    if status is TransportabilityStatus.IDENTIFIED:
        for item in results:
            if (
                item.status is TransportabilityStatus.IDENTIFIED
                and item.transport_mode is TransportMode.DIRECT
            ):
                return item
    if status is TransportabilityStatus.IDENTIFIED:
        for item in results:
            if (
                item.status is TransportabilityStatus.IDENTIFIED
                and item.transport_mode is TransportMode.TRANSPORT_FORMULA
            ):
                return item
        for item in results:
            if item.status is TransportabilityStatus.IDENTIFIED:
                return item
    if status is TransportabilityStatus.UNSUPPORTED:
        for item in results:
            if item.status is TransportabilityStatus.UNSUPPORTED:
                return item
    return results[0]


def _sample_dag_candidates_from_pag(
    *,
    graph: CausalGraphModel,
    sample_cap: int,
    seed: int,
) -> list[CausalGraphModel]:
    edge_options = [_orientation_options_from_pag_edge(edge) for edge in graph.edges]
    if not edge_options:
        return [
            CausalGraphModel(
                graph_type=GraphType.DAG,
                nodes=list(graph.nodes),
                edges=[],
                discovery_method=graph.discovery_method,
                metadata=dict(graph.metadata),
            )
        ]

    sampled: list[CausalGraphModel] = []
    seen: set[tuple[tuple[str, str, int | None], ...]] = set()

    def _add(indices: list[int]) -> None:
        if len(sampled) >= sample_cap:
            return
        oriented_edges = [edge_options[idx][choice] for idx, choice in enumerate(indices)]
        signature = tuple(
            sorted((edge.src, edge.dst, edge.lag) for edge in oriented_edges)
        )
        if signature in seen:
            return
        if _has_cycle(oriented_edges, graph.nodes):
            return
        seen.add(signature)
        sampled.append(
            CausalGraphModel(
                graph_type=GraphType.DAG,
                nodes=list(graph.nodes),
                edges=oriented_edges,
                discovery_method=graph.discovery_method,
                metadata=dict(graph.metadata),
            )
        )

    baseline = [0 for _ in edge_options]
    _add(baseline)

    rng = np.random.RandomState(seed)
    attempts = max(sample_cap * 60, 200)
    for _ in range(attempts):
        if len(sampled) >= sample_cap:
            break
        proposal: list[int] = []
        for options in edge_options:
            if len(options) == 1:
                proposal.append(0)
            else:
                proposal.append(int(rng.randint(0, len(options))))
        _add(proposal)

    return sampled


def _orientation_options_from_pag_edge(edge: CausalEdge) -> list[CausalEdge]:
    if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
        return [_oriented_edge(edge, src=edge.src, dst=edge.dst)]
    if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.TAIL:
        return [_oriented_edge(edge, src=edge.dst, dst=edge.src)]

    # For PAG endpoint uncertainty (circle endpoints or bidirected marks),
    # sample both DAG-compatible orientations.
    forward = _oriented_edge(edge, src=edge.src, dst=edge.dst)
    backward = _oriented_edge(edge, src=edge.dst, dst=edge.src)
    if forward.src == backward.src and forward.dst == backward.dst:
        return [forward]
    return [forward, backward]


def _oriented_edge(edge: CausalEdge, *, src: str, dst: str) -> CausalEdge:
    return edge.model_copy(
        update={
            "src": src,
            "dst": dst,
            "mark_src": EdgeMark.TAIL,
            "mark_dst": EdgeMark.ARROW,
        }
    )


def _has_cycle(edges: list[CausalEdge], nodes: list[str]) -> bool:
    indegree: dict[str, int] = {node: 0 for node in nodes}
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    for edge in edges:
        if edge.lag not in (None, 0):
            continue
        adjacency.setdefault(edge.src, []).append(edge.dst)
        indegree.setdefault(edge.dst, 0)
        indegree[edge.dst] += 1
        indegree.setdefault(edge.src, indegree.get(edge.src, 0))

    queue = [node for node, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in adjacency.get(node, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return visited != len(indegree)


def _evaluate_single_graph(
    *,
    selection_diagram: SelectionDiagram,
    query_treatment: str,
    query_outcome: str,
    graph: CausalGraphModel,
    algorithm_version: str,
) -> TransportabilityResult:
    s_nodes = list(selection_diagram.s_nodes)
    adjacency = _build_adjacency(graph.nodes, graph.edges)

    # DOD-141: detect lagged edges for time stationarity flag.
    lagged_edges = [e for e in graph.edges if e.lag is not None and e.lag != 0]
    lagged_count = len(lagged_edges)
    has_lagged = lagged_count > 0
    max_lag = max((e.lag for e in lagged_edges), default=0) or 0
    temporal_penalty = min(0.05 * max_lag, 0.3) if has_lagged else 0.0

    if not s_nodes:
        return TransportabilityResult(
            query=f"P*({query_outcome}|do({query_treatment}))",
            status=TransportabilityStatus.IDENTIFIED,
            transport_mode=TransportMode.DIRECT,
            base_confidence=1.0,
            context_distance_penalty=0.0,
            data_availability_penalty=0.0,
            final_confidence=1.0,
            algorithm_version=algorithm_version,
            source_context_id=selection_diagram.source_context.context_id,
            target_context_id=selection_diagram.target_context.context_id,
            assumes_time_stationarity=has_lagged,
            lagged_edge_count=lagged_count,
            temporal_distance_penalty=temporal_penalty,
            identification_engine="simplified_legacy",
            identification_trace=["simplified:direct:no_s_nodes"],
        )

    residual_s_nodes: list[SNode] = []
    elimination_results: dict[str, EliminationResult] = {}
    unsupported_cases: list[str] = []

    for s_node in s_nodes:
        elim = _try_eliminate_s_node_simplified(
            s_var=s_node.target_variable,
            adjacency=adjacency,
            treatment=query_treatment,
            outcome=query_outcome,
        )
        if elim.can_eliminate:
            if elim.adj_var:
                existing = elimination_results.get(elim.adj_var)
                if existing is None:
                    elimination_results[elim.adj_var] = elim
                elif elim.requires_conditional and not existing.requires_conditional:
                    elimination_results[elim.adj_var] = elim
            continue

        if elim.method == "collider_selection_bias":
            unsupported_cases.append(
                f"S-node on {s_node.target_variable}: collider selection-bias case."
            )
        else:
            unsupported_cases.append(
                f"S-node on {s_node.target_variable}: requires advanced TR/front-door."
            )
        residual_s_nodes.append(s_node)

    for var, elim in list(elimination_results.items()):
        if not elim.adj_var:
            continue
        if _has_bidirectional_edge(adjacency, query_treatment, var):
            unsupported_cases.append(
                f"Potential hidden confounder between {query_treatment} and {var}; "
                "front-door/IV required."
            )
            residual_s_nodes.extend([node for node in s_nodes if node.target_variable == var])
            elimination_results.pop(var, None)

    distance = float(selection_diagram.context_distance)
    if residual_s_nodes:
        warnings_list = [
            "Simplified TR identified unresolved S-nodes. "
            "Full do-calculus/front-door may still resolve this case."
        ]
        if has_lagged:
            warnings_list.append(
                f"Transport formula includes {lagged_count} lagged edges; "
                "assumes temporal mechanism stationarity."
            )
        return TransportabilityResult(
            query=f"P*({query_outcome}|do({query_treatment}))",
            status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            blocking_s_nodes=residual_s_nodes,
            base_confidence=0.0,
            context_distance_penalty=0.0,
            data_availability_penalty=0.0,
            final_confidence=0.0,
            algorithm_version=algorithm_version,
            unsupported_cases=unsupported_cases,
            warnings=warnings_list,
            required_target_data=sorted({node.target_variable for node in residual_s_nodes}),
            source_context_id=selection_diagram.source_context.context_id,
            target_context_id=selection_diagram.target_context.context_id,
            assumes_time_stationarity=has_lagged,
            lagged_edge_count=lagged_count,
            temporal_distance_penalty=temporal_penalty,
            identification_engine="simplified_legacy",
            identification_trace=[
                "simplified:unsupported:unresolved_s_nodes",
            ],
            unsupported_reason="simplified_unresolved_s_nodes",
        )

    ordered = [elimination_results[key] for key in sorted(elimination_results)]
    formula = _build_formula(
        query_treatment=query_treatment,
        query_outcome=query_outcome,
        elimination_results=ordered,
    )
    final_confidence = _compute_final_confidence(
        base=1.0,
        distance=distance,
        target_quantities=formula.target_quantities,
    )
    context_penalty = min(distance * 0.3, 0.5)
    data_penalty = 1.0 - (0.95 ** len(formula.target_quantities))
    transportable_warnings: list[str] = []
    if has_lagged:
        transportable_warnings.append(
            f"Transport formula includes {lagged_count} lagged edges; "
            "assumes temporal mechanism stationarity."
        )
    return TransportabilityResult(
        query=f"P*({query_outcome}|do({query_treatment}))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.TRANSPORT_FORMULA,
        transport_formula=formula,
        base_confidence=1.0,
        context_distance_penalty=context_penalty,
        data_availability_penalty=data_penalty,
        final_confidence=final_confidence,
        algorithm_version=algorithm_version,
        unsupported_cases=unsupported_cases,
        warnings=transportable_warnings,
        required_target_data=formula.target_quantities,
        source_context_id=selection_diagram.source_context.context_id,
        target_context_id=selection_diagram.target_context.context_id,
        assumes_time_stationarity=has_lagged,
        lagged_edge_count=lagged_count,
        temporal_distance_penalty=temporal_penalty,
        identification_engine="simplified_legacy",
        identification_trace=["simplified:identified:stratification"],
    )


def _build_formula(
    *,
    query_treatment: str,
    query_outcome: str,
    elimination_results: list[EliminationResult],
) -> TransportFormula:
    adjustment_vars = [item.adj_var for item in elimination_results if item.adj_var]  # type: ignore[list-item]
    target_quantities: list[str] = []
    source_quantities: list[str] = []
    strat_details: list[StratificationVariable] = []

    if not adjustment_vars:
        return TransportFormula(
            formula_str=(
                f"P*({query_outcome}|do({query_treatment})) = "
                f"P({query_outcome}|do({query_treatment}))"
            ),
            stratification_variables=[],
            stratification_details=[],
            source_quantities=[f"P({query_outcome}|do({query_treatment}))"],
            target_quantities=[],
            adjustment_type="direct",
        )

    for elimination in elimination_results:
        if not elimination.adj_var:
            continue
        var = elimination.adj_var
        source_quantities.append(f"P({query_outcome}|do({query_treatment}),{var})")
        if elimination.requires_conditional:
            target_quantities.append(f"P*({var}|{query_treatment})")
        else:
            target_quantities.append(f"P*({var})")
        if elimination.role is not None:
            strat_details.append(
                StratificationVariable(
                    name=var,
                    role=elimination.role,
                    requires_conditional=elimination.requires_conditional,
                    condition_on_treatment=(
                        query_treatment if elimination.requires_conditional else None
                    ),
                )
            )

    return TransportFormula(
        formula_str=_build_formula_str(
            query_outcome=query_outcome,
            query_treatment=query_treatment,
            adjustments=adjustment_vars,
        ),
        stratification_variables=adjustment_vars,
        stratification_details=strat_details,
        source_quantities=source_quantities,
        target_quantities=target_quantities,
        adjustment_type="stratification",
    )


def _build_formula_str(
    *,
    query_outcome: str,
    query_treatment: str,
    adjustments: list[str],
) -> str:
    if not adjustments:
        return (
            f"P*({query_outcome}|do({query_treatment})) = "
            f"P({query_outcome}|do({query_treatment}))"
        )
    join_vars = ",".join(adjustments)
    terms = [
        f"P({query_outcome}|do({query_treatment}),{var}) * P*({var})"
        for var in adjustments
    ]
    return (
        f"P*({query_outcome}|do({query_treatment})) = "
        f"Σ_{{{join_vars}}} " + " * ".join(terms)
    )


def _try_eliminate_s_node_simplified(
    *,
    s_var: str,
    adjacency: dict[str, set[str]],
    treatment: str,
    outcome: str,
) -> EliminationResult:
    if s_var not in adjacency or treatment not in adjacency or outcome not in adjacency:
        return EliminationResult(can_eliminate=False, method="node_not_found")

    if _is_collider(adjacency, var=s_var, treatment=treatment, outcome=outcome):
        return EliminationResult(
            can_eliminate=False,
            method="collider_selection_bias",
            role=SNodeRole.COLLIDER,
        )

    is_ancestor_of_treatment = _has_path(adjacency, s_var, treatment, avoid=None)
    if not is_ancestor_of_treatment and not _is_on_all_causal_paths(
        adjacency, treatment, outcome, s_var
    ):
        return EliminationResult(can_eliminate=True, method="not_ancestor")

    if _is_pre_treatment_covariate(adjacency, var=s_var, treatment=treatment, outcome=outcome):
        return EliminationResult(
            can_eliminate=True,
            method="backdoor_adjustment",
            adj_var=s_var,
            role=SNodeRole.PRE_TREATMENT_COVARIATE,
            requires_conditional=False,
        )

    if _is_mediator(adjacency, treatment=treatment, outcome=outcome, var=s_var):
        return EliminationResult(
            can_eliminate=True,
            method="mediator_stratification",
            adj_var=s_var,
            role=SNodeRole.MEDIATOR,
            requires_conditional=True,
        )

    return EliminationResult(can_eliminate=False, method="needs_advanced_tr")


def _build_adjacency(nodes: list[str], edges: list[Any]) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {str(node): set() for node in nodes}
    for edge in edges:
        src = str(getattr(edge, "src", ""))
        dst = str(getattr(edge, "dst", ""))
        if src and dst:
            adjacency.setdefault(src, set()).add(dst)
            adjacency.setdefault(dst, set())
    return adjacency


def _has_path(
    adjacency: dict[str, set[str]],
    start: str,
    goal: str,
    avoid: str | None,
) -> bool:
    if start == goal:
        return True
    if avoid is not None and (start == avoid or goal == avoid):
        return False
    queue: list[str] = [start]
    seen: set[str] = {start}
    while queue:
        node = queue.pop(0)
        for nxt in adjacency.get(node, set()):
            if avoid is not None and nxt == avoid:
                continue
            if nxt == goal:
                return True
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return False


def _is_on_all_causal_paths(
    adjacency: dict[str, set[str]],
    treatment: str,
    outcome: str,
    variable: str,
) -> bool:
    if variable in {treatment, outcome}:
        return True
    return not _has_path(adjacency, treatment, outcome, avoid=variable)


def _is_pre_treatment_covariate(
    adjacency: dict[str, set[str]],
    *,
    var: str,
    treatment: str,
    outcome: str,
) -> bool:
    return (
        _has_path(adjacency, var, treatment, avoid=None)
        and _has_path(adjacency, var, outcome, avoid=None)
        and not _has_path(adjacency, treatment, var, avoid=None)
    )


def _is_mediator(
    adjacency: dict[str, set[str]],
    *,
    treatment: str,
    outcome: str,
    var: str,
) -> bool:
    return _has_path(adjacency, treatment, var, avoid=None) and _has_path(
        adjacency, var, outcome, avoid=None
    )


def _is_collider(
    adjacency: dict[str, set[str]],
    *,
    var: str,
    treatment: str,
    outcome: str,
) -> bool:
    return var in adjacency.get(treatment, set()) and var in adjacency.get(outcome, set())


def _has_bidirectional_edge(adjacency: dict[str, set[str]], node_a: str, node_b: str) -> bool:
    return node_b in adjacency.get(node_a, set()) and node_a in adjacency.get(node_b, set())


def _compute_final_confidence(
    *,
    base: float,
    distance: float,
    target_quantities: list[str],
) -> float:
    distance_factor = 1.0 - min(max(distance, 0.0) * 0.3, 0.5)
    data_factor = 0.95 ** max(0, len(target_quantities))
    confidence = float(base) * distance_factor * data_factor
    if confidence < 0.0:
        return 0.0
    if confidence > 1.0:
        return 1.0
    return confidence


__all__ = ["CheckTransportability", "EliminationResult", "_legacy_pure_step"]
