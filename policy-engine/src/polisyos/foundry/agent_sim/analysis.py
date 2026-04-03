"""Inspect agent-policy behavior, clustering, and counterfactual sensitivity over runs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.actor_critic import ActorCritic, compute_entropy
from polisyos.foundry.agent_sim.state import GlobalState


@dataclass
class AgentCluster:
    """Describe one behavior cluster extracted from active agents in a simulation snapshot."""
    indices: jnp.ndarray
    centroid: jnp.ndarray
    size: int
    mean_wealth: float
    mean_income: float
    behavior_profile: dict[str, float]


class BehaviorAnalyzer:
    """Compute behavioral summaries and counterfactual diagnostics for trained policies."""
    @staticmethod
    def compute_action_statistics(
        actor: ActorCritic,
        states: Sequence[GlobalState],
        n_samples: int = 100,
        rng_key: jax.Array | None = None,
    ) -> dict[str, jnp.ndarray]:
        if rng_key is None:
            rng_key = jax.random.PRNGKey(0)

        states_seq = list(states)
        if n_samples and len(states_seq) > n_samples:
            idx = jax.random.choice(
                rng_key, len(states_seq), (n_samples,), replace=False
            )
            idx = jax.device_get(idx)
            states_seq = [states_seq[int(i)] for i in idx]

        all_means = []
        all_stds = []
        all_entropies = []

        for state in states_seq:
            from polisyos.foundry.agent_sim.temporal import build_temporal_observations

            obs = build_temporal_observations(state, horizon=256)
            action_out, _ = actor(obs, deterministic=True)
            dist = actor.get_action_distribution(obs, action_output=action_out)

            if actor.action_type == "continuous":
                all_means.append(dist["mean"])
                all_stds.append(dist["std"])
                all_entropies.append(
                    compute_entropy(dist, action_type=actor.action_type)
                )
            else:
                logits = dist["logits"]
                probs = jax.nn.softmax(logits, axis=-1)
                action_vals = jnp.arange(logits.shape[-1], dtype=probs.dtype)
                mean_action = jnp.sum(probs * action_vals, axis=-1)
                var_action = jnp.sum(
                    probs * (action_vals - mean_action[..., None]) ** 2,
                    axis=-1,
                )
                all_means.append(mean_action)
                all_stds.append(jnp.sqrt(var_action))
                all_entropies.append(
                    compute_entropy(dist, action_type=actor.action_type)
                )

        return {
            "mean_actions": jnp.stack(all_means) if all_means else None,
            "std_actions": jnp.stack(all_stds) if all_stds else None,
            "entropy": jnp.stack(all_entropies) if all_entropies else None,
        }

    @staticmethod
    def cluster_agents(
        state: GlobalState,
        n_clusters: int = 5,
        features: Sequence[str] = ("wealth", "income", "consumption"),
    ) -> list[AgentCluster]:
        agents = state.agents
        active = agents.active
        n_active = int(jnp.sum(active))
        if n_active == 0:
            return []

        n_clusters = int(min(n_clusters, n_active))

        feature_arrays = []
        for feat in features:
            feature_arrays.append(getattr(agents, feat))

        X = jnp.stack(feature_arrays, axis=-1)
        X_active = X[active]

        X_mean = jnp.mean(X_active, axis=0)
        X_std = jnp.std(X_active, axis=0) + 1e-8
        X_norm = (X_active - X_mean) / X_std

        key = jax.random.PRNGKey(42)
        centroids = X_norm[
            jax.random.choice(key, n_active, (n_clusters,), replace=False)
        ]

        for _ in range(20):
            distances = jnp.sum(
                (X_norm[:, None, :] - centroids[None, :, :]) ** 2,
                axis=-1,
            )
            assignments = jnp.argmin(distances, axis=1)

            new_centroids = []
            for k in range(n_clusters):
                mask = assignments == k
                if jnp.sum(mask) > 0:
                    new_centroids.append(jnp.mean(X_norm[mask], axis=0))
                else:
                    new_centroids.append(centroids[k])
            centroids = jnp.stack(new_centroids)

        clusters = []
        active_indices = jnp.where(active)[0]

        for k in range(n_clusters):
            mask = assignments == k
            cluster_indices = active_indices[mask]
            if cluster_indices.size > 0:
                clusters.append(
                    AgentCluster(
                        indices=cluster_indices,
                        centroid=centroids[k] * X_std + X_mean,
                        size=int(jnp.sum(mask)),
                        mean_wealth=float(jnp.mean(agents.wealth[cluster_indices])),
                        mean_income=float(jnp.mean(agents.income[cluster_indices])),
                        behavior_profile={
                            feat: float(jnp.mean(getattr(agents, feat)[cluster_indices]))
                            for feat in features
                        },
                    )
                )

        return sorted(clusters, key=lambda c: c.mean_wealth, reverse=True)

    @staticmethod
    def compute_mobility_matrix(
        initial_state: GlobalState,
        final_state: GlobalState,
        n_quantiles: int = 5,
    ) -> jnp.ndarray:
        initial_wealth = initial_state.agents.wealth
        final_wealth = final_state.agents.wealth
        active = initial_state.agents.active & final_state.agents.active
        active_count = int(jnp.sum(active))
        if active_count == 0:
            return jnp.zeros((n_quantiles, n_quantiles))

        initial_sorted = jnp.sort(initial_wealth[active])
        final_sorted = jnp.sort(final_wealth[active])

        initial_q = jnp.searchsorted(initial_sorted, initial_wealth[active])
        initial_q = initial_q * n_quantiles // active_count
        final_q = jnp.searchsorted(final_sorted, final_wealth[active])
        final_q = final_q * n_quantiles // active_count

        initial_q = jnp.clip(initial_q, 0, n_quantiles - 1)
        final_q = jnp.clip(final_q, 0, n_quantiles - 1)

        matrix = jnp.zeros((n_quantiles, n_quantiles))
        for i in range(n_quantiles):
            for j in range(n_quantiles):
                count = jnp.sum((initial_q == i) & (final_q == j))
                matrix = matrix.at[i, j].set(count)

        row_sums = jnp.sum(matrix, axis=1, keepdims=True)
        matrix = matrix / jnp.maximum(row_sums, 1.0)
        return matrix

    @staticmethod
    def compute_policy_sensitivity(
        actor: ActorCritic,
        state: GlobalState,
        feature_idx: int,
        delta: float = 0.1,
    ) -> jnp.ndarray:
        from polisyos.foundry.agent_sim.temporal import build_temporal_observations

        obs = build_temporal_observations(state, horizon=256)

        obs_plus = obs.at[:, feature_idx].add(delta)
        obs_minus = obs.at[:, feature_idx].add(-delta)

        action_plus, _ = actor(obs_plus, deterministic=True)
        action_minus, _ = actor(obs_minus, deterministic=True)

        sensitivity = (action_plus - action_minus) / (2 * delta)

        return sensitivity

    @staticmethod
    def counterfactual_analysis(
        actor: ActorCritic,
        state: GlobalState,
        policy_change: dict[str, float],
        executor,
        n_steps: int = 100,
    ) -> dict[str, jnp.ndarray]:
        del actor
        from polisyos.foundry.agent_sim.state import PolicyState

        def _gdp(current_state: GlobalState) -> jnp.ndarray:
            active = current_state.agents.active.astype(jnp.float32)
            return jnp.sum(current_state.agents.income * active)

        baseline_final, _ = executor.run(state, n_steps)

        new_policy = state.policy
        valid_keys = PolicyState.__annotations__.keys()
        for key, value in policy_change.items():
            if key in valid_keys:
                new_policy = new_policy.replace(**{key: jnp.array(value)})

        cf_state = state.replace(policy=new_policy)
        cf_final, _ = executor.run(cf_state, n_steps)

        baseline_gdp = _gdp(baseline_final)
        counterfactual_gdp = _gdp(cf_final)

        return {
            "baseline_gdp": baseline_gdp,
            "counterfactual_gdp": counterfactual_gdp,
            "baseline_gini": baseline_final.distributions.gini_wealth,
            "counterfactual_gini": cf_final.distributions.gini_wealth,
            "gdp_change": counterfactual_gdp - baseline_gdp,
            "gini_change": cf_final.distributions.gini_wealth
            - baseline_final.distributions.gini_wealth,
        }
