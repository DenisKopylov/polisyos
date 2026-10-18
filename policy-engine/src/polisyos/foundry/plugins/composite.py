"""Public plugins composite module API."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, is_dataclass
from dataclasses import replace as dc_replace
from typing import Any

import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.distributions import (
    GiniPopulationProfile,
    _active_gini_population_schema_supported,
    active_gini_population_supported,
)
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
    gini_profile_supported: jnp.ndarray = eqx.field(
        default_factory=lambda: jnp.asarray(True, dtype=jnp.bool_)
    )

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
            domain_states[domain_name] = plugin.create_initial_state(domain_config, subkey)

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
            gini_profile_supported=self.gini_profile_supported,
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
            gini_profile_supported=self.gini_profile_supported,
            config=self.config,
        )

    def increment_time(self) -> CompositeState:
        return CompositeState(
            domain_states=self.domain_states,
            time_step=self.time_step + 1,
            gini_profile_supported=self.gini_profile_supported,
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


def _jax_abstract_leaf_schema(value: Any) -> Any | None:
    """Return JAX's abstract value for one supported dynamic tree leaf."""
    typeof = getattr(jax, "typeof", None)
    if typeof is None:
        core = getattr(jax, "core", None)
        typeof = getattr(core, "get_aval", None)
    if typeof is None:
        return None
    try:
        abstract_value = typeof(value)
    except (OverflowError, TypeError, ValueError):
        return None
    if not hasattr(abstract_value, "shape") or not hasattr(abstract_value, "dtype"):
        return None
    return abstract_value


def _jax_cond_carry_schema_supported(candidate: Any, template: Any) -> bool:
    """Ask JAX's actual conditional tracer whether two output carries match."""
    eval_shape = getattr(jax, "eval_shape", None)
    cond = getattr(getattr(jax, "lax", None), "cond", None)
    if not callable(eval_shape) or not callable(cond):
        return False

    def _conditional_output(predicate: jnp.ndarray) -> Any:
        return cond(
            predicate,
            lambda _: candidate,
            lambda _: template,
            operand=None,
        )

    try:
        eval_shape(_conditional_output, jnp.asarray(True, dtype=jnp.bool_))
    except (OverflowError, TypeError, ValueError):
        return False
    return True


def _population_metadata_schema_supported(
    economic_state: Any,
    domain_config: DomainConfig | None,
) -> bool:
    """Check that configured population counts keep their scalar integer ABI."""
    if not isinstance(domain_config, DomainConfig):
        return False
    if type(domain_config.n_agents) is not int or type(domain_config.max_agents) is not int:
        return False
    for value in (economic_state.n_agents, economic_state.max_agents):
        schema = _jax_abstract_leaf_schema(value)
        if schema is None or schema.shape != () or not jnp.issubdtype(schema.dtype, jnp.integer):
            return False
    return True


def _population_metadata_matches_config(
    economic_state: Any,
    domain_config: DomainConfig | None,
) -> jnp.ndarray:
    """Return whether the source-owned population counts match their config."""
    if not _population_metadata_schema_supported(economic_state, domain_config):
        return jnp.asarray(False, dtype=jnp.bool_)
    assert domain_config is not None
    n_agents_schema = _jax_abstract_leaf_schema(economic_state.n_agents)
    max_agents_schema = _jax_abstract_leaf_schema(economic_state.max_agents)
    assert n_agents_schema is not None
    assert max_agents_schema is not None
    try:
        n_agents_bounds = jnp.iinfo(n_agents_schema.dtype)
        max_agents_bounds = jnp.iinfo(max_agents_schema.dtype)
    except (TypeError, ValueError):
        return jnp.asarray(False, dtype=jnp.bool_)
    if not (
        int(n_agents_bounds.min) <= domain_config.n_agents <= int(n_agents_bounds.max)
        and int(max_agents_bounds.min) <= domain_config.max_agents <= int(max_agents_bounds.max)
    ):
        return jnp.asarray(False, dtype=jnp.bool_)
    return (
        jnp.asarray(economic_state.n_agents)
        == jnp.asarray(domain_config.n_agents, dtype=n_agents_schema.dtype)
    ) & (
        jnp.asarray(economic_state.max_agents)
        == jnp.asarray(domain_config.max_agents, dtype=max_agents_schema.dtype)
    )


def _tree_align_to_template(
    candidate: Any,
    template: Any,
    *,
    allow_float_dtype_change: bool = False,
) -> Any | None:
    """Align a complete JAX pytree to its source-owned shape and dtype template.

    A selected composite step cannot rely on a profiler-like leaf sample: every
    producer output and aggregation result must have the same complete tree
    schema as the state it replaces. The Economics-to-native projection is the
    one explicit conversion boundary, so its caller may request real-floating
    leaf casts to the actual native carry template.

    Returns:
        The aligned candidate, or ``None`` when its tree, shape, or supported
        dtype schema cannot be represented by the template.
    """
    candidate_leaves, candidate_tree = jax.tree_util.tree_flatten(candidate)
    template_leaves, template_tree = jax.tree_util.tree_flatten(template)
    if candidate_tree != template_tree:
        return None

    aligned_leaves = []
    for candidate_leaf, template_leaf in zip(candidate_leaves, template_leaves, strict=True):
        candidate_schema = _jax_abstract_leaf_schema(candidate_leaf)
        template_schema = _jax_abstract_leaf_schema(template_leaf)
        if candidate_schema is None or template_schema is None:
            return None
        try:
            candidate_is_complex = jnp.issubdtype(candidate_schema.dtype, jnp.complexfloating)
            template_is_complex = jnp.issubdtype(template_schema.dtype, jnp.complexfloating)
        except TypeError:
            return None
        if candidate_is_complex or template_is_complex:
            return None
        candidate_dtype = candidate_schema.dtype
        template_dtype = template_schema.dtype
        if candidate_dtype != template_dtype:
            can_align_float = (
                allow_float_dtype_change
                and eqx.is_array(candidate_leaf)
                and eqx.is_array(template_leaf)
                and jnp.issubdtype(candidate_dtype, jnp.floating)
                and jnp.issubdtype(template_dtype, jnp.floating)
            )
            if can_align_float:
                candidate_leaf = candidate_leaf.astype(template_dtype)
        aligned_leaves.append(candidate_leaf)

    aligned_candidate = candidate_tree.unflatten(aligned_leaves)
    if not _jax_cond_carry_schema_supported(aligned_candidate, template):
        return None
    return aligned_candidate


class CompositeExecutor(eqx.Module):
    """Executor for composite multi-domain simulations."""

    registry: PluginRegistry = eqx.field(static=True)
    execution_order: tuple[str, ...] = eqx.field(static=True)
    gini_population_profile: GiniPopulationProfile | None = eqx.field(static=True)

    def __init__(
        self,
        domain_names: Sequence[str],
        registry: PluginRegistry | None = None,
        *,
        gini_population_profile: GiniPopulationProfile | None = None,
    ):
        if gini_population_profile is not None and not isinstance(
            gini_population_profile, GiniPopulationProfile
        ):
            raise TypeError("gini_population_profile must be a source-defined profile")
        self.registry = registry or get_registry()
        self.execution_order = tuple(domain_names)
        self.gini_population_profile = gini_population_profile

    def step(
        self,
        state: CompositeState,
        rng_key: jax.Array | None = None,
    ) -> CompositeState:
        if rng_key is None:
            rng_key = jax.random.PRNGKey(int(state.time_step))

        if self.gini_population_profile is not None:
            return self._step_with_gini_profile(state, rng_key)

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

    def _step_with_gini_profile(
        self,
        state: CompositeState,
        rng_key: jax.Array,
    ) -> CompositeState:
        """Run the selected Economics profile and stop before invalid Gini input."""
        if type(state) is not CompositeState:
            raise CompositeProfileRefusal(
                "composite_gini_profile_schema_unsupported",
                "The selected Gini profile requires the canonical CompositeState type.",
            )
        if self.execution_order != ("economics",) or set(state.domain_states) != {"economics"}:
            raise CompositeProfileRefusal(
                "composite_gini_profile_schema_unsupported",
                "The selected Gini profile requires exactly one Economics domain.",
            )
        if state.config.interactions:
            raise CompositeProfileRefusal(
                "composite_gini_profile_schema_unsupported",
                "The selected Gini profile does not admit cross-domain interactions.",
            )
        initial_domain = state.get_domain("economics")
        from polisyos.foundry.plugins.economics.state import EconomicAgentState, EconomicState

        if type(initial_domain) is not EconomicState:
            raise CompositeProfileRefusal(
                "composite_gini_profile_schema_unsupported",
                "The selected Gini profile requires the canonical Economics state and agent types.",
            )
        initial_agents = initial_domain.agents
        if type(initial_agents) is not EconomicAgentState:
            raise CompositeProfileRefusal(
                "composite_gini_profile_schema_unsupported",
                "The selected Gini profile requires the canonical Economics state and agent types.",
            )
        domain_config = state.config.domains.get("economics")
        if (
            not _population_metadata_schema_supported(initial_domain, domain_config)
            or _tree_align_to_template(initial_domain, initial_domain) is None
        ):
            raise CompositeProfileRefusal(
                "composite_gini_profile_schema_unsupported",
                "The selected Gini profile requires a JAX-compatible state tree and configured "
                "scalar integer population counts.",
            )
        if not _active_gini_population_schema_supported(
            initial_agents.active,
            initial_agents.wealth,
            initial_agents.income,
        ):
            raise CompositeProfileRefusal(
                "composite_gini_profile_schema_unsupported",
                "The selected Gini profile requires matching real-valued resource vectors.",
            )

        initially_supported = active_gini_population_supported(
            initial_agents.active,
            initial_agents.wealth,
            initial_agents.income,
        ) & _population_metadata_matches_config(initial_domain, domain_config)

        def _refuse(current: CompositeState) -> CompositeState:
            return eqx.tree_at(
                lambda candidate: candidate.gini_profile_supported,
                current,
                jnp.asarray(False, dtype=jnp.bool_),
            )

        def _execute(current: CompositeState) -> CompositeState:
            domain_name = "economics"
            domain_state = current.get_domain(domain_name)
            domain_config = current.config.domains.get(domain_name)
            plugin = self.registry.get(domain_name)
            domain_key = rng_key
            mechanisms = plugin.get_mechanisms()
            if domain_config and domain_config.enabled_mechanisms:
                allowed = set(domain_config.enabled_mechanisms)
                mechanisms = [mechanism for mechanism in mechanisms if mechanism.name in allowed]

            producers_supported = jnp.asarray(True, dtype=jnp.bool_)
            for mechanism in mechanisms:
                domain_key, mechanism_key = jax.random.split(domain_key)
                mechanism_config = {}
                if domain_config is not None:
                    mechanism_config = domain_config.mechanism_configs.get(mechanism.name, {})

                def _apply_and_check(carry):
                    previous_domain, _previously_supported = carry
                    candidate = mechanism.apply(
                        previous_domain,
                        rng_key=mechanism_key,
                        **mechanism_config,
                    )
                    if type(candidate) is not EconomicState:
                        return previous_domain, jnp.asarray(False, dtype=jnp.bool_)
                    candidate_agents = candidate.agents
                    if type(candidate_agents) is not EconomicAgentState:
                        return previous_domain, jnp.asarray(False, dtype=jnp.bool_)
                    candidate = _tree_align_to_template(candidate, previous_domain)
                    if candidate is None or not _population_metadata_schema_supported(
                        candidate, domain_config
                    ):
                        return previous_domain, jnp.asarray(False, dtype=jnp.bool_)
                    candidate_agents = candidate.agents
                    if not _active_gini_population_schema_supported(
                        candidate_agents.active,
                        candidate_agents.wealth,
                        candidate_agents.income,
                    ):
                        return previous_domain, jnp.asarray(False, dtype=jnp.bool_)
                    candidate_supported = active_gini_population_supported(
                        candidate_agents.active,
                        candidate_agents.wealth,
                        candidate_agents.income,
                    ) & _population_metadata_matches_config(candidate, domain_config)
                    accepted_domain = jax.lax.cond(
                        candidate_supported,
                        lambda _: candidate,
                        lambda _: previous_domain,
                        operand=None,
                    )
                    return accepted_domain, candidate_supported

                domain_state, producers_supported = jax.lax.cond(
                    producers_supported,
                    _apply_and_check,
                    lambda carry: carry,
                    (domain_state, producers_supported),
                )

            produced = current.update_domain(domain_name, domain_state)

            def _aggregate_and_commit(current_state: CompositeState) -> CompositeState:
                aggregated = EconomicState.update_aggregates(domain_state)
                if _tree_align_to_template(
                    aggregated, domain_state
                ) is None or not _population_metadata_schema_supported(aggregated, domain_config):
                    return _refuse(current_state)

                def _commit(_operand) -> CompositeState:
                    committed = current_state.update_domain(domain_name, aggregated)
                    return committed.increment_time()

                return jax.lax.cond(
                    _population_metadata_matches_config(aggregated, domain_config),
                    _commit,
                    _refuse,
                    current_state,
                )

            return jax.lax.cond(
                producers_supported,
                _aggregate_and_commit,
                _refuse,
                produced,
            )

        return jax.lax.cond(
            state.gini_profile_supported & initially_supported,
            _execute,
            _refuse,
            state,
        )

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
            if self.gini_population_profile is not None and not bool(state.gini_profile_supported):
                raise CompositeProfileRefusal(
                    "composite_gini_population_unsupported",
                    "The selected Gini profile stopped before a supported aggregate state.",
                )

        return state, states


class CompositeProfileRefusal(ValueError):
    """Typed refusal when a selected composite profile cannot safely continue."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


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
                raise KeyError(f"Objective '{obj_name}' not found in domain '{domain_name}'")

            obj = objectives[obj_name]
            value = obj.evaluate(state.get_domain(domain_name))

            if not obj.maximize:
                value = -value

            results[name] = value
            total = total + weight * value

        results["total"] = total
        return results
