"""Public agent sim demographics module API."""
from __future__ import annotations

import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.distributions import compute_quantiles_hard, soft_rank
from polisyos.foundry.agent_sim.state import AgentState


def compute_demographic_metrics(agents: AgentState, *, steps_per_year: int = 12) -> dict[str, jnp.ndarray]:
    """Compute demographic metrics helper."""
    active = agents.active
    n_active = jnp.sum(active.astype(jnp.float32))
    age_years = agents.age.astype(jnp.float32) / float(steps_per_year)

    brackets = [
        (0, 18, "children"),
        (18, 30, "young_adults"),
        (30, 50, "middle_aged"),
        (50, 65, "older_workers"),
        (65, 200, "elderly"),
    ]
    metrics: dict[str, jnp.ndarray] = {}
    for low, high, name in brackets:
        in_bracket = (age_years >= low) & (age_years < high) & active
        metrics[f"frac_{name}"] = jnp.sum(in_bracket) / (n_active + 1e-8)

    metrics["mean_age"] = jnp.sum(age_years * active) / (n_active + 1e-8)

    quantiles = compute_quantiles_hard(age_years, active, 2)
    metrics["median_age"] = quantiles[0]

    children = jnp.sum((age_years < 18) & active)
    elderly = jnp.sum((age_years >= 65) & active)
    working = jnp.sum((age_years >= 18) & (age_years < 65) & active)
    metrics["dependency_ratio"] = (children + elderly) / (working + 1e-8)
    metrics["mean_life_expectancy"] = (
        jnp.sum(agents.life_expectancy * active) / (n_active + 1e-8) / steps_per_year
    )
    fertile = (age_years >= 20) & (age_years <= 45) & active
    metrics["mean_fertility_rate"] = jnp.sum(agents.fertility_rate * fertile) / (
        jnp.sum(fertile) + 1e-8
    )
    return metrics


def compute_population_pyramid(
    agents: AgentState,
    *,
    n_bins: int = 20,
    max_age: int = 100,
    steps_per_year: int = 12,
) -> jnp.ndarray:
    """Compute population pyramid helper."""
    age_years = agents.age.astype(jnp.float32) / float(steps_per_year)
    active = agents.active
    bin_edges = jnp.linspace(0.0, float(max_age), n_bins + 1)

    def body(i, hist):
        in_bin = (age_years >= bin_edges[i]) & (age_years < bin_edges[i + 1]) & active
        return hist.at[i].set(jnp.sum(in_bin))

    histogram = jax.lax.fori_loop(0, int(n_bins), body, jnp.zeros((n_bins,)))
    return histogram / (jnp.sum(active) + 1e-8)


def compute_intergenerational_mobility(
    agents: AgentState,
    parent_wealth_at_birth: jnp.ndarray,
) -> dict[str, jnp.ndarray]:
    """Compute intergenerational mobility helper."""
    active = agents.active
    has_parent = agents.parent_id >= 0
    valid = active & has_parent

    parent_rank = soft_rank(parent_wealth_at_birth, temperature=0.1)
    child_rank = soft_rank(agents.wealth, temperature=0.1)

    n_valid = jnp.sum(valid.astype(jnp.float32))
    mean_parent = jnp.sum(parent_rank * valid) / (n_valid + 1e-8)
    mean_child = jnp.sum(child_rank * valid) / (n_valid + 1e-8)
    cov = jnp.sum((parent_rank - mean_parent) * (child_rank - mean_child) * valid) / (
        n_valid + 1e-8
    )
    var_parent = jnp.sum((parent_rank - mean_parent) ** 2 * valid) / (n_valid + 1e-8)
    var_child = jnp.sum((child_rank - mean_child) ** 2 * valid) / (n_valid + 1e-8)
    rank_corr = cov / (jnp.sqrt(var_parent * var_child) + 1e-8)

    log_parent = jnp.log(parent_wealth_at_birth + 1.0)
    log_child = jnp.log(agents.wealth + 1.0)
    mean_log_parent = jnp.sum(log_parent * valid) / (n_valid + 1e-8)
    mean_log_child = jnp.sum(log_child * valid) / (n_valid + 1e-8)
    cov_log = jnp.sum((log_parent - mean_log_parent) * (log_child - mean_log_child) * valid) / (
        n_valid + 1e-8
    )
    var_log_parent = jnp.sum((log_parent - mean_log_parent) ** 2 * valid) / (
        n_valid + 1e-8
    )
    elasticity = cov_log / (var_log_parent + 1e-8)

    return {
        "rank_correlation": rank_corr,
        "wealth_elasticity": elasticity,
        "mobility_index": 1.0 - jnp.abs(rank_corr),
    }
