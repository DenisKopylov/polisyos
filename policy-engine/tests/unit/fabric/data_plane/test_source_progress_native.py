"""Native finite-replay progress proofs; no production source authority is inferred."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import load_core_json_artifact
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.cursor import CursorState, WatermarkType
from polisyos.core.contracts.fabric import DataSnapshot, EvidenceBundle, EvidenceBundleRef
from polisyos.core.contracts.provenance import ProvenanceCoreGraph, ProvenanceCoreRef
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.cache._store_serialization import ResultSerializer
from polisyos.fabric.connectors.contracts import FieldSpec, SchemaType
from polisyos.fabric.connectors.contracts.source_contract import (
    default_source_field_access_policies,
)
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.data_plane.cursor_store import CursorStore
from polisyos.fabric.data_plane.modes import run_batch_incremental
from polisyos.fabric.evidence import load_provenance_graph, persist_evidence_bundle
from polisyos.fabric.ingestion import IngestionDependencies, resolve_ingestion_dependencies
from polisyos.fabric.ingestion.source_progress import (
    FiniteSourceProgressReader,
    ReconciledSourceFrame,
    load_source_progress_witness,
)
from polisyos.ir.connectors import FetchRequest, VersionStrategy
from tests._helpers.source_progress import SOURCE_TIME, finite_source_reader, write_source_history

_FIRST = {"event_id": "one", "source_version": "1"}
_SECOND = {"event_id": "two", "source_version": "2"}
_SHADOW_KIND = "fixture.unrelated_provenance_view"


@dataclass
class _NativeBatch:
    reader: FiniteSourceProgressReader
    config: ConnectionConfig
    dependencies: IngestionDependencies
    cas_root: Path
    requests: list[FetchRequest]

    def run(self) -> Any:
        return run_batch_incremental(
            connector_manifest={
                "datasets": [{"connector_id": "rest.json", "dataset_id": "events"}]
            },
            source="native-finite-replay-property",
            license_name="fixture-only",
            cas_root=self.cas_root,
            connection_config=self.config,
            produce_snapshot=True,
            ingestion_dependencies=self.dependencies,
        )

    def store(self) -> FileSystemCAS:
        return FileSystemCAS(self.cas_root)

    def cursor(self) -> CursorState:
        cursor = CursorStore(self.store()).find_latest_cursor("rest.json", "events")
        assert cursor is not None
        return cursor

    def index_bytes(self) -> bytes:
        return CursorStore(self.store())._index_path.read_bytes()

    def install(self, cursor: CursorState) -> None:
        CursorStore(self.store()).save_cursor(cursor)

    def assert_complete(self, result: Any, rows: list[dict[str, str]]) -> CursorState:
        from polisyos.foundry.data_plane.bindings import _load_binding_payload

        assert result.status == "completed"
        assert result.cursor_ref is not None and result.data_snapshot_ref is not None
        store = self.store()
        snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(store, result.data_snapshot_ref)
        )
        payload = _load_binding_payload(store, snapshot)
        assert payload["admission_scope"] == "finite_source_fixture"
        assert payload["production_currentness"] == "not_established"
        actual_rows = [row for member in payload["sources"].values() for row in member["data"]]
        assert actual_rows == rows
        cursor = self.cursor()
        proof = cursor.metadata["source_progress"]
        for name in ("witness_ref", "payload_ref", "evidence_ref"):
            assert ArtifactRef.model_validate(proof[name]).manifest_profile_sha256 is not None
        assert store.get_manifest(
            ArtifactRef.model_validate(proof["evidence_ref"])
        ).artifact_schema == (SchemaInfo(name="fabric.evidence_bundle", version="2.0"))
        return cursor

    def assert_refused(self, result: Any, cursor: CursorState, index: bytes) -> None:
        assert result.status == "partial"
        assert result.cursor_ref is None and result.data_snapshot_ref is None
        assert self.requests[-1].incremental_since is None
        assert self.cursor() == cursor
        assert self.index_bytes() == index


@pytest.fixture
def native_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[..., _NativeBatch]]:
    """Use the actual registry, finite source IO, ingestion, persistence and reader."""
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    requests: list[FetchRequest] = []
    real_fetch = ReconciledSourceFrame.replay_fetch

    def observe(frame: ReconciledSourceFrame, config: ConnectionConfig, request: FetchRequest):
        requests.append(request)
        return real_fetch(frame, config, request)

    monkeypatch.setattr(ReconciledSourceFrame, "replay_fetch", observe)

    def create(
        *,
        version_strategy: VersionStrategy = VersionStrategy.ETAG,
        source_time: datetime = SOURCE_TIME,
        snapshots: list[tuple[str, list[dict[str, str]]]] | None = None,
    ) -> _NativeBatch:
        reader = finite_source_reader(
            tmp_path / "owner",
            connector_id="rest.json",
            dataset_id="events",
            schema_id="fixture.native.events",
            snapshots=snapshots if snapshots is not None else [("a8", [dict(_FIRST)])],
            version_strategy=version_strategy,
            source_time=source_time,
        )
        config = ConnectionConfig(url=reader.fixture_path.as_uri())
        registry.set_default_config("rest.json", config)
        return _NativeBatch(
            reader=reader,
            config=config,
            dependencies=resolve_ingestion_dependencies(
                registry=registry, source_progress_readers=(reader,)
            ),
            cas_root=tmp_path / "cas",
            requests=requests,
        )

    try:
        yield create
    finally:
        registry.shutdown()


def _replace_proof(cursor: CursorState, **updates: object) -> CursorState:
    metadata = deepcopy(cursor.metadata)
    metadata["source_progress"].update(updates)
    return cursor.model_copy(update={"metadata": metadata})


def _graph_selector(bundle: EvidenceBundle) -> ArtifactRef:
    ref = bundle.provenance_ref
    assert ref is not None and ref.manifest_profile_sha256 is not None
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(ref.artifact_id),
        kind="fabric.provenance_graph",
        media_type="application/json",
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _same_blob_evidence_view(
    store: FileSystemCAS, evidence_ref: ArtifactRef, mutation: str
) -> EvidenceBundleRef:
    manifest = store.get_manifest(evidence_ref)
    assert manifest.artifact_schema is not None
    kind = manifest.kind
    schema = manifest.artifact_schema
    if mutation == "wrong_kind":
        kind = "fixture.unrelated_evidence_view"
        schema = SchemaInfo(name=kind, version="1.0")
    elif mutation == "wrong_schema_name":
        schema = SchemaInfo(name="fixture.UnrelatedEvidenceSchema", version=schema.version)
    else:
        assert mutation == "wrong_schema_version"
        schema = SchemaInfo(name=schema.name, version="999.0")
    raw = store.get_bytes(evidence_ref)
    ref = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind=kind,
            media_type=manifest.media_type,
            schema=schema,
            producer=manifest.producer,
            env=manifest.env,
            inputs=list(manifest.inputs),
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=list(manifest.warnings),
        ),
        return_selected_profile=True,
    )
    assert ref.artifact_id == evidence_ref.artifact_id
    assert ref.manifest_profile_sha256 != evidence_ref.manifest_profile_sha256
    assert store.verify(ref).ok
    assert store.get_bytes(ref) == raw
    return EvidenceBundleRef.model_validate(ref.model_dump(mode="python"))


@pytest.mark.parametrize(
    "member", ["witness_ref", "payload_ref", "evidence_ref", "actual_request_key", "actual_request"]
)
def test_native_retained_proof_requires_each_member(native_batch, member: str) -> None:
    native = native_batch()
    cursor = native.assert_complete(native.run(), [_FIRST])
    assert native.requests[-1].incremental_since is None
    metadata = deepcopy(cursor.metadata)
    del metadata["source_progress"][member]
    changed = cursor.model_copy(update={"metadata": metadata})
    native.install(changed)
    index = native.index_bytes()
    native.assert_refused(native.run(), changed, index)


@pytest.mark.parametrize("binding", ["owner", "schema", "partition"])
def test_native_retained_proof_refuses_changed_binding(native_batch, binding: str) -> None:
    native = native_batch()
    cursor = native.assert_complete(native.run(), [_FIRST])
    source = native.reader.source_contract
    extension = native.reader.extension
    if binding == "owner":
        source = source.model_copy(update={"owner": "other-finite-owner"})
    elif binding == "schema":
        other_field = FieldSpec(name="other_owned_field", data_type=SchemaType.STRING)
        schema = source.schema_contract.model_copy(
            update={"fields": (*source.schema_contract.fields, other_field)}
        )
        security = source.security.model_copy(
            update={
                "field_policies": (
                    *source.security.field_policies,
                    *default_source_field_access_policies(
                        (other_field,),
                        classification=source.security.classification,
                        pii_tier=source.security.pii_tier,
                        tenant_scope=source.security.tenant_scope,
                    ),
                )
            }
        )
        source = source.model_copy(update={"schema_contract": schema, "security": security})
    else:
        extension = extension.model_copy(update={"partition_key": "other-partition"})
    extension = extension.model_copy(
        update={
            "source_contract_content_hash": source.content_hash,
            "schema_content_hash": source.schema_contract.to_data_schema().content_hash,
        }
    )
    alternate = replace(native.reader, source_contract=source, extension=extension)
    frame = alternate.freeze(tenant_id=None).bind_transport(
        native.config, partition_key=extension.partition_key
    )
    witness_ref = frame.witness(native.store())
    restored = load_source_progress_witness(native.store(), witness_ref)
    assert restored.extension == extension
    assert restored.reader.source_contract == source
    changed = _replace_proof(cursor, witness_ref=witness_ref.model_dump(mode="json"))
    native.install(changed)
    index = native.index_bytes()
    native.assert_refused(native.run(), changed, index)


@pytest.mark.parametrize("mutation", ["removed_ref", "removed_profile", "wrong_profile"])
def test_native_retained_evidence_requires_exact_provenance(
    native_batch, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    native = native_batch()
    cursor = native.assert_complete(native.run(), [_FIRST])
    store = native.store()
    proof = cursor.metadata["source_progress"]
    evidence_ref = EvidenceBundleRef.model_validate(proof["evidence_ref"])
    bundle = EvidenceBundle.model_validate(load_core_json_artifact(store, evidence_ref))
    graph_ref = bundle.provenance_ref
    selector = _graph_selector(bundle)
    if mutation == "removed_ref":
        changed_bundle = bundle.model_copy(update={"provenance_ref": None})
    else:
        profile = None
        if mutation == "wrong_profile":
            legacy = ProvenanceCoreRef.from_dict(
                graph_ref.model_dump(exclude={"manifest_profile_sha256"})
            )
            assert load_provenance_graph(store, legacy).graph_id == graph_ref.graph_id
            with pytest.raises(ValueError, match="selected.*profile"):
                load_provenance_graph(store, legacy, require_selected_profile=True)
            manifest = store.get_manifest(selector)
            shadow = store.put_bytes(
                store.get_bytes(selector),
                ArtifactWriteOptions(
                    kind=_SHADOW_KIND,
                    media_type="application/json",
                    schema=SchemaInfo(name=_SHADOW_KIND, version="1.0"),
                    canon=manifest.canon,
                ),
                return_selected_profile=True,
            )
            assert shadow.artifact_id == selector.artifact_id
            assert shadow.manifest_profile_sha256 != selector.manifest_profile_sha256
            assert store.verify(shadow).ok
            profile = shadow.manifest_profile_sha256
        changed_bundle = bundle.model_copy(
            update={
                "provenance_ref": graph_ref.model_copy(update={"manifest_profile_sha256": profile})
            }
        )
    changed_ref = persist_evidence_bundle(
        store, changed_bundle, schema_version="2.0", return_selected_profile=True
    )
    assert store.verify(changed_ref).ok
    assert changed_bundle.sources == bundle.sources
    assert changed_bundle.notes == bundle.notes
    changed = _replace_proof(cursor, evidence_ref=changed_ref.model_dump(mode="json"))
    changed = changed.model_copy(
        update={
            "evidence_bundle_ref": str(changed_ref.artifact_id),
            "ingestion_run_id": str(changed_ref.artifact_id),
        }
    )
    native.install(changed)
    index = native.index_bytes()
    native.assert_refused(native.run(), changed, index)

    if mutation == "wrong_profile":
        import polisyos.fabric.evidence as evidence_owner

        # Controlled removal: replay the previous ID-only intake over the same
        # actual CAS graph bytes. No producer, payload or graph is fabricated.
        def legacy_graph_load(actual_store, ref, **kwargs):
            del kwargs  # Deliberately remove the binding consumers' strict-profile flag.
            graph = ProvenanceCoreGraph.from_dict(
                load_core_json_artifact(actual_store, ArtifactID.model_validate(ref.artifact_id))
            )
            assert graph.graph_id == ref.graph_id
            assert graph.compute_stable_id() == ref.stable_id
            return graph

        with monkeypatch.context() as removal:
            removal.setattr(evidence_owner, "load_provenance_graph", legacy_graph_load)
            native.assert_complete(native.run(), [_FIRST])
            assert native.requests[-1].incremental_since.value == "a8"
        native.install(changed)
        index = native.index_bytes()
        native.assert_refused(native.run(), changed, index)


def test_native_selected_graph_survives_a_different_default_manifest(
    native_batch, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polisyos.fabric.ingestion.ingestion as ingestion_owner

    native = native_batch()
    real_persist = ingestion_owner.persist_provenance_graph
    selected_graphs = []

    def seed_default_then_persist(store, graph, **kwargs):
        shadow = store.put_json(
            graph.to_dict(),
            ArtifactWriteOptions(
                kind=_SHADOW_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=_SHADOW_KIND, version="1.0"),
            ),
            return_selected_profile=True,
        )
        actual = real_persist(store, graph, **kwargs)
        selector = ArtifactRef(
            artifact_id=ArtifactID.model_validate(actual.artifact_id),
            kind="fabric.provenance_graph",
            media_type="application/json",
            manifest_profile_sha256=actual.manifest_profile_sha256,
        )
        assert actual.manifest_profile_sha256 is not None
        assert shadow.artifact_id == selector.artifact_id
        assert shadow.manifest_profile_sha256 != selector.manifest_profile_sha256
        assert store.get_manifest(selector.artifact_id).kind == _SHADOW_KIND
        assert store.get_manifest(selector).kind == "fabric.provenance_graph"
        selected_graphs.append(actual)
        return actual

    monkeypatch.setattr(ingestion_owner, "persist_provenance_graph", seed_default_then_persist)
    native.assert_complete(native.run(), [_FIRST])
    write_source_history(native.reader, [("a8", [_FIRST]), ("a9", [_FIRST, _SECOND])])
    native.assert_complete(native.run(), [_FIRST, _SECOND])
    assert native.requests[-1].incremental_since.value == "a8"
    for ref in selected_graphs:
        assert load_provenance_graph(native.store(), ref).graph_id == ref.graph_id


def test_native_timestamp_cursor_preserves_delayed_source_time(native_batch) -> None:
    delayed = datetime(2020, 6, 1, tzinfo=UTC)
    later = delayed + timedelta(hours=12)
    native = native_batch(
        version_strategy=VersionStrategy.TIMESTAMP,
        source_time=delayed,
        snapshots=[(delayed.isoformat(), [dict(_FIRST)])],
    )

    def assert_source_time(cursor: CursorState, source_time: datetime) -> None:
        store = native.store()
        proof = cursor.metadata["source_progress"]
        payload_ref = ArtifactRef.model_validate(proof["payload_ref"])
        persisted = ResultSerializer.deserialize(store.get_bytes(payload_ref))
        assert persisted.version.strategy is VersionStrategy.TIMESTAMP
        assert persisted.version.value == source_time.isoformat()
        assert persisted.version.timestamp == source_time
        assert persisted.source_updated_at == source_time
        bundle = EvidenceBundle.model_validate(
            load_core_json_artifact(store, EvidenceBundleRef.model_validate(proof["evidence_ref"]))
        )
        ref = bundle.provenance_ref
        assert ref is not None
        graph = load_provenance_graph(store, ref)
        entity = graph.entities["dataset.rest.json.events"]
        assert entity.attributes["source_updated_at"] == source_time.isoformat()
        assert entity.attributes["version_value"] == source_time.isoformat()
        assert cursor.watermark_type is WatermarkType.TIMESTAMP
        assert cursor.watermark_value == source_time.isoformat()
        assert cursor.created_at > later

    first = native.assert_complete(native.run(), [_FIRST])
    assert_source_time(first, delayed)
    write_source_history(
        native.reader,
        [(delayed.isoformat(), [_FIRST]), (later.isoformat(), [_FIRST, _SECOND])],
        source_time=later,
    )
    second = native.assert_complete(native.run(), [_FIRST, _SECOND])
    assert_source_time(second, later)
    predecessor = native.requests[-1].incremental_since
    assert predecessor is not None
    assert predecessor.strategy is VersionStrategy.TIMESTAMP
    assert predecessor.value == delayed.isoformat()
    assert predecessor.timestamp == delayed


def test_native_cursor_cas_failure_precedes_index_update(
    native_batch, monkeypatch: pytest.MonkeyPatch
) -> None:
    native = native_batch()
    prior = native.assert_complete(native.run(), [_FIRST])
    index = native.index_bytes()
    write_source_history(native.reader, [("a8", [_FIRST]), ("a9", [_FIRST, _SECOND])])
    events = []
    real_put = FileSystemCAS.put_json
    real_index = CursorStore._save_index_unlocked

    def fail_cursor_put(store, obj, opts, canon_spec=None, **kwargs):
        if opts.kind == "fabric.cursor_state":
            events.append("cursor_cas_attempt")
            raise OSError("native cursor CAS failure")
        return real_put(store, obj, opts, canon_spec, **kwargs)

    def observe_index(cursor_store, updated):
        events.append("cursor_index_write")
        return real_index(cursor_store, updated)

    monkeypatch.setattr(FileSystemCAS, "put_json", fail_cursor_put)
    monkeypatch.setattr(CursorStore, "_save_index_unlocked", observe_index)
    with pytest.raises(OSError, match="native cursor CAS failure"):
        native.run()
    assert events == ["cursor_cas_attempt"]
    assert native.cursor() == prior
    assert native.index_bytes() == index
    assert native.requests[-1].incremental_since.value == "a8"


def test_native_stale_batch_cannot_replace_committed_successor(
    native_batch, monkeypatch: pytest.MonkeyPatch
) -> None:
    native = native_batch()
    prior = native.assert_complete(native.run(), [_FIRST])
    write_source_history(native.reader, [("a8", [_FIRST]), ("a9", [_FIRST, _SECOND])])
    real_save = CursorStore.save_cursor_if_unchanged
    at_barrier = False
    newer = []

    def complete_newer_before_save(cursor_store, cursor, *, expected_cursor):
        nonlocal at_barrier
        assert expected_cursor == prior
        if not at_barrier:
            at_barrier = True
            # Both invocations execute their actual source fetch and producer.
            # The second commits while the first is paused before its CAS lock.
            result = native.run()
            committed = native.assert_complete(result, [_FIRST, _SECOND])
            newer.append((committed, native.index_bytes()))
        return real_save(cursor_store, cursor, expected_cursor=expected_cursor)

    monkeypatch.setattr(CursorStore, "save_cursor_if_unchanged", complete_newer_before_save)
    older = native.run()
    assert len(newer) == 1
    committed, index = newer[0]
    assert committed.watermark_value == "a9"
    assert committed != prior
    assert older.status == "partial"
    assert older.cursor_ref is None and older.data_snapshot_ref is None
    assert "source_cursor_predecessor_changed:rest.json:events" in older.warnings
    assert native.cursor() == committed
    assert native.index_bytes() == index
    assert [request.incremental_since.value for request in native.requests[-2:]] == ["a8", "a8"]


@pytest.mark.parametrize("mutation", ["wrong_kind", "wrong_schema_name", "wrong_schema_version"])
def test_native_retained_evidence_requires_its_owner_schema(native_batch, mutation: str) -> None:
    native = native_batch()
    cursor = native.assert_complete(native.run(), [_FIRST])
    evidence_ref = EvidenceBundleRef.model_validate(
        cursor.metadata["source_progress"]["evidence_ref"]
    )
    wrong_view = _same_blob_evidence_view(native.store(), evidence_ref, mutation)
    changed = _replace_proof(cursor, evidence_ref=wrong_view.model_dump(mode="json"))
    native.install(changed)
    index = native.index_bytes()
    native.assert_refused(native.run(), changed, index)


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_kind",
        "wrong_schema_name",
        "wrong_schema_version",
        "missing_selected_manifest",
        "corrupt_blob",
    ],
)
def test_native_result_evidence_loss_is_withheld(
    native_batch, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    import polisyos.fabric.data_plane.orchestrator as orchestrator_owner

    native = native_batch()
    prior = native.assert_complete(native.run(), [_FIRST])
    index = native.index_bytes()
    write_source_history(native.reader, [("a8", [_FIRST]), ("a9", [_FIRST, _SECOND])])
    real_orchestrator = orchestrator_owner.run_orchestrated_ingestion
    saved_members: list[tuple[Path, bytes]] = []
    produced_refs: list[EvidenceBundleRef] = []

    def mutate_after_actual_ingestion(**kwargs):
        result = real_orchestrator(**kwargs)
        ref = result.evidence_bundle_ref
        assert isinstance(ref, EvidenceBundleRef)
        assert ref.manifest_profile_sha256 is not None
        store = native.store()
        assert store.get_manifest(ref).artifact_schema == SchemaInfo(
            name="fabric.evidence_bundle", version="2.0"
        )
        bundle = EvidenceBundle.model_validate(load_core_json_artifact(store, ref))
        assert bundle.sources and bundle.provenance_ref is not None
        produced_refs.append(ref)
        if mutation in {"wrong_kind", "wrong_schema_name", "wrong_schema_version"}:
            result.evidence_bundle_ref = _same_blob_evidence_view(store, ref, mutation)
        else:
            member = (
                store._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256)
                if mutation == "missing_selected_manifest"
                else store._paths(ref.artifact_id)[0]
            )
            assert not member.is_symlink()
            assert member.resolve().is_relative_to(native.cas_root.resolve())
            assert member.stat().st_nlink == 1
            saved_members.append((member, member.read_bytes()))
            if mutation == "missing_selected_manifest":
                member.unlink()
            else:
                member.write_bytes(b'{"corrupted_evidence":true}\n')
        return result

    try:
        with monkeypatch.context() as fault:
            fault.setattr(
                orchestrator_owner, "run_orchestrated_ingestion", mutate_after_actual_ingestion
            )
            result = native.run()
        assert len(produced_refs) == 1
        assert result.status == "partial"
        assert result.evidence_bundle_ref is None
        assert result.cursor_ref is None and result.data_snapshot_ref is None
        warning = (
            "source_evidence_unavailable"
            if mutation == "missing_selected_manifest"
            else "source_evidence_invalid"
        )
        assert warning in result.warnings
        assert native.cursor() == prior
        assert native.index_bytes() == index
        assert native.requests[-1].incremental_since.value == "a8"
    finally:
        for member, raw in saved_members:
            member.write_bytes(raw)

    assert native.store().verify(produced_refs[0]).ok
    current = native.assert_complete(native.run(), [_FIRST, _SECOND])
    assert current.watermark_value == "a9"
    assert native.requests[-1].incremental_since.value == "a8"
