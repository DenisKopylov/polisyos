"""Real served COV seed refusal, selected CAS readback, and candidate limits.

The actual owner emits an unresolved grounding relation/lever, not a WDI
missing-distribution fact. This oracle proves the candidate research request
reaches the existing compiler/planner and retains its honest refusal. It does
not prove a positive costed COV route, acquisition, N8, N9, or current authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    artifact_ref_identity_key,
    load_core_json_artifact,
)
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.runtime.http.services.control.generation_cycle import (
    CompiledRecursiveGenerationCycleRun,
)
from polisyos.runtime.quality import generation_cycle as cycle_owner
from polisyos.runtime.quality.acquisition_planner import (
    data_requirement_compilation_report_digest,
    load_acquisition_planner_report,
    validate_persisted_acquisition_planner_report,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteClosureError,
    _resolve_source_cycle_problem_basis,
)
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationN5InputV5
from polisyos.runtime.quality.generation_source import (
    GenerationSourceRepository,
    N4CandidateScenarioSourceRecordV3,
)
from tests._helpers import acquisition_served_history as fixture
from tests._helpers.acquisition_production import resolve_completed_wdi_route

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def test_served_cov_seed_reaches_persisted_refusal_without_cost_or_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """Keep actual COV admission/cost gaps visible after real candidate N5."""
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )

    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "candidate-source", include_owner_slot_manifest=True
    )
    observed: list[str] = []

    def observe(**values: Any) -> None:
        control, job, run_id = values["control"], values["job"], values["run_id"]
        terminal = control.resolve_completed_control_job_core_run_source(
            job,
            expected_control_run_id=run_id,
            tenant_id=fixture.TENANT,
            cell_id=fixture.CELL,
        )
        assert terminal.manifest.status == "ok"
        assert terminal.tenant_id == fixture.TENANT
        assert terminal.cell_id == fixture.CELL
        outputs = tuple(
            ref
            for ref in terminal.manifest.outputs
            if ref.kind == "runtime.compiled_recursive_generation_cycle"
        )
        assert len(outputs) == 1
        selected = ArtifactRef.model_validate(
            job.progress["compiled_recursive_generation_cycle_artifact_ref"]
        )
        assert artifact_ref_identity_key(outputs[0]) == artifact_ref_identity_key(selected)
        assert str(selected.artifact_id) == job.progress["compiled_recursive_generation_cycle_ref"]
        # This handle is fresh, read-only, and reads the selected manifest view.
        fresh = FileSystemCAS.open_existing_read_only(values["cas_root"])
        assert fresh is not control._artifact_store
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            load_core_json_artifact(fresh, selected)
        )
        cycles = tuple(
            (leaf.cycle_run, cycle)
            for leaf in compiled.recursive_run.leaf_nodes
            if leaf.cycle_run is not None
            for cycle in leaf.cycle_run.cycles
        )
        # Full seed cycle denominator; no costed-route filter hides a member.
        assert len(cycles) == 1
        generation, cycle = cycles[0]
        problem = _resolve_source_cycle_problem_basis(
            generation_run=generation,
            source_cycle=cycle,
            design_problem=compiled.design_problem,
            design_problem_ref=compiled.design_problem_ref,
        )
        assert cycle.simulation.status == "joint_simulated"
        assert cycle.value_port.status == "value_pending_n8"
        assert "candidate_scenario_n5_only" in cycle.value_port.authority_blockers
        assert cycle.acquisition_receipt is None
        request = cycle.revision_request.strategy_payload["acquisition_request"]
        gap, refusal = cycle_owner._n7_cycle_source_gap(
            problem, cycle=cycle, acquisition_request=request
        )
        assert refusal is None and gap is not None
        assert gap.metadata["source"] == "cgf_grounding_coverage"
        assert gap.metadata["acquisition_family"] == "COV"
        assert gap.metadata["authority_purpose"] == "routing_only"
        assert gap.metadata["satisfaction_status"] == "unsatisfied"
        assert gap.metadata["candidate_binding"] == {
            "candidate_id": cycle.selected_candidate_ref,
            "candidate_content_hash": cycle.selected_candidate_content_hash,
            "design_problem_ref": cycle_owner._problem_ref(problem),
        }
        assert not cycle.grounding.current_valid
        simulation = cycle.simulation
        input_ref = simulation.candidate_simulation_n5_input_ref
        assert input_ref is not None
        n5_input = CandidateSimulationN5InputV5.model_validate(
            load_core_json_artifact(fresh, input_ref)
        )
        candidate_source = GenerationSourceRepository(fresh).load_candidate_scenario_source_for_n5(
            n5_input.n4_source_ref,
            expected_run_id=run_id,
            expected_job_id=job.job_id,
            expected_tenant_id=fixture.TENANT,
            expected_cell_id=fixture.CELL,
        )
        assert type(candidate_source) is N4CandidateScenarioSourceRecordV3
        assert candidate_source.candidate.candidate_id == cycle.selected_candidate_ref
        assert n5_input.original_candidate_id == cycle.selected_candidate_ref
        assert n5_input.original_candidate_hash == cycle.selected_candidate_content_hash
        assert candidate_source.stable_subject_ref == compiled.design_problem_ref
        assert candidate_source.profile_selection_ref == values["profile_selection_ref"]
        assert n5_input.profile.profile_selection_ref == values["profile_selection_ref"]
        assert n5_input.context_job_ref == simulation.candidate_simulation_context_job_ref
        assert artifact_ref_identity_key(n5_input.n4_source_ref) == artifact_ref_identity_key(
            simulation.candidate_simulation_n4_source_ref
        )
        report_ref = cycle.acquisition_routing_report_ref
        report = cycle.acquisition_routing_report
        diagnostic = {
            "compiled_ref": selected.model_dump(mode="json"),
            "cycle_count": len(cycles),
            "candidate_id": cycle.selected_candidate_ref,
            "design_problem_ref": cycle_owner._problem_ref(problem),
            "source_acquisition_family": gap.metadata["acquisition_family"],
            "source_gap": gap.model_dump(mode="json"),
            "report": report.model_dump(mode="json") if report is not None else None,
            "report_ref": report_ref.model_dump(mode="json") if report_ref is not None else None,
            "cost_basis": (
                cycle.acquisition_cost_basis_record.model_dump(mode="json")
                if cycle.acquisition_cost_basis_record is not None
                else None
            ),
            "source_semantic_emission_enabled": cycle_owner._N7_SOURCE_SEMANTIC_EMISSION_ENABLED,
            "claim": "candidate COV research escalation and persisted refusal only",
        }
        (tmp_path / "cov-seed-diagnostic.json").write_text(
            json.dumps(diagnostic, indent=2, sort_keys=True) + "\n"
        )
        assert cycle.voi_decision.next_action == "escalate"
        assert report_ref is not None and report is not None, diagnostic
        loaded = load_acquisition_planner_report(fresh, report_ref)
        assert loaded == report
        binding = loaded.requirement_basis_binding
        assert binding is not None
        compiler = DataRequirementCompilationReport.model_validate(
            load_core_json_artifact(fresh, binding.compiler_report_ref)
        )
        assert binding.scenario_id == compiler.scenario_id == problem.design_problem_id
        assert binding.compiler_report_digest == (
            data_requirement_compilation_report_digest(compiler)
        )
        assert binding.input_content_hash == compiler.input_content_hash
        assert binding.producer_report_ref == compiler.producer_report_ref
        assert binding.resolution == compiler.requirement_basis
        refs = tuple(spec.requirement_id for spec in compiler.specs)
        if refs:
            for ref in refs:
                assert not validate_persisted_acquisition_planner_report(
                    fresh,
                    report_ref,
                    loaded,
                    expected_scenario_id=problem.design_problem_id,
                    expected_compiled_requirement_ref=ref,
                )
        else:
            assert validate_persisted_acquisition_planner_report(
                fresh,
                report_ref,
                loaded,
                expected_scenario_id=problem.design_problem_id,
                expected_compiled_requirement_ref=gap.compiled_requirement_ref,
            ) == ({"code": "acquisition_compiled_requirement_not_in_basis"},)
        # Current owner input has no acquire_data:<family> selector. Its COV
        # acquisition family is not a fabricated distribution/data-source family.
        assert gap.metadata["issue_codes"] == ["cgf_disposition_missing"]
        assert cycle_owner._requirement_missing_distributions(gap) == ()
        assert loaded.status == "blocked"
        assert loaded.basis_limitation_code == "requirement_gap_not_compiled"
        assert loaded.cost_estimation_status == "not_estimated"
        assert loaded.acquisition_records == ()
        assert cycle.acquisition_cost_basis_record is None
        assert cycle.acquisition_cost_basis_hash is None
        assert cycle_owner._N7_SOURCE_SEMANTIC_EMISSION_ENABLED is False
        assert "n7_candidate_source_ref" not in request
        assert "n7_source_join_rule" not in request
        # A persisted COV refusal cannot satisfy the old costed WDI consumer.
        with pytest.raises(AcquisitionRouteClosureError, match=r"^costed_route_not_unique$"):
            resolve_completed_wdi_route(
                control, run_id=run_id, tenant_id=fixture.TENANT, cell_id=fixture.CELL
            )
        observed.append(str(report_ref.artifact_id))

    result = fixture._produce_served_acquisition_history(
        tmp_path,
        monkeypatch,
        served_recorded_candidate_gateway,
        source_owner_root=source.root,
        provider_mode="synthetic_settled_candidate",
        seed_only_observer=observe,
    )
    assert result is not None and result["run_id"] and result["job_id"]
    assert len(observed) == 1
