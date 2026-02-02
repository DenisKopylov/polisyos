"""
Self-tests for the Testing Infrastructure (Phase 3.8).
"""
from __future__ import annotations

from typing import Any

import chex
import jax.numpy as jnp

from polisyos.foundry.methods import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
)
from polisyos.foundry.methods.base import Unit
from polisyos.foundry.methods.testing import (
    CheckCategory,
    GoldenContext,
    GoldenRecord,
    GoldenStore,
    MethodTestSuite,
    create_sample_params,
    create_sample_state,
    hash_pytree,
)
from polisyos.foundry.methods.testing.golden import VerificationStatus


# =============================================================================
# Test Fixtures
# =============================================================================


@chex.dataclass(frozen=True)
class SimpleState:
    """Minimal state for testing."""

    value: jnp.ndarray


class IdentityMethod:
    """Minimal valid method for testing."""

    signature = MethodSignature(
        name="identity",
        namespace="test.infra",
        version="1.0.0",
        input_slots=frozenset(
            {SlotSpec(name="input", slot_type=SlotType.SCALAR, unit=Unit("none", "1"))}
        ),
        output_slots=frozenset(
            {SlotSpec(name="output", slot_type=SlotType.SCALAR, unit=Unit("none", "1"))}
        ),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )

    metadata = MethodMetadata(
        description="Identity transformation for testing",
        tags=frozenset({"test"}),
    )

    @staticmethod
    def pure_step(state: SimpleState, params: dict[str, Any]) -> SimpleState:
        return state


class BrokenMethod:
    """Method missing pure_step staticmethod decorator."""

    signature = MethodSignature(
        name="broken",
        namespace="test.infra",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )

    metadata = MethodMetadata(description="Broken method")

    # Missing @staticmethod
    def pure_step(self, state, params):
        return state


class NaNMethod:
    """Method that produces NaN values."""

    signature = MethodSignature(
        name="nan_producer",
        namespace="test.infra",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        supports_grad=False,
    )

    metadata = MethodMetadata(description="Produces NaN")

    @staticmethod
    def pure_step(state: SimpleState, params: dict[str, Any]) -> SimpleState:
        return SimpleState(value=jnp.array(float("nan")))


# =============================================================================
# MethodTestSuite Tests
# =============================================================================


class TestMethodTestSuite:
    def test_valid_method_passes_all_checks(self):
        suite = MethodTestSuite(IdentityMethod)
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}

        result = suite.run_all(state, params)

        assert result.passed, result.summary()
        assert result.passed_count > 0
        assert result.failed_count == 0

    def test_detects_non_static_pure_step(self):
        suite = MethodTestSuite(BrokenMethod)
        checks = suite.check_protocol()

        static_check = next((c for c in checks if c.name == "pure_step_is_static"), None)
        assert static_check is not None
        assert not static_check.passed
        assert "staticmethod" in static_check.message.lower()

    def test_detects_nan_in_output(self):
        suite = MethodTestSuite(NaNMethod)
        state = SimpleState(value=jnp.array(1.0))
        params = {}

        checks = suite.check_numerical_stability(state, params)

        finite_check = next((c for c in checks if c.name == "output_finite"), None)
        assert finite_check is not None
        assert not finite_check.passed

    def test_determinism_check_passes_for_pure_function(self):
        suite = MethodTestSuite(IdentityMethod)
        state = SimpleState(value=jnp.array(42.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}

        checks = suite.check_determinism(state, params, n_runs=5)

        assert len(checks) >= 1
        assert all(c.passed for c in checks)

    def test_quick_check_returns_boolean(self):
        suite = MethodTestSuite(IdentityMethod)
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}

        result = suite.quick_check(state, params)

        assert isinstance(result, bool)
        assert result is True

    def test_result_summary_includes_fqn(self):
        suite = MethodTestSuite(IdentityMethod)
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}

        result = suite.run_all(state, params)

        assert "test.infra.identity@1.0.0" in result.summary()

    def test_checks_have_timing_info(self):
        suite = MethodTestSuite(IdentityMethod)
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}

        result = suite.run_all(state, params)

        timed_checks = [c for c in result.checks if c.duration_ms is not None]
        assert len(timed_checks) > 0

    def test_arrays_only_inputs_fail_on_python_scalars(self):
        suite = MethodTestSuite(IdentityMethod)
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": 0.1}

        checks = suite.check_arrays_only_inputs(state, params)
        assert any(c.name == "arrays_only_inputs" and not c.passed for c in checks)

    def test_vmap_skips_without_axes(self):
        suite = MethodTestSuite(IdentityMethod)
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}

        checks = suite.check_jax_ops(state, params, skip_grad=True)
        vmap_check = next((c for c in checks if c.name == "vmap_works"), None)
        assert vmap_check is not None
        assert vmap_check.passed
        assert "skipped" in vmap_check.message.lower()


# =============================================================================
# Golden Record Tests
# =============================================================================


class TestGoldenContext:
    def test_current_captures_environment(self):
        ctx = GoldenContext.current("test.method@1.0.0")

        assert ctx.method_fqn == "test.method@1.0.0"
        assert ctx.backend.platform in ("cpu", "gpu", "tpu")
        assert ctx.jax_version

    def test_matches_same_platform_precision(self):
        ctx1 = GoldenContext.current("test@1.0.0", precision="float32")
        ctx2 = GoldenContext.current("test@1.0.0", precision="float32")

        assert ctx1.matches(ctx2)

    def test_mismatch_different_precision(self):
        ctx1 = GoldenContext.current("test@1.0.0", precision="float32")
        ctx2 = GoldenContext.current("test@1.0.0", precision="float64")

        assert not ctx1.matches(ctx2)

    def test_serialization_roundtrip(self):
        ctx = GoldenContext.current("test@1.0.0")

        restored = GoldenContext.from_dict(ctx.to_dict())

        assert ctx.method_fqn == restored.method_fqn
        assert ctx.backend.platform == restored.backend.platform


class TestHashPytree:
    def test_identical_arrays_same_hash(self):
        a = {"x": jnp.array([1.0, 2.0, 3.0])}
        b = {"x": jnp.array([1.0, 2.0, 3.0])}

        assert hash_pytree(a) == hash_pytree(b)

    def test_different_arrays_different_hash(self):
        a = {"x": jnp.array([1.0, 2.0, 3.0])}
        b = {"x": jnp.array([1.0, 2.0, 4.0])}

        assert hash_pytree(a) != hash_pytree(b)

    def test_hash_is_deterministic(self):
        state = SimpleState(value=jnp.array([1.0, 2.0]))

        hashes = [hash_pytree(state) for _ in range(10)]

        assert all(h == hashes[0] for h in hashes)

    def test_hash_is_order_independent_for_dicts(self):
        a = {"x": jnp.array(1.0), "y": jnp.array(2.0)}
        b = {"y": jnp.array(2.0), "x": jnp.array(1.0)}

        assert hash_pytree(a) == hash_pytree(b)

    def test_hash_length(self):
        h = hash_pytree({"x": jnp.array(1.0)})

        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)


class TestGoldenRecord:
    def test_create_captures_hashes(self):
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}
        output = SimpleState(value=jnp.array(2.0))

        record = GoldenRecord.create(
            "test.method@1.0.0",
            state,
            params,
            output,
        )

        assert len(record.input_hash) == 32
        assert len(record.output_hash) == 32
        assert record.input_hash != record.output_hash

    def test_verify_passes_for_identical_output(self):
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}
        output = SimpleState(value=jnp.array(2.0))

        record = GoldenRecord.create("test@1.0.0", state, params, output)

        result = record.verify(state, params, output)

        assert result.passed
        assert result.status == VerificationStatus.PASSED

    def test_verify_fails_for_different_output(self):
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}
        original_output = SimpleState(value=jnp.array(2.0))
        different_output = SimpleState(value=jnp.array(3.0))

        record = GoldenRecord.create("test@1.0.0", state, params, original_output)

        result = record.verify(state, params, different_output, strict_output=True)

        assert not result.passed
        assert result.status == VerificationStatus.FAILED_OUTPUT

    def test_verify_tolerance_passes_for_small_change(self):
        state = SimpleState(value=jnp.array(1.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}
        original_output = SimpleState(value=jnp.array(1.0))
        close_output = SimpleState(value=jnp.array(1.0005))

        record = GoldenRecord.create(
            "test@1.0.0",
            state,
            params,
            original_output,
            rtol=0.0,
            atol=1e-3,
        )

        result = record.verify(state, params, close_output)

        assert result.passed
        assert result.status == VerificationStatus.PASSED

    def test_json_roundtrip(self):
        state = SimpleState(value=jnp.array(1.0))
        params = {}
        output = state

        record = GoldenRecord.create("test@1.0.0", state, params, output)
        json_str = record.to_json()
        restored = GoldenRecord.from_json(json_str)

        assert record.input_hash == restored.input_hash
        assert record.output_hash == restored.output_hash
        assert record.context.method_fqn == restored.context.method_fqn


class TestGoldenStore:
    def test_save_and_load(self, temp_golden_store: GoldenStore):
        state = SimpleState(value=jnp.array(1.0))
        params = {}
        output = state

        record = GoldenRecord.create("test.store@1.0.0", state, params, output)
        temp_golden_store.save(record)

        loaded = temp_golden_store.load(
            "test.store@1.0.0", record.input_hash, context=record.context
        )

        assert loaded is not None
        assert loaded.input_hash == record.input_hash

    def test_exists_returns_correct_status(self, temp_golden_store: GoldenStore):
        state = SimpleState(value=jnp.array(1.0))
        params = {}
        output = state

        record = GoldenRecord.create("exists.test@1.0.0", state, params, output)
        temp_golden_store.save(record)

        assert temp_golden_store.exists(
            "exists.test@1.0.0", record.input_hash, context=record.context
        )

    def test_verify_no_record(self, temp_golden_store: GoldenStore):
        state = SimpleState(value=jnp.array(1.0))

        result = temp_golden_store.verify("missing@1.0.0", state, {}, state)

        assert result.status == VerificationStatus.NO_RECORD

    def test_delete_removes_record(self, temp_golden_store: GoldenStore):
        state = SimpleState(value=jnp.array(1.0))
        record = GoldenRecord.create("delete.test@1.0.0", state, {}, state)
        temp_golden_store.save(record)

        assert temp_golden_store.exists(
            "delete.test@1.0.0", record.input_hash, context=record.context
        )

        deleted = temp_golden_store.delete(
            "delete.test@1.0.0", record.input_hash, context=record.context
        )

        assert deleted
        assert not temp_golden_store.exists(
            "delete.test@1.0.0", record.input_hash, context=record.context
        )

    def test_list_records(self, temp_golden_store: GoldenStore):
        state = SimpleState(value=jnp.array(1.0))

        for name in ["a.method@1.0.0", "b.method@2.0.0"]:
            record = GoldenRecord.create(name, state, {}, state)
            temp_golden_store.save(record)

        records = temp_golden_store.list_records()

        assert len(records) == 2


# =============================================================================
# Fixtures Tests
# =============================================================================


class TestFixtures:
    def test_create_fiscal_state(self):
        state = create_sample_state("fiscal", n_agents=50)

        assert hasattr(state, "income")
        assert state.income.shape == (50,)
        assert jnp.all(state.income > 0)

    def test_create_agent_state(self):
        state = create_sample_state("agent", n_agents=100, n_dims=3)

        assert hasattr(state, "positions")
        assert state.positions.shape == (100, 3)

    def test_create_scalar_state(self):
        state = create_sample_state("scalar")

        assert hasattr(state, "value")
        assert state.value.shape == ()

    def test_create_sample_params(self):
        params = create_sample_params("fiscal", rate=jnp.array(0.25, dtype=jnp.float32))

        assert "rate" in params
        assert float(params["rate"]) == 0.25

    def test_seed_is_deterministic(self):
        s1 = create_sample_state("fiscal", n_agents=100, seed=42)
        s2 = create_sample_state("fiscal", n_agents=100, seed=42)

        assert jnp.allclose(s1.income, s2.income)


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    def test_full_workflow(self, temp_golden_store: GoldenStore):
        suite = MethodTestSuite(IdentityMethod)
        state = SimpleState(value=jnp.array(42.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}

        result = suite.run_all(state, params)
        assert result.passed

        output = IdentityMethod.pure_step(state, params)
        temp_golden_store.update_or_create(
            IdentityMethod.signature.fqn,
            state,
            params,
            output,
        )

        verification = temp_golden_store.verify(
            IdentityMethod.signature.fqn,
            state,
            params,
            output,
        )

        assert verification.passed

    def test_regression_detection(self, temp_golden_store: GoldenStore):
        state = SimpleState(value=jnp.array(42.0))
        params = {"rate": jnp.array(0.1, dtype=jnp.float32)}
        original_output = SimpleState(value=jnp.array(42.0))

        temp_golden_store.update_or_create(
            "regression.test@1.0.0",
            state,
            params,
            original_output,
        )

        regressed_output = SimpleState(value=jnp.array(43.0))

        verification = temp_golden_store.verify(
            "regression.test@1.0.0",
            state,
            params,
            regressed_output,
            strict_output=True,
        )

        assert not verification.passed
        assert "regression" in verification.message.lower() or verification.status == VerificationStatus.FAILED_OUTPUT
