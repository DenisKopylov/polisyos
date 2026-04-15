from __future__ import annotations

import logging

from polisyos.scientist.error_semantics import emit_degraded_path


class _FakeMetrics:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record_degraded_path(
        self,
        *,
        component: str,
        operation: str,
        reason: str,
        error_type: str,
    ) -> None:
        self.calls.append(
            {
                "component": component,
                "operation": operation,
                "reason": reason,
                "error_type": error_type,
            }
        )


def test_emit_degraded_path_prefers_injected_metrics_provider(monkeypatch) -> None:
    def _fail_get_metrics() -> object:
        raise AssertionError("global metrics lookup should not run when provider is injected")

    monkeypatch.setattr("polisyos.core.observability.get_metrics", _fail_get_metrics)

    metrics = _FakeMetrics()
    envelope = emit_degraded_path(
        component="scientist.tests",
        operation="emit_degraded_path",
        reason="provider_injected",
        message="test",
        metrics_provider=lambda: metrics,
    )

    assert envelope["reason"] == "provider_injected"
    assert metrics.calls == [
        {
            "component": "scientist.tests",
            "operation": "emit_degraded_path",
            "reason": "provider_injected",
            "error_type": "runtime_error",
        }
    ]


def test_emit_degraded_path_uses_explicit_metrics_instance() -> None:
    metrics = _FakeMetrics()

    envelope = emit_degraded_path(
        component="scientist.tests",
        operation="emit_degraded_path",
        reason="metrics_injected",
        message="test",
        metrics=metrics,
    )

    assert envelope["reason"] == "metrics_injected"
    assert metrics.calls[0]["reason"] == "metrics_injected"


def test_emit_degraded_path_accepts_stdlib_logger() -> None:
    metrics = _FakeMetrics()

    envelope = emit_degraded_path(
        component="scientist.tests",
        operation="emit_degraded_path",
        reason="stdlib_logger",
        message="test",
        log=logging.getLogger("polisyos.tests.error_semantics"),
        metrics=metrics,
    )

    assert envelope["reason"] == "stdlib_logger"
    assert metrics.calls[0]["reason"] == "stdlib_logger"
