"""Public agent sim temporal mechanisms module API."""

from __future__ import annotations

from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

import chex
import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.actor_critic import ActorCritic, compute_log_prob, sample_actions
from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.contracts.fidelity import FidelityLevel

if TYPE_CHECKING:
    from polisyos.foundry.agent_sim.executor import PureExecutor


_TEMPORAL_DECISION_METRIC = "policy_decision"


class _UnsupportedPolicyExecutorError(ValueError):
    """Refuse a policy-training request without a single applied policy decision."""

    code = "training_policy_executor_unsupported"


def _require_temporal_policy_executor(executor: PureExecutor) -> None:
    """Require the one temporal action consumer represented by a PPO trajectory."""
    count = sum(
        isinstance(mechanism, TemporalConsumptionMechanism) for mechanism in executor.mechanisms
    )
    if count != 1:
        raise _UnsupportedPolicyExecutorError(
            "Policy training requires exactly one actual TemporalConsumptionMechanism. "
            "Value/GAE utilities and ordinary evaluation remain available independently."
        )


class _TemporalPolicyDecision(NamedTuple):
    """Capture the policy inputs and actual action at the execution boundary."""

    observations: jax.Array
    actions: jax.Array
    log_probs: jax.Array
    values: jax.Array
    active: jax.Array
    sampled_law: jax.Array


def _temporal_policy_decision(
    actor: ActorCritic,
    state: GlobalState,
    rng_key: chex.PRNGKey,
    fidelity: FidelityLevel,
    *,
    horizon: int,
    include_expectations: bool,
    capture: bool = True,
) -> _TemporalPolicyDecision:
    """Evaluate one actual temporal decision without replaying an executor prefix."""
    observations = build_temporal_observations(
        state, horizon=horizon, include_expectations=include_expectations
    )
    if capture:
        # A training view excludes padding from the computation, not from the
        # stored state. Active malformed values are deliberately untouched.
        observations = jnp.where(state.agents.active[:, None], observations, 0.0)
    output, values = actor(observations, deterministic=True)
    if fidelity == FidelityLevel.HARD_DISCRETE:
        actions = output
        log_probs = jnp.zeros_like(values)
        sampled_law = False
    else:
        distribution = actor.get_action_distribution(observations, action_output=output)
        actions = sample_actions(distribution, rng_key, action_type=actor.action_type)
        log_probs = (
            compute_log_prob(actions, distribution, action_type=actor.action_type)
            if capture
            else jnp.zeros_like(values)
        )
        sampled_law = True
    return _TemporalPolicyDecision(
        observations,
        actions,
        log_probs,
        values,
        state.agents.active,
        jnp.asarray(sampled_law, dtype=jnp.bool_),
    )


def _capture_temporal_decisions(executor: PureExecutor) -> PureExecutor:
    """Create a training view without changing the caller's executor or mechanisms."""
    _require_temporal_policy_executor(executor)
    captured = copy(executor)
    mechanisms = []
    for mechanism in executor.mechanisms:
        if isinstance(mechanism, TemporalConsumptionMechanism):
            mechanism = copy(mechanism)
            object.__setattr__(mechanism, "_capture_policy_decision", True)
        mechanisms.append(mechanism)
    captured.mechanisms = mechanisms
    return captured


def _read_temporal_decision(
    metrics: Mapping[str, object], metric_prefix: str
) -> _TemporalPolicyDecision:
    """Read the complete producer-owned decision from training-only array metrics."""
    values = [metrics.get(f"{metric_prefix}_{field}") for field in _TemporalPolicyDecision._fields]
    if any(value is None for value in values):
        raise ValueError("Temporal executor did not capture its actual policy decision")
    return _TemporalPolicyDecision(*values)


def _next_temporal_observations(
    executor: PureExecutor, state: GlobalState, fidelity: FidelityLevel
) -> tuple[jax.Array, jax.Array]:
    """Observe the next actual policy context without applying its action or advancing time."""
    _require_temporal_policy_executor(executor)
    mechanism = next(
        mechanism
        for mechanism in executor.mechanisms
        if isinstance(mechanism, TemporalConsumptionMechanism)
    )
    before_policy, _ = executor._execute_prefix(state, fidelity, stop_before=mechanism)
    observations = build_temporal_observations(
        before_policy,
        horizon=mechanism.horizon,
        include_expectations=mechanism.include_expectations,
    )
    active = before_policy.agents.active
    return jnp.where(active[:, None], observations, 0.0), active


def _temporal_consumption_metrics(
    consumption: jnp.ndarray,
    values: jnp.ndarray,
    consumption_fraction: jnp.ndarray,
    active: jnp.ndarray,
) -> dict[str, jnp.ndarray]:
    """Build the producer-owned metrics mapping for a temporal step."""
    active_count = jnp.sum(active)
    safe_count = jnp.maximum(active_count, 1.0)
    return {
        "mean_consumption": jnp.sum(consumption) / safe_count,
        "mean_value": jnp.sum(jnp.where(active, values, 0.0)) / safe_count,
        "mean_consumption_fraction": jnp.sum(jnp.where(active, consumption_fraction, 0.0))
        / safe_count,
    }


def _empty_temporal_consumption_metrics(
    state: GlobalState, *, decision_template: _TemporalPolicyDecision | None = None
) -> dict[str, jnp.ndarray]:
    """Build the zero metrics tree from the temporal producer's metric owner."""
    metric_dtype = jnp.result_type(state.agents.wealth.dtype, jnp.asarray(0.0).dtype)
    zero = jnp.asarray(0.0, dtype=metric_dtype)
    metrics = _temporal_consumption_metrics(
        consumption=zero,
        values=zero,
        consumption_fraction=zero,
        active=jnp.asarray(False, dtype=jnp.bool_),
    )
    if decision_template is not None:
        metrics.update(
            {
                f"{_TEMPORAL_DECISION_METRIC}_{field}": jnp.zeros(value.shape, dtype=value.dtype)
                for field, value in zip(
                    _TemporalPolicyDecision._fields, decision_template, strict=True
                )
            }
        )
    return metrics


@dataclass(frozen=True)
class TemporalConsumptionMechanism(Mechanism):
    """Temporal consumption mechanism public type."""

    actor_critic: ActorCritic
    horizon: int = 256
    min_consumption: float = 0.01
    include_expectations: bool = True
    _capture_policy_decision: bool = False

    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="temporal_consumption",
            reads=frozenset(
                {
                    "agents.wealth",
                    "agents.income",
                    "agents.active",
                    "agents.risk_aversion",
                    "agents.discount_factor",
                    "agents.age",
                    "agents.expected_income_growth",
                    "policy.interest_rate",
                    "policy.expected_interest_rate",
                }
            ),
            writes=frozenset(
                {"agents.consumption", "agents.wealth", "agents.expected_lifetime_utility"}
            ),
            parameters={"horizon": int, "min_consumption": float},
            stochastic=True,
        )

    def apply(
        self,
        state: GlobalState,
        rng_key: chex.PRNGKey,
        fidelity: FidelityLevel,
    ) -> tuple[GlobalState, dict[str, jnp.ndarray]]:
        agents = state.agents
        decision = _temporal_policy_decision(
            self.actor_critic,
            state,
            rng_key,
            fidelity,
            horizon=self.horizon,
            include_expectations=self.include_expectations,
            capture=self._capture_policy_decision,
        )
        sampled_actions = decision.actions
        values = decision.values

        if sampled_actions.ndim == 2:
            sampled_actions = sampled_actions[:, 0]
        consumption_fraction = jax.nn.sigmoid(sampled_actions)

        if self._capture_policy_decision:
            budget = jnp.where(agents.active, agents.wealth, 0.0) + jnp.where(
                agents.active, agents.income, 0.0
            )
        else:
            budget = agents.wealth + agents.income
        consumption = consumption_fraction * budget
        consumption = jnp.maximum(consumption, self.min_consumption)
        new_wealth = jnp.maximum(budget - consumption, 0.0)

        active = agents.active
        consumption = jnp.where(active, consumption, 0.0)
        new_wealth = jnp.where(active, new_wealth, agents.wealth)
        new_values = jnp.where(active, values, agents.expected_lifetime_utility)

        # Neural outputs may use a wider parameter dtype than the simulation
        # carry. Preserve the declared state fields at this transition boundary.
        new_agents = agents.replace(
            consumption=consumption.astype(agents.consumption.dtype),
            wealth=new_wealth.astype(agents.wealth.dtype),
            expected_lifetime_utility=new_values.astype(agents.expected_lifetime_utility.dtype),
        )

        metrics = _temporal_consumption_metrics(
            consumption=consumption,
            values=values,
            consumption_fraction=consumption_fraction,
            active=active,
        )
        if self._capture_policy_decision:
            metrics.update(
                {
                    f"{_TEMPORAL_DECISION_METRIC}_{field}": value
                    for field, value in zip(_TemporalPolicyDecision._fields, decision, strict=True)
                }
            )
        return state.replace(agents=new_agents), metrics
