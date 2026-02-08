from __future__ import annotations

import pytest

from polisyos.core.observability import get_metrics


class _FakeCounter:
    def __init__(self) -> None:
        self.calls: list[tuple[int | float, dict[str, object] | None]] = []

    def add(self, value: int | float, attrs: dict[str, object] | None = None) -> None:
        self.calls.append((value, attrs))


class _FakeHistogram:
    def __init__(self) -> None:
        self.calls: list[tuple[int | float, dict[str, object] | None]] = []

    def record(self, value: int | float, attrs: dict[str, object] | None = None) -> None:
        self.calls.append((value, attrs))


def test_authz_and_identity_metric_helpers(monkeypatch) -> None:
    metrics = get_metrics()
    if type(metrics).__module__ != "polisyos.core.observability.metrics":
        pytest.skip("OTel metrics backend is unavailable in this environment")
    monkeypatch.setattr(metrics, "_ensure_initialized", lambda: None)

    decisions = _FakeCounter()
    latency = _FakeHistogram()
    cache_hits = _FakeCounter()
    errors = _FakeCounter()
    identity_failures = _FakeCounter()

    metrics.authz_decisions_total = decisions  # type: ignore[assignment]
    metrics.authz_latency_seconds = latency  # type: ignore[assignment]
    metrics.authz_cache_hits_total = cache_hits  # type: ignore[assignment]
    metrics.authz_errors_total = errors  # type: ignore[assignment]
    metrics.identity_failures_total = identity_failures  # type: ignore[assignment]

    metrics.record_authz_decision(policy="polisyos/authz/decision", decision="allow", cached=False)
    metrics.record_authz_latency("polisyos/authz/decision", 0.002)
    metrics.record_authz_cache_hit(policy="polisyos/authz/decision")
    metrics.record_authz_error(policy="polisyos/authz/decision", reason="opa_unreachable")
    metrics.record_identity_failure(reason="invalid_token", provider="keycloak")

    assert decisions.calls[-1][1] == {
        "policy": "polisyos/authz/decision",
        "decision": "allow",
        "cached": "false",
    }
    assert latency.calls[-1][1] == {"policy": "polisyos/authz/decision"}
    assert cache_hits.calls[-1][1] == {"policy": "polisyos/authz/decision"}
    assert errors.calls[-1][1] == {
        "policy": "polisyos/authz/decision",
        "reason": "opa_unreachable",
    }
    assert identity_failures.calls[-1][1] == {"reason": "invalid_token", "provider": "keycloak"}
