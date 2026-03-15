from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

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
from polisyos.foundry.methods.catalog.causal.full_transport_bridge import (
    normalize_symbolic_backend_mode,
    normalize_transport_formula,
    probe_backend_availability,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    SNodeRole,
    StratificationVariable,
    TransportabilityResult,
    TransportabilityStatus,
    TransportFormula,
    TransportMode,
)

from .transport_engine import solve_transportability


def _y0_available() -> tuple[bool, str | None]:
    return probe_backend_availability("y0")


def _r_backend_available() -> tuple[bool, str | None]:
    return probe_backend_availability("r")


def _resolve_symbolic_backend_locally(
    mode: str,
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    if mode == "y0":
        order = ("y0",)
    elif mode == "r":
        order = ("r",)
    else:
        order = ("y0", "r")

    unavailable: list[str] = []
    for backend in order:
        ok, reason = _y0_available() if backend == "y0" else _r_backend_available()
        if ok:
            return backend, order, tuple(unavailable)
        if reason:
            unavailable.append(reason)
    return None, order, tuple(unavailable)


def _directed_edges(graph: CausalGraphModel) -> set[tuple[str, str]]:
    directed: set[tuple[str, str]] = set()
    for edge in graph.edges:
        direction = _edge_direction(edge)
        if direction is not None:
            directed.add(direction)
    return directed


def _edge_direction(edge: CausalEdge) -> tuple[str, str] | None:
    if edge.mark_src is EdgeMark.ARROW and edge.mark_dst in {EdgeMark.TAIL, EdgeMark.CIRCLE}:
        return edge.dst, edge.src
    if edge.mark_dst is EdgeMark.ARROW and edge.mark_src in {EdgeMark.TAIL, EdgeMark.CIRCLE}:
        return edge.src, edge.dst
    if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.TAIL:
        return None
    return edge.src, edge.dst


def convert_graph_to_symbolic_repr(graph: CausalGraphModel) -> dict[str, Any]:
    directed = sorted(_directed_edges(graph))
    bidirected: list[tuple[str, str]] = []
    directed_set = set(directed)
    seen: set[tuple[str, str]] = set()
    for src, dst in directed:
        if (dst, src) in directed_set:
            key = tuple(sorted((src, dst)))
            if key in seen:
                continue
            seen.add(key)
            bidirected.append(key)
    return {
        "nodes": list(graph.nodes),
        "directed_edges": directed,
        "bidirected_edges": bidirected,
        "graph_type": graph.graph_type.value,
    }


def _frontdoor_mediator(
    *,
    graph: CausalGraphModel,
    treatment: str,
    outcome: str,
) -> str | None:
    directed = _directed_edges(graph)
    mediators = sorted(
        {
            mediator
            for src, mediator in directed
            if src == treatment and (mediator, outcome) in directed
        }
    )
    if not mediators:
        return None
    # Prefer mediator with no direct edge from treatment to outcome in either direction.
    if (treatment, outcome) in directed or (outcome, treatment) in directed:
        return mediators[0]
    return mediators[0]


def _build_frontdoor_formula(*, treatment: str, outcome: str, mediator: str) -> TransportFormula:
    normalized = normalize_transport_formula(
        formula=(
            f"P*({outcome}|do({treatment})) = "
            f"Σ_{{{mediator}}} P*({mediator}|{treatment}) * "
            f"Σ_{{{treatment}}} P({outcome}|{mediator},{treatment})P({treatment})"
        ),
    )
    return TransportFormula(
        formula_str=normalized.formula_str,
        stratification_variables=[*normalized.stratification_variables] or [mediator],
        stratification_details=[
            StratificationVariable(
                name=mediator,
                role=SNodeRole.MEDIATOR,
                requires_conditional=True,
                condition_on_treatment=treatment,
            )
        ],
        source_quantities=[
            *normalized.source_quantities,
        ]
        or [
            f"P({outcome}|{mediator},{treatment})",
            f"P({treatment})",
        ],
        target_quantities=[*normalized.target_quantities] or [f"P*({mediator}|{treatment})"],
        adjustment_type="frontdoor_symbolic",
    )


def _merge_warnings(*warnings_lists: list[str]) -> list[str]:
    merged: list[str] = []
    for warnings in warnings_lists:
        for warning in warnings:
            if warning not in merged:
                merged.append(warning)
    return merged


def _symbolic_engine_name(backend_name: str | None) -> str:
    if backend_name == "r":
        return "r_causaleffect"
    return "y0"


def _unsupported_symbolic_result(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    trace: list[str],
    backend_name: str | None,
    reason: str,
) -> TransportabilityResult:
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        base_confidence=0.0,
        context_distance_penalty=0.0,
        data_availability_penalty=0.0,
        final_confidence=0.0,
        algorithm_version="symbolic_transport_v1",
        identification_engine=_symbolic_engine_name(backend_name),
        identification_trace=[*trace, f"symbolic_backend_unavailable:{reason}"],
        unsupported_reason=reason,
        warnings=["Requested symbolic transport backend is unavailable."],
        source_context_id=diagram.source_context.context_id,
        target_context_id=diagram.target_context.context_id,
    )


def _symbolic_from_frontdoor(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    trace: list[str],
    backend_name: str,
) -> TransportabilityResult | None:
    mediator = _frontdoor_mediator(
        graph=diagram.base_graph,
        treatment=treatment,
        outcome=outcome,
    )
    if mediator is None:
        return None
    formula = _build_frontdoor_formula(treatment=treatment, outcome=outcome, mediator=mediator)
    distance = float(diagram.context_distance)
    context_penalty = min(distance * 0.35, 0.6)
    data_penalty = 1.0 - (0.9 ** len(formula.target_quantities))
    confidence = max(0.0, min(1.0, 1.0 - context_penalty - data_penalty))
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.IDENTIFIED,
        transport_mode=TransportMode.TRANSPORT_FORMULA,
        transport_formula=formula,
        base_confidence=1.0,
        context_distance_penalty=context_penalty,
        data_availability_penalty=data_penalty,
        final_confidence=confidence,
        algorithm_version="symbolic_transport_v1",
        warnings=[
            "Symbolic identification used front-door style derivation.",
            f"symbolic_backend={backend_name}",
        ],
        required_target_data=list(formula.target_quantities),
        source_context_id=diagram.source_context.context_id,
        target_context_id=diagram.target_context.context_id,
        identification_engine="r_causaleffect" if backend_name == "r" else "y0",
        identification_trace=trace + [f"symbolic_success:{backend_name}:frontdoor:{mediator}"],
    )


def _state_payload(
    *,
    selection_diagram: SelectionDiagram,
    query_treatment: str,
    query_outcome: str,
) -> dict[str, Any]:
    return {
        "selection_diagram": selection_diagram.model_dump(mode="json"),
        "query_treatment": query_treatment,
        "query_outcome": query_outcome,
    }


@foundry_method(
    namespace="causal.transport",
    version="1.0.0",
    tags={"causal", "transportability", "symbolic", "y0"},
)
class SymbolicIdentify:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="symbolic_identify",
        namespace="placeholder",
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
            ParameterSpec(name="require_symbolic_backend", default=False),
            ParameterSpec(name="symbolic_backend", default="auto"),
            ParameterSpec(name="pag_identification_policy", default="probabilistic"),
            ParameterSpec(name="pag_max_dag_samples", default=100),
            ParameterSpec(name="pag_threshold", default=0.5),
            ParameterSpec(name="pag_seed", default=0),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Symbolic transportability identification with y0 bridge and safe fallbacks.",
        tags=frozenset({"causal", "transportability", "symbolic", "y0"}),
        assumptions={
            "symbolic_scope": "Current symbolic bridge focuses on common front-door patterns.",
            "fallbacks": (
                "Falls back to simplified transportability when symbolic path is unavailable."
            ),
        },
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        selection_diagram = SelectionDiagram.model_validate(state["selection_diagram"])
        query_treatment = str(state["query_treatment"])
        query_outcome = str(state["query_outcome"])
        require_symbolic = bool(params.get("require_symbolic_backend", False))
        symbolic_backend = normalize_symbolic_backend_mode(params.get("symbolic_backend"))
        selected_backend, backend_order, unavailable_reasons = _resolve_symbolic_backend_locally(
            symbolic_backend
        )
        trace = [f"symbolic_backend_order:{','.join(backend_order)}"]
        if selected_backend is not None:
            symbolic_result = _symbolic_from_frontdoor(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                trace=[*trace, f"symbolic_backend_selected:{selected_backend}"],
                backend_name=selected_backend,
            )
            if symbolic_result is not None:
                return {"transport_result": symbolic_result.model_dump(mode="json")}
        elif require_symbolic:
            reason = ";".join(unavailable_reasons) or "symbolic_backend_unavailable"
            unsupported = _unsupported_symbolic_result(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                trace=trace,
                backend_name=None if symbolic_backend == "full_auto" else symbolic_backend,
                reason=reason,
            )
            return {"transport_result": unsupported.model_dump(mode="json")}

        solver_mode = "full_auto"
        if symbolic_backend == "y0":
            solver_mode = "symbolic_y0"
        elif symbolic_backend == "r":
            solver_mode = "symbolic_r"
        result = solve_transportability(
            selection_diagram=selection_diagram,
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            solver_mode=solver_mode,
            allow_degraded_transport=not require_symbolic,
            pag_identification_policy=params.get("pag_identification_policy"),
            pag_max_dag_samples=int(params.get("pag_max_dag_samples", 100) or 100),
            pag_threshold=float(params.get("pag_threshold", 0.5) or 0.5),
            pag_seed=int(params.get("pag_seed", 0) or 0),
        )
        prefixed_trace = [*trace]
        if selected_backend is not None:
            prefixed_trace.append(f"symbolic_backend_selected:{selected_backend}")
        elif unavailable_reasons:
            prefixed_trace.append(f"symbolic_backend_unavailable:{';'.join(unavailable_reasons)}")
        result = result.model_copy(
            update={
                "identification_trace": [*prefixed_trace, *result.identification_trace],
                "warnings": _merge_warnings(
                    result.warnings,
                    [f"symbolic_backend_requested={symbolic_backend}"],
                ),
            }
        )
        if require_symbolic and result.status is not TransportabilityStatus.IDENTIFIED:
            reason = ";".join(unavailable_reasons) or "symbolic_transport_not_identified"
            result = _unsupported_symbolic_result(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                trace=prefixed_trace,
                backend_name=selected_backend,
                reason=reason,
            )
        return {"transport_result": result.model_dump(mode="json")}


__all__ = [
    "SymbolicIdentify",
    "convert_graph_to_symbolic_repr",
]
