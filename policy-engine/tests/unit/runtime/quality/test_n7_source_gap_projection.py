from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest


@pytest.fixture
def n7_synthetic_catalog_root(tmp_path: Path) -> Path:
    """Use the real registry owner with small, test-owned catalog inputs."""
    from tests.unit.runtime.quality.test_substrate_registry import (
        _write_substrate_catalog_fixture,
    )

    root = tmp_path / "c"
    _write_substrate_catalog_fixture(root)
    return root


@pytest.mark.asyncio
async def test_n7_source_gap_semantics_survive_compiler_and_fresh_route_read(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    n7_synthetic_catalog_root: Path,
) -> None:
    """The persisted N7 record keeps its typed source gap and exact compiler join."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.runtime.quality import generation_cycle
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

    monkeypatch.setattr(generation_cycle, "_N7_SOURCE_SEMANTIC_EMISSION_ENABLED", True)
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    try:
        closure, _request = await persist_wdi_route(
            control,
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            generation_cycle_repo_root=n7_synthetic_catalog_root,
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

            # The generic dispatcher remains fail-closed for the new joined
            # denominator until it has its own current-cycle verification.
            # This test world is synthetic, not an availability measurement.
            from polisyos.runtime.quality.acquisition_planner import (
                AcquisitionPlannerBindingError,
                AcquisitionWorldSnapshot,
                bind_acquisition_planner_report,
                n7_planner_input_content_hash,
                persist_and_verify_acquisition_planner_report,
                run_acquisition_closed_loop,
            )

            raw_request = route_cycle.revision_request.strategy_payload["acquisition_request"]
            assert isinstance(raw_request, Mapping)
            dispatch_request = {**raw_request, "cycle_index": route_cycle.cycle_index}
            world = AcquisitionWorldSnapshot(world_ref="test-only:source-join-world")
            context_hash = n7_planner_input_content_hash(
                run_id=persisted_report.run_id,
                acquisition_request=dispatch_request,
                compiled_requirement_specs=compiler_report.specs,
                world_snapshot=world,
                capability_requirement_resolutions=compiler_report.capability_requirement_resolutions,
                requirement_basis_binding=binding,
                design_problem=closure.design_problem_basis,
                generated_at=persisted_report.generated_at,
            )
            rebound = bind_acquisition_planner_report(
                persisted_report,
                planning_context_hash=context_hash,
            )
            rebound_ref = persist_and_verify_acquisition_planner_report(
                control._artifact_store,
                rebound,
            )
            inputs = {
                "run_id": rebound.run_id,
                "acquisition_request": dispatch_request,
                "data_requirement_specs": compiler_report.specs,
                "world_snapshot": world,
                "capability_requirement_resolutions": compiler_report.capability_requirement_resolutions,
                "design_problem": closure.design_problem_basis,
                "generated_at": rebound.generated_at,
                "planner_report": rebound,
                "planner_report_ref": rebound_ref,
                "requirement_basis_binding": binding,
                "artifact_store": control._artifact_store,
                "require_persisted_planner_report": True,
            }
            with pytest.raises(
                AcquisitionPlannerBindingError,
                match="n7_candidate_recorded_gateway_required",
            ):
                run_acquisition_closed_loop(**inputs)

        availability = source_gap.metadata["availability"]
        candidate_binding = source_gap.metadata["candidate_binding"]
        variable_id = availability["variable_id"]
        from polisyos.runtime.http.services.acquisition_surface_execution import (
            _require_live_variable_route,
        )

        assert _require_live_variable_route(closure) == variable_id
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
        # Coverage is not part of the gap ID. The join must still compare it.
        assert different_source_gap.requirement_gap_id == source_gap.requirement_gap_id
        assert different_source_gap.model_dump(mode="json") != source_gap.model_dump(mode="json")
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
        for foreign_gap in (
            different_variable_gap,
            different_source_gap,
            prior_cycle_gap,
        ):
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


@pytest.mark.asyncio
async def test_fresh_route_rejects_same_id_wrong_compiler_metadata_with_guard_removal(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    n7_synthetic_catalog_root: Path,
) -> None:
    """A CAS-persisted compiler mismatch is rejected despite unchanged route IDs."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        _require_live_variable_route,
    )
    from polisyos.runtime.quality import acquisition_route_loop, generation_cycle
    from tests._helpers.acquisition_production import (
        install_fixture_wdi_cost_basis,
        persist_wdi_route,
        resolve_completed_wdi_route,
    )
    from tests._helpers.runtime_http import _build_control_service

    monkeypatch.setattr(generation_cycle, "_N7_SOURCE_SEMANTIC_EMISSION_ENABLED", True)
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    real_persist = generation_cycle.persist_and_verify_data_requirement_compilation_report
    real_compile = generation_cycle.DataRequirementCompiler.compile_for_scenario
    real_check = acquisition_route_loop._n7_joined_planner_records_match

    def compile_with_metadata(compiler, *args, **kwargs):
        report = real_compile(compiler, *args, **kwargs)
        payload = report.model_dump(mode="json")
        assert len(payload["specs"]) == 1
        payload["specs"][0]["metadata"].update(
            {"deadline_ms": 120, "captured_at": "2026-10-29T00:00:00Z"}
        )
        return DataRequirementCompilationReport.model_validate(payload)

    def persist_wrong_metadata(store, report, *, expected_scenario_id):
        payload = report.model_dump(mode="json")
        assert len(payload["specs"]) == 1
        metadata = payload["specs"][0]["metadata"]
        assert metadata["deadline_ms"] == 120
        assert metadata["captured_at"] == "2026-10-29T00:00:00Z"
        # Keep the requirement ID, schema and metadata keys; change complete
        # compiler quantities before the real CAS writer persists the report.
        metadata["deadline_ms"] = 240
        metadata["captured_at"] = "2026-10-30T00:00:00Z"
        altered = DataRequirementCompilationReport.model_validate(payload)
        return real_persist(store, altered, expected_scenario_id=expected_scenario_id)

    try:
        monkeypatch.setattr(
            generation_cycle.DataRequirementCompiler,
            "compile_for_scenario",
            compile_with_metadata,
        )
        monkeypatch.setattr(
            generation_cycle,
            "persist_and_verify_data_requirement_compilation_report",
            persist_wrong_metadata,
        )
        # Admit the counterfactual case once to leave real compiled/planner/CAS
        # artifacts. The restore/removal/restore below exercises the route owner.
        monkeypatch.setattr(
            acquisition_route_loop,
            "_n7_joined_planner_records_match",
            lambda **_: True,
        )
        closure, _ = await persist_wdi_route(
            control,
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            generation_cycle_repo_root=n7_synthetic_catalog_root,
            revised_source=False,
        )
        with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
            binding = closure.planner_report.requirement_basis_binding
            assert binding is not None
            altered_report = DataRequirementCompilationReport.model_validate(
                load_core_json_artifact(control._artifact_store, binding.compiler_report_ref)
            )
        (altered_spec,) = altered_report.specs
        assert altered_spec.requirement_id == closure.planner_record.compiled_requirement_ref
        assert altered_spec.required_data_families == ("government.balance",)
        assert altered_spec.metadata["deadline_ms"] == 240
        assert altered_spec.metadata["captured_at"] == "2026-10-30T00:00:00Z"
        assert _require_live_variable_route(closure) == "government.balance"

        monkeypatch.setattr(acquisition_route_loop, "_n7_joined_planner_records_match", real_check)
        with pytest.raises(
            acquisition_route_loop.AcquisitionRouteClosureError,
            match="source_requirement_projection_mismatch",
        ):
            resolve_completed_wdi_route(
                control,
                run_id="run-acquisition",
                tenant_id="tenant-fixture",
                cell_id="cell-fixture",
            )
        monkeypatch.setattr(
            acquisition_route_loop,
            "_n7_joined_planner_records_match",
            lambda **_: True,
        )
        false_green, _ = resolve_completed_wdi_route(
            control,
            run_id="run-acquisition",
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
        )
        assert _require_live_variable_route(false_green) == "government.balance"
        monkeypatch.setattr(acquisition_route_loop, "_n7_joined_planner_records_match", real_check)
        with pytest.raises(
            acquisition_route_loop.AcquisitionRouteClosureError,
            match="source_requirement_projection_mismatch",
        ):
            resolve_completed_wdi_route(
                control,
                run_id="run-acquisition",
                tenant_id="tenant-fixture",
                cell_id="cell-fixture",
            )
    finally:
        control.close()


@pytest.mark.asyncio
async def test_fresh_route_selects_one_source_action_and_keeps_unmatched_compiler_gap(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    n7_synthetic_catalog_root: Path,
) -> None:
    """A second compiler requirement survives a real persisted source route."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        _require_live_variable_route,
    )
    from polisyos.runtime.quality import acquisition_route_loop, generation_cycle
    from polisyos.runtime.quality.acquisition_planner import (
        bind_acquisition_planner_report,
        load_acquisition_planner_report,
        persist_and_verify_acquisition_planner_report,
    )
    from tests._helpers.acquisition_production import (
        install_fixture_wdi_cost_basis,
        persist_wdi_route,
    )
    from tests._helpers.runtime_http import _build_control_service

    monkeypatch.setattr(generation_cycle, "_N7_SOURCE_SEMANTIC_EMISSION_ENABLED", True)
    install_fixture_wdi_cost_basis(monkeypatch)
    control = _build_control_service(tmp_path / "control")
    real_compile = generation_cycle.DataRequirementCompiler.compile_for_scenario

    def compile_with_unmatched(compiler, *args, **kwargs):
        report = real_compile(compiler, *args, **kwargs)
        payload = report.model_dump(mode="json")
        assert len(payload["specs"]) == 1
        other = dict(payload["specs"][0])
        other["requirement_id"] += ":other"
        other["claim_id"] += ":other"
        other["required_data_families"] = ["other_panel"]
        payload["specs"].append(other)
        return DataRequirementCompilationReport.model_validate(payload)

    monkeypatch.setattr(
        generation_cycle.DataRequirementCompiler,
        "compile_for_scenario",
        compile_with_unmatched,
    )
    try:
        closure, _ = await persist_wdi_route(
            control,
            tenant_id="tenant-fixture",
            cell_id="cell-fixture",
            generation_cycle_repo_root=n7_synthetic_catalog_root,
            revised_source=False,
        )
        source = closure.route_source_cycle.value_port.acquisition_requirement
        assert source is not None
        report = closure.planner_report
        assert len(report.acquisition_records) == 2
        assert _require_live_variable_route(closure) == "government.balance"
        selected = closure.planner_record
        (unmatched,) = tuple(row for row in report.acquisition_records if row != selected)
        assert unmatched.compiled_requirement_ref.endswith(":other")
        assert "required_data_family:other_panel" in unmatched.missing_requirement_fields
        assert source.requirement_gap_id not in unmatched.scenario_requirement_refs

        # Persist a test-only ambiguous report with two distinct acquisition IDs
        # for the same source. Exercise the actual route owner's selector after
        # CAS reload, not a list-length or marker-only proxy.
        duplicate = selected.model_copy(update={"acquisition_id": selected.acquisition_id + ":dup"})
        ambiguous = report.model_copy(
            update={"acquisition_records": (*report.acquisition_records, duplicate)}
        )
        assert report.planning_context_hash is not None
        ambiguous = bind_acquisition_planner_report(
            ambiguous,
            planning_context_hash=report.planning_context_hash,
        )
        with tenant_scope(None, tenant_id="tenant-fixture", cell_id="cell-fixture"):
            ref = persist_and_verify_acquisition_planner_report(control._artifact_store, ambiguous)
            loaded = load_acquisition_planner_report(control._artifact_store, ref)
        with pytest.raises(
            acquisition_route_loop.AcquisitionRouteClosureError,
            match="costed_route_not_unique",
        ):
            acquisition_route_loop._select_source_planner_record(loaded, source)
    finally:
        control.close()
