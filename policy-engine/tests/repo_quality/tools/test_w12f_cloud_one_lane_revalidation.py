from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import (
    run_policy_design_case_cloud_one_lane_revalidation as w12f,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT
    / "architecture/policy_design_case/wave12f_cloud_one_lane_revalidation_manifest.json"
)


def test_w12f_manifest_is_deterministic_and_declares_one_lane_contract() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == w12f.build_w12f_manifest()
    assert manifest["schema_version"] == w12f.MANIFEST_SCHEMA_VERSION
    assert manifest["phase_id"] == "W12.F"
    assert "run_canary_matrix.py" in manifest["canary_matrix_tool_ref"]
    assert "--only-lane" in manifest["command_contract"]["cloud_lane_command"]
    assert manifest["metric_policy"]["preserves_three_outcome_metrics"] is True
    assert manifest["authority_boundary"]["authoritative_for"] == [
        "w12f_cloud_one_lane_revalidation"
    ]


def test_w12f_passes_when_cloud_lane_and_metrics_clear_floors() -> None:
    report = w12f.build_w12f_cloud_one_lane_revalidation_report(
        matrix_run_report=_matrix_run(status="passed"),
        w12b_report=_w12b_report(rate=82.0),
        w12c_report=_w12c_report(),
        w12d_report=_w12d_report(runtime_rate=0.75, alignment_rate=0.75),
        w12e_report=_w12e_report(status="pass"),
        repo_root=REPO_ROOT,
        rollout_posture="governed-pilot",
    )

    assert report["schema_version"] == w12f.SCHEMA_VERSION
    assert report["status"] == "pass"
    assert report["typed_blockers"] == []
    assert report["summary"]["selected_lane_status"] == "passed"
    assert report["outcome_metrics"]["runtime_useful_design_rate"]["value"] == 0.75
    assert report["outcome_metrics"]["compilation_truthfulness_rate"]["value"] == 82.0
    assert report["frozen_revision_config"]["git_revision"]
    assert "production_closeout_authority" in report["authority_boundary"]["may_not_use_for"]


def test_w12f_missing_cloud_lane_evidence_is_typed_blocker() -> None:
    report = w12f.build_w12f_cloud_one_lane_revalidation_report(
        matrix_run_report={},
        w12b_report=_w12b_report(rate=82.0),
        w12c_report=_w12c_report(),
        w12d_report=_w12d_report(runtime_rate=0.75, alignment_rate=0.75),
        w12e_report=_w12e_report(status="pass"),
        repo_root=REPO_ROOT,
        rollout_posture="governed-pilot",
    )

    assert report["status"] == "blocked"
    blocker = next(
        item
        for item in report["typed_blockers"]
        if item["code"] == "w12f_cloud_lane_evidence_missing"
    )
    assert blocker["owner"] == "team-runtime-platform"
    assert blocker["counts_as_useful_design"] is False


def test_w12f_low_runtime_useful_design_floor_is_typed_blocker() -> None:
    report = w12f.build_w12f_cloud_one_lane_revalidation_report(
        matrix_run_report=_matrix_run(status="passed"),
        w12b_report=_w12b_report(rate=82.0),
        w12c_report=_w12c_report(),
        w12d_report=_w12d_report(runtime_rate=0.0, alignment_rate=0.0),
        w12e_report=_w12e_report(status="pass"),
        repo_root=REPO_ROOT,
        rollout_posture="governed-pilot",
    )

    assert report["status"] == "blocked"
    codes = {blocker["code"] for blocker in report["typed_blockers"]}
    assert "w12f_runtime_useful_design_floor_not_met" in codes
    assert "w12f_useful_design_alignment_floor_not_met" in codes


def _matrix_run(*, status: str) -> dict[str, object]:
    lane_id = w12f.DEFAULT_CLOUD_LANE_ID
    return {
        "schema_version": "policyos.canary_matrix_run.v1",
        "selected_lane_ids": [lane_id],
        "lanes": [
            {
                "lane_id": lane_id,
                "declared_status": "ready",
                "status": status,
                "bundle_path": "_build/.tmp/canary-bundles/cloud-one-lane",
                "scorecard_status": "pass" if status == "passed" else "fail",
                "source_truth_conflicts": [],
                "unknown_provenance_collapses": [],
            }
        ],
    }


def _w12b_report(*, rate: float) -> dict[str, object]:
    return {
        "phase_id": "W12.B",
        "status": "pass",
        "summary": {"aggregate_compilation_truthfulness_rate": rate},
        "typed_compilation_blockers": [],
    }


def _w12c_report() -> dict[str, object]:
    return {
        "phase_id": "W12.C",
        "status": "pass",
        "summary": {
            "aggregate_expert_useful_design_ceiling": 0.9,
            "aggregate_critic_ensemble_diversity_jaccard": 0.42,
        },
        "domain_authority_useful_design_matrix": {
            "housing": {
                "governed": {
                    "case_count": 1,
                    "expert_useful_design_ceiling_count": 1,
                    "expert_useful_design_ceiling": 1.0,
                }
            }
        },
        "warnings": [],
        "typed_domain_coverage_blockers": [],
    }


def _w12d_report(*, runtime_rate: float, alignment_rate: float) -> dict[str, object]:
    return {
        "phase_id": "W12.D",
        "status": "pass",
        "mode": "corpus_stub",
        "summary": {
            "runtime_useful_design_rate": runtime_rate,
            "expert_useful_design_ceiling": 0.9,
            "useful_design_alignment_rate": alignment_rate,
        },
        "typed_blockers": [],
    }


def _w12e_report(*, status: str) -> dict[str, object]:
    return {
        "phase_id": "W12.E",
        "status": status,
        "typed_blockers": [],
        "summary": {"replay_mismatch_count": 0, "packaging_laundering_issue_count": 0},
    }
