from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon.canon_json import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_PROVISION,
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    DEFAULT_L5_MEASUREMENT_REGISTRY,
    AcquisitionAuthorityEntry,
    AcquisitionAuthorityError,
    AuthoritySchemaColumn,
    CanonicalAcquisitionAuthority,
    LicenseDisposition,
    LiveSourceExecutionEvidence,
    build_acquisition_authority_provision,
    build_authority_entry,
    build_authority_registry,
    build_live_source_execution_evidence,
)
from polisyos.data_forge.domains.catalog.knowledge.overlay import (
    CatalogAcquisitionOverlay,
    OverlayAdmissionError,
)
from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
from polisyos.fabric.connectors import resolve_connection_config
from polisyos.fabric.connectors.cache.store import ResultSerializer
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    append_fsync_jsonl,
    build_live_execution_authorization,
    content_sha256,
    resolve_linked_request_event,
    resolve_live_transport_trace,
    resolve_raw_response_body,
)
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.ir.connectors import (
    DataVersion,
    FetchRequest,
    FetchResult,
    QualityTier,
    VersionStrategy,
)
from polisyos.runtime.quality.acquisition_executor import (
    AdmissionStatus,
    build_admission_passport,
    revalidate_admission_passport,
)


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_l5(repo_root: Path) -> Path:
    path = repo_root / DEFAULT_L5_MEASUREMENT_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "coverage_rules": {"macro_state": 0.95},
                "proxy_mappings": {},
                "trust_tiers": {
                    "authoritative_high_coverage": {
                        "tier": "authoritative_high_coverage",
                        "min_coverage": 0.85,
                        "max_coverage": 1.0,
                        "trust_cap": 1.0,
                        "trust_multiplier": 1.0,
                    },
                    "administrative_noisy": {
                        "tier": "administrative_noisy",
                        "min_coverage": 0.0,
                        "max_coverage": 1.0,
                        "trust_cap": 0.7,
                        "trust_multiplier": 0.85,
                    },
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def _write_provision(
    repo_root: Path,
    *,
    baseline: Path,
    l5_path: Path,
    baseline_owner_ref: str,
    live_harness_receipts: tuple[dict[str, str], ...] = (),
) -> Path:
    provision = build_acquisition_authority_provision(
        baseline_owner_ref=baseline_owner_ref,
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_owner_ref=("repo://" + DEFAULT_L5_MEASUREMENT_REGISTRY.as_posix()),
        l5_measurement_registry_content_sha256=_sha(l5_path),
        live_harness_receipts=live_harness_receipts,
    )
    path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            provision.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    return path


def _baseline(repo_root: Path, *, license_id: str = "CC-BY-4.0") -> Path:
    root = repo_root / "catalog"
    graph = build_slice0_fixture_catalog_graph(root)
    graph.close()
    path = root / "catalog.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """
            INSERT INTO ds_datasets (
                id, source, agency, title, description, access_license,
                execution_tier, polisyos_metrics, preferred_distribution_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "source-worldbank-balance",
                "worldbank",
                "World Bank",
                "Cash surplus/deficit (% of GDP)",
                "Government cash balance as a share of GDP.",
                license_id,
                "transport_ready",
                ["gov_balance"],
                "source-worldbank-balance-json",
            ],
        )
        con.execute(
            """
            INSERT INTO ds_distributions (
                id, dataset_id, connector_type, profile_id, source_locator,
                parser_supported, machine_readable, quality_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "source-worldbank-balance-json",
                "source-worldbank-balance",
                "worldbank.wdi",
                "worldbank_wdi",
                "GC.BAL.CASH.GD.ZS",
                True,
                True,
                0.9,
            ],
        )
        con.execute(
            """
            INSERT INTO ds_metric_bindings (
                metric_id, dataset_id, distribution_id, connector_id, profile_id,
                request_dataset_id, confidence, metric_inference_confidence,
                default_filters, execution_tier, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "gov_balance",
                "source-worldbank-balance",
                "source-worldbank-balance-json",
                "worldbank.wdi",
                "worldbank_wdi",
                "GC.BAL.CASH.GD.ZS",
                0.87,
                0.95,
                "{}",
                "transport_ready",
                "worldbank",
            ],
        )
        con.execute(
            """
            INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "source-worldbank-balance",
                "GC.BAL.CASH.GD.ZS",
                "gov_balance",
                "exact",
                0.85,
                "Cash surplus/deficit % GDP;source=worldbank",
                False,
                0.0,
            ],
        )
    finally:
        con.close()
    return path


def _entry():
    return build_authority_entry(
        source_lane="live_fetch",
        target_variable="government.balance",
        landing_dataset_id="acquisition.worldbank.government_balance",
        landing_distribution_id="acquisition.worldbank.government_balance.json",
        source_catalog_dataset_id="source-worldbank-balance",
        source_catalog_distribution_id="source-worldbank-balance-json",
        upstream_metric_id="gov_balance",
        catalog_raw_variable="GC.BAL.CASH.GD.ZS",
        raw_field="value",
        raw_unit="percent_gdp",
        canonical_unit="percent_gdp",
        unit_transform="identity",
        unit_transform_ref="fabric://units/percent-gdp-identity/v1",
        alignment_method="meta_analytic",
        alignment_confidence=0.8,
        is_proxy=False,
        proxy_penalty=0.0,
        aggregation_method="identity",
        valid_min=-100.0,
        valid_max=100.0,
        evidence_refs=("duckdb://production_data/dataset_catalog.duckdb#/gov_balance",),
        schema_contract_ref="fabric://worldbank.wdi.generic@2.0.0",
        schema_columns=(
            AuthoritySchemaColumn(name="country_code", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="country_name", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="decimal", logical_types=("integer",), nullable=False),
            AuthoritySchemaColumn(name="indicator_id", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="indicator_name", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="unit", logical_types=("string",), nullable=False),
            AuthoritySchemaColumn(name="value", logical_types=("null", "number"), nullable=True),
            AuthoritySchemaColumn(name="year", logical_types=("integer",), nullable=False),
        ),
        l5_family_id="macro_state",
        title="Acquired government balance",
        description="Owner-validated World Bank government balance observations.",
        country_codes=("UKR",),
        temporal_start="2020",
        temporal_end="2024",
    )


def _family_receipt(attempt_id: str) -> dict[str, object]:
    outcome = "replay_fixture_missing_after_interception"
    profile = SourceProfileRegistry.get_instance().get("worldbank_wdi")
    assert profile is not None
    return {
        "connector_id": "worldbank.wdi",
        "component_id": "worldbank.wdi@1.0.0",
        "connector_class": ("polisyos.fabric.connectors.sources.world_bank.WorldBankConnector"),
        "protocol_violations": [],
        "protocol_conformant": True,
        "harness_checks_passed": [
            "capability_gated_methods_present",
            "connect_returns_unique_sessions",
            "core_methods_are_async",
            "disconnect_idempotent",
            "protocol_compliance",
            "required_class_attributes",
        ],
        "harness_check_failures": [],
        "carrier_denominator": 1,
        "carrier_attempt_count": 1,
        "dry_run_attempts": [
            {
                "attempt_id": attempt_id,
                "profile_id": "worldbank_wdi",
                "source_profile_family": "worldbank",
                "request_dataset_id": "GC.BAL.CASH.GD.ZS",
                "fetch_request_key": FetchRequest(dataset_id="GC.BAL.CASH.GD.ZS").request_key,
                "connection_config_content_sha256": content_sha256(
                    resolve_connection_config(profile).to_dict(redact=True)
                ),
                "connector_fetch_invoked": True,
                "fetch_completed": False,
                "outcome": outcome,
                "finding_code": outcome,
                "failure_type": (
                    "polisyos.fabric.connectors.testing.simulator.MissingFixtureError"
                ),
                "simulator_mode": "replay",
                "simulator_call_count": 1,
                "transport_intercepted": True,
                "network_escape_attempt_count": 0,
                "actual_network_call_count": 0,
            }
        ],
        "outcome_counts": {outcome: 1},
        "safe_dry_run_passed": True,
        "simulator_mode": "replay",
        "simulator_intercepted": True,
        "simulator_call_count": 1,
        "network_escape_attempt_count": 0,
        "simulator_network_calls": 0,
    }


def _write_family_receipt(
    repo_root: Path,
    *,
    entry_id: str,
    attempt_id: str,
    receipt: dict[str, object],
    receipt_path: str = "evidence/worldbank-wdi-live-harness.json",
) -> dict[str, str]:
    path = repo_root / receipt_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return {
        "entry_id": entry_id,
        "attempt_id": attempt_id,
        "receipt_owner_ref": f"repo://{receipt_path}",
        "receipt_content_sha256": _sha(path),
    }


def _resolver(
    repo_root: Path,
    *,
    license_id: str = "CC-BY-4.0",
    authority_entry: AcquisitionAuthorityEntry | None = None,
    live_harness_receipts: tuple[dict[str, str], ...] = (),
):
    baseline = _baseline(repo_root, license_id=license_id)
    l5 = _write_l5(repo_root)
    entry = authority_entry or _entry()
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5),
        entries=(entry,),
    )
    path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            registry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    _write_provision(
        repo_root,
        baseline=baseline,
        l5_path=l5,
        baseline_owner_ref="repo://catalog/catalog.duckdb",
        live_harness_receipts=live_harness_receipts,
    )
    return (
        CanonicalAcquisitionAuthority.from_provision(
            repo_root=repo_root,
            baseline_path=baseline,
        ),
        entry,
    )


def _live_execution_fixture(
    tmp_path: Path,
    *,
    carrier_updates: dict[str, object] | None = None,
):
    """Build one fully content-bound, network-free WDI execution fixture."""

    from polisyos.data_forge.domains.catalog.knowledge import acquisition_authority

    repo_root = tmp_path / "repo"
    entry = _entry()
    attempt_id = "n13b-worldbank-government-balance-001"
    family_receipt = _family_receipt(attempt_id)
    if carrier_updates:
        carrier = dict(family_receipt["dry_run_attempts"][0])
        carrier.update(carrier_updates)
        family_receipt["dry_run_attempts"] = [carrier]
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=attempt_id,
        receipt=family_receipt,
    )
    resolver, entry = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )
    resolved = resolver.resolve(entry.entry_id)
    store = FileSystemCAS(tmp_path / "cas")
    raw_body = json.dumps(
        [
            {"page": 1, "pages": 1, "per_page": 1000, "total": 2},
            [
                {
                    "countryiso3code": "UKR",
                    "country": {"id": "UA", "value": "Ukraine"},
                    "indicator": {
                        "id": "GC.BAL.CASH.GD.ZS",
                        "value": "Cash surplus/deficit (% of GDP)",
                    },
                    "date": "2023",
                    "value": -18.2,
                    "unit": "% of GDP",
                    "decimal": 1,
                },
                {
                    "countryiso3code": "UKR",
                    "country": {"id": "UA", "value": "Ukraine"},
                    "indicator": {
                        "id": "GC.BAL.CASH.GD.ZS",
                        "value": "Cash surplus/deficit (% of GDP)",
                    },
                    "date": "2024",
                    "value": -17.1,
                    "unit": "% of GDP",
                    "decimal": 1,
                },
            ],
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    raw_sha256 = "sha256:" + hashlib.sha256(raw_body).hexdigest()
    raw_artifact = store.put_bytes(
        raw_body,
        ArtifactWriteOptions(
            kind="fabric.acquisition.raw_evidence",
            media_type="application/json",
        ),
    )
    request = {
        "authority_entry_id": entry.entry_id,
        "authority_registry_content_sha256": resolved.registry_content_sha256,
        "variable_id": entry.target_variable,
        "source_lane": entry.source_lane,
        "dataset_id": entry.landing_dataset_id,
        "distribution_id": entry.landing_distribution_id,
        "connector_id": resolved.registration.connector_id,
        "profile_id": resolved.registration.source_profile_id,
        "request_dataset_id": resolved.registration.request_dataset_id,
        "request_variables": [resolved.registration.request_dataset_id],
        "filters": {"country": ["UKR"]},
        "date_start": "2023-01-01",
        "date_end": "2024-12-31",
        "page_size": 1000,
        "schema_contract": entry.schema_projection(),
    }
    profile = SourceProfileRegistry.get_instance().get("worldbank_wdi")
    assert profile is not None
    baseline_sha256 = _sha(resolver.baseline_path)
    authorization = build_live_execution_authorization(
        attempt_id=attempt_id,
        connector_id="worldbank.wdi",
        request_dataset_id="GC.BAL.CASH.GD.ZS",
        request=request,
        schema_contract=entry.schema_projection(),
        source_profile=profile,
        baseline_sha256=baseline_sha256,
        family_receipt=family_receipt,
        max_response_bytes=65_536,
        max_decompressed_bytes=65_536,
    )
    journal = AppendOnlyEvidenceJournal(tmp_path / "journal.jsonl")
    request_ref = journal.append_request(attempt_id=attempt_id, request=request)
    transport_ref = journal.append_transport_attempt(
        attempt_id=attempt_id,
        request_ref=request_ref,
        connector_id="worldbank.wdi",
        url=("https://api.worldbank.org/v2/country/UKR/indicator/GC.BAL.CASH.GD.ZS"),
        params={
            "date": "2023:2024",
            "format": "json",
            "page": "1",
            "per_page": "1000",
        },
    )
    journal.append_heartbeat(
        attempt_id=attempt_id,
        phase="attempt_started",
        progress_bytes=0,
        elapsed_seconds=0.0,
    )
    journal.append_heartbeat(
        attempt_id=attempt_id,
        phase="response_headers",
        progress_bytes=0,
        elapsed_seconds=0.1,
    )
    journal.append_heartbeat(
        attempt_id=attempt_id,
        phase="body_progress",
        progress_bytes=len(raw_body),
        elapsed_seconds=0.2,
    )
    raw_ref = journal.append_raw_evidence(
        attempt_id=attempt_id,
        request_ref=request_ref,
        transport_ref=transport_ref,
        payload=raw_body,
        status_code=200,
        response_headers={"content-type": "application/json"},
        budget=authorization.budget,
    )
    normalized = pd.DataFrame(
        [
            {
                "country_code": "UKR",
                "country_name": "Ukraine",
                "indicator_id": "GC.BAL.CASH.GD.ZS",
                "indicator_name": "Cash surplus/deficit (% of GDP)",
                "year": 2023,
                "value": -18.2,
                "unit": "% of GDP",
                "decimal": 1,
            },
            {
                "country_code": "UKR",
                "country_name": "Ukraine",
                "indicator_id": "GC.BAL.CASH.GD.ZS",
                "indicator_name": "Cash surplus/deficit (% of GDP)",
                "year": 2024,
                "value": -17.1,
                "unit": "% of GDP",
                "decimal": 1,
            },
        ]
    )
    fetched_at = datetime.now(UTC)
    result = FetchResult(
        data=normalized,
        row_count=len(normalized),
        schema_id="worldbank.wdi.generic",
        schema_version="2.0.0",
        version=DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value=raw_sha256,
            timestamp=fetched_at,
            content_hash=raw_sha256,
        ),
        fetched_at=fetched_at,
        completeness=1.0,
        quality_tier=QualityTier.GOLD,
        has_more=False,
        next_page_token=None,
    )
    serialized, media_type = ResultSerializer.serialize(result)
    data_ref = store.put_bytes(
        serialized,
        ArtifactWriteOptions(
            kind="fabric.connector_cache.payload",
            media_type=media_type,
        ),
    )
    evidence_bundle_ref = persist_evidence_bundle(
        store,
        build_evidence_bundle(sources=[data_ref], notes=["network-free WDI fixture"]),
    )
    snapshot = DataSnapshot(
        data_ref=data_ref,
        evidence_ref=evidence_bundle_ref,
        stats={"datasets_fetched": 1, "source": "orchestrated_ingestion:test"},
        notes=["fabric.data_plane.orchestrator", "datasets=1"],
    )
    snapshot_artifact = store.put_json(
        snapshot,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    snapshot_ref = DataSnapshotRef(artifact_id=snapshot_artifact.artifact_id)
    live_evidence = acquisition_authority.build_live_source_execution_evidence(
        authorization=authorization,
        family_receipt=family_receipt,
        request_ref=request_ref,
        raw_evidence_ref=raw_ref,
        transport_trace=resolve_live_transport_trace(raw_ref),
        raw_artifact_id=str(raw_artifact.artifact_id),
        evidence_bundle_ref=evidence_bundle_ref,
        data_snapshot_ref=snapshot_ref,
        normalized_data_artifact_id=str(data_ref.artifact_id),
        variable_count=1,
        page_count=1,
        baseline_before_sha256=baseline_sha256,
        baseline_after_sha256=baseline_sha256,
        raw_body_sha256=raw_sha256,
        normalized_result_content_sha256=raw_sha256,
    )
    return resolver, entry, store, live_evidence, family_receipt, result


def test_authority_resolves_catalog_license_l5_and_registration(tmp_path: Path) -> None:
    resolver, entry = _resolver(tmp_path)

    resolved = resolver.resolve(entry.entry_id)

    assert resolved.license_disposition is LicenseDisposition.ADMISSIBLE_OPEN
    assert resolved.registration.connector_id == "worldbank.wdi"
    assert resolved.registration.request_dataset_id == "GC.BAL.CASH.GD.ZS"
    assert resolved.field_binding.canonical_variable == "government.balance"
    assert resolved.l5_trust.family_id == "macro_state"
    assert resolved.l5_trust.trust_cap == 1.0
    assert resolved.effective_authority_score == 0.8
    assert resolved.license_authority_ref == (
        "repo://catalog/catalog.duckdb#ds_datasets/source-worldbank-balance/access_license"
    )


def test_live_license_ref_uses_logical_owner_for_external_baseline(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "worktree"
    baseline = _baseline(tmp_path / "main-tree")
    l5 = _write_l5(repo_root)
    entry = _entry()
    registry = build_authority_registry(
        baseline_content_sha256=_sha(baseline),
        l5_measurement_registry_sha256=_sha(l5),
        entries=(entry,),
    )
    path = repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            registry.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    _write_provision(
        repo_root,
        baseline=baseline,
        l5_path=l5,
        baseline_owner_ref=("repo://production_data/snapshot/dataset_catalog.duckdb"),
    )
    resolver = CanonicalAcquisitionAuthority.from_provision(
        repo_root=repo_root,
        baseline_path=baseline,
    )

    resolved = resolver.resolve(entry.entry_id)

    assert resolved.license_authority_ref == (
        "repo://production_data/snapshot/dataset_catalog.duckdb"
        "#ds_datasets/source-worldbank-balance/access_license"
    )


def test_live_execution_evidence_reopens_raw_and_normalized_carriers(
    tmp_path: Path,
) -> None:
    resolver, entry, store, evidence, _, expected = _live_execution_fixture(tmp_path)

    resolved_result = resolver.resolve_live_source_execution(
        entry.entry_id,
        evidence,
        artifact_store=store,
    )

    assert resolved_result.version.content_hash == evidence.raw_body_sha256
    assert resolved_result.data.equals(expected.data)
    assert evidence.call_count == 1
    assert evidence.variable_count == 1
    assert evidence.page_count == 1


def test_live_harness_receipt_resolves_exact_owner_bytes(tmp_path: Path) -> None:
    resolver, entry, _, evidence, family_receipt, _ = _live_execution_fixture(tmp_path)

    resolved = resolver.resolve_live_harness_receipt(
        entry.entry_id,
        evidence.authorization.attempt_id,
    )

    assert resolved.family_receipt == family_receipt
    assert resolved.receipt_owner_ref == ("repo://evidence/worldbank-wdi-live-harness.json")
    assert resolved.receipt_content_sha256 == _sha(
        resolver.repo_root / "evidence/worldbank-wdi-live-harness.json"
    )
    profile = SourceProfileRegistry.get_instance().get("worldbank_wdi")
    assert profile is not None
    assert resolved.connection_config_content_sha256 == content_sha256(
        resolve_connection_config(profile).to_dict(redact=True)
    )
    assert resolved.fetch_request_key == FetchRequest(dataset_id="GC.BAL.CASH.GD.ZS").request_key
    assert resolved.source_profile_family == "worldbank"


@pytest.mark.parametrize(
    ("carrier_updates", "error_code"),
    [
        (
            {"connection_config_content_sha256": "sha256:" + "0" * 64},
            "live_harness_connection_config_drift",
        ),
        (
            {"fetch_request_key": "sha256:" + "0" * 64},
            "live_harness_fetch_request_drift",
        ),
        (
            {"source_profile_family": "forged"},
            "live_harness_profile_family_drift",
        ),
    ],
)
def test_live_execution_recomputes_selected_harness_runtime_bindings(
    tmp_path: Path,
    carrier_updates: dict[str, object],
    error_code: str,
) -> None:
    resolver, entry, store, evidence, _, _ = _live_execution_fixture(
        tmp_path,
        carrier_updates=carrier_updates,
    )

    with pytest.raises(AcquisitionAuthorityError, match=error_code):
        resolver.resolve_live_source_execution(entry.entry_id, evidence, store)


def test_live_harness_receipt_rejects_file_drift(tmp_path: Path) -> None:
    resolver, entry, _, evidence, family_receipt, _ = _live_execution_fixture(tmp_path)
    path = resolver.repo_root / "evidence/worldbank-wdi-live-harness.json"
    path.write_text(
        json.dumps(
            {**family_receipt, "connector_class": "forged.ReplacementConnector"},
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_harness_receipt_content_drift",
    ):
        resolver.resolve_live_harness_receipt(
            entry.entry_id,
            evidence.authorization.attempt_id,
        )


def test_live_harness_receipt_rejects_path_escape(tmp_path: Path) -> None:
    resolver, entry = _resolver(tmp_path)

    with pytest.raises(ValidationError, match="live harness receipt owner ref"):
        build_acquisition_authority_provision(
            baseline_owner_ref=resolver.provision.baseline_owner_ref,
            baseline_content_sha256=_sha(resolver.baseline_path),
            l5_measurement_registry_owner_ref=resolver.provision.l5_measurement_registry_owner_ref,
            l5_measurement_registry_content_sha256=_sha(resolver.l5_path),
            live_harness_receipts=(
                {
                    "entry_id": entry.entry_id,
                    "attempt_id": "n13b-worldbank-government-balance-001",
                    "receipt_owner_ref": "repo://../outside.json",
                    "receipt_content_sha256": "sha256:" + "0" * 64,
                },
            ),
        )


@pytest.mark.parametrize(
    ("entry_id", "attempt_id", "error_code"),
    [
        (
            "acquisition-authority:sha256:" + "0" * 64,
            "n13b-worldbank-government-balance-001",
            "authority_entry_unresolved",
        ),
        (
            _entry().entry_id,
            "n13b-worldbank-government-balance-999",
            "live_harness_receipt_provision_unresolved",
        ),
    ],
)
def test_live_harness_receipt_rejects_entry_or_attempt_mismatch(
    tmp_path: Path,
    entry_id: str,
    attempt_id: str,
    error_code: str,
) -> None:
    resolver, _, _, _, _, _ = _live_execution_fixture(tmp_path)

    with pytest.raises(
        AcquisitionAuthorityError,
        match=error_code,
    ):
        resolver.resolve_live_harness_receipt(entry_id, attempt_id)


def test_live_harness_receipt_rejects_reduced_shaped_green_payload(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    entry = _entry()
    attempt_id = "n13b-worldbank-government-balance-001"
    shaped_green: dict[str, object] = {
        "connector_id": "worldbank.wdi",
        "protocol_conformant": True,
        "harness_checks_passed": ["protocol_compliance"],
        "harness_check_failures": [],
        "safe_dry_run_passed": True,
        "simulator_intercepted": True,
        "network_escape_attempt_count": 0,
        "dry_run_attempts": [
            {
                "attempt_id": attempt_id,
                "profile_id": "worldbank_wdi",
                "request_dataset_id": "GC.BAL.CASH.GD.ZS",
                "outcome": "replay_fixture_missing_after_interception",
                "transport_intercepted": True,
            }
        ],
    }
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=attempt_id,
        receipt=shaped_green,
    )
    resolver, _ = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )

    with pytest.raises(AcquisitionAuthorityError, match="live_harness_receipt_invalid"):
        resolver.resolve_live_harness_receipt(entry.entry_id, attempt_id)


@pytest.mark.parametrize(
    "missing_fields",
    [
        ("connection_config_content_sha256",),
        ("connection_config_content_sha256", "fetch_request_key"),
    ],
)
def test_live_harness_receipt_requires_selected_request_and_config_bindings(
    tmp_path: Path,
    missing_fields: tuple[str, ...],
) -> None:
    repo_root = tmp_path / "repo"
    entry = _entry()
    attempt_id = "n13b-worldbank-government-balance-001"
    family_receipt = _family_receipt(attempt_id)
    carrier = dict(family_receipt["dry_run_attempts"][0])
    for field in missing_fields:
        carrier.pop(field)
    family_receipt["dry_run_attempts"] = [carrier]
    receipt_provision = _write_family_receipt(
        repo_root,
        entry_id=entry.entry_id,
        attempt_id=attempt_id,
        receipt=family_receipt,
    )
    resolver, _ = _resolver(
        repo_root,
        authority_entry=entry,
        live_harness_receipts=(receipt_provision,),
    )

    with pytest.raises(AcquisitionAuthorityError, match="live_harness_receipt_invalid"):
        resolver.resolve_live_harness_receipt(entry.entry_id, attempt_id)


def test_live_harness_receipt_rejects_coordinated_owner_mutation(
    tmp_path: Path,
) -> None:
    resolver, entry, _, evidence, family_receipt, _ = _live_execution_fixture(tmp_path)
    mutated = {
        **family_receipt,
        "connector_class": "forged.ReplacementConnector",
    }
    receipt_provision = _write_family_receipt(
        resolver.repo_root,
        entry_id=entry.entry_id,
        attempt_id=evidence.authorization.attempt_id,
        receipt=mutated,
    )
    _write_provision(
        resolver.repo_root,
        baseline=resolver.baseline_path,
        l5_path=resolver.l5_path,
        baseline_owner_ref=resolver.provision.baseline_owner_ref,
        live_harness_receipts=(receipt_provision,),
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="acquisition_authority_provision_drift",
    ):
        resolver.resolve_live_harness_receipt(
            entry.entry_id,
            evidence.authorization.attempt_id,
        )


def test_live_passport_measures_normalized_snapshot_and_retains_raw_carrier(
    tmp_path: Path,
) -> None:
    resolver, _, store, evidence, _, _ = _live_execution_fixture(tmp_path)

    passport = build_admission_passport(
        epoch_id=1,
        raw_evidence_ref=evidence.raw_evidence_ref,
        artifact_store=store,
        raw_artifact_id=str(evidence.raw_artifact_id),
        authority=resolver,
        live_source_execution=evidence,
    )

    assert passport.status is AdmissionStatus.ADMITTED
    assert passport.source_lane == "live_fetch"
    assert passport.live_source_execution == evidence
    assert passport.measured_profile.sample_row_count == 2
    assert {column.name for column in passport.measured_profile.columns} == {
        "country_code",
        "country_name",
        "decimal",
        "indicator_id",
        "indicator_name",
        "unit",
        "value",
        "year",
    }
    assert passport.measured_profile.sample_content_sha256 != evidence.raw_body_sha256
    assert passport.source_watermark == evidence.raw_body_sha256
    assert passport.raw_evidence_ref == evidence.raw_evidence_ref
    assert passport.source_authority_verified is True
    assert (
        revalidate_admission_passport(
            passport,
            artifact_store=store,
            authority=resolver,
        )
        == passport
    )


def test_live_overlay_derives_only_from_reopened_normalized_snapshot(
    tmp_path: Path,
) -> None:
    resolver, _, store, evidence, _, _ = _live_execution_fixture(tmp_path)
    passport = build_admission_passport(
        epoch_id=1,
        raw_evidence_ref=evidence.raw_evidence_ref,
        artifact_store=store,
        raw_artifact_id=str(evidence.raw_artifact_id),
        authority=resolver,
        live_source_execution=evidence,
    )
    overlay = CatalogAcquisitionOverlay(
        resolver.baseline_path,
        tmp_path / "overlay.duckdb",
    )
    overlay.initialize()

    receipt = overlay.admit_epoch(
        passport=passport,
        artifact_store=store,
        authority=resolver,
    )

    assert receipt.admitted_observation_count == 2
    con = duckdb.connect(str(overlay.overlay_path), read_only=True)
    try:
        assert con.execute("SELECT value FROM ds_observations ORDER BY year").fetchall() == [
            (-18.2,),
            (-17.1,),
        ]
    finally:
        con.close()
        overlay.close()


def test_live_overlay_rejects_mutated_execution_receipt(tmp_path: Path) -> None:
    resolver, _, store, evidence, receipt, _ = _live_execution_fixture(tmp_path)
    passport = build_admission_passport(
        epoch_id=1,
        raw_evidence_ref=evidence.raw_evidence_ref,
        artifact_store=store,
        raw_artifact_id=str(evidence.raw_artifact_id),
        authority=resolver,
        live_source_execution=evidence,
    )
    mutated = evidence.model_copy(
        update={
            "family_receipt": {**receipt, "safe_dry_run_passed": False},
        }
    )
    forged = passport.model_copy(update={"live_source_execution": mutated})
    overlay = CatalogAcquisitionOverlay(
        resolver.baseline_path,
        tmp_path / "overlay.duckdb",
    )
    overlay.initialize()

    with pytest.raises(OverlayAdmissionError, match="live_source_execution_unresolved"):
        overlay.admit_epoch(
            passport=forged,
            artifact_store=store,
            authority=resolver,
        )
    overlay.close()


def _rebuild_live_evidence(
    evidence: LiveSourceExecutionEvidence,
    **updates: object,
) -> LiveSourceExecutionEvidence:
    values: dict[str, object] = {
        "authorization": evidence.authorization,
        "family_receipt": evidence.family_receipt,
        "request_ref": evidence.request_ref,
        "raw_evidence_ref": evidence.raw_evidence_ref,
        "transport_trace": evidence.transport_trace,
        "raw_artifact_id": evidence.raw_artifact_id,
        "evidence_bundle_ref": evidence.evidence_bundle_ref,
        "data_snapshot_ref": evidence.data_snapshot_ref,
        "normalized_data_artifact_id": evidence.normalized_data_artifact_id,
        "variable_count": evidence.variable_count,
        "page_count": evidence.page_count,
        "baseline_before_sha256": evidence.baseline_before_sha256,
        "baseline_after_sha256": evidence.baseline_after_sha256,
        "raw_body_sha256": evidence.raw_body_sha256,
        "normalized_result_content_sha256": (evidence.normalized_result_content_sha256),
    }
    values.update(updates)
    return build_live_source_execution_evidence(**values)  # type: ignore[arg-type]


def _rebind_live_request_and_transport(
    tmp_path: Path,
    evidence: LiveSourceExecutionEvidence,
    family_receipt: dict[str, object],
    *,
    mutation: str,
) -> LiveSourceExecutionEvidence:
    request_event = resolve_linked_request_event(evidence.raw_evidence_ref)
    request = dict(request_event["request"])
    url = "https://api.worldbank.org/v2/country/UKR/indicator/GC.BAL.CASH.GD.ZS"
    params = {
        "date": "2023:2024",
        "format": "json",
        "page": "1",
        "per_page": "1000",
    }
    if mutation == "request_variables":
        request["request_variables"] = ["FP.CPI.TOTL"]
    elif mutation == "country":
        request["filters"] = {"country": ["POL"]}
        url = url.replace("/UKR/", "/POL/")
    elif mutation == "date":
        request["date_start"] = "2019-01-01"
        params["date"] = "2019:2024"
    elif mutation == "page_size":
        request["page_size"] = 0
        params["per_page"] = "0"
    elif mutation == "url":
        url = url.replace("api.worldbank.org", "attacker.invalid")
    elif mutation == "params":
        params["date"] = "2022:2024"
    else:  # pragma: no cover - test helper contract
        raise AssertionError(mutation)

    profile = SourceProfileRegistry.get_instance().get("worldbank_wdi")
    assert profile is not None
    authorization = build_live_execution_authorization(
        attempt_id=evidence.authorization.attempt_id,
        connector_id=evidence.authorization.connector_id,
        request_dataset_id=evidence.authorization.request_variables[0],
        request=request,
        schema_contract=request["schema_contract"],
        source_profile=profile,
        baseline_sha256=evidence.baseline_before_sha256,
        family_receipt=family_receipt,
        max_response_bytes=evidence.authorization.budget.max_response_bytes,
        max_decompressed_bytes=evidence.authorization.budget.max_decompressed_bytes,
    )
    journal = AppendOnlyEvidenceJournal(tmp_path / f"mutated-{mutation}.jsonl")
    request_ref = journal.append_request(
        attempt_id=authorization.attempt_id,
        request=request,
    )
    transport_ref = journal.append_transport_attempt(
        attempt_id=authorization.attempt_id,
        request_ref=request_ref,
        connector_id=authorization.connector_id,
        url=url,
        params=params,
    )
    raw_body = resolve_raw_response_body(evidence.raw_evidence_ref)
    journal.append_heartbeat(
        attempt_id=authorization.attempt_id,
        phase="attempt_started",
        progress_bytes=0,
        elapsed_seconds=0.0,
    )
    journal.append_heartbeat(
        attempt_id=authorization.attempt_id,
        phase="response_headers",
        progress_bytes=0,
        elapsed_seconds=0.1,
    )
    journal.append_heartbeat(
        attempt_id=authorization.attempt_id,
        phase="body_progress",
        progress_bytes=len(raw_body),
        elapsed_seconds=0.2,
    )
    raw_ref = journal.append_raw_evidence(
        attempt_id=authorization.attempt_id,
        request_ref=request_ref,
        transport_ref=transport_ref,
        payload=raw_body,
        status_code=200,
        response_headers={"content-type": "application/json"},
        budget=authorization.budget,
    )
    return _rebuild_live_evidence(
        evidence,
        authorization=authorization,
        request_ref=request_ref,
        raw_evidence_ref=raw_ref,
        transport_trace=resolve_live_transport_trace(raw_ref),
    )


def _rebind_normalized_result(
    store: FileSystemCAS,
    evidence: LiveSourceExecutionEvidence,
    result: FetchResult,
    *,
    field_name: str,
) -> LiveSourceExecutionEvidence:
    frame = result.data.copy()
    replacements = {
        "value": -999.0,
        "unit": "percentage points",
        "decimal": 7,
        "indicator_name": "Fabricated government balance",
    }
    frame.loc[0, field_name] = replacements[field_name]
    mutated_result = result.model_copy(update={"data": frame})
    serialized, media_type = ResultSerializer.serialize(mutated_result)
    data_ref = store.put_bytes(
        serialized,
        ArtifactWriteOptions(
            kind="fabric.connector_cache.payload",
            media_type=media_type,
        ),
    )
    evidence_bundle_ref = persist_evidence_bundle(
        store,
        build_evidence_bundle(
            sources=[data_ref],
            notes=["adversarial normalized projection"],
        ),
    )
    snapshot = DataSnapshot(
        data_ref=data_ref,
        evidence_ref=evidence_bundle_ref,
        stats={"datasets_fetched": 1, "source": "orchestrated_ingestion:test"},
        notes=["fabric.data_plane.orchestrator", "datasets=1"],
    )
    snapshot_artifact = store.put_json(
        snapshot,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return _rebuild_live_evidence(
        evidence,
        evidence_bundle_ref=evidence_bundle_ref,
        data_snapshot_ref=DataSnapshotRef(artifact_id=snapshot_artifact.artifact_id),
        normalized_data_artifact_id=data_ref.artifact_id,
    )


def test_live_execution_rejects_mutated_family_receipt(tmp_path: Path) -> None:
    resolver, entry, store, evidence, receipt, _ = _live_execution_fixture(tmp_path)
    mutated_receipt = {**receipt, "safe_dry_run_passed": False}
    mutated = evidence.model_copy(update={"family_receipt": mutated_receipt})

    with pytest.raises(AcquisitionAuthorityError, match="live_source_execution_invalid"):
        resolver.resolve_live_source_execution(entry.entry_id, mutated, store)


def test_live_execution_rejects_caller_fabricated_shaped_green_receipt(
    tmp_path: Path,
) -> None:
    resolver, entry, store, evidence, _, _ = _live_execution_fixture(tmp_path)
    request_event = resolve_linked_request_event(evidence.raw_evidence_ref)
    request = dict(request_event["request"])
    shaped_green = {
        "connector_id": "worldbank.wdi",
        "protocol_conformant": True,
        "harness_checks_passed": ["protocol_compliance"],
        "harness_check_failures": [],
        "safe_dry_run_passed": True,
        "simulator_intercepted": True,
        "network_escape_attempt_count": 0,
        "dry_run_attempts": [
            {
                "attempt_id": evidence.authorization.attempt_id,
                "profile_id": "worldbank_wdi",
                "request_dataset_id": "GC.BAL.CASH.GD.ZS",
                "outcome": "replay_fixture_missing_after_interception",
                "transport_intercepted": True,
            }
        ],
    }
    profile = SourceProfileRegistry.get_instance().get("worldbank_wdi")
    assert profile is not None
    forged_authorization = build_live_execution_authorization(
        attempt_id=evidence.authorization.attempt_id,
        connector_id=evidence.authorization.connector_id,
        request_dataset_id=evidence.authorization.request_variables[0],
        request=request,
        schema_contract=entry.schema_projection(),
        source_profile=profile,
        baseline_sha256=evidence.baseline_before_sha256,
        family_receipt=shaped_green,
        max_response_bytes=evidence.authorization.budget.max_response_bytes,
        max_decompressed_bytes=evidence.authorization.budget.max_decompressed_bytes,
    )
    forged = _rebuild_live_evidence(
        evidence,
        authorization=forged_authorization,
        family_receipt=shaped_green,
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_harness_receipt_evidence_drift",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, forged, store)


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        ("request_variables", "live_request_owner_projection_drift"),
        ("country", "live_request_scope_invalid"),
        ("date", "live_request_scope_invalid"),
        ("page_size", "live_request_scope_invalid"),
        ("url", "live_transport_owner_projection_drift"),
        ("params", "live_transport_owner_projection_drift"),
    ],
)
def test_live_execution_authority_rederives_request_and_transport_scope(
    tmp_path: Path,
    mutation: str,
    error_code: str,
) -> None:
    resolver, entry, store, evidence, family_receipt, _ = _live_execution_fixture(tmp_path)
    forged = _rebind_live_request_and_transport(
        tmp_path,
        evidence,
        family_receipt,
        mutation=mutation,
    )

    with pytest.raises(AcquisitionAuthorityError, match=error_code):
        resolver.resolve_live_source_execution(entry.entry_id, forged, store)


@pytest.mark.parametrize(
    "field_name",
    ["value", "unit", "decimal", "indicator_name"],
)
def test_live_execution_authority_rederives_all_normalized_fields_from_raw(
    tmp_path: Path,
    field_name: str,
) -> None:
    resolver, entry, store, evidence, _, result = _live_execution_fixture(tmp_path)
    forged = _rebind_normalized_result(
        store,
        evidence,
        result,
        field_name=field_name,
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_normalized_raw_projection_drift",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, forged, store)


def test_live_passport_rejects_source_watermark_not_bound_to_raw_body(
    tmp_path: Path,
) -> None:
    resolver, _, store, evidence, _, _ = _live_execution_fixture(tmp_path)
    passport = build_admission_passport(
        epoch_id=1,
        raw_evidence_ref=evidence.raw_evidence_ref,
        artifact_store=store,
        raw_artifact_id=str(evidence.raw_artifact_id),
        authority=resolver,
        live_source_execution=evidence,
    )
    forged = passport.model_copy(update={"source_watermark": "sha256:" + "0" * 64})

    with pytest.raises(ValueError, match="source_watermark_content_drift"):
        revalidate_admission_passport(
            forged,
            artifact_store=store,
            authority=resolver,
        )


def test_live_execution_rejects_recomputed_wrong_raw_cas(tmp_path: Path) -> None:
    resolver, entry, store, evidence, _, _ = _live_execution_fixture(tmp_path)
    fabricated = store.put_bytes(
        b'{"fabricated":true}',
        ArtifactWriteOptions(
            kind="fabric.acquisition.raw_evidence",
            media_type="application/json",
        ),
    )
    mutated = _rebuild_live_evidence(
        evidence,
        raw_artifact_id=fabricated.artifact_id,
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_raw_journal_cas_mismatch",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, mutated, store)


def test_live_execution_rejects_wrong_snapshot_ref(tmp_path: Path) -> None:
    resolver, entry, store, evidence, _, _ = _live_execution_fixture(tmp_path)
    mutated = _rebuild_live_evidence(
        evidence,
        data_snapshot_ref=DataSnapshotRef(artifact_id=evidence.evidence_bundle_ref.artifact_id),
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_artifact_ref_manifest_drift",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, mutated, store)


def test_live_execution_recomputes_one_dataset_from_snapshot(tmp_path: Path) -> None:
    resolver, entry, store, evidence, _, _ = _live_execution_fixture(tmp_path)
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(evidence.data_snapshot_ref.artifact_id))
    )
    expanded = snapshot.model_copy(update={"stats": {**snapshot.stats, "datasets_fetched": 2}})
    expanded_ref = store.put_json(
        expanded,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    mutated = _rebuild_live_evidence(
        evidence,
        data_snapshot_ref=DataSnapshotRef(artifact_id=expanded_ref.artifact_id),
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_snapshot_dataset_count_invalid",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, mutated, store)


def test_live_execution_recomputes_one_call_from_complete_journal(
    tmp_path: Path,
) -> None:
    resolver, entry, store, evidence, _, _ = _live_execution_fixture(tmp_path)
    retry_request = {
        "variable_id": "government.balance",
        "schema_contract": {"columns": ["value"]},
    }
    retry_request_ref = append_fsync_jsonl(
        Path(evidence.request_ref.journal_path),
        {
            "sequence": evidence.raw_evidence_ref.sequence + 1,
            "event_kind": "request",
            "attempt_id": "renamed-retry",
            "request": retry_request,
            "request_sha256": content_sha256(retry_request),
        },
    )
    append_fsync_jsonl(
        Path(evidence.request_ref.journal_path),
        {
            "sequence": retry_request_ref.sequence + 1,
            "event_kind": "transport_attempt",
            "attempt_id": "renamed-retry",
            "transport_attempt": {
                "request_event_sha256": retry_request_ref.event_sha256,
                "connector_id": "worldbank.wdi",
                "url": ("https://api.worldbank.org/v2/country/UKR/indicator/GC.BAL.CASH.GD.ZS"),
                "params": {"page": "1"},
                "params_sha256": content_sha256({"page": "1"}),
            },
        },
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_transport_trace_invalid",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, evidence, store)


def test_live_execution_recomputes_one_page_from_fetch_result(tmp_path: Path) -> None:
    resolver, entry, store, evidence, _, expected = _live_execution_fixture(tmp_path)
    paged = expected.model_copy(update={"has_more": True, "next_page_token": "page-2"})
    serialized, media_type = ResultSerializer.serialize(paged)
    data_ref = store.put_bytes(
        serialized,
        ArtifactWriteOptions(
            kind="fabric.connector_cache.payload",
            media_type=media_type,
        ),
    )
    evidence_bundle_ref = persist_evidence_bundle(
        store,
        build_evidence_bundle(sources=[data_ref], notes=["two-page adversarial fixture"]),
    )
    snapshot = DataSnapshot(
        data_ref=data_ref,
        evidence_ref=evidence_bundle_ref,
        stats={"datasets_fetched": 1, "source": "orchestrated_ingestion:test"},
        notes=["fabric.data_plane.orchestrator", "datasets=1"],
    )
    snapshot_artifact = store.put_json(
        snapshot,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    mutated = _rebuild_live_evidence(
        evidence,
        evidence_bundle_ref=evidence_bundle_ref,
        data_snapshot_ref=DataSnapshotRef(artifact_id=snapshot_artifact.artifact_id),
        normalized_data_artifact_id=data_ref.artifact_id,
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_result_not_one_page",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, mutated, store)


def test_live_execution_recomputes_one_variable_from_request(tmp_path: Path) -> None:
    resolver, entry, store, evidence, receipt, _ = _live_execution_fixture(tmp_path)
    original_event = resolve_linked_request_event(evidence.raw_evidence_ref)
    request = dict(original_event["request"])
    request["variable_id"] = "government.unrequested_sibling"
    profile = SourceProfileRegistry.get_instance().get("worldbank_wdi")
    assert profile is not None
    authorization = build_live_execution_authorization(
        attempt_id=evidence.authorization.attempt_id,
        connector_id=evidence.authorization.connector_id,
        request_dataset_id=evidence.authorization.request_variables[0],
        request=request,
        schema_contract=entry.schema_projection(),
        source_profile=profile,
        baseline_sha256=evidence.baseline_before_sha256,
        family_receipt=receipt,
        max_response_bytes=evidence.authorization.budget.max_response_bytes,
        max_decompressed_bytes=(evidence.authorization.budget.max_decompressed_bytes),
    )
    journal = AppendOnlyEvidenceJournal(tmp_path / "wrong-variable-journal.jsonl")
    request_ref = journal.append_request(
        attempt_id=authorization.attempt_id,
        request=request,
    )
    transport_ref = journal.append_transport_attempt(
        attempt_id=authorization.attempt_id,
        request_ref=request_ref,
        connector_id="worldbank.wdi",
        url=("https://api.worldbank.org/v2/country/UKR/indicator/GC.BAL.CASH.GD.ZS"),
        params={"format": "json", "page": "1", "per_page": "1000"},
    )
    raw_body = resolve_raw_response_body(evidence.raw_evidence_ref)
    journal.append_heartbeat(
        attempt_id=authorization.attempt_id,
        phase="attempt_started",
        progress_bytes=0,
        elapsed_seconds=0.0,
    )
    journal.append_heartbeat(
        attempt_id=authorization.attempt_id,
        phase="response_headers",
        progress_bytes=0,
        elapsed_seconds=0.1,
    )
    journal.append_heartbeat(
        attempt_id=authorization.attempt_id,
        phase="body_progress",
        progress_bytes=len(raw_body),
        elapsed_seconds=0.2,
    )
    raw_ref = journal.append_raw_evidence(
        attempt_id=authorization.attempt_id,
        request_ref=request_ref,
        transport_ref=transport_ref,
        payload=raw_body,
        status_code=200,
        response_headers={"content-type": "application/json"},
        budget=authorization.budget,
    )
    mutated = _rebuild_live_evidence(
        evidence,
        authorization=authorization,
        request_ref=request_ref,
        raw_evidence_ref=raw_ref,
        transport_trace=resolve_live_transport_trace(raw_ref),
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_request_owner_projection_drift",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, mutated, store)


def test_authority_rejects_catalog_license_and_owner_byte_drift(tmp_path: Path) -> None:
    restricted, entry = _resolver(tmp_path / "restricted", license_id="all-rights-reserved")
    with pytest.raises(AcquisitionAuthorityError, match="license_not_admissible"):
        restricted.resolve(entry.entry_id)

    resolver, entry = _resolver(tmp_path / "l5-drift")
    resolver.l5_path.write_text("{}", encoding="utf-8")
    with pytest.raises(
        AcquisitionAuthorityError,
        match="provision_l5_identity_drift",
    ):
        resolver.resolve(entry.entry_id)


def test_authority_rejects_self_authored_and_invented_exact_edges() -> None:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column) for column in values["schema_columns"]
    )
    values["evidence_refs"] = ("self://invented",)
    with pytest.raises(ValidationError, match="cannot be self-authored"):
        build_authority_entry(**values)

    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column) for column in values["schema_columns"]
    )
    values.update(
        {
            "alignment_method": "exact",
            "alignment_confidence": 0.0,
        }
    )
    with pytest.raises(ValidationError, match="exact authority alignment"):
        build_authority_entry(**values)

    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column) for column in values["schema_columns"]
    )
    values["local_source_path"] = "evidence/should-not-travel.json"
    with pytest.raises(ValidationError, match="cannot carry local authority fields"):
        build_authority_entry(**values)


def test_authority_rejects_landing_identifier_collision_with_epoch_zero(
    tmp_path: Path,
) -> None:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column) for column in values["schema_columns"]
    )
    values["landing_dataset_id"] = "source-worldbank-balance"
    collision = build_authority_entry(**values)
    resolver, entry = _resolver(tmp_path, authority_entry=collision)

    with pytest.raises(
        AcquisitionAuthorityError,
        match="landing_identifier_collides_with_epoch_zero",
    ):
        resolver.resolve(entry.entry_id)
