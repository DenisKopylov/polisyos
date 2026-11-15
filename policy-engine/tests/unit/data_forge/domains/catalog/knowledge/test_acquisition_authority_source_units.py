"""Provision-adopted physical units flow through real Catalog source owners."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.canon import CanonSpec
from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    DEFAULT_ACQUISITION_AUTHORITY_PROVISION,
    DEFAULT_ACQUISITION_AUTHORITY_REGISTRY,
    AcquisitionAuthorityError,
    AcquisitionSupplierDeclaration,
    CanonicalAcquisitionAuthority,
    build_acquisition_authority_provision,
    build_authority_entry,
    build_authority_registry,
    load_acquisition_supplier_declaration,
    persist_acquisition_supplier_declaration,
)
from polisyos.fabric.connectors.contracts import (
    SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE,
    SourceContract,
    SourceContractSemantics,
    SourceMetricDefinition,
    build_contract_registry,
    create_source_metric_unit_declaration,
    load_source_metric_unit_declaration,
)
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.sources._contracts import WDI_GENERIC_CONTRACT
from polisyos.fabric.data_plane.evidence_journal import (
    AppendOnlyEvidenceJournal,
    build_live_execution_authorization,
    resolve_linked_request_event,
    resolve_live_transport_trace,
    resolve_raw_response_body,
)
from tests._helpers.acquisition_production import _sha
from tests._helpers.lane01_wdi_profiles import GDP_PROFILE, build_fixture_wdi_authority
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority import (
    _live_execution_fixture,
    _rebuild_live_evidence,
)


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value.model_dump(mode="json"), sort_keys=True), encoding="utf-8")


def _adopt(authority, entry, store, *, unit: str):
    contracts = build_contract_registry((WDI_GENERIC_CONTRACT,))
    source = SourceContract.from_connector_schema_contract(
        WDI_GENERIC_CONTRACT, profile_id="worldbank_wdi"
    )
    source = source.model_copy(
        update={
            "semantics": SourceContractSemantics(
                domain=source.semantics.domain,
                metric_definitions=(
                    SourceMetricDefinition(
                        metric_id=entry.catalog_raw_variable, unit=unit, canonical_field="value"
                    ),
                ),
            )
        }
    )
    selected = create_source_metric_unit_declaration(
        store,
        source_contract=source,
        contract_registry=contracts,
        connector_contract_id=WDI_GENERIC_CONTRACT.contract_id,
        connector_contract_version=str(WDI_GENERIC_CONTRACT.schema_version),
        catalog_dataset_id=entry.source_catalog_dataset_id,
        catalog_distribution_id=entry.source_catalog_distribution_id,
        catalog_metric_id=entry.upstream_metric_id,
        request_dataset_id=entry.catalog_raw_variable,
        source_metric_id=entry.catalog_raw_variable,
        raw_field="value",
        normalized_field="value",
        metric_selector_field="indicator_id",
        reported_unit_field="unit",
    )
    adopted_entry = build_authority_entry(
        **{
            **entry.model_dump(mode="python", exclude={"entry_id"}),
            "source_unit_declaration_ref": selected,
        }
    )
    registry = build_authority_registry(
        baseline_content_sha256=_sha(authority.baseline_path),
        l5_measurement_registry_sha256=_sha(authority.l5_path),
        entries=(adopted_entry,),
    )
    _write(authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_REGISTRY, registry)
    values = authority.provision.identity_payload()
    values.pop("authority_purpose")
    values["live_harness_receipts"] = tuple(
        {**item.model_dump(mode="python"), "entry_id": adopted_entry.entry_id}
        for item in authority.provision.live_harness_receipts
    )
    provision = build_acquisition_authority_provision(
        **values, source_unit_declaration_refs=(selected,), source_unit_reader=store
    )
    _write(authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION, provision)
    current = CanonicalAcquisitionAuthority.from_provision(
        repo_root=authority.repo_root,
        baseline_path=authority.baseline_path,
        source_unit_reader=store,
        source_unit_contract_registry=contracts,
    )
    return current, adopted_entry, selected, contracts


def _case(tmp_path: Path):
    profile = replace(
        GDP_PROFILE,
        construct="fixture.metric_a",
        indicator_id="TEST.SERIES.A",
        source_title="Controlled series alpha",
        source_description="Explicit fixture declaration; no empirical attribution.",
        target_slot="candidate.metric_a",
        raw_unit="count",
        canonical_unit="count",
        transform_ref="fabric://units/count-identity/v1",
        catalog_metric_id="fixture.metric_a",
    )
    authority, entry = build_fixture_wdi_authority(tmp_path / "repo", profile)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    return authority, entry, store


def test_declared_unit_reaches_catalog_supplier_and_fresh_historical_reader(tmp_path: Path) -> None:
    old, entry, store = _case(tmp_path)
    # A caller's count label or an unrelated health-looking title cannot admit
    # the source. There is no production unit declaration in this fixture.
    with pytest.raises(AcquisitionAuthorityError, match="catalog_unit_unresolved"):
        old.resolve(entry.entry_id)
    authority, adopted, unit_ref, _ = _adopt(old, entry, store, unit="count")
    resolved = authority.resolve(adopted.entry_id)
    assert resolved.field_binding.raw_unit == "count"
    audit = resolved.upstream_catalog_projection["source_unit_declaration"]
    assert audit["ref"] == unit_ref.model_dump(mode="json")
    assert audit["source_contract_hash_profile"] == SOURCE_CONTRACT_FIELD_SET_HASH_PROFILE
    assert audit["hash_replay_limitations"] == []
    assert audit["unit_truth"] == "declared"
    assert audit["semantic_authority"] == audit["source_currentness"] == "not_established"
    assert adopted.schema_projection()["source_unit_declaration_ref"] == unit_ref.model_dump(
        mode="json"
    )
    supplier_ref = persist_acquisition_supplier_declaration(
        store, authority, entry_id=adopted.entry_id
    )
    reader = artifacts.FileSystemCAS.open_existing_read_only(tmp_path / "cas")
    historical = load_acquisition_supplier_declaration(reader, supplier_ref)
    assert historical.entry.source_unit_declaration_ref == unit_ref
    assert historical.semantic_refs_status == "not_established"
    assert historical.acquisition_permission == historical.semantic_authority == "not_established"
    assert historical.source_unit_provision_ref is not None
    receipt_bytes = reader.get_bytes(historical.source_unit_provision_ref)
    assert "sha256:" + hashlib.sha256(receipt_bytes).hexdigest() == (
        historical.authority_provision_content_sha256
    )
    # Current adoption changes invalidate the existing current owner. Exact
    # original provision bytes remain historical facts, never a new permission.
    path = authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION
    values = old.provision.identity_payload()
    values.pop("authority_purpose")
    _write(path, build_acquisition_authority_provision(**values))
    with pytest.raises(AcquisitionAuthorityError, match="acquisition_authority_provision_drift"):
        authority.resolve(adopted.entry_id)
    fresh = CanonicalAcquisitionAuthority.from_provision(
        repo_root=authority.repo_root,
        baseline_path=authority.baseline_path,
        source_unit_reader=reader,
        source_unit_contract_registry=build_contract_registry((WDI_GENERIC_CONTRACT,)),
    )
    with pytest.raises(AcquisitionAuthorityError, match="source_unit_declaration_not_adopted"):
        fresh.resolve(adopted.entry_id)
    assert load_acquisition_supplier_declaration(reader, supplier_ref) == historical


def test_present_unit_ref_needs_original_reader_and_current_actual_contract(tmp_path: Path) -> None:
    old, entry, store = _case(tmp_path)
    authority, adopted, _, _ = _adopt(old, entry, store, unit="count")
    missing_owner = CanonicalAcquisitionAuthority.from_provision(
        repo_root=authority.repo_root, baseline_path=authority.baseline_path
    )
    with pytest.raises(
        AcquisitionAuthorityError,
        match="source_unit_declaration_owner_unavailable",
    ):
        missing_owner.resolve(adopted.entry_id)
    changed_schema = WDI_GENERIC_CONTRACT.schema.model_copy(update={"required_completeness": 0.9})
    changed = WDI_GENERIC_CONTRACT.model_copy(update={"connector_schema": changed_schema})
    drift = CanonicalAcquisitionAuthority.from_provision(
        repo_root=authority.repo_root,
        baseline_path=authority.baseline_path,
        source_unit_reader=store,
        source_unit_contract_registry=build_contract_registry((changed,)),
    )
    with pytest.raises(AcquisitionAuthorityError, match="source_unit_current_schema_drift"):
        drift.resolve(adopted.entry_id)


def test_missing_selected_declaration_bytes_never_fall_back_to_catalog_title(
    tmp_path: Path,
) -> None:
    old, entry = build_fixture_wdi_authority(tmp_path / "repo", GDP_PROFILE)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    authority, adopted, ref, _ = _adopt(old, entry, store, unit="usd")
    authority.resolve(adopted.entry_id)
    # The selected view stays intact while only its owned payload is removed.
    manifest = store.get_manifest(ref)
    payload = store.get_bytes(ref)
    source, _ = store._paths(manifest.artifact_id)
    source.unlink()
    try:
        with pytest.raises((AcquisitionAuthorityError, FileNotFoundError)):
            authority.resolve(adopted.entry_id)
        with pytest.raises((ValueError, FileNotFoundError)):
            load_source_metric_unit_declaration(store, ref)
    finally:
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(payload)
    assert authority.resolve(adopted.entry_id).field_binding.raw_unit == "usd"


def _rebind_typed_request(tmp_path, authority, entry, proof, family_receipt):
    """Use the actual journal/authorization producers for the new owned schema."""
    request = dict(resolve_linked_request_event(proof.raw_evidence_ref)["request"])
    resolved = authority.resolve(entry.entry_id)
    request.update(
        authority_entry_id=entry.entry_id,
        authority_registry_content_sha256=resolved.registry_content_sha256,
        schema_contract=entry.schema_projection(),
    )
    profile = SourceProfileRegistry.get_instance().get(resolved.registration.source_profile_id)
    assert profile is not None
    authorization = build_live_execution_authorization(
        attempt_id=proof.authorization.attempt_id,
        connector_id=resolved.registration.connector_id,
        request_dataset_id=resolved.registration.request_dataset_id,
        request=request,
        schema_contract=entry.schema_projection(),
        source_profile=profile,
        baseline_sha256=proof.baseline_before_sha256,
        family_receipt=family_receipt,
        max_response_bytes=proof.authorization.budget.max_response_bytes,
        max_decompressed_bytes=proof.authorization.budget.max_decompressed_bytes,
    )
    journal = AppendOnlyEvidenceJournal(tmp_path / "typed-request.jsonl")
    request_ref = journal.append_request(attempt_id=authorization.attempt_id, request=request)
    transport_ref = journal.append_transport_attempt(
        attempt_id=authorization.attempt_id,
        request_ref=request_ref,
        connector_id=authorization.connector_id,
        url="https://api.worldbank.org/v2/country/UKR/indicator/GC.BAL.CASH.GD.ZS",
        params={"date": "2023:2024", "format": "json", "page": "1", "per_page": "1000"},
    )
    raw_body = resolve_raw_response_body(proof.raw_evidence_ref)
    for phase, progress, elapsed in (
        ("attempt_started", 0, 0.0),
        ("response_headers", 0, 0.1),
        ("body_progress", len(raw_body), 0.2),
    ):
        journal.append_heartbeat(
            attempt_id=authorization.attempt_id,
            phase=phase,
            progress_bytes=progress,
            elapsed_seconds=elapsed,
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
        proof,
        authorization=authorization,
        request_ref=request_ref,
        raw_evidence_ref=raw_ref,
        transport_trace=resolve_live_transport_trace(raw_ref),
    )


def test_actual_result_consumer_checks_row_unit_and_original_raw_indicator(tmp_path: Path) -> None:
    old, entry, store, proof, family_receipt, result = _live_execution_fixture(tmp_path)
    authority, adopted, _, _ = _adopt(old, entry, store, unit="percent_gdp")
    resolved = authority.resolve(adopted.entry_id)
    typed_proof = _rebind_typed_request(tmp_path, authority, adopted, proof, family_receipt)
    replayed = authority.resolve_live_source_execution(adopted.entry_id, typed_proof, store)
    assert replayed.data.equals(result.data)
    assert resolved.registration.source_profile_id == "worldbank_wdi"
    # The raw response retains a different source-declared spelling (% of GDP).
    # A different declaration cannot reinterpret those actual bytes as count.
    declaration = load_source_metric_unit_declaration(store, adopted.source_unit_declaration_ref)
    assert declaration.reported_unit_field == "unit"
    with pytest.raises(ValueError, match="source_unit_raw_metric_missing"):
        declaration.validate_raw_metric_rows([{"value": -17.1, "unit": "% of GDP"}])
    with pytest.raises(ValueError, match="source_unit_row_metric_mismatch"):
        declaration.reported_units([{"indicator_id": "OTHER", "value": -17.1, "unit": "% of GDP"}])


def test_absent_extension_preserves_legacy_entry_and_provision_wire(tmp_path: Path) -> None:
    authority, entry = build_fixture_wdi_authority(tmp_path / "repo", GDP_PROFILE)
    assert "source_unit_declaration_ref" not in entry.model_dump(mode="json")
    assert "source_unit_declaration_refs" not in authority.provision.model_dump(mode="json")
    assert set(entry.schema_projection()) == {"schema_contract_ref", "columns"}
    assert authority.resolve(entry.entry_id).field_binding.raw_unit == "usd"


def test_explicit_reported_unit_refuses_conflicting_declared_coordinate(tmp_path: Path) -> None:
    old, entry, store, proof, family_receipt, _ = _live_execution_fixture(tmp_path)
    conflict = build_authority_entry(
        **{
            **entry.model_dump(mode="python", exclude={"entry_id"}),
            "raw_unit": "count",
            "canonical_unit": "count",
        }
    )
    authority, adopted, _, _ = _adopt(old, conflict, store, unit="count")
    typed_proof = _rebind_typed_request(tmp_path, authority, adopted, proof, family_receipt)
    with pytest.raises(AcquisitionAuthorityError, match="source_unit_reported_unit_mismatch"):
        authority.resolve_live_source_execution(adopted.entry_id, typed_proof, store)


@pytest.mark.parametrize("mutation", ["profile", "request"])
def test_historical_supplier_rejects_another_adopted_profile_or_request(
    tmp_path: Path, mutation: str
) -> None:
    old, entry, store = _case(tmp_path)
    authority, adopted, original_ref, contracts = _adopt(old, entry, store, unit="count")
    original = load_source_metric_unit_declaration(store, original_ref)
    source = original.source_contract
    request_id = original.request_dataset_id
    if mutation == "profile":
        source = source.model_copy(
            update={"source": source.source.model_copy(update={"profile_id": "other_profile"})}
        )
    else:
        request_id = "TEST.SERIES.B"
        source = source.model_copy(
            update={
                "semantics": SourceContractSemantics(
                    domain=source.semantics.domain,
                    metric_definitions=(
                        SourceMetricDefinition(
                            metric_id=request_id, unit="count", canonical_field="value"
                        ),
                    ),
                )
            }
        )
    other_ref = create_source_metric_unit_declaration(
        store,
        source_contract=source,
        contract_registry=contracts,
        connector_contract_id=WDI_GENERIC_CONTRACT.contract_id,
        connector_contract_version=str(WDI_GENERIC_CONTRACT.schema_version),
        catalog_dataset_id=adopted.source_catalog_dataset_id,
        catalog_distribution_id=adopted.source_catalog_distribution_id,
        catalog_metric_id=adopted.upstream_metric_id,
        request_dataset_id=request_id,
        source_metric_id=request_id,
        raw_field="value",
        normalized_field="value",
        metric_selector_field="indicator_id",
        reported_unit_field="unit",
    )
    values = authority.provision.identity_payload()
    values.pop("authority_purpose")
    values["source_unit_declaration_refs"] = (original_ref, other_ref)
    provision = build_acquisition_authority_provision(**values, source_unit_reader=store)
    _write(authority.repo_root / DEFAULT_ACQUISITION_AUTHORITY_PROVISION, provision)
    current = CanonicalAcquisitionAuthority.from_provision(
        repo_root=authority.repo_root,
        baseline_path=authority.baseline_path,
        source_unit_reader=store,
        source_unit_contract_registry=contracts,
    )
    supplier_ref = persist_acquisition_supplier_declaration(
        store, current, entry_id=adopted.entry_id
    )
    supplier = load_acquisition_supplier_declaration(store, supplier_ref)
    graft_entry = build_authority_entry(
        **{
            **adopted.model_dump(mode="python", exclude={"entry_id"}),
            "source_unit_declaration_ref": other_ref,
        }
    )
    graft = AcquisitionSupplierDeclaration.model_validate(
        {**supplier.model_dump(mode="python"), "entry": graft_entry}
    )
    assert graft.source_unit_profile_id == "worldbank_wdi"
    assert graft.source_unit_request_dataset_id == entry.catalog_raw_variable
    forged_ref = store.put_json(
        graft,
        artifacts.PutOptions(
            kind=graft.ARTIFACT_KIND,
            media_type=graft.ARTIFACT_MEDIA_TYPE,
            schema=artifacts.SchemaInfo(
                name=graft.ARTIFACT_SCHEMA_NAME, version=graft.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[
                artifacts.input_ref_from_artifact_ref(other_ref, role="source_unit_declaration"),
                artifacts.input_ref_from_artifact_ref(
                    graft.source_unit_provision_ref, role="source_unit_provision"
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(AcquisitionAuthorityError, match="source_unit_declaration_scope_mismatch"):
        load_acquisition_supplier_declaration(
            artifacts.FileSystemCAS.open_existing_read_only(tmp_path / "cas"), forged_ref
        )
    assert load_acquisition_supplier_declaration(store, supplier_ref) == supplier
