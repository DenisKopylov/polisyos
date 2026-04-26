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
from .cate import CausalForestEstimator
from .causal_bcf import CausalBCF
from .causal_engine import CausalEngine
from .causal_fairness import (
    CausalFairnessEngine,
    StandardFairnessModel,
    fairness_bounds,
    identify_fairness_effects,
    tv_decomposition,
)
from .constraint_discovery import FCIDiscovery, GESDiscovery, PCDiscovery
from .continuous_treatment import (
    EntropyBalancingContinuousEstimator,
    GeneralizedPropensityScoreEstimator,
    KernelDoseResponseEstimator,
    ShiftInterventionEstimator,
)
from .cross_fit import CrossFitContinuousOrchestrator
from .ctf_calculus import rewrite_ctf_estimand
from .ctf_transport import ctf_transport_bounds, ctf_transportability
from .cyclic_id import cyclic_id_algorithm
from .dagma_discovery import DAGMADiscovery
from .diagnostics import ParallelTrendsCheck, PolicyOverlapDiagnostic
from .did import (
    StaggeredDifferenceInDifferences,
    StandardDifferenceInDifferences,
)
from .discovery_pipeline import UnifiedCausalDiscovery
from .distributional_bounds import (
    DistributionalBoundsEngineMethod,
    lee_trimming_distributional_bounds,
    makarov_distributional_bounds,
    mtr_atkinson_distributional_bounds,
    mtr_gini_lorenz_distributional_bounds,
    mtr_headcount_distributional_bounds,
    mtr_theil_distributional_bounds,
    sd_atkinson_distributional_bounds,
    sd_gini_lorenz_distributional_bounds,
    sd_headcount_distributional_bounds,
    sd_theil_distributional_bounds,
)
from .dml import DoubleMachineLearning
from .dowhy_identify_estimate import DoWhyIdentifyEstimate, DoWhyIdentifyEstimateV1
from .dowhy_refute import DoWhyRefute
from .dtr import estimate_dtr_trajectory
from .dynamic_graph_dscm import (
    DynamicGraphDSCM,
    DynamicGraphDSCMData,
    DynamicGraphDSCMResult,
    DynamicGraphEvent,
    LocalDependenceEdgeResult,
    estimate_dynamic_graph_dscm,
)
from .fairness import (
    CounterfactualFairnessEstimator,
    PathSpecificFairnessEstimator,
    TVFairnessDecomposer,
)
from .forest_dr import ForestDRLearnerEstimator
from .frontier import (
    DistributionalTreatmentEffectEstimator,
    NetworkHeterogeneousEffectEstimator,
    ProximalBridgeEstimator,
    SpatialProximalBridgeEstimator,
)
from .g_computation import estimate_g_computation_trajectory
from .g_estimation import StructuralNestedMeanModel
from .gcm_fit import HybridSCMFit
from .gcm_query import GCMQuery
from .graph_reconciliation import ReconcileCausalGraph, compute_reconciliation_diagnostics
from .interference import (
    BipartiteInterferenceEstimator,
    NetworkAIPWEstimator,
    PartialInterferenceEstimator,
    SpatialInterferenceEstimator,
    build_block_stratified_network_causal_data,
)
from .invariance_tests import InvariantDiscoveryFromRegimes
from .literature_prior import BuildLiteraturePrior
from .lp_bounds import auto_bounds
from .mediation import CausalMediationEstimator, ControlledDirectEffectEstimator
from .meta_learners import MetaLearnerEstimator
from .model_class_compatibility import (
    CompatibilityVerdict,
    check_model_class_compatibility,
)
from .modern_did import (
    BorusyakJaravelSpiessEstimator,
    CallawaySantAnnaEstimator,
    DeChaisemartinDHaultfoeuilleEstimator,
    SunAbrahamEstimator,
)
from .multi_treatment import (
    MultiArmAIPWEstimator,
    MultinomialIPWEstimator,
    pairwise_contrasts,
)
from .nuisance_resolver import MultinomialPropensityModel, ParametricConditionalDensity
from .operator_valued import (
    OperatorApplyProbeMethod,
    OperatorCMEKRREstimator,
    OperatorExportBasisMethod,
    OperatorKIVEstimator,
    OperatorProximalMinimaxEstimator,
    OperatorRLearnerEstimator,
    OperatorUnsupportedTargetMethod,
)
from .parameter_transfer import ParameterTransfer
from .pcmci_discovery import PCMCIDiscovery
from .policy_learning import OptimalPolicyLearner
from .proof_trace_composability import (
    build_witness_index_from_proof_steps,
    check_proof_trace_composability,
    proof_composability_cache_key,
    replay_graph_witness,
)
from .protocols import (
    CausalEstimator,
    ContinuousTreatmentData,
    DoseResponseResult,
    FairnessObservationalData,
    GraphCausalData,
    GraphCausalDataV1,
    GraphReconciliationData,
    HTEObservationalData,
    LiteraturePriorBuildData,
    LLMStructuralHint,
    MultiTreatmentData,
    MultiTreatmentResult,
    NetworkCausalData,
    PanelObservationalData,
    ParameterTransferData,
    RDDObservationalData,
    SCMFitData,
    SCMQueryData,
    TabularCausalDiscoveryData,
    TimeSeriesCausalData,
)
from .proximal_identify import proximal_identify_v1
from .proximal_mediation import (
    ProximalMediationEstimator,
    proximal_mediation_identify_v1,
)
from .query_preservation import (
    check_query_preservation,
    check_query_preservation_batch,
    evaluate_query_preservation,
    evaluate_query_preservation_batch,
    negative_certificate_from_query_preservation_trace,
    update_query_preservation_artifact_refs,
    update_query_preservation_cache,
)
from .query_validator import CausalQueryValidator
from .rdd import RegressionDiscontinuity
from .recourse_manifold import (
    DiscreteActionAtlas,
    PlannerOptions,
    SCMAdapter,
    best_first_support_search,
    branch_and_bound_over_supports,
    build_discrete_atlas,
    exact_graph_search,
    optimal_recourse_intervention,
    program_cost,
)
from .sensitivity_metrics import SensitivityMetrics
from .sigma_calculus import sigma_identify, sigma_z_identify
from .space_time_dscm import (
    FieldNode,
    FittedSPDEParameters,
    OperatorEdge,
    SpaceTimeDomain,
    SpaceTimeDSCM,
    SpaceTimeFieldData,
    SpaceTimeIdentificationCertificate,
    SpaceTimeIdentificationStatus,
    SpaceTimeIntervention,
    SpaceTimeInterventionType,
    SpaceTimeMeshSpec,
    SpaceTimePathSpace,
    SpaceTimeSPDEGComputation,
    SpaceTimeSPDEGComputationResult,
    SpaceTimeSplit,
    SpaceTimeSupport,
    SPDEEstimatorSpec,
    SPDEGenerator,
    SPDEMechanism,
    build_piecewise_linear_fem_matrices,
    build_space_time_identification_certificate,
    estimate_space_time_spde_g_computation,
    estimate_space_time_treatment_density_process,
    simulate_linear_diffusion_response,
    simulate_reaction_diffusion_response,
)
from .stochastic_policies import (
    PolicyAIPWEstimator,
    PolicyPluginEstimator,
    PolicyTMLEEstimator,
)
from .strategic import (
    PerformativeLoopSpec,
    StrategicSolveResult,
    analyze_performative_loop,
    build_strategic_response_bundle,
    evaluate_strategic_hook,
    solve_strategic_response,
    strategic_result_summary,
)
from .structural_time_series import (
    StructuralTimeSeries,
    TemporalTrajectoryResult,
    build_solver_diagnostics,
    estimate_discretization_error,
    estimate_structural_time_series_trajectory,
    solve_temporal_effect_path,
)
from .superlearner import FittedSuperLearner, SuperLearnerNuisanceModel
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
from .transport_bounds import transport_bounds
from .transport_check import CheckTransportability
from .treatment_effects import (
    AIPWEstimator,
    CBPSEstimator,
    EntropyBalancingEstimator,
    IPWEstimator,
    PropensityScoreMatchingEstimator,
    TMLEEstimator,
)
from .twin_network_query import TwinNetworkQuery


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
    "PolicyOverlapDiagnostic",
    "InvariantDiscoveryFromRegimes",
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
    "CompatibilityVerdict",
    "ReconcileCausalGraph",
    "check_model_class_compatibility",
    "compute_reconciliation_diagnostics",
    "check_query_preservation",
    "check_query_preservation_batch",
    "evaluate_query_preservation",
    "evaluate_query_preservation_batch",
    "negative_certificate_from_query_preservation_trace",
    "update_query_preservation_cache",
    "update_query_preservation_artifact_refs",
    "build_witness_index_from_proof_steps",
    "check_proof_trace_composability",
    "proof_composability_cache_key",
    "replay_graph_witness",
    "PCMCIDiscovery",
    "proximal_identify_v1",
    "proximal_mediation_identify_v1",
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
    "PerformativeLoopSpec",
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
    "DistributionalBoundsEngineMethod",
    "lee_trimming_distributional_bounds",
    "makarov_distributional_bounds",
    "mtr_atkinson_distributional_bounds",
    "mtr_gini_lorenz_distributional_bounds",
    "mtr_headcount_distributional_bounds",
    "mtr_theil_distributional_bounds",
    "sd_atkinson_distributional_bounds",
    "sd_gini_lorenz_distributional_bounds",
    "sd_headcount_distributional_bounds",
    "sd_theil_distributional_bounds",
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
    "analyze_performative_loop",
    "estimate_g_computation_trajectory",
    "estimate_dtr_trajectory",
    "DynamicGraphDSCM",
    "DynamicGraphDSCMData",
    "DynamicGraphDSCMResult",
    "DynamicGraphEvent",
    "LocalDependenceEdgeResult",
    "estimate_dynamic_graph_dscm",
    "CausalQueryValidator",
    "transport_bounds",
    # Phase 4: Interference
    "NetworkCausalData",
    "PartialInterferenceEstimator",
    "NetworkAIPWEstimator",
    "SpatialInterferenceEstimator",
    "BipartiteInterferenceEstimator",
    "build_block_stratified_network_causal_data",
    "NetworkHeterogeneousEffectEstimator",
    # Phase 6: Advanced estimation — continuous & multi-valued treatments
    "ContinuousTreatmentData",
    "DoseResponseResult",
    "MultiTreatmentData",
    "MultiTreatmentResult",
    "GeneralizedPropensityScoreEstimator",
    "KernelDoseResponseEstimator",
    "ShiftInterventionEstimator",
    "PolicyAIPWEstimator",
    "PolicyPluginEstimator",
    "PolicyTMLEEstimator",
    "EntropyBalancingContinuousEstimator",
    "MultinomialIPWEstimator",
    "MultiArmAIPWEstimator",
    "ProximalBridgeEstimator",
    "SpatialProximalBridgeEstimator",
    "ProximalMediationEstimator",
    "DistributionalTreatmentEffectEstimator",
    "pairwise_contrasts",
    "FittedSuperLearner",
    "SuperLearnerNuisanceModel",
    "ParametricConditionalDensity",
    "MultinomialPropensityModel",
    "CrossFitContinuousOrchestrator",
    # Stage 14.2: operator-valued causal effects
    "OperatorCMEKRREstimator",
    "OperatorRLearnerEstimator",
    "OperatorKIVEstimator",
    "OperatorProximalMinimaxEstimator",
    "OperatorApplyProbeMethod",
    "OperatorExportBasisMethod",
    "OperatorUnsupportedTargetMethod",
    # Stage 14.5: space-time DSCM controlled SPDE g-computation
    "FieldNode",
    "FittedSPDEParameters",
    "OperatorEdge",
    "SPDEEstimatorSpec",
    "SPDEGenerator",
    "SPDEMechanism",
    "SpaceTimeDSCM",
    "SpaceTimeDomain",
    "SpaceTimeFieldData",
    "SpaceTimeIdentificationCertificate",
    "SpaceTimeIdentificationStatus",
    "SpaceTimeIntervention",
    "SpaceTimeInterventionType",
    "SpaceTimeMeshSpec",
    "SpaceTimePathSpace",
    "SpaceTimeSPDEGComputation",
    "SpaceTimeSPDEGComputationResult",
    "SpaceTimeSplit",
    "SpaceTimeSupport",
    "build_piecewise_linear_fem_matrices",
    "build_space_time_identification_certificate",
    "estimate_space_time_spde_g_computation",
    "estimate_space_time_treatment_density_process",
    "simulate_linear_diffusion_response",
    "simulate_reaction_diffusion_response",
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
    # Stage 13.4: Optimal recourse intervention + causal manifold geometry
    "DiscreteActionAtlas",
    "PlannerOptions",
    "SCMAdapter",
    "best_first_support_search",
    "branch_and_bound_over_supports",
    "build_discrete_atlas",
    "exact_graph_search",
    "optimal_recourse_intervention",
    "program_cost",
]
