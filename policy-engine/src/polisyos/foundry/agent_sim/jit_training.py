from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, NamedTuple, Sequence

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.foundry.agent_sim.actor_critic import ActorCritic, compute_log_prob, sample_actions
from polisyos.foundry.agent_sim.credit_assignment import CreditConfig, compute_credit_assignment
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.metrics import (
    MetricDefinition,
    MetricsCollector,
    standard_training_metrics,
    training_loss_metrics,
)
from polisyos.foundry.agent_sim.prng import get_mechanism_key
from polisyos.foundry.agent_sim.rewards import compute_agent_reward
from polisyos.foundry.agent_sim.rl import Trajectory, compute_returns_and_advantages, ppo_loss
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.temporal_mechanisms import TemporalConsumptionMechanism
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.contracts.fidelity import FidelityLevel


@dataclass(frozen=True)
class JITTrainingConfig:
    n_episodes: int = 100
    steps_per_episode: int = 64
    ppo_epochs: int = 4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    learning_rate: float = 3e-4
    max_grad_norm: float = 1.0
    horizon: int = 256
    utility_type: str = "crra"
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID
    include_expectations: bool = True
    credit_config: CreditConfig | None = None
    collect_metrics: bool = True
    metrics_frequency: int = 1


class TrainingCarry(NamedTuple):
    params: object
    opt_state: optax.OptState
    rng_key: jax.Array
    best_loss: jnp.ndarray
    episode_losses: jnp.ndarray
    metrics_collector: MetricsCollector


def create_jit_trainer(
    actor_critic: ActorCritic,
    executor_factory: Callable[[ActorCritic], PureExecutor],
    initial_state: GlobalState,
    config: JITTrainingConfig,
) -> Callable[[jax.Array], tuple[ActorCritic, dict]]:
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
    ) -> tuple[Trajectory, GlobalState]:
        actor = eqx.combine(static, actor_params)
        executor = executor_factory(actor)

        def step_fn(carry, _):
            cur_state, cur_key = carry
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

            next_state, _ = executor.step(cur_state, fidelity=config.fidelity)
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
            return (next_state, next_key), transition

        (final_state, _), transitions = jax.lax.scan(
            step_fn,
            (state, rng_key),
            None,
            length=int(config.steps_per_episode),
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
        return trajectory, final_state

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

    def _train_loop(rng_key: jax.Array) -> tuple[object, jnp.ndarray]:
        opt_state = optimizer.init(params)
        episode_losses = jnp.zeros((int(config.n_episodes),), dtype=jnp.float32)
        init_carry = TrainingCarry(
            params=params,
            opt_state=opt_state,
            rng_key=rng_key,
            best_loss=jnp.array(jnp.inf, dtype=jnp.float32),
            episode_losses=episode_losses,
            metrics_collector=dummy_collector,
        )

        def episode_step(carry: TrainingCarry, idx):
            key1, key2 = jax.random.split(carry.rng_key)
            trajectory, _ = _collect_trajectory_jit(carry.params, initial_state, key1)
            new_params, new_opt_state, loss = _ppo_update_jit(
                carry.params, carry.opt_state, trajectory
            )
            losses = carry.episode_losses.at[idx].set(loss)
            best_loss = jnp.minimum(carry.best_loss, loss)
            new_carry = TrainingCarry(
                params=new_params,
                opt_state=new_opt_state,
                rng_key=key2,
                best_loss=best_loss,
                episode_losses=losses,
                metrics_collector=carry.metrics_collector,
            )
            return new_carry, loss

        final_carry, losses = jax.lax.scan(
            episode_step,
            init_carry,
            jnp.arange(int(config.n_episodes)),
        )
        return final_carry.params, losses

    @jax.jit
    def trainer(rng_key: jax.Array) -> tuple[ActorCritic, dict]:
        final_params, losses = _train_loop(rng_key)
        trained_actor = eqx.combine(static, final_params)
        metrics = {
            "loss_history": losses,
            "final_loss": losses[-1],
            "best_loss": jnp.min(losses),
        }
        return trained_actor, metrics

    return trainer


def create_jit_trainer_with_metrics(
    actor_critic: ActorCritic,
    executor_factory: Callable[[ActorCritic], PureExecutor],
    initial_state: GlobalState,
    config: JITTrainingConfig,
    custom_metrics: Sequence[MetricDefinition] | None = None,
) -> Callable[[jax.Array], tuple[ActorCritic, dict, MetricsCollector]]:
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

    collector = MetricsCollector(all_metrics, max_history=max_history)

    def _collect_trajectory_jit(
        actor_params: object,
        state: GlobalState,
        rng_key: jax.Array,
    ) -> tuple[Trajectory, GlobalState]:
        actor = eqx.combine(static, actor_params)
        executor = executor_factory(actor)

        def step_fn(carry, _):
            cur_state, cur_key = carry
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

            next_state, _ = executor.step(cur_state, fidelity=config.fidelity)
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
            return (next_state, next_key), transition

        (final_state, _), transitions = jax.lax.scan(
            step_fn,
            (state, rng_key),
            None,
            length=int(config.steps_per_episode),
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
        return trajectory, final_state

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

            (loss_val, metrics), grads = jax.value_and_grad(loss_fn, has_aux=True)(
                cur_params
            )
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
        mean_metrics = jax.tree_map(lambda x: jnp.mean(x, axis=0), metrics_seq)
        train_stats = {
            "mean_reward": mean_reward,
            "mean_advantage": mean_advantage,
        }
        return final_params, final_opt_state, mean_loss, mean_metrics, train_stats

    def _train_loop_with_metrics(
        rng_key: jax.Array,
    ) -> tuple[object, jnp.ndarray, MetricsCollector]:
        opt_state = optimizer.init(params)
        episode_losses = jnp.zeros((int(config.n_episodes),), dtype=jnp.float32)
        init_carry = TrainingCarry(
            params=params,
            opt_state=opt_state,
            rng_key=rng_key,
            best_loss=jnp.array(jnp.inf, dtype=jnp.float32),
            episode_losses=episode_losses,
            metrics_collector=collector,
        )

        def episode_step(carry: TrainingCarry, idx):
            key1, key2 = jax.random.split(carry.rng_key)
            trajectory, final_state = _collect_trajectory_jit(
                carry.params, initial_state, key1
            )
            new_params, new_opt_state, loss, metrics, train_stats = _ppo_update_jit(
                carry.params, carry.opt_state, trajectory
            )
            losses = carry.episode_losses.at[idx].set(loss)
            best_loss = jnp.minimum(carry.best_loss, loss)

            if config.collect_metrics:
                should_collect = (idx % metrics_frequency) == 0

                def _collect_and_record(col):
                    col = col.collect(final_state)
                    return _record_training_losses(col, metrics, train_stats)

                new_collector = jax.lax.cond(
                    should_collect,
                    _collect_and_record,
                    lambda col: col,
                    carry.metrics_collector,
                )
            else:
                new_collector = carry.metrics_collector

            new_carry = TrainingCarry(
                params=new_params,
                opt_state=new_opt_state,
                rng_key=key2,
                best_loss=best_loss,
                episode_losses=losses,
                metrics_collector=new_collector,
            )
            return new_carry, loss

        final_carry, losses = jax.lax.scan(
            episode_step,
            init_carry,
            jnp.arange(int(config.n_episodes)),
        )
        return final_carry.params, losses, final_carry.metrics_collector

    @jax.jit
    def trainer(rng_key: jax.Array) -> tuple[ActorCritic, dict, MetricsCollector]:
        final_params, losses, final_collector = _train_loop_with_metrics(rng_key)
        trained_actor = eqx.combine(static, final_params)
        metrics = {
            "loss_history": losses,
            "final_loss": losses[-1],
            "best_loss": jnp.min(losses),
        }
        return trained_actor, metrics, final_collector

    return trainer


def _record_training_losses(
    collector: MetricsCollector,
    metrics: dict[str, jnp.ndarray],
    train_stats: dict[str, jnp.ndarray],
) -> MetricsCollector:
    buffer = collector.buffer
    idx = (buffer.write_idx - 1) % buffer.max_size
    buffer = buffer.write_scalar_at("policy_loss", metrics["policy_loss"], idx)
    buffer = buffer.write_scalar_at("value_loss", metrics["value_loss"], idx)
    buffer = buffer.write_scalar_at("entropy", metrics["entropy"], idx)
    buffer = buffer.write_scalar_at("mean_reward", train_stats["mean_reward"], idx)
    buffer = buffer.write_scalar_at("mean_advantage", train_stats["mean_advantage"], idx)
    return collector.replace(buffer=buffer)


def _resolve_temporal_salt(executor: PureExecutor) -> int | None:
    for mech in executor.mechanisms:
        if isinstance(mech, TemporalConsumptionMechanism):
            return executor.prng_config.get(mech.spec.name, 0)
    return None
