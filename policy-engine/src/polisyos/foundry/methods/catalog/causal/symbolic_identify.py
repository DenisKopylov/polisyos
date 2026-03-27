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
from polisyos.ir.analytics.causal import ProofBundle, proof_bundle_from_identification_result
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark
from polisyos.ir.analytics.negative_certificate import negative_certificate_from_transport_result
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


def _proof_bundle_from_transport_result(result: TransportabilityResult) -> ProofBundle:
    """Build a heuristic-backed proof bundle for transport-only symbolic paths."""
    proof_status = "identified" if result.status is TransportabilityStatus.IDENTIFIED else "oracle_needed"
    proof_stratum = "A1_extended" if proof_status == "identified" else "A2_oracle_backed"
    return ProofBundle(
        proof_status=proof_status,
        proof_stratum=proof_stratum,
        theorem_family=result.identification_engine or result.algorithm_version or "transport_symbolic",
        completeness_regime="heuristic_backed",
        implementation_coverage="transportability_bridge",
        query_ref=result.query,
        estimand_ast=result.estimand_ast if isinstance(result.estimand_ast, dict) else None,
        negative_certificate_summary=(
            result.unsupported_reason if proof_status != "identified" else None
        ),
        proof_trace=list(result.identification_trace),
        assumptions=list(result.warnings),
        metadata={
            "transport_mode": result.transport_mode.value,
            "algorithm_version": result.algorithm_version,
            "final_confidence": result.final_confidence,
        },
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
        when_to_use="Symbolic causal identification of transportability query P*(Y|do(X)); use when y0/R symbolic backend is available",
        when_not_to_use="No symbolic backend available and simplified transport sufficient; query is purely observational",
        output_interpretation="TransportabilityResult: IDENTIFIED = effect is transportable with given formula. UNSUPPORTED = cannot transport without additional data. Confidence reflects context distance penalty.",
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
                proof_bundle = _proof_bundle_from_transport_result(symbolic_result)
                return {
                    "transport_result": symbolic_result.model_dump(mode="json"),
                    "proof_bundle": proof_bundle.model_dump(mode="json"),
                }
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
            proof_bundle = _proof_bundle_from_transport_result(unsupported)
            negative_certificate = negative_certificate_from_transport_result(
                result=unsupported,
                treatment=query_treatment,
                outcome=query_outcome,
            )
            return {
                "transport_result": unsupported.model_dump(mode="json"),
                "proof_bundle": proof_bundle.model_dump(mode="json"),
                "negative_certificate": negative_certificate.model_dump(mode="json"),
            }

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
        proof_bundle = _proof_bundle_from_transport_result(result)
        payload = {
            "transport_result": result.model_dump(mode="json"),
            "proof_bundle": proof_bundle.model_dump(mode="json"),
        }
        if result.status is not TransportabilityStatus.IDENTIFIED:
            negative_certificate = negative_certificate_from_transport_result(
                result=result,
                treatment=query_treatment,
                outcome=query_outcome,
            )
            payload["negative_certificate"] = negative_certificate.model_dump(mode="json")
        return payload


def _id_result_to_transport_result(
    id_result: "IdentificationResult",
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
) -> TransportabilityResult:
    """Convert IdentificationResult → TransportabilityResult for backward compat."""
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

    if id_result.status is IdentificationStatus.IDENTIFIED:
        assert id_result.estimand_ast is not None
        formula_str = id_result.estimand_ast.to_latex()
        formula = TransportFormula(
            formula_str=formula_str,
            stratification_variables=[],
            source_quantities=[dr.dataset_ref or "" for dr in id_result.required_distributions],
            adjustment_type=id_result.estimand_ast.identification_method,
        )
        distance = float(diagram.context_distance)
        context_penalty = min(distance * 0.35, 0.6)
        return TransportabilityResult(
            query=f"P*({outcome}|do({treatment}))",
            status=TransportabilityStatus.IDENTIFIED,
            transport_mode=TransportMode.TRANSPORT_FORMULA if diagram.s_nodes else TransportMode.DIRECT,
            transport_formula=formula,
            base_confidence=1.0,
            context_distance_penalty=context_penalty,
            data_availability_penalty=0.0,
            final_confidence=max(0.0, 1.0 - context_penalty),
            algorithm_version="id_v1",
            identification_engine="native_id",
            identification_trace=id_result.trace,
            estimand_ast=id_result.estimand_ast.model_dump(mode="json"),
            source_context_id=diagram.source_context.context_id,
            target_context_id=diagram.target_context.context_id,
        )

    if id_result.status is IdentificationStatus.HEDGE_FOUND:
        assert id_result.hedge_certificate is not None
        cert = id_result.hedge_certificate
        return TransportabilityResult(
            query=f"P*({outcome}|do({treatment}))",
            status=TransportabilityStatus.UNSUPPORTED,
            transport_mode=TransportMode.NONE,
            base_confidence=0.0,
            context_distance_penalty=0.0,
            data_availability_penalty=0.0,
            final_confidence=0.0,
            algorithm_version="id_v1",
            identification_engine="native_id",
            identification_trace=id_result.trace,
            unsupported_reason="hedge_certificate: " + cert.description,
            blocking_s_nodes=diagram.s_nodes,
            source_context_id=diagram.source_context.context_id,
            target_context_id=diagram.target_context.context_id,
        )

    # PAG_AMBIGUOUS or ORACLE_NEEDED — fall through to simplified
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        base_confidence=0.0,
        context_distance_penalty=0.0,
        data_availability_penalty=0.0,
        final_confidence=0.0,
        algorithm_version="id_v1",
        identification_engine="native_id",
        identification_trace=id_result.trace,
        unsupported_reason=f"id_status={id_result.status.value}",
        source_context_id=diagram.source_context.context_id,
        target_context_id=diagram.target_context.context_id,
    )


@foundry_method(
    namespace="causal.transport",
    version="2.0.0",
    tags={"causal", "transportability", "symbolic", "id-algorithm", "pearl-bareinboim"},
)
class SymbolicIdentifyV2:
    """Symbolic causal identification using the native Shpitser-Pearl ID algorithm.

    Replaces the heuristic frontdoor fallback in v1 with the full recursive ID
    algorithm (Steps 1-7 from Shpitser & Pearl 2006), producing:

    - A structured EstimandAST (not just a formula string)
    - A HedgeCertificate on failure (formal non-identifiability witness)
    - A backward-compatible TransportabilityResult for existing consumers

    Falls back to v1 solve_transportability() for non-DAG graphs (CPDAG, PAG)
    where the PAG-identification policy governs.
    """

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

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
                ),
                SlotSpec(
                    name="query_treatment",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("variable", "str"),
                ),
                SlotSpec(
                    name="query_outcome",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("variable", "str"),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="transport_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact", "json"),
                ),
                SlotSpec(
                    name="estimand_ast",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("artifact", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="use_native_id", default=True),
            ParameterSpec(name="oracle_backend", default="none"),
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
        description=(
            "Pearl-Bareinboim symbolic identification via native ID algorithm "
            "(Shpitser & Pearl 2006). Returns structured EstimandAST + "
            "TransportabilityResult. Falls back to v1 solver for PAG/CPDAG inputs."
        ),
        tags=frozenset(
            {"causal", "transportability", "symbolic", "id-algorithm", "pearl-bareinboim"}
        ),
        assumptions={
            "id_scope": "Full 7-step recursive ID for DAG/ADMG inputs (GraphType.DAG or PAG with ARROW/ARROW).",
            "fallback": "Non-DAG inputs fall back to solve_transportability() v1 solver.",
            "hedge": "Non-identifiable cases return HedgeCertificate (formal witness).",
        },
        when_to_use=(
            "Formal causal identification of P*(Y|do(X)) with structured EstimandAST output; "
            "use when you need the estimand in compiled form for the EstimandCompiler."
        ),
        when_not_to_use=(
            "When only a qualitative transportability check is needed (use CheckTransportability); "
            "when graph is CPDAG/PAG and PAG-identification is the main path."
        ),
        output_interpretation=(
            "transport_result: TransportabilityResult (backward compat). "
            "estimand_ast: EstimandAST serialised as dict — parse with EstimandAST.model_validate(). "
            "HEDGE_FOUND → status=UNSUPPORTED with hedge description in identification_trace."
        ),
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        from polisyos.foundry.methods.catalog.causal.id_engine import (
            IdentificationStatus,
            id_with_oracle_fallback,
            tr_algorithm,
        )
        from polisyos.ir.analytics.causal_graph import GraphType

        selection_diagram = SelectionDiagram.model_validate(state["selection_diagram"])
        query_treatment = str(state["query_treatment"])
        query_outcome = str(state["query_outcome"])
        use_native = bool(params.get("use_native_id", True))
        oracle = str(params.get("oracle_backend", "none"))

        graph = selection_diagram.base_graph
        can_use_native = use_native and graph.graph_type in {GraphType.DAG, GraphType.PAG}

        if can_use_native:
            # Use TR algorithm if S-nodes present, otherwise plain ID
            if selection_diagram.s_nodes:
                id_result = tr_algorithm(
                    treatment=frozenset({query_treatment}),
                    outcome=frozenset({query_outcome}),
                    selection_diagram=selection_diagram,
                )
            else:
                id_result = id_with_oracle_fallback(
                    treatment=frozenset({query_treatment}),
                    outcome=frozenset({query_outcome}),
                    graph=graph,
                    oracle=oracle,  # type: ignore[arg-type]
                )

            if id_result.status in {
                IdentificationStatus.IDENTIFIED,
                IdentificationStatus.HEDGE_FOUND,
            }:
                transport_result = _id_result_to_transport_result(
                    id_result, selection_diagram, query_treatment, query_outcome
                )
                estimand_dict = (
                    id_result.estimand_ast.model_dump(mode="json")
                    if id_result.estimand_ast is not None
                    else None
                )
                payload = {
                    "transport_result": transport_result.model_dump(mode="json"),
                    "estimand_ast": estimand_dict,
                    "proof_bundle": proof_bundle_from_identification_result(
                        id_result
                    ).model_dump(mode="json"),
                }
                if id_result.status is IdentificationStatus.HEDGE_FOUND:
                    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine

                    negative_certificate = CausalEngine()._hedge_to_negative_cert(id_result)
                    payload["proof_bundle"] = proof_bundle_from_identification_result(
                        id_result,
                        negative_certificate_summary=negative_certificate.to_summary(),
                    ).model_dump(mode="json")
                    payload["negative_certificate"] = negative_certificate.model_dump(mode="json")
                    if negative_certificate.bounds_bundle is not None:
                        payload["bounds_bundle"] = negative_certificate.bounds_bundle.model_dump(
                            mode="json"
                        )
                return payload

            transport_result = _id_result_to_transport_result(
                id_result, selection_diagram, query_treatment, query_outcome
            )
            proof_bundle = proof_bundle_from_identification_result(id_result)
            negative_certificate = negative_certificate_from_transport_result(
                result=transport_result,
                treatment=query_treatment,
                outcome=query_outcome,
            )
            return {
                "transport_result": transport_result.model_dump(mode="json"),
                "estimand_ast": None,
                "proof_bundle": proof_bundle.model_dump(mode="json"),
                "negative_certificate": negative_certificate.model_dump(mode="json"),
            }

        # Fallback: v1 solve_transportability
        symbolic_backend = normalize_symbolic_backend_mode(params.get("symbolic_backend"))
        selected_backend, _, unavailable_reasons = _resolve_symbolic_backend_locally(
            symbolic_backend
        )
        trace = [f"symbolic_backend_order:fallback_to_v1"]

        # Try frontdoor heuristic first (v1 behavior)
        if selected_backend is not None:
            frontdoor_result = _symbolic_from_frontdoor(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                trace=trace,
                backend_name=selected_backend,
            )
            if frontdoor_result is not None:
                proof_bundle = _proof_bundle_from_transport_result(frontdoor_result)
                return {
                    "transport_result": frontdoor_result.model_dump(mode="json"),
                    "estimand_ast": None,
                    "proof_bundle": proof_bundle.model_dump(mode="json"),
                }

        result = solve_transportability(
            selection_diagram=selection_diagram,
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            solver_mode="full_auto",
            allow_degraded_transport=True,
            pag_identification_policy=params.get("pag_identification_policy"),
            pag_max_dag_samples=int(params.get("pag_max_dag_samples", 100) or 100),
            pag_threshold=float(params.get("pag_threshold", 0.5) or 0.5),
            pag_seed=int(params.get("pag_seed", 0) or 0),
        )
        proof_bundle = _proof_bundle_from_transport_result(result)
        payload = {
            "transport_result": result.model_dump(mode="json"),
            "estimand_ast": None,
            "proof_bundle": proof_bundle.model_dump(mode="json"),
        }
        if result.status is not TransportabilityStatus.IDENTIFIED:
            negative_certificate = negative_certificate_from_transport_result(
                result=result,
                treatment=query_treatment,
                outcome=query_outcome,
            )
            payload["negative_certificate"] = negative_certificate.model_dump(mode="json")
        return payload


# Import deferred to avoid circular imports at module-load time
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult  # noqa: E402


__all__ = [
    "SymbolicIdentify",
    "SymbolicIdentifyV2",
    "convert_graph_to_symbolic_repr",
]
