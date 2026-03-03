from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np

_VALID_DISCOVERY_CI_BACKENDS: frozenset[str] = frozenset({"auto", "numpy", "jax"})


@dataclass(frozen=True)
class CIBackendSelection:
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
    requested = _normalize_backend(raw)
    if requested not in _VALID_DISCOVERY_CI_BACKENDS:
        return CIBackendSelection(
            requested=requested,
            used="numpy",
            fallback_reason=(
                f"unsupported_discovery_ci_backend:{requested}; "
                "expected one of auto|numpy|jax"
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


__all__ = [
    "CIBackendSelection",
    "ci_backend_metadata",
    "partial_corr",
    "partial_corr_batch",
    "resolve_discovery_ci_backend",
]
