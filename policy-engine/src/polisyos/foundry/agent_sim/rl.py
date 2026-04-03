"""Store rollout tensors and compute PPO training targets for agent-simulation learning."""
from __future__ import annotations

import chex
import jax
import jax.numpy as jnp
from jaxtyping import Array, Bool, Float

from polisyos.foundry.agent_sim.actor_critic import (
    ActorCritic,
    compute_entropy,
    compute_log_prob,
)


@chex.dataclass(frozen=True)
class Transition:
    """Transition public type."""
    observation: Float[Array, "obs_dim"]
    action: Float[Array, "action_dim"]
    reward: Float[Array, ""]
    next_observation: Float[Array, "obs_dim"]
    done: Bool[Array, ""]
    value: Float[Array, ""]


@chex.dataclass(frozen=True)
class Trajectory:
    """Trajectory public type."""
    observations: Float[Array, "T n_agents obs_dim"]
    actions: Float[Array, "T n_agents action_dim"]
    rewards: Float[Array, "T n_agents"]
    values: Float[Array, "T n_agents"]
    dones: Bool[Array, "T n_agents"]
    log_probs: Float[Array, "T n_agents"]
    final_observation: Float[Array, "n_agents obs_dim"]
    active_mask: Bool[Array, "T n_agents"]


def compute_returns_and_advantages(
    trajectory: Trajectory,
    final_value: Float[Array, "n_agents"],
    *,
    gamma: float = 0.99,
    gae_lambda: float = 0.95,
    active_mask: Bool[Array, "T n_agents"] | None = None,
) -> tuple[Float[Array, "T n_agents"], Float[Array, "T n_agents"]]:
    """Compute PPO returns and generalized-advantage estimates over one trajectory."""
    rewards = trajectory.rewards
    values = trajectory.values
    dones = trajectory.dones
    T = rewards.shape[0]

    if active_mask is None:
        active_mask = trajectory.active_mask

    def gae_step(carry, t):
        next_advantage, next_value = carry
        reward = rewards[t]
        value = values[t]
        done = dones[t]
        mask = active_mask[t].astype(jnp.float32)
        done_mask = 1.0 - done.astype(jnp.float32)
        not_done = done_mask * mask
        delta = reward + gamma * next_value * not_done - value
        advantage = delta + gamma * gae_lambda * next_advantage * not_done
        advantage = advantage * mask
        return (advantage, value), (advantage, advantage + value)

    init_carry = (jnp.zeros_like(final_value), final_value)
    _, (adv_rev, ret_rev) = jax.lax.scan(
        gae_step,
        init_carry,
        jnp.arange(T - 1, -1, -1),
    )
    advantages = jnp.flip(adv_rev, axis=0)
    returns = jnp.flip(ret_rev, axis=0)
    return returns, advantages


def ppo_loss(
    actor_critic: ActorCritic,
    trajectory: Trajectory,
    advantages: Float[Array, "T n_agents"],
    returns: Float[Array, "T n_agents"],
    old_log_probs: Float[Array, "T n_agents"],
    *,
    clip_epsilon: float = 0.2,
    value_coef: float = 0.5,
    entropy_coef: float = 0.01,
    active_mask: Bool[Array, "T n_agents"] | None = None,
) -> tuple[Float[Array, ""], dict[str, Array]]:
    """Evaluate PPO policy, value, and entropy losses over a collected trajectory."""
    observations = trajectory.observations
    actions = trajectory.actions
    T, n_agents, obs_dim = observations.shape
    obs_flat = observations.reshape(T * n_agents, obs_dim)
    actions_flat = actions.reshape(T * n_agents, -1)

    action_out, values = actor_critic(obs_flat, deterministic=True)
    values = values.reshape(T, n_agents)
    dist = actor_critic.get_action_distribution(obs_flat, action_output=action_out)
    new_log_probs = compute_log_prob(
        actions_flat,
        dist,
        action_type=actor_critic.action_type,
    )
    new_log_probs = new_log_probs.reshape(T, n_agents)

    mask = active_mask if active_mask is not None else trajectory.active_mask
    mask_f = mask.astype(jnp.float32)
    mask_sum = jnp.maximum(jnp.sum(mask_f), 1.0)

    adv_mean = jnp.sum(advantages * mask_f) / mask_sum
    adv_std = jnp.sqrt(jnp.sum((advantages - adv_mean) ** 2 * mask_f) / mask_sum)
    advantages_norm = (advantages - adv_mean) / (adv_std + 1e-8)

    ratio = jnp.exp(new_log_probs - old_log_probs)
    clipped_ratio = jnp.clip(ratio, 1.0 - clip_epsilon, 1.0 + clip_epsilon)
    policy_loss = -jnp.minimum(ratio * advantages_norm, clipped_ratio * advantages_norm)
    value_loss = (values - returns) ** 2

    entropy = compute_entropy(dist, action_type=actor_critic.action_type)
    if entropy.ndim == 0:
        entropy_term = entropy
    else:
        entropy_term = jnp.mean(entropy)

    policy_loss = jnp.sum(policy_loss * mask_f) / mask_sum
    value_loss = jnp.sum(value_loss * mask_f) / mask_sum

    total_loss = policy_loss + value_coef * value_loss - entropy_coef * entropy_term
    clip_fraction = jnp.sum((jnp.abs(ratio - 1.0) > clip_epsilon) * mask_f) / mask_sum

    metrics = {
        "policy_loss": policy_loss,
        "value_loss": value_loss,
        "entropy": entropy_term,
        "mean_ratio": jnp.sum(ratio * mask_f) / mask_sum,
        "clip_fraction": clip_fraction,
    }
    return total_loss, metrics
