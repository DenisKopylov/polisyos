from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.data_forge.domains.ukraine.manifests import (
    ArtifactRecord,
    BuildRunManifest,
    write_manifest,
)
from polisyos.data_forge.domains.ukraine.models import StageId
from polisyos.data_forge.read_api.ukraine import (
    UkraineStageArtifactVerificationError,
    load_verified_stage_artifacts,
)


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
) -> None:
    manifest_path, output_path = _stage_manifest(tmp_path)

    receipt = load_verified_stage_artifacts(
        manifest_path,
        allowed_root=tmp_path,
        expected_stage="d3",
        required_outputs=(output_path.name,),
    )

    assert receipt.stage_id == "d3"
    assert receipt.status == "completed"
    assert receipt.finished_at == "2026-08-26T10:01:00+00:00"
    assert receipt.outputs[output_path.name].path == str(output_path.resolve())
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


def test_verified_stage_artifacts_fail_closed_on_content_drift(tmp_path: Path) -> None:
    manifest_path, output_path = _stage_manifest(tmp_path)
    output_path.write_text('{"rows": 3}\n', encoding="utf-8")

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="content hash mismatch",
    ):
        load_verified_stage_artifacts(
            manifest_path,
            allowed_root=tmp_path,
            expected_stage="d3",
            required_outputs=(output_path.name,),
        )


def test_verified_stage_artifacts_fail_closed_on_noncompleted_stage(tmp_path: Path) -> None:
    manifest_path, output_path = _stage_manifest(tmp_path, status="blocked")

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="status must be completed",
    ):
        load_verified_stage_artifacts(
            manifest_path,
            allowed_root=tmp_path,
            expected_stage="d3",
            required_outputs=(output_path.name,),
        )


def test_verified_stage_artifacts_reject_paths_outside_the_declared_root(
    tmp_path: Path,
) -> None:
    allowed_root = tmp_path / "allowed"
    manifest_path, output_path = _stage_manifest(tmp_path / "outside")

    with pytest.raises(
        UkraineStageArtifactVerificationError,
        match="manifest path escapes allowed root",
    ):
        load_verified_stage_artifacts(
            manifest_path,
            allowed_root=allowed_root,
            expected_stage="d3",
            required_outputs=(output_path.name,),
        )
