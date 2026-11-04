"""Selected mixed-plan lineage over the real CAS and compiler owner.

The N4/N5 parents here are component fixtures. This test does not establish a
served source, catalog absence, source admission, or numerical execution.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS, ProducerInfo
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import acquisition_planner as owner
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from polisyos.runtime.quality.generation_cycle import (
    ValuePortObservation,
    _CandidateN5L1RoutingObservation,
    _grounding_unavailable,
)
from tests.unit.runtime.quality.test_n7_descriptor_source_join import _compilation


def test_candidate_plan_binds_typed_source_and_every_reference_occurrence(tmp_path: Path) -> None:
    tenant = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    cell = "018f47a0-0000-7000-8000-000000000001"
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        store = FileSystemCAS(tmp_path / "cas").for_tenant(tenant, cell_id=cell)

        def parent(kind: str):
            return store.put_json(
                {"component_parent": kind},
                ArtifactWriteOptions(kind=kind, media_type="application/json"),
                return_selected_profile=True,
            )

        n4 = parent("runtime.quality.n4_candidate_scenario_source")
        context = parent("runtime.quality.cycle_substrate_context_job")
        n5_input = parent("runtime.quality.candidate_simulation_n5_input")
        execution = parent("runtime.quality.candidate_simulation_execution")
        result = parent("polisyos.runtime.joint_simulation_result")
        candidate_id = "candidate-source-join"
        candidate_hash = "sha256:" + "1" * 64
        problem_ref = "sha256:" + "2" * 64
        grounding = _grounding_unavailable(
            candidate_id,
            issue_codes=("cgf_disposition_missing",),
            candidate_content_hash=candidate_hash,
            design_problem_ref=problem_ref,
            authority_level="research",
        )
        digest_payload = {
            "candidate_id": candidate_id,
            "issue_codes": ["cgf_disposition_missing"],
            "source": "grounding_unavailable",
        }
        assert grounding.report_ref == gy_content_hash(digest_payload)
        assert grounding.acquisition_requirement is not None
        # Both roles deliberately carry the same SHA-looking *non-CAS* text.
        l1 = owner.l1_variable_availability_requirement_gap(
            candidate_id=candidate_id,
            candidate_content_hash=candidate_hash,
            design_problem_ref=problem_ref,
            authority_level="research",
            availability=L1VariableAvailability(
                variable_id="global.unemployment_rate",
                status="unavailable",
                dataset_count=0,
                metric_binding_count=0,
                observation_count=0,
                coverage_ref=grounding.report_ref,
            ),
        )
        routing = _CandidateN5L1RoutingObservation(
            source_ref=n4,
            context_job_ref=context,
            n5_input_ref=n5_input,
            n5_execution_ref=execution,
            n5_result_ref=result,
            requirement_gap=l1,
        )
        value = ValuePortObservation(
            candidate_id=candidate_id,
            authority_blockers=("candidate_scenario_n5_only",),
            candidate_n5_l1_routing=routing,
        )
        source = owner._N7ConfiguredCandidatePortSource(
            tenant_id=tenant,
            cell_id=cell,
            run_id="candidate-run",
            source_job_id="candidate-job",
            source_generation_run_id="generation-run",
            cycle_index=0,
            candidate_id=candidate_id,
            candidate_content_hash=candidate_hash,
            design_problem_basis_ref=problem_ref,
            n4_source_ref=n4,
            context_job_ref=context,
            n5_input_ref=n5_input,
            n5_execution_ref=execution,
            n5_result_ref=result,
            grounding_observation=grounding.model_dump(mode="json"),
            value_observation=value.model_dump(mode="json"),
            grounding_digest_payload=digest_payload,
            source_gap=l1,
            accompanying_requirement_gaps=(grounding.acquisition_requirement,),
        )
        port_ref = owner._n7_put_configured_candidate_port_source(store, source)
        assert port_ref.manifest_profile_sha256 is not None
        assert owner._n7_load_configured_candidate_port_source(store, port_ref) == source

        compilation = _compilation("labor.unemployment_rate", "total_labor_force")
        basis = owner.persist_and_verify_data_requirement_compilation_report(
            store, compilation, expected_scenario_id=compilation.scenario_id
        )
        gaps = owner._n7_candidate_n5_l1_obligation_gaps(
            source_gap=l1,
            accompanying_requirement_gaps=source.accompanying_requirement_gaps,
            specs=compilation.specs,
            capability_resolutions=compilation.capability_requirement_resolutions,
        )
        legacy = owner.plan_evidence_acquisition(
            run_id=f"n7-cycle:{compilation.scenario_id}:0",
            gaps=gaps,
            generated_at=datetime(2026, 11, 3, tzinfo=UTC),
            requirement_basis_binding=basis,
        )
        legacy_bytes = legacy.model_dump_json()
        report = owner._n7_bind_configured_candidate_report(
            store=store, report=legacy, port_source_ref=port_ref
        )
        report = owner.bind_acquisition_planner_report(
            report, planning_context_hash="sha256:" + "3" * 64
        )
        assert report.candidate_lineage is not None
        digest_rows = [
            item for item in report.candidate_lineage.bindings if item.value == grounding.report_ref
        ]
        assert len(digest_rows) == 2
        assert {item.source_kind for item in digest_rows} == {
            "grounding_digest",
            "l1_coverage_locator",
        }
        ref = owner.persist_and_verify_acquisition_planner_report(store, report)
        assert ref.manifest_profile_sha256 is not None
        assert owner._validate_persisted_planner_report(store=store, ref=ref, report=report) == ()
        manifest = store.get_manifest(ref)
        assert list(manifest.inputs) == owner.acquisition_report_inputs(report)
        assert [edge.role for edge in manifest.inputs] == [
            "configured_candidate_port_source",
            "data_requirement_compiler_report",
        ]
        assert all(str(edge.artifact_id) != grounding.report_ref for edge in manifest.inputs)
        assert legacy.model_dump_json() == legacy_bytes

        # Same source bytes under another manifest are not the producer view.
        options, _ = owner._n7_configured_port_write_profile(source)
        foreign = store.put_bytes(
            store.get_bytes(port_ref),
            replace(options, producer=ProducerInfo(component="foreign.fixture", version="1.0")),
            return_selected_profile=True,
        )
        assert foreign.artifact_id == port_ref.artifact_id
        assert foreign.manifest_profile_sha256 != port_ref.manifest_profile_sha256
        with pytest.raises(ValueError, match="source_profile_unverified"):
            owner._n7_load_configured_candidate_port_source(store, foreign)

        # Missing the exact selected owner view withdraws the report, even
        # though the report and an unrelated same-bytes view are still present.
        path = store._layout.view_manifest_path(
            port_ref.artifact_id, port_ref.manifest_profile_sha256
        )
        held = path.with_name(path.name + ".temporarily-unavailable")
        path.rename(held)
        try:
            assert owner._validate_persisted_planner_report(store=store, ref=ref, report=report)
        finally:
            held.rename(path)
        assert owner._validate_persisted_planner_report(store=store, ref=ref, report=report) == ()

        changed = list(report.candidate_lineage.bindings)
        changed[0] = changed[0].model_copy(update={"role": "voi_ranking"})
        with pytest.raises(ValueError, match="input_denominator_mismatch"):
            owner.AcquisitionPlannerReport.model_validate(
                {
                    **report.model_dump(mode="python"),
                    "candidate_lineage": report.candidate_lineage.model_copy(
                        update={"bindings": tuple(changed)}
                    ),
                }
            )
