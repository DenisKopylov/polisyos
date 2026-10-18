from __future__ import annotations

import importlib.util
import json
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _seed_synthetic_r1(
    *,
    journal_path: Path,
    cas_root: Path,
    request_dataset_id: str = "GC.BAL.CASH.CD",
) -> Any:
    """Create a complete, temp-owned prior data attempt and reopen its R1 receipt."""

    from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.data_plane import (
        AppendOnlyEvidenceJournal,
        derive_live_http_budget,
    )

    attempt_id = "fixture-r1-government-balance-001"
    journal = AppendOnlyEvidenceJournal(journal_path)
    request_ref = journal.append_request(
        attempt_id=attempt_id,
        request={
            "call_class": "data_fetch",
            "connector_id": "worldbank.wdi",
            "profile_id": "worldbank_wdi",
            "request_dataset_id": request_dataset_id,
            "variable_id": request_dataset_id,
            "schema_contract": {"columns": ["country_code", "year", "value"]},
        },
    )
    params = {"format": "json", "page": "1", "per_page": "1"}
    transport_ref = journal.append_transport_attempt(
        attempt_id=attempt_id,
        request_ref=request_ref,
        connector_id="worldbank.wdi",
        url=f"https://api.worldbank.org/v2/indicator/{request_dataset_id}",
        params=params,
    )
    journal.append_heartbeat(
        attempt_id=attempt_id,
        phase="attempt_started",
        progress_bytes=0,
        elapsed_seconds=6.945391583998571,
    )
    profile = SourceProfile(
        profile_id="worldbank_wdi",
        display_name="World Bank WDI fixture",
        connector_family="worldbank",
        base_url="https://api.worldbank.org/v2",
        timeout_seconds=15,
    )
    body = _EMPTY_WDI_PAGE
    raw_ref = journal.append_raw_evidence(
        attempt_id=attempt_id,
        request_ref=request_ref,
        transport_ref=transport_ref,
        payload=body,
        status_code=200,
        response_headers={"content-type": "application/json"},
        budget=derive_live_http_budget(
            profile,
            max_response_bytes=16_384,
            max_decompressed_bytes=16_384,
        ),
    )
    FileSystemCAS(cas_root, ownership_enforced=False).put_bytes(
        body,
        ArtifactWriteOptions(
            kind="fabric.acquisition.raw_evidence",
            media_type="application/json",
        ),
    )
    journal.append_failure_terminal(
        attempt_id=attempt_id,
        request_ref=request_ref,
        failure_code="r1_fixture_response",
        raw_evidence_ref=raw_ref,
    )
    return executor.derive_r1_forensic_receipt(
        journal_path=journal_path,
        cas_root=cas_root,
        request_dataset_id=request_dataset_id,
    )


def _synthetic_acceptance_case(tmp_path: Path) -> Any:
    fixture_path = Path(__file__).with_name("_layer3_gy_n13b_acceptance_fixtures.py")
    spec = importlib.util.spec_from_file_location(
        "_layer3_gy_n13b_acceptance_fixtures_for_reentry",
        fixture_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("layer3_gy_n13b_acceptance_fixture_module_unresolved")
    fixture_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture_module)
    return fixture_module.build_synthetic_acceptance_case(tmp_path)


def _fake_metadata_response(owner: Any, body: bytes) -> Any:
    from polisyos.fabric.connectors.sources.http_base import _raw_http_response_observer
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

    async def fake_metadata(
        _self: WorldBankConnector,
        handle: Any,
        _indicator_id: str,
    ) -> tuple[Any, dict[str, str], bytes]:
        observer = _raw_http_response_observer(handle)
        assert observer is not None
        params = {str(key): str(value) for key, value in owner.request["params"].items()}
        endpoint = str(owner.request["endpoint_url"])
        observer.before_request("worldbank.wdi", endpoint, params)
        observer.on_response_headers(
            "worldbank.wdi",
            endpoint,
            params,
            200,
            {"Content-Type": "application/json"},
        )
        observer.on_body_progress("worldbank.wdi", endpoint, params, len(body))
        observer.on_raw_response(
            "worldbank.wdi",
            endpoint,
            params,
            200,
            {"Content-Type": "application/json"},
            body,
        )
        return json.loads(body), {"Content-Type": "application/json"}, body

    return fake_metadata


def _write_model(root: Path, relative: Path, value: Any) -> Path:
    from polisyos.fabric.data_plane import canonical_json_bytes

    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value.model_dump(mode="json")))
    return path


def _cas_blob_path(cas_root: Path, artifact_id: str) -> Path:
    artifact_hex = artifact_id.removeprefix("sha256:")
    return (
        cas_root
        / "artifacts/sha256"
        / artifact_hex[:2]
        / artifact_hex[2:4]
        / f"{artifact_hex}.blob"
    )


def _mutate_raw_journal_bytes(journal_bytes: bytes, evidence: Any) -> bytes:
    ref = evidence.raw_evidence_ref
    assert ref is not None
    raw_line = journal_bytes[ref.byte_offset : ref.byte_offset + ref.byte_length]
    marker = b'"bounded_body_base64":"'
    mutation_offset = ref.byte_offset + raw_line.index(marker) + len(marker)
    changed = bytearray(journal_bytes)
    changed[mutation_offset] = ord("A") if changed[mutation_offset] != ord("A") else ord("B")
    return bytes(changed)


def _synthetic_d6_transform_sources() -> tuple[dict[str, object], dict[str, object]]:
    registry: dict[str, object] = {
        "families": [
            {
                "family_id": "synthetic_share_times_scale",
                "method_id": "arithmetic.synthetic.share_times_scale",
                "method_version": "7.3.1",
                "year_domain_role": "share",
                "input_specs": [
                    {
                        "role": "scale",
                        "basis": {
                            "quantity_kind": "monetary_scale",
                            "unit": "usd",
                            "attributes": [{"name": "currency", "value": "USD"}],
                        },
                        "value_constraints": [],
                    },
                    {
                        "role": "share",
                        "basis": {
                            "quantity_kind": "relative_share",
                            "unit": "percent",
                            "attributes": [{"name": "denominator", "value": "output_scale"}],
                        },
                        "value_constraints": [],
                    },
                ],
                "output_basis": {
                    "quantity_kind": "monetary_flow",
                    "unit": "usd",
                    "attributes": [{"name": "currency", "value": "USD"}],
                },
                "parameter_rules": [],
                "output_parameter_bindings": [],
                "expression": {
                    "operator": "multiply",
                    "operands": [
                        {
                            "operator": "divide",
                            "operands": [
                                {"operator": "current_value", "role": "share"},
                                {"operator": "constant", "constant_value": "100"},
                            ],
                        },
                        {"operator": "current_value", "role": "scale"},
                    ],
                },
                "assumption_rules": [
                    {
                        "name": "arithmetic_contract",
                        "literal_value": "share divided by 100, multiplied by scale",
                    }
                ],
            }
        ]
    }
    policy: dict[str, object] = {
        "policy_id": "synthetic_share_times_scale.d6",
        "family_id": "synthetic_share_times_scale",
        "method_version": "7.3.1",
        "purposes": ["d6_route"],
        "country_code": "UA",
        "output_variable_id_template": "{share_canonical_variable}_amount",
        "roles": [
            {
                "role": "scale",
                "catalog_unit": "usd",
                "semantic_anchor": "gross domestic product current us dollars",
                "owner_metric_id": "synthetic_scale_metric",
                "owner_canonical_variable": "synthetic_scale_metric",
                "minimum_alignment_confidence": 0.0,
                "allow_proxy": False,
                "require_executable_binding": True,
                "executable_connectors": [],
                "required_themes": [],
                "forbidden_theme_fragments": [],
                "required_text_fragments": [],
                "forbidden_text_fragments": [],
            },
            {
                "role": "share",
                "catalog_unit": "percent_gdp",
                "semantic_anchor": "fiscal balance percent of output",
                "owner_metric_id": "gov_balance",
                "owner_canonical_variable": "gov_balance",
                "minimum_alignment_confidence": 0.0,
                "allow_proxy": False,
                "require_executable_binding": True,
                "executable_connectors": [],
                "required_themes": [],
                "forbidden_theme_fragments": ["archive"],
                "required_text_fragments": [],
                "forbidden_text_fragments": [],
            },
        ],
    }
    return registry, policy


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
    journal = tmp_path / "journal.jsonl"
    cas_root = tmp_path / "cas"
    r1 = _seed_synthetic_r1(journal_path=journal, cas_root=cas_root)
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

    from polisyos.core.artifacts import ArtifactIntegrityError
    from polisyos.fabric.data_plane import EvidenceJournalError, canonical_json_bytes
    from tools.quality.validation.acquisition_admission_contract import (
        _require_exact_artifact_payload,
    )

    evidence_path = tmp_path / "r2-evidence.json"
    carrier_path = tmp_path / "carrier-update.json"
    evidence_payload = canonical_json_bytes(evidence.model_dump(mode="json"))
    evidence_path.write_bytes(evidence_payload)
    carrier_path.write_bytes(canonical_json_bytes(update.model_dump(mode="json")))
    _require_exact_artifact_payload(evidence_path, evidence, label="metadata_evidence")
    _require_exact_artifact_payload(carrier_path, update, label="metadata_evidence")

    declared_journal = journal.read_bytes()
    assert evidence.raw_evidence_ref is not None
    raw_start = evidence.raw_evidence_ref.byte_offset
    raw_line = declared_journal[raw_start : raw_start + evidence.raw_evidence_ref.byte_length]
    marker = b'"bounded_body_base64":"'
    marker_offset = raw_line.index(marker) + len(marker)
    mutation_offset = raw_start + marker_offset
    changed = bytearray(declared_journal)
    changed[mutation_offset] = ord("A") if changed[mutation_offset] != ord("A") else ord("B")
    journal.write_bytes(changed)
    with pytest.raises(EvidenceJournalError) as journal_error:
        executor.derive_metadata_probe_execution_evidence(
            owner=owner,
            r1_receipt=r1,
            journal_path=journal,
            cas_root=cas_root,
            baseline_path=catalog,
        )
    assert journal_error.value.code == "live_terminal_raw_link_invalid"
    assert evidence_path.read_bytes() == evidence_payload

    journal.write_bytes(declared_journal)
    assert evidence.raw_artifact_id is not None
    artifact_hex = evidence.raw_artifact_id.removeprefix("sha256:")
    blob_path = (
        cas_root
        / "artifacts/sha256"
        / artifact_hex[:2]
        / artifact_hex[2:4]
        / f"{artifact_hex}.blob"
    )
    declared_blob = blob_path.read_bytes()
    changed_blob = bytearray(declared_blob)
    changed_blob[0] ^= 1
    blob_path.write_bytes(changed_blob)
    with pytest.raises(ArtifactIntegrityError):
        executor.derive_metadata_probe_execution_evidence(
            owner=owner,
            r1_receipt=r1,
            journal_path=journal,
            cas_root=cas_root,
            baseline_path=catalog,
        )
    assert evidence_path.read_bytes() == evidence_payload


def test_rawless_terminal_refuses_stale_classification(
    selection_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
) -> None:
    from polisyos.fabric.data_plane import AppendOnlyEvidenceJournal, canonical_json_bytes

    catalog, _census, _substrate = selection_inputs
    journal = tmp_path / "rawless-journal.jsonl"
    cas_root = tmp_path / "rawless-cas"
    r1 = _seed_synthetic_r1(journal_path=journal, cas_root=cas_root)
    owner = executor.derive_metadata_probe_owner(
        r1_receipt=r1,
        baseline_path=catalog,
        fixture_root=tmp_path / "rawless-replay-fixtures",
    )
    attempt_id = owner.authorization.attempt_id
    journal_owner = AppendOnlyEvidenceJournal(journal)
    request_ref = journal_owner.append_request(attempt_id=attempt_id, request=owner.request)
    journal_owner.append_failure_terminal(
        attempt_id=attempt_id,
        request_ref=request_ref,
        failure_code="metadata_raw_response_missing",
    )

    events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    terminal_index = next(
        index
        for index, event in enumerate(events)
        if event.get("event_kind") == "live_attempt_terminal"
        and event.get("attempt_id") == attempt_id
    )
    terminal_event = events[terminal_index]
    stale_classification = {
        "sequence": terminal_event["sequence"],
        "event_kind": "classification",
        "attempt_id": attempt_id,
        "evidence_event_sha256": "sha256:" + "0" * 64,
        "classification": {"disposition": "carrier_current"},
    }
    events.insert(terminal_index, stale_classification)
    for sequence, event in enumerate(events, start=1):
        event["sequence"] = sequence
    journal.write_bytes(b"\n".join(canonical_json_bytes(event) for event in events) + b"\n")

    with pytest.raises(executor.AcquisitionSelectionError) as raised:
        executor.derive_metadata_probe_execution_evidence(
            owner=owner,
            r1_receipt=r1,
            journal_path=journal,
            cas_root=cas_root,
            baseline_path=catalog,
        )
    assert raised.value.code == "metadata_classification_without_raw"


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
            "('synthetic_scale_metric', 'gdp-dataset', 'gdp-dist', 'worldbank.wdi', "
            "'worldbank_wdi', 'NY.GDP.MKTP.CD', 0.87, '{}', 'transport_ready')"
        )
        con.execute(
            "INSERT INTO ds_datasets VALUES "
            "('bad-gdp-dataset', 'worldbank', 'World Bank', 'GDP (% of GDP)', "
            "'Gross domestic product as percent of GDP.', NULL, NULL, "
            "'', FALSE, 'transport_ready', ?)",
            [json.dumps(["WDI Database Archives"])],
        )
        con.execute(
            "INSERT INTO ds_distributions VALUES "
            "('bad-gdp-dist', 'bad-gdp-dataset', 'https://api.worldbank.org/v2', "
            "'worldbank.wdi', 'worldbank_wdi', 'fixture', ?, 1.0, TRUE)",
            [json.dumps({"indicator_id": "BAD.GDP.PERCENT"})],
        )
        con.execute(
            "INSERT INTO ds_metric_bindings VALUES "
            "('synthetic_scale_metric', 'bad-gdp-dataset', 'bad-gdp-dist', "
            "'worldbank.wdi', 'worldbank_wdi', 'BAD.GDP.PERCENT', 0.87, '{}', "
            "'transport_ready')"
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

    transform_registry, selection_policy = _synthetic_d6_transform_sources()
    selection = executor.derive_d6_route_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
        r1_receipt=r1,
        carrier_liveness_path=(
            repo_root / "architecture/policy_design_case/"
            "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
        ),
        transform_registry_source=transform_registry,
        selection_policy_source=selection_policy,
    )

    assert selection.target_variable == "government.balance"
    assert selection.required_output_unit == "usd"
    assert selection.route_disposition == "derivation_requirement"
    assert selection.transform_method_id == "arithmetic.synthetic.share_times_scale"
    assert selection.transform_method_version == "7.3.1"
    assert selection.primary.role == "share"
    assert selection.primary.request_dataset_id == "GC.BAL.CASH.GD.ZS"
    assert selection.primary.unit == "percent_gdp"
    assert selection.primary_candidate_denominator == 1
    assert selection.auxiliary.request_dataset_id == "NY.GDP.MKTP.CD"
    assert selection.auxiliary.metric_id == "synthetic_scale_metric"
    assert selection.auxiliary.role == "scale"
    assert selection.auxiliary.unit == "usd"
    assert selection.auxiliary_catalog_denominator == 2
    assert selection.auxiliary_candidate_denominator == 1
    assert sum(selection.auxiliary_rejected_counts.values()) == 1
    assert selection.primary_requires_source_characterization is True
    assert selection.selection_sha256 == executor.content_sha256(selection.identity_payload())

    forged_model = selection.model_copy(update={"transform_method_id": "arithmetic.forged"})
    forged = forged_model.model_dump(mode="python")
    forged["selection_sha256"] = executor.content_sha256(forged_model.identity_payload())
    with pytest.raises(ValueError, match="transform edge must recompute"):
        executor.D6RouteSelection.model_validate(forged)


def test_d6_route_selector_refuses_unregistered_basis_pair_with_typed_reason(
    selection_inputs: tuple[Path, Path, Path],
) -> None:
    catalog, census, substrate = selection_inputs
    repo_root = Path(__file__).resolve().parents[3]
    r1 = executor.derive_r1_forensic_receipt(
        journal_path=(
            repo_root / "architecture/policy_design_case/layer3_gy_acquisition_raw_journal.jsonl"
        ),
        cas_root=repo_root / "architecture/policy_design_case/layer3_gy_acquisition_cas",
        request_dataset_id="GC.BAL.CASH.CD",
    )
    transform_registry, selection_policy = _synthetic_d6_transform_sources()
    selection_policy["family_id"] = "unregistered_basis_family"

    with pytest.raises(executor.AcquisitionSelectionError) as raised:
        executor.derive_d6_route_selection(
            catalog_path=catalog,
            census_path=census,
            substrate_path=substrate,
            r1_receipt=r1,
            carrier_liveness_path=(
                repo_root / "architecture/policy_design_case/"
                "layer3_gy_n13a_worldbank_government_balance_carrier_liveness.json"
            ),
            transform_registry_source=transform_registry,
            selection_policy_source=selection_policy,
        )

    assert raised.value.code == "basis_mismatch"
    assert raised.value.reason == "no_certified_transform"


def test_d6_canonical_writer_wires_one_registry_owner_to_both_protocols(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    selection = object()
    metadata_owner = object()
    captured: dict[str, object] = {}

    def fake_selection(**kwargs: object) -> object:
        captured.update(kwargs)
        return selection

    def fake_metadata_owner(**kwargs: object) -> object:
        assert kwargs["selection"] is selection
        return metadata_owner

    monkeypatch.setattr(checker, "derive_d6_route_selection", fake_selection)
    monkeypatch.setattr(checker, "derive_d6_metadata_probe_owner", fake_metadata_owner)

    actual = checker._recompute_d6_route_owners(
        catalog_path=tmp_path / "catalog.duckdb",
        census_path=tmp_path / "census.json",
        substrate_path=tmp_path / "substrate.json",
        r1=object(),
    )

    expected_owner = checker.POLICY_ENGINE_ROOT / checker.DEFAULT_DERIVATION_FAMILY_REGISTRY
    assert actual == (selection, metadata_owner)
    assert captured["transform_registry_source"] == expected_owner
    assert captured["selection_policy_source"] == expected_owner


def test_d6_route_selection_keeps_frozen_v1_receipt_parseable() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    route = executor.D6RouteSelection.model_validate_json(
        (
            repo_root / "architecture/policy_design_case/layer3_gy_n13b_d6_route_selection.json"
        ).read_bytes()
    )

    assert route.schema_version == "policyos.layer3.gy.n13b.d6_route_selection.v1"
    assert route.transform_family is None
    assert route.selection_policy is None


def test_current_metadata_receipts_reopen_through_contract_and_reentry(
    selection_inputs: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.artifacts import ArtifactIntegrityError
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector
    from polisyos.fabric.data_plane import EvidenceJournalError
    from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
    from tools.quality.validation import (
        acquisition_admission_contract as admission,
    )
    from tools.quality.validation import (
        layer3_gy_n13b_acquisition_contract as contract_facade,
    )
    from tools.quality.validation.acquisition_contract_support import (
        DEFAULT_CARRIER_LIVENESS,
        DEFAULT_D6_ROUTE,
        DEFAULT_N13B_CAS,
        DEFAULT_N13B_JOURNAL,
        DEFAULT_R2_METADATA_EVIDENCE,
        DEFAULT_R3_METADATA_EVIDENCE,
        AdmissionDependencies,
    )
    from tools.quality.validation.layer3_gy_n13b_acceptance import DEFAULT_ACCEPTANCE_CASE
    from tools.quality.validation.layer3_gy_n13b_reentry import N7CatalogResolutionProjection

    catalog, census, substrate = selection_inputs
    connection = duckdb.connect(str(catalog))
    try:
        connection.execute(
            "UPDATE ds_datasets SET themes = ? WHERE id = 'percent-dataset'",
            [json.dumps(["WDI Database Archives"])],
        )
        connection.execute(
            "INSERT INTO ds_datasets VALUES "
            "('gdp-dataset', 'worldbank', 'World Bank', 'GDP (current US$)', "
            "'Gross domestic product in current United States dollars.', NULL, NULL, "
            "'CC-BY-4.0', FALSE, 'transport_ready', ?)",
            [json.dumps(["World Development Indicators"])],
        )
        connection.execute(
            "INSERT INTO ds_distributions VALUES "
            "('gdp-dist', 'gdp-dataset', 'https://api.worldbank.org/v2', "
            "'worldbank.wdi', 'worldbank_wdi', 'fixture', ?, 1.0, TRUE)",
            [json.dumps({"indicator_id": "NY.GDP.MKTP.CD"})],
        )
        connection.execute(
            "INSERT INTO ds_metric_bindings VALUES "
            "('synthetic_scale_metric', 'gdp-dataset', 'gdp-dist', 'worldbank.wdi', "
            "'worldbank_wdi', 'NY.GDP.MKTP.CD', 0.87, '{}', 'transport_ready')"
        )
    finally:
        connection.close()

    current_root = tmp_path / "current-consumer-root"
    journal = current_root / DEFAULT_N13B_JOURNAL
    cas_root = current_root / DEFAULT_N13B_CAS
    r1 = _seed_synthetic_r1(journal_path=journal, cas_root=cas_root)
    r2_owner = executor.derive_metadata_probe_owner(
        r1_receipt=r1,
        baseline_path=catalog,
        fixture_root=tmp_path / "r2-replay-fixtures",
    )
    r2_body = (
        b'[{"page":1,"pages":1,"per_page":"1","total":1},'
        b'[{"id":"GC.BAL.CASH.CD","name":"Cash balance",'
        b'"source":{"id":"2","value":"World Development Indicators"},'
        b'"unit":"current US$"}]]'
    )
    monkeypatch.setattr(
        WorldBankConnector,
        "fetch_indicator_metadata_raw",
        _fake_metadata_response(r2_owner, r2_body),
    )
    checker._execute_metadata_probe(owner=r2_owner, journal_path=journal, cas_root=cas_root)
    r2_evidence, carrier_update = executor.derive_metadata_probe_execution_evidence(
        owner=r2_owner,
        r1_receipt=r1,
        journal_path=journal,
        cas_root=cas_root,
        baseline_path=catalog,
    )
    carrier_path = _write_model(current_root, DEFAULT_CARRIER_LIVENESS, carrier_update)

    transform_registry, selection_policy = _synthetic_d6_transform_sources()
    route = executor.derive_d6_route_selection(
        catalog_path=catalog,
        census_path=census,
        substrate_path=substrate,
        r1_receipt=r1,
        carrier_liveness_path=carrier_path,
        transform_registry_source=transform_registry,
        selection_policy_source=selection_policy,
    )
    r3_owner = executor.derive_d6_metadata_probe_owner(
        selection=route,
        r1_receipt=r1,
        baseline_path=catalog,
        fixture_root=tmp_path / "r3-replay-fixtures",
    )
    r3_body = (
        b'[{"page":1,"pages":1,"per_page":"1","total":1},'
        b'[{"id":"GC.BAL.CASH.GD.ZS","name":"Fiscal balance",'
        b'"source":{"id":"2","value":"World Development Indicators"},'
        b'"unit":"% of GDP"}]]'
    )
    monkeypatch.setattr(
        WorldBankConnector,
        "fetch_indicator_metadata_raw",
        _fake_metadata_response(r3_owner, r3_body),
    )
    checker._execute_metadata_probe(owner=r3_owner, journal_path=journal, cas_root=cas_root)
    r3_evidence = executor.derive_d6_metadata_probe_execution_evidence(
        owner=r3_owner,
        selection=route,
        journal_path=journal,
        cas_root=cas_root,
        baseline_path=catalog,
    )
    assert r2_evidence.raw_evidence_ref is not None
    assert r3_evidence.raw_evidence_ref is not None
    assert r2_evidence.raw_evidence_ref.journal_path == journal.as_posix()
    assert r3_evidence.raw_evidence_ref.journal_path == journal.as_posix()

    r2_path = _write_model(current_root, DEFAULT_R2_METADATA_EVIDENCE, r2_evidence)
    route_path = _write_model(current_root, DEFAULT_D6_ROUTE, route)
    r3_path = _write_model(current_root, executor.DEFAULT_D6_PRIMARY_METADATA_EVIDENCE, r3_evidence)
    _write_model(current_root, executor.DEFAULT_METADATA_PROBE_OWNER, r2_owner)
    _write_model(current_root, executor.DEFAULT_D6_PRIMARY_METADATA_OWNER, r3_owner)

    dependencies = AdmissionDependencies(
        derive_lifecycle_manifest=contract_facade.derive_lifecycle_manifest,
        derive_metadata_probe_execution_evidence=executor.derive_metadata_probe_execution_evidence,
        derive_d6_metadata_probe_execution_evidence=(
            executor.derive_d6_metadata_probe_execution_evidence
        ),
    )
    reopened_r2, reopened_r3 = admission._reopen_current_metadata_receipts(
        root=current_root,
        baseline_path=catalog,
        r1=r1,
        d6=route,
        dependencies=dependencies,
    )
    assert reopened_r2 == r2_evidence
    assert reopened_r3 == r3_evidence

    monkeypatch.setattr(checker, "POLICY_ENGINE_ROOT", current_root)
    reopened_reentry = checker._reopen_current_d6_primary_metadata_evidence(
        route=route,
        catalog_path=catalog,
        journal_path=journal,
        cas_root=cas_root,
    )
    assert reopened_reentry == r3_evidence

    acceptance = _synthetic_acceptance_case(tmp_path / "synthetic-acceptance")
    _write_model(current_root, DEFAULT_ACCEPTANCE_CASE, acceptance)

    def current_availability(
        _catalog_root: Path,
        variable_id: str,
        *,
        overlay_path: Path,
    ) -> L1VariableAvailability:
        del overlay_path
        return L1VariableAvailability(
            variable_id=variable_id,
            status="unavailable",
            dataset_count=0,
            metric_binding_count=0,
            observation_count=0,
            coverage_ref=(f"repo://fixture/dataset_catalog.duckdb#variable/{variable_id}"),
        )

    monkeypatch.setattr(checker, "_catalog_repo_root", lambda _path: tmp_path)
    monkeypatch.setattr(checker, "l1_dcat_variable_availability", current_availability)
    monkeypatch.setattr(
        checker,
        "_resolve_reentry_catalog",
        lambda **kwargs: N7CatalogResolutionProjection(
            target_variable=str(kwargs["target_variable"]),
            mode="hybrid",
            fetch_plan_count=0,
            candidate_count=0,
            warnings=("no_fetch_plans_resolved",),
            fetch_plan_execution_count=0,
        ),
    )
    reentry_trace = checker._recompute_n13b_reentry_trace(
        catalog_path=catalog,
        substrate_path=substrate,
    )
    assert reentry_trace.primary_metadata_evidence_sha256 == r3_evidence.evidence_sha256

    original_journal = journal.read_bytes()
    stored_receipts = {path: path.read_bytes() for path in (r2_path, r3_path)}
    old_root = tmp_path / "old-locator-root"
    for relative in (
        DEFAULT_CARRIER_LIVENESS,
        DEFAULT_D6_ROUTE,
        DEFAULT_R2_METADATA_EVIDENCE,
        DEFAULT_R3_METADATA_EVIDENCE,
        executor.DEFAULT_METADATA_PROBE_OWNER,
        executor.DEFAULT_D6_PRIMARY_METADATA_OWNER,
        DEFAULT_ACCEPTANCE_CASE,
    ):
        source_path = current_root / relative
        target_path = old_root / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(source_path.read_bytes())
    monkeypatch.setattr(checker, "POLICY_ENGINE_ROOT", old_root)
    with pytest.raises(EvidenceJournalError) as old_contract_locator:
        admission._reopen_current_metadata_receipts(
            root=old_root,
            baseline_path=catalog,
            r1=r1,
            d6=route,
            dependencies=dependencies,
        )
    assert old_contract_locator.value.code == "journal_event_ref_unresolved"
    with pytest.raises(EvidenceJournalError) as old_reentry_locator:
        checker._recompute_n13b_reentry_trace(
            catalog_path=catalog,
            substrate_path=substrate,
        )
    assert old_reentry_locator.value.code == "journal_event_ref_unresolved"

    monkeypatch.setattr(checker, "POLICY_ENGINE_ROOT", current_root)
    for evidence in (r2_evidence, r3_evidence):
        journal.write_bytes(_mutate_raw_journal_bytes(original_journal, evidence))
        with pytest.raises(EvidenceJournalError):
            admission._reopen_current_metadata_receipts(
                root=current_root,
                baseline_path=catalog,
                r1=r1,
                d6=route,
                dependencies=dependencies,
            )
        with pytest.raises(EvidenceJournalError):
            checker._recompute_n13b_reentry_trace(
                catalog_path=catalog,
                substrate_path=substrate,
            )
        assert {path: path.read_bytes() for path in stored_receipts} == stored_receipts
        journal.write_bytes(original_journal)

    for evidence, require_reentry_refusal in (
        (r2_evidence, False),
        (r3_evidence, True),
    ):
        assert evidence.raw_artifact_id is not None
        blob_path = _cas_blob_path(cas_root, evidence.raw_artifact_id)
        declared_blob = blob_path.read_bytes()
        changed_blob = bytearray(declared_blob)
        changed_blob[0] ^= 1
        blob_path.write_bytes(changed_blob)
        with pytest.raises(ArtifactIntegrityError):
            admission._reopen_current_metadata_receipts(
                root=current_root,
                baseline_path=catalog,
                r1=r1,
                d6=route,
                dependencies=dependencies,
            )
        if require_reentry_refusal:
            with pytest.raises(ArtifactIntegrityError):
                checker._recompute_n13b_reentry_trace(
                    catalog_path=catalog,
                    substrate_path=substrate,
                )
        assert {path: path.read_bytes() for path in stored_receipts} == stored_receipts
        blob_path.write_bytes(declared_blob)
