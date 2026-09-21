"""Test-first witnesses for CAS first-writer identity and bounded lock ownership."""

from __future__ import annotations

import threading
from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, ProducerInfo, SchemaInfo
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


def test_reuse_does_not_return_profile_absent_from_first_manifest(tmp_path: Path) -> None:
    """A content hit cannot claim a second persisted kind or provenance profile."""
    store = FileSystemCAS(tmp_path / "cas")
    first_options = _options(
        "cas.first_writer",
        "application/json",
        producer_version="first",
        schema_name="cas.first.v1",
    )
    second_options = _options(
        "cas.second_writer",
        "text/plain",
        producer_version="second",
        schema_name="cas.second.v1",
    )

    first_ref = store.put_bytes(PAYLOAD, first_options)
    first_manifest = store.get_manifest(first_ref.artifact_id)

    try:
        second_ref = store.put_bytes(PAYLOAD, second_options)
    except ValueError as exc:
        # An explicit profile conflict is an allowed fail-closed outcome.
        detail = str(exc).casefold()
        assert "profile" in detail or "manifest" in detail
    else:
        assert (second_ref.kind, second_ref.media_type) == (
            first_manifest.kind,
            first_manifest.media_type,
        )

    # Content identity does not authorize rewriting the first writer's provenance.
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
    """Concurrent same-content writers cannot return mutually inconsistent refs."""
    store = FileSystemCAS(tmp_path / "cas")
    options = (
        _options("cas.concurrent_a", "application/json", producer_version="a"),
        _options("cas.concurrent_b", "text/plain", producer_version="b"),
    )
    barrier = threading.Barrier(len(options))
    outcome_guard = threading.Lock()
    outcomes: list[ArtifactRef | Exception] = []

    def _writer(write_options: PutOptions) -> None:
        try:
            barrier.wait(timeout=5)
            result = store.put_bytes(PAYLOAD, write_options)
        except Exception as exc:  # pragma: no cover - asserted through outcomes below
            result = exc
        with outcome_guard:
            outcomes.append(result)

    threads = [threading.Thread(target=_writer, args=(item,), daemon=True) for item in options]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert len(outcomes) == len(options)
    successes = [item for item in outcomes if isinstance(item, ArtifactRef)]
    failures = [item for item in outcomes if isinstance(item, Exception)]
    assert successes
    assert all(isinstance(item, ValueError) for item in failures)

    artifact_id = successes[0].artifact_id
    manifest = store.get_manifest(artifact_id)
    assert all(
        (item.kind, item.media_type) == (manifest.kind, manifest.media_type)
        for item in successes
    )
    assert (manifest.kind, manifest.media_type) in {
        (item.kind, item.media_type) for item in options
    }


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
