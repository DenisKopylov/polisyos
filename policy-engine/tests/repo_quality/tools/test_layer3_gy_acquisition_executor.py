from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from tools.quality.validation import layer3_gy_acquisition_executor as executor


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


@pytest.fixture
def selection_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    census = _write_json(
        tmp_path / "census.json",
        {
            "growth_backlog": [
                {
                    "variable_id": "untyped.residual",
                    "rank": 1,
                    "gap_kind": "binding_gap",
                    "demand_sources": ["fixture.untyped"],
                },
                {
                    "variable_id": "government.balance",
                    "rank": 2,
                    "gap_kind": "binding_gap",
                    "demand_sources": ["fixture.fiscal"],
                },
            ],
            "family_scorecards": [
                {
                    "connector_id": "worldbank.wdi",
                    "family_liveness_state": "live_characterized",
                    "liveness_counts": {"alive_schema_unverified": 1},
                },
                {
                    "connector_id": "dead.family",
                    "family_liveness_state": "characterization_failed",
                    "liveness_counts": {"dead": 1},
                },
            ],
        },
    )
    substrate = _write_json(
        tmp_path / "substrate.json",
        {
            "world_slots": [
                {
                    "slot_id": "government.balance",
                    "unit": "usd",
                    "entity_scope": "global",
                }
            ]
        },
    )
    catalog = tmp_path / "catalog.duckdb"
    con = duckdb.connect(str(catalog))
    con.execute(
        """
        CREATE TABLE ds_datasets (
            id VARCHAR,
            source VARCHAR,
            agency VARCHAR,
            title VARCHAR,
            description VARCHAR,
            temporal_start VARCHAR,
            temporal_end VARCHAR,
            access_license VARCHAR,
            access_auth_required BOOLEAN,
            execution_tier VARCHAR
        )
        """
    )
    con.execute(
        """
        CREATE TABLE ds_distributions (
            id VARCHAR,
            dataset_id VARCHAR,
            url VARCHAR,
            connector_type VARCHAR,
            profile_id VARCHAR,
            source_locator VARCHAR,
            quality_score DOUBLE,
            parser_supported BOOLEAN
        )
        """
    )
    con.execute(
        """
        CREATE TABLE ds_metric_bindings (
            metric_id VARCHAR,
            dataset_id VARCHAR,
            distribution_id VARCHAR,
            connector_id VARCHAR,
            profile_id VARCHAR,
            request_dataset_id VARCHAR,
            confidence DOUBLE,
            default_filters JSON,
            execution_tier VARCHAR
        )
        """
    )
    rows = (
        (
            "usd-dataset",
            "Fiscal balance, cash surplus/deficit (current US$)",
            "Current US dollar fiscal balance.",
            "usd-dist",
            "GC.BAL.CASH.CD",
            "gov_balance",
            0.87,
            0.98,
        ),
        (
            "percent-dataset",
            "Fiscal balance (% of GDP)",
            "Percent of GDP fiscal balance.",
            "percent-dist",
            "GC.BAL.CASH.GD.ZS",
            "gov_balance",
            0.99,
            1.0,
        ),
        (
            "trade-dataset",
            "Trade balance (current US$)",
            "Current US dollar trade balance.",
            "trade-dist",
            "NE.RSB.GNFS.CD",
            "trade_balance",
            0.95,
            1.0,
        ),
    )
    for (
        dataset_id,
        title,
        description,
        distribution_id,
        indicator,
        metric,
        confidence,
        quality,
    ) in rows:
        con.execute(
            "INSERT INTO ds_datasets VALUES (?, 'worldbank', 'World Bank', ?, ?, NULL, NULL, "
            "'CC-BY-4.0', FALSE, 'transport_ready')",
            [dataset_id, title, description],
        )
        con.execute(
            "INSERT INTO ds_distributions VALUES (?, ?, 'https://api.worldbank.org/v2', "
            "'worldbank.wdi', 'worldbank_wdi', 'fixture', ?, TRUE)",
            [distribution_id, dataset_id, quality],
        )
        con.execute(
            "INSERT INTO ds_metric_bindings VALUES (?, ?, ?, 'worldbank.wdi', "
            "'worldbank_wdi', ?, ?, '{}', 'transport_ready')",
            [metric, dataset_id, distribution_id, indicator, confidence],
        )
    con.close()
    return catalog, census, substrate


def test_live_target_is_derived_from_backlog_units_and_live_catalog(
    selection_inputs: tuple[Path, Path, Path],
) -> None:
    catalog, census, substrate = selection_inputs

    selection = executor.derive_live_target_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
    )

    assert selection.target_variable == "government.balance"
    assert selection.canonical_unit == "usd"
    assert selection.request_dataset_id == "GC.BAL.CASH.CD"
    assert selection.upstream_metric_id == "gov_balance"
    assert selection.backlog_rank == 2
    assert selection.live_family_denominator == ("worldbank.wdi",)
    assert selection.eligible_target_denominator == ("government.balance",)
    assert selection.catalog_candidate_denominator == 3
    assert selection.eligible_catalog_candidate_count == 2
    assert selection.rejected_candidate_counts["unit_mismatch"] == 1
    assert selection.alignment_score.overall_score > 0.0


def test_live_target_selection_rejects_a_pinned_wrong_carrier(
    selection_inputs: tuple[Path, Path, Path],
) -> None:
    catalog, census, substrate = selection_inputs
    selection = executor.derive_live_target_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
    )

    with pytest.raises(ValueError, match="selection identity must be recomputed"):
        selection.model_copy(
            update={"request_dataset_id": "GC.BAL.CASH.GD.ZS"},
        ).__class__.model_validate(
            selection.model_copy(
                update={"request_dataset_id": "GC.BAL.CASH.GD.ZS"},
            ).model_dump(mode="python")
        )


def test_authority_entry_uses_owner_schema_and_generic_alignment(
    selection_inputs: tuple[Path, Path, Path],
) -> None:
    catalog, census, substrate = selection_inputs
    selection = executor.derive_live_target_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
    )

    entry = executor.build_selected_live_authority_entry(
        selection,
        l5_family_id="macro_state",
        country_codes=("UKR",),
    )

    assert entry.catalog_raw_variable == "GC.BAL.CASH.CD"
    assert entry.raw_field == "value"
    assert entry.raw_unit == entry.canonical_unit == "usd"
    assert entry.alignment_method == "semantic"
    assert entry.alignment_confidence == selection.alignment_score.overall_score
    assert tuple(column.name for column in entry.schema_columns) == (
        "country_code",
        "country_name",
        "decimal",
        "indicator_id",
        "indicator_name",
        "unit",
        "value",
        "year",
    )
    assert entry.schema_contract_ref == "fabric://worldbank.wdi.generic@2.0.0"
