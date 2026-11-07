"""Real capture CAS/event behavior with explicitly adapted candidate parents.

The N4/N5 parents and live current owner are component fixtures. These checks
do not establish a served candidate, a lease, fresh port execution or N5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS, ProducerInfo, SchemaInfo
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionSelectedEvaluation,
    _candidate_evaluation_event_id,
    persist_acquisition_evaluation_artifact,
    read_acquisition_evaluation_artifact,
)
from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
    CandidateAcquisitionEvaluationCurrentOwner,
)
from polisyos.runtime.quality.acquisition_planner import (
    _N7ConfiguredCandidatePortSource,
    l1_variable_availability_requirement_gap,
)
from polisyos.runtime.quality.acquisition_retained_continuation import CandidateRetainedPortCapture
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import (
    ValuePortObservation,
    _CandidateN5L1RoutingObservation,
    _grounding_unavailable,
)
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash
from polisyos.scientist.orchestration.engine import ProducerBudgetObserver
from tests.unit.runtime.quality.test_acquisition_candidate_budget_window import (
    _prepare,
    _settle,
    _unit_window,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.quality.acquisition_evaluation import ResolvedAcquisitionEvaluation
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )


def test_retained_port_capture_requires_owner_scope_and_selected_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    budget = _unit_window(tmp_path, monkeypatch)
    _settle(budget, "capture-unit-producer", Decimal("0.20"))
    window = _prepare(budget)
    store = FileSystemCAS(tmp_path / "cas").for_tenant(
        budget.binding.tenant_id, cell_id=budget.binding.cell_id
    )
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
    budget.bridge.artifact_store = store
    budget.bridge.event_log = events

    def parent(kind: str, label: str) -> ArtifactRef:
        return store.put_json(
            {"component_parent": label},
            ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    action = parent("runtime_quality.acquisition_candidate_action_receipt", "action")
    intent = parent("runtime_quality.acquisition_candidate_world_intent", "intent")
    source = parent("runtime.quality.candidate_acquisition_source", "source")
    decision = parent("runtime_quality.acquisition_evaluation_decision", "decision")
    current_basis = parent("runtime_quality.acquisition_evaluation_basis", "current-basis")
    prior_basis = parent("runtime_quality.acquisition_evaluation_basis", "prior-basis")
    port_source = parent("runtime.quality.n7_configured_candidate_port_source", "port-source")
    selected = AcquisitionSelectedEvaluation(
        candidate_id="candidate-a",
        candidate_content_hash="sha256:" + "5" * 64,
        design_problem_ref="sha256:" + "4" * 64,
        world_model_record_hash="sha256:" + "6" * 64,
        evaluation_job_id="earlier-action-job",
        evaluation_run_id=budget.binding.run_id,
        generation_run_id="earlier-generation",
        cycle_index=2,
        n4_source_ref=parent("runtime.quality.n4_candidate_scenario_source", "n4"),
        context_job_ref=parent("runtime.quality.cycle_substrate_context_job", "context"),
        n5_input_ref=parent("runtime.quality.candidate_simulation_n5_input", "n5-input"),
        n5_execution_ref=parent("runtime.quality.candidate_simulation_execution", "n5-execution"),
        n5_result_ref=parent("polisyos.runtime.joint_simulation_result", "n5-result"),
        basis_ref=prior_basis,
    )
    owner = CandidateAcquisitionEvaluationCurrentOwner(
        bridge=budget.bridge,
        closure=budget.closure,
        candidate_action_ref=action,
        candidate_world_intent_ref=intent,
        current_basis_ref=current_basis,
        decision_ref=decision,
        prior=cast("ResolvedAcquisitionEvaluation", None),
        prepared_n5_configuration=cast("PreparedJointSimulationConfiguration", None),
    )

    def real_observer(*, closure: object, budget_state: object, reentry_budget_scope: object):
        assert closure is budget.closure
        observer = ProducerBudgetObserver(
            settlement_store=budget.service._llm_producer_settlement_store,
            producer_run_binding=budget.binding,
            budget_state=budget_state,
            reentry_budget_scope=reentry_budget_scope,
        )
        return observer

    monkeypatch.setattr(
        budget.service, "build_acquisition_source_budget_observer", real_observer, raising=False
    )
    _, observation = owner._budget_snapshot(window)
    payload = {
        "tenant_id": budget.binding.tenant_id,
        "cell_id": budget.binding.cell_id,
        "run_id": budget.binding.run_id,
        "source_job_id": budget.binding.control_job_id,
        "action_job_id": "current-action-job",
        "action_generation": 3,
        "route_id": "sha256:" + "1" * 64,
        "compiled_ref": "sha256:" + "2" * 64,
        "design_problem_ref": "sha256:" + "3" * 64,
        "design_problem_basis_ref": selected.design_problem_ref,
        "candidate_id": selected.candidate_id,
        "candidate_action_ref": action,
        "candidate_world_intent_ref": intent,
        "candidate_source_ref": source,
        "evaluation_decision_ref": decision,
        "current_basis_ref": current_basis,
        "retained_evaluation": selected,
        "configured_port_source_ref": port_source,
        "catalog_content_ref": "catalog_read_source_content://sha256:" + "7" * 64,
        "budget_observation_before": observation,
        "budget_observation_after": observation,
        "generated_at": datetime(2026, 11, 4, tzinfo=UTC).isoformat(),
    }
    draft = CandidateRetainedPortCapture.model_construct(**payload, content_hash="")
    capture = CandidateRetainedPortCapture.model_validate(
        {
            **payload,
            "content_hash": exact_n5_content_hash(
                draft.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )

    # The generic evaluation writer cannot mint a capture outside its current
    # owner scope. The unit scope below adapts only the live owner recheck.
    with pytest.raises(ValueError, match="candidate_retained_port_writer_scope_not_established"):
        persist_acquisition_evaluation_artifact(store=store, event_log=events, record=capture)
    assert not events.list_events(run_id=capture.run_id, job_id=capture.source_job_id, limit=10)
    monkeypatch.setattr(CandidateAcquisitionEvaluationCurrentOwner, "revalidate", lambda _: None)
    token = dispatch._CANDIDATE_RETAINED_PORT_SCOPE.set(
        dispatch._CandidateRetainedPortScope(owner, capture)
    )
    try:
        ref = persist_acquisition_evaluation_artifact(store=store, event_log=events, record=capture)
    finally:
        dispatch._CANDIDATE_RETAINED_PORT_SCOPE.reset(token)
    assert ref.manifest_profile_sha256 is not None
    assert (
        read_acquisition_evaluation_artifact(
            store=store, event_log=events, ref=ref, record_type=CandidateRetainedPortCapture
        )
        == capture
    )
    assert len(events.list_events(event_id=_candidate_evaluation_event_id(capture), limit=2)) == 1

    sibling = store.put_json(
        capture.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=capture.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=capture.ARTIFACT_SCHEMA_NAME, version="1.0"),
            producer=ProducerInfo(component="foreign.fixture", version="1.0"),
        ),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == ref.artifact_id
    assert sibling.manifest_profile_sha256 != ref.manifest_profile_sha256
    with pytest.raises(ValueError, match="acquisition_evaluation_artifact_owner_mismatch"):
        read_acquisition_evaluation_artifact(
            store=store, event_log=events, ref=sibling, record_type=CandidateRetainedPortCapture
        )
    other_control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "missing.sqlite3")
    without_event = RuntimeDiagnosticEventLog(store=other_control, artifact_store=store)
    with pytest.raises((ValueError, RuntimeError), match=r"event|authority"):
        read_acquisition_evaluation_artifact(
            store=store, event_log=without_event, ref=ref, record_type=CandidateRetainedPortCapture
        )


def test_retained_port_refuses_changed_ledger_before_capture_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A zero-cost event changes the actual ledger without changing USD spend."""
    from polisyos.runtime.quality import acquisition_planner, substrate_registry
    from polisyos.runtime.quality.acquisition_evaluation import (
        CandidateAcquisitionEvaluationDecision,
    )

    case = _unit_window(tmp_path, monkeypatch)
    _settle(case, "capture-initial", Decimal("0.20"))
    window = _prepare(case)
    store = FileSystemCAS(tmp_path / "cas").for_tenant(
        case.binding.tenant_id, cell_id=case.binding.cell_id
    )

    def parent(kind: str, label: str) -> ArtifactRef:
        return store.put_json(
            {"component_parent": label},
            ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    candidate_id = "candidate-a"
    candidate_hash = "sha256:" + "5" * 64
    problem_ref = "sha256:" + "4" * 64
    selected = AcquisitionSelectedEvaluation(
        candidate_id=candidate_id,
        candidate_content_hash=candidate_hash,
        design_problem_ref=problem_ref,
        world_model_record_hash="sha256:" + "6" * 64,
        evaluation_job_id="earlier-action-job",
        evaluation_run_id=case.binding.run_id,
        generation_run_id="earlier-generation",
        cycle_index=2,
        n4_source_ref=parent("runtime.quality.n4_candidate_scenario_source", "n4"),
        context_job_ref=parent("runtime.quality.cycle_substrate_context_job", "context"),
        n5_input_ref=parent("runtime.quality.candidate_simulation_n5_input", "n5-input"),
        n5_execution_ref=parent("runtime.quality.candidate_simulation_execution", "n5-execution"),
        n5_result_ref=parent("polisyos.runtime.joint_simulation_result", "n5-result"),
        basis_ref=parent("runtime_quality.acquisition_evaluation_basis", "prior-basis"),
    )
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
    gap = l1_variable_availability_requirement_gap(
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
            coverage_ref="coverage:unit",
        ),
    )
    routing = _CandidateN5L1RoutingObservation(
        source_ref=selected.n4_source_ref,
        context_job_ref=selected.context_job_ref,
        n5_input_ref=selected.n5_input_ref,
        n5_execution_ref=selected.n5_execution_ref,
        n5_result_ref=selected.n5_result_ref,
        requirement_gap=gap,
    )
    value = ValuePortObservation(
        candidate_id=candidate_id,
        authority_blockers=("candidate_scenario_n5_only",),
        candidate_n5_l1_routing=routing,
    )
    source = _N7ConfiguredCandidatePortSource(
        tenant_id=case.binding.tenant_id,
        cell_id=case.binding.cell_id,
        run_id=case.binding.run_id,
        source_job_id=selected.evaluation_job_id,
        source_generation_run_id=selected.generation_run_id,
        cycle_index=selected.cycle_index,
        candidate_id=candidate_id,
        candidate_content_hash=candidate_hash,
        design_problem_basis_ref=problem_ref,
        n4_source_ref=selected.n4_source_ref,
        context_job_ref=selected.context_job_ref,
        n5_input_ref=selected.n5_input_ref,
        n5_execution_ref=selected.n5_execution_ref,
        n5_result_ref=selected.n5_result_ref,
        grounding_observation=grounding.model_dump(mode="json"),
        value_observation=value.model_dump(mode="json"),
        grounding_digest_payload=digest_payload,
        source_gap=gap,
        accompanying_requirement_gaps=(grounding.acquisition_requirement,),
    )
    closure = SimpleNamespace(
        tenant_id=case.binding.tenant_id,
        cell_id=case.binding.cell_id,
        run_id=case.binding.run_id,
        source_job_id=case.binding.control_job_id,
        source_cycle=SimpleNamespace(value_port=SimpleNamespace(candidate_n5_l1_routing=None)),
    )
    case.bridge.artifact_store = store
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "capture-control.sqlite3")
    case.bridge.event_log = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
    catalog = object()
    case.service.catalog_serving_source = catalog
    owner = CandidateAcquisitionEvaluationCurrentOwner(
        bridge=case.bridge,
        closure=closure,
        candidate_action_ref=parent(
            "runtime_quality.acquisition_candidate_action_receipt", "action"
        ),
        candidate_world_intent_ref=parent(
            "runtime_quality.acquisition_candidate_world_intent", "intent"
        ),
        current_basis_ref=parent("runtime_quality.acquisition_evaluation_basis", "current-basis"),
        decision_ref=parent("runtime_quality.acquisition_evaluation_decision", "decision"),
        prior=cast("ResolvedAcquisitionEvaluation", SimpleNamespace(selected=selected)),
        prepared_n5_configuration=cast("PreparedJointSimulationConfiguration", None),
    )
    decision = CandidateAcquisitionEvaluationDecision.model_construct(
        prior_evaluation=selected, prior_basis_ref=selected.basis_ref
    )
    expected_closure = closure

    def real_observer(*, closure: object, budget_state: object, reentry_budget_scope: object):
        assert closure is expected_closure
        observer = ProducerBudgetObserver(
            settlement_store=case.service._llm_producer_settlement_store,
            producer_run_binding=case.binding,
            budget_state=budget_state,
            reentry_budget_scope=reentry_budget_scope,
        )
        return observer

    monkeypatch.setattr(
        case.service, "build_acquisition_source_budget_observer", real_observer, raising=False
    )
    monkeypatch.setattr(CandidateAcquisitionEvaluationCurrentOwner, "revalidate", lambda _: None)
    monkeypatch.setattr(
        CandidateAcquisitionEvaluationCurrentOwner,
        "current_budget_snapshot",
        lambda self, *, budget_state=None: self._budget_snapshot(window, budget_state=budget_state),
    )
    monkeypatch.setattr(dispatch, "read_acquisition_evaluation_artifact", lambda **_: decision)
    monkeypatch.setattr(substrate_registry, "current_catalog_serving_source", lambda: catalog)
    monkeypatch.setattr(
        substrate_registry,
        "_catalog_content_ref",
        lambda _: "catalog_read_source_content://sha256:" + "7" * 64,
    )
    monkeypatch.setattr(
        acquisition_planner,
        "_n7_put_configured_candidate_port_source",
        lambda *_: pytest.fail("changed budget must refuse before source persistence"),
    )
    fence = owner.begin_retained_port_capture()
    _settle(case, "capture-zero-cost-event", Decimal("0"))
    with pytest.raises(ValueError, match="candidate_retained_port_budget_changed"):
        owner.capture_retained_port_source(source, fence=fence)
