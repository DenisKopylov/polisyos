"""Record/replay cache writes preserve purpose and exact selected session provenance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import (
    FileSystemCAS,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.fabric import IngestionExecutionContext
from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest, FetchResult
from polisyos.fabric.connectors.cache import ConnectorCacheStore, TTLPolicy
from polisyos.fabric.connectors.cache.store import (
    CacheSourceIntent,
    verify_selected_cache_payload_ref,
)
from polisyos.fabric.data_plane.replay_store import RecordSession, ReplayStore
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy

if TYPE_CHECKING:
    from pathlib import Path

_SESSION_ROLE = "fabric.ingestion.record_session"
_INTENT_ROLE = "fabric.connector_cache.selected_source_intent"


def _result(value: int = 1) -> FetchResult[list[dict[str, int]]]:
    now = datetime(2026, 10, 1, tzinfo=UTC)
    return FetchResult(
        data=[{"value": value}],
        row_count=1,
        schema_id="test.cache_execution",
        schema_version="1.0",
        version=DataVersion(
            strategy=VersionStrategy.TIMESTAMP, value=now.isoformat(), timestamp=now
        ),
        fetched_at=now,
        completeness=1.0,
        quality_tier=QualityTier.BRONZE,
    )


def _context(
    cas: FileSystemCAS,
    mode: Literal["record", "replay"] = "replay",
    session_id: str = "captured-session",
) -> IngestionExecutionContext:
    session_ref = None
    if mode == "replay":
        session_ref = ReplayStore(cas).save_record_session(RecordSession(session_id=session_id))
    return IngestionExecutionContext(
        mode=mode, capture_session_id=session_id, selected_record_session_ref=session_ref
    )


def _cache(
    cas: FileSystemCAS, context: IngestionExecutionContext | None = None
) -> ConnectorCacheStore:
    return ConnectorCacheStore(
        cas, TTLPolicy(ttl=timedelta(hours=1)), namespace="owned_cache", execution_context=context
    )


def _intent_ref(cas: FileSystemCAS, payload: ArtifactRef) -> ArtifactRef:
    (edge,) = [item for item in cas.get_manifest(payload).inputs if item.role == _INTENT_ROLE]
    return ArtifactRef(
        artifact_id=edge.artifact_id,
        kind="fabric.connector_cache.selected_source_intent",
        media_type="application/json",
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )


@pytest.mark.parametrize("mode", ["record", "replay"])
def test_execution_cache_namespace_and_artifacts_cannot_replace_warm_ordinary_cache(
    tmp_path: Path,
    mode: Literal["record", "replay"],
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    request = FetchRequest(dataset_id="rows")
    config = ConnectionConfig(url="https://cache-fixture.invalid/rows")
    result = _result()
    context = _context(cas, mode)
    with _cache(cas) as ordinary, _cache(cas, context) as captured:
        warm = ordinary.put(request, result, connector_id="test.source", source_config=config)
        before = ordinary.get_metadata(warm.cache_key)
        assert captured._cache_root != ordinary._cache_root
        assert captured._namespace.startswith(f"owned_cache.execution.{mode}.")
        assert captured.get(request, connector_id="test.source", source_config=config) is None
        written = captured.put(request, result, connector_id="test.source", source_config=config)
        assert ordinary.get_metadata(warm.cache_key) == before
        assert warm.payload_ref.artifact_id == written.payload_ref.artifact_id
        assert (
            warm.payload_ref.manifest_profile_sha256 != written.payload_ref.manifest_profile_sha256
        )
        assert cas.get_bytes(warm.payload_ref) == cas.get_bytes(written.payload_ref)
        assert verify_selected_cache_payload_ref(
            cas, warm.payload_ref, connector_id="test.source", request=request, source_config=config
        )
        assert not verify_selected_cache_payload_ref(
            cas,
            written.payload_ref,
            connector_id="test.source",
            request=request,
            source_config=config,
        )
        assert verify_selected_cache_payload_ref(
            cas,
            written.payload_ref,
            connector_id="test.source",
            request=request,
            source_config=config,
            execution_context=context,
            result=result,
        )
        intent_ref = _intent_ref(cas, written.payload_ref)
        intent = CacheSourceIntent.model_validate(load_core_json_artifact(cas, intent_ref))
        assert intent.contract == "fabric.connector_cache.selected_source_intent.v2"
        assert intent.execution_context == context
        assert cas.get_manifest(intent_ref).artifact_schema.version == "2.0"
        expected_session = (
            [input_ref_from_artifact_ref(context.selected_record_session_ref, role=_SESSION_ROLE)]
            if context.selected_record_session_ref is not None
            else []
        )
        metadata_manifest = cas.get_manifest(written.metadata_artifact_id)
        assert (
            input_ref_from_artifact_ref(written.payload_ref, role="connector_cache.payload")
            in metadata_manifest.inputs
        )
        for manifest in (
            cas.get_manifest(intent_ref),
            cas.get_manifest(written.payload_ref),
            metadata_manifest,
        ):
            assert [
                edge for edge in manifest.inputs if edge.role == _SESSION_ROLE
            ] == expected_session
        derived = captured.put_derived_payload(_result(2), input_payload_ref=written.payload_ref)
        derived_manifest = cas.get_manifest(derived)
        assert [
            edge for edge in derived_manifest.inputs if edge.role == _SESSION_ROLE
        ] == expected_session
        assert (
            input_ref_from_artifact_ref(written.payload_ref, role="connector_cache.raw_payload")
            in derived_manifest.inputs
        )
        assert input_ref_from_artifact_ref(intent_ref, role=_INTENT_ROLE) in derived_manifest.inputs
        assert verify_selected_cache_payload_ref(
            cas,
            derived,
            connector_id="test.source",
            request=request,
            source_config=config,
            execution_context=context,
            result=_result(2),
        )
        with pytest.raises(ValueError, match="execution_context_mismatch"):
            ordinary.put_derived_payload(_result(2), input_payload_ref=written.payload_ref)
    fresh = FileSystemCAS(tmp_path / "cas")
    with _cache(fresh) as ordinary, _cache(fresh, context) as captured:
        reopened = ordinary.get(request, connector_id="test.source", source_config=config)
        replayed = captured.get(request, connector_id="test.source", source_config=config)
        assert reopened is not None and replayed is not None
        assert reopened.metadata.payload_ref == warm.payload_ref
        assert replayed.metadata.payload_ref == written.payload_ref
        assert replayed.result.data == result.data


def test_context_snapshot_session_isolation_and_no_ordinary_index_fallback(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    context = _context(cas)
    frozen = IngestionExecutionContext.model_validate(context.model_dump(mode="python"))
    other_context = _context(cas, session_id="other-capture")
    request = FetchRequest(dataset_id="rows")
    config = ConnectionConfig(url="https://cache-fixture.invalid/rows")
    with (
        _cache(cas) as ordinary,
        _cache(cas, context) as captured,
        _cache(cas, other_context) as other,
    ):
        warm = ordinary.put(request, _result(), connector_id="test.source", source_config=config)
        original = ordinary._index.get_entry(warm.cache_key)
        captured._index.upsert_entry(original)
        assert captured.get(request, connector_id="test.source", source_config=config) is None
        assert ordinary._index.get_entry(warm.cache_key) == original
        assert captured._cache_root != other._cache_root
        context.selected_record_session_ref.kind = "mutated.by.caller"
        written = captured.put(request, _result(), connector_id="test.source", source_config=config)
        assert verify_selected_cache_payload_ref(
            cas,
            written.payload_ref,
            connector_id="test.source",
            request=request,
            source_config=config,
            execution_context=frozen,
        )
        assert other.get(request, connector_id="test.source", source_config=config) is None
        with pytest.raises(ValueError, match="execution_context_mismatch"):
            other.put_derived_payload(_result(2), input_payload_ref=written.payload_ref)


@pytest.mark.parametrize(
    "mutation",
    ["payload_session", "intent_session", "intent_schema", "intent_context", "intent_contract"],
)
def test_execution_intent_and_exact_session_edges_are_reconciled_from_real_cas(
    tmp_path: Path,
    mutation: str,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    context = _context(cas)
    request = FetchRequest(dataset_id="rows")
    config = ConnectionConfig(url="https://cache-fixture.invalid/rows")
    with _cache(cas, context) as cache:
        written = cache.put(request, _result(), connector_id="test.source", source_config=config)
    intent_ref = _intent_ref(cas, written.payload_ref)
    intent_manifest = cas.get_manifest(intent_ref)
    payload_manifest = cas.get_manifest(written.payload_ref)
    payload_inputs = list(payload_manifest.inputs)
    if mutation == "payload_session":
        payload_inputs = [edge for edge in payload_inputs if edge.role != _SESSION_ROLE]
    else:
        body: dict[str, Any] = load_core_json_artifact(cas, intent_ref)
        intent_inputs = list(intent_manifest.inputs)
        version = "2.0"
        if mutation == "intent_session":
            intent_inputs = []
        elif mutation == "intent_schema":
            version = "1.0"
        elif mutation == "intent_context":
            body["execution_context"]["capture_session_id"] = "foreign-capture"
        else:
            body["contract"] = "fabric.connector_cache.selected_source_intent.v1"
        changed_intent = cas.put_json(
            body,
            ArtifactWriteOptions(
                kind=intent_ref.kind,
                media_type=intent_ref.media_type,
                schema=SchemaInfo(
                    name="fabric.connector_cache.selected_source_intent", version=version
                ),
                inputs=intent_inputs,
            ),
            return_selected_profile=True,
        )
        payload_inputs = [
            input_ref_from_artifact_ref(changed_intent, role=_INTENT_ROLE)
            if edge.role == _INTENT_ROLE
            else edge
            for edge in payload_inputs
        ]
    changed_payload = cas.put_bytes(
        cas.get_bytes(written.payload_ref),
        ArtifactWriteOptions(
            kind=written.payload_ref.kind,
            media_type=written.payload_ref.media_type,
            schema=payload_manifest.artifact_schema,
            inputs=payload_inputs,
        ),
        return_selected_profile=True,
    )
    fresh = FileSystemCAS(tmp_path / "cas")
    assert not verify_selected_cache_payload_ref(
        fresh,
        changed_payload,
        connector_id="test.source",
        request=request,
        source_config=config,
        execution_context=context,
    )
    assert verify_selected_cache_payload_ref(
        fresh,
        written.payload_ref,
        connector_id="test.source",
        request=request,
        source_config=config,
        execution_context=context,
    )


def test_v1_source_intent_bytes_and_context_contract_boundary_stay_explicit() -> None:
    fields = {
        "contract": "fabric.connector_cache.selected_source_intent.v1",
        "connector_id": "test.source",
        "dataset_id": "rows",
        "request_key": "request",
        "source_scope_fingerprint": "sha256:" + "a" * 64,
    }
    ordinary = CacheSourceIntent.model_validate(fields)
    assert ordinary.model_dump(mode="json") == fields
    with pytest.raises(ValidationError, match="context_contract_mismatch"):
        CacheSourceIntent.model_validate(
            fields | {"contract": "fabric.connector_cache.selected_source_intent.v2"}
        )
    context = IngestionExecutionContext(mode="record", capture_session_id="recording")
    with pytest.raises(ValidationError, match="context_contract_mismatch"):
        CacheSourceIntent.model_validate(fields | {"execution_context": context})


def test_execution_put_requires_bound_source_and_missing_session_fails_before_index(
    tmp_path: Path,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    record = _context(cas, mode="record")
    with _cache(cas, record) as captured:
        before = tuple(cas.iter_artifact_ids())
        with pytest.raises(ValueError, match="requires_source_config"):
            captured.put(FetchRequest(dataset_id="rows"), _result(), connector_id="test.source")
        assert tuple(cas.iter_artifact_ids()) == before
    selected = ArtifactRef(
        artifact_id="sha256:" + "b" * 64,
        kind="fabric.record_session",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "c" * 64,
    )
    missing = IngestionExecutionContext(
        mode="replay", capture_session_id="missing", selected_record_session_ref=selected
    )
    with pytest.raises(ValueError, match="execution_session_unavailable"):
        _cache(cas, missing)


@pytest.mark.parametrize("mismatch", ["capture_id", "unknown_schema"])
def test_execution_session_binding_reads_selected_schema_and_capture_identity(
    tmp_path: Path,
    mismatch: str,
) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    context = _context(cas)
    selected = context.selected_record_session_ref
    assert selected is not None
    if mismatch == "capture_id":
        invalid = context.model_copy(update={"capture_session_id": "different-capture"})
    else:
        unknown = cas.put_json(
            load_core_json_artifact(cas, selected),
            ArtifactWriteOptions(
                kind="fabric.record_session",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.fabric.RecordSession", version="unknown"),
            ),
            return_selected_profile=True,
        )
        invalid = context.model_copy(update={"selected_record_session_ref": unknown})
    with pytest.raises(ValueError, match="execution_session_unavailable"):
        _cache(cas, invalid)
