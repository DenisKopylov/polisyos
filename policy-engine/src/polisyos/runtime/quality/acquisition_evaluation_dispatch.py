"""One actual post-admission dispatcher for re-entry or retained evaluation.

All current inputs come from the bound Control/epoch/source owners. The native
fence spans the final conditional SQL action-head/frontier write and readback;
it never spans the numerical N5 work. Recovery reuses owned admission/re-entry
receipts and never refetches or repeats provider spend.
"""

from __future__ import annotations

from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from polisyos.core import contracts
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationBasis,
    AcquisitionEvaluationDecision,
    AcquisitionSelectedEvaluation,
    ResolvedAcquisitionEvaluation,
    basis_exact_values_equal,
    issue_acquisition_evaluation_basis,
    persist_acquisition_evaluation_artifact,
    read_acquisition_evaluation_artifact,
    replay_acquisition_basis_for_history,
    resolve_selected_acquisition_evaluation,
    selected_artifact_ref,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoop,
    AcquisitionRouteLoopReceiptV2,
    AcquisitionRoutePhaseReceipt,
)
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionCandidatePreparation,
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthReceipt,
)
from polisyos.runtime.quality.n5_execution_basis import (
    exact_n5_content_bytes,
    exact_n5_content_hash,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from polisyos.core.artifacts import ArtifactRef
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        AcquisitionEvaluationFrontierCAS,
        AcquisitionEvaluationFrontierRecord,
    )
    from polisyos.runtime.quality.acquisition_planner import AcquisitionWorldSnapshot
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure
    from polisyos.runtime.quality.joint_simulation_horizon import (
        PreparedJointSimulationConfiguration,
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
