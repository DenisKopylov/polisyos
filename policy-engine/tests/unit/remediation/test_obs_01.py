"""Test-first witnesses for OBS-01 period relocation and B146 repair.

The canonical owner is intentionally loaded lazily because this file is the
test-first half of the move: the production ``observation`` module does not
exist on the OBS-01 base yet.  The direct helper witnesses are strict about
unknown periods, while the series and consumer witnesses allow the owner to
represent an invalid row as quarantine or typed absence.  In no case may an
invalid value acquire a synthetic 2025 date.
"""

from __future__ import annotations

import importlib
from typing import Any

import pandas as pd
import pytest

from polisyos.data_forge.domains.ukraine.models import SourceConfig, StageId
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.contracts import EntityScope, ObservationFamily

pytestmark = pytest.mark.unit


def _load_builder_surface() -> tuple[Any, Any, Any, Any, Any]:
    """Load the canonical and compatibility builder modules at test time."""
    try:
        observation = importlib.import_module(
            "polisyos.data_forge.domains.ukraine.builders.observation"
        )
        common = importlib.import_module("polisyos.data_forge.domains.ukraine.builders.common")
        sources = importlib.import_module("polisyos.data_forge.domains.ukraine.builders.sources")
        demography = importlib.import_module(
            "polisyos.data_forge.domains.ukraine.builders.demography"
        )
        builders = importlib.import_module("polisyos.data_forge.domains.ukraine.builders")
    except ImportError as exc:
        raise AssertionError(
            "OBS-01 canonical observation owner and existing builder callers must import"
        ) from exc
    return observation, common, sources, demography, builders


@pytest.mark.parametrize(
    ("period_value", "time_grain", "expected_start", "expected_end"),
    [
        ("2024-02", TimeFrequency.MONTH, "2024-02-01", "2024-02-29"),
        ("2023M02", TimeFrequency.MONTH, "2023-02-01", "2023-02-28"),
        ("2024Q2", TimeFrequency.QUARTER, "2024-04-01", "2024-06-30"),
        ("2024", TimeFrequency.YEAR, "2024-01-01", "2024-12-31"),
    ],
    ids=["leap-month", "ordinary-month", "quarter", "year"],
)
def test_canonical_period_owner_uses_inclusive_calendar_bounds(
    period_value: str,
    time_grain: TimeFrequency,
    expected_start: str,
    expected_end: str,
) -> None:
    """Valid month, quarter, and year periods preserve inclusive boundaries."""
    observation, *_ = _load_builder_surface()

    period_start, period_end = observation._period_to_dates(period_value, time_grain)

    assert period_start.isoformat() == expected_start
    assert period_end.isoformat() == expected_end


@pytest.mark.parametrize(
    "period_value",
    ["2024-13", "2024-00", "not-a-period", "", None, pd.NA],
    ids=[
        "month-too-large",
        "month-too-small",
        "malformed",
        "empty",
        "missing-none",
        "missing-na",
    ],
)
def test_period_owner_rejects_unknown_periods_without_2025_fallback(
    period_value: object,
) -> None:
    """Unknown or invalid values fail closed instead of becoming January 2025."""
    observation, *_ = _load_builder_surface()

    with pytest.raises((TypeError, ValueError)):
        observation._period_to_dates(period_value, TimeFrequency.MONTH)


def test_period_series_preserves_unique_mapping_and_typed_absence_for_bad_rows() -> None:
    """Series conversion keeps valid rows and marks invalid rows without inventing dates."""
    observation, *_ = _load_builder_surface()
    values = pd.Series(["2024-02", "2024-02", "2024-13", None], dtype="string")

    period_start, period_end = observation._period_series_to_iso_bounds(
        values,
        time_grain=TimeFrequency.MONTH,
    )

    assert period_start.iloc[0] == "2024-02-01"
    assert period_end.iloc[0] == "2024-02-29"
    assert period_start.iloc[1] == period_start.iloc[0]
    assert period_end.iloc[1] == period_end.iloc[0]
    assert pd.isna(period_start.iloc[2])
    assert pd.isna(period_end.iloc[2])
    assert pd.isna(period_start.iloc[3])
    assert pd.isna(period_end.iloc[3])
    assert not period_start.astype("string").str.contains("2025", na=False).any()
    assert not period_end.astype("string").str.contains("2025", na=False).any()


def test_period_series_precomputes_each_unique_valid_period_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The relocation keeps the existing unique-period precompute optimization."""
    observation, *_ = _load_builder_surface()
    original = observation._period_to_dates
    calls: list[object] = []

    def counting_period_to_dates(value: object, time_grain: TimeFrequency):
        calls.append(value)
        return original(value, time_grain)

    monkeypatch.setattr(observation, "_period_to_dates", counting_period_to_dates)
    observation._period_series_to_iso_bounds(
        pd.Series(["2024-02", "2024-02", "2024-03"], dtype="string"),
        time_grain=TimeFrequency.MONTH,
    )

    assert calls == ["2024-02", "2024-03"]


def test_source_observation_consumer_uses_canonical_period_bounds() -> None:
    """The real source-frame consumer carries leap bounds and no synthetic dates."""
    _, _, sources, _, _ = _load_builder_surface()
    source = SourceConfig(
        source_id="household_period_witness",
        display_name="Household period witness",
        stage_id=StageId.D1,
        normalized_artifact="household.parquet",
        required_columns=["agent_id", "period_id", "household_income"],
        metric_columns=["household_income"],
        observation_family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
        entity_scope=EntityScope.HOUSEHOLD,
    )
    frame = pd.DataFrame(
        {
            "agent_id": [
                "household::valid",
                "household::invalid",
                "household::missing",
            ],
            "period_id": ["2024-02", "2024-13", None],
            "household_income": [100.0, 200.0, 300.0],
        }
    )

    metric_id, observations = next(
        iter(sources._observation_metric_frames_from_frame(source, frame))
    )

    assert metric_id == "household_income"
    valid = observations.loc[observations["entity_id"] == "household::valid"].iloc[0]
    assert valid["period_start"] == "2024-02-01"
    assert valid["period_end"] == "2024-02-29"
    assert not observations["period_start"].astype("string").str.contains("2025", na=False).any()
    assert not observations["period_end"].astype("string").str.contains("2025", na=False).any()


def test_household_demography_consumer_preserves_valid_period_and_rejects_bad_dates() -> None:
    """The household observation panel consumes the moved helper, not a copied parser."""
    _, _, _, demography, _ = _load_builder_surface()
    calibrated = pd.DataFrame(
        {
            "cell_id": ["cell::01::valid", "cell::01::invalid", "cell::01::missing"],
            "region_code": ["01", "01", "01"],
            "period_id": ["2024-02", "2024-13", None],
            "household_income_mean": [100.0, 200.0, 300.0],
            "household_weight_sum": [1.0, 1.0, 1.0],
            "measurement_bias_flag": [False, False, False],
            "trust_weight": [0.95, 0.95, 0.95],
        }
    )

    observations = demography._build_household_distribution_observation_panel(calibrated)

    valid = observations.loc[observations["cell_id"] == "cell::01::valid"].iloc[0]
    assert valid["period_start"] == "2024-02-01"
    assert valid["period_end"] == "2024-02-29"
    assert not observations["period_start"].astype("string").str.contains("2025", na=False).any()
    assert not observations["period_end"].astype("string").str.contains("2025", na=False).any()


def test_period_helpers_have_one_canonical_owner_and_compatibility_aliases() -> None:
    """Common, sources, demography, and the package facade point to observation helpers."""
    observation, common, sources, demography, builders = _load_builder_surface()

    assert observation._period_to_dates.__module__ == observation.__name__
    assert observation._period_series_to_iso_bounds.__module__ == observation.__name__
    assert common._period_to_dates is observation._period_to_dates
    assert sources._period_series_to_iso_bounds is observation._period_series_to_iso_bounds
    assert demography._period_series_to_iso_bounds is observation._period_series_to_iso_bounds
    assert builders._period_to_dates is observation._period_to_dates
    assert builders._period_series_to_iso_bounds is observation._period_series_to_iso_bounds


def test_graph_consumer_quarantines_missing_or_invalid_period_edges() -> None:
    """Graph edges never acquire a synthetic period when source timing is absent."""
    _, common, _, _, _ = _load_builder_surface()
    frame = pd.DataFrame(
        {
            "source_agent_id": ["agent::valid", "agent::invalid", "agent::missing"],
            "target_agent_id": ["agent::target", "agent::target", "agent::target"],
            "amount": [1.0, 2.0, 3.0],
            "period_id": ["2024-02", "2024-13", None],
        }
    )

    arrays = common._graph_arrays_from_edges(
        frame,
        src_col="source_agent_id",
        dst_col="target_agent_id",
        weight_col="amount",
    )

    assert arrays["src_ids"].tolist() == ["agent::valid"]
    assert arrays["period_id"].tolist() == ["2024-02"]
    assert not any("2025" in period for period in arrays["period_id"])


def test_builder_facade_exports_only_the_declared_stage_surface() -> None:
    """Dependency modules and private implementation helpers stay off __all__."""
    _, _, _, _, builders = _load_builder_surface()

    assert {
        "calendar",
        "re",
        "pd",
        "date",
        "TimeFrequency",
    }.isdisjoint(builders.__all__)


def test_legacy_runner_private_facade_aliases_remain_explicit_only() -> None:
    """Ops-runner compatibility names remain available without public leakage."""
    _, common, _, _, builders = _load_builder_surface()
    compatibility_names = (
        "_ensure_agent_numeric_columns",
        "_extract_unresolved_identity_rows",
        "_link_participants",
        "_load_source_frame",
        "_read_parquet_frame",
        "_resolve_agent_lookup",
        "_select_procurement_frame",
        "_write_frame",
        "_write_json",
    )

    for name in compatibility_names:
        assert getattr(builders, name) is getattr(common, name)
        assert name not in builders.__all__


def test_period_projection_is_positional_for_duplicate_indices_and_reordering() -> None:
    """Equal labels do not merge different periods or hide malformed input."""
    observation, *_ = _load_builder_surface()
    values = pd.Series(
        ["2024-02", "2023-02", "2024-13", None, "NaN", ""],
        index=[7, 7, 7, 1, 1, 7],
        dtype="string",
    )
    expected = [
        ("2024-02-01", "2024-02-29", "valid", "<none>"),
        ("2023-02-01", "2023-02-28", "valid", "<none>"),
        ("<none>", "<none>", "invalid", "period_identifier_invalid"),
        ("<none>", "<none>", "missing", "period_identifier_missing"),
        ("<none>", "<none>", "invalid", "period_identifier_invalid"),
        ("<none>", "<none>", "missing", "period_identifier_missing"),
    ]

    def rows(series: pd.Series) -> list[tuple[str, ...]]:
        result = observation.project_ukraine_observation_periods(
            series, time_grain=TimeFrequency.MONTH
        )
        assert all(item.index.equals(series.index) for item in result)
        return list(zip(*(item.fillna("<none>").tolist() for item in result), strict=True))

    assert rows(values) == expected
    assert rows(values.reset_index(drop=True)) == expected
    order = [5, 2, 0, 4, 1, 3]
    assert rows(values.iloc[order]) == [expected[i] for i in order]
    old_start, old_end = observation._period_series_to_iso_bounds(
        values, time_grain=TimeFrequency.MONTH
    )
    assert old_start.fillna("<none>").tolist() == [row[0] for row in expected]
    assert old_end.fillna("<none>").tolist() == [row[1] for row in expected]


def test_source_and_household_consumers_keep_duplicate_rows_by_position() -> None:
    """Producer rows and calendar facts stay paired after index/order changes."""
    _, _, sources, demography, _ = _load_builder_surface()
    source = SourceConfig(
        source_id="period_position",
        display_name="period position",
        stage_id=StageId.D1,
        normalized_artifact="witness.parquet",
        required_columns=["agent_id", "period_id", "income"],
        metric_columns=["income"],
        observation_family=ObservationFamily.HOUSEHOLD_DISTRIBUTION,
        entity_scope=EntityScope.HOUSEHOLD,
    )
    frame = pd.DataFrame(
        {
            "agent_id": ["a", "b", "c", "d"],
            "cell_id": ["a", "b", "c", "d"],
            "region_code": ["01", "01", "01", "01"],
            "period_id": ["2024-02", "2023-02", None, "2024-13"],
            "income": [1.0, 2.0, 3.0, 4.0],
            "trust_weight": [0.95, 0.95, 0.95, 0.95],
            "household_income_mean": [1.0, 2.0, 3.0, 4.0],
        },
        index=[7, 7, 1, 7],
    )
    expected = {
        "a": ("2024-02-29", "valid"),
        "b": ("2023-02-28", "valid"),
        "c": ("<none>", "missing"),
        "d": ("<none>", "invalid"),
    }

    def by_entity(panel: pd.DataFrame) -> dict[str, tuple[str, str]]:
        return {
            str(row.entity_id): (
                "<none>" if pd.isna(row.period_end) else str(row.period_end),
                str(row.period_disposition),
            )
            for row in panel.itertuples(index=False)
        }

    for values in (frame, frame.reset_index(drop=True), frame.iloc[[3, 1, 0, 2]]):
        _, observations = next(iter(sources._observation_metric_frames_from_frame(source, values)))
        assert by_entity(observations) == expected
        household = demography._build_household_distribution_observation_panel(values)
        assert by_entity(household) == expected
        unresolved = household[household["period_disposition"].isin(["missing", "invalid"])]
        assert unresolved["regime_id"].isna().all()
        assert unresolved["schema_regime_id"].isna().all()


def test_coarse_period_cannot_acquire_finer_declared_precision() -> None:
    """A year or quarter must not become an invented month."""
    observation, *_ = _load_builder_surface()
    start, end, disposition, reason = observation.project_ukraine_observation_periods(
        pd.Series(["2024", "2024Q2", "2024-02"], dtype="string"),
        time_grain=TimeFrequency.MONTH,
    )
    assert disposition.tolist() == ["limited", "limited", "valid"]
    assert reason.iloc[:2].tolist() == ["period_precision_insufficient"] * 2
    assert start.isna().tolist() == [True, True, False]
    assert end.iloc[2] == "2024-02-29"
    assert observation._period_to_dates("2024", TimeFrequency.YEAR)[1].isoformat() == "2024-12-31"
    assert (
        observation._period_to_dates("2024Q2", TimeFrequency.QUARTER)[0].isoformat() == "2024-04-01"
    )
