"""
Test fixtures for Foundry Methods test suite.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, NamedTuple

import pytest

os.environ["JAX_PLATFORM_NAME"] = "cpu"
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
os.environ["JAX_ENABLE_X64"] = "true"

try:
    import jax.numpy as jnp
except ModuleNotFoundError:  # pragma: no cover - local environments may be NumPy-only
    import numpy as jnp

from polisyos.foundry.methods import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.types.units import Units

try:
    from polisyos.foundry.methods.testing import (
        GoldenStore,
        GoldenVerificationResult,
        MethodTestSuite,
        VerificationStatus,
        create_sample_params,
        create_sample_state,
    )
except ModuleNotFoundError:  # pragma: no cover - optional test-only dependencies may be absent

    class GoldenStore:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("polisyos.foundry.methods.testing dependencies are unavailable")

    class GoldenVerificationResult:  # type: ignore[no-redef]
        pass

    class MethodTestSuite:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("polisyos.foundry.methods.testing dependencies are unavailable")

    class VerificationStatus:  # type: ignore[no-redef]
        PASSED = "passed"

    def create_sample_params(*_args: Any, **_kwargs: Any) -> Any:  # type: ignore[no-redef]
        raise RuntimeError("polisyos.foundry.methods.testing dependencies are unavailable")

    def create_sample_state(*_args: Any, **_kwargs: Any) -> Any:  # type: ignore[no-redef]
        raise RuntimeError("polisyos.foundry.methods.testing dependencies are unavailable")


@pytest.fixture
def sample_unit() -> Unit:
    return Units.UAH


@pytest.fixture
def custom_unit() -> Unit:
    return Unit("energy", "kWh", scale=1.0)


@pytest.fixture
def pure_step_factory() -> Callable[[Callable[[Any, Mapping[str, Any]], Any] | None], Any]:
    """Create a @staticmethod-compatible pure_step for dynamic test classes."""

    def _factory(
        compute_fn: Callable[[Any, Mapping[str, Any]], Any] | None = None,
    ) -> Any:
        if compute_fn is None:

            def _identity(state: Any, params: Mapping[str, Any]) -> Any:
                del params
                return state

            return staticmethod(_identity)
        return staticmethod(compute_fn)

    return _factory


@pytest.fixture
def income_slot(sample_unit: Unit) -> SlotSpec:
    return SlotSpec(
        name="gross_income",
        slot_type=SlotType.VECTOR,
        unit=sample_unit,
        shape=("n_agents",),
        description="Gross income per agent",
        bounds=(0.0, None),
    )


@pytest.fixture
def tax_slot(sample_unit: Unit) -> SlotSpec:
    return SlotSpec(
        name="tax_due",
        slot_type=SlotType.VECTOR,
        unit=sample_unit,
        shape=("n_agents",),
        description="Tax amount due per agent",
        bounds=(0.0, None),
    )


@pytest.fixture
def rate_slot() -> SlotSpec:
    return SlotSpec(
        name="effective_rate",
        slot_type=SlotType.VECTOR,
        unit=Units.PERCENT,
        shape=("n_agents",),
        description="Effective tax rate per agent",
    )


@pytest.fixture
def scalar_slot() -> SlotSpec:
    return SlotSpec(
        name="total_revenue",
        slot_type=SlotType.SCALAR,
        unit=Units.UAH,
        shape=(),
        description="Total tax revenue",
    )


@pytest.fixture
def rate_param() -> ParameterSpec:
    return ParameterSpec(
        name="tax_rate",
        default=0.18,
        is_static=False,
        bounds=(0.0, 1.0),
        description="Flat tax rate",
    )


@pytest.fixture
def static_param() -> ParameterSpec:
    return ParameterSpec(
        name="n_brackets",
        default=5,
        is_static=True,
        bounds=(1, 20),
        description="Number of tax brackets",
    )


@pytest.fixture
def array_param() -> ParameterSpec:
    return ParameterSpec(
        name="bracket_rates",
        default=jnp.array([0.0, 0.18, 0.20, 0.22, 0.25]),
        is_static=False,
        description="Tax rates per bracket",
    )


@pytest.fixture
def flat_tax_signature(
    income_slot: SlotSpec,
    tax_slot: SlotSpec,
    rate_param: ParameterSpec,
) -> MethodSignature:
    return MethodSignature(
        name="flat_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot}),
        parameters=(rate_param,),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_N,
        supports_jit=True,
        supports_vmap=True,
        supports_grad=True,
    )


@pytest.fixture
def progressive_tax_signature(
    income_slot: SlotSpec,
    tax_slot: SlotSpec,
    rate_slot: SlotSpec,
    static_param: ParameterSpec,
    array_param: ParameterSpec,
) -> MethodSignature:
    return MethodSignature(
        name="progressive_tax",
        namespace="fiscal.taxation",
        version="1.0.0",
        input_slots=frozenset({income_slot}),
        output_slots=frozenset({tax_slot, rate_slot}),
        parameters=(static_param, array_param),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N,
        requires=frozenset(),
        conflicts_with=frozenset({"fiscal.taxation.flat_tax@1.0.0"}),
    )


@pytest.fixture
def minimal_signature() -> MethodSignature:
    return MethodSignature(
        name="noop",
        namespace="test",
        version="1.0.0",
        input_slots=frozenset(),
        output_slots=frozenset(),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )


@pytest.fixture
def sample_metadata() -> MethodMetadata:
    return MethodMetadata(
        description="A flat tax applies the same rate to all income levels.",
        tags=frozenset({"taxation", "fiscal", "simple"}),
        citations=("smith2020taxation", "jones2019policy"),
        equations={"tax": r"T = r * Y"},
    )


class FlatTaxState(NamedTuple):
    income: jnp.ndarray
    tax_due: jnp.ndarray


@pytest.fixture
def sample_state() -> FlatTaxState:
    return FlatTaxState(
        income=jnp.array([1000.0, 2000.0, 3000.0]),
        tax_due=jnp.zeros(3),
    )


@pytest.fixture
def sample_params() -> dict[str, Any]:
    return {"tax_rate": jnp.array(0.18, dtype=jnp.float32)}


@pytest.fixture
def valid_method_class(flat_tax_signature: MethodSignature):
    class FlatTax:
        signature = flat_tax_signature
        metadata = MethodMetadata(
            description="Flat tax implementation",
            tags=frozenset({"test"}),
        )

        @staticmethod
        def pure_step(state: FlatTaxState, params: dict[str, Any]) -> FlatTaxState:
            tax = state.income * params["tax_rate"]
            return state._replace(tax_due=tax)

    return FlatTax


# =============================================================================
# Testing Infrastructure Fixtures (Phase 3.8)
# =============================================================================


@pytest.fixture(scope="session")
def methods_test_root() -> Path:
    """Absolute path to tests/foundry/methods/."""
    return Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def golden_records_path(methods_test_root: Path) -> Path:
    """Path to golden records directory."""
    path = methods_test_root / "golden_records"
    path.mkdir(exist_ok=True)
    return path


@pytest.fixture(scope="session")
def golden_store(golden_records_path: Path) -> GoldenStore:
    """Session-scoped golden store for shared golden records."""
    return GoldenStore(golden_records_path)


@pytest.fixture
def temp_golden_store(tmp_path: Path) -> GoldenStore:
    """Function-scoped golden store for isolated tests."""
    return GoldenStore(tmp_path / "golden_records")


@pytest.fixture
def sample_fiscal_state():
    return create_sample_state("fiscal", n_agents=100, seed=42)


@pytest.fixture
def sample_fiscal_params():
    return create_sample_params("fiscal")


@pytest.fixture
def sample_agent_state():
    return create_sample_state("agent", n_agents=100, seed=42)


@pytest.fixture
def sample_agent_params():
    return create_sample_params("agent")


@pytest.fixture
def sample_scalar_state():
    return create_sample_state("scalar", seed=42)


@pytest.fixture
def sample_scalar_params():
    return create_sample_params("scalar")


@pytest.fixture
def golden_check(
    golden_store: GoldenStore,
) -> Callable[[str, Any, dict[str, Any], Any], GoldenVerificationResult]:
    """
    Fixture providing a callable for golden record verification.

    Environment variables:
        GOLDEN_UPDATE=1: Update golden records instead of verifying
        GOLDEN_STRICT=1: Require exact output hash match
    """

    def check(
        method_fqn: str,
        state: Any,
        params: dict[str, Any],
        output: Any,
        *,
        update: bool = False,
        strict_output: bool | None = None,
    ) -> GoldenVerificationResult:
        env_update = os.environ.get("GOLDEN_UPDATE", "").lower() in ("1", "true", "yes")
        if env_update:
            update = True

        if strict_output is None:
            strict_output = os.environ.get("GOLDEN_STRICT", "").lower() in ("1", "true", "yes")

        if update:
            record, was_existing = golden_store.update_or_create(method_fqn, state, params, output)
            action = "Updated" if was_existing else "Created"
            return GoldenVerificationResult(
                status=VerificationStatus.PASSED,
                message=f"{action} golden record for {method_fqn}",
                expected_hash=record.output_hash,
                actual_hash=record.output_hash,
            )

        return golden_store.verify(
            method_fqn,
            state,
            params,
            output,
            strict_output=strict_output,
        )

    return check


@pytest.fixture
def method_suite(valid_method_class) -> MethodTestSuite:
    return MethodTestSuite(valid_method_class)


@pytest.fixture
def assert_suite_passes():
    def _assert(method_class, state: Any, params: dict[str, Any], *, skip_grad: bool = False):
        suite = MethodTestSuite(method_class)
        result = suite.run_all(state, params, skip_grad=skip_grad)
        if not result.passed:
            failures = result.failures()
            failure_msgs = "\n".join(f"  - {f}" for f in failures)
            raise AssertionError(
                f"Method {result.method_fqn} failed {len(failures)} checks:\n{failure_msgs}"
            )
        return result

    return _assert


@pytest.fixture
def isolated_registry():
    """
    Provide an isolated MethodRegistry for the duration of one test.

    Uses ``registry_scope()`` so the global singleton is never touched and
    tests can run safely in parallel. The isolated registry is populated with
    the catalog so property-style tests exercise real registrations instead of
    silently converting missing setup into coverage-debt skips.
    """
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    from polisyos.foundry.methods.registry import registry_scope

    with registry_scope() as reg:
        ensure_all_methods_registered(reg)
        yield reg


# Alias: preferred name for new tests
fresh_registry = isolated_registry
