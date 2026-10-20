"""Integration coverage for the persisted N7 basis at served route intake."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tests._helpers.acquisition_served_history import (
    _produce_served_acquisition_history,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def test_served_acquisition_binds_n7_compiler_and_planner_cas_before_reentry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: object,
) -> None:
    """The ordinary served route consumes owner-read N7 reports and re-enters N5.

    The two missing-read probes keep every ref, schema marker, and embedded
    report intact while removing only the selected planner or compiler CAS
    bytes from the actual route resolver.
    """

    from polisyos.core import canon
    from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.runtime.quality.acquisition_planner import (
        load_acquisition_planner_report,
        validate_persisted_acquisition_planner_report,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRouteClosureError,
        AcquisitionRouteLoop,
        VerifiedAcquisitionRouteClosure,
    )

    resolved: list[tuple[AcquisitionRouteLoop, VerifiedAcquisitionRouteClosure]] = []
    removal_controls: set[str] = set()
    original_resolve = AcquisitionRouteLoop.resolve_current_route

    def remove_one_cas_read(
        loop: AcquisitionRouteLoop,
        *,
        run_id: str,
        before_action_generation: int | None,
        action_job_id: str | None,
        target_ref: ArtifactRef,
        expected_code: str,
    ) -> None:
        target_id = target_ref.artifact_id
        target_identity = artifact_ref_identity_key(target_ref)
        original_get_bytes = loop._artifact_store.get_bytes

        def missing_selected_artifact(selector: object) -> bytes:
            selected_identity = (
                artifact_ref_identity_key(selector)
                if isinstance(selector, ArtifactRef)
                else str(selector)
            )
            if selected_identity == target_identity or selected_identity == str(target_id):
                raise FileNotFoundError("controlled_missing_bound_cas_object")
            return original_get_bytes(selector)

        with monkeypatch.context() as removal_patch:
            removal_patch.setattr(
                loop._artifact_store,
                "get_bytes",
                missing_selected_artifact,
            )
            with pytest.raises(AcquisitionRouteClosureError, match=expected_code):
                original_resolve(
                    loop,
                    run_id=run_id,
                    before_action_generation=before_action_generation,
                    action_job_id=action_job_id,
                )

    def capture_route(
        loop: AcquisitionRouteLoop,
        *,
        run_id: str,
        before_action_generation: int | None = None,
        action_job_id: str | None = None,
    ) -> VerifiedAcquisitionRouteClosure:
        closure = original_resolve(
            loop,
            run_id=run_id,
            before_action_generation=before_action_generation,
            action_job_id=action_job_id,
        )
        resolved.append((loop, closure))
        if not removal_controls:
            report = closure.planner_report
            basis_binding = report.requirement_basis_binding
            planner_ref = closure.route_source_cycle.acquisition_routing_report_ref
            assert basis_binding is not None
            assert planner_ref is not None
            assert report == closure.route_source_cycle.acquisition_routing_report

            with tenant_scope(None, tenant_id=closure.tenant_id, cell_id=closure.cell_id):
                assert (
                    validate_persisted_acquisition_planner_report(
                        loop._artifact_store,
                        planner_ref,
                        report,
                        expected_scenario_id=closure.design_problem.design_problem_id,
                        expected_compiled_requirement_ref=(
                            closure.planner_record.compiled_requirement_ref
                        ),
                    )
                    == ()
                )
                persisted_report = load_acquisition_planner_report(
                    loop._artifact_store,
                    planner_ref,
                )
                assert persisted_report == report
                compiler_report = DataRequirementCompilationReport.model_validate(
                    canon.from_canonical_bytes(
                        loop._artifact_store.get_bytes(basis_binding.compiler_report_ref)
                    )
                )

            assert type(compiler_report) is DataRequirementCompilationReport
            assert compiler_report.scenario_id == closure.design_problem.design_problem_id
            assert basis_binding.scenario_id == compiler_report.scenario_id
            assert basis_binding.producer_report_ref == compiler_report.producer_report_ref
            assert basis_binding.input_content_hash == compiler_report.input_content_hash
            assert basis_binding.resolution == compiler_report.requirement_basis
            assert f"run:{compiler_report.run_id}" in compiler_report.subject_refs
            assert f"scenario:{closure.design_problem.design_problem_id}" in (
                compiler_report.subject_refs
            )
            compiled_requirement_ids = {spec.requirement_id for spec in compiler_report.specs}
            assert closure.planner_record.compiled_requirement_ref in compiled_requirement_ids
            removal_controls.add("reports_bound_and_read_back")

            remove_one_cas_read(
                loop,
                run_id=run_id,
                before_action_generation=before_action_generation,
                action_job_id=action_job_id,
                target_ref=planner_ref,
                expected_code="acquisition_planner_report_readback_failed",
            )
            removal_controls.add("planner_cas_missing")
            remove_one_cas_read(
                loop,
                run_id=run_id,
                before_action_generation=before_action_generation,
                action_job_id=action_job_id,
                target_ref=basis_binding.compiler_report_ref,
                expected_code="n7_compiler_report_readback_failed",
            )
            removal_controls.add("compiler_cas_missing")
        return closure

    monkeypatch.setattr(AcquisitionRouteLoop, "resolve_current_route", capture_route)
    result = _produce_served_acquisition_history(
        tmp_path,
        monkeypatch,
        served_recorded_candidate_gateway,
    )

    assert result is not None
    assert removal_controls == {
        "reports_bound_and_read_back",
        "planner_cas_missing",
        "compiler_cas_missing",
    }
    assert resolved
    first_loop, initial = next(
        (loop, closure)
        for loop, closure in resolved
        if closure.source_cycle.cycle_index == closure.route_source_cycle_index
    )
    continued = max(
        (
            closure
            for _, closure in resolved
            if closure.source_cycle.cycle_index > closure.route_source_cycle_index
        ),
        key=lambda closure: closure.source_cycle.cycle_index,
    )
    assert continued.run_id == initial.run_id
    assert continued.route_id == initial.route_id
    assert continued.route_source_cycle == initial.source_cycle
    assert continued.source_cycle.cycle_index == initial.route_source_cycle_index + 1
    assert continued.source_cycle.selected_candidate_ref == (
        initial.source_cycle.selected_candidate_ref
    )
    prior_n5 = initial.source_cycle.simulation.candidate_simulation_n5_input_ref
    continued_n5 = continued.source_cycle.simulation.candidate_simulation_n5_input_ref
    prior_context = initial.source_cycle.simulation.candidate_simulation_context_job_ref
    continued_context = continued.source_cycle.simulation.candidate_simulation_context_job_ref
    assert prior_n5 is not None
    assert continued_n5 is not None
    assert prior_context is not None
    assert continued_context is not None
    assert artifact_ref_identity_key(prior_n5) != artifact_ref_identity_key(continued_n5)
    assert artifact_ref_identity_key(prior_context) != artifact_ref_identity_key(continued_context)
    assert first_loop._artifact_store is resolved[-1][0]._artifact_store
