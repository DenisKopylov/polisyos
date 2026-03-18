"""
Tests for MethodContracts pre/postcondition system.

Verifies:
- MethodContracts dataclass is correctly defined
- ContractViolationError is raised for failing preconditions / postconditions / invariants
- Contracts are enforced in strict mode (POLISYOS_STRICT=1)
- Clean contracts pass silently
- MethodMetadata.contracts field is preserved through decorator rebuilds
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from polisyos.foundry.methods.base import (
    ComputeBackend,
    ComplexityClass,
    FidelityLevel,
    MethodContracts,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
    _check_contracts_post,
    _check_contracts_pre,
    foundry_method,
)
from polisyos.foundry.methods.exceptions import ContractViolationError


_UNIT = Unit(dimension="dimensionless", symbol="-")
_SLOT = SlotSpec("outcome", SlotType.VECTOR, _UNIT)


# ---------------------------------------------------------------------------
# MethodContracts dataclass
# ---------------------------------------------------------------------------

class TestMethodContractsDataclass:
    def test_default_empty_tuples(self):
        c = MethodContracts()
        assert c.preconditions == ()
        assert c.postconditions == ()
        assert c.invariants == ()

    def test_tuple_coercion_from_list(self):
        c = MethodContracts(preconditions=["x > 0"], postconditions=["y >= 0"])
        assert isinstance(c.preconditions, tuple)
        assert isinstance(c.postconditions, tuple)

    def test_frozen(self):
        c = MethodContracts(preconditions=("x > 0",))
        with pytest.raises((AttributeError, TypeError)):
            c.preconditions = ()  # type: ignore[misc]

    def test_string_expressions_preserved(self):
        expr = "len(state['outcome']) >= 2"
        c = MethodContracts(preconditions=(expr,))
        assert c.preconditions[0] == expr


# ---------------------------------------------------------------------------
# Contract checking helpers
# ---------------------------------------------------------------------------

class TestCheckContractsPre:
    def test_passing_precondition(self):
        contracts = MethodContracts(preconditions=("len(state['x']) >= 1",))
        # Should not raise
        _check_contracts_pre("test.method@1.0.0", contracts, {"x": [1, 2]}, {})

    def test_failing_precondition_raises(self):
        contracts = MethodContracts(preconditions=("len(state['x']) >= 10",))
        with pytest.raises(ContractViolationError) as exc_info:
            _check_contracts_pre("test.method@1.0.0", contracts, {"x": [1]}, {})
        err = exc_info.value
        assert err.contract_type == "precondition"
        assert "test.method@1.0.0" in str(err)

    def test_passing_invariant(self):
        contracts = MethodContracts(invariants=("params['alpha'] > 0",))
        _check_contracts_pre("test.method@1.0.0", contracts, {}, {"alpha": 0.1})

    def test_failing_invariant_raises(self):
        contracts = MethodContracts(invariants=("params['alpha'] > 0",))
        with pytest.raises(ContractViolationError) as exc_info:
            _check_contracts_pre("test.method@1.0.0", contracts, {}, {"alpha": -1.0})
        assert exc_info.value.contract_type == "invariant"

    def test_expression_exception_wrapped(self):
        """A contract with an expression that raises is caught and re-raised as ContractViolationError."""
        contracts = MethodContracts(preconditions=("state['missing_key'] > 0",))
        with pytest.raises(ContractViolationError) as exc_info:
            _check_contracts_pre("test.method@1.0.0", contracts, {}, {})
        assert exc_info.value.contract_type == "precondition"


class TestCheckContractsPost:
    def test_passing_postcondition(self):
        contracts = MethodContracts(postconditions=("not np.any(np.isnan(result['ate']))",))
        result = {"ate": np.array([0.1, 0.2])}
        _check_contracts_post("test.method@1.0.0", contracts, {}, {}, result)

    def test_failing_postcondition_raises(self):
        contracts = MethodContracts(postconditions=("not np.any(np.isnan(result['ate']))",))
        result = {"ate": np.array([float("nan")])}
        with pytest.raises(ContractViolationError) as exc_info:
            _check_contracts_post("test.method@1.0.0", contracts, {}, {}, result)
        assert exc_info.value.contract_type == "postcondition"

    def test_invariant_checked_post(self):
        contracts = MethodContracts(invariants=("params['alpha'] > 0",))
        with pytest.raises(ContractViolationError) as exc_info:
            _check_contracts_post("test.method@1.0.0", contracts, {}, {"alpha": 0.0}, {})
        assert exc_info.value.contract_type == "invariant"


# ---------------------------------------------------------------------------
# ContractViolationError
# ---------------------------------------------------------------------------

class TestContractViolationError:
    def test_attributes(self):
        err = ContractViolationError("ns.method@1.0.0", "precondition", "x > 0")
        assert err.method_fqn == "ns.method@1.0.0"
        assert err.contract_type == "precondition"
        assert err.expression == "x > 0"

    def test_str_contains_key_info(self):
        err = ContractViolationError("ns.method@1.0.0", "invariant", "params['k'] > 0")
        assert "ns.method@1.0.0" in str(err)
        assert "invariant" in str(err)

    def test_is_foundry_method_error(self):
        from polisyos.foundry.methods.exceptions import FoundryMethodError
        err = ContractViolationError("x@1.0.0", "precondition", "True")
        assert isinstance(err, FoundryMethodError)


# ---------------------------------------------------------------------------
# Integration: contracts enforced in POLISYOS_STRICT=1
# ---------------------------------------------------------------------------

@pytest.fixture()
def strict_env(monkeypatch):
    monkeypatch.setenv("POLISYOS_STRICT", "1")
    yield
    # Clean up any singleton state that might have strict wrapping
    from polisyos.foundry.methods.registry import MethodRegistry
    MethodRegistry.reset_instance()


class TestContractsInStrictMode:
    """These tests re-define methods at test time under strict mode."""

    def test_method_with_passing_contracts_runs(self, strict_env):
        sig = MethodSignature(
            name="contract_ok",
            namespace="test.contracts",
            version="1.0.0",
            backend=ComputeBackend.NUMPY,
            input_slots=frozenset({SlotSpec("x", SlotType.VECTOR, _UNIT)}),
            output_slots=frozenset({SlotSpec("y", SlotType.VECTOR, _UNIT)}),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1, supports_jit=False, supports_vmap=False, supports_grad=False,
        )

        @foundry_method(
            namespace="test.contracts",
            version="1.0.0",
        )
        class ContractOkMethod:
            signature = sig
            metadata = MethodMetadata(
                description="Test",
                contracts=MethodContracts(
                    preconditions=["len(state['x']) >= 1"],
                    postconditions=["len(result['y']) >= 1"],
                ),
            )

            @staticmethod
            def pure_step(state, params):
                return {"y": np.asarray(state["x"]) * 2}

        result = ContractOkMethod.pure_step({"x": [1.0, 2.0]}, {})
        assert "y" in result

    def test_method_failing_precondition_raises(self, strict_env):
        sig = MethodSignature(
            name="contract_fail_pre",
            namespace="test.contracts",
            version="1.0.0",
            backend=ComputeBackend.NUMPY,
            input_slots=frozenset({SlotSpec("x", SlotType.VECTOR, _UNIT)}),
            output_slots=frozenset({SlotSpec("y", SlotType.VECTOR, _UNIT)}),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1, supports_jit=False, supports_vmap=False, supports_grad=False,
        )

        @foundry_method(
            namespace="test.contracts",
            version="1.0.0",
        )
        class ContractFailPre:
            signature = sig
            metadata = MethodMetadata(
                description="Test",
                contracts=MethodContracts(
                    preconditions=["len(state['x']) >= 100"],  # always fails
                ),
            )

            @staticmethod
            def pure_step(state, params):
                return {"y": np.array([1.0])}

        with pytest.raises(ContractViolationError) as exc_info:
            ContractFailPre.pure_step({"x": [1.0]}, {})
        assert exc_info.value.contract_type == "precondition"

    def test_contracts_field_preserved_in_metadata(self):
        """Verify MethodMetadata.contracts is accessible after decorator rebuilds."""
        contracts = MethodContracts(preconditions=("True",))
        meta = MethodMetadata(description="test", contracts=contracts)
        assert meta.contracts is contracts

    def test_no_contracts_no_error(self, strict_env):
        """Method without contracts runs fine in strict mode."""
        sig = MethodSignature(
            name="no_contracts",
            namespace="test.contracts",
            version="1.0.0",
            backend=ComputeBackend.NUMPY,
            input_slots=frozenset(),
            output_slots=frozenset({SlotSpec("result", SlotType.SCALAR, _UNIT)}),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1, supports_jit=False, supports_vmap=False, supports_grad=False,
        )

        @foundry_method(namespace="test.contracts", version="1.0.0")
        class NoContracts:
            signature = sig
            metadata = MethodMetadata(description="No contracts")

            @staticmethod
            def pure_step(state, params):
                return {"result": 42.0}

        # Should run without error
        result = NoContracts.pure_step({}, {})
        assert result["result"] == 42.0
