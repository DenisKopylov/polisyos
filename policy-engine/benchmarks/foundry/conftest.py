"""
Shared fixtures and data generators for foundry domain benchmarks.

All data generators produce tiny datasets suitable for MacBook Air M2 (16GB):
- n ≤ 100 observations
- Bayesian: ≤64 samples, 32 warmup, 1 chain
- Optimization: ≤5 variables
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(scope="session")
def bench_registry() -> MethodRegistry:
    """Session-scoped registry with all catalog domains loaded."""
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered

    reg = MethodRegistry.get_instance()
    ensure_all_methods_registered(reg)
    return reg


# ---------------------------------------------------------------------------
# Synthetic data generators — all tiny
# ---------------------------------------------------------------------------


def make_distribution(n_obs: int = 50, seed: int = 42) -> dict[str, Any]:
    """Income-like distribution for inequality / poverty tests."""
    rng = np.random.default_rng(seed)
    values = rng.lognormal(mean=3.0, sigma=1.0, size=n_obs)
    return {"values": values}


def make_two_class_distribution(seed: int = 42) -> dict[str, Any]:
    """Bimodal distribution for polarization tests."""
    rng = np.random.default_rng(seed)
    low = rng.normal(20.0, 3.0, size=25)
    high = rng.normal(80.0, 3.0, size=25)
    return {"values": np.concatenate([low, high])}


def make_time_series(n_obs: int = 30, trend: float = 0.5, seed: int = 42) -> dict[str, Any]:
    """Simple trending time series."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0, 0.5, size=n_obs)
    series = np.arange(n_obs, dtype=float) * trend + 10.0 + noise
    return {"series": series}


def make_survey_areas(n_areas: int = 8, seed: int = 42) -> dict[str, Any]:
    """Small area estimation data for Fay-Herriot."""
    rng = np.random.default_rng(seed)
    X = np.column_stack([np.ones(n_areas), rng.normal(0, 1, size=n_areas)])
    beta = np.array([50.0, 5.0])
    y_true = X @ beta
    sampling_var = rng.uniform(1.0, 5.0, size=n_areas)
    y_direct = y_true + rng.normal(0, 1, size=n_areas) * np.sqrt(sampling_var)
    return {
        "y_direct": y_direct,
        "X": X,
        "sampling_var": sampling_var,
    }


def make_sobol_data(n_samples: int = 30, n_factors: int = 3, seed: int = 42) -> dict[str, Any]:
    """Sobol analysis inputs for a simple additive model f(x) = sum(x_i)."""
    rng = np.random.default_rng(seed)
    x_a = rng.uniform(0, 1, size=(n_samples, n_factors))
    x_b = rng.uniform(0, 1, size=(n_samples, n_factors))
    outputs_a = x_a.sum(axis=1)
    outputs_b = x_b.sum(axis=1)
    mixed = []
    for i in range(n_factors):
        x_mixed = x_b.copy()
        x_mixed[:, i] = x_a[:, i]
        mixed.append(x_mixed.sum(axis=1))
    return {
        "outputs_a": outputs_a,
        "outputs_b": outputs_b,
        "mixed_outputs": np.array(mixed),
    }


def make_predictions(n_obs: int = 30, bias: float = 0.0, seed: int = 42) -> dict[str, Any]:
    """Prediction vs observation data for validation methods."""
    rng = np.random.default_rng(seed)
    observations = rng.normal(0, 1, size=n_obs)
    predictive_mean = observations + bias + rng.normal(0, 0.1, size=n_obs)
    predictive_std = np.full(n_obs, 0.5)
    return {
        "observations": observations,
        "predictive_mean": predictive_mean,
        "predictive_std": predictive_std,
    }


def make_mobility_data(n_obs: int = 50, n_classes: int = 4, seed: int = 42) -> dict[str, Any]:
    """Mobility transition data."""
    rng = np.random.default_rng(seed)
    origin = rng.integers(0, n_classes, size=n_obs)
    # Some upward mobility bias
    destination = np.clip(origin + rng.choice([-1, 0, 0, 1], size=n_obs), 0, n_classes - 1)
    return {
        "origin_classes": origin.tolist(),
        "destination_classes": destination.tolist(),
    }
