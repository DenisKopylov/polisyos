from __future__ import annotations

import sys
from types import ModuleType

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.backends.gcs_store import GCSArtifactStore
from polisyos.core.artifacts.canonical_profile import read_core_json_artifact
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.artifacts.store import ArtifactIntegrityError, FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec as CoreCanonSpec
from polisyos.core.canon import CanonViolation as CoreCanonViolation
from polisyos.core.canon import content_hash


class _MetricsStub:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def record_artifact_integrity_failure(self, *, backend: str, reason: str) -> None:
        self.events.append((backend, reason))


class _PreconditionFailedError(Exception):
    code = 412


class _FakeBlob:
    def __init__(
        self,
        name: str,
        objects: dict[str, bytes],
        download_errors: dict[str, Exception],
        download_calls: list[str],
    ) -> None:
        self.name = name
        self._objects = objects
        self._download_errors = download_errors
        self._download_calls = download_calls

    def exists(self) -> bool:
        return self.name in self._objects

    def upload_from_string(
        self,
        data: bytes,
        content_type: str | None = None,
        *,
        if_generation_match: int | None = None,
    ) -> None:
        del content_type
        if if_generation_match == 0 and self.name in self._objects:
            raise _PreconditionFailedError(self.name)
        self._objects[self.name] = data

    def download_as_bytes(self) -> bytes:
        self._download_calls.append(self.name)
        error = self._download_errors.get(self.name)
        if error is not None:
            raise error
        if self.name not in self._objects:
            raise FileNotFoundError(self.name)
        return self._objects[self.name]


class _FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.download_errors: dict[str, Exception] = {}
        self.download_calls: list[str] = []
        self.reload_error: Exception | None = None
        self.reload_calls = 0

    def reload(self) -> None:
        self.reload_calls += 1
        if self.reload_error is not None:
            raise self.reload_error

    def blob(self, name: str) -> _FakeBlob:
        return _FakeBlob(name, self.objects, self.download_errors, self.download_calls)

    def list_blobs(self, prefix: str):
        for key in sorted(self.objects):
            if key.startswith(prefix):
                yield _FakeBlob(key, self.objects, self.download_errors, self.download_calls)


def _install_fake_google_api_not_found(monkeypatch: pytest.MonkeyPatch) -> type[Exception]:
    class NotFoundError(Exception):
        """Model google.api_core.exceptions.NotFound for the optional SDK seam."""

    exceptions_module = ModuleType("google.api_core.exceptions")
    exceptions_module.NotFound = NotFoundError
    api_core_module = ModuleType("google.api_core")
    api_core_module.__path__ = []
    api_core_module.exceptions = exceptions_module
    google_module = ModuleType("google")
    google_module.__path__ = []
    google_module.api_core = api_core_module
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.api_core", api_core_module)
    monkeypatch.setitem(sys.modules, "google.api_core.exceptions", exceptions_module)
    return NotFoundError


def test_gcs_store_refuses_canon_spec_mismatch_before_upload() -> None:
    store = GCSArtifactStore(bucket="test-bucket")
    bucket = _FakeBucket()
    store._bucket = bucket

    with pytest.raises(CoreCanonViolation, match="canon metadata must match"):
        store.put_json(
            {"present": None},
            PutOptions(
                kind="test.core-canon-spec-mismatch",
                media_type="application/json",
                canon=CoreCanonInfo(exclude_none=True),
            ),
            canon_spec=CoreCanonSpec(exclude_none=False),
        )

    assert bucket.objects == {}


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(
            {"value": {"_type": "bytes_hex", "value": "00ff"}},
            id="recognized-bytes-alias",
        ),
        pytest.param(
            {"value": {"_type": "float_hex", "value": "0x1.4000000000000p+0"}},
            id="recognized-float-alias",
        ),
    ],
)
def test_gcs_store_refuses_nonconformant_json_profile_before_upload(
    payload: dict[str, object],
) -> None:
    store = GCSArtifactStore(bucket="test-bucket")
    bucket = _FakeBucket()
    store._bucket = bucket
    spec = CoreCanonSpec(forbid_floats=False, exclude_none=False)

    with pytest.raises(CanonicalProfileRefusalError) as refusal:
        store.put_json(
            payload,
            PutOptions(
                kind="test.core-json-profile-nonconformant",
                media_type="application/json",
                canon=CoreCanonInfo.from_spec(spec),
            ),
            canon_spec=spec,
        )

    assert refusal.value.code == "canon_profile_payload_nonconformant"
    assert bucket.objects == {}


def test_gcs_selected_raw_manifest_cold_cache_uses_exact_view_and_reader() -> None:
    bucket = _FakeBucket()
    spec = CoreCanonSpec(sort_keys=False)
    options = PutOptions(
        kind="test.gcs_selected_raw_manifest",
        media_type="application/json",
        canon=CoreCanonInfo.from_spec(spec),
    )
    payload = {"second": 2, "first": 1}
    writer = GCSArtifactStore(bucket="test-bucket")
    writer._bucket = bucket
    selected_ref = writer.put_json(
        payload,
        options,
        canon_spec=spec,
        return_selected_profile=True,
    )

    profile_sha256 = selected_ref.manifest_profile_sha256
    assert profile_sha256 is not None
    selected_key = writer._manifest_key(selected_ref.artifact_id, profile_sha256)
    assert selected_key != writer._manifest_key(selected_ref.artifact_id)
    selected_bytes = bucket.objects[selected_key]

    reader = GCSArtifactStore(bucket="test-bucket")
    reader._bucket = bucket
    reads_before = len(bucket.download_calls)
    with pytest.raises(ValueError, match="manifest_profile_sha256 must be"):
        reader.get_raw_manifest_bytes(
            selected_ref.artifact_id,
            manifest_profile_sha256="malformed-profile",
        )
    assert len(bucket.download_calls) == reads_before

    raw = reader.get_raw_manifest_bytes(
        selected_ref.artifact_id,
        manifest_profile_sha256=profile_sha256,
    )
    assert raw == selected_bytes
    assert bucket.download_calls[reads_before:] == [selected_key]

    read = read_core_json_artifact(reader, selected_ref)
    assert read.status == "declared_bytes_conformant"
    assert read.value == payload
    assert read.selected_artifact_id == str(selected_ref.artifact_id)
    assert read.selected_manifest_profile_sha256 == profile_sha256


def test_gcs_store_get_bytes_rehashes_blob_on_read() -> None:
    metrics = _MetricsStub()
    store = GCSArtifactStore(bucket="test-bucket", metrics=metrics)
    bucket = _FakeBucket()
    store._bucket = bucket

    ref = store.put_bytes(
        b"original",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    bucket.objects[store._blob_key(ref.artifact_id)] = b"tampered"

    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        store.get_bytes(ref.artifact_id)

    assert metrics.events == [("gcs", "ArtifactIntegrityError")]


def test_gcs_missing_object_and_profile_are_typed_absence_across_direct_and_cached_reads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    not_found_type = _install_fake_google_api_not_found(monkeypatch)
    store = GCSArtifactStore(bucket="test-bucket")
    bucket = _FakeBucket()
    store._bucket = bucket
    cached = CachingArtifactStore(
        remote=store,
        local=FileSystemCAS(tmp_path / "local"),
        write_through=False,
    )
    missing_id = "sha256:" + "ab" * 32
    missing_aid = ArtifactID.from_sha256_hex("ab" * 32)
    missing_profile = "sha256:" + "f" * 64
    bucket.download_errors[store._blob_key(missing_aid)] = not_found_type("missing blob")

    with pytest.raises(FileNotFoundError):
        store.get_bytes(missing_id)
    with pytest.raises(FileNotFoundError):
        cached.get_bytes(missing_id)

    ref = store.put_bytes(
        b"existing GCS blob with one manifest view",
        PutOptions(kind="test.gcs_missing_selected_view", media_type="application/json"),
        return_selected_profile=True,
    )
    assert ref.manifest_profile_sha256 is not None
    assert store.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256).kind == (
        "test.gcs_missing_selected_view"
    )
    assert cached.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256).kind == (
        "test.gcs_missing_selected_view"
    )

    before_malformed = len(bucket.download_calls)
    with pytest.raises(ValueError, match="manifest_profile_sha256 must be"):
        store.get_manifest_by_profile(ref.artifact_id, "malformed-profile")
    assert len(bucket.download_calls) == before_malformed

    absent_manifest_key = store._manifest_key(ref.artifact_id, missing_profile)
    bucket.download_errors[absent_manifest_key] = not_found_type("missing manifest profile")
    with pytest.raises(FileNotFoundError):
        store.get_manifest_by_profile(ref.artifact_id, missing_profile)
    with pytest.raises(FileNotFoundError):
        cached.get_manifest_by_profile(ref.artifact_id, missing_profile)

    wrong_refs = (
        ref.model_copy(update={"kind": "test.wrong-kind"}),
        ref.model_copy(update={"media_type": "text/plain"}),
    )
    for wrong_ref in wrong_refs:
        with pytest.raises(ArtifactIntegrityError, match="reference type does not match"):
            store.get_manifest(wrong_ref)
        with pytest.raises(ArtifactIntegrityError, match="reference type does not match"):
            cached.get_manifest(wrong_ref)


def test_gcs_missing_object_has_is_false_only_after_bucket_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_google_api_not_found(monkeypatch)
    store = GCSArtifactStore(bucket="test-bucket")
    bucket = _FakeBucket()
    store._bucket = bucket

    assert store.has("sha256:" + "ab" * 32) is False
    assert bucket.reload_calls == 1


def test_gcs_missing_bucket_is_not_reclassified_by_read_or_has(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    not_found_type = _install_fake_google_api_not_found(monkeypatch)
    store = GCSArtifactStore(bucket="missing-bucket")
    bucket = _FakeBucket()
    store._bucket = bucket
    bucket_missing = not_found_type("bucket does not exist")
    bucket.reload_error = bucket_missing
    missing_id = "sha256:" + "ab" * 32
    from polisyos.core.artifacts.ids import ArtifactID

    key = store._blob_key(ArtifactID.model_validate(missing_id))
    bucket.download_errors[key] = not_found_type("object lookup returned 404")
    manifest_key = store._manifest_key(ArtifactID.model_validate(missing_id))
    bucket.download_errors[manifest_key] = not_found_type("manifest lookup returned 404")
    cached = CachingArtifactStore(
        remote=store,
        local=FileSystemCAS(tmp_path / "local-missing-bucket"),
        write_through=True,
    )

    with pytest.raises(not_found_type) as read_error:
        store.get_bytes(missing_id)
    assert read_error.value is bucket_missing
    with pytest.raises(not_found_type) as cached_read_error:
        cached.get_bytes(missing_id)
    assert cached_read_error.value is bucket_missing

    with pytest.raises(not_found_type) as has_error:
        store.has(missing_id)
    assert has_error.value is bucket_missing
    with pytest.raises(not_found_type) as cached_has_error:
        cached.has(missing_id)
    assert cached_has_error.value is bucket_missing


def test_gcs_bucket_permission_failure_blocks_false_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    not_found_type = _install_fake_google_api_not_found(monkeypatch)
    store = GCSArtifactStore(bucket="test-bucket")
    bucket = _FakeBucket()
    store._bucket = bucket
    payload = b"missing payload"
    digest = content_hash(payload)
    aid = ArtifactID.from_sha256_hex(digest)
    manifest = ManifestLifecycle.build(
        artifact_id=aid,
        data=payload,
        sha=digest,
        opts=PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    bucket.objects[store._manifest_key(aid)] = ManifestLifecycle.to_bytes(manifest)
    denied = PermissionError("bucket metadata permission denied")
    bucket.reload_error = denied
    key = store._blob_key(aid)
    bucket.download_errors[key] = not_found_type("object lookup returned 404")

    with pytest.raises(PermissionError) as raised:
        store.get_bytes(aid)
    assert raised.value is denied


def test_gcs_manifest_404_preserves_bucket_permission_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    not_found_type = _install_fake_google_api_not_found(monkeypatch)
    store = GCSArtifactStore(bucket="test-bucket")
    bucket = _FakeBucket()
    store._bucket = bucket
    aid = ArtifactID.from_sha256_hex("ab" * 32)
    manifest_key = store._manifest_key(aid)
    bucket.download_errors[manifest_key] = not_found_type("manifest lookup returned 404")
    denied = PermissionError("bucket metadata permission denied")
    bucket.reload_error = denied

    with pytest.raises(PermissionError) as raised:
        store.get_bytes(aid)
    assert raised.value is denied
    assert bucket.download_calls == [manifest_key]


@pytest.mark.parametrize("error", [TimeoutError("GCS timeout"), PermissionError("GCS denied")])
def test_gcs_transport_and_permission_errors_are_not_reclassified_as_missing(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    tmp_path,
) -> None:
    _install_fake_google_api_not_found(monkeypatch)
    store = GCSArtifactStore(bucket="test-bucket")
    bucket = _FakeBucket()
    store._bucket = bucket
    ref = store.put_bytes(
        b"GCS transport error object",
        PutOptions(kind="test.gcs_transport_error", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    bucket.download_errors[store._blob_key(ref.artifact_id)] = error
    cached = CachingArtifactStore(
        remote=store,
        local=FileSystemCAS(tmp_path / "local-error"),
        write_through=False,
    )

    with pytest.raises(type(error)) as direct:
        store.get_bytes(ref)
    assert direct.value is error
    with pytest.raises(type(error)) as through_cache:
        cached.get_bytes(ref)
    assert through_cache.value is error


def test_gcs_write_can_return_the_exact_profile_for_a_first_write() -> None:
    store = GCSArtifactStore(bucket="test-bucket")
    store._bucket = _FakeBucket()

    ref = store.put_json(
        {"payload": "profiled first write"},
        PutOptions(kind="test.gcs_profile", media_type="application/json"),
        return_selected_profile=True,
    )

    assert ref.manifest_profile_sha256 is not None
    manifest = store.get_manifest(ref)
    assert ManifestLifecycle.profile_sha256(manifest) == ref.manifest_profile_sha256
    assert manifest.kind == "test.gcs_profile"


def test_gcs_store_accepts_injected_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics = _MetricsStub()
    monkeypatch.setattr(
        "polisyos.core.artifacts.backends.gcs_store._default_metrics",
        lambda: (_ for _ in ()).throw(
            AssertionError("global metrics lookup should not run when metrics are injected")
        ),
    )

    store = GCSArtifactStore(bucket="test-bucket", metrics=metrics)

    assert store._metrics is metrics


def test_gcs_store_preserves_each_exact_view_for_identical_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = GCSArtifactStore(bucket="test-bucket")
    store._bucket = _FakeBucket()

    first = store.put_bytes(
        b"same remote bytes",
        PutOptions(kind="first.view", media_type="application/json"),
    )
    second = store.put_bytes(
        b"same remote bytes",
        PutOptions(kind="second.view", media_type="text/plain"),
    )

    assert first.artifact_id == second.artifact_id
    assert first.manifest_profile_sha256 is None
    assert second.manifest_profile_sha256 is not None
    assert store.get_manifest(first).kind == "first.view"
    assert store.get_manifest(second).kind == "second.view"
    assert store.get_manifest(first.artifact_id).kind == "first.view"
    assert second.manifest_profile_sha256 is not None
    assert (
        store.get_manifest_by_profile(second.artifact_id, second.manifest_profile_sha256).kind
        == "second.view"
    )
    assert store.get_bytes(second) == b"same remote bytes"

    manifest_key = store._manifest_key
    monkeypatch.setattr(
        store,
        "_manifest_key",
        lambda artifact_id, profile_sha256=None: manifest_key(
            artifact_id,
            None if profile_sha256 is not None else profile_sha256,
        ),
    )
    with pytest.raises(ArtifactIntegrityError, match="Selected manifest profile mismatch"):
        store.get_manifest(second)


@pytest.mark.parametrize(
    ("first_bucket", "first_prefix", "second_bucket", "second_prefix"),
    [
        ("first-bucket", "same-prefix", "second-bucket", "same-prefix"),
        ("same-bucket", "first-prefix", "same-bucket", "second-prefix"),
    ],
)
def test_gcs_metadata_cache_isolated_by_bucket_and_prefix(
    first_bucket: str,
    first_prefix: str,
    second_bucket: str,
    second_prefix: str,
    tmp_path,
) -> None:
    shared_cache = tmp_path / "shared-gcs-cache"
    first = GCSArtifactStore(
        bucket=first_bucket,
        prefix=first_prefix,
        local_cache_dir=shared_cache,
    )
    second = GCSArtifactStore(
        bucket=second_bucket,
        prefix=second_prefix,
        local_cache_dir=shared_cache,
    )
    first._bucket = _FakeBucket()
    second._bucket = _FakeBucket()
    payload = b"one content identity, independent GCS namespaces"

    first_ref = first.put_bytes(
        payload,
        PutOptions(
            kind="cache.namespace",
            media_type="text/plain",
            producer=ProducerInfo(component="tests.gcs", version="first"),
        ),
    )
    second.put_bytes(
        payload,
        PutOptions(
            kind="cache.namespace",
            media_type="text/plain",
            producer=ProducerInfo(component="tests.gcs", version="second"),
        ),
    )

    assert first.get_manifest(first_ref).producer.version == "first"
