"""Define typed artifact references that preserve ``kind`` and ``media_type``.

These lightweight mapping-compatible models are the stable handles exchanged
between persistence helpers, bundle manifests, and downstream loaders. A ref
always carries a content-addressed ``artifact_id`` plus the expected artifact
kind/media type so callers can validate the boundary before loading payloads.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polisyos.ir.artifacts import ArtifactID


class ArtifactRefModel(BaseModel, Mapping[str, object]):
    """Provide the common mapping-compatible base contract for artifact refs."""

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
    """Stable handle for a persisted uncertainty envelope produced by estimators and read by reporting layers."""

    kind: Literal["ir.uncertainty_envelope"] = "ir.uncertainty_envelope"
    media_type: Literal["application/json"] = "application/json"


class ForecastingUncertaintyBundleRef(ArtifactRefModel):
    """Stable handle for persisted multi-horizon forecasting uncertainty bundles."""

    kind: Literal["ir.forecasting_uncertainty_bundle"] = "ir.forecasting_uncertainty_bundle"
    media_type: Literal["application/json"] = "application/json"


class EstimandASTRef(ArtifactRefModel):
    """Stable handle for a persisted normalized estimand AST."""

    kind: Literal["ir.estimand_ast"] = "ir.estimand_ast"
    media_type: Literal["application/json"] = "application/json"


class KernelEstimatorSpecRef(ArtifactRefModel):
    """Stable handle for a persisted kernel-estimator lowering specification."""

    kind: Literal["ir.kernel_estimator_spec"] = "ir.kernel_estimator_spec"
    media_type: Literal["application/json"] = "application/json"


class OperatorEffectBundleRef(ArtifactRefModel):
    """Stable handle for a persisted operator-valued causal effect bundle."""

    kind: Literal["ir.operator_effect_bundle"] = "ir.operator_effect_bundle"
    media_type: Literal["application/json"] = "application/json"


class HTEResultRef(ArtifactRefModel):
    """Stable handle for persisted heterogeneous-treatment-effect results used by subgroup and equity analyses."""

    kind: Literal["ir.hte_result"] = "ir.hte_result"
    media_type: Literal["application/json"] = "application/json"


class PolicyRecommendationRef(ArtifactRefModel):
    """Stable handle for a persisted policy recommendation once decision synthesis has frozen the artifact."""

    kind: Literal["ir.policy_recommendation"] = "ir.policy_recommendation"
    media_type: Literal["application/json"] = "application/json"


class CausalEffectReportRef(ArtifactRefModel):
    """Stable handle for persisted causal-effect estimates consumed by governance, briefs, and downstream runners."""

    kind: Literal["ir.causal_effect_report"] = "ir.causal_effect_report"
    media_type: Literal["application/json"] = "application/json"


class ProofBundleRef(ArtifactRefModel):
    """Stable handle for persisted identification or proof bundles reviewed by governance and auditors."""

    kind: Literal["ir.proof_bundle"] = "ir.proof_bundle"
    media_type: Literal["application/json"] = "application/json"


class FrontierSketchRef(ArtifactRefModel):
    """Stable handle for persisted research-boundary sketches attached to Phase-closure artifacts."""

    kind: Literal["ir.frontier_sketch"] = "ir.frontier_sketch"
    media_type: Literal["application/json"] = "application/json"


class DPRobustnessCertificateRef(ArtifactRefModel):
    """Stable handle for DP distortion audits attached to causal proof bundles."""

    kind: Literal["ir.dp_robustness_certificate"] = "ir.dp_robustness_certificate"
    media_type: Literal["application/json"] = "application/json"


class DataReadinessReportRef(ArtifactRefModel):
    """Stable handle for persisted data-readiness reports emitted before execution is allowed to proceed."""

    kind: Literal["ir.data_readiness_report"] = "ir.data_readiness_report"
    media_type: Literal["application/json"] = "application/json"


class SurveyQualityCertificateRef(ArtifactRefModel):
    """Stable handle for persisted survey-quality certificates."""

    kind: Literal["ir.survey_quality_certificate"] = "ir.survey_quality_certificate"
    media_type: Literal["application/json"] = "application/json"


class MicrosimCalibrationReportRef(ArtifactRefModel):
    """Stable handle for persisted microsim calibration gate reports."""

    kind: Literal["ir.microsim_calibration_report"] = "ir.microsim_calibration_report"
    media_type: Literal["application/json"] = "application/json"


class DependenceStructureRef(ArtifactRefModel):
    """Stable handle for the shared persisted dependence primitive."""

    kind: Literal["ir.dependence_structure"] = "ir.dependence_structure"
    media_type: Literal["application/json"] = "application/json"


class MobilityReportRef(ArtifactRefModel):
    """Stable handle for the typed mobility shell registered in Phase 1."""

    kind: Literal["ir.mobility_report"] = "ir.mobility_report"
    media_type: Literal["application/json"] = "application/json"


class BoundsBundleRef(ArtifactRefModel):
    """Stable handle for persisted partial-identification outputs consumed by readiness checks and reporting."""

    kind: Literal["ir.bounds_bundle"] = "ir.bounds_bundle"
    media_type: Literal["application/json"] = "application/json"


class BoundsTighteningLogRef(ArtifactRefModel):
    """Stable handle for certified bounds-tightening search logs."""

    kind: Literal["ir.bounds_tightening_log"] = "ir.bounds_tightening_log"
    media_type: Literal["application/json"] = "application/json"


class DualCertificateRef(ArtifactRefModel):
    """Stable handle for persisted LP dual certificates consumed by bounds auditing."""

    kind: Literal["ir.dual_certificate"] = "ir.dual_certificate"
    media_type: Literal["application/json"] = "application/json"


class ProximalIdentificationCertificateRef(ArtifactRefModel):
    """Stable handle for persisted proximal identification certificates consumed by proof bundles."""

    kind: Literal["ir.proximal_identification_certificate"] = (
        "ir.proximal_identification_certificate"
    )
    media_type: Literal["application/json"] = "application/json"


class BridgePlausibilityReportRef(ArtifactRefModel):
    """Stable handle for persisted proximal bridge plausibility diagnostics."""

    kind: Literal["ir.bridge_plausibility_report"] = "ir.bridge_plausibility_report"
    media_type: Literal["application/json"] = "application/json"


class LocalIndependenceWeightingCertificateRef(ArtifactRefModel):
    """Stable handle for persisted local-independence weighting certificates."""

    kind: Literal["ir.local_independence_weighting_certificate"] = (
        "ir.local_independence_weighting_certificate"
    )
    media_type: Literal["application/json"] = "application/json"


class RecoverabilityCertificateRef(ArtifactRefModel):
    """Stable handle for persisted recoverability certificates consumed by readiness and proof layers."""

    kind: Literal["ir.recoverability_certificate"] = "ir.recoverability_certificate"
    media_type: Literal["application/json"] = "application/json"


class JointDecisionCertificateRef(ArtifactRefModel):
    """Stable handle for persisted joint identification-recoverability decisions."""

    kind: Literal["ir.joint_decision_certificate"] = "ir.joint_decision_certificate"
    media_type: Literal["application/json"] = "application/json"


class NegativeCertificateRef(ArtifactRefModel):
    """Stable handle for persisted negative-control certificates that can block unsafe execution."""

    kind: Literal["ir.negative_certificate"] = "ir.negative_certificate"
    media_type: Literal["application/json"] = "application/json"


class CausalGraphModelRef(ArtifactRefModel):
    """Stable handle for a persisted causal graph model once discovery or linking has frozen the structure."""

    kind: Literal["ir.causal_graph_model"] = "ir.causal_graph_model"
    media_type: Literal["application/json"] = "application/json"


class LiteratureCausalPriorRef(ArtifactRefModel):
    """Stable handle for persisted literature priors produced by academic synthesis and consumed by calibration."""

    kind: Literal["ir.literature_causal_prior"] = "ir.literature_causal_prior"
    media_type: Literal["application/json"] = "application/json"


class CausalDiscoveryReportRef(ArtifactRefModel):
    """Stable handle for persisted discovery diagnostics used when selecting or auditing graph structure."""

    kind: Literal["ir.causal_discovery_report"] = "ir.causal_discovery_report"
    media_type: Literal["application/json"] = "application/json"


class RegimeShiftIdentificationCertificateRef(ArtifactRefModel):
    """Stable handle for persisted ICP regime-shift identification certificates."""

    kind: Literal["ir.regime_shift_identification_certificate"] = (
        "ir.regime_shift_identification_certificate"
    )
    media_type: Literal["application/json"] = "application/json"


class CausalSensitivityResultRef(ArtifactRefModel):
    """Stable handle for persisted sensitivity-analysis output consumed by robustness and governance checks."""

    kind: Literal["ir.sensitivity_result"] = "ir.sensitivity_result"
    media_type: Literal["application/json"] = "application/json"


class ABMAlignmentReportRef(ArtifactRefModel):
    """Stable handle for persisted ABM-alignment diagnostics consumed during model-selection review."""

    kind: Literal["ir.abm_alignment_report"] = "ir.abm_alignment_report"
    media_type: Literal["application/json"] = "application/json"


class TransportabilityResultRef(ArtifactRefModel):
    """Reference a persisted ``TransportabilityResult`` consumed by readiness gates."""

    kind: Literal["ir.transportability_result"] = "ir.transportability_result"
    media_type: Literal["application/json"] = "application/json"


class PrivacyAwareTransportCertificateRef(ArtifactRefModel):
    """Stable handle for persisted privacy-aware transportability certificates."""

    kind: Literal["ir.privacy_aware_transport_certificate"] = (
        "ir.privacy_aware_transport_certificate"
    )
    media_type: Literal["application/json"] = "application/json"


class CausalCapabilityContractRef(ArtifactRefModel):
    """Stable handle for a persisted causal-capability contract emitted by readiness compilation."""

    kind: Literal["ir.causal_capability_contract"] = "ir.causal_capability_contract"
    media_type: Literal["application/json"] = "application/json"


class ContextAdaptiveParameterBundleRef(ArtifactRefModel):
    """Stable handle for persisted context-adapted parameter bundles used by transport and calibration stages."""

    kind: Literal["ir.context_adaptive_parameter_bundle"] = "ir.context_adaptive_parameter_bundle"
    media_type: Literal["application/json"] = "application/json"


class CrossGraphEvidenceProfileRef(ArtifactRefModel):
    """Stable handle for persisted cross-graph evidence profiles used during graph arbitration."""

    kind: Literal["ir.cross_graph_evidence_profile"] = "ir.cross_graph_evidence_profile"
    media_type: Literal["application/json"] = "application/json"


class SCMFragmentRef(ArtifactRefModel):
    """Stable handle for persisted SCM fragments produced before composition into a full causal model."""

    kind: Literal["ir.scm_fragment"] = "ir.scm_fragment"
    media_type: Literal["application/json"] = "application/json"


class VariableAlignmentCertificateRef(ArtifactRefModel):
    """Stable handle for persisted variable-alignment certificates consumed by merge and reuse pipelines."""

    kind: Literal["ir.variable_alignment_certificate"] = "ir.variable_alignment_certificate"
    media_type: Literal["application/json"] = "application/json"


class LatentBridgeHypothesisRef(ArtifactRefModel):
    """Stable handle for persisted automatic latent-bridge hypotheses used by alignment certification."""

    kind: Literal["ir.latent_bridge_hypothesis"] = "ir.latent_bridge_hypothesis"
    media_type: Literal["application/json"] = "application/json"


class AlignmentReportRef(ArtifactRefModel):
    """Stable handle for persisted alignment reports reviewed by governance and composition passes."""

    kind: Literal["ir.alignment_report"] = "ir.alignment_report"
    media_type: Literal["application/json"] = "application/json"


class InterfaceMappingRef(ArtifactRefModel):
    """Stable handle for persisted interface mappings that bridge artifacts across package boundaries."""

    kind: Literal["ir.interface_mapping"] = "ir.interface_mapping"
    media_type: Literal["application/json"] = "application/json"


class CausalBlockBridgeRef(ArtifactRefModel):
    """Stable handle for persisted SBM-to-causal design-stage block bridges."""

    kind: Literal["ir.causal_block_bridge"] = "ir.causal_block_bridge"
    media_type: Literal["application/json"] = "application/json"


class CompositionCertificateRef(ArtifactRefModel):
    """Stable handle for persisted composition certificates once interface checks have succeeded."""

    kind: Literal["ir.composition_certificate"] = "ir.composition_certificate"
    media_type: Literal["application/json"] = "application/json"


class ProofWitnessIndexRef(ArtifactRefModel):
    """Stable handle for persisted proof-witness indexes used during trace replay."""

    kind: Literal["ir.proof_witness_index"] = "ir.proof_witness_index"
    media_type: Literal["application/json"] = "application/json"


class ProofComposabilityCertificateRef(ArtifactRefModel):
    """Stable handle for persisted proof-composability certificates."""

    kind: Literal["ir.proof_composability_certificate"] = "ir.proof_composability_certificate"
    media_type: Literal["application/json"] = "application/json"


class CompositionFailureCardBundleRef(ArtifactRefModel):
    """Stable handle for persisted composition failure cards returned to authoring and governance loops."""

    kind: Literal["ir.composition_failure_card_bundle"] = "ir.composition_failure_card_bundle"
    media_type: Literal["application/json"] = "application/json"


class StructuralCausalModelSpecRef(ArtifactRefModel):
    """Stable handle for a persisted structural causal model spec consumed by query planning and execution."""

    kind: Literal["ir.structural_causal_model_spec"] = "ir.structural_causal_model_spec"
    media_type: Literal["application/json"] = "application/json"


class CausalQueryResultRef(ArtifactRefModel):
    """Reference a persisted ``CausalQueryResult`` produced by query execution."""

    kind: Literal["ir.causal_query_result"] = "ir.causal_query_result"
    media_type: Literal["application/json"] = "application/json"


class ContinuousTimeQueryRef(ArtifactRefModel):
    """Stable handle for a persisted continuous-time causal query prepared for temporal solvers."""

    kind: Literal["ir.continuous_time_query"] = "ir.continuous_time_query"
    media_type: Literal["application/json"] = "application/json"


class TemporalInterventionTrajectoryRef(ArtifactRefModel):
    """Stable handle for persisted intervention trajectories consumed by temporal execution runners."""

    kind: Literal["ir.temporal_intervention_trajectory"] = "ir.temporal_intervention_trajectory"
    media_type: Literal["application/json"] = "application/json"


class DynamicTreatmentRegimeRef(ArtifactRefModel):
    """Stable handle for persisted dynamic treatment regimes consumed by DTR execution workflows."""

    kind: Literal["ir.dynamic_treatment_regime"] = "ir.dynamic_treatment_regime"
    media_type: Literal["application/json"] = "application/json"


class EffectTrajectoryBundleRef(ArtifactRefModel):
    """Stable handle for persisted effect trajectories used by forecasting and temporal reporting."""

    kind: Literal["ir.effect_trajectory_bundle"] = "ir.effect_trajectory_bundle"
    media_type: Literal["application/json"] = "application/json"


class TemporalIdentificationCertificateRef(ArtifactRefModel):
    """Stable handle for persisted temporal identification certificates."""

    kind: Literal["ir.temporal_identification_certificate"] = (
        "ir.temporal_identification_certificate"
    )
    media_type: Literal["application/json"] = "application/json"


class RoughPathInterventionCertificateRef(ArtifactRefModel):
    """Stable handle for persisted rough-path intervention certificates."""

    kind: Literal["ir.rough_path_intervention_certificate"] = (
        "ir.rough_path_intervention_certificate"
    )
    media_type: Literal["application/json"] = "application/json"


class InteractionComplexRef(ArtifactRefModel):
    """Stable handle for persisted interaction-complex artifacts used by interference-aware analysis."""

    kind: Literal["ir.interaction_complex"] = "ir.interaction_complex"
    media_type: Literal["application/json"] = "application/json"


class InterferenceCertificateRef(ArtifactRefModel):
    """Stable handle for persisted interference certificates consumed by readiness gates."""

    kind: Literal["ir.interference_certificate"] = "ir.interference_certificate"
    media_type: Literal["application/json"] = "application/json"


class MAUPInvarianceCertificateRef(ArtifactRefModel):
    """Stable handle for persisted MAUP invariance certificates used by spatial spillover diagnostics."""

    kind: Literal["ir.maup_invariance_certificate"] = "ir.maup_invariance_certificate"
    media_type: Literal["application/json"] = "application/json"


class SpatialHodgeDiagnosticsRef(ArtifactRefModel):
    """Stable handle for persisted multiscale spatial Hodge diagnostics."""

    kind: Literal["ir.spatial_hodge_diagnostics"] = "ir.spatial_hodge_diagnostics"
    media_type: Literal["application/json"] = "application/json"


class InterventionCertificateRef(ArtifactRefModel):
    """Stable handle for persisted proof-kernel intervention type certificates."""

    kind: Literal["ir.intervention_certificate"] = "ir.intervention_certificate"
    media_type: Literal["application/json"] = "application/json"


class InterventionQueryRef(ArtifactRefModel):
    """Stable handle for persisted typed proof-kernel intervention queries."""

    kind: Literal["ir.intervention_query"] = "ir.intervention_query"
    media_type: Literal["application/json"] = "application/json"


class TwinNetworkResultRef(ArtifactRefModel):
    """Stable handle for persisted twin-network results used in counterfactual analysis."""

    kind: Literal["ir.twin_network_result"] = "ir.twin_network_result"
    media_type: Literal["application/json"] = "application/json"


class CausalModelEnsembleRef(ArtifactRefModel):
    """Reference a persisted ``CausalModelEnsemble`` used for structural uncertainty."""

    kind: Literal["ir.causal_model_ensemble"] = "ir.causal_model_ensemble"
    media_type: Literal["application/json"] = "application/json"


class DistributionalReportRef(ArtifactRefModel):
    """Stable handle for persisted distributional-impact reports read by equity and policy-governance workflows."""

    kind: Literal["ir.distributional_report"] = "ir.distributional_report"
    media_type: Literal["application/json"] = "application/json"


class DistributionalEffectBundleRef(ArtifactRefModel):
    """Stable handle for persisted subgroup-effect bundles that feed distributional reporting."""

    kind: Literal["ir.distributional_effect_bundle"] = "ir.distributional_effect_bundle"
    media_type: Literal["application/json"] = "application/json"


class OrdinalPovertyReportRef(ArtifactRefModel):
    """Stable handle for persisted ordinal multidimensional poverty reports."""

    kind: Literal["ir.ordinal_poverty_report"] = "ir.ordinal_poverty_report"
    media_type: Literal["application/json"] = "application/json"


class DistributionalBoundsBundleRef(ArtifactRefModel):
    """Stable handle for persisted distributional partial-identification envelopes."""

    kind: Literal["ir.distributional_bounds_bundle"] = "ir.distributional_bounds_bundle"
    media_type: Literal["application/json"] = "application/json"


class DistributionalDualCertificateRef(ArtifactRefModel):
    """Stable handle for persisted distributional dual certificates."""

    kind: Literal["ir.distributional_dual_certificate"] = "ir.distributional_dual_certificate"
    media_type: Literal["application/json"] = "application/json"


class DistributionalProofArtifactRef(ArtifactRefModel):
    """Stable handle for persisted distributional proof wrappers over proof-kernel output."""

    kind: Literal["ir.distributional_proof_artifact"] = "ir.distributional_proof_artifact"
    media_type: Literal["application/json"] = "application/json"


class CausalAssumptionCardRef(ArtifactRefModel):
    """Stable handle for persisted typed causal-assumption cards."""

    kind: Literal["ir.causal_assumption_card"] = "ir.causal_assumption_card"
    media_type: Literal["application/json"] = "application/json"


class StrategicPayoffTableRef(ArtifactRefModel):
    """Stable handle for persisted payoff tables consumed by strategic-response analyzers."""

    kind: Literal["ir.strategic_payoff_table"] = "ir.strategic_payoff_table"
    media_type: Literal["application/json"] = "application/json"


class StrategicSCMRef(ArtifactRefModel):
    """Stable handle for persisted strategic SCMs consumed by strategic-response execution."""

    kind: Literal["ir.strategic_scm"] = "ir.strategic_scm"
    media_type: Literal["application/json"] = "application/json"


class StrategicResponseBundleRef(ArtifactRefModel):
    """Stable handle for persisted strategic-response bundles reviewed by governance."""

    kind: Literal["ir.strategic_response_bundle"] = "ir.strategic_response_bundle"
    media_type: Literal["application/json"] = "application/json"


class MeanFieldEquilibriumCertificateRef(ArtifactRefModel):
    """Stable handle for persisted mean-field equilibrium certificates."""

    kind: Literal["ir.mean_field_equilibrium_certificate"] = "ir.mean_field_equilibrium_certificate"
    media_type: Literal["application/json"] = "application/json"


class MeanFieldPerturbationSpecRef(ArtifactRefModel):
    """Stable handle for persisted SCM-to-MFG perturbation mappings."""

    kind: Literal["ir.mean_field_perturbation_spec"] = "ir.mean_field_perturbation_spec"
    media_type: Literal["application/json"] = "application/json"


class MeanFieldMacroSimulationConfigRef(ArtifactRefModel):
    """Stable handle for persisted MFG macro-simulation numerics configs."""

    kind: Literal["ir.mean_field_macro_simulation_config"] = "ir.mean_field_macro_simulation_config"
    media_type: Literal["application/json"] = "application/json"


class CausalReadinessBundleRef(ArtifactRefModel):
    """Reference a persisted ``CausalReadinessBundle`` consumed before execution."""

    kind: Literal["ir.causal_readiness_bundle"] = "ir.causal_readiness_bundle"
    media_type: Literal["application/json"] = "application/json"


class CausalExecutionBundleRef(ArtifactRefModel):
    """Reference a persisted ``CausalExecutionBundle`` produced by Scientist runners."""

    kind: Literal["ir.causal_execution_bundle"] = "ir.causal_execution_bundle"
    media_type: Literal["application/json"] = "application/json"


class FiniteStateAbstractionMapRef(ArtifactRefModel):
    """Stable handle for persisted abstraction maps consumed by reduced-state planners."""

    kind: Literal["ir.finite_state_abstraction_map"] = "ir.finite_state_abstraction_map"
    media_type: Literal["application/json"] = "application/json"


class AbstractionCertificateRef(ArtifactRefModel):
    """Stable handle for persisted abstraction certificates that justify reduced-state execution."""

    kind: Literal["ir.abstraction_certificate"] = "ir.abstraction_certificate"
    media_type: Literal["application/json"] = "application/json"


class NormativeArbitrationResultRef(ArtifactRefModel):
    """Stable handle for persisted normative-arbitration output consumed by decision synthesis."""

    kind: Literal["ir.normative_arbitration_result"] = "ir.normative_arbitration_result"
    media_type: Literal["application/json"] = "application/json"


class BacktestReportRef(ArtifactRefModel):
    """Stable handle for persisted backtest reports consumed by Scientist governance and readiness review."""

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


class InterventionCostManifoldRef(ArtifactRefModel):
    """Stable handle for a persisted ``InterventionCostManifold`` spec."""

    kind: Literal["ir.intervention_cost_manifold"] = "ir.intervention_cost_manifold"
    media_type: Literal["application/json"] = "application/json"


class OptimalRecourseInterventionQueryRef(ArtifactRefModel):
    """Stable handle for a persisted ``OptimalRecourseInterventionQuery``."""

    kind: Literal["ir.optimal_recourse_intervention_query"] = (
        "ir.optimal_recourse_intervention_query"
    )
    media_type: Literal["application/json"] = "application/json"


class RecourseProofBundleRef(ArtifactRefModel):
    """Stable handle for a persisted recourse-specific proof bundle."""

    kind: Literal["ir.recourse_proof_bundle"] = "ir.recourse_proof_bundle"
    media_type: Literal["application/json"] = "application/json"


class RecourseFeasibilityCertificateRef(ArtifactRefModel):
    """Stable handle for a persisted recourse feasibility certificate."""

    kind: Literal["ir.recourse_feasibility_certificate"] = "ir.recourse_feasibility_certificate"
    media_type: Literal["application/json"] = "application/json"


class OptimalRecourseInterventionBundleRef(ArtifactRefModel):
    """Stable handle for a persisted optimal-recourse planning result."""

    kind: Literal["ir.optimal_recourse_intervention_bundle"] = (
        "ir.optimal_recourse_intervention_bundle"
    )
    media_type: Literal["application/json"] = "application/json"


__all__ = [
    "AbstractionCertificateRef",
    "ABMAlignmentReportRef",
    "AlignmentReportRef",
    "BacktestReportRef",
    "BoundsBundleRef",
    "BoundsTighteningLogRef",
    "CompositionCertificateRef",
    "CompositionFailureCardBundleRef",
    "CausalAssumptionCardRef",
    "CausalDiscoveryReportRef",
    "CausalEffectReportRef",
    "CausalGraphModelRef",
    "DataReadinessReportRef",
    "SurveyQualityCertificateRef",
    "MicrosimCalibrationReportRef",
    "DependenceStructureRef",
    "MobilityReportRef",
    "LiteratureCausalPriorRef",
    "InterfaceMappingRef",
    "CausalSensitivityResultRef",
    "TransportabilityResultRef",
    "CausalCapabilityContractRef",
    "ContextAdaptiveParameterBundleRef",
    "ContinuousTimeQueryRef",
    "CrossGraphEvidenceProfileRef",
    "CausalBlockBridgeRef",
    "InteractionComplexRef",
    "InterferenceCertificateRef",
    "MAUPInvarianceCertificateRef",
    "SpatialHodgeDiagnosticsRef",
    "InterventionCertificateRef",
    "InterventionCostManifoldRef",
    "InterventionQueryRef",
    "OptimalRecourseInterventionBundleRef",
    "OptimalRecourseInterventionQueryRef",
    "RecourseFeasibilityCertificateRef",
    "RecourseProofBundleRef",
    "LatentBridgeHypothesisRef",
    "SCMFragmentRef",
    "StructuralCausalModelSpecRef",
    "CausalQueryResultRef",
    "TemporalInterventionTrajectoryRef",
    "TemporalIdentificationCertificateRef",
    "DynamicTreatmentRegimeRef",
    "EffectTrajectoryBundleRef",
    "FiniteStateAbstractionMapRef",
    "FrontierSketchRef",
    "TwinNetworkResultRef",
    "CausalModelEnsembleRef",
    "DistributionalBoundsBundleRef",
    "DistributionalDualCertificateRef",
    "DistributionalEffectBundleRef",
    "DistributionalProofArtifactRef",
    "DistributionalReportRef",
    "DPRobustnessCertificateRef",
    "EstimandASTRef",
    "EvidenceBundleRef",
    "KernelEstimatorSpecRef",
    "OperatorEffectBundleRef",
    "ArtifactRefModel",
    "HTEResultRef",
    "NegativeCertificateRef",
    "NormativeArbitrationResultRef",
    "PolicyRecommendationRef",
    "ProofBundleRef",
    "ProofComposabilityCertificateRef",
    "ProofWitnessIndexRef",
    "BridgePlausibilityReportRef",
    "LocalIndependenceWeightingCertificateRef",
    "PrivacyAwareTransportCertificateRef",
    "ProximalIdentificationCertificateRef",
    "RegimeShiftIdentificationCertificateRef",
    "RecoverabilityCertificateRef",
    "RoughPathInterventionCertificateRef",
    "JointDecisionCertificateRef",
    "CausalReadinessBundleRef",
    "CausalExecutionBundleRef",
    "MeanFieldEquilibriumCertificateRef",
    "MeanFieldMacroSimulationConfigRef",
    "MeanFieldPerturbationSpecRef",
    "StrategicPayoffTableRef",
    "StrategicResponseBundleRef",
    "StrategicSCMRef",
    "ForecastingUncertaintyBundleRef",
    "UncertaintyEnvelopeRef",
    "NCMSpecRef",
    "CounterfactualResultRef",
    "VariableAlignmentCertificateRef",
]
