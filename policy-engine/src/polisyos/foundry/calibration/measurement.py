"""Compile measurement targets and attach observation-quality loss weights.

This module owns Foundry's JAX-backed materialization of observed targets and
placebos plus the measurement metadata applied at the boundary between
real-world observations and synthetic traces. It never advances simulation
dynamics; loss adapters only weight already-simulated series in `Calibrator.run()`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol, runtime_checkable

try:  # pragma: no cover - preferred in full Foundry runtime environments.
    import jax.numpy as jnp
except ImportError:  # pragma: no cover - keeps measurement contracts importable.
    import numpy as jnp  # type: ignore[no-redef]
import numpy as np
from pydantic import Field

from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.bundles import (
    BundleAxisSemantic,
    BundleLineageRef,
    CalibrationTargetBundleManifest,
    ContractCompatibilityTarget,
    RequiredArraySpec,
)
from polisyos.ir.observation.compiler import (
    CalibrationSplitLabel,
    CalibrationSplitPlan,
    CalibrationSplitter,
    NegativeControlSpec,
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
    SchemaRegimeRegistry,
)

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"

MEASUREMENT_AWARE_TARGET_CONTRACT = ContractCompatibilityTarget(
    contract_id="foundry.calibration.measurement_aware_target.v1",
    contract_fqn="polisyos.foundry.calibration.measurement.MeasurementAwareTarget",
)


class MeasurementAwareTarget(KernelModel):
    """Describe one observed calibration anchor plus measurement-quality fields.

    These targets let calibration weight losses by measurement quality instead
    of assuming that all observed anchors are equally reliable. Each target
    must reference an observed metric and the companion field names that carry
    trust, coverage, lag, censoring, and regime-change metadata in the bundle
    payload.
    """

    schema_version: str = Field(
        "1.0",
        pattern=SCHEMA_VERSION_PATTERN,
        description="Measurement target schema version persisted in observation bundles.",
    )
    target_id: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Stable calibration target identifier matching `CalibrationConfig.targets`.",
    )
    observation_family: ObservationFamily
    metric_id: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Observed metric ID whose values are compared against synthetic traces.",
    )
    identification_mode: IdentificationMode
    observed_value_field: str = Field(default="observed_value", min_length=1, max_length=120)
    base_weight: float = Field(default=1.0, ge=0.0)
    trust_weight_field: str = Field(default="trust_weight", min_length=1, max_length=120)
    coverage_field: str = Field(default="coverage_estimate", min_length=1, max_length=120)
    censoring_field: str = Field(default="censoring_mask", min_length=1, max_length=120)
    lag_days_field: str = Field(default="lag_days_estimate", min_length=1, max_length=120)
    schema_regime_field: str = Field(default="schema_regime_id", min_length=1, max_length=120)
    shock_mask_field: str = Field(default="shock_mask", min_length=1, max_length=120)
    notes: list[str] = Field(default_factory=list)


class MeasurementAwareLossConfig(KernelModel):
    """Configure how weak, stale, or regime-shifted observations downweight loss.

    The discounts are multiplicative and applied after clipping trust and
    coverage to `[0, 1]`; anchors with zero coverage receive zero effective
    weight regardless of other fields.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    censoring_discount: float = Field(default=0.5, ge=0.0)
    lag_half_life_days: int = Field(default=30, ge=1)
    regime_boundary_discount: float = Field(default=0.75, ge=0.0)
    shock_discount: float = Field(default=0.75, ge=0.0)
    weak_anchor_floor: float = Field(default=0.1, ge=0.0)
    notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class CalibrationTargetBundle:
    """Hold observed series and observation metadata consumed by `Calibrator`.

    `observed_value` and its metadata maps define the measurement side of the
    calibration objective. The synthetic side is produced separately by
    `run_pure_scan()` over the current parameterized `StaticBundle`.

    Attributes:
        manifest: Observation-bundle manifest that describes provenance and
            compatibility with `MEASUREMENT_AWARE_TARGET_CONTRACT`.
        targets: Measurement-aware target specs keyed by `target_id`.
        observed_value: Observed target series compared to synthetic traces.
        trust_weight: Per-target reliability weights in `[0, 1]`.
        coverage_estimate: Per-target coverage fractions in `[0, 1]`.
        censoring_mask: Optional boolean censoring indicators.
        lag_days_estimate: Optional measurement lag per observation.
        shock_mask: Optional masks for known shock periods.
        schema_regime_id: Optional regime labels used to discount schema
            boundary neighborhoods.
        observation_id: Optional source observation identifiers.
        time_axis: Optional time labels attached to each observed series.
        split_label: Optional split labels for train/validation style bundles.
        identification_mode: Identification semantics for each target.
        time_grain: Optional declared time grain per target.
    """

    manifest: CalibrationTargetBundleManifest
    targets: tuple[MeasurementAwareTarget, ...]
    observed_value: Mapping[str, Any]
    trust_weight: Mapping[str, Any]
    coverage_estimate: Mapping[str, Any]
    censoring_mask: Mapping[str, Any]
    lag_days_estimate: Mapping[str, Any]
    shock_mask: Mapping[str, Any]
    schema_regime_id: Mapping[str, tuple[str, ...]]
    observation_id: Mapping[str, tuple[str, ...]]
    time_axis: Mapping[str, tuple[str, ...]]
    split_label: Mapping[str, tuple[str, ...]]
    identification_mode: Mapping[str, tuple[IdentificationMode, ...]]
    time_grain: Mapping[str, Any]

    def target_ids(self) -> tuple[str, ...]:
        """Return target IDs in bundle order for validation and diagnostics."""
        return tuple(target.target_id for target in self.targets)


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


class CalibrationTargetBundleCompiler:
    """Compile observation panels into Foundry calibration target bundles."""

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
        self._splitter = splitter or CalibrationSplitter(
            schema_regime_registry=schema_regime_registry
        )

    def compile(self, panel: ObservationPanel) -> CalibrationTargetBundle:
        """Materialize one aligned JAX-backed target bundle from an IR panel."""
        sorted_records = sorted(
            panel.records, key=lambda item: (item.period_start, item.observation_id)
        )
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
            split_labels = [split_plan.label_for_period(point, point).value for point in full_axis]
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
            time_axis[target_id] = tuple(point.isoformat() for point in full_axis)
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
            axis_semantics=[
                BundleAxisSemantic(axis="time", description="Aligned observation time axis")
            ],
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
    """Materialize non-overlapping Foundry placebo calibration targets."""

    def __init__(self, *, shift_periods: int | None = None) -> None:
        self._shift_periods = shift_periods

    def generate(
        self,
        bundle: CalibrationTargetBundle,
        *,
        split_plan: CalibrationSplitPlan | None = None,
    ) -> tuple[CalibrationTargetBundle, tuple[NegativeControlSpec, ...]]:
        """Build placebo tensors while retaining neutral IR control specs."""
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
            placebo_dates = tuple(
                _shift_period(point, grain, shift_periods) for point in source_dates
            )
            while set(placebo_dates).intersection(source_dates):
                shift_periods += 1
                placebo_dates = tuple(
                    _shift_period(point, grain, shift_periods) for point in source_dates
                )

            placebo_target_id = f"placebo.{source_target_id}"
            placebo_time = tuple(point.isoformat() for point in placebo_dates)
            placebo_labels = []
            for point in placebo_dates:
                label = (
                    split_plan.label_for_period(point, point).value
                    if split_plan is not None
                    else CalibrationSplitLabel.TEST.value
                )
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


@runtime_checkable
class MeasurementAwareLossAdapter(Protocol):
    """Adapt base target weights using observation-quality metadata.

    Implementations sit between simulation traces and the final weighted
    calibration loss. They should be pure with respect to inputs and return a
    mapping that at least contains `effective_weight`.
    """

    def adapt(
        self,
        *,
        targets: Sequence[MeasurementAwareTarget],
        base_weights: Any,
        trust_weight: Any,
        coverage_estimate: Any,
        censoring_mask: Any | None,
        lag_days_estimate: Any | None,
        schema_regime_id: Any | None,
        shock_mask: Any | None,
        identification_mode: Sequence[IdentificationMode] | Any | None,
        config: MeasurementAwareLossConfig,
    ) -> Mapping[str, Any]: ...


def _as_1d_array(value: Any, *, dtype: Any) -> jnp.ndarray:
    arr = jnp.asarray(value, dtype=dtype)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    return arr


def _broadcast_to(arr: jnp.ndarray, length: int) -> jnp.ndarray:
    if arr.shape[0] == length:
        return arr
    if arr.shape[0] == 1:
        return jnp.broadcast_to(arr, (length,))
    raise ValueError(f"Expected length 1 or {length}, got {arr.shape[0]}")


def _schema_regime_boundary_mask(schema_regime_id: Any | None) -> jnp.ndarray:
    if schema_regime_id is None:
        return jnp.zeros((0,), dtype=bool)
    if isinstance(schema_regime_id, (str, bytes)):
        schema_values = [str(schema_regime_id)]
    else:
        schema_values = [str(value) for value in schema_regime_id]
    if not schema_values:
        return jnp.zeros((0,), dtype=bool)
    mask = np.zeros((len(schema_values),), dtype=bool)
    for idx, current in enumerate(schema_values):
        if idx > 0 and current != schema_values[idx - 1]:
            mask[idx] = True
        if idx + 1 < len(schema_values) and current != schema_values[idx + 1]:
            mask[idx] = True
    return jnp.asarray(mask, dtype=bool)


def compute_effective_weight(
    *,
    base_weights: Any,
    trust_weight: Any,
    coverage_estimate: Any,
    censoring_mask: Any | None,
    lag_days_estimate: Any | None,
    schema_regime_id: Any | None,
    shock_mask: Any | None,
    config: MeasurementAwareLossConfig,
) -> Mapping[str, jnp.ndarray]:
    """Combine trust, coverage, lag, censoring, shock, and regime discounts.

    The returned `effective_weight` is the product of the base weight and each
    measurement-quality adjustment, with zeroing for anchors that have no
    usable coverage.
    Args:
        base_weights: Scalar or vector base target weights from
            `CalibrationConfig`.
        trust_weight: Trust score per observation, clipped to `[0, 1]`.
        coverage_estimate: Coverage fraction per observation, broadcastable to
            `trust_weight`.
        censoring_mask: Optional boolean mask for censored observations.
        lag_days_estimate: Optional lag in days used by half-life decay.
        schema_regime_id: Optional regime labels used to detect boundary
            observations.
        shock_mask: Optional boolean mask for shock-period observations.
        config: Discount hyperparameters.

    Returns:
        Mapping with `effective_weight` and intermediate discount arrays used
        by diagnostics/reporting.

    Raises:
        ValueError: If any broadcasted metadata vector has a length that is
            neither `1` nor the trust-vector length.
    """

    trust = _as_1d_array(trust_weight, dtype=jnp.float32)
    coverage = _broadcast_to(
        _as_1d_array(coverage_estimate, dtype=jnp.float32),
        int(trust.shape[0]),
    )
    base = _broadcast_to(_as_1d_array(base_weights, dtype=jnp.float32), int(trust.shape[0]))
    normalized_trust = jnp.clip(trust, 0.0, 1.0)
    coverage = jnp.clip(coverage, 0.0, 1.0)

    if lag_days_estimate is None:
        lag = jnp.zeros_like(normalized_trust)
    else:
        lag = _broadcast_to(_as_1d_array(lag_days_estimate, dtype=jnp.float32), int(trust.shape[0]))
    lag_discount = jnp.power(0.5, lag / float(config.lag_half_life_days))

    if censoring_mask is None:
        censor = jnp.zeros_like(normalized_trust, dtype=bool)
    else:
        censor = _broadcast_to(_as_1d_array(censoring_mask, dtype=bool), int(trust.shape[0]))
    censor_discount = jnp.where(censor, config.censoring_discount, 1.0)

    if shock_mask is None:
        shock = jnp.zeros_like(normalized_trust, dtype=bool)
    else:
        shock = _broadcast_to(_as_1d_array(shock_mask, dtype=bool), int(trust.shape[0]))
    shock_discount = jnp.where(shock, config.shock_discount, 1.0)

    boundary_mask = _schema_regime_boundary_mask(schema_regime_id)
    if int(boundary_mask.shape[0]) == 0:
        boundary_mask = jnp.zeros_like(normalized_trust, dtype=bool)
    else:
        boundary_mask = _broadcast_to(boundary_mask, int(trust.shape[0]))
    regime_discount = jnp.where(boundary_mask, config.regime_boundary_discount, 1.0)

    effective_weight = (
        base
        * normalized_trust
        * coverage
        * lag_discount
        * censor_discount
        * shock_discount
        * regime_discount
    )
    effective_weight = jnp.where(coverage <= 0.0, 0.0, effective_weight)
    return {
        "effective_weight": effective_weight,
        "normalized_trust": normalized_trust,
        "lag_discount": lag_discount,
        "censor_discount": censor_discount,
        "shock_discount": shock_discount,
        "regime_boundary_mask": boundary_mask,
        "regime_discount": regime_discount,
    }


class DefaultMeasurementAwareLossAdapter:
    """Compute the default multiplicative observation-quality weights."""

    def adapt(
        self,
        *,
        targets: Sequence[MeasurementAwareTarget],
        base_weights: Any,
        trust_weight: Any,
        coverage_estimate: Any,
        censoring_mask: Any | None,
        lag_days_estimate: Any | None,
        schema_regime_id: Any | None,
        shock_mask: Any | None,
        identification_mode: Sequence[IdentificationMode] | Any | None,
        config: MeasurementAwareLossConfig,
    ) -> Mapping[str, Any]:
        del targets, identification_mode
        return compute_effective_weight(
            base_weights=base_weights,
            trust_weight=trust_weight,
            coverage_estimate=coverage_estimate,
            censoring_mask=censoring_mask,
            lag_days_estimate=lag_days_estimate,
            schema_regime_id=schema_regime_id,
            shock_mask=shock_mask,
            config=config,
        )


__all__ = [
    "MEASUREMENT_AWARE_TARGET_CONTRACT",
    "CalibrationTargetBundle",
    "CalibrationTargetBundleCompiler",
    "CalibrationTargetBundleManifest",
    "DefaultMeasurementAwareLossAdapter",
    "MeasurementAwareLossAdapter",
    "MeasurementAwareLossConfig",
    "MeasurementAwareTarget",
    "NegativeControlGenerator",
    "compute_effective_weight",
]
