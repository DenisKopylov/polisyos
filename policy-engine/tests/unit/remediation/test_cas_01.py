"""Test-first witnesses for CAS first-writer identity and bounded lock ownership."""

from __future__ import annotations

import hashlib
import os
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
    ArtifactTransactionPendingError,
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


_LEASE_REMOVAL_PROBE_ENV = "POLISYOS_CAS01_REMOVE_STRIPE_EXCLUSION_PROBE"


def _install_same_id_stripe_removal_probe(
    coordinator: Any,
    artifact_id: ArtifactID,
    contender_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> bool:
    """Route one named same-ID contender to a distinct live owner stripe on demand."""
    enabled = os.environ.get(_LEASE_REMOVAL_PROBE_ENV)
    if enabled not in {None, "1"}:
        raise ValueError(f"{_LEASE_REMOVAL_PROBE_ENV} must be unset or 1")
    if enabled is None:
        return False

    locks = coordinator._artifact_locks
    if len(locks) < 2:
        raise AssertionError("stripe-removal probe requires at least two owner stripes")
    original_stripe = coordinator._stripe

    def route_same_id_away(candidate_id: ArtifactID) -> int:
        stripe = original_stripe(candidate_id)
        if (
            candidate_id == artifact_id
            and threading.current_thread().name == contender_name
        ):
            return (stripe + 1) % len(locks)
        return stripe

    monkeypatch.setattr(coordinator, "_stripe", route_same_id_away)
    return True


_BOUNDED_POOL_REMOVAL_PROBE_ENV = "POLISYOS_CAS01_REMOVE_BOUNDED_POOL_PROBE"


def _install_per_id_pool_removal_probe(
    coordinator: Any,
    *,
    bounded_pool: Any,
    pool_size: int,
    pressure_thread_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[bool, dict[int, Any]]:
    """Route pressure leases through unbounded per-ID locks on demand."""
    enabled = os.environ.get(_BOUNDED_POOL_REMOVAL_PROBE_ENV)
    if enabled not in {None, "1"}:
        raise ValueError(f"{_BOUNDED_POOL_REMOVAL_PROBE_ENV} must be unset or 1")
    if enabled is None:
        return False, {}

    original_stripe = coordinator._stripe
    overflow_stripes: dict[str, int] = {}
    overflow_locks: dict[int, Any] = {}

    class _PerIdStripeIndex(int):
        def __new__(cls, lock_index: int, file_stripe: int) -> _PerIdStripeIndex:
            value = int.__new__(cls, lock_index)
            value.file_stripe = file_stripe
            return value

        def __format__(self, format_spec: str) -> str:
            return format(self.file_stripe, format_spec)

    class _UnboundedPressurePool:
        """Keep the bounded table view while routing pressure keys to new locks."""

        def __len__(self) -> int:
            return pool_size

        def __getitem__(self, stripe: int) -> Any:
            if 0 <= stripe < pool_size:
                return bounded_pool[stripe]
            return overflow_locks.setdefault(stripe, threading.RLock())

    def route_pressure_ids_to_distinct_stripes(candidate_id: ArtifactID) -> int:
        if threading.current_thread().name != pressure_thread_name:
            return original_stripe(candidate_id)
        file_stripe = original_stripe(candidate_id)
        per_id_ordinal = overflow_stripes.setdefault(
            candidate_id.hex,
            len(overflow_stripes),
        )
        return _PerIdStripeIndex(pool_size + per_id_ordinal, file_stripe)

    monkeypatch.setattr(coordinator, "_artifact_locks", _UnboundedPressurePool())
    monkeypatch.setattr(coordinator, "_stripe", route_pressure_ids_to_distinct_stripes)
    return True, overflow_locks


def _observe_artifact_lease_attempts(
    coordinator: Any,
    monkeypatch: pytest.MonkeyPatch,
    watched: dict[str, tuple[ArtifactID, threading.Event, threading.Event]],
) -> None:
    """Observe named attempts and successful entries around the real owner lease."""
    original_lease = coordinator.artifact_lease

    @contextmanager
    def observe(artifact_id: ArtifactID, *, exclusive: bool):
        observation = watched.get(threading.current_thread().name)
        is_watched = observation is not None and observation[0] == artifact_id
        if is_watched:
            observation[1].set()
        with original_lease(artifact_id, exclusive=exclusive) as lease:
            if is_watched:
                observation[2].set()
            yield lease

    monkeypatch.setattr(coordinator, "artifact_lease", observe)


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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same-ID profile writes serialize through the current transaction owner."""
    store = FileSystemCAS(tmp_path / "cas")
    coordinator = store._coordinator
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
    artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(PAYLOAD).hexdigest())
    blob_path, _default_manifest_path = store._paths(artifact_id)
    first_manifest = store._manifests.build(
        artifact_id=artifact_id,
        data=PAYLOAD,
        sha=artifact_id.hex,
        opts=first_options,
    )
    first_profile = store._manifests.profile_sha256(first_manifest)
    first_intent_persisted = threading.Event()
    release_first_publication = threading.Event()
    second_lease_attempted = threading.Event()
    second_lease_entered = threading.Event()
    first_thread_started = threading.Event()
    second_thread_started = threading.Event()
    outcome_guard = threading.Lock()
    outcomes: dict[str, ArtifactRef | Exception] = {}
    _observe_artifact_lease_attempts(
        coordinator,
        monkeypatch,
        {
            "cas-second": (
                artifact_id,
                second_lease_attempted,
                second_lease_entered,
            )
        },
    )
    probe_enabled = _install_same_id_stripe_removal_probe(
        coordinator,
        artifact_id,
        "cas-second",
        monkeypatch,
    )

    original_publish = store._publish_transaction_member

    def _gated_publish(
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        if final_path == blob_path and threading.current_thread().name == "cas-first":
            intent = store._ownership_index._read_transaction_intent(artifact_id)
            assert intent is not None
            assert intent["status"] == "pending"
            default_view = next(
                view for view in intent["views"] if view["selector"] == "default"
            )
            assert default_view["manifest_profile_sha256"] == first_profile
            first_intent_persisted.set()
            if not release_first_publication.wait(timeout=5):
                raise TimeoutError("first publication was never released")
        return original_publish(
            stage_path,
            final_path,
            expected_sha256=expected_sha256,
        )

    store._publish_transaction_member = _gated_publish  # type: ignore[method-assign]

    def _writer(name: str, options: PutOptions, started: threading.Event) -> None:
        started.set()
        try:
            outcome: ArtifactRef | Exception = store.put_bytes(PAYLOAD, options)
        except Exception as exc:  # pragma: no cover - checked through outcomes below
            outcome = exc
        with outcome_guard:
            outcomes[name] = outcome

    first_thread = threading.Thread(
        target=_writer,
        args=("cas-first", first_options, first_thread_started),
        name="cas-first",
        daemon=True,
    )
    second_thread = threading.Thread(
        target=_writer,
        args=("cas-second", second_options, second_thread_started),
        name="cas-second",
        daemon=True,
    )
    first_thread.start()
    try:
        assert first_thread_started.wait(timeout=2)
        assert first_intent_persisted.wait(timeout=2)
        second_thread.start()
        assert second_thread_started.wait(timeout=2)
        assert second_lease_attempted.wait(timeout=2)
        # With the removal probe enabled, wait for actual early entry so the
        # same positive witness turns red deterministically.
        if probe_enabled:
            assert second_lease_entered.wait(timeout=2)
        assert not second_lease_entered.is_set()
        assert "cas-second" not in outcomes
    finally:
        release_first_publication.set()
        first_thread.join(timeout=6)
        if second_thread.ident is not None:
            second_thread.join(timeout=6)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert second_lease_entered.is_set()
    assert set(outcomes) == {"cas-first", "cas-second"}
    assert isinstance(outcomes["cas-first"], ArtifactRef)
    assert isinstance(outcomes["cas-second"], ArtifactRef)

    first_ref = outcomes["cas-first"]
    second_ref = outcomes["cas-second"]
    assert isinstance(first_ref, ArtifactRef)
    assert isinstance(second_ref, ArtifactRef)
    assert first_ref.artifact_id == second_ref.artifact_id == artifact_id
    assert first_ref.manifest_profile_sha256 is None
    assert second_ref.manifest_profile_sha256 is not None
    _assert_manifest_profile(store.get_manifest(first_ref), first_options, data=PAYLOAD)
    _assert_manifest_profile(
        store.get_manifest(second_ref), second_options, data=PAYLOAD
    )
    _assert_manifest_profile(
        store.get_manifest(artifact_id), first_options, data=PAYLOAD
    )
    assert store.get_bytes(first_ref) == store.get_bytes(second_ref) == PAYLOAD

    repeated_ref = store.put_bytes(PAYLOAD, second_options)
    assert repeated_ref == second_ref
    _assert_manifest_profile(
        store.get_manifest(repeated_ref), second_options, data=PAYLOAD
    )


def test_exception_releases_same_id_lock_for_scoped_view_waiter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed profile intent denies other views until its exact retry recovers."""
    store = FileSystemCAS(tmp_path / "cas")
    coordinator = store._coordinator
    default_options = _options("cas.default", "application/json")
    failed_options = _options("cas.failed", "application/json")
    waiting_options = _options("cas.waiting", "application/json")
    default_ref = store.put_bytes(PAYLOAD, default_options)
    artifact_id = default_ref.artifact_id
    failed_manifest = store._manifests.build(
        artifact_id=artifact_id,
        data=PAYLOAD,
        sha=artifact_id.hex,
        opts=failed_options,
    )
    waiting_manifest = store._manifests.build(
        artifact_id=artifact_id,
        data=PAYLOAD,
        sha=artifact_id.hex,
        opts=waiting_options,
    )
    failed_profile = store._manifests.profile_sha256(failed_manifest)
    waiting_profile = store._manifests.profile_sha256(waiting_manifest)
    failed_view_path = store._layout.view_manifest_path(artifact_id, failed_profile)
    waiting_view_path = store._layout.view_manifest_path(artifact_id, waiting_profile)
    assert not failed_view_path.exists()
    assert not waiting_view_path.exists()

    failed_publish_entered = threading.Event()
    release_failed_publish = threading.Event()
    waiter_lease_attempted = threading.Event()
    waiter_lease_entered = threading.Event()
    waiter_done = threading.Event()
    outcome_guard = threading.Lock()
    outcomes: dict[str, ArtifactRef | Exception] = {}
    _observe_artifact_lease_attempts(
        coordinator,
        monkeypatch,
        {
            "cas-waiting-view": (
                artifact_id,
                waiter_lease_attempted,
                waiter_lease_entered,
            )
        },
    )
    probe_enabled = _install_same_id_stripe_removal_probe(
        coordinator,
        artifact_id,
        "cas-waiting-view",
        monkeypatch,
    )

    original_publish = store._publish_transaction_member

    def _fail_first_view(
        stage_path: Path | None,
        final_path: Path,
        *,
        expected_sha256: str,
    ) -> bool:
        if (
            final_path == failed_view_path
            and threading.current_thread().name == "cas-failed-view"
        ):
            intent = store._ownership_index._read_transaction_intent(artifact_id)
            assert intent is not None
            assert intent["status"] == "pending"
            assert any(
                view["manifest_profile_sha256"] == failed_profile
                for view in intent["views"]
            )
            failed_publish_entered.set()
            if not release_failed_publish.wait(timeout=5):
                raise TimeoutError("failed view publication was never released")
            raise OSError("injected scoped-view publication failure")
        return original_publish(
            stage_path,
            final_path,
            expected_sha256=expected_sha256,
        )

    store._publish_transaction_member = _fail_first_view  # type: ignore[method-assign]

    def _writer(name: str, options: PutOptions) -> None:
        try:
            try:
                outcome: ArtifactRef | Exception = store.put_bytes(PAYLOAD, options)
            except Exception as exc:  # pragma: no cover - asserted below
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
        assert failed_publish_entered.wait(timeout=2)
        waiting_writer.start()
        assert waiter_lease_attempted.wait(timeout=2)
        # The same test-local stripe mutation must expose early entry as a red.
        if probe_enabled:
            assert waiter_lease_entered.wait(timeout=2)
        assert not waiter_lease_entered.is_set()
        assert not waiter_done.is_set()
    finally:
        release_failed_publish.set()
        failed_writer.join(timeout=6)
        if waiting_writer.ident is not None:
            waiting_writer.join(timeout=6)

    assert not failed_writer.is_alive()
    assert not waiting_writer.is_alive()
    assert waiter_lease_entered.is_set()
    failed_outcome = outcomes.get("cas-failed-view")
    waiting_outcome = outcomes.get("cas-waiting-view")
    assert isinstance(failed_outcome, OSError)
    assert str(failed_outcome) == "injected scoped-view publication failure"
    assert isinstance(waiting_outcome, ArtifactTransactionPendingError)
    assert waiting_outcome.code == "artifact_transaction_pending"
    assert waiting_outcome.artifact_id == artifact_id

    pending = store._ownership_index._read_transaction_intent(artifact_id)
    assert pending is not None
    assert pending["status"] == "pending"
    assert pending["mode"] == "publish"
    assert any(
        view["manifest_profile_sha256"] == failed_profile for view in pending["views"]
    )
    assert not any(
        view["manifest_profile_sha256"] == waiting_profile for view in pending["views"]
    )
    assert not failed_view_path.exists()
    assert not waiting_view_path.exists()
    assert store.get_bytes(default_ref) == PAYLOAD
    _assert_manifest_profile(
        store.get_manifest(default_ref), default_options, data=PAYLOAD
    )

    recovered_ref = store.put_bytes(PAYLOAD, failed_options)
    assert recovered_ref.artifact_id == artifact_id
    assert recovered_ref.manifest_profile_sha256 == failed_profile
    assert store._ownership_index._read_transaction_intent(artifact_id) is None
    assert failed_view_path.is_file()
    _assert_manifest_profile(
        store.get_manifest(recovered_ref), failed_options, data=PAYLOAD
    )

    waiting_ref = store.put_bytes(PAYLOAD, waiting_options)
    assert waiting_ref.artifact_id == artifact_id
    assert waiting_ref.manifest_profile_sha256 == waiting_profile
    assert waiting_view_path.is_file()
    _assert_manifest_profile(
        store.get_manifest(waiting_ref), waiting_options, data=PAYLOAD
    )
    assert store.put_bytes(PAYLOAD, waiting_options) == waiting_ref


def test_lock_registry_is_bounded_without_evicting_active_waiters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Any,
) -> None:
    """Three thousand real owner leases use the fixed pool without evicting waiters."""
    store = FileSystemCAS(tmp_path / "cas")
    coordinator = store._coordinator
    active_id = ArtifactID.from_sha256_hex("a" * 64)
    owner_locks = tuple(coordinator._artifact_locks)
    owner_lock_ids = {id(lock) for lock in owner_locks}
    base_stripe = coordinator._stripe
    active_stripe = base_stripe(active_id)
    pool_size = len(owner_locks)
    assert pool_size > 1
    assert len(owner_lock_ids) == pool_size
    active_lock = owner_locks[active_stripe]

    pressure_count = 3_000
    pressure_ids: list[ArtifactID] = []
    excluded_active_stripe_ids = 0
    candidates_scanned = 0
    while len(pressure_ids) < pressure_count:
        candidate_id = _synthetic_artifact_id(candidates_scanned)
        candidates_scanned += 1
        if base_stripe(candidate_id) == active_stripe:
            excluded_active_stripe_ids += 1
        else:
            pressure_ids.append(candidate_id)
    assert len(pressure_ids) == pressure_count
    assert candidates_scanned == pressure_count + excluded_active_stripe_ids

    holder_entered = threading.Event()
    release_holder = threading.Event()
    waiter_attempted = threading.Event()
    waiter_acquired = threading.Event()
    _observe_artifact_lease_attempts(
        coordinator,
        monkeypatch,
        {"cas-waiter": (active_id, waiter_attempted, waiter_acquired)},
    )
    stripe_probe_enabled = _install_same_id_stripe_removal_probe(
        coordinator,
        active_id,
        "cas-waiter",
        monkeypatch,
    )

    pressure_thread_name = "cas-pressure"
    selected_owner_locks: list[tuple[int, int]] = []

    class _RecordingLock:
        def __init__(self, stripe: int, lock: Any) -> None:
            self.stripe = stripe
            self.lock = lock

        def __enter__(self) -> bool:
            acquired = self.lock.acquire()
            if threading.current_thread().name == pressure_thread_name:
                selected_owner_locks.append((self.stripe, id(self.lock)))
            return acquired

        def __exit__(self, *_exc_info: Any) -> None:
            self.lock.release()

    class _RecordingLockPool:
        def __init__(self) -> None:
            self.locks = tuple(
                _RecordingLock(stripe, lock) for stripe, lock in enumerate(owner_locks)
            )

        def __len__(self) -> int:
            return len(self.locks)

        def __getitem__(self, stripe: int) -> _RecordingLock:
            return self.locks[stripe]

    recording_pool = _RecordingLockPool()
    monkeypatch.setattr(coordinator, "_artifact_locks", recording_pool)
    pool_probe_enabled, per_id_locks = _install_per_id_pool_removal_probe(
        coordinator,
        bounded_pool=recording_pool,
        pool_size=pool_size,
        pressure_thread_name=pressure_thread_name,
        monkeypatch=monkeypatch,
    )

    pressure_finished = threading.Event()
    pressure_errors: list[Exception] = []

    def _holder() -> None:
        with coordinator.artifact_lease(active_id, exclusive=True):
            holder_entered.set()
            if not release_holder.wait(timeout=60):
                raise TimeoutError("active owner lease was never released")

    def _waiter() -> None:
        with coordinator.artifact_lease(active_id, exclusive=True):
            pass

    def _pressure() -> None:
        try:
            for candidate_id in pressure_ids:
                with coordinator.artifact_lease(candidate_id, exclusive=True):
                    pass
        except Exception as exc:
            pressure_errors.append(exc)
        finally:
            pressure_finished.set()

    holder = threading.Thread(target=_holder, name="cas-holder", daemon=True)
    waiter = threading.Thread(target=_waiter, name="cas-waiter", daemon=True)
    pressure = threading.Thread(
        target=_pressure,
        name=pressure_thread_name,
        daemon=True,
    )
    holder.start()
    try:
        assert holder_entered.wait(timeout=2)
        waiter.start()
        assert waiter_attempted.wait(timeout=2)
        # This positive witness remains in the normal denominator; the opt-in
        # mutation must make the active same-ID waiter enter early.
        if stripe_probe_enabled:
            assert waiter_acquired.wait(timeout=2)
        assert not waiter_acquired.is_set()

        pressure.start()
        assert pressure_finished.wait(timeout=30)
        pressure.join(timeout=2)
        assert not pressure.is_alive()
        assert pressure_errors == []
        assert not waiter_acquired.is_set()

        selected_lock_ids = {lock_id for _stripe, lock_id in selected_owner_locks}
        record_property("b153_pressure_eligible_ids", len(pressure_ids))
        record_property("b153_pressure_candidates_scanned", candidates_scanned)
        record_property(
            "b153_pressure_excluded_active_stripe_ids",
            excluded_active_stripe_ids,
        )
        record_property("b153_pressure_owner_pool_size", pool_size)
        record_property(
            "b153_pressure_actual_lock_acquisitions", len(selected_owner_locks)
        )
        record_property("b153_pressure_actual_unique_locks", len(selected_lock_ids))
        record_property("b153_pressure_unbounded_mutant_locks", len(per_id_locks))

        # The marker-preserving removal probe retains the sized owner table but
        # routes every pressure ID through a distinct lock beyond that table.
        if pool_probe_enabled:
            assert len(per_id_locks) == pressure_count
        assert len(selected_owner_locks) == pressure_count
        assert selected_lock_ids <= owner_lock_ids
        assert len(selected_lock_ids) <= pool_size
        assert recording_pool[active_stripe].lock is active_lock
        assert not waiter_acquired.is_set()
    finally:
        release_holder.set()
        holder.join(timeout=6)
        if pressure.ident is not None:
            pressure.join(timeout=6)
        if waiter.ident is not None:
            waiter.join(timeout=6)

    assert not holder.is_alive()
    assert not pressure.is_alive()
    assert not waiter.is_alive()
    assert waiter_acquired.is_set()
    pressure_stripes = {base_stripe(candidate_id) for candidate_id in pressure_ids}
    assert len(pressure_stripes) < pool_size
    assert active_stripe not in pressure_stripes


def test_colliding_lock_stripe_keeps_distinct_cas_bytes_and_manifests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Colliding CAS IDs remain distinct while a separate stripe publishes."""
    store = FileSystemCAS(tmp_path / "cas")
    coordinator = store._coordinator
    owner_locks = tuple(coordinator._artifact_locks)
    pool_size = len(owner_locks)
    assert pool_size > 1
    assert len({id(lock) for lock in owner_locks}) == pool_size
    by_lock: dict[int, tuple[ArtifactID, bytes]] = {}
    collision: tuple[tuple[ArtifactID, bytes], tuple[ArtifactID, bytes]] | None = None
    for index in range(pool_size + 1):
        data = f"cas-01-collision-{index}".encode()
        artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(data).hexdigest())
        stripe = coordinator._stripe(artifact_id)
        prior = by_lock.get(id(owner_locks[stripe]))
        if prior is not None:
            collision = prior, (artifact_id, data)
            break
        by_lock[id(owner_locks[stripe])] = artifact_id, data

    assert collision is not None
    (first_id, first_bytes), (second_id, second_bytes) = collision
    first_stripe = coordinator._stripe(first_id)
    assert first_id != second_id
    assert first_bytes != second_bytes
    assert first_stripe == coordinator._stripe(second_id)
    assert owner_locks[first_stripe] is owner_locks[coordinator._stripe(second_id)]

    independent_pair: tuple[ArtifactID, bytes] | None = None
    for index in range(pool_size * 128):
        data = f"cas-01-independent-{index}".encode()
        artifact_id = ArtifactID.from_sha256_hex(hashlib.sha256(data).hexdigest())
        if coordinator._stripe(artifact_id) != first_stripe:
            independent_pair = artifact_id, data
            break
    assert independent_pair is not None
    independent_id, independent_bytes = independent_pair
    options = _options("cas.stripe.collision", "application/octet-stream")
    collision_attempted = threading.Event()
    collision_entered = threading.Event()
    collision_done = threading.Event()
    independent_attempted = threading.Event()
    independent_entered = threading.Event()
    independent_done = threading.Event()
    outcome_guard = threading.Lock()
    outcomes: dict[str, ArtifactRef | Exception] = {}
    _observe_artifact_lease_attempts(
        coordinator,
        monkeypatch,
        {
            "cas-collision-writer": (second_id, collision_attempted, collision_entered),
            "cas-independent-writer": (
                independent_id,
                independent_attempted,
                independent_entered,
            ),
        },
    )
    holder_entered = threading.Event()
    release_holder = threading.Event()

    def _holder() -> None:
        with coordinator.artifact_lease(first_id, exclusive=True):
            holder_entered.set()
            if not release_holder.wait(timeout=5):
                raise TimeoutError("colliding stripe lease was never released")

    def _writer(name: str, payload: bytes, done: threading.Event) -> None:
        try:
            try:
                outcome: ArtifactRef | Exception = store.put_bytes(payload, options)
            except Exception as exc:  # pragma: no cover - asserted below
                outcome = exc
            with outcome_guard:
                outcomes[name] = outcome
        finally:
            done.set()

    holder = threading.Thread(target=_holder, name="cas-collision-holder", daemon=True)
    collision_writer = threading.Thread(
        target=_writer,
        args=("collision", second_bytes, collision_done),
        name="cas-collision-writer",
        daemon=True,
    )
    independent_writer = threading.Thread(
        target=_writer,
        args=("independent", independent_bytes, independent_done),
        name="cas-independent-writer",
        daemon=True,
    )
    holder.start()
    try:
        assert holder_entered.wait(timeout=2)
        collision_writer.start()
        assert collision_attempted.wait(timeout=2)
        assert not collision_entered.is_set()
        independent_writer.start()
        assert independent_attempted.wait(timeout=2)
        assert independent_entered.wait(timeout=2)
        assert independent_done.wait(timeout=2)
        assert not collision_done.is_set()
    finally:
        release_holder.set()
        holder.join(timeout=6)
        if collision_writer.ident is not None:
            collision_writer.join(timeout=6)
        if independent_writer.ident is not None:
            independent_writer.join(timeout=6)

    assert not holder.is_alive()
    assert not collision_writer.is_alive()
    assert not independent_writer.is_alive()
    assert collision_entered.is_set()
    assert independent_entered.is_set()
    assert set(outcomes) == {"collision", "independent"}
    second_ref = outcomes["collision"]
    independent_ref = outcomes["independent"]
    assert isinstance(second_ref, ArtifactRef)
    assert isinstance(independent_ref, ArtifactRef)

    first_ref = store.put_bytes(first_bytes, options)
    assert first_ref.artifact_id == first_id
    assert second_ref.artifact_id == second_id
    assert independent_ref.artifact_id == independent_id
    assert store.get_bytes(first_ref) == first_bytes
    assert store.get_bytes(second_ref) == second_bytes
    assert store.get_bytes(independent_ref) == independent_bytes
    first_manifest = store.get_manifest(first_ref)
    second_manifest = store.get_manifest(second_ref)
    independent_manifest = store.get_manifest(independent_ref)
    assert first_manifest.artifact_id == first_id
    assert second_manifest.artifact_id == second_id
    assert independent_manifest.artifact_id == independent_id
    _assert_manifest_profile(first_manifest, options, data=first_bytes)
    _assert_manifest_profile(second_manifest, options, data=second_bytes)
    _assert_manifest_profile(independent_manifest, options, data=independent_bytes)
    assert store.get_manifest(first_ref) == first_manifest
    assert store.get_manifest(second_ref) == second_manifest
    assert store.get_manifest(independent_ref) == independent_manifest


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
