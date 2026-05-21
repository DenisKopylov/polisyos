#!/usr/bin/env python3
"""Validate Policy Design Case Wave 36 deterministic canary closeout artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots
from tools.ops_runners.runtime import run_canary_matrix
from tools.quality.validation import build_policy_design_case_wave36_closeout as build

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)


def validate_wave36_closeout(
    *,
    repo_root: Path = REPO_ROOT,
    wave36_dir: Path = build.WAVE36_DIR,
) -> list[str]:
    repo_root = repo_root.resolve()
    wave36_path = _resolve(repo_root, wave36_dir)
    errors: list[str] = []

    closeout = _load_json(wave36_path / build.CLOSEOUT_OUTPUT, errors)
    exit_fence = _load_json(wave36_path / build.EXIT_FENCE_OUTPUT, errors)
    deterministic_payload = _load_json(
        wave36_path / build.DETERMINISTIC_MATRIX_OUTPUT,
        errors,
    )
    dev_smoke_payload = _load_json(
        wave36_path / build.DEV_SMOKE_MATRIX_OUTPUT,
        errors,
    )
    if errors:
        return errors

    _validate_common(closeout, label="closeout", errors=errors)
    _validate_common(exit_fence, label="exit_fence", errors=errors)
    _validate_entry_criteria(closeout, errors)
    deterministic = _mapping(closeout.get("deterministic_matrix"))
    dev_smoke = _mapping(closeout.get("dev_smoke_boundary"))
    _validate_deterministic_matrix_summary(
        deterministic,
        deterministic_payload,
        errors,
    )
    _validate_dev_smoke_boundary(dev_smoke, dev_smoke_payload, errors)
    _validate_exit_fence(
        closeout=closeout,
        exit_fence=exit_fence,
        deterministic=deterministic,
        dev_smoke=dev_smoke,
        errors=errors,
    )
    return errors


def _validate_common(
    payload: Mapping[str, Any],
    *,
    label: str,
    errors: list[str],
) -> None:
    if payload.get("schema_version") != build.SCHEMA_VERSION:
        errors.append(f"{label}: schema_version drifted")
    if payload.get("wave") != "36":
        errors.append(f"{label}: wave must be 36")
    if payload.get("phase") != "36.1":
        errors.append(f"{label}: phase must be 36.1")
    if not payload.get("tool"):
        errors.append(f"{label}: missing tool")
    if not payload.get("generated_at"):
        errors.append(f"{label}: missing generated_at")


def _validate_entry_criteria(
    closeout: Mapping[str, Any],
    errors: list[str],
) -> None:
    rows = _mapping_rows(closeout, "entry_criteria")
    expected_ids = {
        "pass2_disposition_passing",
        "pass2_disposition_closeout_ready",
        "wave35f_integrity",
        "wave35g_backfill",
        "pass2_disposition_zero_unresolved_must_fix",
        "wave35f_exit_fence_allows_wave36",
        "wave35g_exit_fence_allows_wave36",
        "wave35a_through_wave35e_exit_fences_complete",
    }
    observed = {str(row.get("id")) for row in rows}
    missing = expected_ids - observed
    if missing:
        errors.append(f"entry_criteria: missing Wave 36 entry checks: {sorted(missing)}")
    for row in rows:
        check_id = str(row.get("id") or "<unknown>")
        if row.get("status") != "pass":
            errors.append(f"{check_id}: entry criterion must pass")
        if row.get("errors"):
            errors.append(f"{check_id}: entry criterion has errors")


def _validate_deterministic_matrix_summary(
    deterministic: Mapping[str, Any],
    payload: Mapping[str, Any],
    errors: list[str],
) -> None:
    if payload.get("schema_version") != run_canary_matrix.SCHEMA_VERSION:
        errors.append("deterministic matrix: schema_version drifted")
    selection = _mapping(payload.get("selection"))
    summary = _mapping(payload.get("summary"))
    lanes = _mapping_rows(payload, "lanes")
    if selection.get("deterministic") is not True or selection.get("ci_smoke") is not False:
        errors.append("deterministic matrix must be selected with --deterministic only")
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
    if not serious_lane_ids:
        errors.append("deterministic matrix must select at least one serious closeout lane")
    if non_closeout_lane_ids:
        errors.append(
            f"deterministic matrix selected non-closeout lanes: {non_closeout_lane_ids}"
        )
    if ci_safe_lane_ids:
        errors.append(f"deterministic matrix selected dev smoke lanes: {ci_safe_lane_ids}")
    if summary.get("failure_envelope") is not None:
        errors.append("deterministic matrix summary must not contain a failure envelope")
    if summary.get("selected_lanes") != len(lanes):
        errors.append("deterministic matrix selected_lanes count drifted")
    if summary.get("executed") != len(lanes):
        errors.append("deterministic matrix must execute every selected serious lane")
    if summary.get("passed") != len(lanes) or any(
        summary.get(key) != 0 for key in ("failed", "blocked", "skipped")
    ):
        errors.append("deterministic matrix must pass every selected serious lane")
    scorecard_statuses = _scorecard_statuses(payload)
    if not serious_lane_ids or any(
        scorecard_statuses.get(lane_id) != "pass" for lane_id in serious_lane_ids
    ):
        errors.append("serious scorecards must all be pass")
    if deterministic.get("status") != "pass":
        errors.append("deterministic_matrix: status must be pass")
    if deterministic.get("counts_toward_deterministic_closeout") is not True:
        errors.append("deterministic_matrix: must count toward deterministic closeout")
    if list(deterministic.get("serious_lane_ids") or []) != serious_lane_ids:
        errors.append("deterministic_matrix: serious_lane_ids drifted from matrix payload")
    if _mapping(deterministic.get("scorecard_statuses")) != scorecard_statuses:
        errors.append("deterministic_matrix: scorecard_statuses drifted from matrix payload")


def _validate_dev_smoke_boundary(
    dev_smoke: Mapping[str, Any],
    payload: Mapping[str, Any],
    errors: list[str],
) -> None:
    if payload.get("schema_version") != run_canary_matrix.SCHEMA_VERSION:
        errors.append("dev smoke matrix: schema_version drifted")
    selection = _mapping(payload.get("selection"))
    lanes = _mapping_rows(payload, "lanes")
    if selection.get("ci_smoke") is not True or selection.get("deterministic") is not False:
        errors.append("dev smoke must be selected through explicit --ci-smoke")
    lane_ids = [str(lane.get("lane_id")) for lane in lanes if lane.get("lane_id")]
    closeout_lane_ids = [
        str(lane.get("lane_id"))
        for lane in lanes
        if lane.get("closeout_required") is True and lane.get("lane_id")
    ]
    ci_safe_lane_ids = [
        str(lane.get("lane_id"))
        for lane in lanes
        if lane.get("ci_safe") is True and lane.get("lane_id")
    ]
    if closeout_lane_ids:
        errors.append(f"dev smoke selected closeout-required lanes: {closeout_lane_ids}")
    if set(ci_safe_lane_ids) != set(lane_ids):
        errors.append("dev smoke must contain only CI-safe lanes")
    if dev_smoke.get("counts_toward_deterministic_closeout") is not False:
        errors.append("dev smoke cannot count toward deterministic closeout")
    if dev_smoke.get("cannot_satisfy_serious_closeout") is not True:
        errors.append("dev smoke must be marked unable to satisfy serious closeout")
    if dev_smoke.get("selected_closeout_required_lane_ids") not in ([], ()):
        errors.append("dev smoke boundary must list no closeout-required lanes")
    if list(dev_smoke.get("lane_ids") or []) != lane_ids:
        errors.append("dev_smoke_boundary: lane_ids drifted from matrix payload")
    if dev_smoke.get("status") != "pass":
        errors.append("dev_smoke_boundary: status must be pass")


def _validate_exit_fence(
    *,
    closeout: Mapping[str, Any],
    exit_fence: Mapping[str, Any],
    deterministic: Mapping[str, Any],
    dev_smoke: Mapping[str, Any],
    errors: list[str],
) -> None:
    expected_pass = (
        all(row.get("status") == "pass" for row in _mapping_rows(closeout, "entry_criteria"))
        and deterministic.get("status") == "pass"
        and deterministic.get("all_serious_scorecards_pass") is True
        and dev_smoke.get("status") == "pass"
        and dev_smoke.get("counts_toward_deterministic_closeout") is False
        and dev_smoke.get("cannot_satisfy_serious_closeout") is True
        and not dev_smoke.get("selected_closeout_required_lane_ids")
    )
    expected_status = "pass" if expected_pass else "fail"
    if closeout.get("status") != expected_status:
        errors.append("closeout: status does not match Wave 36 exit fence inputs")
    if exit_fence.get("status") != expected_status:
        errors.append("exit_fence: status does not match Wave 36 exit fence inputs")
    if exit_fence.get("deterministic_matrix_passed") is not (
        deterministic.get("status") == "pass"
    ):
        errors.append("exit_fence: deterministic_matrix_passed drifted")
    if exit_fence.get("serious_scorecards_all_pass") is not (
        deterministic.get("all_serious_scorecards_pass") is True
    ):
        errors.append("exit_fence: serious_scorecards_all_pass drifted")
    if exit_fence.get("dev_smoke_excluded_from_closeout") is not (
        dev_smoke.get("status") == "pass"
        and dev_smoke.get("counts_toward_deterministic_closeout") is False
        and dev_smoke.get("cannot_satisfy_serious_closeout") is True
        and not dev_smoke.get("selected_closeout_required_lane_ids")
    ):
        errors.append("exit_fence: dev_smoke_excluded_from_closeout drifted")
    if expected_pass and exit_fence.get("wave37_release_decision") != "allowed":
        errors.append("exit_fence: Wave 37 release decision must be allowed when pass")
    if not expected_pass and exit_fence.get("wave37_release_decision") != "blocked":
        errors.append("exit_fence: Wave 37 release decision must be blocked when fail")


def _scorecard_statuses(payload: Mapping[str, Any]) -> dict[str, str]:
    statuses = {
        str(key): str(value)
        for key, value in _mapping(_mapping(payload.get("summary")).get("scorecard_statuses")).items()
    }
    for lane in _mapping_rows(payload, "lanes"):
        if lane.get("lane_id") and lane.get("scorecard_status"):
            statuses[str(lane["lane_id"])] = str(lane["scorecard_status"])
    return statuses


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing artifact: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path}: JSON artifact must contain an object")
        return {}
    return payload


def _mapping_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    return [row for row in _as_list(payload.get(key)) if isinstance(row, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve(strict=False)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave36-dir", type=Path, default=build.WAVE36_DIR)
    args = parser.parse_args(argv)

    try:
        errors = validate_wave36_closeout(
            repo_root=args.repo_root,
            wave36_dir=args.wave36_dir,
        )
    except (OSError, ValueError) as exc:
        errors = [str(exc)]

    if errors:
        for error in errors:
            sys.stderr.write(f"wave36-closeout: {error}\n")
        sys.stderr.write(f"wave36-closeout: failed with {len(errors)} issue(s)\n")
        return 1
    sys.stdout.write("wave36-closeout: pass\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
