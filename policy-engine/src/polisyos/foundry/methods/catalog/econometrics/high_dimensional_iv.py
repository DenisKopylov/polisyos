"""High-dimensional IV inference with post-selection tiering and weak-IV fallback."""
from __future__ import annotations

from statistics import NormalDist
from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
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

from .high_dimensional import _lasso_cd
from .iv import (
    _call_conf_int,
    _extract_confidence_intervals,
    _iv_input_slots,
    _iv_output_slots,
    _materialize_iv_data,
    _safe_float,
)
from .protocols import (
    ConfidenceSetSegment,
    EconometricResult,
    IdentificationDiagnostic,
    IntervalDisagreementDiagnostic,
    OrthogonalityNuisanceDiagnostic,
    PanelData,
    PostSelectionCoverageDiagnostic,
    PostSelectionInterval,
    SparsityComplexityDiagnostic,
)


def _candidate_names(provided: list[str] | None, *, count: int, prefix: str) -> list[str]:
    if provided is not None and len(provided) == count:
        return [str(name) for name in provided]
    return [f"{prefix}{idx}" for idx in range(count)]


def _design_with_constant(matrix: np.ndarray) -> np.ndarray:
    if matrix.ndim != 2:
        raise ValueError("matrix must be 2D")
    return np.column_stack([np.ones(matrix.shape[0]), matrix])


def _fit_lasso_predict_support(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_eval: np.ndarray,
    *,
    lambda_factor: float,
    max_iter: int,
) -> tuple[np.ndarray, set[int]]:
    if X_train.shape[1] == 0:
        mean_value = float(np.mean(y_train)) if y_train.size else 0.0
        return np.full(X_eval.shape[0], mean_value, dtype=float), set()

    if np.std(y_train) <= 1e-12:
        mean_value = float(np.mean(y_train))
        return np.full(X_eval.shape[0], mean_value, dtype=float), set()

    X_mean = np.mean(X_train, axis=0)
    X_std = np.std(X_train, axis=0)
    X_std = np.where(X_std > 0.0, X_std, 1.0)
    X_train_std = (X_train - X_mean) / X_std
    X_eval_std = (X_eval - X_mean) / X_std

    y_mean = float(np.mean(y_train))
    y_centered = y_train - y_mean
    sigma_hat = max(float(np.std(y_centered)), 1e-6)
    lam = float(lambda_factor) * sigma_hat * np.sqrt(2.0 * np.log(max(X_train.shape[1], 2)) / X_train.shape[0])
    coef = _lasso_cd(X_train_std, y_centered, lam, max_iter=max_iter)
    predictions = y_mean + X_eval_std @ coef
    support = set(np.flatnonzero(np.abs(coef) > 1e-8).tolist())
    return predictions, support


def _iter_kfold_indices(n_obs: int, n_folds: int, *, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(n_obs)
    fold_slices = np.array_split(shuffled, n_folds)
    output: list[tuple[np.ndarray, np.ndarray]] = []
    for fold in fold_slices:
        test_idx = np.sort(np.asarray(fold, dtype=int))
        train_mask = np.ones(n_obs, dtype=bool)
        train_mask[test_idx] = False
        train_idx = np.flatnonzero(train_mask)
        output.append((train_idx, test_idx))
    return output


def _average_jaccard(supports: list[set[int]]) -> float:
    if not supports:
        return 1.0
    if len(supports) == 1:
        return 1.0

    scores: list[float] = []
    for left_idx in range(len(supports)):
        for right_idx in range(left_idx + 1, len(supports)):
            left = supports[left_idx]
            right = supports[right_idx]
            union = left | right
            if not union:
                scores.append(1.0)
                continue
            scores.append(len(left & right) / len(union))
    return float(np.mean(scores)) if scores else 1.0


def _complexity_ratio(selected_count: int, feature_count: int, n_train: int) -> float:
    if selected_count <= 0 or feature_count <= 0 or n_train <= 0:
        return 0.0
    return float(selected_count * np.log(max(feature_count, n_train, 2)) / n_train)


def _robust_f_test(
    y: np.ndarray,
    controls: np.ndarray,
    instruments: np.ndarray,
) -> tuple[float | None, float | None]:
    if instruments.shape[1] == 0:
        return None, None

    import statsmodels.api as sm

    full = _design_with_constant(np.column_stack([controls, instruments]))
    fit = sm.OLS(y, full).fit(cov_type="HC1")

    restriction = np.zeros((instruments.shape[1], full.shape[1]), dtype=float)
    start = 1 + controls.shape[1]
    for row, col in enumerate(range(start, start + instruments.shape[1])):
        restriction[row, col] = 1.0

    test = fit.f_test(restriction)
    return _safe_float(np.asarray(test.fvalue).squeeze()), _safe_float(np.asarray(test.pvalue).squeeze())


def _conditional_weak_iv_stats(
    endog: np.ndarray,
    controls: np.ndarray,
    instruments: np.ndarray,
) -> tuple[list[float | None], list[float | None]]:
    if endog.ndim != 2:
        raise ValueError("endog must be 2D")
    if instruments.shape[1] == 0:
        return ([None] * endog.shape[1], [None] * endog.shape[1])

    stats: list[float | None] = []
    pvalues: list[float | None] = []
    for idx in range(endog.shape[1]):
        other_endog = np.delete(endog, idx, axis=1)
        conditioning = controls if other_endog.size == 0 else np.column_stack([controls, other_endog])
        stat, pvalue = _robust_f_test(endog[:, idx], conditioning, instruments)
        stats.append(stat)
        pvalues.append(pvalue)
    return stats, pvalues


def _extract_first_stage_weak_iv_diagnostics(
    fit_result: Any,
    *,
    endogenous_names: list[str],
) -> tuple[list[float | None], list[float | None], str] | None:
    first_stage = getattr(fit_result, "first_stage", None)
    diagnostics = getattr(first_stage, "diagnostics", None)
    if diagnostics is None:
        return None

    def _resolve_row(name: str) -> Any:
        if hasattr(diagnostics, "loc"):
            try:
                return diagnostics.loc[name]
            except Exception:
                pass
        if hasattr(diagnostics, "index") and len(getattr(diagnostics, "index")) == 1:
            if hasattr(diagnostics, "iloc"):
                return diagnostics.iloc[0]
        return None

    def _resolve_value(row: Any, *candidates: str) -> float | None:
        if row is None:
            return None
        for candidate in candidates:
            value = None
            if hasattr(row, "get"):
                value = row.get(candidate)
            elif isinstance(row, Mapping):
                value = row.get(candidate)
            if value is None and hasattr(row, "__getitem__"):
                try:
                    value = row[candidate]
                except Exception:
                    value = None
            resolved = _safe_float(value)
            if resolved is not None:
                return resolved
        return None

    stats: list[float | None] = []
    pvalues: list[float | None] = []
    for name in endogenous_names:
        row = _resolve_row(name)
        stats.append(_resolve_value(row, "f.stat", "f_stat", "partial_f", "partial.f"))
        pvalues.append(_resolve_value(row, "f.pval", "f_pval", "pval", "p.value"))
    if not any(stat is not None for stat in stats):
        return None
    return stats, pvalues, "linearmodels_first_stage"


def _selected_columns(matrix: np.ndarray, indices: list[int]) -> np.ndarray:
    if not indices:
        return np.empty((matrix.shape[0], 0), dtype=float)
    return np.asarray(matrix[:, indices], dtype=float)


def _ensure_min_instrument_count(
    selected_instruments: list[int],
    *,
    instruments: np.ndarray,
    endog: np.ndarray,
    minimum_count: int,
) -> list[int]:
    if len(selected_instruments) >= minimum_count:
        return selected_instruments

    correlations = np.zeros(instruments.shape[1], dtype=float)
    for idx in range(instruments.shape[1]):
        best = 0.0
        z_col = instruments[:, idx]
        for endog_idx in range(endog.shape[1]):
            corr = np.corrcoef(endog[:, endog_idx], z_col)[0, 1]
            if np.isfinite(corr):
                best = max(best, abs(float(corr)))
        correlations[idx] = best

    for candidate in np.argsort(correlations)[::-1]:
        candidate_idx = int(candidate)
        if candidate_idx not in selected_instruments:
            selected_instruments.append(candidate_idx)
        if len(selected_instruments) >= minimum_count:
            break
    return sorted(set(selected_instruments))


def _orthogonal_pliv_estimate(
    *,
    y: np.ndarray,
    endog: np.ndarray,
    y_hat: np.ndarray,
    d_hat_x: np.ndarray,
    d_hat_xz: np.ndarray,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray, float, float]:
    y_tilde = y - y_hat
    d_tilde = endog - d_hat_x
    v_hat = d_hat_xz - d_hat_x

    a_hat = (v_hat.T @ d_tilde) / y.shape[0]
    if np.linalg.matrix_rank(a_hat) < a_hat.shape[0]:
        score_values = np.full((y.shape[0], endog.shape[1]), np.nan, dtype=float)
        return None, None, score_values, float("inf"), float(np.linalg.cond(a_hat))

    cond_number = float(np.linalg.cond(a_hat))
    if not np.isfinite(cond_number) or cond_number > 1e8:
        score_values = np.full((y.shape[0], endog.shape[1]), np.nan, dtype=float)
        return None, None, score_values, float("inf"), cond_number

    theta_hat = np.linalg.solve(a_hat, (v_hat.T @ y_tilde) / y.shape[0])
    residual = y_tilde - d_tilde @ theta_hat
    score_values = v_hat * residual[:, None]

    score_std = np.std(score_values, axis=0, ddof=1)
    score_mean = np.mean(score_values, axis=0)
    score_z = np.divide(
        np.sqrt(y.shape[0]) * np.abs(score_mean),
        np.where(score_std > 1e-12, score_std, np.nan),
    )
    orthogonality_score = float(np.nanmax(score_z)) if np.any(np.isfinite(score_z)) else float("inf")

    psi_centered = score_values - np.mean(score_values, axis=0, keepdims=True)
    omega_hat = (psi_centered.T @ psi_centered) / y.shape[0]
    a_inv = np.linalg.inv(a_hat)
    vcov = a_inv @ omega_hat @ a_inv.T / y.shape[0]
    se = np.sqrt(np.clip(np.diag(vcov), a_min=0.0, a_max=None))
    return theta_hat, se, score_values, orthogonality_score, cond_number


def _fit_selected_2sls(
    *,
    y: np.ndarray,
    d: np.ndarray,
    controls: np.ndarray,
    instruments: np.ndarray,
    confidence_level: float,
    cov_type: str,
    endogenous_names: list[str],
    control_names: list[str],
    instrument_names: list[str],
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, float], dict[str, tuple[float, float]], Any]:
    import pandas as pd
    from linearmodels.iv import IV2SLS

    if d.ndim == 1:
        d = d[:, None]
    frame = pd.DataFrame({"const": np.ones(y.shape[0], dtype=float), "y": y})
    for idx, name in enumerate(endogenous_names):
        frame[name] = d[:, idx]
    exog_cols = ["const"]
    for idx, name in enumerate(control_names):
        frame[name] = controls[:, idx]
        exog_cols.append(name)
    for idx, name in enumerate(instrument_names):
        frame[name] = instruments[:, idx]

    fit_result = IV2SLS(
        frame["y"],
        frame[exog_cols],
        frame[endogenous_names],
        frame[instrument_names],
    ).fit(cov_type=cov_type)

    params = {str(name): float(fit_result.params[name]) for name in fit_result.params.index}
    std_errors = {str(name): float(fit_result.std_errors[name]) for name in fit_result.params.index}

    t_stats: dict[str, float] = {}
    p_values: dict[str, float] = {}
    for name in fit_result.params.index:
        string_name = str(name)
        t_value = _safe_float(getattr(fit_result, "tstats", {}).get(name))
        p_value = _safe_float(getattr(fit_result, "pvalues", {}).get(name))
        if t_value is not None:
            t_stats[string_name] = t_value
        if p_value is not None:
            p_values[string_name] = p_value

    conf_int_obj = _call_conf_int(fit_result, confidence_level=confidence_level)
    intervals = (
        _extract_confidence_intervals(conf_int_obj, param_names=[str(name) for name in fit_result.params.index])
        if conf_int_obj is not None
        else {}
    )

    return params, std_errors, t_stats, p_values, intervals, fit_result


def _segments_from_mask(grid: np.ndarray, accepted_mask: np.ndarray) -> tuple[ConfidenceSetSegment, ...]:
    if grid.size == 0 or not np.any(accepted_mask):
        return ()

    step = float(grid[1] - grid[0]) if grid.size > 1 else 0.0
    segments: list[ConfidenceSetSegment] = []
    start: int | None = None

    for idx, accepted in enumerate(accepted_mask):
        if accepted and start is None:
            start = idx
        last = idx == accepted_mask.size - 1
        if start is None:
            continue
        if last or not accepted_mask[idx + 1]:
            lower = float(grid[start])
            upper = float(grid[idx])
            if step > 0.0:
                if start > 0:
                    lower -= 0.5 * step
                if idx < accepted_mask.size - 1:
                    upper += 0.5 * step
            segments.append(ConfidenceSetSegment(lower=lower, upper=upper))
            start = None

    return tuple(segments)


def _anderson_rubin_interval(
    *,
    parameter: str,
    y: np.ndarray,
    d: np.ndarray,
    controls: np.ndarray,
    instruments: np.ndarray,
    point_estimate: float,
    se: float,
    confidence_level: float,
    grid_points: int,
    grid_scale: float,
) -> tuple[PostSelectionInterval | None, dict[str, Any]]:
    if instruments.shape[1] == 0:
        return None, {"reason": "no_selected_instruments"}

    import statsmodels.api as sm

    alpha = 1.0 - confidence_level
    scale = se if np.isfinite(se) and se > 1e-12 else float(np.std(y) / max(np.std(d), 1e-6))
    half_width = max(float(grid_scale) * max(scale, 1e-3), 1.0)

    accepted_mask = np.zeros(int(grid_points), dtype=bool)
    boundary_hit = False
    grid = np.linspace(point_estimate - half_width, point_estimate + half_width, int(grid_points))
    stats: list[float] = []

    for _ in range(3):
        for idx, beta in enumerate(grid):
            y_beta = y - beta * d
            fit = sm.OLS(y_beta, _design_with_constant(np.column_stack([controls, instruments]))).fit(
                cov_type="HC1"
            )
            restriction = np.zeros((instruments.shape[1], fit.model.exog.shape[1]), dtype=float)
            start = 1 + controls.shape[1]
            for row, col in enumerate(range(start, start + instruments.shape[1])):
                restriction[row, col] = 1.0
            test = fit.f_test(restriction)
            test_pvalue = _safe_float(np.asarray(test.pvalue).squeeze())
            test_stat = _safe_float(np.asarray(test.fvalue).squeeze())
            if test_stat is not None:
                stats.append(test_stat)
            accepted_mask[idx] = bool(test_pvalue is not None and test_pvalue >= alpha)

        boundary_hit = bool(accepted_mask[0] or accepted_mask[-1])
        if np.any(accepted_mask) and not boundary_hit:
            break
        half_width *= 2.0
        grid = np.linspace(point_estimate - half_width, point_estimate + half_width, int(grid_points))
        accepted_mask = np.zeros(int(grid_points), dtype=bool)

    if not np.any(accepted_mask):
        return None, {"reason": "no_nonrejected_grid_points", "boundary_hit": boundary_hit}

    segments = _segments_from_mask(grid, accepted_mask)
    interval = PostSelectionInterval(
        parameter=parameter,
        confidence_level=confidence_level,
        method_family="anderson_rubin_hc1",
        semantics="confidence_set",
        segments=segments,
        point_estimate=point_estimate,
        metadata={
            "grid_points": int(grid_points),
            "grid_half_width": float(half_width),
            "boundary_hit": boundary_hit,
            "mean_test_stat": float(np.mean(stats)) if stats else None,
        },
    )
    return interval, {"boundary_hit": boundary_hit}


def _build_interval(
    *,
    parameter: str,
    confidence_level: float,
    lower: float,
    upper: float,
    point_estimate: float,
    method_family: str,
    semantics: str = "confidence_interval",
    metadata: dict[str, Any] | None = None,
) -> PostSelectionInterval:
    return PostSelectionInterval(
        parameter=parameter,
        confidence_level=confidence_level,
        method_family=method_family,
        semantics=semantics,
        segments=(ConfidenceSetSegment(lower=min(lower, upper), upper=max(lower, upper)),),
        point_estimate=point_estimate,
        metadata=metadata or {},
    )


def _interval_width(interval: PostSelectionInterval | None) -> float | None:
    if interval is None:
        return None
    hull = interval.convex_hull()
    if hull is None:
        return None
    return float(hull[1] - hull[0])


@foundry_method(
    namespace="econometrics.iv",
    version="1.0.0",
    tags={
        "econometrics",
        "instrumental-variables",
        "high-dimensional",
        "post-selection",
        "double-machine-learning",
        "weak-iv",
    },
)
class HighDimensionalPostSelectionIVEstimator:
    """High-dimensional IV contour with coverage tiering and weak-IV fallback."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "statsmodels", "linearmodels", "pandas")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="high_dimensional_post_selection",
        namespace="",
        version="0.0.0",
        input_slots=_iv_input_slots(),
        output_slots=_iv_output_slots(),
        parameters=(
            ParameterSpec(name="n_endogenous", default=1),
            ParameterSpec(name="inference_route", default="orthogonal"),
            ParameterSpec(name="n_folds", default=3),
            ParameterSpec(name="lambda_factor", default=1.0),
            ParameterSpec(name="max_iter", default=300),
            ParameterSpec(name="confidence_level", default=0.95),
            ParameterSpec(name="cov_type", default="robust"),
            ParameterSpec(name="weak_iv_threshold", default=10.0),
            ParameterSpec(name="complexity_gate_max", default=0.25),
            ParameterSpec(name="product_rate_gate_max", default=0.05),
            ParameterSpec(name="support_stability_min", default=0.4),
            ParameterSpec(name="orthogonality_score_max", default=2.5),
            ParameterSpec(name="ar_grid_points", default=201),
            ParameterSpec(name="ar_grid_scale", default=8.0),
            ParameterSpec(name="weak_set_max_width_ratio", default=25.0),
            ParameterSpec(name="compute_weak_iv_always", default=False),
            ParameterSpec(name="envelope_param", default=None),
            ParameterSpec(name="seed", default=42),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "High-dimensional IV workflow that combines sparse post-selection, "
            "cross-fitted orthogonal scores, and weak-IV robust Anderson-Rubin fallback."
        ),
        tags=frozenset(
            {
                "econometrics",
                "iv",
                "high-dimensional",
                "post-selection",
                "weak-iv",
                "dml",
            }
        ),
        citations=(
            "Belloni, A., Chernozhukov, V. & Hansen, C. (2012). Sparse Models and Methods for Optimal Instruments.",
            "Chernozhukov, V. et al. (2018). Double/Debiased Machine Learning for Treatment and Structural Parameters.",
            "Anderson, T. & Rubin, H. (1949). Estimation of the Parameters of a Single Equation in a Complete System of Stochastic Equations.",
        ),
        equations={
            "orthogonal_score": "E[(m(X,Z)-r(X)) * (Y-l(X)-theta*(D-r(X)))] = 0",
            "complexity_gate": "s_x log(max(p_x,n))/n and s_z log(max(p_z,n))/n must remain small",
            "ar_inversion": "Invert non-rejection region of the Anderson-Rubin test over theta",
        },
        assumptions={
            "approximate_sparsity": "Outcome, treatment, and first-stage nuisance functions admit sparse approximations.",
            "orthogonality": "Inference tier requires Neyman-orthogonal score plus cross-fitting.",
            "identification": "Weak-IV pass is required for orthogonal Wald coverage; otherwise use weak-IV robust set.",
        },
        when_to_use=(
            "High-dimensional controls/instruments with one policy target and a need to distinguish "
            "heuristic post-selection from orthogonal cross-fit and weak-IV robust inference."
        ),
        when_not_to_use=(
            "Settings where sparse nuisance structure is not plausible, or cases requiring exact "
            "Montiel Olea-Pflueger / CLR many-weak coverage rather than the implemented proxy diagnostics."
        ),
        typical_min_obs=200,
        output_interpretation=(
            "coverage_guarantee_tier reports whether the returned interval is heuristic, "
            "orthogonal cross-fit, or weak-IV robust."
        ),
    )

    @staticmethod
    def pure_step(state: PanelData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, PanelData) else PanelData.model_validate(state)
        if data.instrument_ids is None:
            raise ValueError("high_dimensional_post_selection requires instrument_ids")

        n_endogenous = int(params.get("n_endogenous", 1))
        if n_endogenous <= 0 or n_endogenous >= data.exog.shape[1]:
            raise ValueError("n_endogenous must be in range [1, n_exog - 1]")
        n_obs = data.n_obs
        n_folds = max(2, int(params.get("n_folds", 3)))
        if n_folds >= n_obs:
            raise ValueError("n_folds must be smaller than the number of observations")

        confidence_level = float(params.get("confidence_level", 0.95))
        cov_type = str(params.get("cov_type", "robust"))
        seed = int(params.get("seed", 42))
        inference_route = str(params.get("inference_route", "orthogonal")).strip().lower()
        if inference_route not in {"orthogonal", "heuristic"}:
            raise ValueError("inference_route must be one of {'orthogonal', 'heuristic'}")
        lambda_factor = float(params.get("lambda_factor", 1.0))
        max_iter = int(params.get("max_iter", 300))

        complexity_gate_max = float(params.get("complexity_gate_max", 0.25))
        product_rate_gate_max = float(params.get("product_rate_gate_max", 0.05))
        support_stability_min = float(params.get("support_stability_min", 0.4))
        orthogonality_score_max = float(params.get("orthogonality_score_max", 2.5))
        weak_iv_threshold = float(params.get("weak_iv_threshold", 10.0))
        ar_grid_points = int(params.get("ar_grid_points", 201))
        ar_grid_scale = float(params.get("ar_grid_scale", 8.0))
        compute_weak_iv_always = bool(params.get("compute_weak_iv_always", False))
        weak_set_max_width_ratio = float(params.get("weak_set_max_width_ratio", 25.0))

        y = np.asarray(data.dependent, dtype=float)
        endog = np.asarray(data.exog[:, :n_endogenous], dtype=float)
        if endog.ndim == 1:
            endog = endog[:, None]
        controls = np.asarray(data.exog[:, n_endogenous:], dtype=float)
        instruments = np.asarray(data.instrument_ids, dtype=float)

        endogenous_names = _candidate_names(
            data.feature_names[:n_endogenous] if data.feature_names else None,
            count=n_endogenous,
            prefix="x_endog",
        )
        control_names = _candidate_names(
            data.feature_names[n_endogenous:] if data.feature_names else None,
            count=controls.shape[1],
            prefix="x",
        )
        instrument_names = _candidate_names(data.instrument_names, count=instruments.shape[1], prefix="z")
        primary_param = str(params.get("envelope_param") or endogenous_names[0])
        if primary_param not in endogenous_names:
            primary_param = endogenous_names[0]

        y_hat = np.zeros(n_obs, dtype=float)
        d_hat_x = np.zeros((n_obs, n_endogenous), dtype=float)
        d_hat_xz = np.zeros((n_obs, n_endogenous), dtype=float)
        control_supports: list[set[int]] = []
        instrument_supports: list[set[int]] = []
        selected_controls_union: set[int] = set()
        selected_instruments_union: set[int] = set()
        rmse_y_terms: list[float] = []
        rmse_d_terms: list[float] = []
        rmse_z_terms: list[float] = []

        splitter = _iter_kfold_indices(n_obs, n_folds, seed=seed)
        for train_idx, test_idx in splitter:
            X_train = controls[train_idx]
            X_test = controls[test_idx]
            Z_train = instruments[train_idx]
            Z_test = instruments[test_idx]
            d_train = endog[train_idx]
            y_train = y[train_idx]

            pred_y, support_y = _fit_lasso_predict_support(
                X_train,
                y_train,
                X_test,
                lambda_factor=lambda_factor,
                max_iter=max_iter,
            )
            pred_d_x = np.zeros((test_idx.size, n_endogenous), dtype=float)
            pred_d_xz = np.zeros((test_idx.size, n_endogenous), dtype=float)
            fold_control_support = set(support_y)
            fold_instrument_support: set[int] = set()
            for endog_idx in range(n_endogenous):
                pred_d_x_j, support_d_x_j = _fit_lasso_predict_support(
                    X_train,
                    d_train[:, endog_idx],
                    X_test,
                    lambda_factor=lambda_factor,
                    max_iter=max_iter,
                )
                pred_d_xz_j, support_d_xz_j = _fit_lasso_predict_support(
                    np.column_stack([X_train, Z_train]),
                    d_train[:, endog_idx],
                    np.column_stack([X_test, Z_test]),
                    lambda_factor=lambda_factor,
                    max_iter=max_iter,
                )
                pred_d_x[:, endog_idx] = pred_d_x_j
                pred_d_xz[:, endog_idx] = pred_d_xz_j
                fold_control_support |= set(support_d_x_j)
                fold_control_support |= {idx for idx in support_d_xz_j if idx < controls.shape[1]}
                fold_instrument_support |= {
                    idx - controls.shape[1] for idx in support_d_xz_j if idx >= controls.shape[1]
                }

            control_supports.append(fold_control_support)
            instrument_supports.append(fold_instrument_support)
            selected_controls_union |= fold_control_support
            selected_instruments_union |= fold_instrument_support

            y_hat[test_idx] = pred_y
            d_hat_x[test_idx, :] = pred_d_x
            d_hat_xz[test_idx, :] = pred_d_xz

            rmse_y_terms.append(float(np.mean((y[test_idx] - pred_y) ** 2)))
            rmse_d_terms.append(float(np.mean((endog[test_idx, :] - pred_d_x) ** 2)))
            rmse_z_terms.append(float(np.mean((endog[test_idx, :] - pred_d_xz) ** 2)))

        train_size = n_obs - n_obs // n_folds
        selected_controls = sorted(selected_controls_union)
        selected_instruments = sorted(selected_instruments_union)

        warnings_list: list[str] = []
        selected_instruments = _ensure_min_instrument_count(
            selected_instruments,
            instruments=instruments,
            endog=endog,
            minimum_count=n_endogenous,
        )
        if len(selected_instruments) > len(selected_instruments_union):
            warnings_list.append(
                "Instrument selection was too sparse for identification; augmented with strongest marginal instruments."
            )

        selected_control_names = [control_names[idx] for idx in selected_controls]
        selected_instrument_names = [instrument_names[idx] for idx in selected_instruments]
        selected_control_matrix = _selected_columns(controls, selected_controls)
        selected_instrument_matrix = _selected_columns(instruments, selected_instruments)
        insufficient_instruments = selected_instrument_matrix.shape[1] < n_endogenous
        if insufficient_instruments:
            warnings_list.append("The selected instrument set is smaller than the number of endogenous regressors.")

        complexity_ratio_controls = _complexity_ratio(len(selected_controls), controls.shape[1], train_size)
        complexity_ratio_instruments = _complexity_ratio(len(selected_instruments), instruments.shape[1], train_size)
        product_rate_proxy = complexity_ratio_controls * complexity_ratio_instruments
        support_stability_controls = _average_jaccard(control_supports)
        support_stability_instruments = _average_jaccard(instrument_supports)

        sparsity_passed = (
            complexity_ratio_controls <= complexity_gate_max
            and complexity_ratio_instruments <= complexity_gate_max
            and support_stability_controls >= support_stability_min
            and support_stability_instruments >= support_stability_min
        )
        sparsity_diag = SparsityComplexityDiagnostic(
            selected_controls_union=len(selected_controls),
            selected_instruments_union=len(selected_instruments),
            complexity_ratio_controls=complexity_ratio_controls,
            complexity_ratio_instruments=complexity_ratio_instruments,
            support_stability_controls=support_stability_controls,
            support_stability_instruments=support_stability_instruments,
            passed=sparsity_passed,
            metadata={
                "n_train": int(train_size),
                "n_candidate_controls": int(controls.shape[1]),
                "n_candidate_instruments": int(instruments.shape[1]),
            },
        )

        theta_hat_vec, orth_se_vec, score_values, orthogonality_score, orth_condition_number = _orthogonal_pliv_estimate(
            y=y,
            endog=endog,
            y_hat=y_hat,
            d_hat_x=d_hat_x,
            d_hat_xz=d_hat_xz,
        )

        rmse_y = float(np.sqrt(np.mean(rmse_y_terms))) if rmse_y_terms else 0.0
        rmse_d = float(np.sqrt(np.mean(rmse_d_terms))) if rmse_d_terms else 0.0
        rmse_z = float(np.sqrt(np.mean(rmse_z_terms))) if rmse_z_terms else 0.0
        orthogonality_passed = (
            theta_hat_vec is not None
            and orth_se_vec is not None
            and np.all(np.isfinite(theta_hat_vec))
            and np.all(np.isfinite(orth_se_vec))
            and product_rate_proxy <= product_rate_gate_max
            and orthogonality_score <= orthogonality_score_max
        )
        orth_diag = OrthogonalityNuisanceDiagnostic(
            score_type="partial_linear_iv_orthogonal" if inference_route == "orthogonal" else "post_selection_wald",
            cross_fitted=bool(inference_route == "orthogonal"),
            n_folds=n_folds if inference_route == "orthogonal" else None,
            orthogonality_score=orthogonality_score if inference_route == "orthogonal" else None,
            nuisance_rmse_y=rmse_y if inference_route == "orthogonal" else None,
            nuisance_rmse_d=rmse_d if inference_route == "orthogonal" else None,
            nuisance_rmse_z=rmse_z if inference_route == "orthogonal" else None,
            product_rate_proxy=product_rate_proxy if inference_route == "orthogonal" else None,
            passed=orthogonality_passed if inference_route == "orthogonal" else False,
            metadata={"condition_number": orth_condition_number},
        )

        heuristic_params: dict[str, float] = {}
        heuristic_std_errors: dict[str, float] = {}
        heuristic_t_stats: dict[str, float] = {}
        heuristic_p_values: dict[str, float] = {}
        heuristic_intervals: dict[str, tuple[float, float]] = {}
        heuristic_fit = None
        heuristic_intervals_typed: dict[str, PostSelectionInterval] = {}
        if selected_instrument_matrix.shape[1] >= n_endogenous:
            (
                heuristic_params,
                heuristic_std_errors,
                heuristic_t_stats,
                heuristic_p_values,
                heuristic_intervals,
                heuristic_fit,
            ) = _fit_selected_2sls(
                y=y,
                d=endog,
                controls=selected_control_matrix,
                instruments=selected_instrument_matrix,
                confidence_level=confidence_level,
                cov_type=cov_type,
                endogenous_names=endogenous_names,
                control_names=selected_control_names,
                instrument_names=selected_instrument_names,
            )
            for name in endogenous_names:
                heuristic_ci = heuristic_intervals.get(name)
                if heuristic_ci is not None:
                    heuristic_intervals_typed[name] = _build_interval(
                        parameter=name,
                        confidence_level=confidence_level,
                        lower=heuristic_ci[0],
                        upper=heuristic_ci[1],
                        point_estimate=heuristic_params[name],
                        method_family="post_selection_wald",
                        metadata={
                            "selected_controls": selected_control_names,
                            "selected_instruments": selected_instrument_names,
                        },
                    )

        weak_iv_source = "hc1_conditional_f_fallback"
        extracted_first_stage = (
            _extract_first_stage_weak_iv_diagnostics(
                heuristic_fit,
                endogenous_names=endogenous_names,
            )
            if heuristic_fit is not None
            else None
        )
        if extracted_first_stage is not None:
            weak_iv_stats, weak_iv_pvalues, weak_iv_source = extracted_first_stage
        else:
            weak_iv_stats, weak_iv_pvalues = _conditional_weak_iv_stats(
                endog,
                selected_control_matrix,
                selected_instrument_matrix,
            )
        finite_weak_stats = [stat for stat in weak_iv_stats if stat is not None]
        weak_iv_stat = min(finite_weak_stats) if finite_weak_stats else None
        many_instrument_flag = bool(
            len(selected_instruments) > max(10, int(np.sqrt(max(train_size, 1))))
            or complexity_ratio_instruments > complexity_gate_max
        )
        identification_passed = bool(
            finite_weak_stats
            and all(stat is not None and stat >= weak_iv_threshold for stat in weak_iv_stats)
            and not insufficient_instruments
            and not many_instrument_flag
        )
        identification_diag = IdentificationDiagnostic(
            weak_iv_test_family="montiel_olea_pflueger_proxy" if n_endogenous == 1 else "sanderson_windmeijer_proxy",
            weak_iv_stat=weak_iv_stat,
            critical_value=weak_iv_threshold,
            passed=identification_passed,
            many_instrument_flag=many_instrument_flag,
            multiple_endogenous_flag=bool(n_endogenous > 1),
            metadata={
                "diagnostic_source": weak_iv_source,
                "p_values": {name: pvalue for name, pvalue in zip(endogenous_names, weak_iv_pvalues, strict=False)},
                "per_endogenous_stats": {name: stat for name, stat in zip(endogenous_names, weak_iv_stats, strict=False)},
                "selected_instruments": selected_instrument_names,
                "selected_controls": selected_control_names,
            },
        )

        z_value = float(NormalDist().inv_cdf((1.0 + confidence_level) / 2.0))
        orth_intervals_typed: dict[str, PostSelectionInterval] = {}
        if theta_hat_vec is not None and orth_se_vec is not None:
            for idx, name in enumerate(endogenous_names):
                theta_hat = float(theta_hat_vec[idx])
                orth_se = float(orth_se_vec[idx])
                if not np.isfinite(theta_hat) or not np.isfinite(orth_se):
                    continue
                orth_intervals_typed[name] = _build_interval(
                    parameter=name,
                    confidence_level=confidence_level,
                    lower=theta_hat - z_value * orth_se,
                    upper=theta_hat + z_value * orth_se,
                    point_estimate=theta_hat,
                    method_family="orthogonal_score_wald",
                    metadata={
                        "selected_controls": selected_control_names,
                        "selected_instruments": selected_instrument_names,
                    },
                )

        overall_gate_candidate = (
            inference_route == "orthogonal"
            and sparsity_passed
            and orthogonality_passed
            and identification_passed
        )

        weak_interval: PostSelectionInterval | None = None
        weak_interval_meta: dict[str, Any] = {}
        reference_point = None
        reference_se = None
        if theta_hat_vec is not None and orth_se_vec is not None and primary_param in endogenous_names:
            primary_idx = endogenous_names.index(primary_param)
            if np.isfinite(theta_hat_vec[primary_idx]) and np.isfinite(orth_se_vec[primary_idx]):
                reference_point = float(theta_hat_vec[primary_idx])
                reference_se = float(orth_se_vec[primary_idx])
        if reference_point is None and primary_param in heuristic_params and primary_param in heuristic_std_errors:
            reference_point = float(heuristic_params[primary_param])
            reference_se = float(heuristic_std_errors[primary_param])

        if n_endogenous > 1 and not overall_gate_candidate:
            warnings_list.append(
                "Weak-IV robust set inversion is only implemented for one endogenous regressor; multi-endogenous weak failures downgrade to NONE."
            )

        if (
            n_endogenous == 1
            and reference_point is not None
            and reference_se is not None
            and (compute_weak_iv_always or not overall_gate_candidate)
        ):
            weak_interval, weak_interval_meta = _anderson_rubin_interval(
                y=y,
                d=endog[:, 0],
                controls=selected_control_matrix,
                instruments=selected_instrument_matrix,
                parameter=primary_param,
                point_estimate=reference_point,
                se=reference_se,
                confidence_level=confidence_level,
                grid_points=ar_grid_points,
                grid_scale=ar_grid_scale,
            )

        reference_wald = orth_intervals_typed.get(primary_param) or heuristic_intervals_typed.get(primary_param)
        wald_width = _interval_width(reference_wald)
        weak_width = _interval_width(weak_interval)
        disagreement_ratio = (
            float(weak_width / wald_width)
            if weak_width is not None and wald_width is not None and wald_width > 1e-12
            else None
        )
        materially_different = None
        if reference_wald is not None and weak_interval is not None:
            materially_different = (
                len(reference_wald.segments) != len(weak_interval.segments)
                or (disagreement_ratio is not None and disagreement_ratio > 1.5)
            )
        interval_diag = IntervalDisagreementDiagnostic(
            wald_ci=reference_wald,
            weak_iv_robust_ci=weak_interval,
            ci_disagreement_ratio=disagreement_ratio,
            set_inversion_used=weak_interval is not None,
            materially_different=materially_different,
            metadata={"parameter": primary_param, **weak_interval_meta},
        )

        overall_gate_passed = overall_gate_candidate
        decision_notes: list[str] = []
        weak_interval_informative = bool(
            weak_interval is not None
            and not weak_interval.metadata.get("boundary_hit", False)
            and (
                disagreement_ratio is None
                or (np.isfinite(disagreement_ratio) and disagreement_ratio <= weak_set_max_width_ratio)
            )
        )
        if inference_route == "heuristic":
            coverage_tier = "HEURISTIC_POST_SELECTION" if heuristic_intervals_typed else "NONE"
            decision_notes.append("Explicit heuristic route requested: select-then-2SLS Wald intervals are labeled heuristic.")
        elif overall_gate_passed:
            coverage_tier = "ORTHOGONAL_CROSSFIT"
            decision_notes.append("Orthogonal cross-fit score, complexity gates, and weak-IV proxy all passed.")
        elif weak_interval_informative:
            coverage_tier = "WEAK_IV_ROBUST_SET"
            decision_notes.append("Weak-IV robust Anderson-Rubin inversion was used after at least one gate failed.")
        else:
            coverage_tier = "NONE"
            decision_notes.append("No theorem-aligned or weak-IV robust interval could be certified for the orthogonal route.")

        if not sparsity_passed:
            warnings_list.append("Approximate sparsity diagnostics failed the configured complexity/stability gates.")
        if inference_route == "orthogonal" and not orthogonality_passed:
            warnings_list.append("Orthogonal score diagnostics failed the configured product-rate or score gate.")
        if weak_iv_stat is not None and weak_iv_stat < weak_iv_threshold:
            warnings_list.append("Weak-IV strength proxy fell below the configured threshold.")
        if many_instrument_flag:
            warnings_list.append("Selected instrument set entered a many-instrument regime; Wald inference was downgraded.")
        warnings_list.append(
            "Weak-IV gate prefers linearmodels first-stage diagnostics when available and otherwise falls back to HC1 conditional-F proxies; exact MOP effective-F / many-weak CLR calibration is not yet implemented."
        )
        if weak_interval is not None and not weak_interval_informative:
            warnings_list.append("Weak-IV robust set was computed but treated as uninformative for tier assignment.")

        coverage_diag = PostSelectionCoverageDiagnostic(
            sample_size_requirement=(
                f"s_x log(max(p_x,n_train))/n_train={complexity_ratio_controls:.4f}; "
                f"s_z log(max(p_z,n_train))/n_train={complexity_ratio_instruments:.4f}; "
                f"product_rate_proxy={product_rate_proxy:.4f}"
            ),
            sparsity=sparsity_diag,
            orthogonality=orth_diag,
            identification=identification_diag,
            interval_disagreement=interval_diag,
            overall_gate_passed=overall_gate_passed,
            warnings=tuple(warnings_list),
            decision_notes=tuple(decision_notes),
        )

        result_params: dict[str, float] = {}
        result_std_errors: dict[str, float] = {}
        result_t_stats: dict[str, float] = {}
        result_p_values: dict[str, float] = {}
        result_confidence_intervals: dict[str, tuple[float, float]] = {}

        if inference_route == "heuristic" or coverage_tier == "HEURISTIC_POST_SELECTION":
            result_params.update(heuristic_params)
            result_std_errors.update(heuristic_std_errors)
            result_t_stats.update(heuristic_t_stats)
            result_p_values.update(heuristic_p_values)
            result_confidence_intervals.update(heuristic_intervals)
        else:
            result_params.update(heuristic_params)
            result_std_errors.update(heuristic_std_errors)
            result_t_stats.update(heuristic_t_stats)
            result_p_values.update(heuristic_p_values)
            if theta_hat_vec is not None and orth_se_vec is not None:
                normal = NormalDist()
                for idx, name in enumerate(endogenous_names):
                    theta_hat = float(theta_hat_vec[idx])
                    orth_se = float(orth_se_vec[idx])
                    if not np.isfinite(theta_hat) or not np.isfinite(orth_se):
                        continue
                    result_params[name] = theta_hat
                    result_std_errors[name] = orth_se
                    result_t_stats[name] = float(theta_hat / max(orth_se, 1e-12))
                    result_p_values[name] = float(2.0 * (1.0 - normal.cdf(abs(result_t_stats[name]))))
            if coverage_tier == "ORTHOGONAL_CROSSFIT":
                for name, interval in orth_intervals_typed.items():
                    hull = interval.convex_hull()
                    if hull is not None:
                        result_confidence_intervals[name] = hull
            elif coverage_tier == "WEAK_IV_ROBUST_SET" and weak_interval is not None:
                hull = weak_interval.convex_hull()
                if hull is not None:
                    result_confidence_intervals[primary_param] = hull

        post_selection_ci: dict[str, PostSelectionInterval] = {}
        if inference_route == "heuristic":
            post_selection_ci.update(heuristic_intervals_typed)
        elif orth_intervals_typed:
            post_selection_ci.update(orth_intervals_typed)
        elif heuristic_intervals_typed:
            # Preserve the last available Wald-style comparator for diagnostics
            # even when the orthogonal route cannot certify coverage.
            post_selection_ci.update(heuristic_intervals_typed)

        weak_iv_robust_ci = {}
        if weak_interval is not None:
            weak_iv_robust_ci[primary_param] = weak_interval

        result = EconometricResult(
            method_name="iv_high_dimensional_post_selection",
            params=result_params,
            std_errors=result_std_errors,
            t_stats=result_t_stats,
            p_values=result_p_values,
            confidence_intervals=result_confidence_intervals,
            confidence_level=confidence_level,
            r_squared=_safe_float(getattr(heuristic_fit, "rsquared", None)),
            n_obs=n_obs,
            coverage_guarantee_tier=coverage_tier,
            coverage_diagnostic=coverage_diag,
            post_selection_ci=post_selection_ci,
            weak_iv_robust_ci=weak_iv_robust_ci,
            diagnostics={
                "inference_route": inference_route,
                "endogenous_names": endogenous_names,
                "selected_controls": selected_control_names,
                "selected_instruments": selected_instrument_names,
                "weak_iv_proxy_stat": weak_iv_stat,
                "weak_iv_proxy_pvalues": {name: pvalue for name, pvalue in zip(endogenous_names, weak_iv_pvalues, strict=False)},
                "weak_iv_diagnostic_source": weak_iv_source,
                "orthogonality_score": orthogonality_score,
                "product_rate_proxy": product_rate_proxy,
                "coverage_guarantee_tier": coverage_tier,
            },
            model_info={
                "library": "linearmodels+statsmodels+numpy",
                "estimator": "HighDimensionalPostSelectionIVEstimator",
                "score_type": "partial_linear_iv_orthogonal" if inference_route == "orthogonal" else "post_selection_wald",
            },
            metadata={
                "n_candidate_controls": int(controls.shape[1]),
                "n_candidate_instruments": int(instruments.shape[1]),
                "cross_fit_folds": n_folds,
                "n_endogenous": n_endogenous,
            },
        )

        return {
            "result": result,
            "uncertainty_envelope": result.to_uncertainty_envelope(
                param_name=primary_param
            ),
        }

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> PanelData:
        return _materialize_iv_data(bound_inputs, fallback_state)


__all__ = ["HighDimensionalPostSelectionIVEstimator"]
