from __future__ import annotations

from types import SimpleNamespace

import pytest
from polisyos.core.artifacts.backends.s3_store import S3ArtifactStore
from polisyos.core.artifacts.store import ArtifactIntegrityError, PutOptions


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
