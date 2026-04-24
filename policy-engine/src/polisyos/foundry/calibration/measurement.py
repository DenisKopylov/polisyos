"""Attach observation-quality metadata to calibration targets and loss weights.

The classes in this module describe observed targets and measurement metadata
at the boundary between real-world observations and synthetic Foundry traces.
They never advance simulation dynamics; they only adapt loss weights applied
to already-simulated series inside `Calibrator.run()`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

try:  # pragma: no cover - preferred in full Foundry runtime environments.
    import jax.numpy as jnp
except ImportError:  # pragma: no cover - keeps measurement contracts importable.
    import numpy as jnp  # type: ignore[no-redef]
import numpy as np
from pydantic import Field

from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.bundles import (
    CalibrationTargetBundleManifest,
    ContractCompatibilityTarget,
)
from polisyos.ir.observation.contracts import IdentificationMode, ObservationFamily

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
    "CalibrationTargetBundleManifest",
    "DefaultMeasurementAwareLossAdapter",
    "MeasurementAwareLossAdapter",
    "MeasurementAwareLossConfig",
    "MeasurementAwareTarget",
    "compute_effective_weight",
]
