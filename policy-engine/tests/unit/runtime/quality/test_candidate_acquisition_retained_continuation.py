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


def test_experiment_reader_joins_outer_control_and_inner_generation_run_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retained experiment replay binds the selected internal run, not the Control alias."""
    from dataclasses import replace

    from polisyos.runtime.quality import acquisition_retained_continuation as retained_reader
    from polisyos.runtime.quality import acquisition_route_loop
    from polisyos.runtime.quality.acquisition_evaluation import (
        AcquisitionSelectedEvaluation,
        issue_candidate_acquisition_evaluation_decision,
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

    class ArtifactReadReachedError(Exception):
        """Sentinel proving source-owner identity checks passed."""

    def stop_at_artifact_read(**_kwargs: object) -> object:
        raise ArtifactReadReachedError

    monkeypatch.setattr(
        acquisition_route_loop,
        "_candidate_experiment_effective_source",
        lambda _origin: (generation_run, cycle),
    )
    monkeypatch.setattr(
        retained_reader,
        "read_acquisition_evaluation_artifact",
        stop_at_artifact_read,
    )

    def read(*, decision_generation_run_id: str, scope_run_id: str = outer_run_id) -> None:
        selected_prior = selected.model_copy(
            update={"generation_run_id": decision_generation_run_id}
        )
        decision = issue_candidate_acquisition_evaluation_decision(
            tenant_id=terminal.tenant_id,
            cell_id=terminal.cell_id,
            run_id=terminal.run_id,
            source_job_id=terminal.source_job_id,
            action_job_id=terminal.job_id,
            action_generation=terminal.action_generation,
            route_id=terminal.route_id,
            compiled_ref=str(scope.compiled_ref.artifact_id),
            design_problem_ref=scope.design_problem_ref,
            design_problem_basis_ref=scope.design_problem_basis_ref,
            candidate_id=scope.candidate_id,
            source_candidate_content_hash=scope.candidate_content_hash,
            candidate_action_ref=terminal.candidate_action_ref,
            candidate_world_intent_ref=_ref(
                "runtime_quality.acquisition_candidate_world_intent", "a"
            ),
            candidate_source_ref=_ref("runtime.quality.candidate_acquisition_source", "b"),
            current_basis_ref=terminal.selected_basis_ref,
            prior_basis_ref=terminal.selected_basis_ref,
            prior_evaluation=selected_prior,
            comparison_result="equivalent",
            predicate_provenance="recomputed",
            reason_codes=(),
            expected_frontier_revision=1,
            expected_frontier_ref=_hash("e"),
            generated_at=terminal.generated_at.isoformat(),
            reuse_occurrence_ref=terminal.reuse_occurrence_ref,
            decision_version="2.0",
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
            ref=cast("ArtifactRef", terminal.current_continuation_ref),
            decision=decision,
            terminal=terminal,
            prior_experiment_origin=selected_origin,
        )

    with pytest.raises(ArtifactReadReachedError):
        read(decision_generation_run_id=inner_run_id)
    with pytest.raises(ValueError, match="candidate_retained_experiment_source_not_established"):
        read(decision_generation_run_id="generation_cycle_foreign")
    with pytest.raises(ValueError, match="candidate_retained_experiment_source_not_established"):
        read(decision_generation_run_id=inner_run_id, scope_run_id="R_foreign_control")
