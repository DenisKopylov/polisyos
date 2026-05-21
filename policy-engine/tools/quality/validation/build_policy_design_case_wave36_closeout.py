#!/usr/bin/env python3
"""Build Policy Design Case Wave 36 deterministic canary closeout artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.ops_runners.runtime import canary_matrix, run_canary_matrix
from tools.quality.validation import check_policy_design_case_pass2_disposition
from tools.quality.validation import check_policy_design_case_wave35f_integrity
from tools.quality.validation import check_policy_design_case_wave35g_backfill

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.wave36.deterministic_canary_closeout.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-wave36-closeout"

WAVE35_DIR = Path("_build/policy-design-case/rebaseline/wave-35")
WAVE35F_DIR = Path("_build/policy-design-case/rebaseline/wave-35F")
WAVE35G_DIR = Path("_build/policy-design-case/rebaseline/wave-35G")
WAVE36_DIR = Path("_build/policy-design-case/rebaseline/wave-36")

DETERMINISTIC_MATRIX_OUTPUT = "deterministic_canary_matrix.json"
DEV_SMOKE_MATRIX_OUTPUT = "dev_smoke_canary_matrix.json"
CLOSEOUT_OUTPUT = "wave36_deterministic_canary_matrix_closeout.json"
EXIT_FENCE_OUTPUT = "wave36_exit_fence.json"

PASS2_REQUIRED_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_pass2_disposition.py --repo-root . --require-passing"
)
PASS2_CLOSEOUT_READY_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_pass2_disposition.py "
    "--repo-root . --require-passing --require-closeout-ready"
)
WAVE35F_CHECK_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_wave35f_integrity.py --repo-root ."
)
WAVE35G_CHECK_COMMAND = (
    "uv run python tools/quality/validation/"
    "check_policy_design_case_wave35g_backfill.py --repo-root ."
)


def build_wave36_closeout_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35_dir: Path = WAVE35_DIR,
    wave35f_dir: Path = WAVE35F_DIR,
    wave35g_dir: Path = WAVE35G_DIR,
    wave36_dir: Path = WAVE36_DIR,
    timeout_s: int = 1200,
    run_dev_smoke: bool = True,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave35_path = _resolve(repo_root, wave35_dir)
    wave35f_path = _resolve(repo_root, wave35f_dir)
    wave35g_path = _resolve(repo_root, wave35g_dir)
    wave36_path = _resolve(repo_root, wave36_dir)
    wave36_path.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now()
    entry_criteria = _build_entry_criteria(
        repo_root=repo_root,
        wave35_path=wave35_path,
        wave35f_path=wave35f_path,
        wave35g_path=wave35g_path,
        generated_at=generated_at,
    )
    deterministic_payload = _run_matrix_mode(
        mode="deterministic",
        repo_root=repo_root,
        wave36_path=wave36_path,
        timeout_s=timeout_s,
    )
    if run_dev_smoke:
        dev_smoke_payload = _run_matrix_mode(
            mode="ci_smoke",
            repo_root=repo_root,
            wave36_path=wave36_path,
            timeout_s=timeout_s,
        )
    else:
        dev_smoke_payload = _selection_only_dev_smoke_payload()
    atomic_write_json(wave36_path / DETERMINISTIC_MATRIX_OUTPUT, deterministic_payload)
    atomic_write_json(wave36_path / DEV_SMOKE_MATRIX_OUTPUT, dev_smoke_payload)

    deterministic = _deterministic_matrix_closeout(
        deterministic_payload,
        wave36_path=wave36_path,
        repo_root=repo_root,
    )
    dev_smoke_boundary = _dev_smoke_boundary(
        dev_smoke_payload,
        wave36_path=wave36_path,
        repo_root=repo_root,
        run_dev_smoke=run_dev_smoke,
    )
    exit_fence = _build_exit_fence(
        entry_criteria=entry_criteria,
        deterministic=deterministic,
        dev_smoke_boundary=dev_smoke_boundary,
        generated_at=generated_at,
    )
    closeout = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "36",
        "phase": "36.1",
        "status": exit_fence["status"],
        "repo_root": str(repo_root),
        "purpose": "prove deterministic serious lanes after Pass 2 diagnostics",
        "entry_criteria": entry_criteria,
        "deterministic_matrix": deterministic,
        "dev_smoke_boundary": dev_smoke_boundary,
        "exit_fence_ref": _rel_path(wave36_path / EXIT_FENCE_OUTPUT, repo_root),
        "verification": {
            "acceptance_commands": [
                (
                    "uv run pytest "
                    "tests/repo_quality/tools/test_policy_design_case_wave36.py -q"
                ),
                (
                    "uv run python tools/quality/validation/"
                    "check_policy_design_case_wave36_closeout.py --repo-root ."
                ),
            ]
        },
    }
    closeout_path = wave36_path / CLOSEOUT_OUTPUT
    exit_fence["closeout_artifact_ref"] = _rel_path(closeout_path, repo_root)
    atomic_write_json(closeout_path, closeout)
    atomic_write_json(wave36_path / EXIT_FENCE_OUTPUT, exit_fence)
    return {
        "closeout": closeout,
        "exit_fence": exit_fence,
        "deterministic_matrix": deterministic_payload,
        "dev_smoke_matrix": dev_smoke_payload,
    }


def _run_matrix_mode(
    *,
    mode: str,
    repo_root: Path,
    wave36_path: Path,
    timeout_s: int,
) -> dict[str, Any]:
    if mode not in {"deterministic", "ci_smoke"}:
        raise ValueError(f"unknown Wave 36 matrix mode: {mode}")
    deterministic = mode == "deterministic"
    ci_smoke = mode == "ci_smoke"
    output_name = DETERMINISTIC_MATRIX_OUTPUT if deterministic else DEV_SMOKE_MATRIX_OUTPUT
    output_path = wave36_path / output_name
    evidence_root = wave36_path / "canary_evidence" / mode
    run_root = wave36_path / "canary_runs" / mode
    _prepare_matrix_roots(evidence_root, run_root)
    selected_lanes = run_canary_matrix.select_lanes(
        canary_matrix.build_canary_lanes(),
        deterministic=deterministic,
        ci_smoke=ci_smoke,
        include_live_provider=False,
    )
    results = run_canary_matrix.run_matrix(
        lanes=selected_lanes,
        output_root=evidence_root,
        run_root=run_root,
        allow_live_provider=False,
        cwd=repo_root,
        timeout_s=max(1, timeout_s),
        allow_warn_scorecard=ci_smoke,
    )
    payload = run_canary_matrix._build_payload(  # noqa: SLF001 - repo-local runner payload.
        selected_lanes=selected_lanes,
        results=results,
        args=SimpleNamespace(
            deterministic=deterministic,
            ci_smoke=ci_smoke,
            lane_id="",
            scenario="",
            allow_live_provider=False,
        ),
    )
    atomic_write_json(output_path, payload)
    return payload


def _prepare_matrix_roots(*paths: Path) -> None:
    for path in paths:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def _selection_only_dev_smoke_payload() -> dict[str, Any]:
    selected_lanes = run_canary_matrix.select_lanes(
        canary_matrix.build_canary_lanes(),
        ci_smoke=True,
    )
    lane_ids = [str(lane["lane_id"]) for lane in selected_lanes]
    return {
        "schema_version": run_canary_matrix.SCHEMA_VERSION,
        "created_at": _utc_now(),
        "selection": {
            "deterministic": False,
            "ci_smoke": True,
            "lane_id": None,
            "scenario": None,
            "allow_live_provider": False,
        },
        "summary": {
            "selected_lanes": len(selected_lanes),
            "executed": 0,
            "passed": 0,
            "failed": 0,
            "blocked": 0,
            "skipped": 0,
            "lane_statuses": {},
            "bundle_paths": {},
            "scorecard_statuses": {},
            "failure_envelope": None,
        },
        "lanes": [
            {
                "lane_id": str(lane["lane_id"]),
                "declared_status": lane.get("status"),
                "ci_safe": lane.get("ci_safe") is True,
                "closeout_required": lane.get("closeout_required") is True,
                "provider": lane.get("provider"),
                "scenario": lane.get("scenario"),
                "status": "not_run",
                "exit_code": None,
                "bundle_path": None,
                "scorecard_status": "not_run",
                "failure_envelope": None,
                "command": None,
            }
            for lane in selected_lanes
        ],
        "selected_lane_ids": lane_ids,
    }


def _build_entry_criteria(
    *,
    repo_root: Path,
    wave35_path: Path,
    wave35f_path: Path,
    wave35g_path: Path,
    generated_at: str,
) -> list[dict[str, Any]]:
    checks = [
        _validator_entry(
            check_id="pass2_disposition_passing",
            command=PASS2_REQUIRED_COMMAND,
            errors=check_policy_design_case_pass2_disposition.validate_pass2_disposition(
                repo_root=repo_root,
                require_passing=True,
            ),
        ),
        _validator_entry(
            check_id="pass2_disposition_closeout_ready",
            command=PASS2_CLOSEOUT_READY_COMMAND,
            errors=check_policy_design_case_pass2_disposition.validate_pass2_disposition(
                repo_root=repo_root,
                require_passing=True,
                require_closeout_ready=True,
            ),
        ),
        _validator_entry(
            check_id="wave35f_integrity",
            command=WAVE35F_CHECK_COMMAND,
            errors=check_policy_design_case_wave35f_integrity.validate_wave35f_integrity(
                repo_root=repo_root,
            ),
        ),
        _validator_entry(
            check_id="wave35g_backfill",
            command=WAVE35G_CHECK_COMMAND,
            errors=check_policy_design_case_wave35g_backfill.validate_wave35g_backfill(
                repo_root=repo_root,
            ),
        ),
        _disposition_entry(wave35_path / "pass2_disposition.json"),
        _wave35f_entry(wave35f_path / "wave35f_exit_fence.json"),
        _wave35g_entry(wave35g_path / "wave35g_exit_fence.json"),
        _wave35_remediation_fences_entry(repo_root),
    ]
    for check in checks:
        check["checked_at"] = generated_at
    return checks


def _validator_entry(
    *,
    check_id: str,
    command: str,
    errors: list[str],
) -> dict[str, Any]:
    return {
        "id": check_id,
        "kind": "validator_command",
        "command": command,
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def _disposition_entry(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    summary = _mapping(payload.get("summary"))
    errors: list[str] = []
    if summary.get("must_fix_unresolved_count") != 0:
        errors.append("pass2 disposition has unresolved must_fix_before_closeout findings")
    if summary.get("accepted_blocker_count") not in {0, None}:
        errors.append("accepted blockers cannot count toward Wave 36 closeout evidence")
    if summary.get("next_plan_remediation_count") not in {0, None}:
        errors.append("next_plan_remediation rows cannot count toward Wave 36 closeout evidence")
    return {
        "id": "pass2_disposition_zero_unresolved_must_fix",
        "kind": "artifact_field",
        "artifact_path": str(path),
        "status": "pass" if not errors else "fail",
        "summary": {
            "must_fix_unresolved_count": summary.get("must_fix_unresolved_count"),
            "accepted_blocker_count": summary.get("accepted_blocker_count"),
            "next_plan_remediation_count": summary.get("next_plan_remediation_count"),
        },
        "errors": errors,
    }


def _wave35f_entry(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    errors: list[str] = []
    if payload.get("status") != "pass":
        errors.append("Wave 35F exit fence status must be pass")
    if payload.get("wave36_release_decision") != "allowed":
        errors.append("Wave 35F must allow Wave 36 release")
    return {
        "id": "wave35f_exit_fence_allows_wave36",
        "kind": "artifact_field",
        "artifact_path": str(path),
        "status": "pass" if not errors else "fail",
        "observed": {
            "status": payload.get("status"),
            "wave36_release_decision": payload.get("wave36_release_decision"),
            "blocking_finding_ids": payload.get("blocking_finding_ids"),
        },
        "errors": errors,
    }


def _wave35g_entry(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    errors: list[str] = []
    if payload.get("status") != "pass":
        errors.append("Wave 35G exit fence status must be pass")
    if payload.get("wave36_release_decision") != "allowed":
        errors.append("Wave 35G must allow Wave 36 release")
    covered = _as_list(payload.get("covered_release_blocker_ids"))
    if len(covered) != 19:
        errors.append("Wave 35G must cover the 19 Wave 35F release blockers")
    return {
        "id": "wave35g_exit_fence_allows_wave36",
        "kind": "artifact_field",
        "artifact_path": str(path),
        "status": "pass" if not errors else "fail",
        "observed": {
            "status": payload.get("status"),
            "wave36_release_decision": payload.get("wave36_release_decision"),
            "covered_release_blocker_ids_count": len(covered),
        },
        "errors": errors,
    }


def _wave35_remediation_fences_entry(repo_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for wave in ("35A", "35B", "35C", "35D", "35E"):
        path = repo_root / f"_build/policy-design-case/rebaseline/wave-{wave}/wave35_disposition_update.json"
        try:
            payload = _load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"Wave {wave}: missing or invalid disposition update: {exc}")
            rows.append({"wave": wave, "artifact_path": str(path), "status": "missing"})
            continue
        exit_fence = _mapping(payload.get("exit_fence"))
        unresolved = _as_list(payload.get("unresolved_cluster_findings"))
        complete = (
            payload.get("status") == "resolved"
            and not unresolved
            and bool(exit_fence)
            and all(_exit_fence_value_complete(key, value) for key, value in exit_fence.items())
        )
        if not complete:
            errors.append(f"Wave {wave}: exit fence is not complete")
        rows.append(
            {
                "wave": wave,
                "artifact_path": str(path),
                "status": "complete" if complete else "incomplete",
                "top_level_status": payload.get("status"),
                "unresolved_cluster_findings": unresolved,
            }
        )
    return {
        "id": "wave35a_through_wave35e_exit_fences_complete",
        "kind": "artifact_set",
        "status": "pass" if not errors else "fail",
        "rows": rows,
        "errors": errors,
    }


def _exit_fence_value_complete(key: str, value: object) -> bool:
    if key.endswith("_exit_code"):
        return value == 0
    if isinstance(value, bool):
        return value is True
    if isinstance(value, int | float):
        return value >= 0
    return bool(value)


def _deterministic_matrix_closeout(
    payload: Mapping[str, Any],
    *,
    wave36_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    selection = _mapping(payload.get("selection"))
    summary = _mapping(payload.get("summary"))
    lanes = _mapping_rows(payload, "lanes")
    lane_ids = [str(lane.get("lane_id")) for lane in lanes if lane.get("lane_id")]
    serious_lane_ids = [
        str(lane.get("lane_id"))
        for lane in lanes
        if lane.get("closeout_required") is True and lane.get("lane_id")
    ]
    non_closeout_lane_ids = [
        str(lane.get("lane_id"))
        for lane in lanes
        if lane.get("closeout_required") is not True and lane.get("lane_id")
    ]
    ci_safe_lane_ids = [
        str(lane.get("lane_id"))
        for lane in lanes
        if lane.get("ci_safe") is True and lane.get("lane_id")
    ]
    scorecard_statuses = _scorecard_statuses(payload)
    all_serious_scorecards_pass = bool(serious_lane_ids) and all(
        scorecard_statuses.get(lane_id) == "pass" for lane_id in serious_lane_ids
    )
    matrix_passed = (
        payload.get("schema_version") == run_canary_matrix.SCHEMA_VERSION
        and selection.get("deterministic") is True
        and selection.get("ci_smoke") is False
        and bool(serious_lane_ids)
        and not non_closeout_lane_ids
        and not ci_safe_lane_ids
        and summary.get("failure_envelope") is None
        and summary.get("selected_lanes") == len(lanes)
        and summary.get("executed") == len(lanes)
        and summary.get("passed") == len(lanes)
        and summary.get("failed") == 0
        and summary.get("blocked") == 0
        and summary.get("skipped") == 0
        and all_serious_scorecards_pass
    )
    errors: list[str] = []
    if selection.get("deterministic") is not True or selection.get("ci_smoke") is not False:
        errors.append("deterministic matrix must be selected with --deterministic only")
    if not serious_lane_ids:
        errors.append("deterministic matrix selected no serious closeout lanes")
    if non_closeout_lane_ids:
        errors.append(f"deterministic matrix selected non-closeout lanes: {non_closeout_lane_ids}")
    if ci_safe_lane_ids:
        errors.append(f"deterministic matrix selected CI/dev smoke lanes: {ci_safe_lane_ids}")
    if not all_serious_scorecards_pass:
        errors.append("serious scorecards must all be pass")
    if summary.get("failure_envelope") is not None:
        errors.append("deterministic matrix summary has a failure envelope")
    return {
        "status": "pass" if matrix_passed else "fail",
        "command": _matrix_command("deterministic", wave36_path, repo_root),
        "result_path": _rel_path(wave36_path / DETERMINISTIC_MATRIX_OUTPUT, repo_root),
        "selection": dict(selection),
        "summary": dict(summary),
        "lane_ids": lane_ids,
        "serious_lane_ids": serious_lane_ids,
        "non_closeout_lane_ids": non_closeout_lane_ids,
        "ci_safe_lane_ids": ci_safe_lane_ids,
        "scorecard_statuses": scorecard_statuses,
        "all_serious_scorecards_pass": all_serious_scorecards_pass,
        "counts_toward_deterministic_closeout": True,
        "errors": errors,
    }


def _dev_smoke_boundary(
    payload: Mapping[str, Any],
    *,
    wave36_path: Path,
    repo_root: Path,
    run_dev_smoke: bool,
) -> dict[str, Any]:
    selection = _mapping(payload.get("selection"))
    summary = _mapping(payload.get("summary"))
    lanes = _mapping_rows(payload, "lanes")
    lane_ids = [str(lane.get("lane_id")) for lane in lanes if lane.get("lane_id")]
    ci_safe_lane_ids = [
        str(lane.get("lane_id"))
        for lane in lanes
        if lane.get("ci_safe") is True and lane.get("lane_id")
    ]
    closeout_lane_ids = [
        str(lane.get("lane_id"))
        for lane in lanes
        if lane.get("closeout_required") is True and lane.get("lane_id")
    ]
    explicit = selection.get("ci_smoke") is True and selection.get("deterministic") is False
    excluded = explicit and not closeout_lane_ids and set(ci_safe_lane_ids) == set(lane_ids)
    errors: list[str] = []
    if not explicit:
        errors.append("dev smoke boundary must be selected through explicit --ci-smoke")
    if closeout_lane_ids:
        errors.append(f"dev smoke selected closeout-required lanes: {closeout_lane_ids}")
    if set(ci_safe_lane_ids) != set(lane_ids):
        errors.append("dev smoke boundary must contain only CI-safe lanes")
    return {
        "status": "pass" if excluded else "fail",
        "command": _matrix_command("ci_smoke", wave36_path, repo_root),
        "result_path": _rel_path(wave36_path / DEV_SMOKE_MATRIX_OUTPUT, repo_root),
        "selection": dict(selection),
        "summary": dict(summary),
        "lane_ids": lane_ids,
        "ci_safe_lane_ids": ci_safe_lane_ids,
        "selected_closeout_required_lane_ids": closeout_lane_ids,
        "executed_for_boundary_observation": run_dev_smoke,
        "counts_toward_deterministic_closeout": False,
        "cannot_satisfy_serious_closeout": True,
        "reason": (
            "Dev smoke is an explicit --ci-smoke lane family. It may accept warning-scoped "
            "scorecards for fast CI feedback, but it is excluded from deterministic "
            "serious closeout authority."
        ),
        "errors": errors,
    }


def _build_exit_fence(
    *,
    entry_criteria: Sequence[Mapping[str, Any]],
    deterministic: Mapping[str, Any],
    dev_smoke_boundary: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    entry_pass = all(check.get("status") == "pass" for check in entry_criteria)
    deterministic_passed = deterministic.get("status") == "pass"
    serious_scorecards_all_pass = deterministic.get("all_serious_scorecards_pass") is True
    dev_smoke_excluded = (
        dev_smoke_boundary.get("status") == "pass"
        and dev_smoke_boundary.get("counts_toward_deterministic_closeout") is False
        and dev_smoke_boundary.get("cannot_satisfy_serious_closeout") is True
        and not dev_smoke_boundary.get("selected_closeout_required_lane_ids")
    )
    status = (
        "pass"
        if entry_pass
        and deterministic_passed
        and serious_scorecards_all_pass
        and dev_smoke_excluded
        else "fail"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "36",
        "phase": "36.1",
        "status": status,
        "entry_criteria_passed": entry_pass,
        "deterministic_matrix_passed": deterministic_passed,
        "serious_scorecards_all_pass": serious_scorecards_all_pass,
        "serious_lane_ids": list(deterministic.get("serious_lane_ids") or []),
        "serious_scorecard_statuses": dict(
            _mapping(deterministic.get("scorecard_statuses"))
        ),
        "dev_smoke_lane_ids": list(dev_smoke_boundary.get("lane_ids") or []),
        "dev_smoke_excluded_from_closeout": dev_smoke_excluded,
        "dev_smoke_counts_toward_closeout": False,
        "wave37_release_decision": "allowed" if status == "pass" else "blocked",
    }


def _scorecard_statuses(payload: Mapping[str, Any]) -> dict[str, str]:
    summary_statuses = _mapping(_mapping(payload.get("summary")).get("scorecard_statuses"))
    statuses = {str(key): str(value) for key, value in summary_statuses.items()}
    for lane in _mapping_rows(payload, "lanes"):
        lane_id = lane.get("lane_id")
        status = lane.get("scorecard_status")
        if lane_id and status:
            statuses[str(lane_id)] = str(status)
    return statuses


def _matrix_command(mode: str, wave36_path: Path, repo_root: Path) -> str:
    deterministic = mode == "deterministic"
    output = DETERMINISTIC_MATRIX_OUTPUT if deterministic else DEV_SMOKE_MATRIX_OUTPUT
    flag = "--deterministic" if deterministic else "--ci-smoke"
    return (
        "uv run python tools/ops_runners/runtime/run_canary_matrix.py "
        f"{flag} "
        f"--output-root {_rel_path(wave36_path / 'canary_evidence' / mode, repo_root)} "
        f"--run-root {_rel_path(wave36_path / 'canary_runs' / mode, repo_root)} "
        f"--json-output {_rel_path(wave36_path / output, repo_root)} "
        "--timeout-s 1200"
    )


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _mapping_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    return [row for row in _as_list(payload.get(key)) if isinstance(row, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve(strict=False)


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35-dir", type=Path, default=WAVE35_DIR)
    parser.add_argument("--wave35f-dir", type=Path, default=WAVE35F_DIR)
    parser.add_argument("--wave35g-dir", type=Path, default=WAVE35G_DIR)
    parser.add_argument("--wave36-dir", type=Path, default=WAVE36_DIR)
    parser.add_argument("--timeout-s", type=int, default=1200)
    parser.add_argument(
        "--skip-dev-smoke-run",
        action="store_true",
        help="Record the explicit dev-smoke selection boundary without executing the lane.",
    )
    args = parser.parse_args(argv)

    try:
        outputs = build_wave36_closeout_outputs(
            repo_root=args.repo_root,
            wave35_dir=args.wave35_dir,
            wave35f_dir=args.wave35f_dir,
            wave35g_dir=args.wave35g_dir,
            wave36_dir=args.wave36_dir,
            timeout_s=args.timeout_s,
            run_dev_smoke=not args.skip_dev_smoke_run,
        )
    except Exception as exc:
        sys.stderr.write(f"wave36-closeout-build: {exc}\n")
        return 1
    exit_fence = outputs["exit_fence"]
    sys.stdout.write(
        "wave36-closeout-build: "
        f"status={exit_fence['status']} "
        f"serious_lanes={len(exit_fence['serious_lane_ids'])} "
        f"dev_smoke_excluded={exit_fence['dev_smoke_excluded_from_closeout']} "
        f"wave37={exit_fence['wave37_release_decision']}\n"
    )
    return 0 if exit_fence["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
