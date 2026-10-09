from __future__ import annotations

import pytest

from polisyos.core.artifacts.backends.gcs_store import GCSArtifactStore
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.artifacts.store import ArtifactIntegrityError, PutOptions


class _MetricsStub:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def record_artifact_integrity_failure(self, *, backend: str, reason: str) -> None:
        self.events.append((backend, reason))


class _PreconditionFailedError(Exception):
    code = 412


class _FakeBlob:
    def __init__(self, name: str, objects: dict[str, bytes]) -> None:
        self.name = name
        self._objects = objects

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
