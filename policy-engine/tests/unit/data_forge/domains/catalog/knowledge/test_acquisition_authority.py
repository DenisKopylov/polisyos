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
from polisyos.fabric.connectors.cache.store import ResultSerializer
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    build_live_execution_authorization,
    resolve_linked_request_event,
    resolve_raw_response_body,
)
from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle
from polisyos.ir.connectors import (
    DataVersion,
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
    baseline_owner_ref: str,
) -> Path:
    provision = build_acquisition_authority_provision(
        baseline_owner_ref=baseline_owner_ref,
        baseline_content_sha256=_sha(baseline),
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
        evidence_refs=(
            "duckdb://production_data/dataset_catalog.duckdb#/gov_balance",
        ),
        schema_contract_ref="fabric://worldbank.wdi.generic@2.0.0",
        schema_columns=(
            AuthoritySchemaColumn(
                name="country_code", logical_types=("string",), nullable=False
            ),
            AuthoritySchemaColumn(
                name="country_name", logical_types=("string",), nullable=False
            ),
            AuthoritySchemaColumn(
                name="decimal", logical_types=("integer",), nullable=False
            ),
            AuthoritySchemaColumn(
                name="indicator_id", logical_types=("string",), nullable=False
            ),
            AuthoritySchemaColumn(
                name="indicator_name", logical_types=("string",), nullable=False
            ),
            AuthoritySchemaColumn(
                name="unit", logical_types=("string",), nullable=False
            ),
            AuthoritySchemaColumn(
                name="value", logical_types=("null", "number"), nullable=True
            ),
            AuthoritySchemaColumn(
                name="year", logical_types=("integer",), nullable=False
            ),
        ),
        l5_family_id="macro_state",
        title="Acquired government balance",
        description="Owner-validated World Bank government balance observations.",
        country_codes=("UA",),
        temporal_start="2020",
        temporal_end="2024",
    )


def _resolver(
    repo_root: Path,
    *,
    license_id: str = "CC-BY-4.0",
    authority_entry: AcquisitionAuthorityEntry | None = None,
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
        baseline_owner_ref="repo://catalog/catalog.duckdb",
    )
    return (
        CanonicalAcquisitionAuthority.from_provision(
            repo_root=repo_root,
            baseline_path=baseline,
        ),
        entry,
    )


def _live_execution_fixture(tmp_path: Path):
    """Build one fully content-bound, network-free WDI execution fixture."""

    from polisyos.data_forge.domains.catalog.knowledge import acquisition_authority

    resolver, entry = _resolver(tmp_path / "repo")
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
        "filters": {"country": ["UKR"]},
        "date_start": "2023-01-01",
        "date_end": "2024-12-31",
        "page_size": 1000,
        "schema_contract": entry.schema_projection(),
    }
    attempt_id = "n13b-worldbank-government-balance-001"
    family_receipt = {
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
    raw_ref = journal.append_raw_evidence(
        attempt_id=attempt_id,
        request_ref=request_ref,
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
        raw_artifact_id=str(raw_artifact.artifact_id),
        evidence_bundle_ref=evidence_bundle_ref,
        data_snapshot_ref=snapshot_ref,
        normalized_data_artifact_id=str(data_ref.artifact_id),
        call_count=1,
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
        "repo://catalog/catalog.duckdb#ds_datasets/"
        "source-worldbank-balance/access_license"
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
        baseline_owner_ref=(
            "repo://production_data/snapshot/dataset_catalog.duckdb"
        ),
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
    assert revalidate_admission_passport(
        passport,
        artifact_store=store,
        authority=resolver,
    ) == passport


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
        assert con.execute(
            "SELECT value FROM ds_observations ORDER BY year"
        ).fetchall() == [(-18.2,), (-17.1,)]
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
        "raw_artifact_id": evidence.raw_artifact_id,
        "evidence_bundle_ref": evidence.evidence_bundle_ref,
        "data_snapshot_ref": evidence.data_snapshot_ref,
        "normalized_data_artifact_id": evidence.normalized_data_artifact_id,
        "call_count": evidence.call_count,
        "variable_count": evidence.variable_count,
        "page_count": evidence.page_count,
        "baseline_before_sha256": evidence.baseline_before_sha256,
        "baseline_after_sha256": evidence.baseline_after_sha256,
        "raw_body_sha256": evidence.raw_body_sha256,
        "normalized_result_content_sha256": (
            evidence.normalized_result_content_sha256
        ),
    }
    values.update(updates)
    return build_live_source_execution_evidence(**values)  # type: ignore[arg-type]


def test_live_execution_rejects_mutated_family_receipt(tmp_path: Path) -> None:
    resolver, entry, store, evidence, receipt, _ = _live_execution_fixture(tmp_path)
    mutated_receipt = {**receipt, "safe_dry_run_passed": False}
    mutated = evidence.model_copy(update={"family_receipt": mutated_receipt})

    with pytest.raises(AcquisitionAuthorityError, match="live_source_execution_invalid"):
        resolver.resolve_live_source_execution(entry.entry_id, mutated, store)


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
    forged = passport.model_copy(
        update={"source_watermark": "sha256:" + "0" * 64}
    )

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
        data_snapshot_ref=DataSnapshotRef(
            artifact_id=evidence.evidence_bundle_ref.artifact_id
        ),
    )

    with pytest.raises(
        AcquisitionAuthorityError,
        match="live_artifact_ref_manifest_drift",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, mutated, store)


def test_live_execution_recomputes_one_call_from_snapshot(tmp_path: Path) -> None:
    resolver, entry, store, evidence, _, _ = _live_execution_fixture(tmp_path)
    snapshot = DataSnapshot.model_validate(
        from_canonical_bytes(store.get_bytes(evidence.data_snapshot_ref.artifact_id))
    )
    expanded = snapshot.model_copy(
        update={"stats": {**snapshot.stats, "datasets_fetched": 2}}
    )
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
        match="live_snapshot_not_one_call",
    ):
        resolver.resolve_live_source_execution(entry.entry_id, mutated, store)


def test_live_execution_recomputes_one_page_from_fetch_result(tmp_path: Path) -> None:
    resolver, entry, store, evidence, _, expected = _live_execution_fixture(tmp_path)
    paged = expected.model_copy(
        update={"has_more": True, "next_page_token": "page-2"}
    )
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
        data_snapshot_ref=DataSnapshotRef(
            artifact_id=snapshot_artifact.artifact_id
        ),
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
        max_decompressed_bytes=(
            evidence.authorization.budget.max_decompressed_bytes
        ),
    )
    journal = AppendOnlyEvidenceJournal(tmp_path / "wrong-variable-journal.jsonl")
    request_ref = journal.append_request(
        attempt_id=authorization.attempt_id,
        request=request,
    )
    raw_ref = journal.append_raw_evidence(
        attempt_id=authorization.attempt_id,
        request_ref=request_ref,
        payload=resolve_raw_response_body(evidence.raw_evidence_ref),
        status_code=200,
        response_headers={"content-type": "application/json"},
        budget=authorization.budget,
    )
    mutated = _rebuild_live_evidence(
        evidence,
        authorization=authorization,
        request_ref=request_ref,
        raw_evidence_ref=raw_ref,
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
        match="l5_measurement_registry_content_drift",
    ):
        resolver.resolve(entry.entry_id)


def test_authority_rejects_self_authored_and_invented_exact_edges() -> None:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values["evidence_refs"] = ("self://invented",)
    with pytest.raises(ValidationError, match="cannot be self-authored"):
        build_authority_entry(**values)

    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
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
        AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values["local_source_path"] = "evidence/should-not-travel.json"
    with pytest.raises(ValidationError, match="cannot carry local authority fields"):
        build_authority_entry(**values)


def test_authority_rejects_landing_identifier_collision_with_epoch_zero(
    tmp_path: Path,
) -> None:
    values = _entry().model_dump(mode="python", exclude={"entry_id"})
    values["schema_columns"] = tuple(
        AuthoritySchemaColumn.model_validate(column)
        for column in values["schema_columns"]
    )
    values["landing_dataset_id"] = "source-worldbank-balance"
    collision = build_authority_entry(**values)
    resolver, entry = _resolver(tmp_path, authority_entry=collision)

    with pytest.raises(
        AcquisitionAuthorityError,
        match="landing_identifier_collides_with_epoch_zero",
    ):
        resolver.resolve(entry.entry_id)
