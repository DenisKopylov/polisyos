"""Public foundry plugins package API."""
from .api import PolisySimulator, SimulationConfig, SimulationResult, TrainingResult
from .composite import (
    CompositeExecutor,
    CompositeObjective,
    CompositeReward,
    CompositeState,
    CompositeStateConfig,
    CrossDomainInteraction,
)
from .core import (
    DomainAgentState,
    DomainConfig,
    DomainPlugin,
    DomainState,
    MechanismProtocol,
    ObjectiveProtocol,
    PluginCapability,
    PluginMetadata,
    PluginRegistry,
    RewardProtocol,
    get_registry,
)
from .discovery import auto_register_plugins, create_simple_plugin, discover_plugins

__all__ = [
    "DomainAgentState",
    "DomainConfig",
    "DomainPlugin",
    "DomainState",
    "MechanismProtocol",
    "ObjectiveProtocol",
    "PluginCapability",
    "PluginMetadata",
    "PluginRegistry",
    "RewardProtocol",
    "get_registry",
    "CompositeExecutor",
    "CompositeObjective",
    "CompositeReward",
    "CompositeState",
    "CompositeStateConfig",
    "CrossDomainInteraction",
    "auto_register_plugins",
    "create_simple_plugin",
    "discover_plugins",
    "PolisySimulator",
    "SimulationConfig",
    "SimulationResult",
    "TrainingResult",
]
