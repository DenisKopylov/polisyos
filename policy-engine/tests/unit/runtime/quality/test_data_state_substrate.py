from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import polisyos.runtime.quality.data_state_substrate as data_state_substrate_module
from polisyos.runtime.quality.data_state_substrate import (
    DataStateSubstrateError,
    l1_dcat_variable_availability,
)
from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths


def test_missing_catalog_and_unlisted_variable_have_distinct_owner_outcomes(
    tmp_path: Path,
) -> None:
    """Catalog absence is not reported as a variable-level unavailable result."""

    without_catalog = tmp_path / "catalog-absent"
    with pytest.raises(DataStateSubstrateError) as missing_catalog:
        l1_dcat_variable_availability(without_catalog, "unlisted-policy-metric")
    assert missing_catalog.value.code == "l1_dcat_missing"

    catalog_path = default_substrate_catalog_paths(tmp_path).l1_dcat_path
    catalog_path.parent.mkdir(parents=True)
    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute("CREATE TABLE ds_metric_bindings (metric_id VARCHAR)")
        connection.execute("CREATE TABLE ds_observations (canonical_var VARCHAR)")
        connection.execute("CREATE TABLE ds_datasets (polisyos_metrics VARCHAR[])")

    unavailable = l1_dcat_variable_availability(tmp_path, "unlisted-policy-metric")

    assert unavailable.status == "unavailable"
    assert unavailable.variable_id == "unlisted-policy-metric"
    assert (
        unavailable.dataset_count,
        unavailable.metric_binding_count,
        unavailable.observation_count,
    ) == (0, 0, 0)



def test_l1_dcat_count_queries_return_positive_counts_from_duckdb(tmp_path: Path) -> None:
    # Exercise the actual owner schema with nonzero results in each scalar.
    catalog_path = default_substrate_catalog_paths(tmp_path).l1_dcat_path
    catalog_path.parent.mkdir(parents=True)
    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute("CREATE TABLE ds_metric_bindings (metric_id VARCHAR)")
        connection.execute("CREATE TABLE ds_observations (canonical_var VARCHAR)")
        connection.execute("CREATE TABLE ds_datasets (polisyos_metrics VARCHAR[])")
        connection.execute("INSERT INTO ds_metric_bindings VALUES ('policy-metric')")
        connection.execute(
            "INSERT INTO ds_observations VALUES ('policy-metric'), ('policy-metric')"
        )
        connection.execute("INSERT INTO ds_datasets VALUES (['policy-metric'])")

    result = l1_dcat_variable_availability(tmp_path, "policy-metric")

    assert result.status == "available"
    assert (
        result.dataset_count,
        result.metric_binding_count,
        result.observation_count,
    ) == (1, 1, 2)


@pytest.mark.parametrize(
    ("row", "expected_code"),
    [
        (None, "l1_dcat_scalar_row_missing"),
        ((), "l1_dcat_scalar_row_shape_invalid"),
        ((0, 1), "l1_dcat_scalar_row_shape_invalid"),
        (("0",), "l1_dcat_scalar_value_invalid"),
        ((True,), "l1_dcat_scalar_value_invalid"),
        ((-1,), "l1_dcat_scalar_value_invalid"),
    ],
)
def test_l1_dcat_scalar_consumer_fails_closed_on_absent_or_malformed_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    row: tuple[object, ...] | None,
    expected_code: str,
) -> None:
    # Drive the public consumer with a controlled malformed backend row.
    class _ControlledConnection:
        closed = False

        def execute(self, query: str, parameters: list[object]) -> _ControlledConnection:
            del query, parameters
            return self

        def fetchone(self) -> tuple[object, ...] | None:
            return row

        def close(self) -> None:
            self.closed = True

    catalog_path = default_substrate_catalog_paths(tmp_path).l1_dcat_path
    catalog_path.parent.mkdir(parents=True)
    catalog_path.touch()
    connection = _ControlledConnection()
    monkeypatch.setattr(
        data_state_substrate_module.data_forge_read_api.catalog,
        "open_catalog_read_session",
        lambda *_args, **_kwargs: connection,
    )

    with pytest.raises(DataStateSubstrateError) as failure:
        l1_dcat_variable_availability(tmp_path, "policy-metric")

    assert failure.value.code == expected_code
    assert connection.closed
