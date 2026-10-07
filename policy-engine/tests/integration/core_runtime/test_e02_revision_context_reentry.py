"""Served N6 candidate-context revision boundary witnesses."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_served_candidate_profile_two_iteration_cap_stops_before_revision_context_reentry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A candidate-only profile cannot turn an N6 revision into a second N5."""

    from polisyos.core import canon
    from polisyos.core.security import tenant_scope
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
    )
    from tests._helpers.controlled_candidate_profile import (
        _candidate_only_procurement_intervention_bundle,
    )
    from tests.unit.runtime.http.test_control_service_di import (
        _run_controlled_simulate_only_job_fixture,
    )

    fixture = await _run_controlled_simulate_only_job_fixture(
        monkeypatch,
        tmp_path,
        max_iterations=2,
        intervention_substrate=_candidate_only_procurement_intervention_bundle(),
    )
    try:
        assert fixture.job.state == "completed"
        assert fixture.request.max_iterations == 2
        persisted_compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            canon.from_canonical_bytes(fixture.compiled_payload)
        )
        assert persisted_compiled.recursive_budget_resolution is not None
        assert persisted_compiled.recursive_budget_resolution.requested_max_iterations == 2
        assert persisted_compiled.recursive_budget_resolution.effective_max_iterations == 2
        assert persisted_compiled.recursive_run.recursive_budget.max_cycles_per_leaf == 2
        assert persisted_compiled.recursive_run.content_hash == fixture.recursive_run.content_hash
        assert type(fixture.candidate_simulation_admission_owner) is (
            ConfiguredCandidateSimulationContextAdmissionOwner
        )
        assert fixture.verified_nl_job_scope._was_issued_by_verified_nl_execution_owner
        assert fixture.verified_nl_job_scope.job_id == fixture.job.job_id
        assert fixture.verified_nl_job_scope.run_id == str(fixture.job.run_id)
        assert fixture.candidate_simulation_handoffs[0].context_job_ref == (
            fixture.candidate_simulation_context_job_ref
        )
        assert fixture.candidate_simulation_handoffs[0].profile == (
            fixture.candidate_simulation_profile
        )
        assert fixture.candidate_simulation_handoffs[0].model_declaration == (
            fixture.candidate_simulation_model_declaration
        )
        assert fixture.candidate_simulation_profile.profile_selection_ref == (
            cycle_job_profile_selection_ref(fixture.original_problem)
        )

        assert len(fixture.n5_port_observations) == 1
        assert fixture.n5_port_observations[0].problem == fixture.original_problem
        leaf_run = persisted_compiled.recursive_run.leaf_nodes[0].cycle_run
        assert leaf_run is not None
        assert len(leaf_run.cycles) == 1
        cycle = leaf_run.cycles[0]
        assert cycle.simulation.status == "joint_simulated"
        assert cycle.voi_decision.next_action == "blocked"
        assert cycle.voi_decision.reason == "candidate_scenario_n5_only"

        # N6 retains its typed revision request, but candidate-only simulation
        # terminates the served run before the revised problem can reach N4/N5.
        revision = cycle.revision_request
        assert revision.source_counterexample_ref == cycle.counterexample.counterexample_ref
        assert revision.previous_grammar_elements == cycle.grammar_elements
        assert revision.revised_problem.runtime_hints["generation_cycle_revision"][
            "source_counterexample_ref"
        ] == revision.source_counterexample_ref
        assert cycle_job_design_problem_ref(revision.revised_problem) != (
            cycle_job_design_problem_ref(fixture.original_problem)
        )

        # The current owner is configured only for the original exact profile
        # selection. A changed N6 problem does not inherit that profile/context.
        assert cycle_job_profile_selection_ref(revision.revised_problem) != (
            fixture.candidate_simulation_profile.profile_selection_ref
        )
        with tenant_scope(
            None,
            tenant_id=fixture.verified_nl_job_scope.tenant_id,
            cell_id=fixture.verified_nl_job_scope.cell_id,
        ):
            revised_offer = fixture.candidate_simulation_admission_owner.admit_context(
                problem=revision.revised_problem,
                job_id=fixture.verified_nl_job_scope.job_id,
                run_id=fixture.verified_nl_job_scope.run_id,
                tenant_id=fixture.verified_nl_job_scope.tenant_id,
                cell_id=fixture.verified_nl_job_scope.cell_id,
            )
        assert revised_offer is None
        assert len(fixture.n5_port_observations) == 1
    finally:
        fixture.service.close()
