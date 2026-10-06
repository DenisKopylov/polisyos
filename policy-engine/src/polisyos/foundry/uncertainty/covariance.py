"""Public uncertainty covariance module API."""

from __future__ import annotations

import math
from collections.abc import Mapping

import jax.numpy as jnp
import numpy as np

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    UncertaintyEnvelope,
)

from .sampling_admission import admit_float32_range

CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1 = 1e-7
CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1 = 1e-10


def extract_std(env: UncertaintyEnvelope) -> float:
    """Extract a standard deviation from a typed law or a valid interval."""
    payload = env.distribution_payload
    if isinstance(payload, ParametricFitCarrier):
        if env.distribution_family is not payload.family:
            raise ValueError("parametric fit family does not match envelope family")
        if payload.family is DistributionFamily.NORMAL:
            if payload.support is not None:
                raise ValueError("bounded normal parametric fit support is unsupported")
            raw_std = payload.parameters.get(
                "std",
                payload.parameters.get("sigma", payload.parameters.get("scale")),
            )
            if raw_std is None:
                raise ValueError("normal parametric fit requires std, sigma, or scale")
            std = float(raw_std)
            if not math.isfinite(std) or std < 0.0:
                raise ValueError(
                    "normal parametric fit standard deviation must be finite and non-negative"
                )
            return std
        if payload.family is DistributionFamily.UNIFORM:
            support = payload.support
            if support is None:
                low = payload.parameters.get("low")
                high = payload.parameters.get("high")
                if low is None or high is None:
                    raise ValueError("uniform parametric fit requires ordered support")
                support = (float(low), float(high))
            low, high = (float(support[0]), float(support[1]))
            if not all(math.isfinite(value) for value in (low, high)) or low > high:
                raise ValueError("uniform parametric fit requires ordered support")
            return (high - low) / math.sqrt(12.0)
        raise ValueError(f"unsupported parametric fit family: {payload.family.value}")

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
    # Preserve the existing non-gating heuristic path for legacy envelopes that
    # predate typed carriers.  A typed parametric carrier above always takes
    # precedence and fails closed when its law is incomplete or unsupported.
    return width / (2.0 * (3.0**0.5))


def build_covariance_matrix(
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    *,
    use_full_covariance: bool,
    jitter: float,
    preserve_singular: bool = True,
) -> jnp.ndarray:
    """Build a validated covariance matrix, optionally retaining exact null spaces."""
    if not math.isfinite(float(jitter)) or jitter < 0.0:
        raise ValueError("jitter must be finite and non-negative")
    marginal_stds: list[float] = []
    for name in param_names:
        envelope = input_envelopes[name]
        if isinstance(envelope.distribution_payload, ParametricFitCarrier):
            marginal_stds.append(extract_std(envelope))
            continue
        declared_std = envelope.metadata.get("std")
        if declared_std is None:
            marginal_stds.append(extract_std(envelope))
            continue
        if (
            not isinstance(declared_std, (int, float))
            or not math.isfinite(float(declared_std))
            or declared_std < 0
        ):
            raise ValueError(f"declared std is invalid for parameter {name!r}")
        marginal_stds.append(float(declared_std))
    diagonal_values = admit_float32_range(np.diag(np.square(np.asarray(marginal_stds))))
    diag_cov = jnp.asarray(diagonal_values, dtype=jnp.float32)

    rows: list[list[float]] = []
    expected_params: list[str] | None = None
    saw_params_declaration = False
    saw_undeclared_params = False
    has_covariance_metadata = any(
        "covariance_row" in input_envelopes[name].metadata
        or "covariance_params" in input_envelopes[name].metadata
        for name in param_names
    )
    # A numerical option may choose an algorithm, not replace a declared law.
    # Full/partial supplied rows always enter the same admission path, even if
    # an older caller requested the diagonal optimization.
    if not use_full_covariance and not has_covariance_metadata:
        return diag_cov
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
        covariance_values = np.asarray(rows, dtype=np.float64)
        # Every row belongs to the envelope that supplied it.  Only the
        # declared columns need moving into the requested parameter order;
        # moving rows as well changes row ownership and can manufacture a
        # covariance matrix that no producer emitted.
        covariance_values = covariance_values[:, reorder_idx]
    else:
        covariance_values = np.asarray(rows, dtype=np.float64)

    if covariance_values.shape != tuple(diag_cov.shape):
        raise ValueError("covariance matrix has the wrong dimension")

    covariance = covariance_values
    diagonal = np.diag(np.square(np.asarray(marginal_stds, dtype=np.float64)))
    if not np.all(np.isfinite(covariance)):
        raise ValueError("covariance matrix must contain finite values")
    if not np.allclose(np.diag(covariance), np.diag(diagonal), rtol=1e-3, atol=0.0):
        raise ValueError("covariance diagonal must match marginal standard deviations")
    if preserve_singular:
        covariance = preserve_singular_covariance(covariance)
    else:
        symmetric = 0.5 * (covariance + covariance.T)
        if not np.allclose(covariance, covariance.T, rtol=1e-5, atol=1e-6):
            raise ValueError("covariance matrix must be symmetric")
        eigenvalues = np.linalg.eigvalsh(symmetric)
        minimum_eigenvalue = float(np.min(eigenvalues))
        if minimum_eigenvalue < -max(1e-6, 10.0 * jitter):
            raise ValueError("covariance matrix must be positive semidefinite")
        eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
        covariance = (eigenvectors * np.clip(eigenvalues, jitter, None)) @ eigenvectors.T

    if not np.all(np.isfinite(covariance)):
        raise ValueError("covariance matrix must contain finite values")
    return jnp.asarray(admit_float32_range(covariance), dtype=jnp.float32)


def preserve_singular_covariance(
    covariance: object,
    *,
    symmetry_rtol: float = 1e-5,
    symmetry_atol: float = 1e-6,
) -> np.ndarray:
    """Validate a covariance matrix while retaining its declared null space.

    Tiny negative eigenvalues within the established numerical tolerance are
    projected to zero. Materially indefinite or malformed matrices are rejected.
    """
    matrix = np.asarray(covariance, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("covariance matrix must be square")
    if not np.all(np.isfinite(matrix)):
        raise ValueError("covariance matrix must contain finite values")
    scale = float(np.max(np.abs(matrix))) if matrix.size else 0.0
    if not np.allclose(
        matrix,
        matrix.T,
        rtol=symmetry_rtol,
        atol=symmetry_atol * scale,
    ):
        raise ValueError("covariance matrix must be symmetric")
    symmetric = 0.5 * (matrix + matrix.T)
    if symmetric.size == 0:
        return symmetric
    eigenvalues = np.linalg.eigvalsh(symmetric)
    minimum_eigenvalue = float(np.min(eigenvalues))
    # The tolerance is independent of jitter; regularization cannot make an
    # indefinite declared law acceptable.
    if minimum_eigenvalue < -1e-10 * scale:
        raise ValueError("covariance matrix must be positive semidefinite")
    if minimum_eigenvalue < 0.0:
        eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
        symmetric = (eigenvectors * np.clip(eigenvalues, 0.0, None)) @ eigenvectors.T
    if not np.all(np.isfinite(symmetric)):
        raise ValueError("covariance matrix must contain finite values")
    return symmetric


def calibration_covariance_blocks_agree_v1(expected: object, actual: object) -> bool:
    """Compare a cross-owner covariance block under the pinned v1 tolerance."""
    expected_matrix = np.asarray(expected, dtype=np.float64)
    actual_matrix = np.asarray(actual, dtype=np.float64)
    if expected_matrix.shape != actual_matrix.shape:
        return False
    if not np.all(np.isfinite(expected_matrix)) or not np.all(np.isfinite(actual_matrix)):
        return False
    return bool(
        np.allclose(
            expected_matrix,
            actual_matrix,
            rtol=CALIBRATION_COVARIANCE_RECONCILIATION_RTOL_V1,
            atol=CALIBRATION_COVARIANCE_RECONCILIATION_ATOL_V1,
        )
    )


def has_unknown_dependency(input_envelopes: Mapping[str, UncertaintyEnvelope]) -> bool:
    """Treat missing multi-input dependence as unknown, never implicit independence."""
    unknown_values = {"unknown", "unverified", "not_established", "incompatible"}
    for envelope in input_envelopes.values():
        raw = envelope.metadata.get("dependency")
        if raw is None:
            raw = envelope.metadata.get("dependence")
        if raw is not None and str(raw).strip().lower() in unknown_values:
            return True
    if len(input_envelopes) <= 1:
        return False
    has_full_covariance = all(
        "covariance_row" in envelope.metadata and "covariance_params" in envelope.metadata
        for envelope in input_envelopes.values()
    )
    has_joint_carriers = all(
        isinstance(envelope.distribution_payload, PosteriorSamplesCarrier)
        and "joint_sample_id" in envelope.metadata
        for envelope in input_envelopes.values()
    )
    return not (has_full_covariance or has_joint_carriers)


def _repair_covariance(cov: jnp.ndarray, *, jitter: float) -> jnp.ndarray:
    cov_sym = 0.5 * (cov + cov.T)
    evals, evecs = jnp.linalg.eigh(cov_sym)
    clipped = jnp.clip(evals, a_min=jitter, a_max=None)
    return (evecs * clipped) @ evecs.T
