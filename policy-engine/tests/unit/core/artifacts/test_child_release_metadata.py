"""Complete Core/IR metadata mapping and historical wire/profile compatibility."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts._manifest_lifecycle import ManifestLifecycle
from polisyos.core.artifacts.child_release import (
    _CHILD_STAGING_TOKEN,
    ChildReleaseUnavailableError,
    child_store_identity,
)
from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactChildReleaseInfo, ArtifactManifest
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.ir.artifacts.contracts import StorePutOptions

if TYPE_CHECKING:
    from pathlib import Path


def _info(root: Path) -> ArtifactChildReleaseInfo:
    return ArtifactChildReleaseInfo(
        release_id="a" * 32,
        scope_id="b" * 32,
        binding_sha256="sha256:" + "c" * 64,
        served_store_identity=child_store_identity(root),
        root_run_id="root",
        child_run_id="child",
    )


@pytest.mark.parametrize("serializer", ["python", "json", "json_text"])
def test_absent_child_metadata_is_omitted_from_every_model_serializer(
    tmp_path: Path, serializer: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(b"legacy", PutOptions(kind="test.legacy", media_type="text/plain"))
    manifest = store.get_manifest(ref)
    historical_wire = manifest.model_dump(mode="json", exclude_none=True)
    historical_wire.pop("child_release", None)
    replay = ArtifactManifest.model_validate(historical_wire)
    if serializer == "json_text":
        assert '"child_release"' not in replay.model_dump_json()
    else:
        assert "child_release" not in replay.model_dump(mode=serializer, exclude_none=False)
    assert ManifestLifecycle.profile_sha256(replay) == ManifestLifecycle.profile_sha256(manifest)
    assert b'"child_release"' not in ManifestLifecycle.to_bytes(replay)


@pytest.mark.parametrize("carrier", ["core", "ir_dto", "mapping"])
def test_core_ir_mappings_preserve_child_class_and_cannot_read_from_tag_alone(
    tmp_path: Path, carrier: str
) -> None:
    served = FileSystemCAS(tmp_path / "served", ownership_enforced=False)
    private = FileSystemCAS(tmp_path / "private", ownership_enforced=False)
    info = _info(served.root)
    private._configure_child_staging(info, token=_CHILD_STAGING_TOKEN)
    if carrier == "core":
        ref = private.put_bytes(
            b"candidate",
            PutOptions(
                kind="tests.child", media_type="application/octet-stream", child_release=info
            ),
            return_selected_profile=True,
        )
    else:
        adapter = ensure_ir_artifact_store(private)
        options = (
            StorePutOptions(
                kind="tests.child", media_type="application/octet-stream", child_release=info
            )
            if carrier == "ir_dto"
            else {
                "kind": "tests.child",
                "media_type": "application/octet-stream",
                "child_release": info.model_dump(mode="json"),
            }
        )
        ir_ref = adapter.put_bytes(b"candidate", options, return_selected_profile=True)
        from polisyos.core.artifacts.manifest import ArtifactRef

        ref = ArtifactRef.model_validate(ir_ref.model_dump(mode="json"))
    assert private.get_manifest(ref).child_release == info
    # A marker alone has no authority, even ownership_enforced=False and even in
    # the same tenant. Private grant refuses binding to the actual served root.
    with pytest.raises(ValueError, match="a served store cannot use a private staging grant"):
        served._configure_child_staging(info, token=_CHILD_STAGING_TOKEN)
    forged = served.put_bytes(
        b"candidate",
        PutOptions(kind="tests.child", media_type="application/octet-stream", child_release=info),
        return_selected_profile=True,
    )
    with pytest.raises(ChildReleaseUnavailableError):
        FileSystemCAS(served.root, ownership_enforced=False).get_bytes(forged)


def test_private_json_write_preserves_marker_and_selected_profile(tmp_path: Path) -> None:
    served = FileSystemCAS(tmp_path / "served", ownership_enforced=False)
    private = FileSystemCAS(tmp_path / "private", ownership_enforced=False)
    info = _info(served.root)
    private._configure_child_staging(info, token=_CHILD_STAGING_TOKEN)
    ref = private.put_json(
        {"candidate": 1},
        PutOptions(kind="tests.child.json", media_type="application/json", child_release=info),
        return_selected_profile=True,
    )
    manifest = private.get_manifest(ref)
    assert manifest.child_release == info
    assert ref.manifest_profile_sha256 == ManifestLifecycle.profile_sha256(manifest)
    assert private.get_bytes(ref)


@pytest.mark.parametrize("backend", ["s3", "gcs"])
@pytest.mark.parametrize("writer", ["put_bytes", "put_json"])
def test_remote_writer_refuses_child_marker_before_backend_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str, writer: str
) -> None:
    from polisyos.core.artifacts.backends.gcs_store import GCSArtifactStore
    from polisyos.core.artifacts.backends.s3_store import S3ArtifactStore
    from polisyos.core.artifacts.store import ArtifactIntegrityError

    cls = S3ArtifactStore if backend == "s3" else GCSArtifactStore
    store = object.__new__(cls)
    touched: list[str] = []

    def forbidden_backend(*args: object, **kwargs: object) -> None:
        touched.append("backend access")
        raise AssertionError("backend must not be touched")

    monkeypatch.setattr(cls, "_s3" if backend == "s3" else "_gcs_bucket", forbidden_backend)
    opts = PutOptions(
        kind="tests.child", media_type="application/json", child_release=_info(tmp_path)
    )
    with pytest.raises(ArtifactIntegrityError, match="child_release_backend_unsupported"):
        getattr(store, writer)(b"x" if writer == "put_bytes" else {"x": 1}, opts)
    assert touched == []


def test_default_inventory_cursor_does_not_parse_or_size_cap_legacy_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    large = store.put_bytes(b"large", PutOptions(kind="legacy", media_type="text/plain"))
    malformed = store.put_bytes(b"malformed", PutOptions(kind="legacy", media_type="text/plain"))
    manifest = store.get_manifest(large).model_copy(update={"kind": "k" * (8 * 1024 * 1024 + 1)})
    store._paths(large.artifact_id)[1].write_bytes(ManifestLifecycle.to_bytes(manifest))
    store._paths(malformed.artifact_id)[1].write_bytes(b"not-json")

    def forbidden_parse(*args: object, **kwargs: object) -> None:
        raise AssertionError("legacy name census must not parse manifests")

    monkeypatch.setattr(ManifestLifecycle, "read", forbidden_parse)
    monkeypatch.setattr(ArtifactManifest, "model_validate_json", forbidden_parse)
    assert {str(large.artifact_id), str(malformed.artifact_id)} <= {
        str(artifact_id) for artifact_id in store._authenticated_default_inventory_cursor()
    }


def test_import_of_tagged_default_publishes_only_selected_view(tmp_path: Path) -> None:
    served = FileSystemCAS(tmp_path / "served", ownership_enforced=False)
    private = FileSystemCAS(tmp_path / "private", ownership_enforced=False)
    info = _info(served.root)
    private._configure_child_staging(info, token=_CHILD_STAGING_TOKEN)
    ref = private.put_bytes(
        b"selected child",
        PutOptions(kind="tests.child", media_type="text/plain", child_release=info),
        return_selected_profile=True,
    )
    aid = ref.artifact_id
    prefix = f"artifacts/sha256/{aid.hex[:2]}/{aid.hex[2:4]}/{aid.hex}"
    blob_name = prefix + ".blob"
    default_name = prefix + ".manifest.json"
    stage = served._coordinator.transaction_root / "stage" / "tagged-default-test"
    (stage / blob_name).parent.mkdir(parents=True, exist_ok=True)
    (stage / blob_name).write_bytes(private._paths(aid)[0].read_bytes())
    (stage / default_name).write_bytes(
        private._manifest_path_for_ref(aid, ref.manifest_profile_sha256).read_bytes()
    )
    served._publish_admitted_staged_import(stage, {blob_name, default_name}, {str(aid)})
    assert not served._paths(aid)[1].exists()
    assert served._manifest_path_for_ref(aid, ref.manifest_profile_sha256).exists()
    with pytest.raises(ChildReleaseUnavailableError):
        served.get_manifest(ref)


@pytest.mark.parametrize("backend", ["s3", "gcs"])
@pytest.mark.parametrize(
    "reader_method", ["get_manifest", "get_raw_manifest_bytes", "get_bytes", "has"]
)
def test_remote_reader_refuses_marked_view_before_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str, reader_method: str
) -> None:
    from polisyos.core.artifacts.backends.gcs_store import GCSArtifactStore
    from polisyos.core.artifacts.backends.s3_store import S3ArtifactStore

    served = FileSystemCAS(tmp_path / "served", ownership_enforced=False)
    private = FileSystemCAS(tmp_path / "private", ownership_enforced=False)
    info = _info(served.root)
    private._configure_child_staging(info, token=_CHILD_STAGING_TOKEN)
    ref = private.put_bytes(
        b"private payload",
        PutOptions(kind="tests.child", media_type="text/plain", child_release=info),
        return_selected_profile=True,
    )
    raw = private._manifest_path_for_ref(ref.artifact_id, ref.manifest_profile_sha256).read_bytes()
    cls = S3ArtifactStore if backend == "s3" else GCSArtifactStore
    store = object.__new__(cls)
    reads: list[str] = []
    if reader_method == "has":
        monkeypatch.setattr(
            cls, "_cache_read", lambda self, aid, suffix: b"payload" if suffix == ".blob" else raw
        )
    else:
        monkeypatch.setattr(cls, "_cache_read", lambda *args: None)
    monkeypatch.setattr(cls, "_cache_write", lambda *args: None)
    monkeypatch.setattr(cls, "_manifest_key", lambda *args: "manifest")
    monkeypatch.setattr(cls, "_blob_key", lambda *args: "payload")

    def read(key: str) -> bytes:
        reads.append(key)
        return raw if key == "manifest" else b"private payload"

    if backend == "s3":
        monkeypatch.setattr(cls, "_get_object_bytes", lambda self, key: read(key))
    else:

        class Bucket:
            def blob(self, key: str) -> str:
                return key

        monkeypatch.setattr(cls, "_gcs_bucket", lambda self: Bucket())
        monkeypatch.setattr(cls, "_download_blob_bytes", lambda self, key: read(key))
    with pytest.raises(ChildReleaseUnavailableError, match="remote_release_verifier_unavailable"):
        getattr(store, reader_method)(ref)
    assert reads == ([] if reader_method == "has" else ["manifest"])


@pytest.mark.parametrize("backend", ["s3", "gcs"])
def test_remote_inventory_omits_unsupported_marked_default(
    monkeypatch: pytest.MonkeyPatch, backend: str
) -> None:
    from polisyos.core.artifacts.backends.gcs_store import GCSArtifactStore
    from polisyos.core.artifacts.backends.s3_store import S3ArtifactStore

    cls = S3ArtifactStore if backend == "s3" else GCSArtifactStore
    store = object.__new__(cls)
    store._prefix = "artifacts"
    store._bucket = "test"
    marked = "1" * 64
    legacy = "2" * 64
    keys = [
        f"artifacts/sha256/xx/{value}.manifest.json"
        for value in ("short", marked, legacy, "also-short")
    ]

    def guarded_manifest(self: object, aid: object) -> bytes:
        if str(aid).endswith(marked):
            raise ChildReleaseUnavailableError("remote_release_verifier_unavailable")
        return b"legacy"

    monkeypatch.setattr(cls, "get_raw_manifest_bytes", guarded_manifest)
    if backend == "s3":

        class Paginator:
            def paginate(self, **kwargs: object) -> list[dict[str, object]]:
                return [{"Contents": [{"Key": key} for key in keys]}]

        class Client:
            def get_paginator(self, name: str) -> Paginator:
                return Paginator()

        monkeypatch.setattr(cls, "_s3", lambda self: Client())
    else:

        class Blob:
            def __init__(self, name: str) -> None:
                self.name = name

        class Bucket:
            def list_blobs(self, *, prefix: str) -> list[Blob]:
                return [Blob(key) for key in keys]

        monkeypatch.setattr(cls, "_gcs_bucket", lambda self: Bucket())
    assert [aid.hex for aid in store.iter_artifact_ids()] == [legacy]
