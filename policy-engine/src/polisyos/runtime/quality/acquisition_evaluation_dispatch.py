"""One actual post-admission dispatcher for re-entry or retained evaluation.

All current inputs come from the bound Control/epoch/source owners. The native
fence spans the final conditional SQL action-head/frontier write and readback;
it never spans the numerical N5 work. Recovery reuses owned admission/re-entry
receipts and never refetches or repeats provider spend.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from polisyos.core import contracts
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionActionHeadRecord,
    ControlJobRecord,
)
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationBasis,
    AcquisitionEvaluationDecision,
    AcquisitionSelectedEvaluation,
    CandidateAcquisitionEvaluationBasis,
    CandidateAcquisitionEvaluationDecision,
    CandidateEvaluationTerminalHistory,
    CandidateExperimentTerminalHistory,
    ResolvedAcquisitionEvaluation,
    _candidate_model_values_same,
    _candidate_ref_same,
    basis_exact_values_equal,
    issue_acquisition_evaluation_basis,
    persist_acquisition_evaluation_artifact,
    read_acquisition_evaluation_artifact,
    recompute_candidate_acquisition_basis_values,
    replay_acquisition_basis_for_history,
    resolve_selected_acquisition_evaluation,
    selected_artifact_ref,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentTerminalReceipt,
    AcquisitionRouteLoop,
    AcquisitionRouteLoopReceiptV2,
    AcquisitionRoutePhaseReceipt,
    VerifiedCandidateExperimentOrigin,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionCandidatePreparation,
    AcquisitionCandidateSourceRoute,
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthReceipt,
    CandidateExperimentPriorOwner,
)
from polisyos.runtime.quality.n5_execution_basis import (
    exact_n5_content_bytes,
    exact_n5_content_hash,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from polisyos.core.artifacts import ArtifactRef, ArtifactStore
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
        VerifiedAcquisitionActionOutcome,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionEvaluationFrontierCAS,
        AcquisitionEvaluationFrontierRecord,
    )
    from polisyos.runtime.quality.acquisition_evidence_transition import (
        AcquisitionEvidenceTransitionDispatch,
    )
    from polisyos.runtime.quality.acquisition_planner import AcquisitionWorldSnapshot
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        AcquisitionCandidateRouteLoopReceipt,
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationScenarioProfile,
        CandidateSimulationSyntheticModelDeclarationV1,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
    )
    from polisyos.scientist.orchestration.engine import (
        BudgetLedgerReentryBudgetScope,
        BudgetLedgerReentryBudgetWindow,
        BudgetState,
        ProducerBudgetObservation,
    )


type _ComparisonResult = Literal["equivalent", "different", "not_established"]
type _TerminalOutcome = Literal[
    "quarantined_no_growth", "reentry_completed", "source_admitted_evaluation_retained"
]


@dataclass(frozen=True)
class _CurrentSelection:
    closure: VerifiedAcquisitionRouteClosure
    phase: AcquisitionRoutePhaseReceipt
    phase_ref: ArtifactRef
    action_generation: int
    action_job_id: str
    growth_ref: ArtifactRef
    growth: AcquisitionWorldGrowthReceipt
    admitted: object
    projection: object
    overlay: object
    prepared: AcquisitionCandidatePreparation
    admitted_source_ref: ArtifactRef


@dataclass(frozen=True)
class CandidateExperimentEvaluationPreflight:
    """Read-only selected owners for the experiment-native N5 continuation path.

    This result proves composition of the source/template/profile and actual
    continuation owners before enqueue. It intentionally carries no live job,
    lease, budget observation, or effect permission; those are reopened at the
    executing and pending-reentry phases.
    """

    origin: VerifiedCandidateExperimentOrigin
    selection: AcquisitionCandidateSourceRoute
    policy_ref: ArtifactRef
    configured_profile: CandidateSimulationScenarioProfile
    original_model_declaration: CandidateSimulationSyntheticModelDeclarationV1
    continuation_kind: Literal["candidate_source_reentry_n5"]


def preflight_candidate_experiment_evaluation(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    selection: AcquisitionCandidateSourceRoute,
) -> CandidateExperimentEvaluationPreflight:
    """Reopen current experiment source and downstream N5/terminal owners prequeue."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_evaluation_history import (
        verify_candidate_experiment_terminal_history,
    )
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedCandidateExperimentOrigin
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _candidate_experiment_source_selection,
    )
    from polisyos.runtime.quality.candidate_source_reentry_history import (
        verify_candidate_experiment_source_reentry_history,
    )
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController

    service = bridge._source_control_service
    sink = bridge.action_head_sink
    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or type(origin) is not VerifiedCandidateExperimentOrigin
        or type(selection) is not AcquisitionCandidateSourceRoute
        or type(service) is not ControlPlaneService
        or service._artifact_store is not bridge.artifact_store
        or service._control_store is not bridge.control_store
        or service.acquisition_route_sink is not sink
        or sink is None
    ):
        raise ValueError("candidate_experiment_evaluation_preflight_owner_missing")
    _candidate_experiment_verified_prior_history(bridge=bridge, origin=origin)
    selected = _candidate_experiment_source_selection(bridge, origin)
    if selected != selection:
        raise ValueError("candidate_experiment_evaluation_preflight_selection_changed")
    prior_owner = bridge._candidate_experiment_prior_owner(
        origin=origin,
        selection=selected,
    )
    profile = prior_owner.profile
    declaration = prior_owner.model_declaration
    binding = service.verify_acquisition_source_budget_owner(closure=origin)
    budget_scope = service.verify_candidate_unpriced_budget_scope(closure=origin)
    global_limit = service.acquisition_source_global_budget_usd(closure=origin)
    current_policy_ref, current_policy = resolve_current_candidate_unpriced_policy(
        control_service=service,
        scope=origin.policy_scope,
    )
    quota = profile.n5.invocation_quota_policy
    template = current_policy.configured_template
    if (
        binding.run_id != origin.run_id
        or binding.tenant_id != origin.tenant_id
        or binding.cell_id != origin.cell_id
        or budget_scope.run_budget_usd is None
        or budget_scope.run_budget_usd <= 0
        or global_limit <= 0
        or current_policy_ref != origin.policy_ref
        or template is None
        or template.max_metered_reentry_usd <= 0
        or quota is None
        or profile.n5.invocation_purpose != "standard"
    ):
        raise ValueError("candidate_experiment_evaluation_preflight_budget_not_established")
    required_callables = (
        getattr(bridge, "resolve_candidate_experiment_reentry_budget_window", None),
        getattr(bridge, "prepare_candidate_experiment_source_reentry", None),
        getattr(service, "build_candidate_experiment_source_budget_observer", None),
        getattr(service, "build_candidate_experiment_reentry_budget_observer", None),
        getattr(sink, "experiment_action_outcomes", None),
        getattr(sink, "recover_candidate_experiment_terminal", None),
        getattr(sink, "persist_terminal", None),
        getattr(
            GenerationCycleController,
            "_candidate_retained_configured_cheap_continuation",
            None,
        ),
        getattr(GenerationCycleController, "reenter_after_candidate_acquisition_source", None),
        verify_candidate_experiment_source_reentry_history,
        verify_candidate_experiment_terminal_history,
    )
    if any(not callable(item) for item in required_callables):
        raise ValueError("candidate_experiment_evaluation_preflight_continuation_missing")
    return CandidateExperimentEvaluationPreflight(
        origin=origin,
        selection=selected,
        policy_ref=origin.policy_ref,
        configured_profile=profile,
        original_model_declaration=declaration,
        continuation_kind="candidate_source_reentry_n5",
    )


def _candidate_experiment_verified_prior_history(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
) -> CandidateExperimentTerminalHistory | None:
    """Replay the complete committed prefix and bind its latest frontier."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        AcquisitionEvaluationFrontierKey,
    )
    from polisyos.runtime.quality.acquisition_evaluation import (
        CandidateExperimentTerminalHistory,
    )
    from polisyos.runtime.quality.acquisition_evaluation_history import (
        verify_candidate_experiment_terminal_history,
    )

    service = bridge._source_control_service
    chain = origin.candidate_terminal_history_chain
    key = AcquisitionEvaluationFrontierKey(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        source_job_id=origin.source_job_id,
        design_problem_ref=origin.policy_scope.design_problem_ref,
        candidate_id=origin.policy_scope.candidate_id,
    )
    frontier = bridge.control_store.read_acquisition_evaluation_frontier(key)
    if not chain:
        if frontier is not None:
            raise ValueError("candidate_experiment_prior_frontier_not_established")
        return None
    if (
        type(service) is not ControlPlaneService
        or any(type(item) is not CandidateExperimentTerminalHistory for item in chain)
        or tuple(item.head.action_generation for item in chain) != tuple(range(1, len(chain) + 1))
    ):
        raise ValueError("candidate_experiment_prior_history_not_established")
    latest = chain[-1]
    if (
        type(latest.head) is not AcquisitionActionHeadRecord
        or latest.head.receipt_phase != "terminal"
        or latest.terminal_ref.manifest_profile_sha256 is None
        or str(latest.terminal_ref.artifact_id) != latest.head.receipt_ref
        or latest.frontier_after != frontier
    ):
        raise ValueError("candidate_experiment_prior_frontier_not_established")
    if frontier is None and (
        latest.evaluation is not None
        or latest.terminal.selected_evaluation is not None
        or latest.terminal.terminal_outcome
        not in {"candidate_reentry_completed", "candidate_blocked"}
    ):
        raise ValueError("candidate_experiment_prior_candidate_context_not_established")
    replay = verify_candidate_experiment_terminal_history(
        control_service=service,
        head=latest.head,
        terminal_ref=latest.terminal_ref,
    )
    if (
        replay != latest
        or replay.origin.candidate_terminal_history_chain != chain[:-1]
        or bridge.control_store.read_acquisition_evaluation_frontier(key) != frontier
    ):
        raise ValueError("candidate_experiment_prior_history_changed")
    return replay


def _candidate_experiment_unselected_prior(
    origin: VerifiedCandidateExperimentOrigin,
) -> CandidateExperimentTerminalHistory | None:
    """Find the last real candidate calculation in an already verified prefix."""
    for history in reversed(origin.candidate_terminal_history_chain):
        if history.terminal.terminal_outcome == "candidate_blocked":
            if (
                history.terminal.blocker_reason
                != "candidate_experiment_input_change_not_established"
                or history.frontier_after is not None
                or history.evaluation is not None
                or history.reentry is not None
            ):
                raise ValueError("candidate_experiment_prior_blocker_not_established")
            continue
        if (
            history.terminal.terminal_outcome != "candidate_reentry_completed"
            or history.terminal.selected_evaluation is not None
            or history.evaluation is not None
            or history.reentry is None
            or history.reentry_evaluation is None
            or history.frontier_after is not None
            or history.selected_basis is None
            or history.selected_basis.basis_role != "blocked"
        ):
            raise ValueError("candidate_experiment_prior_candidate_context_not_established")
        return history
    return None


def _candidate_experiment_unselected_input_changed(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    prior: ResolvedAcquisitionEvaluation | None,
    prepared: object,
) -> bool:
    """Reopen an unselected prior and compare only its bound numerical input."""
    from polisyos.runtime.quality.candidate_acquisition_source import (
        read_candidate_acquisition_source,
    )
    from polisyos.runtime.quality.candidate_source_basis import (
        CandidateSourceBasisValues,
        candidate_experiment_input_changed,
    )

    history = _candidate_experiment_unselected_prior(origin)
    if (
        history is None
        or prior is None
        or not _candidate_model_values_same(history.reentry_evaluation, prior)
        or type(prepared) is not CandidateSourceBasisValues
        or prepared.inputs is None
    ):
        raise ValueError("candidate_experiment_prior_candidate_context_not_established")
    source = read_candidate_acquisition_source(
        bridge.artifact_store,
        source_ref=prepared.inputs.candidate_source_ref,
        authority=bridge.authority,
    )
    return candidate_experiment_input_changed(
        prior=prior,
        previous_source=history.source,
        current_source=source,
        prepared=prepared,
    )


def _current_selection(bridge: AcquisitionWorldGrowthBridge) -> _CurrentSelection:
    """Resolve the real live job, selected action, native admission and prepared values."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

    service = bridge._source_control_service
    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or type(service) is not ControlPlaneService
        or service._artifact_store is not bridge.artifact_store
        or service._control_store is not bridge.control_store
    ):
        raise ValueError("acquisition_evaluation_current_owner_not_composed")
    admission = bridge.control_store.current_execution_job_admission()
    job = admission.job
    if (
        job.kind != "acquisition"
        or job.state != "running"
        or not job.run_id
        or admission.scope.status != "established"
        or not admission.scope.tenant_id
        or not admission.scope.cell_id
    ):
        raise ValueError("acquisition_evaluation_current_job_not_admitted")
    closure = AcquisitionRouteLoop(
        control_store=bridge.control_store,
        artifact_store=bridge.artifact_store,
        event_log=bridge.event_log,
        core_source_resolver=service.resolve_completed_control_job_core_run_source,
        tenant_id=admission.scope.tenant_id,
        cell_id=admission.scope.cell_id,
        action_outcome_reader=service.acquisition_route_sink,
    ).resolve_current_route(run_id=job.run_id, action_job_id=job.job_id)
    snapshot = service.acquisition_route_sink.current_action_outcome(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        source_job_id=closure.source_job_id,
        route_id=closure.route_id,
    )
    if (
        snapshot is None
        or snapshot.head.job_id != job.job_id
        or snapshot.selection_phase is None
        or snapshot.selection_phase_ref is None
        or snapshot.executing_phase_ref is None
        or snapshot.head.receipt_phase
        not in {"outcome_selected", "world_committed_reentry_pending"}
    ):
        raise ValueError("acquisition_evaluation_action_selection_not_current")
    phase = snapshot.selection_phase
    refs = tuple(
        ref
        for ref in phase.owner_receipt_refs
        if bridge.artifact_store.get_manifest(ref).kind
        == "runtime_quality.acquisition_world_growth_receipt"
    )
    if len(refs) != 1:
        raise ValueError("acquisition_evaluation_selected_growth_missing")
    growth, admitted = bridge._verified_growth(closure, refs[0])
    if growth.action_phase_ref != snapshot.executing_phase_ref:
        raise ValueError("acquisition_evaluation_growth_action_mismatch")
    selected = bridge.selection(closure)
    if selected is None:
        raise ValueError("acquisition_evaluation_route_selection_missing")
    overlay_path, _ = bridge._paths(selected, create=False)
    overlay = data_forge_read_api.catalog.CatalogAcquisitionOverlay(
        bridge.authority.baseline_path,
        overlay_path,
    )
    passport = AdmissionPassport.model_validate(
        contracts.epoch.load_verified_epoch_statement(
            store=bridge.artifact_store,
            ref=growth.activation.passport_ref,
            expected_kind="epoch.acquisition_passport_snapshot",
        )
    )
    projection = overlay.read_activated_semantic_epoch_observations(
        receipt_ref=admitted.receipt_ref,
        artifact_store=bridge.artifact_store,
        passport=passport,
        authority=bridge.authority,
    )
    refreshes = tuple(
        item for item in bridge.config.candidate_world_refreshes if item.key == growth.selection.key
    )
    if len(refreshes) != 1:
        raise ValueError("acquisition_evaluation_controlled_refresh_not_supported")
    candidate = contracts.epoch.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
        contracts.epoch.load_verified_epoch_statement(
            store=bridge.artifact_store,
            ref=passport.semantic_boundary_candidate_ref,
            expected_kind="epoch.acquisition_semantic_boundary_candidate",
        )
    )
    if contracts.epoch.acquisition_semantic_candidate_content_hash(candidate) != (
        passport.semantic_boundary_candidate_content_hash
    ):
        raise ValueError("acquisition_evaluation_source_candidate_mismatch")
    source_ref = candidate.source_record_ref
    if source_ref.manifest_profile_sha256 is None:
        raise ValueError("acquisition_evaluation_source_view_not_established")
    prepared = bridge._prepare_candidate_world_context(
        closure=closure,
        growth=growth,
        overlay=overlay,
        observation_projection=projection,
        refresh=refreshes[0],
    )
    return _CurrentSelection(
        closure=closure,
        phase=phase,
        phase_ref=selected_artifact_ref(bridge.artifact_store, snapshot.selection_phase_ref),
        action_generation=snapshot.head.action_generation,
        action_job_id=job.job_id,
        growth_ref=selected_artifact_ref(bridge.artifact_store, refs[0]),
        growth=growth,
        admitted=admitted,
        projection=projection,
        overlay=overlay,
        prepared=prepared,
        admitted_source_ref=source_ref,
    )


def _frontier(
    bridge: AcquisitionWorldGrowthBridge, selection: _CurrentSelection
) -> AcquisitionEvaluationFrontierRecord | None:
    from polisyos.runtime.http.services.control_plane_store import AcquisitionEvaluationFrontierKey

    return bridge.control_store.read_acquisition_evaluation_frontier(
        AcquisitionEvaluationFrontierKey(
            tenant_id=selection.closure.tenant_id,
            cell_id=selection.closure.cell_id,
            source_job_id=selection.closure.source_job_id,
            design_problem_ref=selection.closure.design_problem_ref,
            candidate_id=selection.closure.source_cycle.selected_candidate_ref,
        )
    )


def _basis_for_current(
    bridge: AcquisitionWorldGrowthBridge,
    selection: _CurrentSelection,
    prior: ResolvedAcquisitionEvaluation | None,
) -> AcquisitionEvaluationBasis:
    return issue_acquisition_evaluation_basis(
        bridge=bridge,
        closure=selection.closure,
        growth_receipt_ref=selection.growth_ref,
        admitted_source_ref=selection.admitted_source_ref,
        prepared=selection.prepared,
        prior=prior,
        actual_evaluation=False,
    )


def _comparison(
    bridge: AcquisitionWorldGrowthBridge,
    selection: _CurrentSelection,
) -> tuple[
    AcquisitionEvaluationBasis,
    ArtifactRef | None,
    AcquisitionSelectedEvaluation | None,
    _ComparisonResult,
    tuple[str, ...],
    AcquisitionEvaluationFrontierRecord | None,
    ResolvedAcquisitionEvaluation | None,
]:
    frontier = _frontier(bridge, selection)
    prior: ResolvedAcquisitionEvaluation | None = None
    reasons: list[str] = []
    old_basis: AcquisitionEvaluationBasis | None = None
    old_ref: ArtifactRef | None = None
    selected: AcquisitionSelectedEvaluation | None = None
    try:
        prior = resolve_selected_acquisition_evaluation(bridge=bridge, closure=selection.closure)
        if frontier is None or frontier.basis_ref is None:
            raise ValueError("acquisition_prior_frontier_basis_not_established")
        if (
            frontier.selected_evaluation_witness_ref
            != str(prior.selected.n5_execution_ref.artifact_id)
            or frontier.selected_evaluation_content_hash != prior.execution.content_hash
        ):
            # A route-only old accumulator cannot overwrite another successful
            # candidate/task frontier. No arbitrary matching earlier result.
            raise RuntimeError("acquisition_selected_frontier_not_route_accumulator")
        old_ref = selected_artifact_ref(bridge.artifact_store, frontier.basis_ref)
        old_basis = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=old_ref,
            record_type=AcquisitionEvaluationBasis,
        )
        if type(old_basis) is not AcquisitionEvaluationBasis or (
            old_basis.content_hash != frontier.basis_content_hash
        ):
            raise ValueError("acquisition_prior_frontier_basis_mismatch")
        replay_acquisition_basis_for_history(
            artifact_store=bridge.artifact_store,
            event_log=bridge.event_log,
            control_store=bridge.control_store,
            basis=old_basis,
            prior_evaluation=prior,
        )
        selected = prior.selected.model_copy(update={"basis_ref": old_ref})
    except RuntimeError:
        raise
    except (OSError, TypeError, ValueError) as exc:
        reasons.append(str(getattr(exc, "code", None) or exc))
    current = _basis_for_current(bridge, selection, prior)
    reasons.extend(current.reason_codes)
    if old_basis is None or old_ref is None or selected is None:
        return (
            current,
            old_ref,
            selected,
            "not_established",
            tuple(dict.fromkeys(reasons)),
            frontier,
            prior,
        )
    if (
        old_basis.predicate_provenance != "recomputed"
        or current.predicate_provenance != "recomputed"
    ):
        reasons.extend(old_basis.reason_codes)
        return (
            current,
            old_ref,
            selected,
            "not_established",
            tuple(dict.fromkeys(reasons)),
            frontier,
            prior,
        )
    comparison: _ComparisonResult = (
        "equivalent" if basis_exact_values_equal(old_basis, current) else "different"
    )
    return current, old_ref, selected, comparison, (), frontier, prior


def _decision(
    selection: _CurrentSelection,
    *,
    current_basis_ref: ArtifactRef,
    prior_basis_ref: ArtifactRef | None,
    prior_evaluation: AcquisitionSelectedEvaluation | None,
    comparison: _ComparisonResult,
    reasons: tuple[str, ...],
    frontier: AcquisitionEvaluationFrontierRecord | None,
) -> AcquisitionEvaluationDecision:
    closure = selection.closure
    payload = {
        "schema_version": "AcquisitionEvaluationDecision@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_rule": "AD-E02-B09-01/owned-complete-native-values/v1",
        "tenant_id": closure.tenant_id,
        "cell_id": closure.cell_id,
        "run_id": closure.run_id,
        "source_job_id": closure.source_job_id,
        "action_job_id": selection.action_job_id,
        "action_generation": selection.action_generation,
        "route_id": closure.route_id,
        "compiled_ref": closure.compiled_ref,
        "design_problem_ref": closure.design_problem_ref,
        "design_problem_basis_ref": closure.design_problem_basis_ref,
        "candidate_id": closure.source_cycle.selected_candidate_ref,
        "selected_action_receipt_ref": selection.phase_ref.model_dump(mode="json"),
        "growth_receipt_ref": selection.growth_ref.model_dump(mode="json"),
        "admitted_source_ref": selection.admitted_source_ref.model_dump(mode="json"),
        "prior_basis_ref": prior_basis_ref.model_dump(mode="json") if prior_basis_ref else None,
        "current_basis_ref": current_basis_ref.model_dump(mode="json"),
        "prior_evaluation": prior_evaluation.model_dump(mode="json") if prior_evaluation else None,
        "comparison_result": comparison,
        "predicate_provenance": "not_established"
        if comparison == "not_established"
        else "recomputed",
        "reason_codes": list(reasons),
        "expected_frontier_revision": frontier.revision if frontier else 0,
        "expected_frontier_ref": frontier.frontier_ref if frontier else None,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return AcquisitionEvaluationDecision.model_validate(
        {
            **payload,
            "content_hash": exact_n5_content_hash(payload),
        }
    )


@dataclass(frozen=True)
class AcquisitionEvaluationCurrentOwner:
    """Bound owner used only by actual current cheap/planner consumers."""

    bridge: AcquisitionWorldGrowthBridge
    current_basis_ref: ArtifactRef
    selection: _CurrentSelection
    prior: ResolvedAcquisitionEvaluation | None

    def revalidate(self) -> _CurrentSelection:
        """Recompute source/lease/basis rather than accepting a currentness flag."""
        current = _current_selection(self.bridge)
        if (
            current.phase_ref != self.selection.phase_ref
            or current.growth_ref != self.selection.growth_ref
            or current.growth != self.selection.growth
            or current.projection != self.selection.projection
            or current.closure != self.selection.closure
        ):
            raise ValueError("acquisition_retained_current_selection_changed")
        record = read_acquisition_evaluation_artifact(
            store=self.bridge.artifact_store,
            event_log=self.bridge.event_log,
            ref=self.current_basis_ref,
            record_type=AcquisitionEvaluationBasis,
        )
        replay = _basis_for_current(self.bridge, current, self.prior)
        if (
            type(record) is not AcquisitionEvaluationBasis
            or record.predicate_provenance != replay.predicate_provenance
            or record.reason_codes != replay.reason_codes
            or exact_n5_content_bytes(record.preparation_inputs.n5_execution_configuration)
            != exact_n5_content_bytes(current.prepared.n5_execution_configuration)
            or bytes.fromhex(record.effective_native_values_hex)
            != bytes.fromhex(replay.effective_native_values_hex)
        ):
            raise ValueError("acquisition_retained_current_basis_changed")
        return current

    def planner_snapshot(self, base: AcquisitionWorldSnapshot) -> AcquisitionWorldSnapshot:
        """Keep the old real evaluation world and bind the freshly revalidated source relation."""
        from polisyos.runtime.quality.acquisition_planner import AcquisitionWorldSnapshot

        self.revalidate()
        if (
            self.prior is None
            or type(base) is not AcquisitionWorldSnapshot
            or (
                base.world_model_record_ref != self.prior.selected.world_model_record_hash
                or base.world_ref != self.prior.selected.world_model_record_hash
            )
        ):
            raise ValueError("acquisition_retained_planner_evaluation_world_mismatch")
        return AcquisitionWorldSnapshot.model_validate(
            {
                **base.model_dump(mode="python"),
                "current_acquisition_basis_ref": self.current_basis_ref,
                "current_acquisition_growth_ref": self.selection.growth_ref,
                "current_acquisition_source_ref": self.selection.admitted_source_ref,
            }
        )


@dataclass(frozen=True)
class _CandidateRetainedBudgetFence:
    """The same owner state and observation surrounding one cheap reaction."""

    owner: CandidateAcquisitionEvaluationCurrentOwner | CandidateExperimentEvaluationCurrentOwner
    budget_state: BudgetState
    state_bytes: bytes
    observation: ProducerBudgetObservation


@dataclass(frozen=True)
class _CandidateRetainedPortScope:
    owner: CandidateAcquisitionEvaluationCurrentOwner | CandidateExperimentEvaluationCurrentOwner
    record: CandidateRetainedPortCapture


_CANDIDATE_RETAINED_PORT_SCOPE: ContextVar[_CandidateRetainedPortScope | None] = ContextVar(
    "polisyos_candidate_retained_port_scope", default=None
)


def _require_candidate_retained_port_scope(
    *, record: CandidateRetainedPortCapture, store: object, event_log: object
) -> None:
    """Permit the existing writer only inside the live current-owner capture."""
    scope = _CANDIDATE_RETAINED_PORT_SCOPE.get()
    if (
        type(scope) is not _CandidateRetainedPortScope
        or type(scope.owner)
        not in {
            CandidateAcquisitionEvaluationCurrentOwner,
            CandidateExperimentEvaluationCurrentOwner,
        }
        or scope.owner.bridge.artifact_store is not store
        or scope.owner.bridge.event_log is not event_log
        or not _candidate_model_values_same(scope.record, record)
    ):
        raise ValueError("candidate_retained_port_writer_scope_not_established")
    scope.owner.revalidate()


@dataclass(frozen=True)
class CandidateAcquisitionEvaluationCurrentOwner:
    """Live owner for equivalent candidate-source reuse, without observed admission.

    An instance alone is not a permit. Each consumer reopens the pending action,
    same-ledger window, selected source chain, both complete bases, actual N5
    witness and composition-root catalog before using the retained result.
    """

    bridge: AcquisitionWorldGrowthBridge
    closure: VerifiedAcquisitionRouteClosure
    candidate_action_ref: ArtifactRef
    candidate_world_intent_ref: ArtifactRef
    current_basis_ref: ArtifactRef
    decision_ref: ArtifactRef
    prior: ResolvedAcquisitionEvaluation
    prepared_n5_configuration: PreparedJointSimulationConfiguration

    def _budget_snapshot(
        self,
        window: BudgetLedgerReentryBudgetWindow,
        *,
        budget_state: BudgetState | None = None,
    ) -> tuple[BudgetState, ProducerBudgetObservation]:
        from polisyos.scientist.orchestration.engine import (
            BudgetState,
            ProducerBudgetObservation,
            ProducerBudgetObserver,
        )

        state = budget_state
        if state is None:
            state = BudgetState.model_validate(
                {"limits": {"run": {"key": "run", "max_usd": window.effective_limit_usd}}}
            )
        if type(state) is not BudgetState:
            raise ValueError("candidate_evaluation_budget_state_untyped")
        # Retention performs only local cheap reads. Reuse the real Control
        # budget/route/lease owner without requiring an available new N5 unit;
        # physical reentry has its own stricter preflight and reservation.
        service = self.bridge._source_control_service
        if service is None:
            raise ValueError("candidate_evaluation_budget_owner_not_established")
        observer = service.build_acquisition_source_budget_observer(
            closure=self.closure, budget_state=state, reentry_budget_scope=window.scope
        )
        if type(observer) is not ProducerBudgetObserver:
            raise ValueError("candidate_evaluation_budget_owner_not_established")
        ProducerBudgetObserver.require_bound_state(observer, state)
        ProducerBudgetObserver.admit(observer)
        observation = ProducerBudgetObserver.observe(observer)
        if type(observation) is not ProducerBudgetObservation:
            raise ValueError("candidate_evaluation_budget_observation_untyped")
        return state, observation

    def _revalidate_comparison(
        self, comparison: Literal["equivalent", "different"]
    ) -> CandidateAcquisitionEvaluationBasis:
        """Recompute one specified comparison under the same live owner fence."""
        from polisyos.core.artifacts import artifact_ref_identity_key
        from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
        from polisyos.runtime.http.services.control_plane_store import (
            AcquisitionEvaluationFrontierKey,
        )
        from polisyos.runtime.quality.acquisition_route_loop import (
            AcquisitionCandidateRouteLoopReceipt,
        )
        from polisyos.runtime.quality.candidate_source_basis import (
            _live_candidate_source_predecessors,
        )
        from polisyos.runtime.quality.candidate_source_reentry_history import (
            _read_historical_action,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import (
            PreparedJointSimulationConfiguration,
        )
        from polisyos.runtime.quality.substrate_registry import (
            current_catalog_serving_source,
            require_catalog_serving_source_unchanged,
            require_catalog_source_registry_binding,
        )
        from polisyos.runtime.quality.world_model_record import world_model_artifact_views

        bridge = self.bridge
        service = bridge._source_control_service
        if (
            type(bridge) is not AcquisitionWorldGrowthBridge
            or type(service) is not ControlPlaneService
            or service._artifact_store is not bridge.artifact_store
            or service._control_store is not bridge.control_store
            or type(self.prepared_n5_configuration) is not PreparedJointSimulationConfiguration
        ):
            raise ValueError("candidate_evaluation_current_owner_not_composed")
        action = bridge._require_selected_candidate_action(
            closure=self.closure, candidate_action_ref=self.candidate_action_ref
        )
        selected = bridge.candidate_source_selection(self.closure)
        if selected is None or action.selection != selected:
            raise ValueError("candidate_evaluation_current_selection_changed")
        window = bridge._resolve_candidate_source_budget_window(
            closure=self.closure, action_phase_ref=action.action_phase_ref
        )
        if (
            window.window_id != action.candidate_budget_window_id
            or window.record_digest != action.candidate_budget_window_digest
        ):
            raise ValueError("candidate_evaluation_budget_window_changed")
        budget_state, budget_before = self._budget_snapshot(window)
        budget_state_before = exact_n5_content_bytes(budget_state)
        profile, declaration, _ = bridge._candidate_source_prior_owner(closure=self.closure)
        intent_ref, intent = bridge._candidate_world_materialization_intent(
            closure=self.closure,
            candidate_action_ref=self.candidate_action_ref,
            configured_profile=profile,
            original_model_declaration=declaration,
            create=False,
        )
        if not _candidate_ref_same(intent_ref, self.candidate_world_intent_ref):
            raise ValueError("candidate_evaluation_world_intent_changed")
        prior = resolve_selected_acquisition_evaluation(bridge=bridge, closure=self.closure)
        if not _candidate_model_values_same(prior, self.prior):
            raise ValueError("candidate_evaluation_prior_selection_changed")
        catalog_source = service.catalog_serving_source
        if current_catalog_serving_source() is not catalog_source:
            raise ValueError("candidate_evaluation_catalog_scope_not_established")
        require_catalog_serving_source_unchanged(catalog_source)
        require_catalog_source_registry_binding(
            bridge.repo_root, prior.handoff.context.substrate_registry, catalog_source
        )
        decision = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=self.decision_ref,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        current = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=self.current_basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        if (
            type(decision) is not CandidateAcquisitionEvaluationDecision
            or type(current) is not CandidateAcquisitionEvaluationBasis
            or decision.comparison_result != comparison
            or decision.predicate_provenance != "recomputed"
            or not _candidate_ref_same(decision.current_basis_ref, self.current_basis_ref)
            or not _candidate_ref_same(decision.candidate_action_ref, self.candidate_action_ref)
            or not _candidate_ref_same(decision.candidate_world_intent_ref, intent_ref)
            or not _candidate_ref_same(decision.candidate_source_ref, action.candidate_source_ref)
            or decision.prior_basis_ref is None
            or decision.prior_evaluation is None
            or current.basis_role != "prospective"
            or not _candidate_ref_same(current.candidate_action_ref, self.candidate_action_ref)
            or not _candidate_ref_same(current.candidate_world_intent_ref, intent_ref)
            or not _candidate_ref_same(current.candidate_source_ref, action.candidate_source_ref)
            or current.prepared_n5_configuration != self.prepared_n5_configuration
            or not _candidate_model_values_same(
                current.preparation_inputs.configured_profile, profile
            )
            or not _candidate_model_values_same(
                current.preparation_inputs.original_model_declaration, declaration
            )
            or current.preparation_inputs.transaction_time != intent.transaction_time
            or not _candidate_ref_same(
                current.preparation_inputs.base_data_snapshot_ref,
                world_model_artifact_views(
                    profile.context_inputs.world_model_record
                ).data_snapshot_ref,
            )
            or current.preparation_inputs.slot_binding.profile_selection_ref
            != selected.profile_selection_ref
            or current.preparation_inputs.slot_binding.candidate_digest != selected.candidate_digest
            or current.preparation_inputs.slot_binding.canonical_variable_id
            != selected.canonical_variable_id
            or current.preparation_inputs.slot_binding.target_slot_id != selected.target_slot_id
            or not set(action.limitations).issubset(current.limitations)
        ):
            raise ValueError("candidate_evaluation_current_basis_binding_mismatch")
        scope = (
            self.closure.tenant_id,
            self.closure.cell_id,
            self.closure.run_id,
            self.closure.source_job_id,
            self.closure.route_id,
            action.action_job_id,
            action.action_generation,
            self.closure.design_problem_ref,
            self.closure.design_problem_basis_ref,
            self.closure.source_cycle.selected_candidate_ref,
            self.closure.source_cycle.selected_candidate_content_hash,
        )
        for record in (current, decision):
            if (
                record.tenant_id,
                record.cell_id,
                record.run_id,
                record.source_job_id,
                record.route_id,
                record.action_job_id,
                record.action_generation,
                record.design_problem_ref,
                record.design_problem_basis_ref,
                record.candidate_id,
                record.source_candidate_content_hash,
            ) != scope:
                raise ValueError("candidate_evaluation_current_scope_mismatch")
        if decision.compiled_ref != self.closure.compiled_ref:
            raise ValueError("candidate_evaluation_current_scope_mismatch")
        predecessors = _live_candidate_source_predecessors(bridge=bridge, closure=self.closure)
        if not predecessors or not self.closure.candidate_basis_transitions:
            raise ValueError("candidate_evaluation_prior_basis_not_established")
        previous_receipt = self.closure.candidate_basis_transitions[-1]
        previous_action, _ = _read_historical_action(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            action_ref=previous_receipt.candidate_action_ref,
        )
        service.verify_candidate_source_budget_window_historical(
            closure=self.closure, action=previous_action
        )
        previous = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=decision.prior_basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        if (
            type(previous) is not CandidateAcquisitionEvaluationBasis
            or previous.basis_role != "evaluated"
            or not _candidate_ref_same(
                previous.candidate_action_ref, previous_receipt.candidate_action_ref
            )
            or not _candidate_ref_same(
                previous.candidate_world_intent_ref, previous_receipt.candidate_world_intent_ref
            )
            or not _candidate_ref_same(
                previous.candidate_source_ref, previous_receipt.candidate_source_ref
            )
            or not _candidate_model_values_same(
                previous.preparation_inputs, predecessors[-1].inputs
            )
            or not _candidate_ref_same(
                previous.selected_data_snapshot_ref, previous_receipt.data_snapshot_ref
            )
            or not _candidate_ref_same(
                previous.selected_world_model_ref, previous_receipt.world_model_ref
            )
            or not _candidate_model_values_same(
                previous.evaluation, prior.selected.model_copy(update={"basis_ref": None})
            )
            or not _candidate_model_values_same(
                decision.prior_evaluation,
                prior.selected.model_copy(update={"basis_ref": decision.prior_basis_ref}),
            )
            or not _candidate_ref_same(
                current.preparation_inputs.base_world_model_ref, predecessors[-1].world_model_ref
            )
            or previous.tenant_id != previous_action.tenant_id
            or previous.cell_id != previous_action.cell_id
            or previous.run_id != previous_action.run_id
            or previous.source_job_id != previous_action.source_job_id
            or previous.action_job_id != previous_action.action_job_id
            or previous.action_generation != previous_action.action_generation
            or previous.route_id != previous_action.route_id
            or previous.design_problem_ref != self.closure.design_problem_ref
            or previous.design_problem_basis_ref != previous_receipt.design_problem_basis_ref
            or previous.candidate_id != previous_receipt.source_candidate_ref
            or previous.source_candidate_content_hash
            != previous_receipt.basis_transition.source_candidate_content_hash
            or not (set(previous_action.limitations) | set(previous_receipt.limitations)).issubset(
                previous.limitations
            )
            or not set(previous.limitations).issubset(current.limitations)
        ):
            raise ValueError("candidate_evaluation_prior_basis_binding_mismatch")
        sink = bridge.action_head_sink
        if sink is None:
            raise ValueError("candidate_evaluation_action_sink_missing")
        outcomes = sink.action_outcomes(
            tenant_id=self.closure.tenant_id,
            cell_id=self.closure.cell_id,
            run_id=self.closure.run_id,
            source_job_id=self.closure.source_job_id,
            route_id=self.closure.route_id,
        )
        prior_terminals = tuple(
            item for item in outcomes if item.head.action_generation < action.action_generation
        )
        if (
            tuple(item.head.action_generation for item in prior_terminals)
            != tuple(range(1, action.action_generation))
            or not prior_terminals
            or type(prior_terminals[-1].latest_receipt) is not AcquisitionCandidateRouteLoopReceipt
        ):
            raise ValueError("candidate_evaluation_prior_terminal_not_established")
        prior_terminal = prior_terminals[-1].latest_receipt
        intervening = tuple(
            item
            for item in prior_terminals
            if item.head.action_generation > previous_receipt.action_generation
        )
        if intervening:
            # Retention does not append an N5 cycle. Reopen every intervening
            # action through the actual route fold rather than treating the
            # latest materialized cycle as the complete limitation history.
            histories = getattr(self.closure, "candidate_terminal_history", None)
            if type(histories) is not tuple or any(
                type(item) is not CandidateEvaluationTerminalHistory for item in histories
            ):
                raise ValueError("candidate_evaluation_retained_limitations_not_established")
            selected_histories = tuple(
                item
                for item in histories
                if item.head.action_generation > previous_receipt.action_generation
            )
            if len(selected_histories) != len(intervening):
                raise ValueError("candidate_evaluation_retained_limitations_not_established")
            carried = set(previous.limitations)
            for outcome, history in zip(intervening, selected_histories, strict=True):
                continuation = history.continuation
                if (
                    history.head != outcome.head
                    or not _candidate_model_values_same(history.terminal, outcome.latest_receipt)
                    or history.terminal.terminal_outcome != "candidate_evaluation_retained"
                    or history.terminal_ref.manifest_profile_sha256 is None
                    or str(history.terminal_ref.artifact_id) != history.head.receipt_ref
                    or not _candidate_model_values_same(history.selected_basis, previous)
                    or not _candidate_model_values_same(history.evaluation, prior)
                    or continuation is None
                    or not _candidate_ref_same(
                        continuation.candidate_action_ref, history.terminal.candidate_action_ref
                    )
                    or not _candidate_model_values_same(
                        continuation.retained_evaluation, history.terminal.selected_evaluation
                    )
                    or not _candidate_ref_same(
                        continuation.current_basis_ref, history.decision.current_basis_ref
                    )
                    or not _candidate_ref_same(
                        continuation.evaluation_decision_ref,
                        history.terminal.evaluation_decision_ref,
                    )
                    or not (carried | set(history.current_basis.limitations)).issubset(
                        continuation.limitations
                    )
                ):
                    raise ValueError("candidate_evaluation_retained_limitations_not_established")
                carried.update(continuation.limitations)
            if not carried.issubset(current.limitations):
                raise ValueError("candidate_evaluation_retained_limitations_not_established")
        if (
            not _candidate_ref_same(prior_terminal.selected_basis_ref, decision.prior_basis_ref)
            or prior_terminal.selected_evaluation is None
            or not _candidate_model_values_same(
                prior_terminal.selected_evaluation, decision.prior_evaluation
            )
        ):
            raise ValueError("candidate_evaluation_prior_terminal_mismatch")
        frontier = bridge.control_store.read_acquisition_evaluation_frontier(
            AcquisitionEvaluationFrontierKey(
                tenant_id=self.closure.tenant_id,
                cell_id=self.closure.cell_id,
                source_job_id=self.closure.source_job_id,
                design_problem_ref=self.closure.design_problem_ref,
                candidate_id=self.closure.source_cycle.selected_candidate_ref,
            )
        )
        if (
            frontier is None
            or frontier.revision != decision.expected_frontier_revision
            or frontier.frontier_ref != decision.expected_frontier_ref
            or frontier.basis_ref != str(decision.prior_basis_ref.artifact_id)
            or frontier.basis_content_hash != previous.content_hash
            or frontier.selected_evaluation_witness_ref
            != str(prior.selected.n5_execution_ref.artifact_id)
            or frontier.selected_evaluation_content_hash != prior.execution.content_hash
            or artifact_ref_identity_key(prior_terminal.selected_evaluation_witness_ref)
            != artifact_ref_identity_key(prior.selected.n5_execution_ref)
        ):
            raise ValueError("candidate_evaluation_prior_frontier_mismatch")
        prior_values, prior_reasons = recompute_candidate_acquisition_basis_values(
            artifact_store=bridge.artifact_store,
            problem=self.closure.design_problem_basis,
            preparation_inputs=previous.preparation_inputs,
            predecessors=predecessors[:-1],
            prior=prior,
            prepared_n5_configuration=previous.prepared_n5_configuration,
            fresh_limit_usd=previous_action.selection.reentry_budget_usd,
            global_limit_usd=service.acquisition_source_global_budget_usd(closure=self.closure),
            selected_data_snapshot_ref=previous.selected_data_snapshot_ref,
            selected_world_model_ref=previous.selected_world_model_ref,
        )
        current_values, current_reasons = recompute_candidate_acquisition_basis_values(
            artifact_store=bridge.artifact_store,
            problem=self.closure.design_problem_basis,
            preparation_inputs=current.preparation_inputs,
            predecessors=predecessors,
            prior=prior,
            prepared_n5_configuration=self.prepared_n5_configuration,
            fresh_limit_usd=window.fresh_limit_usd,
            global_limit_usd=window.global_limit_usd,
        )
        if (
            prior_reasons
            or current_reasons
            or previous.predicate_provenance != "recomputed"
            or current.predicate_provenance != "recomputed"
            or exact_n5_content_bytes(prior_values)
            != bytes.fromhex(previous.effective_native_values_hex)
            or exact_n5_content_bytes(current_values)
            != bytes.fromhex(current.effective_native_values_hex)
            or basis_exact_values_equal(previous, current) != (comparison == "equivalent")
            or bridge._require_selected_candidate_action(
                closure=self.closure, candidate_action_ref=self.candidate_action_ref
            )
            != action
        ):
            raise ValueError("candidate_evaluation_comparison_not_established")
        if bridge.control_store.read_acquisition_evaluation_frontier(frontier.key) != frontier:
            raise ValueError("candidate_evaluation_prior_frontier_changed")
        checked_state, budget_after = self._budget_snapshot(window, budget_state=budget_state)
        if (
            checked_state is not budget_state
            or exact_n5_content_bytes(checked_state) != budget_state_before
            or budget_after != budget_before
        ):
            raise ValueError("candidate_evaluation_budget_observation_changed")
        require_catalog_serving_source_unchanged(catalog_source)
        require_catalog_source_registry_binding(
            bridge.repo_root, prior.handoff.context.substrate_registry, catalog_source
        )
        return current

    def revalidate(self) -> CandidateAcquisitionEvaluationBasis:
        """Require an exactly equivalent current basis before retaining the prior N5."""
        return self._revalidate_comparison("equivalent")

    def currentness_resolver(self) -> bool:
        """Recheck the actual candidate owner; unknown never becomes permission."""
        try:
            self.revalidate()
        except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
            from polisyos.core.artifacts import raise_artifact_read_access_error

            raise_artifact_read_access_error(exc)
            return False
        return True

    def current_budget_snapshot(
        self, *, budget_state: BudgetState | None = None
    ) -> tuple[BudgetState, ProducerBudgetObservation]:
        """Reopen the ledger and reconcile the same state around cheap work.

        Pass the returned state back after the work and compare both detached
        observations. The observation is not a per-call reservation and does
        not establish allocations held by a different runtime state.
        """
        self.revalidate()
        action = self.bridge._require_selected_candidate_action(
            closure=self.closure, candidate_action_ref=self.candidate_action_ref
        )
        window = self.bridge._resolve_candidate_source_budget_window(
            closure=self.closure, action_phase_ref=action.action_phase_ref
        )
        return self._budget_snapshot(window, budget_state=budget_state)

    def begin_retained_port_capture(self) -> _CandidateRetainedBudgetFence:
        """Capture the actual ledger state before producing fresh port outputs."""
        state, observation = self.current_budget_snapshot()
        return _CandidateRetainedBudgetFence(
            owner=self,
            budget_state=state,
            state_bytes=exact_n5_content_bytes(state),
            observation=observation,
        )

    def capture_retained_port_source(
        self,
        source: object,
        *,
        fence: _CandidateRetainedBudgetFence,
    ) -> tuple[ArtifactRef, ArtifactRef]:
        """Select fresh port outputs under this action and its live owner fence.

        The caller is the configured generation producer after its real
        grounding and value-owner calls. This method records their exact source
        and budget scope; it does not turn those observations into admission.
        """
        from polisyos.runtime.quality.acquisition_planner import (
            _n7_put_configured_candidate_port_source,
            _N7ConfiguredCandidatePortSource,
        )
        from polisyos.runtime.quality.acquisition_retained_continuation import (
            CandidateRetainedPortCapture,
        )
        from polisyos.runtime.quality.generation_cycle import ValuePortObservation
        from polisyos.runtime.quality.substrate_registry import (
            _catalog_content_ref,
            current_catalog_serving_source,
        )

        if (
            type(self)
            not in {
                CandidateAcquisitionEvaluationCurrentOwner,
                CandidateExperimentEvaluationCurrentOwner,
            }
            or type(source) is not _N7ConfiguredCandidatePortSource
            or (type(fence) is not _CandidateRetainedBudgetFence or fence.owner is not self)
        ):
            raise ValueError("candidate_retained_port_owner_not_established")
        current = self.revalidate()
        selected = self.prior.selected
        decision = read_acquisition_evaluation_artifact(
            store=self.bridge.artifact_store,
            event_log=self.bridge.event_log,
            ref=self.decision_ref,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        if (
            type(decision) is not CandidateAcquisitionEvaluationDecision
            or decision.prior_evaluation is None
            or not _candidate_model_values_same(
                decision.prior_evaluation,
                selected.model_copy(update={"basis_ref": decision.prior_basis_ref}),
            )
            or (
                source.tenant_id,
                source.cell_id,
                source.run_id,
                source.source_job_id,
                source.source_generation_run_id,
                source.cycle_index,
                source.candidate_id,
                source.candidate_content_hash,
                source.design_problem_basis_ref,
            )
            != (
                self.closure.tenant_id
                if type(self) is CandidateAcquisitionEvaluationCurrentOwner
                else self.origin.tenant_id,
                self.closure.cell_id
                if type(self) is CandidateAcquisitionEvaluationCurrentOwner
                else self.origin.cell_id,
                self.closure.run_id
                if type(self) is CandidateAcquisitionEvaluationCurrentOwner
                else self.origin.run_id,
                selected.evaluation_job_id,
                selected.generation_run_id,
                selected.cycle_index,
                selected.candidate_id,
                selected.candidate_content_hash,
                selected.design_problem_ref,
            )
            or any(
                not _candidate_ref_same(actual, expected)
                for actual, expected in (
                    (source.n4_source_ref, selected.n4_source_ref),
                    (source.context_job_ref, selected.context_job_ref),
                    (source.n5_input_ref, selected.n5_input_ref),
                    (source.n5_execution_ref, selected.n5_execution_ref),
                    (source.n5_result_ref, selected.n5_result_ref),
                )
            )
        ):
            raise ValueError("candidate_retained_port_prior_selection_mismatch")
        value = ValuePortObservation.model_validate(source.value_observation)
        source_cycle = (
            self.closure.source_cycle
            if type(self) is CandidateAcquisitionEvaluationCurrentOwner
            else self.source_cycle
        )
        old_routing = source_cycle.value_port.candidate_n5_l1_routing
        if value.candidate_n5_l1_routing is None or (
            old_routing is not None
            and not _candidate_model_values_same(
                value.candidate_n5_l1_routing.requirement_gap, old_routing.requirement_gap
            )
        ):
            raise ValueError("candidate_retained_port_l1_not_established")
        catalog = self.bridge._source_control_service.catalog_serving_source
        if current_catalog_serving_source() is not catalog:
            raise ValueError("candidate_retained_port_catalog_not_established")
        catalog_ref = _catalog_content_ref(catalog)
        state, after = self.current_budget_snapshot(budget_state=fence.budget_state)
        if (
            state is not fence.budget_state
            or exact_n5_content_bytes(state) != fence.state_bytes
            or after != fence.observation
        ):
            raise ValueError("candidate_retained_port_budget_changed")
        source_ref = _n7_put_configured_candidate_port_source(self.bridge.artifact_store, source)
        saved = _candidate_evaluation_artifact_for_recovery(
            bridge=self.bridge,
            closure=(
                self.closure if type(self) is CandidateAcquisitionEvaluationCurrentOwner else None
            ),
            origin=(
                self.origin if type(self) is CandidateExperimentEvaluationCurrentOwner else None
            ),
            pending_phase_ref=(
                self.pending_phase_ref
                if type(self) is CandidateExperimentEvaluationCurrentOwner
                else None
            ),
            candidate_action_ref=self.candidate_action_ref,
            role="retained_port_capture",
        )
        previous = saved[1] if saved is not None else None
        if previous is not None and type(previous) is not CandidateRetainedPortCapture:
            raise ValueError("candidate_retained_port_recovery_untyped")
        payload = {
            "tenant_id": decision.tenant_id,
            "cell_id": decision.cell_id,
            "run_id": decision.run_id,
            "source_job_id": decision.source_job_id,
            "action_job_id": decision.action_job_id,
            "action_generation": decision.action_generation,
            "route_id": decision.route_id,
            "compiled_ref": decision.compiled_ref,
            "design_problem_ref": decision.design_problem_ref,
            "design_problem_basis_ref": decision.design_problem_basis_ref,
            "candidate_id": decision.candidate_id,
            "candidate_action_ref": self.candidate_action_ref,
            "candidate_world_intent_ref": self.candidate_world_intent_ref,
            "candidate_source_ref": current.candidate_source_ref,
            "evaluation_decision_ref": self.decision_ref,
            "current_basis_ref": self.current_basis_ref,
            "retained_evaluation": decision.prior_evaluation,
            "configured_port_source_ref": source_ref,
            "catalog_content_ref": catalog_ref,
            "budget_observation_before": fence.observation,
            "budget_observation_after": after,
            "generated_at": previous.generated_at if previous else datetime.now(UTC).isoformat(),
        }
        # Include model defaults in the same canonical content hash as its reader.
        provisional = CandidateRetainedPortCapture.model_construct(**payload, content_hash="")
        record = CandidateRetainedPortCapture.model_validate(
            {
                **payload,
                "content_hash": exact_n5_content_hash(
                    provisional.model_dump(mode="json", exclude={"content_hash"})
                ),
            }
        )
        if previous is not None and not _candidate_model_values_same(previous, record):
            raise ValueError("candidate_retained_port_recovery_changed")
        token = _CANDIDATE_RETAINED_PORT_SCOPE.set(_CandidateRetainedPortScope(self, record))
        try:
            capture_ref = _select_candidate_evaluation_artifact(
                bridge=self.bridge,
                closure=(
                    self.closure
                    if type(self) is CandidateAcquisitionEvaluationCurrentOwner
                    else None
                ),
                origin=(
                    self.origin if type(self) is CandidateExperimentEvaluationCurrentOwner else None
                ),
                pending_phase_ref=(
                    self.pending_phase_ref
                    if type(self) is CandidateExperimentEvaluationCurrentOwner
                    else None
                ),
                record=record,
            )
        finally:
            _CANDIDATE_RETAINED_PORT_SCOPE.reset(token)
        checked_state, checked = self.current_budget_snapshot(budget_state=state)
        if (
            checked_state is not state
            or exact_n5_content_bytes(state) != fence.state_bytes
            or checked != fence.observation
            or current_catalog_serving_source() is not catalog
            or _catalog_content_ref(catalog) != catalog_ref
        ):
            raise ValueError("candidate_retained_port_owner_changed")
        self.revalidate()
        return source_ref, capture_ref

    def planner_snapshot(self, base: AcquisitionWorldSnapshot) -> AcquisitionWorldSnapshot:
        """Bind the candidate relation while retaining the actual prior N5 world."""
        from polisyos.runtime.quality.acquisition_planner import AcquisitionWorldSnapshot

        current = self.revalidate()
        if (
            type(base) is not AcquisitionWorldSnapshot
            or base.world_model_record_ref != self.prior.selected.world_model_record_hash
            or base.world_ref != self.prior.selected.world_model_record_hash
        ):
            raise ValueError("candidate_evaluation_planner_world_mismatch")
        return AcquisitionWorldSnapshot.model_validate(
            {
                **base.model_dump(mode="python"),
                "current_candidate_basis_ref": self.current_basis_ref,
                "current_candidate_action_ref": self.candidate_action_ref,
                "current_candidate_source_ref": current.candidate_source_ref,
            }
        )


@dataclass(frozen=True)
class CandidateExperimentEvaluationCurrentOwner:
    """Live owner for a candidate experiment comparison over a verified prefix."""

    bridge: AcquisitionWorldGrowthBridge
    origin: VerifiedCandidateExperimentOrigin
    selection: AcquisitionCandidateSourceRoute
    pending_phase_ref: str
    action_phase_ref: str
    candidate_action_ref: ArtifactRef
    candidate_world_intent_ref: ArtifactRef
    current_basis_ref: ArtifactRef
    decision_ref: ArtifactRef
    prior_owner: CandidateExperimentPriorOwner
    prepared_n5_configuration: PreparedJointSimulationConfiguration
    budget_window: BudgetLedgerReentryBudgetWindow
    comparison: _ComparisonResult

    @property
    def prior(self) -> ResolvedAcquisitionEvaluation | None:
        """Return the source owner's selected prior evaluation, when present."""
        value = getattr(self.prior_owner, "selected_evaluation", None)
        return value if type(value) is ResolvedAcquisitionEvaluation else None

    @property
    def generation_run(self) -> object:
        """Return the verified effective generation run."""
        return getattr(self.prior_owner, "generation_run", None)

    @property
    def source_cycle(self) -> object:
        """Return the verified effective source cycle."""
        return getattr(self.prior_owner, "source_cycle", None)

    @property
    def design_problem_basis(self) -> object:
        """Return the immutable source design problem."""
        return self.origin.design_problem_basis

    def revalidate(self) -> CandidateAcquisitionEvaluationBasis:
        """Replay the current action, full prior history, basis, frontier, and budget."""
        return _revalidate_candidate_experiment_evaluation_owner(self)

    def currentness_resolver(self) -> bool:
        """Expose only an owner-replayed Boolean to the configured port adapter."""
        try:
            self.revalidate()
        except (OSError, RuntimeError, TypeError, ValueError, KeyError, AttributeError) as exc:
            from polisyos.core.artifacts import raise_artifact_read_access_error

            raise_artifact_read_access_error(exc)
            return False
        return True

    def current_budget_snapshot(
        self, *, budget_state: BudgetState | None = None
    ) -> tuple[BudgetState, ProducerBudgetObservation]:
        """Reopen the experiment budget window without reserving a new N5 unit."""
        self.revalidate()
        return _candidate_experiment_budget_snapshot(self, budget_state=budget_state)

    def begin_retained_port_capture(self) -> _CandidateRetainedBudgetFence:
        """Pin the same independently reconciled budget around fresh cheap work."""
        state, observation = self.current_budget_snapshot()
        return _CandidateRetainedBudgetFence(
            owner=self,
            budget_state=state,
            state_bytes=exact_n5_content_bytes(state),
            observation=observation,
        )

    def capture_retained_port_source(
        self,
        source: object,
        *,
        fence: _CandidateRetainedBudgetFence,
    ) -> tuple[ArtifactRef, ArtifactRef]:
        """Use the canonical shared capture writer under this experiment owner."""
        return CandidateAcquisitionEvaluationCurrentOwner.capture_retained_port_source(
            self, source, fence=fence
        )

    def planner_snapshot(self, base: AcquisitionWorldSnapshot) -> AcquisitionWorldSnapshot:
        """Bind the current experiment relation while preserving the prior N5 world."""
        from polisyos.runtime.quality.acquisition_planner import AcquisitionWorldSnapshot

        current = self.revalidate()
        prior = self.prior
        if (
            prior is None
            or type(base) is not AcquisitionWorldSnapshot
            or base.world_model_record_ref != prior.selected.world_model_record_hash
            or base.world_ref != prior.selected.world_model_record_hash
        ):
            raise ValueError("candidate_experiment_retained_planner_world_mismatch")
        return AcquisitionWorldSnapshot.model_validate(
            {
                **base.model_dump(mode="python"),
                "current_candidate_basis_ref": self.current_basis_ref,
                "current_candidate_action_ref": self.candidate_action_ref,
                "current_candidate_source_ref": current.candidate_source_ref,
            }
        )


def _candidate_experiment_budget_snapshot(
    owner: CandidateExperimentEvaluationCurrentOwner,
    *,
    budget_state: BudgetState | None = None,
) -> tuple[BudgetState, ProducerBudgetObservation]:
    """Read the live action budget without asking for N5 invocation capacity."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.scientist.orchestration.engine import (
        BudgetState,
        ProducerBudgetObservation,
        ProducerBudgetObserver,
    )

    bridge = owner.bridge
    service = bridge._source_control_service
    if (
        type(owner) is not CandidateExperimentEvaluationCurrentOwner
        or type(service) is not ControlPlaneService
        or service._artifact_store is not bridge.artifact_store
        or service._control_store is not bridge.control_store
    ):
        raise ValueError("candidate_experiment_retained_budget_owner_not_established")
    window = bridge.resolve_candidate_experiment_reentry_budget_window(
        origin=owner.origin,
        candidate_action_ref=owner.candidate_action_ref,
    )
    if window != owner.budget_window:
        raise ValueError("candidate_experiment_retained_budget_window_changed")
    state = budget_state
    if state is None:
        state = BudgetState.model_validate(
            {"limits": {"run": {"key": "run", "max_usd": window.effective_limit_usd}}}
        )
    if type(state) is not BudgetState:
        raise ValueError("candidate_experiment_retained_budget_state_untyped")
    observer = service.build_candidate_experiment_reentry_budget_observer(
        origin=owner.origin,
        candidate_action_ref=owner.candidate_action_ref,
        budget_state=state,
        reentry_budget_scope=window.scope,
    )
    if type(observer) is not ProducerBudgetObserver:
        raise ValueError("candidate_experiment_retained_budget_observer_untyped")
    ProducerBudgetObserver.require_bound_state(observer, state)
    observation = ProducerBudgetObserver.observe(observer)
    if (
        type(observation) is not ProducerBudgetObservation
        or observation.run_binding != window.scope.run_binding
        or observation.predicate_basis != "independently_reconciled"
        or observation.remaining_usd < 0
    ):
        raise ValueError("candidate_experiment_retained_budget_observation_not_established")
    return state, observation


def _candidate_experiment_reentry_execution_matches(
    *,
    action: CandidateAcquisitionActionReceipt,
    phase: AcquisitionCandidateExperimentPhaseReceipt,
    job: ControlJobRecord,
    selected_action_phase_ref: str,
) -> bool:
    """Bind a reentry action to the selected phase and its live job record."""
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
    )

    if (
        type(action) is not CandidateAcquisitionActionReceipt
        or type(phase) is not AcquisitionCandidateExperimentPhaseReceipt
        or type(job) is not ControlJobRecord
    ):
        return False
    return (
        action.action_phase_ref == selected_action_phase_ref
        and action.action_job_id == phase.job_id == job.job_id
        and action.action_generation == phase.action_generation
        and job.kind == "acquisition"
        and job.state == "running"
    )


def _candidate_experiment_prior_owners_match(
    *,
    current: CandidateExperimentPriorOwner,
    expected: CandidateExperimentPriorOwner,
    artifact_store: ArtifactStore,
) -> bool:
    """Compare prior-owner values without using wrapper object identity."""
    from polisyos.runtime.quality.cycle_substrate import (
        ConfiguredCandidateSimulationContextAdmissionOwner,
    )

    if (
        type(current) is not CandidateExperimentPriorOwner
        or type(expected) is not CandidateExperimentPriorOwner
    ):
        return False
    current_context = current.context_owner
    expected_context = expected.context_owner
    if (
        type(current_context) is not ConfiguredCandidateSimulationContextAdmissionOwner
        or type(expected_context) is not ConfiguredCandidateSimulationContextAdmissionOwner
        or current_context.store is not artifact_store
        or expected_context.store is not artifact_store
    ):
        return False

    def configured_values_match(current_values: object, expected_values: object) -> bool:
        if type(current_values) is not tuple or type(expected_values) is not tuple:
            return False
        if len(current_values) != len(expected_values):
            return False
        return all(
            _candidate_model_values_same(current_value, expected_value)
            for current_value, expected_value in zip(current_values, expected_values, strict=True)
        )

    return (
        configured_values_match(current_context.profiles, expected_context.profiles)
        and configured_values_match(
            current_context.model_declarations, expected_context.model_declarations
        )
        and _candidate_model_values_same(current.profile, expected.profile)
        and _candidate_model_values_same(current.model_declaration, expected.model_declaration)
        and _candidate_model_values_same(current.generation_run, expected.generation_run)
        and _candidate_model_values_same(current.source_cycle, expected.source_cycle)
        and _candidate_model_values_same(current.selected_evaluation, expected.selected_evaluation)
        and _candidate_model_values_same(current.first_n4_source, expected.first_n4_source)
    )


def _revalidate_candidate_experiment_evaluation_owner(
    owner: CandidateExperimentEvaluationCurrentOwner,
) -> CandidateAcquisitionEvaluationBasis:
    """Recompute the selected experiment comparison against its exact prefix."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionEvaluationFrontierKey,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _current_candidate_experiment_reentry_action,
    )
    from polisyos.runtime.quality.candidate_source_basis import (
        _candidate_source_predecessors_for_verified_experiment_origin,
        prepare_live_candidate_experiment_source_basis_values,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
        prepare_joint_simulation_configuration,
    )
    from polisyos.runtime.quality.substrate_registry import (
        current_catalog_serving_source,
        require_catalog_serving_source_unchanged,
        require_catalog_source_registry_binding,
    )

    bridge = owner.bridge
    service = bridge._source_control_service
    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or type(owner.origin) is not VerifiedCandidateExperimentOrigin
        or type(service) is not ControlPlaneService
        or service._artifact_store is not bridge.artifact_store
        or service._control_store is not bridge.control_store
        or type(owner.prior_owner) is not CandidateExperimentPriorOwner
        or type(owner.prepared_n5_configuration) is not PreparedJointSimulationConfiguration
    ):
        raise ValueError("candidate_experiment_evaluation_owner_not_composed")
    selection, phase, admission, action = _current_candidate_experiment_reentry_action(
        bridge,
        owner.origin,
        owner.pending_phase_ref,
        owner.candidate_action_ref,
    )
    if (
        selection != owner.selection
        or phase.receipt_phase != "candidate_input_reentry_pending"
        or not _candidate_experiment_reentry_execution_matches(
            action=action,
            phase=phase,
            job=admission.job,
            selected_action_phase_ref=owner.action_phase_ref,
        )
    ):
        raise ValueError("candidate_experiment_evaluation_action_changed")
    prior_owner = bridge._candidate_experiment_prior_owner(
        origin=owner.origin,
        selection=selection,
    )
    if (
        not _candidate_experiment_prior_owners_match(
            current=prior_owner,
            expected=owner.prior_owner,
            artifact_store=bridge.artifact_store,
        )
        or not _candidate_model_values_same(
            prior_owner.selected_evaluation,
            owner.prior,
        )
        or not _candidate_model_values_same(
            prior_owner.source_cycle,
            owner.origin.effective_source_cycle,
        )
        or not _candidate_model_values_same(
            prior_owner.generation_run,
            owner.origin.effective_generation_run,
        )
    ):
        raise ValueError("candidate_experiment_evaluation_prior_changed")

    latest_history = _candidate_experiment_verified_prior_history(
        bridge=bridge,
        origin=owner.origin,
    )
    if latest_history is not None and prior_owner.selected_evaluation is None:
        raise ValueError("candidate_experiment_evaluation_prior_history_mismatch")
    current_frontier = None
    previous_basis = None
    previous_basis_ref = None
    candidate_only_prior = latest_history is not None and latest_history.frontier_after is None
    if latest_history is not None and not candidate_only_prior:
        if (
            latest_history.selected_basis is None
            or latest_history.evaluation is None
            or latest_history.frontier_after is None
            or not _candidate_model_values_same(
                latest_history.evaluation,
                prior_owner.selected_evaluation,
            )
        ):
            raise ValueError("candidate_experiment_evaluation_prior_not_selected")
        previous_basis = latest_history.selected_basis
        previous_basis_ref = latest_history.terminal.selected_basis_ref
        current_frontier = latest_history.frontier_after

    key = AcquisitionEvaluationFrontierKey(
        tenant_id=owner.origin.tenant_id,
        cell_id=owner.origin.cell_id,
        source_job_id=owner.origin.source_job_id,
        design_problem_ref=owner.origin.policy_scope.design_problem_ref,
        candidate_id=owner.origin.policy_scope.candidate_id,
    )
    if bridge.control_store.read_acquisition_evaluation_frontier(key) != current_frontier:
        raise ValueError("candidate_experiment_evaluation_frontier_changed")
    window = bridge.resolve_candidate_experiment_reentry_budget_window(
        origin=owner.origin,
        candidate_action_ref=owner.candidate_action_ref,
    )
    if window != owner.budget_window:
        raise ValueError("candidate_experiment_evaluation_budget_window_changed")
    profile = prior_owner.profile
    declaration = prior_owner.model_declaration
    intent_ref, intent = bridge._candidate_world_materialization_intent(
        origin=owner.origin,
        candidate_action_ref=owner.candidate_action_ref,
        configured_profile=profile,
        original_model_declaration=declaration,
        create=False,
    )
    if not _candidate_ref_same(intent_ref, owner.candidate_world_intent_ref):
        raise ValueError("candidate_experiment_evaluation_intent_changed")
    preparation, prepared_intent_ref, prepared_intent = (
        prepare_live_candidate_experiment_source_basis_values(
            bridge=bridge,
            origin=owner.origin,
            candidate_action_ref=owner.candidate_action_ref,
            pending_phase_ref=owner.pending_phase_ref,
        )
    )
    if (
        preparation.predicate_provenance != "recomputed"
        or preparation.reason_codes
        or preparation.inputs is None
        or not _candidate_ref_same(prepared_intent_ref, intent_ref)
        or prepared_intent != intent
        or prepare_joint_simulation_configuration() != owner.prepared_n5_configuration
    ):
        raise ValueError("candidate_experiment_evaluation_preparation_changed")

    decision = read_acquisition_evaluation_artifact(
        store=bridge.artifact_store,
        event_log=bridge.event_log,
        ref=owner.decision_ref,
        record_type=CandidateAcquisitionEvaluationDecision,
    )
    current = read_acquisition_evaluation_artifact(
        store=bridge.artifact_store,
        event_log=bridge.event_log,
        ref=owner.current_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    _require_candidate_experiment_evaluation_record_scope(
        bridge=bridge,
        origin=owner.origin,
        pending_phase_ref=owner.pending_phase_ref,
        candidate_action_ref=owner.candidate_action_ref,
        record=current,
    )
    _require_candidate_experiment_evaluation_record_scope(
        bridge=bridge,
        origin=owner.origin,
        pending_phase_ref=owner.pending_phase_ref,
        candidate_action_ref=owner.candidate_action_ref,
        record=decision,
    )
    if (
        type(current) is not CandidateAcquisitionEvaluationBasis
        or type(decision) is not CandidateAcquisitionEvaluationDecision
        or current.basis_role != "prospective"
        or current.preparation_inputs != preparation.inputs
        or current.prepared_n5_configuration != owner.prepared_n5_configuration
        or not _candidate_ref_same(current.candidate_world_intent_ref, intent_ref)
        or not _candidate_ref_same(current.candidate_source_ref, action.candidate_source_ref)
        or not _candidate_ref_same(decision.current_basis_ref, owner.current_basis_ref)
        or not _candidate_ref_same(decision.candidate_action_ref, owner.candidate_action_ref)
        or not _candidate_ref_same(decision.candidate_world_intent_ref, intent_ref)
        or not _candidate_ref_same(decision.candidate_source_ref, action.candidate_source_ref)
        or not set(action.limitations).issubset(current.limitations)
    ):
        raise ValueError("candidate_experiment_evaluation_current_basis_changed")

    actual_prior = prior_owner.selected_evaluation
    if latest_history is None or candidate_only_prior:
        expected_comparison: _ComparisonResult = "not_established"
        expected_prior = None
        expected_revision = 0
        expected_frontier_ref = None
        if bridge.control_store.read_acquisition_evaluation_frontier(key) is not None:
            raise ValueError("candidate_experiment_evaluation_unexpected_frontier")
    else:
        if actual_prior is None or previous_basis is None or previous_basis_ref is None:
            raise ValueError("candidate_experiment_evaluation_prior_not_established")
        expected_prior = actual_prior.selected.model_copy(update={"basis_ref": previous_basis_ref})
        expected_comparison = (
            "equivalent" if basis_exact_values_equal(previous_basis, current) else "different"
        )
        expected_revision = current_frontier.revision
        expected_frontier_ref = current_frontier.frontier_ref
        if not _candidate_model_values_same(
            latest_history.terminal.selected_evaluation,
            expected_prior,
        ):
            raise ValueError("candidate_experiment_evaluation_prior_witness_changed")

    if owner.comparison != expected_comparison:
        raise ValueError("candidate_experiment_evaluation_comparison_changed")
    predecessors = _candidate_source_predecessors_for_verified_experiment_origin(
        store=bridge.artifact_store,
        origin=owner.origin,
    )
    values, reasons = recompute_candidate_acquisition_basis_values(
        artifact_store=bridge.artifact_store,
        problem=owner.origin.design_problem_basis,
        preparation_inputs=preparation.inputs,
        predecessors=predecessors,
        prior=actual_prior,
        prepared_n5_configuration=owner.prepared_n5_configuration,
        fresh_limit_usd=window.fresh_limit_usd,
        global_limit_usd=window.global_limit_usd,
    )
    if latest_history is not None and not candidate_only_prior:
        if reasons:
            raise ValueError("candidate_experiment_evaluation_current_basis_not_established")
        previous_values, previous_reasons = recompute_candidate_acquisition_basis_values(
            artifact_store=bridge.artifact_store,
            problem=owner.origin.design_problem_basis,
            preparation_inputs=previous_basis.preparation_inputs,
            predecessors=_candidate_source_predecessors_for_verified_experiment_origin(
                store=bridge.artifact_store,
                origin=owner.origin,
                before_action_generation=previous_basis.action_generation,
            ),
            prior=actual_prior,
            prepared_n5_configuration=previous_basis.prepared_n5_configuration,
            fresh_limit_usd=latest_history.budget_window.fresh_limit_usd,
            global_limit_usd=latest_history.budget_window.global_limit_usd,
            selected_data_snapshot_ref=previous_basis.selected_data_snapshot_ref,
            selected_world_model_ref=previous_basis.selected_world_model_ref,
        )
        if (
            previous_reasons
            or previous_basis.predicate_provenance != "recomputed"
            or exact_n5_content_bytes(previous_values)
            != bytes.fromhex(previous_basis.effective_native_values_hex)
        ):
            raise ValueError("candidate_experiment_evaluation_prior_basis_changed")
    else:
        previous_reasons = ()
    if candidate_only_prior:
        changed = _candidate_experiment_unselected_input_changed(
            bridge=bridge, origin=owner.origin, prior=actual_prior, prepared=preparation
        )
        input_reason = (
            "candidate_experiment_changed_input"
            if changed
            else "candidate_experiment_input_change_not_established"
        )
        expected_reasons = tuple(
            dict.fromkeys(
                ("candidate_evaluation_prior_basis_not_established", input_reason, *reasons)
            )
        )
    else:
        expected_reasons = (
            tuple(dict.fromkeys(("candidate_evaluation_prior_basis_not_established", *reasons)))
            if latest_history is None
            else reasons
        )
    expected_current_provenance = "not_established" if reasons else "recomputed"
    if (
        reasons != current.reason_codes
        or expected_current_provenance != current.predicate_provenance
        or exact_n5_content_bytes(values) != bytes.fromhex(current.effective_native_values_hex)
        or decision.comparison_result != expected_comparison
        or decision.predicate_provenance
        != ("not_established" if expected_comparison == "not_established" else "recomputed")
        or decision.reason_codes != expected_reasons
        or not _candidate_ref_same(decision.prior_basis_ref, previous_basis_ref)
        or not _candidate_model_values_same(decision.prior_evaluation, expected_prior)
        or decision.expected_frontier_revision != expected_revision
        or decision.expected_frontier_ref != expected_frontier_ref
    ):
        raise ValueError("candidate_experiment_evaluation_decision_changed")
    inherited = _candidate_experiment_inherited_limitations(owner.origin)
    if not set(inherited).issubset(current.limitations):
        raise ValueError("candidate_experiment_evaluation_limitations_changed")
    if bridge.control_store.read_acquisition_evaluation_frontier(key) != current_frontier:
        raise ValueError("candidate_experiment_evaluation_frontier_changed")
    state, observation = _candidate_experiment_budget_snapshot(owner)
    run_limit = state.limits.get("run")
    if (
        observation.run_binding != window.scope.run_binding
        or run_limit is None
        or run_limit.max_usd != window.effective_limit_usd
    ):
        raise ValueError("candidate_experiment_evaluation_budget_not_established")
    catalog = service.catalog_serving_source
    if current_catalog_serving_source() is not catalog:
        raise ValueError("candidate_experiment_evaluation_catalog_not_current")
    require_catalog_serving_source_unchanged(catalog)
    require_catalog_source_registry_binding(
        bridge.repo_root,
        prior_owner.profile.context_inputs.substrate_registry,
        catalog,
    )
    checked_state, checked_observation = _candidate_experiment_budget_snapshot(
        owner,
        budget_state=state,
    )
    if (
        checked_state is not state
        or exact_n5_content_bytes(checked_state) != exact_n5_content_bytes(state)
        or checked_observation != observation
        or bridge.control_store.read_acquisition_evaluation_frontier(key) != current_frontier
        or _current_candidate_experiment_reentry_action(
            bridge,
            owner.origin,
            owner.pending_phase_ref,
            owner.candidate_action_ref,
        )[3]
        != action
    ):
        raise ValueError("candidate_experiment_evaluation_owner_changed")
    return current


def _candidate_experiment_inherited_limitations(
    origin: VerifiedCandidateExperimentOrigin,
) -> tuple[str, ...]:
    """Collect prefix limitations in deterministic generation and owner order."""
    inherited: list[str] = []
    seen: set[str] = set()

    def retain(values: tuple[str, ...]) -> None:
        for value in values:
            if value not in seen:
                seen.add(value)
                inherited.append(value)

    for history in origin.candidate_terminal_history_chain:
        for basis in (history.selected_basis, history.current_basis):
            if basis is not None:
                retain(basis.limitations)
        if history.continuation is not None:
            retain(history.continuation.limitations)
    return tuple(inherited)


@dataclass(frozen=True)
class CandidateAcquisitionEvaluationReentryOwner:
    """Revalidate a candidate action before a fresh or blocked N5 frontier update.

    A different comparison uses the same complete owner replay as retention.
    An unestablished comparison is accepted only for an empty candidate frontier;
    it permits a separately authorized fresh attempt, never reuse of a prior N5.
    """

    bridge: AcquisitionWorldGrowthBridge
    closure: VerifiedAcquisitionRouteClosure
    candidate_action_ref: ArtifactRef
    candidate_world_intent_ref: ArtifactRef
    current_basis_ref: ArtifactRef
    decision_ref: ArtifactRef
    prior: ResolvedAcquisitionEvaluation | None
    prepared_n5_configuration: PreparedJointSimulationConfiguration

    def revalidate(self) -> CandidateAcquisitionEvaluationBasis:
        """Reopen the selected action and the exact fresh-execution decision."""
        from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
        from polisyos.runtime.http.services.control_plane_store import (
            AcquisitionEvaluationFrontierKey,
        )
        from polisyos.runtime.quality.candidate_source_basis import (
            _live_candidate_source_predecessors,
            prepare_live_candidate_source_basis_values,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import (
            PreparedJointSimulationConfiguration,
        )
        from polisyos.runtime.quality.substrate_registry import (
            current_catalog_serving_source,
            require_catalog_serving_source_unchanged,
            require_catalog_source_registry_binding,
        )

        bridge = self.bridge
        service = bridge._source_control_service
        if (
            type(bridge) is not AcquisitionWorldGrowthBridge
            or type(service) is not ControlPlaneService
            or service._artifact_store is not bridge.artifact_store
            or service._control_store is not bridge.control_store
            or type(self.prepared_n5_configuration) is not PreparedJointSimulationConfiguration
        ):
            raise ValueError("candidate_evaluation_reentry_owner_not_composed")
        decision = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=self.decision_ref,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        if type(decision) is not CandidateAcquisitionEvaluationDecision:
            raise ValueError("candidate_evaluation_reentry_decision_untyped")
        if decision.comparison_result == "different":
            if type(self.prior) is not ResolvedAcquisitionEvaluation:
                raise ValueError("candidate_evaluation_reentry_prior_not_established")
            return CandidateAcquisitionEvaluationCurrentOwner(
                bridge=bridge,
                closure=self.closure,
                candidate_action_ref=self.candidate_action_ref,
                candidate_world_intent_ref=self.candidate_world_intent_ref,
                current_basis_ref=self.current_basis_ref,
                decision_ref=self.decision_ref,
                prior=self.prior,
                prepared_n5_configuration=self.prepared_n5_configuration,
            )._revalidate_comparison("different")
        if (
            decision.comparison_result != "not_established"
            or decision.predicate_provenance != "not_established"
            or decision.prior_basis_ref is not None
            or decision.prior_evaluation is not None
            or decision.expected_frontier_revision != 0
            or decision.expected_frontier_ref is not None
            or self.closure.candidate_terminal_history
        ):
            raise ValueError("candidate_evaluation_reentry_unknown_not_established")

        action = bridge._require_selected_candidate_action(
            closure=self.closure, candidate_action_ref=self.candidate_action_ref
        )
        selected = bridge.candidate_source_selection(self.closure)
        window = bridge._resolve_candidate_source_budget_window(
            closure=self.closure, action_phase_ref=action.action_phase_ref
        )
        if (
            selected is None
            or action.selection != selected
            or window.window_id != action.candidate_budget_window_id
            or window.record_digest != action.candidate_budget_window_digest
        ):
            raise ValueError("candidate_evaluation_reentry_action_changed")
        # The observer is the same canonical ledger owner used by the retained
        # path. No detached state here is a per-call reservation.
        from polisyos.scientist.orchestration.engine import (
            BudgetState,
            ProducerBudgetObservation,
            ProducerBudgetObserver,
        )

        state = BudgetState.model_validate(
            {"limits": {"run": {"key": "run", "max_usd": window.effective_limit_usd}}}
        )
        observer = bridge.candidate_source_reentry_preflight(
            closure=self.closure, budget_state=state, reentry_budget_scope=window.scope
        )
        if type(observer) is not ProducerBudgetObserver:
            raise ValueError("candidate_evaluation_budget_owner_not_established")
        ProducerBudgetObserver.require_bound_state(observer, state)
        before = ProducerBudgetObserver.observe(observer)
        state_before = exact_n5_content_bytes(state)
        if type(before) is not ProducerBudgetObservation:
            raise ValueError("candidate_evaluation_budget_observation_untyped")

        profile, declaration, _ = bridge._candidate_source_prior_owner(closure=self.closure)
        intent_ref, intent = bridge._candidate_world_materialization_intent(
            closure=self.closure,
            candidate_action_ref=self.candidate_action_ref,
            configured_profile=profile,
            original_model_declaration=declaration,
            create=False,
        )
        catalog = service.catalog_serving_source
        if current_catalog_serving_source() is not catalog:
            raise ValueError("candidate_evaluation_catalog_scope_not_established")
        require_catalog_serving_source_unchanged(catalog)
        require_catalog_source_registry_binding(
            bridge.repo_root, profile.context_inputs.substrate_registry, catalog
        )
        actual_prior = (
            resolve_selected_acquisition_evaluation(bridge=bridge, closure=self.closure)
            if self.closure.source_cycle.simulation.status == "joint_simulated"
            else None
        )
        if actual_prior is None:
            # This owner only accepts the existing typed first-N5 refusal; a
            # generic missing or blocked input cannot prove a first source.
            bridge._candidate_source_first_prior(closure=self.closure)
        if not _candidate_model_values_same(actual_prior, self.prior):
            raise ValueError("candidate_evaluation_reentry_prior_changed")
        current = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=self.current_basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        prepared = prepare_live_candidate_source_basis_values(
            bridge=bridge,
            closure=self.closure,
            candidate_action_ref=self.candidate_action_ref,
            transaction_time=intent.transaction_time,
        )
        if (
            type(current) is not CandidateAcquisitionEvaluationBasis
            or current.basis_role != "prospective"
            or prepared.predicate_provenance != "recomputed"
            or prepared.reason_codes
            or prepared.inputs is None
            or not _candidate_model_values_same(prepared.inputs, current.preparation_inputs)
            or not _candidate_ref_same(intent_ref, self.candidate_world_intent_ref)
            or not _candidate_ref_same(decision.current_basis_ref, self.current_basis_ref)
            or not _candidate_ref_same(decision.candidate_action_ref, self.candidate_action_ref)
            or not _candidate_ref_same(decision.candidate_world_intent_ref, intent_ref)
            or not _candidate_ref_same(decision.candidate_source_ref, action.candidate_source_ref)
            or not _candidate_ref_same(current.candidate_action_ref, self.candidate_action_ref)
            or not _candidate_ref_same(current.candidate_world_intent_ref, intent_ref)
            or not _candidate_ref_same(current.candidate_source_ref, action.candidate_source_ref)
            or current.prepared_n5_configuration != self.prepared_n5_configuration
            or not set(action.limitations).issubset(current.limitations)
        ):
            raise ValueError("candidate_evaluation_reentry_basis_binding_mismatch")
        expected_scope = (
            self.closure.tenant_id,
            self.closure.cell_id,
            self.closure.run_id,
            self.closure.source_job_id,
            self.closure.route_id,
            action.action_job_id,
            action.action_generation,
            self.closure.design_problem_ref,
            self.closure.design_problem_basis_ref,
            self.closure.source_cycle.selected_candidate_ref,
            self.closure.source_cycle.selected_candidate_content_hash,
        )
        for record in (current, decision):
            if (
                record.tenant_id,
                record.cell_id,
                record.run_id,
                record.source_job_id,
                record.route_id,
                record.action_job_id,
                record.action_generation,
                record.design_problem_ref,
                record.design_problem_basis_ref,
                record.candidate_id,
                record.source_candidate_content_hash,
            ) != expected_scope:
                raise ValueError("candidate_evaluation_reentry_scope_mismatch")
        if decision.compiled_ref != self.closure.compiled_ref:
            raise ValueError("candidate_evaluation_reentry_compiled_mismatch")
        key = AcquisitionEvaluationFrontierKey(
            tenant_id=self.closure.tenant_id,
            cell_id=self.closure.cell_id,
            source_job_id=self.closure.source_job_id,
            design_problem_ref=self.closure.design_problem_ref,
            candidate_id=self.closure.source_cycle.selected_candidate_ref,
        )
        if bridge.control_store.read_acquisition_evaluation_frontier(key) is not None:
            raise ValueError("candidate_evaluation_reentry_frontier_changed")
        predecessors = _live_candidate_source_predecessors(bridge=bridge, closure=self.closure)
        values, reasons = recompute_candidate_acquisition_basis_values(
            artifact_store=bridge.artifact_store,
            problem=self.closure.design_problem_basis,
            preparation_inputs=current.preparation_inputs,
            predecessors=predecessors,
            prior=actual_prior,
            prepared_n5_configuration=self.prepared_n5_configuration,
            fresh_limit_usd=window.fresh_limit_usd,
            global_limit_usd=window.global_limit_usd,
        )
        if (
            current.predicate_provenance != ("not_established" if reasons else "recomputed")
            or current.reason_codes != reasons
            or exact_n5_content_bytes(values) != bytes.fromhex(current.effective_native_values_hex)
            or decision.reason_codes
            != tuple(dict.fromkeys(("candidate_evaluation_prior_basis_not_established", *reasons)))
            or bridge._require_selected_candidate_action(
                closure=self.closure, candidate_action_ref=self.candidate_action_ref
            )
            != action
            or bridge.control_store.read_acquisition_evaluation_frontier(key) is not None
        ):
            raise ValueError("candidate_evaluation_reentry_unknown_replay_mismatch")
        ProducerBudgetObserver.require_bound_state(observer, state)
        after = ProducerBudgetObserver.observe(observer)
        if exact_n5_content_bytes(state) != state_before or after != before:
            raise ValueError("candidate_evaluation_budget_observation_changed")
        require_catalog_serving_source_unchanged(catalog)
        require_catalog_source_registry_binding(
            bridge.repo_root, profile.context_inputs.substrate_registry, catalog
        )
        return current


def _require_candidate_evaluation_record_scope(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
    record: CandidateAcquisitionEvaluationBasis
    | CandidateAcquisitionEvaluationDecision
    | CandidateAcquisitionRetainedContinuation
    | CandidateRetainedPortCapture,
) -> object:
    """Join a strict candidate record to the actual current action and intent."""
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )

    if type(record) not in {
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationDecision,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    }:
        raise TypeError("candidate_evaluation_selected_record_untyped")
    action = bridge._require_selected_candidate_action(
        closure=closure, candidate_action_ref=record.candidate_action_ref
    )
    selection = bridge.candidate_source_selection(closure)
    if (
        selection is None
        or (
            record.tenant_id,
            record.cell_id,
            record.run_id,
            record.source_job_id,
            record.action_job_id,
            record.action_generation,
            record.route_id,
            record.design_problem_ref,
            record.design_problem_basis_ref,
            record.candidate_id,
        )
        != (
            closure.tenant_id,
            closure.cell_id,
            closure.run_id,
            closure.source_job_id,
            action.action_job_id,
            action.action_generation,
            closure.route_id,
            closure.design_problem_ref,
            closure.design_problem_basis_ref,
            closure.source_cycle.selected_candidate_ref,
        )
        or not _candidate_ref_same(record.candidate_source_ref, action.candidate_source_ref)
    ):
        raise ValueError("candidate_evaluation_selected_record_scope_mismatch")
    if type(record) in {
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationDecision,
    }:
        if (
            record.source_candidate_content_hash
            != closure.source_cycle.selected_candidate_content_hash
        ):
            raise ValueError("candidate_evaluation_selected_candidate_mismatch")
    elif record.retained_evaluation.candidate_content_hash != (
        closure.source_cycle.selected_candidate_content_hash
    ):
        raise ValueError("candidate_evaluation_selected_candidate_mismatch")
    if (
        type(record)
        in {
            CandidateAcquisitionEvaluationDecision,
            CandidateAcquisitionRetainedContinuation,
            CandidateRetainedPortCapture,
        }
        and record.compiled_ref != closure.compiled_ref
    ):
        raise ValueError("candidate_evaluation_selected_compiled_mismatch")
    profile, declaration, _ = bridge._candidate_source_prior_owner(closure=closure)
    intent_ref, _ = bridge._candidate_world_materialization_intent(
        closure=closure,
        candidate_action_ref=record.candidate_action_ref,
        configured_profile=profile,
        original_model_declaration=declaration,
        create=False,
    )
    if not _candidate_ref_same(record.candidate_world_intent_ref, intent_ref):
        raise ValueError("candidate_evaluation_selected_record_intent_mismatch")
    return action


def _candidate_evaluation_artifact_for_recovery(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure | None = None,
    origin: VerifiedCandidateExperimentOrigin | None = None,
    pending_phase_ref: str | None = None,
    candidate_action_ref: ArtifactRef,
    role: Literal[
        "decision",
        "prospective_basis",
        "outcome_basis",
        "retained_continuation",
        "retained_port_capture",
    ],
) -> tuple[ArtifactRef, object] | None:
    """Discover one saved selected record without redoing its producer work.

    The returned record is only a recovery candidate. The caller must replay
    its complete semantic inputs and selected owners before repairing a pointer
    or executing anything; the saved timestamp is preserved, not regenerated.
    """
    from polisyos.runtime.quality.acquisition_evaluation import (
        PRODUCER,
        _candidate_evaluation_event_id,
        _candidate_evaluation_role_event_id,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _current_candidate_experiment_reentry_action,
    )

    if (closure is None) == (origin is None):
        raise ValueError("candidate_evaluation_recovery_owner_not_unique")
    if closure is not None:
        action: object = bridge._require_selected_candidate_action(
            closure=closure, candidate_action_ref=candidate_action_ref
        )
        selection = bridge.candidate_source_selection(closure)
    else:
        if pending_phase_ref is None or origin is None:
            raise ValueError("candidate_experiment_recovery_owner_incomplete")
        selection, _phase, _admission, action = _current_candidate_experiment_reentry_action(
            bridge,
            origin,
            pending_phase_ref,
            candidate_action_ref,
        )
    if selection is None:
        raise ValueError("candidate_evaluation_selected_route_missing")
    record_type = {
        "decision": CandidateAcquisitionEvaluationDecision,
        "prospective_basis": CandidateAcquisitionEvaluationBasis,
        "outcome_basis": CandidateAcquisitionEvaluationBasis,
        "retained_continuation": CandidateAcquisitionRetainedContinuation,
        "retained_port_capture": CandidateRetainedPortCapture,
    }.get(role)
    if record_type is None:
        raise ValueError("candidate_evaluation_recovery_role_invalid")
    event_id = _candidate_evaluation_role_event_id(candidate_action_ref, role)
    overlay_path, _ = bridge._paths(selection, create=False)
    pointer = overlay_path.parent / (event_id + ".selected.json")
    action_digest = event_id.rsplit("_", 1)[-1]
    operation = overlay_path.parent / ("candidate-evaluation-" + action_digest + ".lock-target")

    def read_selected(ref: ArtifactRef) -> object:
        value = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=ref,
            record_type=record_type,
        )
        if (
            type(value) is not record_type
            or not _candidate_ref_same(value.candidate_action_ref, candidate_action_ref)
            or _candidate_evaluation_event_id(value) != event_id
            or (
                _require_candidate_evaluation_record_scope(
                    bridge=bridge, closure=closure, record=value
                )
                if closure is not None
                else _require_candidate_experiment_evaluation_record_scope(
                    bridge=bridge,
                    origin=origin,
                    pending_phase_ref=pending_phase_ref,
                    candidate_action_ref=candidate_action_ref,
                    record=value,
                )
            )
            != action
        ):
            raise ValueError("candidate_evaluation_recovery_record_mismatch")
        return value

    with data_forge_read_api.catalog.acquisition_overlay_admission_fence(operation):
        events = bridge.event_log.list_events(event_id=event_id, limit=2)
        if len(events) > 1:
            raise ValueError("candidate_evaluation_event_ambiguous")
        if not events:
            if pointer.exists():
                raise ValueError("candidate_evaluation_event_missing")
            return None
        refs = tuple(events[0].event.artifact_refs)
        if len(refs) != 1:
            raise ValueError("candidate_evaluation_event_unresolved")
        if pointer.exists():
            selected = bridge._read_candidate_world_pointer(
                pointer,
                candidate_action_ref=candidate_action_ref,
                expected_kind=record_type.ARTIFACT_KIND,
            )
            if str(selected.artifact_id) != refs[0]:
                raise ValueError("candidate_evaluation_pointer_event_mismatch")
            value = read_selected(selected)
        else:
            selected, value = bridge._recover_unique_candidate_owner_view(
                artifact_ref=refs[0],
                kind=record_type.ARTIFACT_KIND,
                schema=record_type.ARTIFACT_SCHEMA_NAME,
                version="1.0",
                record_type=record_type,
                verify=read_selected,
                producer_component=PRODUCER,
            )
        current_action = (
            bridge._require_selected_candidate_action(
                closure=closure, candidate_action_ref=candidate_action_ref
            )
            if closure is not None
            else _current_candidate_experiment_reentry_action(
                bridge,
                origin,
                pending_phase_ref,
                candidate_action_ref,
            )[3]
        )
        if current_action != action:
            raise ValueError("candidate_evaluation_selected_action_changed")
        return selected, value


def _select_candidate_evaluation_artifact(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure | None = None,
    origin: VerifiedCandidateExperimentOrigin | None = None,
    pending_phase_ref: str | None = None,
    record: CandidateAcquisitionEvaluationBasis
    | CandidateAcquisitionEvaluationDecision
    | CandidateAcquisitionRetainedContinuation
    | CandidateRetainedPortCapture,
) -> ArtifactRef:
    """Select one owner-replayed candidate record across the event/pointer window.

    On retry, discover the saved record first and independently replay its inputs.
    This operation binds that exact record to a selected pointer; it never runs
    N5 or grants a terminal commit.
    """
    from polisyos.runtime.quality.acquisition_evaluation import (
        PRODUCER,
        _candidate_evaluation_event_id,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _candidate_experiment_source_selection,
        _current_candidate_experiment_reentry_action,
    )

    if (closure is None) == (origin is None):
        raise ValueError("candidate_evaluation_selected_owner_not_unique")
    if closure is not None:
        action = _require_candidate_evaluation_record_scope(
            bridge=bridge, closure=closure, record=record
        )
        selection = bridge.candidate_source_selection(closure)
    else:
        if pending_phase_ref is None or origin is None:
            raise ValueError("candidate_experiment_selected_owner_incomplete")
        action = _require_candidate_experiment_evaluation_record_scope(
            bridge=bridge,
            origin=origin,
            pending_phase_ref=pending_phase_ref,
            candidate_action_ref=record.candidate_action_ref,
            record=record,
        )
        selection = _candidate_experiment_source_selection(bridge, origin)
    if selection is None:
        raise ValueError("candidate_evaluation_selected_route_missing")
    event_id = _candidate_evaluation_event_id(record)
    overlay_path, _ = bridge._paths(selection, create=False)
    pointer = overlay_path.parent / (event_id + ".selected.json")
    action_digest = event_id.rsplit("_", 1)[-1]
    operation = overlay_path.parent / ("candidate-evaluation-" + action_digest + ".lock-target")

    def read_selected(ref: ArtifactRef) -> object:
        value = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=ref,
            record_type=type(record),
        )
        if type(value) is not type(record) or exact_n5_content_bytes(value) != (
            exact_n5_content_bytes(record)
        ):
            raise ValueError("candidate_evaluation_selected_record_changed")
        return value

    with data_forge_read_api.catalog.acquisition_overlay_admission_fence(operation):
        events = bridge.event_log.list_events(event_id=event_id, limit=2)
        pointer_write_required = False
        if len(events) > 1:
            raise ValueError("candidate_evaluation_event_ambiguous")
        if events:
            refs = tuple(events[0].event.artifact_refs)
            if len(refs) != 1:
                raise ValueError("candidate_evaluation_event_unresolved")
            if pointer.exists():
                selected = bridge._read_candidate_world_pointer(
                    pointer,
                    candidate_action_ref=record.candidate_action_ref,
                    expected_kind=record.ARTIFACT_KIND,
                )
                if str(selected.artifact_id) != refs[0]:
                    raise ValueError("candidate_evaluation_pointer_event_mismatch")
                read_selected(selected)
            else:
                selected, _ = bridge._recover_unique_candidate_owner_view(
                    artifact_ref=refs[0],
                    kind=record.ARTIFACT_KIND,
                    schema=record.ARTIFACT_SCHEMA_NAME,
                    version="1.0",
                    record_type=type(record),
                    verify=read_selected,
                    producer_component=PRODUCER,
                )
                pointer_write_required = True
        else:
            if pointer.exists():
                raise ValueError("candidate_evaluation_event_missing")
            selected = persist_acquisition_evaluation_artifact(
                store=bridge.artifact_store, event_log=bridge.event_log, record=record
            )
            pointer_write_required = True
        if pointer_write_required:
            current_action = (
                bridge._require_selected_candidate_action(
                    closure=closure, candidate_action_ref=record.candidate_action_ref
                )
                if closure is not None
                else _current_candidate_experiment_reentry_action(
                    bridge,
                    origin,
                    pending_phase_ref,
                    record.candidate_action_ref,
                )[3]
            )
            if current_action != action:
                raise ValueError("candidate_evaluation_selected_action_changed")
            bridge._write_candidate_world_pointer(
                pointer, candidate_action_ref=record.candidate_action_ref, selected_ref=selected
            )
        current_action = (
            bridge._require_selected_candidate_action(
                closure=closure, candidate_action_ref=record.candidate_action_ref
            )
            if closure is not None
            else _current_candidate_experiment_reentry_action(
                bridge,
                origin,
                pending_phase_ref,
                record.candidate_action_ref,
            )[3]
        )
        if current_action != action:
            raise ValueError("candidate_evaluation_selected_action_changed")
        read_selected(selected)
        return selected


@dataclass(frozen=True)
class _TerminalScope:
    owner: AcquisitionEvaluationCurrentOwner
    decision_ref: ArtifactRef
    decision: AcquisitionEvaluationDecision
    selected_basis_ref: ArtifactRef
    selected_evaluation: AcquisitionSelectedEvaluation | None
    selected_witness_ref: ArtifactRef
    selected_witness_content_hash: str


_TERMINAL_SCOPE: ContextVar[_TerminalScope | None] = ContextVar(
    "polisyos_acquisition_evaluation_terminal_scope",
    default=None,
)


@contextmanager
def _terminal_scope(scope: _TerminalScope) -> Iterator[None]:
    # The caller already holds the real native fence. This scope carries the
    # real bound owner to the SQL sink; it is never a supplied permit boolean.
    token = _TERMINAL_SCOPE.set(scope)
    try:
        yield
    finally:
        _TERMINAL_SCOPE.reset(token)


def acquisition_terminal_frontier_cas(
    terminal: AcquisitionRouteLoopReceiptV2,
    *,
    artifact_store: object,
    control_store: object,
) -> AcquisitionEvaluationFrontierCAS:
    """Reconcile the actual fenced owner before the sink's conditional SQL commit."""
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionEvaluationFrontierCAS,
        AcquisitionEvaluationFrontierKey,
        AcquisitionEvaluationFrontierValue,
    )

    scope = _TERMINAL_SCOPE.get()
    if (
        scope is None
        or type(scope.owner) is not AcquisitionEvaluationCurrentOwner
        or scope.owner.bridge.artifact_store is not artifact_store
        or scope.owner.bridge.control_store is not control_store
        or terminal.evaluation_decision_ref != scope.decision_ref
        or terminal.selected_basis_ref != scope.selected_basis_ref
        or terminal.selected_evaluation != scope.selected_evaluation
        or terminal.selected_evaluation_witness_ref != scope.selected_witness_ref
    ):
        raise ValueError("acquisition_evaluation_native_terminal_fence_not_established")
    scope.owner.revalidate()
    decision = scope.decision
    for name in (
        "tenant_id",
        "cell_id",
        "run_id",
        "source_job_id",
        "route_id",
        "action_generation",
        "compiled_ref",
    ):
        if getattr(terminal, name) != getattr(decision, name):
            raise ValueError("acquisition_evaluation_terminal_decision_scope_mismatch")
    if terminal.job_id != decision.action_job_id:
        raise ValueError("acquisition_evaluation_terminal_job_mismatch")
    basis = read_acquisition_evaluation_artifact(
        store=scope.owner.bridge.artifact_store,
        event_log=scope.owner.bridge.event_log,
        ref=scope.selected_basis_ref,
        record_type=AcquisitionEvaluationBasis,
    )
    if type(basis) is not AcquisitionEvaluationBasis:
        raise ValueError("acquisition_evaluation_terminal_basis_unverified")
    key = AcquisitionEvaluationFrontierKey(
        tenant_id=decision.tenant_id,
        cell_id=decision.cell_id,
        source_job_id=decision.source_job_id,
        design_problem_ref=decision.design_problem_ref,
        candidate_id=decision.candidate_id,
    )
    if terminal.terminal_outcome == "source_admitted_evaluation_retained":
        if decision.comparison_result != "equivalent" or terminal.current_continuation_ref is None:
            raise ValueError("acquisition_retained_terminal_without_equivalent_decision")
        from polisyos.runtime.quality.acquisition_retained_continuation import (
            read_acquisition_retained_continuation,
        )

        read_acquisition_retained_continuation(
            store=scope.owner.bridge.artifact_store,
            event_log=scope.owner.bridge.event_log,
            ref=terminal.current_continuation_ref,
            decision=decision,
            terminal=terminal,
        )
        replacement = None
    else:
        replacement = AcquisitionEvaluationFrontierValue(
            selected_evaluation_witness_ref=str(scope.selected_witness_ref.artifact_id),
            selected_evaluation_content_hash=scope.selected_witness_content_hash,
            basis_ref=str(scope.selected_basis_ref.artifact_id),
            basis_content_hash=basis.content_hash,
            decision_ref=str(scope.decision_ref.artifact_id),
        )
    return AcquisitionEvaluationFrontierCAS(
        key=key,
        expected_revision=decision.expected_frontier_revision,
        expected_frontier_ref=decision.expected_frontier_ref,
        replacement=replacement,
    )


@dataclass(frozen=True)
class _CandidateTerminalScope:
    """Concrete live owner and terminal held by the candidate dispatch fence."""

    owner: CandidateAcquisitionEvaluationCurrentOwner | CandidateAcquisitionEvaluationReentryOwner
    terminal: AcquisitionCandidateRouteLoopReceipt


_CANDIDATE_TERMINAL_SCOPE: ContextVar[_CandidateTerminalScope | None] = ContextVar(
    "polisyos_candidate_acquisition_evaluation_terminal_scope",
    default=None,
)


@dataclass(frozen=True)
class CandidateExperimentReentryOwner:
    """Live current owner pinned to one prepared experiment terminal."""

    bridge: AcquisitionWorldGrowthBridge
    origin: VerifiedCandidateExperimentOrigin
    terminal: AcquisitionCandidateExperimentTerminalReceipt
    predecessor_head: AcquisitionActionHeadRecord
    candidate_action_ref: ArtifactRef
    action_phase_ref: str
    evaluation_owner: CandidateExperimentEvaluationCurrentOwner
    budget_state: BudgetState
    reentry_budget_scope: BudgetLedgerReentryBudgetScope
    budget_window: BudgetLedgerReentryBudgetWindow


@dataclass(frozen=True)
class _CandidateExperimentReentryScope:
    owner: CandidateExperimentReentryOwner
    terminal: AcquisitionCandidateExperimentTerminalReceipt
    predecessor_head: AcquisitionActionHeadRecord


_CANDIDATE_EXPERIMENT_REENTRY_SCOPE: ContextVar[_CandidateExperimentReentryScope | None] = (
    ContextVar("polisyos_candidate_experiment_reentry_scope", default=None)
)


def prepare_candidate_experiment_reentry_owner(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    terminal: AcquisitionCandidateExperimentTerminalReceipt,
    predecessor_head: AcquisitionActionHeadRecord,
    candidate_action_ref: ArtifactRef,
    action_phase_ref: str,
    evaluation_owner: CandidateExperimentEvaluationCurrentOwner,
    budget_state: BudgetState,
    reentry_budget_scope: BudgetLedgerReentryBudgetScope,
    budget_window: BudgetLedgerReentryBudgetWindow,
) -> CandidateExperimentReentryOwner:
    """Create the terminal owner only from the exact current pending action and lease."""
    owner = CandidateExperimentReentryOwner(
        bridge=bridge,
        origin=origin,
        terminal=terminal,
        predecessor_head=predecessor_head,
        candidate_action_ref=candidate_action_ref,
        action_phase_ref=action_phase_ref,
        evaluation_owner=evaluation_owner,
        budget_state=budget_state,
        reentry_budget_scope=reentry_budget_scope,
        budget_window=budget_window,
    )
    _revalidate_candidate_experiment_reentry_owner(owner)
    return owner


@contextmanager
def candidate_experiment_reentry_fence(
    owner: CandidateExperimentReentryOwner,
) -> Iterator[None]:
    """Bind actual source, live lease, budget window and terminal before persistence."""
    if type(owner) is not CandidateExperimentReentryOwner:
        raise TypeError("candidate_experiment_reentry_owner_untyped")
    _revalidate_candidate_experiment_reentry_owner(owner)
    scope = _CandidateExperimentReentryScope(
        owner=owner,
        terminal=owner.terminal,
        predecessor_head=owner.predecessor_head,
    )
    token = _CANDIDATE_EXPERIMENT_REENTRY_SCOPE.set(scope)
    try:
        yield
    finally:
        _CANDIDATE_EXPERIMENT_REENTRY_SCOPE.reset(token)


def _revalidate_candidate_experiment_reentry_owner(
    owner: CandidateExperimentReentryOwner,
) -> None:
    """Replay the pending action and exact terminal-specific current owner."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        read_candidate_acquisition_retained_continuation,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _current_candidate_experiment_reentry_action_context,
    )
    from polisyos.runtime.quality.candidate_source_reentry_history import (
        verify_candidate_experiment_source_reentry_history,
    )
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
    from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationResult
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationCapacityObservation,
        ProducerBudgetObservation,
        ProducerBudgetObserver,
    )

    bridge = owner.bridge
    origin = owner.origin
    service = bridge._source_control_service
    terminal = owner.terminal
    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or type(origin) is not VerifiedCandidateExperimentOrigin
        or type(service) is not ControlPlaneService
        or service._artifact_store is not bridge.artifact_store
        or service._control_store is not bridge.control_store
        or terminal.terminal_outcome
        not in {"candidate_reentry_completed", "candidate_evaluation_retained", "candidate_blocked"}
        or terminal.predecessor_receipt_ref != owner.predecessor_head.receipt_ref
        or terminal.candidate_action_ref != owner.candidate_action_ref
        or terminal.action_generation != owner.predecessor_head.action_generation
        or terminal.receipt_phase != "terminal"
        or type(owner.evaluation_owner) is not CandidateExperimentEvaluationCurrentOwner
        or owner.evaluation_owner.origin != origin
        or owner.evaluation_owner.candidate_action_ref != owner.candidate_action_ref
        or owner.evaluation_owner.pending_phase_ref != owner.predecessor_head.receipt_ref
        or owner.evaluation_owner.action_phase_ref != owner.action_phase_ref
        or not _candidate_ref_same(
            owner.evaluation_owner.decision_ref,
            terminal.blocker_ref
            if terminal.terminal_outcome == "candidate_blocked"
            else terminal.evaluation_decision_ref,
        )
    ):
        raise ValueError("candidate_experiment_reentry_owner_binding_mismatch")
    owner.evaluation_owner.revalidate()
    if service.acquisition_route_sink.get_head(terminal) != owner.predecessor_head:
        raise ValueError("candidate_experiment_reentry_predecessor_changed")
    try:
        reentry_context = _current_candidate_experiment_reentry_action_context(
            bridge,
            origin,
            owner.predecessor_head.receipt_ref,
            candidate_action_ref=owner.candidate_action_ref,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_reentry_live_owner_not_current") from exc
    selection = reentry_context.selection
    phase = reentry_context.phase
    admission = reentry_context.admission
    action = reentry_context.action
    if (
        phase.receipt_phase != "candidate_input_reentry_pending"
        or action.action_phase_ref != owner.action_phase_ref
        or action.action_job_id != terminal.job_id
        or action.action_generation != terminal.action_generation
        or action.selection != selection
        or admission.job.job_id != terminal.job_id
        or admission.job.state != "running"
        or (terminal.tenant_id, terminal.cell_id, terminal.run_id, terminal.source_job_id)
        != (origin.tenant_id, origin.cell_id, origin.run_id, origin.source_job_id)
        or terminal.route_id != origin.route_id
        or terminal.compiled_ref != origin.policy_scope.compiled_ref
    ):
        raise ValueError("candidate_experiment_reentry_live_owner_changed")
    window = reentry_context.budget_window
    if window != owner.budget_window or window.scope != owner.reentry_budget_scope:
        raise ValueError("candidate_experiment_reentry_budget_window_changed")
    if terminal.terminal_outcome == "candidate_blocked":
        decision = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=terminal.blocker_ref,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        if (
            type(decision) is not CandidateAcquisitionEvaluationDecision
            or owner.evaluation_owner.comparison != "not_established"
            or decision.comparison_result != "not_established"
            or decision.predicate_provenance != "not_established"
            or terminal.blocker_reason != "candidate_experiment_input_change_not_established"
            or "candidate_experiment_input_change_not_established" not in decision.reason_codes
        ):
            raise ValueError("candidate_experiment_blocker_owner_not_established")
        owner.evaluation_owner.current_budget_snapshot(budget_state=owner.budget_state)
        return
    if terminal.terminal_outcome == "candidate_evaluation_retained":
        prior = owner.evaluation_owner.prior
        decision = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=owner.evaluation_owner.decision_ref,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        if (
            type(decision) is not CandidateAcquisitionEvaluationDecision
            or owner.evaluation_owner.comparison != "equivalent"
            or owner.origin.candidate_terminal_history_chain == ()
            or terminal.candidate_reentry_ref is not None
            or terminal.current_continuation_ref is None
            or terminal.selected_evaluation is None
            or prior is None
            or terminal.selected_basis_ref is None
            or not _candidate_ref_same(terminal.selected_basis_ref, decision.prior_basis_ref)
        ):
            raise ValueError("candidate_experiment_retained_terminal_binding_mismatch")
        if (
            decision.comparison_result != "equivalent"
            or decision.predicate_provenance != "recomputed"
            or not _candidate_model_values_same(
                terminal.selected_evaluation,
                prior.selected.model_copy(update={"basis_ref": terminal.selected_basis_ref}),
            )
            or not _candidate_model_values_same(
                terminal.selected_evaluation, decision.prior_evaluation
            )
            or not _candidate_ref_same(
                terminal.selected_evaluation_witness_ref,
                prior.selected.n5_execution_ref,
            )
        ):
            raise ValueError("candidate_experiment_retained_terminal_evaluation_mismatch")
        continuation, actual = read_candidate_acquisition_retained_continuation(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            control_store=bridge.control_store,
            ref=terminal.current_continuation_ref,
            decision=decision,
            terminal=terminal,
            prior_experiment_origin=origin,
        )
        if (
            not _candidate_model_values_same(actual, prior)
            or not _candidate_ref_same(
                continuation.current_basis_ref, owner.evaluation_owner.current_basis_ref
            )
            or not _candidate_ref_same(
                continuation.evaluation_decision_ref, owner.evaluation_owner.decision_ref
            )
        ):
            raise ValueError("candidate_experiment_retained_continuation_not_selected")
        state, observation = owner.evaluation_owner.current_budget_snapshot(
            budget_state=owner.budget_state
        )
        run_limit = state.limits.get("run")
        if (
            state is not owner.budget_state
            or run_limit is None
            or run_limit.max_usd != window.effective_limit_usd
            or observation.run_binding != window.scope.run_binding
            or observation.predicate_basis != "independently_reconciled"
            or observation.remaining_usd < 0
        ):
            raise ValueError("candidate_experiment_retained_budget_not_established")
        owner.evaluation_owner.revalidate()
        return
    if (
        terminal.candidate_reentry_ref is None
        or terminal.current_continuation_ref is not None
        or owner.evaluation_owner.comparison == "equivalent"
        or (
            owner.evaluation_owner.comparison == "different"
            and not owner.origin.candidate_terminal_history_chain
        )
    ):
        raise ValueError("candidate_experiment_reentry_comparison_not_established")
    try:
        reentry = verify_candidate_experiment_source_reentry_history(
            bridge=bridge,
            origin=origin,
            receipt_ref=terminal.candidate_reentry_ref,
            expected_selected_action_ref=owner.candidate_action_ref,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_reentry_receipt_not_selected") from exc
    if (
        reentry.candidate_action_ref != owner.candidate_action_ref
        or reentry.source_job_id != origin.source_job_id
        or reentry.run_id != origin.run_id
        or reentry.route_id != origin.route_id
        or reentry.action_generation != terminal.action_generation
        or reentry.action_job_id != terminal.job_id
        or reentry.n5_result_ref is None
        or not reentry.continued_generation_run.cycles
        or reentry.new_cycle != reentry.continued_generation_run.cycles[-1]
    ):
        raise ValueError("candidate_experiment_reentry_receipt_binding_mismatch")
    try:
        observer = service.build_candidate_experiment_reentry_budget_observer(
            origin=origin,
            candidate_action_ref=owner.candidate_action_ref,
            budget_state=owner.budget_state,
            reentry_budget_scope=owner.reentry_budget_scope,
        )
        if type(observer) is not ProducerBudgetObserver:
            raise ValueError("candidate_experiment_reentry_budget_owner_untyped")
        ProducerBudgetObserver.require_bound_state(observer, owner.budget_state)
        quota = bridge._candidate_experiment_standard_quota_policy(
            owner.evaluation_owner.prior_owner
        )
        # Terminal publication reads the existing durable quota. It cannot
        # repair selection or admit more work after the physical invocation.
        selected_quota = ProducerBudgetObserver.bind_existing_invocation_policy_from_selected_owner(
            observer, quota, purpose="standard"
        )
        observation = ProducerBudgetObserver.observe(observer)
        capacity = ProducerBudgetObserver.observe_standard_invocation_capacity(observer)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_reentry_budget_not_reconciled") from exc
    if (
        type(observation) is not ProducerBudgetObservation
        or type(capacity) is not BudgetInvocationCapacityObservation
    ):
        raise ValueError("candidate_experiment_reentry_budget_owner_untyped")
    simulation = reentry.new_cycle.simulation
    if (
        simulation.simulation_result_ref != reentry.n5_result_ref
        or simulation.simulation_ref is None
    ):
        raise ValueError("candidate_experiment_reentry_n5_result_not_in_run")
    current_result = load_joint_simulation_result(
        reentry.n5_result_ref,
        store=bridge.artifact_store,
        expected_world_model_record_content_hash=simulation.k_world_ref_after,
        expected_receipt_payload_hash=simulation.simulation_ref,
    )
    if type(current_result) is not JointSimulationResult:
        raise ValueError("candidate_experiment_reentry_n5_result_untyped")
    current_event_ids = tuple(item.event_id for item in current_result.physical_work_observations)
    expected_event_ids = tuple(
        event_id
        for trajectory in current_result.trajectories
        for event_id in trajectory.diagnostics.get("physical_work_event_ids", ())
    )
    current_event_capture_valid = (
        current_result.diagnostics.get("physical_work_capture_status") == "observed"
        and bool(current_event_ids)
        and len(current_event_ids) == len(set(current_event_ids))
        # Individual and joint trajectories can reference the same physical run.
        and current_event_ids
        and set(current_event_ids) == set(expected_event_ids)
    )
    current_operations = current_result.physical_work_observations
    current_operation_ids = tuple(
        item.invocation_quota_operation_id
        for item in current_operations
        if item.invocation_quota_operation_id is not None
    )
    witness_ids = tuple(item[0] for item in capacity.terminal_witnesses)
    current_operation_bindings_valid = (
        bool(current_operations)
        and len(current_operation_ids) == len(current_operations)
        and len(current_operation_ids) == len(set(current_operation_ids))
        and all(
            item.invocation_quota_profile_digest == capacity.profile_digest
            and item.invocation_quota_purpose == "standard"
            and item.invocation_quota_status == item.status
            and item.status in {"completed", "failed"}
            for item in current_operations
        )
    )
    exhaustion_replayed = False
    if capacity.status == "exhausted":
        witness = capacity.exhaustion_witness
        try:
            from polisyos.scientist.orchestration.engine import BudgetInvocationExhaustionWitness

            exhaustion_replayed = (
                type(witness) is BudgetInvocationExhaustionWitness
                and ProducerBudgetObserver.verify_standard_invocation_exhaustion(observer, witness)
                is True
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            exhaustion_replayed = False
    conservation_cause = None
    if (
        observation.predicate_basis != "independently_reconciled"
        or observation.remaining_usd < 0
        or observation.run_binding != owner.reentry_budget_scope.run_binding
        or capacity.run_binding != owner.reentry_budget_scope.run_binding
        or observation.settlement_owner != capacity.settlement_owner
        or capacity.predicate_basis != "independently_reconciled"
        or capacity.status not in {"available", "exhausted"}
        or capacity.profile_digest != selected_quota.profile_digest
        or capacity.standard_limit_units is None
        or capacity.standard_remaining_units is None
        or (capacity.status == "available" and capacity.standard_remaining_units <= 0)
        or (capacity.status == "exhausted" and capacity.standard_remaining_units != 0)
    ):
        conservation_cause = "candidate_experiment_reentry_budget_capacity_not_reconciled"
    elif not current_event_capture_valid:
        conservation_cause = "candidate_experiment_reentry_physical_events_not_reconciled"
    elif not current_operation_bindings_valid or not set(current_operation_ids).issubset(
        witness_ids
    ):
        conservation_cause = "candidate_experiment_reentry_invocation_witnesses_not_reconciled"
    elif capacity.status == "exhausted" and not exhaustion_replayed:
        conservation_cause = "candidate_experiment_reentry_quota_exhaustion_not_reconciled"
    if conservation_cause is not None:
        raise ValueError(
            "candidate_experiment_reentry_budget_conservation_not_established"
        ) from ValueError(conservation_cause)
    owner.evaluation_owner.revalidate()


def require_candidate_experiment_reentry_fence(
    terminal: AcquisitionCandidateExperimentTerminalReceipt,
    *,
    predecessor_head: AcquisitionActionHeadRecord,
) -> None:
    """Require the exact live owner before the sink writes terminal bytes or event."""
    scope = _CANDIDATE_EXPERIMENT_REENTRY_SCOPE.get()
    if (
        type(terminal) is not AcquisitionCandidateExperimentTerminalReceipt
        or type(predecessor_head) is not AcquisitionActionHeadRecord
        or type(scope) is not _CandidateExperimentReentryScope
        or scope.terminal != terminal
        or scope.predecessor_head != predecessor_head
        or scope.owner.terminal != terminal
        or scope.owner.predecessor_head != predecessor_head
    ):
        raise ValueError("candidate_experiment_reentry_fence_not_established")
    _revalidate_candidate_experiment_reentry_owner(scope.owner)


def candidate_experiment_terminal_frontier_cas(
    terminal: AcquisitionCandidateExperimentTerminalReceipt,
    *,
    terminal_ref: ArtifactRef,
    artifact_store: object,
    control_store: object,
) -> AcquisitionEvaluationFrontierCAS:
    """Replay precommit experiment history and derive the atomic frontier CAS."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionEvaluationFrontierCAS,
        AcquisitionEvaluationFrontierKey,
        AcquisitionEvaluationFrontierValue,
    )
    from polisyos.runtime.quality.acquisition_evaluation_history import (
        verify_candidate_experiment_terminal_history,
    )

    scope = _CANDIDATE_EXPERIMENT_REENTRY_SCOPE.get()
    if (
        type(scope) is not _CandidateExperimentReentryScope
        or type(terminal) is not AcquisitionCandidateExperimentTerminalReceipt
        or scope.terminal != terminal
        or scope.owner.bridge.artifact_store is not artifact_store
        or scope.owner.bridge.control_store is not control_store
        or terminal_ref.kind != "runtime_quality.acquisition_route_loop_receipt"
        or terminal_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("candidate_experiment_reentry_frontier_fence_not_established")
    require_candidate_experiment_reentry_fence(terminal, predecessor_head=scope.predecessor_head)
    service = scope.owner.bridge._source_control_service
    if type(service) is not ControlPlaneService:
        raise ValueError("candidate_experiment_reentry_history_owner_missing")
    history = verify_candidate_experiment_terminal_history(
        control_service=service,
        head=scope.predecessor_head,
        terminal_ref=terminal_ref,
    )
    if terminal.terminal_outcome == "candidate_blocked":
        if (
            history.head != scope.predecessor_head
            or history.terminal != terminal
            or history.terminal_ref != terminal_ref
            or history.action.action_phase_ref != scope.owner.action_phase_ref
            or history.budget_window != scope.owner.budget_window
            or history.frontier_before is not None
            or history.frontier_after is not None
            or history.evaluation is not None
            or history.reentry is not None
            or history.decision is None
            or terminal.blocker_ref != scope.owner.evaluation_owner.decision_ref
        ):
            raise ValueError("candidate_experiment_terminal_history_not_established")
        key = AcquisitionEvaluationFrontierKey(
            tenant_id=scope.owner.origin.tenant_id,
            cell_id=scope.owner.origin.cell_id,
            source_job_id=scope.owner.origin.source_job_id,
            design_problem_ref=scope.owner.origin.policy_scope.design_problem_ref,
            candidate_id=scope.owner.origin.policy_scope.candidate_id,
        )
        _revalidate_candidate_experiment_reentry_owner(scope.owner)
        if scope.owner.bridge.control_store.read_acquisition_evaluation_frontier(key) is not None:
            raise ValueError("candidate_experiment_terminal_frontier_changed")
        return AcquisitionEvaluationFrontierCAS(
            key=key, expected_revision=0, expected_frontier_ref=None, replacement=None
        )
    retained = terminal.terminal_outcome == "candidate_evaluation_retained"
    history_outcome_binding_invalid = (
        (
            history.reentry is not None
            or history.continuation is None
            or terminal.candidate_reentry_ref is not None
            or terminal.current_continuation_ref is None
        )
        if retained
        else (
            history.reentry is None
            or terminal.candidate_reentry_ref is None
            or terminal.current_continuation_ref is not None
        )
    )
    if (
        history.head != scope.predecessor_head
        or history.terminal_ref != terminal_ref
        or history.terminal != terminal
        or replace(history.origin, current_action_head=None, current_terminal_history=None)
        != replace(scope.owner.origin, current_action_head=None, current_terminal_history=None)
        or history.frontier_after is not None
        or history.action.action_phase_ref != scope.owner.action_phase_ref
        or history.budget_window != scope.owner.budget_window
        or history_outcome_binding_invalid
        or history.current_basis is None
        or history.selected_basis is None
        or history.decision is None
        or terminal.evaluation_decision_ref is None
        or terminal.selected_basis_ref is None
        or terminal.selected_evaluation_witness_ref is None
    ):
        raise ValueError("candidate_experiment_terminal_history_not_established")
    decision = history.decision
    if decision is None:
        raise ValueError("candidate_experiment_terminal_decision_not_established")
    first_generation_unknown = (
        not retained
        and (
            not history.origin.candidate_terminal_history_chain
            or "candidate_experiment_changed_input" in decision.reason_codes
        )
        and history.frontier_before is None
        and decision.comparison_result == "not_established"
        and decision.predicate_provenance == "not_established"
        and decision.prior_basis_ref is None
        and decision.prior_evaluation is None
        and decision.expected_frontier_revision == 0
        and decision.expected_frontier_ref is None
        and "candidate_evaluation_prior_basis_not_established" in decision.reason_codes
    )
    decision_outcome_valid = (
        decision.comparison_result == "equivalent"
        if retained
        else decision.comparison_result != "equivalent"
    )
    if (
        not decision_outcome_valid
        or not (decision.predicate_provenance == "recomputed" or first_generation_unknown)
        or not _candidate_ref_same(
            terminal.evaluation_decision_ref, history.terminal.evaluation_decision_ref
        )
        or not _candidate_ref_same(terminal.selected_basis_ref, history.terminal.selected_basis_ref)
        or not _candidate_ref_same(
            terminal.selected_evaluation_witness_ref,
            history.terminal.selected_evaluation_witness_ref,
        )
        or not _candidate_model_values_same(
            terminal.selected_evaluation, history.terminal.selected_evaluation
        )
    ):
        raise ValueError("candidate_experiment_terminal_selected_evaluation_changed")
    key = AcquisitionEvaluationFrontierKey(
        tenant_id=scope.owner.origin.tenant_id,
        cell_id=scope.owner.origin.cell_id,
        source_job_id=scope.owner.origin.source_job_id,
        design_problem_ref=scope.owner.origin.policy_scope.design_problem_ref,
        candidate_id=scope.owner.origin.policy_scope.candidate_id,
    )
    frontier_before = scope.owner.bridge.control_store.read_acquisition_evaluation_frontier(key)
    if frontier_before != history.frontier_before:
        raise ValueError("candidate_experiment_terminal_frontier_changed")
    expected_revision = frontier_before.revision if frontier_before is not None else 0
    expected_frontier_ref = frontier_before.frontier_ref if frontier_before is not None else None
    if history.current_basis.basis_role != "prospective" or not _candidate_ref_same(
        history.current_basis.candidate_action_ref, scope.owner.candidate_action_ref
    ):
        raise ValueError("candidate_experiment_terminal_current_basis_not_established")
    _revalidate_candidate_experiment_reentry_owner(scope.owner)
    if (
        scope.owner.bridge.control_store.read_acquisition_evaluation_frontier(key)
        != frontier_before
    ):
        raise ValueError("candidate_experiment_terminal_frontier_changed")
    if terminal.terminal_outcome == "candidate_evaluation_retained":
        if (
            history.frontier_before is None
            or history.continuation is None
            or history.evaluation is None
            or terminal.selected_evaluation is None
            or history.selected_basis.basis_role != "evaluated"
            or history.selected_basis.predicate_provenance != "recomputed"
            or not _candidate_model_values_same(
                history.selected_basis.evaluation, history.evaluation.selected
            )
            or not _candidate_ref_same(terminal.selected_basis_ref, decision.prior_basis_ref)
            or not _candidate_model_values_same(
                terminal.selected_evaluation,
                history.evaluation.selected.model_copy(
                    update={"basis_ref": terminal.selected_basis_ref}
                ),
            )
            or not _candidate_ref_same(
                terminal.selected_evaluation_witness_ref,
                history.evaluation.selected.n5_execution_ref,
            )
            or history.frontier_before.basis_ref != str(terminal.selected_basis_ref.artifact_id)
            or history.frontier_before.selected_evaluation_witness_ref
            != str(terminal.selected_evaluation_witness_ref.artifact_id)
            or history.frontier_before.selected_evaluation_content_hash
            != history.evaluation.execution.content_hash
            or history.frontier_before.basis_content_hash != history.selected_basis.content_hash
            or scope.owner.bridge.control_store.read_acquisition_evaluation_frontier(key)
            != history.frontier_before
        ):
            raise ValueError("candidate_experiment_retained_frontier_not_established")
        return AcquisitionEvaluationFrontierCAS(
            key=key,
            expected_revision=history.frontier_before.revision,
            expected_frontier_ref=history.frontier_before.frontier_ref,
            replacement=AcquisitionEvaluationFrontierValue(
                selected_evaluation_witness_ref=str(
                    terminal.selected_evaluation_witness_ref.artifact_id
                ),
                selected_evaluation_content_hash=history.evaluation.execution.content_hash,
                basis_ref=str(terminal.selected_basis_ref.artifact_id),
                basis_content_hash=history.selected_basis.content_hash,
                decision_ref=str(terminal.evaluation_decision_ref.artifact_id),
            ),
        )
    if terminal.selected_evaluation is None:
        if (
            history.evaluation is not None
            or history.selected_basis.basis_role != "blocked"
            or history.selected_basis.predicate_provenance != "not_established"
            or history.selected_basis.evaluation is not None
            or terminal.selected_basis_ref != history.terminal.selected_basis_ref
            or terminal.selected_evaluation_witness_ref != terminal.candidate_reentry_ref
            or not _candidate_ref_same(
                terminal.selected_evaluation_witness_ref, terminal.candidate_reentry_ref
            )
            or history.frontier_after is not None
        ):
            raise ValueError("candidate_experiment_terminal_blocked_basis_not_established")
        return AcquisitionEvaluationFrontierCAS(
            key=key,
            expected_revision=expected_revision,
            expected_frontier_ref=expected_frontier_ref,
            replacement=None,
        )
    if (
        history.evaluation is None
        or history.selected_basis.basis_role != "evaluated"
        or history.selected_basis.predicate_provenance != "recomputed"
        or history.selected_basis.evaluation is None
        or not _candidate_model_values_same(
            history.selected_basis.evaluation, history.evaluation.selected
        )
        or not _candidate_model_values_same(
            terminal.selected_evaluation, history.terminal.selected_evaluation
        )
        or not _candidate_ref_same(
            history.evaluation.selected.n5_execution_ref,
            terminal.selected_evaluation_witness_ref,
        )
        or not _candidate_ref_same(
            terminal.selected_evaluation.basis_ref, terminal.selected_basis_ref
        )
        or history.frontier_after is not None
    ):
        raise ValueError("candidate_experiment_terminal_basis_not_recomputed")
    witness_hash = history.evaluation.execution.content_hash
    return AcquisitionEvaluationFrontierCAS(
        key=key,
        expected_revision=expected_revision,
        expected_frontier_ref=expected_frontier_ref,
        replacement=AcquisitionEvaluationFrontierValue(
            selected_evaluation_witness_ref=str(
                terminal.selected_evaluation_witness_ref.artifact_id
            ),
            selected_evaluation_content_hash=witness_hash,
            basis_ref=str(terminal.selected_basis_ref.artifact_id),
            basis_content_hash=history.selected_basis.content_hash,
            decision_ref=str(terminal.evaluation_decision_ref.artifact_id),
        ),
    )


@contextmanager
def _candidate_terminal_scope(scope: _CandidateTerminalScope) -> Iterator[None]:
    """Carry the real candidate owner only while its caller holds the native fence."""
    token = _CANDIDATE_TERMINAL_SCOPE.set(scope)
    try:
        yield
    finally:
        _CANDIDATE_TERMINAL_SCOPE.reset(token)


def _candidate_terminal_marker(
    owner: CandidateAcquisitionEvaluationCurrentOwner | CandidateAcquisitionEvaluationReentryOwner,
) -> Path:
    """Resolve the single action-scoped terminal intent from the native owner."""
    import hashlib

    from polisyos.core import canon

    selection = owner.bridge.candidate_source_selection(owner.closure)
    if selection is None:
        raise ValueError("candidate_evaluation_terminal_intent_not_established")
    overlay_path, _ = owner.bridge._paths(selection, create=False)
    identity = hashlib.sha256(
        canon.to_canonical_bytes(owner.candidate_action_ref.model_dump(mode="json"))
    ).hexdigest()
    return overlay_path.parent / (identity + ".candidate-evaluation-terminal.started")


def _read_candidate_terminal_intent(
    marker: Path,
) -> AcquisitionCandidateRouteLoopReceipt | None:
    """Read one complete intent without following links or accepting partial writes."""
    import json
    import os
    import stat

    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateRouteLoopReceipt,
    )

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(marker, flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError("candidate_evaluation_terminal_intent_invalid") from exc
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1_048_576:
            raise ValueError("candidate_evaluation_terminal_intent_invalid")
        try:
            return AcquisitionCandidateRouteLoopReceipt.model_validate(json.load(stream))
        except (UnicodeError, TypeError, ValueError) as exc:
            raise ValueError("candidate_evaluation_terminal_intent_invalid") from exc


def _write_candidate_terminal_intent(
    marker: Path, terminal: AcquisitionCandidateRouteLoopReceipt
) -> None:
    """Fsync one exact terminal before its writer may publish a durable event."""
    import json
    import os

    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateRouteLoopReceipt,
    )

    if type(terminal) is not AcquisitionCandidateRouteLoopReceipt:
        raise TypeError("candidate_evaluation_terminal_intent_untyped")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(marker, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(terminal.model_dump(mode="json"), stream, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    directory_fd = os.open(marker.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _require_candidate_terminal_recovery_intent(
    terminal: AcquisitionCandidateRouteLoopReceipt,
) -> None:
    """Reopen the exact full intent belonging to the active native terminal fence."""
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateRouteLoopReceipt,
    )

    scope = _CANDIDATE_TERMINAL_SCOPE.get()
    if (
        type(terminal) is not AcquisitionCandidateRouteLoopReceipt
        or type(scope) is not _CandidateTerminalScope
        or type(scope.owner)
        not in {
            CandidateAcquisitionEvaluationCurrentOwner,
            CandidateAcquisitionEvaluationReentryOwner,
        }
        or not _candidate_ref_same(terminal.candidate_action_ref, scope.owner.candidate_action_ref)
        or not _candidate_model_values_same(terminal, scope.terminal)
    ):
        raise ValueError("candidate_evaluation_terminal_intent_not_established")
    saved = _read_candidate_terminal_intent(_candidate_terminal_marker(scope.owner))
    if saved is None or not _candidate_model_values_same(saved, terminal):
        raise ValueError("candidate_evaluation_terminal_intent_not_established")


def _candidate_terminal_intent_for_publication(
    *,
    marker: Path,
    expected: AcquisitionCandidateRouteLoopReceipt,
    event_log: RuntimeDiagnosticEventLog,
    sink: AcquisitionRouteLoopAuthoritySink,
) -> AcquisitionCandidateRouteLoopReceipt:
    """Select the original full terminal across marker and event crash windows.

    The caller holds the native action fence and independently revalidates its
    owner. An incomplete marker or ambiguous event inventory never authorizes
    publication. A missing marker after an unmanaged filesystem deletion is
    outside this native-fence crash model.
    """
    events = event_log.list_events(run_id=expected.run_id, job_id=expected.job_id, limit=1000)
    if len(events) >= 1000:
        raise ValueError("candidate_evaluation_terminal_intent_not_established")
    terminal_events = tuple(
        row.event
        for row in events
        if row.event.event_type == "polisyos.runtime.acquisition.route_loop.v3"
    )
    if len(terminal_events) > 1:
        raise ValueError("candidate_evaluation_terminal_intent_not_established")

    saved = _read_candidate_terminal_intent(marker)
    if saved is not None:
        replay = expected.model_copy(update={"generated_at": saved.generated_at})
        if not _candidate_model_values_same(saved, replay):
            raise ValueError("candidate_evaluation_terminal_intent_changed")
        if terminal_events:
            recovered, _ = sink.recover_candidate_terminal(saved)
            if not _candidate_model_values_same(recovered, saved):
                raise ValueError("candidate_evaluation_terminal_outcome_not_established")
        return saved

    if terminal_events:
        recovered, _ = sink.recover_candidate_terminal_from_event(expected)
        replay = expected.model_copy(update={"generated_at": recovered.generated_at})
        if not _candidate_model_values_same(recovered, replay):
            raise ValueError("candidate_evaluation_terminal_outcome_not_established")
        expected = recovered
    _write_candidate_terminal_intent(marker, expected)
    return expected


def candidate_terminal_frontier_cas(
    terminal: AcquisitionCandidateRouteLoopReceipt,
    *,
    artifact_store: object,
    control_store: object,
) -> AcquisitionEvaluationFrontierCAS:
    """Build the candidate-only CAS under its real native owner fence.

    The SQL sink commits the resulting action head and frontier atomically.
    Retention preserves the existing frontier; a freshly verified result or
    blocked reentry selects its own owner-backed witness.
    """
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionEvaluationFrontierCAS,
        AcquisitionEvaluationFrontierKey,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        read_candidate_acquisition_retained_continuation,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateRouteLoopReceipt,
    )

    scope = _CANDIDATE_TERMINAL_SCOPE.get()
    if (
        type(terminal) is not AcquisitionCandidateRouteLoopReceipt
        or type(scope) is not _CandidateTerminalScope
        or type(scope.owner)
        not in {
            CandidateAcquisitionEvaluationCurrentOwner,
            CandidateAcquisitionEvaluationReentryOwner,
        }
        or scope.owner.bridge.artifact_store is not artifact_store
        or scope.owner.bridge.control_store is not control_store
        or not _candidate_model_values_same(terminal, scope.terminal)
    ):
        raise ValueError("candidate_evaluation_native_terminal_fence_not_established")
    owner = scope.owner
    if type(owner) is CandidateAcquisitionEvaluationReentryOwner:
        return _candidate_reentry_terminal_frontier_cas(terminal, owner=owner)
    if (
        type(owner) is not CandidateAcquisitionEvaluationCurrentOwner
        or terminal.terminal_outcome != "candidate_evaluation_retained"
    ):
        raise ValueError("candidate_evaluation_native_terminal_fence_not_established")
    current = owner.revalidate()
    decision = read_acquisition_evaluation_artifact(
        store=owner.bridge.artifact_store,
        event_log=owner.bridge.event_log,
        ref=owner.decision_ref,
        record_type=CandidateAcquisitionEvaluationDecision,
    )
    if (
        type(decision) is not CandidateAcquisitionEvaluationDecision
        or decision.comparison_result != "equivalent"
        or decision.predicate_provenance != "recomputed"
        or decision.prior_basis_ref is None
        or decision.prior_evaluation is None
        or terminal.current_continuation_ref is None
        or not _candidate_ref_same(terminal.candidate_action_ref, owner.candidate_action_ref)
        or not _candidate_ref_same(terminal.evaluation_decision_ref, owner.decision_ref)
        or not _candidate_ref_same(terminal.selected_basis_ref, decision.prior_basis_ref)
        or not _candidate_model_values_same(terminal.selected_evaluation, decision.prior_evaluation)
        or not _candidate_ref_same(
            terminal.selected_evaluation_witness_ref, owner.prior.selected.n5_execution_ref
        )
        or (terminal.tenant_id, terminal.cell_id, terminal.run_id, terminal.source_job_id)
        != (decision.tenant_id, decision.cell_id, decision.run_id, decision.source_job_id)
        or terminal.route_id != decision.route_id
        or terminal.job_id != decision.action_job_id
        or terminal.action_generation != decision.action_generation
        or terminal.compiled_ref != decision.compiled_ref
    ):
        raise ValueError("candidate_evaluation_terminal_decision_mismatch")
    previous = read_acquisition_evaluation_artifact(
        store=owner.bridge.artifact_store,
        event_log=owner.bridge.event_log,
        ref=decision.prior_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    if (
        type(previous) is not CandidateAcquisitionEvaluationBasis
        or previous.basis_role != "evaluated"
        or not _candidate_model_values_same(previous.evaluation, owner.prior.selected)
        or not basis_exact_values_equal(previous, current)
    ):
        raise ValueError("candidate_evaluation_terminal_basis_not_established")
    continuation, actual = read_candidate_acquisition_retained_continuation(
        store=owner.bridge.artifact_store,
        event_log=owner.bridge.event_log,
        control_store=owner.bridge.control_store,
        ref=terminal.current_continuation_ref,
        decision=decision,
        terminal=terminal,
        prior_closure=owner.closure,
    )
    if not _candidate_model_values_same(actual, owner.prior) or not (
        set(current.limitations) | set(previous.limitations)
    ).issubset(continuation.limitations):
        raise ValueError("candidate_evaluation_terminal_continuation_not_established")
    key = AcquisitionEvaluationFrontierKey(
        tenant_id=decision.tenant_id,
        cell_id=decision.cell_id,
        source_job_id=decision.source_job_id,
        design_problem_ref=decision.design_problem_ref,
        candidate_id=decision.candidate_id,
    )
    frontier = owner.bridge.control_store.read_acquisition_evaluation_frontier(key)
    if (
        frontier is None
        or frontier.revision != decision.expected_frontier_revision
        or frontier.frontier_ref != decision.expected_frontier_ref
        or frontier.basis_ref != str(decision.prior_basis_ref.artifact_id)
        or frontier.basis_content_hash != previous.content_hash
        or frontier.selected_evaluation_witness_ref
        != str(owner.prior.selected.n5_execution_ref.artifact_id)
        or frontier.selected_evaluation_content_hash != owner.prior.execution.content_hash
    ):
        raise ValueError("candidate_evaluation_terminal_frontier_changed")
    owner.revalidate()
    return AcquisitionEvaluationFrontierCAS(
        key=key,
        expected_revision=decision.expected_frontier_revision,
        expected_frontier_ref=decision.expected_frontier_ref,
        replacement=None,
    )


def _candidate_reentry_terminal_frontier_cas(
    terminal: AcquisitionCandidateRouteLoopReceipt,
    *,
    owner: CandidateAcquisitionEvaluationReentryOwner,
) -> AcquisitionEvaluationFrontierCAS:
    """Replay the actual reentry and selected N5 or blocked witness before CAS."""
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionEvaluationFrontierCAS,
        AcquisitionEvaluationFrontierKey,
        AcquisitionEvaluationFrontierValue,
    )
    from polisyos.runtime.quality.acquisition_evaluation import (
        resolve_selected_acquisition_evaluation_parts,
    )
    from polisyos.runtime.quality.candidate_source_basis import (
        _live_candidate_source_predecessors,
    )
    from polisyos.runtime.quality.candidate_source_reentry_history import (
        verify_candidate_source_reentry_history,
    )
    from polisyos.runtime.quality.generation_cycle import validate_candidate_source_continuation

    if (
        terminal.terminal_outcome != "candidate_reentry_completed"
        or terminal.candidate_reentry_ref is None
        or terminal.current_continuation_ref is not None
        or not _candidate_ref_same(terminal.candidate_action_ref, owner.candidate_action_ref)
        or not _candidate_ref_same(terminal.evaluation_decision_ref, owner.decision_ref)
    ):
        raise ValueError("candidate_evaluation_reentry_terminal_mismatch")
    bridge = owner.bridge
    service = bridge._source_control_service
    sink = bridge.action_head_sink
    if type(service) is not ControlPlaneService or sink is not service.acquisition_route_sink:
        raise ValueError("candidate_evaluation_reentry_sink_not_established")
    current = owner.revalidate()
    action = bridge._require_selected_candidate_action(
        closure=owner.closure, candidate_action_ref=owner.candidate_action_ref
    )
    decision = read_acquisition_evaluation_artifact(
        store=bridge.artifact_store,
        event_log=bridge.event_log,
        ref=owner.decision_ref,
        record_type=CandidateAcquisitionEvaluationDecision,
    )
    selected = read_acquisition_evaluation_artifact(
        store=bridge.artifact_store,
        event_log=bridge.event_log,
        ref=terminal.selected_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    if (
        type(decision) is not CandidateAcquisitionEvaluationDecision
        or type(selected) is not CandidateAcquisitionEvaluationBasis
        or decision.comparison_result not in {"different", "not_established"}
        or not _candidate_ref_same(decision.current_basis_ref, owner.current_basis_ref)
        or (terminal.tenant_id, terminal.cell_id, terminal.run_id, terminal.source_job_id)
        != (decision.tenant_id, decision.cell_id, decision.run_id, decision.source_job_id)
        or terminal.route_id != decision.route_id
        or terminal.job_id != decision.action_job_id
        or terminal.action_generation != decision.action_generation
        or terminal.compiled_ref != decision.compiled_ref
    ):
        raise ValueError("candidate_evaluation_reentry_decision_mismatch")
    # This closure is obtained independently from the actual sink, with the
    # current generation excluded before its historical action fold.
    prior_closure = sink._candidate_prior_closure(terminal)
    if not _candidate_model_values_same(prior_closure, owner.closure):
        raise ValueError("candidate_evaluation_reentry_prior_closure_changed")
    service.verify_candidate_source_budget_window_historical(closure=prior_closure, action=action)
    reentry = verify_candidate_source_reentry_history(
        artifact_store=bridge.artifact_store,
        event_log=bridge.event_log,
        control_store=bridge.control_store,
        receipt_ref=terminal.candidate_reentry_ref,
        expected_tenant_id=terminal.tenant_id,
        expected_cell_id=terminal.cell_id,
        expected_run_id=terminal.run_id,
        expected_source_job_id=terminal.source_job_id,
        expected_action_job_id=terminal.job_id,
        expected_route_id=terminal.route_id,
        expected_action_generation=terminal.action_generation,
        expected_selected_action_ref=terminal.candidate_action_ref,
    )
    validate_candidate_source_continuation(prior_closure.generation_run, reentry)
    evaluation = (
        resolve_selected_acquisition_evaluation_parts(
            artifact_store=bridge.artifact_store,
            control_store=bridge.control_store,
            tenant_id=terminal.tenant_id,
            cell_id=terminal.cell_id,
            run_id=terminal.run_id,
            generation_run=reentry.continued_generation_run,
            source_cycle=reentry.new_cycle,
            design_problem_ref=prior_closure.design_problem_ref,
        )
        if reentry.new_cycle.simulation.status == "joint_simulated"
        else None
    )
    if evaluation is not None:
        bridge._verify_candidate_reentry_prepared_configuration(
            closure=prior_closure,
            receipt=reentry,
            prepared_n5_configuration=owner.prepared_n5_configuration,
        )
    expected_witness = (
        evaluation.selected.n5_execution_ref if evaluation else terminal.candidate_reentry_ref
    )
    expected_witness_hash = (
        evaluation.execution.content_hash if evaluation else reentry.content_hash
    )
    if (
        selected.basis_role != ("evaluated" if evaluation else "blocked")
        or (selected.tenant_id, selected.cell_id, selected.run_id, selected.source_job_id)
        != (decision.tenant_id, decision.cell_id, decision.run_id, decision.source_job_id)
        or selected.action_job_id != decision.action_job_id
        or selected.action_generation != decision.action_generation
        or selected.route_id != decision.route_id
        or selected.design_problem_ref != decision.design_problem_ref
        or selected.design_problem_basis_ref != decision.design_problem_basis_ref
        or selected.candidate_id != decision.candidate_id
        or selected.source_candidate_content_hash != decision.source_candidate_content_hash
        or not _candidate_ref_same(selected.candidate_action_ref, terminal.candidate_action_ref)
        or not _candidate_ref_same(selected.candidate_source_ref, reentry.candidate_source_ref)
        or not _candidate_ref_same(
            selected.candidate_world_intent_ref, reentry.candidate_world_intent_ref
        )
        or not _candidate_ref_same(selected.selected_data_snapshot_ref, reentry.data_snapshot_ref)
        or not _candidate_ref_same(selected.selected_world_model_ref, reentry.world_model_ref)
        or not _candidate_model_values_same(selected.preparation_inputs, current.preparation_inputs)
        or selected.prepared_n5_configuration != current.prepared_n5_configuration
        or not (set(current.limitations) | set(reentry.limitations)).issubset(selected.limitations)
        or not _candidate_ref_same(terminal.selected_evaluation_witness_ref, expected_witness)
        or (evaluation is None) != (selected.evaluation is None)
        or (evaluation is None) != (terminal.selected_evaluation is None)
        or (
            evaluation is not None
            and (
                not _candidate_model_values_same(selected.evaluation, evaluation.selected)
                or not _candidate_model_values_same(
                    terminal.selected_evaluation,
                    evaluation.selected.model_copy(
                        update={"basis_ref": terminal.selected_basis_ref}
                    ),
                )
            )
        )
    ):
        raise ValueError("candidate_evaluation_reentry_outcome_mismatch")
    window = bridge._resolve_candidate_source_budget_window(
        closure=owner.closure, action_phase_ref=action.action_phase_ref
    )
    values, reasons = recompute_candidate_acquisition_basis_values(
        artifact_store=bridge.artifact_store,
        problem=prior_closure.design_problem_basis,
        preparation_inputs=selected.preparation_inputs,
        predecessors=_live_candidate_source_predecessors(bridge=bridge, closure=prior_closure),
        prior=evaluation,
        prepared_n5_configuration=selected.prepared_n5_configuration,
        fresh_limit_usd=window.fresh_limit_usd,
        global_limit_usd=window.global_limit_usd,
        selected_data_snapshot_ref=selected.selected_data_snapshot_ref,
        selected_world_model_ref=selected.selected_world_model_ref,
    )
    if (
        selected.predicate_provenance != ("not_established" if reasons else "recomputed")
        or selected.reason_codes != reasons
        or exact_n5_content_bytes(values) != bytes.fromhex(selected.effective_native_values_hex)
    ):
        raise ValueError("candidate_evaluation_reentry_outcome_replay_mismatch")
    if (
        evaluation is not None
        and decision.comparison_result == "different"
        and decision.prior_basis_ref is not None
    ):
        from polisyos.runtime.quality.acquisition_model_transition import (
            CandidateModelRevision,
            is_prospective_candidate_model_revision,
            resolve_candidate_source_model_revision,
        )

        previous = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=decision.prior_basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        if is_prospective_candidate_model_revision(previous, current):
            revision = resolve_candidate_source_model_revision(
                artifact_store=bridge.artifact_store,
                event_log=bridge.event_log,
                control_store=bridge.control_store,
                control_service=service,
                terminal=terminal,
                prior_closure=prior_closure,
            )
            if type(revision) is not CandidateModelRevision:
                raise ValueError("candidate_source_model_revision_result_unverified")
    key = AcquisitionEvaluationFrontierKey(
        tenant_id=decision.tenant_id,
        cell_id=decision.cell_id,
        source_job_id=decision.source_job_id,
        design_problem_ref=decision.design_problem_ref,
        candidate_id=decision.candidate_id,
    )
    frontier = bridge.control_store.read_acquisition_evaluation_frontier(key)
    if (
        frontier.revision if frontier is not None else 0
    ) != decision.expected_frontier_revision or (
        frontier.frontier_ref if frontier is not None else None
    ) != decision.expected_frontier_ref:
        raise ValueError("candidate_evaluation_reentry_frontier_changed")
    owner.revalidate()
    if bridge.control_store.read_acquisition_evaluation_frontier(key) != frontier:
        raise ValueError("candidate_evaluation_reentry_frontier_changed")
    return AcquisitionEvaluationFrontierCAS(
        key=key,
        expected_revision=decision.expected_frontier_revision,
        expected_frontier_ref=decision.expected_frontier_ref,
        replacement=AcquisitionEvaluationFrontierValue(
            selected_evaluation_witness_ref=str(
                terminal.selected_evaluation_witness_ref.artifact_id
            ),
            selected_evaluation_content_hash=expected_witness_hash,
            basis_ref=str(terminal.selected_basis_ref.artifact_id),
            basis_content_hash=selected.content_hash,
            decision_ref=str(terminal.evaluation_decision_ref.artifact_id),
        ),
    )


def dispatch_candidate_acquisition_evaluation(
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
) -> AcquisitionActionHeadRecord:
    """Run one fenced candidate comparison and, when needed, a fresh N5.

    This joins existing selected-action, candidate-source, numerical and SQL
    owners. An unknown initial comparison permits only a separately admitted
    fresh attempt. An equivalent comparison never reruns N5; it waits for the
    current candidate-only cheap continuation owner.
    """
    from polisyos.runtime.http.services.control_plane_store import AcquisitionEvaluationFrontierKey
    from polisyos.runtime.quality.acquisition_evaluation import (
        issue_candidate_acquisition_evaluation_basis,
        issue_candidate_acquisition_evaluation_decision,
        resolve_selected_acquisition_evaluation_parts,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateRouteLoopReceipt,
    )
    from polisyos.runtime.quality.candidate_source_basis import (
        _live_candidate_source_predecessors,
        prepare_live_candidate_source_basis_values,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    sink = bridge.action_head_sink
    if type(bridge) is not AcquisitionWorldGrowthBridge or sink is None:
        raise ValueError("candidate_evaluation_dispatch_owner_not_established")
    # The sink keeps the public @3 path closed until its exact historical
    # reader and transactional frontier are composed. Check before any N5.
    sink._require_candidate_terminal_history_owner()
    snapshot = sink.current_action_outcome(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        source_job_id=closure.source_job_id,
        route_id=closure.route_id,
    )
    pending = snapshot.latest_receipt if snapshot is not None else None
    if type(pending) is AcquisitionCandidateRouteLoopReceipt:
        # The SQL head/frontier transaction already committed. Reopen its exact
        # historical owner and current frontier instead of publishing or
        # invoking numerical work a second time.
        history = snapshot.candidate_terminal_history
        admission = bridge.control_store.current_execution_job_admission()
        if (
            type(history) is not CandidateEvaluationTerminalHistory
            or history.head != snapshot.head
            or not _candidate_model_values_same(history.terminal, pending)
            or history.terminal_ref.manifest_profile_sha256
            != snapshot.head.receipt_manifest_profile_sha256
            or str(history.terminal_ref.artifact_id) != snapshot.head.receipt_ref
            or admission.job.kind != "acquisition"
            or admission.job.state != "running"
            or admission.job.job_id != pending.job_id
            or admission.job.run_id != closure.run_id
            or admission.scope.status != "established"
            or not admission.scope.actor_authenticated
            or admission.scope.tenant_id != closure.tenant_id
            or admission.scope.cell_id != closure.cell_id
            or not _candidate_model_values_same(sink._candidate_prior_closure(pending), closure)
            or bridge.control_store.read_acquisition_evaluation_frontier(history.frontier.key)
            != history.frontier
        ):
            raise ValueError("candidate_evaluation_committed_outcome_not_established")
        if (
            not bridge.control_store.current_execution_job_admission().same_execution_identity(
                admission
            )
            or sink.current_action_outcome(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=closure.run_id,
                source_job_id=closure.source_job_id,
                route_id=closure.route_id,
            )
            != snapshot
            or bridge.control_store.read_acquisition_evaluation_frontier(history.frontier.key)
            != history.frontier
        ):
            raise ValueError("candidate_evaluation_committed_outcome_changed")
        return snapshot.head
    if (
        snapshot is None
        or type(pending) is not AcquisitionRoutePhaseReceipt
        or pending.receipt_phase != "candidate_input_reentry_pending"
        or pending.candidate_receipt_ref is None
    ):
        raise ValueError("candidate_evaluation_dispatch_pending_not_established")
    action_ref = pending.candidate_receipt_ref
    action = bridge._require_selected_candidate_action(
        closure=closure, candidate_action_ref=action_ref
    )
    selection = bridge.candidate_source_selection(closure)
    if selection is None:
        raise ValueError("candidate_evaluation_dispatch_source_not_selected")
    overlay_path, _ = bridge._paths(selection, create=False)
    with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
        profile, declaration, _ = bridge._candidate_source_prior_owner(closure=closure)
        intent_ref, intent = bridge._candidate_world_materialization_intent(
            closure=closure,
            candidate_action_ref=action_ref,
            configured_profile=profile,
            original_model_declaration=declaration,
        )
        prepared = prepare_live_candidate_source_basis_values(
            bridge=bridge,
            closure=closure,
            candidate_action_ref=action_ref,
            transaction_time=intent.transaction_time,
        )
        if (
            prepared.predicate_provenance != "recomputed"
            or prepared.reason_codes
            or prepared.inputs is None
        ):
            raise ValueError("candidate_evaluation_dispatch_preparation_not_established")
        prior = (
            resolve_selected_acquisition_evaluation(bridge=bridge, closure=closure)
            if closure.source_cycle.simulation.status == "joint_simulated"
            else None
        )
        if prior is None:
            bridge._candidate_source_first_prior(closure=closure)
        configuration = prepare_joint_simulation_configuration()
        window = bridge._resolve_candidate_source_budget_window(
            closure=closure, action_phase_ref=action.action_phase_ref
        )
        predecessors = _live_candidate_source_predecessors(bridge=bridge, closure=closure)
        values, reasons = recompute_candidate_acquisition_basis_values(
            artifact_store=bridge.artifact_store,
            problem=closure.design_problem_basis,
            preparation_inputs=prepared.inputs,
            predecessors=predecessors,
            prior=prior,
            prepared_n5_configuration=configuration,
            fresh_limit_usd=window.fresh_limit_usd,
            global_limit_usd=window.global_limit_usd,
        )
        inherited: list[str] = [*action.limitations, *profile.limitations]
        for receipt in closure.candidate_basis_transitions:
            inherited.extend(receipt.limitations)
        for history in closure.candidate_terminal_history:
            inherited.extend(history.selected_basis.limitations)
            inherited.extend(history.current_basis.limitations)
            if history.continuation is not None:
                inherited.extend(history.continuation.limitations)
        world = prepared.effective_values.get("world")
        inherited_world = world.get("inherited_world") if isinstance(world, dict) else None
        world_limitations = (
            inherited_world.get("limitations") if isinstance(inherited_world, dict) else None
        )
        blockers = (
            world_limitations.get("admissibility_blockers")
            if isinstance(world_limitations, dict)
            else None
        )
        if not isinstance(blockers, (list, tuple)) or any(
            not isinstance(item, str) or not item.strip() for item in blockers
        ):
            raise ValueError("candidate_evaluation_dispatch_limitations_not_established")
        limitations = tuple(dict.fromkeys((*inherited, *blockers)))
        if not limitations:
            raise ValueError("candidate_evaluation_dispatch_limitations_not_established")
        basis_kwargs = {
            "tenant_id": closure.tenant_id,
            "cell_id": closure.cell_id,
            "run_id": closure.run_id,
            "source_job_id": closure.source_job_id,
            "action_job_id": action.action_job_id,
            "action_generation": action.action_generation,
            "route_id": closure.route_id,
            "design_problem_ref": closure.design_problem_ref,
            "design_problem_basis_ref": closure.design_problem_basis_ref,
            "candidate_id": closure.source_cycle.selected_candidate_ref,
            "source_candidate_content_hash": closure.source_cycle.selected_candidate_content_hash,
            "candidate_action_ref": action_ref,
            "candidate_world_intent_ref": intent_ref,
            "candidate_source_ref": action.candidate_source_ref,
            "preparation_inputs": prepared.inputs,
            "prepared_n5_configuration": configuration,
        }
        current = issue_candidate_acquisition_evaluation_basis(
            **basis_kwargs,
            basis_role="prospective",
            values=values,
            predicate_provenance="not_established" if reasons else "recomputed",
            reason_codes=reasons,
            limitations=limitations,
        )
        current_ref = _select_candidate_evaluation_artifact(
            bridge=bridge, closure=closure, record=current
        )
        key = AcquisitionEvaluationFrontierKey(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            source_job_id=closure.source_job_id,
            design_problem_ref=closure.design_problem_ref,
            candidate_id=closure.source_cycle.selected_candidate_ref,
        )
        frontier = bridge.control_store.read_acquisition_evaluation_frontier(key)
        previous_ref = None
        prior_selected = None
        comparison: _ComparisonResult = "not_established"
        decision_reasons = tuple(
            dict.fromkeys(("candidate_evaluation_prior_basis_not_established", *reasons))
        )
        if frontier is not None:
            histories = closure.candidate_terminal_history
            if not histories or prior is None or reasons:
                raise ValueError("candidate_evaluation_prior_frontier_not_established")
            latest = histories[-1]
            previous = latest.selected_basis
            previous_ref = latest.terminal.selected_basis_ref
            prior_selected = prior.selected.model_copy(update={"basis_ref": previous_ref})
            if (
                type(latest) is not CandidateEvaluationTerminalHistory
                or latest.frontier != frontier
                or previous.basis_role != "evaluated"
                or previous.predicate_provenance != "recomputed"
                or not _candidate_model_values_same(latest.evaluation, prior)
                or not _candidate_model_values_same(
                    latest.terminal.selected_evaluation, prior_selected
                )
            ):
                raise ValueError("candidate_evaluation_prior_frontier_not_established")
            comparison = (
                "equivalent" if basis_exact_values_equal(previous, current) else "different"
            )
            decision_reasons = ()
        elif closure.candidate_terminal_history:
            raise ValueError("candidate_evaluation_prior_frontier_not_established")

        saved = _candidate_evaluation_artifact_for_recovery(
            bridge=bridge, closure=closure, candidate_action_ref=action_ref, role="decision"
        )
        saved_decision = saved[1] if saved is not None else None
        if saved_decision is not None and type(saved_decision) is not (
            CandidateAcquisitionEvaluationDecision
        ):
            raise ValueError("candidate_evaluation_recovery_record_mismatch")
        decision = issue_candidate_acquisition_evaluation_decision(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            action_job_id=action.action_job_id,
            action_generation=action.action_generation,
            route_id=closure.route_id,
            compiled_ref=closure.compiled_ref,
            design_problem_ref=closure.design_problem_ref,
            design_problem_basis_ref=closure.design_problem_basis_ref,
            candidate_id=closure.source_cycle.selected_candidate_ref,
            source_candidate_content_hash=closure.source_cycle.selected_candidate_content_hash,
            candidate_action_ref=action_ref,
            candidate_world_intent_ref=intent_ref,
            candidate_source_ref=action.candidate_source_ref,
            current_basis_ref=current_ref,
            prior_basis_ref=previous_ref,
            prior_evaluation=prior_selected,
            comparison_result=comparison,
            predicate_provenance="not_established" if decision_reasons else "recomputed",
            reason_codes=decision_reasons,
            expected_frontier_revision=frontier.revision if frontier else 0,
            expected_frontier_ref=frontier.frontier_ref if frontier else None,
            generated_at=(
                saved_decision.generated_at if saved_decision else datetime.now(UTC).isoformat()
            ),
        )
        if saved_decision is not None and not _candidate_model_values_same(
            saved_decision, decision
        ):
            raise ValueError("candidate_evaluation_recovery_decision_changed")
        decision_ref = _select_candidate_evaluation_artifact(
            bridge=bridge, closure=closure, record=decision
        )
        if comparison == "equivalent":
            if prior is None:
                raise ValueError("candidate_evaluation_retained_prior_not_established")
            retained_owner = CandidateAcquisitionEvaluationCurrentOwner(
                bridge=bridge,
                closure=closure,
                candidate_action_ref=action_ref,
                candidate_world_intent_ref=intent_ref,
                current_basis_ref=current_ref,
                decision_ref=decision_ref,
                prior=prior,
                prepared_n5_configuration=configuration,
            )
            return _dispatch_candidate_retained_continuation(
                owner=retained_owner, decision=decision, snapshot=snapshot, pending=pending
            )
        owner = CandidateAcquisitionEvaluationReentryOwner(
            bridge=bridge,
            closure=closure,
            candidate_action_ref=action_ref,
            candidate_world_intent_ref=intent_ref,
            current_basis_ref=current_ref,
            decision_ref=decision_ref,
            prior=prior,
            prepared_n5_configuration=configuration,
        )
        owner.revalidate()

    # This existing owner fences the expensive operation and recovers its saved
    # event/result on retry instead of issuing another physical N5.
    reentry_ref, reentry = bridge._prepare_candidate_source_reentry(
        closure=closure,
        candidate_action_ref=action_ref,
        prepared_n5_configuration=configuration,
    )
    evaluation = (
        resolve_selected_acquisition_evaluation_parts(
            artifact_store=bridge.artifact_store,
            control_store=bridge.control_store,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            generation_run=reentry.continued_generation_run,
            source_cycle=reentry.new_cycle,
            design_problem_ref=closure.design_problem_ref,
        )
        if reentry.new_cycle.simulation.status == "joint_simulated"
        else None
    )
    selected_values, selected_reasons = recompute_candidate_acquisition_basis_values(
        artifact_store=bridge.artifact_store,
        problem=closure.design_problem_basis,
        preparation_inputs=prepared.inputs,
        predecessors=predecessors,
        prior=evaluation,
        prepared_n5_configuration=configuration,
        fresh_limit_usd=window.fresh_limit_usd,
        global_limit_usd=window.global_limit_usd,
        selected_data_snapshot_ref=reentry.data_snapshot_ref,
        selected_world_model_ref=reentry.world_model_ref,
    )
    actual_basis = issue_candidate_acquisition_evaluation_basis(
        **basis_kwargs,
        basis_role="evaluated" if evaluation else "blocked",
        values=selected_values,
        predicate_provenance="not_established" if selected_reasons else "recomputed",
        reason_codes=selected_reasons,
        limitations=tuple(dict.fromkeys((*current.limitations, *reentry.limitations))),
        selected_data_snapshot_ref=reentry.data_snapshot_ref,
        selected_world_model_ref=reentry.world_model_ref,
        evaluation=evaluation.selected if evaluation else None,
    )
    actual_ref = _select_candidate_evaluation_artifact(
        bridge=bridge, closure=closure, record=actual_basis
    )
    selected_evaluation = (
        evaluation.selected.model_copy(update={"basis_ref": actual_ref}) if evaluation else None
    )
    witness = evaluation.selected.n5_execution_ref if evaluation else reentry_ref
    terminal = AcquisitionCandidateRouteLoopReceipt(
        receipt_id=pending.job_id + ".candidate-evaluation.terminal",
        tenant_id=pending.tenant_id,
        cell_id=pending.cell_id,
        run_id=pending.run_id,
        source_job_id=pending.source_job_id,
        route_id=pending.route_id,
        action_generation=pending.action_generation,
        job_id=pending.job_id,
        compiled_ref=pending.compiled_ref,
        planner_report_hash=pending.planner_report_hash,
        cost_basis_hash=pending.cost_basis_hash,
        decision_ref=pending.decision_ref,
        terminal_outcome="candidate_reentry_completed",
        predecessor_receipt_ref=snapshot.head.receipt_ref,
        owner_receipt_refs=tuple(
            sorted({*pending.owner_receipt_refs, str(decision_ref.artifact_id)})
        ),
        candidate_action_ref=action_ref,
        candidate_reentry_ref=reentry_ref,
        evaluation_decision_ref=decision_ref,
        selected_basis_ref=actual_ref,
        selected_evaluation_witness_ref=witness,
        selected_evaluation=selected_evaluation,
        generated_at=datetime.now(UTC),
    )
    marker = _candidate_terminal_marker(owner)
    with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
        owner.revalidate()
        latest = sink.current_action_outcome(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
        )
        if latest is None or latest.head != snapshot.head or latest.latest_receipt != pending:
            raise ValueError("candidate_evaluation_dispatch_pending_changed")
        terminal = _candidate_terminal_intent_for_publication(
            marker=marker, expected=terminal, event_log=bridge.event_log, sink=sink
        )
        with _candidate_terminal_scope(_CandidateTerminalScope(owner, terminal)):
            return sink.persist_terminal(terminal)


def _require_candidate_experiment_evaluation_record_scope(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    pending_phase_ref: str,
    candidate_action_ref: ArtifactRef,
    record: CandidateAcquisitionEvaluationBasis
    | CandidateAcquisitionEvaluationDecision
    | CandidateAcquisitionRetainedContinuation
    | CandidateRetainedPortCapture,
    selected_reentry_ref: ArtifactRef | None = None,
) -> object:
    """Bind one candidate basis/decision to the current typed experiment action."""
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _candidate_experiment_source_selection,
        _current_candidate_experiment_reentry_action,
        read_candidate_experiment_acquisition_action,
    )

    if type(record) not in {
        CandidateAcquisitionEvaluationBasis,
        CandidateAcquisitionEvaluationDecision,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    }:
        raise TypeError("candidate_experiment_evaluation_record_untyped")
    selection, _phase, _admission, action = _current_candidate_experiment_reentry_action(
        bridge,
        origin,
        pending_phase_ref,
        candidate_action_ref,
    )
    current_action = read_candidate_experiment_acquisition_action(
        bridge=bridge,
        origin=origin,
        receipt_ref=candidate_action_ref,
        require_current_action=False,
    )
    if (
        current_action != action
        or action.selection != selection
        or _candidate_experiment_source_selection(bridge, origin) != selection
    ):
        raise ValueError("candidate_experiment_evaluation_action_not_current")
    source_candidate_content_hash = (
        record.source_candidate_content_hash
        if type(record)
        in {CandidateAcquisitionEvaluationBasis, CandidateAcquisitionEvaluationDecision}
        else record.retained_evaluation.candidate_content_hash
    )
    identity = (
        record.tenant_id,
        record.cell_id,
        record.run_id,
        record.source_job_id,
        record.action_job_id,
        record.action_generation,
        record.route_id,
        record.design_problem_ref,
        record.design_problem_basis_ref,
        record.candidate_id,
        source_candidate_content_hash,
    )
    effective_cycle = origin.effective_source_cycle
    expected_candidate_id = effective_cycle.selected_candidate_ref
    expected_candidate_hash = effective_cycle.selected_candidate_content_hash
    selected_reentry = None
    if (
        type(record) is CandidateAcquisitionEvaluationBasis
        and record.basis_role
        in {
            "evaluated",
            "blocked",
        }
        and (
            record.selected_data_snapshot_ref is not None
            or record.selected_world_model_ref is not None
        )
    ):
        if selected_reentry_ref is None:
            raise ValueError("candidate_experiment_selected_reentry_not_established")
        selected_reentry = _read_candidate_experiment_selected_reentry(
            bridge=bridge,
            origin=origin,
            candidate_action_ref=candidate_action_ref,
            receipt_ref=selected_reentry_ref,
        )
        if record.basis_role == "evaluated":
            evaluation = record.evaluation
            if (
                evaluation is None
                or evaluation.candidate_id != selected_reentry.new_cycle.selected_candidate_ref
                or evaluation.candidate_content_hash
                != selected_reentry.new_cycle.selected_candidate_content_hash
            ):
                raise ValueError("candidate_experiment_selected_basis_evaluation_changed")
        elif record.evaluation is not None:
            raise ValueError("candidate_experiment_blocked_basis_evaluation_not_absent")
    expected = (
        origin.tenant_id,
        origin.cell_id,
        origin.run_id,
        origin.source_job_id,
        action.action_job_id,
        action.action_generation,
        origin.route_id,
        origin.policy_scope.design_problem_ref,
        origin.policy_scope.design_problem_basis_ref,
        expected_candidate_id,
        expected_candidate_hash,
    )
    if (
        identity != expected
        or (
            type(record)
            in {
                CandidateAcquisitionEvaluationDecision,
                CandidateAcquisitionRetainedContinuation,
                CandidateRetainedPortCapture,
            }
            and record.compiled_ref != str(origin.policy_scope.compiled_ref.artifact_id)
        )
        or record.candidate_action_ref != candidate_action_ref
        or record.candidate_source_ref != action.candidate_source_ref
    ):
        raise ValueError("candidate_experiment_evaluation_record_scope_mismatch")
    prior_owner = bridge._candidate_experiment_prior_owner(
        origin=origin,
        selection=selection,
    )
    profile = prior_owner.profile
    declaration = prior_owner.model_declaration
    intent_ref, intent = bridge._candidate_world_materialization_intent(
        origin=origin,
        candidate_action_ref=candidate_action_ref,
        configured_profile=profile,
        original_model_declaration=declaration,
        create=False,
    )
    if type(record) is CandidateAcquisitionEvaluationBasis:
        basis = record
    elif type(record) is CandidateAcquisitionEvaluationDecision:
        basis_ref = record.current_basis_ref
        basis = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        if (
            type(basis) is not CandidateAcquisitionEvaluationBasis
            or basis.basis_role != "prospective"
            or not _candidate_ref_same(basis.candidate_action_ref, candidate_action_ref)
            or not _candidate_ref_same(basis.candidate_source_ref, action.candidate_source_ref)
            or not _candidate_ref_same(
                basis.candidate_world_intent_ref, record.candidate_world_intent_ref
            )
        ):
            raise ValueError("candidate_experiment_decision_current_basis_not_established")
        _require_candidate_experiment_evaluation_record_scope(
            bridge=bridge,
            origin=origin,
            pending_phase_ref=pending_phase_ref,
            candidate_action_ref=candidate_action_ref,
            record=basis,
        )
    else:
        selected_decision = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=record.evaluation_decision_ref,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        basis = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=record.current_basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        if (
            type(selected_decision) is not CandidateAcquisitionEvaluationDecision
            or type(basis) is not CandidateAcquisitionEvaluationBasis
            or not _candidate_ref_same(selected_decision.candidate_action_ref, candidate_action_ref)
            or not _candidate_ref_same(
                selected_decision.current_basis_ref, record.current_basis_ref
            )
            or not _candidate_ref_same(selected_decision.candidate_world_intent_ref, intent_ref)
            or not _candidate_ref_same(
                selected_decision.candidate_source_ref, action.candidate_source_ref
            )
            or not _candidate_model_values_same(
                selected_decision.prior_evaluation,
                record.retained_evaluation,
            )
            or not _candidate_ref_same(
                selected_decision.prior_basis_ref,
                record.retained_evaluation.basis_ref,
            )
        ):
            raise ValueError("candidate_experiment_retained_record_decision_mismatch")
        _require_candidate_experiment_evaluation_record_scope(
            bridge=bridge,
            origin=origin,
            pending_phase_ref=pending_phase_ref,
            candidate_action_ref=candidate_action_ref,
            record=selected_decision,
        )
        _require_candidate_experiment_evaluation_record_scope(
            bridge=bridge,
            origin=origin,
            pending_phase_ref=pending_phase_ref,
            candidate_action_ref=candidate_action_ref,
            record=basis,
        )
        if not _candidate_model_values_same(
            selected_decision.prior_evaluation,
            record.retained_evaluation,
        ):
            raise ValueError("candidate_experiment_retained_record_prior_mismatch")
    if (
        not _candidate_ref_same(record.candidate_world_intent_ref, intent_ref)
        or basis.preparation_inputs.configured_profile != profile
        or basis.preparation_inputs.original_model_declaration != declaration
        or basis.preparation_inputs.transaction_time != intent.transaction_time
    ):
        raise ValueError("candidate_experiment_evaluation_record_intent_mismatch")
    return action


def _read_candidate_experiment_selected_reentry(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    candidate_action_ref: ArtifactRef,
    receipt_ref: ArtifactRef,
) -> object:
    """Replay the selected reentry artifact under its action-derived event owner."""
    import hashlib

    from polisyos.core import canon
    from polisyos.runtime.quality.candidate_source_reentry_history import (
        verify_candidate_experiment_source_reentry_history,
    )

    identity = hashlib.sha256(
        canon.to_canonical_bytes(candidate_action_ref.model_dump(mode="json"))
    ).hexdigest()
    events = bridge.event_log.list_events(
        event_id="evt_candidate_source_reentry_" + identity,
        limit=2,
    )
    if (
        receipt_ref.kind != "runtime_quality.candidate_source_reentry_receipt"
        or len(events) != 1
        or tuple(events[0].event.artifact_refs) != (str(receipt_ref.artifact_id),)
    ):
        raise ValueError("candidate_experiment_selected_reentry_event_not_established")
    return verify_candidate_experiment_source_reentry_history(
        bridge=bridge,
        origin=origin,
        receipt_ref=receipt_ref,
        expected_selected_action_ref=candidate_action_ref,
    )


def _candidate_experiment_decision_for_recovery(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    pending_phase_ref: str,
    candidate_action_ref: ArtifactRef,
) -> tuple[ArtifactRef, CandidateAcquisitionEvaluationDecision] | None:
    """Read one saved decision through its action-scoped event and pointer owner."""
    from polisyos.runtime.quality.acquisition_evaluation import (
        PRODUCER,
        _candidate_evaluation_role_event_id,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _candidate_experiment_source_selection,
    )

    event_id = _candidate_evaluation_role_event_id(candidate_action_ref, "decision")
    selection = _candidate_experiment_source_selection(bridge, origin)
    overlay_path, _ = bridge._paths(selection, create=False)
    pointer = overlay_path.parent / (event_id + ".selected.json")
    operation = overlay_path.parent / (event_id + ".lock-target")

    def read_selected(ref: ArtifactRef) -> CandidateAcquisitionEvaluationDecision:
        value = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=ref,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        if (
            type(value) is not CandidateAcquisitionEvaluationDecision
            or _candidate_evaluation_role_event_id(value.candidate_action_ref, "decision")
            != event_id
        ):
            raise ValueError("candidate_experiment_decision_recovery_record_mismatch")
        _require_candidate_experiment_evaluation_record_scope(
            bridge=bridge,
            origin=origin,
            pending_phase_ref=pending_phase_ref,
            candidate_action_ref=candidate_action_ref,
            record=value,
        )
        return value

    with data_forge_read_api.catalog.acquisition_overlay_admission_fence(operation):
        events = bridge.event_log.list_events(event_id=event_id, limit=2)
        if len(events) > 1:
            raise ValueError("candidate_experiment_decision_recovery_ambiguous")
        if not events:
            if pointer.exists():
                raise ValueError("candidate_experiment_decision_recovery_event_missing")
            return None
        refs = tuple(events[0].event.artifact_refs)
        if len(refs) != 1:
            raise ValueError("candidate_experiment_decision_recovery_ref_unresolved")
        if pointer.exists():
            selected = bridge._read_candidate_world_pointer(
                pointer,
                candidate_action_ref=candidate_action_ref,
                expected_kind=CandidateAcquisitionEvaluationDecision.ARTIFACT_KIND,
            )
            if str(selected.artifact_id) != refs[0]:
                raise ValueError("candidate_experiment_decision_recovery_pointer_mismatch")
            value = read_selected(selected)
        else:
            selected, value = bridge._recover_unique_candidate_owner_view(
                artifact_ref=refs[0],
                kind=CandidateAcquisitionEvaluationDecision.ARTIFACT_KIND,
                schema=CandidateAcquisitionEvaluationDecision.ARTIFACT_SCHEMA_NAME,
                version="1.0",
                record_type=CandidateAcquisitionEvaluationDecision,
                verify=read_selected,
                producer_component=PRODUCER,
            )
        return selected, value


def _select_candidate_experiment_evaluation_artifact(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    pending_phase_ref: str,
    candidate_action_ref: ArtifactRef,
    record: CandidateAcquisitionEvaluationBasis
    | CandidateAcquisitionEvaluationDecision
    | CandidateAcquisitionRetainedContinuation
    | CandidateRetainedPortCapture,
    selected_reentry_ref: ArtifactRef | None = None,
) -> ArtifactRef:
    """Persist or recover one experiment basis/decision under its actual action owner."""
    from polisyos.runtime.quality.acquisition_evaluation import (
        PRODUCER,
        _candidate_evaluation_event_id,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _candidate_experiment_source_selection,
    )

    action = _require_candidate_experiment_evaluation_record_scope(
        bridge=bridge,
        origin=origin,
        pending_phase_ref=pending_phase_ref,
        candidate_action_ref=candidate_action_ref,
        record=record,
        selected_reentry_ref=selected_reentry_ref,
    )
    selection = _candidate_experiment_source_selection(bridge, origin)
    overlay_path, _ = bridge._paths(selection, create=False)
    event_id = _candidate_evaluation_event_id(record)
    pointer = overlay_path.parent / (event_id + ".selected.json")
    operation = overlay_path.parent / (event_id + ".lock-target")

    def read_selected(ref: ArtifactRef) -> object:
        value = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=ref,
            record_type=type(record),
        )
        if type(value) is not type(record) or exact_n5_content_bytes(value) != (
            exact_n5_content_bytes(record)
        ):
            raise ValueError("candidate_experiment_evaluation_selected_record_changed")
        _require_candidate_experiment_evaluation_record_scope(
            bridge=bridge,
            origin=origin,
            pending_phase_ref=pending_phase_ref,
            candidate_action_ref=candidate_action_ref,
            record=value,
            selected_reentry_ref=selected_reentry_ref,
        )
        return value

    with data_forge_read_api.catalog.acquisition_overlay_admission_fence(operation):
        events = bridge.event_log.list_events(event_id=event_id, limit=2)
        pointer_write_required = False
        if len(events) > 1:
            raise ValueError("candidate_experiment_evaluation_event_ambiguous")
        if events:
            refs = tuple(events[0].event.artifact_refs)
            if len(refs) != 1:
                raise ValueError("candidate_experiment_evaluation_event_unresolved")
            if pointer.exists():
                selected = bridge._read_candidate_world_pointer(
                    pointer,
                    candidate_action_ref=candidate_action_ref,
                    expected_kind=record.ARTIFACT_KIND,
                )
                if str(selected.artifact_id) != refs[0]:
                    raise ValueError("candidate_experiment_evaluation_pointer_event_mismatch")
                read_selected(selected)
            else:
                selected, _ = bridge._recover_unique_candidate_owner_view(
                    artifact_ref=refs[0],
                    kind=record.ARTIFACT_KIND,
                    schema=record.ARTIFACT_SCHEMA_NAME,
                    version="1.0",
                    record_type=type(record),
                    verify=read_selected,
                    producer_component=PRODUCER,
                )
                pointer_write_required = True
        else:
            if pointer.exists():
                raise ValueError("candidate_experiment_evaluation_event_missing")
            selected = persist_acquisition_evaluation_artifact(
                store=bridge.artifact_store,
                event_log=bridge.event_log,
                record=record,
            )
            pointer_write_required = True
        if pointer_write_required:
            if (
                _require_candidate_experiment_evaluation_record_scope(
                    bridge=bridge,
                    origin=origin,
                    pending_phase_ref=pending_phase_ref,
                    candidate_action_ref=candidate_action_ref,
                    record=record,
                    selected_reentry_ref=selected_reentry_ref,
                )
                != action
            ):
                raise ValueError("candidate_experiment_evaluation_action_changed")
            bridge._write_candidate_world_pointer(
                pointer,
                candidate_action_ref=candidate_action_ref,
                selected_ref=selected,
            )
        read_selected(selected)
        return selected


def dispatch_candidate_experiment_evaluation(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
) -> AcquisitionActionHeadRecord:
    """Run one current first-N5 candidate experiment through its actual terminal.

    This is the unpriced, candidate-only counterpart to the costed dispatcher.
    It shares the same basis comparator and issuers, while keeping experiment
    phase, source, budget, and terminal ownership explicitly typed.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import (
        ControlPlaneService,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionEvaluationFrontierKey,
    )
    from polisyos.runtime.quality.acquisition_evaluation import (
        issue_candidate_acquisition_evaluation_basis,
        issue_candidate_acquisition_evaluation_decision,
        resolve_selected_acquisition_evaluation_parts,
    )
    from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
        candidate_experiment_reentry_fence,
        prepare_candidate_experiment_reentry_owner,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        AcquisitionCandidateExperimentTerminalReceipt,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _current_candidate_experiment_reentry_action,
        _select_current_candidate_experiment_outcome,
    )
    from polisyos.runtime.quality.candidate_source_basis import (
        _candidate_source_predecessors_for_verified_experiment_origin,
        prepare_live_candidate_experiment_source_basis_values,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    sink = bridge.action_head_sink
    service = bridge._source_control_service
    if (
        type(bridge) is not AcquisitionWorldGrowthBridge
        or type(origin) is not VerifiedCandidateExperimentOrigin
        or sink is None
        or type(service) is not ControlPlaneService
        or service._artifact_store is not bridge.artifact_store
        or service._control_store is not bridge.control_store
    ):
        raise ValueError("candidate_experiment_evaluation_owner_not_composed")

    def current_pending_experiment(
        receipt_ref: str | None = None,
    ) -> VerifiedAcquisitionActionOutcome:
        outcomes = sink.experiment_action_outcomes(
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            source_job_id=origin.source_job_id,
            route_id=origin.route_id,
            verified_origin=origin,
        )
        return _select_current_candidate_experiment_outcome(
            outcomes,
            origin=origin,
            action_job_id=service._control_store.current_execution_job_admission().job.job_id,
            action_generation=len(origin.candidate_terminal_history_chain) + 1,
            receipt_ref=receipt_ref,
            required_phase="candidate_input_reentry_pending",
        )

    snapshot = current_pending_experiment()
    if type(snapshot.latest_receipt) is not AcquisitionCandidateExperimentPhaseReceipt:
        raise ValueError("candidate_experiment_evaluation_pending_action_not_established")
    pending = snapshot.latest_receipt
    pending_phase_ref = snapshot.head.receipt_ref
    action_ref = pending.candidate_receipt_ref
    if action_ref is None:
        raise ValueError("candidate_experiment_evaluation_action_missing")
    selection, _phase, _admission, action = _current_candidate_experiment_reentry_action(
        bridge,
        origin,
        pending_phase_ref,
        action_ref,
    )
    prior_owner = bridge._candidate_experiment_prior_owner(origin=origin, selection=selection)

    prepared, intent_ref, intent = prepare_live_candidate_experiment_source_basis_values(
        bridge=bridge,
        origin=origin,
        candidate_action_ref=action_ref,
        pending_phase_ref=pending_phase_ref,
    )
    if (
        prepared.predicate_provenance != "recomputed"
        or prepared.reason_codes
        or prepared.inputs is None
        or intent_ref is None
        or intent is None
    ):
        raise ValueError("candidate_experiment_evaluation_preparation_not_established")
    window = bridge.resolve_candidate_experiment_reentry_budget_window(
        origin=origin,
        candidate_action_ref=action_ref,
    )
    configuration = prepare_joint_simulation_configuration()
    frontier_key = AcquisitionEvaluationFrontierKey(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        source_job_id=origin.source_job_id,
        design_problem_ref=origin.policy_scope.design_problem_ref,
        candidate_id=origin.policy_scope.candidate_id,
    )
    latest_history = _candidate_experiment_verified_prior_history(
        bridge=bridge,
        origin=origin,
    )
    if action.action_generation != len(origin.candidate_terminal_history_chain) + 1:
        raise ValueError("candidate_experiment_evaluation_generation_not_contiguous")
    frontier = bridge.control_store.read_acquisition_evaluation_frontier(frontier_key)
    prior = prior_owner.selected_evaluation
    previous_basis = None
    previous_basis_ref = None
    candidate_only_prior = latest_history is not None and latest_history.frontier_after is None
    if latest_history is None:
        # The original source may already have N5. It remains numerical input;
        # only a committed experiment prefix can establish a retained basis.
        if frontier is not None:
            raise ValueError("candidate_experiment_evaluation_unowned_prior_frontier")
    elif not candidate_only_prior:
        if (
            latest_history.frontier_after is None
            or latest_history.selected_basis is None
            or latest_history.evaluation is None
            or prior is None
            or frontier != latest_history.frontier_after
        ):
            raise ValueError("candidate_experiment_evaluation_prior_not_selected")
        previous_basis = latest_history.selected_basis
        previous_basis_ref = latest_history.terminal.selected_basis_ref
        expected_prior = prior.selected.model_copy(update={"basis_ref": previous_basis_ref})
        if not _candidate_model_values_same(
            latest_history.terminal.selected_evaluation,
            expected_prior,
        ) or not _candidate_model_values_same(latest_history.evaluation, prior):
            raise ValueError("candidate_experiment_evaluation_prior_witness_changed")
    expected_frontier = latest_history.frontier_after if latest_history is not None else None
    if frontier != expected_frontier:
        raise ValueError("candidate_experiment_evaluation_frontier_not_current")
    predecessors = _candidate_source_predecessors_for_verified_experiment_origin(
        store=bridge.artifact_store,
        origin=origin,
    )
    values, reasons = recompute_candidate_acquisition_basis_values(
        artifact_store=bridge.artifact_store,
        problem=origin.design_problem_basis,
        preparation_inputs=prepared.inputs,
        predecessors=predecessors,
        prior=prior,
        prepared_n5_configuration=configuration,
        fresh_limit_usd=window.fresh_limit_usd,
        global_limit_usd=window.global_limit_usd,
    )
    if latest_history is not None and not candidate_only_prior and reasons:
        raise ValueError("candidate_experiment_evaluation_current_basis_not_established")
    profile = prepared.inputs.configured_profile
    limitations = tuple(
        dict.fromkeys(
            (
                *action.limitations,
                *profile.limitations,
                *_candidate_experiment_inherited_limitations(origin),
            )
        )
    )
    if not limitations:
        raise ValueError("candidate_experiment_evaluation_limitations_not_established")
    common = {
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "source_job_id": origin.source_job_id,
        "action_job_id": action.action_job_id,
        "action_generation": action.action_generation,
        "route_id": origin.route_id,
        "design_problem_ref": origin.policy_scope.design_problem_ref,
        "design_problem_basis_ref": origin.policy_scope.design_problem_basis_ref,
        "candidate_id": origin.effective_source_cycle.selected_candidate_ref,
        "source_candidate_content_hash": (
            origin.effective_source_cycle.selected_candidate_content_hash
        ),
        "candidate_action_ref": action_ref,
        "candidate_world_intent_ref": intent_ref,
        "candidate_source_ref": action.candidate_source_ref,
        "preparation_inputs": prepared.inputs,
        "prepared_n5_configuration": configuration,
    }
    current = issue_candidate_acquisition_evaluation_basis(
        **common,
        basis_role="prospective",
        values=values,
        predicate_provenance="not_established" if reasons else "recomputed",
        reason_codes=reasons,
        limitations=limitations,
    )
    current_ref = _select_candidate_experiment_evaluation_artifact(
        bridge=bridge,
        origin=origin,
        pending_phase_ref=pending_phase_ref,
        candidate_action_ref=action_ref,
        record=current,
    )
    comparison: _ComparisonResult
    if latest_history is None or candidate_only_prior:
        comparison = "not_established"
        comparison_provenance: Literal["recomputed", "not_established"] = "not_established"
        comparison_reasons = tuple(
            dict.fromkeys(("candidate_evaluation_prior_basis_not_established", *reasons))
        )
        if candidate_only_prior:
            changed = _candidate_experiment_unselected_input_changed(
                bridge=bridge, origin=origin, prior=prior, prepared=prepared
            )
            input_reason = (
                "candidate_experiment_changed_input"
                if changed
                else "candidate_experiment_input_change_not_established"
            )
            comparison_reasons = tuple(
                dict.fromkeys(
                    ("candidate_evaluation_prior_basis_not_established", input_reason, *reasons)
                )
            )
        expected_prior = None
        expected_frontier_revision = 0
        expected_frontier_ref = None
    else:
        if previous_basis is None or previous_basis_ref is None or frontier is None:
            raise ValueError("candidate_experiment_evaluation_prior_not_established")
        comparison = (
            "equivalent" if basis_exact_values_equal(previous_basis, current) else "different"
        )
        comparison_provenance = "recomputed"
        comparison_reasons = ()
        expected_prior = prior.selected.model_copy(update={"basis_ref": previous_basis_ref})
        expected_frontier_revision = frontier.revision
        expected_frontier_ref = frontier.frontier_ref
    saved_decision_selection = _candidate_experiment_decision_for_recovery(
        bridge=bridge,
        origin=origin,
        pending_phase_ref=pending_phase_ref,
        candidate_action_ref=action_ref,
    )
    saved_decision = saved_decision_selection[1] if saved_decision_selection else None
    decision = issue_candidate_acquisition_evaluation_decision(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        action_job_id=action.action_job_id,
        action_generation=action.action_generation,
        route_id=origin.route_id,
        compiled_ref=str(origin.policy_scope.compiled_ref.artifact_id),
        design_problem_ref=origin.policy_scope.design_problem_ref,
        design_problem_basis_ref=origin.policy_scope.design_problem_basis_ref,
        candidate_id=origin.effective_source_cycle.selected_candidate_ref,
        source_candidate_content_hash=(
            origin.effective_source_cycle.selected_candidate_content_hash
        ),
        candidate_action_ref=action_ref,
        candidate_world_intent_ref=intent_ref,
        candidate_source_ref=action.candidate_source_ref,
        current_basis_ref=current_ref,
        prior_basis_ref=previous_basis_ref,
        prior_evaluation=expected_prior,
        comparison_result=comparison,
        predicate_provenance=comparison_provenance,
        reason_codes=comparison_reasons,
        expected_frontier_revision=expected_frontier_revision,
        expected_frontier_ref=expected_frontier_ref,
        generated_at=(
            saved_decision.generated_at
            if saved_decision is not None
            else datetime.now(UTC).isoformat()
        ),
    )
    if saved_decision is not None and not _candidate_model_values_same(saved_decision, decision):
        raise ValueError("candidate_experiment_decision_recovery_changed")
    decision_ref = _select_candidate_experiment_evaluation_artifact(
        bridge=bridge,
        origin=origin,
        pending_phase_ref=pending_phase_ref,
        candidate_action_ref=action_ref,
        record=decision,
    )

    evaluation_owner = CandidateExperimentEvaluationCurrentOwner(
        bridge=bridge,
        origin=origin,
        selection=selection,
        pending_phase_ref=pending_phase_ref,
        action_phase_ref=action.action_phase_ref,
        candidate_action_ref=action_ref,
        candidate_world_intent_ref=intent_ref,
        current_basis_ref=current_ref,
        decision_ref=decision_ref,
        prior_owner=prior_owner,
        prepared_n5_configuration=configuration,
        budget_window=window,
        comparison=comparison,
    )
    evaluation_owner.revalidate()

    if (
        candidate_only_prior
        and "candidate_experiment_input_change_not_established" in comparison_reasons
    ):
        terminal = AcquisitionCandidateExperimentTerminalReceipt(
            receipt_id=pending.job_id + ".candidate-experiment.terminal",
            tenant_id=pending.tenant_id,
            cell_id=pending.cell_id,
            run_id=pending.run_id,
            source_job_id=pending.source_job_id,
            route_id=pending.route_id,
            action_generation=pending.action_generation,
            job_id=pending.job_id,
            source_payload_ref=pending.source_payload_ref,
            capability_manifest_ref=pending.capability_manifest_ref,
            request_content_hash=pending.request_content_hash,
            policy_scope=pending.policy_scope,
            policy_ref=pending.policy_ref,
            authority_decision_ref=pending.authority_decision_ref,
            voi_decision=pending.voi_decision,
            monetary_cost="not_established",
            information_value="not_established",
            observed_data_authority=False,
            publication_authority=False,
            predecessor_receipt_ref=pending_phase_ref,
            owner_receipt_refs=tuple(
                sorted({str(action_ref.artifact_id), str(decision_ref.artifact_id)})
            ),
            terminal_outcome="candidate_blocked",
            candidate_action_ref=action_ref,
            blocker_ref=decision_ref,
            blocker_reason="candidate_experiment_input_change_not_established",
            generated_at=datetime.now(UTC),
        )
        evaluation_owner.revalidate()
    elif comparison == "equivalent":
        from polisyos.core.artifacts import load_core_json_artifact
        from polisyos.runtime.quality.generation_cycle import (
            GenerationCycleController,
            _RetainedCheapProjection,
        )
        from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope

        if (
            expected_prior is None
            or previous_basis_ref is None
            or prior is None
            or bridge.promotion_runtime is None
            or bridge.promotion_runtime.store is not bridge.artifact_store
            or service.catalog_serving_source is None
        ):
            raise ValueError("candidate_experiment_retained_owner_not_composed")
        payload = load_core_json_artifact(bridge.artifact_store, origin.source_payload_ref)
        models = payload.get("llm_models")
        if not isinstance(models, list) or not models or not isinstance(models[0], str):
            raise ValueError("candidate_experiment_retained_model_not_configured")
        with catalog_serving_source_scope(service.catalog_serving_source):
            evaluation_owner.revalidate()
            controller = GenerationCycleController(
                repo_root=bridge.repo_root,
                model_id=models[0],
                promotion_runtime=bridge.promotion_runtime,
                artifact_store=bridge.artifact_store,
                catalog_serving_source=service.catalog_serving_source,
                capability_resolver=service._registry_providers.capability_resolver,
                cycle_substrate_context=prior.handoff.context,
                candidate_simulation_handoff=prior.handoff,
                candidate_simulation_currentness_resolver=evaluation_owner.currentness_resolver,
                _prepared_n5_configuration=configuration,
            )
            current = controller._candidate_retained_configured_cheap_continuation(
                owner=evaluation_owner
            )
            if type(current) is not _RetainedCheapProjection:
                raise ValueError("candidate_experiment_retained_current_work_not_established")
            continuation_ref = _persist_candidate_current_continuation(
                owner=evaluation_owner,
                decision=decision,
                current=current,
            )
        terminal = AcquisitionCandidateExperimentTerminalReceipt(
            receipt_id=pending.job_id + ".candidate-experiment.terminal",
            tenant_id=pending.tenant_id,
            cell_id=pending.cell_id,
            run_id=pending.run_id,
            source_job_id=pending.source_job_id,
            route_id=pending.route_id,
            action_generation=pending.action_generation,
            job_id=pending.job_id,
            source_payload_ref=pending.source_payload_ref,
            capability_manifest_ref=pending.capability_manifest_ref,
            request_content_hash=pending.request_content_hash,
            policy_scope=pending.policy_scope,
            policy_ref=pending.policy_ref,
            authority_decision_ref=pending.authority_decision_ref,
            voi_decision=pending.voi_decision,
            monetary_cost="not_established",
            information_value="not_established",
            observed_data_authority=False,
            publication_authority=False,
            predecessor_receipt_ref=pending_phase_ref,
            owner_receipt_refs=tuple(
                sorted({str(action_ref.artifact_id), str(decision_ref.artifact_id)})
            ),
            terminal_outcome="candidate_evaluation_retained",
            candidate_action_ref=action_ref,
            candidate_reentry_ref=None,
            evaluation_decision_ref=decision_ref,
            selected_basis_ref=previous_basis_ref,
            selected_evaluation_witness_ref=expected_prior.n5_execution_ref,
            selected_evaluation=expected_prior,
            current_continuation_ref=continuation_ref,
            blocker_ref=None,
            blocker_reason=None,
            generated_at=datetime.now(UTC),
        )
        evaluation_owner.revalidate()
    else:
        if comparison not in {"different", "not_established"}:
            raise ValueError("candidate_experiment_evaluation_comparison_not_established")
        # A different complete basis reaches the existing owner-backed N5 path.
        reentry_ref, reentry = bridge.prepare_candidate_experiment_source_reentry(
            origin=origin,
            candidate_action_ref=action_ref,
            prepared_n5_configuration=configuration,
        )
        evaluation = (
            resolve_selected_acquisition_evaluation_parts(
                artifact_store=bridge.artifact_store,
                control_store=bridge.control_store,
                tenant_id=origin.tenant_id,
                cell_id=origin.cell_id,
                run_id=origin.run_id,
                generation_run=reentry.continued_generation_run,
                source_cycle=reentry.new_cycle,
                design_problem_ref=origin.policy_scope.design_problem_ref,
            )
            if reentry.new_cycle.simulation.status == "joint_simulated"
            else None
        )
        selected_values, selected_reasons = recompute_candidate_acquisition_basis_values(
            artifact_store=bridge.artifact_store,
            problem=origin.design_problem_basis,
            preparation_inputs=prepared.inputs,
            predecessors=predecessors,
            prior=evaluation,
            prepared_n5_configuration=configuration,
            fresh_limit_usd=window.fresh_limit_usd,
            global_limit_usd=window.global_limit_usd,
            selected_data_snapshot_ref=reentry.data_snapshot_ref,
            selected_world_model_ref=reentry.world_model_ref,
        )
        selected_basis_is_evaluated = evaluation is not None and not selected_reasons
        actual_basis = issue_candidate_acquisition_evaluation_basis(
            **common,
            basis_role="evaluated" if selected_basis_is_evaluated else "blocked",
            values=selected_values,
            predicate_provenance=(
                "recomputed" if selected_basis_is_evaluated else "not_established"
            ),
            reason_codes=(
                selected_reasons
                if selected_reasons
                else (
                    () if selected_basis_is_evaluated else ("candidate_reentry_n5_not_established",)
                )
            ),
            limitations=tuple(dict.fromkeys((*current.limitations, *reentry.limitations))),
            selected_data_snapshot_ref=reentry.data_snapshot_ref,
            selected_world_model_ref=reentry.world_model_ref,
            evaluation=evaluation.selected if selected_basis_is_evaluated and evaluation else None,
        )
        actual_ref = _select_candidate_experiment_evaluation_artifact(
            bridge=bridge,
            origin=origin,
            pending_phase_ref=pending_phase_ref,
            candidate_action_ref=action_ref,
            record=actual_basis,
            selected_reentry_ref=reentry_ref,
        )
        selected_evaluation = (
            evaluation.selected.model_copy(update={"basis_ref": actual_ref})
            if selected_basis_is_evaluated and evaluation
            else None
        )
        witness = (
            evaluation.selected.n5_execution_ref
            if selected_basis_is_evaluated and evaluation
            else reentry_ref
        )
        terminal = AcquisitionCandidateExperimentTerminalReceipt(
            receipt_id=pending.job_id + ".candidate-experiment.terminal",
            tenant_id=pending.tenant_id,
            cell_id=pending.cell_id,
            run_id=pending.run_id,
            source_job_id=pending.source_job_id,
            route_id=pending.route_id,
            action_generation=pending.action_generation,
            job_id=pending.job_id,
            source_payload_ref=pending.source_payload_ref,
            capability_manifest_ref=pending.capability_manifest_ref,
            request_content_hash=pending.request_content_hash,
            policy_scope=pending.policy_scope,
            policy_ref=pending.policy_ref,
            authority_decision_ref=pending.authority_decision_ref,
            voi_decision=pending.voi_decision,
            monetary_cost="not_established",
            information_value="not_established",
            observed_data_authority=False,
            publication_authority=False,
            predecessor_receipt_ref=pending_phase_ref,
            owner_receipt_refs=tuple(
                sorted({str(action_ref.artifact_id), str(decision_ref.artifact_id)})
            ),
            terminal_outcome="candidate_reentry_completed",
            candidate_action_ref=action_ref,
            candidate_reentry_ref=reentry_ref,
            evaluation_decision_ref=decision_ref,
            selected_basis_ref=actual_ref,
            selected_evaluation_witness_ref=witness,
            selected_evaluation=selected_evaluation,
            current_continuation_ref=None,
            blocker_ref=None,
            blocker_reason=None,
            generated_at=datetime.now(UTC),
        )
    if (
        sink.get_head(terminal) != snapshot.head
        or current_pending_experiment(pending_phase_ref) != snapshot
    ):
        raise ValueError("candidate_experiment_evaluation_pending_head_changed")
    budget_state, budget_observation = evaluation_owner.current_budget_snapshot()
    if (
        budget_state.limits.get("run") is None
        or budget_state.limits["run"].max_usd != window.effective_limit_usd
        or budget_observation.run_binding != window.scope.run_binding
    ):
        raise ValueError("candidate_experiment_evaluation_budget_not_established")
    owner = prepare_candidate_experiment_reentry_owner(
        bridge=bridge,
        origin=origin,
        terminal=terminal,
        predecessor_head=snapshot.head,
        candidate_action_ref=action_ref,
        action_phase_ref=action.action_phase_ref,
        evaluation_owner=evaluation_owner,
        budget_state=budget_state,
        reentry_budget_scope=window.scope,
        budget_window=window,
    )
    if owner.budget_window != window or owner.evaluation_owner is not evaluation_owner:
        raise ValueError("candidate_experiment_evaluation_owner_changed")
    recovered_terminal = sink.recover_candidate_experiment_terminal(
        terminal,
        predecessor_head=snapshot.head,
        owner=owner,
    )
    if recovered_terminal is not None:
        from polisyos.core.artifacts import ArtifactRef

        if (
            type(recovered_terminal) is not tuple
            or len(recovered_terminal) != 2
            or type(recovered_terminal[0]) is not AcquisitionCandidateExperimentTerminalReceipt
            or type(recovered_terminal[1]) is not ArtifactRef
            or terminal.model_copy(update={"generated_at": recovered_terminal[0].generated_at})
            != recovered_terminal[0]
        ):
            raise ValueError("candidate_experiment_terminal_recovery_changed")
        terminal = recovered_terminal[0]
        owner = prepare_candidate_experiment_reentry_owner(
            bridge=bridge,
            origin=origin,
            terminal=terminal,
            predecessor_head=snapshot.head,
            candidate_action_ref=action_ref,
            action_phase_ref=action.action_phase_ref,
            evaluation_owner=evaluation_owner,
            budget_state=budget_state,
            reentry_budget_scope=window.scope,
            budget_window=window,
        )
        if (
            owner.terminal != terminal
            or owner.budget_window != window
            or owner.evaluation_owner is not evaluation_owner
        ):
            raise ValueError("candidate_experiment_terminal_recovery_owner_changed")
    with candidate_experiment_reentry_fence(owner):
        if current_pending_experiment(pending_phase_ref) != snapshot:
            raise ValueError("candidate_experiment_evaluation_pending_changed")
        return sink.persist_terminal(terminal)


def _terminal_record(
    selection: _CurrentSelection,
    *,
    predecessor_ref: str,
    owner_refs: tuple[str, ...],
    decision_ref: ArtifactRef,
    outcome: _TerminalOutcome,
    selected_basis_ref: ArtifactRef,
    selected_evaluation: AcquisitionSelectedEvaluation | None,
    selected_witness_ref: ArtifactRef,
    reentry_ref: str | None = None,
    continuation_ref: ArtifactRef | None = None,
) -> AcquisitionRouteLoopReceiptV2:
    phase = selection.phase
    return AcquisitionRouteLoopReceiptV2(
        receipt_id=selection.action_job_id + ".terminal.v2",
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        route_id=phase.route_id,
        action_generation=phase.action_generation,
        job_id=phase.job_id,
        compiled_ref=phase.compiled_ref,
        planner_report_hash=phase.planner_report_hash,
        cost_basis_hash=phase.cost_basis_hash,
        decision_ref=phase.decision_ref,
        terminal_outcome=outcome,
        predecessor_receipt_ref=predecessor_ref,
        owner_receipt_refs=owner_refs,
        reentry_receipt_ref=reentry_ref,
        evaluation_decision_ref=decision_ref,
        selected_basis_ref=selected_basis_ref,
        selected_evaluation_witness_ref=selected_witness_ref,
        selected_evaluation=selected_evaluation,
        current_continuation_ref=continuation_ref,
        generated_at=datetime.now(UTC),
    )


def _prospective_model_transition(
    bridge: AcquisitionWorldGrowthBridge,
    *,
    decision_ref: ArtifactRef,
    decision: AcquisitionEvaluationDecision,
) -> AcquisitionEvidenceTransitionDispatch | None:
    """Route only an owner-recomputed coefficient change to the existing verifier."""
    from polisyos.runtime.quality.acquisition_evidence_transition import (
        AcquisitionEvidenceTransitionBasis,
        AcquisitionModelTransitionIntent,
        dispatch_acquisition_evidence_transition,
    )
    from polisyos.runtime.quality.acquisition_model_transition import (
        is_prospective_candidate_model_revision,
    )

    if (
        decision.comparison_result != "different"
        or decision.predicate_provenance != "recomputed"
        or decision.reason_codes
        or decision.prior_basis_ref is None
        or decision.prior_evaluation is None
    ):
        return None
    previous = read_acquisition_evaluation_artifact(
        store=bridge.artifact_store,
        event_log=bridge.event_log,
        ref=decision.prior_basis_ref,
        record_type=AcquisitionEvaluationBasis,
    )
    prospective = read_acquisition_evaluation_artifact(
        store=bridge.artifact_store,
        event_log=bridge.event_log,
        ref=decision.current_basis_ref,
        record_type=AcquisitionEvaluationBasis,
    )
    if not is_prospective_candidate_model_revision(previous, prospective):
        return None
    return dispatch_acquisition_evidence_transition(
        AcquisitionModelTransitionIntent(
            purpose="Re-evaluate the selected candidate after an owned model coefficient change.",
            dependency_basis=AcquisitionEvidenceTransitionBasis(
                evaluation_decision_ref=decision_ref,
                previous_basis_ref=decision.prior_basis_ref,
                prospective_basis_ref=decision.current_basis_ref,
            ),
        )
    )


def _current_cheap_continuation(
    bridge: AcquisitionWorldGrowthBridge,
    selection: _CurrentSelection,
    prior: ResolvedAcquisitionEvaluation,
    current_basis_ref: ArtifactRef,
) -> object:
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController
    from polisyos.scientist import BudgetState

    payload = load_core_json_artifact(bridge.artifact_store, selection.closure.source_payload_ref)
    models = payload.get("llm_models")
    model_id = str(models[0]) if isinstance(models, list) and models else None
    if model_id is None:
        raise ValueError("acquisition_retained_current_model_unconfigured")
    controller = GenerationCycleController(
        repo_root=bridge.repo_root,
        model_id=model_id,
        promotion_runtime=bridge.promotion_runtime,
        cycle_substrate_context=prior.handoff.context,
        candidate_simulation_handoff=prior.handoff,
        _prepared_n5_configuration=selection.prepared.n5_execution_configuration,
    )
    controller._acquisition_retention_current_owner = AcquisitionEvaluationCurrentOwner(
        bridge=bridge,
        current_basis_ref=current_basis_ref,
        selection=selection,
        prior=prior,
    )
    return controller._retained_configured_cheap_continuation(
        original_run=selection.closure.generation_run,
        source_cycle=selection.closure.source_cycle,
        problem=selection.closure.design_problem_basis,
        budget_state=BudgetState.model_validate(
            {
                "limits": {
                    "run": {
                        "key": "run",
                        "max_usd": selection.growth.selection.reentry_budget_usd,
                    }
                }
            }
        ),
        current_basis_ref=current_basis_ref,
        admitted_source_ref=selection.admitted_source_ref,
        growth_ref=selection.growth_ref,
    )


def _dispatch_candidate_retained_continuation(
    *,
    owner: CandidateAcquisitionEvaluationCurrentOwner,
    decision: CandidateAcquisitionEvaluationDecision,
    snapshot: VerifiedAcquisitionActionOutcome,
    pending: AcquisitionRoutePhaseReceipt,
) -> AcquisitionActionHeadRecord:
    """Produce and commit the fresh cheap reaction under the existing owner fence."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionCandidateRouteLoopReceipt
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        _RetainedCheapProjection,
    )
    from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope

    bridge = owner.bridge
    service = bridge._source_control_service
    sink = bridge.action_head_sink
    if (
        type(owner) is not CandidateAcquisitionEvaluationCurrentOwner
        or type(service) is not ControlPlaneService
        or sink is None
        or bridge.promotion_runtime is None
        or bridge.promotion_runtime.store is not bridge.artifact_store
        or service.catalog_serving_source is None
        or decision.prior_basis_ref is None
        or decision.prior_evaluation is None
    ):
        raise ValueError("candidate_retained_current_owner_not_composed")
    payload = load_core_json_artifact(bridge.artifact_store, owner.closure.source_payload_ref)
    models = payload.get("llm_models")
    if not isinstance(models, list) or not models or not isinstance(models[0], str):
        raise ValueError("candidate_retained_current_model_unconfigured")
    with catalog_serving_source_scope(service.catalog_serving_source):
        owner.revalidate()
        controller = GenerationCycleController(
            repo_root=bridge.repo_root,
            model_id=models[0],
            promotion_runtime=bridge.promotion_runtime,
            artifact_store=bridge.artifact_store,
            catalog_serving_source=service.catalog_serving_source,
            capability_resolver=service._registry_providers.capability_resolver,
            cycle_substrate_context=owner.prior.handoff.context,
            candidate_simulation_handoff=owner.prior.handoff,
            candidate_simulation_currentness_resolver=owner.currentness_resolver,
            _prepared_n5_configuration=owner.prepared_n5_configuration,
        )
        current = controller._candidate_retained_configured_cheap_continuation(owner=owner)
        if type(current) is not _RetainedCheapProjection:
            raise ValueError("candidate_evaluation_retained_current_work_not_established")
        continuation_ref = _persist_candidate_current_continuation(
            owner=owner, decision=decision, current=current
        )
        terminal = AcquisitionCandidateRouteLoopReceipt(
            receipt_id=pending.job_id + ".candidate-evaluation.terminal",
            tenant_id=pending.tenant_id,
            cell_id=pending.cell_id,
            run_id=pending.run_id,
            source_job_id=pending.source_job_id,
            route_id=pending.route_id,
            action_generation=pending.action_generation,
            job_id=pending.job_id,
            compiled_ref=pending.compiled_ref,
            planner_report_hash=pending.planner_report_hash,
            cost_basis_hash=pending.cost_basis_hash,
            decision_ref=pending.decision_ref,
            terminal_outcome="candidate_evaluation_retained",
            predecessor_receipt_ref=snapshot.head.receipt_ref,
            owner_receipt_refs=tuple(
                sorted({*pending.owner_receipt_refs, str(owner.decision_ref.artifact_id)})
            ),
            candidate_action_ref=owner.candidate_action_ref,
            evaluation_decision_ref=owner.decision_ref,
            selected_basis_ref=decision.prior_basis_ref,
            selected_evaluation_witness_ref=decision.prior_evaluation.n5_execution_ref,
            selected_evaluation=decision.prior_evaluation,
            current_continuation_ref=continuation_ref,
            generated_at=datetime.now(UTC),
        )
        owner.revalidate()
        latest = sink.current_action_outcome(
            tenant_id=owner.closure.tenant_id,
            cell_id=owner.closure.cell_id,
            run_id=owner.closure.run_id,
            source_job_id=owner.closure.source_job_id,
            route_id=owner.closure.route_id,
        )
        if latest is None or latest.head != snapshot.head or latest.latest_receipt != pending:
            raise ValueError("candidate_evaluation_dispatch_pending_changed")
        terminal = _candidate_terminal_intent_for_publication(
            marker=_candidate_terminal_marker(owner),
            expected=terminal,
            event_log=bridge.event_log,
            sink=sink,
        )
        with _candidate_terminal_scope(_CandidateTerminalScope(owner, terminal)):
            return sink.persist_terminal(terminal)


def _persist_current_continuation(
    bridge: AcquisitionWorldGrowthBridge,
    selection: _CurrentSelection,
    decision_ref: ArtifactRef,
    decision: AcquisitionEvaluationDecision,
    current: object,
) -> ArtifactRef:
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedContinuation,
        AcquisitionRetainedCurrentProjection,
    )
    from polisyos.runtime.quality.generation_cycle import _RetainedCheapProjection

    if type(current) is not _RetainedCheapProjection or decision.prior_evaluation is None:
        raise ValueError("acquisition_retained_current_continuation_not_established")
    route = current.current_route
    projection = AcquisitionRetainedCurrentProjection(
        source_cycle_index=current.source_cycle_index,
        selected_candidate_id=current.selected_candidate_id,
        selected_candidate_content_hash=current.selected_candidate_content_hash,
        grounding=current.grounding,
        value_port=current.value_port,
        execution_schedule=current.execution_schedule,
        terminal_kind=current.terminal_kind,
        voi_decision=current.voi_decision,
        revision_request=current.revision_request,
        counterexample=current.counterexample,
        refinement_decision=current.refinement_decision,
        search_iteration=current.search_iteration,
        current_planner_report=route.report if route else None,
        current_planner_report_ref=route.report_ref if route else None,
        current_planner_world_snapshot=route.world_snapshot if route else None,
        current_cost_basis=route.cost_basis if route else None,
        current_planner_inputs=route.planner_input_values if route else None,
    )
    payload = {
        "schema_version": "AcquisitionRetainedContinuation@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_rule": "AD-E02-B09-01/current-cheap-consequences/v1",
        "tenant_id": decision.tenant_id,
        "cell_id": decision.cell_id,
        "run_id": decision.run_id,
        "source_job_id": decision.source_job_id,
        "action_job_id": decision.action_job_id,
        "action_generation": decision.action_generation,
        "route_id": decision.route_id,
        "compiled_ref": decision.compiled_ref,
        "design_problem_ref": decision.design_problem_ref,
        "candidate_id": decision.candidate_id,
        "selected_action_receipt_ref": selection.phase_ref.model_dump(mode="json"),
        "evaluation_decision_ref": decision_ref.model_dump(mode="json"),
        "current_basis_ref": decision.current_basis_ref.model_dump(mode="json"),
        "growth_receipt_ref": selection.growth_ref.model_dump(mode="json"),
        "admitted_source_ref": selection.admitted_source_ref.model_dump(mode="json"),
        "retained_evaluation": decision.prior_evaluation.model_dump(mode="json"),
        "current_projection": projection.model_dump(mode="json"),
        "predicate_provenance": "recomputed",
        "generated_at": datetime.now(UTC).isoformat(),
    }
    record = AcquisitionRetainedContinuation.model_validate(
        {
            **payload,
            "content_hash": exact_n5_content_hash(payload),
        }
    )
    return persist_acquisition_evaluation_artifact(
        store=bridge.artifact_store,
        event_log=bridge.event_log,
        record=record,
    )


def _persist_candidate_current_continuation(
    *,
    owner: CandidateAcquisitionEvaluationCurrentOwner | CandidateExperimentEvaluationCurrentOwner,
    decision: CandidateAcquisitionEvaluationDecision,
    current: object,
) -> ArtifactRef:
    """Select a fresh candidate reaction without creating another N5 result."""
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedCurrentProjection,
        CandidateAcquisitionRetainedContinuation,
        CandidateRetainedPortCapture,
    )
    from polisyos.runtime.quality.generation_cycle import _RetainedCheapProjection

    if (
        type(owner)
        not in {
            CandidateAcquisitionEvaluationCurrentOwner,
            CandidateExperimentEvaluationCurrentOwner,
        }
        or type(decision) is not CandidateAcquisitionEvaluationDecision
        or type(current) is not _RetainedCheapProjection
        or decision.comparison_result != "equivalent"
        or decision.prior_basis_ref is None
        or decision.prior_evaluation is None
        or current.current_route is None
    ):
        raise ValueError("candidate_retained_current_projection_not_established")
    capture_ref = getattr(current, "retained_port_capture_ref", None)
    fence = getattr(current, "retained_budget_fence", None)
    if type(fence) is not _CandidateRetainedBudgetFence or fence.owner is not owner:
        raise ValueError("candidate_retained_budget_fence_not_established")
    capture = read_acquisition_evaluation_artifact(
        store=owner.bridge.artifact_store,
        event_log=owner.bridge.event_log,
        ref=capture_ref,
        record_type=CandidateRetainedPortCapture,
    )
    route = current.current_route
    if (
        type(capture) is not CandidateRetainedPortCapture
        or route.report.candidate_lineage is None
        or not _candidate_ref_same(
            capture.configured_port_source_ref, route.report.candidate_lineage.port_source_ref
        )
        or not _candidate_ref_same(capture.candidate_action_ref, owner.candidate_action_ref)
        or not _candidate_ref_same(capture.evaluation_decision_ref, owner.decision_ref)
        or not _candidate_ref_same(capture.current_basis_ref, owner.current_basis_ref)
        or capture.budget_observation_before != fence.observation
        or capture.budget_observation_after != fence.observation
    ):
        raise ValueError("candidate_retained_port_capture_not_established")
    basis = owner.revalidate()
    previous = read_acquisition_evaluation_artifact(
        store=owner.bridge.artifact_store,
        event_log=owner.bridge.event_log,
        ref=decision.prior_basis_ref,
        record_type=CandidateAcquisitionEvaluationBasis,
    )
    if (
        type(previous) is not CandidateAcquisitionEvaluationBasis
        or not _candidate_ref_same(decision.current_basis_ref, owner.current_basis_ref)
        or not _candidate_ref_same(decision.candidate_action_ref, owner.candidate_action_ref)
        or not basis_exact_values_equal(previous, basis)
    ):
        raise ValueError("candidate_retained_basis_not_established")

    def check_budget() -> None:
        state, observation = owner.current_budget_snapshot(budget_state=fence.budget_state)
        if (
            state is not fence.budget_state
            or exact_n5_content_bytes(state) != fence.state_bytes
            or observation != fence.observation
        ):
            raise ValueError("candidate_retained_budget_observation_changed")

    check_budget()
    projection = AcquisitionRetainedCurrentProjection(
        source_cycle_index=current.source_cycle_index,
        selected_candidate_id=current.selected_candidate_id,
        selected_candidate_content_hash=current.selected_candidate_content_hash,
        grounding=current.grounding,
        value_port=current.value_port,
        execution_schedule=current.execution_schedule,
        terminal_kind=current.terminal_kind,
        voi_decision=current.voi_decision,
        revision_request=current.revision_request,
        counterexample=current.counterexample,
        refinement_decision=current.refinement_decision,
        search_iteration=current.search_iteration,
        current_planner_report=route.report,
        current_planner_report_ref=route.report_ref,
        current_planner_world_snapshot=route.world_snapshot,
        current_cost_basis=route.cost_basis,
        current_planner_inputs=route.planner_input_values,
    )
    saved = _candidate_evaluation_artifact_for_recovery(
        bridge=owner.bridge,
        closure=(
            owner.closure if type(owner) is CandidateAcquisitionEvaluationCurrentOwner else None
        ),
        origin=(owner.origin if type(owner) is CandidateExperimentEvaluationCurrentOwner else None),
        pending_phase_ref=(
            owner.pending_phase_ref
            if type(owner) is CandidateExperimentEvaluationCurrentOwner
            else None
        ),
        candidate_action_ref=owner.candidate_action_ref,
        role="retained_continuation",
    )
    prior_record = saved[1] if saved else None
    if (
        prior_record is not None
        and type(prior_record) is not CandidateAcquisitionRetainedContinuation
    ):
        raise ValueError("candidate_retained_continuation_recovery_untyped")
    payload = {
        "tenant_id": decision.tenant_id,
        "cell_id": decision.cell_id,
        "run_id": decision.run_id,
        "source_job_id": decision.source_job_id,
        "action_job_id": decision.action_job_id,
        "action_generation": decision.action_generation,
        "route_id": decision.route_id,
        "compiled_ref": decision.compiled_ref,
        "design_problem_ref": decision.design_problem_ref,
        "design_problem_basis_ref": decision.design_problem_basis_ref,
        "candidate_id": decision.candidate_id,
        "candidate_action_ref": owner.candidate_action_ref,
        "candidate_world_intent_ref": owner.candidate_world_intent_ref,
        "candidate_source_ref": basis.candidate_source_ref,
        "evaluation_decision_ref": owner.decision_ref,
        "current_basis_ref": owner.current_basis_ref,
        "retained_evaluation": decision.prior_evaluation,
        "current_projection": projection,
        "retained_port_capture_ref": capture_ref,
        "budget_observation_before": fence.observation,
        "budget_observation_after": fence.observation,
        "limitations": tuple(
            dict.fromkeys(
                (
                    *previous.limitations,
                    *basis.limitations,
                    *fence.observation.limitations,
                    *(
                        _candidate_experiment_inherited_limitations(owner.origin)
                        if type(owner) is CandidateExperimentEvaluationCurrentOwner
                        else ()
                    ),
                    "runtime_allocation_not_established",
                    "historical_catalog_absence_not_established",
                    "catalog_currentness_not_established",
                )
            )
        ),
        "generated_at": prior_record.generated_at
        if prior_record
        else datetime.now(UTC).isoformat(),
    }
    provisional = CandidateAcquisitionRetainedContinuation.model_construct(
        **payload, content_hash=""
    )
    record = CandidateAcquisitionRetainedContinuation.model_validate(
        {
            **payload,
            "content_hash": exact_n5_content_hash(
                provisional.model_dump(mode="json", exclude={"content_hash"})
            ),
        }
    )
    if prior_record is not None and not _candidate_model_values_same(prior_record, record):
        raise ValueError("candidate_retained_continuation_recovery_changed")
    ref = _select_candidate_evaluation_artifact(
        bridge=owner.bridge,
        closure=(
            owner.closure if type(owner) is CandidateAcquisitionEvaluationCurrentOwner else None
        ),
        origin=(owner.origin if type(owner) is CandidateExperimentEvaluationCurrentOwner else None),
        pending_phase_ref=(
            owner.pending_phase_ref
            if type(owner) is CandidateExperimentEvaluationCurrentOwner
            else None
        ),
        record=record,
    )
    check_budget()
    owner.revalidate()
    return ref


def _saved_execution_configuration(
    bridge: AcquisitionWorldGrowthBridge,
    selection: _CurrentSelection,
    decision: AcquisitionEvaluationDecision,
) -> PreparedJointSimulationConfiguration:
    """Reopen exact scoped intent before any recovered materialization/N5."""
    closure = selection.closure
    expected = {
        "tenant_id": closure.tenant_id,
        "cell_id": closure.cell_id,
        "run_id": closure.run_id,
        "source_job_id": closure.source_job_id,
        "action_job_id": selection.action_job_id,
        "action_generation": selection.action_generation,
        "route_id": closure.route_id,
        "compiled_ref": closure.compiled_ref,
        "design_problem_ref": closure.design_problem_ref,
        "design_problem_basis_ref": closure.design_problem_basis_ref,
        "candidate_id": closure.source_cycle.selected_candidate_ref,
        "selected_action_receipt_ref": selection.phase_ref,
        "growth_receipt_ref": selection.growth_ref,
        "admitted_source_ref": selection.admitted_source_ref,
    }
    if any(getattr(decision, name) != value for name, value in expected.items()):
        raise ValueError("acquisition_evaluation_recovery_scope_mismatch")
    basis = read_acquisition_evaluation_artifact(
        store=bridge.artifact_store,
        event_log=bridge.event_log,
        ref=decision.current_basis_ref,
        record_type=AcquisitionEvaluationBasis,
    )
    if type(basis) is not AcquisitionEvaluationBasis or (
        basis.tenant_id != closure.tenant_id
        or basis.cell_id != closure.cell_id
        or basis.run_id != closure.run_id
        or basis.source_job_id != closure.source_job_id
        or basis.design_problem_ref != closure.design_problem_basis_ref
        or basis.candidate_id != closure.source_cycle.selected_candidate_ref
        or basis.growth_receipt_ref != selection.growth_ref
        or basis.admitted_source_ref != selection.admitted_source_ref
    ):
        raise ValueError("acquisition_evaluation_recovery_basis_scope_mismatch")
    frontier = _frontier(bridge, selection)
    if (frontier.revision if frontier else 0) != decision.expected_frontier_revision or (
        frontier.frontier_ref if frontier else None
    ) != decision.expected_frontier_ref:
        raise ValueError("acquisition_evaluation_recovery_frontier_changed")
    prepared = basis.preparation_inputs.n5_execution_configuration
    if prepared is None:
        raise ValueError("acquisition_evaluation_configuration_not_established")
    if exact_n5_content_bytes(prepared) != exact_n5_content_bytes(
        selection.prepared.n5_execution_configuration
    ):
        raise ValueError("acquisition_evaluation_prepared_configuration_changed")
    return prepared


def complete_positive_acquisition_admission(
    bridge: AcquisitionWorldGrowthBridge,
    closure: VerifiedAcquisitionRouteClosure,
) -> AcquisitionActionHeadRecord | None:
    """Perform one durable source reaction, conservatively re-entering unknown profiles.

    ``None`` leaves an unsupported legacy-only source on its existing actual
    re-entry path; it does not record retention or a new capability claim.
    Genuine source corruption, lost ownership and frontier conflicts propagate.
    """
    from polisyos.runtime.quality.generation_cycle import (
        AcquisitionOverlayReentryReceipt,
        _RetainedCheapProjection,
    )

    try:
        selection = _current_selection(bridge)
    except ValueError as exc:
        if str(exc) in {
            "acquisition_evaluation_controlled_refresh_not_supported",
            "acquisition_evaluation_source_view_not_established",
        }:
            return None
        raise
    if selection.closure != closure:
        raise ValueError("acquisition_evaluation_caller_source_changed")
    selected_route = bridge.selection(closure)
    if selected_route is None:
        raise ValueError("acquisition_evaluation_route_selection_missing")
    overlay_path, _ = bridge._paths(selected_route, create=False)
    sink = bridge.action_head_sink
    snapshot = sink.current_action_outcome(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        source_job_id=closure.source_job_id,
        route_id=closure.route_id,
    )
    if snapshot is None:
        raise ValueError("acquisition_evaluation_action_head_missing")
    if snapshot.head.receipt_phase == "world_committed_reentry_pending":
        pending = snapshot.latest_receipt
        if not isinstance(pending, AcquisitionRoutePhaseReceipt):
            raise ValueError("acquisition_evaluation_pending_owner_not_established")
        decision_refs = tuple(
            ref
            for ref in pending.owner_receipt_refs
            if bridge.artifact_store.get_manifest(ref).kind
            == "runtime_quality.acquisition_evaluation_decision"
        )
        if not decision_refs:
            return None
        if len(decision_refs) != 1:
            raise ValueError("acquisition_evaluation_recovery_decision_ambiguous")
        decision_ref = selected_artifact_ref(bridge.artifact_store, decision_refs[0])
        decision = read_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            ref=decision_ref,
            record_type=AcquisitionEvaluationDecision,
        )
        if type(decision) is not AcquisitionEvaluationDecision:
            raise ValueError("acquisition_evaluation_recovery_decision_unverified")
        prior = None
        with suppress(OSError, TypeError, ValueError):
            prior = resolve_selected_acquisition_evaluation(bridge=bridge, closure=closure)
        current_basis_ref = decision.current_basis_ref
    else:
        current, old_ref, old_selected, comparison, reasons, frontier, prior = _comparison(
            bridge,
            selection,
        )
        current_basis_ref = persist_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            record=current,
        )
        # Equivalent source keeps its old evaluation only after the actual cheap
        # current consequences have run. Every deciding re-read and SQL commit
        # remains inside the same native-writer fence.
        if comparison == "equivalent" and prior is not None:
            with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
                owner = AcquisitionEvaluationCurrentOwner(
                    bridge,
                    current_basis_ref,
                    selection,
                    prior,
                )
                owner.revalidate()
                current_cheap = _current_cheap_continuation(
                    bridge, selection, prior, current_basis_ref
                )
                if type(current_cheap) is _RetainedCheapProjection:
                    decision = _decision(
                        selection,
                        current_basis_ref=current_basis_ref,
                        prior_basis_ref=old_ref,
                        prior_evaluation=old_selected,
                        comparison=comparison,
                        reasons=reasons,
                        frontier=frontier,
                    )
                    decision_ref = persist_acquisition_evaluation_artifact(
                        store=bridge.artifact_store,
                        event_log=bridge.event_log,
                        record=decision,
                    )
                    continuation_ref = _persist_current_continuation(
                        bridge,
                        selection,
                        decision_ref,
                        decision,
                        current_cheap,
                    )
                    if old_ref is None or old_selected is None:
                        raise ValueError("acquisition_retained_actual_evaluation_missing")
                    terminal = _terminal_record(
                        selection,
                        predecessor_ref=snapshot.head.receipt_ref,
                        owner_refs=tuple(
                            sorted(
                                {*selection.phase.owner_receipt_refs, str(decision_ref.artifact_id)}
                            )
                        ),
                        decision_ref=decision_ref,
                        outcome="source_admitted_evaluation_retained",
                        selected_basis_ref=old_ref,
                        selected_evaluation=old_selected,
                        selected_witness_ref=prior.selected.n5_execution_ref,
                        continuation_ref=continuation_ref,
                    )
                    with _terminal_scope(
                        _TerminalScope(
                            owner,
                            decision_ref,
                            decision,
                            old_ref,
                            old_selected,
                            prior.selected.n5_execution_ref,
                            prior.execution.content_hash,
                        )
                    ):
                        return sink.persist_terminal(terminal)
                comparison = "not_established"
                reasons = (
                    str(
                        getattr(
                            current_cheap,
                            "reason_code",
                            "acquisition_retained_current_work_not_established",
                        )
                    ),
                )
        decision = _decision(
            selection,
            current_basis_ref=current_basis_ref,
            prior_basis_ref=old_ref,
            prior_evaluation=old_selected,
            comparison=comparison,
            reasons=reasons,
            frontier=frontier,
        )
        decision_ref = persist_acquisition_evaluation_artifact(
            store=bridge.artifact_store,
            event_log=bridge.event_log,
            record=decision,
        )
        if current.preparation_inputs.n5_execution_configuration is None:
            # The admission and scoped typed NE basis/decision are durable.
            # Leave outcome_selected recoverable; do not materialize/run with
            # invented defaults or mislabel unsupported preparation no-growth.
            from polisyos.runtime.http.errors import RuntimeDependencyError

            raise RuntimeDependencyError(
                dependency="n5_configuration_preparation",
                status_code=503,
                code="acquisition_evaluation_configuration_not_established",
                detail="acquisition_evaluation_configuration_not_established",
                retry_state="selected_admission_requires_supported_configuration",
            )
        pending_payload = selection.phase.model_dump(mode="python")
        pending_payload.update(
            schema_version="AcquisitionRoutePhaseReceipt@1.0",
            receipt_id=selection.action_job_id + ".world-committed.evaluation",
            receipt_phase="world_committed_reentry_pending",
            coarse_phase="world_committed",
            recovery_state="reentry_recovery_required",
            generated_at=datetime.now(UTC),
            predecessor_receipt_ref=snapshot.head.receipt_ref,
            owner_receipt_refs=tuple(
                sorted({*selection.phase.owner_receipt_refs, str(decision_ref.artifact_id)})
            ),
        )
        pending = AcquisitionRoutePhaseReceipt.model_validate(pending_payload)
        sink.persist_phase(pending)
    # N5 runs with no native-writer fence. Existing pointer/event recovery is
    # reused; the immutable comparison was saved before any new WMR/context.
    pending_head = sink.get_head(pending)
    if pending_head is None or pending_head.receipt_phase != "world_committed_reentry_pending":
        raise ValueError("acquisition_evaluation_pending_head_changed")
    model_transition = _prospective_model_transition(
        bridge, decision_ref=decision_ref, decision=decision
    )
    if model_transition is not None and model_transition.status != "verification_required":
        raise ValueError("acquisition_model_transition_dispatch_unverified")
    prepared_configuration = _saved_execution_configuration(bridge, selection, decision)
    # Recovery revalidates the saved full basis/configuration BEFORE creating
    # any new WMR/context or running N5. The exact saved descriptor is forwarded
    # through the same materialization/constructor owner, not regenerated.
    AcquisitionEvaluationCurrentOwner(
        bridge,
        current_basis_ref,
        selection,
        prior,
    ).revalidate()
    reentry_ref = bridge.resume(
        closure,
        pending.owner_receipt_refs,
        prepared_n5_configuration=prepared_configuration,
    )
    reentry = AcquisitionOverlayReentryReceipt.model_validate(
        bridge._read(reentry_ref, "runtime_quality.acquisition_overlay_reentry_receipt")
    )
    bridge._validate_reentry(closure, selection.growth, reentry)
    if reentry.continued_generation_run is None:
        raise ValueError("acquisition_evaluation_continued_run_missing")
    after = closure.model_copy(
        update={
            "generation_run": reentry.continued_generation_run,
            "source_cycle": reentry.new_cycle,
            "acquisition_basis_transitions": (*closure.acquisition_basis_transitions, reentry),
        }
    )
    evaluated = None
    with suppress(OSError, TypeError, ValueError):
        evaluated = resolve_selected_acquisition_evaluation(bridge=bridge, closure=after)
    # A real blocked/no-V5 reentry is still a real completed outcome. Its
    # NE basis/failure witness must replace old success, not wedge recovery
    # forever on the already-written reentry pointer. A selected successful
    # result's observed configuration is reconciled by the actual-evaluation
    # basis owner below; absent/legacy/unsupported witness remains typed NE.
    actual_basis = issue_acquisition_evaluation_basis(
        bridge=bridge,
        closure=after,
        growth_receipt_ref=selection.growth_ref,
        admitted_source_ref=selection.admitted_source_ref,
        prepared=selection.prepared,
        prior=evaluated,
        actual_evaluation=True,
    )
    actual_basis_ref = persist_acquisition_evaluation_artifact(
        store=bridge.artifact_store,
        event_log=bridge.event_log,
        record=actual_basis,
    )
    if model_transition is not None and evaluated is not None:
        from polisyos.runtime.quality.acquisition_model_transition import (
            CandidateModelRevision,
            resolve_candidate_model_revision,
        )

        revision = resolve_candidate_model_revision(
            artifact_store=bridge.artifact_store,
            event_log=bridge.event_log,
            control_store=bridge.control_store,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            design_problem_ref=closure.design_problem_ref,
            action_job_id=selection.action_job_id,
            action_generation=selection.action_generation,
            route_id=closure.route_id,
            decision_ref=decision_ref,
            selected_basis_ref=actual_basis_ref,
            previous_run=closure.generation_run,
            previous_cycle=closure.source_cycle,
            selected_run=reentry.continued_generation_run,
            selected_cycle=reentry.new_cycle,
        )
        if type(revision) is not CandidateModelRevision:
            raise ValueError("acquisition_model_transition_result_unverified")
    new_selected = (
        evaluated.selected.model_copy(update={"basis_ref": actual_basis_ref}) if evaluated else None
    )
    new_witness = (
        evaluated.selected.n5_execution_ref
        if evaluated
        else selected_artifact_ref(
            bridge.artifact_store,
            reentry_ref,
        )
    )
    new_hash = evaluated.execution.content_hash if evaluated else reentry.content_hash
    # A failed or unsupported real N5 remains a real re-entry, never a retained
    # old success. The selected failure witness replaces the old selector.
    with data_forge_read_api.catalog.acquisition_overlay_admission_fence(overlay_path):
        owner = AcquisitionEvaluationCurrentOwner(bridge, current_basis_ref, selection, prior)
        owner.revalidate()
        terminal = _terminal_record(
            selection,
            predecessor_ref=pending_head.receipt_ref,
            owner_refs=pending.owner_receipt_refs,
            decision_ref=decision_ref,
            outcome="reentry_completed",
            selected_basis_ref=actual_basis_ref,
            selected_evaluation=new_selected,
            selected_witness_ref=new_witness,
            reentry_ref=reentry_ref,
        )
        with _terminal_scope(
            _TerminalScope(
                owner,
                decision_ref,
                decision,
                actual_basis_ref,
                new_selected,
                new_witness,
                new_hash,
            )
        ):
            return sink.persist_terminal(terminal)
