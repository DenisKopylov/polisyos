"""Fail closed when an ordinary N6 revision would reuse a stale context."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_nonhandoff_revision_blocks_before_stale_context_n4_and_roundtrips_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retain the first conditional N5 when its revised problem lacks a context."""

    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality import design_generation
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleRun,
        JointSimulationPort,
        N4GenerationPort,
    )
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from tests.integration.core_runtime.test_e02_hard_feasibility_before_voi import (
        _FixtureGrounding,
        _owner_fixture,
    )
    from tests.integration.core_runtime.test_e02_informative_voi_execution import (
        _bounded_budget,
        _LowProxyInformationGenerator,
    )

    repo_root = Path(__file__).resolve().parents[3]
    store, problem, context, _high, candidate = _owner_fixture(tmp_path / "owner")
    first_n4 = _LowProxyInformationGenerator(candidate)
    default_n4 = N4GenerationPort(
        model_id="gpt-4o-mini",
        llm_client=object(),
        repo_root=repo_root,
        cycle_substrate_context=context,
    )
    dispatched_cycles: list[int] = []
    default_n4_inputs: list[tuple[Any, Any]] = []

    async def bounded_default_n4_context_boundary(
        revised_problem: Any,
        *,
        cycle_substrate_context: Any,
        **kwargs: Any,
    ) -> Any:
        """Use the real N4 context check without invoking external generation."""

        del kwargs
        default_n4_inputs.append((revised_problem, cycle_substrate_context))
        return design_generation._cycle_substrate_context_for_problem(
            cycle_substrate_context,
            design_problem=revised_problem,
        )

    # A full second N4 would make LLM and production-reference setup part of
    # this context-boundary test. Preserve the real default port and its real
    # context validator, while stopping at the validator before either owner
    # dependency is contacted. This is not a full second default N4 run.
    monkeypatch.setattr(
        design_generation,
        "generate_design_candidate_bundle_under_a",
        bounded_default_n4_context_boundary,
    )

    class _FirstFixtureThenDefaultN4:
        async def __call__(self, candidate_problem: Any, *, cycle_index: int) -> Any:
            dispatched_cycles.append(cycle_index)
            if cycle_index == 0:
                return await first_n4(candidate_problem, cycle_index=cycle_index)
            return await default_n4(candidate_problem, cycle_index=cycle_index)

    n5_observations: list[Any] = []
    original_n5_call = JointSimulationPort.__call__

    def observe_real_n5_call(self: JointSimulationPort, **kwargs: Any) -> Any:
        n5_observations.append(kwargs)
        return original_n5_call(self, **kwargs)

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_real_n5_call)

    try:
        original_problem_ref = gy_content_hash(problem.model_dump(mode="json"))
        assert context.design_problem_ref == original_problem_ref
        controller = GenerationCycleController(
            generation_port=_FirstFixtureThenDefaultN4(),
            grounding_port=_FixtureGrounding(),
            repo_root=repo_root,
            cycle_substrate_context=context,
            promotion_runtime=PromotionRuntime(store=store),
            authority_scope="production",
        )
        assert controller._candidate_simulation_handoff is None
        assert type(controller._simulation_port) is JointSimulationPort
        assert controller._simulation_port.supports_applicability_preflight(problem)

        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            run = await controller.run(
                problem,
                budget_state=_bounded_budget("1.0"),
                min_cycles=1,
                max_cycles=2,
            )

        assert run.terminal_status == "blocked"
        assert run.blocked_reason == "cycle_substrate_context_reissue_required"
        assert len(run.cycles) == 1
        cycle = run.cycles[0]
        assert cycle.cycle_index == 0
        assert cycle.simulation.status == "joint_simulated"
        assert cycle.simulation.simulation_result_ref is not None
        assert cycle.value_port.status == "value_conditional"
        assert cycle.value_port.value_ref == str(
            cycle.simulation.simulation_result_ref.artifact_id
        )
        assert cycle.voi_decision.next_action == "blocked"
        assert cycle.voi_decision.reason == "cycle_substrate_context_reissue_required"
        revision = cycle.revision_request
        revised_problem_ref = gy_content_hash(revision.revised_problem.model_dump(mode="json"))
        assert revised_problem_ref != original_problem_ref
        assert cycle.design_problem_basis_ref == original_problem_ref
        assert revision.source_counterexample_ref == cycle.counterexample.counterexample_ref

        # The guard runs before either a second generator dispatch or second
        # N5 call. The first cycle still owns the only conditional N5 reference.
        assert dispatched_cycles == [0]
        assert default_n4_inputs == []
        assert len(n5_observations) == 1
        assert len(run.candidate_summaries) == 1

        # Persist the complete typed N6 history payload, then use the owner's
        # fresh historical reader. This roundtrip carries the conditional N5
        # result reference and bounded stop reason; it grants no authority.
        persisted_path = tmp_path / "generation-cycle-run.json"
        persisted_path.write_text(
            json.dumps(run.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        persisted_payload = json.loads(persisted_path.read_text(encoding="utf-8"))
        fresh_history = GenerationCycleRun.from_persisted_payload(persisted_payload)
        fresh_cycle = fresh_history.cycles[0]
        assert fresh_history.terminal_status == "blocked"
        assert fresh_history.blocked_reason == "cycle_substrate_context_reissue_required"
        fresh_revised_problem = fresh_cycle.revision_request.revised_problem
        assert fresh_revised_problem.model_dump(mode="json") == (
            revision.revised_problem.model_dump(mode="json")
        )
        assert gy_content_hash(fresh_revised_problem.model_dump(mode="json")) == (
            revised_problem_ref
        )
        assert fresh_cycle.value_port.status == "value_conditional"
        assert fresh_cycle.value_port.value_ref == cycle.value_port.value_ref
        assert fresh_cycle.simulation.simulation_result_ref == (
            cycle.simulation.simulation_result_ref
        )
        assert fresh_cycle.voi_decision.reason == "cycle_substrate_context_reissue_required"
        assert len(fresh_history.cycles) == 1
    finally:
        store.close()
