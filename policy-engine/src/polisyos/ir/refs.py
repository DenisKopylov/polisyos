"""Public ir refs module API."""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polisyos.ir.artifacts import ArtifactID


class ArtifactRefModel(BaseModel, Mapping[str, object]):
    """Artifact ref model public type."""
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
    """Uncertainty envelope ref data model."""
    kind: Literal["ir.uncertainty_envelope"] = "ir.uncertainty_envelope"
    media_type: Literal["application/json"] = "application/json"


class HTEResultRef(ArtifactRefModel):
    """HTE result ref data model."""
    kind: Literal["ir.hte_result"] = "ir.hte_result"
    media_type: Literal["application/json"] = "application/json"


class PolicyRecommendationRef(ArtifactRefModel):
    """Policy recommendation ref data model."""
    kind: Literal["ir.policy_recommendation"] = "ir.policy_recommendation"
    media_type: Literal["application/json"] = "application/json"


class CausalEffectReportRef(ArtifactRefModel):
    """Causal effect report ref data model."""
    kind: Literal["ir.causal_effect_report"] = "ir.causal_effect_report"
    media_type: Literal["application/json"] = "application/json"


class ProofBundleRef(ArtifactRefModel):
    """Proof bundle ref data model."""
    kind: Literal["ir.proof_bundle"] = "ir.proof_bundle"
    media_type: Literal["application/json"] = "application/json"


class DataReadinessReportRef(ArtifactRefModel):
    """Data readiness report ref data model."""
    kind: Literal["ir.data_readiness_report"] = "ir.data_readiness_report"
    media_type: Literal["application/json"] = "application/json"


class BoundsBundleRef(ArtifactRefModel):
    """Bounds bundle ref data model."""
    kind: Literal["ir.bounds_bundle"] = "ir.bounds_bundle"
    media_type: Literal["application/json"] = "application/json"


class NegativeCertificateRef(ArtifactRefModel):
    """Negative certificate ref data model."""
    kind: Literal["ir.negative_certificate"] = "ir.negative_certificate"
    media_type: Literal["application/json"] = "application/json"


class CausalGraphModelRef(ArtifactRefModel):
    """Causal graph model ref data model."""
    kind: Literal["ir.causal_graph_model"] = "ir.causal_graph_model"
    media_type: Literal["application/json"] = "application/json"


class LiteratureCausalPriorRef(ArtifactRefModel):
    """Literature causal prior ref data model."""
    kind: Literal["ir.literature_causal_prior"] = "ir.literature_causal_prior"
    media_type: Literal["application/json"] = "application/json"


class CausalDiscoveryReportRef(ArtifactRefModel):
    """Causal discovery report ref data model."""
    kind: Literal["ir.causal_discovery_report"] = "ir.causal_discovery_report"
    media_type: Literal["application/json"] = "application/json"


class CausalSensitivityResultRef(ArtifactRefModel):
    """Causal sensitivity result ref data model."""
    kind: Literal["ir.sensitivity_result"] = "ir.sensitivity_result"
    media_type: Literal["application/json"] = "application/json"


class ABMAlignmentReportRef(ArtifactRefModel):
    """ABM alignment report ref data model."""
    kind: Literal["ir.abm_alignment_report"] = "ir.abm_alignment_report"
    media_type: Literal["application/json"] = "application/json"


class TransportabilityResultRef(ArtifactRefModel):
    """Reference to a persisted transportability result artifact."""

    kind: Literal["ir.transportability_result"] = "ir.transportability_result"
    media_type: Literal["application/json"] = "application/json"


class CausalCapabilityContractRef(ArtifactRefModel):
    """Causal capability contract ref data model."""
    kind: Literal["ir.causal_capability_contract"] = "ir.causal_capability_contract"
    media_type: Literal["application/json"] = "application/json"


class ContextAdaptiveParameterBundleRef(ArtifactRefModel):
    """Context adaptive parameter bundle ref data model."""
    kind: Literal["ir.context_adaptive_parameter_bundle"] = "ir.context_adaptive_parameter_bundle"
    media_type: Literal["application/json"] = "application/json"


class CrossGraphEvidenceProfileRef(ArtifactRefModel):
    """Cross graph evidence profile ref data model."""
    kind: Literal["ir.cross_graph_evidence_profile"] = "ir.cross_graph_evidence_profile"
    media_type: Literal["application/json"] = "application/json"


class SCMFragmentRef(ArtifactRefModel):
    """SCM fragment ref data model."""
    kind: Literal["ir.scm_fragment"] = "ir.scm_fragment"
    media_type: Literal["application/json"] = "application/json"


class VariableAlignmentCertificateRef(ArtifactRefModel):
    """Variable alignment certificate ref data model."""
    kind: Literal["ir.variable_alignment_certificate"] = "ir.variable_alignment_certificate"
    media_type: Literal["application/json"] = "application/json"


class AlignmentReportRef(ArtifactRefModel):
    """Alignment report ref data model."""
    kind: Literal["ir.alignment_report"] = "ir.alignment_report"
    media_type: Literal["application/json"] = "application/json"


class InterfaceMappingRef(ArtifactRefModel):
    """Interface mapping ref data model."""
    kind: Literal["ir.interface_mapping"] = "ir.interface_mapping"
    media_type: Literal["application/json"] = "application/json"


class CompositionCertificateRef(ArtifactRefModel):
    """Composition certificate ref data model."""
    kind: Literal["ir.composition_certificate"] = "ir.composition_certificate"
    media_type: Literal["application/json"] = "application/json"


class CompositionFailureCardBundleRef(ArtifactRefModel):
    """Composition failure card bundle ref data model."""
    kind: Literal["ir.composition_failure_card_bundle"] = "ir.composition_failure_card_bundle"
    media_type: Literal["application/json"] = "application/json"


class StructuralCausalModelSpecRef(ArtifactRefModel):
    """Structural causal model spec ref data model."""
    kind: Literal["ir.structural_causal_model_spec"] = "ir.structural_causal_model_spec"
    media_type: Literal["application/json"] = "application/json"


class CausalQueryResultRef(ArtifactRefModel):
    """Reference to a persisted causal query result artifact."""

    kind: Literal["ir.causal_query_result"] = "ir.causal_query_result"
    media_type: Literal["application/json"] = "application/json"


class ContinuousTimeQueryRef(ArtifactRefModel):
    """Continuous time query ref data model."""
    kind: Literal["ir.continuous_time_query"] = "ir.continuous_time_query"
    media_type: Literal["application/json"] = "application/json"


class TemporalInterventionTrajectoryRef(ArtifactRefModel):
    """Temporal intervention trajectory ref data model."""
    kind: Literal["ir.temporal_intervention_trajectory"] = "ir.temporal_intervention_trajectory"
    media_type: Literal["application/json"] = "application/json"


class DynamicTreatmentRegimeRef(ArtifactRefModel):
    """Dynamic treatment regime ref data model."""
    kind: Literal["ir.dynamic_treatment_regime"] = "ir.dynamic_treatment_regime"
    media_type: Literal["application/json"] = "application/json"


class EffectTrajectoryBundleRef(ArtifactRefModel):
    """Effect trajectory bundle ref data model."""
    kind: Literal["ir.effect_trajectory_bundle"] = "ir.effect_trajectory_bundle"
    media_type: Literal["application/json"] = "application/json"


class InteractionComplexRef(ArtifactRefModel):
    """Interaction complex ref data model."""
    kind: Literal["ir.interaction_complex"] = "ir.interaction_complex"
    media_type: Literal["application/json"] = "application/json"


class InterferenceCertificateRef(ArtifactRefModel):
    """Interference certificate ref data model."""
    kind: Literal["ir.interference_certificate"] = "ir.interference_certificate"
    media_type: Literal["application/json"] = "application/json"


class TwinNetworkResultRef(ArtifactRefModel):
    """Twin network result ref data model."""
    kind: Literal["ir.twin_network_result"] = "ir.twin_network_result"
    media_type: Literal["application/json"] = "application/json"


class CausalModelEnsembleRef(ArtifactRefModel):
    """Reference to a persisted causal model ensemble artifact."""

    kind: Literal["ir.causal_model_ensemble"] = "ir.causal_model_ensemble"
    media_type: Literal["application/json"] = "application/json"


class DistributionalReportRef(ArtifactRefModel):
    """Distributional report ref data model."""
    kind: Literal["ir.distributional_report"] = "ir.distributional_report"
    media_type: Literal["application/json"] = "application/json"


class DistributionalEffectBundleRef(ArtifactRefModel):
    """Distributional effect bundle ref data model."""
    kind: Literal["ir.distributional_effect_bundle"] = "ir.distributional_effect_bundle"
    media_type: Literal["application/json"] = "application/json"


class StrategicPayoffTableRef(ArtifactRefModel):
    """Strategic payoff table ref data model."""
    kind: Literal["ir.strategic_payoff_table"] = "ir.strategic_payoff_table"
    media_type: Literal["application/json"] = "application/json"


class StrategicSCMRef(ArtifactRefModel):
    """Strategic SCM ref data model."""
    kind: Literal["ir.strategic_scm"] = "ir.strategic_scm"
    media_type: Literal["application/json"] = "application/json"


class StrategicResponseBundleRef(ArtifactRefModel):
    """Strategic response bundle ref data model."""
    kind: Literal["ir.strategic_response_bundle"] = "ir.strategic_response_bundle"
    media_type: Literal["application/json"] = "application/json"


class CausalReadinessBundleRef(ArtifactRefModel):
    """Reference to a persisted causal readiness bundle artifact."""

    kind: Literal["ir.causal_readiness_bundle"] = "ir.causal_readiness_bundle"
    media_type: Literal["application/json"] = "application/json"


class CausalExecutionBundleRef(ArtifactRefModel):
    """Reference to a persisted causal execution bundle artifact."""

    kind: Literal["ir.causal_execution_bundle"] = "ir.causal_execution_bundle"
    media_type: Literal["application/json"] = "application/json"


class FiniteStateAbstractionMapRef(ArtifactRefModel):
    """Finite state abstraction map ref data model."""
    kind: Literal["ir.finite_state_abstraction_map"] = "ir.finite_state_abstraction_map"
    media_type: Literal["application/json"] = "application/json"


class AbstractionCertificateRef(ArtifactRefModel):
    """Abstraction certificate ref data model."""
    kind: Literal["ir.abstraction_certificate"] = "ir.abstraction_certificate"
    media_type: Literal["application/json"] = "application/json"


class NormativeArbitrationResultRef(ArtifactRefModel):
    """Normative arbitration result ref data model."""
    kind: Literal["ir.normative_arbitration_result"] = "ir.normative_arbitration_result"
    media_type: Literal["application/json"] = "application/json"


class BacktestReportRef(ArtifactRefModel):
    """Backtest report ref data model."""
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
    "CausalReadinessBundleRef",
    "CausalExecutionBundleRef",
    "StrategicPayoffTableRef",
    "StrategicResponseBundleRef",
    "StrategicSCMRef",
    "UncertaintyEnvelopeRef",
    "NCMSpecRef",
    "CounterfactualResultRef",
    "VariableAlignmentCertificateRef",
]
