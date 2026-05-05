"""Tests for the @traced decorator."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager

import polisyos.core.observability.decorators as decorators_module
import pytest
from polisyos.core.observability import traced


class TestTracedDecorator:
    """Tests for the @traced decorator."""

    def test_basic_decoration(self, test_tracer_provider, in_memory_exporter):
        """Decorator should create spans for functions."""

        @traced
        def my_function(x: int, y: int) -> int:
            return x + y

        result = my_function(1, 2)

        assert result == 3
        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name.endswith("my_function")

    def test_async_decoration(self, test_tracer_provider, in_memory_exporter):
        """Decorator should work with async functions."""

        @traced
        async def async_function(x: int) -> int:
            await asyncio.sleep(0.001)
            return x * 2

        result = asyncio.run(async_function(5))

        assert result == 10
        spans = in_memory_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name.endswith("async_function")

    def test_custom_attributes(self, test_tracer_provider, in_memory_exporter):
        """Decorator should apply custom attributes."""

        @traced(phase="VALIDATE", agent="governor", node="validate")
        def validate_policy(ir: dict) -> bool:
            return True

        validate_policy({"version": "2.0.0"})

        spans = in_memory_exporter.get_finished_spans()
        span = spans[0]

        assert span.attributes["polisyos.phase"] == "VALIDATE"
        assert span.attributes["polisyos.agent.name"] == "governor"
        assert span.attributes["polisyos.node.name"] == "validate"

    def test_capture_args(self, test_tracer_provider, in_memory_exporter):
        """Decorator should capture arguments when enabled."""

        @traced(capture_args=True)
        def process(name: str, count: int) -> str:
            return f"{name}:{count}"

        process("test", 42)

        spans = in_memory_exporter.get_finished_spans()
        span = spans[0]

        assert span.attributes["function.arg.name"] == "test"
        assert span.attributes["function.arg.count"] == 42

    def test_exception_handling(self, test_tracer_provider, in_memory_exporter):
        """Decorator should record exceptions and re-raise."""

        @traced
        def failing_function() -> None:
            raise RuntimeError("Expected failure")

        with pytest.raises(RuntimeError, match="Expected failure"):
            failing_function()

        spans = in_memory_exporter.get_finished_spans()
        span = spans[0]

        assert span.status.status_code.name == "ERROR"

    def test_tracer_factory_override_avoids_global_lookup(self, monkeypatch):
        """Decorator should honor injected tracer factories instead of global access."""

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

        def _fail_get_tracer():
            raise AssertionError(
                "global tracer lookup should not run when tracer_factory is provided"
            )

        monkeypatch.setattr(decorators_module, "get_tracer", _fail_get_tracer)
        tracer = _FakeTracer()

        @traced(name="custom.trace", tracer_factory=lambda: tracer)
        def traced_function() -> str:
            return "ok"

        assert traced_function() == "ok"
        assert tracer.started_spans == ["custom.trace"]

    def test_traced_method_honors_tracer_factory(self, monkeypatch):
        """Method decorator should honor injected tracer factories instead of global access."""

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
            def start_as_current_span(self, name: str, *, attributes=None):
                _ = attributes
                self.started_spans.append(name)
                yield _FakeSpan()

        monkeypatch.setattr(
            decorators_module,
            "_default_tracer",
            lambda: (_ for _ in ()).throw(
                AssertionError(
                    "global tracer lookup should not run when tracer_factory is provided"
                )
            ),
        )
        tracer = _FakeTracer()

        class _Worker:
            run_id = "run-123"

            @decorators_module.traced_method(
                name="worker.step",
                tracer_factory=lambda: tracer,
            )
            def step(self) -> str:
                return "ok"

        worker = _Worker()

        assert worker.step() == "ok"
        assert tracer.started_spans == ["worker.step"]
