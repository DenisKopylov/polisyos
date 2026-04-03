"""Public observation compiler module API."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from enum import Enum

import jax.numpy as jnp
from pydantic import Field, model_validator

from polisyos.foundry.calibration.measurement import (
    CalibrationTargetBundle,
    MEASUREMENT_AWARE_TARGET_CONTRACT,
    MeasurementAwareTarget,
)
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.bundles import (
    BundleAxisSemantic,
    BundleLineageRef,
    CalibrationTargetBundleManifest,
    RequiredArraySpec,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
)
from polisyos.ir.observation.measurement import (
    IdentificationModeRouter,
    MeasurementRegistry,
    RegimeCalendar,
    SchemaRegimeRegistry,
    ShockCalendar,
)
from polisyos.ir.types import TimeFrequency

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"


def _month_add(year: int, month: int, delta_months: int) -> tuple[int, int]:
    total_months = (year * 12 + (month - 1)) + delta_months
    new_year, new_month_zero = divmod(total_months, 12)
    return new_year, new_month_zero + 1


def _shift_period(value: date, time_grain: TimeFrequency, periods: int) -> date:
    if time_grain == TimeFrequency.MONTH:
        year, month = _month_add(value.year, value.month, periods)
        return date(year, month, 1)
    if time_grain == TimeFrequency.QUARTER:
        year, month = _month_add(value.year, value.month, periods * 3)
        return date(year, month, 1)
    if time_grain == TimeFrequency.YEAR:
        return date(value.year + periods, 1, 1)
    raise ValueError(f"Unsupported time grain: {time_grain}")


def _time_label(value: date) -> str:
    return value.isoformat()


def _scope_locator(record: ObservationRecord) -> str:
    scope = record.entity_scope
    if scope in {EntityScope.AGENT, EntityScope.FIRM, EntityScope.HOUSEHOLD} and record.entity_id:
        return record.entity_id
    if scope in {EntityScope.CELL, EntityScope.HOUSEHOLD_CELL} and record.cell_id:
        return record.cell_id
    if scope == EntityScope.REGION and record.region_code:
        return record.region_code.lower()
    if scope == EntityScope.SECTOR and record.sector_id:
        return record.sector_id.lower()
    return "global"


def _target_id(record: ObservationRecord) -> str:
    return ".".join(
        [
            record.family.value,
            record.metric_id,
            record.entity_scope.value,
            _scope_locator(record),
        ]
    )


class CalibrationSplitLabel(str, Enum):
    """Named partition used when building measurement-aware calibration targets."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"
    HOLDOUT = "holdout"


class CalibrationSplitWindow(KernelModel):
    """Date window assigned to one calibration split label."""

    label: CalibrationSplitLabel
    start_date: date | None = None
    end_date: date | None = None
    reason: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def validate_window(self) -> "CalibrationSplitWindow":
        if self.start_date is not None and self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self

    def contains(self, period_start: date, period_end: date) -> bool:
        if self.start_date is not None and period_end < self.start_date:
            return False
        if self.end_date is not None and period_start > self.end_date:
            return False
        return True


class CalibrationSplitPlan(KernelModel):
    """Full partition plan for train, validation, test, and holdout periods."""

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    windows: list[CalibrationSplitWindow] = Field(default_factory=list)

    def label_for_period(self, period_start: date, period_end: date) -> CalibrationSplitLabel:
        for window in self.windows:
            if window.contains(period_start, period_end):
                return window.label
        return CalibrationSplitLabel.HOLDOUT

    @classmethod
    def default(
        cls,
        *,
        time_grain: TimeFrequency,
        records: list[ObservationRecord],
        holdout_windows: list[CalibrationSplitWindow] | None = None,
    ) -> "CalibrationSplitPlan":
        if not records:
            return cls(windows=[])
        latest_start = max(record.period_start for record in records)
        trailing_periods = {
            TimeFrequency.MONTH: 11,
            TimeFrequency.QUARTER: 3,
            TimeFrequency.YEAR: 1,
        }[time_grain]
        test_start = date(2025, 1, 1)
        if latest_start < test_start:
            test_start = _shift_period(latest_start, time_grain, -trailing_periods)
        windows = list(holdout_windows or [])
        windows.extend(
            [
                CalibrationSplitWindow(
                    label=CalibrationSplitLabel.TRAIN,
                    end_date=date(2023, 12, 31),
                    reason="train_pre_2024",
                ),
                CalibrationSplitWindow(
                    label=CalibrationSplitLabel.VALIDATION,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31),
                    reason="validation_2024",
                ),
                CalibrationSplitWindow(
                    label=CalibrationSplitLabel.TEST,
                    start_date=test_start,
                    reason="test_2025_or_trailing_12m",
                ),
            ]
        )
        return cls(windows=windows)


class NegativeControlSpec(KernelModel):
    """Specification describing a generated placebo target for falsification."""

    source_target_id: str = Field(..., min_length=1, max_length=180)
    placebo_target_id: str = Field(..., min_length=1, max_length=180)
    shift_periods: int = Field(..., ge=1)
    source_time_axis: tuple[str, ...] = Field(default_factory=tuple)
    placebo_time_axis: tuple[str, ...] = Field(default_factory=tuple)
    notes: list[str] = Field(default_factory=list)


class CalibrationSplitter:
    """Assign observation periods to calibration splits with boundary awareness.

    The splitter can consult schema-regime, regime-calendar, and shock-calendar
    registries so unstable boundary windows are automatically pushed into the
    holdout partition.
    """

    def __init__(
        self,
        *,
        split_plan: CalibrationSplitPlan | None = None,
        schema_regime_registry: SchemaRegimeRegistry | None = None,
        regime_calendar: RegimeCalendar | None = None,
        shock_calendar: ShockCalendar | None = None,
    ) -> None:
        self._split_plan = split_plan
        self._schema_regime_registry = schema_regime_registry
        self._regime_calendar = regime_calendar
        self._shock_calendar = shock_calendar

    def plan_for_panel(self, panel: ObservationPanel) -> CalibrationSplitPlan:
        if self._split_plan is not None:
            return self._split_plan
        return CalibrationSplitPlan.default(time_grain=panel.time_grain, records=panel.records)

    def label_record(self, record: ObservationRecord, *, split_plan: CalibrationSplitPlan) -> CalibrationSplitLabel:
        label = split_plan.label_for_period(record.period_start, record.period_end)
        if label in {CalibrationSplitLabel.TRAIN, CalibrationSplitLabel.VALIDATION} and self._is_boundary(record):
            return CalibrationSplitLabel.HOLDOUT
        return label

    def _is_boundary(self, record: ObservationRecord) -> bool:
        if self._schema_regime_registry is not None:
            if self._schema_regime_registry.is_boundary(
                schema_regime_id=record.schema_regime_id,
                period_start=record.period_start,
                period_end=record.period_end,
                time_grain=record.time_grain,
            ):
                return True
        if self._regime_calendar is not None and self._regime_calendar.is_boundary(
            regime_id=record.regime_id,
            period_start=record.period_start,
            period_end=record.period_end,
            time_grain=record.time_grain,
        ):
            return True
        if self._shock_calendar is not None and self._shock_calendar.is_boundary(
            period_start=record.period_start,
            period_end=record.period_end,
            time_grain=record.time_grain,
            regime_id=record.regime_id,
        ):
            return True
        return bool(record.shock_mask)


class CalibrationTargetBundleCompiler:
    """Compiler from observation panels to measurement-aware calibration bundles.

    Produces aligned JAX arrays and a manifest describing how observed values,
    trust weights, coverage, censoring, lag, and shocks should be interpreted
    by the Foundry calibration stack.
    """

    def __init__(
        self,
        *,
        measurement_registry: MeasurementRegistry | None = None,
        identification_router: IdentificationModeRouter | None = None,
        schema_regime_registry: SchemaRegimeRegistry | None = None,
        splitter: CalibrationSplitter | None = None,
    ) -> None:
        self._measurement_registry = measurement_registry or MeasurementRegistry.default()
        self._identification_router = identification_router or IdentificationModeRouter(
            measurement_registry=self._measurement_registry
        )
        self._schema_regime_registry = schema_regime_registry
        self._splitter = splitter or CalibrationSplitter(schema_regime_registry=schema_regime_registry)

    def compile(self, panel: ObservationPanel) -> CalibrationTargetBundle:
        sorted_records = sorted(panel.records, key=lambda item: (item.period_start, item.observation_id))
        full_axis = tuple(sorted({record.period_start for record in sorted_records}))
        axis_index = {value: idx for idx, value in enumerate(full_axis)}
        grouped: dict[str, list[ObservationRecord]] = defaultdict(list)
        split_plan = self._splitter.plan_for_panel(panel)

        for record in sorted_records:
            grouped[_target_id(record)].append(record)

        targets: list[MeasurementAwareTarget] = []
        observed_value: dict[str, jnp.ndarray] = {}
        trust_weight: dict[str, jnp.ndarray] = {}
        coverage_estimate: dict[str, jnp.ndarray] = {}
        censoring_mask: dict[str, jnp.ndarray] = {}
        lag_days_estimate: dict[str, jnp.ndarray] = {}
        shock_mask: dict[str, jnp.ndarray] = {}
        schema_regime_id: dict[str, tuple[str, ...]] = {}
        observation_id: dict[str, tuple[str, ...]] = {}
        time_axis: dict[str, tuple[str, ...]] = {}
        split_label: dict[str, tuple[str, ...]] = {}
        identification_mode: dict[str, tuple[IdentificationMode, ...]] = {}
        time_grain: dict[str, TimeFrequency] = {}

        for target_id, records in grouped.items():
            first = records[0]
            values = [0.0] * len(full_axis)
            trust = [0.0] * len(full_axis)
            coverage = [0.0] * len(full_axis)
            censor = [False] * len(full_axis)
            lag = [0] * len(full_axis)
            shock = [False] * len(full_axis)
            schema_ids = ["missing"] * len(full_axis)
            observation_ids = [
                f"missing.{panel.panel_id}.{first.metric_id}.{idx}" for idx in range(len(full_axis))
            ]
            split_labels = [
                split_plan.label_for_period(point, point).value for point in full_axis
            ]
            routed_modes = [first.identification_mode] * len(full_axis)

            for record in records:
                idx = axis_index[record.period_start]
                route = self._identification_router.route_record(record)
                values[idx] = float(record.observed_value)
                trust[idx] = self._measurement_registry.normalize_record_trust(record)
                coverage[idx] = float(record.coverage_estimate)
                censor[idx] = bool(record.censoring_mask)
                lag[idx] = int(record.lag_days_estimate)
                shock[idx] = bool(record.shock_mask)
                schema_ids[idx] = record.schema_regime_id
                observation_ids[idx] = record.observation_id
                split_labels[idx] = self._splitter.label_record(record, split_plan=split_plan).value
                routed_modes[idx] = route.selected_mode

            dominant_mode = Counter(routed_modes).most_common(1)[0][0]
            targets.append(
                MeasurementAwareTarget(
                    target_id=target_id,
                    observation_family=first.family,
                    metric_id=first.metric_id,
                    identification_mode=dominant_mode,
                )
            )
            observed_value[target_id] = jnp.asarray(values, dtype=jnp.float32)
            trust_weight[target_id] = jnp.asarray(trust, dtype=jnp.float32)
            coverage_estimate[target_id] = jnp.asarray(coverage, dtype=jnp.float32)
            censoring_mask[target_id] = jnp.asarray(censor, dtype=bool)
            lag_days_estimate[target_id] = jnp.asarray(lag, dtype=jnp.int32)
            shock_mask[target_id] = jnp.asarray(shock, dtype=bool)
            schema_regime_id[target_id] = tuple(schema_ids)
            observation_id[target_id] = tuple(observation_ids)
            time_axis[target_id] = tuple(_time_label(point) for point in full_axis)
            split_label[target_id] = tuple(split_labels)
            identification_mode[target_id] = tuple(routed_modes)
            time_grain[target_id] = first.time_grain

        manifest = CalibrationTargetBundleManifest(
            contract_target=MEASUREMENT_AWARE_TARGET_CONTRACT,
            required_arrays=[
                RequiredArraySpec(name="observed_value", axes=["time"], dtype="float32"),
                RequiredArraySpec(name="trust_weight", axes=["time"], dtype="float32"),
                RequiredArraySpec(name="coverage_estimate", axes=["time"], dtype="float32"),
                RequiredArraySpec(name="censoring_mask", axes=["time"], dtype="bool"),
                RequiredArraySpec(name="lag_days_estimate", axes=["time"], dtype="int32"),
                RequiredArraySpec(name="shock_mask", axes=["time"], dtype="bool"),
            ],
            axis_semantics=[BundleAxisSemantic(axis="time", description="Aligned observation time axis")],
            observation_families=[panel.family],
            lineage=[BundleLineageRef(source_artifact=panel.panel_id, source_family=panel.family)],
        )
        return CalibrationTargetBundle(
            manifest=manifest,
            targets=tuple(targets),
            observed_value=observed_value,
            trust_weight=trust_weight,
            coverage_estimate=coverage_estimate,
            censoring_mask=censoring_mask,
            lag_days_estimate=lag_days_estimate,
            shock_mask=shock_mask,
            schema_regime_id=schema_regime_id,
            observation_id=observation_id,
            time_axis=time_axis,
            split_label=split_label,
            identification_mode=identification_mode,
            time_grain=time_grain,
        )


class NegativeControlGenerator:
    """Generator for placebo targets derived from a calibration target bundle.

    Negative controls are created by shifting the time axis far enough to avoid
    overlap with the source series, which enables specification and falsification
    checks without mutating the original targets.
    """

    def __init__(self, *, shift_periods: int | None = None) -> None:
        self._shift_periods = shift_periods

    def generate(
        self,
        bundle: CalibrationTargetBundle,
        *,
        split_plan: CalibrationSplitPlan | None = None,
    ) -> tuple[CalibrationTargetBundle, tuple[NegativeControlSpec, ...]]:
        targets: list[MeasurementAwareTarget] = []
        specs: list[NegativeControlSpec] = []
        observed_value: dict[str, jnp.ndarray] = {}
        trust_weight: dict[str, jnp.ndarray] = {}
        coverage_estimate: dict[str, jnp.ndarray] = {}
        censoring_mask: dict[str, jnp.ndarray] = {}
        lag_days_estimate: dict[str, jnp.ndarray] = {}
        shock_mask: dict[str, jnp.ndarray] = {}
        schema_regime_id: dict[str, tuple[str, ...]] = {}
        observation_id: dict[str, tuple[str, ...]] = {}
        time_axis: dict[str, tuple[str, ...]] = {}
        split_label: dict[str, tuple[str, ...]] = {}
        identification_mode: dict[str, tuple[IdentificationMode, ...]] = {}
        time_grain: dict[str, TimeFrequency] = {}

        for target in bundle.targets:
            source_target_id = target.target_id
            source_time = tuple(bundle.time_axis[source_target_id])
            source_dates = tuple(date.fromisoformat(point) for point in source_time)
            if not source_dates:
                continue
            grain = bundle.time_grain[source_target_id]
            shift_periods = self._shift_periods or (len(source_dates) + 1)
            placebo_dates = tuple(_shift_period(point, grain, shift_periods) for point in source_dates)
            while set(placebo_dates).intersection(source_dates):
                shift_periods += 1
                placebo_dates = tuple(_shift_period(point, grain, shift_periods) for point in source_dates)

            placebo_target_id = f"placebo.{source_target_id}"
            placebo_time = tuple(_time_label(point) for point in placebo_dates)
            placebo_labels = []
            for point in placebo_dates:
                label = split_plan.label_for_period(point, point).value if split_plan is not None else CalibrationSplitLabel.TEST.value
                placebo_labels.append(label)
            if CalibrationSplitLabel.HOLDOUT.value in placebo_labels:
                continue

            targets.append(
                MeasurementAwareTarget(
                    target_id=placebo_target_id,
                    observation_family=target.observation_family,
                    metric_id=f"placebo_{target.metric_id}",
                    identification_mode=target.identification_mode,
                    base_weight=target.base_weight,
                )
            )
            observed_value[placebo_target_id] = bundle.observed_value[source_target_id]
            trust_weight[placebo_target_id] = bundle.trust_weight[source_target_id]
            coverage_estimate[placebo_target_id] = bundle.coverage_estimate[source_target_id]
            censoring_mask[placebo_target_id] = bundle.censoring_mask[source_target_id]
            lag_days_estimate[placebo_target_id] = bundle.lag_days_estimate[source_target_id]
            shock_mask[placebo_target_id] = bundle.shock_mask[source_target_id]
            schema_regime_id[placebo_target_id] = bundle.schema_regime_id[source_target_id]
            observation_id[placebo_target_id] = tuple(
                f"placebo.{identifier}" for identifier in bundle.observation_id[source_target_id]
            )
            time_axis[placebo_target_id] = placebo_time
            split_label[placebo_target_id] = tuple(placebo_labels)
            identification_mode[placebo_target_id] = bundle.identification_mode[source_target_id]
            time_grain[placebo_target_id] = grain
            specs.append(
                NegativeControlSpec(
                    source_target_id=source_target_id,
                    placebo_target_id=placebo_target_id,
                    shift_periods=shift_periods,
                    source_time_axis=source_time,
                    placebo_time_axis=placebo_time,
                )
            )

        placebo_bundle = CalibrationTargetBundle(
            manifest=bundle.manifest,
            targets=tuple(targets),
            observed_value=observed_value,
            trust_weight=trust_weight,
            coverage_estimate=coverage_estimate,
            censoring_mask=censoring_mask,
            lag_days_estimate=lag_days_estimate,
            shock_mask=shock_mask,
            schema_regime_id=schema_regime_id,
            observation_id=observation_id,
            time_axis=time_axis,
            split_label=split_label,
            identification_mode=identification_mode,
            time_grain=time_grain,
        )
        return placebo_bundle, tuple(specs)


__all__ = [
    "CalibrationSplitLabel",
    "CalibrationSplitPlan",
    "CalibrationSplitWindow",
    "CalibrationSplitter",
    "CalibrationTargetBundleCompiler",
    "NegativeControlGenerator",
    "NegativeControlSpec",
]
