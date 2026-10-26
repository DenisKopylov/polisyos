"""Lazy public facade for the owner-curated IR typed-reference family."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.ir.api import REGISTRY_FACADE_EXPORTS, lazy_dir, resolve_lazy_export

if TYPE_CHECKING:
    from polisyos.ir.registry.refs import (
        ABMAlignmentReportRef as ABMAlignmentReportRef,
    )
    from polisyos.ir.registry.refs import (
        ABMResultRef as ABMResultRef,
    )
    from polisyos.ir.registry.refs import (
        AbstractionCertificateRef as AbstractionCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        AlignmentReportRef as AlignmentReportRef,
    )
    from polisyos.ir.registry.refs import (
        ArtifactRefModel as ArtifactRefModel,
    )
    from polisyos.ir.registry.refs import (
        ATEInferenceBasisRef as ATEInferenceBasisRef,
    )
    from polisyos.ir.registry.refs import (
        BacktestReportRef as BacktestReportRef,
    )
    from polisyos.ir.registry.refs import (
        BoundsBundleRef as BoundsBundleRef,
    )
    from polisyos.ir.registry.refs import (
        BoundsTighteningLogRef as BoundsTighteningLogRef,
    )
    from polisyos.ir.registry.refs import (
        BridgePlausibilityReportRef as BridgePlausibilityReportRef,
    )
    from polisyos.ir.registry.refs import (
        CausalAssumptionCardRef as CausalAssumptionCardRef,
    )
    from polisyos.ir.registry.refs import (
        CausalBlockBridgeRef as CausalBlockBridgeRef,
    )
    from polisyos.ir.registry.refs import (
        CausalCapabilityContractRef as CausalCapabilityContractRef,
    )
    from polisyos.ir.registry.refs import (
        CausalDiscoveryReportRef as CausalDiscoveryReportRef,
    )
    from polisyos.ir.registry.refs import (
        CausalEffectReportRef as CausalEffectReportRef,
    )
    from polisyos.ir.registry.refs import (
        CausalExecutionBundleRef as CausalExecutionBundleRef,
    )
    from polisyos.ir.registry.refs import (
        CausalGraphModelRef as CausalGraphModelRef,
    )
    from polisyos.ir.registry.refs import (
        CausalModelEnsembleRef as CausalModelEnsembleRef,
    )
    from polisyos.ir.registry.refs import (
        CausalQueryResultRef as CausalQueryResultRef,
    )
    from polisyos.ir.registry.refs import (
        CausalReadinessBundleRef as CausalReadinessBundleRef,
    )
    from polisyos.ir.registry.refs import (
        CausalSensitivityResultRef as CausalSensitivityResultRef,
    )
    from polisyos.ir.registry.refs import (
        ChannelDecompositionArtifactRef as ChannelDecompositionArtifactRef,
    )
    from polisyos.ir.registry.refs import (
        CompositionCertificateRef as CompositionCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        CompositionFailureCardBundleRef as CompositionFailureCardBundleRef,
    )
    from polisyos.ir.registry.refs import (
        ContextAdaptiveParameterBundleRef as ContextAdaptiveParameterBundleRef,
    )
    from polisyos.ir.registry.refs import (
        ContinuousTimeQueryRef as ContinuousTimeQueryRef,
    )
    from polisyos.ir.registry.refs import (
        CounterfactualResultRef as CounterfactualResultRef,
    )
    from polisyos.ir.registry.refs import (
        CrossGraphEvidenceProfileRef as CrossGraphEvidenceProfileRef,
    )
    from polisyos.ir.registry.refs import (
        DataReadinessReportRef as DataReadinessReportRef,
    )
    from polisyos.ir.registry.refs import (
        DependenceStructureRef as DependenceStructureRef,
    )
    from polisyos.ir.registry.refs import (
        DistributionalBoundsBundleRef as DistributionalBoundsBundleRef,
    )
    from polisyos.ir.registry.refs import (
        DistributionalDualCertificateRef as DistributionalDualCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        DistributionalEffectBundleRef as DistributionalEffectBundleRef,
    )
    from polisyos.ir.registry.refs import (
        DistributionalProofArtifactRef as DistributionalProofArtifactRef,
    )
    from polisyos.ir.registry.refs import (
        DistributionalReportRef as DistributionalReportRef,
    )
    from polisyos.ir.registry.refs import (
        DPRobustnessCertificateRef as DPRobustnessCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        DriftReadinessRef as DriftReadinessRef,
    )
    from polisyos.ir.registry.refs import (
        DualCertificateRef as DualCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        DynamicMicrosimValidationReportRef as DynamicMicrosimValidationReportRef,
    )
    from polisyos.ir.registry.refs import (
        DynamicTreatmentRegimeRef as DynamicTreatmentRegimeRef,
    )
    from polisyos.ir.registry.refs import (
        EffectTrajectoryBundleRef as EffectTrajectoryBundleRef,
    )
    from polisyos.ir.registry.refs import (
        EndogenousGroupInequalityDecompositionRef as EndogenousGroupInequalityDecompositionRef,
    )
    from polisyos.ir.registry.refs import (
        EstimandASTRef as EstimandASTRef,
    )
    from polisyos.ir.registry.refs import (
        EvidenceBundleRef as EvidenceBundleRef,
    )
    from polisyos.ir.registry.refs import (
        ExplanationBundleRef as ExplanationBundleRef,
    )
    from polisyos.ir.registry.refs import (
        FairnessAuditReportRef as FairnessAuditReportRef,
    )
    from polisyos.ir.registry.refs import (
        FiniteStateAbstractionMapRef as FiniteStateAbstractionMapRef,
    )
    from polisyos.ir.registry.refs import (
        FiscalFeedbackLinkRef as FiscalFeedbackLinkRef,
    )
    from polisyos.ir.registry.refs import (
        ForecastingUncertaintyBundleRef as ForecastingUncertaintyBundleRef,
    )
    from polisyos.ir.registry.refs import (
        ForecastInterventionCertificateRef as ForecastInterventionCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        ForecastInterventionQueryRef as ForecastInterventionQueryRef,
    )
    from polisyos.ir.registry.refs import (
        FrontierSketchRef as FrontierSketchRef,
    )
    from polisyos.ir.registry.refs import (
        GEUncertaintyBundleRef as GEUncertaintyBundleRef,
    )
    from polisyos.ir.registry.refs import (
        HTEInputSourceRef as HTEInputSourceRef,
    )
    from polisyos.ir.registry.refs import (
        HTEOutcomeRef as HTEOutcomeRef,
    )
    from polisyos.ir.registry.refs import (
        HTEPhysicalSourceMaterializationBindingRef as HTEPhysicalSourceMaterializationBindingRef,
    )
    from polisyos.ir.registry.refs import (
        HTEPointResultRef as HTEPointResultRef,
    )
    from polisyos.ir.registry.refs import (
        HTERefusalDiagnosticRef as HTERefusalDiagnosticRef,
    )
    from polisyos.ir.registry.refs import (
        HTEResourcePolicyRef as HTEResourcePolicyRef,
    )
    from polisyos.ir.registry.refs import (
        HTEResultEvidenceRef as HTEResultEvidenceRef,
    )
    from polisyos.ir.registry.refs import (
        HTEResultRef as HTEResultRef,
    )
    from polisyos.ir.registry.refs import (
        IncentiveCompatibilityCertificateRef as IncentiveCompatibilityCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        InteractionComplexRef as InteractionComplexRef,
    )
    from polisyos.ir.registry.refs import (
        InterfaceMappingRef as InterfaceMappingRef,
    )
    from polisyos.ir.registry.refs import (
        InterferenceCertificateRef as InterferenceCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        InterventionCertificateRef as InterventionCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        InterventionCostManifoldRef as InterventionCostManifoldRef,
    )
    from polisyos.ir.registry.refs import (
        InterventionQueryRef as InterventionQueryRef,
    )
    from polisyos.ir.registry.refs import (
        JointDecisionCertificateRef as JointDecisionCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        JudgeVerdictRef as JudgeVerdictRef,
    )
    from polisyos.ir.registry.refs import (
        KernelEstimatorSpecRef as KernelEstimatorSpecRef,
    )
    from polisyos.ir.registry.refs import (
        LatentBridgeHypothesisRef as LatentBridgeHypothesisRef,
    )
    from polisyos.ir.registry.refs import (
        LiteratureCausalPriorRef as LiteratureCausalPriorRef,
    )
    from polisyos.ir.registry.refs import (
        LocalIndependenceWeightingCertificateRef as LocalIndependenceWeightingCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        MAUPInvarianceCertificateRef as MAUPInvarianceCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        MeanFieldEquilibriumCertificateRef as MeanFieldEquilibriumCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        MeanFieldMacroSimulationConfigRef as MeanFieldMacroSimulationConfigRef,
    )
    from polisyos.ir.registry.refs import (
        MeanFieldPerturbationSpecRef as MeanFieldPerturbationSpecRef,
    )
    from polisyos.ir.registry.refs import (
        MechanismFamilySpecRef as MechanismFamilySpecRef,
    )
    from polisyos.ir.registry.refs import (
        MechanismWelfareLossBoundRef as MechanismWelfareLossBoundRef,
    )
    from polisyos.ir.registry.refs import (
        MethodExecutionEvidenceRef as MethodExecutionEvidenceRef,
    )
    from polisyos.ir.registry.refs import (
        MethodResultEvidenceRef as MethodResultEvidenceRef,
    )
    from polisyos.ir.registry.refs import (
        MetricValidationReportRef as MetricValidationReportRef,
    )
    from polisyos.ir.registry.refs import (
        MicrosimCalibrationReportRef as MicrosimCalibrationReportRef,
    )
    from polisyos.ir.registry.refs import (
        MobilityReportRef as MobilityReportRef,
    )
    from polisyos.ir.registry.refs import (
        NCMSpecRef as NCMSpecRef,
    )
    from polisyos.ir.registry.refs import (
        NegativeCertificateRef as NegativeCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        NormativeArbitrationResultRef as NormativeArbitrationResultRef,
    )
    from polisyos.ir.registry.refs import (
        OperatorEffectBundleRef as OperatorEffectBundleRef,
    )
    from polisyos.ir.registry.refs import (
        OptimalRecourseInterventionBundleRef as OptimalRecourseInterventionBundleRef,
    )
    from polisyos.ir.registry.refs import (
        OptimalRecourseInterventionQueryRef as OptimalRecourseInterventionQueryRef,
    )
    from polisyos.ir.registry.refs import (
        OptimizationAmbiguityCertificateRef as OptimizationAmbiguityCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        OrdinalPovertyReportRef as OrdinalPovertyReportRef,
    )
    from polisyos.ir.registry.refs import (
        OwnedAttemptAnchorRef as OwnedAttemptAnchorRef,
    )
    from polisyos.ir.registry.refs import (
        PolicyRecommendationRef as PolicyRecommendationRef,
    )
    from polisyos.ir.registry.refs import (
        PrivacyAwareTransportCertificateRef as PrivacyAwareTransportCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        ProofBundleRef as ProofBundleRef,
    )
    from polisyos.ir.registry.refs import (
        ProofComposabilityCertificateRef as ProofComposabilityCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        ProofWitnessIndexRef as ProofWitnessIndexRef,
    )
    from polisyos.ir.registry.refs import (
        ProximalIdentificationCertificateRef as ProximalIdentificationCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        RecourseFeasibilityCertificateRef as RecourseFeasibilityCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        RecourseProofBundleRef as RecourseProofBundleRef,
    )
    from polisyos.ir.registry.refs import (
        RecoverabilityCertificateRef as RecoverabilityCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        RegimeShiftForecastBundleRef as RegimeShiftForecastBundleRef,
    )
    from polisyos.ir.registry.refs import (
        RegimeShiftIdentificationCertificateRef as RegimeShiftIdentificationCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        RoughPathInterventionCertificateRef as RoughPathInterventionCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        SCMFragmentRef as SCMFragmentRef,
    )
    from polisyos.ir.registry.refs import (
        SearchUncertaintyTaskBindingRef as SearchUncertaintyTaskBindingRef,
    )
    from polisyos.ir.registry.refs import (
        SensitivityAnalysisBundleRef as SensitivityAnalysisBundleRef,
    )
    from polisyos.ir.registry.refs import (
        ShiftDiagnosticReportRef as ShiftDiagnosticReportRef,
    )
    from polisyos.ir.registry.refs import (
        SimulationCalibrationReceiptRef as SimulationCalibrationReceiptRef,
    )
    from polisyos.ir.registry.refs import (
        SimulationProofBridgeRef as SimulationProofBridgeRef,
    )
    from polisyos.ir.registry.refs import (
        SocialWeightManifestRef as SocialWeightManifestRef,
    )
    from polisyos.ir.registry.refs import (
        SpaceTimeCausalCertificateRef as SpaceTimeCausalCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        SpatialHodgeDiagnosticsRef as SpatialHodgeDiagnosticsRef,
    )
    from polisyos.ir.registry.refs import (
        StrategicPayoffTableRef as StrategicPayoffTableRef,
    )
    from polisyos.ir.registry.refs import (
        StrategicResponseBundleRef as StrategicResponseBundleRef,
    )
    from polisyos.ir.registry.refs import (
        StrategicSCMRef as StrategicSCMRef,
    )
    from polisyos.ir.registry.refs import (
        StructuralCausalModelSpecRef as StructuralCausalModelSpecRef,
    )
    from polisyos.ir.registry.refs import (
        SurveyQualityCertificateRef as SurveyQualityCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        TemporalGraphCausalCertificateRef as TemporalGraphCausalCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        TemporalIdentificationCertificateRef as TemporalIdentificationCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        TemporalInterventionTrajectoryRef as TemporalInterventionTrajectoryRef,
    )
    from polisyos.ir.registry.refs import (
        TransportabilityResultRef as TransportabilityResultRef,
    )
    from polisyos.ir.registry.refs import (
        TwinNetworkResultRef as TwinNetworkResultRef,
    )
    from polisyos.ir.registry.refs import (
        UncertaintyEnvelopeRef as UncertaintyEnvelopeRef,
    )
    from polisyos.ir.registry.refs import (
        ValidationReportRef as ValidationReportRef,
    )
    from polisyos.ir.registry.refs import (
        VariableAlignmentCertificateRef as VariableAlignmentCertificateRef,
    )
    from polisyos.ir.registry.refs import (
        WelfareBundleRef as WelfareBundleRef,
    )
    from polisyos.ir.registry.refs import (
        WelfareSampleBundleRef as WelfareSampleBundleRef,
    )

__all__ = sorted(REGISTRY_FACADE_EXPORTS)


def __getattr__(name: str) -> Any:  # noqa: ANN401
    return resolve_lazy_export(name, namespace=globals(), exports=REGISTRY_FACADE_EXPORTS)


def __dir__() -> list[str]:
    return lazy_dir(globals(), REGISTRY_FACADE_EXPORTS)
