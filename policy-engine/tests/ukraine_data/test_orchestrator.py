from __future__ import annotations

from pathlib import Path

from polisyos.ukraine_data.manifests import BuildRunManifest, PartAGateManifest, write_manifest
from polisyos.ukraine_data.models import StageId, build_default_pipeline_config
from polisyos.ukraine_data.orchestrator import UkraineDataOrchestrator


def test_bootstrap_server_writes_expected_outputs(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config.server.require_server_for_build = False
    config.server.storage_root = tmp_path / "server-root"
    config.server.workdir = tmp_path / "repo"
    orchestrator = UkraineDataOrchestrator(config)

    summary = orchestrator.bootstrap_server(write_capabilities=True)

    assert summary.status == "completed"
    output_paths = {Path(output.path) for output in summary.manifest.outputs}
    assert config.server.env_path in output_paths
    assert orchestrator.bootstrap_script_path() in output_paths
    assert config.build_root.capability_manifest_path in output_paths


def test_build_stage_blocks_when_part_a_gate_is_missing(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config.server.require_server_for_build = False
    orchestrator = UkraineDataOrchestrator(config)

    summary = orchestrator.build_stage(StageId.D0_P0)

    assert summary.status == "blocked_by_part_a_gate"
    assert "part_a_gate_manifest.json" in summary.manifest.errors[0]


def test_validate_stage_outputs_reports_missing_artifact(tmp_path: Path) -> None:
    config = build_default_pipeline_config(root=tmp_path / "ukraine")
    config.server.require_server_for_build = False
    orchestrator = UkraineDataOrchestrator(config)
    orchestrator.ensure_layout()
    write_manifest(
        config.build_root.part_a_gate_manifest_path,
        PartAGateManifest(status="passed", passed=True),
    )
    missing_path = tmp_path / "does_not_exist.json"
    stage_manifest = BuildRunManifest(
        run_id="d0_test",
        stage_id=StageId.D0_P0,
        status="completed",
        started_at="2026-04-05T00:00:00Z",
        finished_at="2026-04-05T00:00:00Z",
        outputs=[{"path": str(missing_path), "sha256": "", "size_bytes": 0}],
    )
    write_manifest(orchestrator.stage_manifest_path(StageId.D0_P0), stage_manifest)

    summary = orchestrator.validate_stage_outputs(StageId.D0_P0)

    assert summary.status == "failed"
    assert summary.manifest.findings[0].code == "missing_output"
