from __future__ import annotations

from datetime import date

import jax
import jax.numpy as jnp
import numpy.testing as npt

from polisyos.foundry.calibration.loss import pointwise_base_loss, reduce_weighted_loss
from polisyos.foundry.calibration.measurement import (
    CalibrationTargetBundleCompiler,
    DefaultMeasurementAwareLossAdapter,
    MeasurementAwareLossConfig,
    NegativeControlGenerator,
)
from polisyos.ir.analytics.calibration import TargetLossConfig
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.compiler import (
    CalibrationSplitLabel,
    CalibrationSplitPlan,
    CalibrationSplitWindow,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
)
from polisyos.ir.observation.measurement import SchemaRegimeRegistry


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
            ObservationRecord(
                observation_id="obs_grad_cell_b_2024_02",
                family=ObservationFamily.LABOR_MARKET,
                time_grain=TimeFrequency.MONTH,
                period_start=date(2024, 2, 1),
                period_end=date(2024, 2, 29),
                entity_scope=EntityScope.CELL,
                cell_id="cell_b",
                metric_id="employment_rate",
                observed_value=0.61,
                unit="share",
                coverage_estimate=0.9,
                measurement_bias_flag=False,
                censoring_mask=False,
                trust_weight=0.8,
                lag_days_estimate=3,
                source_id="admin_employment",
                source_version="2024.02",
                regime_id="wartime_2024",
                shock_mask=False,
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


def test_compiler_aligns_targets_and_masks_missing_rows() -> None:
    bundle = CalibrationTargetBundleCompiler(
        schema_regime_registry=SchemaRegimeRegistry.default()
    ).compile(_panel())
    target_a = "labor_market.employment_rate.cell.cell_a"
    target_b = "labor_market.employment_rate.cell.cell_b"

    assert tuple(bundle.observed_value) == (target_a, target_b)
    assert bundle.observed_value[target_a].shape == (2,)
    assert float(bundle.coverage_estimate[target_b][0]) == 0.0
    assert float(bundle.trust_weight[target_b][0]) == 0.0
    assert bundle.observation_id[target_b][0].startswith("missing.")
    assert bundle.identification_mode[target_a][0] in {
        IdentificationMode.PROXY_IDENTIFIED,
        IdentificationMode.BOUNDS_ONLY,
    }


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


def test_compiler_bundle_round_trips_into_non_overlapping_placebos() -> None:
    bundle = CalibrationTargetBundleCompiler().compile(_panel())

    placebo_bundle, specs = NegativeControlGenerator().generate(bundle)

    assert len(specs) == 2
    spec = next(
        item
        for item in specs
        if item.source_target_id == "labor_market.employment_rate.cell.cell_a"
    )
    assert spec.source_target_id == "labor_market.employment_rate.cell.cell_a"
    assert spec.placebo_target_id == "placebo.labor_market.employment_rate.cell.cell_a"
    assert set(spec.source_time_axis).isdisjoint(spec.placebo_time_axis)
    assert spec.placebo_target_id in placebo_bundle.observed_value
    npt.assert_allclose(
        placebo_bundle.observed_value[spec.placebo_target_id],
        bundle.observed_value[spec.source_target_id],
    )


def test_negative_control_generator_excludes_holdout_placebos() -> None:
    bundle = CalibrationTargetBundleCompiler().compile(_panel())
    split_plan = CalibrationSplitPlan(
        windows=[
            CalibrationSplitWindow(
                label=CalibrationSplitLabel.HOLDOUT,
                start_date=date(2024, 4, 1),
            )
        ]
    )

    placebo_bundle, specs = NegativeControlGenerator().generate(
        bundle,
        split_plan=split_plan,
    )

    assert specs == ()
    assert placebo_bundle.targets == ()
    assert placebo_bundle.observed_value == {}


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
