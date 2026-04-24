"""Local-independence identification helpers for continuous-time event processes."""

from __future__ import annotations

from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
    ProofStep,
)
from polisyos.ir.analytics.dynamic_causal_semantics import DynamicSemanticsAttachment
from polisyos.ir.analytics.dynamic_regime import (
    TemporalIdentificationCertificate,
    TemporalIdentificationTheoremFamily,
    TemporalInterventionSemantics,
    TemporalLawObject,
    TemporalObservabilityRegime,
    TemporalTargetFunctional,
)
from polisyos.ir.analytics.local_independence import LocalIndependenceWeightingCertificate


def build_temporal_identification_certificate(
    certificate: LocalIndependenceWeightingCertificate,
) -> TemporalIdentificationCertificate:
    """Compress a detailed Stage 4.5 certificate into the shared temporal ID surface."""

    target_functionals = {
        TemporalTargetFunctional.CUMULATIVE_INCIDENCE,
        TemporalTargetFunctional.SURVIVAL_CURVE,
    }
    return TemporalIdentificationCertificate(
        theorem_family=TemporalIdentificationTheoremFamily.LOCAL_INDEPENDENCE_WEIGHTING_V1,
        identified_functionals=tuple(sorted(target_functionals, key=lambda item: item.value)),
        intervention_semantics=TemporalInterventionSemantics.INTENSITY_REPLACEMENT,
        observability_regime=TemporalObservabilityRegime.OBSERVED_FILTRATION,
        law_object=TemporalLawObject.INTENSITY_COMPENSATOR,
        assumptions=certificate.assumptions,
        notes={
            "source_theorem_family": certificate.theorem_family,
            "proof_bundle_target_functional": certificate.target.functional,
            "process_family": certificate.graph.process_family,
        },
    )


def _local_independence_proof_steps(
    certificate: LocalIndependenceWeightingCertificate,
) -> list[ProofStep]:
    steps: list[ProofStep] = []
    if "causal_validity_intensity_replacement" in certificate.assumptions:
        steps.append(
            ProofStep(
                rule_name="LI_CAUSAL_VALIDITY",
                antecedent_vars=(certificate.treatment_intervention.node,),
                consequent_vars=(certificate.target.outcome_process,),
                applied_to_graph_state=certificate.graph.representation,
            )
        )
    if certificate.graphical_checks.independent_censoring.checked:
        steps.append(
            ProofStep(
                rule_name="LI_IC_CENSORING",
                antecedent_vars=(certificate.censoring_intervention.node,),
                consequent_vars=(certificate.target.outcome_process,),
                applied_to_graph_state=certificate.graph.separation_criterion,
            )
        )
    for item in certificate.graphical_checks.eliminability.elimination_sequence:
        steps.append(
            ProofStep(
                rule_name="LI_ELIMINABILITY_STEP",
                antecedent_vars=tuple(item.removed),
                consequent_vars=(certificate.treatment_intervention.node,),
                applied_to_graph_state=item.justification_kind,
                depth=int(item.step),
                graph_state_before=item.witness or "",
            )
        )
    if certificate.verification_status == "identified":
        steps.append(
            ProofStep(
                rule_name="LI_WEIGHTING_IDENTIFY",
                antecedent_vars=(certificate.treatment_intervention.node,),
                consequent_vars=(certificate.target.outcome_process,),
                applied_to_graph_state=certificate.identification.method,
            )
        )
    return steps


def li_id_algorithm(
    *,
    dynamic_semantics: DynamicSemanticsAttachment,
    certificate: LocalIndependenceWeightingCertificate,
    query_ref: str | None = None,
) -> IdentificationResult:
    """Return an ID-engine-style result for Stage 4.5 local-independence proofs."""

    temporal_certificate = build_temporal_identification_certificate(certificate)
    status = (
        IdentificationStatus.IDENTIFIED
        if certificate.verification_status == "identified"
        else IdentificationStatus.ORACLE_NEEDED
    )
    return IdentificationResult(
        status=status,
        estimand_ast=certificate,
        hedge_certificate=None,
        trace=list(certificate.proof_trace),
        required_distributions=[],
        algorithm_version=certificate.theorem_family,
        proof_steps=_local_independence_proof_steps(certificate),
        query_str=query_ref or "",
        metadata={
            "dynamic_semantics": dynamic_semantics.model_dump(mode="json"),
            "local_independence_certificate": certificate.to_summary_dict(),
            "local_independence_verification_status": certificate.verification_status,
            "temporal_identification_certificate": temporal_certificate.model_dump(mode="json"),
        },
    )


__all__ = [
    "build_temporal_identification_certificate",
    "li_id_algorithm",
]
