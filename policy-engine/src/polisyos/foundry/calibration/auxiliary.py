"""Define auxiliary calibration penalties that operate on simulated traces.

Auxiliary components extend the objective with penalties that are not direct
target-vs-trace residuals, such as graph spillover mismatch. They receive
synthetic traces only; observation-side metadata and discounting remain in the
measurement bundle/config they own.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

import jax.numpy as jnp

from polisyos.foundry.calibration.loss import reduce_weighted_loss
from polisyos.foundry.calibration.measurement import (
    MeasurementAwareLossConfig,
    compute_effective_weight,
)
from polisyos.ir.observation.bundles import (
    InterferenceLossSpecBundle,
    InterferenceLossTargetSpec,
)


@runtime_checkable
class AuxLossComponent(Protocol):
    """Compute an additional calibration penalty from synthetic execution traces.

    Implementations are part of the public extension surface for domain-
    specific penalties. They should be deterministic for identical `traces`
    and component configuration.
    """

    component_name: str

    def compute(
        self, *, traces: Mapping[str, jnp.ndarray]
    ) -> tuple[jnp.ndarray, Mapping[str, Any]]:
        """Return `(penalty, diagnostics)` for the provided synthetic traces."""
        ...


def _aggregate_trace(value: jnp.ndarray) -> jnp.ndarray:
    arr = jnp.asarray(value, dtype=jnp.float32)
    if arr.ndim == 0:
        return arr.reshape(1)
    if arr.ndim == 1:
        return arr
    axes = tuple(range(1, arr.ndim))
    return jnp.mean(arr, axis=axes)


def _normalized_adjacency(adjacency: jnp.ndarray, normalization: str) -> jnp.ndarray:
    if normalization == "none":
        return adjacency
    if normalization == "global":
        scale = jnp.maximum(jnp.sum(adjacency), 1.0)
        return adjacency / scale
    row_sum = jnp.sum(adjacency, axis=1, keepdims=True)
    return adjacency / jnp.maximum(row_sum, 1.0)


def _pointwise_loss(residual: jnp.ndarray, *, loss_kind: str, huber_delta: float) -> jnp.ndarray:
    if loss_kind == "huber":
        abs_residual = jnp.abs(residual)
        quadratic = jnp.minimum(abs_residual, huber_delta)
        linear = abs_residual - quadratic
        return 0.5 * quadratic**2 + huber_delta * linear
    return jnp.square(residual)


class InterferenceLossComponent:
    """Penalize mismatch between simulated exposure spillovers and observed spillovers.

    Use this component when calibration must match network/interference
    summaries in addition to direct target series. It expects trace paths to
    expose the predicted metric named by each `InterferenceLossTargetSpec` and
    skips specs whose metric path is absent or shape-incompatible.
    """

    component_name = "interference"

    def __init__(
        self,
        bundle: InterferenceLossSpecBundle,
        *,
        measurement_config: MeasurementAwareLossConfig | None = None,
    ) -> None:
        self.bundle = bundle
        self.measurement_config = measurement_config or MeasurementAwareLossConfig()

    def _weights_for(self, spec: InterferenceLossTargetSpec) -> jnp.ndarray:
        size = len(spec.observed_spillover)
        trust = spec.trust_weight or [1.0] * size
        coverage = spec.coverage_estimate or [1.0] * size
        adapted = compute_effective_weight(
            base_weights=jnp.ones((size,), dtype=jnp.float32),
            trust_weight=trust,
            coverage_estimate=coverage,
            censoring_mask=spec.censoring_mask or None,
            lag_days_estimate=spec.lag_days_estimate or None,
            schema_regime_id=spec.schema_regime_id or None,
            shock_mask=spec.shock_mask or None,
            config=self.measurement_config,
        )
        return jnp.asarray(adapted["effective_weight"], dtype=jnp.float32)

    def compute(
        self, *, traces: Mapping[str, jnp.ndarray]
    ) -> tuple[jnp.ndarray, Mapping[str, Any]]:
        """Accumulate spillover penalties and return applied-spec diagnostics."""
        total = jnp.array(0.0, dtype=jnp.float32)
        diagnostics: dict[str, Any] = {"applied_specs": []}
        for spec in self.bundle.specs:
            if spec.predicted_metric_path not in traces:
                continue
            predicted = _aggregate_trace(
                jnp.asarray(traces[spec.predicted_metric_path], dtype=jnp.float32)
            )
            adjacency = _normalized_adjacency(
                jnp.asarray(spec.adjacency, dtype=jnp.float32),
                spec.normalization,
            )
            observed = jnp.asarray(spec.observed_spillover, dtype=jnp.float32)
            if predicted.shape[0] != observed.shape[0]:
                continue
            exposure = adjacency @ predicted
            weights = self._weights_for(spec)
            penalty = reduce_weighted_loss(
                _pointwise_loss(
                    exposure - observed,
                    loss_kind=spec.loss_kind,
                    huber_delta=float(spec.huber_delta),
                ),
                weights,
            )
            total = total + penalty
            diagnostics["applied_specs"].append(spec.spec_id)
        return total, diagnostics


__all__ = [
    "AuxLossComponent",
    "InterferenceLossComponent",
]
