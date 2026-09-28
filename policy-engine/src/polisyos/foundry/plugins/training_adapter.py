"""Bounded bridge from the Economics plugin to the canonical native trainer.

The plugin API owns ``CompositeState`` and ``CompositeExecutor`` while the
canonical actor-critic trainer owns ``GlobalState`` and ``PureExecutor``.  This
module is deliberately narrow: it admits exactly one built-in Economics
domain, with no cross-domain interactions, and makes the native temporal
mechanism the policy-controlled seam.  The remaining Economics mechanisms are
still executed by the real ``CompositeExecutor`` after that policy action.

Unsupported composite profiles are rejected by the caller as
``bridge_pending``.  There is no duck-typed fallback and no second optimizer
loop here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from math import isfinite

import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.artifact import (
    AgentPolicyArtifact,
    load_policy_artifact,
    store_policy_artifact,
)
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.rewards import UtilityFunction
from polisyos.foundry.agent_sim.state import GlobalState, compute_aggregates
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.temporal_mechanisms import TemporalConsumptionMechanism
from polisyos.foundry.agent_sim.training import TrainingConfig, train_actor_critic_with_artifact
from polisyos.foundry.contracts.fidelity import FidelityLevel
from polisyos.foundry.plugins.composite import (
    CompositeExecutor,
    CompositeState,
    CompositeStateConfig,
)
from polisyos.foundry.plugins.core import DomainConfig
from polisyos.foundry.plugins.economics.plugin import EconomicsPlugin
from polisyos.foundry.plugins.economics.rewards import EconomicReward
from polisyos.foundry.plugins.economics.state import (
    EconomicAgentState,
    EconomicPolicyState,
    EconomicState,
)
from polisyos.foundry.runtime.fingerprint import DeterminismTier

ECONOMICS_DOMAIN = "economics"
_ECONOMICS_MECHANISMS = (
    "labor_market",
    "taxation",
    "transfers",
    "consumption",
    "savings",
)
_ECONOMICS_MECHANISM_SET = frozenset(_ECONOMICS_MECHANISMS)
_DEFAULT_WAGE_GROWTH_RATE = 0.02


class TrainingBridgeError(ValueError):
    """A supported profile could not produce a truthful training result."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BridgeAssessment:
    """Machine-readable admission result for the bounded bridge."""

    code: str
    message: str


@dataclass(frozen=True)
class AdapterTrainingOutcome:
    """Training output kept separate from the public plugin result type."""

    trained_policy: ActorCritic
    loss_history: list[float]
    final_state: CompositeState
    artifact: AgentPolicyArtifact[ActorCritic]
    artifact_refs: tuple[ArtifactRef, ArtifactRef] | None


class _EconomicsTemporalConsumptionMechanism(TemporalConsumptionMechanism):
    """Run native policy consumption, then the real Economics transition.

    The subclass intentionally remains a ``TemporalConsumptionMechanism`` so
    the native trainer resolves the same PRNG salt for trajectory actions and
    executor actions.  It is one mechanism from the native scheduler's point
    of view, which avoids declaring a false read/write ordering between the
    policy's wealth write and the Economics mechanisms' wealth reads.
    """

    def __init__(
        self,
        *,
        actor_critic: ActorCritic,
        horizon: int,
        include_expectations: bool,
        bridge_executor: CompositeExecutor,
        bridge_config: CompositeStateConfig,
        n_agents: int,
        max_agents: int,
        wage_growth_rate: float,
    ) -> None:
        super().__init__(
            actor_critic=actor_critic,
            horizon=horizon,
            include_expectations=include_expectations,
        )
        object.__setattr__(self, "_bridge_executor", bridge_executor)
        object.__setattr__(self, "_bridge_config", bridge_config)
        object.__setattr__(self, "_n_agents", int(n_agents))
        object.__setattr__(self, "_max_agents", int(max_agents))
        object.__setattr__(self, "_wage_growth_rate", float(wage_growth_rate))

    def apply(self, state, rng_key, fidelity: FidelityLevel):
        before = _native_to_composite(
            state,
            config=self._bridge_config,
            n_agents=self._n_agents,
            max_agents=self._max_agents,
            wage_growth_rate=self._wage_growth_rate,
        )
        policy_state, metrics = super().apply(state, rng_key, fidelity)
        after_policy = _native_to_composite(
            policy_state,
            config=self._bridge_config,
            n_agents=self._n_agents,
            max_agents=self._max_agents,
            wage_growth_rate=self._wage_growth_rate,
        )

        _, bridge_key = jax.random.split(rng_key)
        after = self._bridge_executor.step(after_policy, bridge_key)
        native_state = _composite_to_native(after, policy_state)
        native_state = native_state.replace(
            agents=native_state.agents.replace(
                utility_adjustment=_economic_reward_correction(before, after, native_state)
            )
        )
        return native_state, metrics


def _economic_reward_correction(
    before: CompositeState,
    after: CompositeState,
    native_after: GlobalState,
) -> jnp.ndarray:
    """Make the native reward equal the admitted Economics reward exactly."""

    economic_before = before.get_domain(ECONOMICS_DOMAIN)
    economic_after = after.get_domain(ECONOMICS_DOMAIN)
    target_reward = EconomicReward().compute(economic_before, economic_after)

    agents = native_after.agents
    native_utility = UtilityFunction.crra(agents.consumption, agents.risk_aversion)
    native_wealth_bonus = 0.01 * jnp.log(jnp.maximum(agents.wealth, 1.0))
    bankruptcy_penalty = -10.0 * (agents.wealth < 0.1).astype(jnp.float32)
    native_without_adjustment = native_utility + native_wealth_bonus + bankruptcy_penalty
    return jnp.where(
        agents.active,
        target_reward - native_without_adjustment,
        jnp.zeros_like(target_reward),
    )


def _native_to_composite(
    state: GlobalState,
    *,
    config: CompositeStateConfig,
    n_agents: int,
    max_agents: int,
    wage_growth_rate: float,
) -> CompositeState:
    """Project the complete native training state into EconomicState."""

    native_agents = state.agents
    # AgentState has no wage or hours_worked fields.  The bounded temporal
    # executor leaves savings_target and education_years untouched, so they
    # provide lossless per-agent transport slots for the Economics bridge.
    economic_agents = EconomicAgentState(
        active=native_agents.active,
        age=native_agents.age,
        skill_level=native_agents.skill_level,
        wealth=native_agents.wealth,
        income=native_agents.income,
        consumption=native_agents.consumption,
        savings=native_agents.savings,
        employed=native_agents.employed,
        wage=native_agents.savings_target,
        hours_worked=native_agents.education_years,
        discount_rate=native_agents.discount_factor,
        risk_aversion=native_agents.risk_aversion,
        consumption_preference=native_agents.consumption_target,
    )
    economic_policy = EconomicPolicyState(
        tax_rate=state.policy.tax_rate,
        transfer_rate=state.policy.transfer_rate,
        interest_rate=state.policy.interest_rate,
        unemployment_benefit=native_agents.debt[0],
        minimum_wage=native_agents.information_level[0],
    )
    economic_state = EconomicState(
        agents=economic_agents,
        policy=economic_policy,
        distributions=EconomicState._compute_distributions(economic_agents),
        aggregates=EconomicState._compute_aggregates(economic_agents),
        time_step=state.time_step,
        n_agents=n_agents,
        max_agents=max_agents,
    )
    del wage_growth_rate
    return CompositeState(
        domain_states={ECONOMICS_DOMAIN: economic_state},
        time_step=state.time_step,
        config=config,
    )


def _composite_to_native(state: CompositeState, template: GlobalState) -> GlobalState:
    """Project Economics output back without losing native trainer fields."""

    economic_state = state.get_domain(ECONOMICS_DOMAIN)
    economic_agents = economic_state.agents
    native_agents = template.agents.replace(
        active=economic_agents.active,
        age=economic_agents.age,
        skill_level=economic_agents.skill_level,
        wealth=economic_agents.wealth,
        income=economic_agents.income,
        consumption=economic_agents.consumption,
        savings=economic_agents.savings,
        employed=economic_agents.employed,
        discount_factor=economic_agents.discount_rate,
        risk_aversion=economic_agents.risk_aversion,
        consumption_target=economic_agents.consumption_preference,
        education_years=economic_agents.hours_worked,
        savings_target=economic_agents.wage,
    )
    native_policy = template.policy.replace(
        tax_rate=economic_state.policy.tax_rate,
        transfer_rate=economic_state.policy.transfer_rate,
        interest_rate=economic_state.policy.interest_rate,
        expected_interest_rate=economic_state.policy.interest_rate,
    )
    native_agents = native_agents.replace(
        debt=jnp.full_like(native_agents.debt, economic_state.policy.unemployment_benefit),
        information_level=jnp.full_like(
            native_agents.information_level,
            economic_state.policy.minimum_wage,
        ),
    )
    return template.replace(
        agents=native_agents,
        policy=native_policy,
        aggregates=compute_aggregates(native_agents),
    )


class EconomicsTrainingAdapter:
    """Admit and execute the one-domain Economics training profile."""

    def __init__(self, state: CompositeState, executor: CompositeExecutor) -> None:
        self.state = state
        self.executor = executor
        self.domain_config: DomainConfig = state.config.domains[ECONOMICS_DOMAIN]
        economic_state = state.get_domain(ECONOMICS_DOMAIN)
        self.n_agents = int(economic_state.n_agents)
        self.max_agents = int(economic_state.max_agents)
        self.wage_growth_rate = float(
            self.domain_config.mechanism_configs.get("labor_market", {}).get(
                "wage_growth_rate",
                _DEFAULT_WAGE_GROWTH_RATE,
            )
        )

        bridge_domain_config = replace(
            self.domain_config,
            enabled_mechanisms=tuple(
                name for name in _ECONOMICS_MECHANISMS if name != "consumption"
            ),
        )
        bridge_domains = dict(state.config.domains)
        bridge_domains[ECONOMICS_DOMAIN] = bridge_domain_config
        self.bridge_config = replace(state.config, domains=bridge_domains)
        self.bridge_executor = CompositeExecutor(
            executor.execution_order,
            executor.registry,
        )

    @classmethod
    def assess(
        cls,
        state: CompositeState | None,
        executor: CompositeExecutor | None,
    ) -> BridgeAssessment | None:
        """Return a typed rejection reason, or ``None`` when profile is valid."""

        if not isinstance(state, CompositeState) or not isinstance(executor, CompositeExecutor):
            return BridgeAssessment(
                "training_execution_adapter_missing",
                "Training requires the real CompositeState and CompositeExecutor.",
            )
        if set(state.domain_states) != {ECONOMICS_DOMAIN}:
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "The bounded bridge admits exactly one Economics domain.",
            )
        if executor.execution_order != (ECONOMICS_DOMAIN,):
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "The bounded bridge requires one Economics execution order.",
            )
        if state.config.interactions:
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Cross-domain interactions are not admitted by this bridge.",
            )
        domain_config = state.config.domains.get(ECONOMICS_DOMAIN)
        if domain_config is None:
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Economics domain configuration is missing.",
            )
        configured = set(domain_config.enabled_mechanisms)
        if configured and configured != _ECONOMICS_MECHANISM_SET:
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "All built-in Economics mechanisms must remain enabled for training.",
            )
        if not set(domain_config.mechanism_configs).issubset(_ECONOMICS_MECHANISM_SET):
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Unknown Economics mechanism configuration cannot be bridged.",
            )
        if not isinstance(state.get_domain(ECONOMICS_DOMAIN), EconomicState):
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Only the built-in EconomicState has a checked projection.",
            )
        if not isinstance(executor.registry.get(ECONOMICS_DOMAIN), EconomicsPlugin):
            return BridgeAssessment(
                "training_composite_profile_unsupported",
                "Only the built-in EconomicsPlugin has a checked projection.",
            )
        return None

    @classmethod
    def from_composite(
        cls,
        state: CompositeState | None,
        executor: CompositeExecutor | None,
    ) -> EconomicsTrainingAdapter | None:
        """Build the adapter only after all profile predicates pass."""

        if cls.assess(state, executor) is not None:
            return None
        assert state is not None
        assert executor is not None
        return cls(state, executor)

    def to_native_state(
        self,
        *,
        seed: int,
        state: CompositeState | None = None,
    ) -> GlobalState:
        """Project a composite snapshot into the native trainer state."""

        source = state or self.state
        native = GlobalState.empty(
            n_agents=self.n_agents,
            max_agents=self.max_agents,
            seed=seed,
            simulation_horizon=self.domain_config.time_horizon,
        )
        economic_state = source.get_domain(ECONOMICS_DOMAIN)
        native_agents = native.agents.replace(
            active=economic_state.agents.active,
            age=economic_state.agents.age,
            skill_level=economic_state.agents.skill_level,
            wealth=economic_state.agents.wealth,
            income=economic_state.agents.income,
            consumption=economic_state.agents.consumption,
            savings=economic_state.agents.savings,
            employed=economic_state.agents.employed,
            discount_factor=economic_state.agents.discount_rate,
            risk_aversion=economic_state.agents.risk_aversion,
            consumption_target=economic_state.agents.consumption_preference,
            education_years=economic_state.agents.hours_worked,
            savings_target=economic_state.agents.wage,
            expected_income_growth=jnp.full_like(
                native.agents.expected_income_growth,
                self.wage_growth_rate,
            ),
            debt=jnp.full_like(native.agents.debt, economic_state.policy.unemployment_benefit),
            information_level=jnp.full_like(
                native.agents.information_level,
                economic_state.policy.minimum_wage,
            ),
        )
        native_policy = native.policy.replace(
            tax_rate=economic_state.policy.tax_rate,
            transfer_rate=economic_state.policy.transfer_rate,
            interest_rate=economic_state.policy.interest_rate,
            expected_interest_rate=economic_state.policy.interest_rate,
        )
        return native.replace(
            agents=native_agents,
            policy=native_policy,
            aggregates=compute_aggregates(native_agents),
            time_step=source.time_step,
        )

    def make_executor(self, actor: ActorCritic, config: TrainingConfig) -> PureExecutor:
        """Create the canonical PureExecutor with the checked bridge seam."""

        mechanism = _EconomicsTemporalConsumptionMechanism(
            actor_critic=actor,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
            bridge_executor=self.bridge_executor,
            bridge_config=self.bridge_config,
            n_agents=self.n_agents,
            max_agents=self.max_agents,
            wage_growth_rate=self.wage_growth_rate,
        )
        return PureExecutor([mechanism], prng_config={mechanism.spec.name: 0})

    def observation_dim(self, config: TrainingConfig) -> int:
        """Return the native temporal observation width for this profile."""

        native_state = self.to_native_state(seed=0)
        observations = build_temporal_observations(
            native_state,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
        )
        return int(observations.shape[-1])

    def run(
        self,
        actor: ActorCritic,
        config: TrainingConfig,
        *,
        seed: int,
        state: CompositeState | None = None,
        n_steps: int | None = None,
    ) -> tuple[CompositeState, list[CompositeState]]:
        """Run a deterministic evaluation/continuation using the trained actor."""

        source = state or self.state
        native_state = self.to_native_state(seed=seed, state=source)
        executor = self.make_executor(actor, config)
        states = [source]
        for _ in range(config.steps_per_episode if n_steps is None else int(n_steps)):
            native_state, _ = executor.step(native_state, fidelity=config.fidelity)
            states.append(
                _native_to_composite(
                    native_state,
                    config=source.config,
                    n_agents=self.n_agents,
                    max_agents=self.max_agents,
                    wage_growth_rate=self.wage_growth_rate,
                )
            )
        return states[-1], states

    def train(
        self,
        actor: ActorCritic,
        config: TrainingConfig,
        *,
        seed: int,
        artifact_store: ArtifactStore | None = None,
    ) -> AdapterTrainingOutcome:
        """Run the existing native optimizer and persist/read back its artifact."""

        if config.utility_type != "crra":
            raise TrainingBridgeError(
                "training_utility_profile_unsupported",
                "The Economics reward bridge is admitted only for CRRA training.",
            )
        if config.n_episodes <= 0 or config.steps_per_episode <= 0 or config.ppo_epochs <= 0:
            raise TrainingBridgeError(
                "training_update_not_observed",
                "Training requires positive episodes, rollout steps, and PPO epochs.",
            )

        initial_state = self.to_native_state(seed=seed)
        trained_policy, metrics, artifact = train_actor_critic_with_artifact(
            actor,
            initial_state,
            config,
            make_executor=lambda current_actor: self.make_executor(current_actor, config),
            run_id=f"plugins-{ECONOMICS_DOMAIN}-{seed}",
            tier=DeterminismTier.STRICT_CPU,
            seed=seed,
        )
        parameter_delta = _parameter_delta(actor, trained_policy)
        action_delta = _action_delta(actor, trained_policy, initial_state, config)
        if not jnp.isfinite(parameter_delta) or float(parameter_delta) <= 0.0:
            raise TrainingBridgeError(
                "training_update_not_observed",
                "Native optimizer completed without an observable parameter update.",
            )
        if not jnp.isfinite(action_delta) or float(action_delta) <= 0.0:
            raise TrainingBridgeError(
                "training_action_effect_not_observed",
                "Native policy update did not change the next action.",
            )

        artifact_refs: tuple[ArtifactRef, ArtifactRef] | None = None
        if artifact_store is not None:
            artifact_refs = store_policy_artifact(
                artifact_store, _artifact_for_cas(artifact)
            )
            trained_policy, _ = load_policy_artifact(
                artifact_store,
                artifact_refs[1],
                actor,
                DeterminismTier.STRICT_CPU,
                seed,
                strict=True,
            )
        else:
            trained_policy = artifact.load_weights(actor)

        final_state, _ = self.run(
            trained_policy,
            config,
            seed=seed,
            n_steps=config.steps_per_episode,
        )
        losses = [float(value) for value in jnp.asarray(metrics["loss_history"])]
        return AdapterTrainingOutcome(
            trained_policy=trained_policy,
            loss_history=losses,
            final_state=final_state,
            artifact=artifact,
            artifact_refs=artifact_refs,
        )


def _artifact_for_cas(
    artifact: AgentPolicyArtifact[ActorCritic],
) -> AgentPolicyArtifact[ActorCritic]:
    """Prepare artifact metrics for the strict canonical CAS profile.

    The native artifact producer records training metrics as runtime floats,
    while the shared CAS profile represents persisted real numbers as
    ``Decimal`` tagged values.  Keep the runtime artifact unchanged and use a
    storage-only dataclass copy so readback still goes through the existing
    ``store_policy_artifact`` contract.
    """

    metrics = artifact.metrics
    return replace(
        artifact,
        metrics=replace(
            metrics,
            final_loss=_canonical_metric(metrics.final_loss),
            best_loss=_canonical_metric(metrics.best_loss),
            wall_clock_seconds=_canonical_metric(metrics.wall_clock_seconds),
            gpu_hours=_canonical_metric(metrics.gpu_hours),
            learning_rate=_canonical_metric(metrics.learning_rate),
        ),
    )


def _canonical_metric(value: float | None) -> Decimal | None:
    """Encode a finite runtime metric using the canonical Decimal form."""

    if value is None:
        return None
    if not isfinite(value):
        raise TrainingBridgeError(
            "training_artifact_metric_nonfinite",
            "Training artifact metrics must be finite before canonical persistence.",
        )
    return Decimal(str(value))


def _parameter_delta(before: ActorCritic, after: ActorCritic) -> jnp.ndarray:
    """Sum absolute changes over all trainable actor parameters."""

    before_params = eqx.filter(before, eqx.is_inexact_array)
    after_params = eqx.filter(after, eqx.is_inexact_array)
    deltas = jax.tree_util.tree_leaves(
        jax.tree_util.tree_map(
            lambda left, right: jnp.sum(jnp.abs(left - right)),
            before_params,
            after_params,
        )
    )
    return jnp.sum(jnp.stack(deltas))


def _action_delta(
    before: ActorCritic,
    after: ActorCritic,
    initial_state: GlobalState,
    config: TrainingConfig,
) -> jnp.ndarray:
    """Measure whether the learned actor changes the next native action."""

    obs = build_temporal_observations(
        initial_state,
        horizon=config.horizon,
        include_expectations=config.include_expectations,
    )
    before_action, _ = before(obs, deterministic=True)
    after_action, _ = after(obs, deterministic=True)
    return jnp.max(jnp.abs(after_action - before_action))


__all__ = [
    "AdapterTrainingOutcome",
    "BridgeAssessment",
    "EconomicsTrainingAdapter",
    "TrainingBridgeError",
]
