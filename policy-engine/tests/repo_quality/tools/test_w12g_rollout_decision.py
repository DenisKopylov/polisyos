from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import run_policy_design_case_rollout_decision as w12g

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT / "architecture/policy_design_case/wave12g_rollout_decision_manifest.json"
)


def test_w12g_manifest_is_deterministic_and_consumes_w12_evidence_chain() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == w12g.build_w12g_manifest()
    assert manifest["schema_version"] == w12g.MANIFEST_SCHEMA_VERSION
    assert manifest["phase_id"] == "W12.G"
    assert manifest["consumes_phase_reports"] == [
        "W12.A",
        "W12.B",
        "W12.C",
        "W12.D",
        "W12.E",
        "W12.F",
    ]
    assert manifest["metric_policy"]["rollout_decision_cites_three_metrics"] is True
    assert "POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED" in {
        item["flag"] for item in manifest["rollback_and_kill_switches"]
    }


def test_w12g_promotes_governed_pilot_when_all_phase_evidence_passes() -> None:
    report = w12g.build_w12g_rollout_decision_report(
        w12a_report=_phase_report("W12.A", status="pass"),
        w12b_report=_w12b_report(rate=82.0),
        w12c_report=_w12c_report(status="pass"),
        w12d_report=_w12d_report(runtime_rate=0.75, alignment_rate=0.75),
        w12e_report=_phase_report("W12.E", status="pass"),
        w12f_report=_w12f_report(status="pass"),
        repo_root=REPO_ROOT,
        requested_posture="governed-pilot",
    )

    assert report["schema_version"] == w12g.SCHEMA_VERSION
    assert report["status"] == "pass"
    assert report["decision"] == "promote_governed_pilot"
    assert report["requested_posture_allowed"] is True
    assert report["typed_blockers"] == []
    assert report["rollout_blockers"] == []
    assert report["held_domain_slices"]
    assert report["environment_blockers"] == []
    assert report["metric_citations"]["runtime_useful_design_rate"]["value"] == 0.75
    assert report["metric_citations"]["compilation_truthfulness_rate"]["value"] == 82.0
    assert report["metric_citations"]["closeout_honesty_rate"]["source_phase"] == "W12.A"


def test_w12g_holds_rollout_when_cloud_lane_is_blocked() -> None:
    report = w12g.build_w12g_rollout_decision_report(
        w12a_report=_phase_report("W12.A", status="pass"),
        w12b_report=_w12b_report(rate=82.0),
        w12c_report=_w12c_report(status="pass"),
        w12d_report=_w12d_report(runtime_rate=0.75, alignment_rate=0.75),
        w12e_report=_phase_report("W12.E", status="pass"),
        w12f_report=_w12f_report(status="blocked"),
        repo_root=REPO_ROOT,
        requested_posture="governed-pilot",
    )

    assert report["status"] == "blocked"
    assert report["decision"] == "hold_for_remediation"
    assert report["requested_posture_allowed"] is False
    blocker_codes = {blocker["code"] for blocker in report["typed_blockers"]}
    assert "w12g_environment_blocker" in blocker_codes
    assert report["environment_blockers"]
    assert report["remediation_backlog"][0]["owner"]
    assert report["release_note"]["rollout_posture"] == "hold_for_remediation"


def test_w12g_classifies_w12a_environment_blocker_without_honesty_failure() -> None:
    report = w12g.build_w12g_rollout_decision_report(
        w12a_report={
            "phase_id": "W12.A",
            "status": "blocked",
            "typed_blockers": [
                {
                    "code": "local_validation_environment_blocker",
                    "owner": "team-platform-runtime",
                    "environment_blocker_code": "postgres_dsn_missing",
                    "counts_as_closeout_honesty": False,
                }
            ],
        },
        w12b_report=_w12b_report(rate=82.0),
        w12c_report=_w12c_report(status="pass"),
        w12d_report=_w12d_report(runtime_rate=0.75, alignment_rate=0.75),
        w12e_report=_phase_report("W12.E", status="pass"),
        w12f_report=_w12f_report(status="pass"),
        repo_root=REPO_ROOT,
        requested_posture="governed-pilot",
    )

    assert report["status"] == "blocked"
    blocker = report["typed_blockers"][0]
    assert blocker["code"] == "w12g_environment_blocker"
    assert blocker["upstream_phase"] == "W12.A"
    assert blocker["environment_blocker_code"] == "postgres_dsn_missing"
    assert blocker["counts_as_closeout_honesty_failure"] is False


def test_w12g_uses_w12d_rollout_blockers_not_expected_negative_control_audit_blockers() -> None:
    w12d_report = _w12d_report(runtime_rate=0.75, alignment_rate=0.75)
    w12d_report.update(
        {
            "status": "blocked",
            "summary": {
                **w12d_report["summary"],  # type: ignore[arg-type]
                "expected_negative_control_count": 1,
                "rollout_blocker_count": 0,
            },
            "typed_blockers": [
                {
                    "code": "w12d_expert_adjudication_blocks_runtime_outcome",
                    "case_id": "berlin-rent-cap-false-pass",
                    "expected_negative_control": True,
                    "blocks_rollout_posture": False,
                }
            ],
            "rollout_blockers": [],
        }
    )

    report = w12g.build_w12g_rollout_decision_report(
        w12a_report=_phase_report("W12.A", status="pass"),
        w12b_report=_w12b_report(rate=82.0),
        w12c_report=_w12c_report(status="pass"),
        w12d_report=w12d_report,
        w12e_report=_phase_report("W12.E", status="pass"),
        w12f_report=_w12f_report(status="pass"),
        repo_root=REPO_ROOT,
        requested_posture="governed-pilot",
    )

    assert report["status"] == "pass"
    assert not any(
        blocker.get("upstream_phase") == "W12.D" for blocker in report["typed_blockers"]
    )


def test_w12g_corpus_stub_mode_never_promotes_production_capable() -> None:
    report = w12g.build_w12g_rollout_decision_report(
        w12a_report=_phase_report("W12.A", status="pass"),
        w12b_report=_w12b_report(rate=90.0),
        w12c_report=_w12c_report(status="pass"),
        w12d_report=_w12d_report(
            runtime_rate=0.9,
            alignment_rate=0.9,
            mode="corpus_stub",
        ),
        w12e_report=_phase_report("W12.E", status="pass"),
        w12f_report=_w12f_report(status="pass"),
        repo_root=REPO_ROOT,
        requested_posture="production-capable",
    )

    assert report["status"] == "blocked"
    assert report["decision"] == "hold_for_remediation"
    assert "w12g_corpus_stub_cannot_satisfy_production_rollout" in {
        blocker["code"] for blocker in report["typed_blockers"]
    }
    assert "production_closeout_authority" in report["authority_boundary"]["may_not_use_for"]


def test_w12g_uses_real_producer_for_runtime_rate_and_labels_stub_probe() -> None:
    report = w12g.build_w12g_rollout_decision_report(
        w12a_report=_phase_report("W12.A", status="pass"),
        w12b_report=_w12b_report(rate=82.0),
        w12c_report=_w12c_report(status="pass"),
        w12d_report=_w12d_report(
            runtime_rate=0.9231,
            alignment_rate=0.9231,
            mode="corpus_stub",
        ),
        w12d_real_report=_w12d_report(
            runtime_rate=0.0,
            alignment_rate=0.0,
            mode="real_producer",
        ),
        w12d_stub_report=_w12d_report(
            runtime_rate=0.9231,
            alignment_rate=0.9231,
            mode="corpus_stub",
        ),
        w12e_report=_phase_report("W12.E", status="pass"),
        w12f_report=_w12f_report(status="pass"),
        repo_root=REPO_ROOT,
        requested_posture="governed-pilot",
    )

    assert report["status"] == "blocked"
    assert report["decision"] == "hold_for_remediation"
    assert report["metric_citations"]["runtime_useful_design_rate"]["value"] == 0.0
    assert report["metric_citations"]["runtime_useful_design_rate"]["mode"] == (
        "real_producer"
    )
    assert report["metric_citations"]["corpus_stub_useful_design_probe_rate"][
        "value"
    ] == 0.9231
    assert report["metric_citations"]["stub_alignment_probe_rate"]["value"] == 0.9231
    assert "w12g_runtime_useful_design_floor_not_met" in {
        blocker["code"] for blocker in report["typed_blockers"]
    }


def test_w12g_governed_pilot_blocks_when_only_stub_runtime_metric_exists() -> None:
    report = w12g.build_w12g_rollout_decision_report(
        w12a_report=_phase_report("W12.A", status="pass"),
        w12b_report=_w12b_report(rate=82.0),
        w12c_report=_w12c_report(status="pass"),
        w12d_report=_w12d_report(
            runtime_rate=0.9231,
            alignment_rate=0.9231,
            mode="corpus_stub",
        ),
        w12e_report=_phase_report("W12.E", status="pass"),
        w12f_report=_w12f_report(status="pass"),
        repo_root=REPO_ROOT,
        requested_posture="governed-pilot",
    )

    assert report["status"] == "blocked"
    assert report["metric_citations"]["runtime_useful_design_rate"]["value"] is None
    assert report["metric_citations"]["corpus_stub_useful_design_probe_rate"][
        "value"
    ] == 0.9231
    assert "w12g_runtime_useful_design_floor_not_met" in {
        blocker["code"] for blocker in report["typed_blockers"]
    }


def _phase_report(phase_id: str, *, status: str) -> dict[str, object]:
    return {
        "phase_id": phase_id,
        "status": status,
        "summary": {"closeout_honesty_rate": 1.0},
        "typed_blockers": (
            []
            if status == "pass"
            else [{"code": f"{phase_id.lower()}_blocked", "owner": "team-evaluation"}]
        ),
    }


def _w12b_report(*, rate: float) -> dict[str, object]:
    return {
        "phase_id": "W12.B",
        "status": "pass",
        "summary": {"aggregate_compilation_truthfulness_rate": rate},
        "typed_compilation_blockers": [],
    }


def _w12c_report(*, status: str) -> dict[str, object]:
    return {
        "phase_id": "W12.C",
        "status": status,
        "summary": {
            "aggregate_expert_useful_design_ceiling": 0.92,
            "aggregate_critic_ensemble_diversity_jaccard": 0.42,
        },
        "domain_authority_useful_design_matrix": {
            "housing": {"governed": {"expert_useful_design_ceiling": 1.0}}
        },
        "held_domain_slices": [
            {
                "slice_ref": "housing:governed",
                "classification": "negative_control_only",
                "blocks_governed_pilot": False,
                "blocks_production_capable": True,
            }
        ],
        "warnings": [],
        "typed_domain_coverage_blockers": [],
    }


def _w12d_report(
    *,
    runtime_rate: float,
    alignment_rate: float,
    mode: str = "real_producer",
) -> dict[str, object]:
    return {
        "phase_id": "W12.D",
        "status": "pass",
        "mode": mode,
        "summary": {
            "closeout_honesty_rate": 1.0,
            "runtime_useful_design_rate": runtime_rate,
            "expert_useful_design_ceiling": 0.92,
            "useful_design_alignment_rate": alignment_rate,
            "rollout_blocker_count": 0,
        },
        "typed_blockers": [],
        "rollout_blockers": [],
    }


def _w12f_report(*, status: str) -> dict[str, object]:
    return {
        "phase_id": "W12.F",
        "status": status,
        "typed_blockers": (
            []
            if status == "pass"
            else [{"code": "w12f_cloud_lane_evidence_missing", "owner": "team-runtime-platform"}]
        ),
        "frozen_revision_config": {
            "git_revision": "abc123",
            "feature_flags": {"POLISYOS_SCIENTIST_V2_ENABLED": "1"},
        },
    }
