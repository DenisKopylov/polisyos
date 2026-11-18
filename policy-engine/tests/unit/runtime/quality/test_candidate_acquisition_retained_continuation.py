"""Owner-boundary checks for retained candidate continuation replay."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import pytest

from polisyos.runtime.quality.acquisition_evaluation import CandidateAcquisitionEvaluationDecision
from polisyos.runtime.quality.acquisition_retained_continuation import (
    read_candidate_acquisition_retained_continuation,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentTerminalReceipt,
    VerifiedAcquisitionRouteClosure,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts import ArtifactRef, CoreJSONArtifactStore
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


def test_retained_reader_requires_one_typed_prior_source_owner() -> None:
    """A retained read cannot infer or cast its source from a candidate record."""
    decision = CandidateAcquisitionEvaluationDecision.model_construct()
    terminal = AcquisitionCandidateExperimentTerminalReceipt.model_construct()

    def read(*, closure: object | None = None, origin: object | None = None) -> None:
        read_candidate_acquisition_retained_continuation(
            store=cast("CoreJSONArtifactStore", None),
            event_log=cast("RuntimeDiagnosticEventLog", None),
            control_store=cast("ControlPlaneStore", None),
            ref=cast("ArtifactRef", None),
            decision=decision,
            terminal=terminal,
            prior_closure=cast("VerifiedAcquisitionRouteClosure | None", closure),
            prior_experiment_origin=cast("VerifiedCandidateExperimentOrigin | None", origin),
        )

    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read()
    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read(closure=object(), origin=object())
    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read(closure=object())
    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read(origin=object())


def test_costed_owner_cannot_be_paired_with_experiment_terminal() -> None:
    """A costed closure never stands in for the separate experiment owner."""
    decision = CandidateAcquisitionEvaluationDecision.model_construct(
        comparison_result="equivalent",
        predicate_provenance="recomputed",
    )
    closure = VerifiedAcquisitionRouteClosure.model_construct()
    terminal = AcquisitionCandidateExperimentTerminalReceipt.model_construct(
        terminal_outcome="candidate_evaluation_retained",
        current_continuation_ref=None,
    )

    with pytest.raises(ValueError, match="candidate_retained_owner_scope_not_established"):
        read_candidate_acquisition_retained_continuation(
            store=cast("CoreJSONArtifactStore", None),
            event_log=cast("RuntimeDiagnosticEventLog", None),
            control_store=cast("ControlPlaneStore", None),
            ref=cast("ArtifactRef", None),
            decision=decision,
            terminal=terminal,
            prior_closure=closure,
        )


def test_experiment_reader_binds_inner_run_and_compiled_view_through_verified_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The digest joins the record while the verified scope binds its full profile."""
    from dataclasses import replace

    from polisyos.runtime.quality import (
        acquisition_evaluation,
        acquisition_retained_continuation,
        acquisition_route_loop,
    )
    from polisyos.runtime.quality.acquisition_evaluation import (
        AcquisitionSelectedEvaluation,
        issue_candidate_acquisition_evaluation_decision,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        CandidateAcquisitionRetainedContinuation,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedPolicyScope,
    )
    from polisyos.runtime.quality.design_problem import DesignProblem
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleRecord,
        GenerationCycleRun,
        _problem_ref,
    )
    from tests.unit.runtime.quality.test_acquisition_route_loop import _reuse_terminal_payload
    from tests.unit.runtime.quality.test_candidate_acquisition_world import _problem
    from tests.unit.runtime.quality.test_candidate_experiment_route_receipts import _hash, _ref

    outer_run_id = "R_45571964916cd28a"
    inner_run_id = "generation_cycle_0e3c7d55ebe3f1ff"
    problem: DesignProblem = _problem()
    problem_ref = _problem_ref(problem)
    payload = _reuse_terminal_payload("candidate_evaluation_retained")
    payload["run_id"] = outer_run_id
    scope = cast("CandidateUnpricedPolicyScope", payload["policy_scope"])
    scope = scope.model_copy(
        update={
            "run_id": outer_run_id,
            "design_problem_ref": problem_ref,
            "design_problem_basis_ref": problem_ref,
        }
    )
    payload["policy_scope"] = scope
    selected = cast("AcquisitionSelectedEvaluation", payload["selected_evaluation"])
    selected = selected.model_copy(
        update={
            "evaluation_run_id": outer_run_id,
            "generation_run_id": inner_run_id,
            "design_problem_ref": problem_ref,
        }
    )
    payload["selected_evaluation"] = selected
    terminal = AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(payload)
    cycle = GenerationCycleRecord.model_construct(
        cycle_index=scope.source_cycle_index,
        design_problem_ref=problem_ref,
        design_problem_basis_ref=problem_ref,
        selected_candidate_ref=scope.candidate_id,
        selected_candidate_content_hash=scope.candidate_content_hash,
        voi_decision=terminal.voi_decision,
    )
    generation_run = GenerationCycleRun.model_construct(
        run_id=inner_run_id,
        design_problem_ref=problem_ref,
        cycles=(cycle,),
    )
    origin = VerifiedCandidateExperimentOrigin(
        schema_version="polisyos.runtime.candidate_experiment_origin.v1",
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
        run_id=outer_run_id,
        source_job_id=terminal.source_job_id,
        source_payload_ref=terminal.source_payload_ref,
        capability_manifest_ref=terminal.capability_manifest_ref,
        request_content_hash=terminal.request_content_hash,
        route_id=terminal.route_id,
        policy_ref=terminal.policy_ref,
        policy_scope=scope,
        generation_run=generation_run,
        source_cycle=cycle,
        design_problem_basis=problem,
        planner_report=cast("Any", None),
        planner_record=cast("Any", None),
    )

    wrong_profile_scope = scope.model_copy(
        update={
            "compiled_ref": scope.compiled_ref.model_copy(
                update={"manifest_profile_sha256": _hash("c")}
            )
        }
    )
    wrong_profile_payload = terminal.model_dump(mode="python")
    wrong_profile_payload["policy_scope"] = wrong_profile_scope
    wrong_profile_terminal = AcquisitionCandidateExperimentTerminalReceiptV2.model_validate(
        wrong_profile_payload
    )
    assert wrong_profile_terminal.compiled_ref.artifact_id == terminal.compiled_ref.artifact_id
    assert (
        wrong_profile_terminal.compiled_ref.manifest_profile_sha256
        != terminal.compiled_ref.manifest_profile_sha256
    )

    class SelectedJoinReachedError(Exception):
        """Sentinel proving the selected digest join passed before historical replay."""

    selected_record: CandidateAcquisitionRetainedContinuation | None = None
    artifact_read_count = 0

    def return_selected_record(**kwargs: object) -> object:
        nonlocal artifact_read_count
        assert kwargs["ref"] == terminal.current_continuation_ref
        assert kwargs["record_type"] is CandidateAcquisitionRetainedContinuation
        assert selected_record is not None
        artifact_read_count += 1
        return selected_record

    def stop_before_prior_replay(**_kwargs: object) -> object:
        raise SelectedJoinReachedError

    monkeypatch.setattr(
        acquisition_route_loop,
        "_candidate_experiment_effective_source",
        lambda _origin: (generation_run, cycle),
    )
    monkeypatch.setattr(
        acquisition_retained_continuation,
        "read_acquisition_evaluation_artifact",
        return_selected_record,
    )
    monkeypatch.setattr(
        acquisition_evaluation,
        "resolve_selected_acquisition_evaluation_parts",
        stop_before_prior_replay,
    )

    def read(
        *,
        decision_generation_run_id: str,
        scope_run_id: str = outer_run_id,
        terminal_override: AcquisitionCandidateExperimentTerminalReceiptV2 | None = None,
    ) -> None:
        nonlocal selected_record
        selected_terminal = terminal if terminal_override is None else terminal_override
        selected_prior = selected.model_copy(
            update={"generation_run_id": decision_generation_run_id}
        )
        decision = issue_candidate_acquisition_evaluation_decision(
            tenant_id=selected_terminal.tenant_id,
            cell_id=selected_terminal.cell_id,
            run_id=selected_terminal.run_id,
            source_job_id=selected_terminal.source_job_id,
            action_job_id=selected_terminal.job_id,
            action_generation=selected_terminal.action_generation,
            route_id=selected_terminal.route_id,
            compiled_ref=str(scope.compiled_ref.artifact_id),
            design_problem_ref=scope.design_problem_ref,
            design_problem_basis_ref=scope.design_problem_basis_ref,
            candidate_id=scope.candidate_id,
            source_candidate_content_hash=scope.candidate_content_hash,
            candidate_action_ref=selected_terminal.candidate_action_ref,
            candidate_world_intent_ref=_ref(
                "runtime_quality.acquisition_candidate_world_intent", "a"
            ),
            candidate_source_ref=_ref("runtime.quality.candidate_acquisition_source", "b"),
            current_basis_ref=selected_terminal.selected_basis_ref,
            prior_basis_ref=selected_terminal.selected_basis_ref,
            prior_evaluation=selected_prior,
            comparison_result="equivalent",
            predicate_provenance="recomputed",
            reason_codes=(),
            expected_frontier_revision=1,
            expected_frontier_ref=_hash("e"),
            generated_at=selected_terminal.generated_at.isoformat(),
            reuse_occurrence_ref=selected_terminal.reuse_occurrence_ref,
            decision_version="2.0",
        )
        selected_record = CandidateAcquisitionRetainedContinuation.model_construct(
            tenant_id=decision.tenant_id,
            cell_id=decision.cell_id,
            run_id=decision.run_id,
            source_job_id=decision.source_job_id,
            action_job_id=decision.action_job_id,
            action_generation=decision.action_generation,
            route_id=decision.route_id,
            compiled_ref=decision.compiled_ref,
            design_problem_ref=decision.design_problem_ref,
            design_problem_basis_ref=decision.design_problem_basis_ref,
            candidate_id=decision.candidate_id,
            candidate_action_ref=decision.candidate_action_ref,
            reuse_occurrence_ref=selected_terminal.reuse_occurrence_ref,
            candidate_world_intent_ref=decision.candidate_world_intent_ref,
            candidate_source_ref=decision.candidate_source_ref,
            evaluation_decision_ref=selected_terminal.evaluation_decision_ref,
            current_basis_ref=decision.current_basis_ref,
            retained_evaluation=decision.prior_evaluation,
            current_projection=cast("Any", None),
            retained_port_capture_ref=_ref("runtime_quality.candidate_retained_port_capture", "f"),
            budget_observation_before=cast("Any", None),
            budget_observation_after=cast("Any", None),
            limitations=("prior evaluator replay remains required",),
            generated_at=selected_terminal.generated_at.isoformat(),
            content_hash=_hash("9"),
        )
        selected_origin = (
            origin
            if scope_run_id == outer_run_id
            else replace(origin, policy_scope=scope.model_copy(update={"run_id": scope_run_id}))
        )
        read_candidate_acquisition_retained_continuation(
            store=cast("CoreJSONArtifactStore", None),
            event_log=cast("RuntimeDiagnosticEventLog", None),
            control_store=cast("ControlPlaneStore", None),
            ref=cast("ArtifactRef", selected_terminal.current_continuation_ref),
            decision=decision,
            terminal=selected_terminal,
            prior_experiment_origin=selected_origin,
        )

    with pytest.raises(SelectedJoinReachedError):
        read(decision_generation_run_id=inner_run_id)
    with pytest.raises(ValueError, match="candidate_retained_experiment_source_not_established"):
        read(decision_generation_run_id="generation_cycle_foreign")
    with pytest.raises(ValueError, match="candidate_retained_experiment_source_not_established"):
        read(decision_generation_run_id=inner_run_id, scope_run_id="R_foreign_control")

    reads_before_profile_control = artifact_read_count
    with pytest.raises(ValueError, match="candidate_retained_experiment_source_not_established"):
        read(
            decision_generation_run_id=inner_run_id,
            terminal_override=wrong_profile_terminal,
        )
    assert artifact_read_count == reads_before_profile_control


@pytest.mark.parametrize("normalize_wire", [False, True], ids=["preimage", "canonical_wire"])
def test_retained_producer_persists_exact_compiler_wire_and_refuses_corruption(
    tmp_path: Path, normalize_wire: bool
) -> None:
    """Live compiler metadata round-trips through real CAS/event owners without N5.

    Named selected parents and cheap diagnostics are component fixtures. They
    establish the retained artifact's producer/readback contract, not a live
    lease, selected generation history, or numerical/publication authority.
    """
    from contextlib import closing
    from copy import deepcopy
    from datetime import UTC, datetime

    from polisyos.core.artifacts import ArtifactWriteOptions, FileSystemCAS
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
    from polisyos.runtime.quality.acquisition_evaluation import (
        AcquisitionSelectedEvaluation,
        persist_acquisition_evaluation_artifact,
        read_acquisition_evaluation_artifact,
    )
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionPlannerReport,
        AcquisitionWorldSnapshot,
        persist_and_verify_acquisition_planner_report,
        persist_and_verify_data_requirement_compilation_report,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedCurrentProjection,
        AcquisitionRetainedPlannerInputs,
        CandidateAcquisitionRetainedContinuation,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.generation_cycle import (
        LoopVOIDecision,
        ValuePortObservation,
        _counterexample_record,
        _default_revision_request,
        _grounding_unavailable,
        _refinement_decision,
        _search_iteration,
    )
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash
    from polisyos.scientist.methods.search.voi_scheduler import SchedulingDecision
    from polisyos.scientist.orchestration.engine import ProducerBudgetObserver
    from tests._helpers.lane01_candidate_source import compile_lane01_candidate_report
    from tests.unit.runtime.quality.test_candidate_acquisition_world import _problem
    from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import (
        _owner,
        _settle,
    )

    middleware, binding, budget_state = _owner(tmp_path)
    _settle(middleware, binding, "retained-compiler-input", "0.20")
    observation = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=budget_state,
    ).observe()
    store = FileSystemCAS(tmp_path / "cas").for_tenant(binding.tenant_id, cell_id=binding.cell_id)

    def parent(kind: str, label: str) -> ArtifactRef:
        return store.put_json(
            {"component_parent": label},
            ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    problem = _problem()
    compiler_report = compile_lane01_candidate_report(scenario_id=problem.design_problem_id)
    # These are the actual compiler's native values, not rewritten test metadata.
    assert isinstance(compiler_report.metadata["capability_index_refs"], tuple)
    assert compiler_report.metadata["capability_index_refs"]
    compiler_binding = persist_and_verify_data_requirement_compilation_report(
        store, compiler_report, expected_scenario_id=problem.design_problem_id
    )
    now = datetime(2026, 11, 18, tzinfo=UTC)
    planner = AcquisitionPlannerReport(
        run_id="n7-retained-component",
        generated_at=now,
        status="blocked",
        requirement_basis_binding=compiler_binding,
    )
    planner_ref = persist_and_verify_acquisition_planner_report(store, planner)
    world = AcquisitionWorldSnapshot(world_ref="component-retained-world")
    inputs = AcquisitionRetainedPlannerInputs(
        run_id=planner.run_id,
        acquisition_request={},
        compiled_requirement_specs=tuple(
            spec.model_dump(mode="json") for spec in compiler_report.specs
        ),
        capability_requirement_resolutions=compiler_report.capability_requirement_resolutions,
        requirement_basis_binding=compiler_binding,
        design_problem=problem,
        generated_at=now,
        world_snapshot=world,
        compilation_report=compiler_report,
    )
    candidate_id = "candidate-retained-compiler"
    grounding = _grounding_unavailable(candidate_id, issue_codes=("cgf_disposition_missing",))
    value = ValuePortObservation(candidate_id=candidate_id)
    voi = LoopVOIDecision(
        candidate_id=candidate_id,
        terminal_kind="acquisition_required",
        scheduler_action="reject",
        scheduler_reason="roi_below_threshold",
        priority=0.0,
        next_action="escalate",
        reason="component_requires_grounding",
    )
    counterexample = _counterexample_record(
        problem=problem, cycle_index=1, candidate_id=candidate_id, grounding=grounding
    )
    revision = _default_revision_request(
        problem=problem,
        cycle_index=1,
        candidate_id=candidate_id,
        terminal_kind=voi.terminal_kind,
        counterexample=counterexample,
    )
    refinement = _refinement_decision(
        problem=problem,
        cycle_index=1,
        candidate_id=candidate_id,
        counterexample=counterexample,
        revision=revision,
        next_action=voi,
    )
    iteration = _search_iteration(
        problem=problem,
        cycle_index=1,
        candidate_id=candidate_id,
        counterexample=counterexample,
        decision=refinement,
        next_action=voi,
    )
    schedule = SchedulingDecision(
        candidate_id=candidate_id,
        priority=0.0,
        recommended_action="reject",
        reason="roi_below_threshold",
        economics={
            "candidate_id": candidate_id,
            "recommended_action": "reject",
            "expected_improvement_per_usd": 0.0,
            "expected_falsification_value": 0.0,
            "expected_governance_value": 0.0,
            "timeout_risk": 0.0,
            "replay_cost_usd": 0.0,
            "calibration_debt": 0.0,
            "current_pareto_position": "component",
        },
    )
    selected = AcquisitionSelectedEvaluation(
        candidate_id=candidate_id,
        candidate_content_hash="sha256:" + "3" * 64,
        design_problem_ref="sha256:" + "2" * 64,
        world_model_record_hash="sha256:" + "6" * 64,
        evaluation_job_id="component-prior-evaluation",
        evaluation_run_id=binding.run_id,
        generation_run_id="component-prior-generation",
        cycle_index=1,
        n4_source_ref=parent("runtime.quality.n4_candidate_scenario_source", "prior-n4"),
        context_job_ref=parent("runtime.quality.cycle_substrate_context_job", "prior-context"),
        n5_input_ref=parent("runtime.quality.candidate_simulation_n5_input", "prior-input"),
        n5_execution_ref=parent(
            "runtime.quality.candidate_simulation_execution", "prior-execution"
        ),
        n5_result_ref=parent("polisyos.runtime.joint_simulation_result", "prior-result"),
        basis_ref=parent("runtime_quality.acquisition_evaluation_basis", "prior-basis"),
    )
    projection = AcquisitionRetainedCurrentProjection(
        source_cycle_index=selected.cycle_index,
        selected_candidate_id=selected.candidate_id,
        selected_candidate_content_hash=selected.candidate_content_hash,
        grounding=grounding,
        value_port=value,
        execution_schedule=schedule,
        terminal_kind=voi.terminal_kind,
        voi_decision=voi,
        revision_request=revision,
        counterexample=counterexample,
        refinement_decision=refinement,
        search_iteration=iteration,
        current_planner_report=planner,
        current_planner_report_ref=planner_ref,
        current_planner_world_snapshot=world,
        current_planner_inputs=inputs,
    )
    payload: dict[str, object] = {
        "tenant_id": binding.tenant_id,
        "cell_id": binding.cell_id,
        "run_id": binding.run_id,
        "source_job_id": binding.control_job_id,
        "action_job_id": "component-retained-reuse",
        "action_generation": 2,
        "route_id": "sha256:" + "7" * 64,
        "compiled_ref": "sha256:" + "8" * 64,
        "design_problem_ref": "sha256:" + "1" * 64,
        "design_problem_basis_ref": selected.design_problem_ref,
        "candidate_id": candidate_id,
        "candidate_action_ref": parent(
            "runtime_quality.acquisition_candidate_action_receipt", "action"
        ),
        "reuse_occurrence_ref": parent(
            "runtime_quality.candidate_experiment_reuse_occurrence", "reuse"
        ),
        "candidate_world_intent_ref": parent(
            "runtime_quality.acquisition_candidate_world_intent", "intent"
        ),
        "candidate_source_ref": parent(
            "runtime.quality.candidate_acquisition_source", "candidate-source"
        ),
        "evaluation_decision_ref": parent(
            "runtime_quality.acquisition_evaluation_decision", "decision"
        ),
        "current_basis_ref": parent(
            "runtime_quality.acquisition_evaluation_basis", "current-basis"
        ),
        "retained_evaluation": selected,
        "current_projection": projection,
        "budget_observation_before": observation,
        "budget_observation_after": observation,
        "limitations": (*observation.limitations, "runtime_allocation_not_established"),
        "generated_at": now.isoformat(),
    }
    draft = CandidateAcquisitionRetainedContinuation.model_construct(**payload, content_hash="")
    wire = draft.model_dump(mode="json", exclude={"content_hash"})
    native = CandidateAcquisitionRetainedContinuation.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(wire)}
    )
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    ) as control:
        events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
        if not normalize_wire:
            # The old issuer writes the right bytes but fails its typed readback.
            with pytest.raises(
                RuntimeError, match="acquisition_evaluation_artifact_readback_mismatch"
            ):
                persist_acquisition_evaluation_artifact(
                    store=store, event_log=events, record=native
                )
            return
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            dispatch._issue_candidate_retained_continuation({**payload, "undeclared": True})
        record = dispatch._issue_candidate_retained_continuation(payload)
        assert record.model_dump(mode="json", exclude={"content_hash"}) == wire
        assert record.content_hash == native.content_hash
        assert record != native
        selected_ref = persist_acquisition_evaluation_artifact(
            store=store, event_log=events, record=record
        )
        assert (
            read_acquisition_evaluation_artifact(
                store=store,
                event_log=events,
                ref=selected_ref,
                record_type=CandidateAcquisitionRetainedContinuation,
            )
            == record
        )
        corrupt = deepcopy(record.model_dump(mode="json"))
        corrupt["current_projection"]["current_planner_inputs"]["compilation_report"]["metadata"][
            "capability_index_refs"
        ] = ["capability-index:foreign"]
        with pytest.raises(ValueError, match="candidate_retained_continuation_content_mismatch"):
            CandidateAcquisitionRetainedContinuation.model_validate(corrupt)
