from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from tools.quality.validation import check_layer3_gy_acquisition_executor as checker
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
            connector_params JSON,
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
    con.execute(
        """
        CREATE TABLE ds_schema_profiles (
            distribution_id VARCHAR,
            dataset_id VARCHAR,
            columns_json JSON,
            sample_row_count INTEGER,
            preview_sample_hash VARCHAR,
            inference_mode VARCHAR,
            parser_mode VARCHAR
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
            "'worldbank.wdi', 'worldbank_wdi', 'fixture', ?, ?, TRUE)",
            [distribution_id, dataset_id, json.dumps({"indicator_id": indicator}), quality],
        )
        con.execute(
            "INSERT INTO ds_metric_bindings VALUES (?, ?, ?, 'worldbank.wdi', "
            "'worldbank_wdi', ?, ?, '{}', 'transport_ready')",
            [metric, dataset_id, distribution_id, indicator, confidence],
        )
        con.execute(
            "INSERT INTO ds_schema_profiles VALUES (?, ?, ?, 0, NULL, "
            "'metadata_only', 'api_tabular')",
            [
                distribution_id,
                dataset_id,
                json.dumps(
                    [
                        {"name": indicator, "inference_source": "metadata"},
                        {"name": "SURPLUS", "inference_source": "metadata"},
                    ]
                ),
            ],
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


def test_target_specific_harness_replays_exact_selected_carrier_without_network(
    selection_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    catalog, census, substrate = selection_inputs
    selection = executor.derive_live_target_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
    )

    receipt = executor.derive_target_family_receipt(
        selection,
        catalog_path=catalog,
        fixture_root=tmp_path / "fixtures-that-do-not-exist",
    )

    assert receipt.connector_id == "worldbank.wdi"
    assert receipt.safe_dry_run_passed is True
    assert receipt.simulator_network_calls == 0
    assert receipt.network_escape_attempt_count == 0
    assert receipt.carrier_denominator == 1
    assert len(receipt.dry_run_attempts) == 1
    carrier = receipt.dry_run_attempts[0]
    assert carrier.attempt_id == executor.derive_live_attempt_id(selection)
    assert carrier.request_dataset_id == "GC.BAL.CASH.CD"
    assert carrier.connector_fetch_invoked is True
    assert carrier.transport_intercepted is True


def test_target_authority_owners_are_byte_stable_and_bind_exact_harness(
    selection_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    catalog, census, substrate = selection_inputs
    l5_path = _write_json(
        tmp_path / "measurement_registry.json",
        {
            "coverage_rules": {"macro_state": 0.95, "labor_market": 0.7},
            "trust_tiers": {},
        },
    )
    selection = executor.derive_live_target_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
    )
    receipt = executor.derive_target_family_receipt(
        selection,
        catalog_path=catalog,
        fixture_root=tmp_path / "fixtures-that-do-not-exist",
    )

    first = executor.derive_target_authority_owners(
        selection,
        family_receipt=receipt,
        baseline_path=catalog,
        baseline_owner_ref="repo://fixture/catalog.duckdb",
        l5_path=l5_path,
        l5_owner_ref="repo://fixture/measurement_registry.json",
        receipt_owner_ref="repo://fixture/live-harness.json",
        country_codes=("UKR",),
    )
    second = executor.derive_target_authority_owners(
        selection,
        family_receipt=receipt,
        baseline_path=catalog,
        baseline_owner_ref="repo://fixture/catalog.duckdb",
        l5_path=l5_path,
        l5_owner_ref="repo://fixture/measurement_registry.json",
        receipt_owner_ref="repo://fixture/live-harness.json",
        country_codes=("UKR",),
    )

    assert first.payloads() == second.payloads()
    assert first.entry.l5_family_id == "macro_state"
    assert first.registry.entries == (first.entry,)
    provision = first.provision.live_harness_receipts[0]
    assert provision.entry_id == first.entry.entry_id
    assert provision.attempt_id == executor.derive_live_attempt_id(selection)
    assert provision.receipt_content_sha256 == executor.bytes_sha256(first.family_receipt_bytes)


def test_live_execution_output_fence_requires_a_new_attempt_carrier(
    tmp_path: Path,
) -> None:
    journal = tmp_path / "journal.jsonl"
    cas_root = tmp_path / "cas"
    evidence = tmp_path / "evidence.json"

    checker.require_new_live_execution_outputs(
        journal_path=journal,
        cas_root=cas_root,
        evidence_path=evidence,
        attempt_id="attempt-002",
    )
    journal.write_text(
        json.dumps({"attempt_id": "attempt-001", "event_kind": "request"}) + "\n",
        encoding="utf-8",
    )
    cas_root.mkdir()

    checker.require_new_live_execution_outputs(
        journal_path=journal,
        cas_root=cas_root,
        evidence_path=evidence,
        attempt_id="attempt-002",
    )

    with pytest.raises(RuntimeError, match="live_execution_output_already_exists"):
        checker.require_new_live_execution_outputs(
            journal_path=journal,
            cas_root=cas_root,
            evidence_path=evidence,
            attempt_id="attempt-001",
        )


def test_second_attempt_gets_a_distinct_exact_harness_receipt(
    selection_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    catalog, census, substrate = selection_inputs
    selection = executor.derive_live_target_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
    )

    receipt = executor.derive_target_family_receipt(
        selection,
        catalog_path=catalog,
        fixture_root=tmp_path / "fixtures-that-do-not-exist",
        attempt_ordinal=2,
    )

    carrier = receipt.dry_run_attempts[0]
    assert carrier.attempt_id == executor.derive_live_attempt_id(
        selection,
        attempt_ordinal=2,
    )
    assert carrier.request_dataset_id == selection.request_dataset_id
    assert receipt.safe_dry_run_passed is True

    first_receipt = executor.derive_target_family_receipt(
        selection,
        catalog_path=catalog,
        fixture_root=tmp_path / "fixtures-that-do-not-exist",
    )
    l5_path = _write_json(
        tmp_path / "measurement_registry.json",
        {"coverage_rules": {"macro_state": 0.95}, "trust_tiers": {}},
    )
    owners = executor.derive_target_authority_owners(
        selection,
        family_receipt=first_receipt,
        additional_family_receipts=((2, receipt),),
        baseline_path=catalog,
        baseline_owner_ref="repo://fixture/catalog.duckdb",
        l5_path=l5_path,
        l5_owner_ref="repo://fixture/measurement_registry.json",
        receipt_owner_ref="repo://fixture/live-harness.json",
        country_codes=("UKR",),
    )

    assert len(owners.provision.live_harness_receipts) == 2
    assert owners.provision.live_harness_receipts[1].attempt_id.endswith("-002")
    assert executor.target_harness_receipt_path(2) in owners.payloads()
