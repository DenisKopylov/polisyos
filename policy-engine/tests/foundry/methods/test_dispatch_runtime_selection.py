from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, ClassVar, Mapping

import numpy as np
import pytest

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreakerRegistry
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import MethodResult, MethodRunner, MethodTiming, ReproducibilityInfo
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
)
from polisyos.foundry.methods.selection_history import (
    MethodExecutionRecord,
    SelectionHistoryStore,
    get_global_selection_history,
)


def _make_signature() -> MethodSignature:
    return MethodSignature(
        name="runtime_selected",
        namespace="tests.dispatch",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.JAX,
        supports_jit=True,
        supports_vmap=False,
        supports_grad=False,
    )


class _DummyMethod:
    signature: ClassVar[MethodSignature] = _make_signature()
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="runtime selection")

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
        return state


class _RecordingRunner(MethodRunner):
    def __init__(
        self,
        backend: ComputeBackend,
        *,
        fail: bool = False,
        error: Exception | None = None,
    ) -> None:
        self._backend = backend
        self._fail = fail
        self._error = error
        self.calls: list[ComputeBackend] = []

    @property
    def supported_backends(self) -> frozenset[ComputeBackend]:
        return frozenset({self._backend})

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        *,
        method_class: type,
        signature: MethodSignature,
        state: Any,
        params: Mapping[str, Any],
        seed: int,
    ) -> MethodResult:
        self.calls.append(self._backend)
        if self._error is not None:
            raise self._error
        if self._fail:
            raise RuntimeError(f"{self._backend.value} failed")
        return MethodResult(
            output={"backend": self._backend.value},
            timing=MethodTiming(wall_time_ms=1.0),
            reproducibility=ReproducibilityInfo(
                backend=self._backend,
                determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
                seed=seed,
            ),
        )


class _FakeSpan:
    def __init__(self, *, attributes: dict[str, Any] | None = None) -> None:
        self.attributes = dict(attributes or {})
        self.exceptions: list[Exception] = []

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self.exceptions.append(exc)


class _FakeTracer:
    def __init__(self) -> None:
        self.spans: list[_FakeSpan] = []

    @contextmanager
    def start_as_current_span(self, name: str, *, attributes: dict[str, Any] | None = None):
        span = _FakeSpan(attributes={"span_name": name, **dict(attributes or {})})
        self.spans.append(span)
        yield span


class _FakeMetricRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[float, dict[str, Any]]] = []

    def record(self, value: float, attrs: dict[str, Any]) -> None:
        self.calls.append((value, dict(attrs)))


class _FakeMetrics:
    def __init__(self) -> None:
        self.slo_run_cost_usd = _FakeMetricRecorder()
        self.degraded_paths: list[dict[str, Any]] = []

    def record_degraded_path(
        self,
        *,
        component: str,
        operation: str,
        reason: str,
        error_type: str | None = None,
    ) -> None:
        self.degraded_paths.append(
            {
                "component": component,
                "operation": operation,
                "reason": reason,
                "error_type": error_type,
            }
        )


@pytest.fixture(autouse=True)
def _reset_runtime_globals() -> None:
    MethodDispatcher.reset_instance()
    CircuitBreakerRegistry.reset_instance()
    get_global_selection_history().clear()
    yield
    MethodDispatcher.reset_instance()
    CircuitBreakerRegistry.reset_instance()
    get_global_selection_history().clear()


def _history_with_numpy_advantage() -> SelectionHistoryStore:
    history = SelectionHistoryStore()
    now = time.time()
    for idx in range(3):
        history.record(
            MethodExecutionRecord(
                method_fqn=_DummyMethod.signature.fqn,
                timestamp=now + idx,
                latency_ms=120.0,
                success=True,
                data_characteristics={"n_obs": 64, "n_features": 4, "backend": "jax"},
            )
        )
        history.record(
            MethodExecutionRecord(
                method_fqn=_DummyMethod.signature.fqn,
                timestamp=now + idx + 10,
                latency_ms=12.0,
                success=True,
                data_characteristics={"n_obs": 64, "n_features": 4, "backend": "numpy"},
            )
        )
    return history


def test_dispatcher_prefers_profiled_numpy_backend_for_small_workloads() -> None:
    history = _history_with_numpy_advantage()
    dispatcher = MethodDispatcher(runtime_history=history)
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    numpy_runner = _RecordingRunner(ComputeBackend.NUMPY)
    dispatcher.register_runner(jax_runner)
    dispatcher.register_runner(numpy_runner)

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((64, 4))},
        params={},
        seed=7,
    )

    assert result.output["backend"] == "numpy"
    assert jax_runner.calls == []
    assert numpy_runner.calls == [ComputeBackend.NUMPY]


def test_dispatcher_emits_dispatch_trace_and_cost_attribution(monkeypatch) -> None:
    history = _history_with_numpy_advantage()
    dispatcher = MethodDispatcher(runtime_history=history)
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    numpy_runner = _RecordingRunner(ComputeBackend.NUMPY)
    dispatcher.register_runner(jax_runner)
    dispatcher.register_runner(numpy_runner)
    tracer = _FakeTracer()
    metrics = _FakeMetrics()
    monkeypatch.setattr("polisyos.foundry.methods.backends.dispatch.get_tracer", lambda: tracer)
    monkeypatch.setattr("polisyos.foundry.methods.backends.dispatch.get_metrics", lambda: metrics)

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((64, 4))},
        params={},
        seed=7,
    )

    assert result.artifacts["dispatch_trace"]["selected_backend"] == "numpy"
    assert result.artifacts["dispatch_trace"]["selection_reason"] == "runtime_profile_fallback_preferred"
    assert result.artifacts["cost_attribution"]["backend"] == "numpy"
    assert result.artifacts["cost_attribution"]["estimated_cost_usd"] > 0.0
    assert tracer.spans[0].attributes["span_name"] == "foundry.method.dispatch"
    assert tracer.spans[0].attributes["foundry.dispatch_status"] == "success"
    assert tracer.spans[0].attributes["foundry.determinism_tier"] == "library_deterministic"
    assert metrics.slo_run_cost_usd.calls
    assert metrics.degraded_paths == []


def test_dispatcher_retries_declared_backend_when_profile_selected_backend_fails() -> None:
    history = _history_with_numpy_advantage()
    dispatcher = MethodDispatcher(runtime_history=history)
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    numpy_runner = _RecordingRunner(ComputeBackend.NUMPY, fail=True)
    dispatcher.register_runner(jax_runner)
    dispatcher.register_runner(numpy_runner)

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((64, 4))},
        params={},
        seed=9,
    )

    assert result.output["backend"] == "jax"
    assert numpy_runner.calls == [ComputeBackend.NUMPY]
    assert jax_runner.calls == [ComputeBackend.JAX]
    assert result.warnings == ()


def test_dispatcher_records_degraded_recovery_when_profile_backend_fails(monkeypatch) -> None:
    history = _history_with_numpy_advantage()
    dispatcher = MethodDispatcher(runtime_history=history)
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    numpy_runner = _RecordingRunner(ComputeBackend.NUMPY, fail=True)
    dispatcher.register_runner(jax_runner)
    dispatcher.register_runner(numpy_runner)
    tracer = _FakeTracer()
    metrics = _FakeMetrics()
    monkeypatch.setattr("polisyos.foundry.methods.backends.dispatch.get_tracer", lambda: tracer)
    monkeypatch.setattr("polisyos.foundry.methods.backends.dispatch.get_metrics", lambda: metrics)

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((64, 4))},
        params={},
        seed=9,
    )

    assert result.output["backend"] == "jax"
    assert "dispatch_backend_mismatch:jax->jax" not in result.warnings
    assert metrics.degraded_paths == [
        {
            "component": "foundry.method.dispatch",
            "operation": _DummyMethod.signature.fqn,
            "reason": "fallback_recovery",
            "error_type": None,
        }
    ]


def test_dispatcher_fail_closes_on_unclassified_profile_backend_error() -> None:
    history = _history_with_numpy_advantage()
    dispatcher = MethodDispatcher(runtime_history=history)
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    numpy_runner = _RecordingRunner(ComputeBackend.NUMPY, error=KeyError("unexpected lookup"))
    dispatcher.register_runner(jax_runner)
    dispatcher.register_runner(numpy_runner)

    with pytest.raises(KeyError, match="unexpected lookup"):
        dispatcher.dispatch(
            method_class=_DummyMethod,
            signature=_DummyMethod.signature,
            state={"X": np.ones((64, 4))},
            params={},
            seed=9,
        )

    assert numpy_runner.calls == [ComputeBackend.NUMPY]
    assert jax_runner.calls == []
