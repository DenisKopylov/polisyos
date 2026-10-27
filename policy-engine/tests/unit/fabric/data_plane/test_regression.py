from __future__ import annotations

from hashlib import sha256

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, IntegrityInfo
from polisyos.fabric.data_plane.regression import compare_artifact_hashes


class _ManifestStore:
    def __init__(self, manifests: dict[str, ArtifactManifest]) -> None:
        self._manifests = manifests

    def get_manifest(self, artifact_id: ArtifactID | ArtifactRef | str) -> ArtifactManifest:
        return self._manifests[str(artifact_id)]


def _manifest(payload: bytes, *, kind: str) -> ArtifactManifest:
    artifact_id = ArtifactID.from_sha256_hex(sha256(payload).hexdigest())
    return ArtifactManifest(
        artifact_id=artifact_id,
        kind=kind,
        media_type="application/octet-stream",
        byte_size=len(payload),
        integrity=IntegrityInfo(sha256=artifact_id.hex),
    )


def test_compare_artifact_hashes_uses_content_identity_across_manifest_metadata() -> None:
    payload = b'{"value":1}'
    record_manifest = _manifest(payload, kind="recorded")
    replay_manifest = _manifest(payload, kind="replayed")
    store = _ManifestStore(
        {
            "record": record_manifest,
            "replay": replay_manifest,
        }
    )

    assert record_manifest.kind != replay_manifest.kind
    assert record_manifest.artifact_id == replay_manifest.artifact_id
    assert compare_artifact_hashes(store, "record", "replay") == []


def test_compare_artifact_hashes_reports_different_payload_identity() -> None:
    record_manifest = _manifest(b'{"value":1}', kind="recorded")
    replay_manifest = _manifest(b'{"value":2}', kind="replayed")
    store = _ManifestStore(
        {
            "record": record_manifest,
            "replay": replay_manifest,
        }
    )

    assert record_manifest.artifact_id != replay_manifest.artifact_id
    assert compare_artifact_hashes(store, "record", "replay") == [
        "artifact content_hash: "
        f"record={record_manifest.artifact_id.hex}, "
        f"replay={replay_manifest.artifact_id.hex}"
    ]


def test_identical_incomplete_runs_are_not_successful_replay_equivalence() -> None:
    """A pair of identical partial outcomes cannot satisfy the completion gate."""
    from polisyos.fabric.data_plane.orchestrator import IngestionResult
    from polisyos.fabric.data_plane.regression import compare_ingestion_runs

    record = IngestionResult(datasets_fetched=1)
    replay = IngestionResult(datasets_fetched=1)
    record.status = replay.status = "partial"
    comparison = compare_ingestion_runs(record, replay)
    assert not comparison.match
    assert any("incomplete" in reason for reason in comparison.mismatches)
