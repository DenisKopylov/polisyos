from __future__ import annotations

from datetime import date

from polisyos.ir.observation.compiler import (
    CalibrationSplitLabel,
    CalibrationSplitter,
    CalibrationTargetBundleCompiler,
    NegativeControlGenerator,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
)
from polisyos.ir.observation.measurement import (
    SchemaChangepoint,
    SchemaRegimeRegistry,
    SchemaRegimeSpec,
)
from polisyos.ir.types import TimeFrequency


def _record(
    observation_id: str,
    *,
    period_start: date,
    period_end: date,
    cell_id: str,
    metric_id: str = "employment_rate",
    observed_value: float = 0.5,
    schema_regime_id: str = "employment_schema_v1",
) -> ObservationRecord:
    return ObservationRecord(
        observation_id=observation_id,
        family=ObservationFamily.LABOR_MARKET,
        time_grain=TimeFrequency.MONTH,
        period_start=period_start,
        period_end=period_end,
        entity_scope=EntityScope.CELL,
        cell_id=cell_id,
        metric_id=metric_id,
        observed_value=observed_value,
        unit="share",
        coverage_estimate=0.9,
        measurement_bias_flag=False,
        censoring_mask=False,
        trust_weight=0.8,
        lag_days_estimate=3,
        source_id="admin_employment",
        source_version="2024.01",
        regime_id="wartime_2024",
        shock_mask=False,
        schema_regime_id=schema_regime_id,
        identification_mode=IdentificationMode.PROXY_IDENTIFIED,
        proxy_source_id="administrative_employment",
        source_confidence_tier=SourceConfidenceTier.VALIDATED,
    )


def _panel() -> ObservationPanel:
    return ObservationPanel(
        panel_id="panel_labor_monthly",
        family=ObservationFamily.LABOR_MARKET,
        time_grain=TimeFrequency.MONTH,
        records=[
            _record(
                "obs_a_2023_11",
                period_start=date(2023, 11, 1),
                period_end=date(2023, 11, 30),
                cell_id="cell_a",
                observed_value=0.55,
            ),
            _record(
                "obs_a_2024_01",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 1, 31),
                cell_id="cell_a",
                observed_value=0.56,
            ),
            _record(
                "obs_b_2024_06",
                period_start=date(2024, 6, 1),
                period_end=date(2024, 6, 30),
                cell_id="cell_b",
                observed_value=0.61,
                schema_regime_id="employment_schema_v2",
            ),
            _record(
                "obs_a_2025_01",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 1, 31),
                cell_id="cell_a",
                observed_value=0.6,
                schema_regime_id="employment_schema_v2",
            ),
        ],
    )


def test_calibration_splitter_is_regime_aware() -> None:
    registry = SchemaRegimeRegistry(
        regimes={
            "employment_schema_v1": SchemaRegimeSpec(
                schema_regime_id="employment_schema_v1",
                source_version="1.0",
                effective_start=date(2023, 1, 1),
                effective_end=date(2024, 1, 31),
            ),
            "employment_schema_v2": SchemaRegimeSpec(
                schema_regime_id="employment_schema_v2",
                source_version="2.0",
                effective_start=date(2024, 2, 1),
            ),
        },
        changepoints=[
            SchemaChangepoint(
                changepoint_id="employment_cp_2024_02",
                effective_date=date(2024, 2, 1),
                from_schema_regime_id="employment_schema_v1",
                to_schema_regime_id="employment_schema_v2",
            )
        ],
    )
    splitter = CalibrationSplitter(schema_regime_registry=registry)
    panel = _panel()
    split_plan = splitter.plan_for_panel(panel)
    labels = {
        record.observation_id: splitter.label_record(record, split_plan=split_plan)
        for record in panel.records
    }

    assert labels["obs_a_2023_11"] == CalibrationSplitLabel.TRAIN
    assert labels["obs_a_2024_01"] == CalibrationSplitLabel.HOLDOUT
    assert labels["obs_b_2024_06"] == CalibrationSplitLabel.VALIDATION
    assert labels["obs_a_2025_01"] == CalibrationSplitLabel.TEST


def test_compiler_aligns_targets_and_masks_missing_rows() -> None:
    compiler = CalibrationTargetBundleCompiler(
        schema_regime_registry=SchemaRegimeRegistry.default(),
    )
    bundle = compiler.compile(_panel())

    target_a = "labor_market.employment_rate.cell.cell_a"
    target_b = "labor_market.employment_rate.cell.cell_b"

    assert target_a in bundle.observed_value
    assert target_b in bundle.observed_value
    assert bundle.observed_value[target_a].shape[0] == 4
    assert float(bundle.coverage_estimate[target_b][0]) == 0.0
    assert float(bundle.trust_weight[target_b][0]) == 0.0
    assert bundle.observation_id[target_b][0].startswith("missing.")
    assert bundle.identification_mode[target_a][0] in {
        IdentificationMode.PROXY_IDENTIFIED,
        IdentificationMode.BOUNDS_ONLY,
    }


def test_negative_control_generator_produces_non_overlapping_placebos() -> None:
    compiler = CalibrationTargetBundleCompiler()
    bundle = compiler.compile(_panel())
    placebo_bundle, specs = NegativeControlGenerator().generate(bundle)

    assert specs
    for spec in specs:
        assert set(spec.source_time_axis).isdisjoint(spec.placebo_time_axis)
        assert spec.placebo_target_id.startswith("placebo.")
        assert spec.placebo_target_id in placebo_bundle.observed_value
