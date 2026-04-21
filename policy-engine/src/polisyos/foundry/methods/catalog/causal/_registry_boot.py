"""Public causal registry boot module API."""
from __future__ import annotations

import importlib
import logging
import sys
from typing import Sequence

from polisyos.foundry.methods.catalog.causal.interference import (
    BipartiteInterferenceEstimator,
    NetworkAIPWEstimator,
    PartialInterferenceEstimator,
    SpatialInterferenceEstimator,
)
from polisyos.foundry.methods.catalog.causal.measurement_error import (
    MeasurementErrorEstimator,
)
from polisyos.foundry.methods.catalog.causal.missing_data import (
    AdministrativeMissingnessAssessment,
    FullLawIdentify,
    OrderedRecovery,
    RecoverabilityTest,
)
from polisyos.foundry.methods.catalog.causal.advanced_designs import (
    BunchingEstimator,
    DRLearnerEstimator,
    MarginalTreatmentEffectEstimator,
    RegressionKinkDesignEstimator,
    RLearnerEstimator,
    ShiftShareIVEstimator,
)
from polisyos.foundry.methods.catalog.causal.bounds import (
    BalkePearlBoundsEstimator,
    CopulaBoundsEstimator,
    GeneralBalkePearlBoundsEstimator,
    ImbensManskiBoundsEstimator,
    LeeBoundsEstimator,
    ManskiBoundsEstimator,
    OptimizationBasedBoundsEstimator,
)
from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod
from polisyos.foundry.methods.catalog.causal.sensitivity_bounds import (
    IntersectionBoundsEstimator,
    RosenbaumSharpBoundsEstimator,
    TanBoundsEstimator,
)
from polisyos.foundry.methods.catalog.causal.constraint_discovery import (
    FCIDiscovery,
    GESDiscovery,
    PCDiscovery,
)
from polisyos.foundry.methods.catalog.causal.dagma_discovery import DAGMADiscovery
from polisyos.foundry.methods.catalog.causal.discovery_pipeline import UnifiedCausalDiscovery
from polisyos.foundry.methods.catalog.causal.cross_fit import CrossFitOrchestrator
from polisyos.foundry.methods.catalog.causal.cross_fit_schedule import FoldAggregator
from polisyos.foundry.methods.catalog.causal.density_ratio import DensityRatioEstimator
from polisyos.foundry.methods.catalog.causal.distributional_bounds import (
    DistributionalBoundsEngineMethod,
)
from polisyos.foundry.methods.catalog.causal.eif_bounds import (
    SemiparametricEfficiencyBoundMethod,
)
from polisyos.foundry.methods.catalog.causal.diagnostics import (
    ParallelTrendsCheck,
    PolicyOverlapDiagnostic,
    PositivityDiagnostic,
    SupportMismatchDiagnostic,
)
from polisyos.foundry.methods.catalog.causal.independence_tests import (
    CategoricalConditionalIndependenceTest,
    HSICIndependenceTest,
    KCIConditionalTest,
    PartialCorrelationTest,
)
from polisyos.foundry.methods.catalog.causal.invariance_tests import (
    ICPInvarianceTest,
    InvariantDiscoveryFromRegimes,
    KSInvarianceTest,
)
from polisyos.foundry.methods.catalog.causal.did import (
    StandardDifferenceInDifferences,
    StaggeredDifferenceInDifferences,
)
from polisyos.foundry.methods.catalog.causal.gcm_fit import HybridSCMFit
from polisyos.foundry.methods.catalog.causal.gcm_query import GCMQuery
from polisyos.foundry.methods.catalog.causal.twin_network_query import TwinNetworkQuery
from polisyos.foundry.methods.catalog.causal.graph_reconciliation import ReconcileCausalGraph
from polisyos.foundry.methods.catalog.causal.literature_prior import BuildLiteraturePrior
from polisyos.foundry.methods.catalog.causal.actual_causality import (
    ActualCausalityEngine,
    HPActualCauseMethod,
)
from polisyos.foundry.methods.catalog.causal.mediation import (
    CausalMediationEstimator,
    ControlledDirectEffectEstimator,
    NaturalEffectEstimator,
)
from polisyos.foundry.methods.catalog.causal.causal_bcf import CausalBCF
from polisyos.foundry.methods.catalog.causal.forest_dr import ForestDRLearnerEstimator
from polisyos.foundry.methods.catalog.causal.path_specific import PathSpecificEffectEstimator
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.foundry.methods.catalog.causal.modern_did import (
    BorusyakJaravelSpiessEstimator,
    CallawaySantAnnaEstimator,
    DeChaisemartinDHaultfoeuilleEstimator,
    SunAbrahamEstimator,
)
from polisyos.foundry.methods.catalog.causal.parameter_transfer import ParameterTransfer
from polisyos.foundry.methods.catalog.causal.pcmci_discovery import PCMCIDiscovery
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.foundry.methods.catalog.causal.sensitivity_metrics import SensitivityMetrics
from polisyos.foundry.methods.catalog.causal.structural_time_series import StructuralTimeSeries
from polisyos.foundry.methods.catalog.causal.symbolic_identify import (
    SymbolicIdentify,
    SymbolicIdentifyV2,
)
from polisyos.foundry.methods.catalog.causal.synthetic_control import SyntheticControlMethod
from polisyos.foundry.methods.catalog.causal.transport_check import CheckTransportability
from polisyos.foundry.methods.catalog.causal.treatment_effects import (
    AIPWEstimator,
    CBPSEstimator,
    EntropyBalancingEstimator,
    IPWEstimator,
    PropensityScoreMatchingEstimator,
    TMLEEstimator,
)
from polisyos.foundry.methods.catalog.causal.continuous_treatment import (
    EntropyBalancingContinuousEstimator,
    GeneralizedPropensityScoreEstimator,
    KernelDoseResponseEstimator,
    ShiftInterventionEstimator,
)
from polisyos.foundry.methods.catalog.causal.stochastic_policies import (
    PolicyAIPWEstimator,
    PolicyPluginEstimator,
    PolicyTMLEEstimator,
)
from polisyos.foundry.methods.catalog.causal.multi_treatment import (
    MultiArmAIPWEstimator,
    MultinomialIPWEstimator,
)
from polisyos.foundry.methods.catalog.causal.superlearner import SuperLearnerNuisanceModel
from polisyos.foundry.methods.catalog.causal.nuisance_resolver import (
    MultinomialPropensityModel,
    ParametricConditionalDensity,
)
from polisyos.foundry.methods.catalog.causal.cross_fit import CrossFitContinuousOrchestrator
from polisyos.foundry.methods.catalog.causal.fairness import (
    CounterfactualFairnessEstimator,
    PathSpecificFairnessEstimator,
    TVFairnessDecomposer,
)
from polisyos.foundry.methods.catalog.causal.causal_fairness import CausalFairnessEngine
from polisyos.foundry.methods.catalog.causal.data_fusion import DataFusionEngine
from polisyos.foundry.methods.catalog.causal.optimal_design import CausalExperimentDesigner
from polisyos.foundry.methods.catalog.causal.operator_valued import (
    OperatorApplyProbeMethod,
    OperatorCMEKRREstimator,
    OperatorExportBasisMethod,
    OperatorKIVEstimator,
    OperatorProximalMinimaxEstimator,
    OperatorRLearnerEstimator,
    OperatorUnsupportedTargetMethod,
)
from polisyos.foundry.methods.catalog.causal.frontier import (
    DistributionalTreatmentEffectEstimator,
    NetworkHeterogeneousEffectEstimator,
    ProximalBridgeEstimator,
    SpatialProximalBridgeEstimator,
)
from polisyos.foundry.methods.catalog.causal.proximal_mediation import (
    ProximalMediationEstimator,
)
from polisyos.foundry.methods.catalog.causal.kernel_methods import (
    FitCMEMGivenX,
    FitCMEYGivenMX,
    FitCMEYGivenXZ,
    FitDensityRatio,
    FitKernelPropensity,
    FitKIVFirstStage,
    FitKIVSecondStage,
    KernelCMEPluginEstimator,
    KernelDRCMEEstimator,
    KernelEffectTest,
    KernelFrontdoorEstimator,
    KernelIVEstimator,
    KernelProximalMinimaxEstimator,
    KernelRefusal,
    KernelRegularizationDiagnostics,
    KernelSemanticsDiagnostics,
    KernelTransportEstimator,
    SolveKernelProximalBridge,
)

_logger = logging.getLogger(__name__)


def _optional_method_types(
    module_name: str,
    type_names: tuple[str, ...],
    *,
    optional_deps: tuple[str, ...],
) -> tuple[type, ...]:
    """Import optional method classes without breaking unrelated registry use."""
    package_name, _, _ = module_name.rpartition(".")
    package = sys.modules.get(package_name)
    if package is not None:
        preloaded: list[type] = []
        for type_name in type_names:
            candidate = getattr(package, type_name, None)
            if not isinstance(candidate, type):
                preloaded = []
                break
            preloaded.append(candidate)
        if preloaded:
            return tuple(preloaded)

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        missing = exc.name or ""
        if any(missing == dep or missing.startswith(f"{dep}.") for dep in optional_deps):
            _logger.info(
                "Skipping optional causal methods from %s because dependency %s is not installed.",
                module_name,
                missing,
            )
            return ()
        raise
    return tuple(getattr(module, type_name) for type_name in type_names)


def register_causal_methods() -> Sequence[type]:
    """Register causal methods."""
    methods: list[type] = [
        SyntheticControlMethod,
        ParallelTrendsCheck,
        PolicyOverlapDiagnostic,
        PositivityDiagnostic,
        SupportMismatchDiagnostic,
        # Independence tests (D1)
        CategoricalConditionalIndependenceTest,
        HSICIndependenceTest,
        KCIConditionalTest,
        PartialCorrelationTest,
        # Invariance tests (D2)
        KSInvarianceTest,
        ICPInvarianceTest,
        InvariantDiscoveryFromRegimes,
        StandardDifferenceInDifferences,
        StaggeredDifferenceInDifferences,
        RegressionDiscontinuity,
        StructuralTimeSeries,
        HybridSCMFit,
        GCMQuery,
        TwinNetworkQuery,
        ParameterTransfer,
        BuildLiteraturePrior,
        ReconcileCausalGraph,
        SensitivityMetrics,
        FoldAggregator,
        CheckTransportability,
        SymbolicIdentify,
        SymbolicIdentifyV2,
        PCMCIDiscovery,
        PCDiscovery,
        FCIDiscovery,
        GESDiscovery,
        DAGMADiscovery,
        UnifiedCausalDiscovery,
        # Pearl-Bareinboim causal engine
        CrossFitOrchestrator,
        DensityRatioEstimator,
        # Phase 1 additions: treatment effects
        AIPWEstimator,
        TMLEEstimator,
        IPWEstimator,
        PropensityScoreMatchingEstimator,
        EntropyBalancingEstimator,
        CBPSEstimator,
        CausalBCF,
        ForestDRLearnerEstimator,
        # Modern DiD
        CallawaySantAnnaEstimator,
        SunAbrahamEstimator,
        DeChaisemartinDHaultfoeuilleEstimator,
        BorusyakJaravelSpiessEstimator,
        # Bounds (partial identification)
        ManskiBoundsEstimator,
        LeeBoundsEstimator,
        BalkePearlBoundsEstimator,
        ImbensManskiBoundsEstimator,
        OptimizationBasedBoundsEstimator,
        BoundsEngineMethod,
        # Phase 7: Advanced partial identification
        GeneralBalkePearlBoundsEstimator,
        CopulaBoundsEstimator,
        TanBoundsEstimator,
        IntersectionBoundsEstimator,
        RosenbaumSharpBoundsEstimator,
        DistributionalBoundsEngineMethod,
        SemiparametricEfficiencyBoundMethod,
        # Mediation
        CausalMediationEstimator,
        ControlledDirectEffectEstimator,
        NaturalEffectEstimator,
        # Phase 2: Missing data theory (M-graphs)
        AdministrativeMissingnessAssessment,
        RecoverabilityTest,
        OrderedRecovery,
        FullLawIdentify,
        # Phase 1: Counterfactual foundations (L3)
        NCMEngineMethod,
        ActualCausalityEngine,
        HPActualCauseMethod,
        PathSpecificEffectEstimator,
        # Advanced designs
        RegressionKinkDesignEstimator,
        BunchingEstimator,
        MarginalTreatmentEffectEstimator,
        ShiftShareIVEstimator,
        DRLearnerEstimator,
        RLearnerEstimator,
        # Phase 4: Interference and network causal inference
        PartialInterferenceEstimator,
        NetworkAIPWEstimator,
        SpatialInterferenceEstimator,
        BipartiteInterferenceEstimator,
        # Phase 5: Extended identification theory
        MeasurementErrorEstimator,
        # Phase 6: Advanced estimation — continuous & multi-valued treatments
        CrossFitContinuousOrchestrator,
        GeneralizedPropensityScoreEstimator,
        KernelDoseResponseEstimator,
        ShiftInterventionEstimator,
        PolicyPluginEstimator,
        PolicyAIPWEstimator,
        PolicyTMLEEstimator,
        EntropyBalancingContinuousEstimator,
        MultinomialIPWEstimator,
        MultiArmAIPWEstimator,
        SuperLearnerNuisanceModel,
        ParametricConditionalDensity,
        MultinomialPropensityModel,
        # Phase 8: Causal Fairness
        TVFairnessDecomposer,
        PathSpecificFairnessEstimator,
        CounterfactualFairnessEstimator,
        CausalFairnessEngine,
        # Phase 9: Data Fusion and Optimal Experimental Design
        DataFusionEngine,
        CausalExperimentDesigner,
        # WS-9 frontier additions
        ProximalBridgeEstimator,
        SpatialProximalBridgeEstimator,
        ProximalMediationEstimator,
        DistributionalTreatmentEffectEstimator,
        NetworkHeterogeneousEffectEstimator,
        # Stage 14.2 operator-valued causal effects
        OperatorCMEKRREstimator,
        OperatorRLearnerEstimator,
        OperatorKIVEstimator,
        OperatorProximalMinimaxEstimator,
        OperatorApplyProbeMethod,
        OperatorExportBasisMethod,
        OperatorUnsupportedTargetMethod,
        # Stage 14.1 kernel causal operators
        KernelSemanticsDiagnostics,
        KernelRegularizationDiagnostics,
        KernelEffectTest,
        KernelRefusal,
        FitCMEYGivenXZ,
        FitCMEMGivenX,
        FitCMEYGivenMX,
        FitDensityRatio,
        FitKernelPropensity,
        FitKIVFirstStage,
        FitKIVSecondStage,
        SolveKernelProximalBridge,
        KernelCMEPluginEstimator,
        KernelFrontdoorEstimator,
        KernelTransportEstimator,
        KernelDRCMEEstimator,
        KernelIVEstimator,
        KernelProximalMinimaxEstimator,
    ]
    methods.extend(
        _optional_method_types(
            "polisyos.foundry.methods.catalog.causal.g_computation",
            ("ParametricGFormula", "ICEGFormula", "LTMLEEstimator"),
            optional_deps=(),
        )
    )
    methods.extend(
        _optional_method_types(
            "polisyos.foundry.methods.catalog.causal.g_estimation",
            ("StructuralNestedMeanModel",),
            optional_deps=(),
        )
    )
    methods.extend(
        _optional_method_types(
            "polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate",
            ("DoWhyIdentifyEstimateV1", "DoWhyIdentifyEstimate"),
            optional_deps=("dowhy", "cvxpy"),
        )
    )
    methods.extend(
        _optional_method_types(
            "polisyos.foundry.methods.catalog.causal.dowhy_refute",
            ("DoWhyRefute",),
            optional_deps=("dowhy", "cvxpy"),
        )
    )
    methods.extend(
        _optional_method_types(
            "polisyos.foundry.methods.catalog.causal.dtr",
            ("QLearningDTR", "ALearningDTR", "OutcomeWeightedLearning", "DoublyRobustDTR"),
            optional_deps=("sklearn",),
        )
    )
    methods.extend(
        _optional_method_types(
            "polisyos.foundry.methods.catalog.causal.causal_rl",
            ("OffPolicyEvaluator", "CausalBandit"),
            optional_deps=("sklearn",),
        )
    )
    try:
        from polisyos.foundry.methods.catalog.causal.cate import CausalForestEstimator
        from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning
        from polisyos.foundry.methods.catalog.causal.meta_learners import MetaLearnerEstimator
        from polisyos.foundry.methods.catalog.causal.policy_learning import OptimalPolicyLearner

        methods.extend(
            [
                CausalForestEstimator,
                DoubleMachineLearning,
                MetaLearnerEstimator,
                OptimalPolicyLearner,
            ]
        )
    except ModuleNotFoundError as exc:
        if exc.name not in {"econml", "shap"}:
            raise
    return tuple(methods)


__all__ = ["register_causal_methods"]
