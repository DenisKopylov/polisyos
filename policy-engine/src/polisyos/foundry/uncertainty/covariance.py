"""Public uncertainty covariance module API."""
from __future__ import annotations

from typing import Mapping

import jax.numpy as jnp

from polisyos.ir.analytics.uncertainty import DistributionFamily, UncertaintyEnvelope


def extract_std(env: UncertaintyEnvelope) -> float:
    """Extract std helper."""
    lo, hi = env.confidence_interval
    width = max(float(hi - lo), 0.0)
    level = env.confidence_level
    if (
        env.distribution_family == DistributionFamily.NORMAL
        and level is not None
        and 0.0 < level < 1.0
    ):
        from statistics import NormalDist

        z = NormalDist().inv_cdf((1.0 + level) / 2.0)
        if z > 0.0:
            return width / (2.0 * z)
    return width / (2.0 * (3.0**0.5))


def build_covariance_matrix(
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    *,
    use_full_covariance: bool,
    jitter: float,
) -> jnp.ndarray:
    """Build covariance matrix."""
    stds = jnp.asarray(
        [extract_std(input_envelopes[name]) for name in param_names],
        dtype=jnp.float32,
    )
    diag_cov = jnp.diag(stds**2)

    if not use_full_covariance:
        return diag_cov

    rows: list[list[float]] = []
    expected_params: list[str] | None = None
    for name in param_names:
        metadata = input_envelopes[name].metadata
        row = metadata.get("covariance_row")
        params_order = metadata.get("covariance_params")
        if not isinstance(row, list):
            return diag_cov
        if not all(isinstance(item, (int, float)) for item in row):
            return diag_cov
        if isinstance(params_order, list) and all(isinstance(item, str) for item in params_order):
            if expected_params is None:
                expected_params = list(params_order)
            elif expected_params != list(params_order):
                return diag_cov
        rows.append([float(v) for v in row])

    if expected_params is not None:
        if set(expected_params) != set(param_names):
            return diag_cov
        reorder_idx = [expected_params.index(name) for name in param_names]
        cov = jnp.asarray(rows, dtype=jnp.float32)
        cov = cov[:, reorder_idx][reorder_idx, :]
    else:
        cov = jnp.asarray(rows, dtype=jnp.float32)

    if cov.shape != diag_cov.shape:
        return diag_cov

    cov = _repair_covariance(cov, jitter=jitter)
    if not jnp.all(jnp.isfinite(cov)):
        return diag_cov
    return cov


def _repair_covariance(cov: jnp.ndarray, *, jitter: float) -> jnp.ndarray:
    cov_sym = 0.5 * (cov + cov.T)
    evals, evecs = jnp.linalg.eigh(cov_sym)
    clipped = jnp.clip(evals, a_min=jitter, a_max=None)
    return (evecs * clipped) @ evecs.T
