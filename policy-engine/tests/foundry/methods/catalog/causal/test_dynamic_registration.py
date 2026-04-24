"""Smoke tests: verify all Phase 3 dynamic causal methods are registered."""

from __future__ import annotations

import inspect

import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


_DYNAMIC_FQNS = [
    "causal.dynamic.g_computation.parametric_g_formula@1.0.0",
    "causal.dynamic.ice_g_formula.ice_g_formula@1.0.0",
    "causal.dynamic.ltmle.ltmle@1.0.0",
    "causal.dynamic.snmm.snmm_g_estimation@1.0.0",
    "causal.dynamic.q_learning.q_learning@1.0.0",
    "causal.dynamic.a_learning.a_learning@1.0.0",
    "causal.dynamic.owl.owl@1.0.0",
    "causal.dynamic.dr_dtr.dr_dtr@1.0.0",
    "causal.dynamic.ope.ope@1.0.0",
    "causal.dynamic.causal_bandit.causal_bandit@1.0.0",
]


@pytest.mark.parametrize("fqn", _DYNAMIC_FQNS)
def test_method_is_registered(fqn: str) -> None:
    """Each Phase 3 method must be retrievable by its FQN after registration."""
    ensure_causal_methods_registered()
    reg = MethodRegistry.get_instance()
    method_cls = reg.get(fqn)
    assert method_cls is not None, f"Method not found: {fqn}"


@pytest.mark.parametrize("fqn", _DYNAMIC_FQNS)
def test_pure_step_is_staticmethod(fqn: str) -> None:
    """pure_step must be a staticmethod (Law F: no self, pure function)."""
    ensure_causal_methods_registered()
    reg = MethodRegistry.get_instance()
    method_cls = reg.get(fqn)
    assert method_cls is not None
    member = inspect.getattr_static(method_cls, "pure_step")
    assert isinstance(member, staticmethod), (
        f"{fqn}.pure_step must be a staticmethod, got {type(member).__name__}"
    )


@pytest.mark.parametrize("fqn", _DYNAMIC_FQNS)
def test_signature_has_treatment_sequence_slot(fqn: str) -> None:
    """All dynamic methods must declare treatment_sequence as an input slot."""
    ensure_causal_methods_registered()
    reg = MethodRegistry.get_instance()
    method_cls = reg.get(fqn)
    assert method_cls is not None
    slot_names = {s.name for s in method_cls.signature.input_slots}
    assert "treatment_sequence" in slot_names, (
        f"{fqn} is missing 'treatment_sequence' input slot. Got: {slot_names}"
    )


@pytest.mark.parametrize("fqn", _DYNAMIC_FQNS)
def test_namespace_starts_with_causal_dynamic(fqn: str) -> None:
    """All Phase 3 methods must be under the causal.dynamic namespace."""
    ensure_causal_methods_registered()
    reg = MethodRegistry.get_instance()
    method_cls = reg.get(fqn)
    assert method_cls is not None
    assert method_cls.signature.namespace.startswith("causal.dynamic"), (
        f"{fqn} namespace should start with 'causal.dynamic', "
        f"got {method_cls.signature.namespace!r}"
    )


def test_all_ten_dynamic_methods_registered() -> None:
    """Bulk check: all 10 Phase 3 methods registered in one call."""
    ensure_causal_methods_registered()
    reg = MethodRegistry.get_instance()
    missing = [fqn for fqn in _DYNAMIC_FQNS if reg.get(fqn) is None]
    assert not missing, f"Missing dynamic methods: {missing}"
