"""Exercise actual N6 revision/source emission, not WDI acquisition or N5 numerics."""

from __future__ import annotations

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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
    monkeypatch.setattr(
        controller,
        "_n7_world_snapshot",
        lambda *args, **kwargs: planner.AcquisitionWorldSnapshot(
            world_ref="world://n7-source-route-positive-test"
        ),
    )
    route = controller._plan_n7_requirement_gap_if_requested(problem, cycle=cycle)
    assert route is not None
    basis = route.basis
    assert basis.routing_limitation_code is None and not basis.unbound_input_fields
    assert basis.source_route_diagnostic is None
    report = route.report
    report_ref = route.report_ref
    assert report.status != "blocked"
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


@pytest.mark.asyncio
async def test_zero_resolution_report_explains_join_without_claiming_source_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.runtime.quality.acquisition_planner import load_acquisition_planner_report

    problem, gap, controller, cycle, cas_root = await _emitted_cycle(tmp_path)
    request = cycle.revision_request.strategy_payload["acquisition_request"]
    mixed_basis = controller._n7_data_requirement_basis_with_report(
        problem, acquisition_request=request, cycle=cycle
    )
    assert mixed_basis.capability_resolutions is not None
    assert len(mixed_basis.capability_resolutions) == 1
    resolved_row = mixed_basis.capability_resolutions[0]
    unresolved_row = resolved_row.model_copy(
        update={
            "state": "not_established",
            "binding": None,
            "reason_codes": ("unrelated_resolution_not_established",),
        }
    )
    mixed_source_gap = planner.grounding_coverage_requirement_gap(
        candidate_id=cycle.selected_candidate_ref,
        candidate_content_hash=cycle.selected_candidate_content_hash,
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        issue_codes=("acquire_data:global.tax_rate",),
        evidence_refs=("fixture://mixed-resolution-carrier",),
        grounding_report_ref="fixture://mixed-resolution-carrier-report",
        authority_level=problem.authority_profile.requested_authority_level,
    )
    mixed_diagnostic = owner._n7_source_route_diagnostic(
        source_gap=mixed_source_gap,
        specs=mixed_basis.specs,
        capability_resolutions=(resolved_row, unresolved_row),
    )
    assert mixed_diagnostic.compiler_resolution_rows == 2
    assert mixed_diagnostic.non_established_resolution_rows == 1
    assert mixed_diagnostic.exact_descriptor_join_occurrences == 0
    assert mixed_diagnostic.result == "descriptor_join_not_established"

    compiler_type = owner.DataRequirementCompiler
    compile_for_scenario = compiler_type.compile_for_scenario

    def compile_without_resolution(compiler: Any, *args: Any, **kwargs: Any):
        report = compile_for_scenario(compiler, *args, **kwargs)
        payload = report.model_dump(mode="json")
        payload["capability_requirement_resolutions"] = []
        return DataRequirementCompilationReport.model_validate(payload)

    monkeypatch.setattr(compiler_type, "compile_for_scenario", compile_without_resolution)
    from tests.unit.runtime.quality.test_candidate_n5_l1_routing import _simulation

    simulation = _simulation(cycle.selected_candidate_ref)
    execution_ref = owner.CASArtifactRef.model_validate(
        simulation.diagnostics["candidate_simulation_execution_selected_ref"]
    )
    l1_route = owner._CandidateN5L1RoutingObservation(
        source_ref=simulation.candidate_simulation_n4_source_ref,
        context_job_ref=simulation.candidate_simulation_context_job_ref,
        n5_input_ref=simulation.candidate_simulation_n5_input_ref,
        n5_execution_ref=execution_ref,
        n5_result_ref=simulation.simulation_result_ref,
        requirement_gap=gap,
    )
    value_port = owner.ValuePortObservation(
        status="value_pending_n8",
        candidate_id=cycle.selected_candidate_ref,
        authority_blockers=("candidate_scenario_n5_only",),
        reason="Candidate L1 route is present for the N7 report refusal test.",
        candidate_n5_l1_routing=l1_route,
    )
    request = dict(request)
    request.update(
        {
            "n7_source_join_rule": planner._N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE,
            "accompanying_requirement_gaps": [],
        }
    )
    revision = cycle.revision_request.model_copy(
        update={
            "strategy_payload": {
                **cycle.revision_request.strategy_payload,
                "acquisition_request": request,
            }
        }
    )
    cycle = owner.GenerationCycleRecord.model_validate(
        cycle.model_copy(
            update={"simulation": simulation, "value_port": value_port, "revision_request": revision}
        ).model_dump(mode="json")
    )
    monkeypatch.setattr(
        controller,
        "_n7_world_snapshot",
        lambda *args, **kwargs: planner.AcquisitionWorldSnapshot(
            world_ref="world://n7-source-route-zero-resolution-test"
        ),
    )

    route = controller._plan_n7_requirement_gap_if_requested(problem, cycle=cycle)
    assert route is not None
    basis = route.basis
    diagnostic = basis.source_route_diagnostic
    assert diagnostic is not None
    assert diagnostic.source_gap_ref == gap.requirement_gap_id
    assert diagnostic.target_world_slot == "global.unemployment_rate"
    assert diagnostic.source_origin == "l1_outcome_validation_gap"
    assert diagnostic.model_input_obligation_status == "not_established"
    assert diagnostic.total_compiled_spec_occurrences == 1
    assert diagnostic.compiler_resolution_rows == 0
    assert diagnostic.exact_descriptor_join_occurrences == 0
    assert diagnostic.resolution_carrier_state == "supplied_empty"
    assert diagnostic.result == "no_resolution_rows"
    assert diagnostic.source_search_completeness == "not_established"
    report = route.report
    assert report.status == "blocked"
    assert report.basis_limitation_code == "unbound_requirement_input_refused"
    assert report.source_route_diagnostic == diagnostic

    fresh_store = FileSystemCAS.open_existing_read_only(cas_root)
    loaded = load_acquisition_planner_report(fresh_store, route.report_ref)
    assert loaded == report
    assert loaded.source_route_diagnostic == diagnostic

    legacy_shape = loaded.model_copy(update={"source_route_diagnostic": None})
    assert "source_route_diagnostic" not in legacy_shape.model_dump(mode="json")
    assert legacy_shape.schema_version == loaded.schema_version
