from __future__ import annotations

from contextlib import contextmanager

import polisyos.scientist.governance.pipeline as pipeline_module
from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    PassContext,
    ValidatorPass,
)
from polisyos.scientist.governance.pipeline import ValidationPipeline
from polisyos.scientist.governance.profiles import ProfileLevel, ValidationProfile


class _ExplodingPass(ValidatorPass):
    @property
    def pass_id(self) -> str:
        return "exploding"

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        del ctx
        raise RuntimeError("boom")


class _FakeSpan:
    def set_attribute(self, _name: str, _value: object) -> None:
        return None

    def set_status(self, _status: object) -> None:
        return None

    def record_exception(self, _exc: BaseException) -> None:
        return None


class _FakeTracer:
    def __init__(self) -> None:
        self.started_spans: list[str] = []

    @contextmanager
    def start_as_current_span(self, name: str, *, attributes=None, kind=None):
        _ = attributes, kind
        self.started_spans.append(name)
        yield _FakeSpan()


class _FakeTimer:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb
        return None


class _FakeMetrics:
    def __init__(self) -> None:
        self.validation_issue_calls: list[dict[str, object]] = []
        self.timer_labels: list[dict[str, object]] = []
        self.degraded_calls: list[dict[str, object]] = []

    def time_governance_pass(self, labels: dict[str, object]) -> _FakeTimer:
        self.timer_labels.append(labels)
        return _FakeTimer()

    def record_validation_issue(self, **kwargs: object) -> None:
        self.validation_issue_calls.append(kwargs)

    def record_degraded_path(self, **kwargs: object) -> None:
        self.degraded_calls.append(kwargs)


def test_validation_pipeline_accepts_injected_observability(monkeypatch) -> None:
    def _fail_get_tracer():
        raise AssertionError("global tracer lookup should not run when tracer is injected")

    def _fail_get_metrics():
        raise AssertionError("global metrics lookup should not run when metrics are injected")

    monkeypatch.setattr(pipeline_module, "get_tracer", _fail_get_tracer)
    monkeypatch.setattr(pipeline_module, "get_metrics", _fail_get_metrics)
    monkeypatch.setattr("polisyos.core.observability.get_metrics", _fail_get_metrics)

    tracer = _FakeTracer()
    metrics = _FakeMetrics()
    pipeline = ValidationPipeline([_ExplodingPass()], tracer=tracer, metrics=metrics)
    profile = ValidationProfile(
        level=ProfileLevel.MVP,
        pass_ids=frozenset({"exploding"}),
        thresholds={},
        short_circuit_on_blocker=False,
    )
    ctx = PassContext(
        ir=None,
        state={},
        registry_bundle=None,
        profile=profile,
        run_id="test_injected_observability",
    )

    issues, trace = pipeline.validate(ctx, profile)

    assert len(issues) == 1
    assert issues[0].code == "PASS_EXECUTION_ERROR"
    assert tracer.started_spans[0] == "governance.validation_pipeline"
    assert "governance.pass.exploding" in tracer.started_spans
    assert metrics.timer_labels == [{"pass_id": "exploding"}]
    assert metrics.validation_issue_calls[0]["error_type"] == "PASS_EXECUTION_ERROR"
    assert metrics.degraded_calls[0]["reason"] == "validator_pass_failed"
    assert trace.total_blockers == 1
