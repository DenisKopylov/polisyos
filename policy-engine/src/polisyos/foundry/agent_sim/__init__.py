"""Re-export the stable agent-simulation surface used by Foundry runtimes and tooling."""

from __future__ import annotations

import importlib
from typing import Any

from .actor_critic import (
    ActorCritic,
    AdvantageNetwork,
    ValueNetwork,
    compute_entropy,
    compute_log_prob,
    sample_actions,
)
from .analysis import AgentCluster, BehaviorAnalyzer
from .credit_assignment import (
    CentralizedCritic,
    CreditConfig,
    CreditMode,
    compute_credit_assignment,
)
from .dashboard import DashboardConfig, DashboardGenerator
from .demographics import (
    compute_demographic_metrics,
    compute_intergenerational_mobility,
    compute_population_pyramid,
)
from .distribution_executor import (
    DistributionAwareExecutor,
    create_distribution_aware_executor,
)
from .distribution_mechanisms import (
    DistributionAwareTaxMechanism,
    RelativeConsumptionMechanism,
    TargetedTransferMechanism,
)
from .distributions import (
    AdaptiveUpdateStrategy,
    AgentGrouping,
    CompactDistributionState,
    ComputeMode,
    DistributionConfig,
    DistributionState,
    RewardConfig,
    batch_assign_to_quantile_groups,
    batch_compute_group_means,
    compress_distribution_state,
    compute_bottom_share,
    compute_distribution_aware_reward,
    compute_gini,
    compute_gini_hard,
    compute_gini_proxy,
    compute_gini_soft,
    compute_group_statistics,
    compute_palma_ratio,
    compute_percentile_ratios,
    compute_quantiles,
    compute_quantiles_approximate,
    compute_quantiles_hard,
    compute_quantiles_soft,
    compute_rank_correlation,
    compute_ranks,
    compute_ranks_hard,
    compute_ranks_soft,
    compute_top_share,
    compute_transition_matrix,
    create_distribution_update_schedule,
    maybe_update_distributions,
)
from .evolution import (
    CMAESConfig,
    ESConfig,
    run_cma_es,
    run_evolution_strategies,
)
from .executor import MechanismOrder, PureExecutor
from .experiment import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentRun,
    ExperimentTracker,
)
from .government_policy import (
    GovernmentPolicy,
    GovernmentTrainingConfig,
    build_government_welfare_reward,
    train_government_policy,
)
from .graph_executor import GraphAwareExecutor, create_graph_aware_executor
from .graph_mechanisms import (
    InformationDiffusionMechanism,
    LaborNetworkMechanism,
    NetworkLendingMechanism,
    SocialInfluenceMechanism,
)
from .graph_observations import build_graph_enhanced_observations
from .graphs import (
    DynamicGraphUpdater,
    EdgeList,
    EdgeType,
    FixedSizeEdgeList,
    GraphState,
    MultiEdgeList,
    aggregate_messages,
    apply_edge_attention,
    compute_degree_centrality,
    compute_degrees,
    compute_graph_metrics,
    compute_pagerank,
    create_fixed_size_graph,
    create_random_graph,
    create_scale_free_graph,
    create_spatial_graph,
    create_watts_strogatz_graph,
    multi_hop_aggregation,
    scatter_messages,
    segment_softmax,
)
from .jit_training import (
    JITTrainingConfig,
    TrainingCarry,
    create_jit_trainer,
    create_jit_trainer_with_metrics,
)
from .mechanism import Mechanism, MechanismSpec
from .mechanisms import ConsumptionMechanism, TaxationMechanism
from .metrics import (
    MetricDefinition,
    MetricsBuffer,
    MetricsCollector,
    MetricType,
    standard_training_metrics,
    training_loss_metrics,
)
from .modes import (
    BilevelConfig,
    CalibrationTarget,
    LearningMode,
    ModeAConfig,
    ModeBConfig,
    run_bilevel,
    run_mode_a,
    run_mode_a_jit,
    run_mode_b,
    run_mode_b_jit,
    run_mode_c,
    social_welfare_objective,
)
from .mpc import HybridPlanner, MPCPlanner
from .policy import SharedPolicy, build_observations
from .population import (
    GraphSyncConfig,
    InheritanceConfig,
    LifecycleConfig,
    PopulationConfig,
    PopulationManager,
    PopulationState,
    allocate_multiple_slots,
    allocate_slot,
    batch_create_agents,
    batch_remove_agents,
    compute_death_mask,
    create_population_manager,
    free_multiple_slots,
    free_slot,
    initialize_population,
    sync_graph_with_population,
)
from .population_executor import PopulationAwareExecutor, lifecycle_step
from .population_mechanisms import (
    AgingMechanism,
    BirthMechanism,
    DeathMechanism,
    GiftTransferMechanism,
    InheritanceMechanism,
    MigrationMechanism,
)
from .prng import PRNGState, advance_prng, get_mechanism_key
from .rewards import (
    UtilityFunction,
    apply_discounting,
    compute_agent_reward,
    compute_agent_reward_with_credit,
)
from .rl import Trajectory, Transition, compute_returns_and_advantages, ppo_loss
from .state import AgentState, AggregateState, GlobalState, PolicyState, compute_aggregates
from .temporal import TemporalObservation, build_temporal_mask, build_temporal_observations
from .temporal_executor import create_temporal_executor
from .temporal_mechanisms import TemporalConsumptionMechanism
from .training import (
    TrainingConfig,
    collect_trajectory,
    train_actor_critic,
    train_actor_critic_jit,
    train_actor_critic_with_artifact,
)
from .vfi import OfflineVFI, VFILookupTable
from .visualization import TrainingVisualizer, VisualizationConfig

__all__ = [
    "ActorCritic",
    "AdaptiveUpdateStrategy",
    "AdvantageNetwork",
    "AgentCluster",
    "AgentGrouping",
    "AgentState",
    "AggregateState",
    "AgingMechanism",
    "BehaviorAnalyzer",
    "BilevelConfig",
    "BirthMechanism",
    "CMAESConfig",
    "CalibrationTarget",
    "CentralizedCritic",
    "CompactDistributionState",
    "ComputeMode",
    "ConsumptionMechanism",
    "ContractsDistributionAwareExecutor",
    "ContractsGraphAwareExecutor",
    "ContractsPopulationAwareExecutor",
    "CreditConfig",
    "CreditMode",
    "DashboardConfig",
    "DashboardGenerator",
    "DeathMechanism",
    "DistributionAwareExecutor",
    "DistributionAwareTaxMechanism",
    "DistributionConfig",
    "DistributionState",
    "DynamicGraphUpdater",
    "ESConfig",
    "EdgeList",
    "EdgeType",
    "ExperimentConfig",
    "ExperimentResult",
    "ExperimentRun",
    "ExperimentTracker",
    "FirmLifecycleEventBatch",
    "FirmLifecycleEventType",
    "FixedSizeEdgeList",
    "GiftTransferMechanism",
    "GlobalState",
    "GovernmentPolicy",
    "GovernmentTrainingConfig",
    "GraphAwareExecutor",
    "GraphState",
    "GraphSyncConfig",
    "HybridPlanner",
    "InformationDiffusionMechanism",
    "InheritanceConfig",
    "InheritanceMechanism",
    "InterventionMechanismConfig",
    "JITTrainingConfig",
    "LaborNetworkMechanism",
    "LearningMode",
    "LifecycleConfig",
    "MPCPlanner",
    "Mechanism",
    "MechanismOrder",
    "MechanismSpec",
    "MetricDefinition",
    "MetricType",
    "MetricsBuffer",
    "MetricsCollector",
    "MigrationMechanism",
    "ModeAConfig",
    "ModeBConfig",
    "MultiEdgeList",
    "NetworkLendingMechanism",
    "OfflineVFI",
    "PRNGState",
    "PolicyState",
    "PopulationAwareExecutor",
    "PopulationConfig",
    "PopulationManager",
    "PopulationState",
    "ProcurementShockBatch",
    "PureExecutor",
    "RelativeConsumptionMechanism",
    "RewardConfig",
    "SharedPolicy",
    "SocialInfluenceMechanism",
    "TargetedTransferMechanism",
    "TaxationMechanism",
    "TemporalConsumptionMechanism",
    "TemporalObservation",
    "TrainingCarry",
    "TrainingConfig",
    "TrainingVisualizer",
    "Trajectory",
    "Transition",
    "UtilityFunction",
    "VFILookupTable",
    "ValueNetwork",
    "VisualizationConfig",
    "advance_prng",
    "aggregate_messages",
    "allocate_multiple_slots",
    "allocate_slot",
    "apply_discounting",
    "apply_edge_attention",
    "batch_assign_to_quantile_groups",
    "batch_compute_group_means",
    "batch_create_agents",
    "batch_remove_agents",
    "build_government_welfare_reward",
    "build_graph_enhanced_observations",
    "build_observations",
    "build_temporal_mask",
    "build_temporal_observations",
    "collect_trajectory",
    "compress_distribution_state",
    "compute_agent_reward",
    "compute_agent_reward_with_credit",
    "compute_aggregates",
    "compute_bottom_share",
    "compute_credit_assignment",
    "compute_death_mask",
    "compute_degree_centrality",
    "compute_degrees",
    "compute_demographic_metrics",
    "compute_distribution_aware_reward",
    "compute_entropy",
    "compute_gini",
    "compute_gini_hard",
    "compute_gini_proxy",
    "compute_gini_soft",
    "compute_graph_metrics",
    "compute_group_statistics",
    "compute_intergenerational_mobility",
    "compute_log_prob",
    "compute_pagerank",
    "compute_palma_ratio",
    "compute_percentile_ratios",
    "compute_population_pyramid",
    "compute_quantiles",
    "compute_quantiles_approximate",
    "compute_quantiles_hard",
    "compute_quantiles_soft",
    "compute_rank_correlation",
    "compute_ranks",
    "compute_ranks_hard",
    "compute_ranks_soft",
    "compute_returns_and_advantages",
    "compute_top_share",
    "compute_transition_matrix",
    "create_distribution_aware_executor",
    "create_distribution_update_schedule",
    "create_fixed_size_graph",
    "create_graph_aware_executor",
    "create_jit_trainer",
    "create_jit_trainer_with_metrics",
    "create_population_manager",
    "create_random_graph",
    "create_scale_free_graph",
    "create_spatial_graph",
    "create_temporal_executor",
    "create_watts_strogatz_graph",
    "free_multiple_slots",
    "free_slot",
    "get_mechanism_key",
    "initialize_population",
    "lifecycle_step",
    "maybe_update_distributions",
    "multi_hop_aggregation",
    "multiplex_layer_code",
    "ppo_loss",
    "run_bilevel",
    "run_cma_es",
    "run_evolution_strategies",
    "run_mode_a",
    "run_mode_a_jit",
    "run_mode_b",
    "run_mode_b_jit",
    "run_mode_c",
    "sample_actions",
    "scatter_messages",
    "segment_softmax",
    "social_welfare_objective",
    "standard_training_metrics",
    "sync_graph_with_population",
    "train_actor_critic",
    "train_actor_critic_jit",
    "train_actor_critic_with_artifact",
    "train_government_policy",
    "training_loss_metrics",
]

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "ContractsDistributionAwareExecutor": (
        "polisyos.foundry.agent_sim.wiring",
        "ContractsDistributionAwareExecutor",
    ),
    "ContractsGraphAwareExecutor": (
        "polisyos.foundry.agent_sim.wiring",
        "ContractsGraphAwareExecutor",
    ),
    "ContractsPopulationAwareExecutor": (
        "polisyos.foundry.agent_sim.wiring",
        "ContractsPopulationAwareExecutor",
    ),
    "FirmLifecycleEventBatch": (
        "polisyos.foundry.agent_sim.wiring",
        "FirmLifecycleEventBatch",
    ),
    "FirmLifecycleEventType": (
        "polisyos.foundry.agent_sim.wiring",
        "FirmLifecycleEventType",
    ),
    "InterventionMechanismConfig": (
        "polisyos.foundry.agent_sim.wiring",
        "InterventionMechanismConfig",
    ),
    "ProcurementShockBatch": (
        "polisyos.foundry.agent_sim.wiring",
        "ProcurementShockBatch",
    ),
    "multiplex_layer_code": (
        "polisyos.foundry.agent_sim.wiring",
        "multiplex_layer_code",
    ),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f"module 'polisyos.foundry.agent_sim' has no attribute '{name}'")
    module_name, attr_name = _LAZY_IMPORTS[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))
