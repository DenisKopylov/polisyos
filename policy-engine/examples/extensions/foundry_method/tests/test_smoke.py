from __future__ import annotations

from polisyos_foundry_method_example import weighted_average_plugin

from polisyos.foundry.methods.registry import MethodRegistry


def test_weighted_average_plugin_registers_and_runs() -> None:
    MethodRegistry.reset_instance()
    registry = MethodRegistry.get_instance()

    method_class = weighted_average_plugin.create()
    registry.register(method_class)

    resolved = registry.get("example.summary.weighted_average@1.0.0")
    result = resolved.pure_step({"values": [1, 3, 5], "weights": [1, 2, 1]}, {})
    if result != {"mean": 3.0}:
        raise AssertionError(result)

    MethodRegistry.reset_instance()
