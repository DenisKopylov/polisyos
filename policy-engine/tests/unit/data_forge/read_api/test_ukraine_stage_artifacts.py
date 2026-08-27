from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    D5ReleaseContentRef,
    D5ReleaseHandoffRequest,
    D5ReleaseProducerFacts,
    ReleaseManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import StageId
from polisyos.data_forge.read_api.ukraine import (
    UkraineStageArtifactVerificationError,
    load_verified_release_artifact_bytes,
    load_verified_release_artifacts,
    load_verified_stage_artifacts,
    load_verified_stage_output_bytes,
)


def _release_manifest(root: Path) -> tuple[Path, dict[str, Path]]:
    release_root = root / "bundles" / "d5"
    runtime_dir = release_root / "runtime_bundle_v1"
    method_dir = release_root / "method_contract_bundle_v1"
    runtime_dir.mkdir(parents=True)
    method_dir.mkdir(parents=True)
    runtime_file = runtime_dir / "runtime.json"
    runtime_file.write_text('{"runtime": true}\n', encoding="utf-8")
    method_file = method_dir / "contract.json"
    method_file.write_text('{"contract": true}\n', encoding="utf-8")
    cell_registry = root / "runtime" / "cell_registry_region_sector.parquet"
    cell_registry.parent.mkdir(parents=True)
    cell_registry.write_bytes(b"cell-registry-bytes")
    d4_request = root / "calibration" / "d4_governance_request.json"
    d4_request.parent.mkdir(parents=True)
    d4_request.write_text('{"candidate": true}\n', encoding="utf-8")
    compression = release_root / "graph_compression_bundle.json"
    compression.write_text('{"fidelity_metrics": {}}\n', encoding="utf-8")
    content_records = {
        "cell_registry": ArtifactRecord.from_path(cell_registry),
        "d4_governance_request": ArtifactRecord.from_path(d4_request),
        "graph_compression_bundle": ArtifactRecord.from_path(compression),
    }
    handoff = D5ReleaseHandoffRequest(
        declared_release_root=str(release_root),
        producer_facts=D5ReleaseProducerFacts(
            primary_region_id="01",
            primary_sector_id="A",
            graph_compression_degree_preservation_score=1.0,
            graph_compression_edge_weight_reconstruction_error=0.0,
        ),
        content_refs={
            name: D5ReleaseContentRef.from_artifact_record(record)
            for name, record in content_records.items()
        },
    )
    handoff_path = release_root / "d5_release_handoff_request.json"
    write_manifest(handoff_path, handoff)
    manifest = ReleaseManifest(
        bundles={
            "runtime_bundle_v1": ArtifactRecord(
                path=str(runtime_dir),
                size_bytes=runtime_file.stat().st_size,
            ),
            "method_contract_bundle_v1": ArtifactRecord(
                path=str(method_dir),
                size_bytes=method_file.stat().st_size,
            ),
        },
        bundle_contents={
            "runtime_bundle_v1": {"runtime.json": ArtifactRecord.from_path(runtime_file)},
            "method_contract_bundle_v1": {
                "contract.json": ArtifactRecord.from_path(method_file)
            },
        },
        evidence_refs={
            **content_records,
            "d5_release_handoff_request": ArtifactRecord.from_path(handoff_path),
        },
    )
    manifest_path = release_root / "release_manifest_v1.json"
    write_manifest(manifest_path, manifest)
    return manifest_path, {
        "manifest": manifest_path,
        "runtime": runtime_file,
        "method": method_file,
        "cell_registry": cell_registry,
        "d4_governance_request": d4_request,
        "graph_compression_bundle": compression,
        "d5_release_handoff_request": handoff_path,
    }


def _stage_manifest(
    root: Path,
    *,
    status: str = "completed",
) -> tuple[Path, Path]:
    output_path = root / "stages" / "d3" / "microsim_survey_contract_v1.json"
    output_path.parent.mkdir(parents=True)
    output_path.write_text('{"rows": 2}\n', encoding="utf-8")
    manifest = BuildRunManifest(
        run_id="d3-test-run",
        stage_id=StageId.D3,
        status=status,
        started_at="2026-08-26T10:00:00+00:00",
        finished_at="2026-08-26T10:01:00+00:00",
        outputs=[ArtifactRecord.from_path(output_path, row_count=2)],
    )
    manifest_path = root / "manifests" / "build_d3.json"
    write_manifest(manifest_path, manifest)
    return manifest_path, output_path


def test_verified_stage_artifacts_recompute_and_bind_the_producer_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path, output_path = _stage_manifest(tmp_path)
    original_manifest_bytes = manifest_path.read_bytes()
    original_output_bytes = output_path.read_bytes()
    store = FileSystemCAS(tmp_path / "cas")
    producer_paths = {manifest_path.resolve(), output_path.resolve()}
    read_counts = dict.fromkeys(producer_paths, 0)
    read_completed: set[Path] = set()
    read_bytes = Path.read_bytes
    stat = Path.stat

    def _counted_read_bytes(path: Path) -> bytes:
        if path in producer_paths:
            read_counts[path] += 1
            read_completed.add(path)
        return read_bytes(path)

    def _reject_post_read_stat(path: Path, *args, **kwargs):
        if path in read_completed:
            raise AssertionError(f"producer path was stated after its admitted read: {path}")
        return stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", _counted_read_bytes)
    monkeypatch.setattr(Path, "stat", _reject_post_read_stat)

    receipt = load_verified_stage_artifacts(
        manifest_path,
        store=store,
        allowed_root=tmp_path,
        expected_stage="d3",
        required_outputs=(output_path.name,),
    )

    assert receipt.stage_id == "d3"
    assert receipt.status == "completed"
    assert receipt.finished_at == "2026-08-26T10:01:00+00:00"
    assert receipt.manifest_ref.artifact_id.hex == receipt.manifest_sha256
    assert receipt.outputs[output_path.name].source_path == str(output_path.resolve())
    assert (
        receipt.outputs[output_path.name].content_ref.artifact_id.hex
        == receipt.outputs[output_path.name].sha256
    )
    assert receipt.outputs[output_path.name].row_count == 2
    assert receipt.stage_status_provenance == "institutionally_supplied"
    assert receipt.path_scope_provenance == "recomputed"
    assert receipt.content_binding_provenance == "recomputed"
    assert receipt.authoritative_for == (
        "producer_artifact_identity",
        "producer_artifact_content_binding",
    )
    assert "governance_admissibility" in receipt.may_not_use_for
    assert "release_acceptance" in receipt.may_not_use_for
    assert read_counts == dict.fromkeys(producer_paths, 1)

    output_path.write_text('{"rows": "mutated"}\n', encoding="utf-8")
    manifest_path.write_text('{"status": "mutated"}\n', encoding="utf-8")

    assert (
        load_verified_stage_output_bytes(store, receipt, output_path.name)
        == original_output_bytes
    )
    assert store.get_bytes(receipt.manifest_ref.artifact_id) == original_manifest_bytes


def test_verified_stage_artifacts_fail_closed_on_content_drift(tmp_path: Path) -> None:
    manifest_path, output_path = _stage_manifest(tmp_path)
    output_path.write_text('{"rows": 3}\n', encoding="utf-8")
    store = FileSystemCAS(tmp_path / "cas")

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="content hash mismatch",
    ):
        load_verified_stage_artifacts(
            manifest_path,
            store=store,
            allowed_root=tmp_path,
            expected_stage="d3",
            required_outputs=(output_path.name,),
        )


def test_verified_stage_artifacts_fail_closed_on_noncompleted_stage(tmp_path: Path) -> None:
    manifest_path, output_path = _stage_manifest(tmp_path, status="blocked")
    store = FileSystemCAS(tmp_path / "cas")

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="status must be completed",
    ):
        load_verified_stage_artifacts(
            manifest_path,
            store=store,
            allowed_root=tmp_path,
            expected_stage="d3",
            required_outputs=(output_path.name,),
        )


def test_verified_stage_artifacts_reject_paths_outside_the_declared_root(
    tmp_path: Path,
) -> None:
    allowed_root = tmp_path / "allowed"
    manifest_path, output_path = _stage_manifest(tmp_path / "outside")
    store = FileSystemCAS(tmp_path / "cas")

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="manifest path escapes allowed root",
    ):
        load_verified_stage_artifacts(
            manifest_path,
            store=store,
            allowed_root=allowed_root,
            expected_stage="d3",
            required_outputs=(output_path.name,),
        )


def test_verified_release_artifacts_bind_exact_manifest_and_handoff_sets_to_cas(
    tmp_path: Path,
) -> None:
    manifest_path, producer_paths = _release_manifest(tmp_path)
    original = {name: path.read_bytes() for name, path in producer_paths.items()}
    store = FileSystemCAS(tmp_path / "cas")

    receipt = load_verified_release_artifacts(
        manifest_path,
        store=store,
        allowed_root=tmp_path,
        expected_stage="d5",
    )

    assert receipt.stage_id == "d5"
    assert receipt.stage_declaration_provenance == "institutionally_supplied"
    assert receipt.release_root_declaration_provenance == "institutionally_supplied"
    assert receipt.path_scope_provenance == "recomputed"
    assert receipt.content_binding_provenance == "recomputed"
    assert receipt.authority_purpose == "non_authoritative_release_artifact_admission"
    assert receipt.authoritative_for == ()
    assert receipt.verified_for == (
        "producer_artifact_identity",
        "producer_artifact_content_binding",
    )
    assert receipt.manifest_size_bytes == len(original["manifest"])
    with pytest.raises(ValidationError, match="cannot declare downstream authority"):
        type(receipt).model_validate(
            {
                **receipt.model_dump(mode="json"),
                "authoritative_for": ["release_acceptance"],
            }
        )
    assert "release_acceptance" in receipt.may_not_use_for
    assert set(receipt.evidence) == {
        "cell_registry",
        "d4_governance_request",
        "d5_release_handoff_request",
        "graph_compression_bundle",
    }
    assert set(receipt.handoff_request.content_refs) == set(receipt.evidence) - {
        "d5_release_handoff_request"
    }
    for path in producer_paths.values():
        path.write_bytes(b"mutated-after-admission")
    assert (
        load_verified_release_artifact_bytes(store, receipt.evidence["cell_registry"])
        == original["cell_registry"]
    )
    assert store.get_bytes(receipt.manifest_ref.artifact_id) == original["manifest"]


def test_verified_release_artifacts_reject_forged_hash_strings_over_tampered_bytes(
    tmp_path: Path,
) -> None:
    manifest_path, producer_paths = _release_manifest(tmp_path)
    producer_paths["cell_registry"].write_bytes(b"tampered-but-producer-strings-unchanged")

    with pytest.raises(UkraineStageArtifactVerificationError, match="content hash mismatch"):
        load_verified_release_artifacts(
            manifest_path,
            store=FileSystemCAS(tmp_path / "cas"),
            allowed_root=tmp_path,
            expected_stage="d5",
        )


def test_verified_release_artifacts_reject_nonexact_evidence_and_path_escape(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _release_manifest(tmp_path)
    manifest = ReleaseManifest.model_validate_json(manifest_path.read_bytes())
    outside = tmp_path.parent / "outside-release-evidence.json"
    outside.write_text("{}\n", encoding="utf-8")
    malformed = manifest.model_copy(
        update={
            "evidence_refs": {
                **manifest.evidence_refs,
                "unexpected": ArtifactRecord.from_path(outside),
            }
        }
    )
    write_manifest(manifest_path, malformed)

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="release manifest evidence_refs must match the exact D5 set",
    ):
        load_verified_release_artifacts(
            manifest_path,
            store=FileSystemCAS(tmp_path / "cas"),
            allowed_root=tmp_path,
            expected_stage="d5",
        )

    escaped = manifest.model_copy(
        update={
            "evidence_refs": {
                **manifest.evidence_refs,
                "graph_compression_bundle": ArtifactRecord.from_path(outside),
            }
        }
    )
    write_manifest(manifest_path, escaped)
    with pytest.raises(UkraineStageArtifactVerificationError, match="escapes allowed root"):
        load_verified_release_artifacts(
            manifest_path,
            store=FileSystemCAS(tmp_path / "path-escape-cas"),
            allowed_root=tmp_path,
            expected_stage="d5",
        )

    forged_inventory = manifest.model_copy(
        update={
            "bundle_contents": {
                **manifest.bundle_contents,
                "runtime_bundle_v1": {
                    "forged-runtime-name.json": manifest.bundle_contents[
                        "runtime_bundle_v1"
                    ]["runtime.json"]
                },
            }
        }
    )
    write_manifest(manifest_path, forged_inventory)
    with pytest.raises(UkraineStageArtifactVerificationError, match="inventory key"):
        load_verified_release_artifacts(
            manifest_path,
            store=FileSystemCAS(tmp_path / "forged-inventory-cas"),
            allowed_root=tmp_path,
            expected_stage="d5",
        )


def test_verified_release_artifacts_reject_self_consistent_handoff_manifest_mismatch(
    tmp_path: Path,
) -> None:
    manifest_path, _ = _release_manifest(tmp_path)
    manifest = ReleaseManifest.model_validate_json(manifest_path.read_bytes())
    handoff_path = Path(manifest.evidence_refs["d5_release_handoff_request"].path)
    handoff = D5ReleaseHandoffRequest.model_validate_json(handoff_path.read_bytes())
    cell_record = manifest.evidence_refs["cell_registry"]
    handoff = handoff.model_copy(
        update={
            "content_refs": {
                **handoff.content_refs,
                "graph_compression_bundle": D5ReleaseContentRef.from_artifact_record(
                    cell_record
                ),
            }
        }
    )
    write_manifest(handoff_path, handoff)
    manifest = manifest.model_copy(
        update={
            "evidence_refs": {
                **manifest.evidence_refs,
                "d5_release_handoff_request": ArtifactRecord.from_path(handoff_path),
            }
        }
    )
    write_manifest(manifest_path, manifest)

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="handoff content_refs must equal manifest evidence_refs",
    ):
        load_verified_release_artifacts(
            manifest_path,
            store=FileSystemCAS(tmp_path / "cas"),
            allowed_root=tmp_path,
            expected_stage="d5",
        )
