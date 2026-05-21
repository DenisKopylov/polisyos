from __future__ import annotations

# ruff: noqa: S101
import json
from pathlib import Path

from tools.quality.validation import build_policy_design_case_wave36_closeout as build
from tools.quality.validation import check_policy_design_case_wave36_closeout as check

REPO_ROOT = Path(__file__).resolve().parents[3]
SERIOUS_LANE_ID = (
    "profile-research__provider-simulated__data-canonical_production"
    "__scenario-public_golden__ui-api_only"
)
DEV_SMOKE_LANE_ID = (
    "profile-dev__provider-simulated__data-fixture"
    "__scenario-public_golden__ui-api_only"
)


def _matrix_payload(
    *,
    deterministic: bool,
    ci_smoke: bool,
    lane_id: str,
    closeout_required: bool,
    ci_safe: bool,
    scorecard_status: str = "pass",
) -> dict[str, object]:
    return {
        "schema_version": "policyos.canary_matrix_run.v1",
        "selection": {
            "deterministic": deterministic,
            "ci_smoke": ci_smoke,
            "lane_id": None,
            "scenario": None,
            "allow_live_provider": False,
        },
        "summary": {
            "selected_lanes": 1,
            "executed": 1,
            "passed": 1 if scorecard_status == "pass" else 0,
            "failed": 0 if scorecard_status == "pass" else 1,
            "blocked": 0,
            "skipped": 0,
            "lane_statuses": {
                lane_id: "passed" if scorecard_status == "pass" else "failed"
            },
            "bundle_paths": {lane_id: str(Path("/tmp") / lane_id)},
            "scorecard_statuses": {lane_id: scorecard_status},
            "failure_envelope": None
            if scorecard_status == "pass"
            else {"code": "canary_matrix_has_failures"},
        },
        "lanes": [
            {
                "lane_id": lane_id,
                "declared_status": "ready",
                "ci_safe": ci_safe,
                "closeout_required": closeout_required,
                "provider": "simulated",
                "scenario": "public_golden",
                "status": "passed" if scorecard_status == "pass" else "failed",
                "exit_code": 0,
                "bundle_path": str(Path("/tmp") / lane_id),
                "scorecard_status": scorecard_status,
                "failure_envelope": None,
                "command": ["uv", "run", "python", "tools/ops_runners/runtime/run_canary_matrix.py"],
            }
        ],
        "selected_lane_ids": [lane_id],
    }


def test_wave36_closeout_records_serious_matrix_and_excludes_dev_smoke(
    tmp_path: Path,
    monkeypatch,
) -> None:
    wave36_dir = tmp_path / "wave-36"

    def fake_run_matrix_mode(**kwargs):
        mode = kwargs["mode"]
        if mode == "deterministic":
            return _matrix_payload(
                deterministic=True,
                ci_smoke=False,
                lane_id=SERIOUS_LANE_ID,
                closeout_required=True,
                ci_safe=False,
            )
        if mode == "ci_smoke":
            return _matrix_payload(
                deterministic=False,
                ci_smoke=True,
                lane_id=DEV_SMOKE_LANE_ID,
                closeout_required=False,
                ci_safe=True,
            )
        raise AssertionError(mode)

    monkeypatch.setattr(build, "_run_matrix_mode", fake_run_matrix_mode)

    outputs = build.build_wave36_closeout_outputs(
        repo_root=REPO_ROOT,
        wave36_dir=wave36_dir,
    )

    closeout = outputs["closeout"]
    exit_fence = outputs["exit_fence"]

    assert closeout["schema_version"] == build.SCHEMA_VERSION
    assert closeout["status"] == "pass"
    assert closeout["deterministic_matrix"]["serious_lane_ids"] == [SERIOUS_LANE_ID]
    assert closeout["deterministic_matrix"]["all_serious_scorecards_pass"] is True
    assert closeout["deterministic_matrix"]["counts_toward_deterministic_closeout"] is True
    assert closeout["dev_smoke_boundary"]["lane_ids"] == [DEV_SMOKE_LANE_ID]
    assert closeout["dev_smoke_boundary"]["selected_closeout_required_lane_ids"] == []
    assert closeout["dev_smoke_boundary"]["counts_toward_deterministic_closeout"] is False
    assert closeout["dev_smoke_boundary"]["cannot_satisfy_serious_closeout"] is True
    assert exit_fence["status"] == "pass"
    assert exit_fence["deterministic_matrix_passed"] is True
    assert exit_fence["serious_scorecards_all_pass"] is True
    assert exit_fence["dev_smoke_excluded_from_closeout"] is True

    assert (
        check.validate_wave36_closeout(repo_root=REPO_ROOT, wave36_dir=wave36_dir)
        == []
    )


def test_wave36_matrix_mode_cleans_generated_roots_before_running(
    tmp_path: Path,
    monkeypatch,
) -> None:
    wave36_dir = tmp_path / "wave-36"
    stale_evidence = wave36_dir / "canary_evidence" / "deterministic" / "stale.json"
    stale_run = wave36_dir / "canary_runs" / "deterministic" / "control_plane.sqlite3"
    stale_evidence.parent.mkdir(parents=True)
    stale_run.parent.mkdir(parents=True)
    stale_evidence.write_text("stale", encoding="utf-8")
    stale_run.write_text("stale", encoding="utf-8")

    def fake_select_lanes(*_args, **_kwargs):
        return []

    def fake_run_matrix(**kwargs):
        assert not stale_evidence.exists()
        assert not stale_run.exists()
        assert kwargs["output_root"].is_dir()
        assert kwargs["run_root"].is_dir()
        return []

    def fake_build_payload(**_kwargs):
        return _matrix_payload(
            deterministic=True,
            ci_smoke=False,
            lane_id=SERIOUS_LANE_ID,
            closeout_required=True,
            ci_safe=False,
        )

    monkeypatch.setattr(build.run_canary_matrix, "select_lanes", fake_select_lanes)
    monkeypatch.setattr(build.run_canary_matrix, "run_matrix", fake_run_matrix)
    monkeypatch.setattr(build.run_canary_matrix, "_build_payload", fake_build_payload)

    build._run_matrix_mode(
        mode="deterministic",
        repo_root=REPO_ROOT,
        wave36_path=wave36_dir,
        timeout_s=60,
    )


def test_wave36_validator_rejects_dev_smoke_counting_as_closeout(
    tmp_path: Path,
    monkeypatch,
) -> None:
    wave36_dir = tmp_path / "wave-36"

    def fake_run_matrix_mode(**kwargs):
        mode = kwargs["mode"]
        if mode == "deterministic":
            return _matrix_payload(
                deterministic=True,
                ci_smoke=False,
                lane_id=SERIOUS_LANE_ID,
                closeout_required=True,
                ci_safe=False,
            )
        return _matrix_payload(
            deterministic=False,
            ci_smoke=True,
            lane_id=DEV_SMOKE_LANE_ID,
            closeout_required=False,
            ci_safe=True,
        )

    monkeypatch.setattr(build, "_run_matrix_mode", fake_run_matrix_mode)
    build.build_wave36_closeout_outputs(repo_root=REPO_ROOT, wave36_dir=wave36_dir)

    closeout_path = wave36_dir / build.CLOSEOUT_OUTPUT
    closeout = json.loads(closeout_path.read_text(encoding="utf-8"))
    closeout["dev_smoke_boundary"]["counts_toward_deterministic_closeout"] = True
    closeout_path.write_text(json.dumps(closeout, indent=2) + "\n", encoding="utf-8")

    errors = check.validate_wave36_closeout(repo_root=REPO_ROOT, wave36_dir=wave36_dir)

    assert any("dev smoke cannot count toward deterministic closeout" in error for error in errors)


def test_wave36_validator_rejects_nonpassing_serious_scorecard(
    tmp_path: Path,
    monkeypatch,
) -> None:
    wave36_dir = tmp_path / "wave-36"

    def fake_run_matrix_mode(**kwargs):
        mode = kwargs["mode"]
        if mode == "deterministic":
            return _matrix_payload(
                deterministic=True,
                ci_smoke=False,
                lane_id=SERIOUS_LANE_ID,
                closeout_required=True,
                ci_safe=False,
                scorecard_status="warn",
            )
        return _matrix_payload(
            deterministic=False,
            ci_smoke=True,
            lane_id=DEV_SMOKE_LANE_ID,
            closeout_required=False,
            ci_safe=True,
        )

    monkeypatch.setattr(build, "_run_matrix_mode", fake_run_matrix_mode)
    outputs = build.build_wave36_closeout_outputs(
        repo_root=REPO_ROOT,
        wave36_dir=wave36_dir,
    )

    assert outputs["exit_fence"]["status"] == "fail"
    errors = check.validate_wave36_closeout(repo_root=REPO_ROOT, wave36_dir=wave36_dir)
    assert any("serious scorecards must all be pass" in error for error in errors)
