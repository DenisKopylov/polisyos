"""Candidate-source transport never borrows observed DataSnapshot authority."""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import (
    DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
    CandidateAcquisitionSourceDataSnapshotLineage,
    DataSnapshot,
    DataSnapshotOwnerBound,
    data_snapshot_owner_input_requirements,
)
from polisyos.runtime.quality.data_snapshot_lineage import (
    ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
    CANDIDATE_SOURCE_LIMITATIONS,
    DataSnapshotLineageError,
    DataSnapshotSourceRowNotEstablishedError,
    validate_data_snapshot_owner_lineage,
)
from tests._helpers.world_model_record import _data_snapshot_ref


def _candidate_transport(
    store: FileSystemCAS,
    *,
    source_kind: str = "runtime.quality.candidate_acquisition_source",
    omit_parent_source: bool = False,
    omit_payload_source: bool = False,
) -> tuple[ArtifactRef, DataSnapshot]:
    """Write real transport edges; this alone does not issue source evidence."""
    base_ref = _data_snapshot_ref(store)
    source_ref = store.put_json(
        {"fixture": "not-an-issued-candidate-source"},
        PutOptions(kind=source_kind, media_type="application/json"),
        return_selected_profile=True,
    )
    source_inputs = [input_ref_from_artifact_ref(base_ref, role="input.base_data_snapshot")]
    if not omit_payload_source:
        source_inputs.append(
            input_ref_from_artifact_ref(source_ref, role="evidence.candidate_acquisition_source")
        )
    payload_ref = store.put_json(
        {
            "_policyos_candidate_acquisition": {
                "base_data_snapshot_ref": base_ref.model_dump(mode="json"),
                "candidate_source_ref": source_ref.model_dump(mode="json"),
            }
        },
        PutOptions(
            kind="fabric.production_data_state_payload",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.quality.CandidateAcquisitionDataStatePayload",
                version="policyos.runtime.candidate_acquisition_data_state.v1",
            ),
            inputs=source_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    snapshot = DataSnapshotOwnerBound(
        data_ref=payload_ref,
        source_lineage=CandidateAcquisitionSourceDataSnapshotLineage(
            base_data_snapshot_ref=base_ref,
            candidate_source_ref=source_ref,
        ),
    )
    inputs = [
        input_ref_from_artifact_ref(ref, role=role)
        for ref, role in data_snapshot_owner_input_requirements(snapshot)
        if not (omit_parent_source and role == "evidence.candidate_acquisition_source")
    ]
    ref = store.put_json(
        snapshot,
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DATA_SNAPSHOT_LINEAGE_SCHEMA_VERSION,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ref, snapshot


@pytest.mark.parametrize(
    ("omission", "reason"),
    [
        ("parent", "data_snapshot_owner_parent_inputs_mismatch"),
        ("payload", "data_snapshot_owner_source_edges_mismatch"),
    ],
)
def test_candidate_source_edges_are_required_before_owner_replay(
    tmp_path: Path, omission: str, reason: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref, _snapshot = _candidate_transport(
        store,
        omit_parent_source=omission == "parent",
        omit_payload_source=omission == "payload",
    )
    fresh = FileSystemCAS(store.root)
    snapshot = DataSnapshot.model_validate(load_core_json_artifact(fresh, ref))
    with pytest.raises(DataSnapshotLineageError, match=reason):
        validate_data_snapshot_owner_lineage(fresh, ref, snapshot, candidate_only=True)


@pytest.mark.parametrize(
    "source_kind",
    ["epoch.activated_overlay_admission_receipt", "epoch.acquisition_passport_snapshot"],
)
def test_observed_epoch_artifacts_cannot_be_candidate_source_refs(
    tmp_path: Path, source_kind: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref, snapshot = _candidate_transport(store, source_kind=source_kind)
    with pytest.raises(
        DataSnapshotLineageError, match="candidate_acquisition_source_payload_manifest"
    ):
        validate_data_snapshot_owner_lineage(store, ref, snapshot, candidate_only=True)


def test_candidate_source_cannot_downgrade_to_generic_legacy_snapshot(tmp_path: Path) -> None:
    """Stripping the candidate schema/edges cannot hide its actual payload marker."""
    store = FileSystemCAS(tmp_path / "cas")
    payload_ref = store.put_json(
        {"_policyos_candidate_acquisition": {"status": "candidate_only"}},
        PutOptions(
            kind="fabric.production_data_state_payload",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.quality.DataStatePayload",
                version="policyos.runtime.data_state_substrate.v1",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    snapshot = DataSnapshot(data_ref=payload_ref)
    ref = store.put_json(
        snapshot,
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(payload_ref, role="data_ref")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(
        DataSnapshotLineageError, match="candidate_acquisition_source_lineage_missing"
    ):
        validate_data_snapshot_owner_lineage(store, ref, snapshot, candidate_only=True)


def test_ordinary_legacy_snapshot_does_not_acquire_candidate_limitations(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = _data_snapshot_ref(store)
    fresh = FileSystemCAS(store.root)
    snapshot = DataSnapshot.model_validate(load_core_json_artifact(fresh, ref))
    verdict = validate_data_snapshot_owner_lineage(fresh, ref, snapshot)
    assert verdict.acquisition_source_row_status == "not_applicable"
    assert verdict.candidate_source_limitations == ()
    assert verdict.required_admissibility_blockers == ()


def _retained_options(manifest: Any, **updates: Any) -> PutOptions:
    """Retain selected metadata while an adversary recomputes ordinary CAS hashes."""
    values = {
        field.name: getattr(manifest, "artifact_schema" if field.name == "schema" else field.name)
        for field in fields(PutOptions)
    }
    return PutOptions(**{**values, **updates})


def _legacy_snapshot(
    store: FileSystemCAS, payload_ref: ArtifactRef
) -> tuple[ArtifactRef, DataSnapshot]:
    snapshot = DataSnapshot(data_ref=payload_ref)
    ref = store.put_json(
        snapshot,
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=DataSnapshot.ARTIFACT_SCHEMA_NAME, version="0.2.0"),
            inputs=[input_ref_from_artifact_ref(payload_ref, role="data_ref")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ref, snapshot


def _real_sql_snapshot(store: FileSystemCAS, tmp_path: Path) -> tuple[ArtifactRef, DataSnapshot]:
    """Use the actual SQLite connector and Fabric producer before the rewrap control."""
    import sqlite3

    from polisyos.core.contracts.fabric import DataViewRequestRef
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
    from polisyos.ir.model_layer.queries import DataViewRequest
    from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort

    db_path = tmp_path / "source.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE policy_inputs (value REAL NOT NULL)")
        connection.execute("INSERT INTO policy_inputs VALUES (4.0)")
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(url=f"sqlite:///{db_path}", headers={"X-SQL-Table": "policy_inputs"}),
    )
    request_ref = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="candidate-wrap-control",
            view_type="table",
            metrics=["policy_inputs"],
        ),
        PutOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
        return_selected_profile=True,
    )
    try:
        ref = DefaultFabricPort(connector_registry=registry).snapshot(
            store, DataViewRequestRef.model_validate(request_ref.model_dump(mode="json"))
        )
    finally:
        registry.shutdown()
    snapshot = DataSnapshot.model_validate(load_core_json_artifact(store, ref))
    assert (
        validate_data_snapshot_owner_lineage(store, ref, snapshot).required_admissibility_blockers
        == ()
    )
    return ref, snapshot


@pytest.mark.parametrize("limit", ["max_bytes", "max_elements", "max_depth", "max_manifest_bytes"])
def test_owner_band_resource_limits_refuse_without_unbounded_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, limit: str
) -> None:
    """A genuine ordinary payload over this profile is explicitly unqualified."""
    from polisyos.core.artifacts import CoreJsonReadBoundsRefusalError, CoreJsonReadLimits
    from polisyos.runtime.quality import data_snapshot_lineage as owner

    store = FileSystemCAS(tmp_path / "cas")
    ref = _data_snapshot_ref(store)
    snapshot = DataSnapshot.model_validate(load_core_json_artifact(store, ref))
    assert (
        validate_data_snapshot_owner_lineage(store, ref, snapshot).required_admissibility_blockers
        == ()
    )
    limits = {
        "max_bytes": 64 * 1024 * 1024,
        "max_depth": 128,
        "max_elements": 1_000_000,
        "max_manifest_bytes": 1024 * 1024,
    }
    limits[limit] = 1
    with monkeypatch.context() as changed:
        changed.setattr(owner, "DATA_SNAPSHOT_OWNER_BAND_READ_LIMITS", CoreJsonReadLimits(**limits))
        with pytest.raises(
            DataSnapshotLineageError, match="data_snapshot_owner_band_not_established"
        ) as failure:
            validate_data_snapshot_owner_lineage(store, ref, snapshot)
        assert isinstance(failure.value.__cause__, CoreJsonReadBoundsRefusalError)
        assert failure.value.__cause__.limit_name == limit
    assert (
        validate_data_snapshot_owner_lineage(store, ref, snapshot).required_admissibility_blockers
        == ()
    )


def test_owner_band_without_bounded_store_never_falls_back_to_unbounded_payload(
    tmp_path: Path,
) -> None:
    """A legacy store adapter is an explicit unsupported capacity, not proof of a band."""
    store = FileSystemCAS(tmp_path / "cas")
    ref = _data_snapshot_ref(store)
    snapshot = DataSnapshot.model_validate(load_core_json_artifact(store, ref))

    class LegacyStore:
        get_manifest = store.get_manifest
        get_manifest_by_profile = store.get_manifest_by_profile
        verify = store.verify

        @staticmethod
        def get_bytes(*args: object, **kwargs: object) -> bytes:
            del args, kwargs
            raise AssertionError("owner-band verification attempted an unbounded fallback")

    with pytest.raises(DataSnapshotLineageError, match="data_snapshot_owner_band_not_established"):
        validate_data_snapshot_owner_lineage(LegacyStore(), ref, snapshot)
    assert (
        validate_data_snapshot_owner_lineage(store, ref, snapshot).required_admissibility_blockers
        == ()
    )


def test_actual_candidate_source_replays_fresh_snapshot_and_refuses_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, record_property: Any
) -> None:
    """Real source and state owners remain necessary despite self-consistent hashes."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.data_state_substrate import (
        CandidateAcquisitionSourceSlotBinding,
        materialize_candidate_acquisition_snapshot,
    )
    from tests._helpers.lane01_candidate_source import build_lane01_candidate_source

    tenant_id = "00000000-0000-4000-8000-000000000101"
    cell_id = "00000000-0000-4000-8000-000000000102"
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        case = build_lane01_candidate_source(
            tmp_path / "source", monkeypatch, tenant_id=tenant_id, cell_id=cell_id
        )
        assert isinstance(case.store, FileSystemCAS)
        source = case.source
        assert source.observation_class == "model_output"
        base_ref = _data_snapshot_ref(case.store)
        binding = CandidateAcquisitionSourceSlotBinding(
            profile_selection_ref="sha256:" + "9" * 64,
            candidate_digest=case.candidate_digest,
            canonical_variable_id=case.entry.target_variable,
            target_slot_id=source.target_slot_id,
        )
        issued = materialize_candidate_acquisition_snapshot(
            case.store,
            workspace_dir=tmp_path / "candidate-data",
            base_data_snapshot_ref=base_ref,
            candidate_source_ref=case.source_ref,
            slot_binding=binding,
            transaction_time=datetime(2026, 11, 3, 12, tzinfo=UTC),
            authority=case.authority,
        )
        fresh = FileSystemCAS(case.store.root)
        ref = issued.data_snapshot_ref
        snapshot = DataSnapshot.model_validate(load_core_json_artifact(fresh, ref))
        assert isinstance(snapshot.source_lineage, CandidateAcquisitionSourceDataSnapshotLineage)
        assert snapshot.source_lineage.base_data_snapshot_ref == base_ref
        assert snapshot.source_lineage.candidate_source_ref == case.source_ref
        payload = load_core_json_artifact(fresh, snapshot.data_ref)
        assert isinstance(payload, dict)
        assert payload["acquisition"]["selected"]["value"] == source.observation
        assert "_policyos_acquisition" not in payload

        def read_candidate() -> None:
            verdict = validate_data_snapshot_owner_lineage(
                fresh, ref, snapshot, candidate_only=True
            )
            assert verdict.acquisition_source_row_status == "not_established"
            assert verdict.required_admissibility_blockers == (
                ACQUIRED_SOURCE_ROW_REVALIDATION_LIMITATION,
                *tuple(dict.fromkeys((*CANDIDATE_SOURCE_LIMITATIONS, *source.limitations))),
            )

        read_candidate()
        with pytest.raises(DataSnapshotSourceRowNotEstablishedError):
            validate_data_snapshot_owner_lineage(fresh, ref, snapshot)
        record_property("candidate_source_ref", str(case.source_ref.artifact_id))
        record_property("candidate_data_snapshot_ref", str(ref.artifact_id))
        record_property("candidate_numeric_value", source.observation)

        # Neither the canonical source itself nor its unchanged bytes may be
        # laundered by an ordinary schema-0.2 wrapper or another kind/MIME.
        selected_sources = [case.source_ref]
        for kind, media_type, body in (
            ("fabric.world_payload", "application/json", source.model_dump(mode="json")),
            ("fixture.future_payload", "application/octet-stream", source.model_dump(mode="json")),
            ("fabric.world_payload", "application/json", payload),
            ("fixture.future_payload", "application/octet-stream", payload),
        ):
            selected_sources.append(
                fresh.put_json(
                    body,
                    PutOptions(kind=kind, media_type=media_type),
                    canon_spec=CanonSpec(forbid_floats=False),
                    return_selected_profile=True,
                )
            )
        for payload_ref in selected_sources:
            wrapped_ref, wrapped = _legacy_snapshot(fresh, payload_ref)
            with pytest.raises(
                DataSnapshotLineageError, match="candidate_acquisition_source_lineage_missing"
            ):
                validate_data_snapshot_owner_lineage(fresh, wrapped_ref, wrapped)

        # A real FabricBridge snapshot and selected request/schema/report are
        # available; replacing just its data with candidate bytes must refuse.
        bridge_ref, bridge = _real_sql_snapshot(fresh, tmp_path)
        bridge_parent = fresh.get_manifest(bridge_ref)
        bridge_payload_manifest = fresh.get_manifest(bridge.data_ref)
        for body in (source.model_dump(mode="json"), payload):
            wrapped_payload_ref = fresh.put_json(
                body,
                _retained_options(bridge_payload_manifest),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            wrapped = bridge.model_copy(update={"data_ref": wrapped_payload_ref})
            wrapped_ref = fresh.put_json(
                wrapped,
                _retained_options(
                    bridge_parent,
                    inputs=[
                        input_ref_from_artifact_ref(child, role=role)
                        for child, role in data_snapshot_owner_input_requirements(wrapped)
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            with pytest.raises(
                DataSnapshotLineageError, match="candidate_acquisition_source_lineage_missing"
            ):
                validate_data_snapshot_owner_lineage(fresh, wrapped_ref, wrapped)

        # Move each actual deciding blob aside and restore it. The source owner
        # must reopen these bytes; refs and hashes left in the manifest cannot
        # stand in for source access. No store method or verifier is replaced.
        for selected in (case.source_ref, source.raw_source_ref, source.normalized_source_ref):
            blob_path, _manifest_path = fresh._paths(selected.artifact_id)
            held_path = blob_path.with_name(blob_path.name + ".candidate-lineage-held")
            assert not held_path.exists()
            blob_path.rename(held_path)
            try:
                with pytest.raises(DataSnapshotLineageError):
                    read_candidate()
            finally:
                held_path.rename(blob_path)
            read_candidate()

        # A coherent rehash of the payload and its parent still cannot change
        # the selected value behind the real compiler/source owner's back.
        payload_manifest = fresh.get_manifest_by_profile(
            snapshot.data_ref.artifact_id, snapshot.data_ref.manifest_profile_sha256
        )
        parent = fresh.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256)
        for mutation in ("value", "limitation", "provenance"):
            changed = load_core_json_artifact(fresh, snapshot.data_ref)
            if mutation == "value":
                changed["acquisition"]["selected"]["value"] = source.observation + 0.01
            elif mutation == "limitation":
                changed["_policyos_candidate_acquisition"]["limitation_codes"].remove(
                    source.limitations[-1]
                )
            else:
                changed["acquisition"]["selected"]["provenance_class"] = "observed"
            changed_payload_ref = fresh.put_json(
                changed,
                _retained_options(payload_manifest),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            changed_snapshot = snapshot.model_copy(update={"data_ref": changed_payload_ref})
            changed_ref = fresh.put_json(
                changed_snapshot,
                _retained_options(
                    parent,
                    inputs=[
                        input_ref_from_artifact_ref(child, role=role)
                        for child, role in data_snapshot_owner_input_requirements(changed_snapshot)
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            with pytest.raises(
                DataSnapshotLineageError, match="candidate_acquisition_source_owner_replay"
            ):
                validate_data_snapshot_owner_lineage(
                    fresh, changed_ref, changed_snapshot, candidate_only=True
                )
        read_candidate()
