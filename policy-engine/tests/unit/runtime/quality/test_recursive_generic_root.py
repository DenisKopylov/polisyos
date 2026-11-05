"""Refuse malformed generic root wiring before generation or numerical work.

These negative composition tests issue no NL scope or permission. The genuine
served test covers the actual root handoff, worker lease and persisted result.
"""

from __future__ import annotations

from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality.design_axes.coupling_composition import derive_recursive_design_graph
from polisyos.runtime.quality.generation_cycle import GenerationCycleController
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    RecursiveGenerationCycleError,
    build_default_recursive_generation_cycle_controller,
)
from tests._helpers.controlled_candidate_profile import _budget, _problem


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["missing_callback", "foreign_callback", "untyped_handoff"])
async def test_generic_root_binding_refuses_before_any_generation(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """A callback map is exact-root scoped and cannot admit an untyped handoff."""
    calls: list[object] = []

    async def must_not_generate(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        raise AssertionError("invalid root composition reached N4")

    monkeypatch.setattr(GenerationCycleController, "_generate_node", must_not_generate)
    store = FileSystemCAS(tmp_path / "root-binding")
    controller = build_default_recursive_generation_cycle_controller(
        promotion_runtime=PromotionRuntime(store=store), repo_root=tmp_path
    )
    graph = derive_recursive_design_graph(
        design_ref="design://root-binding",
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="test://root-binding",
    )
    root = graph.root_design_ref
    handoffs = {} if case == "foreign_callback" else {root: object()}
    callbacks = {} if case == "missing_callback" else {root: lambda: True}
    code = (
        "recursive_generic_root_binding_mismatch"
        if case == "untyped_handoff"
        else "recursive_generic_root_currentness_denominator_mismatch"
    )
    with pytest.raises(RecursiveGenerationCycleError, match=code):
        await controller.run(
            graph,
            problems_by_node={root: _problem("generic_root_binding")},
            budget_state=_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=0, max_nodes=1, min_cycles_per_leaf=1, max_cycles_per_leaf=1
            ),
            generic_simulation_handoffs_by_node=handoffs,
            generic_simulation_currentness_resolvers_by_node=callbacks,
            execution_intents_by_node={root: "simulate_only"},
        )
    assert calls == []
