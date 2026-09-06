"""Public survey estimation module API."""

from __future__ import annotations

from collections.abc import Mapping
from statistics import NormalDist
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.foundry.methods.catalog.dependence.diagnostics import _row_standardize_weights
from polisyos.foundry.methods.catalog.dependence.protocols import (
    DependenceDiagnosticData,
    DependenceGraphSpec,
)
from polisyos.foundry.methods.catalog.survey.protocols import (
    AUXILIARY_TOTAL_UNCERTAINTY_TARGET,
    CALIBRATION_WEIGHTS_TARGET,
    AuxiliaryTotalUncertainty,
    CalibrationWeights,
    SAEResult,
)
from polisyos.ir.analytics.dependence_structure import (
    dependence_structure_from_graph_diagnostic,
    persist_dependence_structure,
)
from polisyos.ir.artifacts.io import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel

_FLOAT_EPS = 1e-12
_CHI2_95 = 3.841458820694124


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _persist_sae_quality_certificate(
    artifact_store: Any | None,
    quality_certificate: dict[str, Any],
) -> ArtifactRefModel | None:
    if artifact_store is None:
        return None
    ref = put_json_artifact(
        artifact_store,
        quality_certificate,
        kind="ir.sae_quality_certificate",
        schema_name="ir.sae_quality_certificate",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref)


def _greg_output_slots() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec("result", SlotType.SCALAR, Unit("result", "json")),
            SlotSpec(
                "calibration_weights",
                SlotType.SCALAR,
                Unit("weight", "json"),
                contract_id=CALIBRATION_WEIGHTS_TARGET.contract_id,
            ),
        }
    )


def _condition_number(matrix: np.ndarray) -> float:
    if matrix.size == 0:
        return 1.0
    try:
        return float(np.linalg.cond(matrix))
    except np.linalg.LinAlgError:
        return float("inf")


def _vector_from_state(state: Mapping[str, Any], key: str, *aliases: str) -> np.ndarray:
    for candidate in (key,) + aliases:
        if candidate in state:
            arr = np.asarray(state[candidate], dtype=float)
            if arr.ndim != 1:
                raise ValueError(f"{candidate} must be a 1D vector")
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"{candidate} must contain only finite values")
            return arr
    raise KeyError(f"missing required input: {key}")


def _matrix_from_state(state: Mapping[str, Any], key: str, *aliases: str) -> np.ndarray:
    for candidate in (key,) + aliases:
        if candidate in state:
            arr = np.asarray(state[candidate], dtype=float)
            if arr.ndim != 2:
                raise ValueError(f"{candidate} must be a 2D matrix")
            if not np.all(np.isfinite(arr)):
                raise ValueError(f"{candidate} must contain only finite values")
            return arr
    raise KeyError(f"missing required input: {key}")


def _optional_q_weights(
    state: Mapping[str, Any], params: Mapping[str, Any], n_obs: int
) -> np.ndarray:
    raw = state.get("q_weights", params.get("q_weights"))
    if raw is None:
        return np.ones((n_obs,), dtype=float)
    if np.isscalar(raw):
        value = float(raw)
        if not np.isfinite(value) or value <= 0.0:
            raise ValueError("q_weights scalar must be finite and > 0")
        return np.full((n_obs,), value, dtype=float)
    arr = np.asarray(raw, dtype=float).reshape(-1)
    if arr.shape[0] != n_obs:
        raise ValueError("q_weights length must match y")
    if not np.all(np.isfinite(arr)) or np.any(arr <= 0.0):
        raise ValueError("q_weights must be finite and strictly positive")
    return arr


def _optional_sample_aux_error_cov(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    n_aux: int,
) -> np.ndarray | None:
    raw = state.get("sample_aux_error_cov", params.get("sample_aux_error_cov"))
    if raw is None:
        return None
    arr = np.asarray(raw, dtype=float)
    if arr.shape != (n_aux, n_aux):
        raise ValueError(f"sample_aux_error_cov must have shape {(n_aux, n_aux)}")
    if not np.all(np.isfinite(arr)):
        raise ValueError("sample_aux_error_cov must contain only finite values")
    if not np.allclose(arr, arr.T, atol=1e-10):
        raise ValueError("sample_aux_error_cov must be symmetric")
    return 0.5 * (arr + arr.T)


def _optional_bounds(
    state: Mapping[str, Any], params: Mapping[str, Any]
) -> tuple[float, float] | None:
    raw = state.get("bounds", params.get("bounds"))
    if raw is None:
        return None
    if isinstance(raw, np.ndarray):
        values = raw.reshape(-1).tolist()
    elif isinstance(raw, (list, tuple)):
        values = list(raw)
    else:
        raise TypeError("bounds must be a length-2 sequence")
    if len(values) != 2:
        raise ValueError("bounds must be a length-2 sequence")
    lower, upper = map(float, values)
    if not np.isfinite(lower) or not np.isfinite(upper):
        raise ValueError("bounds must be finite")
    if lower >= upper:
        raise ValueError("bounds must satisfy lower < upper")
    return lower, upper


def _normalize_auxiliary_total_uncertainty(
    raw: Any,
    *,
    n_aux: int,
) -> AuxiliaryTotalUncertainty:
    if isinstance(raw, AuxiliaryTotalUncertainty):
        if raw.n_targets != n_aux:
            raise ValueError(
                "auxiliary_total_uncertainty target count must match population_totals"
            )
        return raw
    if not isinstance(raw, Mapping):
        raise TypeError(
            "auxiliary_total_uncertainty must be a mapping or AuxiliaryTotalUncertainty"
        )

    payload = dict(raw)
    payload.setdefault("schema_version", "1.0")
    payload.setdefault("target_names", [f"aux_{idx}" for idx in range(n_aux)])
    if "source_kind" not in payload:
        probe_keys = ("covariance_matrix", "variance", "standard_error", "replicate_totals")
        is_exact = False
        for probe_key in probe_keys:
            candidate = payload.get(probe_key)
            if candidate is None:
                continue
            arr = np.asarray(candidate, dtype=float)
            is_exact = bool(np.allclose(arr, 0.0, atol=1e-10))
            break
        payload["source_kind"] = "exact" if is_exact else "estimated_external"

    model = AuxiliaryTotalUncertainty.model_validate(payload)
    if model.n_targets != n_aux:
        raise ValueError("auxiliary_total_uncertainty target count must match population_totals")
    return model


def _covariance_from_state(
    state: Mapping[str, Any], n_aux: int, totals: np.ndarray
) -> tuple[
    AuxiliaryTotalUncertainty | None,
    np.ndarray,
]:
    raw = state.get("auxiliary_total_uncertainty")
    if raw is None:
        return None, np.zeros((n_aux, n_aux), dtype=float)
    uncertainty = _normalize_auxiliary_total_uncertainty(raw, n_aux=n_aux)
    covariance = uncertainty.to_covariance(reference_totals=totals)
    if covariance.shape != (n_aux, n_aux):
        raise ValueError("auxiliary_total_uncertainty covariance dimension mismatch")
    return uncertainty, covariance


def _materialize_greg_state(
    bound_inputs: Mapping[str, Any], fallback_state: Any
) -> Mapping[str, Any]:
    if isinstance(fallback_state, Mapping):
        payload = dict(fallback_state)
    else:
        payload = {}
    payload.update(bound_inputs)

    x_sample = payload.get("X", payload.get("x_sample"))
    known_totals = payload.get("population_totals", payload.get("known_totals"))
    aux_uncertainty = payload.get("auxiliary_total_uncertainty")
    if aux_uncertainty is not None and x_sample is not None and known_totals is not None:
        n_aux = int(np.asarray(known_totals, dtype=float).reshape(-1).shape[0])
        payload["auxiliary_total_uncertainty"] = _normalize_auxiliary_total_uncertainty(
            aux_uncertainty,
            n_aux=n_aux,
        )
    if "sample_aux_error_cov" in payload and payload["sample_aux_error_cov"] is not None:
        n_aux = int(np.asarray(known_totals, dtype=float).reshape(-1).shape[0])
        payload["sample_aux_error_cov"] = _optional_sample_aux_error_cov(payload, {}, n_aux)
    if "q_weights" in payload and payload["q_weights"] is not None and x_sample is not None:
        n_obs = int(np.asarray(x_sample, dtype=float).shape[0])
        payload["q_weights"] = _optional_q_weights(payload, {}, n_obs)
    if "bounds" in payload and payload["bounds"] is not None:
        payload["bounds"] = _optional_bounds(payload, {})
    return payload


def _solve_system(
    system: np.ndarray, rhs: np.ndarray
) -> tuple[np.ndarray, np.ndarray, str, float, float]:
    if system.shape[0] == 0:
        return rhs.copy(), system.copy(), "ok", 1.0, 0.0

    sym_system = 0.5 * (system + system.T)
    try:
        condition_number = float(np.linalg.cond(sym_system))
    except np.linalg.LinAlgError:
        condition_number = float("inf")

    ridge = 0.0
    adjusted = sym_system
    status = "ok"
    if not np.isfinite(condition_number) or condition_number > 1e12:
        ridge = max(float(np.trace(sym_system)) / max(sym_system.shape[0], 1), 1.0) * 1e-8
        adjusted = sym_system + ridge * np.eye(sym_system.shape[0])
        status = "regularized"

    try:
        solution = np.linalg.solve(adjusted, rhs)
        return solution, adjusted, status, condition_number, ridge
    except np.linalg.LinAlgError:
        if ridge == 0.0:
            ridge = max(float(np.trace(sym_system)) / max(sym_system.shape[0], 1), 1.0) * 1e-8
            adjusted = sym_system + ridge * np.eye(sym_system.shape[0])
        solution = np.linalg.pinv(adjusted) @ rhs
        return solution, adjusted, "fallback_pinv", condition_number, ridge


def _safe_solve(matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(matrix) @ rhs


def _normal_logscore(observed: np.ndarray, mean: np.ndarray, variance: np.ndarray) -> np.ndarray:
    clipped = np.maximum(np.asarray(variance, dtype=float), _FLOAT_EPS)
    return -0.5 * (
        np.log(2.0 * np.pi * clipped)
        + ((np.asarray(observed, dtype=float) - np.asarray(mean, dtype=float)) ** 2) / clipped
    )


def _normal_crps(observed: np.ndarray, mean: np.ndarray, variance: np.ndarray) -> np.ndarray:
    std = np.sqrt(np.maximum(np.asarray(variance, dtype=float), _FLOAT_EPS))
    z = (np.asarray(observed, dtype=float) - np.asarray(mean, dtype=float)) / std
    phi = np.exp(-0.5 * z**2) / np.sqrt(2.0 * np.pi)
    Phi = np.asarray([NormalDist().cdf(float(value)) for value in z], dtype=float)
    return std * (z * (2.0 * Phi - 1.0) + 2.0 * phi - 1.0 / np.sqrt(np.pi))


def _conditional_predictive_scores(
    y: np.ndarray,
    X: np.ndarray,
    D: np.ndarray,
    fit: Mapping[str, Any],
) -> dict[str, float]:
    beta = np.asarray(fit["beta"], dtype=float)
    mean = X @ beta
    G = np.asarray(fit["G"], dtype=float)
    V = np.diag(D) + G
    cond_mean = np.empty(y.shape[0], dtype=float)
    cond_var = np.empty(y.shape[0], dtype=float)

    if np.allclose(V, np.diag(np.diag(V)), atol=1e-10):
        cond_mean[:] = mean
        cond_var[:] = np.diag(V)
    else:
        for idx in range(y.shape[0]):
            mask = np.ones(y.shape[0], dtype=bool)
            mask[idx] = False
            if not np.any(mask):
                cond_mean[idx] = mean[idx]
                cond_var[idx] = max(float(V[idx, idx]), _FLOAT_EPS)
                continue
            v_i = V[idx, mask]
            solved_resid = _safe_solve(V[np.ix_(mask, mask)], y[mask] - mean[mask])
            solved_cov = _safe_solve(V[np.ix_(mask, mask)], V[mask, idx])
            cond_mean[idx] = float(mean[idx] + v_i @ solved_resid)
            cond_var[idx] = max(float(V[idx, idx] - v_i @ solved_cov), _FLOAT_EPS)

    logscore = _normal_logscore(y, cond_mean, cond_var)
    crps = _normal_crps(y, cond_mean, cond_var)
    return {
        "heldout_logscore": float(np.mean(logscore)),
        "crps": float(np.mean(crps)),
    }


def _profile_interval(
    values: np.ndarray, profile_loss: np.ndarray
) -> tuple[tuple[float, float] | None, bool | None]:
    finite_mask = np.isfinite(profile_loss)
    if not np.any(finite_mask):
        return None, None
    min_loss = float(np.min(profile_loss[finite_mask]))
    support = finite_mask & (profile_loss <= min_loss + _CHI2_95)
    if not np.any(support):
        return None, None
    interval = (float(np.min(values[support])), float(np.max(values[support])))
    return interval, bool(interval[0] <= 0.0 <= interval[1])


def _numerical_hessian_2d(
    fn: Any,
    x0: float,
    y0: float,
    *,
    hx: float,
    hy: float,
) -> np.ndarray | None:
    points = {
        "f00": fn(x0, y0),
        "fxp": fn(x0 + hx, y0),
        "fxm": fn(x0 - hx, y0),
        "fyp": fn(x0, y0 + hy),
        "fym": fn(x0, y0 - hy),
        "fpp": fn(x0 + hx, y0 + hy),
        "fpm": fn(x0 + hx, y0 - hy),
        "fmp": fn(x0 - hx, y0 + hy),
        "fmm": fn(x0 - hx, y0 - hy),
    }
    if not all(np.isfinite(value) for value in points.values()):
        return None

    h11 = (points["fxp"] - 2.0 * points["f00"] + points["fxm"]) / max(hx * hx, _FLOAT_EPS)
    h22 = (points["fyp"] - 2.0 * points["f00"] + points["fym"]) / max(hy * hy, _FLOAT_EPS)
    h12 = (points["fpp"] - points["fpm"] - points["fmp"] + points["fmm"]) / max(
        4.0 * hx * hy, _FLOAT_EPS
    )
    return np.asarray([[h11, h12], [h12, h22]], dtype=float)


def _graph_role(graph: DependenceGraphSpec) -> str | None:
    text = " ".join(
        [
            graph.graph_id,
            graph.family,
            str(graph.metadata.get("role", "")),
            str(graph.metadata.get("graph_role", "")),
        ]
    ).lower()
    if any(token in text for token in ("admin", "network", "hierarchy", "flow")):
        return "admin"
    if any(token in text for token in ("spatial", "geo", "contiguity", "neighbor")):
        return "spatial"
    return None


def _validate_small_area_inputs(y: np.ndarray, X: np.ndarray, D: np.ndarray) -> None:
    if y.ndim != 1:
        raise ValueError("y_direct must be a 1D vector")
    if X.ndim != 2:
        raise ValueError("X must be a 2D matrix")
    if D.ndim != 1:
        raise ValueError("sampling_var must be a 1D vector")
    if X.shape[0] != y.shape[0] or D.shape[0] != y.shape[0]:
        raise ValueError("y_direct, X, and sampling_var must align on n_areas")
    if y.shape[0] < 3:
        raise ValueError("Fay-Herriot requires at least 3 areas")
    if X.shape[1] < 1:
        raise ValueError("X must contain at least one covariate")
    if not np.isfinite(y).all() or not np.isfinite(X).all() or not np.isfinite(D).all():
        raise ValueError("inputs must be finite")
    if np.any(D <= 0.0):
        raise ValueError("sampling_var must be strictly positive")
    if np.linalg.matrix_rank(X) < X.shape[1]:
        raise ValueError("X must have full column rank")


def _reml_from_covariance(y: np.ndarray, X: np.ndarray, V: np.ndarray) -> dict[str, Any] | None:
    sign_v, logdet_v = np.linalg.slogdet(V)
    if sign_v <= 0.0:
        return None

    vinv_x = _safe_solve(V, X)
    xt_vinv_x = X.T @ vinv_x
    sign_x, logdet_x = np.linalg.slogdet(xt_vinv_x)
    if sign_x <= 0.0:
        return None

    vinv_y = _safe_solve(V, y)
    beta = _safe_solve(xt_vinv_x, X.T @ vinv_y)
    residuals = y - X @ beta
    quad = float(residuals @ _safe_solve(V, residuals))

    return {
        "beta": beta,
        "residuals": residuals,
        "reml_loss": float(logdet_v + logdet_x + quad),
    }


def _fay_herriot_baseline_fit(
    y: np.ndarray, X: np.ndarray, D: np.ndarray, *, max_iter: int
) -> dict[str, Any]:
    beta_ols = np.linalg.lstsq(X, y, rcond=None)[0]
    residuals = y - X @ beta_ols
    A_hat = max(0.0, float(np.mean(residuals**2) - np.mean(D)))
    beta = beta_ols

    for _ in range(max_iter):
        w = 1.0 / np.maximum(D + A_hat, _FLOAT_EPS)
        xtwx = X.T @ (w[:, None] * X)
        xtwy = X.T @ (w * y)
        beta = _safe_solve(xtwx, xtwy)
        resid = y - X @ beta
        numerator = float(np.sum((w**2) * (resid**2 - D)))
        denominator = max(float(np.sum(w**2)), _FLOAT_EPS)
        A_new = max(0.0, numerator / denominator)
        if abs(A_new - A_hat) < 1e-8:
            A_hat = A_new
            break
        A_hat = A_new

    gamma = A_hat / np.maximum(A_hat + D, _FLOAT_EPS)
    regression_mean = X @ beta
    eblup = gamma * y + (1.0 - gamma) * regression_mean
    mse = D * A_hat / np.maximum(D + A_hat, _FLOAT_EPS)
    reml = _reml_from_covariance(y, X, np.diag(D + A_hat))
    reml_loss = float(reml["reml_loss"]) if reml is not None else float("inf")

    fit = {
        "beta": beta,
        "A_hat": float(A_hat),
        "gamma": gamma,
        "theta": eblup,
        "mse": np.clip(mse, 0.0, None),
        "reml_loss": reml_loss,
        "bic": float(reml_loss + np.log(y.shape[0])),
        "residuals": y - regression_mean,
        "fitted_mean": regression_mean,
        "G": np.diag(np.full(y.shape[0], A_hat, dtype=float)),
    }
    fit.update(_conditional_predictive_scores(y, X, D, fit))
    return fit


def _sar_covariance(weights: np.ndarray, rho: float) -> np.ndarray:
    identity = np.eye(weights.shape[0], dtype=float)
    system = identity - rho * weights
    covariance = np.linalg.pinv(system.T @ system)
    return 0.5 * (covariance + covariance.T)


def _tau2_grid(y: np.ndarray, D: np.ndarray, baseline_a: float, *, n_grid: int) -> np.ndarray:
    upper = max(
        baseline_a * 5.0,
        float(np.var(y)),
        float(np.mean(D)),
        1e-3,
    )
    grid = np.geomspace(1e-6, upper, num=max(4, n_grid))
    return np.unique(np.concatenate(([0.0, baseline_a], grid)))


def _rho_grid(weights: np.ndarray, *, n_grid: int) -> tuple[np.ndarray, float]:
    spectral_radius = float(np.max(np.abs(np.linalg.eigvals(weights))))
    if spectral_radius <= 1e-8:
        return np.array([0.0], dtype=float), 0.0
    rho_limit = 0.95 / spectral_radius
    return np.linspace(-rho_limit, rho_limit, num=max(3, n_grid)), rho_limit


def _graph_reml_loss(
    y: np.ndarray,
    X: np.ndarray,
    D: np.ndarray,
    weights: np.ndarray,
    *,
    tau2: float,
    rho: float,
) -> float:
    if tau2 < 0.0:
        return float("inf")
    try:
        R = _sar_covariance(weights, float(rho))
    except np.linalg.LinAlgError:
        return float("inf")
    reml = _reml_from_covariance(y, X, np.diag(D) + float(tau2) * R)
    return float(reml["reml_loss"]) if reml is not None else float("inf")


def _fit_graph_fh(
    y: np.ndarray,
    X: np.ndarray,
    D: np.ndarray,
    graph: DependenceGraphSpec,
    *,
    baseline_a: float,
    rho_grid_size: int,
    tau2_grid_size: int,
) -> dict[str, Any] | None:
    weights = _row_standardize_weights(graph.W)
    rho_values, rho_limit = _rho_grid(weights, n_grid=rho_grid_size)
    tau2_values = _tau2_grid(y, D, baseline_a, n_grid=tau2_grid_size)
    profile_loss = np.full(rho_values.shape[0], np.inf, dtype=float)
    best: dict[str, Any] | None = None

    for rho_idx, rho in enumerate(rho_values):
        try:
            R = _sar_covariance(weights, float(rho))
        except np.linalg.LinAlgError:
            continue
        best_for_rho: dict[str, Any] | None = None

        for tau2 in tau2_values:
            G = float(tau2) * R
            V = np.diag(D) + G
            reml = _reml_from_covariance(y, X, V)
            if reml is None:
                continue

            beta = np.asarray(reml["beta"], dtype=float)
            residuals = np.asarray(reml["residuals"], dtype=float)
            v_inv_residuals = _safe_solve(V, residuals)
            theta = X @ beta + G @ v_inv_residuals
            mse = np.diag(G - G @ _safe_solve(V, G))
            candidate = {
                "graph_id": graph.graph_id,
                "family": graph.family,
                "beta": beta,
                "tau2": float(tau2),
                "rho": float(rho),
                "theta": np.asarray(theta, dtype=float),
                "mse": np.clip(np.asarray(mse, dtype=float), 0.0, None),
                "reml_loss": float(reml["reml_loss"]),
                "G": G,
            }
            if best_for_rho is None or candidate["reml_loss"] < best_for_rho["reml_loss"]:
                best_for_rho = candidate

        if best_for_rho is not None:
            profile_loss[rho_idx] = best_for_rho["reml_loss"]
            if best is None or best_for_rho["reml_loss"] < best["reml_loss"]:
                best = best_for_rho
                best["rho_index"] = rho_idx
                best["rho_limit"] = rho_limit

    if best is None:
        return None

    rho_index = int(best["rho_index"])
    if rho_index == 0 or rho_index == len(rho_values) - 1:
        curvature = 0.0
        boundary_hit = True
    else:
        curvature = float(
            profile_loss[rho_index - 1]
            - 2.0 * profile_loss[rho_index]
            + profile_loss[rho_index + 1]
        )
        boundary_hit = bool(abs(best["rho"]) >= 0.98 * rho_limit)

    rho_confidence_interval, rho_interval_contains_zero = _profile_interval(
        rho_values, profile_loss
    )
    tau_step = max(1e-5, 0.05 * max(float(best["tau2"]), 1e-3))
    rho_step = max(1e-4, 0.05 * max(abs(rho_limit), 1e-2))
    hessian = _numerical_hessian_2d(
        lambda tau2, rho: _graph_reml_loss(y, X, D, weights, tau2=tau2, rho=rho),
        float(best["tau2"]),
        float(best["rho"]),
        hx=tau_step,
        hy=min(rho_step, max(rho_limit * 0.25, 1e-4)),
    )
    information_eigen_min = None
    information_condition_number = None
    if hessian is not None:
        eigenvalues = np.linalg.eigvalsh(0.5 * (hessian + hessian.T))
        information_eigen_min = float(np.min(eigenvalues))
        max_eigen = float(np.max(eigenvalues))
        information_condition_number = (
            float(max_eigen / max(information_eigen_min, _FLOAT_EPS))
            if information_eigen_min > _FLOAT_EPS
            else float("inf")
        )

    weak_rho_identification = bool(
        rho_confidence_interval is not None
        and rho_interval_contains_zero
        and abs(float(best["rho"])) <= max(0.05, 0.25 * max(rho_limit, 1e-3))
    )
    best["profile_curvature"] = curvature
    best["boundary_hit"] = boundary_hit
    best["information_eigen_min"] = information_eigen_min
    best["information_condition_number"] = information_condition_number
    best["rho_confidence_interval"] = rho_confidence_interval
    best["rho_interval_contains_zero"] = rho_interval_contains_zero
    best["identifiable"] = bool(
        not boundary_hit
        and curvature > 1e-4
        and best["tau2"] > 1e-8
        and (information_eigen_min is None or information_eigen_min > 1e-5)
        and (
            information_condition_number is None
            or (np.isfinite(information_condition_number) and information_condition_number < 1e8)
        )
        and not weak_rho_identification
    )
    best["bic"] = float(best["reml_loss"] + 2.0 * np.log(y.shape[0]))
    best.update(_conditional_predictive_scores(y, X, D, best))
    return best


def _hybrid_pair(
    candidate_graphs: tuple[DependenceGraphSpec, ...],
) -> tuple[DependenceGraphSpec, DependenceGraphSpec] | None:
    spatial = next((graph for graph in candidate_graphs if _graph_role(graph) == "spatial"), None)
    admin = next((graph for graph in candidate_graphs if _graph_role(graph) == "admin"), None)
    if spatial is not None and admin is not None and spatial.graph_id != admin.graph_id:
        return spatial, admin
    if len(candidate_graphs) >= 2:
        return candidate_graphs[0], candidate_graphs[1]
    return None


def _fit_hybrid_graph_fh(
    y: np.ndarray,
    X: np.ndarray,
    D: np.ndarray,
    primary_graph: DependenceGraphSpec,
    secondary_graph: DependenceGraphSpec,
    *,
    primary_fit: Mapping[str, Any],
    secondary_fit: Mapping[str, Any],
    baseline_a: float,
    tau2_grid_size: int,
    mix_grid_size: int = 19,
) -> dict[str, Any] | None:
    if primary_fit.get("rho") is None or secondary_fit.get("rho") is None:
        return None

    R_primary = _sar_covariance(
        _row_standardize_weights(primary_graph.W), float(primary_fit["rho"])
    )
    R_secondary = _sar_covariance(
        _row_standardize_weights(secondary_graph.W), float(secondary_fit["rho"])
    )
    tau2_values = _tau2_grid(y, D, baseline_a, n_grid=tau2_grid_size)
    mix_values = np.linspace(0.05, 0.95, num=max(5, mix_grid_size))
    profile_loss = np.full(mix_values.shape[0], np.inf, dtype=float)
    best: dict[str, Any] | None = None

    for mix_idx, mix_weight in enumerate(mix_values):
        covariance_kernel = mix_weight * R_primary + (1.0 - mix_weight) * R_secondary
        covariance_kernel = 0.5 * (covariance_kernel + covariance_kernel.T)
        best_for_mix: dict[str, Any] | None = None
        for tau2 in tau2_values:
            G = float(tau2) * covariance_kernel
            reml = _reml_from_covariance(y, X, np.diag(D) + G)
            if reml is None:
                continue
            beta = np.asarray(reml["beta"], dtype=float)
            residuals = np.asarray(reml["residuals"], dtype=float)
            theta = X @ beta + G @ _safe_solve(np.diag(D) + G, residuals)
            mse = np.diag(G - G @ _safe_solve(np.diag(D) + G, G))
            candidate = {
                "graph_id": f"hybrid:{primary_graph.graph_id}+{secondary_graph.graph_id}",
                "family": "HYBRID",
                "beta": beta,
                "tau2": float(tau2),
                "rho": None,
                "theta": np.asarray(theta, dtype=float),
                "mse": np.clip(np.asarray(mse, dtype=float), 0.0, None),
                "reml_loss": float(reml["reml_loss"]),
                "G": G,
                "mix_weight": float(mix_weight),
                "kernel_components": (
                    {
                        "graph_id": primary_graph.graph_id,
                        "rho": float(primary_fit["rho"]),
                    },
                    {
                        "graph_id": secondary_graph.graph_id,
                        "rho": float(secondary_fit["rho"]),
                    },
                ),
            }
            if best_for_mix is None or candidate["reml_loss"] < best_for_mix["reml_loss"]:
                best_for_mix = candidate
        if best_for_mix is not None:
            profile_loss[mix_idx] = best_for_mix["reml_loss"]
            if best is None or best_for_mix["reml_loss"] < best["reml_loss"]:
                best = best_for_mix
                best["mix_index"] = mix_idx

    if best is None:
        return None

    mix_index = int(best["mix_index"])
    if mix_index == 0 or mix_index == len(mix_values) - 1:
        curvature = 0.0
        boundary_hit = True
    else:
        curvature = float(
            profile_loss[mix_index - 1]
            - 2.0 * profile_loss[mix_index]
            + profile_loss[mix_index + 1]
        )
        boundary_hit = bool(best["mix_weight"] <= 0.06 or best["mix_weight"] >= 0.94)

    tau_step = max(1e-5, 0.05 * max(float(best["tau2"]), 1e-3))
    mix_step = 0.05

    def hybrid_loss(tau2: float, mix_weight: float) -> float:
        if tau2 < 0.0 or mix_weight <= 0.0 or mix_weight >= 1.0:
            return float("inf")
        kernel = mix_weight * R_primary + (1.0 - mix_weight) * R_secondary
        kernel = 0.5 * (kernel + kernel.T)
        reml = _reml_from_covariance(y, X, np.diag(D) + float(tau2) * kernel)
        return float(reml["reml_loss"]) if reml is not None else float("inf")

    hessian = _numerical_hessian_2d(
        hybrid_loss,
        float(best["tau2"]),
        float(best["mix_weight"]),
        hx=tau_step,
        hy=mix_step,
    )
    information_eigen_min = None
    information_condition_number = None
    if hessian is not None:
        eigenvalues = np.linalg.eigvalsh(0.5 * (hessian + hessian.T))
        information_eigen_min = float(np.min(eigenvalues))
        max_eigen = float(np.max(eigenvalues))
        information_condition_number = (
            float(max_eigen / max(information_eigen_min, _FLOAT_EPS))
            if information_eigen_min > _FLOAT_EPS
            else float("inf")
        )

    best["profile_curvature"] = curvature
    best["boundary_hit"] = boundary_hit
    best["information_eigen_min"] = information_eigen_min
    best["information_condition_number"] = information_condition_number
    best["rho_confidence_interval"] = None
    best["rho_interval_contains_zero"] = None
    best["identifiable"] = bool(
        not boundary_hit
        and curvature > 1e-4
        and best["tau2"] > 1e-8
        and 0.10 <= best["mix_weight"] <= 0.90
        and (information_eigen_min is None or information_eigen_min > 1e-5)
        and (
            information_condition_number is None
            or (np.isfinite(information_condition_number) and information_condition_number < 1e8)
        )
    )
    best["bic"] = float(best["reml_loss"] + 3.0 * np.log(y.shape[0]))
    best.update(_conditional_predictive_scores(y, X, D, best))
    return best


def _analytic_intervals(estimates: np.ndarray, mse: np.ndarray) -> list[list[float]]:
    radius = 1.96 * np.sqrt(np.maximum(mse, 0.0))
    return [
        [float(est - rad), float(est + rad)] for est, rad in zip(estimates, radius, strict=False)
    ]


def _bootstrap_uncertainty(
    y: np.ndarray,
    X: np.ndarray,
    D: np.ndarray,
    selected_fit: dict[str, Any],
    *,
    bootstrap_reps: int,
    max_iter: int,
    rho_grid_size: int,
    tau2_grid_size: int,
    graph: DependenceGraphSpec | None,
    hybrid_graphs: tuple[DependenceGraphSpec, DependenceGraphSpec] | None,
    seed: int,
) -> tuple[np.ndarray, list[list[float]]]:
    rng = np.random.default_rng(seed)
    draws = np.empty((bootstrap_reps, y.shape[0]), dtype=float)
    beta = np.asarray(selected_fit["beta"], dtype=float)
    mean = X @ beta
    D_chol = np.sqrt(D)

    for rep in range(bootstrap_reps):
        if graph is None and hybrid_graphs is None:
            A_hat = float(selected_fit["A_hat"])
            latent = mean + np.sqrt(max(A_hat, 0.0)) * rng.normal(size=y.shape[0])
        else:
            G = np.asarray(selected_fit["G"], dtype=float)
            latent = rng.multivariate_normal(mean=mean, cov=G + 1e-10 * np.eye(G.shape[0]))
        direct = latent + D_chol * rng.normal(size=y.shape[0])
        if graph is None and hybrid_graphs is None:
            fit_rep = _fay_herriot_baseline_fit(direct, X, D, max_iter=max_iter)
        elif hybrid_graphs is not None:
            component_map = {
                str(item["graph_id"]): item for item in selected_fit.get("kernel_components", ())
            }
            primary_graph, secondary_graph = hybrid_graphs
            fit_rep = _fit_hybrid_graph_fh(
                direct,
                X,
                D,
                primary_graph,
                secondary_graph,
                primary_fit=component_map.get(primary_graph.graph_id, {"rho": 0.0}),
                secondary_fit=component_map.get(secondary_graph.graph_id, {"rho": 0.0}),
                baseline_a=float(max(selected_fit["tau2"], 1e-6)),
                tau2_grid_size=tau2_grid_size,
            )
            if fit_rep is None:
                fit_rep = _fay_herriot_baseline_fit(direct, X, D, max_iter=max_iter)
        else:
            fit_rep = _fit_graph_fh(
                direct,
                X,
                D,
                graph,
                baseline_a=float(max(selected_fit["tau2"], 1e-6)),
                rho_grid_size=rho_grid_size,
                tau2_grid_size=tau2_grid_size,
            )
            if fit_rep is None:
                fit_rep = _fay_herriot_baseline_fit(direct, X, D, max_iter=max_iter)
        draws[rep] = np.asarray(fit_rep["theta"], dtype=float)

    mse = np.var(draws, axis=0, ddof=1 if bootstrap_reps > 1 else 0)
    intervals = [
        [float(np.percentile(draws[:, idx], 2.5)), float(np.percentile(draws[:, idx], 97.5))]
        for idx in range(draws.shape[1])
    ]
    return np.asarray(mse, dtype=float), intervals


def _coerce_candidate_graphs(
    state: Mapping[str, Any], n_areas: int
) -> tuple[DependenceGraphSpec, ...]:
    raw_graphs = state.get("candidate_graphs") or ()
    graphs = tuple(
        item if isinstance(item, DependenceGraphSpec) else DependenceGraphSpec.model_validate(item)
        for item in raw_graphs
    )
    for graph in graphs:
        if graph.W.shape != (n_areas, n_areas):
            raise ValueError(f"candidate graph {graph.graph_id!r} does not match n_areas")
    return graphs


def _diagnose_dependence(
    residuals: np.ndarray,
    candidate_graphs: tuple[DependenceGraphSpec, ...],
    *,
    area_ids: tuple[str, ...] | None,
    y_direct: np.ndarray | None,
    X: np.ndarray | None,
    candidate_fit_summaries: list[Mapping[str, Any]] | None,
    params: Mapping[str, Any],
) -> dict[str, Any]:
    from polisyos.foundry.methods.catalog.dependence.diagnostics import (
        GraphDependenceDiagnosticEstimator,
    )

    if not candidate_graphs:
        return {
            "detected": False,
            "class_label": "none",
            "estimator_status": "fallback_independent",
            "decision": "fallback_independent",
            "strength": "none",
            "identifiable": False,
            "selected_graph_id": None,
            "moran_i": None,
            "geary_c": None,
            "moran_p_value": None,
            "geary_p_value": None,
            "pesaran_cd": None,
            "pesaran_cd_p_value": None,
            "lm_error": None,
            "lm_error_p_value": None,
            "lm_lag": None,
            "lm_lag_p_value": None,
            "profile_curvature": None,
            "information_eigen_min": None,
            "information_condition_number": None,
            "rho_confidence_interval": None,
            "rho_interval_contains_zero": None,
            "fallback_reason": "no_candidate_graphs",
            "graph_diagnostics": (),
            "metadata": {},
        }

    result = GraphDependenceDiagnosticEstimator.pure_step(
        DependenceDiagnosticData(
            residuals=residuals,
            candidate_graphs=candidate_graphs,
            area_ids=area_ids,
            metadata={
                "y_direct": y_direct,
                "X": X,
                "candidate_fit_summaries": candidate_fit_summaries or [],
            },
        ),
        params,
    )["result"]
    return result.model_dump(mode="python")


def _criterion_value(fit: Mapping[str, Any], criterion: str) -> float:
    if criterion == "heldout_logscore":
        return float(-fit.get("heldout_logscore", float("-inf")))
    if criterion == "crps":
        return float(fit.get("crps", float("inf")))
    return float(fit.get("bic", fit.get("reml_loss", float("inf"))))


def _criterion_improvement(
    baseline_fit: Mapping[str, Any],
    candidate_fit: Mapping[str, Any],
    criterion: str,
) -> float:
    if criterion == "heldout_logscore":
        return float(
            candidate_fit.get("heldout_logscore", float("-inf"))
            - baseline_fit.get("heldout_logscore", float("-inf"))
        )
    if criterion == "crps":
        return float(
            baseline_fit.get("crps", float("inf")) - candidate_fit.get("crps", float("inf"))
        )
    return float(
        _criterion_value(baseline_fit, criterion) - _criterion_value(candidate_fit, criterion)
    )


def _criterion_threshold(criterion: str) -> float:
    if criterion == "bic":
        return 2.0
    if criterion == "heldout_logscore":
        return 1e-3
    if criterion == "crps":
        return 1e-4
    return 1e-3


@foundry_method(
    namespace="survey.estimation",
    version="1.0.0",
    tags={"survey", "small-area", "fay-herriot"},
)
class FayHerriotEstimator:
    """Estimate small-area outcomes with Fay-Herriot models."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fay_herriot",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "y_direct", SlotType.VECTOR, Unit("estimate", "value"), shape=("n_areas",)
                ),
                SlotSpec(
                    "X",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_areas", "n_covariates"),
                ),
                SlotSpec(
                    "sampling_var", SlotType.VECTOR, Unit("variance", "value"), shape=("n_areas",)
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("result", "json"),
                    contract_id=SAEResult.contract_id,
                )
            }
        ),
        parameters=(ParameterSpec(name="max_iter", default=100),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Fay-Herriot area-level model for small area estimation via EBLUP.",
        tags=frozenset({"survey", "small-area", "fay-herriot", "eblup"}),
        citations=(
            "Fay, R.E. & Herriot, R.A. (1979). Estimates of Income for Small Places. JASA.",
        ),
        equations={"fay_herriot": "y_i = x_i'*beta + v_i + e_i; v_i ~ N(0, A), e_i ~ N(0, D_i)"},
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Reliable estimates for small domains/areas with insufficient direct sample size; borrow strength",
        typical_min_obs=5,
        output_interpretation="EBLUP = weighted average of direct estimate and regression estimate. MSE smaller than direct. Shrinkage toward model prediction.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        y = np.asarray(state["y_direct"], dtype=float)
        X = np.asarray(state["X"], dtype=float)
        D = np.asarray(state["sampling_var"], dtype=float)
        _validate_small_area_inputs(y, X, D)
        m, _ = X.shape
        max_iter = int(params.get("max_iter", 100))
        fit = _fay_herriot_baseline_fit(y, X, D, max_iter=max_iter)

        return {
            "result": {
                "eblup_estimates": np.asarray(fit["theta"], dtype=float).tolist(),
                "beta": np.asarray(fit["beta"], dtype=float).tolist(),
                "model_variance_A": float(fit["A_hat"]),
                "shrinkage_factors": np.asarray(fit["gamma"], dtype=float).tolist(),
                "mse_estimates": np.asarray(fit["mse"], dtype=float).tolist(),
                "n_areas": m,
            }
        }


@foundry_method(
    namespace="survey.estimation",
    version="1.0.0",
    tags={"survey", "small-area", "fay-herriot", "dependence-aware"},
)
class FayHerriotDependenceAwareEstimator:
    """Estimate area-level outcomes with graph-aware FH selection and explicit fallback."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="fay_herriot_dependence_aware",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "y_direct", SlotType.VECTOR, Unit("estimate", "value"), shape=("n_areas",)
                ),
                SlotSpec(
                    "X",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_areas", "n_covariates"),
                ),
                SlotSpec(
                    "sampling_var", SlotType.VECTOR, Unit("variance", "value"), shape=("n_areas",)
                ),
                SlotSpec("candidate_graphs", SlotType.SCALAR, Unit("graph", "json")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="mode", default="auto"),
            ParameterSpec(name="criterion", default="bic"),
            ParameterSpec(name="selection_rule", default="diagnostic_plus_reml"),
            ParameterSpec(name="bootstrap_reps", default=0),
            ParameterSpec(name="coverage_benchmark_reps", default=0),
            ParameterSpec(name="coverage_bootstrap_reps", default=0),
            ParameterSpec(name="max_iter", default=100),
            ParameterSpec(name="rho_grid_size", default=21),
            ParameterSpec(name="tau2_grid_size", default=18),
            ParameterSpec(name="score_threshold", default=0.1),
            ParameterSpec(name="n_permutations", default=0),
            ParameterSpec(name="allow_hybrid", default=False),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Dependence-aware Fay-Herriot with graph diagnostics, selected-kernel fitting, and automatic fallback to independent FH.",
        tags=frozenset({"survey", "small-area", "fay-herriot", "dependence-aware", "eblup"}),
        citations=(
            "Fay, R.E. & Herriot, R.A. (1979). Estimates of Income for Small Places. JASA.",
            "Molina, I. & Marhuenda, Y. (2015). sae: An R package for small area estimation.",
        ),
        equations={
            "generalized_fh": "y = X beta + u + e; e ~ N(0, D), u ~ N(0, tau^2 R(rho))",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Small-area estimation when cross-area dependence may follow an exogenous spatial or administrative graph and the engine must safely fall back to independent FH when evidence is weak.",
        typical_min_obs=5,
        output_interpretation="The selected estimates borrow strength either through the independent FH baseline or through a graph-aware kernel. Diagnostics explain when fallback happened and which graph, if any, was trusted.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        y = np.asarray(state["y_direct"], dtype=float)
        X = np.asarray(state["X"], dtype=float)
        D = np.asarray(state["sampling_var"], dtype=float)
        _validate_small_area_inputs(y, X, D)

        max_iter = int(params.get("max_iter", 100))
        mode = str(params.get("mode", "auto")).strip().lower()
        criterion = str(params.get("criterion", "bic")).strip().lower()
        rho_grid_size = max(5, int(params.get("rho_grid_size", 21)))
        tau2_grid_size = max(5, int(params.get("tau2_grid_size", 18)))
        bootstrap_reps = max(0, int(params.get("bootstrap_reps", 0)))
        coverage_benchmark_reps = max(0, int(params.get("coverage_benchmark_reps", 0)))
        coverage_bootstrap_reps = max(0, int(params.get("coverage_bootstrap_reps", bootstrap_reps)))
        selection_rule = str(params.get("selection_rule", "diagnostic_plus_reml")).strip().lower()
        allow_hybrid = bool(params.get("allow_hybrid", False))
        area_ids = tuple(str(item) for item in state.get("area_ids", ())) or None

        candidate_graphs = _coerce_candidate_graphs(state, y.shape[0])
        baseline_fit = _fay_herriot_baseline_fit(y, X, D, max_iter=max_iter)
        baseline_selected: dict[str, Any] = {
            **baseline_fit,
            "selected_model": "independent",
            "selected_graph_id": None,
            "rho": None,
            "tau2": float(baseline_fit["A_hat"]),
            "identifiable": True,
            "fallback_reason": None,
            "family": "INDEPENDENT",
            "kernel_components": (),
        }
        selected_fit: dict[str, Any] = dict(baseline_selected)
        selected_graph: DependenceGraphSpec | None = None
        selected_hybrid_graphs: tuple[DependenceGraphSpec, DependenceGraphSpec] | None = None
        selection_note: str | None = None
        fallback_reason: str | None = None

        if mode == "independent":
            graphs_to_fit: tuple[DependenceGraphSpec, ...] = ()
        elif mode == "spatial":
            graphs_to_fit = tuple(
                graph for graph in candidate_graphs if _graph_role(graph) == "spatial"
            )
            if not graphs_to_fit:
                fallback_reason = "requested_mode_spatial_not_found"
        elif mode == "admin":
            graphs_to_fit = tuple(
                graph for graph in candidate_graphs if _graph_role(graph) == "admin"
            )
            if not graphs_to_fit:
                fallback_reason = "requested_mode_admin_not_found"
        elif mode in {"auto", "hybrid"}:
            graphs_to_fit = candidate_graphs
        else:
            graphs_to_fit = tuple(
                graph
                for graph in candidate_graphs
                if mode == graph.graph_id.lower()
                or mode in graph.graph_id.lower()
                or mode in graph.family.lower()
                or mode in str(graph.metadata.get("role", "")).lower()
            )
            if not graphs_to_fit:
                fallback_reason = f"requested_mode_{mode}_not_found"

        single_fit_candidates: list[dict[str, Any]] = []
        fit_by_graph_id: dict[str, dict[str, Any]] = {}
        if mode != "independent" and graphs_to_fit:
            for graph in graphs_to_fit:
                fit = _fit_graph_fh(
                    y,
                    X,
                    D,
                    graph,
                    baseline_a=float(baseline_fit["A_hat"]),
                    rho_grid_size=rho_grid_size,
                    tau2_grid_size=tau2_grid_size,
                )
                if fit is not None:
                    single_fit_candidates.append(fit)
                    fit_by_graph_id[graph.graph_id] = fit

        hybrid_fit: dict[str, Any] | None = None
        hybrid_pair = _hybrid_pair(graphs_to_fit) if (mode == "hybrid" or allow_hybrid) else None
        if hybrid_pair is not None:
            primary_graph, secondary_graph = hybrid_pair
            primary_fit = fit_by_graph_id.get(primary_graph.graph_id)
            secondary_fit = fit_by_graph_id.get(secondary_graph.graph_id)
            if primary_fit is not None and secondary_fit is not None:
                hybrid_fit = _fit_hybrid_graph_fh(
                    y,
                    X,
                    D,
                    primary_graph,
                    secondary_graph,
                    primary_fit=primary_fit,
                    secondary_fit=secondary_fit,
                    baseline_a=float(baseline_fit["A_hat"]),
                    tau2_grid_size=tau2_grid_size,
                )
            elif mode == "hybrid":
                fallback_reason = fallback_reason or "hybrid_components_not_estimable"
        elif mode == "hybrid":
            fallback_reason = fallback_reason or "hybrid_pair_not_available"

        fit_summary_payloads = [
            {
                "graph_id": fit["graph_id"],
                "identifiable": bool(fit.get("identifiable", False)),
                "profile_curvature": fit.get("profile_curvature"),
                "information_eigen_min": fit.get("information_eigen_min"),
                "information_condition_number": fit.get("information_condition_number"),
                "rho_confidence_interval": fit.get("rho_confidence_interval"),
                "rho_interval_contains_zero": fit.get("rho_interval_contains_zero"),
                "boundary_hit": fit.get("boundary_hit"),
            }
            for fit in single_fit_candidates
        ]
        diagnostics = _diagnose_dependence(
            np.asarray(baseline_fit["residuals"], dtype=float),
            candidate_graphs,
            area_ids=area_ids,
            y_direct=y,
            X=X,
            candidate_fit_summaries=fit_summary_payloads,
            params=params,
        )

        fit_candidates = list(single_fit_candidates)
        if hybrid_fit is not None and (mode == "hybrid" or allow_hybrid):
            fit_candidates.append(hybrid_fit)

        selection_candidates = [
            {
                "graph_id": "independent",
                "family": "INDEPENDENT",
                "criterion_value": _criterion_value(baseline_selected, criterion),
                "criterion_improvement": 0.0,
                "identifiable": True,
                "boundary_hit": False,
                "selected_model": "independent",
            }
        ]
        for fit in fit_candidates:
            selection_candidates.append(
                {
                    "graph_id": fit["graph_id"],
                    "family": fit["family"],
                    "criterion_value": _criterion_value(fit, criterion),
                    "criterion_improvement": _criterion_improvement(
                        baseline_selected, fit, criterion
                    ),
                    "identifiable": bool(fit.get("identifiable", False)),
                    "boundary_hit": bool(fit.get("boundary_hit", False)),
                    "selected_model": "hybrid" if fit["family"] == "HYBRID" else "graph",
                }
            )

        criterion_threshold = _criterion_threshold(criterion)
        best_overall = (
            min(fit_candidates, key=lambda item: _criterion_value(item, criterion))
            if fit_candidates
            else None
        )
        identifiable_candidates = [
            fit for fit in fit_candidates if bool(fit.get("identifiable", False))
        ]
        best_identifiable = (
            min(identifiable_candidates, key=lambda item: _criterion_value(item, criterion))
            if identifiable_candidates
            else None
        )
        close_candidates = []
        if best_identifiable is not None:
            best_value = _criterion_value(best_identifiable, criterion)
            close_candidates = [
                fit
                for fit in identifiable_candidates
                if abs(_criterion_value(fit, criterion) - best_value) <= criterion_threshold
            ]
        conflicting_candidates = len({fit["graph_id"] for fit in close_candidates}) > 1

        candidate_to_publish = best_identifiable
        if mode == "hybrid":
            if hybrid_fit is not None and bool(hybrid_fit.get("identifiable", False)):
                candidate_to_publish = hybrid_fit
            elif best_identifiable is not None:
                candidate_to_publish = best_identifiable
                selection_note = "hybrid_collapsed_to_single_kernel"

        if mode != "independent" and candidate_to_publish is not None:
            improvement = _criterion_improvement(baseline_selected, candidate_to_publish, criterion)
            diagnostic_gate = True
            if selection_rule == "diagnostic_plus_reml" and mode == "auto":
                diagnostic_gate = bool(
                    diagnostics.get("decision") == "identified"
                ) or improvement > (2.0 * criterion_threshold)
                if (
                    diagnostic_gate
                    and diagnostics.get("selected_graph_id") is not None
                    and candidate_to_publish["family"] != "HYBRID"
                    and diagnostics.get("selected_graph_id") != candidate_to_publish["graph_id"]
                    and improvement <= (2.0 * criterion_threshold)
                ):
                    diagnostic_gate = False
                    fallback_reason = "diagnostic_selected_different_graph"

            if not bool(candidate_to_publish.get("identifiable", False)):
                fallback_reason = fallback_reason or "graph_parameters_not_identifiable"
            elif bool(candidate_to_publish.get("boundary_hit", False)):
                fallback_reason = "dependence_parameter_on_boundary"
            elif (
                candidate_to_publish["family"] != "HYBRID"
                and bool(candidate_to_publish.get("rho_interval_contains_zero"))
                and improvement <= (2.0 * criterion_threshold)
            ):
                fallback_reason = "rho_interval_includes_zero"
            elif conflicting_candidates and improvement <= (2.0 * criterion_threshold):
                fallback_reason = "conflicting_candidate_graphs"
            elif not diagnostic_gate:
                fallback_reason = (
                    fallback_reason
                    or diagnostics.get("fallback_reason")
                    or "diagnostic_rejected_graph_dependence"
                )
            elif improvement <= criterion_threshold:
                fallback_reason = f"graph_model_did_not_improve_{criterion}"
            else:
                selected_fit = {
                    **candidate_to_publish,
                    "selected_model": "hybrid"
                    if candidate_to_publish["family"] == "HYBRID"
                    else "graph",
                    "selected_graph_id": candidate_to_publish["graph_id"],
                    "fallback_reason": None,
                }
                fallback_reason = None
                if selected_fit["selected_model"] == "graph":
                    selected_graph = next(
                        (
                            graph
                            for graph in candidate_graphs
                            if graph.graph_id == selected_fit["graph_id"]
                        ),
                        None,
                    )
                elif hybrid_pair is not None:
                    selected_hybrid_graphs = hybrid_pair
        elif mode != "independent" and best_overall is None:
            fallback_reason = (
                fallback_reason or diagnostics.get("fallback_reason") or "graph_model_not_estimable"
            )

        quality_certificate: dict[str, Any] = {
            "coverage_benchmark_id": "runtime_benchmark_not_executed",
            "coverage_passed": False,
        }
        if coverage_benchmark_reps > 0 and candidate_graphs:
            benchmark_seed = int(params.get("__seed__", 0)) + 7919
            benchmark_rng = np.random.default_rng(benchmark_seed)
            benchmark_mean = X @ np.asarray(baseline_fit["beta"], dtype=float)
            base_a = float(max(baseline_fit["A_hat"], 1e-3))
            if selected_fit["selected_model"] in {"graph", "hybrid"}:
                strong_cov = np.asarray(selected_fit["G"], dtype=float)
            else:
                primary_graph = candidate_graphs[0]
                strong_cov = base_a * _sar_covariance(
                    _row_standardize_weights(primary_graph.W), 0.75
                )
            strong_cov = 0.5 * (strong_cov + strong_cov.T) + 1e-10 * np.eye(y.shape[0])
            weak_cov = 0.35 * strong_cov + 0.65 * base_a * np.eye(y.shape[0])
            perm = benchmark_rng.permutation(y.shape[0])
            mismatch_graph = candidate_graphs[0].model_copy(
                update={"W": candidate_graphs[0].W[np.ix_(perm, perm)]}
            )
            mismatch_cov = base_a * _sar_covariance(
                _row_standardize_weights(mismatch_graph.W), 0.75
            )
            mismatch_cov = 0.5 * (mismatch_cov + mismatch_cov.T) + 1e-10 * np.eye(y.shape[0])
            scenarios = {
                "independent": base_a * np.eye(y.shape[0]),
                "weak_dependence": weak_cov,
                "strong_dependence": strong_cov,
                "graph_mismatch": mismatch_cov,
            }
            benchmark_params = dict(params)
            benchmark_params.update(
                {
                    "mode": "auto",
                    "bootstrap_reps": coverage_bootstrap_reps,
                    "coverage_benchmark_reps": 0,
                    "coverage_bootstrap_reps": 0,
                }
            )
            scenario_results: dict[str, Any] = {}
            for scenario_name, covariance in scenarios.items():
                coverage_rows: list[np.ndarray] = []
                rmse_values: list[float] = []
                baseline_rmse_values: list[float] = []
                interval_lengths: list[float] = []
                independent_count = 0
                for _ in range(coverage_benchmark_reps):
                    theta_truth = benchmark_rng.multivariate_normal(
                        mean=benchmark_mean,
                        cov=0.5 * (covariance + covariance.T) + 1e-10 * np.eye(y.shape[0]),
                    )
                    y_direct = theta_truth + np.sqrt(D) * benchmark_rng.normal(size=y.shape[0])
                    benchmark_result = FayHerriotDependenceAwareEstimator.pure_step(
                        {
                            "y_direct": y_direct,
                            "X": X,
                            "sampling_var": D,
                            "candidate_graphs": state.get("candidate_graphs", ()),
                            "area_ids": state.get("area_ids", ()),
                        },
                        benchmark_params,
                    )["result"]
                    benchmark_stats = benchmark_result.statistics
                    independent_count += int(benchmark_stats["selected_model"] == "independent")
                    estimates = np.asarray(benchmark_stats["estimates"], dtype=float)
                    baseline_estimates = np.asarray(
                        benchmark_stats["baseline_independent"]["estimates"],
                        dtype=float,
                    )
                    intervals = np.asarray(
                        benchmark_stats["uncertainty"]["interval_95"], dtype=float
                    )
                    coverage_rows.append(
                        (intervals[:, 0] <= theta_truth) & (theta_truth <= intervals[:, 1])
                    )
                    rmse_values.append(float(np.sqrt(np.mean((estimates - theta_truth) ** 2))))
                    baseline_rmse_values.append(
                        float(np.sqrt(np.mean((baseline_estimates - theta_truth) ** 2)))
                    )
                    interval_lengths.append(float(np.mean(intervals[:, 1] - intervals[:, 0])))
                coverage_matrix = (
                    np.vstack(coverage_rows)
                    if coverage_rows
                    else np.zeros((0, y.shape[0]), dtype=bool)
                )
                area_coverage = (
                    coverage_matrix.mean(axis=0)
                    if coverage_rows
                    else np.zeros((y.shape[0],), dtype=float)
                )
                scenario_results[scenario_name] = {
                    "n_runs": coverage_benchmark_reps,
                    "independent_selection_rate": float(
                        independent_count / max(coverage_benchmark_reps, 1)
                    ),
                    "coverage_mean": float(np.mean(area_coverage)) if coverage_rows else 0.0,
                    "coverage_lower_quartile": float(np.quantile(area_coverage, 0.25))
                    if coverage_rows
                    else 0.0,
                    "mean_interval_length": float(np.mean(interval_lengths))
                    if interval_lengths
                    else 0.0,
                    "rmse": float(np.mean(rmse_values)) if rmse_values else float("inf"),
                    "baseline_rmse": float(np.mean(baseline_rmse_values))
                    if baseline_rmse_values
                    else float("inf"),
                    "rmse_improvement": (
                        float(np.mean(baseline_rmse_values) - np.mean(rmse_values))
                        if rmse_values and baseline_rmse_values
                        else 0.0
                    ),
                }

            independent_ok = scenario_results["independent"]["independent_selection_rate"] >= 0.90
            mismatch_ok = scenario_results["graph_mismatch"]["independent_selection_rate"] >= 0.90
            strong_coverage_ok = (
                0.92 <= scenario_results["strong_dependence"]["coverage_mean"] <= 0.98
                and scenario_results["strong_dependence"]["coverage_lower_quartile"] >= 0.90
            )
            strong_rmse_ok = scenario_results["strong_dependence"]["rmse_improvement"] >= 0.0
            coverage_passed = bool(
                independent_ok and mismatch_ok and strong_coverage_ok and strong_rmse_ok
            )
            quality_certificate = {
                "coverage_benchmark_id": f"fh_dependence_benchmark_r{coverage_benchmark_reps}",
                "coverage_passed": coverage_passed,
                "summary": scenario_results,
            }
            if selected_fit["selected_model"] in {"graph", "hybrid"} and not coverage_passed:
                selected_fit = dict(baseline_selected)
                selected_graph = None
                selected_hybrid_graphs = None
                fallback_reason = "coverage_benchmark_failed"

        if selected_fit["selected_model"] == "independent" and fallback_reason is None:
            if mode == "independent":
                fallback_reason = "independent_mode_requested"
            else:
                fallback_reason = diagnostics.get("fallback_reason") or "fallback_to_independent"

        uncertainty_method = "analytic"
        if bootstrap_reps > 0:
            mse, interval_95 = _bootstrap_uncertainty(
                y,
                X,
                D,
                selected_fit,
                bootstrap_reps=bootstrap_reps,
                max_iter=max_iter,
                rho_grid_size=rho_grid_size,
                tau2_grid_size=tau2_grid_size,
                graph=selected_graph if selected_fit["selected_model"] == "graph" else None,
                hybrid_graphs=selected_hybrid_graphs
                if selected_fit["selected_model"] == "hybrid"
                else None,
                seed=int(params.get("__seed__", 0)),
            )
            uncertainty_method = "parametric_bootstrap"
        else:
            mse = np.asarray(selected_fit["mse"], dtype=float)
            interval_95 = _analytic_intervals(np.asarray(selected_fit["theta"], dtype=float), mse)

        diagnostics.update(
            {
                "decision": "identified"
                if selected_fit["selected_model"] in {"graph", "hybrid"}
                else diagnostics.get("decision"),
                "identifiable": bool(selected_fit.get("identifiable", True)),
                "fallback_reason": fallback_reason,
                "selected_graph_id": selected_fit.get("selected_graph_id"),
                "profile_curvature": selected_fit.get("profile_curvature"),
                "information_eigen_min": selected_fit.get("information_eigen_min"),
                "information_condition_number": selected_fit.get("information_condition_number"),
                "rho_confidence_interval": selected_fit.get("rho_confidence_interval"),
                "rho_interval_contains_zero": selected_fit.get("rho_interval_contains_zero"),
            }
        )
        artifact_store = resolve_artifact_store(
            state if isinstance(state, Mapping) else None, params
        )
        dependence_structure = dependence_structure_from_graph_diagnostic(
            diagnostics,
            regime="areal",
            source_method="survey.estimation.fay_herriot_dependence_aware",
        )
        dependence_ref = (
            persist_dependence_structure(artifact_store, dependence_structure)
            if artifact_store is not None
            else None
        )
        quality_certificate_ref = _persist_sae_quality_certificate(
            artifact_store,
            quality_certificate,
        )
        statistics = {
            "selected_model": selected_fit["selected_model"],
            "selection_rule": selection_rule,
            "criterion": criterion,
            "estimates": np.asarray(selected_fit["theta"], dtype=float).tolist(),
            "beta": np.asarray(selected_fit["beta"], dtype=float).tolist(),
            "variance_components": {
                "tau2": float(selected_fit["tau2"]),
                "rho": float(selected_fit["rho"]) if selected_fit.get("rho") is not None else None,
                "selected_graph_id": selected_fit.get("selected_graph_id"),
                "mix_weight": (
                    float(selected_fit["mix_weight"])
                    if selected_fit.get("mix_weight") is not None
                    else None
                ),
                "kernel_components": [
                    dict(item) for item in selected_fit.get("kernel_components", ())
                ],
            },
            "diagnostics": {
                "moran_i": diagnostics.get("moran_i"),
                "geary_c": diagnostics.get("geary_c"),
                "moran_p_value": diagnostics.get("moran_p_value"),
                "geary_p_value": diagnostics.get("geary_p_value"),
                "pesaran_cd": diagnostics.get("pesaran_cd"),
                "pesaran_cd_p_value": diagnostics.get("pesaran_cd_p_value"),
                "lm_error": diagnostics.get("lm_error"),
                "lm_error_p_value": diagnostics.get("lm_error_p_value"),
                "lm_lag": diagnostics.get("lm_lag"),
                "lm_lag_p_value": diagnostics.get("lm_lag_p_value"),
                "decision": diagnostics.get("decision"),
                "strength": diagnostics.get("strength"),
                "identifiable": bool(diagnostics.get("identifiable")),
                "fallback_reason": fallback_reason,
                "class_label": diagnostics.get("class_label"),
                "estimator_status": diagnostics.get("estimator_status"),
                "profile_curvature": diagnostics.get("profile_curvature"),
                "information_eigen_min": diagnostics.get("information_eigen_min"),
                "information_condition_number": diagnostics.get("information_condition_number"),
                "rho_confidence_interval": diagnostics.get("rho_confidence_interval"),
                "rho_interval_contains_zero": diagnostics.get("rho_interval_contains_zero"),
                "selection_note": selection_note,
                "selection_candidates": selection_candidates,
                "graph_diagnostics": [
                    item.model_dump(mode="python") if hasattr(item, "model_dump") else item
                    for item in diagnostics.get("graph_diagnostics", ())
                ],
            },
            "uncertainty": {
                "mse": np.asarray(mse, dtype=float).tolist(),
                "interval_95": interval_95,
                "method": uncertainty_method,
            },
            "baseline_independent": {
                "estimates": np.asarray(baseline_fit["theta"], dtype=float).tolist(),
                "mse": np.asarray(baseline_fit["mse"], dtype=float).tolist(),
            },
            "quality_certificate": quality_certificate,
        }

        return {
            "result": SAEResult(
                method_name="survey.estimation.fay_herriot_dependence_aware",
                statistics=statistics,
                dependence_ref=dependence_ref,
                quality_certificate_ref=quality_certificate_ref,
                metadata={
                    "selected_model": selected_fit["selected_model"],
                    "quality_certificate": quality_certificate,
                    "diagnostics": statistics["diagnostics"],
                },
            )
        }


@foundry_method(
    namespace="survey.estimation",
    version="1.0.0",
    tags={"survey", "calibration", "greg"},
)
class CalibrationGREGEstimator:
    """Estimate calibrated totals with generalized regression weighting."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="calibration_greg",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("y", SlotType.VECTOR, Unit("outcome", "value"), shape=("n_obs",)),
                SlotSpec(
                    "X", SlotType.MATRIX, Unit("auxiliary", "value"), shape=("n_obs", "n_aux")
                ),
                SlotSpec("weights", SlotType.VECTOR, Unit("weight", "value"), shape=("n_obs",)),
                SlotSpec(
                    "population_totals", SlotType.VECTOR, Unit("total", "value"), shape=("n_aux",)
                ),
                SlotSpec("q_weights", SlotType.VECTOR, Unit("weight", "value"), shape=("n_obs",)),
                SlotSpec(
                    "sample_aux_error_cov",
                    SlotType.MATRIX,
                    Unit("variance", "value"),
                    shape=("n_aux", "n_aux"),
                ),
                SlotSpec(
                    "auxiliary_total_uncertainty",
                    SlotType.SCALAR,
                    Unit("uncertainty", "json"),
                    contract_id=AUXILIARY_TOTAL_UNCERTAINTY_TARGET.contract_id,
                ),
            }
        ),
        output_slots=_greg_output_slots(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Generalized Regression (GREG) calibration estimator for survey totals with optional relaxed calibration under noisy control totals.",
        tags=frozenset({"survey", "calibration", "greg", "regression-estimator"}),
        citations=(
            "Särndal, C.E. et al. (1992). Model Assisted Survey Sampling. Springer.",
            "Deville, J.-C. & Särndal, C.-E. (1992). Calibration estimators in survey sampling. JASA.",
        ),
        equations={
            "greg": "t_GREG = t_HT(y) + (T_X - t_HT(X))' * B_w",
            "relaxed_greg": "t_relaxed = t_HT(y) + (T_X - t_HT(X))' * (X' D_q X + Omega)^(-1) X' D_q y",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Estimate population totals/means from complex sample; use relaxed mode when control totals are estimated or benchmarked with uncertainty.",
        output_interpretation="When auxiliary totals are exact the estimator reduces to classical GREG; when uncertainty is provided, calibration is softened and the variance estimate includes an auxiliary-total uncertainty add-on.",
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any], fallback_state: Any
    ) -> Mapping[str, Any]:
        return _materialize_greg_state(bound_inputs, fallback_state)

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        y = _vector_from_state(state, "y", "y_sample")
        X = _matrix_from_state(state, "X", "x_sample")
        design_weights = _vector_from_state(state, "weights", "design_weights")
        population_totals = _vector_from_state(state, "population_totals", "known_totals")
        n_obs, n_aux = X.shape

        if y.shape[0] != n_obs:
            raise ValueError("y length must match X rows")
        if design_weights.shape[0] != n_obs:
            raise ValueError("weights length must match X rows")
        if population_totals.shape[0] != n_aux:
            raise ValueError("population_totals length must match X columns")
        if np.any(design_weights <= 0.0):
            raise ValueError("weights must be strictly positive")

        bounds = _optional_bounds(state, params)
        q_weights = _optional_q_weights(state, params, n_obs)
        sample_aux_error_cov = _optional_sample_aux_error_cov(state, params, n_aux)
        auxiliary_total_uncertainty, omega = _covariance_from_state(
            state,
            n_aux=n_aux,
            totals=population_totals,
        )

        weighted_q = design_weights * q_weights
        t_ht_y = float(np.sum(design_weights * y))
        t_ht_x = np.sum(design_weights[:, None] * X, axis=0)
        delta = population_totals - t_ht_x

        gram = X.T @ (weighted_q[:, None] * X)
        if sample_aux_error_cov is not None:
            gram = 0.5 * ((gram - sample_aux_error_cov) + (gram - sample_aux_error_cov).T)
        rhs = np.column_stack([delta, X.T @ (weighted_q * y)])
        system = gram + omega
        solution, system_used, solver_status, condition_number, ridge_added = _solve_system(
            system, rhs
        )
        lambda_ = solution[:, 0]
        beta = solution[:, 1]

        calibrated_weights = design_weights + weighted_q * (X @ lambda_)
        achieved_totals = X.T @ calibrated_weights
        control_residual = population_totals - achieved_totals
        greg_total = t_ht_y + float(delta @ beta)

        residual = y - X @ beta
        sampling_variance = float(np.sum((design_weights * residual) ** 2))
        aux_uncertainty_variance = float(beta.T @ omega @ beta)
        variance_estimate = sampling_variance + aux_uncertainty_variance

        constraint_mode = "exact" if np.allclose(omega, 0.0, atol=1e-10) else "relaxed"
        shrinkage = (
            np.diag(gram @ np.linalg.pinv(system_used)) if n_aux else np.zeros((0,), dtype=float)
        )
        diagnostics = {
            "n_obs": int(n_obs),
            "n_aux": int(n_aux),
            "gram_condition_number": _condition_number(gram),
            "system_condition_number": condition_number,
            "ridge_added": float(ridge_added),
            "weight_shift_l2": float(np.linalg.norm(calibrated_weights - design_weights)),
            "control_residual_l2": float(np.linalg.norm(control_residual)),
            "shrinkage_factors": np.clip(shrinkage, 0.0, None).tolist(),
            "used_q_weights": bool(not np.allclose(q_weights, 1.0, atol=1e-10)),
            "used_sample_aux_error_cov": bool(sample_aux_error_cov is not None),
            "bounds_supplied": bool(bounds is not None),
            "bounds_enforced": False,
            "uncertainty_source_kind": (
                auxiliary_total_uncertainty.source_kind
                if auxiliary_total_uncertainty is not None
                else "exact"
            ),
            "uncertainty_used_replicates": bool(
                auxiliary_total_uncertainty is not None
                and auxiliary_total_uncertainty.replicate_totals is not None
            ),
        }

        calibration_weights = CalibrationWeights(
            calibrated_weights=calibrated_weights,
            lambda_=lambda_,
            achieved_totals=achieved_totals,
            control_residual=control_residual,
            uncertainty_covariance_used=omega,
            constraint_mode=constraint_mode,
            solver_status=solver_status,
            design_weights=design_weights,
            x_sample=X,
            known_totals=population_totals,
            q_weights=q_weights,
            auxiliary_total_uncertainty=auxiliary_total_uncertainty,
            bounds=bounds,
            sample_aux_error_cov=sample_aux_error_cov,
            diagnostics=diagnostics,
        )
        return {
            "result": {
                "estimator": "greg" if constraint_mode == "exact" else "greg_downweighted",
                "greg_total": greg_total,
                "population_total": greg_total,
                "ht_total": t_ht_y,
                "regression_coefficients": beta.tolist(),
                "beta": beta.tolist(),
                "lambda": lambda_.tolist(),
                "variance_estimate": variance_estimate,
                "variance_components": {
                    "sampling": sampling_variance,
                    "aux_total_uncertainty": aux_uncertainty_variance,
                },
                "calibrated_weights": calibrated_weights.tolist(),
                "calibration_weights_mean": float(np.mean(calibrated_weights)),
                "achieved_totals": achieved_totals.tolist(),
                "control_residual": control_residual.tolist(),
                "uncertainty_covariance_used": omega.tolist(),
                "constraint_mode": constraint_mode,
                "solver_status": solver_status,
                "uncertainty_source_kind": diagnostics["uncertainty_source_kind"],
                "diagnostics": diagnostics,
                "n_obs": int(n_obs),
            },
            "calibration_weights": calibration_weights,
        }


__all__ = [
    "CalibrationGREGEstimator",
    "FayHerriotDependenceAwareEstimator",
    "FayHerriotEstimator",
]
