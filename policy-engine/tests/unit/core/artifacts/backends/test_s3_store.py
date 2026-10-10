from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.backends.s3_store import S3ArtifactStore
from polisyos.core.artifacts.manifest import CanonInfo as CoreCanonInfo
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.artifacts.store import ArtifactIntegrityError, PutOptions
from polisyos.core.canon import CanonSpec as CoreCanonSpec
from polisyos.core.canon import CanonViolation as CoreCanonViolation


class _MetricsStub:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def record_artifact_integrity_failure(self, *, backend: str, reason: str) -> None:
        self.events.append((backend, reason))


class _FakeClientError(Exception):
    def __init__(self, code: str, *, status_code: int | None = None) -> None:
        http_status = status_code or (404 if code in {"404", "NotFound", "NoSuchKey"} else 403)
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
        self.put_calls: list[str] = []

    def head_object(self, **kwargs) -> dict[str, object]:
        key = str(kwargs["Key"])
        error = self.head_errors.get(key)
        if error is not None:
            raise error
        if key not in self.objects:
            raise _FakeClientError("NotFound")
        return {}

    def get_object(self, **kwargs) -> dict[str, object]:
        key = str(kwargs["Key"])
        if key not in self.objects:
            raise _FakeClientError("NotFound")
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
