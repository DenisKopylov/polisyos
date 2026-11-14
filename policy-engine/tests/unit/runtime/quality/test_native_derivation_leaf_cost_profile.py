from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.runtime.quality import acquisition_planner as acquisition_owner
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionCostBasisRecord,
    AcquisitionStrategy,
    NativeDerivationLeafCostProfile,
    NativeDerivationLeafCostProfileScope,
    load_native_derivation_leaf_cost_profile,
    persist_native_derivation_leaf_cost_profile,
    produce_acquisition_cost_basis_record,
    validate_native_derivation_leaf_cost_profile_for_scope,
)


def _put_selected_fact(
    store: FileSystemCAS,
    *,
    kind: str,
    name: str,
) -> artifacts.ArtifactRef:
    spec = canon.CanonSpec(forbid_floats=False, forbid_nan_inf=True)
    return store.put_json(
        {"selected_fact": name},
        artifacts.PutOptions(
            kind=kind,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=f"test.{name}", version="1.0"),
            producer=artifacts.ProducerInfo(component="tests.native_leaf_cost", version="1.0"),
            canon=artifacts.CanonInfo.from_spec(spec),
            inputs=[],
        ),
        canon_spec=spec,
        return_selected_profile=True,
    )


def _profile_scope(
    store: FileSystemCAS,
) -> tuple[NativeDerivationLeafCostProfileScope, artifacts.ArtifactRef]:
    configured_port = _put_selected_fact(
        store,
        kind="runtime.quality.n7_configured_candidate_port_source",
        name="configured_port",
    )
    planner_report = _put_selected_fact(
        store,
        kind="runtime.acquisition_planner_report",
        name="planner_report",
    )
    derivation_bundle = _put_selected_fact(
        store,
        kind="runtime.quality.n7_derivation_bundle",
        name="derivation_bundle",
    )
    obligation_set = _put_selected_fact(
        store,
        kind="runtime.quality.model_input_obligation_set",
        name="obligation_set",
    )
    supplier = _put_selected_fact(
        store,
        kind="external.source_supplier_fact",
        name="supplier",
    )
    quote = _put_selected_fact(
        store,
        kind="external.owner_quote_fact",
        name="quote",
    )
    scope = NativeDerivationLeafCostProfileScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="job-a",
        configured_port_source_ref=configured_port,
        planner_report_ref=planner_report,
        derivation_bundle_ref=derivation_bundle,
        obligation_set_ref=obligation_set,
        source_node_id="source:metric-a",
        requirement_gap_id="gap:metric-a",
        compiled_requirement_ref="compiled:metric-a",
        planner_record_id="record:metric-a",
        strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
        selected_supplier_ref=supplier,
        missing_distribution="metric-a",
    )
    return scope, quote


def _profile(
    scope: NativeDerivationLeafCostProfileScope,
    quote_ref: artifacts.ArtifactRef,
    *,
    now: datetime,
) -> NativeDerivationLeafCostProfile:
    payload = {
        "schema_version": "polisyos.runtime.native_derivation_leaf_cost_profile.v1",
        "authority_purpose": "costing_and_provenance_only",
        "scope": scope.model_dump(mode="json"),
        "quote_evidence_ref": quote_ref.model_dump(mode="json"),
        "effective_at": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "rule_version": "supplier-rate-card:2026-11",
        "collection_mode": "owner quoted registry request",
        "currency": "USD",
        "line_items": [
            {
                "line_item_id": "source_request",
                "quantity": 4.0,
                "rate_name": "supplier_quote",
                "unit_rate": 17.5,
                "amount": 70.0,
            }
        ],
        "quantity_unit_by_line_item": {"source_request": "registry-request"},
        "calendar_days": 3,
        "expert_hours": 1.5,
    }
    return NativeDerivationLeafCostProfile.model_validate(
        {
            **payload,
            "content_hash": acquisition_owner._stable_content_hash(payload),
        }
    )


def test_native_leaf_cost_profile_persists_binds_scope_and_produces_record(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    scope, quote_ref = _profile_scope(store)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    profile = _profile(scope, quote_ref, now=now)

    profile_ref = persist_native_derivation_leaf_cost_profile(store, profile)
    loaded = load_native_derivation_leaf_cost_profile(store, profile_ref)
    assert loaded == profile
    assert len(store.get_manifest(profile_ref).inputs) == 6
    assert (
        validate_native_derivation_leaf_cost_profile_for_scope(
            loaded, expected_scope=scope, now=now
        )
        == profile
    )

    record = produce_acquisition_cost_basis_record(
        missing_distribution="metric-a",
        strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
        owner_declared_profile_ref=profile_ref,
        store=store,
        expected_scope=scope,
        now=now,
    )
    assert isinstance(record, AcquisitionCostBasisRecord)
    assert record.schema_version == "AcquisitionCostBasisRecord@1.1"
    assert record.owner_declared_profile_ref == profile_ref
    assert record.line_items == profile.line_items
    assert record.total_amount == 70.0
    assert record.calendar_days == 3
    assert record.expert_hours == 1.5


def test_native_leaf_cost_profile_recomputes_quantity_and_profile_hash(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    scope, quote_ref = _profile_scope(store)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    profile = _profile(scope, quote_ref, now=now)
    changed = profile.model_dump(mode="json")
    changed["line_items"][0]["quantity"] = 5.0

    with pytest.raises(ValidationError, match="cost_line_item_amount_mismatch"):
        NativeDerivationLeafCostProfile.model_validate(changed)

    changed["line_items"][0]["amount"] = 87.5
    with pytest.raises(
        ValidationError, match="native_derivation_leaf_cost_profile_content_hash_mismatch"
    ):
        NativeDerivationLeafCostProfile.model_validate(changed)


def test_native_leaf_cost_profile_rejects_foreign_scope_supplier_strategy_and_expiry(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    scope, quote_ref = _profile_scope(store)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    profile = _profile(scope, quote_ref, now=now)
    profile_ref = persist_native_derivation_leaf_cost_profile(store, profile)

    foreign_tenant = scope.model_copy(update={"tenant_id": "tenant-b"})
    with pytest.raises(ValueError, match="native_derivation_leaf_cost_profile_scope_mismatch"):
        validate_native_derivation_leaf_cost_profile_for_scope(
            profile, expected_scope=foreign_tenant, now=now
        )

    foreign_supplier_ref = _put_selected_fact(
        store,
        kind="external.source_supplier_fact",
        name="foreign_supplier",
    )
    foreign_supplier = scope.model_copy(update={"selected_supplier_ref": foreign_supplier_ref})
    with pytest.raises(ValueError, match="native_derivation_leaf_cost_profile_scope_mismatch"):
        produce_acquisition_cost_basis_record(
            missing_distribution="metric-a",
            strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
            owner_declared_profile_ref=profile_ref,
            store=store,
            expected_scope=foreign_supplier,
            now=now,
        )

    with pytest.raises(
        ValueError, match="native_derivation_leaf_cost_profile_cost_selection_mismatch"
    ):
        produce_acquisition_cost_basis_record(
            missing_distribution="metric-a",
            strategy=AcquisitionStrategy.AGENCY_REQUEST,
            owner_declared_profile_ref=profile_ref,
            store=store,
            expected_scope=scope,
            now=now,
        )

    with pytest.raises(ValueError, match="native_derivation_leaf_cost_profile_not_current"):
        validate_native_derivation_leaf_cost_profile_for_scope(
            profile,
            expected_scope=scope,
            now=datetime(2026, 11, 14, 15, 0, tzinfo=UTC),
        )


def test_native_leaf_cost_profile_rejects_missing_profile_and_removed_quote_bytes(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    scope, quote_ref = _profile_scope(store)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    profile = _profile(scope, quote_ref, now=now)
    profile_ref = persist_native_derivation_leaf_cost_profile(store, profile)

    missing_profile_ref = artifacts.ArtifactRef.model_validate(
        {
            **profile_ref.model_dump(mode="json"),
            "artifact_id": f"sha256:{'0' * 64}",
        }
    )
    with pytest.raises(FileNotFoundError):
        load_native_derivation_leaf_cost_profile(store, missing_profile_ref)

    store._paths(quote_ref.artifact_id)[0].unlink()
    with pytest.raises(ValueError, match="native_derivation_leaf_cost_profile_input_unverified"):
        load_native_derivation_leaf_cost_profile(store, profile_ref)


def test_canonical_cost_producer_keeps_legacy_record_profile_free() -> None:
    record = produce_acquisition_cost_basis_record(
        missing_distribution="administrative_tax_receipts",
        strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
    )

    assert isinstance(record, AcquisitionCostBasisRecord)
    assert record.schema_version == "AcquisitionCostBasisRecord@1.0"
    assert record.owner_declared_profile_ref is None
    assert "owner_declared_profile_ref" not in record.model_dump(mode="json")
