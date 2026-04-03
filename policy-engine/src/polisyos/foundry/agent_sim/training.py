"""Train actor-critic policies against agent-simulation rollouts and persist artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.agent_sim.actor_critic import ActorCritic, compute_log_prob, sample_actions
from polisyos.foundry.agent_sim.artifact import AgentPolicyArtifact, store_policy_artifact
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.prng import get_mechanism_key
from polisyos.foundry.agent_sim.rewards import compute_agent_reward
from polisyos.foundry.agent_sim.rl import Trajectory, compute_returns_and_advantages, ppo_loss
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.agent_sim.training_config import TrainingConfigBase
from polisyos.foundry.agent_sim.temporal_mechanisms import TemporalConsumptionMechanism
from polisyos.foundry.contracts.fidelity import FidelityLevel
from polisyos.foundry.runtime.fingerprint import DeterminismTier, EnvironmentFingerprint


@dataclass(frozen=True)
class TrainingConfig(TrainingConfigBase):
    """Extend the base training config with logging controls for iterative runs."""
    log_interval: int = 10


def train_actor_critic(
    actor_critic: ActorCritic,
    initial_state,
    config: TrainingConfig,
    *,
    executor: PureExecutor | None = None,
    make_executor: Callable[[ActorCritic], PureExecutor] | None = None,
) -> ActorCritic:
    """Iteratively train an actor-critic policy against executor rollouts."""
    if executor is None and make_executor is None:
        raise ValueError("Provide either executor or make_executor.")

    params, static = eqx.partition(actor_critic, eqx.is_inexact_array)
    optimizer = optax.chain(
        optax.clip_by_global_norm(config.max_grad_norm),
        optax.adam(config.learning_rate),
    )
    opt_state = optimizer.init(params)

    @eqx.filter_jit
    def update_step(params, opt_state, trajectory: Trajectory):
        actor = eqx.combine(static, params)
        _, final_value = actor(trajectory.final_observation, deterministic=True)
        returns, advantages = compute_returns_and_advantages(
            trajectory,
            final_value,
            gamma=config.gamma,
            gae_lambda=config.gae_lambda,
            active_mask=trajectory.active_mask,
        )

        def epoch_body(_, carry):
            cur_params, cur_opt_state = carry
            actor_iter = eqx.combine(static, cur_params)
            (loss, _), grads = eqx.filter_value_and_grad(ppo_loss, has_aux=True)(
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
            updates, next_opt_state = optimizer.update(grads, cur_opt_state, cur_params)
            next_params = optax.apply_updates(cur_params, updates)
            return next_params, next_opt_state

        params_out, opt_state_out = jax.lax.fori_loop(
            0,
            int(config.ppo_epochs),
            epoch_body,
            (params, opt_state),
        )
        actor_out = eqx.combine(static, params_out)
        return params_out, opt_state_out, actor_out

    for episode in range(int(config.n_episodes)):
        current_actor = eqx.combine(static, params)
        if make_executor is not None:
            current_executor = make_executor(current_actor)
        else:
            current_executor = _replace_temporal_mechanism(executor, current_actor)

        trajectory = collect_trajectory(
            current_executor,
            initial_state,
            current_actor,
            config,
        )
        params, opt_state, _ = update_step(params, opt_state, trajectory)

        if config.log_interval and episode % int(config.log_interval) == 0:
            _ = trajectory

    return eqx.combine(static, params)


def collect_trajectory(
    executor: PureExecutor,
    initial_state,
    actor_critic: ActorCritic,
    config: TrainingConfig,
) -> Trajectory:
    """Roll out one executor trajectory and capture PPO training tensors."""
    mech = _find_temporal_mechanism(executor)
    salt = executor.prng_config.get(mech.spec.name, 0)

    observations = []
    actions = []
    rewards = []
    values = []
    log_probs = []
    dones = []
    active_masks = []

    state = initial_state
    for _ in range(int(config.steps_per_episode)):
        obs = build_temporal_observations(
            state,
            horizon=config.horizon,
            include_expectations=config.include_expectations,
        )
        action_out, value = actor_critic(obs, deterministic=True)
        dist = actor_critic.get_action_distribution(obs, action_output=action_out)
        mech_key = get_mechanism_key(state.rng_key, state.time_step, salt)
        action = sample_actions(dist, mech_key, action_type=actor_critic.action_type)
        if actor_critic.action_type == "continuous" and action.ndim == 1:
            action = action[:, None]
        log_prob = compute_log_prob(action, dist, action_type=actor_critic.action_type)

        next_state, _ = executor.step(state, fidelity=config.fidelity)
        reward = compute_agent_reward(state, next_state, utility_type=config.utility_type)

        observations.append(obs)
        actions.append(action)
        rewards.append(reward)
        values.append(value)
        log_probs.append(log_prob)
        dones.append(jnp.zeros_like(state.agents.active, dtype=jnp.bool_))
        active_masks.append(state.agents.active)

        state = next_state

    final_obs = build_temporal_observations(
        state,
        horizon=config.horizon,
        include_expectations=config.include_expectations,
    )

    return Trajectory(
        observations=jnp.stack(observations),
        actions=jnp.stack(actions),
        rewards=jnp.stack(rewards),
        values=jnp.stack(values),
        dones=jnp.stack(dones),
        log_probs=jnp.stack(log_probs),
        final_observation=final_obs,
        active_mask=jnp.stack(active_masks),
    )


def _find_temporal_mechanism(executor: PureExecutor) -> TemporalConsumptionMechanism:
    for mech in executor.mechanisms:
        if isinstance(mech, TemporalConsumptionMechanism):
            return mech
    raise ValueError("TemporalConsumptionMechanism not found in executor.")


def _replace_temporal_mechanism(
    executor: PureExecutor, actor_critic: ActorCritic
) -> PureExecutor:
    mechanisms = []
    for mech in executor.mechanisms:
        if isinstance(mech, TemporalConsumptionMechanism):
            mechanisms.append(
                TemporalConsumptionMechanism(
                    actor_critic=actor_critic,
                    horizon=mech.horizon,
                    min_consumption=mech.min_consumption,
                    include_expectations=mech.include_expectations,
                )
            )
        else:
            mechanisms.append(mech)
    return PureExecutor(
        mechanisms,
        prng_config=executor.prng_config,
        aggregate_every=executor.aggregate_every,
        compute_gini=executor.compute_gini,
    )


def train_actor_critic_jit(
    actor_critic: ActorCritic,
    initial_state,
    config: TrainingConfig,
    *,
    make_executor: Callable[[ActorCritic], PureExecutor],
    rng_key: jax.Array | None = None,
) -> tuple[ActorCritic, dict]:
    """
    Fully JIT-compiled training loop for large-scale runs.
    """
    from polisyos.foundry.agent_sim.jit_training import (
        JITTrainingConfig,
        create_jit_trainer,
    )

    jit_config = JITTrainingConfig(**config.common_kwargs())

    if rng_key is None:
        rng_key = jax.random.PRNGKey(0)

    trainer = create_jit_trainer(actor_critic, make_executor, initial_state, jit_config)
    return trainer(rng_key)


def train_actor_critic_with_artifact(
    actor_critic: ActorCritic,
    initial_state,
    config: TrainingConfig,
    *,
    make_executor: Callable[[ActorCritic], PureExecutor],
    run_id: str,
    tier: DeterminismTier = DeterminismTier.NONDETERMINISTIC,
    seed: int = 42,
    cas: FileSystemCAS | None = None,
) -> tuple[ActorCritic, dict, AgentPolicyArtifact]:
    """
    Train actor-critic and produce immutable artifact.

    Returns:
        Tuple of (trained_policy, metrics_dict, artifact)
    """
    log = get_logger(__name__)

    fingerprint = EnvironmentFingerprint.capture(tier, seed)
    for warning in fingerprint.validate_for_tier():
        log.warning("[%s] %s", run_id, warning)

    rng_key = jax.random.PRNGKey(seed)
    trained_policy, metrics = train_actor_critic_jit(
        actor_critic,
        initial_state,
        config,
        make_executor=make_executor,
        rng_key=rng_key,
    )

    final_loss = metrics.get("final_loss", 0.0)
    best_loss = metrics.get("best_loss", final_loss)

    artifact = AgentPolicyArtifact.from_trained_policy(
        policy=trained_policy,
        run_id=run_id,
        steps=int(config.n_episodes) * int(config.steps_per_episode),
        loss=float(final_loss),
        fingerprint=fingerprint,
        best_loss=float(best_loss) if best_loss is not None else None,
        extended_metrics={
            "total_episodes": int(config.n_episodes),
            "learning_rate": config.learning_rate,
            "ppo_epochs": int(config.ppo_epochs),
        },
    )

    if cas is not None:
        weights_ref, manifest_ref = _store_artifact_in_cas(cas, artifact)
        log.info(
            "[%s] Artifact stored: %s (weights=%s, manifest=%s, loss=%.4f)",
            run_id,
            artifact.artifact_id,
            weights_ref.artifact_id,
            manifest_ref.artifact_id,
            artifact.metrics.final_loss,
        )

    return trained_policy, metrics, artifact


def _store_artifact_in_cas(
    cas: FileSystemCAS,
    artifact: AgentPolicyArtifact,
):
    """Store artifact weights and manifest in CAS."""
    return store_policy_artifact(cas, artifact)
