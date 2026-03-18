from __future__ import annotations

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
from polisyos.foundry.methods.catalog.causal.density_ratio import DensityRatioEstimator
from polisyos.foundry.methods.catalog.causal.diagnostics import (
    ParallelTrendsCheck,
    PositivityDiagnostic,
    SupportMismatchDiagnostic,
)
from polisyos.foundry.methods.catalog.causal.independence_tests import (
    HSICIndependenceTest,
    KCIConditionalTest,
    PartialCorrelationTest,
)
from polisyos.foundry.methods.catalog.causal.invariance_tests import (
    ICPInvarianceTest,
    KSInvarianceTest,
)
from polisyos.foundry.methods.catalog.causal.did import (
    StandardDifferenceInDifferences,
    StaggeredDifferenceInDifferences,
)
from polisyos.foundry.methods.catalog.causal.dowhy_identify_estimate import (
    DoWhyIdentifyEstimate,
    DoWhyIdentifyEstimateV1,
)
from polisyos.foundry.methods.catalog.causal.dowhy_refute import DoWhyRefute
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
from polisyos.foundry.methods.catalog.causal.g_computation import (
    ICEGFormula,
    LTMLEEstimator,
    ParametricGFormula,
)
from polisyos.foundry.methods.catalog.causal.g_estimation import StructuralNestedMeanModel
from polisyos.foundry.methods.catalog.causal.dtr import (
    ALearningDTR,
    DoublyRobustDTR,
    OutcomeWeightedLearning,
    QLearningDTR,
)
from polisyos.foundry.methods.catalog.causal.causal_rl import (
    CausalBandit,
    OffPolicyEvaluator,
)
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
from polisyos.foundry.methods.catalog.causal.data_fusion import DataFusionEngine
from polisyos.foundry.methods.catalog.causal.optimal_design import CausalExperimentDesigner


def register_causal_methods() -> Sequence[type]:
    methods: list[type] = [
        SyntheticControlMethod,
        ParallelTrendsCheck,
        PositivityDiagnostic,
        SupportMismatchDiagnostic,
        # Independence tests (D1)
        HSICIndependenceTest,
        KCIConditionalTest,
        PartialCorrelationTest,
        # Invariance tests (D2)
        KSInvarianceTest,
        ICPInvarianceTest,
        StandardDifferenceInDifferences,
        StaggeredDifferenceInDifferences,
        RegressionDiscontinuity,
        StructuralTimeSeries,
        DoWhyIdentifyEstimateV1,
        DoWhyIdentifyEstimate,
        DoWhyRefute,
        HybridSCMFit,
        GCMQuery,
        TwinNetworkQuery,
        ParameterTransfer,
        BuildLiteraturePrior,
        ReconcileCausalGraph,
        SensitivityMetrics,
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
        # Mediation
        CausalMediationEstimator,
        ControlledDirectEffectEstimator,
        NaturalEffectEstimator,
        # Phase 2: Missing data theory (M-graphs)
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
        # Phase 3: Dynamic causal inference (g-computation, DTR, causal RL)
        ParametricGFormula,
        ICEGFormula,
        LTMLEEstimator,
        StructuralNestedMeanModel,
        QLearningDTR,
        ALearningDTR,
        OutcomeWeightedLearning,
        DoublyRobustDTR,
        OffPolicyEvaluator,
        CausalBandit,
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
        # Phase 9: Data Fusion and Optimal Experimental Design
        DataFusionEngine,
        CausalExperimentDesigner,
    ]
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
