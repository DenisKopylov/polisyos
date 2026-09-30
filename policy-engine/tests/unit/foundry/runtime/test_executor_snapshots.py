from __future__ import annotations

import dataclasses
import hashlib
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest

import polisyos.foundry.execute._internal.snapshots as snapshots_module
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import ArtifactIntegrityError, FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import StateSnapshot
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.models import load_model
from polisyos.foundry.execute._internal.snapshots import (
    _build_dataclass,
    _dataclass_type_hints,
    _decode_snapshot_leaf,
    _flatten_state,
    _nest_state,
    _nest_state_from_keys,
    _SnapshotLeaf,
    _validate_snapshot_blob,
    load_state_snapshot,
    put_state_snapshot,
)
from polisyos.runtime.http.resilience import guard_runtime_cas

if TYPE_CHECKING:
    MissingSnapshotType = Any


@dataclasses.dataclass(frozen=True)
class _ScalarState:
    step: int
    ratio: float
    active: bool


@dataclasses.dataclass(frozen=True)
class _ForwardChild:
    value: Any


@dataclasses.dataclass(frozen=True)
class _ForwardParent:
    child: _ForwardChild
    count: int


@dataclasses.dataclass(frozen=True)
class _UnresolvedAnnotation:
    value: MissingSnapshotType


def _seed_legacy_state_blob(tmp_path, state: GlobalState):
    source = FileSystemCAS(tmp_path / "canonical-source")
    source_snapshot_ref = put_state_snapshot(source, state=state)
    source_snapshot = load_model(source, source_snapshot_ref, StateSnapshot)
    blob_bytes = source.get_bytes(source_snapshot.state_ref.artifact_id)

    store = FileSystemCAS(tmp_path / "legacy-target")
    legacy_inputs = [
        InputRef(artifact_id=ArtifactID.from_sha256_hex("e" * 64), role="base_state"),
        InputRef(artifact_id=ArtifactID.from_sha256_hex("f" * 64), role="state_delta"),
    ]
    legacy_ref = store.put_bytes(
        blob_bytes,
        PutOptions(
            kind="foundry.state_blob",
            media_type="application/x-npz",
            inputs=legacy_inputs,
        ),
    )
    return store, legacy_ref, legacy_inputs


def test_snapshot_metadata_includes_version_checksum_and_entry_count(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=3, n_firms=2)

    snapshot_ref = put_state_snapshot(store, state=state, step=4)
    snapshot = load_model(store, snapshot_ref, StateSnapshot)
    blob_bytes = store.get_bytes(snapshot.state_ref.artifact_id)

    assert snapshot.schema_version == "2.2"
    assert snapshot.format_version == "npz-v2"
    assert snapshot.codec == "numpy-npz"
    assert snapshot.checksum_sha256 == hashlib.sha256(blob_bytes).hexdigest()
    assert snapshot.entry_count is not None
    assert snapshot.entry_count > 0
    assert snapshot.step == 4
    assert "snapshot_format:npz-v2" in snapshot.notes
    assert snapshot.lineage_inputs == [
        InputRef(artifact_id=snapshot.state_ref.artifact_id, role="state_blob")
    ]
    assert store.get_manifest(snapshot_ref.artifact_id).artifact_schema == SchemaInfo(
        name="polisyos.core.StateSnapshot", version="2.2.0"
    )


def test_state_snapshot_payload_without_version_keeps_historical_2_1_default() -> None:
    """An omitted version remains interpreted through the historical 2.1 contract."""
    state_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("c" * 64),
        kind="foundry.state_blob",
        media_type="application/x-npz",
    )

    snapshot = StateSnapshot.model_validate(
        {"state_ref": state_ref.model_dump(mode="json")}
    )

    assert snapshot.schema_version == "2.1"
    assert snapshot.lineage_inputs is None


def test_tenant_scoped_snapshot_creation_accepts_absent_blob(tmp_path) -> None:
    """A missing deterministic blob falls through before ownership lookup."""
    store = FileSystemCAS(
        tmp_path / "cas",
        tenant_id="tenant-a",
        cell_id="cell-a",
    )

    snapshot_ref = put_state_snapshot(
        store,
        state=GlobalState.empty(n_agents=1, n_firms=1),
        step=0,
    )

    snapshot = load_model(store, snapshot_ref, StateSnapshot)
    blob_path, manifest_path = store._paths(snapshot.state_ref.artifact_id)
    assert blob_path.is_file()
    assert manifest_path.is_file()


def test_guarded_tenant_scoped_snapshot_put_claims_new_blob_and_denies_foreign_read(
    tmp_path,
) -> None:
    """A guarded CAS can write under its tenant and refuses a foreign reader."""
    raw_store = FileSystemCAS(tmp_path / "cas").with_ambient_ownership_enforcement()
    store = guard_runtime_cas(raw_store)
    state = GlobalState.empty(n_agents=1, n_firms=1)

    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            snapshot_ref = put_state_snapshot(store, state=state, step=0)
            snapshot = load_model(store, snapshot_ref, StateSnapshot)
            state_blob_id = snapshot.state_ref.artifact_id
            assert store.has(snapshot_ref.artifact_id)
            assert store.has(state_blob_id)
            assert store.get_bytes(state_blob_id)

        with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-b"):
            with pytest.raises(ArtifactOwnershipError):
                store.get_bytes(snapshot_ref.artifact_id)
            with pytest.raises(ArtifactOwnershipError):
                store.get_bytes(state_blob_id)
    finally:
        store.close()


def test_tenant_scoped_snapshot_deduplicates_foreign_owned_blob_through_exact_view(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit re-put claims a compatible shared blob after read denial."""
    cas_root = tmp_path / "cas"
    state = GlobalState.empty(n_agents=1, n_firms=1)
    foreign_store = FileSystemCAS(cas_root, tenant_id="tenant-b", cell_id="cell-b")
    foreign_snapshot_ref = put_state_snapshot(foreign_store, state=state, step=0)
    foreign_snapshot = load_model(foreign_store, foreign_snapshot_ref, StateSnapshot)
    foreign_blob_id = foreign_snapshot.state_ref.artifact_id

    tenant_store = FileSystemCAS(cas_root, tenant_id="tenant-a", cell_id="cell-a")
    with pytest.raises(ArtifactOwnershipError):
        tenant_store.get_bytes(foreign_blob_id)

    guarded_tenant_store = guard_runtime_cas(tenant_store)
    try:
        tenant_snapshot_ref = put_state_snapshot(guarded_tenant_store, state=state, step=0)
        tenant_snapshot = load_model(guarded_tenant_store, tenant_snapshot_ref, StateSnapshot)
        expected_blob_input = InputRef(
            artifact_id=foreign_blob_id,
            role="state_blob",
            manifest_profile_sha256=tenant_snapshot.state_ref.manifest_profile_sha256,
        )
        wrapper_manifest = guarded_tenant_store.get_manifest(tenant_snapshot_ref)

        assert tenant_snapshot.state_ref.artifact_id == foreign_blob_id
        assert tenant_snapshot.state_ref.manifest_profile_sha256 is not None
        assert tenant_snapshot.lineage_inputs is not None
        assert tenant_snapshot.lineage_inputs[-1] == expected_blob_input
        assert wrapper_manifest.inputs[-1] == expected_blob_input
        assert guarded_tenant_store.has(tenant_snapshot.state_ref)
        assert guarded_tenant_store.get_bytes(tenant_snapshot.state_ref) == (
            foreign_store.get_bytes(foreign_blob_id)
        )
        assert foreign_store.has(foreign_blob_id)
        restored = load_state_snapshot(
            guarded_tenant_store,
            snapshot_ref=tenant_snapshot_ref,
        )
        assert int(np.asarray(restored.step)) == int(np.asarray(state.step))

        original_ref_to_input = snapshots_module.artifact_input_ref

        def _drop_selected_view(ref: ArtifactRef, *, role: str) -> InputRef:
            edge = original_ref_to_input(ref, role=role)
            if role != "state_blob":
                return edge
            assert ref.manifest_profile_sha256 is not None
            return InputRef(artifact_id=edge.artifact_id, role=edge.role)

        monkeypatch.setattr(snapshots_module, "artifact_input_ref", _drop_selected_view)
        with pytest.raises(ArtifactOwnershipError):
            put_state_snapshot(guarded_tenant_store, state=state, step=1)
    finally:
        guarded_tenant_store.close()


def test_state_blob_is_content_only_while_wrapper_preserves_lineage(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=1, n_firms=1)
    first_inputs = [
        InputRef(artifact_id=ArtifactID.from_sha256_hex("a" * 64), role="base_state"),
        InputRef(artifact_id=ArtifactID.from_sha256_hex("b" * 64), role="state_delta"),
    ]
    second_inputs = [
        InputRef(artifact_id=ArtifactID.from_sha256_hex("c" * 64), role="base_state"),
        InputRef(artifact_id=ArtifactID.from_sha256_hex("d" * 64), role="state_delta"),
    ]

    first_ref = put_state_snapshot(store, state=state, step=1, inputs=first_inputs)
    second_ref = put_state_snapshot(store, state=state, step=2, inputs=second_inputs)

    first_snapshot = load_model(store, first_ref, StateSnapshot)
    second_snapshot = load_model(store, second_ref, StateSnapshot)
    blob_manifest = store.get_manifest(first_snapshot.state_ref.artifact_id)
    first_manifest = store.get_manifest(first_ref.artifact_id)
    second_manifest = store.get_manifest(second_ref.artifact_id)

    assert first_snapshot.state_ref.artifact_id == second_snapshot.state_ref.artifact_id
    assert blob_manifest.kind == "foundry.state_blob"
    assert blob_manifest.inputs == []
    assert {item.role for item in first_manifest.inputs} == {
        "base_state",
        "state_delta",
        "state_blob",
    }
    assert {item.role for item in second_manifest.inputs} == {
        "base_state",
        "state_delta",
        "state_blob",
    }
    assert first_manifest.inputs[:2] != second_manifest.inputs[:2]
    assert first_snapshot.lineage_inputs == first_manifest.inputs
    assert second_snapshot.lineage_inputs == second_manifest.inputs


def test_state_snapshot_wrapper_identity_includes_ordered_lineage(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=1, n_firms=1)
    first_inputs = [
        InputRef(artifact_id=ArtifactID.from_sha256_hex("1" * 64), role="base_state"),
        InputRef(artifact_id=ArtifactID.from_sha256_hex("2" * 64), role="state_delta"),
    ]
    second_inputs = list(reversed(first_inputs))

    first_ref = put_state_snapshot(store, state=state, step=5, inputs=first_inputs)
    second_ref = put_state_snapshot(store, state=state, step=5, inputs=second_inputs)

    first_snapshot = load_model(store, first_ref, StateSnapshot)
    second_snapshot = load_model(store, second_ref, StateSnapshot)
    first_manifest = store.get_manifest(first_ref.artifact_id)
    second_manifest = store.get_manifest(second_ref.artifact_id)
    expected_first_lineage = [
        *first_inputs,
        InputRef(artifact_id=first_snapshot.state_ref.artifact_id, role="state_blob"),
    ]
    expected_second_lineage = [
        *second_inputs,
        InputRef(artifact_id=second_snapshot.state_ref.artifact_id, role="state_blob"),
    ]

    assert first_ref.artifact_id != second_ref.artifact_id
    assert first_snapshot.state_ref.artifact_id == second_snapshot.state_ref.artifact_id
    assert first_snapshot.lineage_inputs == expected_first_lineage
    assert second_snapshot.lineage_inputs == expected_second_lineage
    assert first_manifest.inputs == expected_first_lineage
    assert second_manifest.inputs == expected_second_lineage
    assert store.get_manifest(first_snapshot.state_ref.artifact_id).inputs == []


def test_state_snapshot_reuses_identical_ordered_lineage(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=1, n_firms=1)
    inputs = [
        InputRef(artifact_id=ArtifactID.from_sha256_hex("5" * 64), role="base_state"),
        InputRef(artifact_id=ArtifactID.from_sha256_hex("6" * 64), role="state_delta"),
    ]

    first_ref = put_state_snapshot(store, state=state, step=6, inputs=inputs)
    first_manifest_bytes = store.get_manifest_bytes(first_ref.artifact_id)
    second_ref = put_state_snapshot(store, state=state, step=6, inputs=inputs)

    assert second_ref.artifact_id == first_ref.artifact_id
    assert store.get_manifest_bytes(second_ref.artifact_id) == first_manifest_bytes


def test_state_snapshot_2_2_readback_rejects_manifest_lineage_mismatch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=1, n_firms=1)
    inputs = [
        InputRef(artifact_id=ArtifactID.from_sha256_hex("7" * 64), role="base_state"),
    ]
    snapshot_ref = put_state_snapshot(store, state=state, step=7, inputs=inputs)
    manifest = store.get_manifest(snapshot_ref.artifact_id)
    _blob_path, manifest_path = store._paths(snapshot_ref.artifact_id)
    manifest_path.write_bytes(
        ManifestLifecycle.to_bytes(
            manifest.model_copy(
                update={
                    "inputs": [
                        InputRef(
                            artifact_id=ArtifactID.from_sha256_hex("8" * 64),
                            role="different_context",
                        ),
                        *manifest.inputs[1:],
                    ]
                }
            )
        )
    )

    with pytest.raises(ValueError, match="lineage.*manifest"):
        load_state_snapshot(store, snapshot_ref=snapshot_ref)


def test_state_snapshot_2_2_readback_rejects_manifest_schema_mismatch(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=1, n_firms=1)
    snapshot_ref = put_state_snapshot(store, state=state, step=7)
    manifest = store.get_manifest(snapshot_ref.artifact_id)
    _blob_path, manifest_path = store._paths(snapshot_ref.artifact_id)
    manifest_path.write_bytes(
        ManifestLifecycle.to_bytes(
            manifest.model_copy(
                update={
                    "artifact_schema": SchemaInfo(
                        name="polisyos.core.StateSnapshot", version="2.0.0"
                    )
                }
            )
        )
    )

    with pytest.raises(ValueError, match="manifest schema"):
        load_state_snapshot(store, snapshot_ref=snapshot_ref)


def test_legacy_state_snapshot_2_0_without_lineage_remains_readable(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=1, n_firms=1)
    source_ref = put_state_snapshot(store, state=state, step=0)
    source_snapshot = load_model(store, source_ref, StateSnapshot)
    legacy_inputs = [
        InputRef(artifact_id=ArtifactID.from_sha256_hex("9" * 64), role="legacy_context"),
        InputRef(artifact_id=source_snapshot.state_ref.artifact_id, role="state_blob"),
    ]
    legacy_snapshot = StateSnapshot(
        schema_version="2.0",
        state_ref=source_snapshot.state_ref,
        step=source_snapshot.step,
        format_version=source_snapshot.format_version,
        checksum_sha256=source_snapshot.checksum_sha256,
        entry_count=source_snapshot.entry_count,
        codec=source_snapshot.codec,
        notes=source_snapshot.notes,
    )
    legacy_ref = store.put_json(
        legacy_snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="2.0.0"),
            inputs=legacy_inputs,
        ),
    )
    prior_manifest_bytes = store.get_manifest_bytes(legacy_ref.artifact_id)

    restored = load_state_snapshot(store, snapshot_ref=legacy_ref)
    persisted_legacy = load_model(store, legacy_ref, StateSnapshot)

    assert legacy_snapshot.lineage_inputs is None
    assert persisted_legacy.schema_version == "2.0"
    assert persisted_legacy.lineage_inputs is None
    assert b"lineage_inputs" not in store.get_bytes(legacy_ref.artifact_id)
    assert int(np.asarray(restored.step)) == int(np.asarray(state.step))
    assert store.get_manifest_bytes(legacy_ref.artifact_id) == prior_manifest_bytes


def test_state_snapshot_2_1_selected_state_ref_replays_legacy_bare_edge_without_rewrite(
    tmp_path,
) -> None:
    """Historical 2.1 selector metadata never upgrades its bare lineage edge."""
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=1, n_firms=1)
    source_ref = put_state_snapshot(store, state=state, step=4)
    source_snapshot = load_model(store, source_ref, StateSnapshot)
    blob_bytes = store.get_bytes(source_snapshot.state_ref.artifact_id)
    default_manifest_bytes = store.get_manifest_bytes(source_snapshot.state_ref.artifact_id)
    selected_state_ref = store.put_bytes(
        blob_bytes,
        PutOptions(
            kind="foundry.state_blob",
            media_type="application/x-npz",
            inputs=[
                InputRef(
                    artifact_id=ArtifactID.from_sha256_hex("a" * 64),
                    role="historical_context",
                )
            ],
        ),
    )
    assert selected_state_ref.manifest_profile_sha256 is not None
    historical_edge = InputRef(
        artifact_id=selected_state_ref.artifact_id, role="state_blob"
    )
    historical_snapshot = StateSnapshot(
        schema_version="2.1",
        state_ref=selected_state_ref,
        step=source_snapshot.step,
        format_version=source_snapshot.format_version,
        checksum_sha256=source_snapshot.checksum_sha256,
        entry_count=source_snapshot.entry_count,
        codec=source_snapshot.codec,
        lineage_inputs=[historical_edge],
        notes=source_snapshot.notes,
    )
    historical_ref = store.put_json(
        historical_snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="2.1.0"),
            inputs=[historical_edge],
        ),
    )
    historical_payload_bytes = store.get_bytes(historical_ref.artifact_id)
    historical_manifest_bytes = store.get_manifest_bytes(historical_ref.artifact_id)

    restored = load_state_snapshot(store, snapshot_ref=historical_ref)

    replayed = load_model(store, historical_ref, StateSnapshot)
    assert replayed.schema_version == "2.1"
    assert replayed.state_ref.manifest_profile_sha256 == (
        selected_state_ref.manifest_profile_sha256
    )
    assert replayed.lineage_inputs == [historical_edge]
    assert store.get_bytes(replayed.state_ref.artifact_id) == blob_bytes
    assert int(np.asarray(restored.step)) == int(np.asarray(state.step))
    assert store.get_bytes(historical_ref.artifact_id) == historical_payload_bytes
    assert store.get_manifest_bytes(historical_ref.artifact_id) == historical_manifest_bytes
    assert store.get_manifest_bytes(replayed.state_ref.artifact_id) == default_manifest_bytes


def test_state_snapshot_2_1_readback_requires_lineage_payload(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=1, n_firms=1)
    source_ref = put_state_snapshot(store, state=state, step=0)
    source_snapshot = load_model(store, source_ref, StateSnapshot)
    state_blob_input = InputRef(artifact_id=source_snapshot.state_ref.artifact_id, role="state_blob")
    incomplete_snapshot = StateSnapshot(
        schema_version="2.1",
        state_ref=source_snapshot.state_ref,
        step=source_snapshot.step,
        format_version=source_snapshot.format_version,
        checksum_sha256=source_snapshot.checksum_sha256,
        entry_count=source_snapshot.entry_count,
        codec=source_snapshot.codec,
        notes=source_snapshot.notes,
    )
    incomplete_ref = store.put_json(
        incomplete_snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.StateSnapshot", version="2.1.0"),
            inputs=[state_blob_input],
        ),
    )

    with pytest.raises(ValueError, match="lineage_inputs"):
        load_state_snapshot(store, snapshot_ref=incomplete_ref)


@pytest.mark.parametrize("schema_version", ["2.3", "9.9"])
def test_unknown_state_snapshot_schema_fails_closed_before_lineage_bypass(
    tmp_path, schema_version: str
) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=1, n_firms=1)
    source_ref = put_state_snapshot(store, state=state, step=0)
    source_snapshot = load_model(store, source_ref, StateSnapshot)
    state_blob_input = InputRef(
        artifact_id=source_snapshot.state_ref.artifact_id,
        role="state_blob",
    )
    unknown_snapshot = StateSnapshot(
        schema_version=schema_version,
        state_ref=source_snapshot.state_ref,
        step=source_snapshot.step,
        format_version=source_snapshot.format_version,
        checksum_sha256=source_snapshot.checksum_sha256,
        entry_count=source_snapshot.entry_count,
        codec=source_snapshot.codec,
        lineage_inputs=[state_blob_input],
        notes=source_snapshot.notes,
    )
    unknown_ref = store.put_json(
        unknown_snapshot,
        PutOptions(
            kind="foundry.state_snapshot",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.StateSnapshot", version=f"{schema_version}.0"
            ),
            inputs=[state_blob_input],
        ),
    )

    with pytest.raises(ValueError, match="Unsupported StateSnapshot schema_version"):
        load_state_snapshot(store, snapshot_ref=unknown_ref)


def test_legacy_state_blob_gets_content_only_view_and_preserves_default_lineage(tmp_path) -> None:
    state = GlobalState.empty(n_agents=1, n_firms=1)
    store, legacy_ref, legacy_inputs = _seed_legacy_state_blob(tmp_path, state)
    prior_manifest_bytes = store.get_manifest_bytes(legacy_ref.artifact_id)
    contextual_inputs = [
        InputRef(artifact_id=ArtifactID.from_sha256_hex("1" * 64), role="input.data_snapshot_ref"),
        InputRef(
            artifact_id=ArtifactID.from_sha256_hex("2" * 64),
            role="input.registry_bundle_ref",
        ),
    ]

    snapshot_ref = put_state_snapshot(
        store,
        state=state,
        step=3,
        inputs=contextual_inputs,
    )

    snapshot = load_model(store, snapshot_ref, StateSnapshot)
    default_blob_manifest = store.get_manifest(legacy_ref.artifact_id)
    selected_blob_manifest = store.get_manifest(snapshot.state_ref)
    wrapper_manifest = store.get_manifest(snapshot_ref)
    expected_blob_input = InputRef(
        artifact_id=legacy_ref.artifact_id,
        role="state_blob",
        manifest_profile_sha256=snapshot.state_ref.manifest_profile_sha256,
    )

    assert snapshot.state_ref.artifact_id == legacy_ref.artifact_id
    assert snapshot.state_ref.manifest_profile_sha256 is not None
    assert store.get_manifest_bytes(legacy_ref.artifact_id) == prior_manifest_bytes
    assert default_blob_manifest.inputs == legacy_inputs
    assert selected_blob_manifest.inputs == []
    assert selected_blob_manifest.kind == "foundry.state_blob"
    assert selected_blob_manifest.media_type == "application/x-npz"
    assert wrapper_manifest.inputs[:2] == contextual_inputs
    assert wrapper_manifest.inputs[-1] == expected_blob_input
    assert snapshot.lineage_inputs == wrapper_manifest.inputs
    restored = load_state_snapshot(store, snapshot_ref=snapshot_ref)
    assert int(np.asarray(restored.step)) == int(np.asarray(state.step))


def test_legacy_state_blob_profile_mismatch_gets_tenant_owned_view(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = GlobalState.empty(n_agents=1, n_firms=1)
    canonical_source = FileSystemCAS(tmp_path / "canonical-source")
    source_snapshot_ref = put_state_snapshot(canonical_source, state=state)
    source_snapshot = load_model(canonical_source, source_snapshot_ref, StateSnapshot)
    blob_bytes = canonical_source.get_bytes(source_snapshot.state_ref.artifact_id)

    cas_root = tmp_path / "legacy-target"
    foreign_store = FileSystemCAS(cas_root, tenant_id="tenant-b", cell_id="cell-b")
    foreign_input_ref = foreign_store.put_bytes(
        b"foreign legacy input",
        PutOptions(kind="foundry.legacy_input", media_type="application/octet-stream"),
    )
    foreign_blob_ref = foreign_store.put_bytes(
        blob_bytes,
        PutOptions(
            kind="foundry.state_blob",
            media_type="application/x-legacy-npz",
            inputs=[
                InputRef(
                    artifact_id=foreign_input_ref.artifact_id,
                    role="base_state",
                )
            ],
        ),
    )
    tenant_store = FileSystemCAS(cas_root, tenant_id="tenant-a", cell_id="cell-a")
    foreign_manifest = foreign_store.get_manifest(foreign_blob_ref)
    foreign_profile = ManifestLifecycle.profile_sha256(foreign_manifest)
    prior_foreign_manifest_bytes = foreign_store.get_manifest_bytes(
        foreign_blob_ref.artifact_id
    )
    foreign_default_manifest_path = foreign_store._paths(foreign_blob_ref.artifact_id)[1]
    prewrite_foreign_manifest_reads: list[Any] = []
    write_started = False
    original_manifest_read = tenant_store._manifests.read
    original_put_bytes = tenant_store.put_bytes
    observed_has_refs: list[ArtifactRef | ArtifactID | str] = []
    original_has = tenant_store.has

    def _record_manifest_read(path: Any) -> Any:
        if not write_started and path == foreign_default_manifest_path:
            prewrite_foreign_manifest_reads.append(path)
        return original_manifest_read(path)

    def _record_put_bytes(data: bytes, options: PutOptions) -> ArtifactRef:
        nonlocal write_started
        write_started = True
        return original_put_bytes(data, options)

    def _record_has(ref: ArtifactRef | ArtifactID | str) -> bool:
        observed_has_refs.append(ref)
        return original_has(ref)

    monkeypatch.setattr(tenant_store._manifests, "read", _record_manifest_read)
    monkeypatch.setattr(tenant_store, "put_bytes", _record_put_bytes)
    monkeypatch.setattr(tenant_store, "has", _record_has)
    with pytest.raises(ArtifactOwnershipError):
        tenant_store.get_bytes(foreign_blob_ref.artifact_id)

    snapshot_ref = put_state_snapshot(tenant_store, state=state, step=3)
    snapshot = load_model(tenant_store, snapshot_ref, StateSnapshot)
    expected_blob_input = InputRef(
        artifact_id=foreign_blob_ref.artifact_id,
        role="state_blob",
        manifest_profile_sha256=snapshot.state_ref.manifest_profile_sha256,
    )
    selected_blob_manifest = tenant_store.get_manifest(snapshot.state_ref)
    wrapper_manifest = tenant_store.get_manifest(snapshot_ref)

    assert not prewrite_foreign_manifest_reads
    assert not any(ref == foreign_blob_ref.artifact_id for ref in observed_has_refs)
    assert snapshot.state_ref.artifact_id == foreign_blob_ref.artifact_id
    assert snapshot.state_ref.manifest_profile_sha256 is not None
    assert tenant_store.has(snapshot.state_ref)
    assert selected_blob_manifest.kind == "foundry.state_blob"
    assert selected_blob_manifest.media_type == "application/x-npz"
    assert selected_blob_manifest.inputs == []
    assert wrapper_manifest.inputs[-1] == expected_blob_input
    assert snapshot.lineage_inputs is not None
    assert snapshot.lineage_inputs[-1] == expected_blob_input
    assert tenant_store.get_bytes(snapshot.state_ref) == blob_bytes
    assert tenant_store.has_manifest_view(
        foreign_blob_ref.artifact_id,
        foreign_profile,
    ) is False
    assert foreign_store.has_manifest_view(
        foreign_blob_ref.artifact_id,
        foreign_profile,
    )
    assert foreign_store.get_manifest_bytes(foreign_blob_ref.artifact_id) == (
        prior_foreign_manifest_bytes
    )
    assert foreign_store.get_manifest(foreign_blob_ref).media_type == "application/x-legacy-npz"
    assert foreign_store.get_bytes(foreign_blob_ref) == blob_bytes
    restored = load_state_snapshot(tenant_store, snapshot_ref=snapshot_ref)
    assert int(np.asarray(restored.step)) == int(np.asarray(state.step))


def test_corrupt_legacy_state_blob_fails_closed(tmp_path) -> None:
    state = GlobalState.empty(n_agents=1, n_firms=1)
    store, legacy_ref, _legacy_inputs = _seed_legacy_state_blob(tmp_path, state)
    blob_path, _manifest_path = store._paths(legacy_ref.artifact_id)
    blob_path.write_bytes(b"corrupt legacy state blob")

    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        put_state_snapshot(store, state=state, step=3)


def test_load_state_snapshot_rejects_corrupt_blob_checksum(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(n_agents=2, n_firms=1)
    snapshot_ref = put_state_snapshot(store, state=state, step=0)
    snapshot = load_model(store, snapshot_ref, StateSnapshot)

    blob_path, _manifest_path = store._paths(snapshot.state_ref.artifact_id)
    blob_path.write_bytes(b"not a valid snapshot blob")

    with pytest.raises(ValueError, match="Snapshot checksum mismatch"):
        load_state_snapshot(store, snapshot_ref=snapshot_ref)


def test_put_state_snapshot_does_not_publish_snapshot_when_blob_not_visible(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    monkeypatch.setattr(store, "has", lambda _artifact_id: False)

    with pytest.raises(ValueError, match="not fully persisted"):
        put_state_snapshot(store, state=GlobalState.empty(n_agents=1, n_firms=1), step=0)

    persisted_kinds = [
        store.get_manifest(artifact_id).kind for artifact_id in store.iter_artifact_ids()
    ]
    assert "foundry.state_snapshot" not in persisted_kinds


def test_flatten_state_iterative_codec_handles_scalar_values() -> None:
    flat = dict(_flatten_state(_ScalarState(step=7, ratio=0.25, active=True)))

    assert flat["step"].shape == ()
    assert flat["ratio"].shape == ()
    assert flat["active"].shape == ()

    restored = _build_dataclass(_ScalarState, _nest_state(flat))

    assert int(np.asarray(restored.step)) == 7
    assert float(np.asarray(restored.ratio)) == pytest.approx(0.25)
    assert bool(np.asarray(restored.active)) is True


def test_snapshot_helpers_fail_closed_on_invalid_shapes_and_types() -> None:
    with pytest.raises(ValueError, match="unnamed scalar root"):
        dict(_flatten_state(1))

    with pytest.raises(TypeError, match="Unsupported snapshot value"):
        dict(_flatten_state({"not": "a dataclass"}, prefix="payload."))

    with pytest.raises(ValueError, match="Invalid snapshot key"):
        _nest_state_from_keys(["agents..income"])

    with pytest.raises(ValueError, match="key collision"):
        _nest_state_from_keys(["agents", "agents.income"])

    with pytest.raises(ValueError, match="Expected dataclass type"):
        _build_dataclass(dict, {})

    with pytest.raises(ValueError, match="Missing nested data"):
        _build_dataclass(_ForwardParent, {"count": np.asarray(1)})

    with pytest.raises(ValueError, match="Missing nested data"):
        _build_dataclass(_ForwardParent, {"child": np.asarray(1), "count": np.asarray(1)})

    with pytest.raises(ValueError, match="Missing value"):
        _build_dataclass(_ScalarState, {"step": np.asarray(1), "ratio": np.asarray(1.0)})

    with pytest.raises(ValueError, match="requires an open NPZ blob"):
        _decode_snapshot_leaf(_SnapshotLeaf("missing"), blob=None)

    assert _dataclass_type_hints(_UnresolvedAnnotation) == {}


def test_validate_snapshot_blob_rejects_unknown_format_and_codec() -> None:
    state_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("c" * 64),
        kind="foundry.state_blob",
        media_type="application/x-npz",
    )

    with pytest.raises(ValueError, match="Unsupported snapshot format_version"):
        _validate_snapshot_blob(
            StateSnapshot(state_ref=state_ref, format_version="npz-v99"),
            b"",
        )

    with pytest.raises(ValueError, match="Unsupported snapshot codec"):
        _validate_snapshot_blob(
            StateSnapshot(state_ref=state_ref, codec="native-array"),
            b"",
        )

    _validate_snapshot_blob(
        StateSnapshot(
            state_ref=state_ref,
            checksum_sha256=hashlib.sha256(b"ok").hexdigest(),
        ),
        b"ok",
    )


def test_build_dataclass_resolves_forward_refs_without_eager_blob_materialization() -> None:
    accessed: list[str] = []

    class LazyBlob:
        files = ["child.value", "count"]

        def __getitem__(self, key: str) -> np.ndarray:
            accessed.append(key)
            if key == "child.value":
                return np.asarray([1, 2, 3], dtype=np.int32)
            if key == "count":
                return np.asarray(3, dtype=np.int32)
            raise KeyError(key)

    blob = LazyBlob()
    nested = _nest_state_from_keys(blob.files)

    assert isinstance(nested["child"]["value"], _SnapshotLeaf)

    restored = _build_dataclass(_ForwardParent, nested, blob=blob)

    assert isinstance(restored.child, _ForwardChild)
    assert np.array_equal(np.asarray(restored.child.value), np.asarray([1, 2, 3]))
    assert int(np.asarray(restored.count)) == 3
    assert accessed == ["child.value", "count"]


def test_large_state_snapshot_round_trips_with_bounded_memory(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    state = GlobalState.empty(
        n_agents=2048,
        n_firms=512,
        n_cells=64,
        n_household_cells=128,
    )

    snapshot_ref = put_state_snapshot(store, state=state, step=8)
    restored = load_state_snapshot(store, snapshot_ref=snapshot_ref)

    assert int(np.asarray(restored.step)) == int(np.asarray(state.step))
    assert restored.agents.income.shape == (2048,)
    assert restored.firms.wage_offer.shape == (512,)
    assert restored.cells is not None
    assert restored.cells.population.shape == (64,)
    assert restored.household_cells is not None
    assert restored.household_cells.disposable_income.shape == (128,)
