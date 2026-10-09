"""Select conditional-independence and interval backends for causal discovery and inference."""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using the error function (no scipy dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (rational approximation, Abramowitz & Stegun).

    Accurate to ~4.5e-4 absolute error across (0, 1).
    """
    if p <= 0.0:
        return -6.0
    if p >= 1.0:
        return 6.0
    if p == 0.5:
        return 0.0
    if p > 0.5:
        return -_norm_ppf(1.0 - p)
    t = math.sqrt(-2.0 * math.log(p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return -(t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t))


_VALID_DISCOVERY_CI_BACKENDS: frozenset[str] = frozenset({"auto", "numpy", "jax"})


class BootstrapExecutionWork(BaseModel):
    """Measured work performed by one bootstrap replicate loop."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    work_unit: Literal["bootstrap_replicate"] = "bootstrap_replicate"
    requested_draw_count: int = Field(ge=0)
    attempted_draw_count: int = Field(ge=0)
    completed_draw_count: int = Field(ge=0)
    failed_draw_count: int = Field(ge=0)
    unattempted_draw_count: int = Field(ge=0)
    draw_execution_status: Literal["complete", "partial", "not_started"]

    @model_validator(mode="after")
    def _validate_measured_counts(self) -> BootstrapExecutionWork:
        if self.attempted_draw_count != self.completed_draw_count + self.failed_draw_count:
            raise ValueError("attempted draws must equal completed plus failed draws")
        if self.requested_draw_count != self.attempted_draw_count + self.unattempted_draw_count:
            raise ValueError("requested draws must equal attempted plus unattempted draws")
        expected_status = (
            "not_started"
            if self.requested_draw_count > 0 and self.attempted_draw_count == 0
            else "complete"
            if self.attempted_draw_count == self.requested_draw_count
            and self.failed_draw_count == 0
            else "partial"
        )
        if self.draw_execution_status != expected_status:
            raise ValueError("draw execution status does not match measured counts")
        return self


class BootstrapExecutionCounter:
    """Count work at the actual bootstrap replicate loop, without changing its result."""

    def __init__(self, *, requested_draw_count: int) -> None:
        if (
            isinstance(requested_draw_count, bool)
            or not isinstance(requested_draw_count, int)
            or requested_draw_count < 0
        ):
            raise ValueError("requested_draw_count must be a non-negative integer")
        self._requested = requested_draw_count
        self._attempted = 0
        self._completed = 0
        self._failed = 0

    @property
    def requested_draw_count(self) -> int:
        """Return the explicitly requested draw count for this loop."""
        return self._requested

    def begin_draw(self) -> None:
        """Record entry into one actual draw attempt."""
        if self._attempted >= self._requested:
            raise RuntimeError("bootstrap loop attempted more draws than requested")
        self._attempted += 1

    def complete_draw(self) -> None:
        """Record one draw whose replicate mean was stored successfully."""
        self._completed += 1

    def fail_draw(self) -> None:
        """Record one draw that raised before its replicate mean was stored."""
        self._failed += 1

    def snapshot(self) -> BootstrapExecutionWork:
        """Return an immutable count packet reconciled to the requested total."""
        unattempted = self._requested - self._attempted
        status: Literal["complete", "partial", "not_started"]
        if self._requested > 0 and self._attempted == 0:
            status = "not_started"
        elif self._attempted == self._requested and self._failed == 0:
            status = "complete"
        else:
            status = "partial"
        return BootstrapExecutionWork(
            requested_draw_count=self._requested,
            attempted_draw_count=self._attempted,
            completed_draw_count=self._completed,
            failed_draw_count=self._failed,
            unattempted_draw_count=unattempted,
            draw_execution_status=status,
        )


@dataclass(frozen=True)
class CIBackendSelection:
    """Describe the chosen CI backend plus fallback and availability metadata."""

    requested: str
    used: str
    fallback_reason: str | None = None


def _normalize_backend(raw: Any) -> str:
    if raw is None:
        return "auto"
    token = str(raw).strip().lower()
    if not token:
        return "auto"
    return token


@lru_cache(maxsize=1)
def _is_jax_available() -> bool:
    return bool(importlib.util.find_spec("jax") and importlib.util.find_spec("jax.numpy"))


def resolve_discovery_ci_backend(raw: Any) -> CIBackendSelection:
    """Resolve discovery ci backend."""
    requested = _normalize_backend(raw)
    if requested not in _VALID_DISCOVERY_CI_BACKENDS:
        return CIBackendSelection(
            requested=requested,
            used="numpy",
            fallback_reason=(
                f"unsupported_discovery_ci_backend:{requested}; expected one of auto|numpy|jax"
            ),
        )
    if requested == "numpy":
        return CIBackendSelection(requested="numpy", used="numpy")
    if requested == "jax":
        if _is_jax_available():
            return CIBackendSelection(requested="jax", used="jax")
        return CIBackendSelection(
            requested="jax",
            used="numpy",
            fallback_reason="jax_unavailable",
        )
    if _is_jax_available():
        return CIBackendSelection(requested="auto", used="jax")
    return CIBackendSelection(
        requested="auto",
        used="numpy",
        fallback_reason="auto_selected_numpy:jax_unavailable",
    )


def ci_backend_metadata(selection: CIBackendSelection) -> dict[str, Any]:
    """Ci backend metadata helper."""
    return {
        "ci_backend_requested": selection.requested,
        "ci_backend_used": selection.used,
        "ci_backend_fallback_reason": selection.fallback_reason,
    }


def _residualize_numpy(target: np.ndarray, cond: np.ndarray | None) -> np.ndarray:
    if cond is None:
        return target - float(np.mean(target))
    z = np.asarray(cond, dtype=float)
    if z.ndim == 1:
        z = z.reshape(-1, 1)
    if z.shape[1] == 0:
        return target - float(np.mean(target))
    beta = np.linalg.pinv(z) @ target
    return target - z @ beta


def _partial_corr_numpy(x: np.ndarray, y: np.ndarray, z: np.ndarray | None) -> float:
    x_res = _residualize_numpy(x, z)
    y_res = _residualize_numpy(y, z)
    x_std = float(np.std(x_res))
    y_std = float(np.std(y_res))
    if x_std <= 1e-12 or y_std <= 1e-12:
        return 0.0
    value = float(np.corrcoef(x_res, y_res)[0, 1])
    if not np.isfinite(value):
        return 0.0
    return float(np.clip(value, -1.0, 1.0))


def _partial_corr_jax(x: np.ndarray, y: np.ndarray, z: np.ndarray | None) -> float:
    import jax.numpy as jnp

    x_j = jnp.asarray(np.asarray(x, dtype=float))
    y_j = jnp.asarray(np.asarray(y, dtype=float))
    if z is None:
        z_j = None
    else:
        z_j = jnp.asarray(np.asarray(z, dtype=float))

    def _residualize(target: Any, cond: Any | None) -> Any:
        if cond is None:
            return target - jnp.mean(target)
        if cond.ndim == 1:
            cond = cond.reshape((-1, 1))
        if cond.shape[1] == 0:
            return target - jnp.mean(target)
        beta = jnp.linalg.pinv(cond) @ target
        return target - cond @ beta

    x_res = _residualize(x_j, z_j)
    y_res = _residualize(y_j, z_j)
    x_std = jnp.std(x_res)
    y_std = jnp.std(y_res)
    if float(x_std) <= 1e-12 or float(y_std) <= 1e-12:
        return 0.0
    value = jnp.corrcoef(x_res, y_res)[0, 1]
    value_f = float(np.asarray(value))
    if not np.isfinite(value_f):
        return 0.0
    return float(np.clip(value_f, -1.0, 1.0))


def partial_corr(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray | None = None,
    *,
    backend: str = "numpy",
) -> float:
    """Partial corr helper."""
    backend_norm = _normalize_backend(backend)
    if backend_norm not in {"numpy", "jax"}:
        backend_norm = "numpy"

    x_arr = np.asarray(x, dtype=float).reshape(-1)
    y_arr = np.asarray(y, dtype=float).reshape(-1)
    if x_arr.shape[0] != y_arr.shape[0]:
        raise ValueError("x and y must have the same sample length")

    z_arr: np.ndarray | None = None
    if z is not None:
        z_arr = np.asarray(z, dtype=float)
        if z_arr.ndim == 1:
            z_arr = z_arr.reshape((-1, 1))
        if z_arr.shape[0] != x_arr.shape[0]:
            raise ValueError("z sample length must match x/y")

    if backend_norm == "jax" and _is_jax_available():
        return _partial_corr_jax(x_arr, y_arr, z_arr)
    return _partial_corr_numpy(x_arr, y_arr, z_arr)


def partial_corr_batch(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray | None = None,
    *,
    backend: str = "numpy",
) -> np.ndarray:
    """Partial corr batch helper."""
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    if x_arr.ndim != 2 or y_arr.ndim != 2:
        raise ValueError("x and y must be 2D arrays shaped (n_samples, n_pairs)")
    if x_arr.shape != y_arr.shape:
        raise ValueError("x and y must have identical shape")

    z_arr: np.ndarray | None = None
    if z is not None:
        z_arr = np.asarray(z, dtype=float)
        if z_arr.ndim == 1:
            z_arr = z_arr.reshape((-1, 1))
        if z_arr.shape[0] != x_arr.shape[0]:
            raise ValueError("z sample length must match x/y")

    backend_norm = _normalize_backend(backend)
    if backend_norm == "jax" and _is_jax_available():
        import jax.numpy as jnp
        from jax import jit, vmap

        x_j = jnp.asarray(x_arr)
        y_j = jnp.asarray(y_arr)
        z_j = None if z_arr is None else jnp.asarray(z_arr)

        def _residualize(target: Any, cond: Any | None) -> Any:
            if cond is None:
                return target - jnp.mean(target)
            if cond.ndim == 1:
                cond = cond.reshape((-1, 1))
            if cond.shape[1] == 0:
                return target - jnp.mean(target)
            beta = jnp.linalg.pinv(cond) @ target
            return target - cond @ beta

        def _corr_scalar(x_col: Any, y_col: Any, cond: Any | None) -> Any:
            x_res = _residualize(x_col, cond)
            y_res = _residualize(y_col, cond)
            x_std = jnp.std(x_res)
            y_std = jnp.std(y_res)
            safe = (x_std > 1e-12) & (y_std > 1e-12)
            corr = jnp.corrcoef(x_res, y_res)[0, 1]
            return jnp.where(safe, corr, 0.0)

        batch_corr = jit(vmap(_corr_scalar, in_axes=(1, 1, None)))
        values = np.asarray(batch_corr(x_j, y_j, z_j))
        return np.clip(values, -1.0, 1.0).astype(float)

    pairs = x_arr.shape[1]
    out = np.zeros(pairs, dtype=float)
    for idx in range(pairs):
        out[idx] = partial_corr(x_arr[:, idx], y_arr[:, idx], z_arr, backend="numpy")
    return out


def bootstrap_mean_interval(
    values: np.ndarray,
    *,
    seed: int,
    draws: int,
    influence_values: np.ndarray | None = None,
    backend: str = "bootstrap_eif",
    work_counter: BootstrapExecutionCounter | None = None,
) -> tuple[float, float]:
    """Bootstrap mean interval helper.

    ``work_counter`` is an opt-in diagnostic. It records actual loop iterations
    while preserving the historical return tuple and interval calculation.
    """
    if work_counter is not None and work_counter.requested_draw_count != draws:
        raise ValueError("work counter requested_draw_count must match draws")
    arr = np.asarray(values, dtype=float).reshape(-1)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan"), float("nan")
    if arr.size == 1:
        return float(arr[0]), float(arr[0])

    backend_normalized = backend.strip().lower()
    if backend_normalized in {"eif", "bootstrap_eif", "bootstrap"} and influence_values is not None:
        return _bootstrap_eif_interval(
            arr,
            influence_values,
            seed=seed,
            draws=draws,
            work_counter=work_counter,
        )
    return _bootstrap_interval(arr, seed=seed, draws=draws, work_counter=work_counter)


def robust_standard_error(values: np.ndarray) -> float:
    """Robust standard error helper."""
    arr = np.asarray(values, dtype=float).reshape(-1)
    arr = arr[np.isfinite(arr)]
    if arr.size <= 1:
        return 0.0
    centered = arr - np.mean(arr)
    return float(np.std(centered, ddof=1) / np.sqrt(arr.size))


def _bootstrap_interval(
    values: np.ndarray,
    *,
    seed: int,
    draws: int,
    work_counter: BootstrapExecutionCounter | None = None,
) -> tuple[float, float]:
    """BCa (bias-corrected and accelerated) bootstrap interval.

    Falls back to percentile bootstrap when jackknife acceleration
    cannot be computed (e.g. constant data).
    """
    arr = np.asarray(values, dtype=float).reshape(-1)
    n = arr.size
    rng = np.random.default_rng(seed)
    theta_hat = float(np.mean(arr))

    # Bootstrap replicates
    means = np.empty(draws, dtype=float)
    for idx in range(draws):
        if work_counter is not None:
            work_counter.begin_draw()
        try:
            sample = rng.choice(arr, size=n, replace=True)
            means[idx] = float(np.mean(sample))
        except Exception:
            if work_counter is not None:
                work_counter.fail_draw()
            raise
        if work_counter is not None:
            work_counter.complete_draw()

    # --- Bias correction factor (z0) ---
    prop_below = float(np.mean(means < theta_hat))
    prop_below = max(1e-8, min(1.0 - 1e-8, prop_below))
    z0 = _norm_ppf(prop_below)

    # --- Acceleration factor (a) via jackknife ---
    total = float(np.sum(arr))
    jackknife_means = (total - arr) / max(n - 1, 1)
    jk_mean = float(np.mean(jackknife_means))
    diffs = jk_mean - jackknife_means
    denom = float(np.sum(diffs**2))
    if denom < 1e-15:
        # Constant data — fall back to simple percentile
        return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))
    a = float(np.sum(diffs**3)) / (6.0 * denom**1.5)

    # --- BCa adjusted percentiles ---
    z_lo = _norm_ppf(0.025)
    z_hi = _norm_ppf(0.975)

    def _adj(z_alpha: float) -> float:
        numer = z0 + z_alpha
        denom_a = 1.0 - a * numer
        if abs(denom_a) < 1e-12:
            return 0.5
        return max(0.0, min(1.0, _norm_cdf(z0 + numer / denom_a)))

    adj_lo = _adj(z_lo)
    adj_hi = _adj(z_hi)

    return float(np.percentile(means, 100.0 * adj_lo)), float(np.percentile(means, 100.0 * adj_hi))


def _bootstrap_eif_interval(
    values: np.ndarray,
    influence_values: np.ndarray,
    *,
    seed: int,
    draws: int,
    work_counter: BootstrapExecutionCounter | None = None,
) -> tuple[float, float]:
    """BCa bootstrap on EIF pseudo-values for improved coverage."""
    arr = np.asarray(values, dtype=float).reshape(-1)
    infl = np.asarray(influence_values, dtype=float).reshape(-1)
    if infl.size != arr.size:
        return _bootstrap_interval(arr, seed=seed, draws=draws, work_counter=work_counter)

    center = float(np.mean(arr))
    eif_scores = center + infl
    if eif_scores.size == 0:
        return float("nan"), float("nan")
    # Delegate to BCa-aware _bootstrap_interval on the pseudo-values
    return _bootstrap_interval(eif_scores, seed=seed, draws=draws, work_counter=work_counter)


__all__ = [
    "BootstrapExecutionCounter",
    "BootstrapExecutionWork",
    "CIBackendSelection",
    "bootstrap_mean_interval",
    "ci_backend_metadata",
    "partial_corr",
    "partial_corr_batch",
    "resolve_discovery_ci_backend",
    "robust_standard_error",
]
