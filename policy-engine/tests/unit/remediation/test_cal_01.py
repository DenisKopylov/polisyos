"""Test-first witnesses for CAL-01 observation and target alignment contracts.

The corpus keeps the existing compiler and preflight seams visible while
separating the three CAL-01 concerns: observation identity, paired temporal
alignment, and explicit missing-data semantics.  The expected RED cases are
intentional until the production owner repairs the corresponding paths.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import numpy.testing as npt
import pandas as pd
import pytest

from polisyos.foundry.calibration.measurement import CalibrationTargetBundleCompiler
from polisyos.foundry.calibration.preflight import (
    _resample_series,
    extract_fabric_series,
    prepare_targets,
)
from polisyos.ir.analytics.calibration import (
    CalibrationConfig,
    CalibrationTarget,
    TargetAlignConfig,
    TargetLossConfig,
)
from polisyos.ir.analytics.data_views import AccessTier, DataViewRequest, DataViewType
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
)

pytestmark = pytest.mark.unit

TARGET_ID = "labor_market.calibration_rate.cell.cell_a"


def _record(
    *,
    observation_id: str,
    period_start: date,
    observed_value: float,
    trust_weight: float = 0.8,
    coverage_estimate: float = 1.0,
    censoring_mask: bool = False,
    lag_days_estimate: int = 0,
    schema_regime_id: str = "schema_v1",
    shock_mask: bool = False,
    source_id: str = "source_a",
) -> ObservationRecord:
    """Build one valid record while keeping observation metadata distinctive."""
    return ObservationRecord(
        observation_id=observation_id,
        family=ObservationFamily.LABOR_MARKET,
        time_grain=TimeFrequency.MONTH,
        period_start=period_start,
        period_end=period_start,
        entity_scope=EntityScope.CELL,
        cell_id="cell_a",
        metric_id="calibration_rate",
        observed_value=observed_value,
        unit="share",
        coverage_estimate=coverage_estimate,
        measurement_bias_flag=False,
        censoring_mask=censoring_mask,
        trust_weight=trust_weight,
        lag_days_estimate=lag_days_estimate,
        source_id=source_id,
        source_version="v1",
        regime_id="regime_a",
        shock_mask=shock_mask,
        schema_regime_id=schema_regime_id,
        identification_mode=IdentificationMode.POINT_IDENTIFIED,
    )


def _compile(records: list[ObservationRecord]):
    """Compile records through the real Foundry measurement boundary."""
    panel = ObservationPanel(
        panel_id="panel_cal01",
        family=ObservationFamily.LABOR_MARKET,
        time_grain=TimeFrequency.MONTH,
        records=records,
    )
    return CalibrationTargetBundleCompiler().compile(panel)


def _target(
    *,
    align: TargetAlignConfig | None = None,
    loss: TargetLossConfig | None = None,
) -> CalibrationTarget:
    """Build a target for the real preflight preparation path."""
    return CalibrationTarget(
        target_id="target_cal01",
        model_metric_path="metrics.calibration_rate",
        fabric_metric="metric",
        align=align or TargetAlignConfig(),
        loss=loss or TargetLossConfig(relative=False),
    )


def _config(target: CalibrationTarget, *, steps: int = 3) -> CalibrationConfig:
    """Build a minimal calibration config with an explicit shared horizon."""
    return CalibrationConfig(targets=[target], steps=steps)


def test_observation_id_renaming_does_not_change_compiled_value() -> None:
    """Technical lineage IDs must not choose a different same-period value."""

    def compile_value(first_id: str, second_id: str) -> np.ndarray:
        bundle = _compile(
            [
                _record(
                    observation_id=first_id,
                    period_start=date(2024, 1, 1),
                    observed_value=10.0,
                    source_id="source_a",
                ),
                _record(
                    observation_id=second_id,
                    period_start=date(2024, 1, 1),
                    observed_value=20.0,
                    source_id="source_b",
                ),
            ]
        )
        return np.asarray(bundle.observed_value[TARGET_ID])

    original = compile_value("obs_a", "obs_b")
    renamed = compile_value("obs_z", "obs_a")

    npt.assert_array_equal(renamed, original)


def test_compiler_keeps_time_value_and_metadata_pairs_after_record_reordering() -> None:
    """Sorting records by time keeps masks and lineage attached to values."""
    bundle = _compile(
        [
            _record(
                observation_id="obs_feb",
                period_start=date(2024, 2, 1),
                observed_value=20.0,
                trust_weight=0.2,
                coverage_estimate=0.3,
                censoring_mask=True,
                lag_days_estimate=7,
                schema_regime_id="schema_feb",
                shock_mask=True,
                source_id="source_feb",
            ),
            _record(
                observation_id="obs_jan",
                period_start=date(2024, 1, 1),
                observed_value=10.0,
                trust_weight=0.9,
                coverage_estimate=0.7,
                lag_days_estimate=2,
                schema_regime_id="schema_jan",
                source_id="source_jan",
            ),
        ]
    )

    npt.assert_array_equal(bundle.observed_value[TARGET_ID], [10.0, 20.0])
    npt.assert_allclose(bundle.coverage_estimate[TARGET_ID], [0.7, 0.3])
    npt.assert_array_equal(bundle.censoring_mask[TARGET_ID], [False, True])
    npt.assert_array_equal(bundle.lag_days_estimate[TARGET_ID], [2, 7])
    npt.assert_array_equal(bundle.shock_mask[TARGET_ID], [False, True])
    assert bundle.schema_regime_id[TARGET_ID] == ("schema_jan", "schema_feb")
    assert bundle.observation_id[TARGET_ID] == ("obs_jan", "obs_feb")


def test_unsorted_time_axis_resamples_values_with_their_time_pairs() -> None:
    """Interpolation must sort time together with the values it describes."""
    result = _resample_series(
        np.asarray([20.0, 0.0, 10.0]),
        np.asarray([2.0, 0.0, 1.0]),
        target_time=np.asarray([0.5, 1.5]),
        steps=2,
        method="linear",
        fill_value=None,
    )

    npt.assert_allclose(result, [5.0, 15.0])


def test_missing_requested_time_column_fails_closed() -> None:
    """A requested calendar column cannot silently become a positional axis."""
    target = _target(align=TargetAlignConfig(time_column="event_time"))
    request = DataViewRequest(
        request_id="request_cal01",
        run_id="run_cal01",
        view_type=DataViewType.PANEL,
        metrics=["metric"],
        access_tier=AccessTier.PUBLIC,
    )
    frame = pd.DataFrame({"metric": [10.0, 20.0]})

    with pytest.raises(ValueError, match="event_time"):
        extract_fabric_series(frame, target, request)


def test_fractional_fill_is_dtype_stable_for_integer_and_float_inputs() -> None:
    """Integer and float representations receive the same fractional fill."""
    target = _target(align=TargetAlignConfig(steps=3, fill_value=0.5))
    config = _config(target)

    integer_aligned, _, _ = prepare_targets(
        config,
        raw_targets={target.target_id: np.asarray([1], dtype=np.int64)},
        steps=3,
    )
    float_aligned, _, _ = prepare_targets(
        config,
        raw_targets={target.target_id: np.asarray([1.0], dtype=float)},
        steps=3,
    )

    npt.assert_allclose(integer_aligned[target.target_id], [1.0, 0.5, 0.5])
    npt.assert_allclose(
        integer_aligned[target.target_id], float_aligned[target.target_id]
    )


def test_empty_target_with_explicit_steps_is_not_an_observable_zero_series() -> None:
    """An empty source must not acquire an observed all-zero series by padding."""
    target = _target(align=TargetAlignConfig(steps=3, fill_value=0.0))
    config = _config(target)

    with pytest.raises(ValueError, match="empty|observ"):
        prepare_targets(
            config,
            raw_targets={target.target_id: np.asarray([], dtype=float)},
            steps=3,
        )


def test_endpoint_fill_remains_supported_for_nonempty_series() -> None:
    """Ordinary endpoint padding remains an explicit supported behavior."""
    result = _resample_series(
        np.asarray([1.0, 2.0]),
        None,
        target_time=None,
        steps=3,
        method="linear",
        fill_value=None,
    )

    npt.assert_allclose(result, [1.0, 2.0, 2.0])
