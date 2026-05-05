from __future__ import annotations

from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
from polisyos.core.contracts.backtest import BacktestReportRef as CoreBacktestReportRef
from polisyos.core.contracts.causal import (
    CausalDiscoveryReportRef as CoreCausalDiscoveryReportRef,
)
from polisyos.core.contracts.causal import CausalEffectReportRef as CoreCausalEffectReportRef
from polisyos.core.contracts.causal import CausalGraphModelRef as CoreCausalGraphModelRef
from polisyos.core.contracts.causal import (
    CausalModelEnsembleRef as CoreCausalModelEnsembleRef,
)
from polisyos.core.contracts.causal import CausalQueryResultRef as CoreCausalQueryResultRef
from polisyos.core.contracts.causal import (
    InterventionCostManifoldRef as CoreInterventionCostManifoldRef,
)
from polisyos.core.contracts.causal import (
    LiteratureCausalPriorRef as CoreLiteratureCausalPriorRef,
)
from polisyos.core.contracts.causal import (
    MeanFieldEquilibriumCertificateRef as CoreMeanFieldEquilibriumCertificateRef,
)
from polisyos.core.contracts.causal import (
    MeanFieldMacroSimulationConfigRef as CoreMeanFieldMacroSimulationConfigRef,
)
from polisyos.core.contracts.causal import (
    MeanFieldPerturbationSpecRef as CoreMeanFieldPerturbationSpecRef,
)
from polisyos.core.contracts.causal import (
    OperatorEffectBundleRef as CoreOperatorEffectBundleRef,
)
from polisyos.core.contracts.causal import (
    OptimalRecourseInterventionBundleRef as CoreOptimalRecourseInterventionBundleRef,
)
from polisyos.core.contracts.causal import (
    OptimalRecourseInterventionQueryRef as CoreOptimalRecourseInterventionQueryRef,
)
from polisyos.core.contracts.causal import (
    PrivacyAwareTransportCertificateRef as CorePrivacyAwareTransportCertificateRef,
)
from polisyos.core.contracts.causal import (
    RecourseFeasibilityCertificateRef as CoreRecourseFeasibilityCertificateRef,
)
from polisyos.core.contracts.causal import RecourseProofBundleRef as CoreRecourseProofBundleRef
from polisyos.core.contracts.causal import (
    RoughPathInterventionCertificateRef as CoreRoughPathInterventionCertificateRef,
)
from polisyos.core.contracts.causal import (
    StructuralCausalModelSpecRef as CoreStructuralCausalModelSpecRef,
)
from polisyos.core.contracts.distributional import (
    CausalAssumptionCardRef as CoreCausalAssumptionCardRef,
)
from polisyos.core.contracts.distributional import (
    DistributionalBoundsBundleRef as CoreDistributionalBoundsBundleRef,
)
from polisyos.core.contracts.distributional import (
    DistributionalDualCertificateRef as CoreDistributionalDualCertificateRef,
)
from polisyos.core.contracts.distributional import (
    DistributionalEffectBundleRef as CoreDistributionalEffectBundleRef,
)
from polisyos.core.contracts.distributional import (
    DistributionalProofArtifactRef as CoreDistributionalProofArtifactRef,
)
from polisyos.core.contracts.distributional import (
    DistributionalReportRef as CoreDistributionalReportRef,
)
from polisyos.core.contracts.distributional import (
    OrdinalPovertyReportRef as CoreOrdinalPovertyReportRef,
)
from polisyos.core.contracts.hte import (
    HTEResultRef as CoreHTEResultRef,
)
from polisyos.core.contracts.hte import (
    PolicyRecommendationRef as CorePolicyRecommendationRef,
)
from polisyos.core.contracts.normative_arbitration import (
    NormativeArbitrationResultRef as CoreNormativeArbitrationResultRef,
)
from polisyos.core.contracts.uncertainty import (
    RegimeShiftForecastBundleRef as CoreRegimeShiftForecastBundleRef,
)
from polisyos.core.contracts.uncertainty import (
    UncertaintyEnvelopeRef as CoreUncertaintyEnvelopeRef,
)
from polisyos.ir.refs import (
    BacktestReportRef as IrBacktestReportRef,
)
from polisyos.ir.refs import (
    CausalAssumptionCardRef as IrCausalAssumptionCardRef,
)
from polisyos.ir.refs import (
    CausalDiscoveryReportRef as IrCausalDiscoveryReportRef,
)
from polisyos.ir.refs import (
    CausalEffectReportRef as IrCausalEffectReportRef,
)
from polisyos.ir.refs import (
    CausalGraphModelRef as IrCausalGraphModelRef,
)
from polisyos.ir.refs import (
    CausalModelEnsembleRef as IrCausalModelEnsembleRef,
)
from polisyos.ir.refs import (
    CausalQueryResultRef as IrCausalQueryResultRef,
)
from polisyos.ir.refs import (
    DistributionalBoundsBundleRef as IrDistributionalBoundsBundleRef,
)
from polisyos.ir.refs import (
    DistributionalDualCertificateRef as IrDistributionalDualCertificateRef,
)
from polisyos.ir.refs import (
    DistributionalEffectBundleRef as IrDistributionalEffectBundleRef,
)
from polisyos.ir.refs import (
    DistributionalProofArtifactRef as IrDistributionalProofArtifactRef,
)
from polisyos.ir.refs import (
    DistributionalReportRef as IrDistributionalReportRef,
)
from polisyos.ir.refs import (
    HTEResultRef as IrHTEResultRef,
)
from polisyos.ir.refs import (
    InterventionCostManifoldRef as IrInterventionCostManifoldRef,
)
from polisyos.ir.refs import (
    LiteratureCausalPriorRef as IrLiteratureCausalPriorRef,
)
from polisyos.ir.refs import (
    MeanFieldEquilibriumCertificateRef as IrMeanFieldEquilibriumCertificateRef,
)
from polisyos.ir.refs import (
    MeanFieldMacroSimulationConfigRef as IrMeanFieldMacroSimulationConfigRef,
)
from polisyos.ir.refs import (
    MeanFieldPerturbationSpecRef as IrMeanFieldPerturbationSpecRef,
)
from polisyos.ir.refs import (
    NormativeArbitrationResultRef as IrNormativeArbitrationResultRef,
)
from polisyos.ir.refs import (
    OperatorEffectBundleRef as IrOperatorEffectBundleRef,
)
from polisyos.ir.refs import (
    OptimalRecourseInterventionBundleRef as IrOptimalRecourseInterventionBundleRef,
)
from polisyos.ir.refs import (
    OptimalRecourseInterventionQueryRef as IrOptimalRecourseInterventionQueryRef,
)
from polisyos.ir.refs import (
    OrdinalPovertyReportRef as IrOrdinalPovertyReportRef,
)
from polisyos.ir.refs import (
    PolicyRecommendationRef as IrPolicyRecommendationRef,
)
from polisyos.ir.refs import (
    PrivacyAwareTransportCertificateRef as IrPrivacyAwareTransportCertificateRef,
)
from polisyos.ir.refs import (
    RecourseFeasibilityCertificateRef as IrRecourseFeasibilityCertificateRef,
)
from polisyos.ir.refs import RecourseProofBundleRef as IrRecourseProofBundleRef
from polisyos.ir.refs import (
    RegimeShiftForecastBundleRef as IrRegimeShiftForecastBundleRef,
)
from polisyos.ir.refs import (
    RoughPathInterventionCertificateRef as IrRoughPathInterventionCertificateRef,
)
from polisyos.ir.refs import (
    StructuralCausalModelSpecRef as IrStructuralCausalModelSpecRef,
)
from polisyos.ir.refs import (
    UncertaintyEnvelopeRef as IrUncertaintyEnvelopeRef,
)

_ID = "sha256:" + "a" * 64


def test_core_contract_facades_reexport_ir_ref_types() -> None:
    assert CoreBacktestReportRef is IrBacktestReportRef
    assert CoreCausalModelEnsembleRef is IrCausalModelEnsembleRef
    assert CoreCausalDiscoveryReportRef is IrCausalDiscoveryReportRef
    assert CoreCausalEffectReportRef is IrCausalEffectReportRef
    assert CoreCausalGraphModelRef is IrCausalGraphModelRef
    assert CoreCausalQueryResultRef is IrCausalQueryResultRef
    assert CoreInterventionCostManifoldRef is IrInterventionCostManifoldRef
    assert CoreLiteratureCausalPriorRef is IrLiteratureCausalPriorRef
    assert CoreMeanFieldEquilibriumCertificateRef is IrMeanFieldEquilibriumCertificateRef
    assert CoreMeanFieldMacroSimulationConfigRef is IrMeanFieldMacroSimulationConfigRef
    assert CoreMeanFieldPerturbationSpecRef is IrMeanFieldPerturbationSpecRef
    assert CoreOperatorEffectBundleRef is IrOperatorEffectBundleRef
    assert CoreOptimalRecourseInterventionBundleRef is IrOptimalRecourseInterventionBundleRef
    assert CoreOptimalRecourseInterventionQueryRef is IrOptimalRecourseInterventionQueryRef
    assert CorePrivacyAwareTransportCertificateRef is IrPrivacyAwareTransportCertificateRef
    assert CoreRecourseFeasibilityCertificateRef is IrRecourseFeasibilityCertificateRef
    assert CoreRecourseProofBundleRef is IrRecourseProofBundleRef
    assert CoreRoughPathInterventionCertificateRef is IrRoughPathInterventionCertificateRef
    assert CoreStructuralCausalModelSpecRef is IrStructuralCausalModelSpecRef
    assert CoreCausalAssumptionCardRef is IrCausalAssumptionCardRef
    assert CoreDistributionalBoundsBundleRef is IrDistributionalBoundsBundleRef
    assert CoreDistributionalDualCertificateRef is IrDistributionalDualCertificateRef
    assert CoreDistributionalEffectBundleRef is IrDistributionalEffectBundleRef
    assert CoreOrdinalPovertyReportRef is IrOrdinalPovertyReportRef
    assert CoreDistributionalProofArtifactRef is IrDistributionalProofArtifactRef
    assert CoreDistributionalReportRef is IrDistributionalReportRef
    assert CoreHTEResultRef is IrHTEResultRef
    assert CoreNormativeArbitrationResultRef is IrNormativeArbitrationResultRef
    assert CorePolicyRecommendationRef is IrPolicyRecommendationRef
    assert CoreUncertaintyEnvelopeRef is IrUncertaintyEnvelopeRef
    assert CoreRegimeShiftForecastBundleRef is IrRegimeShiftForecastBundleRef


def test_core_contract_facades_accept_core_artifact_id_values() -> None:
    core_id = CoreArtifactID.model_validate(_ID)

    refs = [
        CoreBacktestReportRef(artifact_id=core_id),
        CoreCausalModelEnsembleRef(artifact_id=core_id),
        CoreCausalDiscoveryReportRef(artifact_id=core_id),
        CoreCausalEffectReportRef(artifact_id=core_id),
        CoreCausalGraphModelRef(artifact_id=core_id),
        CoreCausalQueryResultRef(artifact_id=core_id),
        CoreInterventionCostManifoldRef(artifact_id=core_id),
        CoreLiteratureCausalPriorRef(artifact_id=core_id),
        CoreMeanFieldEquilibriumCertificateRef(artifact_id=core_id),
        CoreMeanFieldMacroSimulationConfigRef(artifact_id=core_id),
        CoreMeanFieldPerturbationSpecRef(artifact_id=core_id),
        CoreOperatorEffectBundleRef(artifact_id=core_id),
        CoreOptimalRecourseInterventionBundleRef(artifact_id=core_id),
        CoreOptimalRecourseInterventionQueryRef(artifact_id=core_id),
        CorePrivacyAwareTransportCertificateRef(artifact_id=core_id),
        CoreRecourseFeasibilityCertificateRef(artifact_id=core_id),
        CoreRecourseProofBundleRef(artifact_id=core_id),
        CoreRoughPathInterventionCertificateRef(artifact_id=core_id),
        CoreStructuralCausalModelSpecRef(artifact_id=core_id),
        CoreCausalAssumptionCardRef(artifact_id=core_id),
        CoreDistributionalBoundsBundleRef(artifact_id=core_id),
        CoreDistributionalDualCertificateRef(artifact_id=core_id),
        CoreDistributionalEffectBundleRef(artifact_id=core_id),
        CoreOrdinalPovertyReportRef(artifact_id=core_id),
        CoreDistributionalProofArtifactRef(artifact_id=core_id),
        CoreDistributionalReportRef(artifact_id=core_id),
        CoreHTEResultRef(artifact_id=core_id),
        CoreNormativeArbitrationResultRef(artifact_id=core_id),
        CorePolicyRecommendationRef(artifact_id=core_id),
        CoreUncertaintyEnvelopeRef(artifact_id=core_id),
        CoreRegimeShiftForecastBundleRef(artifact_id=core_id),
    ]

    for ref in refs:
        assert str(ref.artifact_id) == _ID
        assert ref.artifact_id.hex == "a" * 64
