"""Public plugins core module API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

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


_REGISTRATION_METADATA: ContextVar[tuple[object, object, PluginMetadata] | None] = ContextVar(
    "domain_plugin_registration_metadata", default=None
)


@contextmanager
def _registration_metadata_scope(
    registry: PluginRegistry, plugin: DomainPlugin, metadata: PluginMetadata
) -> Iterator[None]:
    """Carry one source's detached declaration through the ordinary override point."""
    token = _REGISTRATION_METADATA.set((registry, plugin, metadata))
    try:
        yield
    finally:
        _REGISTRATION_METADATA.reset(token)


def _snapshot_plugin_metadata(plugin: DomainPlugin) -> PluginMetadata:
    """Materialize typed registration metadata without retaining callback-owned containers."""
    return _copy_plugin_metadata(plugin.metadata)


def _copy_plugin_metadata(metadata: PluginMetadata) -> PluginMetadata:
    """Validate and detach one already materialized metadata declaration."""
    if not isinstance(metadata, PluginMetadata):
        raise TypeError("DomainPlugin.metadata must return PluginMetadata")

    def plain_string(value: object, field: str, *, nonempty: bool = False) -> str:
        if not isinstance(value, str) or (nonempty and not value):
            raise TypeError(f"DomainPlugin.metadata.{field} must be a string")
        # Preserve the underlying string while avoiding a custom subclass hash.
        return str.__str__(value)

    def sequence(value: object, field: str) -> tuple:
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise TypeError(f"DomainPlugin.metadata.{field} must be a sequence")
        return tuple(value)

    dependencies = tuple(
        plain_string(value, "dependencies", nonempty=True)
        for value in sequence(metadata.dependencies, "dependencies")
    )
    tags = tuple(plain_string(value, "tags") for value in sequence(metadata.tags, "tags"))
    capabilities = []
    for value in sequence(metadata.capabilities, "capabilities"):
        try:
            capabilities.append(
                value
                if isinstance(value, PluginCapability)
                else PluginCapability(plain_string(value, "capabilities"))
            )
        except ValueError as exc:
            raise TypeError(
                "DomainPlugin.metadata.capabilities contains an unsupported value"
            ) from exc
    return PluginMetadata(
        name=plain_string(metadata.name, "name", nonempty=True),
        version=plain_string(metadata.version, "version", nonempty=True),
        description=plain_string(metadata.description, "description"),
        author=plain_string(metadata.author, "author"),
        capabilities=tuple(capabilities),
        dependencies=dependencies,
        tags=tags,
    )


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
            raise ValueError(f"n_agents ({self.n_agents}) > max_agents ({self.max_agents})")


class PluginRegistry:
    """Central registry for domain plugins."""

    _instance: PluginRegistry | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins = {}
            cls._instance._loaded = set()
            cls._instance._metadata = {}
        return cls._instance

    def register(self, plugin: DomainPlugin) -> None:
        """Register a domain against a detached, consistently used metadata snapshot.

        Source admission carries an already evaluated declaration in a scoped
        context. Ordinary callers evaluate their plugin's declaration once;
        existing one-argument registry overrides remain supported.
        """
        admitted = _REGISTRATION_METADATA.get()
        meta = (
            _copy_plugin_metadata(admitted[2])
            if admitted is not None and admitted[0] is self and admitted[1] is plugin
            else _snapshot_plugin_metadata(plugin)
        )
        if meta.name in self._plugins:
            raise ValueError(f"Plugin '{meta.name}' already registered")

        for dep in meta.dependencies:
            if dep not in self._plugins:
                raise ValueError(f"Plugin '{meta.name}' requires '{dep}' which is not registered")

        self._plugins[meta.name] = plugin
        self._metadata[meta.name] = meta

    def unregister(self, name: str) -> None:
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' not found")

        for other_name, metadata in self._metadata.items():
            if name in metadata.dependencies:
                raise ValueError(f"Cannot unregister '{name}': '{other_name}' depends on it")

        if name in self._loaded:
            self._plugins[name].on_unload()
            self._loaded.remove(name)

        del self._plugins[name]
        del self._metadata[name]

    def get(self, name: str) -> DomainPlugin:
        if name not in self._plugins:
            raise KeyError(f"Plugin '{name}' not found. Available: {list(self._plugins.keys())}")

        plugin = self._plugins[name]

        if name not in self._loaded:
            plugin.on_load()
            self._loaded.add(name)

        return plugin

    def list_plugins(self) -> list[PluginMetadata]:
        return [PluginMetadata(**vars(metadata)) for metadata in self._metadata.values()]

    def with_capability(self, capability: PluginCapability) -> list[DomainPlugin]:
        return [
            p
            for name, p in self._plugins.items()
            if capability in self._metadata[name].capabilities
        ]

    def with_tag(self, tag: str) -> list[DomainPlugin]:
        return [p for name, p in self._plugins.items() if tag in self._metadata[name].tags]

    def clear(self) -> None:
        for name in list(self._loaded):
            self._plugins[name].on_unload()
        self._plugins.clear()
        self._loaded.clear()
        self._metadata.clear()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return PluginRegistry()
