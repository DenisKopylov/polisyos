"""
Test suite for Method Compiler and Specialization.
"""
from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable, Mapping, NamedTuple

import numpy as np
import pytest
import jax.numpy as jnp

from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.compiler import (
    CompilationCache,
    CompiledMethod,
    MethodCompiler,
    get_global_cache,
    reset_global_cache,
)
from polisyos.foundry.methods.composer import (
    MethodComposer,
)
from polisyos.foundry.methods.exceptions import ParameterValidationError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.foundry.methods.specialization import (
    BackendSpec,
    ShapeSpec,
    build_specialization,
    compute_static_params_hash,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_caches() -> None:
    reset_global_cache()
    MethodRegistry.reset_instance()
    yield
    reset_global_cache()
    MethodRegistry.reset_instance()


@pytest.fixture
def sample_unit() -> Unit:
    return Unit("currency", "UAH", scale=1.0)


@pytest.fixture
def income_slot(sample_unit: Unit) -> SlotSpec:
    return SlotSpec(
        name="income",
        slot_type=SlotType.VECTOR,
        unit=sample_unit,
        shape=("n_agents",),
        description="Agent gross income",
    )


@pytest.fixture
def tax_slot(sample_unit: Unit) -> SlotSpec:
    return SlotSpec(
        name="tax",
        slot_type=SlotType.VECTOR,
        unit=sample_unit,
        shape=("n_agents",),
        description="Tax due",
    )


def create_test_method(
    name: str,
    namespace: str,
    version: str,
    input_slots: frozenset[SlotSpec],
    output_slots: frozenset[SlotSpec],
    parameters: tuple[ParameterSpec, ...] = (),
    compute_fn: Any = None,
    pure_step_factory: (
        Callable[[Callable[[Any, Mapping[str, Any]], Any] | None], Any] | None
    ) = None,
) -> type:
    sig = MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        input_slots=input_slots,
        output_slots=output_slots,
        parameters=parameters,
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
    )

    meta = MethodMetadata(
        description=f"Test method: {name}",
        tags=frozenset({"test"}),
    )

    if pure_step_factory is None:
        def pure_step_factory(
            fn: Callable[[Any, Mapping[str, Any]], Any] | None = None,
        ) -> Any:
            if fn is None:
                def _identity(state: Any, params: Mapping[str, Any]) -> Any:
                    del params
                    return state

                return staticmethod(_identity)
            return staticmethod(fn)

    method_name = name.replace("_", " ").title().replace(" ", "") + "Method"
    return type(
        method_name,
        (),
        {
            "signature": sig,
            "metadata": meta,
            "pure_step": pure_step_factory(compute_fn),
        },
    )


@pytest.fixture
def flat_tax_method(
    income_slot: SlotSpec,
    tax_slot: SlotSpec,
    pure_step_factory: Callable[[Callable[[Any, Mapping[str, Any]], Any] | None], Any],
) -> type:
    def compute(state: Any, params: Mapping[str, Any]) -> Any:
        rate = params.get("rate", 0.18)
        threshold = params.get("threshold", 0.0)
        income = state.income
        taxable = jnp.maximum(income - threshold, 0.0)
        tax = taxable * rate
        return state._replace(tax=tax)

    return create_test_method(
        name="flat_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot}),
        parameters=(
            ParameterSpec(
                name="rate",
                default=0.18,
                is_static=False,
                bounds=(0.0, 1.0),
            ),
            ParameterSpec(
                name="threshold",
                default=0.0,
                is_static=True,
                bounds=(0.0, None),
            ),
        ),
        compute_fn=compute,
        pure_step_factory=pure_step_factory,
    )


@pytest.fixture
def progressive_tax_method(
    income_slot: SlotSpec,
    tax_slot: SlotSpec,
    pure_step_factory: Callable[[Callable[[Any, Mapping[str, Any]], Any] | None], Any],
) -> type:
    def compute(state: Any, params: Mapping[str, Any]) -> Any:
        rate1 = params.get("rate1", 0.10)
        rate2 = params.get("rate2", 0.20)
        rate3 = params.get("rate3", 0.30)
        bracket1 = params.get("bracket1", 10000.0)
        bracket2 = params.get("bracket2", 50000.0)

        income = state.income

        tax_b1 = jnp.minimum(income, bracket1) * rate1
        tax_b2 = jnp.clip(income - bracket1, 0.0, bracket2 - bracket1) * rate2
        tax_b3 = jnp.maximum(income - bracket2, 0.0) * rate3

        tax = tax_b1 + tax_b2 + tax_b3
        return state._replace(tax=tax)

    return create_test_method(
        name="progressive_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot}),
        parameters=(
            ParameterSpec(name="rate1", default=0.10, is_static=False),
            ParameterSpec(name="rate2", default=0.20, is_static=False),
            ParameterSpec(name="rate3", default=0.30, is_static=False),
            ParameterSpec(name="bracket1", default=10000.0, is_static=True),
            ParameterSpec(name="bracket2", default=50000.0, is_static=True),
        ),
        compute_fn=compute,
        pure_step_factory=pure_step_factory,
    )


@pytest.fixture
def registry_with_methods(
    flat_tax_method: type,
    progressive_tax_method: type,
) -> MethodRegistry:
    registry = MethodRegistry.get_instance()
    registry.register(flat_tax_method)
    registry.register(progressive_tax_method)
    return registry


class TaxState(NamedTuple):
    income: jnp.ndarray
    tax: jnp.ndarray


@pytest.fixture
def sample_state() -> TaxState:
    return TaxState(
        income=jnp.linspace(0, 100000, 1000),
        tax=jnp.zeros(1000),
    )


# =============================================================================
# ShapeSpec Tests
# =============================================================================


class TestShapeSpec:
    def test_from_array_1d(self):
        arr = jnp.zeros((100,), dtype=jnp.float32)
        spec = ShapeSpec.from_array(arr)
        assert spec.shape == (100,)
        assert spec.dtype == "float32"

    def test_from_array_2d(self):
        arr = np.zeros((50, 10), dtype=np.float64)
        spec = ShapeSpec.from_array(arr)
        assert spec.shape == (50, 10)
        assert spec.dtype == "float64"

    def test_hash_determinism(self):
        spec1 = ShapeSpec(shape=(100, 50), dtype="float32")
        spec2 = ShapeSpec(shape=(100, 50), dtype="float32")
        assert hash(spec1) == hash(spec2)

    def test_hash_different_shape(self):
        spec1 = ShapeSpec(shape=(100,), dtype="float32")
        spec2 = ShapeSpec(shape=(200,), dtype="float32")
        assert hash(spec1) != hash(spec2)

    def test_hash_different_dtype(self):
        spec1 = ShapeSpec(shape=(100,), dtype="float32")
        spec2 = ShapeSpec(shape=(100,), dtype="float64")
        assert hash(spec1) != hash(spec2)

    def test_canonical_str(self):
        spec = ShapeSpec(shape=(100, 50), dtype="float32")
        assert spec.canonical_str == "(100,50):float32"

    def test_ndim_and_size(self):
        spec = ShapeSpec(shape=(10, 20, 30), dtype="float32")
        assert spec.ndim == 3
        assert spec.size == 6000


# =============================================================================
# BackendSpec Tests
# =============================================================================


class TestBackendSpec:
    def test_current_defaults_to_cpu_in_tests(self):
        spec = BackendSpec.current()
        assert spec.platform == "cpu"
        assert spec.device_count >= 1
        assert spec.precision == "float32"
        assert isinstance(spec.jax_version, str)
        assert isinstance(spec.jaxlib_version, str)
        assert len(spec.config_fingerprint) in {0, 16}

    def test_custom_precision(self):
        spec = BackendSpec.current(precision="float64")
        assert spec.precision == "float64"

    def test_hash_determinism(self):
        spec1 = BackendSpec(platform="cpu", device_count=1, precision="float32")
        spec2 = BackendSpec(platform="cpu", device_count=1, precision="float32")
        assert hash(spec1) == hash(spec2)

    def test_canonical_str(self):
        spec = BackendSpec(
            platform="gpu",
            device_count=4,
            precision="float16",
            device_kinds=("A100",),
            jax_version="0.0.0",
            jaxlib_version="0.0.0",
            config_fingerprint="deadbeefdeadbeef",
        )
        assert spec.canonical_str == "gpu:4:float16::A100:0.0.0:0.0.0:deadbeefdeadbeef"

    def test_xla_flags_in_canonical_str(self):
        spec = BackendSpec(
            platform="gpu",
            device_count=1,
            precision="float32",
            xla_flags=frozenset({"xla_gpu_strict_conv_algorithm_picker=true"}),
            device_kinds=("A100",),
            jax_version="0.0.0",
            jaxlib_version="0.0.0",
            config_fingerprint="deadbeefdeadbeef",
        )
        assert "xla_gpu_strict_conv_algorithm_picker=true" in spec.canonical_str


# =============================================================================
# Static Params Hash Tests
# =============================================================================


class TestStaticParamsHash:
    def test_same_dict_same_hash(self):
        h1 = compute_static_params_hash({"a": 1, "b": 2})
        h2 = compute_static_params_hash({"a": 1, "b": 2})
        assert h1 == h2

    def test_different_key_order_same_hash(self):
        h1 = compute_static_params_hash({"a": 1, "b": 2, "c": 3})
        h2 = compute_static_params_hash({"c": 3, "a": 1, "b": 2})
        h3 = compute_static_params_hash({"b": 2, "c": 3, "a": 1})
        assert h1 == h2 == h3

    def test_different_values_different_hash(self):
        h1 = compute_static_params_hash({"a": 1})
        h2 = compute_static_params_hash({"a": 2})
        assert h1 != h2

    def test_nested_dict_order_invariant(self):
        h1 = compute_static_params_hash({"outer": {"a": 1, "b": 2}})
        h2 = compute_static_params_hash({"outer": {"b": 2, "a": 1}})
        assert h1 == h2

    def test_float_handling(self):
        h1 = compute_static_params_hash({"rate": 0.18})
        h2 = compute_static_params_hash({"rate": 0.18})
        assert h1 == h2

    def test_array_handling(self):
        arr = jnp.array([1.0, 2.0, 3.0])
        h1 = compute_static_params_hash({"thresholds": arr})
        h2 = compute_static_params_hash({"thresholds": jnp.array([1.0, 2.0, 3.0])})
        assert h1 == h2

    def test_array_nan_inf_handling(self):
        arr = jnp.array([0.0, jnp.nan, jnp.inf, -jnp.inf], dtype=jnp.float32)
        h1 = compute_static_params_hash({"values": arr})
        h2 = compute_static_params_hash({"values": arr})
        assert h1 == h2

    def test_hash_is_32_chars(self):
        h = compute_static_params_hash({"x": 1})
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)


# =============================================================================
# Specialization Tests
# =============================================================================


class TestSpecialization:
    def test_build_specialization_basic(self):
        spec = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={"threshold": 1000.0},
            input_arrays={"income": jnp.zeros((100,))},
        )
        assert spec.method_fqn == "test.method@1.0.0"
        assert spec.jit_enabled is True
        assert spec.vmap_axis is None
        assert len(spec.input_shapes) == 1

    def test_cache_key_determinism(self):
        spec1 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={"a": 1, "b": 2},
            input_arrays={"x": jnp.zeros((100,))},
        )
        spec2 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={"b": 2, "a": 1},
            input_arrays={"x": jnp.zeros((100,))},
        )
        assert spec1.cache_key == spec2.cache_key
        assert len(spec1.cache_key) == 32

    def test_different_fqn_different_key(self):
        spec1 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((100,))},
        )
        spec2 = build_specialization(
            method_fqn="test.method@2.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((100,))},
        )
        assert spec1.cache_key != spec2.cache_key

    def test_different_static_params_different_key(self):
        spec1 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={"threshold": 1000.0},
            input_arrays={"x": jnp.zeros((100,))},
        )
        spec2 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={"threshold": 2000.0},
            input_arrays={"x": jnp.zeros((100,))},
        )
        assert spec1.cache_key != spec2.cache_key

    def test_different_shapes_different_key(self):
        spec1 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((100,))},
        )
        spec2 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((200,))},
        )
        assert spec1.cache_key != spec2.cache_key

    def test_different_dtypes_different_key(self):
        spec1 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={},
            input_arrays={"x": np.zeros((100,), dtype=np.float32)},
        )
        spec2 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={},
            input_arrays={"x": np.zeros((100,), dtype=np.float64)},
        )
        assert spec1.cache_key != spec2.cache_key

    def test_different_jit_setting_different_key(self):
        spec1 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((100,))},
            jit_enabled=True,
        )
        spec2 = build_specialization(
            method_fqn="test.method@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((100,))},
            jit_enabled=False,
        )
        assert spec1.cache_key != spec2.cache_key

    def test_signature_summary(self):
        spec = build_specialization(
            method_fqn="fiscal.taxation.flat@1.0.0",
            static_params={"threshold": 1000.0},
            input_arrays={"income": jnp.zeros((100,))},
        )
        summary = spec.signature_summary
        assert "fiscal.taxation.flat@1.0.0" in summary
        assert "cpu" in summary
        assert "income" in summary


# =============================================================================
# CompilationCache Tests
# =============================================================================


class TestCompilationCache:
    def test_cache_miss_then_hit(self):
        cache = CompilationCache(max_size=10)
        spec = build_specialization(
            method_fqn="test@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((100,))},
        )

        assert cache.get(spec) is None
        assert cache.stats["misses"] == 1

        dummy_compiled = CompiledMethod(
            method_fqn="test@1.0.0",
            signature=MethodSignature(
                name="test",
                namespace="test",
                version="1.0.0",
                input_slots=frozenset(),
                output_slots=frozenset(),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_1,
            ),
            specialization=spec,
            step_fn=lambda s, p: s,
            dynamic_defaults={},
        )
        cache.put(spec, dummy_compiled)

        result = cache.get(spec)
        assert result is dummy_compiled
        assert cache.stats["hits"] == 1

    def test_lru_eviction(self):
        cache = CompilationCache(max_size=2)

        def make_spec(name: str):
            return build_specialization(
                method_fqn=name,
                static_params={},
                input_arrays={"x": jnp.zeros((10,))},
            )

        def make_compiled(name: str, spec):
            return CompiledMethod(
                method_fqn=name,
                signature=MethodSignature(
                    name="test",
                    namespace="test",
                    version="1.0.0",
                    input_slots=frozenset(),
                    output_slots=frozenset(),
                    parameters=(),
                    fidelity=FidelityLevel.LOW,
                    complexity=ComplexityClass.O_1,
                ),
                specialization=spec,
                step_fn=lambda s, p: s,
                dynamic_defaults={},
            )

        spec1 = make_spec("a@1.0.0")
        spec2 = make_spec("b@1.0.0")
        cache.put(spec1, make_compiled("a", spec1))
        cache.put(spec2, make_compiled("b", spec2))
        assert cache.stats["size"] == 2

        spec3 = make_spec("c@1.0.0")
        cache.put(spec3, make_compiled("c", spec3))

        assert cache.stats["size"] == 2
        assert cache.stats["evictions"] == 1
        assert cache.get(spec1) is None
        assert cache.get(spec2) is not None
        assert cache.get(spec3) is not None

    def test_contains(self):
        cache = CompilationCache()
        spec = build_specialization(
            method_fqn="test@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((10,))},
        )

        assert not cache.contains(spec)

        cache.put(spec, CompiledMethod(
            method_fqn="test@1.0.0",
            signature=MethodSignature(
                name="test",
                namespace="test",
                version="1.0.0",
                input_slots=frozenset(),
                output_slots=frozenset(),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_1,
            ),
            specialization=spec,
            step_fn=lambda s, p: s,
            dynamic_defaults={},
        ))

        assert cache.contains(spec)

    def test_invalidate(self):
        cache = CompilationCache()
        spec = build_specialization(
            method_fqn="test@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((10,))},
        )

        cache.put(spec, CompiledMethod(
            method_fqn="test@1.0.0",
            signature=MethodSignature(
                name="test",
                namespace="test",
                version="1.0.0",
                input_slots=frozenset(),
                output_slots=frozenset(),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_1,
            ),
            specialization=spec,
            step_fn=lambda s, p: s,
            dynamic_defaults={},
        ))

        assert cache.invalidate(spec) is True
        assert cache.contains(spec) is False
        assert cache.invalidate(spec) is False

    def test_clear(self):
        cache = CompilationCache()

        for i in range(5):
            spec = build_specialization(
                method_fqn=f"test{i}@1.0.0",
                static_params={},
                input_arrays={"x": jnp.zeros((10,))},
            )
            cache.put(spec, CompiledMethod(
                method_fqn=f"test{i}@1.0.0",
                signature=MethodSignature(
                    name="test",
                    namespace="test",
                    version="1.0.0",
                    input_slots=frozenset(),
                    output_slots=frozenset(),
                    parameters=(),
                    fidelity=FidelityLevel.LOW,
                    complexity=ComplexityClass.O_1,
                ),
                specialization=spec,
                step_fn=lambda s, p: s,
                dynamic_defaults={},
            ))

        assert cache.stats["size"] == 5
        cleared = cache.clear()
        assert cleared == 5
        assert cache.stats["size"] == 0

    def test_reset_stats(self):
        cache = CompilationCache()
        spec = build_specialization(
            method_fqn="test@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((10,))},
        )

        cache.get(spec)
        cache.reset_stats()

        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0

    def test_invalidate_all_advances_generation_and_blocks_stale_publication(self):
        cache = CompilationCache()
        spec = build_specialization(
            method_fqn="test@1.0.0",
            static_params={},
            input_arrays={"x": jnp.zeros((10,))},
        )
        token = cache.current_token()
        compiled = CompiledMethod(
            method_fqn="test@1.0.0",
            signature=MethodSignature(
                name="test",
                namespace="test",
                version="1.0.0",
                input_slots=frozenset(),
                output_slots=frozenset(),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_1,
            ),
            specialization=spec,
            step_fn=lambda s, p: s,
            dynamic_defaults={},
        )

        assert cache.put(spec, compiled, token=token) is True
        assert cache.invalidate_all() == 1
        assert cache.put(spec, compiled, token=token) is False
        assert cache.get(spec) is None
        assert cache.stats["generation"] == token.generation + 1

    def test_reset_global_cache_preserves_singleton_identity(self):
        cache = get_global_cache()
        generation = cache.stats["generation"]

        reset_global_cache()

        assert get_global_cache() is cache
        assert cache.stats["generation"] == generation + 1


# =============================================================================
# MethodCompiler Tests
# =============================================================================


class TestMethodCompiler:
    def test_compile_basic(
        self,
        registry_with_methods: MethodRegistry,
        sample_state: TaxState,
    ):
        compiler = MethodCompiler(registry=registry_with_methods)

        compiled = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 10000.0},
            sample_inputs={"income": sample_state.income},
        )

        assert compiled.method_fqn == "fiscal.taxation.flat_tax@1.0.0"
        assert compiled.compile_time_ms > 0
        assert callable(compiled.step_fn)

    def test_compile_cache_hit(
        self,
        registry_with_methods: MethodRegistry,
        sample_state: TaxState,
    ):
        compiler = MethodCompiler(registry=registry_with_methods)

        compiled1 = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 10000.0},
            sample_inputs={"income": sample_state.income},
        )

        compiled2 = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 10000.0},
            sample_inputs={"income": sample_state.income},
        )

        assert compiled1 is compiled2

    def test_compile_retries_after_generation_invalidation(
        self,
        registry_with_methods: MethodRegistry,
        sample_state: TaxState,
    ):
        class RacingCompiler(MethodCompiler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.compile_calls = 0

            def _compile_method(self, *args, **kwargs):
                self.compile_calls += 1
                if self.compile_calls == 1:
                    self._cache.invalidate_all()
                return super()._compile_method(*args, **kwargs)

        compiler = RacingCompiler(
            registry=registry_with_methods,
            cache=CompilationCache(),
        )

        compiled = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 10000.0},
            sample_inputs={"income": sample_state.income},
            jit=False,
        )

        assert compiled.method_fqn == "fiscal.taxation.flat_tax@1.0.0"
        assert compiler.compile_calls == 2
        assert compiler.cache_stats["generation"] == 1
        assert compiler.cache_stats["misses"] == 2

    def test_compile_cache_miss_different_static(
        self,
        registry_with_methods: MethodRegistry,
        sample_state: TaxState,
    ):
        compiler = MethodCompiler(registry=registry_with_methods)

        compiled1 = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 10000.0},
            sample_inputs={"income": sample_state.income},
        )

        compiled2 = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 20000.0},
            sample_inputs={"income": sample_state.income},
        )

        assert compiled1 is not compiled2
        assert compiled1.specialization.cache_key != compiled2.specialization.cache_key
        assert compiler.cache_stats["misses"] == 2

    def test_jit_execution_correctness(
        self,
        registry_with_methods: MethodRegistry,
        sample_state: TaxState,
    ):
        compiler = MethodCompiler(registry=registry_with_methods)

        compiled = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 10000.0},
            sample_inputs={"income": sample_state.income},
            jit=True,
        )

        result = compiled.step_fn(sample_state, {"rate": 0.20})

        expected_tax = jnp.maximum(sample_state.income - 10000.0, 0.0) * 0.20
        assert jnp.allclose(result.tax, expected_tax)

    def test_no_jit_execution(
        self,
        registry_with_methods: MethodRegistry,
        sample_state: TaxState,
    ):
        compiler = MethodCompiler(registry=registry_with_methods)

        compiled = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 5000.0},
            sample_inputs={"income": sample_state.income},
            jit=False,
        )

        result = compiled.step_fn(sample_state, {"rate": 0.15})

        expected_tax = jnp.maximum(sample_state.income - 5000.0, 0.0) * 0.15
        assert jnp.allclose(result.tax, expected_tax)

    def test_static_param_changes_result(
        self,
        registry_with_methods: MethodRegistry,
        sample_state: TaxState,
    ):
        compiler = MethodCompiler(registry=registry_with_methods)

        compiled_low = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 0.0},
            sample_inputs={"income": sample_state.income},
        )

        compiled_high = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 50000.0},
            sample_inputs={"income": sample_state.income},
        )

        params = {"rate": 0.20}
        result_low = compiled_low.step_fn(sample_state, params)
        result_high = compiled_high.step_fn(sample_state, params)

        assert result_low.tax.sum() > result_high.tax.sum()

    def test_dynamic_param_changes_without_recompile(
        self,
        registry_with_methods: MethodRegistry,
        sample_state: TaxState,
    ):
        compiler = MethodCompiler(registry=registry_with_methods)

        compiled = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 10000.0},
            sample_inputs={"income": sample_state.income},
        )

        result1 = compiled.step_fn(sample_state, {"rate": 0.10})
        result2 = compiled.step_fn(sample_state, {"rate": 0.30})

        assert result1.tax.sum() < result2.tax.sum()
        assert compiler.cache_stats["misses"] == 1

    def test_dynamic_param_unknown_key_raises(
        self,
        registry_with_methods: MethodRegistry,
        sample_state: TaxState,
    ):
        compiler = MethodCompiler(registry=registry_with_methods)

        compiled = compiler.compile(
            method_name="fiscal.taxation.flat_tax@1.0.0",
            params={"threshold": 10000.0},
            sample_inputs={"income": sample_state.income},
        )

        with pytest.raises(ParameterValidationError):
            compiled.step_fn(sample_state, {"rate": 0.20, "unknown": 1.0})


# =============================================================================
# Single-flight Tests
# =============================================================================


class TestSingleFlight:
    def test_single_flight_compilation(self, registry_with_methods: MethodRegistry, sample_state: TaxState):
        class CountingCompiler(MethodCompiler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.compile_calls = 0

            def _compile_method(self, *args, **kwargs):
                self.compile_calls += 1
                time.sleep(0.05)
                return super()._compile_method(*args, **kwargs)

        compiler = CountingCompiler(registry=registry_with_methods)

        def worker() -> CompiledMethod:
            return compiler.compile(
                method_name="fiscal.taxation.flat_tax@1.0.0",
                params={"threshold": 10000.0},
                sample_inputs={"income": sample_state.income},
                jit=False,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker) for _ in range(8)]
            results = [f.result() for f in futures]

        assert compiler.compile_calls == 1
        assert all(r is results[0] for r in results)


# =============================================================================
# Chain Compilation Tests
# =============================================================================


class RevenueState(NamedTuple):
    tax: jnp.ndarray
    total_tax: jnp.ndarray
    revenue: jnp.ndarray


class TestCompiledChainExecutor:
    def test_chain_shape_inference_eager(
        self,
        sample_unit: Unit,
        pure_step_factory: Callable[[Callable[[Any, Mapping[str, Any]], Any] | None], Any],
    ):
        tax_slot = SlotSpec(
            name="tax",
            slot_type=SlotType.VECTOR,
            unit=sample_unit,
            shape=("n_agents",),
        )
        total_tax_slot = SlotSpec(
            name="total_tax",
            slot_type=SlotType.SCALAR,
            unit=sample_unit,
            shape=(),
        )
        revenue_slot = SlotSpec(
            name="revenue",
            slot_type=SlotType.SCALAR,
            unit=sample_unit,
            shape=(),
        )

        def compute_sum(state: RevenueState, params: Mapping[str, Any]) -> RevenueState:
            return state._replace(total_tax=jnp.sum(state.tax))

        def compute_revenue(state: RevenueState, params: Mapping[str, Any]) -> RevenueState:
            return state._replace(revenue=state.total_tax * 0.1)

        sum_method = create_test_method(
            name="sum_tax",
            namespace="fiscal.taxation",
            version="1.0.0",
            input_slots=frozenset({tax_slot}),
            output_slots=frozenset({total_tax_slot}),
            compute_fn=compute_sum,
            pure_step_factory=pure_step_factory,
        )
        revenue_method = create_test_method(
            name="revenue",
            namespace="fiscal.budget",
            version="1.0.0",
            input_slots=frozenset({total_tax_slot}),
            output_slots=frozenset({revenue_slot}),
            compute_fn=compute_revenue,
            pure_step_factory=pure_step_factory,
        )

        registry = MethodRegistry.get_instance()
        registry.register(sum_method)
        registry.register(revenue_method)

        composer = MethodComposer(registry=registry)
        node_sum = composer.add("fiscal.taxation.sum_tax@1.0.0")
        node_rev = composer.add("fiscal.budget.revenue@1.0.0")
        composer.connect(node_sum, node_rev)
        chain = composer.build()

        sample_state = RevenueState(
            tax=jnp.ones((5,)),
            total_tax=jnp.zeros((5,)),
            revenue=jnp.zeros(()),
        )

        compiler = MethodCompiler(registry=registry)
        executor = compiler.compile_chain(chain, sample_state)

        compiled_b = executor.compiled_methods[1][1]
        input_shapes = dict(compiled_b.specialization.input_shapes)
        assert input_shapes["total_tax"].shape == ()
