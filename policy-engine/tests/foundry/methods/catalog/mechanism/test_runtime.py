from __future__ import annotations

import numpy as np
import pytest


def _method_or_skip(registry, fqn):
    from polisyos.foundry.methods.catalog import ensure_all_methods_registered
    ensure_all_methods_registered(registry)
    try:
        return registry.get(fqn)
    except Exception:
        pytest.skip(f"{fqn} not registered")


def _minimal_runtime_state():
    """Create a GlobalState with .agents attribute to pass _coerce_runtime_state."""
    pytest.importorskip("jax")
    from polisyos.foundry.agent_sim.state import GlobalState
    return GlobalState.empty(n_agents=4, seed=42, max_agents=4)


class TestTaxSubsidyRuntime:
    def test_basic(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "mechanism.runtime.tax_subsidy@1.0.0")
        state = _minimal_runtime_state()
        result = method.pure_step(state, {"rate": 0.2})
        assert isinstance(result, dict)

    def test_output_has_result_key(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "mechanism.runtime.tax_subsidy@1.0.0")
        state = _minimal_runtime_state()
        result = method.pure_step(state, {"rate": 0.3})
        assert "result" in result

    def test_result_contains_mechanism_type(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "mechanism.runtime.tax_subsidy@1.0.0")
        state = _minimal_runtime_state()
        result = method.pure_step(state, {"rate": 0.1})
        assert result["result"]["mechanism_type"] == "tax_subsidy"


class TestMechanismRegistration:
    """Verify all mechanism runtime methods are registered in the catalog."""

    @pytest.mark.parametrize("fqn", [
        "mechanism.runtime.tax_subsidy@1.0.0",
        "mechanism.runtime.income_tax@1.0.0",
        "mechanism.runtime.labor_market@1.0.0",
        "mechanism.runtime.queue@1.0.0",
        "mechanism.runtime.adaptive_agent@1.0.0",
    ])
    def test_registered(self, isolated_registry, fqn) -> None:
        from polisyos.foundry.methods.catalog import ensure_all_methods_registered
        ensure_all_methods_registered(isolated_registry)
        method = isolated_registry.get(fqn)
        assert hasattr(method, "pure_step")

    def test_tax_subsidy_has_signature(self, isolated_registry) -> None:
        method = _method_or_skip(isolated_registry, "mechanism.runtime.tax_subsidy@1.0.0")
        assert hasattr(method, "signature")
