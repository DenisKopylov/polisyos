"""Transport-result construction and projection helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from polisyos.data_forge.read_api.catalog import PStarZResult
from polisyos.ir.analytics.alignment_certification import (
    AlignmentCertificate,
    AlignmentCertificateType,
    AlignmentCertificationPolicy,
    OuterObjectiveResult,
    compute_outer_objective,
    run_outer_search,
)
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.partial_identification import compute_manski_bounds
from polisyos.ir.analytics.privacy_transportability import (
    TransportPrivacyContext,
    apply_transport_privacy_context,
)
from polisyos.ir.analytics.transportability import (
    DataGap,
    SelectionDiagram,
    SNode,
    SNodeOrigin,
    TransportabilityResult,
    TransportabilityStatus,
    TransportMode,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    ConstraintSeverity,
    LegalConstraint,
    LegalToDAGMapping,
    LegalToDAGMappingType,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState

from .transport_resolution_inputs import (
    InvalidTransportInput,
    _context_id_for_blocking,
    _resolve_query_outcome_for_blocking,
    _resolve_query_treatment_for_blocking,
    _transport_execution_profile,
)

if TYPE_CHECKING:
    from .resolve_transport import ResolutionState


def _invalid_transport_input_outcome(
    state: ExperimentState,
    error: InvalidTransportInput,
) -> NodeOutcome:
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(
            code=node_errors.ERROR_INVALID_STATE,
            message=str(error),
            details={"execution_profile": state.execution_profile},
        ),
    )


def _build_proxy_quantity_or_gap(
    *,
    variable: str,
    target_context: ContextProfile,
    outcome: str,
    adjacency: dict[str, set[str]],
    proxy_chain: Any,
    condition_on: dict[str, float] | None,
    proxy_threshold: float,
    validate_proxy_fn: Callable[..., Any],
    compose_confidence_harmonic_fn: Callable[[float, float], float],
) -> tuple[
    PStarZResult | None,
    DataGap | None,
    dict[str, Any] | None,
    float | None,
    bool,
    list[str],
]:
    if proxy_chain.proxies and proxy_chain.best_single_confidence > proxy_threshold:
        best = proxy_chain.proxies[0]
        checklist = validate_proxy_fn(
            proxy=best.proxy_variable,
            target=variable,
            outcome=outcome,
            adjacency=adjacency,
            correlation_matrix={(best.proxy_variable, variable): best.base_correlation},
        )
        validity = checklist.model_dump(mode="json")
        validity_score = _proxy_validity_score(checklist)
        conditional_penalty = 0.1 if condition_on else 0.0
        confidence = compose_confidence_harmonic_fn(best.effective_confidence, validity_score)
        confidence = max(0.0, min(1.0, confidence - conditional_penalty))
        expert_review_reasons: list[str] = []
        requires_expert_review = checklist.requires_expert_review or not checklist.overall_valid
        if requires_expert_review:
            joined_violations = "; ".join(checklist.violations) or "validation_failed"
            expert_review_reasons.append(
                f"proxy_validation:{variable}:{best.proxy_variable}:{joined_violations}"
            )
        p_star = PStarZResult(
            canonical_variable=variable,
            value=None,
            dataset_id=best.proxy_dataset_id,
            raw_variable=best.proxy_raw_name,
            is_proxy=True,
            proxy_chain=[f"{best.proxy_variable} -> {variable}"],
            confidence=confidence,
            penalty_breakdown={
                "proxy": max(0.0, 1.0 - best.effective_confidence),
                "proxy_validity": max(0.0, 1.0 - validity_score),
                **({"conditional_proxy": conditional_penalty} if condition_on else {}),
            },
            is_conditional=condition_on is not None,
            condition_on=condition_on or {},
        )
        penalty = max(0.0, min(1.0, 1.0 - confidence))
        return p_star, None, validity, penalty, requires_expert_review, expert_review_reasons

    gap = DataGap(
        required_variable=variable,
        required_context=f"{target_context.context_id}, {target_context.time_period}",
        available_proxies=proxy_chain.proxies,
        best_proxy_confidence=proxy_chain.best_single_confidence,
        gap_impact="transport_confidence reduced due to missing target quantity",
        suggested_action=_suggest_data_collection(variable),
    )
    return None, gap, None, None, False, []


def _finalize_transport_loop_result(
    result: TransportabilityResult,
    *,
    privacy_context: TransportPrivacyContext | None,
) -> TransportabilityResult:
    return apply_transport_privacy_context(result, privacy_context)


def _build_blocking_transportability_result(
    *,
    state: ExperimentState,
    reason: str,
    message: str,
    causal_report: CausalEffectReport | None,
    source_context: ContextProfile | None,
    target_context: ContextProfile | None,
) -> TransportabilityResult:
    treatment = _resolve_query_treatment_for_blocking(state, causal_report)
    outcome = _resolve_query_outcome_for_blocking(state, causal_report)
    return TransportabilityResult(
        query=f"P*({outcome}|do({treatment}))",
        status=TransportabilityStatus.UNSUPPORTED,
        transport_mode=TransportMode.NONE,
        base_confidence=0.0,
        final_confidence=0.0,
        feasible=False,
        identification_engine="prerequisite_gate",
        identification_trace=[f"prerequisite_gate:{reason}"],
        unsupported_reason=reason,
        unsupported_cases=[reason],
        requires_expert_review=True,
        expert_review_reasons=[reason, "operator_review_required"],
        source_context_id=_context_id_for_blocking(
            source_context,
            state.params.get("source_context"),
        ),
        target_context_id=_context_id_for_blocking(
            target_context,
            state.params.get("target_context"),
        ),
        warnings=[message],
        metadata={
            "blocking_prerequisite": reason,
            "owner_node": "run_transportability",
            "execution_profile": _transport_execution_profile(state),
        },
        notes=[message],
    )


def _apply_partial_identification_fallback(
    *,
    tr_result: TransportabilityResult,
    state: ResolutionState,
    warnings: list[str],
) -> tuple[TransportabilityResult, Any | None]:
    if tr_result.status is not TransportabilityStatus.UNSUPPORTED:
        return tr_result, None
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
    return tr_result, partial_identification


def _append_outer_search_annotations(
    *,
    tr_result: TransportabilityResult,
    outer: dict[str, Any],
    warnings: list[str],
    search_events: list[str],
) -> list[str]:
    identification_trace = list(tr_result.identification_trace)
    identification_trace.append(f"outer_search_configs_evaluated:{outer['configs_evaluated']}")
    if outer["truncated"]:
        for token in ("outer_search_truncated", "search_budget_exhausted"):
            if token not in search_events:
                search_events.append(token)
        warnings.append("Bounded alignment outer-search truncated due to budget/time limit.")
        identification_trace.append("outer_search_truncated")
        identification_trace.append("search_budget_exhausted")
    return identification_trace


def _attach_partial_identification(
    update_payload: dict[str, Any],
    partial_identification: Any | None,
) -> None:
    if partial_identification is not None:
        update_payload["partial_identification_result"] = partial_identification


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
    identification_trace = _append_outer_search_annotations(
        tr_result=tr_result,
        outer=outer,
        warnings=warnings,
        search_events=search_events,
    )
    tr_result, partial_identification = _apply_partial_identification_fallback(
        tr_result=tr_result,
        state=state,
        warnings=warnings,
    )

    metadata["lineage_three_graph"] = _build_three_graph_lineage(tr_result=tr_result, state=state)
    metadata["alignment_outer_search"] = {
        "configs_evaluated": int(outer["configs_evaluated"]),
        "best_score": float(outer["best_score"]),
        "truncated": bool(outer["truncated"]),
    }
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
    _attach_partial_identification(update_payload, partial_identification)
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


def _legal_constraints_to_s_nodes(
    *,
    mappings: list[LegalToDAGMapping],
    causal_graph: CausalGraphModel,
    expert_review_reasons: list[str] | None = None,
) -> list[SNode]:
    graph_nodes = set(causal_graph.nodes)
    nodes: list[SNode] = []
    seen: set[tuple[str, str]] = set()
    for mapping in mappings:
        constraint = mapping.legal_constraint
        mapping_type = mapping.mapping_type.value
        if mapping.requires_expert_review:
            _append_unique(
                expert_review_reasons,
                f"legal_mapping_requires_expert_review:{constraint.constraint_id}:{mapping_type}",
            )
        severity = "high" if constraint.severity == ConstraintSeverity.HARD else "medium"
        delta = 1.0 if constraint.severity == ConstraintSeverity.HARD else 0.4
        target_var, unresolved_reason = _candidate_legal_target_variable(mapping, graph_nodes)
        if target_var is None:
            _append_unique(
                expert_review_reasons,
                f"legal_mapping_unresolved:{constraint.constraint_id}:{unresolved_reason}",
            )
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


def _append_unique(reasons: list[str] | None, reason: str) -> None:
    if reasons is not None and reason not in reasons:
        reasons.append(reason)


def _candidate_legal_target_variable(
    mapping: LegalToDAGMapping,
    graph_nodes: set[str],
) -> tuple[str | None, str | None]:
    """Return a candidate under the current review-required graph projection.

    ADR-0051 remains proposed, and the mapping schema does not define target
    resolution. This helper does not validate a legal rule. Missing or ambiguous
    projections require review and are not evidence that a rule is invalid.
    """
    if mapping.mapping_type is LegalToDAGMappingType.MECHANISM_NODE:
        candidate = mapping.new_node_name
        if candidate is None or not candidate.strip():
            return None, "missing_explicit_mechanism_target"
        if candidate not in graph_nodes:
            return None, "mechanism_target_not_present_in_current_graph"
        return candidate, None

    if mapping.mapping_type is LegalToDAGMappingType.EFFECT_MODIFIER:
        if mapping.new_node_name is not None:
            return None, "effect_modifier_target_shape_unresolved"
        valid_edges = {
            (source, target)
            for source, target in mapping.affected_edges
            if source in graph_nodes and target in graph_nodes
        }
        if not valid_edges:
            return None, "affected_edge_not_in_graph"
        if len(valid_edges) != 1:
            return None, "effect_modifier_edges_ambiguous"
        _, target = next(iter(valid_edges))
        return target, None

    return None, "intervention_redefinition_target_not_represented"


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
