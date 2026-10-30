from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.backends.caching_store import CachingArtifactStore
from polisyos.core.artifacts.backends.s3_store import S3ArtifactStore
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


class _FakeClientError(Exception):
    def __init__(self, code: str, *, status_code: int | None = None) -> None:
        http_status = status_code or (
            404 if code in {"404", "NotFound", "NoSuchKey", "NoSuchBucket"} else 403
        )
        self.response = {
            "Error": {"Code": code},
            "ResponseMetadata": {"HTTPStatusCode": http_status},
        }
        super().__init__(code)


class _FakeBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class _FakeS3Client:
    exceptions = SimpleNamespace(ClientError=_FakeClientError)

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.head_errors: dict[str, _FakeClientError] = {}
        self.get_errors: dict[str, Exception] = {}
        self.get_calls: list[str] = []
        self.put_calls: list[str] = []
        self.bucket_exists = True
        self.head_bucket_error: Exception | None = None
        self.head_bucket_calls = 0

    def head_bucket(self, **kwargs) -> dict[str, object]:
        del kwargs
        self.head_bucket_calls += 1
        if self.head_bucket_error is not None:
            raise self.head_bucket_error
        if not self.bucket_exists:
            raise _FakeClientError("NoSuchBucket")
        return {}

    def head_object(self, **kwargs) -> dict[str, object]:
        key = str(kwargs["Key"])
        error = self.head_errors.get(key)
        if error is not None:
            raise error
        if key not in self.objects:
            if not self.bucket_exists:
                raise _FakeClientError("NoSuchBucket")
            raise _FakeClientError("404", status_code=404)
        return {}

    def get_object(self, **kwargs) -> dict[str, object]:
        key = str(kwargs["Key"])
        self.get_calls.append(key)
        error = self.get_errors.get(key)
        if error is not None:
            raise error
        if key not in self.objects:
            if not self.bucket_exists:
                raise _FakeClientError("NoSuchBucket")
            raise _FakeClientError("NoSuchKey")
        return {"Body": _FakeBody(self.objects[key])}

    def put_object(self, **kwargs) -> dict[str, object]:
        key = str(kwargs["Key"])
        body = bytes(kwargs["Body"])
        self.put_calls.append(key)
        if kwargs.get("IfNoneMatch") == "*" and key in self.objects:
            raise _FakeClientError("PreconditionFailed", status_code=412)
        self.objects[key] = body
        return {}

    def get_paginator(self, name: str) -> object:
        raise AssertionError(f"Paginator {name} should not be used in this test")


def test_s3_store_does_not_mask_head_permission_errors() -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    client = _FakeS3Client()
    store._client = client

    ref = store.put_bytes(
        b"data",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    manifest_key = store._manifest_key(ref.artifact_id)
    client.head_errors[manifest_key] = _FakeClientError("AccessDenied", status_code=403)

    with pytest.raises(_FakeClientError, match="AccessDenied"):
        store.put_bytes(
            b"data",
            PutOptions(kind="test.bytes", media_type="application/octet-stream"),
        )


def test_s3_store_refuses_canon_spec_mismatch_before_upload() -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    client = _FakeS3Client()
    store._client = client

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

    assert client.put_calls == []
    assert client.objects == {}


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
def test_s3_store_refuses_nonconformant_json_profile_before_upload(
    payload: dict[str, object],
) -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    client = _FakeS3Client()
    store._client = client
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
    assert client.put_calls == []
    assert client.objects == {}


def test_s3_store_get_bytes_rehashes_blob_on_read() -> None:
    metrics = _MetricsStub()
    store = S3ArtifactStore(bucket="test-bucket", metrics=metrics)
    client = _FakeS3Client()
    store._client = client

    ref = store.put_bytes(
        b"original",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    client.objects[store._blob_key(ref.artifact_id)] = b"tampered"

    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        store.get_bytes(ref.artifact_id)

    assert metrics.events == [("s3", "ArtifactIntegrityError")]


def test_s3_missing_object_and_profile_are_typed_absence_across_direct_and_cached_reads(
    tmp_path,
) -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    client = _FakeS3Client()
    store._client = client
    cached = CachingArtifactStore(
        remote=store,
        local=FileSystemCAS(tmp_path / "local"),
        write_through=False,
    )
    missing_id = "sha256:" + "ab" * 32
    missing_profile = "sha256:" + "f" * 64

    with pytest.raises(FileNotFoundError):
        store.get_bytes(missing_id)
    with pytest.raises(FileNotFoundError):
        store.get_manifest_by_profile(missing_id, missing_profile)
    with pytest.raises(FileNotFoundError):
        cached.get_bytes(missing_id)
    with pytest.raises(FileNotFoundError):
        cached.get_manifest_by_profile(missing_id, missing_profile)

    ref = store.put_bytes(
        b"existing blob with one manifest view",
        PutOptions(kind="test.s3_missing_selected_view", media_type="application/json"),
        return_selected_profile=True,
    )
    assert ref.manifest_profile_sha256 is not None
    assert store.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256).kind == (
        "test.s3_missing_selected_view"
    )
    assert cached.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256).kind == (
        "test.s3_missing_selected_view"
    )

    before_malformed = len(client.get_calls)
    with pytest.raises(ValueError, match="manifest_profile_sha256 must be"):
        store.get_manifest_by_profile(ref.artifact_id, "malformed-profile")
    assert len(client.get_calls) == before_malformed

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


def test_s3_ambiguous_404_is_absent_only_after_bucket_verification() -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    client = _FakeS3Client()
    store._client = client
    payload = b"missing payload"
    digest = content_hash(payload)
    aid = ArtifactID.from_sha256_hex(digest)
    manifest = ManifestLifecycle.build(
        artifact_id=aid,
        data=payload,
        sha=digest,
        opts=PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    client.objects[store._manifest_key(aid)] = ManifestLifecycle.to_bytes(manifest)
    missing_id = str(aid)
    key = store._blob_key(aid)
    client.get_errors[key] = _FakeClientError("404", status_code=404)

    with pytest.raises(FileNotFoundError):
        store.get_bytes(missing_id)
    assert client.head_bucket_calls == 1
    assert store.has(missing_id) is False
    assert client.head_bucket_calls == 2


def test_s3_ambiguous_manifest_404_preserves_bucket_permission_failure() -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    client = _FakeS3Client()
    store._client = client
    aid = ArtifactID.from_sha256_hex("ab" * 32)
    manifest_key = store._manifest_key(aid)
    client.get_errors[manifest_key] = _FakeClientError("404", status_code=404)
    denied = _FakeClientError("AccessDenied", status_code=403)
    client.head_bucket_error = denied

    with pytest.raises(_FakeClientError) as raised:
        store.get_bytes(aid)
    assert raised.value is denied
    assert client.get_calls == [manifest_key]


def test_s3_missing_bucket_404_is_not_reclassified_by_read_or_has(tmp_path) -> None:
    store = S3ArtifactStore(bucket="missing-bucket")
    client = _FakeS3Client()
    client.bucket_exists = False
    store._client = client
    missing_id = "sha256:" + "ab" * 32
    from polisyos.core.artifacts.ids import ArtifactID

    aid = ArtifactID.model_validate(missing_id)
    key = store._blob_key(aid)
    ambiguous = _FakeClientError("404", status_code=404)
    client.get_errors[key] = ambiguous
    manifest_key = store._manifest_key(ArtifactID.model_validate(missing_id))
    client.get_errors[manifest_key] = _FakeClientError("404", status_code=404)
    cached = CachingArtifactStore(
        remote=store,
        local=FileSystemCAS(tmp_path / "local-missing-bucket"),
        write_through=True,
    )

    with pytest.raises(_FakeClientError, match="NoSuchBucket"):
        store.get_bytes(missing_id)
    assert client.head_bucket_calls == 1
    with pytest.raises(_FakeClientError, match="NoSuchBucket"):
        cached.get_bytes(missing_id)
    assert client.head_bucket_calls == 2

    client.head_errors[key] = _FakeClientError("404", status_code=404)
    with pytest.raises(_FakeClientError, match="NoSuchBucket"):
        store.has(missing_id)
    assert client.head_bucket_calls == 3
    with pytest.raises(_FakeClientError, match="NoSuchBucket"):
        cached.has(missing_id)
    assert client.head_bucket_calls == 4


def test_s3_namespace_and_permission_errors_are_not_missing_objects(tmp_path: Path) -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    client = _FakeS3Client()
    store._client = client
    data = b"existing selected remote artifact"
    ref = store.put_bytes(
        data,
        PutOptions(kind="test.s3_provider_error", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    if ref.manifest_profile_sha256 is None:
        pytest.fail("the remote error control requires an exact selected manifest view")
    if store.get_bytes(ref) != data:
        pytest.fail("the selected S3 fixture did not read back its stored bytes")
    cached = CachingArtifactStore(
        remote=store,
        local=FileSystemCAS(tmp_path / "local-provider-error"),
        write_through=True,
    )
    key = store._blob_key(ref.artifact_id)
    head_bucket_calls_before_errors = client.head_bucket_calls

    for error in (
        _FakeClientError("NoSuchBucket"),
        _FakeClientError("NoSuchKey", status_code=403),
        _FakeClientError("AccessDenied", status_code=403),
        _FakeClientError("AccessDenied", status_code=404),
        _FakeClientError("NoSuchObject", status_code=404),
        _FakeClientError("UnrecognizedProviderError", status_code=404),
    ):
        client.get_errors[key] = error
        client.head_errors[key] = error
        with pytest.raises(type(error)) as raised:
            store.get_bytes(ref)
        if raised.value is not error:
            pytest.fail("direct GET changed the provider error instance")
        with pytest.raises(type(error)) as raised_cached:
            cached.get_bytes(ref)
        if raised_cached.value is not error:
            pytest.fail("cached GET changed the provider error instance")
        with pytest.raises(type(error)) as raised_head:
            store.has(ref)
        if raised_head.value is not error:
            pytest.fail("direct HEAD changed the provider error instance")
        with pytest.raises(type(error)) as raised_cached_head:
            cached.has(ref)
        if raised_cached_head.value is not error:
            pytest.fail("cached HEAD changed the provider error instance")
    if client.head_bucket_calls != head_bucket_calls_before_errors:
        pytest.fail("provider errors triggered ambiguous-404 bucket verification")


@pytest.mark.parametrize("code", ["NoSuchObject", "UnrecognizedProviderError"])
def test_s3_unknown_404_during_default_manifest_probe_is_not_absence(code: str) -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    client = _FakeS3Client()
    store._client = client
    data = b"unknown S3 response during default manifest probe"
    artifact_id = ArtifactID.from_sha256_hex(content_hash(data))
    manifest_key = store._manifest_key(artifact_id)
    error = _FakeClientError(code, status_code=404)
    client.head_errors[manifest_key] = error

    with pytest.raises(_FakeClientError) as raised:
        store.put_bytes(
            data,
            PutOptions(kind="test.s3_unknown_not_found", media_type="application/octet-stream"),
        )

    assert raised.value is error
    assert client.put_calls == [store._blob_key(artifact_id)]
    assert manifest_key not in client.objects


@pytest.mark.parametrize("error", [TimeoutError("S3 timeout"), _FakeClientError("AccessDenied")])
def test_s3_transport_and_permission_errors_are_not_reclassified_as_missing(
    error: Exception,
    tmp_path,
) -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    client = _FakeS3Client()
    store._client = client
    ref = store.put_bytes(
        b"transport error object",
        PutOptions(kind="test.s3_transport_error", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    client.get_errors[store._blob_key(ref.artifact_id)] = error
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


def test_s3_write_can_return_the_exact_profile_for_a_first_write() -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    store._client = _FakeS3Client()

    ref = store.put_json(
        {"payload": "profiled first write"},
        PutOptions(kind="test.s3_profile", media_type="application/json"),
        return_selected_profile=True,
    )

    assert ref.manifest_profile_sha256 is not None
    manifest = store.get_manifest(ref)
    assert ManifestLifecycle.profile_sha256(manifest) == ref.manifest_profile_sha256
    assert manifest.kind == "test.s3_profile"


def test_s3_store_accepts_injected_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    metrics = _MetricsStub()
    monkeypatch.setattr(
        "polisyos.core.artifacts.backends.s3_store._default_metrics",
        lambda: (_ for _ in ()).throw(
            AssertionError("global metrics lookup should not run when metrics are injected")
        ),
    )

    store = S3ArtifactStore(bucket="test-bucket", metrics=metrics)

    assert store._metrics is metrics


def test_s3_store_preserves_each_exact_view_for_identical_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = S3ArtifactStore(bucket="test-bucket")
    store._client = _FakeS3Client()

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
def test_s3_metadata_cache_isolated_by_bucket_and_prefix(
    first_bucket: str,
    first_prefix: str,
    second_bucket: str,
    second_prefix: str,
    tmp_path,
) -> None:
    shared_cache = tmp_path / "shared-s3-cache"
    first = S3ArtifactStore(
        bucket=first_bucket,
        prefix=first_prefix,
        local_cache_dir=shared_cache,
    )
    second = S3ArtifactStore(
        bucket=second_bucket,
        prefix=second_prefix,
        local_cache_dir=shared_cache,
    )
    first._client = _FakeS3Client()
    second._client = _FakeS3Client()
    payload = b"one content identity, independent S3 namespaces"

    first_ref = first.put_bytes(
        payload,
        PutOptions(
            kind="cache.namespace",
            media_type="text/plain",
            producer=ProducerInfo(component="tests.s3", version="first"),
        ),
    )
    second.put_bytes(
        payload,
        PutOptions(
            kind="cache.namespace",
            media_type="text/plain",
            producer=ProducerInfo(component="tests.s3", version="second"),
        ),
    )

    assert first.get_manifest(first_ref).producer.version == "first"
