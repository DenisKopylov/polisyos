"""Causal justification, assumption, and proof-artifact helpers for distributional analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.ir.analytics.causal import (
    ProofBundle,
    persist_proof_bundle,
    proof_bundle_from_identification_result,
    proof_bundle_from_negative_certificate,
)
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.analytics.distributional import (
    CausalAssumptionCard,
    DistributionalBoundUniformity,
    DistributionalCouplingStatus,
    DistributionalJustification,
    DistributionalProofArtifact,
    DistributionalProofTarget,
    persist_causal_assumption_card,
    persist_distributional_proof_artifact,
)
from polisyos.ir.analytics.estimand import DistributionLawQuery, EstimandAST, persist_estimand_ast
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    NegativeCertificate,
    persist_negative_certificate,
)
from polisyos.ir.registry.refs import (
    CausalAssumptionCardRef,
    CausalGraphModelRef,
    DistributionalBoundsBundleRef,
    DistributionalProofArtifactRef,
    EstimandASTRef,
    NegativeCertificateRef,
    ProofBundleRef,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

_DISTRIBUTIONAL_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_DISTRIBUTIONAL_EXECUTION_ERRORS = (RuntimeError, TypeError, ValueError, ValidationError)

_BASE_CAUSAL_ASSUMPTIONS = [
    "distributional_estimand_not_proof_kernel_identified",
    "scenario_level_ot_coupling",
    "sinkhorn_regularized_discrete_measure_approximation",
]

_ASSUMPTION_DESCRIPTIONS = {
    "distributional_estimand_not_proof_kernel_identified": (
        "No proof-kernel identification result is attached for the counterfactual marginal law "
        "on this path, so the distributional claim must remain below identified/bounded status."
    ),
    "scenario_level_ot_coupling": (
        "The OT coupling is rendered as a scenario object unless a separate joint-law "
        "identification or set-identification argument is supplied."
    ),
    "sinkhorn_regularized_discrete_measure_approximation": (
        "The transport plan is a Sinkhorn-regularized discrete approximation used for "
        "numerical stability and visualization, not a proof of a structural joint law."
    ),
    "uniform_weighting_used": (
        "Distributional summaries use uniform unit weights rather than density-ratio reweighting."
    ),
    "positivity": "Positivity / overlap must hold on the support of the interventional query.",
    "overlap": "Source and target supports must overlap on the covariate region used by the query.",
    "sutva": "SUTVA must hold so each unit's potential outcome is well defined.",
    "consistency": "Consistency must link the observed outcome to the potential outcome under the realized treatment.",
    "no_interference": "No interference must hold unless the query explicitly models spillovers.",
    "time_stationarity": "Time-stationarity assumptions must hold for longitudinal identification formulas.",
    "selection": "Selection assumptions must justify the observed conditioning event used by the query.",
    "exclusion_restriction": "Exclusion restriction must hold for IV-style distributional identification claims.",
}

_TESTABLE_ASSUMPTIONS = {
    "positivity",
    "overlap",
    "time_stationarity",
    "selection",
    "uniform_weighting_used",
    "sinkhorn_regularized_discrete_measure_approximation",
}


@dataclass(frozen=True)
class _PersistedAssumptionCards:
    all_refs: list[CausalAssumptionCardRef]
    marginal_refs: list[CausalAssumptionCardRef]
    coupling_refs: list[CausalAssumptionCardRef]


@dataclass(frozen=True)
class _DistributionalJustificationResolution:
    marginal_justification: DistributionalJustification
    coupling_justification: DistributionalJustification | None
    causal_assumptions: list[str]
    coupling_assumptions: list[str]
    metadata: dict[str, Any]
    proof_bundle: ProofBundle | None = None
    coupling_negative_certificate: NegativeCertificate | None = None


def _causal_assumptions(
    *,
    weighting_mode: str,
    proof_kernel_identified: bool = False,
) -> list[str]:
    assumptions = [
        assumption
        for assumption in _BASE_CAUSAL_ASSUMPTIONS
        if (
            not proof_kernel_identified
            or assumption != "distributional_estimand_not_proof_kernel_identified"
        )
    ]
    if weighting_mode != "density_ratio":
        assumptions.append("uniform_weighting_used")
    return assumptions


def _resolve_distributional_treatment_variable(state: ExperimentState) -> str | None:
    for key in ("distributional_treatment_variable", "query_treatment", "treatment_variable"):
        raw = state.params.get(key)
        if raw is None:
            continue
        candidate = str(raw).strip()
        if candidate:
            return candidate
    return None


def _resolve_distributional_graph(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> tuple[CausalGraphModelRef | None, Any | None]:
    raw = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
    if raw is None:
        raw = state.params.get("causal_graph_ref")
    if raw is None:
        return None, None
    try:
        payload = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw
        graph_ref = CausalGraphModelRef.model_validate(payload)
        return graph_ref, load_causal_graph_model(_ensure_ir_artifact_store(ctx.store), graph_ref)
    except _DISTRIBUTIONAL_LOAD_ERRORS:
        return None, None


def _resolve_distributional_justification(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    outcome_name: str,
    weighting_mode: str,
) -> _DistributionalJustificationResolution:
    base_metadata = {
        "distributional_query_kind": "interventional_law",
        "coupling_justification": DistributionalJustification.SCENARIO.value,
        "marginal_law_justification": DistributionalJustification.SCENARIO.value,
    }
    treatment = _resolve_distributional_treatment_variable(state)
    if treatment is None:
        return _DistributionalJustificationResolution(
            marginal_justification=DistributionalJustification.SCENARIO,
            coupling_justification=DistributionalJustification.SCENARIO,
            causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
            coupling_assumptions=_coupling_assumptions(weighting_mode=weighting_mode),
            metadata={
                **base_metadata,
                "proof_kernel": {
                    "status": "unavailable",
                    "reason": "missing_treatment_variable",
                },
            },
        )

    graph_ref, graph = _resolve_distributional_graph(ctx, state)
    if graph_ref is None or graph is None:
        return _DistributionalJustificationResolution(
            marginal_justification=DistributionalJustification.SCENARIO,
            coupling_justification=DistributionalJustification.SCENARIO,
            causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
            coupling_assumptions=_coupling_assumptions(weighting_mode=weighting_mode),
            metadata={
                **base_metadata,
                "proof_kernel": {
                    "status": "unavailable",
                    "reason": "missing_reconciled_causal_graph",
                    "treatment_variable": treatment,
                },
            },
        )

    query = DistributionLawQuery(
        outcome_variables=(outcome_name,),
        intervention_set=(treatment,),
        support_space="real",
        representation="cdf",
    )
    engine = CausalEngine(registry=None, knowledge_base=None)
    result = engine.identify(
        treatment,
        outcome_name,
        graph,
        distribution_query=query,
    )
    coupling_assumptions = _coupling_assumptions(weighting_mode=weighting_mode)

    if isinstance(result, IdentificationResult):
        proof_bundle = proof_bundle_from_identification_result(
            result,
            graph_ref=str(graph_ref.artifact_id),
        )
        proof_metadata = {
            "status": proof_bundle.proof_status,
            "theorem_family": proof_bundle.theorem_family,
            "proof_stratum": proof_bundle.proof_stratum,
            "query_kind": proof_bundle.metadata.get("query_kind"),
            "distributional_query_kind": "interventional_law",
            "distribution_family": proof_bundle.metadata.get("distribution_family"),
            "generator_type": proof_bundle.metadata.get("generator_type"),
            "parameter_domain": proof_bundle.metadata.get("parameter_domain"),
            "support_space": proof_bundle.metadata.get("support_space"),
            "representation": proof_bundle.metadata.get("representation"),
            "derived_functionals_allowed": proof_bundle.metadata.get("derived_functionals_allowed"),
            "not_identified_objects": proof_bundle.metadata.get("not_identified_objects"),
            "query_ref": proof_bundle.query_ref,
            "graph_ref": str(graph_ref.artifact_id),
            "treatment_variable": treatment,
            "outcome_name": outcome_name,
        }
        if result.status is IdentificationStatus.IDENTIFIED:
            assumptions = _causal_assumptions(
                weighting_mode=weighting_mode,
                proof_kernel_identified=True,
            )
            for assumption in proof_bundle.assumptions:
                if assumption not in assumptions:
                    assumptions.append(assumption)
            return _DistributionalJustificationResolution(
                marginal_justification=DistributionalJustification.IDENTIFIED,
                coupling_justification=DistributionalJustification.SCENARIO,
                causal_assumptions=assumptions,
                coupling_assumptions=coupling_assumptions,
                metadata={
                    **base_metadata,
                    "marginal_law_justification": DistributionalJustification.IDENTIFIED.value,
                    "proof_kernel": proof_metadata,
                },
                proof_bundle=proof_bundle,
                coupling_negative_certificate=_coupling_negative_certificate(
                    treatment=treatment,
                    outcome_name=outcome_name,
                    graph_ref=str(graph_ref.artifact_id),
                    marginal_proof=proof_bundle,
                ),
            )
        return _DistributionalJustificationResolution(
            marginal_justification=DistributionalJustification.SCENARIO,
            coupling_justification=DistributionalJustification.SCENARIO,
            causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
            coupling_assumptions=coupling_assumptions,
            metadata={
                **base_metadata,
                "proof_kernel": proof_metadata,
            },
            proof_bundle=proof_bundle,
        )

    if isinstance(result, NegativeCertificate):
        proof_bundle = proof_bundle_from_negative_certificate(
            result,
            graph_ref=str(graph_ref.artifact_id),
            query_ref=f"P({outcome_name} in A | do({treatment}))",
            theorem_family="negative_distribution_law",
            status_raw="hedge_found",
        ).model_copy(
            update={
                "metadata": {
                    "query_kind": "distribution_law",
                    "distribution_family": "cdf",
                    "generator_type": query.generator_type,
                    "parameter_domain": query.resolved_parameter_domain,
                    "measure_determination_regime": "countable_generator_reduction",
                    "regularity_assumptions": [
                        "cdf_monotone",
                        "cdf_right_continuous",
                        "cdf_limits_0_1",
                    ],
                    "derived_functionals_allowed": [
                        "survival",
                        "tail_probability",
                        "quantile",
                        "expected_shortfall",
                        "quantile_shift",
                        "tail_risk_delta",
                        "histogram",
                    ],
                    "not_identified_objects": [
                        "ot_coupling",
                        "joint_potential_outcome_law",
                        "individual_treatment_effect_distribution",
                        "cross_world_transport_map",
                    ],
                    "status": "non_identified",
                    "required_distributions_count": len(result.required_distributions),
                },
            }
        )
        return _DistributionalJustificationResolution(
            marginal_justification=DistributionalJustification.SCENARIO,
            coupling_justification=DistributionalJustification.SCENARIO,
            causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
            coupling_assumptions=coupling_assumptions,
            metadata={
                **base_metadata,
                "proof_kernel": {
                    "status": "non_identified",
                    "reason": result.to_summary(),
                    "blocking_type": result.blocking_type.value,
                    "query_kind": "distribution_law",
                    "distributional_query_kind": "interventional_law",
                    "treatment_variable": treatment,
                    "outcome_name": outcome_name,
                    "graph_ref": str(graph_ref.artifact_id),
                },
            },
            proof_bundle=proof_bundle,
        )

    return _DistributionalJustificationResolution(
        marginal_justification=DistributionalJustification.SCENARIO,
        coupling_justification=DistributionalJustification.SCENARIO,
        causal_assumptions=_causal_assumptions(weighting_mode=weighting_mode),
        coupling_assumptions=_coupling_assumptions(weighting_mode=weighting_mode),
        metadata={
            **base_metadata,
            "proof_kernel": {
                "status": "unavailable",
                "reason": "unexpected_distribution_proof_result",
                "distributional_query_kind": "interventional_law",
                "treatment_variable": treatment,
                "outcome_name": outcome_name,
            },
        },
    )


def _coupling_assumptions(*, weighting_mode: str) -> list[str]:
    assumptions = [
        assumption
        for assumption in _causal_assumptions(
            weighting_mode=weighting_mode,
            proof_kernel_identified=True,
        )
        if assumption != "distributional_estimand_not_proof_kernel_identified"
    ]
    return assumptions


def _coupling_negative_certificate(
    *,
    treatment: str,
    outcome_name: str,
    graph_ref: str,
    marginal_proof: ProofBundle,
) -> NegativeCertificate:
    return NegativeCertificate(
        blocking_type=BlockingType.COUPLING_NOT_IDENTIFIED,
        blocking_description=(
            f"Marginal counterfactual law P({outcome_name} in A | do({treatment})) is certified, "
            "but the OT coupling / joint counterfactual law is not identified from current assumptions."
        ),
        technical_detail=(
            "Identified marginals do not determine the cross-world or transport coupling without "
            "additional assumptions such as rank invariance, monotone response, or panel linkage."
        ),
        quantitative_diagnostics={
            "graph_ref": graph_ref,
            "marginal_theorem_family": marginal_proof.theorem_family,
            "marginal_proof_status": marginal_proof.proof_status,
            "marginal_proof_stratum": marginal_proof.proof_stratum,
            "distribution_family": marginal_proof.metadata.get("distribution_family"),
            "not_identified_objects": list(
                marginal_proof.metadata.get("not_identified_objects") or []
            ),
        },
        constructive_message=(
            "Keep marginal distribution claims on the proof-carrying path, but treat coupling, "
            "transport heatmaps, and individual-level movement claims as scenario-only unless a "
            "separate coupling identification theorem is supplied."
        ),
    )


def _merge_assumptions(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for assumption in group:
            candidate = str(assumption).strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            merged.append(candidate)
    return merged


def _distributional_theorem_family(
    *,
    proof_bundle: ProofBundle | None,
    metadata: dict[str, Any],
) -> str:
    if proof_bundle is not None:
        return proof_bundle.theorem_family
    proof_kernel = metadata.get("proof_kernel")
    if isinstance(proof_kernel, dict):
        status = str(proof_kernel.get("status", "") or "").strip().lower()
        if status:
            return f"distribution_law_{status}"
    return "distribution_law_scenario"


def _assumption_scope(assumption: str, *, default_scope: str) -> str:
    if assumption == "scenario_level_ot_coupling":
        return "coupling"
    if assumption in {
        "sinkhorn_regularized_discrete_measure_approximation",
        "uniform_weighting_used",
    }:
        return "estimation"
    return default_scope


def _assumption_status(
    assumption: str,
    *,
    marginal_justification: DistributionalJustification,
    default_scope: str,
) -> str:
    scope = _assumption_scope(assumption, default_scope=default_scope)
    if scope in {"coupling", "estimation"}:
        return "scenario_only"
    if marginal_justification is DistributionalJustification.BOUNDED:
        return "bound_needed"
    return "identified_needed"


def _assumption_theorem_family(
    assumption: str,
    *,
    default_theorem_family: str,
) -> str:
    if assumption == "scenario_level_ot_coupling":
        return "ot_coupling_scenario"
    if assumption == "sinkhorn_regularized_discrete_measure_approximation":
        return "ot_sinkhorn_transport"
    if assumption == "uniform_weighting_used":
        return "distributional_weighting_mode"
    if assumption == "distributional_estimand_not_proof_kernel_identified":
        return "distribution_law_unavailable"
    return default_theorem_family


def _assumption_description(assumption: str) -> str:
    description = _ASSUMPTION_DESCRIPTIONS.get(assumption)
    if description is not None:
        return description
    return assumption.replace("_", " ")


def _persist_distributional_assumption_cards(
    ctx: ExecutionContext,
    *,
    inputs: list[InputRef],
    marginal_assumptions: list[str],
    coupling_assumptions: list[str],
    marginal_justification: DistributionalJustification,
    default_theorem_family: str,
) -> _PersistedAssumptionCards:
    seen: set[str] = set()
    all_refs: list[CausalAssumptionCardRef] = []
    marginal_refs: list[CausalAssumptionCardRef] = []
    coupling_refs: list[CausalAssumptionCardRef] = []

    def _persist_group(assumptions: list[str], *, default_scope: str) -> None:
        for assumption in assumptions:
            candidate = str(assumption).strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            scope = _assumption_scope(candidate, default_scope=default_scope)
            ref = persist_causal_assumption_card(
                _ensure_ir_artifact_store(ctx.store),
                CausalAssumptionCard(
                    scope=scope,
                    status=_assumption_status(
                        candidate,
                        marginal_justification=marginal_justification,
                        default_scope=default_scope,
                    ),
                    theorem_family=_assumption_theorem_family(
                        candidate,
                        default_theorem_family=default_theorem_family,
                    ),
                    assumption_type=candidate,
                    description=_assumption_description(candidate),
                    testable=candidate in _TESTABLE_ASSUMPTIONS,
                ),
                inputs=inputs,
            )
            all_refs.append(ref)
            if scope == "coupling":
                coupling_refs.append(ref)
            elif scope == "estimation":
                marginal_refs.append(ref)
                coupling_refs.append(ref)
            else:
                marginal_refs.append(ref)

    _persist_group(marginal_assumptions, default_scope="marginal")
    _persist_group(coupling_assumptions, default_scope="coupling")
    return _PersistedAssumptionCards(
        all_refs=all_refs,
        marginal_refs=marginal_refs,
        coupling_refs=coupling_refs,
    )


def _maybe_persist_distributional_estimand_ast(
    ctx: ExecutionContext,
    *,
    proof_bundle: ProofBundle | None,
    inputs: list[InputRef],
) -> EstimandASTRef | None:
    if proof_bundle is None or proof_bundle.estimand_ast is None:
        return None
    try:
        estimand_ast = (
            proof_bundle.estimand_ast
            if isinstance(proof_bundle.estimand_ast, EstimandAST)
            else EstimandAST.model_validate(proof_bundle.estimand_ast)
        )
    except _DISTRIBUTIONAL_VALIDATION_ERRORS:
        return None
    return persist_estimand_ast(_ensure_ir_artifact_store(ctx.store), estimand_ast, inputs=inputs)


def _bound_uniformity_for_justification(
    justification: DistributionalJustification,
) -> DistributionalBoundUniformity:
    if justification is DistributionalJustification.IDENTIFIED:
        return DistributionalBoundUniformity.IDENTIFIED
    if justification is DistributionalJustification.BOUNDED:
        return DistributionalBoundUniformity.UNIFORM_OUTER
    return DistributionalBoundUniformity.NOT_APPLICABLE


def _coupling_status_for_justification(
    justification: DistributionalJustification | None,
) -> DistributionalCouplingStatus:
    if justification is DistributionalJustification.IDENTIFIED:
        return DistributionalCouplingStatus.IDENTIFIED
    if justification is DistributionalJustification.BOUNDED:
        return DistributionalCouplingStatus.SET_IDENTIFIED
    if justification is DistributionalJustification.SCENARIO:
        return DistributionalCouplingStatus.SCENARIO_ONLY
    return DistributionalCouplingStatus.NOT_USED


def _persist_distributional_proof_artifacts(
    ctx: ExecutionContext,
    *,
    inputs: list[InputRef],
    proof_bundle: ProofBundle | None,
    metadata: dict[str, Any],
    marginal_justification: DistributionalJustification,
    coupling_justification: DistributionalJustification | None,
    marginal_assumption_refs: list[CausalAssumptionCardRef],
    coupling_assumption_refs: list[CausalAssumptionCardRef],
    coupling_negative_certificate: NegativeCertificate | None,
    distributional_bounds_refs: list[DistributionalBoundsBundleRef] | None = None,
    distributional_bounds_metadata: dict[str, Any] | None = None,
    distributional_bounds_uniformity: DistributionalBoundUniformity | None = None,
    distributional_bounds_target: DistributionalProofTarget | None = None,
) -> tuple[DistributionalProofArtifactRef | None, DistributionalProofArtifactRef | None]:
    proof_bundle_ref: ProofBundleRef | None = None
    if proof_bundle is not None:
        proof_bundle_ref = persist_proof_bundle(
            _ensure_ir_artifact_store(ctx.store), proof_bundle, inputs=inputs
        )
    estimand_ast_ref = _maybe_persist_distributional_estimand_ast(
        ctx,
        proof_bundle=proof_bundle,
        inputs=inputs,
    )
    theorem_family = _distributional_theorem_family(
        proof_bundle=proof_bundle,
        metadata=metadata,
    )
    marginal_ref: DistributionalProofArtifactRef | None = None
    bounds_refs = list(distributional_bounds_refs or [])
    if proof_bundle_ref is not None:
        marginal_ref = persist_distributional_proof_artifact(
            _ensure_ir_artifact_store(ctx.store),
            DistributionalProofArtifact(
                base_proof_ref=proof_bundle_ref,
                estimand_ast_ref=estimand_ast_ref,
                target=(
                    distributional_bounds_target
                    if (
                        marginal_justification is DistributionalJustification.BOUNDED
                        and distributional_bounds_target is not None
                    )
                    else DistributionalProofTarget.CDF
                ),
                bounded_curve_ref=(
                    bounds_refs[0]
                    if (
                        marginal_justification is DistributionalJustification.BOUNDED
                        and bounds_refs
                    )
                    else None
                ),
                bound_uniformity=(
                    distributional_bounds_uniformity
                    if (
                        marginal_justification is DistributionalJustification.BOUNDED
                        and distributional_bounds_uniformity is not None
                    )
                    else _bound_uniformity_for_justification(marginal_justification)
                ),
                coupling_status=DistributionalCouplingStatus.NOT_USED,
                theorem_family=theorem_family,
                assumption_card_refs=marginal_assumption_refs,
                metadata={
                    "distributional_query_kind": metadata.get("distributional_query_kind"),
                    "proof_kernel": metadata.get("proof_kernel"),
                    "proof_status": proof_bundle.proof_status,
                    "justification": marginal_justification.value,
                    "distributional_bounds_refs": [
                        ref.model_dump(mode="json") for ref in bounds_refs
                    ],
                },
            ),
            inputs=inputs,
        )
    if marginal_ref is None and bounds_refs:
        bounds_metadata = dict(distributional_bounds_metadata or {})
        first_bounds_ref = bounds_refs[0]
        marginal_ref = persist_distributional_proof_artifact(
            _ensure_ir_artifact_store(ctx.store),
            DistributionalProofArtifact(
                target=distributional_bounds_target or DistributionalProofTarget.CDF,
                bounded_curve_ref=first_bounds_ref,
                bound_uniformity=(
                    distributional_bounds_uniformity or DistributionalBoundUniformity.UNIFORM_OUTER
                ),
                coupling_status=DistributionalCouplingStatus.NOT_USED,
                theorem_family=str(
                    bounds_metadata.get("primary_theorem_family")
                    or bounds_metadata.get("theorem_family")
                    or theorem_family
                    or "distributional_bounds"
                ),
                assumption_card_refs=marginal_assumption_refs,
                metadata={
                    "distributional_query_kind": metadata.get("distributional_query_kind"),
                    "justification": marginal_justification.value,
                    "distributional_bounds_refs": [
                        ref.model_dump(mode="json") for ref in bounds_refs
                    ],
                    **bounds_metadata,
                },
            ),
            inputs=[
                *inputs,
                *(
                    InputRef(artifact_id=str(ref.artifact_id), role="distributional_bounds_bundle")
                    for ref in bounds_refs
                ),
            ],
        )

    coupling_negative_ref: NegativeCertificateRef | None = None
    if coupling_negative_certificate is not None:
        coupling_negative_ref = persist_negative_certificate(
            _ensure_ir_artifact_store(ctx.store),
            coupling_negative_certificate,
            inputs=inputs,
        )
    coupling_ref: DistributionalProofArtifactRef | None = None
    coupling_status = _coupling_status_for_justification(coupling_justification)
    if coupling_status is not DistributionalCouplingStatus.NOT_USED:
        coupling_ref = persist_distributional_proof_artifact(
            _ensure_ir_artifact_store(ctx.store),
            DistributionalProofArtifact(
                base_proof_ref=proof_bundle_ref,
                estimand_ast_ref=estimand_ast_ref,
                target=DistributionalProofTarget.COUPLING,
                bound_uniformity=DistributionalBoundUniformity.NOT_APPLICABLE,
                coupling_status=coupling_status,
                theorem_family=(
                    theorem_family
                    if coupling_status is not DistributionalCouplingStatus.SCENARIO_ONLY
                    else "ot_coupling_scenario"
                ),
                assumption_card_refs=coupling_assumption_refs,
                metadata={
                    "distributional_query_kind": metadata.get("distributional_query_kind"),
                    "proof_kernel": metadata.get("proof_kernel"),
                    "negative_certificate_ref": (
                        coupling_negative_ref.model_dump(mode="json")
                        if coupling_negative_ref is not None
                        else None
                    ),
                    "justification": coupling_justification.value
                    if coupling_justification is not None
                    else None,
                },
            ),
            inputs=inputs,
        )
    return marginal_ref, coupling_ref
