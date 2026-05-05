from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _benchmark_script_path() -> Path:
    return (
        Path(__file__).resolve().parents[4]
        / "tools"
        / "research"
        / "benchmarks"
        / "lex"
        / "benchmark_lex_llm_steady_state.py"
    )


def test_worker_start_delay_seconds_ramps_linearly() -> None:
    module = _load_script_module(
        _benchmark_script_path(),
        "lex_llm_benchmark_script_test",
    )

    assert module._worker_start_delay_seconds(0, 4, ramp_seconds=60.0, jitter_seconds=0.0) == 0.0
    assert module._worker_start_delay_seconds(3, 4, ramp_seconds=60.0, jitter_seconds=0.0) == 60.0
    assert module._worker_start_delay_seconds(1, 4, ramp_seconds=60.0, jitter_seconds=0.0) == 20.0


def test_active_window_summary_uses_request_start_times() -> None:
    module = _load_script_module(
        _benchmark_script_path(),
        "lex_llm_benchmark_script_summary_test",
    )
    rows = [
        {
            "http_status": 200,
            "group_size": 4,
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "retry_count": 0,
            "total_latency_ms": 1000.0,
            "limiter_wait_ms": 100.0,
            "backoff_sleep_ms": 0.0,
            "provider_rate_scale": 2.0,
            "shared_rate_scale": 3.0,
            "request_started_at_epoch_ms": 1000,
            "completed_at_epoch_ms": 9000,
        },
        {
            "http_status": 200,
            "group_size": 4,
            "prompt_tokens": 80,
            "completion_tokens": 10,
            "retry_count": 1,
            "total_latency_ms": 1200.0,
            "limiter_wait_ms": 200.0,
            "backoff_sleep_ms": 100.0,
            "provider_rate_scale": 2.5,
            "shared_rate_scale": 3.5,
            "request_started_at_epoch_ms": 2500,
            "completed_at_epoch_ms": 11000,
        },
        {
            "http_status": 0,
            "group_size": 4,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "retry_count": 2,
            "provider_rate_scale": 2.0,
            "shared_rate_scale": 4.0,
            "request_started_at_epoch_ms": 8000,
            "completed_at_epoch_ms": 15000,
        },
    ]

    active_rows = module._filter_rows_for_window(
        rows,
        event_epoch_field="request_started_at_epoch_ms",
        window_start_epoch_ms=1000,
        window_end_epoch_ms=5000,
    )
    summary = module._summarize_rows(
        active_rows,
        started_epoch_ms=1000,
        event_epoch_field="request_started_at_epoch_ms",
        duration_override_seconds=4.0,
    )

    assert len(active_rows) == 2
    assert summary["success_requests"] == 2
    assert summary["failed_requests"] == 0
    assert summary["success_items"] == 8
    assert summary["items_per_hour"] == 7200.0
    assert summary["retried_request_pct"] == 50.0


def test_benchmark_grouping_uses_adaptive_batch_downshift() -> None:
    module = _load_script_module(
        _benchmark_script_path(),
        "lex_llm_benchmark_script_grouping_test",
    )
    items = [
        module.BenchItem(
            doc_title="Документ",
            doc_type="Закон",
            publisher="",
            date_acc="",
            provision_citation=f"Пункт {idx}",
            provision_text="x" * 700,
            legal_unit_subtype="core_normative_clause",
            text_len=700,
        )
        for idx in range(5)
    ]

    groups = module._group_items_by_request_budget(
        items,
        request_batch_size=5,
        request_batch_chars=4800,
        estimate_chars=module._estimate_bench_item_chars,
        adaptive_batch_downshift_enabled=True,
        adaptive_batch_soft_chars_share=0.80,
    )

    assert [len(group) for group in groups] == [4, 1]
