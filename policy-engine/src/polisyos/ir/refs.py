from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polisyos.ir.artifacts import ArtifactID


class ArtifactRefModel(BaseModel, Mapping[str, object]):
    model_config = ConfigDict(extra="forbid")

    artifact_id: ArtifactID
    kind: str
    media_type: str

    def __iter__(self) -> Iterator[str]:
        yield "artifact_id"
        yield "kind"
        yield "media_type"

    def __len__(self) -> int:
        return 3

    def __getitem__(self, key: str) -> object:
        if key == "artifact_id":
            return str(self.artifact_id)
        if key == "kind":
            return self.kind
        if key == "media_type":
            return self.media_type
        raise KeyError(key)


class EvidenceBundleRef(ArtifactRefModel):
    """IR-level reference to a fabric evidence bundle artifact."""

    kind: Literal["fabric.evidence_bundle"] = "fabric.evidence_bundle"
    media_type: Literal["application/json"] = "application/json"


class UncertaintyEnvelopeRef(ArtifactRefModel):
    kind: Literal["ir.uncertainty_envelope"] = "ir.uncertainty_envelope"
    media_type: Literal["application/json"] = "application/json"


class HTEResultRef(ArtifactRefModel):
    kind: Literal["ir.hte_result"] = "ir.hte_result"
    media_type: Literal["application/json"] = "application/json"


class PolicyRecommendationRef(ArtifactRefModel):
    kind: Literal["ir.policy_recommendation"] = "ir.policy_recommendation"
    media_type: Literal["application/json"] = "application/json"


class CausalEffectReportRef(ArtifactRefModel):
    kind: Literal["ir.causal_effect_report"] = "ir.causal_effect_report"
    media_type: Literal["application/json"] = "application/json"


class ProofBundleRef(ArtifactRefModel):
    kind: Literal["ir.proof_bundle"] = "ir.proof_bundle"
    media_type: Literal["application/json"] = "application/json"


class DataReadinessReportRef(ArtifactRefModel):
    kind: Literal["ir.data_readiness_report"] = "ir.data_readiness_report"
    media_type: Literal["application/json"] = "application/json"


class BoundsBundleRef(ArtifactRefModel):
    kind: Literal["ir.bounds_bundle"] = "ir.bounds_bundle"
    media_type: Literal["application/json"] = "application/json"


class NegativeCertificateRef(ArtifactRefModel):
    kind: Literal["ir.negative_certificate"] = "ir.negative_certificate"
    media_type: Literal["application/json"] = "application/json"


class CausalGraphModelRef(ArtifactRefModel):
    kind: Literal["ir.causal_graph_model"] = "ir.causal_graph_model"
    media_type: Literal["application/json"] = "application/json"


class LiteratureCausalPriorRef(ArtifactRefModel):
    kind: Literal["ir.literature_causal_prior"] = "ir.literature_causal_prior"
    media_type: Literal["application/json"] = "application/json"


class CausalDiscoveryReportRef(ArtifactRefModel):
    kind: Literal["ir.causal_discovery_report"] = "ir.causal_discovery_report"
    media_type: Literal["application/json"] = "application/json"


class CausalSensitivityResultRef(ArtifactRefModel):
    kind: Literal["ir.sensitivity_result"] = "ir.sensitivity_result"
    media_type: Literal["application/json"] = "application/json"


class ABMAlignmentReportRef(ArtifactRefModel):
    kind: Literal["ir.abm_alignment_report"] = "ir.abm_alignment_report"
    media_type: Literal["application/json"] = "application/json"


class TransportabilityResultRef(ArtifactRefModel):
    kind: Literal["ir.transportability_result"] = "ir.transportability_result"
    media_type: Literal["application/json"] = "application/json"


class CausalCapabilityContractRef(ArtifactRefModel):
    kind: Literal["ir.causal_capability_contract"] = "ir.causal_capability_contract"
    media_type: Literal["application/json"] = "application/json"


class ContextAdaptiveParameterBundleRef(ArtifactRefModel):
    kind: Literal["ir.context_adaptive_parameter_bundle"] = "ir.context_adaptive_parameter_bundle"
    media_type: Literal["application/json"] = "application/json"


class CrossGraphEvidenceProfileRef(ArtifactRefModel):
    kind: Literal["ir.cross_graph_evidence_profile"] = "ir.cross_graph_evidence_profile"
    media_type: Literal["application/json"] = "application/json"


class SCMFragmentRef(ArtifactRefModel):
    kind: Literal["ir.scm_fragment"] = "ir.scm_fragment"
    media_type: Literal["application/json"] = "application/json"


class VariableAlignmentCertificateRef(ArtifactRefModel):
    kind: Literal["ir.variable_alignment_certificate"] = "ir.variable_alignment_certificate"
    media_type: Literal["application/json"] = "application/json"


class AlignmentReportRef(ArtifactRefModel):
    kind: Literal["ir.alignment_report"] = "ir.alignment_report"
    media_type: Literal["application/json"] = "application/json"


class InterfaceMappingRef(ArtifactRefModel):
    kind: Literal["ir.interface_mapping"] = "ir.interface_mapping"
    media_type: Literal["application/json"] = "application/json"


class CompositionCertificateRef(ArtifactRefModel):
    kind: Literal["ir.composition_certificate"] = "ir.composition_certificate"
    media_type: Literal["application/json"] = "application/json"


class CompositionFailureCardBundleRef(ArtifactRefModel):
    kind: Literal["ir.composition_failure_card_bundle"] = "ir.composition_failure_card_bundle"
    media_type: Literal["application/json"] = "application/json"


class StructuralCausalModelSpecRef(ArtifactRefModel):
    kind: Literal["ir.structural_causal_model_spec"] = "ir.structural_causal_model_spec"
    media_type: Literal["application/json"] = "application/json"


class CausalQueryResultRef(ArtifactRefModel):
    kind: Literal["ir.causal_query_result"] = "ir.causal_query_result"
    media_type: Literal["application/json"] = "application/json"


class ContinuousTimeQueryRef(ArtifactRefModel):
    kind: Literal["ir.continuous_time_query"] = "ir.continuous_time_query"
    media_type: Literal["application/json"] = "application/json"


class TemporalInterventionTrajectoryRef(ArtifactRefModel):
    kind: Literal["ir.temporal_intervention_trajectory"] = "ir.temporal_intervention_trajectory"
    media_type: Literal["application/json"] = "application/json"


class DynamicTreatmentRegimeRef(ArtifactRefModel):
    kind: Literal["ir.dynamic_treatment_regime"] = "ir.dynamic_treatment_regime"
    media_type: Literal["application/json"] = "application/json"


class EffectTrajectoryBundleRef(ArtifactRefModel):
    kind: Literal["ir.effect_trajectory_bundle"] = "ir.effect_trajectory_bundle"
    media_type: Literal["application/json"] = "application/json"


class InteractionComplexRef(ArtifactRefModel):
    kind: Literal["ir.interaction_complex"] = "ir.interaction_complex"
    media_type: Literal["application/json"] = "application/json"


class InterferenceCertificateRef(ArtifactRefModel):
    kind: Literal["ir.interference_certificate"] = "ir.interference_certificate"
    media_type: Literal["application/json"] = "application/json"


class TwinNetworkResultRef(ArtifactRefModel):
    kind: Literal["ir.twin_network_result"] = "ir.twin_network_result"
    media_type: Literal["application/json"] = "application/json"


class CausalModelEnsembleRef(ArtifactRefModel):
    kind: Literal["ir.causal_model_ensemble"] = "ir.causal_model_ensemble"
    media_type: Literal["application/json"] = "application/json"


class DistributionalReportRef(ArtifactRefModel):
    kind: Literal["ir.distributional_report"] = "ir.distributional_report"
    media_type: Literal["application/json"] = "application/json"


class DistributionalEffectBundleRef(ArtifactRefModel):
    kind: Literal["ir.distributional_effect_bundle"] = "ir.distributional_effect_bundle"
    media_type: Literal["application/json"] = "application/json"


class StrategicPayoffTableRef(ArtifactRefModel):
    kind: Literal["ir.strategic_payoff_table"] = "ir.strategic_payoff_table"
    media_type: Literal["application/json"] = "application/json"


class StrategicSCMRef(ArtifactRefModel):
    kind: Literal["ir.strategic_scm"] = "ir.strategic_scm"
    media_type: Literal["application/json"] = "application/json"


class StrategicResponseBundleRef(ArtifactRefModel):
    kind: Literal["ir.strategic_response_bundle"] = "ir.strategic_response_bundle"
    media_type: Literal["application/json"] = "application/json"


class FiniteStateAbstractionMapRef(ArtifactRefModel):
    kind: Literal["ir.finite_state_abstraction_map"] = "ir.finite_state_abstraction_map"
    media_type: Literal["application/json"] = "application/json"


class AbstractionCertificateRef(ArtifactRefModel):
    kind: Literal["ir.abstraction_certificate"] = "ir.abstraction_certificate"
    media_type: Literal["application/json"] = "application/json"


class NormativeArbitrationResultRef(ArtifactRefModel):
    kind: Literal["ir.normative_arbitration_result"] = "ir.normative_arbitration_result"
    media_type: Literal["application/json"] = "application/json"


class BacktestReportRef(ArtifactRefModel):
    kind: Literal["ir.backtest_report"] = "ir.backtest_report"
    media_type: Literal["application/json"] = "application/json"


class NCMSpecRef(ArtifactRefModel):
    """Reference to a persisted NCMSpec artifact."""

    kind: Literal["ir.ncm_spec"] = "ir.ncm_spec"
    media_type: Literal["application/json"] = "application/json"


class CounterfactualResultRef(ArtifactRefModel):
    """Reference to a persisted counterfactual query result artifact."""

    kind: Literal["ir.counterfactual_result"] = "ir.counterfactual_result"
    media_type: Literal["application/json"] = "application/json"


__all__ = [
    "AbstractionCertificateRef",
    "ABMAlignmentReportRef",
    "AlignmentReportRef",
    "BacktestReportRef",
    "BoundsBundleRef",
    "CompositionCertificateRef",
    "CompositionFailureCardBundleRef",
    "CausalDiscoveryReportRef",
    "CausalEffectReportRef",
    "CausalGraphModelRef",
    "DataReadinessReportRef",
    "LiteratureCausalPriorRef",
    "InterfaceMappingRef",
    "CausalSensitivityResultRef",
    "TransportabilityResultRef",
    "CausalCapabilityContractRef",
    "ContextAdaptiveParameterBundleRef",
    "ContinuousTimeQueryRef",
    "CrossGraphEvidenceProfileRef",
    "InteractionComplexRef",
    "InterferenceCertificateRef",
    "SCMFragmentRef",
    "StructuralCausalModelSpecRef",
    "CausalQueryResultRef",
    "TemporalInterventionTrajectoryRef",
    "DynamicTreatmentRegimeRef",
    "EffectTrajectoryBundleRef",
    "FiniteStateAbstractionMapRef",
    "TwinNetworkResultRef",
    "CausalModelEnsembleRef",
    "DistributionalEffectBundleRef",
    "DistributionalReportRef",
    "EvidenceBundleRef",
    "ArtifactRefModel",
    "HTEResultRef",
    "NegativeCertificateRef",
    "NormativeArbitrationResultRef",
    "PolicyRecommendationRef",
    "ProofBundleRef",
    "StrategicPayoffTableRef",
    "StrategicResponseBundleRef",
    "StrategicSCMRef",
    "UncertaintyEnvelopeRef",
    "NCMSpecRef",
    "CounterfactualResultRef",
    "VariableAlignmentCertificateRef",
]
