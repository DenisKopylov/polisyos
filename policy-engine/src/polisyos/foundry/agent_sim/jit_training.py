"""Public agent sim jit training module API."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import NamedTuple

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.foundry.agent_sim.actor_critic import ActorCritic, compute_log_prob, sample_actions
from polisyos.foundry.agent_sim.credit_assignment import CreditConfig, compute_credit_assignment
from polisyos.foundry.agent_sim.distributions import (
    _GINI_POPULATION_STATUS_METRIC,
    GiniPopulationProfile,
    _GiniPopulationStatus,
    active_gini_population_supported,
)
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.metrics import (
    MetricDefinition,
    MetricsBuffer,
    MetricsCollector,
    MetricType,
    _safe_histogram_bins,
    standard_training_metrics,
    training_loss_metrics,
)
from polisyos.foundry.agent_sim.prng import get_mechanism_key
from polisyos.foundry.agent_sim.rewards import compute_agent_reward
from polisyos.foundry.agent_sim.rl import (
    Trajectory,
    _zero_ppo_loss_metrics,
    compute_returns_and_advantages,
    ppo_loss,
)
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.temporal_mechanisms import TemporalConsumptionMechanism
from polisyos.foundry.agent_sim.training_config import TrainingConfigBase


def _require_exact_bool_selector(value: object, selector_name: str) -> bool:
    """Return an exact bool or reject a malformed behavior selector.

    Args:
        value: Value supplied to a boolean configuration or function selector.
        selector_name: Source name used in the typed error.

    Returns:
        The supplied boolean value.

    Raises:
        TypeError: If ``value`` is not exactly ``bool``.
    """
    if type(value) is not bool:
        raise TypeError(f"{selector_name} must be a bool")
    return value


@dataclass(frozen=True)
class JITTrainingConfig(TrainingConfigBase):
    """Configure the fully JIT-compiled actor-critic training loop."""

    credit_config: CreditConfig | None = None
    collect_metrics: bool = True
    metrics_frequency: int = 1
    track_active_wealth: bool = False
    gini_population_profile: GiniPopulationProfile | None = None

    def __post_init__(self) -> None:
        """Require exact selectors, a typed profile, and an enabled monitor."""
        _require_exact_bool_selector(self.track_active_wealth, "track_active_wealth")
        if (
            self.gini_population_profile is not None
            and type(self.gini_population_profile) is not GiniPopulationProfile
        ):
            raise TypeError("gini_population_profile must be a source-defined profile")
        if self.gini_population_profile is not None and not self.track_active_wealth:
            raise ValueError("a selected Gini population profile requires track_active_wealth=True")


@dataclass(frozen=True)
class _ActiveWealthTrajectoryValidation:
    """Record the complete active-wealth scan observed by a native training run."""

    initial_state_checked: bool
    episodes_checked: int
    transitions_checked: int
    active_wealth_supported: bool


class _ActiveWealthTrajectoryValidationError(RuntimeError):
    """Refuse an unsupported or incomplete active-wealth training trajectory."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _NativeExecutionValidationError(RuntimeError):
    """Report a native Equinox validation guard without guessing its predicate."""

    code = "native_execution_validation_refused"

    def __init__(self) -> None:
        super().__init__(
            "Native execution stopped at a validation guard; the trainer does not classify "
            "that guard's predicate."
        )


def _native_execution_validation_error() -> _NativeExecutionValidationError:
    """Build a generic refusal without parsing a native Equinox guard's message."""

    return _NativeExecutionValidationError()


def _active_wealth_supported(state: GlobalState) -> jnp.ndarray:
    """Preserve the legacy monitor's wealth-only population semantics."""

    return active_gini_population_supported(
        state.agents.active,
        state.agents.wealth,
    )


def _tracked_population_supported(
    state: GlobalState,
    profile: GiniPopulationProfile | None,
) -> jnp.ndarray:
    """Recompute the active resources selected by the typed training profile."""
    if profile is None:
        return _active_wealth_supported(state)
    if type(profile) is not GiniPopulationProfile:
        raise TypeError("gini_population_profile must be a source-defined profile")
    if profile is GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1:
        return active_gini_population_supported(
            state.agents.active,
            state.agents.wealth,
            state.agents.income,
        )
    raise ValueError("unsupported Gini population profile")


def _selected_profile_status_supported(
    step_metrics: dict[str, object],
    profile: GiniPopulationProfile | None,
) -> jnp.ndarray:
    """Read only the source-owned typed status for the selected bridge profile."""
    status = step_metrics.get(f"temporal_consumption/{_GINI_POPULATION_STATUS_METRIC}")
    if profile is None:
        return jnp.asarray(status is None, dtype=jnp.bool_)
    if type(status) is not _GiniPopulationStatus or status.profile is not profile:
        return jnp.asarray(False, dtype=jnp.bool_)
    return jnp.asarray(status.supported, dtype=jnp.bool_)


class TrainingCarry(NamedTuple):
    """Training carry public type."""

    params: object
    opt_state: optax.OptState
    rng_key: jax.Array
    best_loss: jnp.ndarray
    episode_losses: jnp.ndarray
    metrics_collector: MetricsCollector


class _TrainingCarryState(NamedTuple):
    """Private scan state that keeps validation out of the public carry ABI."""

    training: TrainingCarry
    active_wealth_supported: jnp.ndarray


class TrainingMetricsCarry(NamedTuple):
    """JAX-friendly carry for metric-enabled training."""

    params: object
    opt_state: optax.OptState
    rng_key: jax.Array
    best_loss: jnp.ndarray
    episode_losses: jnp.ndarray
    metrics_buffer: MetricsBuffer
    metrics_step_counter: jnp.ndarray
    active_wealth_supported: jnp.ndarray


def _training_loss_dtype(
    evaluate_loss: Callable[[jax.Array], jnp.ndarray], rng_key: jax.Array
) -> jnp.dtype:
    """Derive storage from the actual abstract rollout/PPO result, without draws."""
    return jax.eval_shape(evaluate_loss, rng_key).dtype


def create_jit_trainer(
    actor_critic: ActorCritic,
    executor_factory: Callable[[ActorCritic], PureExecutor],
    initial_state: GlobalState,
    config: JITTrainingConfig,
) -> Callable[[jax.Array], tuple[ActorCritic, dict]]:
    """Create jit trainer."""
    params, static = eqx.partition(actor_critic, eqx.is_inexact_array)

    probe_executor = executor_factory(actor_critic)
    temporal_salt = _resolve_temporal_salt(probe_executor)

    optimizer = optax.chain(
        optax.clip_by_global_norm(config.max_grad_norm),
        optax.adam(config.learning_rate),
    )
    dummy_collector = MetricsCollector((), max_history=1)

    def _collect_trajectory_jit(
        actor_params: object,
        state: GlobalState,
        rng_key: jax.Array,
    ) -> tuple[Trajectory, GlobalState, jnp.ndarray]:
        actor = eqx.combine(static, actor_params)
        executor = executor_factory(actor)

        def _run_step(cur_state: GlobalState, cur_key: jax.Array):
            key_action, key_credit, next_key = jax.random.split(cur_key, 3)

            obs = build_temporal_observations(
                cur_state,
                horizon=config.horizon,
                include_expectations=config.include_expectations,
            )
            action_out, value = actor(obs, deterministic=True)
            dist = actor.get_action_distribution(obs, action_output=action_out)

            if temporal_salt is None:
                action_key = key_action
            else:
                action_key = get_mechanism_key(
                    cur_state.rng_key,
                    cur_state.time_step,
                    temporal_salt,
                )

            action = sample_actions(dist, action_key, action_type=actor.action_type)
            if actor.action_type == "continuous" and action.ndim == 1:
                action = action[:, None]
            log_prob = compute_log_prob(action, dist, action_type=actor.action_type)

            next_state, step_metrics = executor.step(cur_state, fidelity=config.fidelity)
            transition_supported = jnp.asarray(True)
            if config.track_active_wealth:
                transition_supported = _tracked_population_supported(
                    next_state,
                    config.gini_population_profile,
                )
                transition_supported = transition_supported & _selected_profile_status_supported(
                    step_metrics,
                    config.gini_population_profile,
                )

                def _supported_reward(_):
                    reward_value = compute_agent_reward(
                        cur_state,
                        next_state,
                        utility_type=config.utility_type,
                    )
                    if config.credit_config is not None:
                        reward_value = compute_credit_assignment(
                            reward_value,
                            cur_state,
                            next_state,
                            config.credit_config,
                            rng_key=key_credit,
                        )
                    return reward_value

                reward = jax.lax.cond(
                    transition_supported,
                    _supported_reward,
                    lambda _: jnp.zeros_like(cur_state.agents.wealth),
                    operand=None,
                )
                next_state = jax.lax.cond(
                    transition_supported,
                    lambda _: next_state,
                    lambda _: cur_state,
                    operand=None,
                )
            else:
                reward = compute_agent_reward(
                    cur_state,
                    next_state,
                    utility_type=config.utility_type,
                )
                if config.credit_config is not None:
                    reward = compute_credit_assignment(
                        reward,
                        cur_state,
                        next_state,
                        config.credit_config,
                        rng_key=key_credit,
                    )

            transition = {
                "obs": obs,
                "action": action,
                "reward": reward,
                "value": value,
                "log_prob": log_prob,
                "active": cur_state.agents.active,
            }
            if config.track_active_wealth:
                transition["active_wealth_supported"] = transition_supported
            return next_state, next_key, transition, transition_supported

        def step_fn(carry, _):
            if not config.track_active_wealth:
                cur_state, cur_key = carry
                next_state, next_key, transition, _ = _run_step(cur_state, cur_key)
                return (next_state, next_key), transition

            cur_state, cur_key, prior_supported = carry

            def _execute(_operand):
                next_state, next_key, transition, transition_supported = _run_step(
                    cur_state,
                    cur_key,
                )
                return (next_state, next_key, transition_supported), transition

            def _terminal(_operand):
                n_agents = cur_state.agents.active.shape[0]
                observation_width = build_temporal_observations(
                    state,
                    horizon=config.horizon,
                    include_expectations=config.include_expectations,
                ).shape[-1]
                dtype = cur_state.agents.wealth.dtype
                action_shape = (
                    (n_agents, actor.action_dim)
                    if actor.action_type == "continuous"
                    else (n_agents,)
                )
                transition = {
                    "obs": jnp.zeros((n_agents, observation_width), dtype=dtype),
                    "action": jnp.zeros(action_shape, dtype=dtype),
                    "reward": jnp.zeros_like(cur_state.agents.wealth),
                    "value": jnp.zeros_like(cur_state.agents.wealth),
                    "log_prob": jnp.zeros_like(cur_state.agents.wealth),
                    "active": cur_state.agents.active,
                    "active_wealth_supported": jnp.asarray(False, dtype=jnp.bool_),
                }
                return (cur_state, cur_key, jnp.asarray(False)), transition

            return jax.lax.cond(prior_supported, _execute, _terminal, operand=None)

        initial_supported = (
            _tracked_population_supported(state, config.gini_population_profile)
            if config.track_active_wealth
            else jnp.asarray(True)
        )
        initial_carry = (
            (state, rng_key, initial_supported) if config.track_active_wealth else (state, rng_key)
        )
        final_carry, transitions = jax.lax.scan(
            step_fn,
            initial_carry,
            None,
            length=int(config.steps_per_episode),
        )
        final_state = final_carry[0]

        trajectory_supported = (
            initial_supported & jnp.all(transitions["active_wealth_supported"])
            if config.track_active_wealth
            else jnp.asarray(True)
        )
        final_state = jax.lax.cond(
            trajectory_supported,
            lambda current: current,
            lambda _: state,
            final_state,
        )

        final_obs = build_temporal_observations(
            final_state,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
        )

        trajectory = Trajectory(
            observations=transitions["obs"],
            actions=transitions["action"],
            rewards=transitions["reward"],
            values=transitions["value"],
            dones=jnp.zeros_like(transitions["reward"], dtype=jnp.bool_),
            log_probs=transitions["log_prob"],
            final_observation=final_obs,
            active_mask=transitions["active"],
        )
        return trajectory, final_state, trajectory_supported

    def _ppo_update_jit(
        actor_params: object,
        opt_state: optax.OptState,
        trajectory: Trajectory,
    ) -> tuple[object, optax.OptState, jnp.ndarray]:
        actor = eqx.combine(static, actor_params)
        _, final_value = actor(trajectory.final_observation, deterministic=True)
        returns, advantages = compute_returns_and_advantages(
            trajectory,
            final_value,
            gamma=config.gamma,
            gae_lambda=config.gae_lambda,
            active_mask=trajectory.active_mask,
        )

        def epoch_step(carry, _):
            cur_params, cur_opt_state = carry

            def loss_fn(p):
                actor_iter = eqx.combine(static, p)
                (loss, _metrics) = ppo_loss(
                    actor_iter,
                    trajectory,
                    advantages,
                    returns,
                    trajectory.log_probs,
                    clip_epsilon=config.clip_epsilon,
                    value_coef=config.value_coef,
                    entropy_coef=config.entropy_coef,
                    active_mask=trajectory.active_mask,
                )
                return loss

            loss_val, grads = jax.value_and_grad(loss_fn)(cur_params)
            updates, next_opt_state = optimizer.update(grads, cur_opt_state, cur_params)
            next_params = optax.apply_updates(cur_params, updates)
            return (next_params, next_opt_state), loss_val

        (final_params, final_opt_state), losses = jax.lax.scan(
            epoch_step,
            (actor_params, opt_state),
            None,
            length=int(config.ppo_epochs),
        )
        return final_params, final_opt_state, jnp.mean(losses)

    def _train_loop(rng_key: jax.Array) -> tuple[object, jnp.ndarray, jnp.ndarray]:
        opt_state = optimizer.init(params)
        loss_dtype = _training_loss_dtype(
            lambda key: _ppo_update_jit(
                params, opt_state, _collect_trajectory_jit(params, initial_state, key)[0]
            )[2],
            rng_key,
        )
        episode_losses = jnp.zeros((int(config.n_episodes),), dtype=loss_dtype)
        initial_training_carry = TrainingCarry(
            params=params,
            opt_state=opt_state,
            rng_key=rng_key,
            best_loss=jnp.array(jnp.inf, dtype=loss_dtype),
            episode_losses=episode_losses,
            metrics_collector=dummy_collector,
        )
        init_carry = _TrainingCarryState(
            training=initial_training_carry,
            active_wealth_supported=(
                _tracked_population_supported(initial_state, config.gini_population_profile)
                if config.track_active_wealth
                else jnp.asarray(True)
            ),
        )

        def episode_step(carry: _TrainingCarryState, idx):
            def _run_episode(current: _TrainingCarryState):
                training_carry = current.training
                key1, key2 = jax.random.split(training_carry.rng_key)
                trajectory, _, trajectory_supported = _collect_trajectory_jit(
                    training_carry.params,
                    initial_state,
                    key1,
                )

                def _update(_operand):
                    return _ppo_update_jit(
                        training_carry.params,
                        training_carry.opt_state,
                        trajectory,
                    )

                def _skip_update(_operand):
                    return (
                        training_carry.params,
                        training_carry.opt_state,
                        jnp.asarray(0.0, dtype=loss_dtype),
                    )

                new_params, new_opt_state, loss = jax.lax.cond(
                    trajectory_supported,
                    _update,
                    _skip_update,
                    operand=None,
                )
                losses = training_carry.episode_losses.at[idx].set(loss)
                best_loss = jnp.minimum(training_carry.best_loss, loss)
                new_training_carry = TrainingCarry(
                    params=new_params,
                    opt_state=new_opt_state,
                    rng_key=key2,
                    best_loss=best_loss,
                    episode_losses=losses,
                    metrics_collector=training_carry.metrics_collector,
                )
                new_carry = _TrainingCarryState(
                    training=new_training_carry,
                    active_wealth_supported=(
                        current.active_wealth_supported & trajectory_supported
                    ),
                )
                return new_carry, loss

            def _skip_episode(current: _TrainingCarryState):
                return current, jnp.asarray(0.0, dtype=loss_dtype)

            return jax.lax.cond(
                carry.active_wealth_supported,
                _run_episode,
                _skip_episode,
                carry,
            )

        final_carry, losses = jax.lax.scan(
            episode_step,
            init_carry,
            jnp.arange(int(config.n_episodes)),
        )
        return (
            final_carry.training.params,
            losses,
            final_carry.active_wealth_supported,
        )

    @eqx.filter_jit
    def _trainer_jit(
        rng_key: jax.Array,
    ) -> tuple[ActorCritic, dict, jnp.ndarray]:
        final_params, losses, active_wealth_supported = _train_loop(rng_key)
        trained_actor = eqx.combine(static, final_params)
        metrics = {
            "loss_history": losses,
            "final_loss": losses[-1],
            "best_loss": jnp.min(losses),
        }
        return trained_actor, metrics, active_wealth_supported

    def trainer(rng_key: jax.Array) -> tuple[ActorCritic, dict]:
        try:
            trained_actor, metrics, active_wealth_supported = _trainer_jit(rng_key)
            if config.track_active_wealth:
                active_wealth_supported = bool(active_wealth_supported)
        except eqx.EquinoxRuntimeError as exc:
            if config.track_active_wealth:
                raise _native_execution_validation_error() from exc
            raise
        if config.track_active_wealth:
            validation = _ActiveWealthTrajectoryValidation(
                initial_state_checked=True,
                episodes_checked=int(config.n_episodes),
                transitions_checked=int(config.n_episodes) * int(config.steps_per_episode),
                active_wealth_supported=bool(active_wealth_supported),
            )
            if not validation.active_wealth_supported:
                raise _ActiveWealthTrajectoryValidationError(
                    "training_active_gini_trajectory_unsupported",
                    "Active wealth or income left the finite nonnegative Gini profile during "
                    "native training.",
                )
            metrics["active_wealth_validation"] = validation
        return trained_actor, metrics

    return trainer


def create_jit_trainer_with_metrics(
    actor_critic: ActorCritic,
    executor_factory: Callable[[ActorCritic], PureExecutor],
    initial_state: GlobalState,
    config: JITTrainingConfig,
    custom_metrics: Sequence[MetricDefinition] | None = None,
) -> Callable[[jax.Array], tuple[ActorCritic, dict, MetricsCollector]]:
    """Create jit trainer with metrics."""
    params, static = eqx.partition(actor_critic, eqx.is_inexact_array)

    probe_executor = executor_factory(actor_critic)
    temporal_salt = _resolve_temporal_salt(probe_executor)

    optimizer = optax.chain(
        optax.clip_by_global_norm(config.max_grad_norm),
        optax.adam(config.learning_rate),
    )

    metrics_frequency = max(1, int(config.metrics_frequency))
    if config.collect_metrics:
        all_metrics = standard_training_metrics() + training_loss_metrics()
        if custom_metrics:
            all_metrics.extend(custom_metrics)
        max_history = int(config.n_episodes) * 10
    else:
        all_metrics = []
        max_history = 1

    collector_template = MetricsCollector(all_metrics, max_history=max_history)

    def _collect_trajectory_jit(
        actor_params: object,
        state: GlobalState,
        rng_key: jax.Array,
    ) -> tuple[Trajectory, GlobalState, jnp.ndarray]:
        actor = eqx.combine(static, actor_params)
        executor = executor_factory(actor)

        def _run_step(cur_state: GlobalState, cur_key: jax.Array):
            key_action, key_credit, next_key = jax.random.split(cur_key, 3)

            obs = build_temporal_observations(
                cur_state,
                horizon=config.horizon,
                include_expectations=config.include_expectations,
            )
            action_out, value = actor(obs, deterministic=True)
            dist = actor.get_action_distribution(obs, action_output=action_out)

            if temporal_salt is None:
                action_key = key_action
            else:
                action_key = get_mechanism_key(
                    cur_state.rng_key,
                    cur_state.time_step,
                    temporal_salt,
                )

            action = sample_actions(dist, action_key, action_type=actor.action_type)
            if actor.action_type == "continuous" and action.ndim == 1:
                action = action[:, None]
            log_prob = compute_log_prob(action, dist, action_type=actor.action_type)

            next_state, step_metrics = executor.step(cur_state, fidelity=config.fidelity)
            transition_supported = jnp.asarray(True)
            if config.track_active_wealth:
                transition_supported = _tracked_population_supported(
                    next_state,
                    config.gini_population_profile,
                )
                transition_supported = transition_supported & _selected_profile_status_supported(
                    step_metrics,
                    config.gini_population_profile,
                )

                def _supported_reward(_):
                    reward_value = compute_agent_reward(
                        cur_state,
                        next_state,
                        utility_type=config.utility_type,
                    )
                    if config.credit_config is not None:
                        reward_value = compute_credit_assignment(
                            reward_value,
                            cur_state,
                            next_state,
                            config.credit_config,
                            rng_key=key_credit,
                        )
                    return reward_value

                reward = jax.lax.cond(
                    transition_supported,
                    _supported_reward,
                    lambda _: jnp.zeros_like(cur_state.agents.wealth),
                    operand=None,
                )
                next_state = jax.lax.cond(
                    transition_supported,
                    lambda _: next_state,
                    lambda _: cur_state,
                    operand=None,
                )
            else:
                reward = compute_agent_reward(
                    cur_state,
                    next_state,
                    utility_type=config.utility_type,
                )
                if config.credit_config is not None:
                    reward = compute_credit_assignment(
                        reward,
                        cur_state,
                        next_state,
                        config.credit_config,
                        rng_key=key_credit,
                    )

            transition = {
                "obs": obs,
                "action": action,
                "reward": reward,
                "value": value,
                "log_prob": log_prob,
                "active": cur_state.agents.active,
            }
            if config.track_active_wealth:
                transition["active_wealth_supported"] = transition_supported
            return next_state, next_key, transition, transition_supported

        def step_fn(carry, _):
            if not config.track_active_wealth:
                cur_state, cur_key = carry
                next_state, next_key, transition, _ = _run_step(cur_state, cur_key)
                return (next_state, next_key), transition

            cur_state, cur_key, prior_supported = carry

            def _execute(_operand):
                next_state, next_key, transition, transition_supported = _run_step(
                    cur_state,
                    cur_key,
                )
                return (next_state, next_key, transition_supported), transition

            def _terminal(_operand):
                n_agents = cur_state.agents.active.shape[0]
                observation_width = build_temporal_observations(
                    state,
                    horizon=config.horizon,
                    include_expectations=config.include_expectations,
                ).shape[-1]
                dtype = cur_state.agents.wealth.dtype
                action_shape = (
                    (n_agents, actor.action_dim)
                    if actor.action_type == "continuous"
                    else (n_agents,)
                )
                transition = {
                    "obs": jnp.zeros((n_agents, observation_width), dtype=dtype),
                    "action": jnp.zeros(action_shape, dtype=dtype),
                    "reward": jnp.zeros_like(cur_state.agents.wealth),
                    "value": jnp.zeros_like(cur_state.agents.wealth),
                    "log_prob": jnp.zeros_like(cur_state.agents.wealth),
                    "active": cur_state.agents.active,
                    "active_wealth_supported": jnp.asarray(False, dtype=jnp.bool_),
                }
                return (cur_state, cur_key, jnp.asarray(False)), transition

            return jax.lax.cond(prior_supported, _execute, _terminal, operand=None)

        initial_supported = (
            _tracked_population_supported(state, config.gini_population_profile)
            if config.track_active_wealth
            else jnp.asarray(True)
        )
        initial_carry = (
            (state, rng_key, initial_supported) if config.track_active_wealth else (state, rng_key)
        )
        final_carry, transitions = jax.lax.scan(
            step_fn,
            initial_carry,
            None,
            length=int(config.steps_per_episode),
        )
        final_state = final_carry[0]

        trajectory_supported = (
            initial_supported & jnp.all(transitions["active_wealth_supported"])
            if config.track_active_wealth
            else jnp.asarray(True)
        )
        final_state = jax.lax.cond(
            trajectory_supported,
            lambda current: current,
            lambda _: state,
            final_state,
        )

        final_obs = build_temporal_observations(
            final_state,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
        )

        trajectory = Trajectory(
            observations=transitions["obs"],
            actions=transitions["action"],
            rewards=transitions["reward"],
            values=transitions["value"],
            dones=jnp.zeros_like(transitions["reward"], dtype=jnp.bool_),
            log_probs=transitions["log_prob"],
            final_observation=final_obs,
            active_mask=transitions["active"],
        )
        return trajectory, final_state, trajectory_supported

    def _ppo_update_jit(
        actor_params: object,
        opt_state: optax.OptState,
        trajectory: Trajectory,
    ) -> tuple[object, optax.OptState, jnp.ndarray, dict[str, jnp.ndarray], dict[str, jnp.ndarray]]:
        actor = eqx.combine(static, actor_params)
        _, final_value = actor(trajectory.final_observation, deterministic=True)
        returns, advantages = compute_returns_and_advantages(
            trajectory,
            final_value,
            gamma=config.gamma,
            gae_lambda=config.gae_lambda,
            active_mask=trajectory.active_mask,
        )

        mask_f = trajectory.active_mask.astype(jnp.float32)
        mask_sum = jnp.maximum(jnp.sum(mask_f), 1.0)
        mean_reward = jnp.sum(trajectory.rewards * mask_f) / mask_sum
        mean_advantage = jnp.sum(advantages * mask_f) / mask_sum

        def epoch_step(carry, _):
            cur_params, cur_opt_state = carry

            def loss_fn(p):
                actor_iter = eqx.combine(static, p)
                (loss, metrics) = ppo_loss(
                    actor_iter,
                    trajectory,
                    advantages,
                    returns,
                    trajectory.log_probs,
                    clip_epsilon=config.clip_epsilon,
                    value_coef=config.value_coef,
                    entropy_coef=config.entropy_coef,
                    active_mask=trajectory.active_mask,
                )
                return loss, metrics

            (loss_val, metrics), grads = jax.value_and_grad(loss_fn, has_aux=True)(cur_params)
            updates, next_opt_state = optimizer.update(grads, cur_opt_state, cur_params)
            next_params = optax.apply_updates(cur_params, updates)
            return (next_params, next_opt_state), (loss_val, metrics)

        (final_params, final_opt_state), (losses, metrics_seq) = jax.lax.scan(
            epoch_step,
            (actor_params, opt_state),
            None,
            length=int(config.ppo_epochs),
        )
        mean_loss = jnp.mean(losses)
        mean_metrics = jax.tree_util.tree_map(lambda x: jnp.mean(x, axis=0), metrics_seq)
        train_stats = {
            "mean_reward": mean_reward,
            "mean_advantage": mean_advantage,
        }
        return final_params, final_opt_state, mean_loss, mean_metrics, train_stats

    def _collect_metrics_buffer(
        buffer: MetricsBuffer,
        step_counter: jnp.ndarray,
        state: GlobalState,
    ) -> tuple[MetricsBuffer, jnp.ndarray]:
        idx = buffer.write_idx % buffer.max_size

        for defn in all_metrics:
            should_collect = (step_counter % defn.frequency) == 0

            def _collect(buf: MetricsBuffer) -> MetricsBuffer:
                value = defn.compute_fn(state)
                if defn.metric_type == MetricType.SCALAR:
                    return buf.write_scalar_at(defn.name, value, idx)
                if defn.metric_type == MetricType.HISTOGRAM:
                    n_bins = buf.histograms[defn.name].shape[1]
                    bins = _safe_histogram_bins(value, n_bins)
                    return buf.write_histogram_at(defn.name, value, bins, idx)
                return buf

            buffer = jax.lax.cond(should_collect, _collect, lambda b: b, buffer)

        return buffer.advance(1), step_counter + 1

    def _train_loop_with_metrics(
        rng_key: jax.Array,
    ) -> tuple[object, jnp.ndarray, MetricsBuffer, jnp.ndarray, jnp.ndarray]:
        opt_state = optimizer.init(params)
        loss_dtype = _training_loss_dtype(
            lambda key: _ppo_update_jit(
                params, opt_state, _collect_trajectory_jit(params, initial_state, key)[0]
            )[2],
            rng_key,
        )
        episode_losses = jnp.zeros((int(config.n_episodes),), dtype=loss_dtype)
        init_carry = TrainingMetricsCarry(
            params=params,
            opt_state=opt_state,
            rng_key=rng_key,
            best_loss=jnp.array(jnp.inf, dtype=loss_dtype),
            episode_losses=episode_losses,
            metrics_buffer=collector_template.buffer,
            metrics_step_counter=jnp.array(0, dtype=jnp.int32),
            active_wealth_supported=(
                _tracked_population_supported(initial_state, config.gini_population_profile)
                if config.track_active_wealth
                else jnp.asarray(True)
            ),
        )

        def episode_step(carry: TrainingMetricsCarry, idx):
            def _run_episode(current: TrainingMetricsCarry):
                key1, key2 = jax.random.split(current.rng_key)
                trajectory, final_state, trajectory_supported = _collect_trajectory_jit(
                    current.params,
                    initial_state,
                    key1,
                )

                def _update(_operand):
                    return _ppo_update_jit(current.params, current.opt_state, trajectory)

                def _skip_update(_operand):
                    zero = jnp.asarray(0.0, dtype=loss_dtype)
                    return (
                        current.params,
                        current.opt_state,
                        zero,
                        _zero_ppo_loss_metrics(zero),
                        {"mean_reward": zero, "mean_advantage": zero},
                    )

                new_params, new_opt_state, loss, metrics, train_stats = jax.lax.cond(
                    trajectory_supported,
                    _update,
                    _skip_update,
                    operand=None,
                )
                losses = current.episode_losses.at[idx].set(loss)
                best_loss = jnp.minimum(current.best_loss, loss)

                if config.collect_metrics:
                    should_collect = trajectory_supported & ((idx % metrics_frequency) == 0)

                    def _collect_and_record(payload):
                        buffer, step_counter = payload
                        buffer, step_counter = _collect_metrics_buffer(
                            buffer,
                            step_counter,
                            final_state,
                        )
                        buffer = _record_training_losses(buffer, metrics, train_stats)
                        return buffer, step_counter

                    new_buffer, new_step_counter = jax.lax.cond(
                        should_collect,
                        _collect_and_record,
                        lambda payload: payload,
                        (current.metrics_buffer, current.metrics_step_counter),
                    )
                else:
                    new_buffer = current.metrics_buffer
                    new_step_counter = current.metrics_step_counter

                new_carry = TrainingMetricsCarry(
                    params=new_params,
                    opt_state=new_opt_state,
                    rng_key=key2,
                    best_loss=best_loss,
                    episode_losses=losses,
                    metrics_buffer=new_buffer,
                    metrics_step_counter=new_step_counter,
                    active_wealth_supported=(
                        current.active_wealth_supported & trajectory_supported
                    ),
                )
                return new_carry, loss

            def _skip_episode(current: TrainingMetricsCarry):
                return current, jnp.asarray(0.0, dtype=loss_dtype)

            return jax.lax.cond(
                carry.active_wealth_supported,
                _run_episode,
                _skip_episode,
                carry,
            )

        final_carry, losses = jax.lax.scan(
            episode_step,
            init_carry,
            jnp.arange(int(config.n_episodes)),
        )
        return (
            final_carry.params,
            losses,
            final_carry.metrics_buffer,
            final_carry.metrics_step_counter,
            final_carry.active_wealth_supported,
        )

    @eqx.filter_jit
    def _trainer_jit(
        rng_key: jax.Array,
    ) -> tuple[object, jnp.ndarray, MetricsBuffer, jnp.ndarray, jnp.ndarray]:
        return _train_loop_with_metrics(rng_key)

    def trainer(rng_key: jax.Array) -> tuple[ActorCritic, dict, MetricsCollector]:
        try:
            (
                final_params,
                losses,
                final_buffer,
                final_step_counter,
                active_wealth_supported,
            ) = _trainer_jit(rng_key)
            if config.track_active_wealth:
                active_wealth_supported = bool(active_wealth_supported)
        except eqx.EquinoxRuntimeError as exc:
            if config.track_active_wealth:
                raise _native_execution_validation_error() from exc
            raise
        trained_actor = eqx.combine(static, final_params)
        final_collector = MetricsCollector(
            all_metrics,
            buffer=final_buffer,
            step_counter=final_step_counter,
        )
        metrics = {
            "loss_history": losses,
            "final_loss": losses[-1],
            "best_loss": jnp.min(losses),
        }
        if config.track_active_wealth:
            validation = _ActiveWealthTrajectoryValidation(
                initial_state_checked=True,
                episodes_checked=int(config.n_episodes),
                transitions_checked=int(config.n_episodes) * int(config.steps_per_episode),
                active_wealth_supported=bool(active_wealth_supported),
            )
            if not validation.active_wealth_supported:
                raise _ActiveWealthTrajectoryValidationError(
                    "training_active_gini_trajectory_unsupported",
                    "Active wealth or income left the finite nonnegative Gini profile during "
                    "native training.",
                )
            metrics["active_wealth_validation"] = validation
        return trained_actor, metrics, final_collector

    return trainer


def _record_training_losses(
    buffer: MetricsBuffer,
    metrics: dict[str, jnp.ndarray],
    train_stats: dict[str, jnp.ndarray],
) -> MetricsBuffer:
    idx = (buffer.write_idx - 1) % buffer.max_size
    buffer = buffer.write_scalar_at("policy_loss", metrics["policy_loss"], idx)
    buffer = buffer.write_scalar_at("value_loss", metrics["value_loss"], idx)
    buffer = buffer.write_scalar_at("entropy", metrics["entropy"], idx)
    buffer = buffer.write_scalar_at("mean_reward", train_stats["mean_reward"], idx)
    buffer = buffer.write_scalar_at("mean_advantage", train_stats["mean_advantage"], idx)
    return buffer


def _resolve_temporal_salt(executor: PureExecutor) -> int | None:
    for mech in executor.mechanisms:
        if isinstance(mech, TemporalConsumptionMechanism):
            return executor.prng_config.get(mech.spec.name, 0)
    return None
