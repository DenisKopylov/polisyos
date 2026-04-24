#!/usr/bin/env python3
"""Compare calibration results across Lex shard hypotheses."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tools._lib.fs import atomic_write_json
from tools._lib.imports import ensure_repo_import_roots

ensure_repo_import_roots(__file__, include_src_root=False)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL in {path} at line {line_number}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"expected JSON object in {path} at line {line_number}")
            rows.append(payload)
    return rows


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_resumed_docs(pipeline_log: str) -> int:
    match = re.search(
        r"Progress loaded:\s+\d+\s+entries across\s+(\d+)\s+documents",
        pipeline_log,
    )
    if not match:
        return 0
    return int(match.group(1))


def analyze_shard(
    *,
    telemetry_path: Path,
    progress_path: Path,
    run_config_path: Path,
    stage_telemetry_path: Path,
    pipeline_log_path: Path,
    shard_idx: int,
) -> dict[str, Any]:
    rows = _load_jsonl(telemetry_path)
    progress = _load_jsonl(progress_path)
    run_cfg = _load_json(run_config_path)
    stage_telemetry = _load_json(stage_telemetry_path)
    pipeline_log = _load_text(pipeline_log_path)
    log_429_count = pipeline_log.count("Gonka pool 429")
    completed = (
        "Manifest pipeline complete:" in pipeline_log or "Pipeline complete in" in pipeline_log
    )
    docs_from_telemetry = int(stage_telemetry.get("docs_processed") or 0)
    duration_s = float(stage_telemetry.get("total_duration_s") or 0.0)
    progress_doc_ids = {
        row.get("doc_id") for row in progress if row.get("doc_id") not in {None, "__global__"}
    }
    docs_total = docs_from_telemetry or len(progress_doc_ids)
    resumed_docs = _extract_resumed_docs(pipeline_log)
    docs_count = max(0, docs_total - resumed_docs) if resumed_docs else docs_total
    if not rows:
        return {
            "shard": shard_idx,
            "hypothesis": run_cfg.get("hypothesis", "unknown"),
            "verify": run_cfg.get("spo_verify_mode", "?"),
            "global_cap": run_cfg.get("parallel_llm_global", 0),
            "docs": docs_count,
            "docs_total": docs_total,
            "resumed_docs": resumed_docs,
            "log_429_count": log_429_count,
            "completed": completed,
            "status": "no_data",
        }

    ok = [row for row in rows if int(row.get("http_status") or 0) == 200]
    err_429 = [row for row in rows if int(row.get("http_status") or 0) == 429]
    lats = [float(row["total_latency_ms"]) for row in ok if row.get("total_latency_ms") is not None]
    epochs = [
        int(row["completed_at_epoch_ms"])
        for row in rows
        if row.get("completed_at_epoch_ms") is not None
    ]
    span_sec = (max(epochs) - min(epochs)) / 1000 if len(epochs) > 1 else 1.0
    err_classes = Counter(
        str(row.get("error_class") or "unknown")
        for row in rows
        if int(row.get("http_status") or 0) != 200
    )
    p50_ms = round(statistics.median(lats)) if lats else 0
    p90_ms = round(statistics.quantiles(lats, n=10)[8]) if len(lats) >= 10 else 0
    effective_duration_s = duration_s or span_sec
    docs_per_hour = round(docs_count / max(0.001, effective_duration_s / 3600), 1)
    effective_rps = round(len(ok) / max(1.0, span_sec), 2)

    return {
        "shard": shard_idx,
        "hypothesis": run_cfg.get("hypothesis", "unknown"),
        "verify": run_cfg.get("spo_verify_mode", "?"),
        "global_cap": run_cfg.get("parallel_llm_global", 0),
        "docs": docs_count,
        "docs_total": docs_total,
        "resumed_docs": resumed_docs,
        "total_requests": len(rows),
        "ok": len(ok),
        "pct_429": round(100 * len(err_429) / max(1, len(rows)), 1),
        "pct_capacity_reached": round(
            100 * err_classes.get("transfer_agent_capacity_reached", 0) / max(1, len(rows)),
            1,
        ),
        "log_429_count": log_429_count,
        "rps_effective": effective_rps,
        "p50_ms": p50_ms,
        "p90_ms": p90_ms,
        "docs_per_hour": docs_per_hour,
        "error_breakdown": dict(err_classes.most_common(5)),
        "stage_times": stage_telemetry.get("stage_times", {}),
        "quality_gate_passed": stage_telemetry.get("quality_gate_passed"),
        "completed": completed,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", nargs="?", type=Path, default=Path("/tmp/calibration"))
    parser.add_argument("--shards", type=int, default=6, help="Number of shard indexes to compare")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.shards <= 0:
        print("--shards must be positive", file=sys.stderr)
        return 2
    data_dir = args.data_dir
    results: list[dict[str, Any]] = []

    for shard_idx in range(args.shards):
        results.append(
            analyze_shard(
                telemetry_path=data_dir / f"shard_{shard_idx}_llm_requests.jsonl",
                progress_path=data_dir / f"shard_{shard_idx}_progress.jsonl",
                run_config_path=data_dir / f"shard_{shard_idx}_run_config.json",
                stage_telemetry_path=data_dir / f"shard_{shard_idx}_telemetry.json",
                pipeline_log_path=data_dir / f"shard_{shard_idx}_pipeline.log",
                shard_idx=shard_idx,
            )
        )

    ranked = sorted(
        results,
        key=lambda row: (
            -float(row.get("docs_per_hour", 0.0)),
            -float(row.get("completed", False)),
            -float(row.get("docs", 0.0)),
            float(row.get("log_429_count", 10**9)),
            float(row.get("pct_429", 100.0)),
            float(row.get("p50_ms", 10**9)),
        ),
    )

    headers = [
        "shard",
        "hypothesis",
        "docs",
        "docs_total",
        "resumed_docs",
        "docs_per_hour",
        "pct_429",
        "log_429_count",
        "pct_capacity_reached",
        "rps_effective",
        "p50_ms",
        "p90_ms",
        "verify",
        "global_cap",
        "completed",
        "quality_gate_passed",
    ]
    widths = {header: len(header) for header in headers}
    for row in ranked:
        for header in headers:
            widths[header] = max(widths[header], len(str(row.get(header, ""))))

    line = "  ".join(header.ljust(widths[header]) for header in headers)
    print(line)
    print("  ".join("-" * widths[header] for header in headers))
    for row in ranked:
        print("  ".join(str(row.get(header, "")).ljust(widths[header]) for header in headers))

    print("")
    print("Top error breakdowns:")
    for row in ranked:
        if row.get("error_breakdown"):
            print(f"shard {row['shard']} ({row['hypothesis']}): {row['error_breakdown']}")

    summary_path = data_dir / "comparison_summary.json"
    atomic_write_json(summary_path, {"ranked": ranked})
    print("")
    print(f"Summary JSON written to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
