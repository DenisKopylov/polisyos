from __future__ import annotations

from polisyos.foundry.methods.base import SlotType
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


_AFFINITY_TAGS = {
    "panel",
    "cross-section",
    "time-series",
    "spatial",
    "network",
    "survey",
    "optimization",
    "structural",
    "tabular",
}
_TASK_TAGS = {
    "estimation",
    "diagnostics",
    "forecasting",
    "simulation",
    "discovery",
    "feature-selection",
    "uncertainty",
    "policy-learning",
}


def test_all_registered_methods_have_affinity_task_tags_and_shaped_tensor_slots() -> None:
    MethodRegistry.reset_instance()
    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()

    for signature in registry.query():
        method_cls = registry.get(signature.fqn)
        tags = set(method_cls.metadata.tags)
        assert tags & _AFFINITY_TAGS, signature.fqn
        assert tags & _TASK_TAGS, signature.fqn

        for slot in tuple(signature.input_slots) + tuple(signature.output_slots):
            if slot.slot_type is SlotType.SCALAR:
                continue
            assert slot.shape is not None, (signature.fqn, slot.name)


def test_registry_queries_by_affinity_and_task_tags_return_expected_methods() -> None:
    MethodRegistry.reset_instance()
    ensure_all_methods_registered()
    registry = MethodRegistry.get_instance()

    panel_diagnostics = {sig.fqn for sig in registry.query(tags={"panel", "diagnostics"})}
    tabular_estimators = {sig.fqn for sig in registry.query(tags={"tabular", "estimation"})}
    optimization_methods = {sig.fqn for sig in registry.query(tags={"optimization", "estimation"})}
    structural_methods = {sig.fqn for sig in registry.query(tags={"structural", "estimation"})}

    assert "causal.diagnostics.parallel_trends_check@1.0.0" in panel_diagnostics
    assert "econometrics.diagnostics.hausman_test@1.0.0" in panel_diagnostics
    assert "ml.regression.elastic_net@1.0.0" in tabular_estimators
    assert "bayesian.regression.linear_regression@1.0.0" in tabular_estimators
    assert "optimization.linear.resource_lp@1.0.0" in optimization_methods
    assert "optimization.integer.budget_milp@1.0.0" in optimization_methods
    assert "optimization.io.leontief_io@1.0.0" in optimization_methods
    assert "causal.transport.symbolic_identify@1.0.0" in structural_methods
