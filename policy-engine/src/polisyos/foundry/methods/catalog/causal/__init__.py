"""Expose causal estimators, diagnostics, and discovery methods under the `causal.*` namespaces."""
from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    DiagnosticTest,
    EstimationStatus,
    PlaceboResult,
)

from ._registry_boot import register_causal_methods
from .advanced_designs import (
    BunchingEstimator,
    DRLearnerEstimator,
    MarginalTreatmentEffectEstimator,
    RegressionKinkDesignEstimator,
    RLearnerEstimator,
    ShiftShareIVEstimator,
)
from .bounds import (
    BalkePearlBoundsEstimator,
    ImbensManskiBoundsEstimator,
    LeeBoundsEstimator,
    ManskiBoundsEstimator,
    OptimizationBasedBoundsEstimator,
)
from .bounds_engine import BoundsEngineMethod
from .lp_bounds import auto_bounds
from .cate import CausalForestEstimator
from .constraint_discovery import FCIDiscovery, GESDiscovery, PCDiscovery
from .dagma_discovery import DAGMADiscovery
from .discovery_pipeline import UnifiedCausalDiscovery
from .diagnostics import ParallelTrendsCheck
from .did import (
    StandardDifferenceInDifferences,
    StaggeredDifferenceInDifferences,
)
from .dtr import estimate_dtr_trajectory
from .dml import DoubleMachineLearning
from .dowhy_identify_estimate import DoWhyIdentifyEstimate, DoWhyIdentifyEstimateV1
from .dowhy_refute import DoWhyRefute
from .g_computation import estimate_g_computation_trajectory
from .g_estimation import StructuralNestedMeanModel
from .gcm_fit import HybridSCMFit
from .gcm_query import GCMQuery
from .twin_network_query import TwinNetworkQuery
from .graph_reconciliation import ReconcileCausalGraph, compute_reconciliation_diagnostics
from .query_preservation import (
    check_query_preservation,
    check_query_preservation_batch,
    evaluate_query_preservation,
    evaluate_query_preservation_batch,
    update_query_preservation_cache,
)
from .literature_prior import BuildLiteraturePrior
from .mediation import CausalMediationEstimator, ControlledDirectEffectEstimator
from .causal_bcf import CausalBCF
from .forest_dr import ForestDRLearnerEstimator
from .meta_learners import MetaLearnerEstimator
from .modern_did import (
    BorusyakJaravelSpiessEstimator,
    CallawaySantAnnaEstimator,
    DeChaisemartinDHaultfoeuilleEstimator,
    SunAbrahamEstimator,
)
from .parameter_transfer import ParameterTransfer
from .pcmci_discovery import PCMCIDiscovery
from .policy_learning import OptimalPolicyLearner
from .strategic import (
    StrategicSolveResult,
    build_strategic_response_bundle,
    evaluate_strategic_hook,
    solve_strategic_response,
    strategic_result_summary,
)
from .protocols import (
    CausalEstimator,
    GraphCausalData,
    GraphCausalDataV1,
    GraphReconciliationData,
    HTEObservationalData,
    LiteraturePriorBuildData,
    LLMStructuralHint,
    PanelObservationalData,
    ParameterTransferData,
    RDDObservationalData,
    SCMFitData,
    SCMQueryData,
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
)
from .rdd import RegressionDiscontinuity
from .sensitivity_metrics import SensitivityMetrics
from .structural_time_series import (
    StructuralTimeSeries,
    TemporalTrajectoryResult,
    build_solver_diagnostics,
    estimate_discretization_error,
    estimate_structural_time_series_trajectory,
    solve_temporal_effect_path,
)
from .symbolic_identify import SymbolicIdentify
from .synthetic_control import SyntheticControlMethod
from .temporal_estimand_compiler import (
    TemporalBackendTarget,
    TemporalComparatorSemantics,
    TemporalCompileError,
    TemporalDataContract,
    TemporalExecutionPlan,
    TemporalFallbackMode,
    compile_temporal_estimand,
)
from .causal_engine import CausalEngine
from .query_validator import CausalQueryValidator
from .transport_check import CheckTransportability
from .transport_bounds import transport_bounds
from .treatment_effects import (
    AIPWEstimator,
    CBPSEstimator,
    EntropyBalancingEstimator,
    IPWEstimator,
    PropensityScoreMatchingEstimator,
    TMLEEstimator,
)
from .interference import (
    BipartiteInterferenceEstimator,
    NetworkAIPWEstimator,
    PartialInterferenceEstimator,
    SpatialInterferenceEstimator,
)
from .protocols import NetworkCausalData
from .protocols import (
    ContinuousTreatmentData,
    DoseResponseResult,
    MultiTreatmentData,
    MultiTreatmentResult,
)
from .continuous_treatment import (
    EntropyBalancingContinuousEstimator,
    GeneralizedPropensityScoreEstimator,
    KernelDoseResponseEstimator,
    ShiftInterventionEstimator,
)
from .multi_treatment import (
    MultiArmAIPWEstimator,
    MultinomialIPWEstimator,
    pairwise_contrasts,
)
from .superlearner import FittedSuperLearner, SuperLearnerNuisanceModel
from .nuisance_resolver import MultinomialPropensityModel, ParametricConditionalDensity
from .cross_fit import CrossFitContinuousOrchestrator
from .fairness import (
    CounterfactualFairnessEstimator,
    PathSpecificFairnessEstimator,
    TVFairnessDecomposer,
)
from .causal_fairness import (
    CausalFairnessEngine,
    StandardFairnessModel,
    fairness_bounds,
    identify_fairness_effects,
    tv_decomposition,
)
from .ctf_calculus import rewrite_ctf_estimand
from .ctf_transport import ctf_transportability, ctf_transport_bounds
from .cyclic_id import cyclic_id_algorithm
from .sigma_calculus import sigma_identify, sigma_z_identify
from .protocols import FairnessObservationalData


def ensure_causal_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Register all built-in causal methods into `registry` or the global singleton."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_causal_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "CausalEffectReport",
    "CausalMethod",
    "DiagnosticTest",
    "EstimationStatus",
    "PlaceboResult",
    "CausalEstimator",
    "PanelObservationalData",
    "HTEObservationalData",
    "GraphCausalData",
    "GraphCausalDataV1",
    "LiteraturePriorBuildData",
    "GraphReconciliationData",
    "LLMStructuralHint",
    "SCMFitData",
    "SCMQueryData",
    "ParameterTransferData",
    "RDDObservationalData",
    "TimeSeriesCausalData",
    "TabularCausalDiscoveryData",
    "SyntheticControlMethod",
    "ParallelTrendsCheck",
    "StandardDifferenceInDifferences",
    "StaggeredDifferenceInDifferences",
    "RegressionDiscontinuity",
    "StructuralTimeSeries",
    "TemporalTrajectoryResult",
    "TemporalBackendTarget",
    "TemporalComparatorSemantics",
    "TemporalCompileError",
    "TemporalDataContract",
    "TemporalExecutionPlan",
    "TemporalFallbackMode",
    "DoWhyIdentifyEstimate",
    "DoWhyIdentifyEstimateV1",
    "DoWhyRefute",
    "HybridSCMFit",
    "GCMQuery",
    "TwinNetworkQuery",
    "ParameterTransfer",
    "BuildLiteraturePrior",
    "ReconcileCausalGraph",
    "compute_reconciliation_diagnostics",
    "check_query_preservation",
    "check_query_preservation_batch",
    "evaluate_query_preservation",
    "evaluate_query_preservation_batch",
    "update_query_preservation_cache",
    "PCMCIDiscovery",
    "PCDiscovery",
    "FCIDiscovery",
    "GESDiscovery",
    "DAGMADiscovery",
    "UnifiedCausalDiscovery",
    "SensitivityMetrics",
    "CheckTransportability",
    "SymbolicIdentify",
    "CausalForestEstimator",
    "CausalBCF",
    "ForestDRLearnerEstimator",
    "DoubleMachineLearning",
    "StructuralNestedMeanModel",
    "MetaLearnerEstimator",
    "OptimalPolicyLearner",
    "StrategicSolveResult",
    "AIPWEstimator",
    "TMLEEstimator",
    "IPWEstimator",
    "PropensityScoreMatchingEstimator",
    "EntropyBalancingEstimator",
    "CBPSEstimator",
    "CallawaySantAnnaEstimator",
    "SunAbrahamEstimator",
    "DeChaisemartinDHaultfoeuilleEstimator",
    "BorusyakJaravelSpiessEstimator",
    "ManskiBoundsEstimator",
    "LeeBoundsEstimator",
    "BalkePearlBoundsEstimator",
    "ImbensManskiBoundsEstimator",
    "OptimizationBasedBoundsEstimator",
    "BoundsEngineMethod",
    "auto_bounds",
    "CausalMediationEstimator",
    "ControlledDirectEffectEstimator",
    "RegressionKinkDesignEstimator",
    "BunchingEstimator",
    "MarginalTreatmentEffectEstimator",
    "ShiftShareIVEstimator",
    "DRLearnerEstimator",
    "RLearnerEstimator",
    "register_causal_methods",
    "ensure_causal_methods_registered",
    "CausalEngine",
    "compile_temporal_estimand",
    "build_solver_diagnostics",
    "estimate_discretization_error",
    "estimate_structural_time_series_trajectory",
    "solve_temporal_effect_path",
    "solve_strategic_response",
    "strategic_result_summary",
    "build_strategic_response_bundle",
    "evaluate_strategic_hook",
    "estimate_g_computation_trajectory",
    "estimate_dtr_trajectory",
    "CausalQueryValidator",
    "transport_bounds",
    # Phase 4: Interference
    "NetworkCausalData",
    "PartialInterferenceEstimator",
    "NetworkAIPWEstimator",
    "SpatialInterferenceEstimator",
    "BipartiteInterferenceEstimator",
    # Phase 6: Advanced estimation — continuous & multi-valued treatments
    "ContinuousTreatmentData",
    "DoseResponseResult",
    "MultiTreatmentData",
    "MultiTreatmentResult",
    "GeneralizedPropensityScoreEstimator",
    "KernelDoseResponseEstimator",
    "ShiftInterventionEstimator",
    "EntropyBalancingContinuousEstimator",
    "MultinomialIPWEstimator",
    "MultiArmAIPWEstimator",
    "pairwise_contrasts",
    "FittedSuperLearner",
    "SuperLearnerNuisanceModel",
    "ParametricConditionalDensity",
    "MultinomialPropensityModel",
    "CrossFitContinuousOrchestrator",
    # Phase 8: Causal Fairness
    "FairnessObservationalData",
    "TVFairnessDecomposer",
    "PathSpecificFairnessEstimator",
    "CounterfactualFairnessEstimator",
    "CausalFairnessEngine",
    "StandardFairnessModel",
    "identify_fairness_effects",
    "fairness_bounds",
    "tv_decomposition",
    # Phase 2-5: Counterfactual calculus, transport, cyclic
    "rewrite_ctf_estimand",
    "ctf_transportability",
    "ctf_transport_bounds",
    "cyclic_id_algorithm",
    "sigma_identify",
    "sigma_z_identify",
]
