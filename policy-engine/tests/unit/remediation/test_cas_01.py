"""Test-first witnesses for CAS first-writer identity and bounded lock ownership."""

from __future__ import annotations

import hashlib
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    IntegrityInfo,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier
from polisyos.core.artifacts.store import (
    ArtifactIntegrityError,
    FileSystemCAS,
    PutOptions,
)

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
    assert manifest.manifest_schema_version == "v3"


def test_distinct_profiles_get_honest_views_of_one_blob(tmp_path: Path) -> None:
    """The same bytes may have multiple exact metadata views without rewriting history."""
    store = FileSystemCAS(tmp_path / "cas")
    first_options = _options(
        "cas.first_writer",
        "application/json",
        producer_version="first",
        schema_name="cas.first.v1",
    )
    first_options = first_options.__class__(
        **{**first_options.__dict__, "inputs": [
            InputRef(
                artifact_id=ArtifactID.from_sha256_hex("a" * 64),
                role="first_basis",
                manifest_profile_sha256="sha256:" + "1" * 64,
            )
        ]}
    )
    second_options = _options(
        "cas.second_writer",
        "text/plain",
        producer_version="second",
        schema_name="cas.second.v1",
    )
    second_options = second_options.__class__(
        **{**second_options.__dict__, "inputs": [
            InputRef(
                artifact_id=ArtifactID.from_sha256_hex("b" * 64),
                role="second_basis",
                manifest_profile_sha256="sha256:" + "2" * 64,
            )
        ]}
    )

    first_ref = store.put_bytes(PAYLOAD, first_options)
    first_manifest = store.get_manifest(first_ref)
    second_ref = store.put_bytes(PAYLOAD, second_options)
    second_manifest = store.get_manifest(second_ref)

    assert first_ref.artifact_id == second_ref.artifact_id
    assert first_ref.kind == first_options.kind
    assert first_ref.media_type == first_options.media_type
    assert second_ref.kind == second_options.kind
    assert second_ref.media_type == second_options.media_type
    assert first_ref.manifest_profile_sha256 is None
    assert second_ref.manifest_profile_sha256 is not None
    assert second_ref.manifest_profile_sha256.startswith("sha256:")
    assert first_manifest != second_manifest
    _assert_manifest_profile(first_manifest, first_options, data=PAYLOAD)
    _assert_manifest_profile(second_manifest, second_options, data=PAYLOAD)
    # ID-only callers retain the historical first-writer view and byte identity.
    assert store.get_manifest(first_ref.artifact_id).kind == first_options.kind
    assert store.get_manifest(first_ref.artifact_id).manifest_schema_version == "v3"
    assert store.get_bytes(first_ref) == PAYLOAD
    assert store.get_bytes(second_ref) == PAYLOAD

    repeated_ref = store.put_bytes(PAYLOAD, second_options)
    assert repeated_ref == second_ref
    assert store.get_manifest(repeated_ref) == second_manifest


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
    first_manifest = store.get_manifest(first_ref)
    assert first_manifest.manifest_schema_version == "v3"
    second_ref = store.put_bytes(PAYLOAD, options)

    assert second_ref == first_ref
    assert store.get_manifest(first_ref) == first_manifest
    assert store.get_manifest(first_ref.artifact_id).kind == options.kind


def test_manifest_lifecycle_reconstructs_the_current_write_manifest(
    tmp_path: Path,
) -> None:
    """Fresh-write expectations use the same v3 schema selection as the CAS owner."""
    store = FileSystemCAS(tmp_path / "cas")
    options = _options("cas.expected.current", "application/octet-stream")
    ref = store.put_bytes(PAYLOAD, options)
    observed = store.get_manifest(ref)

    expected = ManifestLifecycle.expected_for_write(
        artifact_id=ref.artifact_id,
        data=PAYLOAD,
        opts=options,
        created_at=observed.created_at,
    )

    assert expected == observed
    assert expected.manifest_schema_version == "v3"
    assert expected.model_copy(update={"manifest_schema_version": "v2"}) != observed


def test_selectorless_refs_keep_the_historical_serialized_projection() -> None:
    artifact_id = ArtifactID.from_sha256_hex("c" * 64)
    ref = ArtifactRef(artifact_id=artifact_id, kind="legacy.ref", media_type="application/json")
    input_ref = InputRef(artifact_id=artifact_id, role="legacy_input")

    assert ref.model_dump(mode="json") == {
        "artifact_id": str(artifact_id),
        "kind": "legacy.ref",
        "media_type": "application/json",
    }
    assert input_ref.model_dump(mode="json") == {
        "artifact_id": str(artifact_id),
        "role": "legacy_input",
    }


def test_selected_input_view_requires_manifest_schema_v2() -> None:
    with pytest.raises(ValidationError, match="manifest_schema_version v2"):
        ArtifactManifest.model_validate(
            {
                "manifest_schema_version": "v1",
                "artifact_id": ArtifactID.from_sha256_hex("d" * 64),
                "kind": "cas.selected_input",
                "media_type": "application/json",
                "byte_size": len(PAYLOAD),
                "inputs": [
                    InputRef(
                        artifact_id=ArtifactID.from_sha256_hex("a" * 64),
                        role="selected_basis",
                        manifest_profile_sha256="sha256:" + "1" * 64,
                    )
                ],
                "integrity": IntegrityInfo(sha256="d" * 64),
            }
        )


def test_view_resolution_removal_fails_with_both_sidecars_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    first = store.put_bytes(PAYLOAD, _options("cas.view.first", "application/json"))
    second = store.put_bytes(PAYLOAD, _options("cas.view.second", "text/plain"))
    assert second.manifest_profile_sha256 is not None
    assert store._layout.view_manifest_path(
        second.artifact_id,
        second.manifest_profile_sha256,
    ).is_file()
    assert store._paths(second.artifact_id)[1].is_file()

    monkeypatch.setattr(
        store,
        "_manifest_path_for_ref",
        lambda artifact_id, profile_sha256: store._paths(artifact_id)[1],
    )
    with pytest.raises(ArtifactIntegrityError, match="Selected manifest profile mismatch"):
        store.get_manifest(second)
    assert store.get_manifest(first).kind == "cas.view.first"


def test_integrity_verification_uses_the_selected_manifest_view(tmp_path: Path) -> None:
    """Selected-view verification must reject a corrupt non-default sidecar."""
    store = FileSystemCAS(tmp_path / "cas")
    store.put_bytes(PAYLOAD, _options("cas.verify.default", "application/json"))
    selected = store.put_bytes(PAYLOAD, _options("cas.verify.selected", "text/plain"))
    assert selected.manifest_profile_sha256 is not None

    selected_path = store._layout.view_manifest_path(
        selected.artifact_id,
        selected.manifest_profile_sha256,
    )
    selected_path.write_bytes(selected_path.read_bytes().replace(b"cas.verify.selected", b"cas.verify.tampered"))

    report = store.verify(selected)

    assert report.ok is False
    assert report.error is not None
    assert "manifest profile mismatch" in report.error.lower()


def test_selectorless_historical_signature_replays_after_another_view_is_added(
    tmp_path: Path,
) -> None:
    """Historical ID-only refs keep the original manifest and signature sidecars."""
    store = FileSystemCAS(tmp_path / "cas")
    key = Ed25519PrivateKey.generate()
    signer = Ed25519Signer(key)
    verifier = Ed25519Verifier()
    verifier.add_trusted_key(key.public_key())

    first_ref = store.put_bytes(PAYLOAD, _options("cas.history.first", "application/json"))
    legacy_ref = ArtifactRef(
        artifact_id=first_ref.artifact_id,
        kind=first_ref.kind,
        media_type=first_ref.media_type,
    )
    original_manifest = store.get_manifest_bytes(legacy_ref)
    store.sign_artifact(first_ref.artifact_id, signer)
    original_signature = store.get_signature_bytes(legacy_ref)

    store.put_bytes(PAYLOAD, _options("cas.history.second", "text/plain"))

    assert store.get_manifest_bytes(legacy_ref) == original_manifest
    assert store.get_signature_bytes(legacy_ref) == original_signature
    assert store.verify_signature(legacy_ref, verifier).ok is True


def test_guarded_store_requires_exact_owner_for_manifest_view(tmp_path: Path) -> None:
    root_store = FileSystemCAS(tmp_path / "shared")
    tenant_a = root_store.for_tenant("tenant-a")
    tenant_b = root_store.for_tenant("tenant-b")
    first = tenant_a.put_bytes(PAYLOAD, _options("cas.tenant.a", "application/json"))
    second = tenant_b.put_bytes(PAYLOAD, _options("cas.tenant.b", "text/plain"))

    assert tenant_b.get_manifest(second).kind == "cas.tenant.b"
    assert tenant_b.get_bytes(second) == PAYLOAD
    first_manifest = tenant_a.get_manifest(first)
    first_typed_ref = first.model_copy(
        update={"manifest_profile_sha256": ManifestLifecycle.profile_sha256(first_manifest)}
    )
    with pytest.raises(PermissionError, match="Manifest view"):
        tenant_b.get_manifest(first_typed_ref)
    with pytest.raises(PermissionError, match="not owned"):
        tenant_b.get_manifest(first.artifact_id)
    with pytest.raises(PermissionError, match="not owned"):
        tenant_b.get_bytes(first.artifact_id)


def test_existing_corrupt_blob_is_not_confirmed_by_successful_retry(tmp_path: Path) -> None:
    """A retry must fail closed or complete an independently verified repair."""
    store = FileSystemCAS(tmp_path / "cas")
    options = _options("cas.corrupt_retry", "application/octet-stream")
    first_ref = store.put_bytes(PAYLOAD, options)
    blob_path, _manifest_path = store._paths(first_ref.artifact_id)
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
    assert isinstance(outcomes["cas-second"], ArtifactRef)

    first_ref = outcomes["cas-first"]
    second_ref = outcomes["cas-second"]
    assert isinstance(first_ref, ArtifactRef)
    assert isinstance(second_ref, ArtifactRef)
    assert first_ref.artifact_id == second_ref.artifact_id
    _assert_manifest_profile(store.get_manifest(first_ref), first_options, data=PAYLOAD)
    _assert_manifest_profile(store.get_manifest(second_ref), second_options, data=PAYLOAD)


def test_exception_releases_same_id_lock_for_scoped_view_waiter(tmp_path: Path) -> None:
    """A failed view writer cannot strand a waiting writer of the same blob."""
    store = FileSystemCAS(tmp_path / "cas")
    default_options = _options("cas.default", "application/json")
    failed_options = _options("cas.failed", "application/json")
    waiting_options = _options("cas.waiting", "application/json")
    default_ref = store.put_bytes(PAYLOAD, default_options)
    aid = default_ref.artifact_id
    failed_manifest = store._manifests.build(
        artifact_id=aid,
        data=PAYLOAD,
        sha=aid.hex,
        opts=failed_options,
    )
    failed_view_path = store._layout.view_manifest_path(
        aid,
        store._manifests.profile_sha256(failed_manifest),
    )
    assert not failed_view_path.exists()

    first_inside_lock = threading.Event()
    release_first = threading.Event()
    waiter_contended = threading.Event()
    waiter_acquired_early = threading.Event()
    waiter_done = threading.Event()
    outcome_guard = threading.Lock()
    outcomes: dict[str, ArtifactRef | Exception] = {}
    observed_ids: dict[str, ArtifactID] = {}
    observed_locks: dict[str, object] = {}
    original_write_once = store._files.write_once
    original_artifact_lock = store._artifact_lock

    def _fail_first_view(path: Path, data: bytes) -> bool:
        if path == failed_view_path and threading.current_thread().name == "cas-failed-view":
            first_inside_lock.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("failed view writer was never released")
            raise OSError("injected scoped-view write failure")
        return original_write_once(path, data)

    @contextmanager
    def _waiter_lock(lock):
        if lock.acquire(blocking=False):
            waiter_acquired_early.set()
        else:
            waiter_contended.set()
            if not lock.acquire(timeout=3):
                raise TimeoutError("same-ID waiter did not acquire after failed view")
        try:
            yield
        finally:
            lock.release()

    def _observed_artifact_lock(artifact_id: ArtifactID):
        lock = original_artifact_lock(artifact_id)
        thread_name = threading.current_thread().name
        if thread_name in {"cas-failed-view", "cas-waiting-view"}:
            with outcome_guard:
                observed_ids[thread_name] = artifact_id
                observed_locks[thread_name] = lock
        if thread_name == "cas-waiting-view":
            return _waiter_lock(lock)
        # The failed writer receives the actual production lock. Its exception
        # release must come from the CAS owner's `with`, not this observer.
        return lock

    store._files.write_once = _fail_first_view  # type: ignore[method-assign]
    store._artifact_lock = _observed_artifact_lock  # type: ignore[method-assign]

    def _writer(name: str, options: PutOptions) -> None:
        try:
            try:
                outcome: ArtifactRef | Exception = store.put_bytes(PAYLOAD, options)
            except Exception as exc:  # pragma: no cover - checked through outcomes below
                outcome = exc
            with outcome_guard:
                outcomes[name] = outcome
        finally:
            if name == "cas-waiting-view":
                waiter_done.set()

    failed_writer = threading.Thread(
        target=_writer,
        args=("cas-failed-view", failed_options),
        name="cas-failed-view",
        daemon=True,
    )
    waiting_writer = threading.Thread(
        target=_writer,
        args=("cas-waiting-view", waiting_options),
        name="cas-waiting-view",
        daemon=True,
    )
    failed_writer.start()
    try:
        assert first_inside_lock.wait(timeout=2)
        waiting_writer.start()
        assert waiter_contended.wait(timeout=2)
        assert not waiter_acquired_early.is_set()
        assert not waiter_done.is_set()
    finally:
        release_first.set()
        failed_writer.join(timeout=6)
        if waiting_writer.ident is not None:
            waiting_writer.join(timeout=6)

    assert not failed_writer.is_alive()
    assert not waiting_writer.is_alive()
    assert observed_ids == {"cas-failed-view": aid, "cas-waiting-view": aid}
    assert observed_locks["cas-failed-view"] is observed_locks["cas-waiting-view"]
    assert isinstance(outcomes.get("cas-failed-view"), OSError)
    assert str(outcomes["cas-failed-view"]) == "injected scoped-view write failure"
    waiting_ref = outcomes.get("cas-waiting-view")
    assert isinstance(waiting_ref, ArtifactRef)
    assert waiting_ref.artifact_id == aid
    assert waiting_ref.manifest_profile_sha256 is not None
    assert not failed_view_path.exists()
    assert store.get_bytes(default_ref) == PAYLOAD
    assert store.get_bytes(waiting_ref) == PAYLOAD
    _assert_manifest_profile(store.get_manifest(default_ref), default_options, data=PAYLOAD)
    _assert_manifest_profile(store.get_manifest(waiting_ref), waiting_options, data=PAYLOAD)
    assert store.put_bytes(PAYLOAD, waiting_options) == waiting_ref


def test_lock_registry_is_bounded_without_evicting_active_waiters(tmp_path: Path) -> None:
    """Three thousand IDs retain bounded locks and same-ID exclusion."""
    store = FileSystemCAS(tmp_path / "cas")
    active_id = ArtifactID.from_sha256_hex("a" * 64)
    initial_pool_ids = {id(lock) for lock in store._artifact_locks}
    held_lock = store._artifact_lock(active_id)
    held_lock.acquire()
    waiter_started = threading.Event()
    waiter_probed = threading.Event()
    waiter_acquired = threading.Event()

    def _waiter() -> None:
        candidate = store._artifact_lock(active_id)
        waiter_started.set()
        if candidate.acquire(blocking=False):
            waiter_acquired.set()
            candidate.release()
            waiter_probed.set()
            return
        waiter_probed.set()
        candidate.acquire()
        try:
            waiter_acquired.set()
        finally:
            candidate.release()

    waiter = threading.Thread(target=_waiter, daemon=True)
    waiter.start()
    try:
        assert waiter_started.wait(timeout=2)
        assert waiter_probed.wait(timeout=2)
        assert not waiter_acquired.is_set()

        # The source-card discriminator allocates lock keys without CAS writes.
        # Count the lock objects actually returned, not the owner's tuple size.
        key_count = 3_000
        returned_lock_ids = {
            id(store._artifact_lock(_synthetic_artifact_id(index)))
            for index in range(key_count)
        }

        assert store._artifact_lock(active_id) is held_lock
        assert len(returned_lock_ids) <= len(initial_pool_ids)
        assert returned_lock_ids <= initial_pool_ids
        assert not waiter_acquired.is_set()
    finally:
        held_lock.release()
        waiter.join(timeout=2)

    assert not waiter.is_alive()
    assert waiter_acquired.is_set()


def test_colliding_lock_stripe_keeps_distinct_cas_bytes_and_manifests(tmp_path: Path) -> None:
    """A benign lock collision may serialize writes but cannot alias records."""
    store = FileSystemCAS(tmp_path / "cas")
    coordinator = store._coordinator
    initial_pool_size = len(coordinator._artifact_locks)
    assert initial_pool_size == coordinator.STRIPE_COUNT == 64
    by_lock: dict[int, tuple[ArtifactID, bytes]] = {}
    collision: tuple[tuple[ArtifactID, bytes], tuple[ArtifactID, bytes]] | None = None
    for index in range(initial_pool_size + 1):
        data = f"cas-01-collision-{index}".encode()
        artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(data).hexdigest())
        lock_identity = id(coordinator._artifact_locks[coordinator._stripe(artifact_id)])
        prior = by_lock.get(lock_identity)
        if prior is not None:
            collision = prior, (artifact_id, data)
            break
        by_lock[lock_identity] = artifact_id, data

    assert collision is not None
    (first_id, first_bytes), (second_id, second_bytes) = collision
    assert first_id != second_id
    assert first_bytes != second_bytes
    assert coordinator._artifact_locks[coordinator._stripe(first_id)] is (
        coordinator._artifact_locks[coordinator._stripe(second_id)]
    )

    options = _options("cas.stripe.collision", "application/octet-stream")
    first_ref = store.put_bytes(first_bytes, options)
    second_ref = store.put_bytes(second_bytes, options)

    assert first_ref.artifact_id == first_id
    assert second_ref.artifact_id == second_id
    assert store.get_bytes(first_ref) == first_bytes
    assert store.get_bytes(second_ref) == second_bytes
    first_manifest = store.get_manifest(first_ref)
    second_manifest = store.get_manifest(second_ref)
    assert first_manifest.artifact_id == first_id
    assert second_manifest.artifact_id == second_id
    _assert_manifest_profile(first_manifest, options, data=first_bytes)
    _assert_manifest_profile(second_manifest, options, data=second_bytes)
    assert store.get_manifest(first_ref) == first_manifest
    assert store.get_manifest(second_ref) == second_manifest


def _historical_profile_fixture(schema_version: str) -> ArtifactManifest:
    """Build deterministic pre-v3 profile bytes for historical selector replay."""
    artifact_id = ArtifactID.from_sha256_hex("a" * 64 if schema_version == "v1" else "c" * 64)
    historical_basis_id = ArtifactID.from_sha256_hex("b" * 64)
    values: dict[str, object] = {
        "artifact_id": artifact_id,
        "kind": "fixture.historical" if schema_version == "v1" else "fixture.historical.selected",
        "media_type": "application/json",
        "byte_size": 7 if schema_version == "v1" else 17,
        "created_at": datetime(2026, 9, 26, tzinfo=UTC),
        "inputs": [InputRef(artifact_id=historical_basis_id, role="historical_basis")],
        "integrity": IntegrityInfo(sha256=artifact_id.hex),
    }
    if schema_version == "v2":
        values["manifest_schema_version"] = "v2"
        values["inputs"] = [
            InputRef(
                artifact_id=historical_basis_id,
                role="selected_basis",
                manifest_profile_sha256="sha256:" + "1" * 64,
            )
        ]
    return ArtifactManifest.model_validate(values)


def test_historical_v1_and_v2_profile_selectors_keep_exact_digest() -> None:
    """Old default and selected-input manifest keys keep the v1 projection."""
    assert ManifestLifecycle.profile_sha256(_historical_profile_fixture("v1")) == (
        "sha256:38e4f96c98d60275375a2b425e68537db875d4797e91f5733f6fd118f7885180"
    )
    assert ManifestLifecycle.profile_sha256(_historical_profile_fixture("v2")) == (
        "sha256:74520648cfc1a9624b5db9e6c8a5acf15b6c4dfd56963df8506af657492479dc"
    )


def test_manifest_profile_digest_binds_optional_integrity_metadata() -> None:
    """A selected view key distinguishes consumer-visible optional integrity claims."""
    artifact_id = _synthetic_artifact_id(101)
    base = ArtifactManifest(
        manifest_schema_version="v3",
        artifact_id=artifact_id,
        kind="cas.integrity.optional",
        media_type="application/octet-stream",
        byte_size=len(PAYLOAD),
        integrity=IntegrityInfo(sha256=artifact_id.hex),
    )
    enriched = base.model_copy(
        update={
            "integrity": IntegrityInfo(
                sha256=artifact_id.hex,
                optional={"verification": "external-check-v1"},
            )
        }
    )

    base_profile = ManifestLifecycle.profile_sha256(base)
    enriched_profile = ManifestLifecycle.profile_sha256(enriched)
    base_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind=base.kind,
        media_type=base.media_type,
        manifest_profile_sha256=base_profile,
    )
    enriched_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind=enriched.kind,
        media_type=enriched.media_type,
        manifest_profile_sha256=enriched_profile,
    )

    assert base_ref.artifact_id == enriched_ref.artifact_id
    assert base_profile != enriched_profile
    assert base_ref.manifest_profile_sha256 != enriched_ref.manifest_profile_sha256
    assert ManifestLifecycle.profile_projection(base)["integrity"] == {}
    assert ManifestLifecycle.profile_projection(enriched)["integrity"] == {
        "optional": {"verification": "external-check-v1"}
    }


def test_same_optional_integrity_profile_has_stable_selector() -> None:
    """Repeated identical typed views resolve to the same profile selector."""
    artifact_id = _synthetic_artifact_id(105)
    first = ArtifactManifest(
        manifest_schema_version="v3",
        artifact_id=artifact_id,
        kind="cas.integrity.optional",
        media_type="application/octet-stream",
        byte_size=len(PAYLOAD),
        integrity=IntegrityInfo(
            sha256=artifact_id.hex,
            optional={"verification": "external-check-v1"},
        ),
    )
    replay = ArtifactManifest.model_validate(first.model_dump(mode="python"))

    assert ManifestLifecycle.profile_sha256(first) == ManifestLifecycle.profile_sha256(replay)


def test_transfer_resolves_distinct_optional_integrity_views(tmp_path: Path) -> None:
    """CAS transfer preserves both selectors when only optional integrity differs."""
    source = FileSystemCAS(tmp_path / "source")
    target = FileSystemCAS(tmp_path / "target")
    stored_ref = source.put_bytes(
        PAYLOAD,
        _options("cas.integrity.optional.transfer", "application/octet-stream"),
    )
    stored_manifest = source.get_manifest(stored_ref)
    base_manifest = stored_manifest.model_copy(update={"manifest_schema_version": "v3"})
    base_profile = ManifestLifecycle.profile_sha256(base_manifest)
    base_path = source._layout.view_manifest_path(stored_ref.artifact_id, base_profile)
    base_path.write_bytes(ManifestLifecycle.to_bytes(base_manifest))
    base_ref = ArtifactRef(
        artifact_id=stored_ref.artifact_id,
        kind=stored_ref.kind,
        media_type=stored_ref.media_type,
        manifest_profile_sha256=base_profile,
    )
    optional_manifest = base_manifest.model_copy(
        update={
            "integrity": IntegrityInfo(
                sha256=base_manifest.integrity.sha256,
                optional={"verification": "external-check-v1"},
            )
        }
    )
    optional_profile = ManifestLifecycle.profile_sha256(optional_manifest)
    optional_path = source._layout.view_manifest_path(
        stored_ref.artifact_id, optional_profile
    )
    optional_path.write_bytes(ManifestLifecycle.to_bytes(optional_manifest))
    optional_ref = ArtifactRef(
        artifact_id=stored_ref.artifact_id,
        kind=stored_ref.kind,
        media_type=stored_ref.media_type,
        manifest_profile_sha256=optional_profile,
    )

    export = source.export_subgraph(
        [base_ref, optional_ref], tmp_path / "integrity-views.tar.gz"
    )
    report = target.import_subgraph(export.output_path, verify_integrity=True)

    assert report.verification_failed == []
    assert target.get_bytes(base_ref) == PAYLOAD
    assert target.get_bytes(optional_ref) == PAYLOAD
    assert target.get_manifest(base_ref).integrity.optional is None
    assert target.get_manifest(optional_ref).integrity.optional == {
        "verification": "external-check-v1"
    }
