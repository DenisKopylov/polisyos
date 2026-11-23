"""Exercise the ordinary retained dispatcher through the real source reader."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from polisyos.core import artifacts
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality.acquisition_evaluation import AcquisitionEvaluationBasis
from polisyos.runtime.quality.generation_cycle import GenerationCycleController, GenerationCycleRun
from polisyos.runtime.quality.generation_source import GenerationSourceRepository
from polisyos.runtime.quality.substrate_registry import current_catalog_serving_source
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.quality.test_acquisition_evidence_transition import (
    controlled_draws as controlled_draws,
)
from tests.unit.runtime.quality.test_generation_cycle_model_input_wire import _v3_fixture
from tests.unit.runtime.quality.test_n5_prepared_configuration_owner import (
    _candidate_context_fixture,
)

if TYPE_CHECKING:
    from tests.unit.runtime.quality.test_acquisition_evidence_transition import _ControlledDraws


def test_ordinary_evaluation_rejects_foreign_persisted_job_route_scope(tmp_path: Path) -> None:
    """Use the actual job payload owner and live lease before resolving the N7 source."""
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.execution_policy import RuntimePrincipal
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        AcquisitionWorldGrowthConfig,
    )
    from tests._helpers.lane01_wdi_profiles import UNEMPLOYMENT_PROFILE, build_fixture_wdi_authority

    authority, _ = build_fixture_wdi_authority(tmp_path / "wdi", UNEMPLOYMENT_PROFILE)
    service = _build_control_service(tmp_path / "control")
    store = service._control_store
    bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(),
        repo_root=authority.repo_root,
        runtime_root=tmp_path / "runtime",
        authority=authority,
        artifact_store=service._artifact_store,
        event_log=service._diagnostic_event_log,
        epoch_deployment=None,
        control_store=store,
        action_head_sink=service.acquisition_route_sink,
        source_control_service=service,
    )
    principal = RuntimePrincipal(
        subject="ordinary-acquisition-reader",
        tenant_id="tenant-a",
        cell_id="cell-a",
        roles=frozenset({"analyst"}),
        authenticated=True,
    )
    route_id = "sha256:" + "a" * 64
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        for payload_run_id, reason in (
            ("foreign-run", "acquisition_evaluation_job_route_not_established"),
            ("admitted-run", "source_job_not_completed"),
        ):
            job = service.enqueue_acquisition_job(
                job_id=payload_run_id,
                run_id="admitted-run",
                payload={"run_id": payload_run_id, "route_id": route_id},
                principal=principal,
            )
            assert job.payload_ref is not None
            worker = "worker-" + payload_run_id
            leased = store.lease_next_job(worker_id=worker, lease_seconds=60)
            assert leased is not None and leased.job_id == job.job_id
            with store.job_execution_fence(
                job_id=job.job_id, worker_id=worker, attempt=leased.attempt
            ):
                admission = store.current_execution_job_admission()
                assert admission.scope.status == "established"
                assert admission.job.run_id == "admitted-run"
                payload = service._load_payload_ref(
                    job.payload_ref, kind="runtime.control_job_payload.acquisition"
                )
                assert (payload["run_id"], payload["route_id"]) == (payload_run_id, route_id)
                with pytest.raises(ValueError) as refusal:
                    dispatch._current_selection(bridge)
                assert str(refusal.value) == reason
            assert store.get_job(job.job_id) == leased


def test_ordinary_retention_composes_current_owner_and_reopens_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adapt the lease and N5 basis inputs while exercising composition and CAS reads."""
    _, handoff, store = _candidate_context_fixture(tmp_path)
    repo_root = Path(__file__).resolve().parents[4]
    service = _build_control_service(tmp_path, artifact_store=store, repo_root=repo_root)
    catalog = service.catalog_serving_source
    acquisition_root = tmp_path / "wdi" / "repo"
    acquisition_root.mkdir(parents=True)
    assert acquisition_root != catalog.repo_root

    def save(value: dict[str, object], kind: str) -> artifacts.ArtifactRef:
        return store.put_json(
            value,
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    source_payload_ref = save({"llm_models": ["fixture-model"]}, "test.source_payload")
    basis_ref = save({"effective_native_values_hex": "08"}, "test.current_basis")
    # The fixture deliberately carries no historical N4/N5 execution. The real
    # reader must reach the exact selected source, then refuse its unsupported view.
    source_ref = save({"fixture_source": "selected"}, "test.unqualified_retained_source")
    _, wire = _v3_fixture()
    run = GenerationCycleRun.model_validate(wire)
    old = run.cycles[-1]
    simulation = old.simulation.model_copy(
        update={
            "status": "joint_simulated",
            "simulation_result_ref": basis_ref,
            "candidate_simulation_n5_input_ref": basis_ref,
            "candidate_simulation_context_job_ref": handoff.context_job_ref,
            "diagnostics": {
                "candidate_simulation_n4_source_selected_ref": source_ref.model_dump(mode="json"),
            },
        }
    )
    cycle = old.model_copy(update={"simulation": simulation})
    run = run.model_copy(update={"run_id": handoff.run_id, "cycles": (*run.cycles[:-1], cycle)})
    prepared = SimpleNamespace(n5_execution_configuration=None)
    selection = SimpleNamespace(
        closure=SimpleNamespace(
            source_payload_ref=source_payload_ref,
            generation_run=run,
            source_cycle=cycle,
            design_problem_basis=None,
        ),
        phase_ref=basis_ref,
        growth_ref=basis_ref,
        growth=SimpleNamespace(selection=SimpleNamespace(reentry_budget_usd="0.5")),
        projection=object(),
        prepared=prepared,
        admitted_source_ref=source_ref,
    )
    bridge = SimpleNamespace(
        artifact_store=store,
        event_log=service._diagnostic_event_log,
        repo_root=acquisition_root,
        promotion_runtime=service._promotion_runtime,
        _source_control_service=service,
    )
    prior = SimpleNamespace(handoff=handoff)
    basis = AcquisitionEvaluationBasis.model_construct(
        comparison_profile="fixture",
        predicate_provenance="recomputed",
        reason_codes=(),
        preparation_inputs=prepared,
        effective_native_values_hex="08",
    )
    monkeypatch.setattr(dispatch, "_current_selection", lambda _: selection)
    monkeypatch.setattr(dispatch, "_basis_for_current", lambda *_: basis)

    def read_basis(*, store, event_log, ref, kind):
        assert event_log is service._diagnostic_event_log and kind == "basis"
        payload = artifacts.load_core_json_artifact(store, ref)
        return basis.model_copy(update=payload)

    monkeypatch.setattr(dispatch, "read_acquisition_basis_or_decision_artifact", read_basis)
    begin = GenerationCycleController._begin_source_run

    def observe_begin(controller: GenerationCycleController, run_id: str) -> None:
        assert controller._repo_root == catalog.repo_root
        assert current_catalog_serving_source() is catalog
        begin(controller, run_id)

    monkeypatch.setattr(GenerationCycleController, "_begin_source_run", observe_begin)
    reopened = []
    real_source_read = GenerationSourceRepository.load_candidate_scenario_source_in_owner_scope

    def observe_read(self, ref, **expected):
        assert self.store is store and current_catalog_serving_source() is catalog
        reopened.append((ref, expected))
        return real_source_read(self, ref, **expected)

    monkeypatch.setattr(
        GenerationSourceRepository, "load_candidate_scenario_source_in_owner_scope", observe_read
    )
    owner = dispatch.AcquisitionEvaluationCurrentOwner(bridge, basis_ref, selection, prior)
    assert owner.currentness_resolver() is True
    result = dispatch._current_cheap_continuation(owner)
    assert result.reason_code == "retained_cheap_prior_source_unresolved"
    assert reopened == [
        (
            source_ref,
            {
                "expected_run_id": handoff.run_id,
                "expected_tenant_id": handoff.tenant_id,
                "expected_cell_id": handoff.cell_id,
            },
        ),
    ]
    assert current_catalog_serving_source() is None

    changed_ref = save({"effective_native_values_hex": "09"}, "test.current_basis")
    changed = replace(owner, current_basis_ref=changed_ref)
    assert changed.currentness_resolver() is False
    with pytest.raises(ValueError, match=r"^acquisition_retained_current_basis_changed$"):
        dispatch._current_cheap_continuation(changed)
    assert len(reopened) == 1
    assert current_catalog_serving_source() is None


def test_ordinary_retained_replica_roundtrips_the_strict_wire_and_refuses_relabel(
    tmp_path: Path,
    controlled_draws: _ControlledDraws,  # noqa: F811
) -> None:
    """Exercise exact CAS and diagnostic readback for the actual local draw proof."""
    from pydantic import ValidationError

    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.acquisition_evaluation import (
        AcquisitionSelectedEvaluation,
        _parse_retained_continuation_wire,
        persist_acquisition_evaluation_artifact,
        read_acquisition_evaluation_artifact,
    )
    from polisyos.runtime.quality.acquisition_evidence_transition import (
        replay_controlled_acquisition_replica,
        resolve_controlled_acquisition_replica,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedContinuation,
        AcquisitionRetainedCurrentProjection,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash
    from polisyos.scientist.methods.search.voi_scheduler import SchedulingDecision

    store, plan_ref, previous, selected = controlled_draws
    database = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "retained.sqlite3")
    events = RuntimeDiagnosticEventLog(store=database, artifact_store=store)
    _, run_wire = _v3_fixture()
    run = GenerationCycleRun.model_validate(run_wire)
    cycle = run.cycles[-1]
    candidate = cycle.selected_candidate_ref
    tenant, cell, run_id, route = selected.route_key

    def parent(kind: str) -> artifacts.ArtifactRef:
        return store.put_json(
            {"component_parent": kind},
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    evaluation = AcquisitionSelectedEvaluation(
        candidate_id=candidate,
        candidate_content_hash=cycle.selected_candidate_content_hash,
        design_problem_ref=run.design_problem_ref,
        world_model_record_hash="sha256:" + "8" * 64,
        evaluation_job_id="previous-action-job",
        evaluation_run_id=run_id,
        generation_run_id=run.run_id,
        cycle_index=cycle.cycle_index,
        n4_source_ref=parent("runtime.quality.n4_candidate_scenario_source"),
        context_job_ref=parent("runtime.quality.cycle_substrate_context_job"),
        n5_input_ref=parent("runtime.quality.candidate_simulation_n5_input"),
        n5_execution_ref=parent("runtime.quality.candidate_simulation_execution"),
        n5_result_ref=parent("polisyos.runtime.joint_simulation_result"),
    )
    schedule = SchedulingDecision(
        candidate_id=candidate,
        priority=0.125,
        recommended_action="reject",
        reason="roi_below_threshold",
        economics={
            "candidate_id": candidate,
            "recommended_action": "reject",
            "expected_improvement_per_usd": 0.125,
            "expected_falsification_value": 0.0,
            "expected_governance_value": 0.0,
            "timeout_risk": 0.0,
            "replay_cost_usd": 0.0,
            "calibration_debt": 0.0,
            "current_pareto_position": "component",
        },
    )
    proof = resolve_controlled_acquisition_replica(
        store=store, plan_ref=plan_ref, previous_source=previous, selected_source=selected
    )
    draft = AcquisitionRetainedContinuation.model_construct(
        tenant_id=tenant,
        cell_id=cell,
        run_id=run_id,
        source_job_id="source-job",
        action_job_id="equal-replica-job",
        action_generation=selected.action_generation,
        route_id=route,
        compiled_ref="sha256:" + "7" * 64,
        design_problem_ref=run.design_problem_ref,
        candidate_id=candidate,
        selected_action_receipt_ref=parent("runtime_quality.acquisition_route_phase_receipt"),
        evaluation_decision_ref=parent("runtime_quality.acquisition_evaluation_decision"),
        current_basis_ref=parent("runtime_quality.acquisition_evaluation_basis"),
        growth_receipt_ref=selected.growth_ref,
        admitted_source_ref=selected.admitted_source_ref,
        retained_evaluation=evaluation,
        current_projection=AcquisitionRetainedCurrentProjection(
            source_cycle_index=cycle.cycle_index,
            selected_candidate_id=candidate,
            selected_candidate_content_hash=cycle.selected_candidate_content_hash,
            grounding=cycle.grounding,
            value_port=cycle.value_port.model_copy(update={"candidate_id": candidate}),
            execution_schedule=schedule,
            terminal_kind=cycle.terminal_kind,
            voi_decision=cycle.voi_decision,
            revision_request=cycle.revision_request,
            counterexample=cycle.counterexample,
            refinement_decision=cycle.refinement_decision,
            search_iteration=cycle.search_iteration,
        ),
        controlled_replica=proof,
        generated_at=proof.selected_sample.observed_at.isoformat(),
    )
    wire = draft.model_dump(mode="json", exclude={"content_hash"})
    body = {**wire, "content_hash": exact_n5_content_hash(wire)}
    with pytest.raises(ValidationError, match=r"controlled_replica\.previous_source\.route_key"):
        AcquisitionRetainedContinuation.model_validate(body)
    record = _parse_retained_continuation_wire(body)
    ref = persist_acquisition_evaluation_artifact(store=store, event_log=events, record=record)
    fresh = artifacts.FileSystemCAS(store.root)
    assert artifacts.load_core_json_artifact(fresh, ref) == body
    reopened = read_acquisition_evaluation_artifact(
        store=fresh, event_log=events, ref=ref, record_type=AcquisitionRetainedContinuation
    )
    assert reopened == record
    assert type(reopened) is AcquisitionRetainedContinuation
    assert reopened.controlled_replica == proof

    relabelled = deepcopy(wire)
    relabelled["controlled_replica"]["selected_sample"]["members"] = relabelled[
        "controlled_replica"
    ]["previous_sample"]["members"]
    tampered = _parse_retained_continuation_wire(
        {**relabelled, "content_hash": exact_n5_content_hash(relabelled)}
    )
    with pytest.raises(ValueError, match="controlled_replica_replay_mismatch"):
        replay_controlled_acquisition_replica(
            tampered.controlled_replica,
            store=fresh,
            plan_ref=plan_ref,
            previous_source=previous,
            selected_source=selected,
        )
