"""Public plugins composite module API."""
from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
from dataclasses import replace as dc_replace
from typing import Any, Callable, Sequence

import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.plugins.core import (
    DomainConfig,
    DomainState,
    PluginRegistry,
    get_registry,
)


@dataclass
class CompositeStateConfig:
    """Configuration for composite multi-domain state."""

    domains: dict[str, DomainConfig]
    interactions: list[CrossDomainInteraction] = field(default_factory=list)
    global_seed: int = 42
    synchronize_time: bool = True


@dataclass
class CrossDomainInteraction:
    """Definition of interaction between domains."""

    source_domain: str
    target_domain: str
    source_field: str
    target_field: str
    transform: Callable[[jnp.ndarray], jnp.ndarray] = lambda x: x
    weight: float = 1.0


class CompositeState(eqx.Module):
    """Composite state combining multiple domain states."""

    domain_states: dict[str, Any]
    time_step: jnp.ndarray
    config: CompositeStateConfig = eqx.field(static=True)

    @classmethod
    def create(
        cls,
        config: CompositeStateConfig,
        registry: PluginRegistry | None = None,
    ) -> CompositeState:
        if registry is None:
            registry = get_registry()

        rng = jax.random.PRNGKey(config.global_seed)
        domain_states: dict[str, Any] = {}

        for domain_name, domain_config in config.domains.items():
            rng, subkey = jax.random.split(rng)
            plugin = registry.get(domain_name)
            domain_states[domain_name] = plugin.create_initial_state(
                domain_config, subkey
            )

        return cls(
            domain_states=domain_states,
            time_step=jnp.array(0),
            config=config,
        )

    def get_domain(self, name: str) -> DomainState:
        if name not in self.domain_states:
            raise KeyError(f"Domain '{name}' not in composite state")
        return self.domain_states[name]

    def update_domain(self, name: str, new_state: DomainState) -> CompositeState:
        new_domains = dict(self.domain_states)
        new_domains[name] = new_state
        return CompositeState(
            domain_states=new_domains,
            time_step=self.time_step,
            config=self.config,
        )

    def apply_interactions(self) -> CompositeState:
        new_domains = dict(self.domain_states)

        for interaction in self.config.interactions:
            source_state = self.domain_states[interaction.source_domain]
            target_state = new_domains[interaction.target_domain]

            source_value = _get_nested_field(source_state, interaction.source_field)
            transformed = interaction.transform(source_value) * interaction.weight

            target_state = _set_nested_field(
                target_state,
                interaction.target_field,
                transformed,
            )
            new_domains[interaction.target_domain] = target_state

        return CompositeState(
            domain_states=new_domains,
            time_step=self.time_step,
            config=self.config,
        )

    def increment_time(self) -> CompositeState:
        return CompositeState(
            domain_states=self.domain_states,
            time_step=self.time_step + 1,
            config=self.config,
        )


def _get_nested_field(obj: Any, path: str) -> Any:
    parts = path.split(".")
    current = obj
    for part in parts:
        if hasattr(current, part):
            current = getattr(current, part)
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise AttributeError(f"Cannot access '{part}' in {type(current)}")
    return current


def _replace_obj(obj: Any, **updates) -> Any:
    if hasattr(obj, "replace"):
        return obj.replace(**updates)
    if is_dataclass(obj):
        return dc_replace(obj, **updates)
    if isinstance(obj, dict):
        new_dict = dict(obj)
        new_dict.update(updates)
        return new_dict
    raise AttributeError(f"Cannot update {type(obj)}")


def _set_nested_field(obj: Any, path: str, value: Any) -> Any:
    parts = path.split(".")

    if len(parts) == 1:
        return _replace_obj(obj, **{parts[0]: value})

    head, rest = parts[0], ".".join(parts[1:])

    if hasattr(obj, head):
        child = getattr(obj, head)
        new_child = _set_nested_field(child, rest, value)
        return _replace_obj(obj, **{head: new_child})
    if isinstance(obj, dict):
        new_dict = dict(obj)
        new_dict[head] = _set_nested_field(obj[head], rest, value)
        return new_dict

    raise AttributeError(f"Cannot set '{path}' in {type(obj)}")


class CompositeExecutor(eqx.Module):
    """Executor for composite multi-domain simulations."""

    registry: PluginRegistry = eqx.field(static=True)
    execution_order: tuple[str, ...] = eqx.field(static=True)

    def __init__(
        self,
        domain_names: Sequence[str],
        registry: PluginRegistry | None = None,
    ):
        self.registry = registry or get_registry()
        self.execution_order = tuple(domain_names)

    def step(
        self,
        state: CompositeState,
        rng_key: jax.Array | None = None,
    ) -> CompositeState:
        if rng_key is None:
            rng_key = jax.random.PRNGKey(int(state.time_step))

        for domain_name in self.execution_order:
            rng_key, domain_key = jax.random.split(rng_key)

            plugin = self.registry.get(domain_name)
            domain_state = state.get_domain(domain_name)
            domain_cfg = state.config.domains.get(domain_name)

            mechanisms = plugin.get_mechanisms()
            if domain_cfg and domain_cfg.enabled_mechanisms:
                allowed = set(domain_cfg.enabled_mechanisms)
                mechanisms = [m for m in mechanisms if m.name in allowed]

            for mechanism in mechanisms:
                domain_key, mech_key = jax.random.split(domain_key)
                mech_cfg = {}
                if domain_cfg is not None:
                    mech_cfg = domain_cfg.mechanism_configs.get(mechanism.name, {})
                domain_state = mechanism.apply(domain_state, rng_key=mech_key, **mech_cfg)

            if hasattr(domain_state, "update_aggregates"):
                domain_state = domain_state.update_aggregates()

            state = state.update_domain(domain_name, domain_state)

        state = state.apply_interactions()
        state = state.increment_time()
        return state

    def run(
        self,
        initial_state: CompositeState,
        n_steps: int,
        rng_key: jax.Array | None = None,
    ) -> tuple[CompositeState, list[CompositeState]]:
        if rng_key is None:
            rng_key = jax.random.PRNGKey(0)

        states = [initial_state]
        state = initial_state

        for _ in range(n_steps):
            rng_key, subkey = jax.random.split(rng_key)
            state = self.step(state, subkey)
            states.append(state)

        return state, states


class CompositeReward(eqx.Module):
    """Aggregate reward across multiple domains."""

    domain_weights: dict[str, float]
    registry: PluginRegistry = eqx.field(static=True)

    def __init__(
        self,
        domain_weights: dict[str, float],
        registry: PluginRegistry | None = None,
    ):
        self.domain_weights = domain_weights
        self.registry = registry or get_registry()

    def compute(self, state: CompositeState, next_state: CompositeState) -> dict[str, jnp.ndarray]:
        rewards: dict[str, jnp.ndarray] = {}
        total = jnp.array(0.0)

        for domain_name, weight in self.domain_weights.items():
            plugin = self.registry.get(domain_name)
            reward_fn = plugin.get_reward_function()

            domain_reward = reward_fn.compute(
                state.get_domain(domain_name),
                next_state.get_domain(domain_name),
            )

            rewards[domain_name] = domain_reward

            if domain_reward.ndim > 0:
                total = total + weight * jnp.mean(domain_reward)
            else:
                total = total + weight * domain_reward

        rewards["total"] = total
        return rewards


class CompositeObjective(eqx.Module):
    """Multi-objective function combining domain objectives."""

    objectives: dict[str, tuple[str, str, float]]
    registry: PluginRegistry = eqx.field(static=True)

    def __init__(
        self,
        objectives: dict[str, tuple[str, str, float]],
        registry: PluginRegistry | None = None,
    ):
        self.objectives = objectives
        self.registry = registry or get_registry()

    def evaluate(self, state: CompositeState) -> dict[str, jnp.ndarray]:
        results: dict[str, jnp.ndarray] = {}
        total = jnp.array(0.0)

        for name, (domain_name, obj_name, weight) in self.objectives.items():
            plugin = self.registry.get(domain_name)
            objectives = plugin.get_objectives()

            if obj_name not in objectives:
                raise KeyError(
                    f"Objective '{obj_name}' not found in domain '{domain_name}'"
                )

            obj = objectives[obj_name]
            value = obj.evaluate(state.get_domain(domain_name))

            if not obj.maximize:
                value = -value

            results[name] = value
            total = total + weight * value

        results["total"] = total
        return results
