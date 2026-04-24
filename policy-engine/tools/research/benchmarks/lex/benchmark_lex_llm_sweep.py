#!/usr/bin/env python3
"""Sequential sweep runner for Lex steady-state LLM benchmark."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools._lib.imports import ensure_repo_import_roots, repo_root_from

sys.path.insert(0, str(repo_root_from(__file__)))

PRODUCT_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)


def _parse_csv_ints(raw: str) -> list[int]:
    values = [int(part.strip()) for part in str(raw or "").split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one integer value")
    return values


def _parse_csv_floats(raw: str) -> list[float]:
    values = [float(part.strip()) for part in str(raw or "").split(",") if part.strip()]
    if not values:
        raise ValueError("Expected at least one float value")
    return values


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--provisions-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument(
        "--benchmark-script",
        type=Path,
        default=Path(__file__).with_name("benchmark_lex_llm_steady_state.py"),
    )
    p.add_argument(
        "--config-pairs",
        default="",
        help="Optional explicit configs as 'parallel:rps[:batch],parallel:rps[:batch]'.",
    )
    p.add_argument("--parallel-values", default="8,10,12")
    p.add_argument("--rps-values", default="0.6,0.7,0.8")
    p.add_argument("--batch-size-values", default="4")
    p.add_argument("--duration-minutes", type=float, default=2.0)
    p.add_argument("--drain-grace-seconds", type=float, default=30.0)
    p.add_argument("--worker-ramp-seconds", type=float, default=60.0)
    p.add_argument("--worker-ramp-jitter-seconds", type=float, default=1.0)
    p.add_argument("--sample-items", type=int, default=240)
    p.add_argument("--spo-request-batch-chars", type=int, default=4800)
    p.add_argument(
        "--spo-adaptive-batch-downshift-enabled",
        dest="spo_adaptive_batch_downshift_enabled",
        action="store_true",
    )
    p.add_argument(
        "--no-spo-adaptive-batch-downshift-enabled",
        dest="spo_adaptive_batch_downshift_enabled",
        action="store_false",
    )
    p.set_defaults(spo_adaptive_batch_downshift_enabled=True)
    p.add_argument("--spo-adaptive-batch-soft-chars-share", type=float, default=0.80)
    p.add_argument("--max-retries", type=int, default=6)
    p.add_argument("--spo-rate-warmup-seconds", type=float, default=90.0)
    p.add_argument("--spo-rate-warmup-start-scale", type=float, default=4.0)
    p.add_argument("--spo-adaptive-rate-recovery-factor", type=float, default=0.97)
    p.add_argument("--spo-adaptive-rate-penalty-multiplier", type=float, default=1.35)
    p.add_argument("--spo-adaptive-rate-max-scale", type=float, default=8.0)
    p.add_argument("--limit-configs", type=int, default=0)
    return p.parse_args()


def _parse_config_pairs(raw: str) -> list[tuple[int, float, int]]:
    configs: list[tuple[int, float, int]] = []
    for chunk in [part.strip() for part in str(raw or "").split(",") if part.strip()]:
        pieces = [piece.strip() for piece in chunk.split(":") if piece.strip()]
        if len(pieces) not in {2, 3}:
            raise ValueError(f"Invalid config pair: {chunk!r}")
        parallel = int(pieces[0])
        rps = float(pieces[1])
        batch = int(pieces[2]) if len(pieces) == 3 else 4
        configs.append((parallel, rps, batch))
    return configs


def _build_command(
    args: argparse.Namespace,
    *,
    parallel: int,
    rate_limit_rps: float,
    batch_size: int,
) -> list[str]:
    command = [
        sys.executable,
        str(args.benchmark_script),
        "--provisions-dir",
        str(args.provisions_dir),
        "--output-dir",
        str(args.output_dir),
        "--duration-minutes",
        str(args.duration_minutes),
        "--sample-items",
        str(args.sample_items),
        "--batch-size",
        str(batch_size),
        "--spo-request-batch-chars",
        str(args.spo_request_batch_chars),
        "--parallel",
        str(parallel),
        "--parallel-global",
        str(parallel),
        "--gonka-rate-limit-rps",
        str(rate_limit_rps),
        "--max-retries",
        str(args.max_retries),
        "--spo-rate-warmup-seconds",
        str(args.spo_rate_warmup_seconds),
        "--spo-rate-warmup-start-scale",
        str(args.spo_rate_warmup_start_scale),
        "--spo-adaptive-rate-recovery-factor",
        str(args.spo_adaptive_rate_recovery_factor),
        "--spo-adaptive-rate-penalty-multiplier",
        str(args.spo_adaptive_rate_penalty_multiplier),
        "--spo-adaptive-rate-max-scale",
        str(args.spo_adaptive_rate_max_scale),
        "--spo-adaptive-batch-soft-chars-share",
        str(args.spo_adaptive_batch_soft_chars_share),
        "--worker-ramp-seconds",
        str(args.worker_ramp_seconds),
        "--worker-ramp-jitter-seconds",
        str(args.worker_ramp_jitter_seconds),
        "--drain-grace-seconds",
        str(args.drain_grace_seconds),
    ]
    if args.spo_adaptive_batch_downshift_enabled:
        command.append("--spo-adaptive-batch-downshift-enabled")
    else:
        command.append("--no-spo-adaptive-batch-downshift-enabled")
    return command


def _score_run(summary: dict[str, Any]) -> tuple[float, int, float, int]:
    active = (
        summary.get("active_window", {}) if isinstance(summary.get("active_window"), dict) else {}
    )
    overall = summary.get("overall", {}) if isinstance(summary.get("overall"), dict) else {}
    return (
        -float(active.get("items_per_hour", 0.0) or 0.0),
        int(active.get("failed_requests", 0) or 0),
        float(active.get("retried_request_pct", 0.0) or 0.0),
        int(overall.get("failed_requests", 0) or 0),
    )


def _markdown_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Rank | Parallel | RPS/key | Batch | Active items/h | Active fails | Retry % | Overall items/h | Summary |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for rank, result in enumerate(results, start=1):
        active = result["active_window"]
        overall = result["overall"]
        lines.append(
            "| "
            f"{rank} | {result['parallel']} | {result['rate_limit_rps_per_key']:.2f} | {result['batch_size']} | "
            f"{active.get('items_per_hour', 0.0):.1f} | {active.get('failed_requests', 0)} | "
            f"{active.get('retried_request_pct', 0.0):.2f} | {overall.get('items_per_hour', 0.0):.1f} | "
            f"[json]({result['summary_path']}) |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = _parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sweep_stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    sweep_dir = args.output_dir / f"llm_sweep_{sweep_stamp}"
    sweep_dir.mkdir(parents=True, exist_ok=True)

    explicit_configs = _parse_config_pairs(args.config_pairs)
    if explicit_configs:
        configurations = explicit_configs
    else:
        parallels = _parse_csv_ints(args.parallel_values)
        rps_values = _parse_csv_floats(args.rps_values)
        batch_sizes = _parse_csv_ints(args.batch_size_values)
        configurations = list(itertools.product(parallels, rps_values, batch_sizes))
    if args.limit_configs and args.limit_configs > 0:
        configurations = configurations[: int(args.limit_configs)]

    run_summaries: list[dict[str, Any]] = []
    stderr_logs: list[dict[str, Any]] = []

    for index, (parallel, rate_limit_rps, batch_size) in enumerate(configurations, start=1):
        command = _build_command(
            args,
            parallel=parallel,
            rate_limit_rps=rate_limit_rps,
            batch_size=batch_size,
        )
        completed = subprocess.run(
            command,
            cwd=str(PRODUCT_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )
        stderr_path = sweep_dir / f"run_{index:02d}_stderr.log"
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        if completed.returncode != 0:
            stderr_logs.append(
                {
                    "index": index,
                    "parallel": parallel,
                    "rate_limit_rps_per_key": rate_limit_rps,
                    "batch_size": batch_size,
                    "returncode": completed.returncode,
                    "stderr_path": str(stderr_path),
                    "stdout": completed.stdout[-4000:],
                }
            )
            continue
        summary = json.loads(completed.stdout)
        summary["stderr_path"] = str(stderr_path)
        run_summaries.append(summary)

    ranked = sorted(run_summaries, key=_score_run)
    report = {
        "benchmark": "lex_llm_sweep",
        "created_at": datetime.now(UTC).isoformat(),
        "provisions_dir": str(args.provisions_dir),
        "duration_minutes": args.duration_minutes,
        "drain_grace_seconds": args.drain_grace_seconds,
        "worker_ramp_seconds": args.worker_ramp_seconds,
        "worker_ramp_jitter_seconds": args.worker_ramp_jitter_seconds,
        "configurations_total": len(configurations),
        "successful_runs": len(run_summaries),
        "failed_runs": stderr_logs,
        "ranked_runs": ranked,
    }
    report_path = sweep_dir / "sweep_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = sweep_dir / "SWEEP_REPORT.md"
    markdown_path.write_text(_markdown_table(ranked), encoding="utf-8")
    print(
        json.dumps(
            {
                "report_path": str(report_path),
                "markdown_path": str(markdown_path),
                "successful_runs": len(ranked),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
