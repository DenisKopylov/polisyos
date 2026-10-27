from __future__ import annotations

from collections.abc import Mapping

import pytest


@pytest.mark.asyncio
async def test_n7_source_gap_semantics_survive_compiler_and_fresh_route_read(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The persisted N7 record keeps its typed source gap and exact compiler join."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.runtime.quality.acquisition_planner import (
        l1_variable_availability_requirement_gap,
        load_acquisition_planner_report,
        validate_persisted_acquisition_planner_report,
    )
    from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        _n7_cycle_source_gap,
    )
    from tests._helpers.acquisition_production import (
        install_fixture_wdi_cost_basis,
        persist_wdi_route,
    )
    from tests._helpers.runtime_http import _build_control_service

    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    try:
        closure, _request = await persist_wdi_route(
            control,
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            revised_source=False,
        )
        route_cycle = closure.route_source_cycle
        source_gap = route_cycle.value_port.acquisition_requirement
        assert route_cycle.cycle_index == 0
        assert route_cycle.grounding.acquisition_requirement is None
        assert source_gap is not None
        assert source_gap.metadata["source"] == "l1_dcat_variable_availability"
        assert route_cycle.acquisition_routing_report_ref is not None

        with tenant_scope(None, tenant_id=closure.tenant_id, cell_id=closure.cell_id):
            persisted_report = load_acquisition_planner_report(
                control._artifact_store,
                route_cycle.acquisition_routing_report_ref,
            )
            assert persisted_report == closure.planner_report
            assert len(persisted_report.acquisition_records) == 1
            record = persisted_report.acquisition_records[0]
            assert record == closure.planner_record

            binding = persisted_report.requirement_basis_binding
            assert binding is not None
            compiler_report = DataRequirementCompilationReport.model_validate(
                load_core_json_artifact(control._artifact_store, binding.compiler_report_ref)
            )
            selected_specs = tuple(
                spec
                for spec in compiler_report.specs
                if spec.requirement_id == record.compiled_requirement_ref
            )
            assert len(selected_specs) == 1
            selected_spec = selected_specs[0]
            assert compiler_report.scenario_id == closure.design_problem_basis.design_problem_id
            assert selected_spec.scope.jurisdiction == (
                closure.design_problem_basis.jurisdiction_time.region
            )

            issues = validate_persisted_acquisition_planner_report(
                control._artifact_store,
                route_cycle.acquisition_routing_report_ref,
                persisted_report,
                expected_scenario_id=compiler_report.scenario_id,
                expected_compiled_requirement_ref=selected_spec.requirement_id,
            )
            assert issues == ()

        availability = source_gap.metadata["availability"]
        candidate_binding = source_gap.metadata["candidate_binding"]
        variable_id = availability["variable_id"]
        source_compiled_ref = source_gap.compiled_requirement_ref
        assert record.gap_id == source_gap.requirement_gap_id
        assert record.requirement_gap_ref == source_gap.requirement_gap_id
        assert record.gap_type == source_gap.gap_type
        assert record.requirement_family == source_gap.requirement_family.value
        assert record.requirement_schema_version == source_gap.requirement_schema_version
        assert record.claim_ref == source_gap.claim_ref
        assert record.missing_requirement_fields == source_gap.missing_requirement_fields
        assert record.authority_level == source_gap.authority_level
        assert record.mandatory_gate_state == source_gap.mandatory_gate_state
        assert record.mandatory_gate_refs == source_gap.mandatory_gate_refs
        assert record.producer_output_ref == source_gap.producer_output_ref
        assert record.compiled_requirement_ref == selected_spec.requirement_id
        assert tuple(selected_spec.required_data_families) == (variable_id,)
        assert source_gap.requirement_gap_id in record.scenario_requirement_refs
        assert source_compiled_ref in record.scenario_requirement_refs
        assert selected_spec.requirement_id in record.scenario_requirement_refs
        assert variable_id in record.scenario_requirement_refs
        assert candidate_binding["candidate_id"] == route_cycle.selected_candidate_ref
        assert candidate_binding["candidate_content_hash"] == (
            route_cycle.selected_candidate_content_hash
        )
        assert candidate_binding["design_problem_ref"] == closure.design_problem_basis_ref
        assert record.recommended_strategy.value == "production_snapshot_build"

        problem = closure.design_problem_basis
        request = route_cycle.revision_request.strategy_payload.get("acquisition_request")
        assert isinstance(request, Mapping)
        assert "scope_profile" not in request
        foreign_scope_problem = problem.model_copy(
            update={
                "jurisdiction_time": problem.jurisdiction_time.model_copy(
                    update={"region": "USA", "data_time": "2025"}
                )
            }
        )
        foreign_scope_gap, foreign_scope_code = _n7_cycle_source_gap(
            foreign_scope_problem,
            cycle=route_cycle,
            acquisition_request=request,
        )
        assert foreign_scope_gap is None
        assert foreign_scope_code == "unbound_requirement_input_refused"

        different_variable = f"{variable_id}.other"
        coverage_root = availability["coverage_ref"].partition("#variable/")[0]
        different_variable_gap = l1_variable_availability_requirement_gap(
            candidate_id=candidate_binding["candidate_id"],
            candidate_content_hash=candidate_binding["candidate_content_hash"],
            design_problem_ref=candidate_binding["design_problem_ref"],
            availability=L1VariableAvailability(
                variable_id=different_variable,
                status="unavailable",
                dataset_count=0,
                metric_binding_count=0,
                observation_count=0,
                coverage_ref=f"{coverage_root}#variable/{different_variable}",
            ),
            authority_level=source_gap.authority_level,
        )
        different_source_gap = l1_variable_availability_requirement_gap(
            candidate_id=candidate_binding["candidate_id"],
            candidate_content_hash=candidate_binding["candidate_content_hash"],
            design_problem_ref=candidate_binding["design_problem_ref"],
            availability=L1VariableAvailability(
                variable_id=variable_id,
                status="unavailable",
                dataset_count=0,
                metric_binding_count=0,
                observation_count=0,
                coverage_ref=f"{coverage_root}#alternate-source/{variable_id}",
            ),
            authority_level=source_gap.authority_level,
        )
        prior_cycle_gap = l1_variable_availability_requirement_gap(
            candidate_id=candidate_binding["candidate_id"],
            candidate_content_hash="sha256:" + "0" * 64,
            design_problem_ref=candidate_binding["design_problem_ref"],
            availability=L1VariableAvailability(
                variable_id=variable_id,
                status="unavailable",
                dataset_count=0,
                metric_binding_count=0,
                observation_count=0,
                coverage_ref=availability["coverage_ref"],
            ),
            authority_level=source_gap.authority_level,
        )
        for foreign_gap in (different_variable_gap, different_source_gap, prior_cycle_gap):
            foreign_request = {
                **request,
                "requirement_gap": foreign_gap.model_dump(mode="json"),
            }
            admitted_gap, refusal = _n7_cycle_source_gap(
                problem,
                cycle=route_cycle,
                acquisition_request=foreign_request,
            )
            assert admitted_gap is None
            assert refusal == "unbound_requirement_input_refused"

        controller = GenerationCycleController(authority_scope="contract_testing")
        foreign_scope_request = {
            **request,
            "scope_profile": controller._n7_scope_profile(
                foreign_scope_problem,
                acquisition_request={},
            ),
        }
        foreign_basis = controller._n7_data_requirement_basis_with_report(
            problem,
            acquisition_request=foreign_scope_request,
            cycle=route_cycle,
        )
        assert foreign_basis.routing_limitation_code == "unbound_requirement_input_refused"
        assert foreign_basis.routed_compiler_gaps == ()
    finally:
        control.close()
