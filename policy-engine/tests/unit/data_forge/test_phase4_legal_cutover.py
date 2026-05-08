from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from polisyos.data_forge.read_api.legal import (
    compare_lex_shadow_bundles,
    load_lex_shadow_bundle,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "_data" / "data_forge" / "legal_shadow"
BASELINE_ROOT = FIXTURES_ROOT / "baseline"
CANDIDATE_ROOT = FIXTURES_ROOT / "candidate"
ACCEPTED_ROOT_DESCRIPTOR = FIXTURES_ROOT / "accepted_artifact_root.json"


def test_legal_batch_runtime_lives_in_data_forge_and_legacy_entrypoints_are_removed() -> None:
    new_config = importlib.import_module("polisyos.data_forge.domains.legal.batch.config")
    new_pipeline = importlib.import_module("polisyos.data_forge.domains.legal.batch.pipeline")

    assert "polisyos.data_forge.domains.legal.batch.pipeline" in sys.modules
    assert (
        Path(new_pipeline.__file__)
        .as_posix()
        .endswith("src/polisyos/data_forge/domains/legal/batch/pipeline.py")
    )
    assert new_config.BatchConfig.__module__ == "polisyos.data_forge.domains.legal.batch.config"
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("polisyos.lex.batch")


def test_legal_batch_legacy_entrypoints_are_deleted() -> None:
    shim_root = Path(__file__).resolve().parents[3] / "src" / "polisyos" / "lex" / "batch"

    assert not shim_root.exists()


def test_legal_shadow_diff_covers_phase4_output_classes() -> None:
    baseline = load_lex_shadow_bundle(BASELINE_ROOT)
    candidate = load_lex_shadow_bundle(CANDIDATE_ROOT)

    diff = compare_lex_shadow_bundles(baseline, candidate)

    assert baseline.cache_resume_markers
    assert tuple(marker.relative_path for marker in baseline.cache_resume_markers) == (
        "cache/spo_cache.json",
        "progress/resume_state.json",
    )
    assert diff.has_changes
    assert {
        "benchmark_report.json",
        "claim_exports/normative_claims.jsonl",
        "claim_exports/normative_claims_summary.json",
        "manifests/run.json",
        "publish/manifest.json",
        "publish/consumer_readiness.json",
        "qc_report.json",
    } <= set(diff.changed_artifacts)
    assert diff.added_artifacts == ("claim_exports/normative_claim_sets_summary.json",)
    assert diff.changed_cache_resume_markers == ("cache/spo_cache.json",)
    assert diff.readiness_changes["release_ready"] == (True, False)
    assert diff.metric_deltas["quality.metrics.normative_ready_share_pct"] == -25.0


def test_legal_shadow_diff_reports_no_changes_for_identical_outputs() -> None:
    baseline = load_lex_shadow_bundle(BASELINE_ROOT)

    diff = compare_lex_shadow_bundles(baseline, baseline)

    assert not diff.has_changes
    assert diff.added_artifacts == ()
    assert diff.removed_artifacts == ()
    assert diff.changed_artifacts == ()
    assert diff.changed_cache_resume_markers == ()
    assert diff.readiness_changes == {}
    assert diff.metric_deltas == {}


def test_legal_cloud_runner_imports_data_forge_batch_runtime() -> None:
    runner = importlib.import_module("tools.ops_runners.cloud.run_lex_from_manifest")

    assert runner.BatchConfig.__module__ == "polisyos.data_forge.domains.legal.batch.config"
    assert (
        runner.run_batch_pipeline.__module__ == "polisyos.data_forge.domains.legal.batch.pipeline"
    )


def test_legal_runtime_jobs_use_read_api_surface() -> None:
    from polisyos.data_forge.read_api.legal import BatchConfig, ProgressTracker, run_batch_pipeline

    service = importlib.import_module("polisyos.runtime.http.services.control.run_lifecycle")
    control_source = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "control"
        / "run_lifecycle.py"
    ).read_text(encoding="utf-8")

    assert "from polisyos.lex.batch" not in control_source
    assert "from polisyos.data_forge.read_api.legal" in control_source
    assert service.ControlPlaneService.__module__ == service.__name__
    assert BatchConfig.__module__ == "polisyos.data_forge.domains.legal.batch.config"
    assert ProgressTracker.__module__ == "polisyos.data_forge.domains.legal.batch.progress"
    assert run_batch_pipeline.__module__ == "polisyos.data_forge.domains.legal.batch.pipeline"


def test_legal_cli_entrypoint_is_data_forge_only() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "polisyos.data_forge.domains.legal.batch", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Legal Data Forge pipeline" in result.stdout

    retired = subprocess.run(
        [sys.executable, "-m", "polisyos.lex.batch", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert retired.returncode != 0


def test_accepted_npa_artifact_root_is_recorded() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    descriptor = json.loads(ACCEPTED_ROOT_DESCRIPTOR.read_text(encoding="utf-8"))

    assert descriptor["schema_version"] == "polisyos.data_forge.legal_cutover.accepted_root.v1"
    assert descriptor["accepted_at"] == "2026-05-01"
    assert descriptor["root_kind"] == "ignored_immutable_local_root"
    assert descriptor["root"] == "production_data/lex_current_20260501/finalize"
    required = {
        item["class"]: item["path"]
        for item in descriptor["required_artifacts"]
        if isinstance(item, dict)
    }
    assert required == {
        "claims": "claim_exports/normative_claims.jsonl",
        "claim_summary": "claim_exports/normative_claims_summary.json",
        "qc": "qc_report.json",
        "benchmark_summary": "benchmark_report.json",
        "graph_publish_candidate": "lex_knowledge_graph.duckdb",
    }
    assert {
        "publish/manifest.json",
        "publish/consumer_readiness.json",
        "cache/spo_cache.json",
        "progress/resume_state.json",
    } <= set(descriptor["ci_replay_covers"])

    accepted_root = repo_root / descriptor["root"]
    if accepted_root.exists():
        for relative_path in required.values():
            artifact_path = accepted_root / relative_path
            assert artifact_path.exists(), relative_path
            assert artifact_path.stat().st_size > 0, relative_path


def test_legal_batch_complexity_exceptions_are_burned_down() -> None:
    payload = tomllib.loads(
        (
            Path(__file__).resolve().parents[3] / "architecture" / "complexity_exceptions.toml"
        ).read_text(encoding="utf-8")
    )
    exception_paths = {
        str(entry.get("path")) for entry in payload.get("exception", []) if isinstance(entry, dict)
    }

    assert not {path for path in exception_paths if path.startswith("src/polisyos/lex/batch/")}
