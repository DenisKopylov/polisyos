"""Test-first witnesses for CAS first-writer identity and bounded lock ownership."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions


PAYLOAD = b"cas-01-first-writer-payload"


def _options(
    kind: str,
    media_type: str,
    *,
    producer_version: str = "1.0",
    schema_name: str | None = None,
) -> PutOptions:
    """Build a manifest profile with deliberate provenance differences."""
    return PutOptions(
        kind=kind,
        media_type=media_type,
        schema=SchemaInfo(name=schema_name or kind, version="1"),
        producer=ProducerInfo(component="tests.cas01", version=producer_version),
    )


def _synthetic_artifact_id(index: int) -> ArtifactID:
    """Return a deterministic lock key without writing any CAS bytes."""
    return ArtifactID.from_sha256_hex(f"{index:064x}")


def _assert_manifest_profile(
    manifest: ArtifactManifest,
    options: PutOptions,
    *,
    data: bytes,
) -> None:
    """Assert every persisted write-option field, not only the ref projection."""
    assert manifest.kind == options.kind
    assert manifest.media_type == options.media_type
    assert manifest.byte_size == len(data)
    assert manifest.artifact_schema == options.schema
    assert manifest.canon == options.canon
    assert manifest.inputs == list(options.inputs or [])
    assert manifest.producer == options.producer
    assert manifest.env == options.env
    assert manifest.governance == options.governance
    assert manifest.tenant_context == options.tenant_context
    assert manifest.same_input_closure == options.same_input_closure
    assert manifest.authority == options.authority
    assert manifest.integrity.sha256 == manifest.artifact_id.hex
    assert manifest.warnings == []


def test_reuse_does_not_return_profile_absent_from_first_manifest(tmp_path: Path) -> None:
    """A content hit cannot silently discard a second schema or producer profile."""
    store = FileSystemCAS(tmp_path / "cas")
    first_options = _options(
        "cas.first_writer",
        "application/json",
        producer_version="first",
        schema_name="cas.first.v1",
    )
    second_options = _options(
        "cas.first_writer",
        "application/json",
        producer_version="second",
        schema_name="cas.second.v1",
    )

    first_ref = store.put_bytes(PAYLOAD, first_options)
    first_manifest = store.get_manifest(first_ref.artifact_id)

    with pytest.raises(ValueError):
        store.put_bytes(PAYLOAD, second_options)

    _assert_manifest_profile(first_manifest, first_options, data=PAYLOAD)
    # Content identity does not authorize rewriting the complete first manifest.
    assert store.get_manifest(first_ref.artifact_id) == first_manifest


def test_reuse_with_same_profile_preserves_first_manifest_and_ref(tmp_path: Path) -> None:
    """The compatible deduplication control remains a stable first-writer reuse."""
    store = FileSystemCAS(tmp_path / "cas")
    options = _options(
        "cas.same_profile",
        "application/json",
        producer_version="same",
        schema_name="cas.same.v1",
    )

    first_ref = store.put_bytes(PAYLOAD, options)
    first_manifest = store.get_manifest(first_ref.artifact_id)
    second_ref = store.put_bytes(PAYLOAD, options)

    assert second_ref == first_ref
    assert store.get_manifest(first_ref.artifact_id) == first_manifest


def test_existing_corrupt_blob_is_not_confirmed_by_successful_retry(tmp_path: Path) -> None:
    """A retry must fail closed or complete an independently verified repair."""
    store = FileSystemCAS(tmp_path / "cas")
    options = _options("cas.corrupt_retry", "application/octet-stream")
    first_ref = store.put_bytes(PAYLOAD, options)
    blob_path, _manifest_path = store.get_paths(first_ref.artifact_id)
    blob_path.write_bytes(PAYLOAD + b"-corrupted")

    try:
        retry_ref = store.put_bytes(PAYLOAD, options)
    except ValueError:
        # The conservative first implementation may quarantine and reject repair.
        assert store.verify(first_ref.artifact_id).ok is False
    else:
        # A permitted recovery path must not return success until bytes are valid.
        assert retry_ref.artifact_id == first_ref.artifact_id
        assert store.get_bytes(retry_ref.artifact_id) == PAYLOAD
        assert store.verify(retry_ref.artifact_id).ok is True


def test_concurrent_writers_publish_only_the_persisted_first_writer_profile(
    tmp_path: Path,
) -> None:
    """Concurrent same-content writers cannot discard the first schema or producer."""
    store = FileSystemCAS(tmp_path / "cas")
    first_options = _options(
        "cas.concurrent",
        "application/json",
        producer_version="first",
        schema_name="cas.concurrent.first.v1",
    )
    second_options = _options(
        "cas.concurrent",
        "application/json",
        producer_version="second",
        schema_name="cas.concurrent.second.v1",
    )
    first_blob_write_started = threading.Event()
    release_first_blob_write = threading.Event()
    second_writer_started = threading.Event()
    outcome_guard = threading.Lock()
    outcomes: dict[str, ArtifactRef | Exception] = {}

    original_write_once = store._files.write_once

    def _gated_write_once(path: Path, data: bytes) -> bool:
        if path.suffix == ".blob" and threading.current_thread().name == "cas-first":
            first_blob_write_started.set()
            release_first_blob_write.wait(timeout=5)
        return original_write_once(path, data)

    store._files.write_once = _gated_write_once  # type: ignore[method-assign]

    def _writer(name: str, write_options: PutOptions, started: threading.Event) -> None:
        started.set()
        try:
            result = store.put_bytes(PAYLOAD, write_options)
        except Exception as exc:  # pragma: no cover - asserted through outcomes below
            result = exc
        with outcome_guard:
            outcomes[name] = result

    first_thread_started = threading.Event()
    first_thread = threading.Thread(
        target=_writer,
        args=("cas-first", first_options, first_thread_started),
        name="cas-first",
        daemon=True,
    )
    second_thread = threading.Thread(
        target=_writer,
        args=("cas-second", second_options, second_writer_started),
        name="cas-second",
        daemon=True,
    )
    first_thread.start()
    try:
        assert first_thread_started.wait(timeout=2)
        assert first_blob_write_started.wait(timeout=2)
        second_thread.start()
        assert second_writer_started.wait(timeout=2)
    finally:
        release_first_blob_write.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert set(outcomes) == {"cas-first", "cas-second"}
    assert isinstance(outcomes["cas-first"], ArtifactRef)
    assert isinstance(outcomes["cas-second"], ValueError)

    first_ref = outcomes["cas-first"]
    assert isinstance(first_ref, ArtifactRef)
    artifact_id = first_ref.artifact_id
    manifest = store.get_manifest(artifact_id)
    _assert_manifest_profile(manifest, first_options, data=PAYLOAD)


def test_lock_registry_is_bounded_without_evicting_active_waiters(tmp_path: Path) -> None:
    """A bounded registry retains the same lock for a live holder and waiter."""
    store = FileSystemCAS(tmp_path / "cas")
    active_id = ArtifactID.from_sha256_hex("a" * 64)
    held_lock = store._artifact_lock(active_id)
    held_lock.acquire()
    waiter_started = threading.Event()
    waiter_acquired = threading.Event()

    def _waiter() -> None:
        candidate = store._artifact_lock(active_id)
        waiter_started.set()
        candidate.acquire()
        try:
            waiter_acquired.set()
        finally:
            candidate.release()

    waiter = threading.Thread(target=_waiter, daemon=True)
    waiter.start()
    try:
        assert waiter_started.wait(timeout=2)
        assert not waiter_acquired.is_set()

        # Artificial pressure cap: only lock objects are created; no files are written.
        key_count = 128
        for index in range(key_count):
            store._artifact_lock(_synthetic_artifact_id(index))

        assert store._artifact_lock(active_id) is held_lock
        assert len(store._artifact_locks) <= key_count
        assert not waiter_acquired.is_set()
    finally:
        held_lock.release()
        waiter.join(timeout=2)

    assert not waiter.is_alive()
    assert waiter_acquired.is_set()
