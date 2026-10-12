"""Attempt symbolic causal identification and return formula/proof metadata."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from typing import Any, ClassVar

from polisyos.core.observability import DeterminismTier
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
    Y0_SURROGATE_DATA_PROFILE_ABSENT,
    build_y0_graph,
    normalize_symbolic_backend_mode,
    parse_y0_surrogate_data_profile,
    probe_backend_availability,
    profile_unknown_variables,
)
from polisyos.ir.analytics.causal import (
    ProofBundle,
    proof_bundle_from_identification_result,
    proof_bundle_from_transportability_result,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark
from polisyos.ir.analytics.estimand import DistributionDomain
from polisyos.ir.analytics.privacy_transportability import (
    TransportPrivacyContext,
    coerce_transport_privacy_context,
)
from polisyos.ir.analytics.transportability import (
    SelectionDiagram,
    TransportabilityResult,
    TransportabilityStatus,
    TransportFormula,
    TransportMode,
)

from .transport_engine import (
    scalar_graph_admission_refusal,
    scalar_graph_refusal_proof_bundle,
    solve_transportability,
    validate_scalar_graph_selection_diagram,
)


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
    """Convert graph to symbolic repr helper."""
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


def _merge_warnings(*warnings_lists: list[str]) -> list[str]:
    merged: list[str] = []
    for warnings in warnings_lists:
        for warning in warnings:
            if warning not in merged:
                merged.append(warning)
    return merged


def _unsupported_symbolic_result(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    trace: list[str],
    backend_name: str | None,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> TransportabilityResult:
    """Return an explicit limitation without implying a negative ID result."""
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        base_confidence=0.0,
        context_distance_penalty=0.0,
        data_availability_penalty=0.0,
        final_confidence=0.0,
        algorithm_version="symbolic_transport_v2",
        identification_engine=backend_name or "none",
        identification_trace=[*trace, f"symbolic_backend_limited:{reason}"],
        unsupported_reason=reason,
        warnings=["No identification conclusion is established by this limitation."],
        source_context_id=diagram.source_context.context_id,
        target_context_id=diagram.target_context.context_id,
        metadata=metadata or {},
    )


def _proof_bundle_from_transport_result(result: TransportabilityResult) -> ProofBundle:
    """Build a proof bundle whose status distinguishes results from limitations."""
    graph_admission_proof = scalar_graph_refusal_proof_bundle(result)
    if graph_admission_proof is not None:
        return graph_admission_proof
    return proof_bundle_from_transportability_result(result)


def _profile_digest(profile: Any) -> str:
    payload = profile.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _y0_population_profile_limited_result(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    raw_profile: object,
    trace: list[str],
) -> tuple[TransportabilityResult, ProofBundle]:
    profile, profile_state = parse_y0_surrogate_data_profile(raw_profile)
    reason = {
        "absent": "y0_surrogate_data_profile_absent",
        "null": "y0_surrogate_data_profile_null",
        "invalid": "y0_surrogate_data_profile_invalid",
        "valid": "y0_surrogate_data_profile_invalid",
    }[profile_state]
    profile_metadata = {
        "backend_requested": "y0",
        "backend_call_attempted": False,
        "backend_call_established": False,
        "backend_result": "not_returned",
        "profile_origin": "consumer_asserted" if profile_state != "absent" else "not_supplied",
        "profile_input_state": profile_state,
        "gate_predicates": {
            "profile_declaration": "consumer_asserted",
            "source_data_exists": "not_established",
            "source_data_currentness": "not_established",
            "source_data_authority": "not_established",
        },
    }
    if profile is not None:
        profile_metadata["surrogate_profile_sha256"] = _profile_digest(profile)
        profile_metadata["surrogate_population_ids"] = [
            population.population_id for population in profile.populations
        ]
    result = _unsupported_symbolic_result(
        diagram=diagram,
        treatment=treatment,
        outcome=outcome,
        trace=[*trace, f"y0_surrogate_profile:{profile_state}"],
        backend_name="y0",
        reason=reason,
        metadata=profile_metadata,
    )
    proof = _proof_bundle_from_transport_result(result)
    return result, proof


def _expression_population_quantities(expression: Any) -> tuple[str, list[str], list[str], list[str]]:
    """Extract exact Y0 text and typed quantity partitions from its expression tree."""
    from y0.dsl import Fraction, PopulationProbability, Probability, Product, Sum

    source: list[str] = []
    target: list[str] = []
    summation_variables: list[str] = []
    visited: set[int] = set()

    def visit(node: Any) -> None:
        marker = id(node)
        if marker in visited:
            return
        visited.add(marker)
        if isinstance(node, Sum):
            for variable in node.ranges:
                name = str(getattr(variable, "name", variable))
                if name not in summation_variables:
                    summation_variables.append(name)
            visit(node.expression)
        elif isinstance(node, Product):
            for factor in node.expressions:
                visit(factor)
        elif isinstance(node, Fraction):
            visit(node.numerator)
            visit(node.denominator)
        elif isinstance(node, PopulationProbability):
            population = getattr(node.population, "name", str(node.population))
            rendered = node.to_latex()
            bucket = target if population == "pi*" else source
            if rendered not in bucket:
                bucket.append(rendered)
        elif isinstance(node, Probability):
            rendered = node.to_latex()
            if rendered not in source:
                source.append(rendered)
        else:
            raise TypeError(f"unsupported_y0_trso_expression:{type(node).__name__}")

    visit(expression)
    if not source and not target:
        raise TypeError("y0_trso_expression_has_no_probability_quantities")
    return expression.to_latex(), source, target, summation_variables


def _run_y0_trso(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    raw_profile: object,
    trace: list[str],
) -> tuple[TransportabilityResult, ProofBundle]:
    """Call locked Y0 TRSO with explicit caller-declared population observations."""
    profile, profile_state = parse_y0_surrogate_data_profile(raw_profile)
    if profile is None:
        return _y0_population_profile_limited_result(
            diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            raw_profile=raw_profile,
            trace=trace,
        )

    unknown = profile_unknown_variables(profile, set(diagram.base_graph.nodes))
    profile_metadata = {
        "backend_requested": "y0",
        "backend_call_established": False,
        "profile_origin": "consumer_asserted",
        "profile_input_state": profile_state,
        "surrogate_profile_sha256": _profile_digest(profile),
        "surrogate_population_ids": [population.population_id for population in profile.populations],
        "gate_predicates": {
            "profile_declaration": "consumer_asserted",
            "profile_variables_belong_to_admitted_graph": "recomputed",
            "source_data_exists": "not_established",
            "source_data_currentness": "not_established",
            "source_data_authority": "not_established",
        },
    }
    if unknown:
        result = _unsupported_symbolic_result(
            diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            trace=[*trace, "y0_trso:profile_variables_outside_graph"],
            backend_name="y0",
            reason="y0_surrogate_profile_variables_outside_admitted_graph",
            metadata={**profile_metadata, "unknown_profile_variables": list(unknown)},
        )
        return result, _proof_bundle_from_transport_result(result)

    try:
        from importlib.metadata import version as package_version

        from y0.algorithm.transport import (
            identify_target_outcomes,  # type: ignore[import-not-found]
        )
        from y0.dsl import Variable  # type: ignore[import-not-found]

        mixed_graph = build_y0_graph(diagram.base_graph)
        surrogate_outcomes = {
            Variable(population.population_id): {Variable(name) for name in population.outcomes}
            for population in profile.populations
        }
        surrogate_interventions = {
            Variable(population.population_id): {Variable(name) for name in population.interventions}
            for population in profile.populations
        }
        profile_metadata["backend_call_attempted"] = True
        expression = identify_target_outcomes(
            graph=mixed_graph,
            target_outcomes={Variable(outcome)},
            target_interventions={Variable(treatment)},
            surrogate_outcomes=surrogate_outcomes,
            surrogate_interventions=surrogate_interventions,
        )
        version = package_version("y0")
        profile_metadata.update(
            {
                "backend_call_established": True,
                "backend_id": "y0",
                "backend_version": version,
                "backend_operation": "identify_target_outcomes",
                "backend_result": "none_returned" if expression is None else "expression_returned",
                "gate_predicates": {
                    **profile_metadata["gate_predicates"],
                    "backend_operation_result": "recomputed",
                },
            }
        )
        if expression is None:
            result = _unsupported_symbolic_result(
                diagram=diagram,
                treatment=treatment,
                outcome=outcome,
                trace=[*trace, "y0_trso:api_called:identify_target_outcomes", f"y0_version:{version}"],
                backend_name="y0",
                reason="y0_trso_returned_no_expression",
                metadata=profile_metadata,
            )
            return result, _proof_bundle_from_transport_result(result)
        try:
            formula_text, source_quantities, target_quantities, sums = _expression_population_quantities(
                expression
            )
        except (TypeError, ValueError) as exc:
            result = _unsupported_symbolic_result(
                diagram=diagram,
                treatment=treatment,
                outcome=outcome,
                trace=[*trace, "y0_trso:api_called:identify_target_outcomes", f"y0_version:{version}"],
                backend_name="y0",
                reason=f"y0_trso_expression_not_representable:{type(exc).__name__}",
                metadata={
                    **profile_metadata,
                    "backend_expression_candidate_latex": expression.to_latex(),
                },
            )
            return result, _proof_bundle_from_transport_result(result)

        profile_metadata.update(
            {
                "backend_expression_candidate_latex": formula_text,
                "backend_expression_candidate_y0": expression.to_y0(),
                "candidate_formula_latex": formula_text,
                "candidate_expression_y0": expression.to_y0(),
                "backend_source_quantities_candidate": source_quantities,
                "backend_target_quantities_candidate": target_quantities,
                "backend_summation_variables_candidate": sums,
                "source_data_exists": "not_established",
                "source_data_currentness": "not_established",
                "source_data_authority": "not_established",
                "target_data_exists": "not_established",
                "target_data_currentness": "not_established",
                "target_data_authority": "not_established",
                "typed_expression_ast": "not_representable_population_indexed_ast",
            }
        )
        warnings = [
            "Y0 TRSO returned an expression under the caller-declared population profile.",
            "Population declarations do not establish source or target data existence, currentness, or authority.",
            "The existing estimand AST cannot preserve population-indexed Y0 leaves; "
            "the exact formula is retained as a candidate only.",
        ]
        result = _unsupported_symbolic_result(
            diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            trace=[
                *trace,
                "y0_trso:api_called:identify_target_outcomes",
                f"y0_version:{version}",
                f"y0_expression_candidate_latex:{formula_text}",
                f"y0_surrogate_profile_sha256:{profile_metadata['surrogate_profile_sha256']}",
            ],
            backend_name="y0",
            reason="y0_trso_population_indexed_ast_unavailable",
            metadata=profile_metadata,
        )
        result = result.model_copy(
            update={
                "algorithm_version": f"y0_{version}",
                "requires_expert_review": True,
                "expert_review_reasons": [
                    "caller_declared_surrogate_population_profile",
                    "source_and_target_data_authority_not_established",
                    "population_indexed_estimand_ast_unavailable",
                ],
                "warnings": warnings,
            }
        )
        return result, _proof_bundle_from_transport_result(result)
    except Exception as exc:
        result = _unsupported_symbolic_result(
            diagram=diagram,
            treatment=treatment,
            outcome=outcome,
            trace=[*trace, "y0_trso:api_call_failed"],
            backend_name="y0",
            reason=f"y0_trso_api_error:{type(exc).__name__}",
            metadata={**profile_metadata, "backend_error_type": type(exc).__name__},
        )
        return result, _proof_bundle_from_transport_result(result)


def _y0_direct_result(
    *,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
    trace: list[str],
    dataset_ref: str | None = None,
) -> tuple[TransportabilityResult, ProofBundle]:
    """Run actual Y0 direct ID through the canonical typed ID result path."""
    from polisyos.foundry.methods.catalog.causal.id_engine import (
        IdentificationStatus,
        id_with_oracle_fallback,
    )

    id_result = id_with_oracle_fallback(
        treatment=frozenset({treatment}),
        outcome=frozenset({outcome}),
        graph=diagram.base_graph,
        oracle="y0",
        dataset_ref=dataset_ref,
        force_y0=True,
    )
    id_result = dataclasses.replace(id_result, trace=[*trace, *id_result.trace])
    result = _id_result_to_transport_result(id_result, diagram, treatment, outcome)
    proof = proof_bundle_from_identification_result(id_result)
    if id_result.status is IdentificationStatus.IDENTIFIED:
        result = result.model_copy(
            update={
                "requires_expert_review": True,
                "expert_review_reasons": ["source_data_authority_not_established"],
                "warnings": [
                    *result.warnings,
                    "Y0's identified expression is a mathematical result under the admitted graph; data existence, currentness, and authority are not established.",
                ],
                "metadata": {
                    **dict(result.metadata),
                    "gate_predicates": {
                        **dict(result.metadata.get("gate_predicates", {})),
                        "graph_admission": "recomputed",
                        "backend_family_support": "recomputed",
                        "backend_operation_result": "recomputed",
                        "query_input_scope": "recomputed",
                        "source_data_exists": "not_established",
                        "source_data_currentness": "not_established",
                        "source_data_authority": "not_established",
                    },
                },
            }
        )
    return result, proof_bundle_from_transportability_result(result, existing_bundle=proof)


def _scalar_graph_refusal_payload(
    *,
    selection_diagram: SelectionDiagram | None,
    query_treatment: str,
    query_outcome: str,
    params: Mapping[str, Any],
    solver_mode: str,
    include_estimand_ast: bool = False,
    privacy_context: TransportPrivacyContext | None = None,
    admission_refusal: TransportabilityResult | None = None,
) -> dict[str, Any] | None:
    """Return a shared typed limitation before any scalar graph route."""
    result = admission_refusal or scalar_graph_admission_refusal(
        selection_diagram=selection_diagram,
        treatment=query_treatment,
        outcome=query_outcome,
        solver_mode=solver_mode,
        pag_identification_policy=params.get("pag_identification_policy"),
        policy_present="pag_identification_policy" in params,
        privacy_context=privacy_context,
    )
    if result is None:
        return None

    proof_bundle = scalar_graph_refusal_proof_bundle(result)
    assert proof_bundle is not None
    payload: dict[str, Any] = {
        "transport_result": result.model_dump(mode="json"),
        "proof_bundle": proof_bundle.model_dump(mode="json"),
    }
    if include_estimand_ast:
        payload["estimand_ast"] = None
    return payload


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
    """Run symbolic ID over a graph/query contract; avoid treating identification output as an estimator without data support."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="symbolic_identify",
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
            ParameterSpec(name="require_symbolic_backend", default=False),
            ParameterSpec(name="symbolic_backend", default="auto"),
            ParameterSpec(
                name="surrogate_data_profile",
                default=Y0_SURROGATE_DATA_PROFILE_ABSENT,
                description="Optional strict caller-declared Y0 source-population availability profile; not evidence of existence or authority.",
            ),
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
            "symbolic_scope": (
                "Y0 direct ID uses the locked identify_outcomes API; TRSO requires an explicit strict source-population profile."
            ),
            "authority": (
                "An algorithmic expression and caller-declared population profile do not establish data existence, currentness, or authority."
            ),
        },
        when_to_use="Symbolic causal identification with Y0; supply surrogate_data_profile for cross-population TRSO when selection nodes are present.",
        citations=(
            "Bareinboim, E. & Pearl, J. (2016). Causal inference and the data-fusion problem. PNAS, 113(27), 7345-7352.",
            "Tikka, S. & Karvanen, J. (2017). Identifying causal effects with the R package causaleffect. Journal of Statistical Software, 76(12).",
        ),
        when_not_to_use="Population-indexed data or authority is required but no independently verified source evidence is available.",
        output_interpretation="IDENTIFIED records the algorithm's result under the admitted graph/profile; it does not establish data existence, currentness, authority, or estimate validity. UNSUPPORTED carries a typed limitation and does not imply non-identification.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        query_treatment = str(state["query_treatment"])
        query_outcome = str(state["query_outcome"])
        selection_diagram, malformed_graph_refusal = validate_scalar_graph_selection_diagram(
            state["selection_diagram"],
            treatment=query_treatment,
            outcome=query_outcome,
            solver_mode="symbolic_identify",
        )
        if malformed_graph_refusal is not None:
            payload = _scalar_graph_refusal_payload(
                selection_diagram=selection_diagram,
                query_treatment=query_treatment,
                query_outcome=query_outcome,
                params=params,
                solver_mode="symbolic_identify",
                admission_refusal=malformed_graph_refusal,
            )
            assert payload is not None
            return payload
        assert selection_diagram is not None
        graph_admission_payload = _scalar_graph_refusal_payload(
            selection_diagram=selection_diagram,
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            params=params,
            solver_mode="symbolic_identify",
        )
        if graph_admission_payload is not None:
            return graph_admission_payload

        require_symbolic = bool(params.get("require_symbolic_backend", False))
        symbolic_backend = normalize_symbolic_backend_mode(params.get("symbolic_backend"))
        selected_backend, backend_order, unavailable_reasons = _resolve_symbolic_backend_locally(
            symbolic_backend
        )
        trace = [f"symbolic_backend_order:{','.join(backend_order)}"]
        raw_profile = params.get(
            "surrogate_data_profile", Y0_SURROGATE_DATA_PROFILE_ABSENT
        )
        if selected_backend == "y0":
            selected_trace = [*trace, "symbolic_backend_selected:y0"]
            if selection_diagram.s_nodes:
                result, proof = _run_y0_trso(
                    diagram=selection_diagram,
                    treatment=query_treatment,
                    outcome=query_outcome,
                    raw_profile=raw_profile,
                    trace=selected_trace,
                )
            else:
                result, proof = _y0_direct_result(
                    diagram=selection_diagram,
                    treatment=query_treatment,
                    outcome=query_outcome,
                    trace=selected_trace,
                )
            return {
                "transport_result": result.model_dump(mode="json"),
                "proof_bundle": proof.model_dump(mode="json"),
            }
        if require_symbolic:
            reason = ";".join(unavailable_reasons) or "symbolic_backend_execution_unavailable"
            unsupported = _unsupported_symbolic_result(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                trace=trace,
                backend_name=None,
                reason=reason,
                metadata={
                    "backend_requested": symbolic_backend,
                    "backend_call_established": False,
                    "gate_predicates": {
                        "backend_operation_result": "not_established",
                        "source_data_exists": "not_established",
                        "source_data_currentness": "not_established",
                        "source_data_authority": "not_established",
                    },
                },
            )
            proof_bundle = _proof_bundle_from_transport_result(unsupported)
            return {
                "transport_result": unsupported.model_dump(mode="json"),
                "proof_bundle": proof_bundle.model_dump(mode="json"),
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
                backend_name=None,
                reason=reason,
                metadata={"backend_call_established": False, "backend_requested": symbolic_backend},
            )
        proof_bundle = _proof_bundle_from_transport_result(result)
        return {
            "transport_result": result.model_dump(mode="json"),
            "proof_bundle": proof_bundle.model_dump(mode="json"),
        }


def _id_result_to_transport_result(
    id_result: IdentificationResult,
    diagram: SelectionDiagram,
    treatment: str,
    outcome: str,
) -> TransportabilityResult:
    """Convert an IdentificationResult while preserving actual producer metadata."""
    from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus

    backend_id = str(id_result.metadata.get("backend_id", "native_id"))
    engine = "y0" if backend_id == "y0" else "native_id"
    version = id_result.algorithm_version or "id_v1"
    result_metadata = dict(id_result.metadata)
    identification_trace = list(id_result.trace)
    if (
        backend_id == "y0"
        and result_metadata.get("backend_operation") == "identify_outcomes"
    ):
        from polisyos.foundry.methods.catalog.causal.capabilities import (
            build_causal_capability_contract,
        )
        from polisyos.ir.analytics.causal_capabilities import (
            CausalBackendId,
            CausalIdentificationFamily,
        )

        graph_payload = diagram.base_graph.model_dump(mode="json")
        graph_encoded = json.dumps(
            graph_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        graph_sha256 = hashlib.sha256(graph_encoded).hexdigest()
        capability_fingerprint: str | None = None
        capability_family_supported = False
        try:
            capability_contract = build_causal_capability_contract()
            capability_fingerprint = capability_contract.dependency_fingerprint
            backend = capability_contract.backend(CausalBackendId.Y0)
            capability_family_supported = (
                backend is not None
                and backend.available
                and CausalIdentificationFamily.DIRECT in backend.supported_families
            )
        except Exception:
            # Preserve the actual mathematical result; the consumer grade will
            # remain unknown if scoped capability evidence cannot be recomputed.
            capability_family_supported = False
        query = f"P*({outcome}|do({treatment}))"
        result_metadata["operation_scope"] = {
            "schema_version": "policyos.transport.operation-scope.v1",
            "family": "direct",
            "operation": "identify_outcomes",
            "query": query,
            "treatment": treatment,
            "outcome": outcome,
            "graph_sha256": graph_sha256,
            "graph_type": diagram.base_graph.graph_type.value,
            "capability_fingerprint": capability_fingerprint,
            "capability_family_supported": capability_family_supported,
        }
        predicates = dict(result_metadata.get("gate_predicates", {}))
        predicates.update(
            {
                "backend_family_support": (
                    "recomputed" if capability_family_supported else "not_established"
                ),
                "query_input_scope": "recomputed",
            }
        )
        result_metadata["gate_predicates"] = predicates
        identification_trace.extend(
            [
                "family:direct",
                "operation:y0.identify_outcomes",
                f"y0_operation_scope_sha256:{graph_sha256}",
            ]
        )
    common = {
        "algorithm_version": version,
        "identification_engine": engine,
        "identification_trace": identification_trace,
        "source_context_id": diagram.source_context.context_id,
        "target_context_id": diagram.target_context.context_id,
        "metadata": result_metadata,
    }

    if id_result.status is IdentificationStatus.IDENTIFIED:
        assert id_result.estimand_ast is not None
        formula = TransportFormula(
            formula_str=id_result.estimand_ast.to_latex(),
            stratification_variables=[],
            source_quantities=[
                distribution.to_latex()
                for distribution in id_result.required_distributions
                if distribution.domain is DistributionDomain.SOURCE
            ],
            target_quantities=[
                distribution.to_latex()
                for distribution in id_result.required_distributions
                if distribution.domain is DistributionDomain.TARGET
            ],
            adjustment_type=id_result.estimand_ast.identification_method,
        )
        distance = float(diagram.context_distance)
        context_penalty = min(distance * 0.35, 0.6)
        metadata = dict(common["metadata"])
        if backend_id == "y0":
            metadata.update(
                {
                    "source_data_exists": "not_established",
                    "source_data_currentness": "not_established",
                    "source_data_authority": "not_established",
                }
            )
        return TransportabilityResult(
            query=f"P*({outcome}|do({treatment}))",
            status=TransportabilityStatus.IDENTIFIED,
            transport_mode=TransportMode.TRANSPORT_FORMULA if diagram.s_nodes else TransportMode.DIRECT,
            transport_formula=formula,
            base_confidence=1.0,
            context_distance_penalty=context_penalty,
            data_availability_penalty=0.0,
            final_confidence=max(0.0, 1.0 - context_penalty),
            estimand_ast=id_result.estimand_ast.model_dump(mode="json"),
            requires_expert_review=backend_id == "y0",
            expert_review_reasons=(
                ["source_data_authority_not_established"] if backend_id == "y0" else []
            ),
            warnings=(
                [
                    "Y0's identified expression is a mathematical result under the admitted graph; data existence, currentness, and authority are not established."
                ]
                if backend_id == "y0"
                else []
            ),
            metadata=metadata,
            **{key: value for key, value in common.items() if key != "metadata"},
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
            unsupported_reason="hedge_certificate: " + cert.description,
            blocking_s_nodes=diagram.s_nodes,
            metadata={**dict(id_result.metadata), "negative_identification_witness": "native_hedge"},
            **{key: value for key, value in common.items() if key != "metadata"},
        )

    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        base_confidence=0.0,
        context_distance_penalty=0.0,
        data_availability_penalty=0.0,
        final_confidence=0.0,
        unsupported_reason=f"id_status={id_result.status.value}",
        metadata={
            **dict(id_result.metadata),
            "backend_call_established": bool(id_result.metadata.get("backend_call_established")),
        },
        **{key: value for key, value in common.items() if key != "metadata"},
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
        namespace="",
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
            ParameterSpec(
                name="surrogate_data_profile",
                default=Y0_SURROGATE_DATA_PROFILE_ABSENT,
                description="Optional strict caller-declared Y0 source-population availability profile; not evidence of existence or authority.",
            ),
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
        citations=(
            "Bareinboim, E. & Pearl, J. (2016). Causal inference and the data-fusion problem. PNAS, 113(27), 7345-7352.",
        ),
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

        query_treatment = str(state["query_treatment"])
        query_outcome = str(state["query_outcome"])
        use_native = bool(params.get("use_native_id", True))
        oracle = str(params.get("oracle_backend", "none"))
        privacy_context = _resolve_transport_privacy_context(state, params)
        selection_diagram, malformed_graph_refusal = validate_scalar_graph_selection_diagram(
            state["selection_diagram"],
            treatment=query_treatment,
            outcome=query_outcome,
            solver_mode="symbolic_identify_v2",
            privacy_context=privacy_context,
        )
        if malformed_graph_refusal is not None:
            payload = _scalar_graph_refusal_payload(
                selection_diagram=selection_diagram,
                query_treatment=query_treatment,
                query_outcome=query_outcome,
                params=params,
                solver_mode="symbolic_identify_v2",
                include_estimand_ast=True,
                privacy_context=privacy_context,
                admission_refusal=malformed_graph_refusal,
            )
            assert payload is not None
            return payload
        assert selection_diagram is not None

        graph = selection_diagram.base_graph
        graph_admission_payload = _scalar_graph_refusal_payload(
            selection_diagram=selection_diagram,
            query_treatment=query_treatment,
            query_outcome=query_outcome,
            params=params,
            solver_mode="symbolic_identify_v2",
            include_estimand_ast=True,
            privacy_context=privacy_context,
        )
        if graph_admission_payload is not None:
            return graph_admission_payload

        profile_raw = params.get(
            "surrogate_data_profile", Y0_SURROGATE_DATA_PROFILE_ABSENT
        )
        symbolic_backend = normalize_symbolic_backend_mode(params.get("symbolic_backend"))
        y0_requested = oracle == "y0" or symbolic_backend == "y0"
        profile_supplied = profile_raw is not Y0_SURROGATE_DATA_PROFILE_ABSENT
        can_use_native = use_native and graph.graph_type in {GraphType.DAG, GraphType.PAG}

        if selection_diagram.s_nodes and (y0_requested or profile_supplied):
            if symbolic_backend == "r" and oracle != "y0":
                limited = _unsupported_symbolic_result(
                    diagram=selection_diagram,
                    treatment=query_treatment,
                    outcome=query_outcome,
                    trace=["symbolic_backend_requested:r"],
                    backend_name=None,
                    reason="r_causaleffect_execution_adapter_not_implemented",
                    metadata={"backend_requested": "r", "backend_call_established": False},
                )
                proof_bundle = _proof_bundle_from_transport_result(limited)
                return {
                    "transport_result": limited.model_dump(mode="json"),
                    "estimand_ast": None,
                    "proof_bundle": proof_bundle.model_dump(mode="json"),
                }
            transport_result, proof_bundle = _run_y0_trso(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                raw_profile=profile_raw,
                trace=["symbolic_backend_selected:y0", "transport_operation_requested:trso"],
            )
            return {
                "transport_result": transport_result.model_dump(mode="json"),
                "estimand_ast": None,
                "proof_bundle": proof_bundle.model_dump(mode="json"),
            }

        if can_use_native:
            # Direct Y0 is an explicit backend choice; native transport remains separate.
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
                    oracle="y0" if y0_requested else oracle,  # type: ignore[arg-type]
                    force_y0=y0_requested,
                )

            if id_result.status in {
                IdentificationStatus.IDENTIFIED,
                IdentificationStatus.HEDGE_FOUND,
            }:
                transport_result = _id_result_to_transport_result(
                    id_result, selection_diagram, query_treatment, query_outcome
                )
                identification_proof = proof_bundle_from_identification_result(id_result)
                proof_bundle = proof_bundle_from_transportability_result(
                    transport_result,
                    existing_bundle=identification_proof,
                )
                estimand_dict = (
                    id_result.estimand_ast.model_dump(mode="json")
                    if id_result.estimand_ast is not None
                    else None
                )
                payload = {
                    "transport_result": transport_result.model_dump(mode="json"),
                    "estimand_ast": estimand_dict,
                    "proof_bundle": proof_bundle.model_dump(mode="json"),
                }
                if id_result.status is IdentificationStatus.HEDGE_FOUND:
                    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine

                    negative_certificate = CausalEngine()._hedge_to_negative_cert(id_result)
                    identification_proof = proof_bundle_from_identification_result(
                        id_result,
                        negative_certificate_summary=negative_certificate.to_summary(),
                    )
                    payload["proof_bundle"] = proof_bundle_from_transportability_result(
                        transport_result,
                        existing_bundle=identification_proof,
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
            proof_bundle = proof_bundle_from_transportability_result(
                transport_result,
                existing_bundle=proof_bundle_from_identification_result(id_result),
            )
            return {
                "transport_result": transport_result.model_dump(mode="json"),
                "estimand_ast": None,
                "proof_bundle": proof_bundle.model_dump(mode="json"),
            }

        # Fallback: use a real Y0 ID call when that backend is selected; the old
        # local front-door formula was a backend-identity proxy and is removed.
        symbolic_backend = normalize_symbolic_backend_mode(params.get("symbolic_backend"))
        selected_backend, _, unavailable_reasons = _resolve_symbolic_backend_locally(
            symbolic_backend
        )
        trace = ["symbolic_backend_order:fallback_to_v1"]
        if selected_backend == "y0":
            if selection_diagram.s_nodes:
                y0_result, proof_bundle = _run_y0_trso(
                    diagram=selection_diagram,
                    treatment=query_treatment,
                    outcome=query_outcome,
                    raw_profile=profile_raw,
                    trace=[*trace, "symbolic_backend_selected:y0"],
                )
                return {
                    "transport_result": y0_result.model_dump(mode="json"),
                    "estimand_ast": None,
                    "proof_bundle": proof_bundle.model_dump(mode="json"),
                }
            direct_result, proof_bundle = _y0_direct_result(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                trace=[*trace, "symbolic_backend_selected:y0"],
            )
            return {
                "transport_result": direct_result.model_dump(mode="json"),
                "estimand_ast": direct_result.estimand_ast,
                "proof_bundle": proof_bundle.model_dump(mode="json"),
            }
        if params.get("require_symbolic_backend", False):
            reason = ";".join(unavailable_reasons) or "symbolic_backend_execution_unavailable"
            limited = _unsupported_symbolic_result(
                diagram=selection_diagram,
                treatment=query_treatment,
                outcome=query_outcome,
                trace=trace,
                backend_name=None,
                reason=reason,
                metadata={"backend_requested": symbolic_backend, "backend_call_established": False},
            )
            return {
                "transport_result": limited.model_dump(mode="json"),
                "estimand_ast": None,
                "proof_bundle": _proof_bundle_from_transport_result(limited).model_dump(mode="json"),
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
            privacy_context=_resolve_transport_privacy_context(state, params),
        )
        proof_bundle = _proof_bundle_from_transport_result(result)
        payload = {
            "transport_result": result.model_dump(mode="json"),
            "estimand_ast": None,
            "proof_bundle": proof_bundle.model_dump(mode="json"),
        }
        return payload


def _resolve_transport_privacy_context(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
) -> TransportPrivacyContext | None:
    for candidate in (
        params.get("privacy_context"),
        state.get("privacy_context"),
        params.get("dp_utility_manifest"),
        state.get("dp_utility_manifest"),
        params.get("privacy_transport_certificate"),
        state.get("privacy_transport_certificate"),
    ):
        context = coerce_transport_privacy_context(candidate)
        if context is not None:
            return context
    return None


# Import deferred to avoid circular imports at module-load time
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationResult

__all__ = [
    "SymbolicIdentify",
    "SymbolicIdentifyV2",
    "convert_graph_to_symbolic_repr",
]
