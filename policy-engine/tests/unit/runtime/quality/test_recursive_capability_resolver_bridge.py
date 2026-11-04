"""Exercise the composed N7 resolver through the real recursive leaf boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_requirement import compiled_requirements_for_world_slot
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from polisyos.runtime.quality.design_axes.coupling_composition import derive_recursive_design_graph
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    GenerationCycleError,
)
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    build_default_recursive_generation_cycle_controller,
)
from tests._helpers.controlled_candidate_profile import _budget
from tests._helpers.lane01_candidate_problem import labor_candidate_problem


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", [True, False])
async def test_recursive_leaf_uses_composed_resolver_for_real_compiler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selected: bool
) -> None:
    """A separately selected index reaches the compiler; no owner stays unbound."""
    source_root = tmp_path / "catalog-root-without-capability-index"
    source_root.mkdir()
    resolver = RequirementToCapabilityResolver.governed_fixture() if selected else None
    problem = labor_candidate_problem()
    graph = derive_recursive_design_graph(
        design_ref="design://resolver-bridge",
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="test://resolver-bridge",
    )
    controller = build_default_recursive_generation_cycle_controller(
        promotion_runtime=PromotionRuntime(store=FileSystemCAS(tmp_path / "cas")),
        repo_root=source_root,
        capability_resolver=resolver,
    )
    observations: list[tuple[object, tuple[object, ...]]] = []

    async def compile_at_actual_leaf(
        leaf: GenerationCycleController, actual_problem: Any, **_kwargs: Any
    ) -> Any:
        basis = leaf._n7_data_requirement_basis_with_report(
            actual_problem, acquisition_request={"world_slot": "global.unemployment_rate"}
        )
        matches = compiled_requirements_for_world_slot(
            world_slot="global.unemployment_rate",
            specs=basis.specs,
            capability_resolutions=basis.capability_resolutions,
        )
        observations.append((leaf._capability_resolver, matches))
        raise GenerationCycleError("test_compiler_probe_completed")

    monkeypatch.setattr(GenerationCycleController, "run", compile_at_actual_leaf)
    with pytest.raises(GenerationCycleError, match="test_compiler_probe_completed"):
        await controller.run(
            graph,
            problems_by_node={graph.root_design_ref: problem},
            budget_state=_budget(),
            recursive_budget=RecursiveCycleBudget(
                max_depth=0, max_nodes=1, min_cycles_per_leaf=1, max_cycles_per_leaf=1
            ),
            execution_intents_by_node={graph.root_design_ref: "simulate_only"},
        )
    assert len(observations) == 1
    actual_owner, matches = observations[0]
    assert actual_owner is resolver
    assert len(matches) == (1 if selected else 0)


def test_composed_resolver_cannot_be_replaced_by_problem_hints(tmp_path: Path) -> None:
    """A composed owner wins before any untrusted hint or gateway is inspected."""
    resolver = RequirementToCapabilityResolver.governed_fixture()

    class PoisonResolver:
        def resolve(self, _query: object) -> object:
            raise AssertionError("caller-supplied resolver was used")

    class PoisonGateway:
        @property
        def capability_resolver(self) -> object:
            raise AssertionError("caller-supplied gateway was inspected")

    problem = labor_candidate_problem()
    problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "n7_capability_resolver": PoisonResolver(),
                "n7_owner_gateway": PoisonGateway(),
            }
        }
    )
    controller = GenerationCycleController(repo_root=tmp_path, capability_resolver=resolver)
    basis = controller._n7_data_requirement_basis_with_report(
        problem, acquisition_request={"world_slot": "global.unemployment_rate"}
    )
    matches = compiled_requirements_for_world_slot(
        world_slot="global.unemployment_rate",
        specs=basis.specs,
        capability_resolutions=basis.capability_resolutions,
    )
    assert len(matches) == 1


def test_invalid_composed_resolver_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TypeError, match="recursive_capability_resolver_invalid"):
        build_default_recursive_generation_cycle_controller(
            promotion_runtime=PromotionRuntime(store=FileSystemCAS(tmp_path / "cas")),
            capability_resolver=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="generation_cycle_capability_resolver_invalid"):
        GenerationCycleController(capability_resolver=object())  # type: ignore[arg-type]
