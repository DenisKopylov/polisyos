from __future__ import annotations

import pytest
from polisyos.core.artifacts.backends.gcs_store import GCSArtifactStore
from polisyos.core.artifacts.store import ArtifactIntegrityError, PutOptions


class _MetricsStub:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def record_artifact_integrity_failure(self, *, backend: str, reason: str) -> None:
        self.events.append((backend, reason))


class _FakeBlob:
    def __init__(self, name: str, objects: dict[str, bytes]) -> None:
        self.name = name
        self._objects = objects

    def exists(self) -> bool:
        return self.name in self._objects

    def upload_from_string(self, data: bytes, content_type: str | None = None) -> None:
        del content_type
        self._objects[self.name] = data

    def download_as_bytes(self) -> bytes:
        if self.name not in self._objects:
            raise FileNotFoundError(self.name)
        return self._objects[self.name]


class _FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def blob(self, name: str) -> _FakeBlob:
        return _FakeBlob(name, self.objects)

    def list_blobs(self, prefix: str):
        for key in sorted(self.objects):
            if key.startswith(prefix):
                yield _FakeBlob(key, self.objects)


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
