from __future__ import annotations

from typing import Any, Mapping

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.discovery import bootstrap_registry
from polisyos.foundry.methods.registry import MethodRegistry


def _legacy_method_class() -> type:
    unit = Unit("none", "1")

    class LegacyMethod:
        signature = MethodSignature(
            name="sample",
            namespace="legacy.group",
            version="1.0.0",
            input_slots=frozenset({SlotSpec("x", SlotType.SCALAR, unit)}),
            output_slots=frozenset({SlotSpec("y", SlotType.SCALAR, unit)}),
            parameters=(),
            fidelity=FidelityLevel.LOW,
            complexity=ComplexityClass.O_1,
        )
        metadata = MethodMetadata(
            description="legacy test method",
            tags=frozenset({"legacy"}),
        )

        @staticmethod
        def pure_step(state: Any, params: Mapping[str, Any]) -> Any:
            del params
            return state

    return LegacyMethod


class _FakeEntryPoint:
    def __init__(self, *, name: str, value: str, loaded: object) -> None:
        self.name = name
        self.value = value
        self._loaded = loaded

    def load(self) -> object:
        return self._loaded


def test_bootstrap_registry_legacy_adapter_via_components(monkeypatch) -> None:
    MethodRegistry.reset_instance()
    registry = MethodRegistry.get_instance()

    legacy_method = _legacy_method_class()

    def _entry_points(*, group: str | None = None):
        if group == "my.legacy.group":
            return [
                _FakeEntryPoint(
                    name="legacy.sample",
                    value="legacy.sample:method",
                    loaded=legacy_method,
                )
            ]
        return []

    monkeypatch.setattr(
        "polisyos.foundry.methods.discovery.importlib.metadata.entry_points",
        _entry_points,
    )

    with pytest.warns(DeprecationWarning):
        report = bootstrap_registry(
            registry=registry,
            entry_point_group="my.legacy.group",
        )

    assert report.errors == []
    assert "legacy.group.sample@1.0.0" in report.registered

    resolved = registry.get("legacy.group.sample@1.0.0")
    assert resolved.signature.fqn == "legacy.group.sample@1.0.0"

    MethodRegistry.reset_instance()
