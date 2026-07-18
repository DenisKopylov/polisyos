from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import duckdb
import pytest

from tools.quality.validation import check_layer3_gy_acquisition_executor as checker
from tools.quality.validation import layer3_gy_acquisition_executor as executor

_EMPTY_WDI_PAGE = (
    b'[{"page":0,"pages":0,"per_page":0,"total":0,"sourceid":null,"lastupdated":null},null]'
)


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
            execution_tier VARCHAR,
            themes JSON
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
            "'CC-BY-4.0', FALSE, 'transport_ready', ?)",
            [
                dataset_id,
                title,
                description,
                json.dumps(["World Development Indicators"]),
            ],
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


def test_paid_worldbank_data_body_is_classified_without_inference() -> None:
    empty = executor.classify_worldbank_data_response(_EMPTY_WDI_PAGE)
    retired = executor.classify_worldbank_data_response(
        b'[{"message":[{"id":"175","key":"Invalid indicator","value":"retired"}]}]'
    )
    unknown = executor.classify_worldbank_data_response(b'{"total":0}')

    assert empty.disposition == "no_data_for_scope"
    assert empty.row_count == 0
    assert retired.disposition == "carrier_retired_or_invalid"
    assert unknown.disposition == "response_shape_unclassified"


def test_indicator_metadata_classification_binds_identity_and_declared_coverage() -> None:
    current = executor.classify_worldbank_indicator_metadata(
        b'[{"page":1,"pages":1,"per_page":"1","total":1},'
        b'[{"id":"GC.BAL.CASH.CD","name":"Cash balance",'
        b'"source":{"id":"2","value":"World Development Indicators"},'
        b'"sourceNote":"Owner note","unit":"current US$"}]]',
        indicator_id="GC.BAL.CASH.CD",
    )
    retired = executor.classify_worldbank_indicator_metadata(
        b'[{"page":0,"pages":0,"per_page":0,"total":0},null]',
        indicator_id="GC.BAL.CASH.CD",
    )

    assert current.disposition == "carrier_current"
    assert current.indicator_id == "GC.BAL.CASH.CD"
    assert current.source_id == "2"
    assert current.declared_coverage == "not_declared_by_indicator_metadata_endpoint"
    assert retired.disposition == "carrier_retired_or_invalid"


def test_metadata_e7_receipt_intercepts_exact_carrier_without_network(tmp_path: Path) -> None:
    receipt = executor.derive_worldbank_metadata_harness_receipt(
        attempt_id="gy-n13b-worldbank-wdi-government-balance-usd-metadata-001",
        indicator_id="GC.BAL.CASH.CD",
        profile_id="worldbank_wdi",
        fixture_root=tmp_path / "missing-replay-fixtures",
    )

    assert receipt.call_class == "indicator_metadata"
    assert receipt.request_variable == "GC.BAL.CASH.CD"
    assert receipt.simulator_call_count == 1
    assert receipt.transport_intercepted is True
    assert receipt.network_escape_attempt_count == 0
    assert receipt.actual_network_call_count == 0
    assert receipt.safe_dry_run_passed is True


def test_r1_forensic_receipt_reopens_paid_journal_and_cas() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    receipt = executor.derive_r1_forensic_receipt(
        journal_path=(
            repo_root / "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
        ),
        cas_root=repo_root / "architecture/policy_design_case/layer3_gy_acquisition_cas",
        request_dataset_id="GC.BAL.CASH.CD",
    )

    assert receipt.classification.disposition == "no_data_for_scope"
    assert receipt.classification.byte_count == 85
    assert receipt.decisive_attempt_id.endswith("-001")
    assert len(receipt.attempts) == 2
    assert receipt.attempts[0].max_elapsed_seconds == pytest.approx(6.945391583998571)
    assert receipt.attempts[1].max_elapsed_seconds == pytest.approx(15.766325374999724)
    assert receipt.cas_blob_sha256 == receipt.classification.body_sha256
    assert receipt.journal_prefix_byte_length > 0


def test_metadata_probe_owner_derives_timeout_from_paid_latency(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[3]
    r1 = executor.derive_r1_forensic_receipt(
        journal_path=(
            repo_root / "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
        ),
        cas_root=repo_root / "architecture/policy_design_case/layer3_gy_acquisition_cas",
        request_dataset_id="GC.BAL.CASH.CD",
    )

    baseline_path = tmp_path / "catalog.duckdb"
    baseline_path.write_bytes(b"immutable-catalog-fixture")
    owner = executor.derive_metadata_probe_owner(
        r1_receipt=r1,
        baseline_path=baseline_path,
        fixture_root=tmp_path / "missing-replay-fixtures",
    )

    assert owner.request["call_class"] == "indicator_metadata"
    assert owner.request["request_variables"] == ["GC.BAL.CASH.CD"]
    assert owner.authorization.budget.call_budget == 1
    assert owner.authorization.budget.variable_budget == 1
    assert owner.authorization.budget.timeout_cap_seconds == 14.0
    assert owner.authorization.timeout_derivation["paid_success_elapsed_seconds"] == pytest.approx(
        6.945391583998571
    )
    with pytest.raises(ValueError, match="metadata probe owner identity must be recomputed"):
        executor.MetadataProbeOwner.model_validate(
            {
                **owner.model_dump(mode="python"),
                "owner_sha256": "sha256:" + "0" * 64,
            }
        )


def test_metadata_one_shot_journals_raw_before_classification_and_updates_d3(
    selection_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.fabric.connectors.sources.http_base import _raw_http_response_observer
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

    catalog, _census, _substrate = selection_inputs
    repo_root = Path(__file__).resolve().parents[3]
    source_journal = (
        repo_root / "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
    )
    source_cas = repo_root / "architecture/policy_design_case/layer3_gy_acquisition_cas"
    journal = tmp_path / "journal.jsonl"
    cas_root = tmp_path / "cas"
    shutil.copy2(source_journal, journal)
    shutil.copytree(source_cas, cas_root)
    r1 = executor.derive_r1_forensic_receipt(
        journal_path=journal,
        cas_root=cas_root,
        request_dataset_id="GC.BAL.CASH.CD",
    )
    journal.write_bytes(journal.read_bytes()[: r1.journal_prefix_byte_length])
    owner = executor.derive_metadata_probe_owner(
        r1_receipt=r1,
        baseline_path=catalog,
        fixture_root=tmp_path / "missing-replay-fixtures",
    )
    body = (
        b'[{"page":1,"pages":1,"per_page":"1","total":1},'
        b'[{"id":"GC.BAL.CASH.CD","name":"Cash balance",'
        b'"source":{"id":"2","value":"World Development Indicators"},'
        b'"unit":"current US$"}]]'
    )

    async def fake_metadata(
        _self: WorldBankConnector,
        handle: Any,
        _indicator_id: str,
    ) -> tuple[Any, dict[str, str], bytes]:
        observer = _raw_http_response_observer(handle)
        assert observer is not None
        params = {"format": "json", "page": "1", "per_page": "1"}
        observer.before_request("worldbank.wdi", owner.request["endpoint_url"], params)
        observer.on_response_headers(
            "worldbank.wdi",
            owner.request["endpoint_url"],
            params,
            200,
            {"Content-Type": "application/json"},
        )
        observer.on_body_progress(
            "worldbank.wdi",
            owner.request["endpoint_url"],
            params,
            len(body),
        )
        observer.on_raw_response(
            "worldbank.wdi",
            owner.request["endpoint_url"],
            params,
            200,
            {"Content-Type": "application/json"},
            body,
        )
        return json.loads(body), {"Content-Type": "application/json"}, body

    monkeypatch.setattr(WorldBankConnector, "fetch_indicator_metadata_raw", fake_metadata)
    checker._execute_metadata_probe(owner=owner, journal_path=journal, cas_root=cas_root)

    evidence, update = executor.derive_metadata_probe_execution_evidence(
        owner=owner,
        r1_receipt=r1,
        journal_path=journal,
        cas_root=cas_root,
        baseline_path=catalog,
    )

    assert evidence.call_count == 1
    assert evidence.classification is not None
    assert evidence.classification.disposition == "carrier_current"
    attempt_kinds = [
        event["event_kind"]
        for event in (json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines())
        if event.get("attempt_id") == owner.authorization.attempt_id
    ]
    assert attempt_kinds.index("raw_response") < attempt_kinds.index("classification")
    assert attempt_kinds[-1] == "live_attempt_terminal"
    assert update.carrier_disposition == "carrier_current_no_data_for_scope"
    assert update.metadata_attempt.raw_evidence_event_sha256 == (
        evidence.raw_evidence_ref.event_sha256
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


def test_d6_route_selector_derives_ratio_times_scale_from_owner_denominators(
    selection_inputs: tuple[Path, Path, Path],
) -> None:
    catalog, census, substrate = selection_inputs
    con = duckdb.connect(str(catalog))
    try:
        con.execute(
            "UPDATE ds_datasets SET themes = ? WHERE id = 'percent-dataset'",
            [json.dumps(["WDI Database Archives"])],
        )
        con.execute(
            "INSERT INTO ds_datasets VALUES "
            "('gdp-dataset', 'worldbank', 'World Bank', 'GDP (current US$)', "
            "'Gross domestic product in current United States dollars.', NULL, NULL, "
            "'CC-BY-4.0', FALSE, 'transport_ready', ?)",
            [json.dumps(["World Development Indicators"])],
        )
        con.execute(
            "INSERT INTO ds_distributions VALUES "
            "('gdp-dist', 'gdp-dataset', 'https://api.worldbank.org/v2', "
            "'worldbank.wdi', 'worldbank_wdi', 'fixture', ?, 1.0, TRUE)",
            [json.dumps({"indicator_id": "NY.GDP.MKTP.CD"})],
        )
        con.execute(
            "INSERT INTO ds_metric_bindings VALUES "
            "('gdp', 'gdp-dataset', 'gdp-dist', 'worldbank.wdi', "
            "'worldbank_wdi', 'NY.GDP.MKTP.CD', 0.87, '{}', 'transport_ready')"
        )
    finally:
        con.close()
    repo_root = Path(__file__).resolve().parents[3]
    r1 = executor.derive_r1_forensic_receipt(
        journal_path=(
            repo_root / "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
        ),
        cas_root=repo_root / "architecture/policy_design_case/layer3_gy_acquisition_cas",
        request_dataset_id="GC.BAL.CASH.CD",
    )

    selection = executor.derive_d6_route_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
        r1_receipt=r1,
        carrier_liveness_path=(
            repo_root / "architecture/policy_design_case/"
            "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
        ),
    )

    assert selection.target_variable == "government.balance"
    assert selection.required_output_unit == "usd"
    assert selection.route_disposition == "derivation_requirement"
    assert selection.transform_method_id == "percent_of_gdp_times_current_usd_exact_year"
    assert selection.primary.request_dataset_id == "GC.BAL.CASH.GD.ZS"
    assert selection.primary.unit == "percent_gdp"
    assert selection.primary_candidate_denominator == 1
    assert selection.auxiliary.request_dataset_id == "NY.GDP.MKTP.CD"
    assert selection.auxiliary.unit == "usd"
    assert selection.auxiliary_candidate_denominator == 1
    assert selection.primary_requires_source_characterization is True
    assert selection.selection_sha256 == executor.content_sha256(selection.identity_payload())


def test_d6_metadata_owner_binds_route_and_paid_latency(
    selection_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    catalog, census, substrate = selection_inputs
    con = duckdb.connect(str(catalog))
    try:
        con.execute(
            "UPDATE ds_datasets SET themes = ? WHERE id = 'percent-dataset'",
            [json.dumps(["WDI Database Archives"])],
        )
        con.execute(
            "INSERT INTO ds_datasets VALUES "
            "('gdp-dataset', 'worldbank', 'World Bank', 'GDP (current US$)', "
            "'Gross domestic product in current United States dollars.', NULL, NULL, "
            "'CC-BY-4.0', FALSE, 'transport_ready', ?)",
            [json.dumps(["World Development Indicators"])],
        )
        con.execute(
            "INSERT INTO ds_distributions VALUES "
            "('gdp-dist', 'gdp-dataset', 'https://api.worldbank.org/v2', "
            "'worldbank.wdi', 'worldbank_wdi', 'fixture', ?, 1.0, TRUE)",
            [json.dumps({"indicator_id": "NY.GDP.MKTP.CD"})],
        )
        con.execute(
            "INSERT INTO ds_metric_bindings VALUES "
            "('gdp', 'gdp-dataset', 'gdp-dist', 'worldbank.wdi', "
            "'worldbank_wdi', 'NY.GDP.MKTP.CD', 0.87, '{}', 'transport_ready')"
        )
    finally:
        con.close()
    repo_root = Path(__file__).resolve().parents[3]
    r1 = executor.derive_r1_forensic_receipt(
        journal_path=(
            repo_root / "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
        ),
        cas_root=repo_root / "architecture/policy_design_case/layer3_gy_acquisition_cas",
        request_dataset_id="GC.BAL.CASH.CD",
    )
    selection = executor.derive_d6_route_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
        r1_receipt=r1,
        carrier_liveness_path=(
            repo_root / "architecture/policy_design_case/"
            "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
        ),
    )

    owner = executor.derive_d6_metadata_probe_owner(
        selection=selection,
        r1_receipt=r1,
        baseline_path=catalog,
        fixture_root=tmp_path / "missing-replay-fixtures",
    )

    assert owner.route_selection_sha256 == selection.selection_sha256
    assert owner.request["request_variables"] == ["GC.BAL.CASH.GD.ZS"]
    assert owner.authorization.budget.timeout_cap_seconds == 14.0
    assert owner.authorization.call_class == "indicator_metadata"
    assert owner.harness.actual_network_call_count == 0
    assert owner.harness.safe_dry_run_passed is True
