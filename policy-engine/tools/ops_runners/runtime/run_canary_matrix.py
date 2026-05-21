#!/usr/bin/env python3
"""Execute real PolicyOS canary matrix lanes and emit a lane scorecard summary."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.source_truth import (
    detect_source_truth_conflict,
    load_source_truth_lattice,
)
from polisyos.runtime.quality.closeout_compatibility import (
    build_closeout_compatibility_record_from_bundle_dir,
)
from tools.ops_runners.runtime import canary_matrix

SCHEMA_VERSION = "policyos.canary_matrix_run.v1"
LIVE_PROVIDER_ENV = "POLISYOS_LLM_GATEWAY_API_KEY"
LIVE_PROVIDER_VALUES = frozenset({"live_gonka_proxy"})
TERMINAL_FAILURE_STATUSES = frozenset({"blocked", "failed", "skipped"})
EVIDENCE_BUNDLE_RE = re.compile(r"^Evidence bundle:\s*(?P<path>.+?)\s*$", re.MULTILINE)


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _json_default(value: Any) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default)
        + "\n",
        encoding="utf-8",
    )


def _tail(text: str, *, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _safe_lane_dirname(lane_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.=-]+", "_", lane_id)


def _is_live_provider_lane(lane: dict[str, Any]) -> bool:
    return str(lane.get("provider") or "") in LIVE_PROVIDER_VALUES


def live_provider_credentials_present(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    return bool(str(source.get(LIVE_PROVIDER_ENV) or "").strip())


def select_lanes(
    lanes: list[dict[str, Any]],
    *,
    deterministic: bool = False,
    ci_smoke: bool = False,
    lane_id: str = "",
    only_lane: str = "",
    scenario: str = "",
    include_live_provider: bool = False,
) -> list[dict[str, Any]]:
    """Select matrix lanes for one run mode.

    Scenario mode intentionally defaults to the deterministic CI-safe subset,
    which lets CI ask for a single scenario without accidentally selecting live
    or deferred lanes.
    """
    if lane_id:
        selected = [lane for lane in lanes if lane.get("lane_id") == lane_id]
    elif only_lane:
        selected = [lane for lane in lanes if lane.get("lane_id") == only_lane]
    elif ci_smoke:
        selected = [lane for lane in lanes if lane.get("ci_safe") is True]
    elif scenario:
        selected = [
            lane
            for lane in lanes
            if lane.get("scenario") == scenario
            and (
                lane.get("closeout_required") is True
                or (include_live_provider and lane.get("status") == "ready")
            )
        ]
    elif deterministic:
        selected = [
            lane
            for lane in lanes
            if lane.get("status") == "ready"
            and lane.get("closeout_required") is True
            and not _is_live_provider_lane(lane)
        ]
    else:
        selected = []

    if only_lane:
        selected = [lane for lane in selected if lane.get("lane_id") == only_lane]

    if not include_live_provider:
        return [
            lane
            for lane in selected
            if not _is_live_provider_lane(lane) or lane_id or only_lane
        ]
    return selected


def _extract_bundle_path(stdout: str) -> Path | None:
    match = EVIDENCE_BUNDLE_RE.search(stdout)
    if not match:
        return None
    return Path(match.group("path")).expanduser()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else {"payload": payload}


def _scorecard_status(bundle_path: Path | None) -> str:
    if bundle_path is None:
        return "missing"
    scorecard = _load_json(bundle_path / "quality_evidence" / "quality_scorecard.json")
    if isinstance(scorecard, dict) and isinstance(scorecard.get("quality_status"), str):
        return str(scorecard["quality_status"])
    bundle = _load_json(bundle_path / "bundle.json")
    if isinstance(bundle, dict) and isinstance(bundle.get("quality_status"), str):
        return str(bundle["quality_status"])
    return "missing"


def _source_truth_conflicts(bundle_path: Path | None) -> list[dict[str, Any]]:
    if bundle_path is None:
        return []
    bundle = _load_json(bundle_path / "bundle.json")
    scorecard = _load_json(bundle_path / "quality_evidence" / "quality_scorecard.json")
    if not isinstance(bundle, dict) or not isinstance(scorecard, dict):
        return []
    lattice = load_source_truth_lattice()
    scorecard_refs = scorecard.get("evidence_refs")
    if not isinstance(scorecard_refs, dict):
        scorecard_refs = {}
    runtime_scorecard = {
        "quality_scorecard_ref": (
            scorecard.get("quality_scorecard_ref")
            or scorecard.get("scorecard_ref")
            or scorecard_refs.get("quality_scorecard")
        ),
        "quality_status": scorecard.get("quality_status"),
    }
    bundle_scorecard = {
        "quality_scorecard_ref": bundle.get("quality_scorecard_ref"),
        "quality_status": bundle.get("quality_status"),
    }
    conflict = detect_source_truth_conflict(
        field_family="scorecard_identity_and_gates",
        authoritative_source="runtime.scorecard",
        authoritative_surface="runtime.scorecard",
        authoritative_values=runtime_scorecard,
        conflicting_source="runtime.canary_bundle",
        conflicting_surface="runtime.canary_bundle",
        conflicting_values=bundle_scorecard,
        fields=("quality_scorecard_ref", "quality_status"),
        downstream_impact="Canary matrix would accept a packaged scorecard over runtime authority.",
        lattice=lattice,
    )
    return [conflict] if conflict is not None else []


def _closeout_compatibility(bundle_path: Path | None) -> dict[str, Any] | None:
    if bundle_path is None:
        return None
    try:
        return build_closeout_compatibility_record_from_bundle_dir(bundle_path)
    except Exception as exc:  # pragma: no cover - surfaced in lane failure envelope.
        return {
            "schema_version": "policyos.runtime.can_i_closeout_compatibility.v1",
            "status": "fail",
            "issues": [
                {
                    "code": "closeout_compatibility_unreadable",
                    "message": str(exc),
                    "next_action": "Inspect the emitted evidence bundle and rerun check_can_i_closeout.",
                }
            ],
        }


def _bundle_failure(bundle_path: Path | None) -> dict[str, Any] | None:
    if bundle_path is None:
        return None
    return _load_json(bundle_path / "failure.json")


def _missing_required_evidence(bundle_path: Path | None, lane: dict[str, Any]) -> list[str]:
    if bundle_path is None:
        return []
    missing: list[str] = []
    for rel_path in lane.get("required_evidence_files") or []:
        if not isinstance(rel_path, str) or not rel_path.strip():
            continue
        if not (bundle_path / rel_path).exists():
            missing.append(rel_path)
    return missing


def _scorecard_status_acceptable(
    *,
    scorecard_status: str,
    allow_warn_scorecard: bool,
) -> bool:
    if scorecard_status == "pass":
        return True
    return scorecard_status == "warn" and allow_warn_scorecard


def _lane_setup_error(lane: dict[str, Any]) -> dict[str, Any] | None:
    setup_error = lane.get("setup_error")
    if isinstance(setup_error, dict) and setup_error.get("code"):
        failure = dict(setup_error)
        failure.setdefault("lane_id", lane["lane_id"])
        failure.setdefault("message", "Canary lane setup prerequisites are unavailable.")
        return failure
    return None


def _lane_env(lane: dict[str, Any]) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("POLISYOS_RUN_CORO_SYNC_TIMEOUT_SECONDS", "180")
    env.setdefault("POLISYOS_NL_PIPELINE_TIMEOUT_SECONDS", "900")
    env.setdefault("POLISYOS_AGENT_LLM_TIMEOUT_S", "180")
    runner = lane.get("runner")
    runner_env = runner.get("env") if isinstance(runner, dict) else {}
    if not isinstance(runner_env, dict):
        return env
    for key, value in runner_env.items():
        key_text = str(key)
        value_text = str(value)
        if value_text == "<required>":
            inherited = os.environ.get(key_text)
            if inherited:
                env[key_text] = inherited
            else:
                env.pop(key_text, None)
            continue
        env[key_text] = value_text
    return env


def _command_for_lane(
    lane: dict[str, Any],
    *,
    output_root: Path,
    run_root: Path,
) -> list[str]:
    runner = lane.get("runner")
    if not isinstance(runner, dict):
        raise ValueError(f"Lane {lane.get('lane_id')} does not declare a runner")
    module = str(runner.get("module") or "")
    runner_argv = [str(item) for item in runner.get("argv") or []]
    lane_id = str(lane["lane_id"])
    lane_dirname = _safe_lane_dirname(lane_id)

    if module == "tools.ops_runners.runtime.local_production_canary":
        return [
            sys.executable,
            "-m",
            module,
            *runner_argv,
            f"--output-root={output_root / lane_dirname}",
            f"--run-root={run_root / lane_dirname}",
            f"--matrix-lane-id={lane_id}",
        ]

    return [sys.executable, "-m", module, *runner_argv]


def _run_lane_command(
    command: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    timeout_s: int,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603 - trusted repo-local lane contracts.
            command,
            cwd=str(cwd),
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr = (stderr + "\n" if stderr else "") + f"Timed out after {timeout_s}s"
        return subprocess.CompletedProcess(command, 124, stdout=stdout, stderr=stderr)


def _blocked_result(lane: dict[str, Any], *, failure: dict[str, Any]) -> dict[str, Any]:
    return {
        "lane_id": lane["lane_id"],
        "declared_status": lane["status"],
        "ci_safe": lane["ci_safe"],
        "provider": lane["provider"],
        "scenario": lane["scenario"],
        "status": "blocked",
        "exit_code": None,
        "bundle_path": None,
        "scorecard_status": "not_run",
        "failure_envelope": failure,
        "command": None,
    }


def _skipped_result(lane: dict[str, Any], *, reason: str) -> dict[str, Any]:
    return {
        "lane_id": lane["lane_id"],
        "declared_status": lane["status"],
        "ci_safe": lane["ci_safe"],
        "provider": lane["provider"],
        "scenario": lane["scenario"],
        "status": "skipped",
        "exit_code": None,
        "bundle_path": None,
        "scorecard_status": "not_run",
        "failure_envelope": {
            "code": "lane_not_executable",
            "lane_id": lane["lane_id"],
            "message": reason,
            "declared_status": lane["status"],
        },
        "command": None,
    }


def _completed_result(
    lane: dict[str, Any],
    *,
    command: list[str],
    completed: subprocess.CompletedProcess[str],
    allow_warn_scorecard: bool,
) -> dict[str, Any]:
    bundle_path = _extract_bundle_path(completed.stdout or "")
    scorecard_status = _scorecard_status(bundle_path)
    has_bundle_and_scorecard = bundle_path is not None and scorecard_status != "missing"
    scorecard_acceptable = _scorecard_status_acceptable(
        scorecard_status=scorecard_status,
        allow_warn_scorecard=allow_warn_scorecard,
    )
    missing_required_evidence = _missing_required_evidence(bundle_path, lane)
    source_truth_conflicts = _source_truth_conflicts(bundle_path)
    closeout_compatibility = (
        _closeout_compatibility(bundle_path) if lane.get("closeout_required") is True else None
    )
    closeout_compatible = (
        closeout_compatibility is None
        or str(closeout_compatibility.get("status") or "") == "pass"
    )
    passed = (
        completed.returncode == 0
        and has_bundle_and_scorecard
        and scorecard_acceptable
        and not missing_required_evidence
        and not source_truth_conflicts
        and closeout_compatible
    )
    failure_envelope = None
    if not passed:
        code = "canary_lane_failed"
        message = "Canary lane command failed or did not emit a scorecard bundle."
        if completed.returncode == 0 and missing_required_evidence:
            code = "canary_required_evidence_missing"
            message = "Canary lane did not emit all required evidence files."
        if (
            completed.returncode == 0
            and has_bundle_and_scorecard
            and not scorecard_acceptable
        ):
            code = "canary_scorecard_failed"
            message = "Canary lane emitted a non-passing quality scorecard."
        if (
            completed.returncode == 0
            and has_bundle_and_scorecard
            and scorecard_acceptable
            and source_truth_conflicts
        ):
            code = "source_truth_conflict"
            message = "Canary lane bundle conflicted with runtime scorecard authority."
        if (
            completed.returncode == 0
            and has_bundle_and_scorecard
            and scorecard_acceptable
            and not missing_required_evidence
            and not source_truth_conflicts
            and not closeout_compatible
        ):
            code = "can_i_closeout_failed"
            message = "Canary lane failed Can-I-Closeout compatibility."
        failure_envelope = {
            "code": code,
            "lane_id": lane["lane_id"],
            "message": message,
            "exit_code": completed.returncode,
            "bundle_path": str(bundle_path) if bundle_path is not None else None,
            "scorecard_status": scorecard_status,
            "missing_required_evidence": missing_required_evidence,
            "source_truth_conflicts": source_truth_conflicts,
            "closeout_compatibility": closeout_compatibility,
            "bundle_failure": _bundle_failure(bundle_path),
            "stdout_tail": _tail(completed.stdout or ""),
            "stderr_tail": _tail(completed.stderr or ""),
        }

    return {
        "lane_id": lane["lane_id"],
        "declared_status": lane["status"],
        "ci_safe": lane["ci_safe"],
        "closeout_required": lane.get("closeout_required") is True,
        "provider": lane["provider"],
        "scenario": lane["scenario"],
        "status": "passed" if passed else "failed",
        "exit_code": completed.returncode,
        "bundle_path": str(bundle_path) if bundle_path is not None else None,
        "scorecard_status": scorecard_status,
        "closeout_compatibility_status": (
            str(closeout_compatibility.get("status"))
            if isinstance(closeout_compatibility, dict)
            else "not_applicable"
        ),
        "failure_envelope": failure_envelope,
        "command": command,
    }


def _matrix_failure_envelope(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    failures = [
        {
            "lane_id": result["lane_id"],
            "status": result["status"],
            "failure_envelope": result["failure_envelope"],
        }
        for result in results
        if result["status"] in TERMINAL_FAILURE_STATUSES
    ]
    if not failures:
        return None
    return {
        "code": "canary_matrix_has_failures",
        "failed_lanes": len(failures),
        "failures": failures,
    }


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = ("passed", "failed", "blocked", "skipped")
    scorecard_statuses: dict[str, str] = {
        str(result["lane_id"]): str(result["scorecard_status"]) for result in results
    }
    return {
        "selected_lanes": len(results),
        "executed": sum(1 for result in results if result["exit_code"] is not None),
        **{
            status: sum(1 for result in results if result["status"] == status)
            for status in statuses
        },
        "lane_statuses": {str(result["lane_id"]): str(result["status"]) for result in results},
        "bundle_paths": {
            str(result["lane_id"]): result["bundle_path"] for result in results
        },
        "scorecard_statuses": scorecard_statuses,
        "failure_envelope": _matrix_failure_envelope(results),
    }


def run_matrix(
    *,
    lanes: list[dict[str, Any]],
    output_root: Path,
    run_root: Path,
    allow_live_provider: bool,
    cwd: Path,
    timeout_s: int,
    allow_warn_scorecard: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    run_root.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)

    for lane in lanes:
        setup_error = _lane_setup_error(lane)
        if lane.get("status") != "ready" and setup_error is not None:
            results.append(_blocked_result(lane, failure=setup_error))
            continue
        if _is_live_provider_lane(lane):
            lane_env = _lane_env(lane)
            if not allow_live_provider or not live_provider_credentials_present(lane_env):
                missing: list[str] = []
                if not allow_live_provider:
                    missing.append("--allow-live-provider")
                if not live_provider_credentials_present(lane_env):
                    missing.append(LIVE_PROVIDER_ENV)
                results.append(
                    _blocked_result(
                        lane,
                        failure={
                            "type": "live_provider_unavailable",
                            "code": "live_provider_not_enabled",
                            "readiness_state": "not_ready",
                            "phase": "setup",
                            "service": "gonka_proxy_llm_gateway",
                            "required_backend": "gonka_compatible_llm_proxy",
                            "detected_backend": "missing_operator_approval_or_credentials",
                            "retryable": True,
                            "lane_id": lane["lane_id"],
                            "message": (
                                "Live-provider canary lanes require explicit operator "
                                "approval and provider credentials."
                            ),
                            "missing": missing,
                            "owner": "runtime-quality",
                            "next_action": (
                                "Re-run with --allow-live-provider and "
                                f"{LIVE_PROVIDER_ENV} set by an approved operator."
                            ),
                        },
                    )
                )
                continue
        elif lane.get("status") != "ready":
            results.append(
                _skipped_result(
                    lane,
                    reason=str(
                        (lane.get("coverage") or {}).get("missing_or_deferred_reason")
                        or "Lane is not ready to execute."
                    ),
                )
            )
            continue

        command = _command_for_lane(lane, output_root=output_root, run_root=run_root)
        completed = _run_lane_command(
            command,
            env=_lane_env(lane),
            cwd=cwd,
            timeout_s=timeout_s,
        )
        results.append(
            _completed_result(
                lane,
                command=command,
                completed=completed,
                allow_warn_scorecard=allow_warn_scorecard,
            )
        )

    return results


def _build_payload(
    *,
    selected_lanes: list[dict[str, Any]],
    results: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "selection": {
            "deterministic": bool(args.deterministic),
            "ci_smoke": bool(args.ci_smoke),
            "lane_id": args.lane_id or None,
            "only_lane": args.only_lane or None,
            "scenario": args.scenario or None,
            "allow_live_provider": bool(args.allow_live_provider or args.only_lane),
        },
        "summary": _summary(results),
        "lanes": results,
        "selected_lane_ids": [str(lane["lane_id"]) for lane in selected_lanes],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--deterministic",
        action="store_true",
        help="Run the deterministic closeout subset.",
    )
    selection.add_argument(
        "--ci-smoke",
        action="store_true",
        help="Run the fast CI-safe smoke subset; warn scorecards are accepted here only.",
    )
    selection.add_argument("--lane-id", default="", help="Run one stable matrix lane id.")
    selection.add_argument(
        "--scenario",
        default="",
        help="Run deterministic lanes for one scenario.",
    )
    parser.add_argument(
        "--only-lane",
        default="",
        help=(
            "Filter the selected run mode to one stable lane id. This is the "
            "operator-approved one-lane cloud debug selector."
        ),
    )
    parser.add_argument(
        "--allow-live-provider",
        action="store_true",
        help="Permit quarantined live-provider lanes when credentials are also present.",
    )
    parser.add_argument(
        "--output-root",
        default=".polisyos/canary_evidence",
        help="Root directory where per-lane evidence bundles are written.",
    )
    parser.add_argument(
        "--run-root",
        default="",
        help="Root directory for per-lane runtime state.",
    )
    parser.add_argument("--json-output", default="", help="Write matrix execution JSON here.")
    parser.add_argument("--timeout-s", type=int, default=1200, help="Per-lane process timeout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.only_lane and args.lane_id:
        print("--only-lane cannot be combined with --lane-id.", file=sys.stderr)
        return 3
    repo_root = Path.cwd()
    run_root = (
        Path(args.run_root)
        if args.run_root
        else repo_root / ".polisyos" / "canary_matrix_runs" / _utc_stamp()
    )
    output_root = Path(args.output_root)
    selected_lanes = select_lanes(
        canary_matrix.build_canary_lanes(),
        deterministic=args.deterministic,
        ci_smoke=args.ci_smoke,
        lane_id=args.lane_id,
        only_lane=args.only_lane,
        scenario=args.scenario,
        include_live_provider=(
            args.allow_live_provider or bool(args.lane_id) or bool(args.only_lane)
        ),
    )
    if not selected_lanes:
        failure = {
            "code": "canary_matrix_selection_empty",
            "message": "No canary matrix lanes matched the requested selection.",
            "selection": {
                "deterministic": bool(args.deterministic),
                "ci_smoke": bool(args.ci_smoke),
                "lane_id": args.lane_id or None,
                "only_lane": args.only_lane or None,
                "scenario": args.scenario or None,
            },
        }
        payload = {
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "selection": failure["selection"],
            "summary": {
                "selected_lanes": 0,
                "executed": 0,
                "passed": 0,
                "failed": 0,
                "blocked": 0,
                "skipped": 0,
                "lane_statuses": {},
                "bundle_paths": {},
                "scorecard_statuses": {},
                "failure_envelope": failure,
            },
            "lanes": [],
            "selected_lane_ids": [],
        }
        if args.json_output:
            _write_json(Path(args.json_output), payload)
        print("No canary matrix lanes matched the requested selection.", file=sys.stderr)
        return 2

    results = run_matrix(
        lanes=selected_lanes,
        output_root=output_root,
        run_root=run_root,
        allow_live_provider=bool(args.allow_live_provider or args.only_lane),
        cwd=repo_root,
        timeout_s=max(1, args.timeout_s),
        allow_warn_scorecard=bool(args.ci_smoke),
    )
    payload = _build_payload(selected_lanes=selected_lanes, results=results, args=args)
    if args.json_output:
        _write_json(Path(args.json_output), payload)

    summary = payload["summary"]
    print(
        "Canary matrix run: "
        f"{summary['selected_lanes']} selected, "
        f"{summary['executed']} executed, "
        f"{summary['passed']} passed, "
        f"{summary['failed']} failed, "
        f"{summary['blocked']} blocked, "
        f"{summary['skipped']} skipped"
    )
    for result in results:
        print(
            f"{result['lane_id']} [{result['status']}] "
            f"bundle={result['bundle_path'] or 'none'} "
            f"scorecard={result['scorecard_status']}"
        )
    return 0 if summary["failure_envelope"] is None else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
