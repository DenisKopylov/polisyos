from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata


def _create_simple_evaluator() -> object:
    from polisyos.lex.legal_evaluation.evaluate import evaluate_legality_impl as evaluate_simple_v1

    return evaluate_simple_v1


@dataclass(frozen=True)
class _StaticComponent:
    metadata: ComponentMetadata
    factory: Callable[[], object]

    def create(self) -> object:
        return self.factory()


lex_simple_evaluator_component = _StaticComponent(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("lex.eval.simple_v1@1.0.0"),
        kind=ComponentKind.LEX_EVALUATOR,
        abi_targets={"ir_abi": "1.x", "world_abi": "1.x"},
        domains=[],
        jurisdictions=[],
        tags=["pack:roads", "lex", "builtin"],
        capabilities=Capability.LEX_EVALUATOR | Capability.LEX_EVALUATE,
        deps=[],
        display_name="Lex Simple Evaluator",
        description="Component wrapper for simple_v1 legal evaluator.",
    ),
    factory=_create_simple_evaluator,
)


__all__ = ["lex_simple_evaluator_component"]
