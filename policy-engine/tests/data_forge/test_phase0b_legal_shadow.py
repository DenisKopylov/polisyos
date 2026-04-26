from __future__ import annotations

import shutil
import sys
from pathlib import Path

from polisyos.data_forge.kernel.testing import capture_golden_file, verify_golden_file
from polisyos.data_forge.read_api.legal import (
    compare_lex_shadow_bundles,
    load_lex_shadow_bundle,
)

FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures" / "legal_shadow"
BASELINE_ROOT = FIXTURES_ROOT / "baseline"
CANDIDATE_ROOT = FIXTURES_ROOT / "candidate"


def test_legal_shadow_adapter_loads_completed_lex_fixture_without_lex_imports() -> None:
    before = {name for name in sys.modules if name.startswith("polisyos.lex.batch")}

    bundle = load_lex_shadow_bundle(BASELINE_ROOT)

    after = {name for name in sys.modules if name.startswith("polisyos.lex.batch")}
    assert after == before
    assert bundle.pipeline == "lex"
    assert bundle.consumer_ready is True
    assert bundle.release_ready is True
    assert bundle.warnings == ()
    assert len(bundle.artifacts) == 6
    assert all(artifact.exists for artifact in bundle.artifacts)
    assert all(artifact.checksum_ok is True for artifact in bundle.artifacts)
    assert bundle.table_counts["lex_normative_facts"] == 2
    assert bundle.artifact_by_relative_path("claim_exports/normative_claims_summary.json")
    assert bundle.stage_manifests[0].stage == "run"
    assert bundle.stage_manifests[0].metrics["facts"] == 2


def test_legal_shadow_diff_reports_artifact_and_metric_changes() -> None:
    baseline = load_lex_shadow_bundle(BASELINE_ROOT)
    candidate = load_lex_shadow_bundle(CANDIDATE_ROOT)

    diff = compare_lex_shadow_bundles(baseline, candidate)

    assert diff.has_changes
    assert diff.added_artifacts == ("claim_exports/normative_claim_sets_summary.json",)
    assert "claim_exports/normative_claims_summary.json" in diff.changed_artifacts
    assert "publish/consumer_readiness.json" in diff.changed_artifacts
    assert diff.readiness_changes["release_ready"] == (True, False)
    assert diff.metric_deltas["table_counts.lex_normative_facts"] == 1.0
    assert diff.metric_deltas["quality.metrics.normative_ready_share_pct"] == -25.0
    assert diff.metric_deltas["benchmark.metrics.benchmark_search_top5_relevance_pct"] == -20.0


def test_legal_shadow_golden_fixture_detects_manifest_drift(tmp_path) -> None:
    working_root = tmp_path / "legal_shadow"
    shutil.copytree(BASELINE_ROOT, working_root)
    golden = capture_golden_file(
        working_root,
        "publish/manifest.json",
        name="baseline_publish_manifest",
    )

    assert verify_golden_file(working_root, golden)

    manifest_path = working_root / "publish" / "manifest.json"
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            '"pipeline": "lex"', '"pipeline": "lex2"'
        ),
        encoding="utf-8",
    )
    assert not verify_golden_file(working_root, golden)
