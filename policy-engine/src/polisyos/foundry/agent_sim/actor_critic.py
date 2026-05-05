"""Build actor-critic networks and the action-distribution math used during training."""

from __future__ import annotations

from collections.abc import Callable

import chex
import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.runtime.numeric import (
    clip_probability,
    safe_exp_from_log_std,
    stable_normal_entropy,
    stable_normal_log_prob,
)


class NormalizedMLP(eqx.Module):
    """Normalized MLP public type."""

    layers: tuple[eqx.nn.Linear, ...]
    norms: tuple[eqx.nn.LayerNorm, ...]
    activation: Callable[[jnp.ndarray], jnp.ndarray] = eqx.field(static=True)

    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        if x.ndim == 1:
            return self._forward_single(x)
        if x.ndim == 2:
            return jax.vmap(self._forward_single)(x)
        raise ValueError(f"NormalizedMLP expects ndim 1 or 2, got shape={x.shape!r}")

    def _forward_single(self, x: jnp.ndarray) -> jnp.ndarray:
        out = x
        for idx, layer in enumerate(self.layers):
            out = layer(out)
            if idx < len(self.norms):
                out = self.norms[idx](out)
            out = self.activation(out)
        return out


class ValueNetwork(eqx.Module):
    """Value network public type."""

    trunk: NormalizedMLP
    head: eqx.nn.Linear

    def __init__(
        self,
        key: jax.Array,
        obs_dim: int,
        hidden_dims: tuple[int, ...] = (128, 128, 64),
    ):
        if not hidden_dims:
            hidden_dims = (64,)
        keys = jax.random.split(key, len(hidden_dims) + 1)
        trunk_dims = (int(obs_dim),) + tuple(int(d) for d in hidden_dims)
        layers = tuple(
            eqx.nn.Linear(trunk_dims[i], trunk_dims[i + 1], key=keys[i])
            for i in range(len(trunk_dims) - 1)
        )
        norms = tuple(eqx.nn.LayerNorm(dim, elementwise_affine=True) for dim in trunk_dims[1:])
        self.trunk = NormalizedMLP(layers=layers, norms=norms, activation=jax.nn.gelu)
        self.head = eqx.nn.Linear(trunk_dims[-1], 1, key=keys[-1])

    def __call__(self, observations: jnp.ndarray) -> jnp.ndarray:
        features = self.trunk(observations)
        values = self.head(features)
        return jnp.squeeze(values, axis=-1)


class AdvantageNetwork(eqx.Module):
    """Advantage network public type."""

    trunk: NormalizedMLP
    value_head: eqx.nn.Linear
    advantage_head: eqx.nn.Linear
    action_dim: int = eqx.field(static=True)

    def __init__(
        self,
        key: jax.Array,
        obs_dim: int,
        action_dim: int = 1,
        hidden_dims: tuple[int, ...] = (128, 128),
    ):
        if not hidden_dims:
            hidden_dims = (64,)
        self.action_dim = int(action_dim)
        keys = jax.random.split(key, len(hidden_dims) + 3)
        trunk_dims = (int(obs_dim),) + tuple(int(d) for d in hidden_dims)
        layers = tuple(
            eqx.nn.Linear(trunk_dims[i], trunk_dims[i + 1], key=keys[i])
            for i in range(len(trunk_dims) - 1)
        )
        norms = tuple(eqx.nn.LayerNorm(dim, elementwise_affine=True) for dim in trunk_dims[1:])
        self.trunk = NormalizedMLP(layers=layers, norms=norms, activation=jax.nn.gelu)
        self.value_head = eqx.nn.Linear(trunk_dims[-1], 1, key=keys[-2])
        self.advantage_head = eqx.nn.Linear(trunk_dims[-1] + self.action_dim, 1, key=keys[-1])

    def __call__(self, observations: jnp.ndarray, actions: jnp.ndarray) -> jnp.ndarray:
        features = self.trunk(observations)
        value = self.value_head(features)
        sa = jnp.concatenate([features, actions], axis=-1)
        advantage = self.advantage_head(sa)
        return jnp.squeeze(value + advantage, axis=-1)


class ActorCritic(eqx.Module):
    """Actor critic public type."""

    shared: NormalizedMLP
    actor_hidden: eqx.nn.Linear
    actor_norm: eqx.nn.LayerNorm
    actor_out: eqx.nn.Linear
    critic_hidden: eqx.nn.Linear
    critic_norm: eqx.nn.LayerNorm
    critic_out: eqx.nn.Linear
    action_log_std: jnp.ndarray
    action_dim: int = eqx.field(static=True)
    action_type: str = eqx.field(static=True)

    def __init__(
        self,
        key: jax.Array,
        obs_dim: int,
        *,
        hidden_dims: tuple[int, ...] = (256, 128, 64),
        action_dim: int = 1,
        action_type: str = "continuous",
    ):
        if not hidden_dims:
            hidden_dims = (64,)
        self.action_dim = int(action_dim)
        self.action_type = str(action_type)

        head_dim = int(hidden_dims[-1])
        shared_dims = (int(obs_dim),) + tuple(int(d) for d in hidden_dims[:-1])
        if len(shared_dims) == 1:
            shared_layers = ()
            shared_norms = ()
            shared_out_dim = int(obs_dim)
        else:
            keys = jax.random.split(key, len(shared_dims) + 4)
            shared_layers = tuple(
                eqx.nn.Linear(shared_dims[i], shared_dims[i + 1], key=keys[i])
                for i in range(len(shared_dims) - 1)
            )
            shared_norms = tuple(
                eqx.nn.LayerNorm(dim, elementwise_affine=True) for dim in shared_dims[1:]
            )
            shared_out_dim = shared_dims[-1]

        if len(shared_dims) == 1:
            keys = jax.random.split(key, 4)
        else:
            keys = jax.random.split(key, len(shared_dims) + 4)[-4:]

        self.shared = NormalizedMLP(
            layers=shared_layers, norms=shared_norms, activation=jax.nn.gelu
        )
        self.actor_hidden = eqx.nn.Linear(shared_out_dim, head_dim, key=keys[0])
        self.actor_norm = eqx.nn.LayerNorm(head_dim, elementwise_affine=True)
        self.actor_out = eqx.nn.Linear(head_dim, self.action_dim, key=keys[1])
        self.critic_hidden = eqx.nn.Linear(shared_out_dim, head_dim, key=keys[2])
        self.critic_norm = eqx.nn.LayerNorm(head_dim, elementwise_affine=True)
        self.critic_out = eqx.nn.Linear(head_dim, 1, key=keys[3])
        self.action_log_std = jnp.zeros((self.action_dim,), dtype=jnp.float32)

    def __call__(
        self,
        observations: jnp.ndarray,
        *,
        deterministic: bool = False,
    ) -> tuple[jnp.ndarray, jnp.ndarray]:
        del deterministic
        if observations.ndim == 1:
            obs = observations[None, :]
            action_out, value = self._forward(obs)
            return action_out[0], value[0]
        return self._forward(observations)

    def _forward(self, observations: jnp.ndarray) -> tuple[jnp.ndarray, jnp.ndarray]:
        shared_features = self.shared(observations)
        if shared_features.ndim == 1:
            actor_hidden = self.actor_hidden(shared_features)
            actor_hidden = self.actor_norm(actor_hidden)
            actor_hidden = jax.nn.gelu(actor_hidden)
            action_out = self.actor_out(actor_hidden)

            critic_hidden = self.critic_hidden(shared_features)
            critic_hidden = self.critic_norm(critic_hidden)
            critic_hidden = jax.nn.gelu(critic_hidden)
            value = self.critic_out(critic_hidden)
            return action_out, jnp.squeeze(value, axis=-1)

        actor_hidden = jax.vmap(self.actor_hidden)(shared_features)
        actor_hidden = jax.vmap(self.actor_norm)(actor_hidden)
        actor_hidden = jax.nn.gelu(actor_hidden)
        action_out = jax.vmap(self.actor_out)(actor_hidden)

        critic_hidden = jax.vmap(self.critic_hidden)(shared_features)
        critic_hidden = jax.vmap(self.critic_norm)(critic_hidden)
        critic_hidden = jax.nn.gelu(critic_hidden)
        value = jax.vmap(self.critic_out)(critic_hidden)

        return action_out, jnp.squeeze(value, axis=-1)

    def get_action_distribution(
        self,
        observations: jnp.ndarray,
        *,
        action_output: jnp.ndarray | None = None,
    ) -> dict[str, jnp.ndarray]:
        if action_output is None:
            action_output, _ = self(observations, deterministic=True)
        if self.action_type == "continuous":
            mean = action_output
            log_std = self.action_log_std
            if mean.ndim == 1:
                log_std = jnp.broadcast_to(log_std, mean.shape)
            else:
                log_std = jnp.broadcast_to(log_std, mean.shape)
            clipped_log_std, std = safe_exp_from_log_std(log_std)
            return {"mean": mean, "log_std": clipped_log_std, "std": std}
        return {"logits": action_output}


def sample_actions(
    distribution: dict[str, jnp.ndarray],
    rng_key: chex.PRNGKey,
    *,
    action_type: str = "continuous",
) -> jnp.ndarray:
    """Sample continuous or categorical actions from the actor's output distribution."""
    if action_type == "continuous":
        noise = jax.random.normal(rng_key, shape=distribution["mean"].shape)
        return distribution["mean"] + distribution["std"] * noise
    return jax.random.categorical(rng_key, distribution["logits"])


def compute_log_prob(
    actions: jnp.ndarray,
    distribution: dict[str, jnp.ndarray],
    *,
    action_type: str = "continuous",
) -> jnp.ndarray:
    """Evaluate action log-probabilities under the actor's current policy distribution."""
    if action_type == "continuous":
        return stable_normal_log_prob(
            actions,
            distribution["mean"],
            distribution["log_std"],
        )
    logits = distribution["logits"]
    if actions.ndim > 1:
        actions = actions[:, 0]
    log_probs = jax.nn.log_softmax(logits, axis=-1)
    return log_probs[jnp.arange(actions.shape[0]), actions]


def compute_entropy(
    distribution: dict[str, jnp.ndarray],
    *,
    action_type: str = "continuous",
) -> jnp.ndarray:
    """Compute action-distribution entropy for continuous or categorical policies."""
    if action_type == "continuous":
        return stable_normal_entropy(distribution["log_std"])
    probs = jax.nn.softmax(distribution["logits"], axis=-1)
    return -jnp.sum(probs * jnp.log(clip_probability(probs)), axis=-1)
