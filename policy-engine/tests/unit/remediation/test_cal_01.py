"""Behavioral witnesses for CAL-01 observation and target alignment contracts.

The corpus keeps the real compiler and preflight boundaries visible while
separating observation identity, paired temporal alignment and missing data.
The execution records retain pre-fix failures; current assertions require the
correct positive and negative behavior.
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
    SourceConfidenceTier,
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
    source_confidence_tier: SourceConfidenceTier = SourceConfidenceTier.VALIDATED,
    unit: str = "share",
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
        unit=unit,
        coverage_estimate=coverage_estimate,
        measurement_bias_flag=False,
        censoring_mask=censoring_mask,
        trust_weight=trust_weight,
        lag_days_estimate=lag_days_estimate,
        source_id=source_id,
        source_confidence_tier=source_confidence_tier,
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


def test_observation_id_renaming_does_not_resolve_ambiguous_measurements() -> None:
    """Technical lineage IDs must not choose a same-period measurement."""

    def compile_value(first_id: str, second_id: str) -> np.ndarray:
        bundle = _compile(
            [
                _record(
                    observation_id=first_id,
                    period_start=date(2024, 1, 1),
                    observed_value=10.0,
                    trust_weight=0.9,
                    source_id="source_a",
                ),
                _record(
                    observation_id=second_id,
                    period_start=date(2024, 1, 1),
                    observed_value=20.0,
                    source_id="source_a",
                ),
            ]
        )
        return np.asarray(bundle.observed_value[TARGET_ID])

    with pytest.raises(ValueError, match=r"Ambiguous observations|aggregation"):
        compile_value("obs_a", "obs_b")
    with pytest.raises(ValueError, match=r"Ambiguous observations|aggregation"):
        compile_value("obs_z", "obs_a")


@pytest.mark.parametrize("second_unit", ["share", "percent"])
def test_unequal_quality_conflicts_require_an_explicit_policy(second_unit: str) -> None:
    """Trust, quality, source, and unit declarations cannot silently drop a row."""
    with pytest.raises(ValueError, match=r"2 records.*lineage-preserving aggregation"):
        _compile(
            [
                _record(
                    observation_id="obs_high_quality",
                    period_start=date(2024, 1, 1),
                    observed_value=10.0,
                    trust_weight=0.9,
                    source_id="source_a",
                    source_confidence_tier=SourceConfidenceTier.CORE,
                ),
                _record(
                    observation_id="obs_low_quality",
                    period_start=date(2024, 1, 1),
                    observed_value=20.0,
                    trust_weight=0.1,
                    source_id="source_b",
                    source_confidence_tier=SourceConfidenceTier.EXPLORATORY,
                    unit=second_unit,
                ),
            ]
        )


def test_conflicting_same_period_sources_fail_closed_before_source_tie_break() -> None:
    """A source ID cannot silently choose one conflicting measurement."""
    with pytest.raises(ValueError, match=r"Ambiguous observations|aggregation"):
        _compile(
            [
                _record(
                    observation_id="obs_a",
                    period_start=date(2024, 1, 1),
                    observed_value=10.0,
                    source_id="source_a",
                ),
                _record(
                    observation_id="obs_b",
                    period_start=date(2024, 1, 1),
                    observed_value=20.0,
                    source_id="source_b",
                ),
            ]
        )


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


def test_mismatched_time_and_value_lengths_fail_closed_before_alignment() -> None:
    """A shorter calendar axis cannot silently discard observed values."""
    target = _target(align=TargetAlignConfig(steps=2))
    config = _config(target, steps=2)

    with pytest.raises(ValueError, match="equal lengths"):
        prepare_targets(
            config,
            raw_targets={
                target.target_id: {
                    "values": np.asarray([1.0, 2.0, 3.0]),
                    "time": np.asarray([0.0, 1.0]),
                }
            },
            steps=2,
        )


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
    npt.assert_allclose(integer_aligned[target.target_id], float_aligned[target.target_id])


def test_empty_target_with_explicit_steps_is_not_an_observable_zero_series() -> None:
    """An empty source must not acquire an observed all-zero series by padding."""
    target = _target(align=TargetAlignConfig(steps=3, fill_value=0.0))
    config = _config(target)

    with pytest.raises(ValueError, match=r"empty|observ"):
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


@pytest.mark.parametrize("method", ["linear", "ffill"])
@pytest.mark.parametrize("values", [[1.0, 2.0, 3.0], [2.0, 1.0, 3.0]])
def test_duplicate_source_times_refuse_before_alignment(method: str, values: list[float]) -> None:
    """A duplicate coordinate cannot choose a source observation by row order."""
    target = _target(align=TargetAlignConfig(method=method))
    with pytest.raises(ValueError, match=r"duplicate.*time|time.*duplicate"):
        prepare_targets(
            _config(target),
            raw_targets={target.target_id: {"values": values, "time": [0.0, 0.0, 1.0]}},
            steps=3,
        )


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("axis", ["source", "target"])
def test_nonfinite_time_refuses_before_alignment(axis: str, nonfinite: float) -> None:
    """A finite value series cannot legitimate a nonfinite temporal coordinate."""
    target = _target()
    source = [0.0, nonfinite, 2.0] if axis == "source" else [0.0, 1.0, 2.0]
    destination = [0.0, nonfinite, 2.0] if axis == "target" else None
    with pytest.raises(ValueError, match=r"finite.*time|time.*finite"):
        prepare_targets(
            _config(target),
            raw_targets={target.target_id: {"values": [0.0, 10.0, 20.0], "time": source}},
            steps=3,
            time_axis=destination,
        )


@pytest.mark.parametrize("steps", [2, 3])
def test_inferred_axis_is_invariant_to_paired_source_permutation(steps: int) -> None:
    """Canonical endpoints and equal-length values come from admitted pairs."""
    target = _target()
    expected_values = [0.0, 20.0] if steps == 2 else [0.0, 10.0, 20.0]
    expected_axis = [0.0, 2.0] if steps == 2 else [0.0, 1.0, 2.0]
    for order in ([0, 1, 2], [2, 0, 1], [1, 2, 0]):
        values, _, axes = prepare_targets(
            _config(target, steps=steps),
            raw_targets={
                target.target_id: {
                    "values": np.asarray([0.0, 10.0, 20.0])[order],
                    "time": np.asarray([0.0, 1.0, 2.0])[order],
                }
            },
            steps=steps,
        )
        npt.assert_allclose(values[target.target_id], expected_values)
        npt.assert_allclose(axes[target.target_id], expected_axis)


def test_explicit_target_order_is_not_silently_sorted() -> None:
    """An explicit query order is retained while source pairs are canonicalized."""
    target = _target()
    values, _, axes = prepare_targets(
        _config(target, steps=2),
        raw_targets={target.target_id: {"values": [20.0, 0.0, 10.0], "time": [2, 0, 1]}},
        steps=2,
        time_axis=[1.5, 0.5],
    )
    npt.assert_allclose(values[target.target_id], [15.0, 5.0])
    assert axes[target.target_id] == [1.5, 0.5]


@pytest.mark.parametrize("axis", ["source", "target"])
@pytest.mark.parametrize("invalid", [[[0.0, 1.0]], [0.0, 1.0 + 2.0j]])
def test_time_coordinates_refuse_undeclared_dimensions_or_complex_projection(axis, invalid) -> None:
    """An axis cannot silently flatten or discard an imaginary component."""
    target = _target()
    with pytest.raises(ValueError, match=r"one-dimensional|real-valued"):
        prepare_targets(
            _config(target, steps=2),
            raw_targets={
                target.target_id: {
                    "values": [0.0, 10.0],
                    "time": invalid if axis == "source" else [0.0, 1.0],
                }
            },
            steps=2,
            time_axis=invalid if axis == "target" else None,
        )


@pytest.mark.parametrize("axis", ["source", "target"])
@pytest.mark.parametrize(
    "temporal",
    [
        np.asarray(["2024-01-01", "2024-02-01"], dtype="datetime64[ns]"),
        np.asarray([0, 1], dtype="timedelta64[D]"),
    ],
)
def test_temporal_dtype_requires_declared_numeric_conversion(axis, temporal) -> None:
    """A datetime dtype is not silently stripped into an inferred numeric unit."""
    target = _target()
    with pytest.raises(ValueError, match="explicit temporal conversion"):
        prepare_targets(
            _config(target, steps=2),
            raw_targets={
                target.target_id: {
                    "values": [0.0, 10.0],
                    "time": temporal if axis == "source" else [0.0, 1.0],
                }
            },
            steps=2,
            time_axis=temporal if axis == "target" else None,
        )


def test_different_period_units_require_an_explicit_upstream_conversion() -> None:
    """Different dates do not make share and percent the same target unit."""
    records = [
        _record(observation_id="unit_jan", period_start=date(2024, 1, 1), observed_value=0.5),
        _record(
            observation_id="unit_feb",
            period_start=date(2024, 2, 1),
            observed_value=50.0,
            unit="percent",
        ),
    ]
    original = [record.model_dump(mode="json") for record in records]
    with pytest.raises(ValueError, match=r"unit.*compatib|[Mm]ixed.*unit"):
        _compile(records)
    assert [record.model_dump(mode="json") for record in records] == original


def test_same_unit_and_declared_upstream_conversion_preserve_unit_and_lineage() -> None:
    """Already converted records remain useful without a metric-name heuristic."""
    first = _record(
        observation_id="converted_jan", period_start=date(2024, 1, 1), observed_value=0.5
    )
    converted = _record(
        observation_id="converted_feb",
        period_start=date(2024, 2, 1),
        observed_value=0.5,
    ).model_copy(
        update={
            "notes_json": {
                "upstream_transform": {
                    "version": "fixture.percent_to_share.v1",
                    "formula": "x/100",
                    "original_observation_id": "raw_percent_feb",
                    "original_unit": "percent",
                    "original_value": 50.0,
                }
            }
        }
    )
    bundle = _compile([converted, first])
    npt.assert_allclose(bundle.observed_value[TARGET_ID], [0.5, 0.5])
    assert bundle.targets[0].unit == "share"
    assert bundle.observation_id[TARGET_ID] == ("converted_jan", "converted_feb")
    assert (
        converted.notes_json["upstream_transform"]["original_observation_id"] == "raw_percent_feb"
    )


def test_point_and_interval_records_do_not_form_one_undeclared_temporal_target() -> None:
    """A point and an inclusive interval require an upstream alignment contract."""
    point = _record(observation_id="point", period_start=date(2024, 1, 1), observed_value=0.5)
    interval = _record(
        observation_id="interval", period_start=date(2024, 2, 1), observed_value=0.5
    ).model_copy(update={"period_end": date(2024, 2, 29)})
    with pytest.raises(ValueError, match="interval semantics"):
        _compile([point, interval])


def test_compiler_preserves_exact_interval_ends_through_missing_rows_and_placebo() -> None:
    """Source interval bounds remain paired metadata rather than inferred dates."""
    from polisyos.foundry.calibration.measurement import NegativeControlGenerator

    records = [
        _record(
            observation_id="march_interval", period_start=date(2024, 3, 1), observed_value=0.3
        ).model_copy(update={"period_end": date(2024, 3, 20)}),
        _record(
            observation_id="january_interval", period_start=date(2024, 1, 1), observed_value=0.1
        ).model_copy(update={"period_end": date(2024, 1, 31)}),
    ]
    # The compiler uses declared panel periods, not an invented complete
    # calendar. A different metric declares February, leaving a real missing
    # cell for this target while keeping its source intervals unchanged.
    records.append(
        _record(
            observation_id="other_february", period_start=date(2024, 2, 1), observed_value=0.2
        ).model_copy(update={"metric_id": "other_rate"})
    )
    compiled = _compile(records)
    assert compiled.period_end[TARGET_ID] == ("2024-01-31", None, "2024-03-20")
    assert compiled.observation_id[TARGET_ID][0] == "january_interval"
    assert compiled.coverage_estimate[TARGET_ID][1] == 0.0
    placebo, specs = NegativeControlGenerator(shift_periods=4).generate(compiled)
    placebo_id = specs[0].placebo_target_id
    assert placebo.period_end[placebo_id] == ("2024-05-31", None, "2024-07-20")
    assert placebo.targets[0].unit == "share"
    assert placebo.targets[0].interval_semantics == "inclusive_interval"


def test_placebo_interval_end_cannot_escape_holdout_boundary() -> None:
    """A declared interval is excluded when only its end enters holdout."""
    from dataclasses import replace

    from polisyos.foundry.calibration.measurement import NegativeControlGenerator
    from polisyos.ir.observation.compiler import (
        CalibrationSplitLabel,
        CalibrationSplitPlan,
        CalibrationSplitWindow,
    )

    compiled = _compile(
        [
            _record(
                observation_id="january_span", period_start=date(2024, 1, 1), observed_value=0.1
            ).model_copy(update={"period_end": date(2024, 1, 31)})
        ]
    )
    split_plan = CalibrationSplitPlan(
        windows=[
            CalibrationSplitWindow(
                label=CalibrationSplitLabel.HOLDOUT,
                start_date=date(2024, 5, 20),
                end_date=date(2024, 5, 31),
            ),
            CalibrationSplitWindow(label=CalibrationSplitLabel.TEST),
        ]
    )
    # The declared Jan1-Jan31 interval translates to May1-May31, and the
    # established split owner must see its full inclusive bounds.
    blocked, specs = NegativeControlGenerator(shift_periods=4).generate(
        compiled, split_plan=split_plan
    )
    assert blocked.targets == ()
    assert specs == ()
    # Removing only the declaration restores the historical unknown-bound
    # behavior; no invented interval end may be supplied on its behalf.
    undeclared, legacy_specs = NegativeControlGenerator(shift_periods=4).generate(
        replace(compiled, period_end={}), split_plan=split_plan
    )
    assert len(legacy_specs) == 1
    assert undeclared.period_end == {}
    assert undeclared.split_label[legacy_specs[0].placebo_target_id] == ("test",)


def test_placebo_nonoverlap_uses_declared_source_interval_not_only_start() -> None:
    """A shifted start cannot hide overlap with the original occupied interval."""
    from polisyos.foundry.calibration.measurement import NegativeControlGenerator

    start, end = date(2024, 1, 1), date(2024, 4, 30)
    compiled = _compile(
        [
            _record(observation_id="long_span", period_start=start, observed_value=0.1).model_copy(
                update={"period_end": end}
            )
        ]
    )
    placebo, specs = NegativeControlGenerator(shift_periods=1).generate(compiled)
    spec = specs[0]
    shifted_start = date.fromisoformat(placebo.time_axis[spec.placebo_target_id][0])
    shifted_end = date.fromisoformat(placebo.period_end[spec.placebo_target_id][0])
    assert shifted_start > end
    assert shifted_end - shifted_start == end - start
    assert spec.shift_periods == 4
