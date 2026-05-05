#!/usr/bin/env python3
"""Steady-state LLM benchmark for Lex using real SPO light prompts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots, repo_root_from

sys.path.insert(0, str(repo_root_from(__file__)))

ensure_repo_import_roots(__file__)

from polisyos.data_forge.read_api.legal import (  # noqa: E402
    SPO_LIGHT_BATCH_SYSTEM_PROMPT,
    SPO_LIGHT_SYSTEM_PROMPT,
    GonkaClientPool,
    _group_items_by_request_budget,
    build_spo_light_batch_user_prompt,
    build_spo_light_user_prompt,
)


@dataclass(slots=True)
class BenchItem:
    doc_title: str
    doc_type: str
    publisher: str
    date_acc: str
    provision_citation: str
    provision_text: str
    legal_unit_subtype: str
    text_len: int


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--provisions-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--duration-minutes", type=float, default=30.0)
    p.add_argument("--sample-items", type=int, default=240)
    p.add_argument("--batch-size", type=int, default=4)
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
    p.add_argument("--parallel", type=int, default=8)
    p.add_argument("--parallel-global", type=int, default=None)
    p.add_argument("--gonka-base-url", default="https://api.gonkagate.com/v1")
    p.add_argument("--llm-model", default="qwen/qwen3-235b-a22b-instruct-2507-fp8")
    p.add_argument("--gonka-rate-limit-rps", type=float, default=1.0)
    p.add_argument("--max-retries", type=int, default=8)
    p.add_argument("--llm-temperature", type=float, default=0.1)
    p.add_argument("--spo-connect-timeout-seconds", type=int, default=15)
    p.add_argument("--spo-read-timeout-seconds", type=int, default=120)
    p.add_argument("--spo-total-timeout-seconds", type=int, default=180)
    p.add_argument("--spo-provider-watchdog-seconds", type=float, default=300.0)
    p.add_argument("--spo-rate-warmup-seconds", type=float, default=60.0)
    p.add_argument("--spo-rate-warmup-start-scale", type=float, default=3.0)
    p.add_argument("--spo-adaptive-rate-recovery-factor", type=float, default=0.97)
    p.add_argument("--spo-adaptive-rate-penalty-multiplier", type=float, default=1.35)
    p.add_argument("--spo-adaptive-rate-max-scale", type=float, default=8.0)
    p.add_argument("--worker-ramp-seconds", type=float, default=90.0)
    p.add_argument("--worker-ramp-jitter-seconds", type=float, default=1.0)
    p.add_argument("--drain-grace-seconds", type=float, default=45.0)
    p.add_argument("--text-min-chars", type=int, default=60)
    p.add_argument("--text-max-chars", type=int, default=900)
    return p.parse_args()


def _load_api_keys() -> list[str]:
    keys: list[str] = []
    index = 1
    while True:
        value = str(os.environ.get(f"GONKA_API_KEY_{index}", "") or "").strip()
        if not value:
            break
        keys.append(value)
        index += 1
    if not keys:
        single = str(os.environ.get("GONKA_API_KEY", "") or "").strip()
        if single:
            keys.append(single)
    if not keys:
        raise RuntimeError("No Gonka API keys found in GONKA_API_KEY or GONKA_API_KEY_1..N")
    return keys


def _load_items(args: argparse.Namespace) -> list[BenchItem]:
    items: list[BenchItem] = []
    for path in sorted(args.provisions_dir.rglob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if not row.get("fallback_allowed_for_reasoning", False):
                    continue
                text = str(row.get("text") or "").strip()
                if len(text) < args.text_min_chars or len(text) > args.text_max_chars:
                    continue
                items.append(
                    BenchItem(
                        doc_title=str(
                            row.get("doc_type_category")
                            or row.get("struct_kind")
                            or "Нормативний акт"
                        ),
                        doc_type=str(row.get("doc_type_category") or "law"),
                        publisher="",
                        date_acc="",
                        provision_citation=str(row.get("citation_label") or ""),
                        provision_text=text,
                        legal_unit_subtype=str(row.get("legal_unit_subtype") or ""),
                        text_len=len(text),
                    )
                )
                if len(items) >= args.sample_items:
                    return items
    return items


def _group_items(items: list[BenchItem], batch_size: int) -> list[list[BenchItem]]:
    size = max(1, int(batch_size))
    return [items[i : i + size] for i in range(0, len(items), size)]


def _estimate_bench_item_chars(item: BenchItem) -> int:
    return (
        len(item.provision_text)
        + len(item.provision_citation or "")
        + len(item.doc_title or "")
        + len(item.doc_type or "")
        + 128
    )


def _build_messages(group: list[BenchItem]) -> tuple[list[dict[str, str]], int]:
    if len(group) == 1:
        item = group[0]
        prompt = build_spo_light_user_prompt(
            provision_text=item.provision_text,
            doc_title=item.doc_title,
            doc_type=item.doc_type,
            publisher=item.publisher,
            date_acc=item.date_acc,
            provision_citation=item.provision_citation,
        )
        return (
            [
                {"role": "system", "content": SPO_LIGHT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            len(prompt),
        )

    prompt_items = [
        {
            "id": f"item_{idx:04d}",
            "doc_title": item.doc_title,
            "doc_type": item.doc_type,
            "publisher": item.publisher,
            "date_acc": item.date_acc,
            "provision_citation": item.provision_citation,
            "provision_text": item.provision_text,
        }
        for idx, item in enumerate(group)
    ]
    prompt = build_spo_light_batch_user_prompt(items=prompt_items)
    return (
        [
            {"role": "system", "content": SPO_LIGHT_BATCH_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        len(prompt),
    )


def _window_bucket(epoch_ms: int, *, started_epoch_ms: int, minutes: int = 5) -> int:
    span_ms = max(1, minutes) * 60 * 1000
    return max(0, (epoch_ms - started_epoch_ms) // span_ms)


def _worker_start_delay_seconds(
    worker_id: int,
    worker_count: int,
    *,
    ramp_seconds: float,
    jitter_seconds: float,
) -> float:
    if worker_count <= 1 or ramp_seconds <= 0.0:
        return 0.0
    slot = ramp_seconds * (float(worker_id) / float(max(1, worker_count - 1)))
    if jitter_seconds > 0.0:
        slot += random.uniform(0.0, jitter_seconds)  # noqa: S311
    return max(0.0, slot)


def _filter_rows_for_window(
    rows: list[dict[str, Any]],
    *,
    event_epoch_field: str,
    window_start_epoch_ms: int,
    window_end_epoch_ms: int | None = None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        event_epoch_ms = int(row.get(event_epoch_field) or row.get("completed_at_epoch_ms") or 0)
        if event_epoch_ms < window_start_epoch_ms:
            continue
        if window_end_epoch_ms is not None and event_epoch_ms > window_end_epoch_ms:
            continue
        filtered.append(row)
    return filtered


def _summarize_rows(
    rows: list[dict[str, Any]],
    *,
    started_epoch_ms: int,
    event_epoch_field: str = "completed_at_epoch_ms",
    duration_override_seconds: float | None = None,
) -> dict[str, Any]:
    statuses = Counter(int(row.get("http_status") or 0) for row in rows)
    success_rows = [row for row in rows if int(row.get("http_status") or 0) == 200]
    duration_seconds = 0.0
    if rows:
        if duration_override_seconds is not None:
            duration_seconds = max(0.001, float(duration_override_seconds))
        else:
            completed = [
                int(
                    row.get(event_epoch_field)
                    or row.get("completed_at_epoch_ms")
                    or started_epoch_ms
                )
                for row in rows
            ]
            duration_seconds = max(0.001, (max(completed) - started_epoch_ms) / 1000.0)
    success_requests = len(success_rows)
    success_items = sum(int(row.get("group_size") or 1) for row in success_rows)
    tokens_total = sum(
        int(row.get("prompt_tokens") or 0) + int(row.get("completion_tokens") or 0)
        for row in success_rows
    )
    wall_ms = [
        float(row.get("total_latency_ms") or 0.0)
        + float(row.get("limiter_wait_ms") or 0.0)
        + float(row.get("backoff_sleep_ms") or 0.0)
        for row in success_rows
    ]

    window_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        bucket = _window_bucket(
            int(row.get(event_epoch_field) or row.get("completed_at_epoch_ms") or started_epoch_ms),
            started_epoch_ms=started_epoch_ms,
            minutes=5,
        )
        window_rows[bucket].append(row)

    windows = []
    for bucket in sorted(window_rows):
        subset = window_rows[bucket]
        subset_success = [row for row in subset if int(row.get("http_status") or 0) == 200]
        subset_duration = 5 * 60.0
        windows.append(
            {
                "window_index": int(bucket),
                "window_start_minute": int(bucket * 5),
                "requests_total": len(subset),
                "success_requests": len(subset_success),
                "failed_requests": len(subset) - len(subset_success),
                "success_items": sum(int(row.get("group_size") or 1) for row in subset_success),
                "tokens_total": sum(
                    int(row.get("prompt_tokens") or 0) + int(row.get("completion_tokens") or 0)
                    for row in subset_success
                ),
                "requests_per_hour": round(len(subset_success) * 3600.0 / subset_duration, 1),
                "items_per_hour": round(
                    sum(int(row.get("group_size") or 1) for row in subset_success)
                    * 3600.0
                    / subset_duration,
                    1,
                ),
                "avg_retry_count": round(
                    sum(int(row.get("retry_count") or 0) for row in subset) / len(subset),
                    3,
                )
                if subset
                else 0.0,
                "avg_provider_rate_scale": round(
                    sum(float(row.get("provider_rate_scale") or 1.0) for row in subset)
                    / len(subset),
                    3,
                )
                if subset
                else 1.0,
                "avg_shared_rate_scale": round(
                    sum(float(row.get("shared_rate_scale") or 1.0) for row in subset) / len(subset),
                    3,
                )
                if subset
                else 1.0,
            }
        )

    return {
        "requests_total": len(rows),
        "success_requests": success_requests,
        "failed_requests": len(rows) - success_requests,
        "success_items": success_items,
        "status_counts": dict(statuses),
        "duration_seconds": round(duration_seconds, 3),
        "requests_per_hour": round(success_requests * 3600.0 / duration_seconds, 1)
        if duration_seconds > 0
        else 0.0,
        "items_per_hour": round(success_items * 3600.0 / duration_seconds, 1)
        if duration_seconds > 0
        else 0.0,
        "tokens_total": tokens_total,
        "tokens_per_hour": round(tokens_total * 3600.0 / duration_seconds, 1)
        if duration_seconds > 0
        else 0.0,
        "avg_retry_count": round(
            sum(int(row.get("retry_count") or 0) for row in rows) / len(rows), 3
        )
        if rows
        else 0.0,
        "retried_request_pct": (
            round(
                sum(1 for row in rows if int(row.get("retry_count") or 0) > 0) * 100.0 / len(rows),
                2,
            )
            if rows
            else 0.0
        ),
        "avg_wall_ms_success": round(sum(wall_ms) / len(wall_ms), 1) if wall_ms else 0.0,
        "avg_provider_rate_scale": (
            round(sum(float(row.get("provider_rate_scale") or 1.0) for row in rows) / len(rows), 3)
            if rows
            else 1.0
        ),
        "avg_shared_rate_scale": (
            round(sum(float(row.get("shared_rate_scale") or 1.0) for row in rows) / len(rows), 3)
            if rows
            else 1.0
        ),
        "five_minute_windows": windows,
    }


async def _run_probe(args: argparse.Namespace) -> dict[str, Any]:
    api_keys = _load_api_keys()
    items = _load_items(args)
    if len(items) < max(8, args.batch_size):
        raise RuntimeError(
            f"Not enough benchmark items loaded from {args.provisions_dir}: {len(items)}"
        )
    groups = _group_items_by_request_budget(
        items,
        request_batch_size=args.batch_size,
        request_batch_chars=args.spo_request_batch_chars,
        estimate_chars=_estimate_bench_item_chars,
        adaptive_batch_downshift_enabled=bool(args.spo_adaptive_batch_downshift_enabled),
        adaptive_batch_soft_chars_share=float(args.spo_adaptive_batch_soft_chars_share),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    log_path = args.output_dir / f"lex_llm_steady_state_{stamp}.jsonl"
    summary_path = args.output_dir / f"lex_llm_steady_state_{stamp}.summary.json"
    started_at = datetime.now(UTC)
    started_epoch_ms = int(started_at.timestamp() * 1000)
    active_window_seconds = max(60.0, args.duration_minutes * 60.0)
    active_stop_at = time.monotonic() + active_window_seconds
    active_end_epoch_ms = started_epoch_ms + int(active_window_seconds * 1000)
    drain_grace_seconds = max(0.0, float(args.drain_grace_seconds))

    pool = GonkaClientPool(
        api_keys=api_keys,
        base_url=args.gonka_base_url,
        model=args.llm_model,
        disable_json_mode=False,
        max_concurrent=max(1, args.parallel),
        rate_limit_rps=args.gonka_rate_limit_rps,
        temperature=args.llm_temperature,
        max_retries=args.max_retries,
        connect_timeout_seconds=args.spo_connect_timeout_seconds,
        read_timeout_seconds=args.spo_read_timeout_seconds,
        total_timeout_seconds=args.spo_total_timeout_seconds,
        provider_watchdog_seconds=args.spo_provider_watchdog_seconds,
        global_concurrent_cap=args.parallel_global,
        rate_warmup_seconds=args.spo_rate_warmup_seconds,
        rate_warmup_start_scale=args.spo_rate_warmup_start_scale,
        adaptive_rate_enabled=True,
        adaptive_rate_recovery_factor=args.spo_adaptive_rate_recovery_factor,
        adaptive_rate_penalty_multiplier=args.spo_adaptive_rate_penalty_multiplier,
        adaptive_rate_max_scale=args.spo_adaptive_rate_max_scale,
    )
    pool.set_request_log_path(log_path)

    request_counter = count()
    worker_count = max(1, min(len(groups), args.parallel_global or args.parallel))

    async def _worker(worker_id: int) -> None:
        delay = _worker_start_delay_seconds(
            worker_id,
            worker_count,
            ramp_seconds=max(0.0, float(args.worker_ramp_seconds)),
            jitter_seconds=max(0.0, float(args.worker_ramp_jitter_seconds)),
        )
        if delay > 0.0:
            await asyncio.sleep(delay)
        while time.monotonic() < active_stop_at:
            request_index = next(request_counter)
            group = groups[request_index % len(groups)]
            messages, prompt_chars = _build_messages(group)
            started_request_at = datetime.now(UTC)
            try:
                await pool.chat_completion(
                    messages,
                    response_format={"type": "json_object"},
                    request_meta={
                        "request_kind": "steady_state_batch"
                        if len(group) > 1
                        else "steady_state_single",
                        "group_size": len(group),
                        "prompt_chars": prompt_chars,
                        "steady_state_worker_id": worker_id,
                        "steady_state_request_index": request_index,
                        "request_started_at": started_request_at.isoformat(),
                        "request_started_at_epoch_ms": int(started_request_at.timestamp() * 1000),
                    },
                )
            except Exception:  # noqa: S112
                continue

    cancelled_workers = 0
    async with pool:
        tasks = [asyncio.create_task(_worker(worker_id)) for worker_id in range(worker_count)]
        done, pending = await asyncio.wait(
            tasks,
            timeout=active_window_seconds + drain_grace_seconds,
        )
        if pending:
            cancelled_workers = len(pending)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        if done:
            await asyncio.gather(*done, return_exceptions=True)

    rows = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    active_rows = _filter_rows_for_window(
        rows,
        event_epoch_field="request_started_at_epoch_ms",
        window_start_epoch_ms=started_epoch_ms,
        window_end_epoch_ms=active_end_epoch_ms,
    )
    drain_rows = _filter_rows_for_window(
        rows,
        event_epoch_field="completed_at_epoch_ms",
        window_start_epoch_ms=active_end_epoch_ms + 1,
    )
    summary = {
        "benchmark": "lex_llm_steady_state",
        "started_at": started_at.isoformat(),
        "ended_at": datetime.now(UTC).isoformat(),
        "provisions_dir": str(args.provisions_dir),
        "model": args.llm_model,
        "base_url": args.gonka_base_url,
        "keys": len(api_keys),
        "parallel": args.parallel,
        "parallel_global": args.parallel_global
        if args.parallel_global is not None
        else args.parallel,
        "batch_size": args.batch_size,
        "request_batch_chars": args.spo_request_batch_chars,
        "adaptive_batch_downshift_enabled": bool(args.spo_adaptive_batch_downshift_enabled),
        "adaptive_batch_soft_chars_share": float(args.spo_adaptive_batch_soft_chars_share),
        "rate_limit_rps_per_key": args.gonka_rate_limit_rps,
        "max_retries": args.max_retries,
        "warmup_seconds": args.spo_rate_warmup_seconds,
        "warmup_start_scale": args.spo_rate_warmup_start_scale,
        "adaptive_rate_recovery_factor": args.spo_adaptive_rate_recovery_factor,
        "adaptive_rate_penalty_multiplier": args.spo_adaptive_rate_penalty_multiplier,
        "adaptive_rate_max_scale": args.spo_adaptive_rate_max_scale,
        "worker_ramp_seconds": args.worker_ramp_seconds,
        "worker_ramp_jitter_seconds": args.worker_ramp_jitter_seconds,
        "active_window_seconds": active_window_seconds,
        "drain_grace_seconds": drain_grace_seconds,
        "active_end_epoch_ms": active_end_epoch_ms,
        "cancelled_workers": cancelled_workers,
        "sample_items": len(items),
        "sample_subtypes_top10": Counter(item.legal_unit_subtype for item in items).most_common(10),
        "sample_text_len_avg": round(sum(item.text_len for item in items) / len(items), 1),
        "overall": _summarize_rows(rows, started_epoch_ms=started_epoch_ms),
        "active_window": _summarize_rows(
            active_rows,
            started_epoch_ms=started_epoch_ms,
            event_epoch_field="request_started_at_epoch_ms",
            duration_override_seconds=active_window_seconds,
        ),
        "drain_window": _summarize_rows(
            drain_rows,
            started_epoch_ms=active_end_epoch_ms,
            event_epoch_field="completed_at_epoch_ms",
        ),
        "log_path": str(log_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> None:
    args = _parse_args()
    summary = asyncio.run(_run_probe(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
