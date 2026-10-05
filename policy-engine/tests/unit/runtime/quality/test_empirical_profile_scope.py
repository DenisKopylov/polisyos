"""Exercise empirical profile scope and unit refusals through the DuckDB owner gateway."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from polisyos.runtime.quality import data_state_substrate, substrate_registry
from polisyos.runtime.quality.generation_cycle import (
    RealValueOwnerGateway,
    ValueOwnerAccessError,
)

_OUTCOME = "cells.distress_score"


def _catalog_gateway(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rows: list[tuple[str, int, float, str, str, str | None]],
) -> RealValueOwnerGateway:
    """Create a private DuckDB catalog and route both real owners to it."""

    catalog_path = tmp_path / "l1-dcat.duckdb"
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute(
            "CREATE TABLE ds_observations ("
            "canonical_var VARCHAR, value DOUBLE, year INTEGER, survey_year INTEGER, "
            "wave INTEGER, country_code VARCHAR, dataset_id VARCHAR, "
            "observation_id VARCHAR, condition_json VARCHAR)"
        )
        connection.execute("CREATE TABLE ds_metric_bindings (metric_id VARCHAR)")
        connection.execute("INSERT INTO ds_metric_bindings VALUES (?)", [_OUTCOME])
        connection.execute(
            "CREATE TABLE ds_datasets (dataset_id VARCHAR, polisyos_metrics VARCHAR[])"
        )
        dataset_ids = sorted({dataset_id for _, _, _, dataset_id, _, _ in rows})
        connection.executemany(
            "INSERT INTO ds_datasets VALUES (?, ?)",
            [(dataset_id, [_OUTCOME]) for dataset_id in dataset_ids],
        )
        connection.executemany(
            "INSERT INTO ds_observations VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, ?)",
            [
                (
                    _OUTCOME,
                    value,
                    period,
                    country_code,
                    dataset_id,
                    observation_id,
                    None
                    if measurement_unit is None
                    else json.dumps({"unit": measurement_unit}),
                )
                for country_code, period, value, dataset_id, observation_id, measurement_unit in rows
            ],
        )

    paths = SimpleNamespace(l1_dcat_path=catalog_path)
    monkeypatch.setattr(
        data_state_substrate,
        "default_substrate_catalog_paths",
        lambda _repo_root: paths,
    )
    monkeypatch.setattr(
        substrate_registry,
        "default_substrate_catalog_paths",
        lambda _repo_root: paths,
    )
    return RealValueOwnerGateway(
        repo_root=tmp_path,
        # A missing explicit overlay gives the actual read API its baseline-only
        # mode, keeping this test isolated from any shared catalog or overlay.
        catalog_overlay_path=tmp_path / "absent-overlay.duckdb",
    )


def _profile(gateway: RealValueOwnerGateway, region: str):
    return gateway.load_value_data_profile(
        candidate=SimpleNamespace(atom=SimpleNamespace(target_world_slots=(_OUTCOME,))),
        problem=SimpleNamespace(
            outcome_of_interest=SimpleNamespace(target_variable=_OUTCOME),
            jurisdiction_time=SimpleNamespace(region=region),
        ),
        world_record=object(),
    )


def test_supported_country_scope_filters_foreign_rows_before_profile_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A foreign prefix cannot consume the owner's bounded rows before scope."""

    rows = [
        (
            "AF",
            1900 + index,
            float(index),
            "foreign-source",
            f"foreign-{index}",
            "ratio",
        )
        for index in range(20_001)
    ]
    for country_code, offset in (("UA", 0), ("PL", 100)):
        rows.extend(
            (
                country_code,
                2020 + index,
                float(offset + index),
                "scoped-source",
                f"{country_code.lower()}-{index}",
                "ratio",
            )
            for index in range(4)
        )
    gateway = _catalog_gateway(tmp_path, monkeypatch, rows)

    ukrainian = _profile(gateway, "UA")
    polish = _profile(gateway, "PL")

    assert ukrainian.owner_row_count == polish.owner_row_count == 4
    assert {row.unit_id for row in ukrainian.rows} == {"UA"}
    assert {row.unit_id for row in polish.rows} == {"PL"}
    assert tuple(row.period_id for row in ukrainian.rows) == (2020, 2021, 2022, 2023)
    assert tuple(row.period_id for row in polish.rows) == (2020, 2021, 2022, 2023)
    assert ukrainian.content_hash != polish.content_hash
    assert ukrainian.treatment_assignment_status == "owner_assignment_unresolved"


def test_non_country_scope_is_a_typed_refusal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A basin-like region is not silently copied into the country-code column."""

    rows = [
        ("UA", 2020 + index, float(index), "source", f"ua-{index}", "ratio")
        for index in range(4)
    ]
    gateway = _catalog_gateway(tmp_path, monkeypatch, rows)

    with pytest.raises(ValueOwnerAccessError) as raised:
        _profile(gateway, "Dniester basin")

    assert raised.value.code == "acquire_data:value_scope_binding_missing"


@pytest.mark.parametrize(
    ("case", "units", "dataset_ids", "message"),
    [
        ("unit-missing", (None, None, None, None), ("source",) * 4, "do not carry"),
        ("unit-mixed", ("ratio", "ratio", "percent", "percent"), ("source",) * 4, "multiple condition_json.unit"),
        ("dataset-mixed", ("ratio",) * 4, ("source-a", "source-a", "source-b", "source-b"), "multiple or missing dataset/source identities"),
    ],
)
def test_untyped_mixed_unit_and_multi_dataset_profiles_refuse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    units: tuple[str | None, ...],
    dataset_ids: tuple[str, ...],
    message: str,
) -> None:
    """The consumer refuses untyped, mixed-unit, and cross-dataset profiles."""

    rows = [
        (
            "UA",
            2020 + index,
            float(index),
            dataset_ids[index],
            f"{case}-{index}",
            units[index],
        )
        for index in range(4)
    ]
    gateway = _catalog_gateway(tmp_path / case, monkeypatch, rows)

    with pytest.raises(ValueOwnerAccessError) as raised:
        _profile(gateway, "UA")

    assert raised.value.code == "acquire_data:value_owner_unit_binding_ambiguous"
    assert message in str(raised.value)
