"""Selected candidate experiment policy with explicit unknown information value.

The compiled, port and payload parents are component fixtures; this test does
not establish a signed request, protected route, source rights, or fetch permit.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from polisyos.runtime.http.services.control_registry_providers import (
    resolve_control_registry_providers,
)
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    POLICY_KIND,
    POLICY_SCHEMA,
    CandidateUnpricedAcquisitionPolicy,
    CandidateUnpricedPolicyBinding,
    issue_candidate_unpriced_experiment_policy,
    persist_candidate_unpriced_policy,
    read_candidate_unpriced_policy,
    reconcile_candidate_unpriced_work,
    resolve_current_candidate_unpriced_policy,
    verify_candidate_unpriced_experiment_policy_intent,
)
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from polisyos.runtime.quality.generation_cycle import (
    ValuePortObservation,
    _CandidateN5L1RoutingObservation,
    _grounding_unavailable,
)
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.quality.test_candidate_unpriced_policy import _component_policy, _parent
from tests.unit.runtime.quality.test_n7_descriptor_source_join import _compilation
from tests.unit.scientist.orchestration.engine.test_invocation_capacity_observation import _owner


class _PlannerReportRef(artifacts.ArtifactRef):
    """A semantic subtype with no additional selected-view fields."""


class _PlannerReportWithExtraMeaning(_PlannerReportRef):
    custody_note: str


def _selected_mixed_report(cas, scope):
    """Use the real selected V2 planner producer with component N4/N5 parents."""
    candidate_id = scope.candidate_id
    candidate_hash = scope.candidate_content_hash
    problem_ref = scope.design_problem_basis_ref
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
    gap = planner.l1_variable_availability_requirement_gap(
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
            coverage_ref="fixture://declared-unavailable/unemployment",
        ),
    )
    n4 = _parent(cas, "runtime.quality.n4_candidate_scenario_source", "n4")
    context = _parent(cas, "runtime.quality.cycle_substrate_context_job", "context")
    n5_input = _parent(cas, "runtime.quality.candidate_simulation_n5_input", "input")
    execution = _parent(cas, "runtime.quality.candidate_simulation_execution", "execution")
    result = _parent(cas, "polisyos.runtime.joint_simulation_result", "result")
    value = ValuePortObservation(
        candidate_id=candidate_id,
        authority_blockers=("candidate_scenario_n5_only",),
        candidate_n5_l1_routing=_CandidateN5L1RoutingObservation(
            source_ref=n4,
            context_job_ref=context,
            n5_input_ref=n5_input,
            n5_execution_ref=execution,
            n5_result_ref=result,
            requirement_gap=gap,
        ),
    )
    source = planner._N7ConfiguredCandidatePortSource(
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        run_id=scope.run_id,
        source_job_id=scope.source_job_id,
        source_generation_run_id="component-generation",
        cycle_index=scope.source_cycle_index,
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
        source_gap=gap,
        accompanying_requirement_gaps=(grounding.acquisition_requirement,),
    )
    port_ref = planner._n7_put_configured_candidate_port_source(cas, source)
    compilation = _compilation("labor.unemployment_rate", "total_labor_force")
    basis = planner.persist_and_verify_data_requirement_compilation_report(
        cas, compilation, expected_scenario_id=compilation.scenario_id
    )
    gaps = planner._n7_candidate_n5_l1_obligation_gaps(
        source_gap=gap,
        accompanying_requirement_gaps=source.accompanying_requirement_gaps,
        specs=compilation.specs,
        capability_resolutions=compilation.capability_requirement_resolutions,
    )
    report = planner.plan_evidence_acquisition(
        run_id=f"n7-cycle:{compilation.scenario_id}:{scope.source_cycle_index}",
        gaps=gaps,
        generated_at=datetime(2026, 11, 3, tzinfo=UTC),
        requirement_basis_binding=basis,
    )
    report = planner._n7_bind_configured_candidate_report(
        store=cas, report=report, port_source_ref=port_ref
    )
    report = planner.bind_acquisition_planner_report(
        report, planning_context_hash="sha256:" + "3" * 64
    )
    report_ref = planner.persist_and_verify_acquisition_planner_report(cas, report)
    selected = [
        row
        for row in report.acquisition_records
        if row.requirement_gap_ref == gap.requirement_gap_id
    ]
    assert len(selected) == 1
    return scope.model_copy(
        update={
            "planner_report_hash": agent_action_content_hash(report),
            "planner_report_ref": report_ref,
            "compiler_report_ref": basis.compiler_report_ref,
            "configured_port_source_ref": port_ref,
            "compiled_requirement_ref": selected[0].compiled_requirement_ref,
        }
    ), report


def test_selected_experiment_policy_preserves_v1_and_reopens_its_exact_v2_view(
    tmp_path: Path,
) -> None:
    """A configured V2 is a candidate declaration, with no inferred permit or VOI."""
    cas = artifacts.FileSystemCAS(tmp_path / "cas")
    base = _build_control_service(tmp_path / "control", artifact_store=cas)
    ledger, _, observer = _owner(tmp_path / "quota-ledger.json", total=2, protected=1)
    profile = observer.invocation_quota_profile
    assert profile is not None
    bound: ControlPlaneService | None = None
    try:
        with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
            scope, legacy, authorization = _component_policy(cas, profile)
            old_payload = legacy.model_dump(mode="json")
            assert "experiment_intent" not in old_payload
            assert "information_value" not in old_payload
            legacy_ref = persist_candidate_unpriced_policy(
                store=cas, event_log=base._diagnostic_event_log, policy=legacy
            )
            # The fixture's canonical V1 bytes were persisted by the same
            # owner before the V2 extension; this catches changed old bytes.
            assert str(legacy_ref.artifact_id) == (
                "sha256:df5a76a24c066721618074c159cc6623830e383b509d60226d4ec319d9deb1b0"
            )
            assert (
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=legacy_ref
                )
                == legacy
            )
            scope, report = _selected_mixed_report(cas, scope)
            # CAS canonical bytes contain a typed datetime; route hashes bind
            # the owner's validated JSON projection, a distinct hash layer.
            raw = artifacts.load_core_json_artifact(cas, scope.planner_report_ref)
            assert agent_action_content_hash(raw) != agent_action_content_hash(report)
            payload_ref = _parent(cas, "runtime.control_nl_job_payload", "request")
            policy = issue_candidate_unpriced_experiment_policy(
                scope=scope,
                live_authorization=authorization,
                n5_quota_profile=profile,
                source_payload_ref=str(payload_ref.artifact_id),
                request_content_hash="sha256:" + "8" * 64,
                original_metered_budget_usd=Decimal("5.00"),
                limitations=(
                    *legacy.limitations,
                    "candidate_experiment_voi_not_established",
                ),
            )
            assert legacy.model_dump(mode="json") == old_payload
            assert policy.purpose == "bounded_candidate_experiment_voi_unknown"
            assert policy.information_value == "not_established"
            assert policy.monetary_cost == "not_established"
            assert policy.hard_usd_reservation is False
            assert policy.publication_authority is False
            ref = persist_candidate_unpriced_policy(
                store=cas, event_log=base._diagnostic_event_log, policy=policy
            )
            manifest = cas.get_manifest(ref)
            assert manifest.artifact_schema == artifacts.SchemaInfo(
                name=POLICY_SCHEMA, version="2.0"
            )
            assert (
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=ref
                )
                == policy
            )
            providers = replace(
                resolve_control_registry_providers(),
                candidate_unpriced_policy_bindings=(
                    CandidateUnpricedPolicyBinding(scope=scope, policy_ref=ref),
                ),
            )
            bound = ControlPlaneService(
                cas_root=tmp_path / "cas",
                core_runs_root=tmp_path / "control" / "runs",
                artifact_store=cas,
                control_store=base._control_store,
                registry_providers=providers,
                policy_resolver=base._policy_resolver,
            )
            assert resolve_current_candidate_unpriced_policy(
                control_service=bound, scope=scope
            ) == (
                ref,
                policy,
            )
            # Compare the actual writer-selected planner view by its complete
            # identity, including profile, rather than its Python ref class.
            selected_parent = scope.planner_report_ref
            typed_parent = _PlannerReportRef.model_validate(
                selected_parent.model_dump(mode="python")
            )
            typed_scope = scope.model_copy(update={"planner_report_ref": typed_parent})
            assert resolve_current_candidate_unpriced_policy(
                control_service=bound, scope=typed_scope
            ) == (ref, policy)
            extended = _PlannerReportWithExtraMeaning(
                **selected_parent.model_dump(mode="python"), custody_note="additional semantics"
            )
            with pytest.raises(
                ValueError, match="candidate_unpriced_policy_selected_source_invalid"
            ):
                type(scope).model_validate(
                    {**scope.model_dump(mode="python"), "planner_report_ref": extended}
                )
            with pytest.raises(ValueError, match="candidate_unpriced_policy_not_selected"):
                resolve_current_candidate_unpriced_policy(
                    control_service=bound,
                    scope=scope.model_copy(update={"planner_report_ref": extended}),
                )
            parent_manifest = cas.get_manifest(selected_parent)
            sibling_parent = cas.put_bytes(
                cas.get_bytes(selected_parent),
                artifacts.ArtifactWriteOptions(
                    kind=selected_parent.kind,
                    media_type=selected_parent.media_type,
                    schema=parent_manifest.artifact_schema,
                    producer=artifacts.ProducerInfo(component="foreign.test.planner", version="1"),
                    canon=parent_manifest.canon,
                    inputs=parent_manifest.inputs,
                    governance=parent_manifest.governance,
                    tenant_context=parent_manifest.tenant_context,
                ),
                return_selected_profile=True,
            )
            assert sibling_parent.artifact_id == selected_parent.artifact_id
            assert sibling_parent.manifest_profile_sha256 != selected_parent.manifest_profile_sha256
            with pytest.raises(ValueError, match="candidate_unpriced_policy_not_selected"):
                resolve_current_candidate_unpriced_policy(
                    control_service=bound,
                    scope=scope.model_copy(update={"planner_report_ref": sibling_parent}),
                )
            before = ledger.snapshot()
            with pytest.raises(
                ValueError, match="candidate_experiment_policy_intent_not_established"
            ):
                reconcile_candidate_unpriced_work(
                    control_service=bound,
                    scope=scope,
                    policy_ref=ref,
                    action_phase_ref="sha256:" + "9" * 64,
                    live_authorization=authorization,
                    budget_observer=observer,
                    budget_state=observer._state,
                )
            assert ledger.snapshot() == before
            # A configured declaration and existing payload bytes cannot replace
            # the completed signed source-job owner.
            closure = SimpleNamespace(
                tenant_id=scope.tenant_id,
                cell_id=scope.cell_id,
                run_id=scope.run_id,
                source_job_id=scope.source_job_id,
                source_payload_ref=str(payload_ref.artifact_id),
                capability_manifest_ref="sha256:" + "6" * 64,
            )
            with pytest.raises(ValueError, match="acquisition_source_budget_job_not_established"):
                verify_candidate_unpriced_experiment_policy_intent(
                    control_service=bound, closure=closure, scope=scope, policy_ref=ref
                )
            assert ledger.snapshot() == before

            # The original request/decision values are load-bearing: deleting or
            # changing one must not silently recreate a V1 or a valid V2.
            encoded = policy.model_dump(mode="json")
            for field in (
                "experiment_intent",
                "information_value",
                "source_payload_ref",
                "request_content_hash",
                "original_metered_budget_usd",
            ):
                altered = dict(encoded)
                altered.pop(field)
                with pytest.raises(ValueError):
                    CandidateUnpricedAcquisitionPolicy.model_validate(altered)
            altered = {**encoded, "purpose": "bounded_candidate_research"}
            with pytest.raises(ValueError):
                CandidateUnpricedAcquisitionPolicy.model_validate(altered)

            foreign = cas.put_bytes(
                cas.get_bytes(ref),
                artifacts.ArtifactWriteOptions(
                    kind=POLICY_KIND,
                    media_type="application/json",
                    schema=manifest.artifact_schema,
                    producer=artifacts.ProducerInfo(component="foreign.test.policy", version="1"),
                    canon=manifest.canon,
                    inputs=manifest.inputs,
                    governance=manifest.governance,
                    tenant_context=manifest.tenant_context,
                ),
                return_selected_profile=True,
            )
            assert foreign.artifact_id == ref.artifact_id
            assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256
            with pytest.raises(ValueError, match="candidate_unpriced_policy_owner_mismatch"):
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=foreign
                )
            missing = scope.compiler_report_ref
            manifest_path = cas._manifest_path_for_ref(
                missing.artifact_id, missing.manifest_profile_sha256
            )
            held = manifest_path.with_name(manifest_path.name + ".held")
            manifest_path.rename(held)
            try:
                cold = artifacts.FileSystemCAS.open_existing_read_only(cas.root)
                with pytest.raises((FileNotFoundError, ValueError)):
                    read_candidate_unpriced_policy(
                        store=cold, event_log=base._diagnostic_event_log, ref=ref
                    )
            finally:
                held.rename(manifest_path)
            assert (
                read_candidate_unpriced_policy(
                    store=cas, event_log=base._diagnostic_event_log, ref=ref
                )
                == policy
            )
    finally:
        if bound is not None:
            bound._control_store.close()
        else:
            base._control_store.close()
