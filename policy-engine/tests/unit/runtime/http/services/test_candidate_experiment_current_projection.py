"""Project a selected blocked basis from the current candidate terminal view."""

from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.artifacts import SchemaInfo
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionActionServiceError,
)
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlPlaneStore,
)
from polisyos.runtime.quality.acquisition_evaluation import (
    CandidateAcquisitionEvaluationBasis,
    CandidateExperimentTerminalHistory,
    issue_candidate_acquisition_evaluation_basis,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
    AcquisitionCandidateExperimentTerminalReceipt,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyScope,
)
from polisyos.runtime.quality.candidate_source_basis import CandidateSourceBasisInputs
from polisyos.runtime.quality.generation_cycle import LoopVOIDecision
from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
    _requested_phase,
)
from tests.unit.runtime.quality.test_candidate_source_basis import _inputs


def _component_ref(
    store: artifacts.FileSystemCAS, *, kind: str, name: str
) -> artifacts.ArtifactRef:
    """Persist a selected component reference without invoking protected work."""
    return store.put_json(
        {"component_fixture": name, "protected_execution": "not_performed"},
        artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
        return_selected_profile=True,
    )


def _basis(
    *,
    store: artifacts.FileSystemCAS,
    preparation_inputs: CandidateSourceBasisInputs,
    phase_scope: CandidateUnpricedPolicyScope,
    route_id: str,
    action_ref: artifacts.ArtifactRef,
    intent_ref: artifacts.ArtifactRef,
    generation: int,
    role: Literal["blocked", "prospective"],
    reasons: tuple[str, ...],
    selected_data_snapshot_ref: artifacts.ArtifactRef,
    selected_world_model_ref: artifacts.ArtifactRef,
) -> tuple[CandidateAcquisitionEvaluationBasis, artifacts.ArtifactRef]:
    """Use the canonical issuer for a typed component basis boundary double."""
    source_ref = preparation_inputs.candidate_source_ref
    basis = issue_candidate_acquisition_evaluation_basis(
        tenant_id=phase_scope.tenant_id,
        cell_id=phase_scope.cell_id,
        run_id=phase_scope.run_id,
        source_job_id=phase_scope.source_job_id,
        action_job_id=f"candidate-current-projection-{generation}",
        action_generation=generation,
        route_id=route_id,
        design_problem_ref=phase_scope.design_problem_ref,
        design_problem_basis_ref=phase_scope.design_problem_basis_ref,
        candidate_id=phase_scope.candidate_id,
        source_candidate_content_hash=phase_scope.candidate_content_hash,
        candidate_action_ref=action_ref,
        candidate_world_intent_ref=intent_ref,
        candidate_source_ref=source_ref,
        preparation_inputs=preparation_inputs,
        prepared_n5_configuration=None,
        basis_role=role,
        values={"fixture": "verified-history adapter boundary only"},
        predicate_provenance="not_established",
        reason_codes=reasons,
        limitations=("unit_boundary_only_no_history_replay_or_authority",),
        selected_data_snapshot_ref=(None if role == "prospective" else selected_data_snapshot_ref),
        selected_world_model_ref=(None if role == "prospective" else selected_world_model_ref),
    )
    selected_ref = store.put_json(
        basis.model_dump(mode="json"),
        artifacts.ArtifactWriteOptions(
            kind=basis.ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=basis.ARTIFACT_SCHEMA_NAME,
                version=basis.schema_version,
            ),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return basis, selected_ref


def _terminal_history(
    *,
    store: artifacts.FileSystemCAS,
    preparation_inputs: CandidateSourceBasisInputs,
    scope: CandidateUnpricedPolicyScope,
    phase: AcquisitionCandidateExperimentPhaseReceipt,
    route_id: str,
    selected_data_snapshot_ref: artifacts.ArtifactRef,
    selected_world_model_ref: artifacts.ArtifactRef,
    generation: int,
    reasons: tuple[str, ...],
    basis_role: Literal["blocked", "prospective"] = "blocked",
) -> CandidateExperimentTerminalHistory:
    """Build the exact history datatype as an explicit upstream boundary double.

    The typed view is supplied here as if the terminal-history owner had
    verified it. This unit test does not replay that history or establish action
    authority; it checks only the adapter from that boundary into the reader.
    """
    phase_identity = phase
    voi_payload = phase_identity.voi_decision.model_dump(mode="python")
    voi_payload["candidate_id"] = scope.candidate_id
    voi_decision = LoopVOIDecision.model_validate(voi_payload)
    job_id = f"candidate-current-projection-{generation}"
    action_ref = _component_ref(
        store,
        kind="runtime_quality.acquisition_candidate_action_receipt",
        name=f"candidate-action-{generation}",
    )
    intent_ref = _component_ref(
        store,
        kind="runtime_quality.acquisition_candidate_world_intent",
        name=f"candidate-intent-{generation}",
    )
    basis, basis_ref = _basis(
        store=store,
        preparation_inputs=preparation_inputs,
        phase_scope=scope,
        route_id=route_id,
        action_ref=action_ref,
        intent_ref=intent_ref,
        generation=generation,
        role=basis_role,
        reasons=reasons,
        selected_data_snapshot_ref=selected_data_snapshot_ref,
        selected_world_model_ref=selected_world_model_ref,
    )
    decision_ref = _component_ref(
        store,
        kind="runtime_quality.acquisition_evaluation_decision",
        name=f"candidate-decision-{generation}",
    )
    reentry_ref = _component_ref(
        store,
        kind="runtime_quality.candidate_source_reentry_receipt",
        name=f"candidate-reentry-{generation}",
    )
    terminal = AcquisitionCandidateExperimentTerminalReceipt(
        receipt_id=f"{job_id}.terminal",
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        run_id=scope.run_id,
        source_job_id=scope.source_job_id,
        route_id=route_id,
        action_generation=generation,
        job_id=job_id,
        source_payload_ref=phase_identity.source_payload_ref,
        capability_manifest_ref=phase_identity.capability_manifest_ref,
        request_content_hash=phase_identity.request_content_hash,
        policy_scope=scope,
        policy_ref=phase_identity.policy_ref,
        authority_decision_ref=phase_identity.authority_decision_ref,
        voi_decision=voi_decision,
        predecessor_receipt_ref="sha256:" + str(generation % 10) * 64,
        owner_receipt_refs=(
            str(action_ref.artifact_id),
            str(decision_ref.artifact_id),
        ),
        generated_at=phase_identity.generated_at,
        terminal_outcome="candidate_reentry_completed",
        candidate_action_ref=action_ref,
        candidate_reentry_ref=reentry_ref,
        evaluation_decision_ref=decision_ref,
        selected_basis_ref=basis_ref,
        selected_evaluation_witness_ref=reentry_ref,
    )
    terminal_ref = store.put_json(
        terminal.model_dump(mode="json"),
        artifacts.ArtifactWriteOptions(
            kind="runtime_quality.acquisition_route_loop_receipt",
            media_type="application/json",
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    head = AcquisitionActionHeadRecord(
        tenant_id=terminal.tenant_id,
        cell_id=terminal.cell_id,
        run_id=terminal.run_id,
        source_job_id=terminal.source_job_id,
        route_id=terminal.route_id,
        action_generation=generation,
        head_generation=generation,
        receipt_ref=str(terminal_ref.artifact_id),
        receipt_sha256=str(terminal_ref.artifact_id),
        durable_event_id=f"unit-boundary-terminal-{generation}",
        coarse_phase="terminal",
        receipt_phase="terminal",
        recovery_state="complete",
        job_id=terminal.job_id,
        predecessor_receipt_ref=terminal.predecessor_receipt_ref,
        created_at=phase_identity.generated_at,
        receipt_manifest_profile_sha256=terminal_ref.manifest_profile_sha256,
    )
    origin = SimpleNamespace(
        tenant_id=head.tenant_id,
        cell_id=head.cell_id,
        run_id=head.run_id,
        source_job_id=head.source_job_id,
        route_id=head.route_id,
    )
    history = CandidateExperimentTerminalHistory(
        head=head,
        terminal_ref=terminal_ref,
        terminal=terminal,
        origin=origin,
        phase_chain=(),
        action=None,
        source=None,
        budget_window=None,
        decision=None,
        current_basis=None,
        selected_basis=basis,
        evaluation=None,
        reentry=None,
        continuation=None,
        frontier_before=None,
        frontier_after=None,
    )
    return history


def _scope_for_case(
    case: Any,
) -> tuple[AcquisitionCandidateExperimentPhaseReceipt, CandidateUnpricedPolicyScope, str]:
    """Align the fixture's existing valid phase identity to its typed source."""
    phase = _requested_phase()
    source = case.source_case.source
    scope_payload = phase.policy_scope.model_dump(mode="python")
    scope_payload.update(
        tenant_id=source.tenant_id,
        cell_id=source.cell_id,
        run_id=source.run_id,
        source_job_id=source.job_id,
        candidate_id=source.candidate_digest,
        candidate_content_hash=source.candidate_digest,
    )
    scope = CandidateUnpricedPolicyScope.model_validate(scope_payload)
    # The source fixture uses a non-hash route label; retain the existing
    # selected phase's content-addressed route identity for this boundary view.
    return phase, scope, phase.route_id


def test_current_action_reader_uses_only_current_verified_history_blocker_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Project current basis reasons, reject malformed basis, and drop stale history."""
    from tests.unit.runtime.quality import test_candidate_acquisition_world as world_fixture

    with tenant_scope(None, tenant_id=world_fixture.TENANT_ID, cell_id=world_fixture.CELL_ID):
        world_model_writer = world_fixture.build_world_model_record

        def write_selected_world_model(*args: Any, **kwargs: Any) -> Any:
            return world_model_writer(
                *args,
                **{**kwargs, "return_selected_profile": True},
            )

        monkeypatch.setattr(
            world_fixture,
            "build_world_model_record",
            write_selected_world_model,
        )
        case = world_fixture._candidate_world_case(tmp_path, monkeypatch)
        preparation_inputs = _inputs(case)
        phase, scope, route_id = _scope_for_case(case)
        selected_world_model_ref = case.base.record_ref
        assert selected_world_model_ref.manifest_profile_sha256 is not None
        stale = _terminal_history(
            store=case.store,
            preparation_inputs=preparation_inputs,
            scope=scope,
            phase=phase,
            route_id=route_id,
            selected_data_snapshot_ref=case.materialization.data_snapshot_ref,
            selected_world_model_ref=selected_world_model_ref,
            generation=1,
            reasons=("stale history reason",),
        )
        current = _terminal_history(
            store=case.store,
            preparation_inputs=preparation_inputs,
            scope=scope,
            phase=phase,
            route_id=route_id,
            selected_data_snapshot_ref=case.materialization.data_snapshot_ref,
            selected_world_model_ref=selected_world_model_ref,
            generation=2,
            reasons=("current basis reason one", "current basis reason two"),
        )
        wrong_basis, _ = _basis(
            store=case.store,
            preparation_inputs=preparation_inputs,
            phase_scope=scope,
            route_id=route_id,
            action_ref=current.terminal.candidate_action_ref,
            intent_ref=current.selected_basis.candidate_world_intent_ref,
            generation=2,
            role="prospective",
            reasons=("not a blocked basis",),
            selected_data_snapshot_ref=case.materialization.data_snapshot_ref,
            selected_world_model_ref=selected_world_model_ref,
        )

    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    ) as control:
        service = object.__new__(AcquisitionActionService)
        service.control_service = SimpleNamespace(
            _control_store=control,
            _artifact_store=case.store,
        )

        origin = SimpleNamespace(
            tenant_id=current.head.tenant_id,
            cell_id=current.head.cell_id,
            run_id=current.head.run_id,
            source_job_id=current.head.source_job_id,
            route_id=current.head.route_id,
            current_action_head=current.head,
            current_terminal_history=current,
        )
        projected = service._candidate_experiment_current_action_projection(origin)
        assert projected.status == "completed"
        assert projected.terminal_outcome == "candidate_reentry_completed"
        assert projected.evaluation_disposition == "blocked"
        assert projected.selected_evaluation is None
        assert projected.blocker_reason == "current basis reason one; current basis reason two"
        assert projected.selected_receipt_ref == current.terminal_ref

        # A stale history cannot fill the newer current head, even though its
        # selected basis itself contains plausible blocker reasons.
        stale_origin = SimpleNamespace(
            tenant_id=current.head.tenant_id,
            cell_id=current.head.cell_id,
            run_id=current.head.run_id,
            source_job_id=current.head.source_job_id,
            route_id=current.head.route_id,
            current_action_head=current.head,
            current_terminal_history=stale,
        )
        stale_projection = service._candidate_experiment_current_action_projection(stale_origin)
        assert stale_projection.status == "unknown"
        assert stale_projection.terminal_outcome is None
        assert stale_projection.evaluation_disposition == "unknown"
        assert stale_projection.blocker_reason is None
        assert stale_projection.selected_receipt_ref == current.terminal_ref

        with pytest.raises(AcquisitionActionServiceError) as missing_basis:
            service._candidate_experiment_current_action_projection(
                SimpleNamespace(
                    tenant_id=current.head.tenant_id,
                    cell_id=current.head.cell_id,
                    run_id=current.head.run_id,
                    source_job_id=current.head.source_job_id,
                    route_id=current.head.route_id,
                    current_action_head=current.head,
                    current_terminal_history=replace(current, selected_basis=None),
                )
            )
        assert missing_basis.value.code == (
            "candidate_experiment_blocked_evaluation_basis_not_established"
        )

        with pytest.raises(AcquisitionActionServiceError) as wrong_basis_refusal:
            service._candidate_experiment_current_action_projection(
                SimpleNamespace(
                    tenant_id=current.head.tenant_id,
                    cell_id=current.head.cell_id,
                    run_id=current.head.run_id,
                    source_job_id=current.head.source_job_id,
                    route_id=current.head.route_id,
                    current_action_head=current.head,
                    current_terminal_history=replace(current, selected_basis=wrong_basis),
                )
            )
        assert wrong_basis_refusal.value.code == (
            "candidate_experiment_blocked_evaluation_basis_not_established"
        )


def test_v2_current_action_projection_uses_occurrence_selected_prior_n5(tmp_path: Path) -> None:
    """A no-fetch V2 retention projects only the N5 selected by its verified occurrence."""
    from tests.unit.runtime.quality.test_candidate_experiment_reuse import _v2_reuse_history

    history, _evaluation = _v2_reuse_history(artifacts.FileSystemCAS(tmp_path / "cas"))

    selected = AcquisitionActionService._candidate_experiment_v2_selected_evaluation_projection(
        history
    )

    occurrence = history.reuse_occurrence
    assert occurrence is not None
    assert history.terminal.terminal_outcome == "candidate_evaluation_retained"
    assert selected == history.terminal.selected_evaluation
    assert selected.n5_input_ref == occurrence.selection.n5_input_ref
    assert selected.n5_execution_ref == occurrence.selection.n5_execution_ref
    assert selected.n5_result_ref == occurrence.selection.n5_result_ref

    with pytest.raises(AcquisitionActionServiceError) as missing_occurrence:
        AcquisitionActionService._candidate_experiment_v2_selected_evaluation_projection(
            replace(history, reuse_occurrence_ref=None)
        )
    assert missing_occurrence.value.code == (
        "candidate_experiment_reuse_selected_n5_not_established"
    )
