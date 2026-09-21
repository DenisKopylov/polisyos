"""Public uncertainty covariance module API."""

from __future__ import annotations

import math
from collections.abc import Mapping

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
    marginal_stds: list[float] = []
    for name in param_names:
        declared_std = input_envelopes[name].metadata.get("std")
        if declared_std is None:
            marginal_stds.append(extract_std(input_envelopes[name]))
            continue
        if (
            not isinstance(declared_std, (int, float))
            or not math.isfinite(float(declared_std))
            or declared_std < 0
        ):
            raise ValueError(f"declared std is invalid for parameter {name!r}")
        marginal_stds.append(float(declared_std))
    stds = jnp.asarray(marginal_stds, dtype=jnp.float32)
    diag_cov = jnp.diag(stds**2)

    if not use_full_covariance:
        return diag_cov

    rows: list[list[float]] = []
    expected_params: list[str] | None = None
    saw_params_declaration = False
    saw_undeclared_params = False
    has_covariance_metadata = any(
        "covariance_row" in input_envelopes[name].metadata
        or "covariance_params" in input_envelopes[name].metadata
        for name in param_names
    )
    for name in param_names:
        metadata = input_envelopes[name].metadata
        row = metadata.get("covariance_row")
        params_order = metadata.get("covariance_params")
        if not isinstance(row, list):
            if has_covariance_metadata:
                raise ValueError(f"covariance row is missing for parameter {name!r}")
            return diag_cov
        if not all(isinstance(item, (int, float)) for item in row):
            raise ValueError(f"covariance row is not numeric for parameter {name!r}")
        if len(row) != len(param_names):
            raise ValueError(f"covariance row has the wrong dimension for parameter {name!r}")
        if params_order is not None:
            saw_params_declaration = True
            if not isinstance(params_order, list) or not all(
                isinstance(item, str) for item in params_order
            ):
                raise ValueError("covariance_params must be a list of parameter names")
            if len(params_order) != len(param_names) or len(set(params_order)) != len(params_order):
                raise ValueError("covariance_params must contain unique parameter names")
            if expected_params is None:
                expected_params = list(params_order)
            elif expected_params != list(params_order):
                raise ValueError("covariance_params must use one common column ordering")
        else:
            saw_undeclared_params = True
        rows.append([float(v) for v in row])

    if saw_params_declaration and saw_undeclared_params:
        raise ValueError("covariance_params must be declared for every covariance row")

    if expected_params is not None:
        if set(expected_params) != set(param_names):
            raise ValueError("covariance_params must cover exactly the requested parameters")
        reorder_idx = [expected_params.index(name) for name in param_names]
        cov = jnp.asarray(rows, dtype=jnp.float32)
        # Every row belongs to the envelope that supplied it.  Only the
        # declared columns need moving into the requested parameter order;
        # moving rows as well changes row ownership and can manufacture a
        # covariance matrix that no producer emitted.
        cov = cov[:, reorder_idx]
    else:
        cov = jnp.asarray(rows, dtype=jnp.float32)

    if cov.shape != diag_cov.shape:
        raise ValueError("covariance matrix has the wrong dimension")

    if not bool(jnp.all(jnp.isfinite(cov))):
        raise ValueError("covariance matrix must contain finite values")
    symmetric = 0.5 * (cov + cov.T)
    if not bool(jnp.allclose(cov, cov.T, rtol=1e-5, atol=1e-6)):
        raise ValueError("covariance matrix must be symmetric")
    if not bool(jnp.allclose(jnp.diag(cov), stds**2, rtol=1e-3, atol=1e-5)):
        raise ValueError("covariance diagonal must match marginal standard deviations")
    eigenvalues = jnp.linalg.eigvalsh(symmetric)
    if float(jnp.min(eigenvalues)) < -max(1e-6, 10.0 * jitter):
        raise ValueError("covariance matrix must be positive semidefinite")

    cov = _repair_covariance(cov, jitter=jitter)
    if not bool(jnp.all(jnp.isfinite(cov))):
        raise ValueError("covariance matrix must contain finite values")
    return cov


def has_unknown_dependency(input_envelopes: Mapping[str, UncertaintyEnvelope]) -> bool:
    """Return whether a producer explicitly withheld the input dependency law."""
    unknown_values = {"unknown", "unverified", "not_established", "incompatible"}
    for envelope in input_envelopes.values():
        raw = envelope.metadata.get("dependency")
        if raw is None:
            raw = envelope.metadata.get("dependence")
        if raw is not None and str(raw).strip().lower() in unknown_values:
            return True
    return False


def _repair_covariance(cov: jnp.ndarray, *, jitter: float) -> jnp.ndarray:
    cov_sym = 0.5 * (cov + cov.T)
    evals, evecs = jnp.linalg.eigh(cov_sym)
    clipped = jnp.clip(evals, a_min=jitter, a_max=None)
    return (evecs * clipped) @ evecs.T
