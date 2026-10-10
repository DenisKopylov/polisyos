from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

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
