#!/usr/bin/env python3
"""Run the N4 CGF closeout sweep through one shared grounding world."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.quality.validation.shared_grounding_world_cache import (
    GroundingWorldCache,
    rss_mb,
    stable_json_bytes,
)

WARM_BUDGET_SECONDS = 5 * 60
HISTORICAL_COLD_SECONDS = 4 * 60 * 60
DEFAULT_RECEIPT = Path(".tmp/gy-infra-1/n4_warm_closeout_sweep_receipt.json")


@dataclass(frozen=True)
class SweepStage:
    """One validator stage in the closeout sweep."""

    name: str
    module_name: str
    mode: str = "check"


STAGES: tuple[SweepStage, ...] = (
    SweepStage(
        "N4",
        "tools.quality.validation.check_layer3_gy_design_generation_contract",
    ),
    SweepStage(
        "CG1",
        "tools.quality.validation.check_grounding_relation_contract",
        mode="write_then_check",
    ),
    SweepStage(
        "CG2",
        "tools.quality.validation.check_grounding_bind_contract",
        mode="write_then_check",
    ),
    SweepStage(
        "CG0",
        "tools.quality.validation.check_grounding_credal_reference_contract",
    ),
    SweepStage(
        "CG3",
        "tools.quality.validation.check_grounding_admission_contract",
    ),
    SweepStage(
        "CG4",
        "tools.quality.validation.check_grounding_phrasing_defense_contract",
    ),
    SweepStage(
        "CG5",
        "tools.quality.validation.check_grounding_active_controller_contract",
    ),
    SweepStage(
        "CG6",
        "tools.quality.validation.check_grounding_benchmark_contract",
    ),
    SweepStage(
        "GY-S2",
        "tools.quality.validation.check_layer3_gy_knowledge_substrate_contract",
    ),
    SweepStage(
        "GY-S3",
        "tools.quality.validation.check_layer3_gy_intervention_substrate_contract",
    ),
    SweepStage(
        "N3-ledger",
        "tools.quality.validation.check_layer3_gy_generation_cycle_disposition_ledger",
    ),
)

BYTE_IDENTITY_SAMPLES = {
    "cg0": "tools.quality.validation.check_grounding_credal_reference_contract",
    "cg1": "tools.quality.validation.check_grounding_relation_contract",
}


def main(argv: list[str] | None = None) -> int:
    """Run the one-process warm closeout sweep."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument(
        "--byte-identity-sample",
        choices=tuple(BYTE_IDENTITY_SAMPLES),
        default="cg1",
    )
    parser.add_argument("--skip-byte-identity", action="store_true")
    parser.add_argument("--byte-identity-only", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    _ensure_paths(repo_root)
    cache = GroundingWorldCache(repo_root)
    sweep_started = time.monotonic()
    stages: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    byte_identity: dict[str, Any] | None = None
    if not args.skip_byte_identity:
        byte_identity = _run_byte_identity_check(
            repo_root,
            cache,
            sample=args.byte_identity_sample,
        )
        if byte_identity["status"] != "pass":
            findings.append(
                {
                    "code": "e1_byte_identity_failed",
                    "sample": args.byte_identity_sample,
                }
            )

    _emit_marker("cache_prime_start", "cache", 0.0)
    cache_prime_started = time.monotonic()
    entry = cache.get_entry(reason="sweep_prime")
    cache_prime_elapsed = max(0.0, time.monotonic() - cache_prime_started)
    _emit_marker("cache_prime_end", "cache", cache_prime_elapsed)

    if args.byte_identity_only:
        pass
    elif byte_identity is None or byte_identity["status"] == "pass":
        with cache.installed():
            for stage in STAGES:
                result = _run_stage(stage, repo_root, cache)
                stages.append(result)
                if result["status"] != "pass":
                    findings.append(
                        {
                            "code": "validator_stage_failed",
                            "issues": result.get("issues", []),
                            "stage": stage.name,
                        }
                    )
                    if not args.continue_on_failure:
                        break
                if result.get("cache_builds_during_stage", 0):
                    findings.append(
                        {
                            "code": "e5_cache_reuse_missed",
                            "cache_builds": result["cache_builds_during_stage"],
                            "stage": stage.name,
                        }
                    )
    owner_change_probe = cache.owner_change_probe()
    if owner_change_probe["status"] != "pass":
        findings.append({"code": "e1_owner_change_probe_failed"})

    elapsed = max(0.0, time.monotonic() - sweep_started)
    receipt = {
        "schema_version": "policyos.tools.validation.grounding_closeout_sweep.v1",
        "byte_identity": byte_identity,
        "cache": {
            "active_entry": entry.to_receipt(),
            "owner_change_probe": owner_change_probe,
            "stats": dict(sorted(cache.stats.items())),
        },
        "compute_economics": {
            "historical_cold_seconds": HISTORICAL_COLD_SECONDS,
            "historical_cold_wall_time": "about 4 hours from Rev 14 notes",
            "total_elapsed_seconds": elapsed,
            "warm_budget_seconds": WARM_BUDGET_SECONDS,
        },
        "findings": findings,
        "rss_mb": rss_mb(),
        "stages": stages,
        "status": "pass" if not findings else "fail",
    }
    receipt_path = repo_root / args.receipt
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.output_format == "json":
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(
            "status={status} elapsed={elapsed:.3f}s receipt={receipt}".format(
                status=receipt["status"],
                elapsed=elapsed,
                receipt=receipt_path,
            )
        )
        for finding in findings:
            print(json.dumps(finding, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 1


def _run_byte_identity_check(
    repo_root: Path,
    cache: GroundingWorldCache,
    *,
    sample: str,
) -> dict[str, Any]:
    module_name = BYTE_IDENTITY_SAMPLES[sample]
    module = importlib.import_module(module_name)
    _emit_marker("byte_identity_cold_start", sample, 0.0)
    cold_started = time.monotonic()
    cold_payload = module.build_live_payload(repo_root)
    cold_elapsed = max(0.0, time.monotonic() - cold_started)
    _emit_marker("byte_identity_cold_end", sample, cold_elapsed)
    cold_bytes = stable_json_bytes(cold_payload)
    with cache.installed():
        _emit_marker("byte_identity_warm_start", sample, 0.0)
        warm_started = time.monotonic()
        warm_payload = module.build_live_payload(repo_root)
        warm_elapsed = max(0.0, time.monotonic() - warm_started)
        _emit_marker("byte_identity_warm_end", sample, warm_elapsed)
    warm_bytes = stable_json_bytes(warm_payload)
    return {
        "cold_elapsed_seconds": cold_elapsed,
        "sample": sample,
        "status": "pass" if cold_bytes == warm_bytes else "fail",
        "warm_elapsed_seconds": warm_elapsed,
    }


def _run_stage(
    stage: SweepStage,
    repo_root: Path,
    cache: GroundingWorldCache,
) -> dict[str, Any]:
    module = importlib.import_module(stage.module_name)
    builds_before = int(cache.stats.get("builds", 0))
    _emit_marker("stage_start", stage.name, 0.0)
    started = time.monotonic()
    try:
        report = _run_stage_report(module, repo_root, mode=stage.mode)
        status = str(report.get("status") or "fail")
        issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    except BaseException as exc:
        status = "fail"
        issues = [{"code": type(exc).__name__, "message": str(exc)}]
        report = {"status": status, "issues": issues}
    elapsed = max(0.0, time.monotonic() - started)
    result = {
        "cache_builds_during_stage": int(cache.stats.get("builds", 0)) - builds_before,
        "elapsed_seconds": elapsed,
        "issues": issues,
        "mode": stage.mode,
        "module": stage.module_name,
        "rss_mb": rss_mb(),
        "stage": stage.name,
        "status": status,
    }
    _emit_marker("stage_end", stage.name, elapsed, status=status)
    result["report"] = _compact_report(report)
    return result


def _run_stage_report(module: Any, repo_root: Path, *, mode: str) -> dict[str, Any]:
    if mode == "write_then_check":
        payload = module.build_live_payload(repo_root)
        _call_write(module.write, repo_root, payload)
        return module.validate(repo_root)
    if hasattr(module, "validate"):
        return module.validate(repo_root)
    payload = module.build_live_payload(repo_root)
    return module.validate_payload(payload)


def _call_write(write: Callable[..., Any], repo_root: Path, payload: dict[str, Any]) -> None:
    try:
        write(repo_root, payload=payload)
    except TypeError:
        write(repo_root)


def _compact_report(report: dict[str, Any]) -> dict[str, Any]:
    compact = {
        "outputs": report.get("outputs") or report.get("output"),
        "status": report.get("status"),
    }
    issues = report.get("issues")
    if isinstance(issues, list):
        compact["issue_count"] = len(issues)
    return compact


def _emit_marker(
    event: str,
    name: str,
    elapsed_seconds: float,
    *,
    status: str | None = None,
) -> None:
    marker = {
        "elapsed_seconds": round(elapsed_seconds, 3),
        "event": event,
        "name": name,
        "rss_mb": round(rss_mb(), 3),
    }
    if status is not None:
        marker["status"] = status
    print(json.dumps(marker, sort_keys=True), flush=True)


def _ensure_paths(repo_root: Path) -> None:
    for item in (repo_root, repo_root / "src"):
        text = str(item)
        if text not in sys.path:
            sys.path.insert(0, text)


if __name__ == "__main__":
    raise SystemExit(main())
