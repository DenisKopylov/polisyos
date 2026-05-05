from __future__ import annotations

from typing import Any, ClassVar

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodComposer,
    MethodMetadata,
    MethodRegistry,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    execute_heterogeneous_chain,
)
from polisyos.foundry.methods.backends.adapters import adapt_state
from polisyos.foundry.methods.backends.bayesian_runner import (
    BayesianBackendUnavailableError,
    BayesianRunner,
    bayesian_backend_health,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.jax_runner import JaxRunner
from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner
from polisyos.foundry.methods.backends.runtime_fingerprint import (
    BackendRuntimeFingerprint,
    capture_backend_runtime_fingerprint,
    compose_observed_tolerance_budgets,
    validate_observed_tolerance_budget,
    validate_observed_tolerance_budget_metrics,
)
from polisyos.foundry.methods.backends.solver_runner import SolverRunner
from polisyos.foundry.methods.exceptions import BackendAdaptationError


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _register_method(cls: type) -> type:
    registry = MethodRegistry.get_instance()
    registry.register(cls, override=True)
    return cls


class _JaxIncrement:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="jax_increment",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(ParameterSpec(name="delta", default=1.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="jax increment")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return state + params["delta"]


class _JaxRuntimeSeeded:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="jax_runtime_seeded",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="jax runtime seeded")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        draw = jax.random.uniform(params["__rng__"], shape=state.shape, dtype=state.dtype)
        return state + draw + jnp.asarray(params["__seed__"], dtype=state.dtype)


class _NumpyIncrement:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="numpy_increment",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(ParameterSpec(name="delta", default=1.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="numpy increment")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> Any:
        return np.asarray(state) + float(params["delta"])


class _SolverToy:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="solver_toy",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(ParameterSpec(name="x", default=1.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.SOLVER,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="solver toy")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
        return (
            {"x": float(params["x"])},
            {"status": "optimal", "gap": 0.0, "iterations": 4},
        )


class _EmitSignal:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="emit_signal",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="signal",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("none", "1"),
                )
            }
        ),
        parameters=(ParameterSpec(name="delta", default=1.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="emit signal")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> float:
        return float(state) + float(params["delta"])


class _ConsumeSignal:
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="consume_signal",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    name="signal",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("none", "1"),
                )
            }
        ),
        output_slots=frozenset(),
        parameters=(ParameterSpec(name="factor", default=2.0),),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="consume signal")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> float:
        return float(state) * float(params["factor"])


class _BayesianEmitSignal:
    method_variant: ClassVar[str] = "hmc"
    signature: ClassVar[MethodSignature] = MethodSignature(
        name="bayesian_emit_signal",
        namespace="tests.polyglot",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(
            {
                SlotSpec(
                    name="signal",
                    slot_type=SlotType.SCALAR,
                    unit=Unit("none", "1"),
                )
            }
        ),
        parameters=(
            ParameterSpec(name="delta", default=1.0),
            ParameterSpec(name="runtime_backend", default="auto"),
        ),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.BAYESIAN,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="bayesian emit signal")

    @staticmethod
    def pure_step(state: Any, params: dict[str, Any]) -> float:
        return float(state) + float(params["delta"])


def test_adapters_roundtrip_between_jax_and_numpy():
    arr = jnp.array([1.0, 2.0], dtype=jnp.float32)
    as_numpy = adapt_state(
        arr,
        source_backend=ComputeBackend.JAX,
        target_backend=ComputeBackend.NUMPY,
    )
    assert isinstance(as_numpy, np.ndarray)
    as_jax = adapt_state(
        as_numpy,
        source_backend=ComputeBackend.NUMPY,
        target_backend=ComputeBackend.JAX,
    )
    assert np.allclose(np.asarray(as_jax), np.asarray(arr))


def test_to_numpy_fails_closed_when_device_leaves_leak(monkeypatch):
    arr = jnp.array([1.0, 2.0], dtype=jnp.float32)

    monkeypatch.setattr("jax.device_get", lambda value: value)

    with pytest.raises(BackendAdaptationError):
        adapt_state(
            arr,
            source_backend=ComputeBackend.JAX,
            target_backend=ComputeBackend.NUMPY,
        )


def test_to_jax_rejects_object_dtype_host_arrays():
    arr = np.array([{"value": 1.0}], dtype=object)

    with pytest.raises(BackendAdaptationError, match="ndarray\\[object\\]"):
        adapt_state(
            arr,
            source_backend=ComputeBackend.NUMPY,
            target_backend=ComputeBackend.JAX,
        )


def test_numpy_runner_executes():
    method = _register_method(_NumpyIncrement)
    runner = NumpyRunner()
    result = runner.execute(
        method_class=method,
        signature=method.signature,
        state=np.array([1.0, 2.0]),
        params={"delta": 2.5},
        seed=42,
    )
    assert np.allclose(result.output, np.array([3.5, 4.5]))
    assert result.reproducibility.backend == ComputeBackend.NUMPY
    assert result.artifacts["backend_runtime_fingerprint"]["backend"] == "numpy"
    assert (
        result.artifacts["backend_runtime_fingerprint"]["tolerance_budget"]["semantic_mode"]
        == "library_exact_cpu"
    )
    assert result.reproducibility.observed_tolerance_budget["budget_source"] == "seed_prior"
    assert (
        result.artifacts["backend_runtime_fingerprint"]["observed_tolerance_budget"]["route_key"][
            "backend_route"
        ]
        == "numpy"
    )


def test_solver_runner_extracts_status():
    method = _register_method(_SolverToy)
    runner = SolverRunner()
    result = runner.execute(
        method_class=method,
        signature=method.signature,
        state={},
        params={"x": 3.0},
        seed=11,
    )
    assert result.output["x"] == 3.0
    assert result.reproducibility.solver_status is not None
    assert result.reproducibility.solver_status.value == "optimal"


def test_bayesian_runner_executes():
    method = _register_method(_BayesianEmitSignal)
    runner = BayesianRunner()
    result = runner.execute(
        method_class=method,
        signature=method.signature,
        state=4.0,
        params={"delta": 3.0},
        seed=5,
    )
    assert result.output == 7.0
    assert result.slot_outputs["signal"] == 7.0
    assert result.reproducibility.backend == ComputeBackend.BAYESIAN
    assert result.artifacts["bayesian_runtime_backend"] in {"numpy", "numpyro"}
    assert "bayesian_backend_health" in result.artifacts
    assert result.artifacts["backend_runtime_fingerprint"]["backend"] == "bayesian"


def test_bayesian_runner_reports_backend_health_and_fail_closed_request():
    method = _register_method(_BayesianEmitSignal)
    health = bayesian_backend_health(method)

    assert health.preferred_engine == "numpyro"
    assert health.default_runtime in {"numpy", "numpyro"}
    assert any(engine.engine == "numpy" and engine.available for engine in health.engines)

    runner = BayesianRunner()
    if health.default_runtime == "numpy":
        with pytest.raises(BayesianBackendUnavailableError):
            runner.execute(
                method_class=method,
                signature=method.signature,
                state=2.0,
                params={"delta": 1.0, "runtime_backend": "numpyro"},
                seed=7,
            )


def test_bayesian_bart_health_requires_full_pymc_bart_stack(monkeypatch) -> None:
    versions = {
        "numpy": "2.0.0",
        "pymc": "5.0.0",
    }

    monkeypatch.setattr(
        "polisyos.foundry.methods.backends.bayesian_runner.safe_version",
        lambda package: versions.get(package),
    )

    bart_method = type("BartMethod", (), {"method_variant": "bart"})
    health = bayesian_backend_health(bart_method)

    assert health.default_runtime == "unavailable"
    assert health.is_available is False


def test_jax_runner_executes():
    method = _register_method(_JaxIncrement)
    runner = JaxRunner()
    result = runner.execute(
        method_class=method,
        signature=method.signature,
        state=jnp.array([1.0, 2.0]),
        params={"delta": 2.0},
        seed=0,
    )
    assert np.allclose(np.asarray(result.output), np.array([3.0, 4.0]))
    assert result.reproducibility.backend == ComputeBackend.JAX


def test_jax_runner_uses_runtime_posture_tier(monkeypatch):
    method = _register_method(_JaxIncrement)
    runner = JaxRunner()

    monkeypatch.setattr(
        "polisyos.foundry.methods.backends.jax_runner.capture_backend_runtime_fingerprint",
        lambda *args, **kwargs: BackendRuntimeFingerprint(
            backend=ComputeBackend.JAX,
            available=True,
            determinism_tier=DeterminismTier.BEST_EFFORT_GPU,
            execution_device="gpu:test",
            runtime_stack=("jax", "jaxlib"),
            library_versions={"jax": "1.0", "jaxlib": "1.0"},
            seed=kwargs.get("seed"),
        ),
    )

    result = runner.execute(
        method_class=method,
        signature=method.signature,
        state=jnp.array([1.0, 2.0]),
        params={"delta": 2.0},
        seed=11,
    )

    assert result.reproducibility.determinism_tier == DeterminismTier.BEST_EFFORT_GPU
    assert result.artifacts["backend_runtime_fingerprint"]["determinism_tier"] == "best_effort_gpu"


def test_jax_runner_injects_runtime_seed_and_rng() -> None:
    method = _register_method(_JaxRuntimeSeeded)
    runner = JaxRunner()

    result = runner.execute(
        method_class=method,
        signature=method.signature,
        state=jnp.zeros((3,), dtype=jnp.float32),
        params={},
        seed=7,
    )

    expected = jax.random.uniform(jax.random.PRNGKey(7), shape=(3,), dtype=jnp.float32) + 7.0
    assert np.allclose(np.asarray(result.output), np.asarray(expected))


def test_backend_runtime_fingerprint_exposes_replay_contract() -> None:
    posture = capture_backend_runtime_fingerprint(ComputeBackend.NUMPY)

    assert posture.backend == ComputeBackend.NUMPY
    assert posture.replay_semantics
    assert posture.tolerance_budget["semantic_mode"] == "library_exact_cpu"
    assert posture.observed_tolerance_budget["route_key"]["backend_route"] == "numpy"
    assert posture.observed_tolerance_budget["validation_status"] == "compatible"
    assert posture.as_dict()["fingerprint"]


def test_backend_runtime_fingerprint_degrades_jax_ray_route() -> None:
    posture = BackendRuntimeFingerprint(
        backend=ComputeBackend.JAX,
        available=True,
        determinism_tier=DeterminismTier.STRICT_CPU,
        execution_device="cpu:test",
        runtime_stack=("jax", "ray"),
        library_versions={"jax": "1.0", "jaxlib": "1.0"},
        route_key={
            "backend_route": "jax+ray",
            "arch_family": "x86_64",
            "device_family": "cpu",
        },
    )

    assert posture.observed_tolerance_budget["downgraded_from"] == "strict_cpu"
    assert posture.observed_tolerance_budget["downgraded_to"] == "library_deterministic"
    assert "ray_serialization_boundary" in posture.observed_tolerance_budget["failure_reasons"]


def test_execute_heterogeneous_chain_numpy_to_jax():
    _register_method(_NumpyIncrement)
    _register_method(_JaxIncrement)

    composer = MethodComposer(registry=MethodRegistry.get_instance())
    node_np = composer.add("tests.polyglot.numpy_increment@1.0.0", delta=1.0)
    node_jax = composer.add("tests.polyglot.jax_increment@1.0.0", delta=2.0)
    chain = composer.build()

    result = execute_heterogeneous_chain(chain, state=np.array([1.0]))
    assert len(result.node_results) == 2
    assert np.allclose(np.asarray(result.final_state), np.array([4.0]))
    assert result.node_results[0][0] == node_np.id
    assert result.node_results[1][0] == node_jax.id
    assert result.reproducibility_contract["determinism_tier"] == "library_deterministic"
    assert (
        result.reproducibility_contract["observed_tolerance_budget"]["route_key"]["backend_route"]
        == "numpy->jax"
    )
    assert (
        result.reproducibility_contract["observed_tolerance_budget"]["budget_source"]
        == "seed_prior"
    )


def test_validate_observed_tolerance_budget_degrades_when_runtime_drift_exceeds_cpu_budget() -> (
    None
):
    posture = capture_backend_runtime_fingerprint(ComputeBackend.NUMPY, seed=7)

    validated = validate_observed_tolerance_budget(
        reference=np.array([1.0, 2.0]),
        candidate=np.array([1.0 + 5.0e-7, 2.0 + 5.0e-7]),
        budget=posture.observed_tolerance_budget,
        current_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
    )

    assert validated["validation_status"] == "degraded"
    assert validated["budget_source"] == "runtime_measured"
    assert validated["downgraded_from"] == "library_deterministic"
    assert validated["downgraded_to"] == "best_effort_gpu"
    assert "runtime_drift_exceeded_expected_budget" in validated["failure_reasons"]
    assert validated["abs_tol_p99"] == pytest.approx(5.0e-7)


def test_validate_observed_tolerance_budget_validates_statistical_same_fingerprint_replay() -> None:
    posture = BackendRuntimeFingerprint(
        backend=ComputeBackend.BAYESIAN,
        available=True,
        determinism_tier=DeterminismTier.STATISTICAL,
        execution_device="cpu:test",
        runtime_stack=("numpy", "numpyro"),
        library_versions={"numpy": "1.0"},
        route_key={
            "backend_route": "bayesian:numpy",
            "arch_family": "x86_64",
            "device_family": "cpu",
        },
    )

    reference = np.linspace(-1.0, 1.0, 128, dtype=float).reshape(64, 2)
    validated = validate_observed_tolerance_budget(
        reference=reference,
        candidate=reference.copy(),
        budget=posture.observed_tolerance_budget,
        current_tier=DeterminismTier.STATISTICAL,
    )

    assert validated["mode"] == "distributional"
    assert validated["validation_status"] == "validated"
    assert validated["scope"] == "same_fingerprint"
    assert validated["distributional_metrics"]["ks_statistic"] == pytest.approx(0.0)
    assert validated["distributional_metrics"]["q50_abs_error"] == pytest.approx(0.0)
    assert validated["distributional_metrics"]["q90_width_abs_error"] == pytest.approx(0.0)


def test_validate_observed_tolerance_budget_marks_statistical_cross_architecture_as_compatible() -> (
    None
):
    posture = BackendRuntimeFingerprint(
        backend=ComputeBackend.BAYESIAN,
        available=True,
        determinism_tier=DeterminismTier.STATISTICAL,
        execution_device="cpu:test",
        runtime_stack=("numpy", "numpyro"),
        library_versions={"numpy": "1.0"},
        route_key={
            "backend_route": "bayesian:numpy",
            "arch_family": "x86_64",
            "device_family": "cpu",
        },
    )

    validated = validate_observed_tolerance_budget_metrics(
        metrics={
            "ks_statistic": 0.09,
            "q50_abs_error": 0.04,
            "q90_width_abs_error": 0.06,
        },
        budget=posture.observed_tolerance_budget,
        current_tier=DeterminismTier.STATISTICAL,
    )

    assert validated["mode"] == "distributional"
    assert validated["validation_status"] == "compatible"
    assert validated["scope"] == "cross_architecture"
    assert "distributional_runtime_validation_not_implemented" not in validated["failure_reasons"]


def test_validate_observed_tolerance_budget_marks_excessive_statistical_drift_unknown() -> None:
    posture = BackendRuntimeFingerprint(
        backend=ComputeBackend.BAYESIAN,
        available=True,
        determinism_tier=DeterminismTier.STATISTICAL,
        execution_device="cpu:test",
        runtime_stack=("numpy", "numpyro"),
        library_versions={"numpy": "1.0"},
        route_key={
            "backend_route": "bayesian:numpy",
            "arch_family": "x86_64",
            "device_family": "cpu",
        },
    )

    validated = validate_observed_tolerance_budget_metrics(
        metrics={
            "ks_statistic": 0.20,
            "q50_abs_error": 0.20,
            "q90_width_abs_error": 0.20,
        },
        budget=posture.observed_tolerance_budget,
        current_tier=DeterminismTier.STATISTICAL,
    )

    assert validated["validation_status"] == "unknown"
    assert "runtime_drift_exceeded_expected_budget" in validated["failure_reasons"]


def test_compose_observed_tolerance_budgets_preserves_distributional_metrics() -> None:
    posture = BackendRuntimeFingerprint(
        backend=ComputeBackend.BAYESIAN,
        available=True,
        determinism_tier=DeterminismTier.STATISTICAL,
        execution_device="cpu:test",
        runtime_stack=("numpy", "numpyro"),
        library_versions={"numpy": "1.0"},
        route_key={
            "backend_route": "bayesian:numpy",
            "arch_family": "x86_64",
            "device_family": "cpu",
        },
    )
    budget_a = validate_observed_tolerance_budget_metrics(
        metrics={
            "ks_statistic": 0.00,
            "q50_abs_error": 0.00,
            "q90_width_abs_error": 0.00,
        },
        budget=posture.observed_tolerance_budget,
        current_tier=DeterminismTier.STATISTICAL,
    )
    budget_b = validate_observed_tolerance_budget_metrics(
        metrics={
            "ks_statistic": 0.09,
            "q50_abs_error": 0.04,
            "q90_width_abs_error": 0.06,
        },
        budget=posture.observed_tolerance_budget,
        current_tier=DeterminismTier.STATISTICAL,
    )

    composed = compose_observed_tolerance_budgets(
        [budget_a, budget_b],
        determinism_tiers=[DeterminismTier.STATISTICAL, DeterminismTier.STATISTICAL],
        composition_kind="parallel",
    )
    revalidated = validate_observed_tolerance_budget_metrics(
        metrics=composed["distributional_metrics"],
        budget=composed,
        current_tier=DeterminismTier.STATISTICAL,
    )

    assert composed["mode"] == "distributional"
    assert composed["distributional_metrics"]["ks_statistic"] == pytest.approx(0.09)
    assert composed["distributional_metrics"]["q50_abs_error"] == pytest.approx(0.04)
    assert composed["distributional_metrics"]["q90_width_abs_error"] == pytest.approx(0.06)
    assert composed["expected_budget"]["same_fingerprint_ks_tol"] == pytest.approx(0.05)
    assert revalidated["validation_status"] == "compatible"


def test_execute_heterogeneous_chain_routes_bound_slot_values():
    _register_method(_EmitSignal)
    _register_method(_ConsumeSignal)

    composer = MethodComposer(registry=MethodRegistry.get_instance())
    producer = composer.add("tests.polyglot.emit_signal@1.0.0", delta=1.0)
    consumer = composer.add("tests.polyglot.consume_signal@1.0.0", factor=3.0)
    composer.connect(producer, consumer, {"signal": "signal"})
    chain = composer.build()

    result = execute_heterogeneous_chain(chain, state=2.0)

    assert result.final_state == 9.0
    assert result.node_results[0][1].slot_outputs["signal"] == 3.0
