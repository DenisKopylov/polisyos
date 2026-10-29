"""Behavioral negatives for finite source-owner progress admission."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.cursor import CursorState, WatermarkType
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.contracts.source_contract import SourceDeprecationPolicy
from polisyos.fabric.data_plane.cursor_store import CursorStore, CursorStoreConflict
from polisyos.fabric.data_plane.modes import _cursor_version
from polisyos.fabric.ingestion.source_progress import (
    FiniteSourceProgressReader,
    SourceProgressAdmissionError,
    resolve_source_progress_frame,
)
from polisyos.ir.connectors import DataVersion, FetchRequest, FetchResult, VersionStrategy
from tests._helpers.source_progress import SOURCE_TIME, finite_source_reader


def _owner(tmp_path: Path) -> FiniteSourceProgressReader:
    return finite_source_reader(
        tmp_path,
        connector_id="rest.json",
        dataset_id="events",
        schema_id="fixture.events",
        snapshots=[
            ("a8", []),
            (
                "a9",
                [
                    {"event_id": "one", "source_version": "1"},
                    {"event_id": "two", "source_version": "2"},
                ],
            ),
        ],
    )


def _result(rows: list[dict[str, str]]) -> FetchResult[list[dict[str, str]]]:
    return FetchResult(
        data=rows,
        row_count=len(rows),
        schema_id="fixture.events",
        schema_version="1.0.0",
        version=DataVersion(strategy=VersionStrategy.ETAG, value="a9", timestamp=SOURCE_TIME),
        fetched_at=SOURCE_TIME,
        completeness=1.0,
    )


def test_source_progress_reconciles_the_complete_actual_owner_file(tmp_path: Path) -> None:
    reader = _owner(tmp_path)
    frame = reader.freeze(tenant_id="tenant-a").bind_transport(
        ConnectionConfig(url=reader.fixture_path.as_uri())
    )
    rows = [
        {"event_id": "one", "source_version": "1"},
        {"event_id": "two", "source_version": "2"},
    ]
    admitted = frame.reconcile_fetch(FetchRequest(dataset_id="events"), _result(rows))
    assert admitted.data == rows
    assert admitted.row_count == 2
    assert frame.extension.admission_scope == "finite_source_fixture"

    # Keep completeness=1 and source version/owner declarations intact; omit
    # an ACTUAL source member from connector output, not an expected-ID list.
    with pytest.raises(SourceProgressAdmissionError, match="source_progress_not_reconciled"):
        frame.reconcile_fetch(FetchRequest(dataset_id="events"), _result(rows[:1]))
    with pytest.raises(SourceProgressAdmissionError):
        frame.reconcile_fetch(FetchRequest(dataset_id="other"), _result(rows))


@pytest.mark.parametrize(
    "field", ["source_contract_content_hash", "schema_content_hash", "connector_id"]
)
def test_source_progress_refuses_changed_owner_bindings(tmp_path: Path, field: str) -> None:
    reader = _owner(tmp_path)
    value = "sha256:" + "0" * 64 if field.endswith("hash") else "other.source"
    extension = reader.extension.model_copy(update={field: value})
    with pytest.raises(ValueError, match="identity differs"):
        replace(reader, extension=extension).freeze(tenant_id="tenant-a")


def test_source_progress_refuses_duplicate_readers_without_choosing_one(tmp_path: Path) -> None:
    reader = _owner(tmp_path)
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_source_progress_frame(
            (reader, reader), connector_id="rest.json", dataset_id="events", tenant_id=None
        )


@pytest.mark.parametrize(
    "watermark", [WatermarkType.ETAG, WatermarkType.REVISION, WatermarkType.TIMESTAMP]
)
def test_unverified_legacy_cursors_never_create_incremental_authority(
    tmp_path: Path, watermark: WatermarkType
) -> None:
    from polisyos.fabric.connectors.sources.rest_json import RestJsonConnector

    cursor = CursorState(
        cursor_id="rest.json:events",
        connector_id="rest.json",
        dataset_id="events",
        watermark_type=watermark,
        watermark_value="123",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert _cursor_version(cursor, RestJsonConnector()) is None
    assert (
        _cursor_version(
            cursor,
            RestJsonConnector(),
            frame=_owner(tmp_path / "owner").freeze(tenant_id=None),
            store=FileSystemCAS(tmp_path / "cas"),
        )
        is None
    )


def test_cursor_promotion_cannot_overwrite_a_newer_process_predecessor(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    cursor = CursorState(
        cursor_id="rest.json:events",
        connector_id="rest.json",
        dataset_id="events",
        watermark_type=WatermarkType.ETAG,
        watermark_value="a8",
        created_at=SOURCE_TIME,
    )
    CursorStore(store).save_cursor_if_unchanged(cursor, expected_cursor=None)
    later = cursor.model_copy(update={"watermark_value": "a10"})
    CursorStore(store).save_cursor_if_unchanged(later, expected_cursor=cursor)
    with pytest.raises(CursorStoreConflict):
        CursorStore(store).save_cursor_if_unchanged(
            cursor.model_copy(update={"watermark_value": "a9"}), expected_cursor=cursor
        )
    assert (
        CursorStore(FileSystemCAS(tmp_path / "cas")).find_latest_cursor("rest.json", "events")
        == later
    )


def test_owner_movement_refuses_instead_of_reusing_a_frozen_premise(tmp_path: Path) -> None:
    reader = _owner(tmp_path)
    frame = reader.freeze(tenant_id=None).bind_transport(
        ConnectionConfig(url=reader.fixture_path.as_uri())
    )
    reader.fixture_path.write_text(reader.fixture_path.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        frame.assert_current()


def test_same_entity_at_distinct_source_versions_has_distinct_owned_keys(tmp_path: Path) -> None:
    rows = [
        {"event_id": "same-entity", "source_version": "1"},
        {"event_id": "same-entity", "source_version": "2"},
    ]
    reader = finite_source_reader(
        tmp_path,
        connector_id="rest.json",
        dataset_id="events",
        schema_id="fixture.events",
        snapshots=[("a9", rows)],
    )
    frame = reader.freeze(tenant_id=None).bind_transport(
        ConnectionConfig(url=reader.fixture_path.as_uri())
    )
    frame.admit_stream_rows(rows)
    with pytest.raises(ValueError, match="absent"):
        frame.admit_stream_rows([{"event_id": "same-entity", "source_version": "3"}])


@pytest.mark.asyncio
async def test_disabled_idempotency_is_explicitly_non_deduping(tmp_path: Path) -> None:
    import json

    from polisyos.core.contracts.cursor import WindowStrategy
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.data_plane.streaming import StreamRuntimeOptions, process_stream_dataset
    from polisyos.fabric.data_plane.watermark import WindowPolicy
    from polisyos.fabric.quality.processing_guarantees import stream_processing_contract

    row = {"entity_id": "same-entity", "value": "candidate-only"}
    path = tmp_path / "stream.jsonl"
    path.write_text((json.dumps(row) + "\n") * 2, encoding="utf-8")
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config("stream.jsonl", ConnectionConfig(url=path.as_uri()))
    contract = stream_processing_contract()
    contract = contract.model_copy(
        update={
            "idempotency": contract.idempotency.model_copy(update={"enabled": False}),
        }
    )
    store = FileSystemCAS(tmp_path / "cas")

    def valid_rows(batch, **kwargs):
        del kwargs
        return list(batch), [], 0

    try:
        result = await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="events",
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=valid_rows,
            runtime_options=StreamRuntimeOptions(
                processing_contract=contract,
                window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
            ),
            registry=registry,
        )
        assert result.processing_guarantee == "at_least_once"
        assert result.rows_emitted == 2 and result.dedupe_dropped == 0
        assert result.final_checkpoint.metadata["processing"]["idempotency"]["enabled"] is False
        metadata = dict(result.final_checkpoint.metadata)
        metadata.pop("ingestion_clock_profile", None)
        metadata.pop("frontier_intent", None)
        CursorStore(store).save_stream_checkpoint(
            result.final_checkpoint.model_copy(update={"metadata": metadata})
        )
        resumed = await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="events",
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=valid_rows,
            runtime_options=StreamRuntimeOptions(
                processing_contract=contract,
                window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
            ),
            registry=registry,
        )
        assert resumed.processing_guarantee == "at_least_once"
        assert resumed.dedupe_dropped == 0
    finally:
        await registry.shutdown_async()


def test_owner_header_cannot_hide_a_later_actual_source_snapshot(tmp_path: Path) -> None:
    import json

    reader = _owner(tmp_path)
    payload = json.loads(reader.fixture_path.read_text())
    payload["current_version"] = "a8"
    # Both actual a9 members remain in the complete owner file. A current-head
    # declaration cannot hide them or turn the empty a8 snapshot into progress.
    reader.fixture_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="final actual owner snapshot"):
        reader.freeze(tenant_id=None)


@pytest.mark.parametrize("status", ["draft", "deprecated", "sunset"])
def test_nonactive_source_status_cannot_bind_even_with_matching_content_hash(
    tmp_path: Path, status: str
) -> None:
    reader = _owner(tmp_path)
    deprecation = None
    if status in {"deprecated", "sunset"}:
        deprecation = SourceDeprecationPolicy(
            deprecated_at=datetime(2026, 1, 1, tzinfo=UTC),
            sunset_at=datetime(2030, 1, 1, tzinfo=UTC),
            reason="fixture status mismatch",
            migration_note="Use the active fixture contract",
        )
    source = reader.source_contract.model_copy(
        update={"status": status, "deprecation": deprecation}
    )
    extension = reader.extension.model_copy(
        update={"source_contract_content_hash": source.content_hash}
    )
    with pytest.raises(ValueError, match="identity differs"):
        replace(reader, source_contract=source, extension=extension).freeze(tenant_id=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["hidden_actual_event", "wrong_partition", "different_file"])
async def test_actual_jsonl_universe_and_partition_are_reconciled_before_effects(
    tmp_path: Path, mismatch: str
) -> None:
    import json

    from polisyos.core.contracts.cursor import WindowStrategy
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.data_plane.streaming import (
        StreamDedupeUnsupported,
        StreamRuntimeOptions,
        process_stream_dataset,
    )
    from polisyos.fabric.data_plane.watermark import WindowPolicy

    rows = [{"event_id": value, "source_version": "1"} for value in ("A", "B", "C")]
    path = tmp_path / "actual.jsonl"
    path.write_text(
        "".join(
            json.dumps(row) + "\n"
            for row in rows
            if mismatch == "hidden_actual_event" or row["event_id"] != "C"
        )
    )
    reader = finite_source_reader(
        tmp_path / "owner",
        connector_id="stream.jsonl",
        dataset_id="events",
        schema_id="fixture.events",
        snapshots=[("a9", rows[:2])],
        transport_path=path,
    )
    other_path = tmp_path / "same-bytes-other-source.jsonl"
    other_path.write_bytes(path.read_bytes())
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl",
        ConnectionConfig(
            url=(other_path if mismatch == "different_file" else path).as_uri(),
            headers={"X-Stream-ChunkSize": "1"},
        ),
    )
    store = FileSystemCAS(tmp_path / "cas")
    before = set(map(str, store.iter_artifact_ids()))

    def valid(batch, **kwargs):
        del kwargs
        return list(batch), [], 0

    try:
        with pytest.raises(StreamDedupeUnsupported, match="transport"):
            await process_stream_dataset(
                connector_id="stream.jsonl",
                dataset_id="events",
                store=store,
                cursor_store=CursorStore(store),
                sanitize_rows=valid,
                registry=registry,
                runtime_options=StreamRuntimeOptions(
                    partition_key="other" if mismatch == "wrong_partition" else "default",
                    window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1),
                ),
                source_progress_readers=(reader,),
            )
        assert set(map(str, store.iter_artifact_ids())) == before
        assert CursorStore(store).find_latest_cursor("stream.jsonl", "events") is None
    finally:
        await registry.shutdown_async()


@pytest.mark.asyncio
async def test_finite_stream_scope_survives_actual_chunk_and_window_consumption(
    tmp_path: Path,
) -> None:
    import json

    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.contracts.cursor import WindowStrategy
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.data_plane.streaming import StreamRuntimeOptions, process_stream_dataset
    from polisyos.fabric.data_plane.watermark import WindowPolicy
    from polisyos.fabric.ingestion.source_progress import load_source_progress_witness

    rows = [{"event_id": value, "source_version": "1"} for value in ("A", "B")]
    path = tmp_path / "actual.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    reader = finite_source_reader(
        tmp_path / "owner",
        connector_id="stream.jsonl",
        dataset_id="events",
        schema_id="fixture.events",
        snapshots=[("a9", rows)],
        transport_path=path,
    )
    ConnectorRegistry.reset_instance()
    registry = ConnectorRegistry.get_instance()
    registry.set_default_config(
        "stream.jsonl", ConnectionConfig(url=path.as_uri(), headers={"X-Stream-ChunkSize": "1"})
    )
    store = FileSystemCAS(tmp_path / "cas")

    def valid(batch, **kwargs):
        del kwargs
        return list(batch), [], 0

    try:
        result = await process_stream_dataset(
            connector_id="stream.jsonl",
            dataset_id="events",
            store=store,
            cursor_store=CursorStore(store),
            sanitize_rows=valid,
            registry=registry,
            runtime_options=StreamRuntimeOptions(
                window_policy=WindowPolicy(strategy=WindowStrategy.COUNT, size=1)
            ),
            source_progress_readers=(reader,),
        )
        assert result.processing_guarantee == "replay_only"
        assert result.rows_emitted == 2
        assert result.chunk_refs and result.window_refs
        for ref in [*result.chunk_refs, *result.window_refs, *result.cdc_event_refs]:
            payload = load_core_json_artifact(store, ref)
            scope = payload["source_progress"]
            assert scope["admission_scope"] == "finite_source_fixture"
            assert scope["production_currentness"] == "not_established"
            witness_ref = ArtifactRef.model_validate(scope["source_witness_ref"])
            restored = load_source_progress_witness(store, witness_ref)
            assert restored.extension == reader.extension
            assert {row["event_id"] for row in restored.current.rows} == {"A", "B"}
    finally:
        await registry.shutdown_async()


def test_source_evidence_schema_uses_persisted_typed_field_and_refuses_absence(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.contracts.fabric import EvidenceBundle, EvidenceBundleRef
    from polisyos.fabric.ingestion._source_evidence_schema import (
        require_source_evidence_schema,
    )
    from polisyos.fabric.ingestion.source_collection import materialize_source_collection
    from polisyos.fabric.ingestion.source_progress import project_partial_source_scope

    store = FileSystemCAS(tmp_path / "cas")
    expected = SchemaInfo(name="fabric.evidence_bundle", version="1.0")
    typed_ref = store.put_json(
        EvidenceBundle(),
        ArtifactWriteOptions(
            kind="fabric.evidence_bundle",
            media_type="application/json",
            schema=expected,
        ),
        return_selected_profile=True,
    )
    typed_manifest = store.get_manifest(typed_ref)
    assert require_source_evidence_schema(typed_manifest) == expected

    missing_ref = store.put_json(
        EvidenceBundle(),
        ArtifactWriteOptions(kind="fabric.evidence_bundle", media_type="application/json"),
        return_selected_profile=True,
    )
    missing_manifest = store.get_manifest(missing_ref)
    assert missing_manifest.artifact_schema is None
    with pytest.raises(ValueError, match="no schema information"):
        require_source_evidence_schema(missing_manifest)

    before_projection = set(map(str, store.iter_artifact_ids()))
    with pytest.raises(ValueError, match="no schema information"):
        project_partial_source_scope(
            store,
            EvidenceBundleRef.model_validate(missing_ref.model_dump(mode="python")),
            frames={},
            advanced=set(),
        )
    assert set(map(str, store.iter_artifact_ids())) == before_projection

    with pytest.raises(ValueError, match="no schema information"):
        materialize_source_collection(
            store=store,
            evidence_ref=EvidenceBundleRef.model_validate(missing_ref.model_dump(mode="python")),
            datasets=(),
            persisted_results={},
            frames={},
        )
    assert set(map(str, store.iter_artifact_ids())) == before_projection
