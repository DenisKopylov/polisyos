from __future__ import annotations

import asyncio
import json

from polisyos.data_forge.domains.legal.batch import spo_client


def test_sliding_window_limiter_warmup_and_adaptive_recovery(monkeypatch) -> None:
    now = {"value": 100.0}

    monkeypatch.setattr(spo_client.time, "monotonic", lambda: now["value"])

    limiter = spo_client._SlidingWindowLimiter(
        max_requests=1,
        window=1.0,
        warmup_seconds=60.0,
        warmup_start_scale=4.0,
        adaptive_enabled=True,
        adaptive_recovery_factor=0.5,
        adaptive_penalty_multiplier=1.5,
        adaptive_max_scale=8.0,
    )

    assert limiter.current_scale() == 4.0

    now["value"] += 30.0
    assert round(limiter.current_scale(), 2) == 2.5

    asyncio.run(limiter.penalise(12.0))
    assert limiter.current_scale() >= 3.0

    limiter.record_success()
    assert limiter.current_scale() < 3.0

    now["value"] += 60.0
    limiter.record_success()
    assert limiter.current_scale() == 1.0


def test_gonka_client_log_includes_completion_and_rate_fields(tmp_path) -> None:
    shared = spo_client._SlidingWindowLimiter(max_requests=1, window=1.0)
    client = spo_client.GonkaClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        shared_limiter=shared,
        rate_limit_rps=2.0,
        rate_warmup_seconds=10.0,
        rate_warmup_start_scale=2.0,
        adaptive_rate_enabled=True,
    )
    path = tmp_path / "llm_requests.jsonl"
    client.set_request_log_path(path)

    client._log_request(
        request_meta={"request_kind": "unit_test", "group_size": 1},
        http_status=200,
        retry_count=1,
        limiter_wait_ms=12.5,
        backoff_sleep_ms=25.0,
        total_latency_ms=100.0,
        error_class="",
        provider_key_index=1,
        payload={
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
        },
    )

    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["completed_at"]
    assert row["completed_at_epoch_ms"] > 0
    assert row["provider_rate_scale"] >= 1.0
    assert row["provider_effective_rps"] > 0.0
    assert row["shared_rate_scale"] >= 1.0
    assert row["shared_effective_rps"] > 0.0
    assert row["request_kind"] == "unit_test"


def test_gonka_client_log_includes_request_lane_fields(tmp_path) -> None:
    client = spo_client.GonkaClient(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="test-model",
        rate_limit_rps=2.0,
        max_concurrent=8,
    )
    path = tmp_path / "lane_requests.jsonl"
    client.set_request_log_path(path)

    with client.request_lane(
        lane_name="retry_followup",
        rate_scale=0.5,
        concurrency_scale=0.5,
    ):
        client._log_request(
            request_meta={"request_kind": "unit_test_lane", "group_size": 1},
            http_status=200,
            retry_count=0,
            limiter_wait_ms=0.0,
            backoff_sleep_ms=0.0,
            total_latency_ms=10.0,
            error_class="",
            provider_key_index=1,
            payload={
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
                "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
            },
        )

    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["request_lane"] == "retry_followup"
    assert row["request_lane_rate_scale"] == 0.5
    assert row["request_lane_concurrency_scale"] == 0.5
