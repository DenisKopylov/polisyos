"""Finite-sample calibration helpers for algebraic causal constraints.

The first production-calibrated algebraic family is tetrad testing.  This
module keeps the calibration contract separate from graph discovery so the
offline benchmark suite and the runtime severity map share the same thresholds.
"""
from __future__ import annotations

import math
from collections import defaultdict
from enum import StrEnum
from itertools import combinations, product
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from collections.abc import Iterable


class TetradCalibrationScenarioKind(StrEnum):
    """Scenario families used to calibrate tetrad tests under misspecification."""

    EXACT_NULL = "exact_null"
    ROBUST_NULL = "robust_null"
    APPROXIMATE_NULL = "approximate_null"
    ORDINAL_ROUTE = "ordinal_route"
    MODERATE_ALTERNATIVE = "moderate_alternative"
    STRONG_ALTERNATIVE = "strong_alternative"


class TetradCalibrationScenario(BaseModel):
    """One benchmark scenario family for finite-sample tetrad calibration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str = Field(min_length=1)
    kind: TetradCalibrationScenarioKind
    description: str = Field(min_length=1)
    expected_population_relation: Literal[
        "exact_null",
        "approximate_null",
        "alternative",
        "route_specific",
    ]
    misspecification_axes: tuple[str, ...] = ()
    expected_max_severity: Literal["info", "warning", "blocker"] = "warning"

    @property
    def expected_violation(self) -> bool:
        return self.expected_population_relation == "alternative"


class TetradCalibrationBenchmarkSuite(BaseModel):
    """Executable benchmark grid for tetrad calibration research."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_id: str = "algebraic_tetrad_finite_sample_v1"
    suite_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    scenarios: tuple[TetradCalibrationScenario, ...]
    sample_sizes: tuple[int, ...] = (100, 200, 500, 1000)
    missing_rates: tuple[float, ...] = (0.0, 0.10, 0.20)
    indicator_counts: tuple[int, ...] = (4, 6, 8)
    routes: tuple[str, ...] = ("bootstrap_tetrad", "modified_bootstrap_tetrad")
    metrics: tuple[str, ...] = (
        "algebraic_tetrad_min_q",
        "algebraic_tetrad_max_abs_z",
        "algebraic_tetrad_median_delta",
        "algebraic_tetrad_violation_support",
        "algebraic_tetrad_effective_n",
    )
    calibration_notes: tuple[str, ...] = (
        "Blocker-grade severity requires continuous data, effective_n >= 500, "
        "at least 1000 bootstrap draws, and at least two corroborating tetrad violations.",
        "Ordinal/polychoric routes remain warning-capped until route-specific calibration lands.",
    )

    @model_validator(mode="after")
    def _validate_grid(self) -> TetradCalibrationBenchmarkSuite:
        if not self.scenarios:
            raise ValueError("tetrad calibration benchmark suite requires scenarios")
        if any(size < 8 for size in self.sample_sizes):
            raise ValueError("sample sizes must support at least one tetrad complete-case test")
        if any(rate < 0.0 or rate >= 1.0 for rate in self.missing_rates):
            raise ValueError("missing rates must be in [0, 1)")
        if any(count < 4 for count in self.indicator_counts):
            raise ValueError("tetrad indicator counts must be at least 4")
        return self


class TetradCalibrationCaseSpec(BaseModel):
    """One concrete benchmark cell in the tetrad calibration grid."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    scenario_kind: TetradCalibrationScenarioKind
    n_samples: int = Field(ge=8)
    n_indicators: int = Field(ge=4)
    missing_rate: float = Field(ge=0.0, lt=1.0)
    route: str = Field(min_length=1)
    expected_violation: bool
    expected_max_severity: Literal["info", "warning", "blocker"]


class TetradBlockCalibrationMetrics(BaseModel):
    """Block-level finite-sample metrics used for tetrad severity calibration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_q: float | None = Field(default=None, ge=0.0, le=1.0)
    max_abs_z: float = Field(default=0.0, ge=0.0)
    median_delta: float = Field(default=0.0, ge=0.0)
    violation_support: float = Field(default=0.0, ge=0.0, le=1.0)
    effective_n: int = Field(default=0, ge=0)
    n_violations: int = Field(default=0, ge=0)
    bootstrap_draws: int = Field(default=0, ge=0)
    continuous_only: bool = True
    route: str = "bootstrap_tetrad"
    route_calibrated: bool = True

    def metric_values(self) -> dict[str, float]:
        return {
            "algebraic_tetrad_min_q": 1.0 if self.min_q is None else float(self.min_q),
            "algebraic_tetrad_max_abs_z": float(self.max_abs_z),
            "algebraic_tetrad_median_delta": float(self.median_delta),
            "algebraic_tetrad_violation_support": float(self.violation_support),
            "algebraic_tetrad_effective_n": float(self.effective_n),
        }


class TetradSeverityThresholds(BaseModel):
    """Provisional Stage 8.2 threshold map for tetrad severity decisions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    warn_min_q_below: float = Field(default=0.10, ge=0.0, le=1.0)
    fail_min_q_below: float = Field(default=0.01, ge=0.0, le=1.0)
    warn_max_abs_z_above: float = Field(default=2.5, ge=0.0)
    fail_max_abs_z_above: float = Field(default=4.0, ge=0.0)
    warn_median_delta_above: float = Field(default=0.03, ge=0.0)
    fail_median_delta_above: float = Field(default=0.08, ge=0.0)
    warn_violation_support_above: float = Field(default=0.70, ge=0.0, le=1.0)
    fail_violation_support_above: float = Field(default=0.90, ge=0.0, le=1.0)
    warn_effective_n_below: int = Field(default=150, ge=0)
    fail_effective_n_below: int = Field(default=80, ge=0)
    blocker_min_effective_n: int = Field(default=500, ge=0)
    blocker_min_bootstrap_draws: int = Field(default=1000, ge=0)
    blocker_min_corroborating_violations: int = Field(default=2, ge=1)


class TetradThresholdRecommendation(BaseModel):
    """Registry-ready threshold recommendation for tetrad calibration metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str = Field(min_length=1)
    threshold_value: float
    direction: Literal["max", "min"]
    threshold_tier: Literal["warning", "blocker"]
    rationale: str = Field(min_length=1)


class TetradSeverityDecision(BaseModel):
    """Severity decision plus the reasons that capped or escalated it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    severity: Literal["info", "warning", "blocker"]
    warn_conditions_met: tuple[str, ...] = ()
    fail_conditions_met: tuple[str, ...] = ()
    blocker_eligibility_failures: tuple[str, ...] = ()
    metric_values: dict[str, float] = Field(default_factory=dict)
    threshold_profile: dict[str, float | int] = Field(default_factory=dict)


class TetradCalibrationRunResult(BaseModel):
    """One observed result from running a calibration case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    scenario_kind: TetradCalibrationScenarioKind
    expected_violation: bool
    severity: Literal["info", "warning", "blocker"]
    metrics: TetradBlockCalibrationMetrics


class TetradCalibrationBenchmarkReport(BaseModel):
    """Executable output of the Stage 8.2 tetrad benchmark suite."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    suite_id: str = Field(min_length=1)
    suite_version: str = Field(pattern=r"^\d+\.\d+$")
    bootstrap_draws: int = Field(ge=1)
    results: tuple[TetradCalibrationRunResult, ...]
    type_error_summary: dict[str, dict[str, float]] = Field(default_factory=dict)


PROVISIONAL_TETRAD_SEVERITY_THRESHOLDS = TetradSeverityThresholds()


def default_tetrad_calibration_benchmark_suite() -> TetradCalibrationBenchmarkSuite:
    """Return the Stage 8.2 tetrad benchmark grid specification."""

    return TetradCalibrationBenchmarkSuite(
        scenarios=(
            TetradCalibrationScenario(
                scenario_id="exact_null_one_factor_gaussian",
                kind=TetradCalibrationScenarioKind.EXACT_NULL,
                description="One-factor continuous Gaussian blocks with 4, 6, and 8 indicators.",
                expected_population_relation="exact_null",
                expected_max_severity="warning",
            ),
            TetradCalibrationScenario(
                scenario_id="robust_null_heavy_tail_contamination",
                kind=TetradCalibrationScenarioKind.ROBUST_NULL,
                description=(
                    "One-factor blocks with heavy tails, skew, contamination, and outliers."
                ),
                expected_population_relation="exact_null",
                misspecification_axes=("heavy_tails", "skew", "contamination", "outliers"),
                expected_max_severity="warning",
            ),
            TetradCalibrationScenario(
                scenario_id="approximate_null_mild_cross_loading",
                kind=TetradCalibrationScenarioKind.APPROXIMATE_NULL,
                description=(
                    "Mostly one-factor blocks with small cross-loading or residual dependence."
                ),
                expected_population_relation="approximate_null",
                misspecification_axes=("cross_loading", "correlated_residuals"),
                expected_max_severity="warning",
            ),
            TetradCalibrationScenario(
                scenario_id="ordinal_polychoric_route",
                kind=TetradCalibrationScenarioKind.ORDINAL_ROUTE,
                description="Ordinalized indicators for route-specific polychoric calibration.",
                expected_population_relation="route_specific",
                misspecification_axes=("ordinalization",),
                expected_max_severity="warning",
            ),
            TetradCalibrationScenario(
                scenario_id="moderate_two_factor_alternative",
                kind=TetradCalibrationScenarioKind.MODERATE_ALTERNATIVE,
                description=(
                    "Two-factor split with moderate cross-loading and residual correlation."
                ),
                expected_population_relation="alternative",
                misspecification_axes=("two_factor_split", "cross_loading", "residual_correlation"),
                expected_max_severity="blocker",
            ),
            TetradCalibrationScenario(
                scenario_id="strong_measurement_block_alternative",
                kind=TetradCalibrationScenarioKind.STRONG_ALTERNATIVE,
                description=(
                    "Clearly misspecified measurement block with full-rank indicator structure."
                ),
                expected_population_relation="alternative",
                misspecification_axes=("full_rank_measurement_block",),
                expected_max_severity="blocker",
            ),
        )
    )


def tetrad_threshold_recommendations(
    thresholds: TetradSeverityThresholds | None = None,
) -> tuple[TetradThresholdRecommendation, ...]:
    """Return registry-ready threshold recommendations for tetrad calibration."""

    profile = thresholds or PROVISIONAL_TETRAD_SEVERITY_THRESHOLDS
    return (
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_min_q",
            threshold_value=float(profile.warn_min_q_below),
            direction="min",
            threshold_tier="warning",
            rationale=(
                "Warning-level tetrad evidence starts at BH-adjusted q < 0.10; "
                "exact algebraic rejection remains warning-capped without effect-size "
                "and stability corroboration."
            ),
        ),
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_min_q",
            threshold_value=float(profile.fail_min_q_below),
            direction="min",
            threshold_tier="blocker",
            rationale=(
                "Blocker-grade tetrad evidence requires a strong BH-adjusted q-value "
                "plus finite-sample severity gates."
            ),
        ),
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_max_abs_z",
            threshold_value=float(profile.warn_max_abs_z_above),
            direction="max",
            threshold_tier="warning",
            rationale="Warning-level standardized tetrad deviation threshold.",
        ),
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_max_abs_z",
            threshold_value=float(profile.fail_max_abs_z_above),
            direction="max",
            threshold_tier="blocker",
            rationale="Blocker-grade standardized tetrad deviation threshold.",
        ),
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_median_delta",
            threshold_value=float(profile.warn_median_delta_above),
            direction="max",
            threshold_tier="warning",
            rationale="Approximate-fit tetrad effect-size warning threshold.",
        ),
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_median_delta",
            threshold_value=float(profile.fail_median_delta_above),
            direction="max",
            threshold_tier="blocker",
            rationale="Approximate-fit tetrad effect-size blocker threshold.",
        ),
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_violation_support",
            threshold_value=float(profile.warn_violation_support_above),
            direction="max",
            threshold_tier="warning",
            rationale="Warning threshold for bootstrap sign-stability support.",
        ),
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_violation_support",
            threshold_value=float(profile.fail_violation_support_above),
            direction="max",
            threshold_tier="blocker",
            rationale="Blocker threshold for bootstrap sign-stability support.",
        ),
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_effective_n",
            threshold_value=float(profile.warn_effective_n_below),
            direction="min",
            threshold_tier="warning",
            rationale="Below 150 complete cases, tetrad evidence should be downgraded.",
        ),
        TetradThresholdRecommendation(
            metric_name="algebraic_tetrad_effective_n",
            threshold_value=float(profile.fail_effective_n_below),
            direction="min",
            threshold_tier="blocker",
            rationale="Below 80 complete cases, tetrad calibration is screening-only.",
        ),
    )


def iter_tetrad_calibration_cases(
    suite: TetradCalibrationBenchmarkSuite | None = None,
) -> tuple[TetradCalibrationCaseSpec, ...]:
    """Materialize the benchmark grid as deterministic case specs."""

    resolved_suite = suite or default_tetrad_calibration_benchmark_suite()
    cases: list[TetradCalibrationCaseSpec] = []
    for scenario, n_samples, n_indicators, missing_rate, route in product(
        resolved_suite.scenarios,
        resolved_suite.sample_sizes,
        resolved_suite.indicator_counts,
        resolved_suite.missing_rates,
        resolved_suite.routes,
    ):
        case_id = (
            f"{scenario.kind.value}:n={n_samples}:p={n_indicators}:"
            f"missing={missing_rate:.2f}:route={route}"
        )
        cases.append(
            TetradCalibrationCaseSpec(
                case_id=case_id,
                scenario_id=scenario.scenario_id,
                scenario_kind=scenario.kind,
                n_samples=n_samples,
                n_indicators=n_indicators,
                missing_rate=missing_rate,
                route=route,
                expected_violation=scenario.expected_violation,
                expected_max_severity=scenario.expected_max_severity,
            )
        )
    return tuple(cases)


def generate_tetrad_calibration_dataset(
    *,
    scenario_kind: TetradCalibrationScenarioKind | str,
    n_samples: int,
    n_indicators: int = 4,
    missing_rate: float = 0.0,
    seed: int = 0,
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    """Generate one synthetic tetrad calibration dataset.

    The generator is intentionally compact and deterministic.  It is for
    benchmark calibration, not for production discovery.
    """

    kind = (
        scenario_kind
        if isinstance(scenario_kind, TetradCalibrationScenarioKind)
        else TetradCalibrationScenarioKind(str(scenario_kind))
    )
    if n_samples < 8:
        raise ValueError("n_samples must be at least 8")
    if n_indicators < 4:
        raise ValueError("n_indicators must be at least 4")
    if missing_rate < 0.0 or missing_rate >= 1.0:
        raise ValueError("missing_rate must be in [0, 1)")

    rng = np.random.default_rng(seed)
    names = [f"X{i}" for i in range(1, n_indicators + 1)]
    loadings = np.linspace(0.70, 1.10, n_indicators)
    noise_scale = 0.22

    if kind is TetradCalibrationScenarioKind.EXACT_NULL:
        latent = rng.normal(0.0, 1.0, size=n_samples)
        noise = rng.normal(0.0, noise_scale, size=(n_samples, n_indicators))
        data = latent[:, None] * loadings[None, :] + noise
    elif kind is TetradCalibrationScenarioKind.ROBUST_NULL:
        latent = rng.standard_t(df=3, size=n_samples)
        skew_component = rng.exponential(0.35, size=(n_samples, n_indicators)) - 0.35
        noise = rng.standard_t(df=4, size=(n_samples, n_indicators)) * noise_scale
        data = latent[:, None] * loadings[None, :] + noise + 0.12 * skew_component
        n_contaminated = max(1, round(0.05 * n_samples))
        contaminated_rows = rng.choice(n_samples, size=n_contaminated, replace=False)
        data[contaminated_rows] += rng.normal(0.0, 1.5, size=(n_contaminated, n_indicators))
    elif kind is TetradCalibrationScenarioKind.APPROXIMATE_NULL:
        latent = rng.normal(0.0, 1.0, size=n_samples)
        weak_factor = rng.normal(0.0, 1.0, size=n_samples)
        shared_residual = rng.normal(0.0, 1.0, size=n_samples)
        noise = rng.normal(0.0, noise_scale, size=(n_samples, n_indicators))
        data = latent[:, None] * loadings[None, :] + noise
        data[:, n_indicators // 2 :] += 0.08 * weak_factor[:, None]
        data[:, :2] += 0.06 * shared_residual[:, None]
    elif kind is TetradCalibrationScenarioKind.ORDINAL_ROUTE:
        latent = rng.normal(0.0, 1.0, size=n_samples)
        noise = rng.normal(0.0, noise_scale, size=(n_samples, n_indicators))
        continuous = latent[:, None] * loadings[None, :] + noise
        data = np.zeros_like(continuous)
        for idx in range(n_indicators):
            cuts = np.quantile(continuous[:, idx], [0.25, 0.50, 0.75])
            data[:, idx] = np.digitize(continuous[:, idx], cuts).astype(float)
    elif kind is TetradCalibrationScenarioKind.MODERATE_ALTERNATIVE:
        latent_a = rng.normal(0.0, 1.0, size=n_samples)
        latent_b = rng.normal(0.0, 1.0, size=n_samples)
        noise = rng.normal(0.0, noise_scale, size=(n_samples, n_indicators))
        split = max(2, n_indicators // 2)
        data = np.empty((n_samples, n_indicators), dtype=float)
        data[:, :split] = latent_a[:, None] * loadings[:split][None, :]
        data[:, split:] = latent_b[:, None] * loadings[split:][None, :]
        data[:, 1::2] += 0.25 * latent_b[:, None]
        data += noise
        data[:, :2] += 0.12 * rng.normal(0.0, 1.0, size=(n_samples, 1))
    else:
        factors = rng.normal(0.0, 1.0, size=(n_samples, min(n_indicators, 4)))
        mixing = rng.normal(0.0, 0.70, size=(factors.shape[1], n_indicators))
        noise = rng.normal(0.0, 0.18, size=(n_samples, n_indicators))
        data = factors @ mixing + noise

    if missing_rate > 0.0:
        missing = rng.random(size=data.shape) < missing_rate
        data = data.copy()
        data[missing] = np.nan

    metadata = {
        "scenario_kind": kind.value,
        "n_samples": int(n_samples),
        "n_indicators": int(n_indicators),
        "missing_rate": float(missing_rate),
        "seed": int(seed),
    }
    return data.astype(float), names, metadata


def _covariance(matrix: np.ndarray) -> np.ndarray:
    centered = np.asarray(matrix, dtype=float) - np.mean(matrix, axis=0, keepdims=True)
    return np.cov(centered, rowvar=False, ddof=1)


def _tetrad_pairings() -> tuple[
    tuple[
        str,
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
    ],
    ...,
]:
    return (
        ("ab_cd_vs_ac_bd", ((0, 1), (2, 3)), ((0, 2), (1, 3))),
        ("ab_cd_vs_ad_bc", ((0, 1), (2, 3)), ((0, 3), (1, 2))),
        ("ac_bd_vs_ad_bc", ((0, 2), (1, 3)), ((0, 3), (1, 2))),
    )


def _tetrad_value(
    matrix: np.ndarray,
    *,
    left_pairs: tuple[tuple[int, int], tuple[int, int]],
    right_pairs: tuple[tuple[int, int], tuple[int, int]],
) -> float:
    cov = _covariance(matrix)
    return float(
        cov[left_pairs[0]] * cov[left_pairs[1]]
        - cov[right_pairs[0]] * cov[right_pairs[1]]
    )


def _tetrad_delta(
    matrix: np.ndarray,
    *,
    observed: float,
    left_pairs: tuple[tuple[int, int], tuple[int, int]],
    right_pairs: tuple[tuple[int, int], tuple[int, int]],
) -> float:
    cov = _covariance(matrix)
    left_scale = float(abs(cov[left_pairs[0]] * cov[left_pairs[1]]))
    right_scale = float(abs(cov[right_pairs[0]] * cov[right_pairs[1]]))
    denominator = max(left_scale, right_scale, 1e-12)
    return float(abs(observed) / denominator)


def _complete_case_mask(columns: list[np.ndarray]) -> np.ndarray:
    if not columns:
        raise ValueError("at least one column is required")
    mask = np.ones(len(columns[0]), dtype=bool)
    for column in columns:
        arr = np.asarray(column, dtype=float).reshape(-1)
        if len(arr) != len(mask):
            raise ValueError("all columns must have the same length")
        mask &= np.isfinite(arr)
    return mask


def _bootstrap_resample(*, data: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    if data.shape[0] == 0:
        return data
    indices = rng.integers(0, data.shape[0], size=data.shape[0])
    return data[indices]


def _bh_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    n = len(p_values)
    order = np.argsort(np.asarray(p_values, dtype=float))
    adjusted = np.empty(n, dtype=float)
    running = 1.0
    for rank in range(n - 1, -1, -1):
        idx = int(order[rank])
        raw = float(p_values[idx])
        candidate = min(1.0, raw * n / float(rank + 1))
        running = min(running, candidate)
        adjusted[idx] = running
    return [float(value) for value in adjusted]


def _is_continuous_only(data: np.ndarray) -> bool:
    for idx in range(data.shape[1]):
        values = data[:, idx]
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return False
        unique = np.unique(finite)
        if unique.size <= 12 and np.allclose(unique, np.round(unique)):
            return False
    return True


def run_tetrad_calibration_case(
    case: TetradCalibrationCaseSpec,
    *,
    seed: int = 0,
    bootstrap_draws: int = 2000,
) -> TetradCalibrationRunResult:
    """Run one synthetic Stage 8.2 benchmark case and return calibrated metrics."""

    data, variable_names, _ = generate_tetrad_calibration_dataset(
        scenario_kind=case.scenario_kind,
        n_samples=case.n_samples,
        n_indicators=case.n_indicators,
        missing_rate=case.missing_rate,
        seed=seed,
    )
    rng = np.random.default_rng(seed + 17)
    raw_results: list[dict[str, float | bool]] = []

    for quad_indices in combinations(range(len(variable_names)), 4):
        quad_matrix = np.column_stack([data[:, idx] for idx in quad_indices])
        mask = _complete_case_mask([quad_matrix[:, idx] for idx in range(quad_matrix.shape[1])])
        quad_complete = quad_matrix[mask]
        if quad_complete.shape[0] < 8:
            continue
        for _, left_pairs, right_pairs in _tetrad_pairings():
            observed = _tetrad_value(
                quad_complete,
                left_pairs=left_pairs,
                right_pairs=right_pairs,
            )
            bootstrap_values = np.zeros(bootstrap_draws, dtype=float)
            for draw in range(bootstrap_draws):
                sampled = _bootstrap_resample(data=quad_complete, rng=rng)
                bootstrap_values[draw] = _tetrad_value(
                    sampled,
                    left_pairs=left_pairs,
                    right_pairs=right_pairs,
                )
            std = float(np.std(bootstrap_values, ddof=1))
            abs_z = (
                0.0
                if std <= 1e-12 and abs(observed) <= 1e-12
                else abs(observed) / max(std, 1e-12)
            )
            if case.route == "modified_bootstrap_tetrad":
                center = float(np.mean(bootstrap_values))
                p_value = float(
                    np.mean(np.abs(bootstrap_values - center) >= abs(float(observed) - center))
                )
                raw_reject = p_value < 0.05
            else:
                ci_lower, ci_upper = np.quantile(bootstrap_values, [0.025, 0.975])
                p_value = float(np.clip(math.erfc(abs_z / math.sqrt(2.0)), 0.0, 1.0))
                raw_reject = bool(ci_lower > 0.0 or ci_upper < 0.0)
            support = (
                0.0
                if abs(observed) <= 1e-12
                else float(np.mean((bootstrap_values * float(observed)) > 0.0))
            )
            raw_results.append(
                {
                    "p_value": float(np.clip(p_value, 0.0, 1.0)),
                    "raw_reject": raw_reject,
                    "abs_z": float(abs_z),
                    "delta": _tetrad_delta(
                        quad_complete,
                        observed=float(observed),
                        left_pairs=left_pairs,
                        right_pairs=right_pairs,
                    ),
                    "support": float(support),
                    "complete_cases": float(quad_complete.shape[0]),
                }
            )

    adjusted = _bh_adjust([float(entry["p_value"]) for entry in raw_results])
    for entry, adjusted_p in zip(raw_results, adjusted, strict=False):
        entry["adjusted_p"] = float(adjusted_p)
        entry["violation_candidate"] = bool(entry["raw_reject"] and adjusted_p < 0.05)

    complete_cases = [int(entry["complete_cases"]) for entry in raw_results]
    metrics = TetradBlockCalibrationMetrics(
        min_q=min((float(entry["adjusted_p"]) for entry in raw_results), default=1.0),
        max_abs_z=max((float(entry["abs_z"]) for entry in raw_results), default=0.0),
        median_delta=float(
            np.median([float(entry["delta"]) for entry in raw_results]) if raw_results else 0.0
        ),
        violation_support=max((float(entry["support"]) for entry in raw_results), default=0.0),
        effective_n=int(np.median(complete_cases)) if complete_cases else 0,
        n_violations=sum(1 for entry in raw_results if entry["violation_candidate"]),
        bootstrap_draws=bootstrap_draws,
        continuous_only=_is_continuous_only(data),
        route=case.route,
        route_calibrated=case.route in {"bootstrap_tetrad", "modified_bootstrap_tetrad"},
    )
    decision = decide_tetrad_severity(metrics)
    return TetradCalibrationRunResult(
        case_id=case.case_id,
        scenario_kind=case.scenario_kind,
        expected_violation=case.expected_violation,
        severity=decision.severity,
        metrics=metrics,
    )


def run_tetrad_calibration_suite(
    suite: TetradCalibrationBenchmarkSuite | None = None,
    *,
    seed: int = 0,
    bootstrap_draws: int = 2000,
    max_cases: int | None = None,
) -> TetradCalibrationBenchmarkReport:
    """Execute the Stage 8.2 benchmark grid and return Type I/II summaries."""

    resolved_suite = suite or default_tetrad_calibration_benchmark_suite()
    cases = list(iter_tetrad_calibration_cases(resolved_suite))
    if max_cases is not None:
        cases = cases[: max(0, int(max_cases))]
    results = tuple(
        run_tetrad_calibration_case(
            case,
            seed=seed + idx * 97,
            bootstrap_draws=bootstrap_draws,
        )
        for idx, case in enumerate(cases)
    )
    return TetradCalibrationBenchmarkReport(
        suite_id=resolved_suite.suite_id,
        suite_version=resolved_suite.suite_version,
        bootstrap_draws=bootstrap_draws,
        results=results,
        type_error_summary=summarize_tetrad_type_errors(results),
    )


def decide_tetrad_severity(
    metrics: TetradBlockCalibrationMetrics,
    thresholds: TetradSeverityThresholds | None = None,
) -> TetradSeverityDecision:
    """Map block-level tetrad metrics to info/warning/blocker severity."""

    profile = thresholds or PROVISIONAL_TETRAD_SEVERITY_THRESHOLDS
    metric_values = metrics.metric_values()
    threshold_profile = profile.model_dump(mode="python")
    warn_conditions: list[str] = []
    fail_conditions: list[str] = []

    if metrics.min_q is not None and metrics.min_q < profile.warn_min_q_below:
        warn_conditions.append("min_q")
    if metrics.max_abs_z > profile.warn_max_abs_z_above:
        warn_conditions.append("max_abs_z")
    if metrics.median_delta > profile.warn_median_delta_above:
        warn_conditions.append("median_delta")
    if metrics.violation_support > profile.warn_violation_support_above:
        warn_conditions.append("violation_support")
    if metrics.effective_n < profile.warn_effective_n_below:
        warn_conditions.append("effective_n_low")

    if metrics.min_q is not None and metrics.min_q < profile.fail_min_q_below:
        fail_conditions.append("min_q")
    if metrics.max_abs_z > profile.fail_max_abs_z_above:
        fail_conditions.append("max_abs_z")
    if metrics.median_delta > profile.fail_median_delta_above:
        fail_conditions.append("median_delta")
    if metrics.violation_support > profile.fail_violation_support_above:
        fail_conditions.append("violation_support")
    if metrics.effective_n < profile.fail_effective_n_below:
        fail_conditions.append("effective_n_low")

    eligibility_failures: list[str] = []
    if metrics.effective_n < profile.blocker_min_effective_n:
        eligibility_failures.append("effective_n_below_blocker_floor")
    if metrics.bootstrap_draws < profile.blocker_min_bootstrap_draws:
        eligibility_failures.append("bootstrap_draws_below_blocker_floor")
    if metrics.n_violations < profile.blocker_min_corroborating_violations:
        eligibility_failures.append("insufficient_corroborating_tetrads")
    if not metrics.continuous_only:
        eligibility_failures.append("noncontinuous_or_ordinal_route")
    if not metrics.route_calibrated:
        eligibility_failures.append("route_not_calibrated")

    core_failures = {"min_q", "max_abs_z", "median_delta", "violation_support"}
    if core_failures.issubset(set(fail_conditions)) and not eligibility_failures:
        severity: Literal["info", "warning", "blocker"] = "blocker"
    elif warn_conditions or fail_conditions:
        severity = "warning"
    else:
        severity = "info"

    if metrics.effective_n < profile.fail_effective_n_below and severity == "warning":
        severity = "info"
        eligibility_failures.append("effective_n_too_low_for_warning_escalation")

    return TetradSeverityDecision(
        severity=severity,
        warn_conditions_met=tuple(warn_conditions),
        fail_conditions_met=tuple(fail_conditions),
        blocker_eligibility_failures=tuple(eligibility_failures),
        metric_values=metric_values,
        threshold_profile=threshold_profile,
    )


def summarize_tetrad_type_errors(
    results: Iterable[TetradCalibrationRunResult],
) -> dict[str, dict[str, float]]:
    """Summarize Type I/II-style rates by scenario kind from benchmark runs."""

    grouped: dict[str, list[TetradCalibrationRunResult]] = defaultdict(list)
    for result in results:
        grouped[result.scenario_kind.value].append(result)

    summary: dict[str, dict[str, float]] = {}
    for scenario_kind, items in grouped.items():
        total = len(items)
        if total == 0:
            continue
        null_items = [item for item in items if not item.expected_violation]
        alt_items = [item for item in items if item.expected_violation]
        false_alarms = [
            item for item in null_items if item.severity in {"warning", "blocker"}
        ]
        blocker_false_alarms = [
            item for item in null_items if item.severity == "blocker"
        ]
        misses = [item for item in alt_items if item.severity == "info"]
        warning_or_blocker_hits = [
            item for item in alt_items if item.severity in {"warning", "blocker"}
        ]
        summary[scenario_kind] = {
            "n_cases": float(total),
            "false_alarm_rate": (
                len(false_alarms) / float(len(null_items)) if null_items else 0.0
            ),
            "blocker_false_alarm_rate": (
                len(blocker_false_alarms) / float(len(null_items)) if null_items else 0.0
            ),
            "miss_rate": len(misses) / float(len(alt_items)) if alt_items else 0.0,
            "warning_or_blocker_power": (
                len(warning_or_blocker_hits) / float(len(alt_items)) if alt_items else 0.0
            ),
        }
    return summary


__all__ = [
    "PROVISIONAL_TETRAD_SEVERITY_THRESHOLDS",
    "TetradBlockCalibrationMetrics",
    "TetradCalibrationBenchmarkReport",
    "TetradCalibrationBenchmarkSuite",
    "TetradCalibrationCaseSpec",
    "TetradCalibrationRunResult",
    "TetradCalibrationScenario",
    "TetradCalibrationScenarioKind",
    "TetradSeverityDecision",
    "TetradSeverityThresholds",
    "TetradThresholdRecommendation",
    "decide_tetrad_severity",
    "default_tetrad_calibration_benchmark_suite",
    "generate_tetrad_calibration_dataset",
    "iter_tetrad_calibration_cases",
    "run_tetrad_calibration_case",
    "run_tetrad_calibration_suite",
    "summarize_tetrad_type_errors",
    "tetrad_threshold_recommendations",
]
