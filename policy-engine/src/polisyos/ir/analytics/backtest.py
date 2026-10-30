"""Define historical validation reports and trust diagnostics for backtesting."""

from __future__ import annotations

import math
from collections.abc import Mapping
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics._owner_admission import (
    OwnedJSONRepresentation,
    declare_model_owner,
    owner_profile_for_spec,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef  # noqa: TC001
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import CompatibilityMode
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel, BacktestReportRef


class BiasDirection(str, Enum):
    """Direction of systematic bias detected in historical validation."""

    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class OutcomeComparison(BaseModel):
    """Comparison between predicted and observed outcomes for one metric."""

    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(min_length=1)
    y_pred: float
    y_true: float
    absolute_error: float = Field(ge=0.0)
    relative_error: float | None = Field(default=None, ge=0.0)
    within_ci: bool | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None

    @model_validator(mode="after")
    def _validate_numerics(self) -> OutcomeComparison:
        if not math.isfinite(self.y_pred):
            raise ValueError("y_pred must be finite")
        if not math.isfinite(self.y_true):
            raise ValueError("y_true must be finite")
        if not math.isfinite(self.absolute_error):
            raise ValueError("absolute_error must be finite")
        if self.relative_error is not None and not math.isfinite(self.relative_error):
            raise ValueError("relative_error must be finite when present")
        if not math.isfinite(self.y_pred - self.y_true):
            raise ValueError("prediction residual must be finite")
        if self.ci_lower is not None and not math.isfinite(self.ci_lower):
            raise ValueError("ci_lower must be finite when present")
        if self.ci_upper is not None and not math.isfinite(self.ci_upper):
            raise ValueError("ci_upper must be finite when present")
        if (
            self.ci_lower is not None
            and self.ci_upper is not None
            and self.ci_lower > self.ci_upper
        ):
            raise ValueError("ci_lower must be <= ci_upper")
        return self


class SystematicBias(BaseModel):
    """Structured bias pattern detected across backtest scenarios."""

    model_config = ConfigDict(extra="forbid")

    bias_type: str = Field(min_length=1)
    direction: BiasDirection
    magnitude: float = Field(ge=0.0)
    affected_metrics: list[str] = Field(default_factory=list)
    description: str = ""
    statistical_test: str = ""
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_magnitude(self) -> SystematicBias:
        if not math.isfinite(self.magnitude):
            raise ValueError("magnitude must be finite")
        return self


class MetricBiasDiagnostic(BaseModel):
    """One metric's residual description and exact statistical execution state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_name: str = Field(min_length=1)
    status: str = Field(pattern="^(exact_zero|available|not_computable|unavailable)$")
    n: int = Field(ge=0)
    mean_residual: float
    magnitude: float = Field(ge=0.0)
    scope: dict[str, Any] = Field(default_factory=dict)
    residual_sign: Literal["negative", "zero", "positive"]
    direction_status: Literal["not_established", "not_applicable"]
    method_id: str | None = None
    backend_id: str | None = None
    backend_version: str | None = None
    statistic: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    reason: str | None = None
    unresolved_assumptions: list[str] = Field(
        default_factory=lambda: [
            "residual_independence",
            "multiplicity_policy",
            "population_scope",
            "metric_direction",
        ]
    )

    @model_validator(mode="before")
    @classmethod
    def _retain_legacy_signed_residual(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        mean = payload.get("mean_residual")
        status = payload.get("status")
        if isinstance(mean, (int, float)) and not isinstance(mean, bool):
            if "residual_sign" not in payload:
                payload["residual_sign"] = (
                    "positive" if mean > 0 else "negative" if mean < 0 else "zero"
                )
            if "direction_status" not in payload:
                payload["direction_status"] = (
                    "not_applicable" if status == "exact_zero" else "not_established"
                )
        if "unresolved_assumptions" not in payload:
            payload["unresolved_assumptions"] = [
                "residual_independence",
                "multiplicity_policy",
                "population_scope",
                *([] if status == "exact_zero" else ["metric_direction"]),
            ]
        elif (status != "exact_zero" and isinstance(payload["unresolved_assumptions"], list)) and (
            "metric_direction" not in payload["unresolved_assumptions"]
        ):
            payload["unresolved_assumptions"] = [
                *payload["unresolved_assumptions"],
                "metric_direction",
            ]
        return payload

    @model_validator(mode="after")
    def _validate_execution_identity(self) -> MetricBiasDiagnostic:
        executed = self.status == "available"
        identity = (
            self.method_id,
            self.backend_id,
            self.backend_version,
            self.statistic,
            self.p_value,
        )
        if executed and any(value is None for value in identity):
            raise ValueError(
                "available diagnostic requires executed method, backend, statistic and p"
            )
        if executed and (
            self.method_id != "scipy.stats.ttest_1samp"
            or self.backend_id != "scipy"
            or not (self.backend_version or "").strip()
        ):
            raise ValueError(
                "available diagnostic requires the actual named SciPy execution identity"
            )
        if not executed and any(value is not None for value in identity):
            raise ValueError("non-available diagnostic cannot claim an executed statistical method")
        if self.status in {"not_computable", "unavailable"} and not self.reason:
            raise ValueError("non-executed diagnostic requires its reason")
        expected_sign = (
            "positive"
            if self.mean_residual > 0
            else "negative"
            if self.mean_residual < 0
            else "zero"
        )
        if self.residual_sign != expected_sign:
            raise ValueError("residual_sign must match the signed mean residual")
        if self.status == "exact_zero":
            if self.mean_residual != 0.0 or self.magnitude != 0.0:
                raise ValueError("exact_zero diagnostic requires zero residual and magnitude")
            if self.direction_status != "not_applicable":
                raise ValueError("exact_zero diagnostic has no directional claim")
        else:
            if self.direction_status != "not_established":
                raise ValueError("nonzero residual direction must remain not_established")
            if self.magnitude != abs(self.mean_residual):
                raise ValueError("diagnostic magnitude must equal absolute signed mean residual")
        if not math.isfinite(self.mean_residual) or not math.isfinite(self.magnitude):
            raise ValueError("diagnostic residual values must be finite")
        if self.statistic is not None and not math.isfinite(self.statistic):
            raise ValueError("diagnostic statistic must be finite")
        return self


class BacktestScenario(BaseModel):
    """Historical validation scenario with per-metric forecast comparisons."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    scenario_label: str = Field(min_length=1)
    jurisdiction: str = ""
    intervention_date: str = ""
    data_source: str = ""

    outcome_comparisons: list[OutcomeComparison] = Field(default_factory=list)
    rmse: float | None = Field(default=None, ge=0.0)
    mae: float | None = Field(default=None, ge=0.0)
    mape: float | None = Field(default=None, ge=0.0)
    coverage_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    requested_count: int = Field(default=0, ge=0)
    compared_count: int = Field(default=0, ge=0)
    missing_count: int = Field(default=0, ge=0)
    invalid_count: int = Field(default=0, ge=0)
    missing_cells: list[tuple[str, int]] = Field(default_factory=list)
    invalid_cells: list[tuple[str, int]] = Field(default_factory=list)
    interval_requested_count: int = Field(default=0, ge=0)
    interval_available_count: int = Field(default=0, ge=0)
    interval_evaluated_count: int = Field(default=0, ge=0)
    interval_hit_count: int = Field(default=0, ge=0)
    interval_availability: float | None = Field(default=None, ge=0.0, le=1.0)
    interval_hit_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    nominal_confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    interval_type: str | None = Field(default=None, min_length=1)
    squared_error_sum: float | None = Field(default=None, ge=0.0)
    absolute_error_sum: float | None = Field(default=None, ge=0.0)
    percentage_error_sum: float | None = Field(default=None, ge=0.0)
    percentage_error_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_metrics(self) -> BacktestScenario:
        if self.requested_count > 0:
            counted = self.compared_count + self.missing_count + self.invalid_count
            if counted != self.requested_count:
                raise ValueError(
                    "requested_count must equal compared_count + missing_count + invalid_count"
                )
            if len(self.missing_cells) != self.missing_count:
                raise ValueError("missing_cells must match missing_count")
            if len(self.invalid_cells) != self.invalid_count:
                raise ValueError("invalid_cells must match invalid_count")
        if self.interval_available_count > self.interval_requested_count:
            raise ValueError("interval_available_count cannot exceed interval_requested_count")
        if self.interval_evaluated_count > self.interval_available_count:
            raise ValueError("interval_evaluated_count cannot exceed interval_available_count")
        if self.interval_hit_count > self.interval_evaluated_count:
            raise ValueError("interval_hit_count cannot exceed interval_evaluated_count")
        if self.percentage_error_count == 0 and self.percentage_error_sum not in (None, 0.0):
            raise ValueError("percentage_error_sum requires percentage_error_count")
        for value, name in (
            (self.rmse, "rmse"),
            (self.mae, "mae"),
            (self.mape, "mape"),
            (self.coverage_probability, "coverage_probability"),
            (self.interval_availability, "interval_availability"),
            (self.interval_hit_rate, "interval_hit_rate"),
            (self.nominal_confidence_level, "nominal_confidence_level"),
            (self.squared_error_sum, "squared_error_sum"),
            (self.absolute_error_sum, "absolute_error_sum"),
            (self.percentage_error_sum, "percentage_error_sum"),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        return self


class BacktestReport(BaseModel):
    """Summarize historical validation quality and trust diagnostics for one model/policy pair.

    Downstream trust governance reads ``trust_eligible``, ``trust_score``, and
    ``detected_biases`` to decide whether a model-policy combination can be
    promoted or should be degraded before decision support.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    report_id: str = Field(min_length=1)

    model_spec_ref: str | None = None
    policy_spec_ref: str | None = None
    historical_data_ref: str | None = None
    backtest_config_ref: str | None = None

    scenarios: list[BacktestScenario] = Field(default_factory=list)

    overall_rmse: float | None = Field(default=None, ge=0.0)
    overall_macro_rmse: float | None = Field(default=None, ge=0.0)
    overall_mae: float | None = Field(default=None, ge=0.0)
    overall_mape: float | None = Field(default=None, ge=0.0)
    overall_coverage_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    overall_r_squared: float | None = None
    n_scenarios: int = Field(default=0, ge=0)
    n_metrics_evaluated: int = Field(default=0, ge=0)
    aggregation_policy: str | None = Field(default=None, min_length=1)

    detected_biases: list[SystematicBias] = Field(default_factory=list)
    metric_diagnostics: list[MetricBiasDiagnostic] = Field(default_factory=list)
    overall_bias_direction: BiasDirection = BiasDirection.NEUTRAL

    prediction_mode_requested: str | None = None
    prediction_mode_effective: str | None = None
    degraded: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    trust_eligible: bool = True
    trust_score: float | None = Field(default=None, ge=0.0, le=1.0)
    trust_grade: str | None = None

    cas_artifact_id: str | None = None
    decision_packet_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_counts(self) -> BacktestReport:
        if self.n_scenarios == 0 and self.scenarios:
            self.n_scenarios = len(self.scenarios)
        if self.n_scenarios != len(self.scenarios):
            raise ValueError("n_scenarios must match scenarios length")
        for value, name in (
            (self.overall_rmse, "overall_rmse"),
            (self.overall_macro_rmse, "overall_macro_rmse"),
            (self.overall_mae, "overall_mae"),
            (self.overall_mape, "overall_mape"),
            (self.overall_coverage_probability, "overall_coverage_probability"),
            (self.overall_r_squared, "overall_r_squared"),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if "metric_diagnostics" in self.model_fields_set:
            self._assert_metric_diagnostics_match_scenarios()
        else:
            self._refuse_unbound_legacy_trust()
        if any(item.direction_status == "not_established" for item in self.metric_diagnostics):
            if self.overall_bias_direction is not BiasDirection.UNKNOWN:
                raise ValueError("unresolved metric direction requires unknown report direction")
            if (
                not self.degraded
                or self.trust_eligible
                or self.trust_score is not None
                or self.trust_grade is not None
            ):
                raise ValueError("unresolved metric direction requires degraded trust refusal")
            if any(
                item.direction in {BiasDirection.OPTIMISTIC, BiasDirection.PESSIMISTIC}
                for item in self.detected_biases
            ):
                raise ValueError(
                    "unresolved metric direction cannot claim optimistic or pessimistic bias"
                )
        return self

    @staticmethod
    def _close(actual: float, expected: float) -> bool:
        return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12)

    def _assert_metric_diagnostics_match_scenarios(self) -> None:
        """Reconcile every persisted diagnostic and aggregate against source rows."""
        errors_by_metric: dict[str, list[float]] = {}
        total_absolute_error = 0.0
        total_squared_error = 0.0
        total_count = 0
        total_percentage_error = 0.0
        total_percentage_count = 0
        total_interval_evaluated = 0
        total_interval_hits = 0
        coverage_values: list[float] = []
        interval_contracts: list[dict[str, Any]] = []
        for scenario in self.scenarios:
            scenario_errors: list[float] = []
            percentage_errors: list[float] = []
            interval_available = 0
            interval_hits = 0
            if scenario.interval_requested_count not in (0, scenario.requested_count):
                raise ValueError("interval request count must cover all rows or none")
            if scenario.compared_count != len(scenario.outcome_comparisons):
                raise ValueError("scenario compared_count must match actual outcome rows")
            for comparison in scenario.outcome_comparisons:
                residual = comparison.y_pred - comparison.y_true
                if not math.isfinite(residual) or not math.isfinite(comparison.absolute_error):
                    raise ValueError("source residual and absolute error must be finite")
                absolute_error = abs(residual)
                if not self._close(comparison.absolute_error, absolute_error):
                    raise ValueError("source outcome absolute_error does not match its residual")
                relative = (
                    absolute_error / abs(comparison.y_true)
                    if abs(comparison.y_true) > 1e-12
                    else None
                )
                percentage = None if relative is None else relative * 100.0
                if percentage is not None and not math.isfinite(percentage):
                    relative = None
                    percentage = None
                if comparison.relative_error is not None and not math.isfinite(
                    comparison.relative_error
                ):
                    raise ValueError("source relative_error must be finite")
                if relative is None:
                    if comparison.relative_error is not None:
                        raise ValueError(
                            "source relative_error does not reconcile with outcome rows"
                        )
                elif comparison.relative_error is None or not self._close(
                    comparison.relative_error, relative
                ):
                    raise ValueError("source relative_error does not reconcile with outcome rows")
                if percentage is not None:
                    percentage_errors.append(percentage)
                has_lower = comparison.ci_lower is not None
                has_upper = comparison.ci_upper is not None
                if has_lower != has_upper:
                    raise ValueError("source interval bounds must be supplied as a complete pair")
                expected_within = None
                if comparison.ci_lower is not None and comparison.ci_upper is not None:
                    interval_available += 1
                    expected_within = bool(
                        comparison.ci_lower <= comparison.y_true <= comparison.ci_upper
                    )
                    interval_hits += int(expected_within)
                if comparison.within_ci is not expected_within:
                    raise ValueError("source outcome within_ci does not match interval bounds")
                errors_by_metric.setdefault(comparison.metric_name, []).append(residual)
                scenario_errors.append(residual)
            expected_pct_sum = math.fsum(percentage_errors)
            expected_pct_count = len(percentage_errors)
            if scenario.percentage_error_count != expected_pct_count:
                raise ValueError(
                    "scenario percentage-error count does not reconcile with outcome rows"
                )
            if expected_pct_count:
                if scenario.percentage_error_sum is None or not self._close(
                    scenario.percentage_error_sum, expected_pct_sum
                ):
                    raise ValueError(
                        "scenario percentage-error sum does not reconcile with outcome rows"
                    )
                expected_mape = expected_pct_sum / expected_pct_count
            else:
                if scenario.percentage_error_sum not in (None, 0.0):
                    raise ValueError(
                        "scenario percentage-error sum requires source relative errors"
                    )
                expected_mape = None
            if expected_mape is None:
                if scenario.mape is not None:
                    raise ValueError("scenario MAPE does not reconcile with source relative errors")
            elif scenario.mape is None or not self._close(scenario.mape, expected_mape):
                raise ValueError("scenario MAPE does not reconcile with source relative errors")
            total_percentage_error += expected_pct_sum
            total_percentage_count += expected_pct_count
            if scenario.interval_requested_count == 0 and interval_available:
                raise ValueError("source intervals require a declared interval request")
            expected_availability = (
                interval_available / scenario.interval_requested_count
                if scenario.interval_requested_count
                else None
            )
            expected_coverage = interval_hits / interval_available if interval_available else None
            if (
                scenario.interval_available_count != interval_available
                or scenario.interval_evaluated_count != interval_available
            ):
                raise ValueError("scenario interval counts do not reconcile with source bounds")
            if scenario.interval_hit_count != interval_hits:
                raise ValueError(
                    "scenario interval hit count does not reconcile with source bounds"
                )
            if expected_availability is None:
                if scenario.interval_availability is not None:
                    raise ValueError(
                        "scenario interval availability does not reconcile with source bounds"
                    )
            elif scenario.interval_availability is None or not self._close(
                scenario.interval_availability, expected_availability
            ):
                raise ValueError(
                    "scenario interval availability does not reconcile with source bounds"
                )
            if expected_coverage is None:
                if (
                    scenario.coverage_probability is not None
                    or scenario.interval_hit_rate is not None
                ):
                    raise ValueError(
                        "scenario coverage does not reconcile with source interval bounds"
                    )
            elif (
                scenario.coverage_probability is None
                or scenario.interval_hit_rate is None
                or not self._close(scenario.coverage_probability, expected_coverage)
                or not self._close(scenario.interval_hit_rate, expected_coverage)
            ):
                raise ValueError("scenario coverage does not reconcile with source interval bounds")
            if expected_coverage is not None:
                coverage_values.append(expected_coverage)
            total_interval_evaluated += interval_available
            total_interval_hits += interval_hits
            if scenario.nominal_confidence_level is not None or scenario.interval_type is not None:
                interval_contracts.append(
                    {
                        "scenario_id": scenario.scenario_id,
                        "nominal_confidence_level": scenario.nominal_confidence_level,
                        "interval_type": scenario.interval_type,
                        "interval_requested_count": scenario.interval_requested_count,
                        "interval_available_count": scenario.interval_available_count,
                        "interval_evaluated_count": scenario.interval_evaluated_count,
                        "interval_hit_count": scenario.interval_hit_count,
                    }
                )
            if scenario_errors:
                scenario_abs = math.fsum(abs(value) for value in scenario_errors)
                scenario_sq = math.fsum(value * value for value in scenario_errors)
                scenario_mae = scenario_abs / len(scenario_errors)
                scenario_rmse = math.sqrt(scenario_sq / len(scenario_errors))
                if scenario.mae is None or not self._close(scenario.mae, scenario_mae):
                    raise ValueError("scenario MAE does not reconcile with actual outcome rows")
                if scenario.rmse is None or not self._close(scenario.rmse, scenario_rmse):
                    raise ValueError("scenario RMSE does not reconcile with actual outcome rows")
                if scenario.absolute_error_sum is None or not self._close(
                    scenario.absolute_error_sum, scenario_abs
                ):
                    raise ValueError(
                        "scenario absolute-error sum does not reconcile with actual outcome rows"
                    )
                if scenario.squared_error_sum is None or not self._close(
                    scenario.squared_error_sum, scenario_sq
                ):
                    raise ValueError(
                        "scenario squared-error sum does not reconcile with actual outcome rows"
                    )
                total_absolute_error += scenario_abs
                total_squared_error += scenario_sq
                total_count += len(scenario_errors)
        recorded_intervals = self.metadata.get("interval_contracts")
        if interval_contracts:
            if recorded_intervals != interval_contracts:
                raise ValueError(
                    "interval contracts do not reconcile with scenario source declarations"
                )
        elif recorded_intervals not in (None, []):
            raise ValueError("interval contracts have no matching source scenarios")
        if self.n_metrics_evaluated != total_count:
            raise ValueError("n_metrics_evaluated must match the complete actual outcome-row set")
        if total_count:
            expected_mae = total_absolute_error / total_count
            expected_rmse = math.sqrt(total_squared_error / total_count)
            if self.overall_mae is None or not self._close(self.overall_mae, expected_mae):
                raise ValueError("overall MAE does not reconcile with actual outcome rows")
            if self.overall_rmse is None or not self._close(self.overall_rmse, expected_rmse):
                raise ValueError("overall RMSE does not reconcile with actual outcome rows")
        expected_mape = (
            total_percentage_error / total_percentage_count if total_percentage_count else None
        )
        if expected_mape is None:
            if self.overall_mape is not None:
                raise ValueError("overall MAPE does not reconcile with actual outcome rows")
        elif self.overall_mape is None or not self._close(self.overall_mape, expected_mape):
            raise ValueError("overall MAPE does not reconcile with actual outcome rows")
        expected_coverage = (
            total_interval_hits / total_interval_evaluated
            if total_interval_evaluated
            else (math.fsum(coverage_values) / len(coverage_values) if coverage_values else None)
        )
        if expected_coverage is None:
            if self.overall_coverage_probability is not None:
                raise ValueError("overall coverage does not reconcile with actual interval rows")
        elif self.overall_coverage_probability is None or not self._close(
            self.overall_coverage_probability, expected_coverage
        ):
            raise ValueError("overall coverage does not reconcile with actual interval rows")

        diagnostics = self.metric_diagnostics
        names = [item.metric_name for item in diagnostics]
        if len(names) != len(set(names)) or set(names) != set(errors_by_metric):
            raise ValueError(
                "metric diagnostics must match the complete actual metric set exactly once"
            )
        for diagnostic in diagnostics:
            values = errors_by_metric[diagnostic.metric_name]
            n = len(values)
            mean = math.fsum(values) / n
            magnitude = abs(mean)
            exact_zero = all(value == 0.0 for value in values)
            expected_sign = "positive" if mean > 0 else "negative" if mean < 0 else "zero"
            expected_direction = "not_applicable" if exact_zero else "not_established"
            if diagnostic.n != n or not self._close(diagnostic.mean_residual, mean):
                raise ValueError(
                    "metric diagnostic does not reconcile source count/mean: "
                    f"{diagnostic.metric_name}"
                )
            if not self._close(diagnostic.magnitude, magnitude):
                raise ValueError(
                    "metric diagnostic does not reconcile source magnitude: "
                    f"{diagnostic.metric_name}"
                )
            if (
                diagnostic.residual_sign != expected_sign
                or diagnostic.direction_status != expected_direction
            ):
                raise ValueError(
                    "metric diagnostic direction does not reconcile with source rows: "
                    f"{diagnostic.metric_name}"
                )
            if diagnostic.scope != self._expected_metric_scope(diagnostic.metric_name):
                raise ValueError(
                    "metric diagnostic scope does not reconcile with source scenarios: "
                    f"{diagnostic.metric_name}"
                )
            expected_assumptions = [
                "residual_independence",
                "multiplicity_policy",
                "population_scope",
            ]
            if not exact_zero:
                expected_assumptions.append("metric_direction")
            if diagnostic.unresolved_assumptions != expected_assumptions:
                raise ValueError(
                    "metric diagnostic assumptions do not match source status: "
                    f"{diagnostic.metric_name}"
                )
            if exact_zero:
                if diagnostic.status != "exact_zero" or diagnostic.reason is not None:
                    raise ValueError(
                        "exact-zero diagnostic status does not match source rows: "
                        f"{diagnostic.metric_name}"
                    )
                continue
            if diagnostic.status == "exact_zero":
                raise ValueError(
                    "nonzero source residuals cannot be marked exact_zero: "
                    f"{diagnostic.metric_name}"
                )
            sample_std = (
                math.sqrt(math.fsum((value - mean) ** 2 for value in values) / (n - 1))
                if n > 1
                else 0.0
            )
            if n < 3:
                if (
                    diagnostic.status != "not_computable"
                    or diagnostic.reason != "insufficient_observations"
                ):
                    raise ValueError(
                        "metric diagnostic availability does not match source count: "
                        f"{diagnostic.metric_name}"
                    )
            elif sample_std <= 1e-12:
                if diagnostic.status != "not_computable" or diagnostic.reason != "zero_variance":
                    raise ValueError(
                        "metric diagnostic availability does not match source variance: "
                        f"{diagnostic.metric_name}"
                    )
            elif diagnostic.status == "not_computable":
                raise ValueError(
                    "variable source residuals cannot be marked not_computable: "
                    f"{diagnostic.metric_name}"
                )
            elif diagnostic.status == "available":
                expected_statistic = mean / (sample_std / math.sqrt(n))
                if (
                    diagnostic.method_id != "scipy.stats.ttest_1samp"
                    or diagnostic.backend_id != "scipy"
                    or not diagnostic.backend_version
                    or diagnostic.statistic is None
                    or not self._close(diagnostic.statistic, expected_statistic)
                    or diagnostic.p_value is None
                    or not math.isfinite(diagnostic.p_value)
                    or not 0.0 <= diagnostic.p_value <= 1.0
                    or diagnostic.reason is not None
                ):
                    raise ValueError(
                        "executed diagnostic does not reconcile to source t-statistic: "
                        f"{diagnostic.metric_name}"
                    )
            elif diagnostic.status == "unavailable":
                if diagnostic.reason is None or not diagnostic.reason.startswith(
                    "scipy_ttest_1samp_"
                ):
                    raise ValueError(
                        "unavailable diagnostic requires a typed SciPy execution reason: "
                        f"{diagnostic.metric_name}"
                    )
            else:
                raise ValueError(
                    "unrecognized diagnostic availability for source metric: "
                    f"{diagnostic.metric_name}"
                )

    def _expected_metric_scope(self, metric_name: str) -> dict[str, Any]:
        matching = [
            scenario
            for scenario in self.scenarios
            if any(item.metric_name == metric_name for item in scenario.outcome_comparisons)
        ]
        return {
            "scenario_ids": [scenario.scenario_id for scenario in matching],
            "holdout_windows": sorted(
                {
                    str(window)
                    for scenario in matching
                    for window in scenario.metadata.get("holdout_windows", [])
                }
            ),
            "selected_training_roles": sorted(
                {
                    str(scenario.metadata["selected_training_role"])
                    for scenario in matching
                    if scenario.metadata.get("selected_training_role")
                }
            ),
            "selected_validation_roles": sorted(
                {
                    str(scenario.metadata["selected_validation_role"])
                    for scenario in matching
                    if scenario.metadata.get("selected_validation_role")
                }
            ),
            "selected_holdout_roles": sorted(
                {
                    str(scenario.metadata["selected_holdout_role"])
                    for scenario in matching
                    if scenario.metadata.get("selected_holdout_role")
                }
            ),
        }

    def metric_diagnostics_are_source_bound(self) -> bool:
        """Return whether the full diagnostic set reconciles with persisted source rows."""
        if "metric_diagnostics" not in self.model_fields_set:
            return False
        try:
            self._assert_metric_diagnostics_match_scenarios()
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
            return False
        return True

    def has_source_bound_exact_zero_metrics(self) -> bool:
        """Report source-bound exact-zero rows without admitting score markers."""
        return bool(
            not self.degraded
            and self.overall_bias_direction is BiasDirection.NEUTRAL
            and not self.detected_biases
            and self.scenarios
            and self.metric_diagnostics
            and self.metric_diagnostics_are_source_bound()
            and all(item.status == "exact_zero" for item in self.metric_diagnostics)
            and all(
                s.requested_count > 0
                and s.compared_count == s.requested_count
                and s.missing_count == 0
                and s.invalid_count == 0
                and len(s.outcome_comparisons) == s.compared_count
                and s.mae is not None
                and s.rmse is not None
                for s in self.scenarios
            )
        )

    def _refuse_unbound_legacy_trust(self) -> None:
        """Keep legacy reports readable while removing trust that lacks source binding."""
        self.trust_eligible = False
        self.trust_score = None
        self.trust_grade = None
        self.degraded = True
        reason = "metric_diagnostics_not_source_bound"
        if reason not in self.degraded_reasons:
            self.degraded_reasons.append(reason)


_BACKTEST_REPORT_OWNER = declare_model_owner(
    BacktestReport,
    contract_id="ir.analytics.ir_backtest_report.owner.v1",
    dto_fqn="polisyos.ir.analytics.backtest.BacktestReport",
    abi_key="ir.analytics.ir_backtest_report.owner.v1.dto-abi.v1",
    registry_key="ir.backtest_report",
    kind="ir.backtest_report",
    media_type="application/json",
    purpose="backtest_report",
    policy_revision="ir.analytics.ir_backtest_report.owner.v1.admission.v1",
    accepted_wire_policies=(("ir.analytics.ir_backtest_report.wire-law", "1"),),
    payload_version_field="schema_version",
    validate_profile=owner_profile_for_spec(
        CanonSpec(forbid_floats=False),
        profile_ref=None,
    ),
    representations=(
        OwnedJSONRepresentation(
            schema_name="ir.backtest_report",
            schema_version="1.0",
            payload_version="1.0",
            wire_policy_ref="ir.analytics.ir_backtest_report.wire-law",
            wire_policy_revision="1",
            profile_ref=None,
            compatibility=CompatibilityMode.NONE,
            notes=("Exact owner-bound analytics tuple; unknown history remains opaque.",),
            readable=True,
            writable=True,
            current=True,
            default_write=True,
            readable_from=(),
        ),
    ),
)


def persist_backtest_report(
    store: ArtifactStore,
    report: BacktestReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.backtest_report",
    schema_version: str = "1.0",
) -> BacktestReportRef:
    """Persist a backtest report through its exact typed owner."""
    payload = report.model_dump(mode="python")
    if "metric_diagnostics" not in report.model_fields_set:
        payload.pop("metric_diagnostics", None)
    verified = BacktestReport.model_validate(payload)
    payload = verified.model_dump(mode="json")
    if "metric_diagnostics" not in verified.model_fields_set:
        payload.pop("metric_diagnostics", None)
    ref = _put_owned_json_artifact(
        store,
        payload,
        owner=_BACKTEST_REPORT_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return BacktestReportRef.model_validate(ref)


class NativeBacktestVerificationRequiredError(ValueError):
    """A selected native report needs its higher-layer trajectory verifier."""


def load_backtest_report_candidate(store: ArtifactStore, ref: BacktestReportRef) -> BacktestReport:
    """Load owner-admitted report bytes for verification, without native authority.

    This candidate read alone does not establish native prediction, workflow, or
    cohort consistency. Consumers must use the native verifier before use.
    """
    return _get_owned_json_artifact(store, ref, owner=_BACKTEST_REPORT_OWNER)


def load_backtest_report(store: ArtifactStore, ref: BacktestReportRef) -> BacktestReport:
    """Load a report, refusing native sources without higher-layer verification."""
    report = load_backtest_report_candidate(store, ref)
    native_fields = {
        "native_forecast_ref",
        "native_request_ref",
        "native_forecast_purpose",
        "native_workflow_status",
        "native_workflow_failures",
        "native_foundry_step_count",
        "native_randomness_scope",
        "native_limitations",
        "native_requested_replicas",
        "native_started_replicas",
        "native_requested_count_status",
        "native_started_count_status",
    }
    if (
        any(native_fields.intersection(item.metadata) for item in report.scenarios)
        or report.prediction_mode_effective in {"scientist_candidate", "scientist_unavailable"}
        or any(
            item.metadata.get("prediction_source_effective")
            in {"scientist_candidate", "scientist_unavailable"}
            for item in report.scenarios
        )
        or any(
            reason.startswith("native_") or ": native_" in reason
            for reason in report.degraded_reasons
        )
    ):
        raise NativeBacktestVerificationRequiredError(
            "native_backtest_requires_trajectory_verification"
        )

    def field(value: object, name: str) -> object:
        return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)

    def input_edges(value: object) -> list[object] | tuple[object, ...]:
        edges = field(value, "inputs")
        if edges is None:
            return ()
        if not isinstance(edges, (list, tuple)):
            raise ValueError("backtest_report_manifest_inputs_invalid")
        return edges

    manifest = store.get_manifest(ref)
    for edge in input_edges(manifest):
        role = field(edge, "role")
        if isinstance(role, str) and role.startswith("native_forecast:"):
            raise NativeBacktestVerificationRequiredError(
                "native_backtest_requires_trajectory_verification"
            )
        profile = field(edge, "manifest_profile_sha256")
        if isinstance(role, str) and role.startswith("replica_cohort:") and profile is not None:
            cohort = store.get_manifest(
                ArtifactRefModel(
                    artifact_id=field(edge, "artifact_id"),
                    kind="scientist.backtest.replica_cohort",
                    media_type="application/json",
                    manifest_profile_sha256=profile,
                )
            )
            for item in input_edges(cohort):
                cohort_role = field(item, "role")
                if isinstance(cohort_role, str) and cohort_role.startswith("native_forecast:"):
                    raise NativeBacktestVerificationRequiredError(
                        "native_backtest_requires_trajectory_verification"
                    )
    return report


__all__ = [
    "BacktestReport",
    "BacktestScenario",
    "BiasDirection",
    "NativeBacktestVerificationRequiredError",
    "OutcomeComparison",
    "SystematicBias",
    "load_backtest_report",
    "load_backtest_report_candidate",
    "persist_backtest_report",
]
