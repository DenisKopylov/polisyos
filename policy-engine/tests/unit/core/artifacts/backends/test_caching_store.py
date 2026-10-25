"""Tests for CachingArtifactStore."""

from __future__ import annotations

from datetime import datetime, tzinfo
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from polisyos.core.artifacts._integrity_ops import ArtifactIntegrityError
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.canonical_profile import (
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    read_core_json_artifact_bounded,
)
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    ProducerInfo,
)
from polisyos.core.artifacts.manifest import (
    CanonInfo as CoreCanonInfo,
)
from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.signing import Ed25519Signer, Ed25519Verifier
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import to_canonical_bytes
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.artifacts.io import get_json_artifact
from polisyos.runtime.http.resilience import guard_runtime_cas

_FAKE_ID = "sha256:" + "aa" * 32


class _CapabilityLimitedStore:
    """Delegate an ArtifactStore while withholding one optional cache capability."""

    def __init__(self, store: Any, missing_capability: str) -> None:
        self._store = store
        self._missing_capability = missing_capability

    def __getattr__(self, name: str) -> Any:
        if name == self._missing_capability:
            raise AttributeError(name)
        return getattr(self._store, name)


class _OwnerManifestReadFailureStore:
    """Record a durable write, then fail one selected owner-manifest read."""

    def __init__(self, store: Any, failure_method: str) -> None:
        self._store = store
        self._failure_method = failure_method
        self.committed = False
        self.last_ref: Any = None

    def __getattr__(self, name: str) -> Any:
        if name == self._failure_method and self.committed:

            def fail_manifest_read(*args: Any, **kwargs: Any) -> Any:
                raise OSError("durable owner selected manifest read unavailable")

            return fail_manifest_read
        if name in {"put_bytes", "put_json"}:
            method = getattr(self._store, name)

            def commit_then_mark(*args: Any, **kwargs: Any) -> Any:
                result = method(*args, **kwargs)
                self.last_ref = result
                self.committed = True
                return result

            return commit_then_mark
        return getattr(self._store, name)


def _install_manifest_timestamps(
    monkeypatch: pytest.MonkeyPatch,
    *timestamps: str,
) -> None:
    values = iter(datetime.fromisoformat(value) for value in timestamps)
    original_build = ManifestLifecycle.build

    def build_with_timestamp(*, created_at=None, **kwargs):
        timestamp = created_at if created_at is not None else next(values)
        return original_build(**kwargs, created_at=timestamp)

    monkeypatch.setattr(
        ManifestLifecycle,
        "build",
        staticmethod(build_with_timestamp),
    )


def test_cache_write_through_returns_remote_selected_profile(tmp_path: Path) -> None:
    local = FileSystemCAS(tmp_path / "local")
    remote = FileSystemCAS(tmp_path / "remote")
    cached = CachingArtifactStore(remote=remote, local=local, write_through=True)

    ref = cached.put_bytes(
        b"same selected profile",
        PutOptions(kind="test.cache_profile", media_type="application/json"),
        return_selected_profile=True,
    )

    assert ref.manifest_profile_sha256 is not None
    assert local.get_manifest(ref) == remote.get_manifest(ref)
    assert remote.get_manifest(ref).kind == "test.cache_profile"


def test_cache_write_through_returns_remote_selected_profile_for_json(
    tmp_path: Path,
) -> None:
    local = FileSystemCAS(tmp_path / "local-json")
    remote = FileSystemCAS(tmp_path / "remote-json")
    cached = CachingArtifactStore(remote=remote, local=local, write_through=True)

    ref = cached.put_json(
        {"value": "json selected profile"},
        PutOptions(kind="test.cache_json_profile", media_type="application/json"),
        return_selected_profile=True,
    )

    assert ref.manifest_profile_sha256 is not None
    assert local.get_manifest(ref) == remote.get_manifest(ref)
    assert remote.get_manifest(ref).kind == "test.cache_json_profile"


def test_bounded_selected_json_forwards_only_to_the_manifest_owner(
    tmp_path: Path,
) -> None:
    local = FileSystemCAS(tmp_path / "bounded-local")
    remote_base = FileSystemCAS(tmp_path / "bounded-remote")

    class BoundedOwnerSpy:
        def __init__(self, target: FileSystemCAS) -> None:
            self._target = target
            self.manifest_receipt_calls = 0
            self.member_open_calls = 0
            self.get_bytes_calls = 0

        def __getattr__(self, name: str):
            return getattr(self._target, name)

        def read_raw_manifest_bytes_bounded(self, selected_ref, *, max_manifest_bytes):
            self.manifest_receipt_calls += 1
            return self._target.read_raw_manifest_bytes_bounded(
                selected_ref,
                max_manifest_bytes=max_manifest_bytes,
            )

        def open_member_bounded(self, selected_ref, member, **kwargs):
            self.member_open_calls += 1
            return self._target.open_member_bounded(selected_ref, member, **kwargs)

        def get_bytes(self, selected_ref):
            self.get_bytes_calls += 1
            raise AssertionError("strict bounded reads must not call get_bytes")

    remote = BoundedOwnerSpy(remote_base)
    store = CachingArtifactStore(remote=remote, local=local, write_through=True)
    raw = to_canonical_bytes({"value": "selected"})
    selected_ref = store.put_bytes(
        raw,
        PutOptions(
            kind="test.cache_bounded_json",
            media_type="application/json",
            canon=CoreCanonInfo(),
        ),
        return_selected_profile=True,
    )

    result = read_core_json_artifact_bounded(
        store,
        selected_ref,
        limits=CoreJsonReadLimits(
            max_bytes=1024,
            max_depth=8,
            max_elements=16,
            max_manifest_bytes=4096,
        ),
    )

    assert result.value == {"value": "selected"}
    assert result.profile_read.reader_policy_id == "core-tag-policy@1"
    assert remote.manifest_receipt_calls == 1
    assert remote.member_open_calls == 1
    assert remote.get_bytes_calls == 0


def test_bounded_cache_refuses_when_durable_owner_lacks_receipts(
    tmp_path: Path,
) -> None:
    local = FileSystemCAS(tmp_path / "bounded-unsupported-local")
    remote_base = FileSystemCAS(tmp_path / "bounded-unsupported-remote")
    raw = to_canonical_bytes({"value": "selected"})
    options = PutOptions(
        kind="test.cache_bounded_unavailable",
        media_type="application/json",
        canon=CoreCanonInfo(),
    )
    selected_ref = remote_base.put_bytes(raw, options, return_selected_profile=True)
    local.put_bytes(raw, options, return_selected_profile=True)

    class LegacyOwner:
        def __init__(self, target: FileSystemCAS) -> None:
            self._target = target
            self.get_bytes_calls = 0

        def __getattr__(self, name: str):
            if name in {"read_raw_manifest_bytes_bounded", "open_member_bounded"}:
                raise AttributeError(name)
            return getattr(self._target, name)

        def get_bytes(self, selected):
            self.get_bytes_calls += 1
            return self._target.get_bytes(selected)

    remote = LegacyOwner(remote_base)
    store = CachingArtifactStore(remote=remote, local=local, write_through=True)

    with pytest.raises(CoreJsonReadBoundsRefusalError) as refusal:
        read_core_json_artifact_bounded(
            store,
            selected_ref,
            limits=CoreJsonReadLimits(
                max_bytes=1024,
                max_depth=8,
                max_elements=16,
                max_manifest_bytes=4096,
            ),
        )

    assert refusal.value.code == "canon_profile_bounded_manifest_unavailable"
    assert refusal.value.source_usage_complete is False
    assert remote.get_bytes_calls == 0
    assert local.get_bytes(selected_ref) == raw


def test_cache_refuses_unsupported_profile_owner_before_local_write(
    tmp_path: Path,
) -> None:
    class LegacyRemote:
        def put_bytes(self, data, opts):
            raise AssertionError("unsupported remote must not be called")

        def put_json(self, obj, opts, canon_spec=None):
            raise AssertionError("unsupported remote must not be called")

    local = FileSystemCAS(tmp_path / "local")
    cached = CachingArtifactStore(remote=LegacyRemote(), local=local, write_through=True)
    with pytest.raises(
        NotImplementedError,
        match="artifact_store_return_selected_profile_unsupported",
    ):
        cached.put_bytes(
            b"must not mutate local",
            PutOptions(kind="test.cache_profile_unsupported", media_type="text/plain"),
            return_selected_profile=True,
        )
    assert local.iter_artifact_ids() == []


@pytest.mark.parametrize(
    "signature_kind",
    ["positional_only", "variadic_positional", "variadic_keyword"],
)
def test_cache_refuses_non_keyword_profile_parameter_before_local_write(
    signature_kind: str,
    tmp_path: Path,
) -> None:
    class PositionalOnlyRemote:
        called = False

        def put_bytes(self, data, opts, return_selected_profile=False, /):
            self.called = True

    class VariadicPositionalRemote:
        called = False

        def put_bytes(self, data, opts, *return_selected_profile):
            self.called = True

    class VariadicKeywordRemote:
        called = False

        def put_bytes(self, data, opts, **return_selected_profile):
            self.called = True

    remote_type = {
        "positional_only": PositionalOnlyRemote,
        "variadic_positional": VariadicPositionalRemote,
        "variadic_keyword": VariadicKeywordRemote,
    }[signature_kind]
    remote = remote_type()
    local = FileSystemCAS(tmp_path / signature_kind)
    cached = CachingArtifactStore(remote=remote, local=local, write_through=True)

    with pytest.raises(
        NotImplementedError,
        match="artifact_store_return_selected_profile_unsupported",
    ):
        cached.put_bytes(
            b"must not mutate local",
            PutOptions(kind="test.cache_bad_profile_signature", media_type="text/plain"),
            return_selected_profile=True,
        )

    assert remote.called is False
    assert local.iter_artifact_ids() == []


def _make_ref(kind: str = "test") -> ArtifactRef:
    return ArtifactRef(artifact_id=_FAKE_ID, kind=kind, media_type="text/plain")


class TestCachingArtifactStore:
    def test_cold_readthrough_loads_and_caches_exact_selected_raw_manifest(self, tmp_path: Path):
        """A cold local cache reads the selected raw sidecar from its remote owner."""
        exact_bytes = b'{"nested":{"value":1}}'
        remote = FileSystemCAS(tmp_path / "remote-selected-profile")
        local = FileSystemCAS(tmp_path / "local-selected-profile")
        default_ref = remote.put_bytes(
            exact_bytes,
            ArtifactWriteOptions(
                kind="cache.selected.default-kind",
                media_type="application/json",
                canon=CoreCanonInfo(max_depth=0),
            ),
        )
        selected_ref = remote.put_bytes(
            exact_bytes,
            ArtifactWriteOptions(
                kind="cache.selected.remote-kind",
                media_type="application/json",
                canon=CoreCanonInfo(max_depth=8),
            ),
        )
        assert default_ref.artifact_id == selected_ref.artifact_id
        assert selected_ref.manifest_profile_sha256 is not None
        remote_manifest_bytes = remote.get_manifest_bytes(selected_ref)
        assert local.has(selected_ref) is False

        cached = CachingArtifactStore(remote=remote, local=local, write_through=False)
        loaded = get_json_artifact(ensure_ir_artifact_store(cached), selected_ref)

        assert loaded == {"nested": {"value": 1}}
        assert local.has(selected_ref) is True
        assert local.get_manifest_bytes(selected_ref) == remote_manifest_bytes
        assert local.get_manifest(selected_ref).kind == "cache.selected.remote-kind"
        assert local.get_manifest(selected_ref).canon.max_depth == 8

        wrong_profile = ArtifactRef(
            artifact_id=selected_ref.artifact_id,
            kind=selected_ref.kind,
            media_type=selected_ref.media_type,
            manifest_profile_sha256="sha256:" + "f" * 64,
        )
        with pytest.raises((FileNotFoundError, ArtifactIntegrityError)):
            get_json_artifact(ensure_ir_artifact_store(cached), wrong_profile)
        assert local.has(wrong_profile) is False

    def test_get_bytes_local_hit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An admitted exact local view serves bytes without a remote blob read."""
        payload = b"cached"
        local = FileSystemCAS(tmp_path / "local")
        remote = FileSystemCAS(tmp_path / "remote")
        remote_ref = remote.put_bytes(
            payload,
            PutOptions(kind="cache.local-hit", media_type="text/plain"),
        )
        remote_manifest = remote.get_manifest(remote_ref)
        exact_remote_view = ArtifactRef(
            artifact_id=remote_ref.artifact_id,
            kind=remote_manifest.kind,
            media_type=remote_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(remote_manifest),
        )
        local.import_exact_view(
            payload,
            remote.get_manifest_bytes(remote_ref),
            artifact_id=exact_remote_view,
        )
        remote_get_bytes = MagicMock(wraps=remote.get_bytes)
        monkeypatch.setattr(remote, "get_bytes", remote_get_bytes)

        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_bytes(remote_ref) == payload
        remote_get_bytes.assert_not_called()

    def test_get_bytes_local_miss_remote_hit(self, tmp_path: Path) -> None:
        """An exact-view cache miss fetches from its owner and preserves that view."""
        payload = b"remote-data"
        local = FileSystemCAS(tmp_path / "local-miss")
        remote = FileSystemCAS(tmp_path / "remote-miss")
        remote_ref = remote.put_bytes(
            payload,
            PutOptions(kind="cache.remote-miss", media_type="text/plain"),
        )
        remote_manifest = remote.get_manifest(remote_ref)
        exact_remote_view = ArtifactRef(
            artifact_id=remote_ref.artifact_id,
            kind=remote_manifest.kind,
            media_type=remote_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(remote_manifest),
        )

        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_bytes(remote_ref) == payload
        assert local.has(exact_remote_view) is True
        assert local.get_manifest(exact_remote_view) == remote_manifest

    def test_get_bytes_cache_population_failure_can_raise(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Cache population degradation is explicit when policy is `raise`."""
        local = FileSystemCAS(tmp_path / "local-population-failure")
        remote = FileSystemCAS(tmp_path / "remote-population-failure")
        remote_ref = remote.put_bytes(
            b"remote-data",
            PutOptions(kind="cache.population-failure", media_type="text/plain"),
        )
        monkeypatch.setattr(
            local,
            "import_exact_view",
            MagicMock(side_effect=OSError("cache disk unavailable")),
        )
        store = CachingArtifactStore(
            remote=remote,
            local=local,
            cache_population_failure_policy="raise",
        )

        with pytest.raises(OSError, match="cache disk unavailable"):
            store.get_bytes(remote_ref)

    def test_put_bytes_write_through(self, tmp_path: Path) -> None:
        """Write-through: both owners persist the same typed view and payload."""
        local = FileSystemCAS(tmp_path / "local-write-through")
        remote = FileSystemCAS(tmp_path / "remote-write-through")
        store = CachingArtifactStore(remote=remote, local=local, write_through=True)
        opts = PutOptions(kind="test", media_type="text/plain")
        ref = store.put_bytes(b"data", opts)

        assert local.get_bytes(ref) == b"data"
        assert remote.get_bytes(ref) == b"data"
        assert store.get_manifest(ref).kind == "test"
        assert ManifestLifecycle.profile_sha256(
            local.get_manifest(ref)
        ) == ManifestLifecycle.profile_sha256(remote.get_manifest(ref))

    @pytest.mark.parametrize("failure_policy", ["warn", "raise"])
    def test_put_bytes_preserves_durable_write_when_cache_population_fails(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        failure_policy: str,
    ) -> None:
        local = FileSystemCAS(tmp_path / "write-failure-local")
        remote = FileSystemCAS(tmp_path / "write-failure-remote")
        monkeypatch.setattr(
            local,
            "import_exact_view",
            MagicMock(side_effect=OSError("cache disk unavailable")),
        )
        store = CachingArtifactStore(
            remote=remote,
            local=local,
            cache_population_failure_policy=failure_policy,
        )
        payload = b"durable write survives cache failure"

        if failure_policy == "raise":
            with pytest.raises(OSError, match="cache disk unavailable"):
                store.put_bytes(
                    payload,
                    PutOptions(kind="cache.write-failure", media_type="text/plain"),
                )
        else:
            returned_ref = store.put_bytes(
                payload,
                PutOptions(kind="cache.write-failure", media_type="text/plain"),
            )

        durable_ids = remote.iter_artifact_ids()
        assert len(durable_ids) == 1
        durable_ref = durable_ids[0]
        assert remote.get_bytes(durable_ref) == payload
        if failure_policy == "warn":
            assert returned_ref.artifact_id == durable_ref

    @pytest.mark.parametrize("operation", ["put_bytes", "put_json"])
    @pytest.mark.parametrize("failure_method", ["get_manifest", "get_manifest_bytes"])
    @pytest.mark.parametrize("failure_policy", ["warn", "raise"])
    def test_postcommit_owner_manifest_read_failure_obeys_degradation_policy(
        self,
        tmp_path: Path,
        failure_policy: str,
        failure_method: str,
        operation: str,
    ) -> None:
        durable = FileSystemCAS(tmp_path / "owner-read-failure-remote")
        local = FileSystemCAS(tmp_path / "owner-read-failure-local")
        remote = _OwnerManifestReadFailureStore(durable, failure_method)
        store = CachingArtifactStore(
            remote=remote,
            local=local,
            cache_population_failure_policy=failure_policy,
        )
        opts = PutOptions(kind="cache.owner-read-failure", media_type="application/json")
        value = {"committed": True, "operation": operation}
        expected = to_canonical_bytes(value) if operation == "put_json" else b"committed bytes"

        def write() -> ArtifactRef:
            if operation == "put_json":
                return store.put_json(value, opts)
            return store.put_bytes(expected, opts)

        if failure_policy == "raise":
            with pytest.raises(
                OSError,
                match="durable owner selected manifest read unavailable",
            ):
                write()
        else:
            returned_ref = write()
            assert remote.committed is True
            assert returned_ref == remote.last_ref

        assert remote.committed is True
        durable_ids = durable.iter_artifact_ids()
        assert len(durable_ids) == 1
        assert durable.get_bytes(durable_ids[0]) == expected
        assert not local.has(durable_ids[0])

    @pytest.mark.parametrize("operation", ["put_bytes", "put_json"])
    @pytest.mark.parametrize(
        "missing_side",
        ["remote_raw_manifest", "local_exact_import"],
    )
    @pytest.mark.parametrize("failure_policy", ["warn", "raise"])
    def test_write_through_skips_cache_without_exact_copy_capabilities(
        self,
        tmp_path: Path,
        operation: str,
        missing_side: str,
        failure_policy: str,
    ) -> None:
        durable = FileSystemCAS(tmp_path / "missing-exact-cap-remote")
        local_storage = FileSystemCAS(tmp_path / "missing-exact-cap-local")
        local_import = MagicMock(wraps=local_storage.import_exact_view)
        local_storage.import_exact_view = local_import
        remote_manifest_reader = MagicMock(wraps=durable.get_manifest_bytes)
        durable.get_manifest_bytes = remote_manifest_reader
        remote = (
            _CapabilityLimitedStore(durable, "get_manifest_bytes")
            if missing_side == "remote_raw_manifest"
            else durable
        )
        local = (
            _CapabilityLimitedStore(local_storage, "import_exact_view")
            if missing_side == "local_exact_import"
            else local_storage
        )
        store = CachingArtifactStore(
            remote=remote,
            local=local,
            cache_population_failure_policy=failure_policy,
        )
        opts = PutOptions(
            kind="cache.missing-exact-capability",
            media_type="application/json" if operation == "put_json" else "text/plain",
            producer=ProducerInfo(component="tests.cache", version=missing_side),
        )
        value = {"written": True, "missing_side": missing_side}
        payload = to_canonical_bytes(value) if operation == "put_json" else b"exact owner bytes"

        def write() -> ArtifactRef:
            if operation == "put_json":
                return store.put_json(value, opts, return_selected_profile=True)
            return store.put_bytes(payload, opts, return_selected_profile=True)

        if failure_policy == "raise":
            with pytest.raises(RuntimeError, match="exact selected"):
                write()
        else:
            returned_ref = write()
            assert returned_ref.manifest_profile_sha256 is not None

        durable_ids = durable.iter_artifact_ids()
        assert len(durable_ids) == 1
        durable_ref = durable_ids[0]
        durable_manifest = durable.get_manifest(durable_ref)
        selected_ref = ArtifactRef(
            artifact_id=durable_ref,
            kind=durable_manifest.kind,
            media_type=durable_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(durable_manifest),
        )
        assert durable.get_bytes(durable_ref) == payload
        assert durable.get_manifest(selected_ref) == durable_manifest
        assert not local_storage.has_manifest_view(
            durable_ref,
            selected_ref.manifest_profile_sha256,
        )
        local_import.assert_not_called()
        if missing_side == "remote_raw_manifest":
            remote_manifest_reader.assert_not_called()
        if failure_policy == "warn":
            assert returned_ref.artifact_id == durable_ref
            assert returned_ref.manifest_profile_sha256 == selected_ref.manifest_profile_sha256

    @pytest.mark.parametrize(
        "missing_side",
        ["remote_raw_manifest", "local_exact_import"],
    )
    @pytest.mark.parametrize("failure_policy", ["warn", "raise"])
    def test_readthrough_skips_cache_without_exact_copy_capabilities(
        self,
        tmp_path: Path,
        missing_side: str,
        failure_policy: str,
    ) -> None:
        durable = FileSystemCAS(tmp_path / "readthrough-missing-cap-remote")
        local_storage = FileSystemCAS(tmp_path / "readthrough-missing-cap-local")
        payload = b"readthrough stays owned by the durable store"
        ref = durable.put_bytes(
            payload,
            PutOptions(kind="cache.readthrough-missing-capability", media_type="text/plain"),
        )
        remote_bytes = MagicMock(wraps=durable.get_bytes)
        durable.get_bytes = remote_bytes
        remote_manifest_reader = MagicMock(wraps=durable.get_manifest_bytes)
        durable.get_manifest_bytes = remote_manifest_reader
        local_import = MagicMock(wraps=local_storage.import_exact_view)
        local_storage.import_exact_view = local_import
        remote = (
            _CapabilityLimitedStore(durable, "get_manifest_bytes")
            if missing_side == "remote_raw_manifest"
            else durable
        )
        local = (
            _CapabilityLimitedStore(local_storage, "import_exact_view")
            if missing_side == "local_exact_import"
            else local_storage
        )
        store = CachingArtifactStore(
            remote=remote,
            local=local,
            cache_population_failure_policy=failure_policy,
        )

        if failure_policy == "raise":
            with pytest.raises(RuntimeError, match="exact selected"):
                store.get_bytes(ref.artifact_id)
        else:
            assert store.get_bytes(ref.artifact_id) == payload

        remote_bytes.assert_called_once()
        assert not local_storage.has(ref.artifact_id)
        local_import.assert_not_called()
        if missing_side == "remote_raw_manifest":
            remote_manifest_reader.assert_not_called()
        assert store.get_manifest(ref.artifact_id) == durable.get_manifest(ref.artifact_id)
        if missing_side == "remote_raw_manifest":
            with pytest.raises(TypeError, match="get_manifest_bytes"):
                store.get_manifest_bytes(ref.artifact_id)
        else:
            assert store.get_manifest_bytes(ref.artifact_id) == durable.get_manifest_bytes(
                ref.artifact_id
            )

    def test_malformed_durable_manifest_is_not_cache_degradation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        durable = FileSystemCAS(tmp_path / "malformed-owner-remote")
        local = FileSystemCAS(tmp_path / "malformed-owner-local")
        malformed = MagicMock(side_effect=lambda selected: b"{malformed manifest")
        monkeypatch.setattr(durable, "get_manifest_bytes", malformed)
        store = CachingArtifactStore(remote=durable, local=local)

        with pytest.raises(ValidationError):
            store.put_bytes(
                b"durable write with malformed owner view",
                PutOptions(kind="cache.malformed-owner-view", media_type="text/plain"),
            )

        durable_ids = durable.iter_artifact_ids()
        assert len(durable_ids) == 1
        assert durable.get_bytes(durable_ids[0]) == b"durable write with malformed owner view"
        assert not local.has(durable_ids[0])

    def test_same_profile_raw_record_mismatch_is_not_cache_degradation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        durable = FileSystemCAS(tmp_path / "raw-record-mismatch-remote")
        local = FileSystemCAS(tmp_path / "raw-record-mismatch-local")
        store = CachingArtifactStore(remote=durable, local=local)
        original_get_manifest_bytes = durable.get_manifest_bytes
        original_put = durable.put_bytes

        def put_then_change_record(
            data: bytes,
            opts: PutOptions,
            *,
            return_selected_profile: bool = False,
        ) -> ArtifactRef:
            ref = original_put(
                data,
                opts,
                return_selected_profile=return_selected_profile,
            )
            manifest = durable.get_manifest(ref).model_copy(
                update={"created_at": datetime.fromisoformat("2026-10-25T00:00:22+00:00")}
            )
            monkeypatch.setattr(
                durable,
                "get_manifest_bytes",
                lambda selected: manifest.model_dump_json().encode("utf-8"),
            )
            return ref

        monkeypatch.setattr(durable, "put_bytes", put_then_change_record)
        with pytest.raises(ArtifactIntegrityError, match="raw manifest differs"):
            store.put_bytes(
                b"same profile, different owner record",
                PutOptions(
                    kind="cache.same-profile-record-mismatch",
                    media_type="text/plain",
                    producer=ProducerInfo(component="tests.cache", version="same"),
                ),
            )
        durable_ids = durable.iter_artifact_ids()
        assert len(durable_ids) == 1
        owner_manifest = durable.get_manifest(durable_ids[0])
        changed_manifest = owner_manifest.model_copy(
            update={"created_at": datetime.fromisoformat("2026-10-25T00:00:22+00:00")}
        )
        assert durable.get_manifest_bytes(durable_ids[0]) != original_get_manifest_bytes(
            durable_ids[0]
        )
        assert ManifestLifecycle.profile_sha256(owner_manifest) == ManifestLifecycle.profile_sha256(
            changed_manifest
        )
        assert not local.has(durable_ids[0])

    def test_put_bytes_no_write_through(self):
        """write_through=False: only writes to local."""
        local = MagicMock()
        remote = MagicMock()
        local.put_bytes.return_value = _make_ref()

        store = CachingArtifactStore(remote=remote, local=local, write_through=False)
        opts = PutOptions(kind="test", media_type="text/plain")
        store.put_bytes(b"data", opts)

        local.put_bytes.assert_called_once()
        remote.put_bytes.assert_not_called()

    def test_write_through_false_keeps_local_store_as_default_owner(
        self,
        tmp_path: Path,
    ) -> None:
        local = FileSystemCAS(tmp_path / "local-only")
        remote = FileSystemCAS(tmp_path / "unused-remote")
        store = CachingArtifactStore(remote=remote, local=local, write_through=False)
        options = PutOptions(
            kind="cache.local-only",
            media_type="text/plain",
            producer=ProducerInfo(component="tests.cache", version="local-only"),
        )

        ref = store.put_bytes(b"local-only artifact", options)

        assert remote.iter_artifact_ids() == []
        assert store.has(ref) is True
        assert store.iter_artifact_ids() == [ref.artifact_id]
        assert store.get_manifest(ref).producer.version == "local-only"
        assert store.verify(ref).ok is True

    def test_write_through_selectorless_has_uses_remote_default_owner(
        self,
        tmp_path: Path,
    ) -> None:
        local = FileSystemCAS(tmp_path / "cache-only")
        remote = FileSystemCAS(tmp_path / "durable-owner")
        local_ref = local.put_bytes(
            b"local-only orphan",
            PutOptions(
                kind="cache.default-owner",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="cache-only"),
            ),
        )
        local_manifest = local.get_manifest(local_ref)
        selected_local_view = ArtifactRef(
            artifact_id=local_ref.artifact_id,
            kind=local_manifest.kind,
            media_type=local_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(local_manifest),
        )
        store = CachingArtifactStore(remote=remote, local=local)

        assert store.has(local_ref.artifact_id) is False
        assert store.has(selected_local_view) is False
        with pytest.raises(FileNotFoundError):
            store.get_manifest(selected_local_view)
        with pytest.raises(FileNotFoundError):
            store.verify(selected_local_view)

    def test_write_through_inventory_omits_cache_only_default_orphans(
        self,
        tmp_path: Path,
    ) -> None:
        local = FileSystemCAS(tmp_path / "cache-only-inventory")
        remote = FileSystemCAS(tmp_path / "durable-inventory")
        local.put_bytes(
            b"local-only inventory orphan",
            PutOptions(kind="cache.inventory", media_type="text/plain"),
        )
        remote_ref = remote.put_bytes(
            b"durable inventory artifact",
            PutOptions(kind="cache.inventory", media_type="text/plain"),
        )

        assert CachingArtifactStore(remote=remote, local=local).iter_artifact_ids() == [
            remote_ref.artifact_id
        ]

    def test_has_selector_free_delegates_to_remote_default_owner(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = True
        remote.has.return_value = False

        store = CachingArtifactStore(remote=remote, local=local)
        assert store.has(_FAKE_ID) is False
        remote.has.assert_called_once_with(_FAKE_ID)
        local.has.assert_not_called()

    def test_has_local_false_remote_true(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = False
        remote.has.return_value = True

        store = CachingArtifactStore(remote=remote, local=local)
        assert store.has(_FAKE_ID) is True

    def test_verify_selector_free_delegates_to_remote(self):
        local = MagicMock()
        remote = MagicMock()
        local.has.return_value = True
        expected = MagicMock(ok=True)
        remote.verify.return_value = expected

        store = CachingArtifactStore(remote=remote, local=local)
        report = store.verify(_FAKE_ID)
        assert report.ok is True
        remote.verify.assert_called_once_with(_FAKE_ID)
        local.verify.assert_not_called()

    def test_verify_selected_view_uses_local_when_cached(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        remote = FileSystemCAS(tmp_path / "remote")
        local = FileSystemCAS(tmp_path / "local")
        payload = b"selected view for cached verification"
        remote_ref = remote.put_bytes(
            payload,
            PutOptions(kind="test", media_type="text/plain"),
        )
        remote_manifest = remote.get_manifest(remote_ref)
        selected_ref = ArtifactRef(
            artifact_id=remote_ref.artifact_id,
            kind=remote_manifest.kind,
            media_type=remote_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(remote_manifest),
        )
        local.import_exact_view(
            payload,
            remote.get_manifest_bytes(selected_ref),
            artifact_id=selected_ref,
        )
        local_verify = MagicMock(wraps=local.verify)
        remote_verify = MagicMock(wraps=remote.verify)
        monkeypatch.setattr(local, "verify", local_verify)
        monkeypatch.setattr(remote, "verify", remote_verify)

        report = CachingArtifactStore(remote=remote, local=local).verify(selected_ref)

        assert report.ok is True
        local.verify.assert_called_once_with(selected_ref)
        remote_verify.assert_not_called()

    def test_remote_population_preserves_the_complete_selected_manifest_profile(
        self,
        tmp_path: Path,
    ) -> None:
        remote = FileSystemCAS(tmp_path / "remote")
        local = FileSystemCAS(tmp_path / "local")
        selected = remote.put_bytes(
            b"cache exact-view bytes",
            PutOptions(
                kind="cache.selected.view",
                media_type="application/octet-stream",
                tenant_context=ArtifactTenantContextInfo(tenant_id="tenant-a"),
            ),
        )
        selected_manifest = remote.get_manifest(selected)
        exact_selected = ArtifactRef(
            artifact_id=selected.artifact_id,
            kind=selected_manifest.kind,
            media_type=selected_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(selected_manifest),
        )
        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_bytes(selected) == b"cache exact-view bytes"

        assert local.has(exact_selected)
        assert local.get_manifest(exact_selected) == selected_manifest
        assert not local.has(selected)

    def test_selectorless_manifest_read_uses_remote_default_when_cache_defaults_diverge(
        self,
        tmp_path: Path,
    ) -> None:
        """The remote default wins when equal bytes have distinct first-writer profiles."""
        payload = b"same bytes, independent cache defaults"
        local = FileSystemCAS(tmp_path / "local")
        remote = FileSystemCAS(tmp_path / "remote")
        local_ref = local.put_bytes(
            payload,
            PutOptions(
                kind="cache.shared-kind",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="local-first"),
            ),
        )
        remote_ref = remote.put_bytes(
            payload,
            PutOptions(
                kind="cache.shared-kind",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="remote-first"),
            ),
        )
        assert local_ref.artifact_id == remote_ref.artifact_id
        assert local_ref == remote_ref
        assert (
            local.get_manifest(local_ref).producer.version
            != remote.get_manifest(remote_ref).producer.version
        )

        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_manifest(remote_ref).producer.version == "remote-first"
        assert store.get_manifest(remote_ref.artifact_id).producer.version == "remote-first"
        assert store.has(remote_ref.artifact_id) is True
        assert store.iter_artifact_ids() == [remote_ref.artifact_id]
        # Payload reads and byte-integrity reports remain valid because the blob ID is shared.
        assert store.get_bytes(remote_ref) == payload
        assert store.verify(remote_ref).ok is True

    @pytest.mark.parametrize(
        ("local_kind", "remote_kind", "local_version", "remote_version"),
        [
            (
                "cache.shared-kind",
                "cache.shared-kind",
                "stale-local-profile",
                "current-remote-profile",
            ),
            (
                "cache.local-default",
                "cache.remote-default",
                "local-first",
                "remote-first",
            ),
        ],
        ids=("same-kind-stale-profile", "different-kind-default"),
    )
    def test_selector_free_read_pins_remote_profile_when_cache_default_diverges(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        local_kind: str,
        remote_kind: str,
        local_version: str,
        remote_version: str,
    ) -> None:
        """A stale local alias cannot shadow the remote owner's selected profile."""
        payload = b"same content-addressed bytes, different default profiles"
        local = FileSystemCAS(tmp_path / "local-kind")
        remote = FileSystemCAS(tmp_path / "remote-kind")
        local_ref = local.put_bytes(
            payload,
            PutOptions(
                kind=local_kind,
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version=local_version),
            ),
        )
        remote_ref = remote.put_bytes(
            payload,
            PutOptions(
                kind=remote_kind,
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version=remote_version),
            ),
        )
        assert local_ref.artifact_id == remote_ref.artifact_id
        local_profile_sha256 = ManifestLifecycle.profile_sha256(local.get_manifest(local_ref))
        remote_profile_sha256 = ManifestLifecycle.profile_sha256(remote.get_manifest(remote_ref))
        assert local_profile_sha256 != remote_profile_sha256
        local_get_bytes = MagicMock(wraps=local.get_bytes)
        local_has_view = MagicMock(wraps=local.has_manifest_view)
        remote_get_bytes = MagicMock(wraps=remote.get_bytes)
        monkeypatch.setattr(local, "get_bytes", local_get_bytes)
        monkeypatch.setattr(local, "has_manifest_view", local_has_view)
        monkeypatch.setattr(remote, "get_bytes", remote_get_bytes)

        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_bytes(remote_ref) == payload
        local_get_bytes.assert_not_called()
        local_has_view.assert_called_once_with(remote_ref.artifact_id, remote_profile_sha256)
        remote_get_bytes.assert_called_once()
        assert remote_get_bytes.call_args.args[0].manifest_profile_sha256 == remote_profile_sha256

    def test_selected_remote_view_uses_matching_local_view_when_defaults_diverge(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An explicitly admitted exact view remains eligible for local caching."""
        payload = b"selected remote view remains locally readable"
        local = FileSystemCAS(tmp_path / "selected-local")
        remote = FileSystemCAS(tmp_path / "selected-remote")
        local.put_bytes(
            payload,
            PutOptions(kind="cache.local-default", media_type="text/plain"),
        )
        remote_default = remote.put_bytes(
            payload,
            PutOptions(kind="cache.remote-default", media_type="text/plain"),
        )
        remote_manifest = remote.get_manifest(remote_default)
        selected_remote_view = ArtifactRef(
            artifact_id=remote_default.artifact_id,
            kind=remote_manifest.kind,
            media_type=remote_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(remote_manifest),
        )
        local.import_exact_view(
            payload,
            remote.get_manifest_bytes(remote_default),
            artifact_id=selected_remote_view,
        )
        local_get_bytes = MagicMock(wraps=local.get_bytes)
        remote_get_bytes = MagicMock(wraps=remote.get_bytes)
        monkeypatch.setattr(local, "get_bytes", local_get_bytes)
        monkeypatch.setattr(remote, "get_bytes", remote_get_bytes)

        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_bytes(selected_remote_view) == payload
        local_get_bytes.assert_called_once_with(selected_remote_view)
        remote_get_bytes.assert_not_called()

    def test_corrupt_admitted_exact_cache_view_fails_closed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An admitted exact view with corrupt bytes is an integrity error, not a miss."""
        payload = b"integrity failures remain fail-closed"
        local = FileSystemCAS(tmp_path / "corrupt-local")
        remote = FileSystemCAS(tmp_path / "corrupt-remote")
        remote_ref = remote.put_bytes(
            payload,
            PutOptions(kind="cache.integrity", media_type="application/octet-stream"),
        )
        manifest = remote.get_manifest(remote_ref)
        exact_ref = ArtifactRef(
            artifact_id=remote_ref.artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(manifest),
        )
        local.import_exact_view(
            payload,
            remote.get_manifest_bytes(remote_ref),
            artifact_id=exact_ref,
        )
        blob_path, _manifest_path = local._paths(remote_ref.artifact_id)
        blob_path.write_bytes(b"corrupt local blob")
        remote_get_bytes = MagicMock(wraps=remote.get_bytes)
        monkeypatch.setattr(remote, "get_bytes", remote_get_bytes)

        store = CachingArtifactStore(remote=remote, local=local)

        with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
            store.get_bytes(remote_ref)
        remote_get_bytes.assert_not_called()

    def test_exact_cached_view_requires_durable_tenant_admission(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A local exact-view hit cannot bypass its durable owner's tenant boundary."""
        payload = b"tenant-a exact-view cache entry"
        remote = FileSystemCAS(tmp_path / "tenant-owner").with_ambient_ownership_enforcement()
        local = FileSystemCAS(tmp_path / "shared-local-cache")
        store = guard_runtime_cas(CachingArtifactStore(remote=remote, local=local))
        try:
            with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
                owner_ref = remote.put_bytes(
                    payload,
                    PutOptions(kind="cache.tenant-bound", media_type="application/octet-stream"),
                )
                owner_manifest = remote.get_manifest(owner_ref)
                exact_ref = ArtifactRef(
                    artifact_id=owner_ref.artifact_id,
                    kind=owner_manifest.kind,
                    media_type=owner_manifest.media_type,
                    manifest_profile_sha256=ManifestLifecycle.profile_sha256(owner_manifest),
                )
                # First guarded read populates the same unscoped local cache used
                # by cached S3/GCS configurations.
                assert store.get_bytes(exact_ref) == payload
                assert local.has_manifest_view(
                    exact_ref.artifact_id,
                    exact_ref.manifest_profile_sha256,
                )

            remote_get_manifest = MagicMock(wraps=remote.get_manifest)
            remote_get_bytes = MagicMock(wraps=remote.get_bytes)
            local_has_manifest_view = MagicMock(wraps=local.has_manifest_view)
            local_has = MagicMock(wraps=local.has)
            local_get_bytes = MagicMock(wraps=local.get_bytes)
            local_get_manifest = MagicMock(wraps=local.get_manifest)
            local_verify = MagicMock(wraps=local.verify)
            monkeypatch.setattr(remote, "get_manifest", remote_get_manifest)
            monkeypatch.setattr(remote, "get_bytes", remote_get_bytes)
            monkeypatch.setattr(local, "has_manifest_view", local_has_manifest_view)
            monkeypatch.setattr(local, "has", local_has)
            monkeypatch.setattr(local, "get_bytes", local_get_bytes)
            monkeypatch.setattr(local, "get_manifest", local_get_manifest)
            monkeypatch.setattr(local, "verify", local_verify)

            with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
                assert store.get_bytes(exact_ref) == payload
                assert store.has(exact_ref)
                assert store.get_manifest(exact_ref).kind == exact_ref.kind
                assert store.verify(exact_ref).ok
            remote_get_bytes.assert_not_called()
            local_get_bytes.assert_called_once_with(exact_ref)
            local_has_manifest_view.assert_called()
            local_has.assert_called_with(exact_ref)
            local_get_manifest.assert_called()
            local_verify.assert_called_once_with(exact_ref)

            remote_get_manifest.reset_mock()
            local_has_manifest_view.reset_mock()
            local_has.reset_mock()
            local_get_bytes.reset_mock()
            local_get_manifest.reset_mock()
            local_verify.reset_mock()
            with tenant_scope(None, tenant_id="tenant-b", cell_id="cell-a"):
                with pytest.raises(ArtifactOwnershipError):
                    store.get_bytes(exact_ref)
                with pytest.raises(ArtifactOwnershipError):
                    store.has(exact_ref)
                with pytest.raises(ArtifactOwnershipError):
                    store.get_manifest(exact_ref)
                with pytest.raises(ArtifactOwnershipError):
                    store.verify(exact_ref)

            assert remote_get_manifest.call_count == 4
            remote_get_bytes.assert_not_called()
            local_has_manifest_view.assert_not_called()
            local_has.assert_not_called()
            local_get_bytes.assert_not_called()
            local_get_manifest.assert_not_called()
            local_verify.assert_not_called()
        finally:
            store.close()

    def test_selectorless_verification_uses_remote_default_when_cache_defaults_diverge(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = b"verify must follow the composite default owner"
        local = FileSystemCAS(tmp_path / "verify-local")
        remote = FileSystemCAS(tmp_path / "verify-remote")
        local_ref = local.put_bytes(
            payload,
            PutOptions(
                kind="cache.verify-default",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="local-first"),
            ),
        )
        remote_ref = remote.put_bytes(
            payload,
            PutOptions(
                kind="cache.verify-default",
                media_type="text/plain",
                producer=ProducerInfo(component="tests.cache", version="remote-first"),
            ),
        )
        assert local_ref == remote_ref
        assert local.get_manifest(local_ref).producer.version == "local-first"
        assert remote.get_manifest(remote_ref).producer.version == "remote-first"
        assert local.has(remote_ref)

        local_verify = MagicMock(
            side_effect=AssertionError("selector-free verification used the cache default")
        )
        monkeypatch.setattr(local, "verify", local_verify)

        report = CachingArtifactStore(remote=remote, local=local).verify(remote_ref)

        assert report.ok is True
        local_verify.assert_not_called()

    @pytest.mark.parametrize("operation", ["put_bytes", "put_json"])
    @pytest.mark.parametrize("seed_local_default", [True, False])
    def test_write_through_accepts_remote_view_when_cache_defaults_diverge(
        self,
        tmp_path: Path,
        operation: str,
        seed_local_default: bool,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _install_manifest_timestamps(
            monkeypatch,
            "2026-10-25T00:00:00+00:00",
            "2026-10-25T00:00:01+00:00",
            "2026-10-25T00:00:02+00:00",
        )
        local = FileSystemCAS(tmp_path / "write-local")
        remote = FileSystemCAS(tmp_path / "write-remote")
        payload = {"shared": "write-through payload"} if operation == "put_json" else b"shared"
        media_type = "application/json" if operation == "put_json" else "text/plain"

        def options(version: str) -> PutOptions:
            return PutOptions(
                kind="cache.write-through-view",
                media_type=media_type,
                producer=ProducerInfo(component="tests.cache", version=version),
            )

        seeded_store = local if seed_local_default else remote
        if operation == "put_json":
            seeded_ref = seeded_store.put_json(payload, options("existing-default"))
        else:
            seeded_ref = seeded_store.put_bytes(payload, options("existing-default"))

        store = CachingArtifactStore(remote=remote, local=local)
        original_import = local.import_exact_view

        def import_after_remote_commit(
            data: bytes,
            manifest_bytes: bytes,
            *,
            artifact_id,
            signature_bytes: bytes | None = None,
        ):
            assert remote.has(artifact_id) is True
            return original_import(
                data,
                manifest_bytes,
                artifact_id=artifact_id,
                signature_bytes=signature_bytes,
            )

        monkeypatch.setattr(local, "import_exact_view", import_after_remote_commit)
        if operation == "put_json":
            written_ref = store.put_json(payload, options("new-view"))
        else:
            written_ref = store.put_bytes(payload, options("new-view"))

        remote_manifest = remote.get_manifest(written_ref)
        assert remote_manifest.producer.version == "new-view"
        exact_remote_view = ArtifactRef(
            artifact_id=written_ref.artifact_id,
            kind=remote_manifest.kind,
            media_type=remote_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(remote_manifest),
        )
        assert local.get_manifest(exact_remote_view) == remote_manifest
        assert local.get_manifest_bytes(exact_remote_view) == remote.get_manifest_bytes(written_ref)
        if seed_local_default:
            assert local.get_manifest(seeded_ref).producer.version == "existing-default"
        else:
            assert remote.get_manifest(seeded_ref).producer.version == "existing-default"
        assert store.get_manifest(written_ref).producer.version == "new-view"
        assert store.verify(written_ref).ok is True

    def test_selected_manifest_read_returns_owner_creation_time_when_profiles_match(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _install_manifest_timestamps(
            monkeypatch,
            "2026-10-25T00:00:10+00:00",
            "2026-10-25T00:00:11+00:00",
        )
        payload = b"same selected view with independent owner timestamps"
        options = PutOptions(
            kind="cache.same-profile",
            media_type="application/octet-stream",
            producer=ProducerInfo(component="tests.cache", version="same"),
        )
        local = FileSystemCAS(tmp_path / "same-profile-local")
        remote = FileSystemCAS(tmp_path / "same-profile-remote")
        local_ref = local.put_bytes(payload, options, return_selected_profile=True)
        remote_ref = remote.put_bytes(payload, options, return_selected_profile=True)
        local_manifest = local.get_manifest(local_ref)
        remote_manifest = remote.get_manifest(remote_ref)

        assert local_ref.manifest_profile_sha256 == remote_ref.manifest_profile_sha256
        assert local_manifest.created_at != remote_manifest.created_at
        assert local_manifest.model_dump(mode="json", exclude={"created_at"}) == (
            remote_manifest.model_dump(mode="json", exclude={"created_at"})
        )

        store = CachingArtifactStore(remote=remote, local=local)
        assert store.get_bytes(remote_ref) == payload
        selected = store.get_manifest(remote_ref)

        assert selected == remote_manifest

    def test_remote_child_read_skips_cache_when_input_view_is_not_locally_admitted(
        self,
        tmp_path: Path,
    ) -> None:
        remote = FileSystemCAS(tmp_path / "remote", tenant_id="tenant-a")
        local_root = tmp_path / "local"
        foreign_local = FileSystemCAS(local_root, tenant_id="tenant-b")
        local = FileSystemCAS(local_root, tenant_id="tenant-a")
        parent_options = PutOptions(
            kind="cache.parent",
            media_type="application/octet-stream",
            producer=ProducerInfo(component="tests.cache", version="parent"),
        )
        foreign_parent = foreign_local.put_bytes(b"shared parent bytes", parent_options)
        remote_parent = remote.put_bytes(b"shared parent bytes", parent_options)
        assert foreign_parent.artifact_id == remote_parent.artifact_id

        child_ref = remote.put_bytes(
            b"authorized remote child",
            PutOptions(
                kind="cache.child",
                media_type="application/octet-stream",
                producer=ProducerInfo(component="tests.cache", version="child"),
                inputs=(InputRef(artifact_id=remote_parent.artifact_id, role="parent"),),
            ),
        )
        # The local index admits the child blob for this reader, but has no local ownership
        # of the manifest's upstream view. The remote owner remains the authority for the
        # already-validated child read; cache population must not manufacture parent custody.
        local._ownership_index.record_blob_reader(
            child_ref.artifact_id,
            tenant_id="tenant-a",
        )
        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_bytes(child_ref) == b"authorized remote child"
        assert not local.has(child_ref)
        assert not local.has(remote_parent.artifact_id)
        with pytest.raises(PermissionError):
            local.get_bytes(remote_parent.artifact_id)

    def test_same_default_profile_remains_readable_through_cache(self, tmp_path: Path) -> None:
        payload = b"same default profile remains usable"
        opts = PutOptions(
            kind="cache.same-default",
            media_type="text/plain",
            producer=ProducerInfo(component="tests.cache", version="same"),
        )
        local = FileSystemCAS(tmp_path / "same-local")
        remote = FileSystemCAS(tmp_path / "same-remote")
        local_ref = local.put_bytes(payload, opts)
        remote_ref = remote.put_bytes(payload, opts)
        assert local_ref == remote_ref

        store = CachingArtifactStore(remote=remote, local=local)

        selected = store.get_manifest(remote_ref)
        assert selected.producer.version == "same"
        assert store.get_bytes(remote_ref) == payload
        assert store.verify(remote_ref).ok is True

    def test_cache_population_preserves_raw_manifest_and_signature_bytes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        payload = b"historical signed manifest must remain byte exact"
        remote = FileSystemCAS(tmp_path / "signed-remote")
        local = FileSystemCAS(tmp_path / "signed-local")
        key = Ed25519PrivateKey.generate()
        signer = Ed25519Signer(key)
        verifier = Ed25519Verifier()
        verifier.add_trusted_key(key.public_key())
        ref = remote.put_bytes(
            payload,
            PutOptions(kind="cache.signed", media_type="application/octet-stream"),
        )
        remote.sign_artifact(ref, signer, signer_identity="cache-test")
        remote_manifest_bytes = remote.get_manifest_bytes(ref)
        remote_signature_bytes = remote.get_signature_bytes(ref)
        manifest = remote.get_manifest(ref)
        exact_ref = ArtifactRef(
            artifact_id=ref.artifact_id,
            kind=manifest.kind,
            media_type=manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(manifest),
        )
        assert remote.verify_signature(ref, verifier).ok is True

        store = CachingArtifactStore(remote=remote, local=local)

        class HistoricalClock:
            @staticmethod
            def now(tz: tzinfo | None = None) -> datetime:
                return datetime(2000, 1, 1, tzinfo=tz)

        monkeypatch.setattr(
            "polisyos.core.artifacts.manifest.datetime",
            HistoricalClock,
        )
        assert store.get_bytes(ref) == payload

        assert local.get_manifest_bytes(exact_ref) == remote_manifest_bytes
        assert local.get_signature_bytes(exact_ref) == remote_signature_bytes
        assert local.verify_signature(exact_ref, verifier).ok is True

    def test_cache_does_not_copy_signature_after_default_moves_off_pinned_view(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A changed selector-free default cannot lend its signature to a pinned view."""
        payload = b"one blob, two manifest profiles"
        remote = FileSystemCAS(tmp_path / "moving-signed-remote")
        local = FileSystemCAS(tmp_path / "moving-signed-local")
        key = Ed25519PrivateKey.generate()
        signer = Ed25519Signer(key)
        default_ref = remote.put_bytes(
            payload,
            PutOptions(kind="cache.signed-default", media_type="application/octet-stream"),
        )
        default_manifest = remote.get_manifest(default_ref)
        pinned_ref = ArtifactRef(
            artifact_id=default_ref.artifact_id,
            kind=default_manifest.kind,
            media_type=default_manifest.media_type,
            manifest_profile_sha256=ManifestLifecycle.profile_sha256(default_manifest),
        )
        remote.sign_artifact(default_ref, signer, signer_identity="cache-test")
        moved_default_ref = remote.put_bytes(
            payload,
            PutOptions(kind="cache.moved-default", media_type="application/octet-stream"),
        )
        moved_default_bytes = remote.get_manifest_bytes(moved_default_ref)
        pinned_manifest_bytes = remote.get_manifest_bytes(pinned_ref)
        assert moved_default_bytes != pinned_manifest_bytes

        owner_manifest_reader = remote.get_manifest_bytes
        monkeypatch.setattr(
            remote,
            "get_manifest_bytes",
            lambda selected: (
                owner_manifest_reader(selected) if selected == pinned_ref else moved_default_bytes
            ),
        )
        signature_reader = MagicMock(wraps=remote.get_signature_bytes)
        monkeypatch.setattr(remote, "get_signature_bytes", signature_reader)

        store = CachingArtifactStore(remote=remote, local=local)

        assert store.get_bytes(default_ref) == payload
        assert local.has(pinned_ref) is True
        assert local.has_signature(pinned_ref) is False
        assert signature_reader.call_count == 1
        assert signature_reader.call_args.args[0] == pinned_ref


def test_cache_bounded_default_manifest_uses_only_durable_owner(tmp_path, monkeypatch) -> None:
    payload = b"same blob with independent durable and local defaults"
    local = FileSystemCAS(tmp_path / "bounded-local")
    remote = FileSystemCAS(tmp_path / "bounded-remote")
    local.put_bytes(
        payload,
        PutOptions(
            kind="cache.local-default",
            media_type="application/json",
            producer=ProducerInfo(component="tests.cache", version="local"),
        ),
    )
    remote_ref = remote.put_bytes(
        payload,
        PutOptions(
            kind="cache.durable-default",
            media_type="application/json",
            producer=ProducerInfo(component="tests.cache", version="durable"),
        ),
        return_selected_profile=True,
    )
    assert local.get_manifest(remote_ref.artifact_id).kind == "cache.local-default"
    expected = remote.get_raw_manifest_bytes(remote_ref.artifact_id)
    durable_reader = remote.read_raw_manifest_bytes_bounded
    calls = 0

    def observe_durable(selector, *, max_manifest_bytes, manifest_profile_sha256=None):
        nonlocal calls
        calls += 1
        assert selector == remote_ref.artifact_id
        assert manifest_profile_sha256 is None
        return durable_reader(
            selector,
            max_manifest_bytes=max_manifest_bytes,
            manifest_profile_sha256=manifest_profile_sha256,
        )

    monkeypatch.setattr(remote, "read_raw_manifest_bytes_bounded", observe_durable)
    cached = CachingArtifactStore(remote=remote, local=local, write_through=True)
    result = cached.read_raw_manifest_bytes_bounded(
        remote_ref.artifact_id, max_manifest_bytes=len(expected)
    )
    assert calls == 1
    assert result.raw_manifest_bytes == expected
    assert result.usage.observed_manifest_selection_bytes == len(expected)
    assert result.usage.observed_source_bytes == len(expected)


def test_cache_bounded_default_manifest_refuses_unsupported_durable_owner(
    tmp_path,
) -> None:
    local = FileSystemCAS(tmp_path / "bounded-local-hit")
    local_ref = local.put_bytes(
        b"local hit must not satisfy durable selection",
        PutOptions(kind="cache.local-only", media_type="application/json"),
    )

    class UnsupportedRemote:
        pass

    cached = CachingArtifactStore(remote=UnsupportedRemote(), local=local, write_through=True)
    with pytest.raises(
        NotImplementedError, match="cache_manifest_owner_bounded_receipt_unavailable"
    ):
        cached.read_raw_manifest_bytes_bounded(local_ref.artifact_id, max_manifest_bytes=4096)
