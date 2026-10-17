from __future__ import annotations

import time
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreakerRegistry
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodRunner,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
)
from polisyos.foundry.methods.equivalence import (
    ComparatorKind,
    CrossBackendEquivalenceCertificate,
    FieldToleranceSpec,
    InMemoryEquivalenceCertificateRegistry,
    get_default_equivalence_resolver,
    reset_default_equivalence_resolver,
    runtime_envelope_from_results,
    set_default_equivalence_resolver,
)
from polisyos.foundry.methods.selection_history import (
    ADVISOR_EXECUTION_CONTEXT_PARAM,
    AdvisorExecutionContext,
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
        equivalence_ref: str | None = None,
    ) -> None:
        self._backend = backend
        self._fail = fail
        self._error = error
        self._equivalence_ref = equivalence_ref
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
            cross_backend_equivalence_ref=self._equivalence_ref,
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
    reset_default_equivalence_resolver()
    yield
    MethodDispatcher.reset_instance()
    CircuitBreakerRegistry.reset_instance()
    get_global_selection_history().clear()
    reset_default_equivalence_resolver()


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
    assert (
        result.artifacts["dispatch_trace"]["selection_reason"]
        == "runtime_profile_fallback_preferred"
    )
    assert (
        result.artifacts["dispatch_trace"]["declared_route_budget"]["route_key"]["backend_route"]
        == "jax"
    )
    assert (
        result.artifacts["dispatch_trace"]["observed_route_budget"]["route_key"]["backend_route"]
        == "jax->numpy_fallback"
    )
    assert (
        result.artifacts["dispatch_trace"]["observed_route_budget"]["validation_status"]
        == "degraded"
    )
    assert result.artifacts["cost_attribution"]["backend"] == "numpy"
    assert result.artifacts["cost_attribution"]["estimated_cost_usd"] > 0.0
    assert tracer.spans[0].attributes["span_name"] == "foundry.method.dispatch"
    assert tracer.spans[0].attributes["foundry.dispatch_status"] == "success"
    assert tracer.spans[0].attributes["foundry.determinism_tier"] == "library_deterministic"
    assert metrics.slo_run_cost_usd.calls
    assert metrics.degraded_paths == []
    assert "dispatch_contract_degraded:jax->numpy" in result.warnings


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


def test_dispatcher_preserves_cross_backend_equivalence_ref() -> None:
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    jax_runner = _RecordingRunner(
        ComputeBackend.JAX,
        equivalence_ref="sha256:" + "a" * 64,
    )
    dispatcher.register_runner(jax_runner)

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=3,
    )

    assert result.cross_backend_equivalence_ref == "sha256:" + "a" * 64


def test_dispatcher_attaches_resolved_cross_backend_equivalence_certificate() -> None:
    history = _history_with_numpy_advantage()
    numpy_runner = _RecordingRunner(ComputeBackend.NUMPY)
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    source_result = numpy_runner.execute(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=11,
    )
    target_result = jax_runner.execute(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=11,
    )
    registry = InMemoryEquivalenceCertificateRegistry()
    registry.register(
        certificate_ref="sha256:" + "b" * 64,
        attestation_ref="sha256:" + "c" * 64,
        certificate=CrossBackendEquivalenceCertificate(
            certificate_id="xbeq:test:dispatch",
            method_fqn=_DummyMethod.signature.fqn,
            runtime_envelope=runtime_envelope_from_results(
                source_result=source_result,
                target_result=target_result,
            ),
            field_specs=(
                FieldToleranceSpec(
                    path="output.backend",
                    comparator=ComparatorKind.EXACT,
                ),
            ),
        ),
    )
    dispatcher = MethodDispatcher(
        runtime_history=history,
        equivalence_resolver=registry,
    )
    dispatcher.register_runner(_RecordingRunner(ComputeBackend.JAX))
    dispatcher.register_runner(_RecordingRunner(ComputeBackend.NUMPY))

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((64, 4))},
        params={},
        seed=11,
    )

    assert result.output["backend"] == "numpy"
    assert result.cross_backend_equivalence_ref == "sha256:" + "b" * 64
    assert result.artifacts["cross_backend_equivalence"]["attestation_ref"] == "sha256:" + "c" * 64


def test_dispatcher_default_singleton_uses_global_equivalence_resolver() -> None:
    history = _history_with_numpy_advantage()
    numpy_runner = _RecordingRunner(ComputeBackend.NUMPY)
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    source_result = numpy_runner.execute(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=21,
    )
    target_result = jax_runner.execute(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=21,
    )
    registry = InMemoryEquivalenceCertificateRegistry()
    registry.register(
        certificate_ref="sha256:" + "d" * 64,
        certificate=CrossBackendEquivalenceCertificate(
            certificate_id="xbeq:test:default-path",
            method_fqn=_DummyMethod.signature.fqn,
            runtime_envelope=runtime_envelope_from_results(
                source_result=source_result,
                target_result=target_result,
            ),
            field_specs=(
                FieldToleranceSpec(
                    path="output.backend",
                    comparator=ComparatorKind.EXACT,
                ),
            ),
        ),
    )
    set_default_equivalence_resolver(registry)

    dispatcher = MethodDispatcher.get_instance()
    dispatcher._runtime_history = history
    dispatcher.register_runner(_RecordingRunner(ComputeBackend.JAX))
    dispatcher.register_runner(_RecordingRunner(ComputeBackend.NUMPY))

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((64, 4))},
        params={},
        seed=21,
    )

    assert get_default_equivalence_resolver() is registry
    assert result.output["backend"] == "numpy"
    assert result.cross_backend_equivalence_ref == "sha256:" + "d" * 64


def test_dispatcher_explicit_equivalence_resolver_overrides_global_default() -> None:
    history = _history_with_numpy_advantage()
    numpy_runner = _RecordingRunner(ComputeBackend.NUMPY)
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    source_result = numpy_runner.execute(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=23,
    )
    target_result = jax_runner.execute(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=23,
    )
    global_registry = InMemoryEquivalenceCertificateRegistry()
    global_registry.register(
        certificate_ref="sha256:" + "e" * 64,
        certificate=CrossBackendEquivalenceCertificate(
            certificate_id="xbeq:test:global",
            method_fqn="other.method@1.0.0",
            runtime_envelope=runtime_envelope_from_results(
                source_result=source_result,
                target_result=target_result,
            ),
            field_specs=(
                FieldToleranceSpec(
                    path="output.backend",
                    comparator=ComparatorKind.EXACT,
                ),
            ),
        ),
    )
    explicit_registry = InMemoryEquivalenceCertificateRegistry()
    explicit_registry.register(
        certificate_ref="sha256:" + "f" * 64,
        certificate=CrossBackendEquivalenceCertificate(
            certificate_id="xbeq:test:explicit",
            method_fqn=_DummyMethod.signature.fqn,
            runtime_envelope=runtime_envelope_from_results(
                source_result=source_result,
                target_result=target_result,
            ),
            field_specs=(
                FieldToleranceSpec(
                    path="output.backend",
                    comparator=ComparatorKind.EXACT,
                ),
            ),
        ),
    )
    set_default_equivalence_resolver(global_registry)

    dispatcher = MethodDispatcher(
        runtime_history=history,
        equivalence_resolver=explicit_registry,
    )
    dispatcher.register_runner(_RecordingRunner(ComputeBackend.JAX))
    dispatcher.register_runner(_RecordingRunner(ComputeBackend.NUMPY))

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((64, 4))},
        params={},
        seed=23,
    )

    assert result.cross_backend_equivalence_ref == "sha256:" + "f" * 64


def test_dispatcher_preserves_existing_equivalence_ref_when_global_resolver_matches() -> None:
    history = _history_with_numpy_advantage()
    numpy_runner = _RecordingRunner(
        ComputeBackend.NUMPY,
        equivalence_ref="sha256:" + "1" * 64,
    )
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    source_result = numpy_runner.execute(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=25,
    )
    target_result = jax_runner.execute(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={},
        seed=25,
    )
    registry = InMemoryEquivalenceCertificateRegistry()
    registry.register(
        certificate_ref="sha256:" + "2" * 64,
        certificate=CrossBackendEquivalenceCertificate(
            certificate_id="xbeq:test:preserve-existing",
            method_fqn=_DummyMethod.signature.fqn,
            runtime_envelope=runtime_envelope_from_results(
                source_result=source_result,
                target_result=target_result,
            ),
            field_specs=(
                FieldToleranceSpec(
                    path="output.backend",
                    comparator=ComparatorKind.EXACT,
                ),
            ),
        ),
    )
    set_default_equivalence_resolver(registry)

    dispatcher = MethodDispatcher(runtime_history=history)
    dispatcher.register_runner(jax_runner)
    dispatcher.register_runner(numpy_runner)

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((64, 4))},
        params={},
        seed=25,
    )

    assert result.output["backend"] == "numpy"
    assert result.cross_backend_equivalence_ref == "sha256:" + "1" * 64


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


def test_dispatcher_records_advisor_execution_context_in_runtime_history() -> None:
    history = SelectionHistoryStore()
    dispatcher = MethodDispatcher(
        runtime_history=history,
        enable_runtime_selection=False,
    )
    jax_runner = _RecordingRunner(ComputeBackend.JAX)
    dispatcher.register_runner(jax_runner)

    result = dispatcher.dispatch(
        method_class=_DummyMethod,
        signature=_DummyMethod.signature,
        state={"X": np.ones((8, 2))},
        params={
            ADVISOR_EXECUTION_CONTEXT_PARAM: AdvisorExecutionContext(
                query_fingerprint="query-abc",
                loss_profile_id="coverage_strict",
                candidate_fqns=(
                    _DummyMethod.signature.fqn,
                    "tests.dispatch.alternative@1.0.0",
                ),
                selected_rank=1,
                selection_propensity=0.5,
                advisor_score_vector={
                    _DummyMethod.signature.fqn: 12.0,
                    "tests.dispatch.alternative@1.0.0": 11.2,
                },
                shadow_loss_estimates={"tests.dispatch.alternative@1.0.0": 0.2},
            ).model_dump(mode="json")
        },
        seed=5,
    )

    assert result.output["backend"] == "jax"
    record = history.latest_record_for(_DummyMethod.signature.fqn)
    assert record is not None
    assert record.query_fingerprint == "query-abc"
    assert record.loss_profile_id == "coverage_strict"
    assert record.candidate_fqns == (
        _DummyMethod.signature.fqn,
        "tests.dispatch.alternative@1.0.0",
    )
    assert record.selected_rank == 1
    assert record.selection_propensity == pytest.approx(0.5)
    assert record.advisor_score_vector["tests.dispatch.alternative@1.0.0"] == pytest.approx(11.2)
    assert record.shadow_loss_estimates["tests.dispatch.alternative@1.0.0"] == pytest.approx(0.2)
