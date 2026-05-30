from __future__ import annotations

from datetime import date

import jax
import jax.numpy as jnp
import numpy.testing as npt
from polisyos.foundry.calibration.loss import pointwise_base_loss, reduce_weighted_loss
from polisyos.foundry.calibration.measurement import (
    DefaultMeasurementAwareLossAdapter,
    MeasurementAwareLossConfig,
)
from polisyos.ir.analytics.calibration import TargetLossConfig
from polisyos.ir.observation.compiler import CalibrationTargetBundleCompiler
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
)
from polisyos.ir.model_layer.types import TimeFrequency


def _panel() -> ObservationPanel:
    return ObservationPanel(
        panel_id="panel_labor_grad",
        family=ObservationFamily.LABOR_MARKET,
        time_grain=TimeFrequency.MONTH,
        records=[
            ObservationRecord(
                observation_id="obs_grad_2024_01",
                family=ObservationFamily.LABOR_MARKET,
                time_grain=TimeFrequency.MONTH,
                period_start=date(2024, 1, 1),
                period_end=date(2024, 1, 31),
                entity_scope=EntityScope.CELL,
                cell_id="cell_a",
                metric_id="employment_rate",
                observed_value=0.5,
                unit="share",
                coverage_estimate=0.8,
                measurement_bias_flag=False,
                censoring_mask=False,
                trust_weight=0.8,
                lag_days_estimate=4,
                source_id="admin_employment",
                source_version="2024.01",
                regime_id="wartime_2024",
                shock_mask=False,
                schema_regime_id="employment_schema_v1",
                identification_mode=IdentificationMode.PROXY_IDENTIFIED,
                proxy_source_id="administrative_employment",
                source_confidence_tier=SourceConfidenceTier.VALIDATED,
            ),
            ObservationRecord(
                observation_id="obs_grad_2024_02",
                family=ObservationFamily.LABOR_MARKET,
                time_grain=TimeFrequency.MONTH,
                period_start=date(2024, 2, 1),
                period_end=date(2024, 2, 29),
                entity_scope=EntityScope.CELL,
                cell_id="cell_a",
                metric_id="employment_rate",
                observed_value=0.55,
                unit="share",
                coverage_estimate=0.0,
                measurement_bias_flag=False,
                censoring_mask=True,
                trust_weight=0.6,
                lag_days_estimate=12,
                source_id="admin_employment",
                source_version="2024.02",
                regime_id="wartime_2024",
                shock_mask=True,
                schema_regime_id="employment_schema_v2",
                identification_mode=IdentificationMode.PROXY_IDENTIFIED,
                proxy_source_id="administrative_employment",
                source_confidence_tier=SourceConfidenceTier.VALIDATED,
            ),
        ],
    )


def test_measurement_adapter_zeroes_missing_coverage_and_downweights_censoring() -> None:
    bundle = CalibrationTargetBundleCompiler().compile(_panel())
    target_id = bundle.targets[0].target_id
    adapter = DefaultMeasurementAwareLossAdapter()
    config = MeasurementAwareLossConfig(
        censoring_discount=0.25, regime_boundary_discount=0.5, shock_discount=0.5
    )

    adapted = adapter.adapt(
        targets=(bundle.targets[0],),
        base_weights=1.0,
        trust_weight=bundle.trust_weight[target_id],
        coverage_estimate=bundle.coverage_estimate[target_id],
        censoring_mask=bundle.censoring_mask[target_id],
        lag_days_estimate=bundle.lag_days_estimate[target_id],
        schema_regime_id=bundle.schema_regime_id[target_id],
        shock_mask=bundle.shock_mask[target_id],
        identification_mode=bundle.identification_mode[target_id],
        config=config,
    )

    weights = adapted["effective_weight"]
    assert float(weights[1]) == 0.0
    assert float(adapted["censor_discount"][1]) == 0.25
    assert bool(adapted["regime_boundary_mask"][1]) is True


def test_compiler_bundle_to_measurement_loss_has_finite_gradient() -> None:
    bundle = CalibrationTargetBundleCompiler().compile(_panel())
    target = bundle.targets[0]
    target_id = target.target_id
    adapter = DefaultMeasurementAwareLossAdapter()
    cfg = TargetLossConfig(kind="mse", weight=1.0, relative=False, epsilon=1e-8)
    measurement_cfg = MeasurementAwareLossConfig()

    def loss_fn(scale: jax.Array) -> jax.Array:
        prediction = scale * jnp.ones_like(bundle.observed_value[target_id])
        pointwise = pointwise_base_loss(
            prediction, bundle.observed_value[target_id], cfg, scale=1.0
        )
        adapted = adapter.adapt(
            targets=(target,),
            base_weights=1.0,
            trust_weight=bundle.trust_weight[target_id],
            coverage_estimate=bundle.coverage_estimate[target_id],
            censoring_mask=bundle.censoring_mask[target_id],
            lag_days_estimate=bundle.lag_days_estimate[target_id],
            schema_regime_id=bundle.schema_regime_id[target_id],
            shock_mask=bundle.shock_mask[target_id],
            identification_mode=bundle.identification_mode[target_id],
            config=measurement_cfg,
        )
        return reduce_weighted_loss(pointwise, adapted["effective_weight"], epsilon=cfg.epsilon)

    grad = jax.grad(loss_fn)(jnp.array(0.4, dtype=jnp.float32))
    npt.assert_allclose(jnp.isfinite(grad), jnp.array(True))


def test_measurement_loss_fails_closed_on_non_finite_predictions() -> None:
    bundle = CalibrationTargetBundleCompiler().compile(_panel())
    target_id = bundle.targets[0].target_id
    cfg = TargetLossConfig(kind="mse", weight=1.0, relative=False, epsilon=1e-8)

    pointwise = pointwise_base_loss(
        jnp.array([0.4, jnp.nan], dtype=jnp.float32),
        bundle.observed_value[target_id],
        cfg,
        scale=1.0,
    )

    reduced = reduce_weighted_loss(pointwise, jnp.ones_like(pointwise), epsilon=cfg.epsilon)
    assert jnp.isinf(reduced)
