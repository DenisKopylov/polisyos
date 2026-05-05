from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import ArtifactIntegrityError, FileSystemCAS, PutOptions
from polisyos.ir.artifacts import ArtifactID as IrArtifactID
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact


def test_put_get_roundtrip_and_verify(store: FileSystemCAS):
    data = b"hello policy os"
    ref = store.put_bytes(
        data,
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )

    assert store.has(ref.artifact_id)
    out = store.get_bytes(ref.artifact_id)
    assert out == data

    rep = store.verify(ref.artifact_id)
    assert rep.ok is True
    assert rep.actual_sha256_hex == ref.artifact_id.hex


def test_dedup_put_same_bytes(store: FileSystemCAS):
    data = b"same"
    r1 = store.put_bytes(data, PutOptions(kind="test.bytes", media_type="application/octet-stream"))
    r2 = store.put_bytes(data, PutOptions(kind="test.bytes", media_type="application/octet-stream"))

    assert str(r1.artifact_id) == str(r2.artifact_id)


def test_concurrent_put_creates_single_valid_manifest(store: FileSystemCAS) -> None:
    data = b"concurrent-manifest"
    opts = PutOptions(kind="test.concurrent", media_type="application/octet-stream")

    with ThreadPoolExecutor(max_workers=8) as executor:
        refs = list(executor.map(lambda _: store.put_bytes(data, opts), range(32)))

    artifact_ids = {str(ref.artifact_id) for ref in refs}
    assert len(artifact_ids) == 1

    manifest = store.get_manifest(refs[0].artifact_id)
    assert manifest.kind == "test.concurrent"
    assert manifest.integrity.sha256 == refs[0].artifact_id.hex
    assert store.get_bytes(refs[0].artifact_id) == data


def test_put_json_is_canonical_and_dedups(store: FileSystemCAS):
    obj1 = {"b": 1, "a": "x", "nested": {"z": 9, "y": 8}}
    obj2 = {"nested": {"y": 8, "z": 9}, "a": "x", "b": 1}

    r1 = store.put_json(obj1, PutOptions(kind="test.json", media_type="application/json"))
    r2 = store.put_json(obj2, PutOptions(kind="test.json", media_type="application/json"))

    assert str(r1.artifact_id) == str(r2.artifact_id)

    b = store.get_bytes(r1.artifact_id)
    assert hashlib.sha256(b).hexdigest() == r1.artifact_id.hex


def test_manifest_written_and_parses(store: FileSystemCAS):
    ref = store.put_json(
        {"x": 1, "y": "ok"},
        PutOptions(
            kind="test.manifested_json",
            media_type="application/json",
            schema=SchemaInfo(name="tests.Payload", version="0.1.0"),
        ),
    )

    man = store.get_manifest(ref.artifact_id)
    assert str(man.artifact_id) == str(ref.artifact_id)
    assert man.kind == "test.manifested_json"
    assert man.media_type == "application/json"
    assert man.byte_size > 0
    assert man.integrity.sha256 == ref.artifact_id.hex
    assert man.artifact_schema is not None
    assert man.artifact_schema.name == "tests.Payload"


def test_filesystem_cas_accepts_ir_artifact_id_roundtrip(store: FileSystemCAS) -> None:
    ref = put_json_artifact(
        store,
        {"source": "ir", "ok": True},
        kind="ir.test_payload",
        schema_name="tests.IRPayload",
        schema_version="1.0",
    )
    ir_artifact_id = IrArtifactID.model_validate(ref["artifact_id"])

    manifest = store.get_manifest(ir_artifact_id)

    assert manifest.kind == "ir.test_payload"
    assert str(manifest.artifact_id) == ref["artifact_id"]
    assert get_json_artifact(store, ir_artifact_id) == {"source": "ir", "ok": True}


def test_corruption_detection(store: FileSystemCAS):
    data = b"original"
    ref = store.put_bytes(
        data,
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )

    blob_path, _ = store._paths(ref.artifact_id)
    blob_path.write_bytes(b"tampered!!!")

    rep = store.verify(ref.artifact_id)
    assert rep.ok is False
    assert rep.error == "sha256 mismatch"


def test_get_bytes_raises_typed_integrity_error_on_corruption(store: FileSystemCAS):
    ref = store.put_bytes(
        b"original",
        PutOptions(kind="test.bytes", media_type="application/octet-stream"),
    )
    blob_path, _ = store._paths(ref.artifact_id)
    blob_path.write_bytes(b"tampered!!!")

    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        store.get_bytes(ref.artifact_id)


def test_import_subgraph_skips_unexpected_paths(store: FileSystemCAS, tmp_path):
    source = tmp_path / "import"
    source.mkdir()
    weird = source / "artifacts" / "sha256" / "aa" / "bb" / "not-a-real-artifact.txt"
    weird.parent.mkdir(parents=True)
    weird.write_text("oops", encoding="utf-8")

    report = store.import_subgraph(source)

    assert report.imported_files == 0
    assert report.skipped_entries == [str(weird.relative_to(source))]


def test_cas_metrics_emission(store: FileSystemCAS):
    from polisyos.core.observability import get_tracer

    class DummyCounter:
        def __init__(self) -> None:
            self.calls: list[tuple[int, dict[str, str]]] = []

        def add(self, value: int, attrs: dict[str, str]) -> None:
            self.calls.append((value, attrs))

    class DummyHistogram:
        def __init__(self) -> None:
            self.calls: list[tuple[float, dict[str, str]]] = []

        def record(self, value: float, attrs: dict[str, str]) -> None:
            self.calls.append((value, attrs))

    class DummyMetrics:
        def __init__(self) -> None:
            self.artifact_cache_hits_total = DummyCounter()
            self.artifact_cache_misses_total = DummyCounter()
            self.artifact_io_bytes = DummyHistogram()
            self.artifact_io_duration_seconds = DummyHistogram()
            self.artifact_operations_total = DummyCounter()
            self.integrity_failures: list[tuple[str, str]] = []

        def record_artifact_integrity_failure(self, *, backend: str, reason: str) -> None:
            self.integrity_failures.append((backend, reason))

    store._hpc_enabled = True
    store._tracer = get_tracer()
    store._metrics = DummyMetrics()

    data = b"metrics-test"
    ref = store.put_bytes(
        data,
        PutOptions(kind="test.metrics", media_type="application/octet-stream"),
    )

    assert store.has(ref.artifact_id)
    _ = store.get_bytes(ref.artifact_id)

    metrics = store._metrics
    assert metrics.artifact_operations_total.calls
    assert metrics.artifact_io_bytes.calls
    assert metrics.artifact_io_duration_seconds.calls
    assert metrics.artifact_cache_hits_total.calls

    blob_path, _ = store._paths(ref.artifact_id)
    blob_path.write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError):
        store.get_bytes(ref.artifact_id)

    assert ("filesystem", "ArtifactIntegrityError") in metrics.integrity_failures
