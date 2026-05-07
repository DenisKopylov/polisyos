from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.core.components import DuplicateComponentIdPolicy
from polisyos.foundry.extensions import (
    bootstrap_builtin_foundry_method_family,
    bootstrap_foundry_method_registry,
    build_foundry_method_components_index,
    component_for_method,
)
from polisyos.foundry.extensions._builtin_loader import builtin_foundry_method_components
from polisyos.foundry.methods import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.registry import registry_scope


def test_builtin_loader_exposes_methods_as_components() -> None:
    components = builtin_foundry_method_components(["mechanism"])

    assert len(components) == 5
    assert str(components[0].metadata.component_id).startswith("mechanism.runtime.")
    assert all(component.metadata.kind.value == "foundry_method" for component in components)
    assert all(
        component.create().signature.fqn == str(component.metadata.component_id)
        for component in components
    )


def test_bootstrap_registers_builtin_components_through_bridge() -> None:
    index, discovery_report = build_foundry_method_components_index(
        include_builtins=False,
        include_entry_points=False,
        include_dev_scan=False,
        builtin_loaders=[
            (
                "test:mechanism_components",
                lambda: builtin_foundry_method_components(["mechanism"]),
            )
        ],
        duplicate_policy=DuplicateComponentIdPolicy.WARN,
    )

    with registry_scope() as registry:
        report = bootstrap_foundry_method_registry(registry, components_index=index)

        assert discovery_report.errors == []
        assert report.errors == []
        assert report.registered == [
            "mechanism.runtime.adaptive_agent@1.0.0",
            "mechanism.runtime.income_tax@1.0.0",
            "mechanism.runtime.labor_market@1.0.0",
            "mechanism.runtime.queue@1.0.0",
            "mechanism.runtime.tax_subsidy@1.0.0",
        ]
        assert registry.get("mechanism.runtime.income_tax@1.0.0").signature.name == "income_tax"


def test_family_bootstrap_uses_canonical_component_bridge() -> None:
    with registry_scope() as registry:
        report = bootstrap_builtin_foundry_method_family("mechanism", registry)

        assert report.errors == []
        assert report.discovery_errors == []
        assert report.components_total == 5
        assert "mechanism.runtime.queue@1.0.0" in report.registered
        assert registry.get("mechanism.runtime.queue@1.0.0").signature.name == "queue"


def test_component_for_method_is_external_author_contract() -> None:
    unit = Unit("dimensionless", "1")

    class ExternalMethod:
        signature = MethodSignature(
            name="demo",
            namespace="external.method",
            version="1.0.0",
            input_slots=frozenset({SlotSpec("x", SlotType.SCALAR, unit)}),
            output_slots=frozenset({SlotSpec("y", SlotType.SCALAR, unit)}),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1,
            backend=ComputeBackend.NUMPY,
            supports_jit=False,
            supports_vmap=False,
            supports_grad=False,
        )
        metadata = MethodMetadata(description="External demo method")

        @staticmethod
        def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> Mapping[str, Any]:
            del params
            return {"y": state["x"]}

    plugin = component_for_method(ExternalMethod, domains=["external"])

    with registry_scope() as registry:
        registered = registry.register(plugin.create())

    assert registered == "external.method.demo@1.0.0"
    assert str(plugin.metadata.component_id) == registered
    assert plugin.metadata.abi_targets == {"foundry_methods_api": ">=3.5.0,<4.0.0"}
