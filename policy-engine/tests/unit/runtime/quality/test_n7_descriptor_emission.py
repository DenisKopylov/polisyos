"""Exercise actual N6 revision/source emission, not WDI acquisition or N5 numerics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality import generation_cycle as owner
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from tests._helpers.controlled_candidate_profile import _StableShadowGrounding
from tests._helpers.lane01_candidate_problem import labor_candidate_problem
from tests.unit.runtime.quality.test_generation_cycle import (
    _budget,
    _canonical_n7_test_atom,
    _CounterexampleAwareGenerator,
    _N7ReentrySimulationPort,
)


async def _emitted_cycle(
    tmp_path: Path,
    *,
    resolver: RequirementToCapabilityResolver | None = None,
):
    problem = labor_candidate_problem()
    candidate_id = "candidate_cycle_1"
    atom = _canonical_n7_test_atom(
        problem, candidate_id=candidate_id, target_world_slot="global.tax_rate"
    )
    gap = planner.l1_variable_availability_requirement_gap(
        candidate_id=candidate_id,
        candidate_content_hash=atom.content_hash,
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        authority_level="research",
        availability=L1VariableAvailability(
            variable_id="global.unemployment_rate",
            status="unavailable",
            dataset_count=0,
            metric_binding_count=0,
            observation_count=0,
            coverage_ref="fixture://declared-labor-context-missing",
        ),
    )

    class ValueGapInput:
        def __call__(self, *, candidate: Any, **kwargs: Any):
            return owner.ValuePortObservation(
                status="value_blocked",
                candidate_id=str(candidate.candidate_id),
                authority_blockers=("acquire_data:value_panel_data_missing",),
                reason="Controlled candidate context needs the declared labor source.",
                decision_grade="blocked",
                acquisition_requirement=gap,
            )

    repo = tmp_path / "runtime"
    repo.mkdir(parents=True)
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root).for_tenant("tenant-source", cell_id="cell-source")
    controller = owner.GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(first_atom=atom),
        # Existing controlled shadow input lets the typed Value/L1 absence
        # reach N7; this fixture does not establish real CGF grounding.
        grounding_port=_StableShadowGrounding(),
        simulation_port=_N7ReentrySimulationPort(),
        value_port=ValueGapInput(),
        capability_resolver=resolver or RequirementToCapabilityResolver.governed_fixture(),
        authority_scope="contract_testing",
        artifact_store=store,
        repo_root=repo,
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    controller._begin_source_run("generation_cycle_" + problem_ref.removeprefix("sha256:")[:16])
    cycle, _summaries = await controller._run_cycle(
        problem,
        cycle_index=0,
        budget_state=_budget(),
        previous_cycle=None,
        stable_design_problem_ref=problem_ref,
    )
    return problem, gap, controller, cycle, cas_root


@pytest.mark.asyncio
async def test_actual_revision_emits_descriptor_marker_and_fresh_checkpoint_replays(
    tmp_path: Path,
) -> None:
    assert owner._N7_SOURCE_SEMANTIC_EMISSION_ENABLED is False
    problem, gap, controller, cycle, cas_root = await _emitted_cycle(tmp_path)
    request = cycle.revision_request.strategy_payload["acquisition_request"]
    assert request["n7_source_join_rule"] == planner._N7_SOURCE_DESCRIPTOR_JOIN_RULE
    # The value owner has one canonical routing code. The exact source slot is
    # carried by its typed gap, not synthesized into a different owner issue.
    assert request["driver"] == "acquire_data:value_panel_data_missing"
    assert request["requirement_gap"] == gap.model_dump(mode="json")
    checkpoint_ref = controller._n7_candidate_checkpoint_refs[0]
    store = controller._n7_runtime_artifact_store()
    basis = controller._n7_data_requirement_basis_with_report(
        problem, acquisition_request=request, cycle=cycle
    )
    assert basis.routing_limitation_code is None and not basis.unbound_input_fields
    binding = planner.persist_and_verify_data_requirement_compilation_report(
        store, basis.compilation_report, expected_scenario_id=problem.design_problem_id
    )
    semantic_gaps = planner._n7_source_semantic_planning_gaps(
        source_gap=gap, compiler_gaps=basis.routed_compiler_gaps, specs=basis.specs
    )
    report = planner.plan_evidence_acquisition(
        run_id=f"n7-cycle:{problem.design_problem_id}:0",
        gaps=semantic_gaps,
        requirement_basis_binding=binding,
        generated_at=datetime(2026, 11, 3, tzinfo=UTC),
    )
    report_ref = planner.persist_and_verify_acquisition_planner_report(store, report)
    selected_request = {
        **request,
        "cycle_index": 0,
        "n7_candidate_source_ref": checkpoint_ref.model_dump(mode="json"),
    }
    fresh = FileSystemCAS(cas_root).for_tenant("tenant-source", cell_id="cell-source")
    reopened = planner.load_acquisition_planner_report(fresh, report_ref)
    arguments = {
        "store": fresh,
        "checkpoint_ref": checkpoint_ref,
        "run_id": report.run_id,
        "problem": problem,
        "specs": basis.specs,
        "capability_resolutions": basis.capability_resolutions,
        "report": reopened,
        "require_current": False,
    }
    assert planner._n7_validate_candidate_checkpoint(request=selected_request, **arguments) == gap
    row = next(
        row
        for row in reopened.acquisition_records
        if row.requirement_gap_ref == gap.requirement_gap_id
    )
    assert row.compiled_requirement_ref != gap.compiled_requirement_ref
    assert "global.unemployment_rate" in row.scenario_requirement_refs
    # The selected new law is part of actual sealed cycle bytes. A consumer
    # cannot remove it or reinterpret this checkpoint under historical v1.
    for marker in (None, planner._N7_SOURCE_JOIN_RULE):
        altered = dict(selected_request)
        if marker is None:
            altered.pop("n7_source_join_rule")
        else:
            altered["n7_source_join_rule"] = marker
        with pytest.raises(ValueError, match="n7_candidate_source_cycle_mismatch"):
            planner._n7_validate_candidate_checkpoint(request=altered, **arguments)


@pytest.mark.asyncio
async def test_actual_revision_does_not_emit_descriptor_law_when_qualifier_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        owner.GenerationCycleController,
        "_n7_descriptor_source_join_qualified",
        lambda *args, **kwargs: False,
    )
    _problem, _gap, controller, cycle, _root = await _emitted_cycle(tmp_path)
    request = cycle.revision_request.strategy_payload.get("acquisition_request", {})
    assert request.get("n7_source_join_rule") != planner._N7_SOURCE_DESCRIPTOR_JOIN_RULE
    assert not controller._n7_candidate_checkpoint_refs


@pytest.mark.asyncio
async def test_actual_revision_refuses_rehashed_wrong_descriptor_target(tmp_path: Path) -> None:
    governed = RequirementToCapabilityResolver.governed_fixture()
    capabilities = []
    for capability in governed.capabilities:
        if capability.construct_id == "labor.unemployment_rate":
            capability = capability.model_copy(
                update={
                    "source_assets": tuple(
                        asset.model_copy(
                            update={
                                "metadata": {**asset.metadata, "target_world_slot": "global.gdp"}
                            }
                        )
                        for asset in capability.source_assets
                    )
                }
            )
        capabilities.append(capability)
    _problem, _gap, controller, cycle, _root = await _emitted_cycle(
        tmp_path, resolver=RequirementToCapabilityResolver(capabilities=capabilities)
    )
    assert (
        cycle.revision_request.strategy_payload.get("acquisition_request", {}).get(
            "n7_source_join_rule"
        )
        != planner._N7_SOURCE_DESCRIPTOR_JOIN_RULE
    )
    assert not controller._n7_candidate_checkpoint_refs
