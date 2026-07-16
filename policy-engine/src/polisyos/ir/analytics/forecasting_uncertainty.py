"""Forecasting-specific uncertainty contracts for multi-horizon predictions."""

from __future__ import annotations

import itertools
import math
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics._truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessScope,
    TruthfulnessTier,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    NativeValueEstimandBinding,
    NumericPolicySpec,
    OutputContractDeclaration,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    ValueUncertaintyProjectionKind,
    value_uncertainty_output_contract,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel, ForecastingUncertaintyBundleRef

if TYPE_CHECKING:
    from datetime import datetime
else:
    from datetime import datetime


def _coerce_python_numeric(value: Any) -> Any:
    if isinstance(value, (str, bytes)):
        return value
    if hasattr(value, "tolist") and not isinstance(value, (list, tuple, dict)):
        converted = None
        try:
            converted = value.tolist()
        except Exception:
            converted = None
        if converted is not None:
            return converted
    if hasattr(value, "item") and not isinstance(value, (list, tuple, dict)):
        converted = None
        try:
            converted = value.item()
        except Exception:
            converted = None
        if converted is not None:
            return converted
    return value


def _normalize_numeric_payload(value: Any, policy: NumericPolicySpec) -> Any:
    value = _coerce_python_numeric(value)
    if isinstance(value, (list, tuple)):
        if not value:
            raise ValueError("numeric payload collections must be non-empty")
        return tuple(_normalize_numeric_payload(item, policy) for item in value)
    try:
        numeric = policy.canonicalize(float(value))
    except Exception as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"numeric payload value {value!r} is not coercible to float") from exc
    if not math.isfinite(numeric):
        raise ValueError("numeric payload values must be finite")
    return numeric


def _shape_signature(value: Any) -> tuple[Any, ...]:
    if isinstance(value, tuple):
        child = _shape_signature(value[0])
        for item in value[1:]:
            if _shape_signature(item) != child:
                raise ValueError("ragged numeric payloads are not supported")
        return (len(value), child)
    return ("scalar",)


def _flatten_numeric_payload(value: Any) -> list[float]:
    if isinstance(value, tuple):
        flattened: list[float] = []
        for item in value:
            flattened.extend(_flatten_numeric_payload(item))
        return flattened
    return [float(value)]


def _canonicalize_optional_float_mapping(
    mapping: dict[Any, Any] | None,
    policy: NumericPolicySpec,
) -> dict[int, float | None]:
    if not mapping:
        return {}
    normalized: dict[int, float | None] = {}
    for key, value in mapping.items():
        horizon = int(key)
        if value is None:
            normalized[horizon] = None
            continue
        numeric = policy.canonicalize(float(value))
        if not math.isfinite(numeric):
            raise ValueError("diagnostic mapping values must be finite when provided")
        normalized[horizon] = numeric
    return dict(sorted(normalized.items()))


class ForecastIntervalSemantics(str, Enum):
    """Semantic meaning of the multi-horizon interval surface."""

    PREDICTION_INTERVAL = "prediction_interval"
    CREDIBLE_INTERVAL = "credible_interval"
    CONFORMALIZED_PREDICTION_INTERVAL = "conformalized_prediction_interval"
    HEURISTIC_RANGE = "heuristic_range"


class ForecastCalibrationMethod(str, Enum):
    """Construction family used to populate the bundle."""

    NONE = "none"
    PARAMETRIC = "parametric"
    BOOTSTRAP = "bootstrap"
    CONFORMAL = "conformal"
    BAYESIAN = "bayesian"
    BAYESIAN_PLUS_CONFORMAL = "bayesian_plus_conformal"
    GAUSSIAN_RECONCILIATION = "gaussian_reconciliation"
    COHERENT_BOOTSTRAP = "coherent_bootstrap"
    CONFORMAL_AFTER_RECONCILIATION = "conformal_after_reconciliation"


class ReconciliationStatus(str, Enum):
    """Certification status for hierarchical or grouped forecast reconciliation."""

    CERTIFIED = "certified"
    FALLBACK = "fallback"


class ReconciliationMethod(str, Enum):
    """Reconciliation family used before uncertainty calibration."""

    NONE = "none"
    BOTTOM_UP = "bottom_up"
    OLS = "ols"
    MINT_SHRINK = "mint_shrink"
    GAUSSIAN_PROJECTION = "gaussian_projection"
    GENERAL_LINEAR_PROJECTION = "general_linear_projection"
    CONDITIONING_BUIS = "conditioning_buis"


class ReconciliationCertificate(BaseModel):
    """Typed evidence surface for forecast reconciliation coverage claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ReconciliationStatus
    method: ReconciliationMethod
    constraints_kind: Literal["hierarchical", "grouped", "general_linear"]
    coherent_points: bool
    coherent_paths: bool
    coverage_scope: Literal[
        "per_series_marginal",
        "per_series_marginal_with_beta_mixing_penalty",
        "uncertified",
    ]
    preconditions_passed: bool
    preconditions: dict[str, bool | str | int | float | None] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    coherent_sample_paths_ref: ArtifactRefModel | None = None
    node_level_diagnostics_ref: ArtifactRefModel | None = None
    fallback_reason: str | None = None

    @model_validator(mode="after")
    def _validate_certificate(self) -> ReconciliationCertificate:
        if self.status is ReconciliationStatus.CERTIFIED:
            if not self.preconditions_passed:
                raise ValueError("certified reconciliation requires passed preconditions")
            if self.coverage_scope == "uncertified":
                raise ValueError("certified reconciliation requires a coverage scope")
        if self.status is ReconciliationStatus.FALLBACK and not self.fallback_reason:
            raise ValueError("fallback reconciliation requires fallback_reason")
        return self


class HorizonDiagnosticState(str, Enum):
    """Health state for one horizon block."""

    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class HorizonInterval(BaseModel):
    """One forecast horizon with point and interval endpoints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon: int = Field(ge=1)
    point: Any
    lower: Any
    upper: Any
    coverage_target: float | None = Field(default=None, gt=0.0, lt=1.0)
    constructor: ForecastCalibrationMethod
    sample_count: int | None = Field(default=None, ge=1)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_interval(self) -> HorizonInterval:
        point_sig = _shape_signature(self.point)
        lower_sig = _shape_signature(self.lower)
        upper_sig = _shape_signature(self.upper)
        if point_sig != lower_sig or point_sig != upper_sig:
            raise ValueError("point/lower/upper payloads must share the same shape")
        flat_point = _flatten_numeric_payload(self.point)
        flat_lower = _flatten_numeric_payload(self.lower)
        flat_upper = _flatten_numeric_payload(self.upper)
        for point, lower, upper in zip(flat_point, flat_lower, flat_upper, strict=True):
            if lower > upper:
                raise ValueError("interval lower bounds must not exceed upper bounds")
            if not lower <= point <= upper:
                raise ValueError("point values must lie inside interval bounds")
        return self


class HorizonQuantileSet(BaseModel):
    """Fan-chart quantiles for one forecast horizon."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon: int = Field(ge=1)
    quantiles: dict[str, Any]

    @model_validator(mode="after")
    def _validate_quantiles(self) -> HorizonQuantileSet:
        if not self.quantiles:
            raise ValueError("fan-chart horizon requires at least one quantile")
        parsed_quantiles = {float(key): value for key, value in self.quantiles.items()}
        ordered_levels = sorted(parsed_quantiles)
        if any(level < 0.0 or level > 1.0 for level in ordered_levels):
            raise ValueError("fan-chart quantile levels must be within [0, 1]")
        reference_shape: tuple[Any, ...] | None = None
        ordered_payloads: list[list[float]] = []
        for level in ordered_levels:
            payload = parsed_quantiles[level]
            payload_shape = _shape_signature(payload)
            if reference_shape is None:
                reference_shape = payload_shape
            elif payload_shape != reference_shape:
                raise ValueError("fan-chart quantile payloads must share the same shape")
            ordered_payloads.append(_flatten_numeric_payload(payload))
        for position in range(len(ordered_payloads[0])):
            values = [payload[position] for payload in ordered_payloads]
            if any(left > right for left, right in itertools.pairwise(values)):
                raise ValueError(
                    "fan-chart quantiles must be monotone within each payload position"
                )
        return self


class FanChartSpec(BaseModel):
    """Machine-readable fan chart surface used to render nested forecast bands."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quantile_levels: tuple[float, ...] = ()
    horizons: tuple[HorizonQuantileSet, ...] = ()

    @model_validator(mode="after")
    def _validate_fan_chart(self) -> FanChartSpec:
        if any(level < 0.0 or level > 1.0 for level in self.quantile_levels):
            raise ValueError("fan-chart levels must be within [0, 1]")
        if tuple(sorted(self.quantile_levels)) != self.quantile_levels:
            raise ValueError("fan-chart levels must be sorted ascending")
        if len(set(self.quantile_levels)) != len(self.quantile_levels):
            raise ValueError("fan-chart levels must be unique")
        expected_keys = {float(level) for level in self.quantile_levels}
        seen_horizons: set[int] = set()
        for entry in self.horizons:
            if entry.horizon in seen_horizons:
                raise ValueError("fan-chart horizons must be unique")
            seen_horizons.add(entry.horizon)
            if expected_keys and {float(key) for key in entry.quantiles} != expected_keys:
                raise ValueError("fan-chart horizon quantiles must match quantile_levels exactly")
        return self


class ForecastCoverageDiagnostic(BaseModel):
    """Coverage and calibration diagnostics attached to the bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    nominal_coverage: float = Field(gt=0.0, lt=1.0)
    empirical_coverage_by_horizon: dict[int, float] = Field(default_factory=dict)
    coverage_gap_by_horizon: dict[int, float] = Field(default_factory=dict)
    mean_interval_width_by_horizon: dict[int, float | None] = Field(default_factory=dict)
    conditional_coverage_pvalue_by_horizon: dict[int, float | None] = Field(default_factory=dict)
    independence_pvalue_by_horizon: dict[int, float | None] = Field(default_factory=dict)
    wis_by_horizon: dict[int, float | None] = Field(default_factory=dict)
    sample_count_by_horizon: dict[int, int] = Field(default_factory=dict)
    pit_summary_ref: ArtifactRefModel | None = None
    regime_flags: tuple[str, ...] = ()
    recommended_fallback: ForecastCalibrationMethod | None = None
    calibration_window: int = Field(default=0, ge=0)
    last_recalibrated_at: datetime

    @model_validator(mode="after")
    def _validate_mappings(self) -> ForecastCoverageDiagnostic:
        for mapping in (
            self.empirical_coverage_by_horizon,
            self.conditional_coverage_pvalue_by_horizon,
            self.independence_pvalue_by_horizon,
        ):
            for horizon, value in mapping.items():
                if horizon < 1:
                    raise ValueError("diagnostic horizons must be >= 1")
                if value is not None and not 0.0 <= value <= 1.0:
                    raise ValueError("coverage and p-value diagnostics must be within [0, 1]")
        for horizon, value in self.mean_interval_width_by_horizon.items():
            if horizon < 1:
                raise ValueError("width horizons must be >= 1")
            if value is not None and value < 0.0:
                raise ValueError("interval widths must be non-negative")
        for horizon, count in self.sample_count_by_horizon.items():
            if horizon < 1:
                raise ValueError("sample-count horizons must be >= 1")
            if count < 0:
                raise ValueError("sample counts must be non-negative")
        return self


class HorizonPolicyRule(BaseModel):
    """Routing policy for a contiguous horizon block."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizon_start: int = Field(ge=1)
    horizon_end: int = Field(ge=1)
    diagnostic_state: HorizonDiagnosticState
    allowed_methods: tuple[ForecastCalibrationMethod, ...] = ()
    gate_eligible: bool = True
    regime: str | None = None
    fallback: ForecastCalibrationMethod | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _validate_rule(self) -> HorizonPolicyRule:
        if self.horizon_start > self.horizon_end:
            raise ValueError("horizon_start must be <= horizon_end")
        if not self.allowed_methods and self.gate_eligible:
            raise ValueError("gate-eligible horizon rules must declare at least one allowed method")
        return self


class HorizonPolicySpec(BaseModel):
    """Bundle-level routing policy across forecast horizons."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    default_method: ForecastCalibrationMethod
    rules: tuple[HorizonPolicyRule, ...] = ()
    gate_eligible: bool = True
    summary: str | None = None

    @model_validator(mode="after")
    def _validate_rules(self) -> HorizonPolicySpec:
        seen: list[tuple[int, int]] = []
        for rule in self.rules:
            for start, end in seen:
                overlaps = not (rule.horizon_end < start or rule.horizon_start > end)
                if overlaps:
                    raise ValueError("horizon policy rules must not overlap")
            seen.append((rule.horizon_start, rule.horizon_end))
        return self


class ForecastingUncertaintyBundle(BaseModel):
    """Forecasting-specific specialization of PolicyOS uncertainty artifacts."""

    contract_id: ClassVar[str] = "ir.forecasting_uncertainty_bundle.v1"
    output_contract_declaration: ClassVar[OutputContractDeclaration] = (
        value_uncertainty_output_contract(
            contract_id,
            projection_kind=ValueUncertaintyProjectionKind.FORECASTING,
        )
    )
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    numeric_policy: NumericPolicySpec = Field(default_factory=NumericPolicySpec)

    method_fqn: str
    source_method: str | None = None
    target_id: str
    generated_at: datetime

    prediction_interval: tuple[HorizonInterval, ...] = ()
    fan_chart: FanChartSpec
    posterior_predictive_ref: ArtifactRefModel | None = None
    coverage_diagnostic: ForecastCoverageDiagnostic
    horizon_policy: HorizonPolicySpec

    interval_semantics: ForecastIntervalSemantics
    calibration_method: ForecastCalibrationMethod
    nominal_coverage: float = Field(gt=0.0, lt=1.0)
    sample_size_assumption: str
    regime_assumption: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _canonicalize_payload(cls, value: Any) -> Any:
        if isinstance(value, ForecastingUncertaintyBundle):
            return value
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        if payload.get("source_method") is None and payload.get("method_fqn") is not None:
            payload["source_method"] = str(payload["method_fqn"])
        policy = NumericPolicySpec.model_validate(payload.get("numeric_policy", {}))
        payload["numeric_policy"] = policy.model_dump(mode="python")
        payload["nominal_coverage"] = policy.canonicalize(float(payload["nominal_coverage"]))

        intervals: list[dict[str, Any]] = []
        for interval in payload.get("prediction_interval", ()):
            if isinstance(interval, BaseModel):
                interval = interval.model_dump(mode="python", round_trip=True)
            normalized = dict(interval)
            normalized["point"] = _normalize_numeric_payload(interval["point"], policy)
            normalized["lower"] = _normalize_numeric_payload(interval["lower"], policy)
            normalized["upper"] = _normalize_numeric_payload(interval["upper"], policy)
            if interval.get("coverage_target") is not None:
                normalized["coverage_target"] = policy.canonicalize(
                    float(interval["coverage_target"])
                )
            intervals.append(normalized)
        payload["prediction_interval"] = intervals

        fan_chart_payload = payload.get("fan_chart") or {}
        if isinstance(fan_chart_payload, BaseModel):
            fan_chart_payload = fan_chart_payload.model_dump(mode="python", round_trip=True)
        fan_chart = dict(fan_chart_payload)
        if fan_chart:
            fan_chart["quantile_levels"] = tuple(
                policy.canonicalize(float(level)) for level in fan_chart.get("quantile_levels", ())
            )
            normalized_horizons: list[dict[str, Any]] = []
            for entry in fan_chart.get("horizons", ()):
                if isinstance(entry, BaseModel):
                    entry = entry.model_dump(mode="python", round_trip=True)
                normalized_entry = dict(entry)
                normalized_entry["quantiles"] = {
                    str(level): _normalize_numeric_payload(level_value, policy)
                    for level, level_value in entry.get("quantiles", {}).items()
                }
                normalized_horizons.append(normalized_entry)
            fan_chart["horizons"] = normalized_horizons
        payload["fan_chart"] = fan_chart

        coverage_payload = payload.get("coverage_diagnostic") or {}
        if isinstance(coverage_payload, BaseModel):
            coverage_payload = coverage_payload.model_dump(mode="python", round_trip=True)
        coverage = dict(coverage_payload)
        if coverage:
            coverage["nominal_coverage"] = policy.canonicalize(float(coverage["nominal_coverage"]))
            for key in (
                "empirical_coverage_by_horizon",
                "coverage_gap_by_horizon",
                "mean_interval_width_by_horizon",
                "conditional_coverage_pvalue_by_horizon",
                "independence_pvalue_by_horizon",
                "wis_by_horizon",
            ):
                coverage[key] = _canonicalize_optional_float_mapping(coverage.get(key), policy)
        payload["coverage_diagnostic"] = coverage
        return payload

    @model_validator(mode="after")
    def _validate_bundle(self) -> ForecastingUncertaintyBundle:
        prediction_horizons = [interval.horizon for interval in self.prediction_interval]
        if prediction_horizons and prediction_horizons != sorted(prediction_horizons):
            raise ValueError("prediction intervals must be sorted by horizon")
        if len(set(prediction_horizons)) != len(prediction_horizons):
            raise ValueError("prediction intervals must not repeat horizons")
        fan_horizons = [entry.horizon for entry in self.fan_chart.horizons]
        if fan_horizons and fan_horizons != sorted(fan_horizons):
            raise ValueError("fan-chart horizons must be sorted by horizon")
        return self

    def to_truthfulness_receipt(self) -> TruthfulnessReceipt:
        """Map forecasting uncertainty evidence into the shared runtime truthfulness surface."""

        scope = TruthfulnessScope.MARGINAL_COVERAGE
        if (
            self.interval_semantics is ForecastIntervalSemantics.HEURISTIC_RANGE
            or self.calibration_method is ForecastCalibrationMethod.NONE
        ):
            runtime_tier = TruthfulnessTier.UNVERIFIED
            scope = TruthfulnessScope.PREDICTIVE_CALIBRATION
        elif self.calibration_method in {
            ForecastCalibrationMethod.CONFORMAL,
            ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL,
        }:
            runtime_tier = TruthfulnessTier.APPROXIMATE_CALIBRATED
        else:
            runtime_tier = TruthfulnessTier.ASYMPTOTIC

        red_count = sum(
            1
            for rule in self.horizon_policy.rules
            if rule.diagnostic_state is HorizonDiagnosticState.RED
        )
        amber_count = sum(
            1
            for rule in self.horizon_policy.rules
            if rule.diagnostic_state is HorizonDiagnosticState.AMBER
        )
        degradation_reasons = list(self.coverage_diagnostic.regime_flags)
        if red_count > 0 or not self.horizon_policy.gate_eligible:
            runtime_tier = TruthfulnessTier.UNVERIFIED
            degradation_reasons.append("uncalibrated_horizon_detected")
        elif amber_count > 0 and runtime_tier is TruthfulnessTier.ASYMPTOTIC:
            runtime_tier = TruthfulnessTier.APPROXIMATE_CALIBRATED
            degradation_reasons.append("amber_horizon_diagnostic")

        evidence_ref: str | None = None
        if self.posterior_predictive_ref is not None:
            evidence_ref = str(self.posterior_predictive_ref.artifact_id)
        elif self.coverage_diagnostic.pit_summary_ref is not None:
            evidence_ref = str(self.coverage_diagnostic.pit_summary_ref.artifact_id)

        diagnostics = {
            "interval_semantics": self.interval_semantics.value,
            "calibration_method": self.calibration_method.value,
            "method_fqn": self.method_fqn,
            "source_method": self.source_method,
            "nominal_coverage": self.nominal_coverage,
            "bundle_gate_eligible": self.horizon_policy.gate_eligible,
            "red_horizon_count": red_count,
            "amber_horizon_count": amber_count,
            "green_horizon_count": sum(
                1
                for rule in self.horizon_policy.rules
                if rule.diagnostic_state is HorizonDiagnosticState.GREEN
            ),
            "empirical_coverage_by_horizon": self.coverage_diagnostic.empirical_coverage_by_horizon,
            "coverage_gap_by_horizon": self.coverage_diagnostic.coverage_gap_by_horizon,
            "mean_interval_width_by_horizon": self.coverage_diagnostic.mean_interval_width_by_horizon,
            "conditional_coverage_pvalue_by_horizon": (
                self.coverage_diagnostic.conditional_coverage_pvalue_by_horizon
            ),
            "independence_pvalue_by_horizon": (
                self.coverage_diagnostic.independence_pvalue_by_horizon
            ),
            "wis_by_horizon": self.coverage_diagnostic.wis_by_horizon,
        }
        return TruthfulnessReceipt(
            runtime_truthfulness_tier=runtime_tier,
            truthfulness_scope=scope,
            diagnostics=diagnostics,
            degradation_reasons=tuple(dict.fromkeys(degradation_reasons)),
            evidence_ref=evidence_ref,
        )

    def to_value_uncertainty(
        self,
        *,
        estimand: object,
        projection_binding: NativeValueEstimandBinding,
    ) -> UncertaintyEnvelope | None:
        """Project one explicitly requested scalar forecast horizon."""

        estimand_id = str(getattr(estimand, "estimand_id", "") or "")
        outcome = str(getattr(estimand, "outcome", "") or "")
        if self.target_id not in {estimand_id, outcome}:
            return None
        if (
            projection_binding.native_contract_id != self.contract_id
            or not projection_binding.matches(estimand)
        ):
            return None
        horizon_raw = str(getattr(estimand, "time_horizon", "") or "")
        try:
            horizon = int(horizon_raw)
        except ValueError:
            return None
        interval = next(
            (item for item in self.prediction_interval if item.horizon == horizon),
            None,
        )
        if interval is None:
            return None
        point = _flatten_numeric_payload(interval.point)
        lower = _flatten_numeric_payload(interval.lower)
        upper = _flatten_numeric_payload(interval.upper)
        if len(point) != 1 or len(lower) != 1 or len(upper) != 1:
            return None
        heuristic = self.interval_semantics is ForecastIntervalSemantics.HEURISTIC_RANGE
        covered_rules = tuple(
            rule
            for rule in self.horizon_policy.rules
            if rule.horizon_start <= horizon <= rule.horizon_end
        )
        gate_eligible = (
            self.horizon_policy.gate_eligible
            and all(rule.gate_eligible for rule in covered_rules)
            and not heuristic
        )
        return UncertaintyEnvelope(
            point_estimate=point[0],
            confidence_interval=(lower[0], upper[0]),
            confidence_level=(
                None
                if heuristic
                else float(interval.coverage_target or self.nominal_coverage)
            ),
            distribution_family=DistributionFamily.UNKNOWN,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=(
                IntervalSemantics.HEURISTIC_RANGE
                if heuristic
                else IntervalSemantics.CONFIDENCE_INTERVAL
            ),
            sample_size=interval.sample_count,
            is_heuristic_ci=heuristic,
            gate_eligible=gate_eligible,
            metadata={
                "method_fqn": self.method_fqn,
                "target_id": self.target_id,
                "horizon": horizon,
                "native_interval_semantics": self.interval_semantics.value,
                "calibration_method": self.calibration_method.value,
                "value_estimand_binding_content_hash": (
                    projection_binding.content_hash
                ),
                "value_estimand_binding_native_contract_id": (
                    projection_binding.native_contract_id
                ),
                "value_estimand_binding_producer_method_fqn": (
                    projection_binding.producer_method_fqn
                ),
            },
        )


class ForecastingUncertaintyBundleV2(ForecastingUncertaintyBundle):
    """Forecasting uncertainty bundle with reconciliation certification metadata."""

    contract_id: ClassVar[str] = "ir.forecasting_uncertainty_bundle.v2"
    output_contract_declaration: ClassVar[OutputContractDeclaration] = (
        value_uncertainty_output_contract(
            contract_id,
            projection_kind=ValueUncertaintyProjectionKind.FORECASTING,
        )
    )

    schema_version: str = Field(default="2.0", pattern=r"^\d+\.\d+$")
    reconciliation_certificate: ReconciliationCertificate | None = None

    @model_validator(mode="after")
    def _validate_v2_bundle(self) -> ForecastingUncertaintyBundleV2:
        super()._validate_bundle()
        if self.calibration_method is ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION:
            if self.reconciliation_certificate is None:
                raise ValueError(
                    "conformal-after-reconciliation bundles require a reconciliation certificate"
                )
            if self.reconciliation_certificate.status is not ReconciliationStatus.CERTIFIED:
                raise ValueError(
                    "conformal-after-reconciliation requires a certified reconciliation certificate"
                )
        return self

    def to_truthfulness_receipt(self) -> TruthfulnessReceipt:
        """Map v2 reconciliation evidence into the shared truthfulness surface."""

        receipt = super().to_truthfulness_receipt()
        certificate = self.reconciliation_certificate
        if certificate is None:
            return receipt

        diagnostics = dict(receipt.diagnostics)
        diagnostics["reconciliation_certificate"] = certificate.model_dump(mode="json")
        degradation_reasons = list(receipt.degradation_reasons)
        runtime_tier = receipt.runtime_truthfulness_tier
        scope = receipt.truthfulness_scope

        red_count = int(diagnostics.get("red_horizon_count", 0))
        if certificate.status is ReconciliationStatus.CERTIFIED:
            if (
                self.calibration_method
                is ForecastCalibrationMethod.CONFORMAL_AFTER_RECONCILIATION
                and certificate.coverage_scope in {
                    "per_series_marginal",
                    "per_series_marginal_with_beta_mixing_penalty",
                }
                and red_count == 0
                and self.horizon_policy.gate_eligible
            ):
                runtime_tier = TruthfulnessTier.APPROXIMATE_CALIBRATED
                scope = TruthfulnessScope.MARGINAL_COVERAGE
            else:
                degradation_reasons.append("reconciliation_certificate_not_gate_eligible")
        else:
            runtime_tier = TruthfulnessTier.UNVERIFIED
            scope = TruthfulnessScope.PREDICTIVE_CALIBRATION
            degradation_reasons.append("reconciliation_coverage_certificate_missing")

        return receipt.model_copy(
            update={
                "runtime_truthfulness_tier": runtime_tier,
                "truthfulness_scope": scope,
                "diagnostics": diagnostics,
                "degradation_reasons": tuple(dict.fromkeys(degradation_reasons)),
                "certificate_version": "2.0",
            }
        )


def persist_forecasting_uncertainty_bundle(
    store: ArtifactStore,
    bundle: ForecastingUncertaintyBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.forecasting_uncertainty_bundle",
    schema_version: str = "1.0",
) -> ForecastingUncertaintyBundleRef:
    """Persist a forecasting uncertainty bundle as a typed JSON artifact."""

    if isinstance(bundle, ForecastingUncertaintyBundleV2) and schema_version == "1.0":
        schema_version = "2.0"

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json", round_trip=True),
        kind="ir.forecasting_uncertainty_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ForecastingUncertaintyBundleRef.model_validate(ref)


def load_forecasting_uncertainty_bundle(
    store: ArtifactStore,
    ref: ForecastingUncertaintyBundleRef,
) -> ForecastingUncertaintyBundle | ForecastingUncertaintyBundleV2:
    """Load a forecasting uncertainty bundle from artifact storage."""

    payload = get_json_artifact(store, ref.artifact_id)
    if (
        isinstance(payload, dict)
        and (
            payload.get("schema_version") == "2.0"
            or payload.get("reconciliation_certificate") is not None
        )
    ):
        return ForecastingUncertaintyBundleV2.model_validate(payload)
    return ForecastingUncertaintyBundle.model_validate(payload)


__all__ = [
    "FanChartSpec",
    "ForecastCalibrationMethod",
    "ForecastCoverageDiagnostic",
    "ForecastIntervalSemantics",
    "ForecastingUncertaintyBundle",
    "ForecastingUncertaintyBundleV2",
    "HorizonDiagnosticState",
    "HorizonInterval",
    "HorizonPolicyRule",
    "HorizonPolicySpec",
    "HorizonQuantileSet",
    "ReconciliationCertificate",
    "ReconciliationMethod",
    "ReconciliationStatus",
    "load_forecasting_uncertainty_bundle",
    "persist_forecasting_uncertainty_bundle",
]
