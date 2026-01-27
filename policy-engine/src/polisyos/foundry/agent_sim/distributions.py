from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import chex
import jax
import jax.numpy as jnp
from jaxtyping import Array, Bool, Float, Int

if TYPE_CHECKING:
    from polisyos.foundry.agent_sim.state import GlobalState


class ComputeMode(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    CACHED = "cached"


@chex.dataclass(frozen=True)
class DistributionConfig:
    mode: ComputeMode = ComputeMode.HARD
    update_frequency: int = 8
    soft_temperature: float = 1.0
    n_quantiles: int = 10
    use_approximate: bool = True
    approximate_sample_size: int = 1000


@chex.dataclass(frozen=True)
class DistributionState:
    last_update_step: Int[Array, ""]
    wealth_quantiles: Float[Array, "n_quantiles"]
    income_quantiles: Float[Array, "n_quantiles"]
    consumption_quantiles: Float[Array, "n_quantiles"]
    wealth_ranks: Float[Array, "n_agents"]
    income_ranks: Float[Array, "n_agents"]
    gini_wealth: Float[Array, ""]
    gini_income: Float[Array, ""]
    top_10_share: Float[Array, ""]
    bottom_50_share: Float[Array, ""]

    @classmethod
    def empty(cls, n_agents: int, *, n_quantiles: int = 10) -> "DistributionState":
        zeros_q = jnp.zeros((n_quantiles,), dtype=jnp.float32)
        zeros_n = jnp.zeros((n_agents,), dtype=jnp.float32)
        return cls(
            last_update_step=jnp.array(-1, dtype=jnp.int32),
            wealth_quantiles=zeros_q,
            income_quantiles=zeros_q,
            consumption_quantiles=zeros_q,
            wealth_ranks=zeros_n,
            income_ranks=zeros_n,
            gini_wealth=jnp.array(0.0, dtype=jnp.float32),
            gini_income=jnp.array(0.0, dtype=jnp.float32),
            top_10_share=jnp.array(0.0, dtype=jnp.float32),
            bottom_50_share=jnp.array(0.0, dtype=jnp.float32),
        )


@chex.dataclass(frozen=True)
class CompactDistributionState:
    wealth_deciles: Float[Array, "10"]
    income_deciles: Float[Array, "10"]
    gini_wealth: Float[Array, ""]
    gini_income: Float[Array, ""]
    top_1_wealth_share: Float[Array, ""]
    top_10_wealth_share: Float[Array, ""]
    bottom_50_wealth_share: Float[Array, ""]
    last_update_step: Int[Array, ""]


def maybe_update_distributions(state: "GlobalState", config: DistributionConfig) -> "GlobalState":
    last_step = state.distributions.last_update_step
    needs_update = (last_step < 0) | (
        (state.time_step - last_step) >= config.update_frequency
    )

    def _update(s: "GlobalState") -> DistributionState:
        return compute_all_distributions(s, config)

    new_distributions = jax.lax.cond(
        needs_update,
        _update,
        lambda s: s.distributions,
        operand=state,
    )
    return state.replace(distributions=new_distributions)


def compute_all_distributions(
    state: "GlobalState",
    config: DistributionConfig,
) -> DistributionState:
    agents = state.agents
    active = agents.active
    mode = ComputeMode.HARD if config.mode == ComputeMode.CACHED else config.mode

    rng_key = jax.random.fold_in(state.rng_key, state.time_step)

    wealth_quantiles = compute_quantiles(
        agents.wealth,
        active,
        config.n_quantiles,
        mode=mode,
        temperature=config.soft_temperature,
        use_approximate=config.use_approximate,
        rng_key=rng_key,
        sample_size=config.approximate_sample_size,
    )
    wealth_ranks = compute_ranks(
        agents.wealth,
        active,
        mode=mode,
        temperature=config.soft_temperature,
    )

    income_quantiles = compute_quantiles(
        agents.income,
        active,
        config.n_quantiles,
        mode=mode,
        temperature=config.soft_temperature,
        use_approximate=config.use_approximate,
        rng_key=jax.random.fold_in(rng_key, 1),
        sample_size=config.approximate_sample_size,
    )
    income_ranks = compute_ranks(
        agents.income,
        active,
        mode=mode,
        temperature=config.soft_temperature,
    )

    consumption_quantiles = compute_quantiles(
        agents.consumption,
        active,
        config.n_quantiles,
        mode=mode,
        temperature=config.soft_temperature,
        use_approximate=config.use_approximate,
        rng_key=jax.random.fold_in(rng_key, 2),
        sample_size=config.approximate_sample_size,
    )

    gini_wealth = compute_gini(
        agents.wealth,
        active,
        mode=mode,
        temperature=config.soft_temperature,
    )
    gini_income = compute_gini(
        agents.income,
        active,
        mode=mode,
        temperature=config.soft_temperature,
    )

    top_10_share = compute_top_share(
        agents.wealth,
        active,
        0.10,
        ranks=wealth_ranks,
    )
    bottom_50_share = compute_bottom_share(
        agents.wealth,
        active,
        0.50,
        ranks=wealth_ranks,
    )

    return DistributionState(
        last_update_step=state.time_step,
        wealth_quantiles=wealth_quantiles,
        income_quantiles=income_quantiles,
        consumption_quantiles=consumption_quantiles,
        wealth_ranks=wealth_ranks,
        income_ranks=income_ranks,
        gini_wealth=gini_wealth,
        gini_income=gini_income,
        top_10_share=top_10_share,
        bottom_50_share=bottom_50_share,
    )


def compute_quantiles(
    values: jnp.ndarray,
    active: jnp.ndarray,
    n_quantiles: int,
    *,
    mode: ComputeMode = ComputeMode.HARD,
    temperature: float = 1.0,
    use_approximate: bool = True,
    rng_key: chex.PRNGKey | None = None,
    sample_size: int = 1000,
) -> jnp.ndarray:
    if mode == ComputeMode.SOFT:
        return compute_quantiles_soft(values, active, n_quantiles, temperature=temperature)
    if use_approximate and rng_key is not None:
        return compute_quantiles_approximate(
            values,
            active,
            n_quantiles,
            rng_key=rng_key,
            sample_size=sample_size,
        )
    return compute_quantiles_hard(values, active, n_quantiles)


def compute_ranks(
    values: jnp.ndarray,
    active: jnp.ndarray,
    *,
    mode: ComputeMode = ComputeMode.HARD,
    temperature: float = 1.0,
) -> jnp.ndarray:
    if mode == ComputeMode.SOFT:
        return compute_ranks_soft(values, active, temperature=temperature)
    return compute_ranks_hard(values, active)


def compute_quantiles_hard(
    values: jnp.ndarray,
    active: jnp.ndarray,
    n_quantiles: int,
) -> jnp.ndarray:
    n_agents = values.shape[0]
    n_active = jnp.sum(active).astype(jnp.int32)

    def _no_active():
        return jnp.zeros((n_quantiles,), dtype=values.dtype)

    def _with_active():
        masked_values = jnp.where(active, values, -jnp.inf)
        sorted_values = jnp.sort(masked_values)
        fractions = jnp.linspace(0.0, 1.0, n_quantiles + 1, dtype=jnp.float32)[1:]
        idx = (fractions * (n_active - 1)).astype(jnp.int32)
        n_inactive = n_agents - n_active
        idx = idx + n_inactive
        idx = jnp.clip(idx, 0, n_agents - 1)
        return sorted_values[idx]

    return jax.lax.cond(n_active > 0, _with_active, _no_active)


def compute_ranks_hard(values: jnp.ndarray, active: jnp.ndarray) -> jnp.ndarray:
    n_active = jnp.sum(active).astype(jnp.float32)
    safe_n = jnp.maximum(n_active - 1.0, 1.0)
    masked_values = jnp.where(active, values, jnp.inf)
    sorted_indices = jnp.argsort(masked_values)
    ranks = jnp.zeros(values.shape[0], dtype=jnp.float32)
    ranks = ranks.at[sorted_indices].set(jnp.arange(values.shape[0], dtype=jnp.float32))
    ranks = ranks / safe_n
    return jnp.where(active, ranks, 0.0)


def soft_sort(values: jnp.ndarray, *, temperature: float = 1.0, n_iters: int = 10) -> jnp.ndarray:
    target = jnp.sort(values)
    cost = (values[:, None] - target[None, :]) ** 2
    log_p = -cost / temperature

    def _sinkhorn(_, log_p):
        log_p = log_p - jax.nn.logsumexp(log_p, axis=1, keepdims=True)
        log_p = log_p - jax.nn.logsumexp(log_p, axis=0, keepdims=True)
        return log_p

    log_p = jax.lax.fori_loop(0, int(n_iters), _sinkhorn, log_p)
    perm = jnp.exp(log_p)
    return perm @ target


def soft_rank(values: jnp.ndarray, *, temperature: float = 1.0) -> jnp.ndarray:
    diff = values[:, None] - values[None, :]
    soft_comp = jax.nn.sigmoid(diff / temperature)
    ranks = jnp.sum(soft_comp, axis=1) - 0.5
    return ranks / jnp.maximum(values.shape[0] - 1, 1)


def compute_quantiles_soft(
    values: jnp.ndarray,
    active: jnp.ndarray,
    n_quantiles: int,
    *,
    temperature: float = 1.0,
) -> jnp.ndarray:
    n_agents = values.shape[0]
    n_active = jnp.sum(active).astype(jnp.int32)

    def _no_active():
        return jnp.zeros((n_quantiles,), dtype=values.dtype)

    def _with_active():
        masked_values = jnp.where(active, values, -1e6)
        soft_sorted = soft_sort(masked_values, temperature=temperature)
        fractions = jnp.linspace(0.0, 1.0, n_quantiles + 1, dtype=jnp.float32)[1:]
        idx_f = fractions * (n_active - 1)
        lower = jnp.floor(idx_f).astype(jnp.int32)
        upper = jnp.ceil(idx_f).astype(jnp.int32)
        weights = idx_f - lower
        n_inactive = n_agents - n_active
        lower = jnp.clip(lower + n_inactive, 0, n_agents - 1)
        upper = jnp.clip(upper + n_inactive, 0, n_agents - 1)
        return (1.0 - weights) * soft_sorted[lower] + weights * soft_sorted[upper]

    return jax.lax.cond(n_active > 0, _with_active, _no_active)


def compute_ranks_soft(
    values: jnp.ndarray,
    active: jnp.ndarray,
    *,
    temperature: float = 1.0,
) -> jnp.ndarray:
    masked_values = jnp.where(active, values, -1e6)
    ranks = soft_rank(masked_values, temperature=temperature)
    return jnp.where(active, ranks, 0.0)


def compute_quantiles_approximate(
    values: jnp.ndarray,
    active: jnp.ndarray,
    n_quantiles: int,
    *,
    rng_key: chex.PRNGKey,
    sample_size: int = 1000,
) -> jnp.ndarray:
    n_active = jnp.sum(active)
    sample_size = min(int(sample_size), values.shape[0])

    def _no_active():
        return jnp.zeros((n_quantiles,), dtype=values.dtype)

    def _with_active():
        weights = active.astype(jnp.float32)
        weights = weights / jnp.maximum(jnp.sum(weights), 1.0)
        indices = jax.random.choice(
            rng_key,
            values.shape[0],
            shape=(sample_size,),
            replace=True,
            p=weights,
        )
        sample = values[indices]
        sorted_sample = jnp.sort(sample)
        fractions = jnp.linspace(0.0, 1.0, n_quantiles + 1, dtype=jnp.float32)[1:]
        idx = (fractions * (sample_size - 1)).astype(jnp.int32)
        return sorted_sample[idx]

    return jax.lax.cond(n_active > 0, _with_active, _no_active)


def compute_gini(
    values: jnp.ndarray,
    active: jnp.ndarray,
    *,
    mode: ComputeMode = ComputeMode.HARD,
    temperature: float = 1.0,
) -> jnp.ndarray:
    if mode == ComputeMode.SOFT:
        return compute_gini_soft(values, active, temperature=temperature)
    return compute_gini_hard(values, active)


def compute_gini_hard(values: jnp.ndarray, active: jnp.ndarray) -> jnp.ndarray:
    n_agents = values.shape[0]
    n_active = jnp.sum(active).astype(jnp.int32)

    def _no_active():
        return jnp.array(0.0, dtype=jnp.float32)

    def _with_active():
        masked = jnp.where(active, values, jnp.inf)
        sorted_values = jnp.sort(masked)
        active_mask = jnp.arange(n_agents) < n_active
        sorted_values = jnp.where(active_mask, sorted_values, 0.0)
        indices = jnp.arange(n_agents, dtype=jnp.float32) + 1.0
        indices = jnp.where(active_mask, indices, 0.0)
        total = jnp.sum(sorted_values)
        weighted_sum = jnp.sum(indices * sorted_values)
        n_act = n_active.astype(jnp.float32)
        return (2.0 * weighted_sum) / (n_act * total + 1e-8) - (n_act + 1.0) / (
            n_act + 1e-8
        )

    return jax.lax.cond(n_active > 0, _with_active, _no_active)


def compute_gini_soft(
    values: jnp.ndarray,
    active: jnp.ndarray,
    *,
    temperature: float = 1.0,
) -> jnp.ndarray:
    n_active = jnp.sum(active).astype(jnp.float32)
    ranks = compute_ranks_soft(values, active, temperature=temperature)
    masked_values = jnp.where(active, values, 0.0)
    masked_ranks = jnp.where(active, ranks, 0.0)
    mean_value = jnp.sum(masked_values) / jnp.maximum(n_active, 1.0)
    cov = jnp.sum(masked_ranks * masked_values) / jnp.maximum(n_active, 1.0) - 0.5 * mean_value
    return 2.0 * cov / (mean_value + 1e-8)


def compute_gini_proxy(values: jnp.ndarray, active: jnp.ndarray) -> jnp.ndarray:
    n_active = jnp.sum(active).astype(jnp.float32)
    masked = jnp.where(active, values, 0.0)
    mean_value = jnp.sum(masked) / jnp.maximum(n_active, 1.0)
    mad = jnp.sum(jnp.abs(masked - mean_value) * active) / jnp.maximum(n_active, 1.0)
    return mad / (2.0 * mean_value + 1e-8)


def compute_top_share(
    values: jnp.ndarray,
    active: jnp.ndarray,
    top_fraction: float = 0.10,
    *,
    ranks: jnp.ndarray | None = None,
) -> jnp.ndarray:
    total = jnp.sum(values * active)
    if ranks is not None:
        threshold = 1.0 - float(top_fraction)
        top_mask = (ranks >= threshold) & active
        top_total = jnp.sum(values * top_mask)
        return top_total / (total + 1e-8)

    n_agents = values.shape[0]
    n_active = jnp.sum(active).astype(jnp.int32)

    def _topk():
        k = max(1, int(n_agents * top_fraction))
        top_values, _ = jax.lax.top_k(values, k)
        top_total = jnp.sum(top_values)
        return top_total / (total + 1e-8)

    def _ranks():
        computed_ranks = compute_ranks_hard(values, active)
        threshold = 1.0 - float(top_fraction)
        top_mask = (computed_ranks >= threshold) & active
        top_total = jnp.sum(values * top_mask)
        return top_total / (total + 1e-8)

    return jax.lax.cond(n_active == n_agents, _topk, _ranks)


def compute_bottom_share(
    values: jnp.ndarray,
    active: jnp.ndarray,
    bottom_fraction: float = 0.50,
    *,
    ranks: jnp.ndarray | None = None,
) -> jnp.ndarray:
    total = jnp.sum(values * active)
    if ranks is not None:
        threshold = float(bottom_fraction)
        bottom_mask = (ranks <= threshold) & active
        bottom_total = jnp.sum(values * bottom_mask)
        return bottom_total / (total + 1e-8)

    n_agents = values.shape[0]
    n_active = jnp.sum(active).astype(jnp.int32)

    def _topk():
        k = max(1, int(n_agents * bottom_fraction))
        neg_values, _ = jax.lax.top_k(-values, k)
        bottom_total = jnp.sum(-neg_values)
        return bottom_total / (total + 1e-8)

    def _ranks():
        computed_ranks = compute_ranks_hard(values, active)
        threshold = float(bottom_fraction)
        bottom_mask = (computed_ranks <= threshold) & active
        bottom_total = jnp.sum(values * bottom_mask)
        return bottom_total / (total + 1e-8)

    return jax.lax.cond(n_active == n_agents, _topk, _ranks)


def compute_palma_ratio(values: jnp.ndarray, active: jnp.ndarray) -> jnp.ndarray:
    top_10 = compute_top_share(values, active, 0.10)
    bottom_40 = compute_bottom_share(values, active, 0.40)
    return top_10 / (bottom_40 + 1e-8)


def compute_percentile_ratios(values: jnp.ndarray, active: jnp.ndarray) -> dict[str, jnp.ndarray]:
    quantiles = compute_quantiles_hard(values, active, 100)
    return {
        "p90_p10": quantiles[89] / (quantiles[9] + 1e-8),
        "p90_p50": quantiles[89] / (quantiles[49] + 1e-8),
        "p50_p10": quantiles[49] / (quantiles[9] + 1e-8),
    }


def compute_rank_correlation(
    values_t: jnp.ndarray,
    values_t_plus_k: jnp.ndarray,
    active: jnp.ndarray,
) -> jnp.ndarray:
    ranks_t = compute_ranks_hard(values_t, active)
    ranks_k = compute_ranks_hard(values_t_plus_k, active)
    n_active = jnp.sum(active).astype(jnp.float32)
    mean_rank = 0.5
    cov = jnp.sum((ranks_t - mean_rank) * (ranks_k - mean_rank) * active) / jnp.maximum(
        n_active, 1.0
    )
    var_t = jnp.sum((ranks_t - mean_rank) ** 2 * active) / jnp.maximum(n_active, 1.0)
    var_k = jnp.sum((ranks_k - mean_rank) ** 2 * active) / jnp.maximum(n_active, 1.0)
    return cov / (jnp.sqrt(var_t * var_k) + 1e-8)


def compute_transition_matrix(
    values_t: jnp.ndarray,
    values_t_plus_k: jnp.ndarray,
    active: jnp.ndarray,
    *,
    n_bins: int = 5,
) -> jnp.ndarray:
    ranks_t = compute_ranks_hard(values_t, active)
    ranks_k = compute_ranks_hard(values_t_plus_k, active)
    bins_t = jnp.clip(jnp.floor(ranks_t * n_bins), 0, n_bins - 1).astype(jnp.int32)
    bins_k = jnp.clip(jnp.floor(ranks_k * n_bins), 0, n_bins - 1).astype(jnp.int32)
    mask = active.astype(jnp.float32)
    onehot_t = jax.nn.one_hot(bins_t, n_bins) * mask[:, None]
    onehot_k = jax.nn.one_hot(bins_k, n_bins)
    counts = onehot_t.T @ onehot_k
    row_sums = jnp.sum(counts, axis=1, keepdims=True)
    return counts / (row_sums + 1e-8)


class AgentGrouping:
    @staticmethod
    def by_quantile(values: jnp.ndarray, active: jnp.ndarray, n_groups: int) -> jnp.ndarray:
        ranks = compute_ranks_hard(values, active)
        groups = jnp.floor(ranks * n_groups).astype(jnp.int32)
        groups = jnp.clip(groups, 0, n_groups - 1)
        return jnp.where(active, groups, -1)

    @staticmethod
    def by_threshold(
        values: jnp.ndarray,
        active: jnp.ndarray,
        thresholds: jnp.ndarray,
    ) -> jnp.ndarray:
        above = values[:, None] >= thresholds[None, :]
        groups = jnp.sum(above, axis=1).astype(jnp.int32)
        return jnp.where(active, groups, -1)

    @staticmethod
    def by_multiple_criteria(
        criteria: dict[str, jnp.ndarray],
        active: jnp.ndarray,
        *,
        n_bins_per_criterion: int = 3,
    ) -> jnp.ndarray:
        group_ids = jnp.zeros(active.shape[0], dtype=jnp.int32)
        multiplier = 1
        for _, values in criteria.items():
            ranks = compute_ranks_hard(values, active)
            bins = jnp.floor(ranks * n_bins_per_criterion).astype(jnp.int32)
            bins = jnp.clip(bins, 0, n_bins_per_criterion - 1)
            group_ids = group_ids + bins * multiplier
            multiplier *= n_bins_per_criterion
        return jnp.where(active, group_ids, -1)


def compute_group_statistics(
    values: jnp.ndarray,
    groups: jnp.ndarray,
    active: jnp.ndarray,
    n_groups: int,
) -> dict[str, jnp.ndarray]:
    group_ids = jnp.arange(n_groups)

    def _stats_for_group(gid):
        mask = (groups == gid) & active
        count = jnp.sum(mask)
        mean = jnp.sum(values * mask) / (count + 1e-8)
        var = jnp.sum((values - mean) ** 2 * mask) / (count + 1e-8)
        min_val = jnp.min(jnp.where(mask, values, jnp.inf))
        max_val = jnp.max(jnp.where(mask, values, -jnp.inf))
        return mean, jnp.sqrt(var), min_val, max_val, count

    means, stds, mins, maxs, counts = jax.vmap(_stats_for_group)(group_ids)
    return {
        "mean": means,
        "std": stds,
        "min": mins,
        "max": maxs,
        "count": counts,
    }


def batch_compute_group_means(values: jnp.ndarray, groups: jnp.ndarray, n_groups: int) -> jnp.ndarray:
    group_onehot = jax.nn.one_hot(groups, n_groups)
    group_sums = jnp.sum(values[:, None] * group_onehot, axis=0)
    group_counts = jnp.sum(group_onehot, axis=0)
    return group_sums / (group_counts + 1e-8)


def batch_assign_to_quantile_groups(
    values: jnp.ndarray,
    quantiles: jnp.ndarray,
    active: jnp.ndarray,
) -> jnp.ndarray:
    above = values[:, None] >= quantiles[None, :]
    groups = jnp.sum(above, axis=1).astype(jnp.int32)
    groups = jnp.clip(groups, 0, quantiles.shape[0])
    return jnp.where(active, groups, -1)


def compress_distribution_state(
    full_state: DistributionState,
    *,
    wealth_values: jnp.ndarray | None = None,
    wealth_active: jnp.ndarray | None = None,
) -> CompactDistributionState:
    top_1 = full_state.top_10_share
    if wealth_values is not None and wealth_active is not None:
        top_1 = compute_top_share(wealth_values, wealth_active, 0.01)
    return CompactDistributionState(
        wealth_deciles=full_state.wealth_quantiles,
        income_deciles=full_state.income_quantiles,
        gini_wealth=full_state.gini_wealth,
        gini_income=full_state.gini_income,
        top_1_wealth_share=top_1,
        top_10_wealth_share=full_state.top_10_share,
        bottom_50_wealth_share=full_state.bottom_50_share,
        last_update_step=full_state.last_update_step,
    )


@dataclass
class RewardConfig:
    reward_mobility: bool = False
    penalize_inequality: bool = False
    mobility_weight: float = 0.1
    inequality_weight: float = 1.0


def compute_distribution_aware_reward(
    state: "GlobalState",
    next_state: "GlobalState",
    config: RewardConfig,
) -> jnp.ndarray:
    from polisyos.foundry.agent_sim.rewards import UtilityFunction

    agents = next_state.agents
    base_reward = UtilityFunction.crra(agents.consumption, agents.risk_aversion)
    base_reward = base_reward + agents.utility_adjustment

    if config.reward_mobility:
        rank_change = next_state.distributions.wealth_ranks - state.distributions.wealth_ranks
        base_reward = base_reward + config.mobility_weight * rank_change

    if config.penalize_inequality:
        gini = next_state.distributions.gini_wealth
        base_reward = base_reward - config.inequality_weight * gini

    return jnp.where(agents.active, base_reward, 0.0)


class AdaptiveUpdateStrategy:
    def __init__(
        self,
        base_frequency: int = 8,
        min_frequency: int = 2,
        max_frequency: int = 32,
        change_threshold: float = 0.05,
    ):
        self.base_frequency = base_frequency
        self.min_frequency = min_frequency
        self.max_frequency = max_frequency
        self.change_threshold = change_threshold
        self.last_gini = None
        self.current_frequency = base_frequency

    def should_update(self, state: "GlobalState", step: int) -> bool:
        if step % self.current_frequency != 0:
            return False

        current_gini = compute_gini_proxy(state.agents.wealth, state.agents.active)
        if self.last_gini is not None:
            relative_change = abs(float(current_gini - self.last_gini)) / (self.last_gini + 1e-8)
            if relative_change > self.change_threshold:
                self.current_frequency = max(self.min_frequency, self.current_frequency // 2)
            else:
                self.current_frequency = min(self.max_frequency, self.current_frequency + 1)
        self.last_gini = float(current_gini)
        return True


def create_distribution_update_schedule(total_steps: int, *, strategy: str = "fixed") -> list[int]:
    if strategy == "fixed":
        return list(range(0, total_steps, 8))
    if strategy == "logarithmic":
        steps = [0]
        current = 1
        while current < total_steps:
            steps.append(current)
            current = int(current * 1.5) + 1
        return steps
    if strategy == "key_points":
        return [
            0,
            total_steps // 4,
            total_steps // 2,
            3 * total_steps // 4,
            total_steps - 1,
        ]
    raise ValueError(f"Unknown strategy: {strategy}")
