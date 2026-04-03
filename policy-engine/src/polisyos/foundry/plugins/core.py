"""Public plugins core module API."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Generic, Protocol, Sequence, TypeVar, runtime_checkable

import jax
import jax.numpy as jnp

StateT = TypeVar("StateT", bound="DomainState")
AgentT = TypeVar("AgentT", bound="DomainAgentState")
ActionT = TypeVar("ActionT")
ObsT = TypeVar("ObsT")


@runtime_checkable
class DomainState(Protocol):
    """Protocol for domain-specific state."""

    @classmethod
    def empty(cls, n_agents: int, seed: int, **kwargs) -> DomainState:
        """Create empty state."""
        ...

    def validate(self) -> bool:
        """Validate state consistency."""
        ...


@runtime_checkable
class DomainAgentState(Protocol):
    """Protocol for agent state within a domain."""

    active: jnp.ndarray

    def get_observations(self) -> jnp.ndarray:
        """Get observation tensor for all agents."""
        ...


class MechanismProtocol(Protocol[StateT]):
    """Protocol for domain mechanisms."""

    def apply(self, state: StateT, **kwargs) -> StateT:
        """Apply mechanism to state."""
        ...

    @property
    def name(self) -> str:
        """Mechanism identifier."""
        ...


class RewardProtocol(Protocol[StateT]):
    """Protocol for reward computation."""

    def compute(
        self,
        state: StateT,
        next_state: StateT,
        agent_actions: jnp.ndarray | None = None,
    ) -> jnp.ndarray:
        """Compute rewards for all agents."""
        ...


class ObjectiveProtocol(Protocol[StateT]):
    """Protocol for policy objective functions."""

    def evaluate(self, state: StateT) -> jnp.ndarray:
        """Evaluate objective (scalar)."""
        ...

    @property
    def maximize(self) -> bool:
        """True if objective should be maximized."""
        ...


class PluginCapability(str, Enum):
    """Capabilities a plugin can provide."""

    AGENTS = "agents"
    MECHANISMS = "mechanisms"
    REWARDS = "rewards"
    OBJECTIVES = "objectives"
    OBSERVATIONS = "observations"
    VISUALIZATION = "visualization"
    CALIBRATION = "calibration"


@dataclass
class PluginMetadata:
    """Metadata for a domain plugin."""

    name: str
    version: str
    description: str
    author: str = ""
    capabilities: tuple[PluginCapability, ...] = ()
    dependencies: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Plugin name required")
        if not self.version:
            raise ValueError("Plugin version required")


class DomainPlugin(ABC, Generic[StateT]):
    """Base class for domain plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Plugin metadata."""
        ...

    @abstractmethod
    def create_initial_state(self, config: DomainConfig, rng_key: jax.Array) -> StateT:
        """Create initial state for this domain."""
        ...

    @abstractmethod
    def get_mechanisms(self) -> Sequence[MechanismProtocol[StateT]]:
        """Get all mechanisms for this domain."""
        ...

    @abstractmethod
    def get_reward_function(self) -> RewardProtocol[StateT]:
        """Get reward function for agent learning."""
        ...

    @abstractmethod
    def get_objectives(self) -> dict[str, ObjectiveProtocol[StateT]]:
        """Get available policy objectives."""
        ...

    def get_observation_builder(self) -> Callable[[StateT], jnp.ndarray] | None:
        """Optional custom observation builder."""
        return None

    def get_visualizations(self) -> dict[str, Callable] | None:
        """Optional custom visualizations."""
        return None

    def validate_config(self, config: DomainConfig) -> list[str]:
        """Validate configuration, return list of errors."""
        return []

    def on_load(self) -> None:
        """Called when plugin is loaded."""
        return None

    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        return None


@dataclass
class DomainConfig:
    """Configuration for a domain."""

    n_agents: int = 1000
    max_agents: int = 10000
    seed: int = 42
    time_horizon: int = 256
    parameters: dict[str, Any] = field(default_factory=dict)
    enabled_mechanisms: tuple[str, ...] = ()
    mechanism_configs: dict[str, dict] = field(default_factory=dict)
    agent_learning: bool = True
    policy_learning: bool = True

    def __post_init__(self) -> None:
        if self.n_agents > self.max_agents:
            raise ValueError(
                f"n_agents ({self.n_agents}) > max_agents ({self.max_agents})"
            )


class PluginRegistry:
    """Central registry for domain plugins."""

    _instance: PluginRegistry | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins = {}
            cls._instance._loaded = set()
        return cls._instance

    def register(self, plugin: DomainPlugin) -> None:
        meta = plugin.metadata
        if meta.name in self._plugins:
            raise ValueError(f"Plugin '{meta.name}' already registered")

        for dep in meta.dependencies:
            if dep not in self._plugins:
                raise ValueError(
                    f"Plugin '{meta.name}' requires '{dep}' which is not registered"
                )

        self._plugins[meta.name] = plugin

    def unregister(self, name: str) -> None:
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' not found")

        for other_name, other_plugin in self._plugins.items():
            if name in other_plugin.metadata.dependencies:
                raise ValueError(
                    f"Cannot unregister '{name}': '{other_name}' depends on it"
                )

        if name in self._loaded:
            self._plugins[name].on_unload()
            self._loaded.remove(name)

        del self._plugins[name]

    def get(self, name: str) -> DomainPlugin:
        if name not in self._plugins:
            raise KeyError(
                f"Plugin '{name}' not found. Available: {list(self._plugins.keys())}"
            )

        plugin = self._plugins[name]

        if name not in self._loaded:
            plugin.on_load()
            self._loaded.add(name)

        return plugin

    def list_plugins(self) -> list[PluginMetadata]:
        return [p.metadata for p in self._plugins.values()]

    def with_capability(self, capability: PluginCapability) -> list[DomainPlugin]:
        return [
            p for p in self._plugins.values() if capability in p.metadata.capabilities
        ]

    def with_tag(self, tag: str) -> list[DomainPlugin]:
        return [p for p in self._plugins.values() if tag in p.metadata.tags]

    def clear(self) -> None:
        for name in list(self._loaded):
            self._plugins[name].on_unload()
        self._plugins.clear()
        self._loaded.clear()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return PluginRegistry()
