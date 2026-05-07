"""Public foundry agents module API."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from io import BytesIO
from pathlib import Path
from typing import Any

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.contracts.mechanism import Mechanism, PatchMap
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.methods.exceptions import ActionRoutingError, ObservationBindingError


def _activation_from_name(name: str) -> Callable[[jnp.ndarray], jnp.ndarray]:
    if name == "tanh":
        return jax.nn.tanh
    if name in {"", "relu"}:
        return jax.nn.relu
    raise ValueError(f"Unsupported activation '{name}'")


def _cas_root() -> Path:
    env = os.getenv("POLISYOS_CAS_ROOT")
    if env:
        return Path(env)
    return Path(".polisyos/cas")


def _load_policy_from_artifact(weights_artifact: str, template: eqx.Module) -> eqx.Module:
    artifact_id = ArtifactID.model_validate(weights_artifact)
    store = FileSystemCAS(_cas_root())
    payload = store.get_bytes(artifact_id)
    return eqx.tree_deserialise_leaves(BytesIO(payload), template)


def _as_feature(value: Any, n_agents: int) -> jnp.ndarray:
    arr = jnp.asarray(value, dtype=jnp.float32)
    if arr.shape == ():
        return jnp.full((n_agents,), arr, dtype=jnp.float32)
    if arr.shape[0] == n_agents:
        if arr.ndim == 1:
            return arr
        return jnp.mean(arr, axis=tuple(range(1, arr.ndim)))
    return jnp.full((n_agents,), jnp.mean(arr), dtype=jnp.float32)


def _apply_mask(mask: jnp.ndarray | None, value: jnp.ndarray, fallback: jnp.ndarray) -> jnp.ndarray:
    if mask is None:
        return value
    mask_arr = jnp.asarray(mask, dtype=jnp.bool_)
    if value.ndim > 1 and mask_arr.ndim == 1:
        mask_arr = mask_arr.reshape((mask_arr.shape[0],) + (1,) * (value.ndim - 1))
    return jnp.where(mask_arr, value, fallback)


def _combine_masks(
    target_mask: jnp.ndarray | None, active_mask: jnp.ndarray | None
) -> jnp.ndarray | None:
    if target_mask is None:
        return active_mask
    if active_mask is None:
        return target_mask
    return jnp.asarray(target_mask, dtype=jnp.bool_) & jnp.asarray(active_mask, dtype=jnp.bool_)


def _resolve_observation_value(
    state: GlobalState,
    field: str,
    overrides: Mapping[str, Any],
) -> Any:
    if field.startswith("agents."):
        subfield = field.split("agents.", 1)[1]
        value = getattr(state.agents, subfield, None)
        if value is None and field in overrides:
            value = overrides[field]
        if value is None:
            raise ObservationBindingError(field, "agents field is missing from state")
        return value
    if field.startswith(("global.", "policy.")):
        name = field.split(".", 1)[1]
        if name in overrides:
            value = overrides[name]
        else:
            value = getattr(state, name, None)
        if value is None and field in overrides:
            value = overrides[field]
        if value is None:
            raise ObservationBindingError(field, "global/policy field is missing from state")
        return value
    if "." in field:
        scope, slot = field.split(".", 1)
        container = getattr(state, scope, None)
        if container is not None and hasattr(container, slot):
            value = getattr(container, slot)
        elif field in overrides:
            value = overrides[field]
        else:
            value = None
        if value is None:
            raise ObservationBindingError(field, "scoped field is missing from state")
        return value
    if field in overrides:
        return overrides[field]
    value = getattr(state, field, None)
    if value is None:
        raise ObservationBindingError(field, "field is missing from state")
    return value


def build_observations(
    state: GlobalState,
    observation_space: Iterable[str],
    *,
    overrides: Mapping[str, Any] | None = None,
) -> jnp.ndarray:
    """Build observations."""
    n_agents = state.agents.size
    override_values = overrides or {}
    features: list[jnp.ndarray] = []
    for field in observation_space:
        value = _resolve_observation_value(state, field, override_values)
        features.append(_as_feature(value, n_agents))
    if not features:
        return jnp.zeros((n_agents, 0), dtype=jnp.float32)
    return jnp.stack(features, axis=1)


def _range_scale(range_spec: Any, values: jnp.ndarray) -> jnp.ndarray:
    if range_spec is None:
        return values
    if not isinstance(range_spec, (list, tuple)) or len(range_spec) != 2:
        raise ActionRoutingError("range", "range must be a 2-item list or tuple")
    lower_raw, upper_raw = range_spec
    if not isinstance(lower_raw, (int, float)) or not isinstance(upper_raw, (int, float)):
        raise ActionRoutingError("range", "range endpoints must be numeric")
    lower = float(lower_raw)
    upper = float(upper_raw)
    return lower + (upper - lower) * values


def continuous_actions_from_logits(
    logits: jnp.ndarray,
    action_space: Mapping[str, Any],
    *,
    key: jax.Array | None = None,
    stochastic: bool = False,
) -> jnp.ndarray:
    """Continuous actions from logits helper."""
    action_val = jax.nn.sigmoid(logits)
    if stochastic and key is not None:
        noise = 0.01 * jax.random.normal(key, shape=action_val.shape)
        action_val = jnp.clip(action_val + noise, 0.0, 1.0)
    action_val = _range_scale(action_space.get("range"), action_val)
    if action_val.ndim == 2 and action_val.shape[1] == 1:
        action_val = action_val[:, 0]
    return action_val


class AgentPolicy(eqx.Module):
    """Agent policy data model."""

    layers: tuple[eqx.nn.Linear, ...]
    activation: Callable[[jnp.ndarray], jnp.ndarray] = eqx.field(static=True)
    action_type: str = eqx.field(static=True)
    out_dim: int = eqx.field(static=True)

    def __init__(
        self,
        key: jax.Array,
        in_dim: int,
        action_type: str,
        out_dim: int,
        *,
        hidden_layers: Iterable[int] = (64, 64),
        activation: str = "relu",
    ):
        self.action_type = action_type
        self.out_dim = int(out_dim)
        hidden = tuple(int(val) for val in hidden_layers)
        layer_sizes = (int(in_dim),) + hidden + (self.out_dim,)
        keys = jax.random.split(key, max(len(layer_sizes) - 1, 1))
        self.layers = tuple(
            eqx.nn.Linear(layer_sizes[i], layer_sizes[i + 1], key=keys[i])
            for i in range(len(layer_sizes) - 1)
        )
        self.activation = _activation_from_name(activation)

    def __call__(self, obs: jnp.ndarray) -> jnp.ndarray:
        x = obs
        if not self.layers:
            return x

        # `eqx.nn.Linear` is defined for a single feature vector (in_dim,).
        # In our usage, observations are often batched as (batch, in_dim),
        # so we `vmap` the layer application over the leading dimension.
        if x.ndim == 1:
            for layer in self.layers[:-1]:
                x = self.activation(layer(x))
            return self.layers[-1](x)

        if x.ndim == 2:
            # Feature-wise normalization helps keep heterogeneous features
            # (e.g. income vs risk) on comparable scales and avoids activation
            # saturation that can collapse actions to a constant.
            mean = jnp.mean(x, axis=0, keepdims=True)
            std = jnp.std(x, axis=0, keepdims=True)
            x = (x - mean) / (std + 1e-6)

            for layer in self.layers[:-1]:
                x = jax.vmap(layer)(x)
                x = self.activation(x)
            return jax.vmap(self.layers[-1])(x)

        raise ValueError(f"AgentPolicy expected obs ndim 1 or 2, got shape={x.shape!r}")


class AdaptiveAgentMechanism(Mechanism):
    """Adaptive agent mechanism public type."""

    policy: AgentPolicy
    action_space: dict[str, Any] = eqx.field(static=True)
    observation_space: tuple[str, ...] = eqx.field(static=True)
    utility: str | None = eqx.field(static=True)
    learning_rate: float = eqx.field(static=True)
    optimizer: optax.GradientTransformation = eqx.field(static=True)
    opt_state: optax.OptState | None
    stochastic: bool = eqx.field(static=True)
    tax_rate_value: jnp.ndarray | None = eqx.field(default=None, static=True)

    def __init__(
        self,
        observation_space: list[str],
        action_space: dict[str, Any],
        utility: str | None = None,
        policy_model: dict[str, Any] | None = None,
        weights_artifact: str | None = None,
        learning_rate: float | None = 0.01,
        *,
        seed: int | None = None,
        stochastic: bool = True,
        init_opt: bool = True,
        debug_mode: bool = False,
        **kwargs: Any,
    ):
        if observation_space is None:
            observation_space = []
        if not isinstance(observation_space, list):
            raise ValueError("AdaptiveAgentMechanism observation_space must be a list")
        if any(not isinstance(field, str) or not field.strip() for field in observation_space):
            raise ObservationBindingError(
                "observation_space", "all observation fields must be non-empty strings"
            )
        if not isinstance(action_space, dict):
            raise ValueError("AdaptiveAgentMechanism action_space must be a dict")

        self.observation_space = tuple(observation_space)
        self.action_space = action_space
        self.utility = utility
        self.stochastic = bool(stochastic)
        self.debug_mode = bool(debug_mode)
        self.tax_rate_value = None

        obs_dim = len(self.observation_space)
        action_type = action_space.get("type", "continuous")
        if action_type not in {"continuous", "discrete"}:
            raise ActionRoutingError(str(action_type), "unsupported action type")
        affects = action_space.get("affects")
        if isinstance(affects, str):
            affects_values = [affects]
        elif isinstance(affects, list):
            affects_values = affects
        else:
            affects_values = []
        if not affects_values or any(
            not isinstance(item, str) or not item.strip() for item in affects_values
        ):
            raise ActionRoutingError("affects", "must contain at least one non-empty slot target")
        if any(not item.startswith("agents.") for item in affects_values):
            raise ActionRoutingError(
                "affects", "all action targets must use the agents.* namespace"
            )
        out_dim = None
        if action_type == "discrete":
            out_dim = (
                action_space.get("n_categories")
                or action_space.get("num_choices")
                or action_space.get("dim")
            )
            out_dim = int(out_dim) if out_dim is not None else 2
        else:
            out_dim = action_space.get("dim")
            if out_dim is None:
                out_dim = len(affects) if isinstance(affects, list) else 1
            out_dim = int(out_dim)

        policy_model = policy_model or {}
        model_type = policy_model.get("type", "mlp")
        if model_type != "mlp":
            raise ValueError(f"Unsupported policy_model.type '{model_type}'")
        hidden_layers = policy_model.get("hidden_layers")
        if hidden_layers is None:
            hidden_layers = (64, 64)
        activation = policy_model.get("activation") or "relu"

        key = jax.random.PRNGKey(int(seed) if seed is not None else 0)
        if weights_artifact:
            template = AgentPolicy(
                key,
                obs_dim,
                action_type,
                out_dim,
                hidden_layers=hidden_layers,
                activation=activation,
            )
            self.policy = _load_policy_from_artifact(weights_artifact, template)
        else:
            self.policy = AgentPolicy(
                key,
                obs_dim,
                action_type,
                out_dim,
                hidden_layers=hidden_layers,
                activation=activation,
            )

        lr = 0.01 if learning_rate is None else float(learning_rate)
        self.learning_rate = lr if lr > 0 else 0.01
        self.optimizer = optax.sgd(self.learning_rate)
        self.opt_state = None
        if init_opt:
            self.opt_state = self.optimizer.init(eqx.filter(self.policy, eqx.is_inexact_array))

    def with_runtime_overrides(self, **overrides: Any) -> AdaptiveAgentMechanism:
        """Return a copy with explicit runtime override fields applied."""
        updated: AdaptiveAgentMechanism = self
        for field_name, value in overrides.items():
            if not hasattr(updated, field_name):
                raise ObservationBindingError(field_name, "runtime override field does not exist")
            updated = eqx.tree_at(lambda mech: getattr(mech, field_name), updated, value)
        return updated

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        if hasattr(state.agents, "reported_income"):
            new_agents = state.agents.replace(reported_income=state.agents.income)
            state = state.replace(agents=new_agents)
        return state, key

    def _extract_observations(self, state: GlobalState) -> jnp.ndarray:
        overrides: dict[str, Any] = {}
        for field in self.observation_space:
            if field.startswith(("global.", "policy.")):
                name = field.split(".", 1)[1]
                override_value = getattr(self, f"{name}_value", None)
                if override_value is not None:
                    overrides[name] = override_value
        return build_observations(state, self.observation_space, overrides=overrides)

    def emit_patches(
        self,
        state: GlobalState,
        key: jax.Array,
        *,
        target_mask=None,
    ) -> tuple[PatchMap, jax.Array]:
        active_mask = getattr(state.agents, "active", None)
        effective_mask = _combine_masks(target_mask, active_mask)
        obs = self._extract_observations(state)
        logits = self.policy(obs)
        n_agents = obs.shape[0] if obs.ndim > 0 else state.agents.size
        action_type = self.action_space.get("type", "continuous")
        affects = self.action_space.get("affects")
        affects_list = []
        if isinstance(affects, str):
            affects_list = [affects]
        elif isinstance(affects, list):
            affects_list = [item for item in affects if isinstance(item, str)]

        patches: PatchMap = {}
        if not affects_list:
            raise ActionRoutingError("affects", "no valid action targets were configured")
        if n_agents == 0:
            return patches, key
        if action_type == "discrete":
            probs = jax.nn.softmax(logits, axis=-1)
            if self.stochastic and key is not None:
                subkeys = jax.random.split(key, n_agents)
                action_idx = jax.vmap(lambda pk, p: jax.random.categorical(pk, jnp.log(p)))(
                    subkeys, probs
                )
            else:
                action_idx = jnp.argmax(probs, axis=-1)
            action_idx = action_idx.astype(jnp.int32)
            for slot_id in affects_list:
                if not slot_id.startswith("agents."):
                    raise ActionRoutingError(slot_id, "only agents.* targets are supported")
                field_name = slot_id.split("agents.", 1)[1]
                current = getattr(state.agents, field_name, None)
                if current is None:
                    raise ActionRoutingError(slot_id, "target field is missing from state.agents")
                if jnp.issubdtype(current.dtype, jnp.bool_):
                    new_value = (
                        action_idx.astype(jnp.bool_) if probs.shape[-1] == 2 else action_idx > 0
                    )
                else:
                    new_value = action_idx.astype(current.dtype)
                new_value = _apply_mask(effective_mask, new_value, current)
                patches[slot_id] = [{"value": new_value}]
            if self.debug_mode and affects_list:
                avg_action = jnp.mean(action_idx.astype(jnp.float32))
                jax.debug.print("AdaptiveAgent discrete avg_action={x:.3f}", x=avg_action)
            return patches, key

        action_val = continuous_actions_from_logits(
            logits,
            self.action_space,
            key=key,
            stochastic=self.stochastic,
        )

        for idx, slot_id in enumerate(affects_list or []):
            if not slot_id.startswith("agents."):
                raise ActionRoutingError(slot_id, "only agents.* targets are supported")
            field_name = slot_id.split("agents.", 1)[1]
            current = getattr(state.agents, field_name, None)
            if current is None:
                raise ActionRoutingError(slot_id, "target field is missing from state.agents")
            if action_val.ndim == 1:
                chosen_val = action_val
            else:
                col = idx if action_val.shape[1] == len(affects_list) else 0
                chosen_val = action_val[:, col]
            if slot_id == "agents.reported_income":
                new_value = state.agents.income * chosen_val
            else:
                new_value = chosen_val.astype(current.dtype)
            new_value = _apply_mask(effective_mask, new_value, current)
            patches[slot_id] = [{"value": new_value}]

        if self.debug_mode and affects_list:
            avg_action = jnp.mean(action_val if action_val.ndim == 1 else action_val[:, 0])
            jax.debug.print("AdaptiveAgent continuous avg_action={x:.3f}", x=avg_action)
        return patches, key
