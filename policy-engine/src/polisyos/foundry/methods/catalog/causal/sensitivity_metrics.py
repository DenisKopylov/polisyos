"""Public causal sensitivity metrics module API."""
from __future__ import annotations

import importlib
import math
from collections.abc import Mapping
from typing import Any, ClassVar

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
from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData
from polisyos.ir.analytics.sensitivity import BenchmarkResult, EValueResult, SensitivityResult

_EPS = 1.0e-12


def _to_float(value: Any, *, name: str) -> float:
    scalar = float(value)
    if not math.isfinite(scalar):
        raise ValueError(f"{name} must be finite")
    return scalar


def _to_optional_float(value: Any, *, name: str) -> float | None:
    if value is None:
        return None
    return _to_float(value, name=name)


def _parse_confidence_interval(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("confidence_interval must be a list/tuple with two numeric values")
    lo = _to_float(value[0], name="confidence_interval[0]")
    hi = _to_float(value[1], name="confidence_interval[1]")
    return (lo, hi) if lo <= hi else (hi, lo)


def _ate_to_rr_log(effect: float) -> float:
    rr = math.exp(effect)
    return max(rr, _EPS)


def _ate_to_rr_approx(effect: float, *, baseline_risk: float) -> float:
    if not (0.0 < baseline_risk < 1.0):
        raise ValueError("baseline_risk must be in (0,1) for ate_to_rr_approx")
    treated_risk = min(max(baseline_risk + effect, _EPS), 1.0 - _EPS)
    rr = treated_risk / baseline_risk
    return max(rr, _EPS)


def _resolve_conversion_method(
    *,
    requested: str,
    baseline_risk: float | None,
) -> tuple[str, str | None]:
    if requested in {"ate_to_rr_log", "ate_to_rr_approx"}:
        if requested == "ate_to_rr_approx" and baseline_risk is None:
            return "ate_to_rr_log", "baseline_risk missing; falling back to ate_to_rr_log"
        return requested, None
    if requested != "auto":
        return "ate_to_rr_log", f"unknown conversion_method={requested!r}; using ate_to_rr_log"
    if baseline_risk is not None and 0.0 < baseline_risk < 1.0:
        return "ate_to_rr_approx", None
    return "ate_to_rr_log", None


def _convert_to_rr(
    *,
    effect: float,
    method: str,
    baseline_risk: float | None,
) -> float:
    if method == "ate_to_rr_approx":
        assert baseline_risk is not None
        return _ate_to_rr_approx(effect, baseline_risk=baseline_risk)
    return _ate_to_rr_log(effect)


def _rr_to_evalue(rr: float) -> float:
    rr_abs = max(rr, _EPS)
    if rr_abs < 1.0:
        rr_abs = 1.0 / rr_abs
    return float(rr_abs + math.sqrt(rr_abs * (rr_abs - 1.0)))


def _compute_evalue(
    *,
    point_estimate: float,
    confidence_interval: tuple[float, float] | None,
    conversion_method: str,
    baseline_risk: float | None,
) -> tuple[float, float | None, EValueResult]:
    rr_point = _convert_to_rr(
        effect=point_estimate,
        method=conversion_method,
        baseline_risk=baseline_risk,
    )
    e_value = _rr_to_evalue(rr_point)

    rr_ci: tuple[float, float] | None = None
    ci_crosses_null = False
    e_value_ci_lower: float | None = None
    if confidence_interval is not None:
        rr_lo = _convert_to_rr(
            effect=confidence_interval[0],
            method=conversion_method,
            baseline_risk=baseline_risk,
        )
        rr_hi = _convert_to_rr(
            effect=confidence_interval[1],
            method=conversion_method,
            baseline_risk=baseline_risk,
        )
        rr_ci = (min(rr_lo, rr_hi), max(rr_lo, rr_hi))
        ci_crosses_null = rr_ci[0] <= 1.0 <= rr_ci[1]
        if ci_crosses_null:
            e_value_ci_lower = 1.0
        else:
            if rr_ci[0] > 1.0:
                rr_bound = rr_ci[0]
            else:
                rr_bound = rr_ci[1]
            e_value_ci_lower = _rr_to_evalue(rr_bound)

    details = {
        "point_rr": rr_point,
        "baseline_risk_used": baseline_risk,
    }
    return (
        e_value,
        e_value_ci_lower,
        EValueResult(
            raw_effect=point_estimate,
            rr_equivalent=rr_point,
            method=conversion_method,
            ci_rr=rr_ci,
            ci_crosses_null=ci_crosses_null,
            details=details,
        ),
    )


def _load_sensemakr_module() -> Any:
    candidates = ("sensemakr", "pysensemakr")
    last_error: Exception | None = None
    for module_name in candidates:
        try:
            return importlib.import_module(module_name)
        except Exception as exc:
            last_error = exc
    if last_error is None:
        raise ModuleNotFoundError("sensemakr is unavailable")
    raise ModuleNotFoundError(str(last_error))


def _extract_stat(payload: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(payload, Mapping):
        for key in keys:
            if key not in payload:
                continue
            value = payload[key]
            if value is None:
                continue
            try:
                scalar = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(scalar):
                return scalar
        return None
    for key in keys:
        if not hasattr(payload, key):
            continue
        value = getattr(payload, key)
        if value is None:
            continue
        try:
            scalar = float(value)
        except Exception:
            continue
        if math.isfinite(scalar):
            return scalar
    return None


def _compute_robustness(
    *,
    point_estimate: float,
    standard_error: float | None,
    sample_size: int | None,
) -> tuple[float | None, float | None, str | None]:
    if standard_error is None or standard_error <= 0:
        return None, None, "robustness_value skipped: standard_error unavailable"
    if sample_size is None or sample_size < 4:
        return None, None, "robustness_value skipped: sample_size too small"

    dof = max(sample_size - 3, 1)
    try:
        sensemakr = _load_sensemakr_module()
    except Exception as exc:
        return None, None, f"robustness_value skipped: sensemakr unavailable ({exc})"

    sensitivity_stats = getattr(sensemakr, "sensitivity_stats", None)
    if not callable(sensitivity_stats):
        return None, None, "robustness_value skipped: sensemakr.sensitivity_stats missing"

    stats_payload: Any | None = None
    call_candidates: tuple[dict[str, Any], ...] = (
        {"estimate": point_estimate, "se": standard_error, "dof": dof},
        {"est": point_estimate, "se": standard_error, "dof": dof},
        {"estimate": point_estimate, "se": standard_error, "dof": dof, "q": 1.0},
    )
    for kwargs in call_candidates:
        try:
            stats_payload = sensitivity_stats(**kwargs)
            break
        except TypeError:
            continue
        except Exception as exc:
            return None, None, f"robustness_value skipped: sensemakr error ({exc})"

    if stats_payload is None:
        return None, None, "robustness_value skipped: unsupported sensemakr API"

    rv = _extract_stat(stats_payload, ("rv_q", "rv", "robustness_value"))
    partial_r2 = _extract_stat(
        stats_payload,
        ("r2yd_x", "partial_r2_treatment", "r2_y_dx"),
    )
    if partial_r2 is not None:
        partial_r2 = min(max(partial_r2, 0.0), 1.0)

    if rv is None and partial_r2 is not None:
        rv = partial_r2
    if partial_r2 is None and rv is not None:
        partial_r2 = rv

    if rv is None:
        t_stat = abs(point_estimate / standard_error)
        partial_r2 = float((t_stat * t_stat) / ((t_stat * t_stat) + dof))
        rv = partial_r2
        return rv, partial_r2, "robustness_value approximated from t-statistic fallback"

    return rv, partial_r2, None


def _log_binom_pmf(n: int, k: int, p: float) -> float:
    if p <= 0.0:
        return 0.0 if k == 0 else -math.inf
    if p >= 1.0:
        return 0.0 if k == n else -math.inf
    return (
        math.lgamma(n + 1)
        - math.lgamma(k + 1)
        - math.lgamma(n - k + 1)
        + (k * math.log(p))
        + ((n - k) * math.log(1.0 - p))
    )


def _binom_tail_ge(n: int, k: int, p: float) -> float:
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    logs = [_log_binom_pmf(n, i, p) for i in range(k, n + 1)]
    max_log = max(logs)
    if not math.isfinite(max_log):
        return 0.0
    total = sum(math.exp(value - max_log) for value in logs)
    return float(min(1.0, math.exp(max_log) * total))


def _match_pairs(
    *,
    data: np.ndarray,
    treatment_idx: int,
    covariate_indices: list[int],
) -> list[tuple[int, int]]:
    treatment = np.asarray(data[:, treatment_idx], dtype=float)
    treated_rows = np.flatnonzero(treatment != 0.0)
    control_rows = np.flatnonzero(treatment == 0.0)
    if treated_rows.size == 0 or control_rows.size == 0:
        return []
    if not covariate_indices:
        return []

    cov = np.asarray(data[:, covariate_indices], dtype=float)
    treated_cov = cov[treated_rows]
    control_cov = cov[control_rows]
    pooled_scale = np.std(cov, axis=0)
    pooled_scale = np.where(pooled_scale <= 0.0, 1.0, pooled_scale)
    treated_cov = treated_cov / pooled_scale
    control_cov = control_cov / pooled_scale

    available: set[int] = set(range(control_rows.size))
    pairs: list[tuple[int, int]] = []
    for tidx, trow in enumerate(treated_rows.tolist()):
        if not available:
            break
        candidate_idx = np.asarray(sorted(available), dtype=int)
        deltas = control_cov[candidate_idx] - treated_cov[tidx]
        distances = np.einsum("ij,ij->i", deltas, deltas)
        best_local = int(candidate_idx[int(np.argmin(distances))])
        available.remove(best_local)
        pairs.append((trow, int(control_rows[best_local])))
    return pairs


def _compute_rosenbaum_gamma(
    *,
    data: np.ndarray,
    treatment_idx: int,
    outcome_idx: int,
    covariate_indices: list[int],
    alpha: float,
    gamma_max: float,
    gamma_step: float,
) -> tuple[float | None, float | None, str | None]:
    if gamma_step <= 0.0:
        return None, None, "rosenbaum_gamma skipped: gamma_step must be > 0"
    treatment = np.asarray(data[:, treatment_idx], dtype=float)
    finite_treatment = treatment[np.isfinite(treatment)]
    unique_values = np.unique(finite_treatment)
    if unique_values.size != 2 or not np.all(np.isin(unique_values, (0.0, 1.0))):
        return None, None, "rosenbaum_gamma skipped: treatment must be binary (0/1)"
    pairs = _match_pairs(
        data=data,
        treatment_idx=treatment_idx,
        covariate_indices=covariate_indices,
    )
    if len(pairs) < 6:
        return None, None, "rosenbaum_gamma skipped: insufficient matched pairs"

    outcome = np.asarray(data[:, outcome_idx], dtype=float)
    diffs = np.asarray([outcome[i] - outcome[j] for i, j in pairs], dtype=float)
    non_zero = diffs[np.abs(diffs) > _EPS]
    if non_zero.size < 6:
        return None, None, "rosenbaum_gamma skipped: insufficient non-zero pair differences"

    n_plus = int(np.sum(non_zero > 0.0))
    n_minus = int(np.sum(non_zero < 0.0))
    n_pairs = int(non_zero.size)
    n_extreme = max(n_plus, n_minus)

    gamma = 1.0
    last_p = 1.0
    while gamma <= (gamma_max + _EPS):
        p_low = 1.0 / (1.0 + gamma)
        p_high = gamma / (1.0 + gamma)
        tail_low = _binom_tail_ge(n_pairs, n_extreme, p_low)
        tail_high = _binom_tail_ge(n_pairs, n_extreme, p_high)
        p_upper = min(1.0, 2.0 * max(tail_low, tail_high))
        last_p = p_upper
        if p_upper > alpha:
            return float(gamma), float(p_upper), None
        gamma += gamma_step

    return float(gamma_max + gamma_step), float(last_p), None


def _partial_r2_numpy(
    X: np.ndarray,
    y: np.ndarray,
    col_idx: int,
) -> float | None:
    """Compute partial R² of column col_idx of X on y, controlling for remaining columns.

    partial R² = 1 - RSS_full / RSS_restricted
    where RSS_full = OLS residuals of y ~ X (all columns)
    and   RSS_restricted = OLS residuals of y ~ X_without_col_idx
    """
    n, p = X.shape
    if n < p + 2 or p < 2:
        return None

    # Full model: y ~ X
    try:
        coef_full, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        res_full = y - X @ coef_full
        rss_full = float(np.dot(res_full, res_full))

        # Restricted model: drop col_idx
        keep = [i for i in range(p) if i != col_idx]
        X_restr = X[:, keep]
        coef_restr, _, _, _ = np.linalg.lstsq(X_restr, y, rcond=None)
        res_restr = y - X_restr @ coef_restr
        rss_restr = float(np.dot(res_restr, res_restr))

        if rss_restr <= _EPS:
            return None
        r2 = 1.0 - rss_full / rss_restr
        return float(max(0.0, min(1.0, r2)))
    except (np.linalg.LinAlgError, ValueError):
        return None


def _compute_benchmarks(
    *,
    data_matrix: np.ndarray,
    treatment_col: int,
    outcome_col: int,
    covariate_cols: list[int],
    benchmark_names: list[str],
    partial_r2_treatment: float | None,
    sensemakr_mod: Any | None,
) -> tuple[list[BenchmarkResult], str | None]:
    """Compute Cinelli-Hazlett benchmarks relative to named observed covariates.

    For each benchmark covariate, computes:
    - r2yd_x: partial R² of that covariate on the outcome
    - r2td_x: partial R² of that covariate on the treatment
    - bias_scale: r2td_x / partial_r2_treatment (how many times this covariate's
      treatment-confounding would be needed to explain away the effect)
    - rv_benchmarked: sensemakr RV benchmarked to this covariate (if available)

    Falls back to numpy-only partial R² computation when sensemakr is unavailable.
    """
    if not benchmark_names or not covariate_cols:
        return [], None

    n, p_total = data_matrix.shape
    # Build design matrix with intercept, treatment, and all covariates
    all_cols = [treatment_col] + covariate_cols
    X_base = np.hstack([
        np.ones((n, 1), dtype=float),
        data_matrix[:, all_cols],
    ])
    y_outcome = data_matrix[:, outcome_col].astype(float)
    t_treatment = data_matrix[:, treatment_col].astype(float)

    # Covariate-only design (for r2td_x: partial R² of covariate on treatment)
    X_covariates = np.hstack([
        np.ones((n, 1), dtype=float),
        data_matrix[:, covariate_cols],
    ])

    # Build name → position in covariate_cols mapping
    # covariate_cols[i] is the column index in data_matrix
    col_idx_to_pos: dict[int, int] = {col: idx for idx, col in enumerate(covariate_cols)}

    results: list[BenchmarkResult] = []
    warnings_found: list[str] = []

    for name in benchmark_names:
        # Find the column index for this benchmark covariate
        bench_col: int | None = None
        for col_idx in covariate_cols:
            pass  # we'll match by name index below — handled outside

        # We receive benchmark_names and covariate_cols in the same order
        # from the caller, so zip them together
        # This function is called with benchmark names that map to covariate_cols
        # positionally (caller filters to matching columns first).
        # Use the outer scope variable; iterate below.
        r2yd_x: float | None = None
        r2td_x: float | None = None
        bias_scale: float | None = None
        rv_benchmarked: float | None = None
        interpretation = ""

        # Find bench_col by position in the names → covariate_cols list
        # (caller passes only names that exist in covariate_cols ordering)
        try:
            bench_pos = benchmark_names.index(name)  # position in benchmark_names list
            if bench_pos < len(covariate_cols):
                bench_col_idx = covariate_cols[bench_pos]
            else:
                warnings_found.append(f"benchmark covariate '{name}' not found; skipping")
                continue
        except ValueError:
            warnings_found.append(f"benchmark covariate '{name}' not found; skipping")
            continue

        # r2yd_x: partial R² of bench_col on outcome (controlling for T + other covariates)
        # In X_base: column 0 = intercept, column 1 = treatment, columns 2.. = covariates
        # The benchmark covariate is at X_base column = 2 + bench_pos
        bench_in_base = 2 + bench_pos
        if bench_in_base < X_base.shape[1]:
            r2yd_x = _partial_r2_numpy(X_base, y_outcome, bench_in_base)

        # r2td_x: partial R² of bench_col on treatment (controlling for other covariates)
        # In X_covariates: column 0 = intercept, columns 1.. = covariates
        bench_in_cov = 1 + bench_pos
        if bench_in_cov < X_covariates.shape[1]:
            r2td_x = _partial_r2_numpy(X_covariates, t_treatment, bench_in_cov)

        # bias_scale: relative to treatment's own partial R²
        if r2td_x is not None and partial_r2_treatment is not None and partial_r2_treatment > _EPS:
            bias_scale = r2td_x / partial_r2_treatment

        # Optional sensemakr enhancement
        if sensemakr_mod is not None and r2yd_x is not None and r2td_x is not None:
            ovb_bounds = getattr(sensemakr_mod, "ovb_bounds", None)
            if callable(ovb_bounds):
                try:
                    bounds_result = ovb_bounds(
                        r2yd_x=r2yd_x,
                        r2td_x=r2td_x,
                    )
                    rv_benchmarked = _extract_stat(
                        bounds_result,
                        ("rv_q", "rv", "robustness_value", "adjusted_rv"),
                    )
                except Exception:
                    pass  # sensemakr API mismatch — skip

        # Build interpretation string
        parts: list[str] = [f"Covariate '{name}':"]
        if r2yd_x is not None:
            parts.append(f"r2_outcome={r2yd_x:.3f}")
        if r2td_x is not None:
            parts.append(f"r2_treatment={r2td_x:.3f}")
        if bias_scale is not None:
            if bias_scale >= 1.0:
                parts.append(
                    f"bias_scale={bias_scale:.1f}x (effect is more robust than this covariate)"
                )
            else:
                parts.append(
                    f"bias_scale={bias_scale:.2f}x (confounder of this strength could explain away effect)"
                )
        interpretation = " ".join(parts)

        results.append(BenchmarkResult(
            covariate_name=name,
            r2yd_x=r2yd_x,
            r2td_x=r2td_x,
            bias_scale=bias_scale,
            rv_benchmarked=rv_benchmarked,
            interpretation=interpretation,
        ))

    warning_msg = "; ".join(warnings_found) if warnings_found else None
    return results, warning_msg


def _build_interpretation(result: SensitivityResult) -> str:
    parts: list[str] = []
    if result.e_value is not None:
        parts.append(f"E-value={result.e_value:.3f}")
    if result.robustness_value is not None:
        parts.append(f"RV={result.robustness_value:.3f}")
    if result.rosenbaum_gamma is not None:
        parts.append(f"Rosenbaum_Gamma={result.rosenbaum_gamma:.3f}")
    if not parts:
        return "Sensitivity metrics were not available."
    status = "robust" if result.is_robust else "not robust"
    return f"{'; '.join(parts)}; combined_assessment={status}."


@foundry_method(
    namespace="causal.sensitivity",
    version="1.0.0",
    tags={"causal", "sensitivity", "robustness"},
)
class SensitivityMetrics:
    """Compute causal sensitivity diagnostics for observational estimates."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sensitivity_metrics",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="graph_causal_data",
                    slot_type=SlotType.MATRIX,
                    unit=Unit("observations", "rows"),
                    shape=("n_obs", "n_features"),
                )
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="sensitivity_result",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("report", "json"),
                ),
            }
        ),
        parameters=(
            ParameterSpec(name="point_estimate", default=0.0),
            ParameterSpec(name="confidence_interval", default=None),
            ParameterSpec(name="standard_error", default=None),
            ParameterSpec(name="sample_size", default=None),
            ParameterSpec(name="baseline_risk", default=None),
            ParameterSpec(name="conversion_method", default="auto"),
            ParameterSpec(name="alpha", default=0.05),
            ParameterSpec(name="rosenbaum_gamma_max", default=4.0),
            ParameterSpec(name="rosenbaum_gamma_step", default=0.1),
            ParameterSpec(name="e_value_threshold", default=1.25),
            ParameterSpec(name="robustness_value_threshold", default=0.05),
            ParameterSpec(name="rosenbaum_gamma_threshold", default=1.25),
            ParameterSpec(name="covariates", default=None),
            ParameterSpec(
                name="ess_fraction",
                default=None,
                description="ESS fraction from upstream density-ratio or positivity check.",
            ),
            ParameterSpec(
                name="ess_min_threshold",
                default=0.1,
                description="ESS fraction below which to emit a near-inestimable warning.",
            ),
            ParameterSpec(
                name="benchmark_covariates",
                default=None,
                description=(
                    "List of covariate column names for Cinelli-Hazlett relative sensitivity "
                    "benchmarking. Each named covariate's partial R² on treatment and outcome "
                    "is computed and compared to the treatment's own partial R². "
                    "If None, benchmarking is skipped."
                ),
            ),
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
            "Sensitivity metrics for hidden confounding: E-value, robustness value, "
            "and Rosenbaum gamma."
        ),
        tags=frozenset({"causal", "sensitivity", "evalue", "rosenbaum", "sensemakr"}),
        citations=(
            "Ding, P., VanderWeele, T. J. (2016). Sensitivity Analysis "
            "Without Assumptions.",
            "Cinelli, C., Hazlett, C. (2020). Making sense of sensitivity.",
            "Rosenbaum, P. R. (2002). Observational Studies.",
        ),
        assumptions={
            "binary_treatment": "Rosenbaum gamma requires binary treatment assignments.",
            "matching_quality": "Nearest-neighbor covariate matching approximates pair balance.",
            "effect_scale": "ATE to RR conversion is an approximation recorded in conversion_method.",
        },
        when_to_use="Assess robustness of causal estimate to unmeasured confounding; how strong must confounding be to explain away result",
        when_not_to_use="Purely descriptive analysis without causal claim; no concern about unobserved confounders",
        output_interpretation="E-value: minimum association a confounder must have with T and Y to fully explain the effect. Higher E-value = more robust.",
    )

    @staticmethod
    def pure_step(state: GraphCausalData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, GraphCausalData) else GraphCausalData.model_validate(state)
        warnings: list[str] = []

        if "point_estimate" not in params:
            raise ValueError("point_estimate is required for sensitivity_metrics")
        point_estimate = _to_float(params.get("point_estimate"), name="point_estimate")
        confidence_interval = _parse_confidence_interval(params.get("confidence_interval"))
        standard_error = _to_optional_float(params.get("standard_error"), name="standard_error")
        sample_size_raw = params.get("sample_size")
        if sample_size_raw is None:
            sample_size = int(data.sample_size)
        else:
            sample_size = int(sample_size_raw)
        baseline_risk = _to_optional_float(params.get("baseline_risk"), name="baseline_risk")
        if baseline_risk is not None and not (0.0 < baseline_risk < 1.0):
            warnings.append("baseline_risk must be in (0,1); ignored")
            baseline_risk = None

        requested_conversion = str(params.get("conversion_method", "auto"))
        conversion_method, conversion_warning = _resolve_conversion_method(
            requested=requested_conversion,
            baseline_risk=baseline_risk,
        )
        if conversion_warning:
            warnings.append(conversion_warning)

        e_value, e_value_ci_lower, e_value_result = _compute_evalue(
            point_estimate=point_estimate,
            confidence_interval=confidence_interval,
            conversion_method=conversion_method,
            baseline_risk=baseline_risk,
        )

        robustness_value, partial_r2_treatment, robustness_warning = _compute_robustness(
            point_estimate=point_estimate,
            standard_error=standard_error,
            sample_size=sample_size,
        )
        if robustness_warning is not None:
            warnings.append(robustness_warning)

        alpha = _to_float(params.get("alpha", 0.05), name="alpha")
        if not (0.0 < alpha < 1.0):
            raise ValueError("alpha must be in (0,1)")
        rosenbaum_gamma_max = _to_float(
            params.get("rosenbaum_gamma_max", 4.0),
            name="rosenbaum_gamma_max",
        )
        rosenbaum_gamma_step = _to_float(
            params.get("rosenbaum_gamma_step", 0.1),
            name="rosenbaum_gamma_step",
        )
        if rosenbaum_gamma_max <= 1.0:
            raise ValueError("rosenbaum_gamma_max must be > 1")

        covariate_names_raw = params.get("covariates")
        if isinstance(covariate_names_raw, list):
            covariate_names = [str(item) for item in covariate_names_raw]
        else:
            covariate_names = list(data.covariates)
        covariate_indices = [
            data.column_names.index(name)
            for name in covariate_names
            if name in data.column_names and name not in {data.treatment, data.outcome}
        ]
        rosenbaum_gamma: float | None = None
        rosenbaum_p_value: float | None = None
        rosenbaum_warning: str | None = None
        treatment_idx = data.column_names.index(data.treatment)
        outcome_idx = data.column_names.index(data.outcome)
        rosenbaum_gamma, rosenbaum_p_value, rosenbaum_warning = _compute_rosenbaum_gamma(
            data=np.asarray(data.data, dtype=float),
            treatment_idx=treatment_idx,
            outcome_idx=outcome_idx,
            covariate_indices=covariate_indices,
            alpha=alpha,
            gamma_max=rosenbaum_gamma_max,
            gamma_step=rosenbaum_gamma_step,
        )
        if rosenbaum_warning is not None:
            warnings.append(rosenbaum_warning)

        # Cinelli-Hazlett benchmarking
        benchmark_covariates_raw = params.get("benchmark_covariates")
        benchmark_results: list[BenchmarkResult] = []
        benchmark_covariate_names: list[str] = []
        if benchmark_covariates_raw is not None:
            raw_names = [str(c) for c in benchmark_covariates_raw]
            # Filter to names that exist in data and are covariates (not treatment/outcome)
            valid_names = [
                name for name in raw_names
                if name in data.column_names
                and name not in {data.treatment, data.outcome}
                and data.column_names.index(name) in covariate_indices
            ]
            if valid_names:
                bench_cols = [data.column_names.index(name) for name in valid_names]
                # Load sensemakr once (may already have tried above)
                try:
                    sensemakr_mod = _load_sensemakr_module()
                except Exception:
                    sensemakr_mod = None
                benchmark_results, bench_warning = _compute_benchmarks(
                    data_matrix=np.asarray(data.data, dtype=float),
                    treatment_col=treatment_idx,
                    outcome_col=outcome_idx,
                    covariate_cols=covariate_indices,
                    benchmark_names=valid_names,
                    partial_r2_treatment=partial_r2_treatment,
                    sensemakr_mod=sensemakr_mod,
                )
                benchmark_covariate_names = valid_names
                if bench_warning:
                    warnings.append(bench_warning)
            else:
                skipped = [n for n in raw_names if n not in data.column_names]
                if skipped:
                    warnings.append(
                        f"benchmark_covariates not found in data columns: {skipped}"
                    )

        ess_fraction_raw = params.get("ess_fraction")
        ess_min_threshold = _to_float(params.get("ess_min_threshold", 0.1), name="ess_min_threshold")
        if ess_fraction_raw is not None:
            ess_frac = _to_float(ess_fraction_raw, name="ess_fraction")
            if ess_frac < ess_min_threshold:
                warnings.append(
                    f"transport near-inestimable: ESS fraction {ess_frac:.3f} < threshold "
                    f"{ess_min_threshold:.3f}. The estimand is formally identifiable but "
                    "statistical precision is critically limited."
                )

        e_value_threshold = _to_float(params.get("e_value_threshold", 1.25), name="e_value_threshold")
        robustness_value_threshold = _to_float(
            params.get("robustness_value_threshold", 0.05),
            name="robustness_value_threshold",
        )
        rosenbaum_gamma_threshold = _to_float(
            params.get("rosenbaum_gamma_threshold", 1.25),
            name="rosenbaum_gamma_threshold",
        )

        metric_checks: dict[str, bool] = {}
        if e_value is not None:
            metric_checks["e_value"] = bool(e_value >= e_value_threshold)
        if robustness_value is not None:
            metric_checks["robustness_value"] = bool(robustness_value >= robustness_value_threshold)
        if rosenbaum_gamma is not None:
            metric_checks["rosenbaum_gamma"] = bool(rosenbaum_gamma >= rosenbaum_gamma_threshold)
        is_robust = bool(metric_checks) and all(metric_checks.values())

        result = SensitivityResult(
            e_value=e_value,
            e_value_ci_lower=e_value_ci_lower,
            conversion_method=conversion_method,
            e_value_result=e_value_result,
            robustness_value=robustness_value,
            partial_r2_treatment=partial_r2_treatment,
            rosenbaum_gamma=rosenbaum_gamma,
            rosenbaum_p_value=rosenbaum_p_value,
            is_robust=is_robust,
            benchmark_results=benchmark_results,
            benchmark_covariates=benchmark_covariate_names,
            metadata={
                "sample_size": sample_size,
                "alpha": alpha,
                "thresholds": {
                    "e_value": e_value_threshold,
                    "robustness_value": robustness_value_threshold,
                    "rosenbaum_gamma": rosenbaum_gamma_threshold,
                },
                "metric_checks": metric_checks,
                "covariates_used": [data.column_names[idx] for idx in covariate_indices],
                "warnings": list(warnings),
                "ess_fraction": ess_fraction_raw,
            },
        )
        result = result.model_copy(update={"interpretation": _build_interpretation(result)})
        return {
            "sensitivity_result": result,
            "warnings": warnings,
            "__determinism_tier__": DeterminismTier.STATISTICAL,
        }


__all__ = ["SensitivityMetrics"]
