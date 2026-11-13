"""Real selected basis/decision links at the experiment record boundary.

The current-action, selection and intent owners are explicit upstream component
adapters. No verified experiment origin, PA2 permit or N5 result is fabricated.
The source/profile inputs, record constructors, CAS/event persistence, selected
manifest reads and the record-scope/link predicates under test remain real.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import acquisition_evaluation_dispatch as dispatch
from polisyos.runtime.quality import candidate_acquisition_action as action_owner
from polisyos.runtime.quality.acquisition_evaluation import (
    CandidateAcquisitionEvaluationBasis,
    CandidateAcquisitionEvaluationBasisV2,
    CandidateAcquisitionEvaluationDecision,
    CandidateAcquisitionEvaluationDecisionV2,
    ResolvedAcquisitionEvaluation,
    _candidate_evaluation_event_id,
    issue_candidate_acquisition_evaluation_basis,
    issue_candidate_acquisition_evaluation_decision,
    persist_acquisition_evaluation_artifact,
    read_acquisition_evaluation_artifact,
)
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests.unit.runtime.quality.test_candidate_acquisition_world import (
    CELL_ID,
    TENANT_ID,
    TRANSACTION_TIME,
    _candidate_world_case,
)
from tests.unit.runtime.quality.test_candidate_experiment_read_operation import (
    _PhaseRecord,
    _Row,
)
from tests.unit.runtime.quality.test_candidate_source_basis import _inputs


@dataclass(frozen=True)
class _RecordCycle:
    selected_candidate_ref: str
    selected_candidate_content_hash: str


@dataclass(frozen=True)
class _RecordPolicy:
    compiled_ref: artifacts.ArtifactRef
    design_problem_ref: str
    design_problem_basis_ref: str


@dataclass(frozen=True)
class _RecordOrigin:
    tenant_id: str
    cell_id: str
    run_id: str
    source_job_id: str
    route_id: str
    effective_source_cycle: _RecordCycle
    policy_scope: _RecordPolicy
    candidate_terminal_history_chain: tuple[object, ...] = ()


@dataclass(frozen=True)
class _RecordSelection:
    profile_selection_ref: str


@dataclass(frozen=True)
class _RecordAction:
    selection: _RecordSelection
    action_job_id: str
    action_generation: int
    candidate_source_ref: artifacts.ArtifactRef
    action_phase_ref: str = "sha256:" + "a" * 64


@pytest.fixture
def record_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    """Reuse actual source/profile bytes and adapt only upstream action admission."""
    world = _candidate_world_case(tmp_path / "world", monkeypatch)
    inputs = _inputs(world)
    store = world.store
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "events.sqlite3")
    events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
    root = tmp_path / "selection"
    root.mkdir()

    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):

        def parent(kind: str, name: str) -> artifacts.ArtifactRef:
            return store.put_json(
                {"component_parent": name, "protected_action_not_established": True},
                artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
                return_selected_profile=True,
            )

        action_ref = parent("runtime_quality.acquisition_candidate_action_receipt", "action")
        intent_ref = parent("runtime_quality.acquisition_candidate_world_intent", "intent")
        compiled_ref = parent("runtime.compiled_recursive_generation_cycle", "compiled")
        problem_ref = cycle_job_design_problem_ref(world.problem)
        cycle = _RecordCycle(
            selected_candidate_ref="component-candidate",
            selected_candidate_content_hash="sha256:" + "4" * 64,
        )
        origin = _RecordOrigin(
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
            run_id="record-component-run",
            source_job_id="record-component-source",
            route_id="sha256:" + "5" * 64,
            effective_source_cycle=cycle,
            policy_scope=_RecordPolicy(
                compiled_ref=compiled_ref,
                design_problem_ref=problem_ref,
                design_problem_basis_ref=problem_ref,
            ),
        )
        selection = _RecordSelection(
            profile_selection_ref=inputs.configured_profile.profile_selection_ref
        )
        action = _RecordAction(
            selection=selection,
            action_job_id="record-component-action",
            action_generation=1,
            candidate_source_ref=inputs.candidate_source_ref,
        )
        bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
        bridge.artifact_store = store
        bridge.event_log = events
        action_replays = []

        phase = _Row("phase")
        chain = (_PhaseRecord(action.action_phase_ref, phase),)
        context = action_owner._VerifiedCurrentCandidateExperimentReentryAction(
            selection=selection,
            action=action,
            phase=phase,
            admission=_Row("admission"),
            head=_Row("head"),
            outcome=_Row("outcome", phase_chain=chain),
            budget_window=_Row("window"),
        )
        state = {"heads": (context.head,), "window": context.budget_window, "chain": chain}

        def replay_action(*args: object) -> object:
            action_replays.append(args)
            return context

        monkeypatch.setattr(
            action_owner, "_current_candidate_experiment_reentry_action_context", replay_action
        )
        service = SimpleNamespace(
            acquisition_route_sink=SimpleNamespace(
                _verified_candidate_experiment_phase_chain=lambda *_args, **_kwargs: state["chain"]
            )
        )
        monkeypatch.setattr(
            action_owner, "_require_canonical_action_bridge", lambda _bridge: service
        )
        monkeypatch.setattr(
            action_owner,
            "read_candidate_experiment_acquisition_action_historical",
            lambda **_kwargs: (action, None, state["window"]),
        )
        bridge.control_store = control
        monkeypatch.setattr(control, "get_job", lambda _job: None)
        monkeypatch.setattr(control, "get_job_created_event_payload", lambda _job: None)
        monkeypatch.setattr(control, "get_job_created_outbox_event", lambda _job: None)
        monkeypatch.setattr(
            control, "list_acquisition_action_heads_for_source", lambda **_kwargs: state["heads"]
        )
        monkeypatch.setattr(
            control, "get_acquisition_action_head", lambda **_kwargs: state["heads"][0]
        )
        monkeypatch.setattr(control, "current_execution_job_admission", lambda: context.admission)
        monkeypatch.setattr(
            action_owner, "_candidate_experiment_source_selection", lambda *_args: selection
        )
        monkeypatch.setattr(
            bridge,
            "_candidate_experiment_prior_owner",
            lambda **_kwargs: SimpleNamespace(
                profile=inputs.configured_profile,
                model_declaration=inputs.original_model_declaration,
            ),
        )
        monkeypatch.setattr(
            bridge,
            "_candidate_world_materialization_intent",
            lambda **_kwargs: (intent_ref, SimpleNamespace(transaction_time=TRANSACTION_TIME)),
        )
        monkeypatch.setattr(bridge, "_paths", lambda *_args, **_kwargs: (root / "overlay", None))
        common = {
            "tenant_id": TENANT_ID,
            "cell_id": CELL_ID,
            "run_id": origin.run_id,
            "source_job_id": origin.source_job_id,
            "action_job_id": action.action_job_id,
            "action_generation": 1,
            "route_id": origin.route_id,
            "design_problem_ref": problem_ref,
            "design_problem_basis_ref": problem_ref,
            "candidate_id": cycle.selected_candidate_ref,
            "source_candidate_content_hash": cycle.selected_candidate_content_hash,
            "candidate_action_ref": action_ref,
            "candidate_world_intent_ref": intent_ref,
            "candidate_source_ref": inputs.candidate_source_ref,
        }

        def basis(**updates: object) -> CandidateAcquisitionEvaluationBasis:
            basis_version = updates.pop("basis_version", "1.0")
            values = updates.pop("values", {"component_record_scope": "not_a_numerical_evaluation"})
            provenance = updates.pop("predicate_provenance", "not_established")
            reasons = updates.pop("reason_codes", ("component_evaluation_not_established",))
            configuration = updates.pop("prepared_n5_configuration", None)
            return issue_candidate_acquisition_evaluation_basis(
                **{**common, **updates},
                preparation_inputs=inputs,
                prepared_n5_configuration=configuration,
                basis_role="prospective",
                basis_version=basis_version,
                values=values,
                predicate_provenance=provenance,
                reason_codes=reasons,
                limitations=("component_only_no_protected_action_or_n5",),
            )

        def decision(
            current_basis_ref: artifacts.ArtifactRef,
            *,
            decision_version: str = "1.0",
            compiled_ref_override: str | None = None,
        ) -> CandidateAcquisitionEvaluationDecision:
            return issue_candidate_acquisition_evaluation_decision(
                **common,
                decision_version=decision_version,
                compiled_ref=compiled_ref_override or str(compiled_ref.artifact_id),
                current_basis_ref=current_basis_ref,
                prior_basis_ref=None,
                prior_evaluation=None,
                comparison_result="not_established",
                predicate_provenance="not_established",
                reason_codes=("candidate_evaluation_prior_basis_not_established",),
                expected_frontier_revision=0,
                expected_frontier_ref=None,
                generated_at=TRANSACTION_TIME.isoformat(),
            )

        def select(record: object, *, read_context=None) -> artifacts.ArtifactRef:
            return dispatch._select_candidate_experiment_evaluation_artifact(
                bridge=bridge,
                origin=origin,
                pending_phase_ref="sha256:" + "6" * 64,
                candidate_action_ref=action_ref,
                record=record,
                _read_context=read_context,
            )

        def read_current(
            basis_ref: artifacts.ArtifactRef,
            decision_ref: artifacts.ArtifactRef,
            *,
            read_context=None,
        ) -> tuple[CandidateAcquisitionEvaluationBasis, CandidateAcquisitionEvaluationDecision]:
            owner = SimpleNamespace(
                bridge=bridge,
                origin=origin,
                pending_phase_ref="sha256:" + "6" * 64,
                candidate_action_ref=action_ref,
                current_basis_ref=basis_ref,
                decision_ref=decision_ref,
            )
            return dispatch._read_current_candidate_experiment_evaluation_records(
                owner, _read_context=read_context
            )

        try:
            yield SimpleNamespace(
                store=store,
                events=events,
                basis=basis,
                decision=decision,
                select=select,
                parent=parent,
                read_current=read_current,
                action_replays=action_replays,
                bridge=bridge,
                origin=origin,
                action_ref=action_ref,
                context=context,
                state=state,
            )
        finally:
            control.close()


def _component_prior(
    case: SimpleNamespace, *, observation: object
) -> ResolvedAcquisitionEvaluation:
    """Supply a routing double; it is not an N5 witness or an authority claim."""
    return ResolvedAcquisitionEvaluation(
        selected=SimpleNamespace(
            n5_input_ref=case.action_ref,
            evaluation_run_id="component-run",
            evaluation_job_id="component-job",
        ),
        source=None,
        input_record=SimpleNamespace(tenant_id=TENANT_ID, cell_id=CELL_ID),
        execution=None,
        result=SimpleNamespace(
            diagnostics={"candidate_n5_execution_content_observation": observation}
        ),
        handoff=None,
    )


def _prospective_version(
    case: SimpleNamespace,
    *,
    prior: ResolvedAcquisitionEvaluation | None,
    previous: CandidateAcquisitionEvaluationBasis | None = None,
) -> str:
    return dispatch._candidate_experiment_prospective_basis_version(
        bridge=case.bridge,
        origin=case.origin,
        pending_phase_ref="sha256:" + "6" * 64,
        candidate_action_ref=case.action_ref,
        previous_basis=previous,
        prior=prior,
    )


def test_content_observed_bootstrap_recomputes_current_but_not_comparison(
    record_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Version routing and real issuers keep current identity separate from a frontier.

    Upstream preparation and the content reconciler are explicit component
    doubles; the saved record/event/selected-view and comparison are real.
    """
    from decimal import Decimal

    from polisyos.runtime.quality import acquisition_evaluation as evaluation
    from polisyos.runtime.quality import candidate_source_basis
    from polisyos.runtime.quality import n5_candidate_content as content
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    case = record_case
    prior = _component_prior(case, observation={"component_only": True})
    version = _prospective_version(case, prior=prior)
    assert version == "2.0"
    calls: list[str] = []
    monkeypatch.setattr(
        candidate_source_basis,
        "prepare_candidate_source_numerical_basis_values_v2",
        lambda **_kwargs: SimpleNamespace(
            predicate_provenance="recomputed", reason_codes=(), effective_values={"state": 0.175}
        ),
    )
    monkeypatch.setattr(
        evaluation, "rebuild_selected_candidate_n5_request", lambda **_kwargs: object()
    )

    def reconcile(_result: object, **_kwargs: object) -> dict[str, object]:
        calls.append("v2-content-owner")
        return {
            "content_image": {"component_only": True},
            "execution_profile": {"component_only": True},
            "callable_identity": "component_only",
        }

    monkeypatch.setattr(content, "reconcile_candidate_n5_declared_implementation", reconcile)
    monkeypatch.setattr(
        evaluation, "_candidate_v5_numerical_request_facets", lambda **_kwargs: {"seed": 17}
    )
    monkeypatch.setattr(
        evaluation,
        "reconcile_live_n5_implementation",
        lambda *_args, **_kwargs: pytest.fail("new content reached the legacy witness"),
    )
    configuration = prepare_joint_simulation_configuration()
    values, reasons = evaluation.recompute_candidate_acquisition_basis_values(
        artifact_store=case.store,
        problem=object(),
        preparation_inputs=case.basis().preparation_inputs,
        predecessors=(),
        prior=prior,
        prepared_n5_configuration=configuration,
        fresh_limit_usd=Decimal(0),
        global_limit_usd=Decimal(0),
        basis_version=version,
    )
    assert calls == ["v2-content-owner"] and reasons == ()
    basis = case.basis(
        basis_version=version,
        values=values,
        predicate_provenance="recomputed",
        reason_codes=(),
        prepared_n5_configuration=configuration,
    )
    assert type(basis) is CandidateAcquisitionEvaluationBasisV2
    basis_ref = case.select(basis)
    decision = case.decision(basis_ref, decision_version=version)
    decision_ref = case.select(decision)
    assert type(decision) is CandidateAcquisitionEvaluationDecisionV2
    assert decision.comparison_result == decision.predicate_provenance == "not_established"
    assert decision.reason_codes == ("candidate_evaluation_prior_basis_not_established",)
    assert decision.prior_basis_ref is decision.prior_evaluation is None
    assert decision.expected_frontier_revision == 0 and decision.expected_frontier_ref is None
    assert case.read_current(basis_ref, decision_ref) == (basis, decision)
    assert not basis.observed_admission and not basis.publication_authority


def test_content_marker_cannot_establish_a_missing_witness(
    record_case: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """V2 selection alone cannot promote a malformed observed result."""
    from decimal import Decimal

    from polisyos.runtime.quality import acquisition_evaluation as evaluation
    from polisyos.runtime.quality import candidate_source_basis
    from polisyos.runtime.quality.joint_simulation_horizon import (
        prepare_joint_simulation_configuration,
    )

    case = record_case
    prior = _component_prior(case, observation=None)
    version = _prospective_version(case, prior=prior)
    assert version == "2.0"
    monkeypatch.setattr(
        candidate_source_basis,
        "prepare_candidate_source_numerical_basis_values_v2",
        lambda **_kwargs: SimpleNamespace(
            predicate_provenance="recomputed", reason_codes=(), effective_values={}
        ),
    )
    monkeypatch.setattr(
        evaluation, "rebuild_selected_candidate_n5_request", lambda **_kwargs: object()
    )
    values, reasons = evaluation.recompute_candidate_acquisition_basis_values(
        artifact_store=case.store,
        problem=object(),
        preparation_inputs=case.basis().preparation_inputs,
        predecessors=(),
        prior=prior,
        prepared_n5_configuration=prepare_joint_simulation_configuration(),
        fresh_limit_usd=Decimal(0),
        global_limit_usd=Decimal(0),
        basis_version=version,
    )
    assert values == {} and reasons == ("candidate_n5_content_result_untyped",)
    assert _prospective_version(case, prior=None) == "1.0"
    prior.result.diagnostics.clear()
    assert _prospective_version(case, prior=prior) == "1.0"


@pytest.mark.parametrize("saved_version", ["1.0", "2.0"])
def test_experiment_bootstrap_recovers_saved_basis_version(
    record_case: SimpleNamespace, saved_version: str
) -> None:
    """A retry reopens its existing action-local selected record without upgrading it."""
    case = record_case
    saved = case.basis(basis_version=saved_version)
    selected = case.select(saved)
    prior = _component_prior(case, observation={"component_only": True})
    assert _prospective_version(case, prior=prior) == saved_version
    assert _prospective_version(case, prior=None) == saved_version
    assert case.select(saved) == selected


@pytest.mark.parametrize("previous_version", ["1.0", "2.0"])
def test_experiment_existing_frontier_preserves_its_basis_version(
    record_case: SimpleNamespace, previous_version: str
) -> None:
    case = record_case
    previous = case.basis(basis_version=previous_version)
    prior = _component_prior(case, observation={"component_only": True})
    assert _prospective_version(case, prior=prior, previous=previous) == previous_version


def test_experiment_saved_version_cannot_conflict_with_selected_frontier(
    record_case: SimpleNamespace,
) -> None:
    case = record_case
    case.select(case.basis(basis_version="1.0"))
    previous = case.basis(basis_version="2.0")
    with pytest.raises(ValueError, match="candidate_experiment_saved_basis_version_mismatch"):
        _prospective_version(case, prior=_component_prior(case, observation={}), previous=previous)


def test_experiment_saved_version_refuses_corrupt_selected_basis(
    record_case: SimpleNamespace,
) -> None:
    """Event presence never substitutes for an owner-reopened selected basis."""
    case = record_case
    selected = case.select(case.basis(basis_version="2.0"))
    path, _manifest = case.store._paths(selected.artifact_id)
    original = path.read_bytes()
    assert path.stat().st_nlink == 1 and not path.is_symlink()
    path.write_bytes(b"corrupted-selected-basis")
    try:
        with pytest.raises((ValueError, RuntimeError), match=r"integrity|artifact|mismatch"):
            _prospective_version(case, prior=_component_prior(case, observation={}))
    finally:
        path.write_bytes(original)
    assert _prospective_version(case, prior=_component_prior(case, observation={})) == "2.0"


def test_experiment_saved_version_refuses_nonexact_selected_pointer(
    record_case: SimpleNamespace,
) -> None:
    """A different action's pointer cannot determine this action's wire version."""
    import json

    case = record_case
    saved = case.basis(basis_version="2.0")
    case.select(saved)
    pointer = case.bridge._paths(case.context.selection, create=False)[0].parent / (
        _candidate_evaluation_event_id(saved) + ".selected.json"
    )
    original = pointer.read_bytes()
    assert pointer.stat().st_nlink == 1 and not pointer.is_symlink()
    changed = json.loads(original)
    changed["candidate_action_ref"] = case.parent(
        "runtime_quality.acquisition_candidate_action_receipt", "foreign-action"
    ).model_dump(mode="json")
    pointer.write_text(json.dumps(changed))
    try:
        with pytest.raises(ValueError, match="candidate_world_selected_profile_mismatch"):
            _prospective_version(case, prior=_component_prior(case, observation={}))
    finally:
        pointer.write_bytes(original)
    assert _prospective_version(case, prior=_component_prior(case, observation={})) == "2.0"


def test_experiment_orphan_pointer_refuses_new_selected_basis(
    record_case: SimpleNamespace,
) -> None:
    """Absence of an event never allows an existing pointer to be overwritten."""
    case = record_case
    basis = case.basis(basis_version="2.0")
    pointer = case.bridge._paths(case.context.selection, create=False)[0].parent / (
        _candidate_evaluation_event_id(basis) + ".selected.json"
    )
    orphan = case.parent("runtime_quality.acquisition_evaluation_basis", "orphan")
    case.bridge._write_candidate_world_pointer(
        pointer, candidate_action_ref=case.action_ref, selected_ref=orphan
    )
    assert _prospective_version(case, prior=_component_prior(case, observation={})) == "2.0"
    with pytest.raises(ValueError, match="candidate_experiment_evaluation_event_missing"):
        case.select(basis)
    assert not case.events.list_events(event_id=_candidate_evaluation_event_id(basis), limit=2)


def test_v2_experiment_decision_refuses_rehashed_foreign_compiled_ref(
    record_case: SimpleNamespace,
) -> None:
    """V2 must recheck the same compiled parent before event or pointer writes."""
    case = record_case
    basis_ref = case.select(case.basis(basis_version="2.0"))
    foreign = case.decision(
        basis_ref,
        decision_version="2.0",
        compiled_ref_override="sha256:" + "f" * 64,
    )
    assert type(foreign) is CandidateAcquisitionEvaluationDecisionV2
    with pytest.raises(ValueError, match="candidate_experiment_evaluation_record_scope_mismatch"):
        case.select(foreign)
    assert not case.events.list_events(event_id=_candidate_evaluation_event_id(foreign), limit=2)
    valid = case.decision(basis_ref, decision_version="2.0")
    assert case.read_current(basis_ref, case.select(valid)) == (
        case.basis(basis_version="2.0"),
        valid,
    )


def test_experiment_decision_reopens_its_real_selected_prospective_basis(
    record_case: SimpleNamespace,
) -> None:
    """A decision has no preparation field; its exact selected basis supplies it."""
    case = record_case
    basis = case.basis()
    basis_ref = case.select(basis)
    decision = case.decision(basis_ref)
    assert "preparation_inputs" not in type(decision).model_fields
    decision_ref = case.select(decision)
    reopened = read_acquisition_evaluation_artifact(
        store=case.store,
        event_log=case.events,
        ref=decision_ref,
        record_type=CandidateAcquisitionEvaluationDecision,
    )
    assert reopened == decision
    assert reopened.current_basis_ref == basis_ref

    case.action_replays.clear()
    assert case.read_current(basis_ref, decision_ref) == (basis, decision)
    # Decision and basis keep their own content checks but share the action prefix.
    assert len(case.action_replays) == 2
    assert (
        read_acquisition_evaluation_artifact(
            store=case.store,
            event_log=case.events,
            ref=reopened.current_basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        == basis
    )


@pytest.mark.parametrize("saved", [False, True])
def test_experiment_record_bundle_shares_one_complete_owner_operation(
    record_case: SimpleNamespace, saved: bool
) -> None:
    """Real CAS/event/pointer work keeps one entry/exit fold, including recovery."""
    case = record_case
    basis = case.basis()
    if saved:
        basis_ref = case.select(basis)
        case.select(case.decision(basis_ref))
    case.action_replays.clear()
    with action_owner._candidate_experiment_reentry_read_operation(
        case.bridge, case.origin, "sha256:" + "6" * 64, case.action_ref
    ) as context:
        basis_ref = case.select(basis, read_context=context)
        recovered = dispatch._candidate_experiment_decision_for_recovery(
            bridge=case.bridge,
            origin=case.origin,
            pending_phase_ref="sha256:" + "6" * 64,
            candidate_action_ref=case.action_ref,
            _read_context=context,
        )
        decision = case.decision(basis_ref)
        assert (recovered is not None) is saved
        if recovered is not None:
            assert recovered[1] == decision
        decision_ref = case.select(decision, read_context=context)
        assert case.read_current(basis_ref, decision_ref, read_context=context) == (
            basis,
            decision,
        )
        assert len(case.action_replays) == 1
    assert len(case.action_replays) == 2
    with pytest.raises(ValueError, match="read_operation_changed"):
        case.select(basis, read_context=context)


@pytest.mark.parametrize("change", ["head", "phase", "window"])
def test_experiment_record_bundle_refuses_changes_between_real_records(
    record_case: SimpleNamespace, change: str
) -> None:
    """A shared proof never makes a later decision valid after its live parents change."""
    case = record_case
    decision = None
    with action_owner._candidate_experiment_reentry_read_operation(
        case.bridge, case.origin, "sha256:" + "6" * 64, case.action_ref
    ) as context:
        basis_ref = case.select(case.basis(), read_context=context)
        decision = case.decision(basis_ref)
        if change == "head":
            case.state["heads"] = (replace(case.context.head, values={"profile": "changed"}),)
        elif change == "phase":
            case.state["chain"] = (
                _PhaseRecord(case.context.action.action_phase_ref, _Row("changed-phase")),
            )
        else:
            case.state["window"] = _Row("changed-window")
        with pytest.raises(
            ValueError, match=r"read_operation_(changed|phase_changed|parents_changed)"
        ):
            case.select(decision, read_context=context)
        # Restore the live dependency so the enclosing operation may close.
        case.state.update(
            heads=(case.context.head,),
            chain=case.context.outcome.phase_chain,
            window=case.context.budget_window,
        )
    assert decision is not None
    assert not case.events.list_events(event_id=_candidate_evaluation_event_id(decision), limit=2)


def test_current_experiment_evaluation_requires_the_decisions_exact_profile(
    record_case: SimpleNamespace,
) -> None:
    """Individually readable same-byte views cannot substitute for the selected basis."""
    case = record_case
    basis = case.basis()
    selected = case.select(basis)
    decision_ref = case.select(case.decision(selected))
    manifest = case.store.get_manifest(selected)
    alternate = case.store.put_bytes(
        case.store.get_bytes(selected),
        artifacts.ArtifactWriteOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            env=manifest.env,
            inputs=manifest.inputs,
            canon=manifest.canon,
            governance=manifest.governance,
            tenant_context=manifest.tenant_context,
            same_input_closure=manifest.same_input_closure,
            authority=manifest.authority,
            warnings=[
                *manifest.warnings,
                artifacts.WarningRecord(code="alternate-view", msg="Retained comparison view"),
            ],
        ),
        return_selected_profile=True,
    )
    assert alternate.artifact_id == selected.artifact_id
    assert alternate.manifest_profile_sha256 != selected.manifest_profile_sha256
    assert (
        read_acquisition_evaluation_artifact(
            store=case.store,
            event_log=case.events,
            ref=alternate,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        == basis
    )

    case.action_replays.clear()
    with pytest.raises(ValueError, match="candidate_experiment_evaluation_current_basis_changed"):
        case.read_current(alternate, decision_ref)
    assert case.action_replays == []


@pytest.mark.parametrize("control", ["foreign_profile", "foreign_action", "corrupt_blob"])
def test_experiment_decision_refuses_an_unowned_or_unlinked_current_basis(
    record_case: SimpleNamespace, control: str
) -> None:
    """Keep the decision link real while changing its selected view or bytes."""
    case = record_case
    basis = case.basis()
    selected = case.select(basis)
    original_selected = selected
    original_blob: tuple[Path, bytes] | None = None
    if control == "foreign_profile":
        original_manifest = case.store.get_manifest(original_selected)
        default_manifest = case.store.get_manifest(original_selected.artifact_id)
        original_bytes = case.store.get_bytes(original_selected)
        selected = case.store.put_bytes(
            original_bytes,
            artifacts.ArtifactWriteOptions(
                kind=original_manifest.kind,
                media_type=original_manifest.media_type,
                schema=original_manifest.artifact_schema,
                producer=artifacts.ProducerInfo(component="foreign.component", version="1.0"),
                env=original_manifest.env,
                inputs=original_manifest.inputs,
                canon=original_manifest.canon,
                governance=original_manifest.governance,
                tenant_context=original_manifest.tenant_context,
                same_input_closure=original_manifest.same_input_closure,
                authority=original_manifest.authority,
                warnings=original_manifest.warnings,
            ),
            return_selected_profile=True,
        )
        assert selected.artifact_id == original_selected.artifact_id
        assert selected.manifest_profile_sha256 != original_selected.manifest_profile_sha256
        assert case.store.get_bytes(selected) == original_bytes
        assert case.store.get_manifest(original_selected) == original_manifest
        assert case.store.get_manifest(original_selected.artifact_id) == default_manifest
    elif control == "foreign_action":
        foreign_action = case.parent(
            "runtime_quality.acquisition_candidate_action_receipt", "another-action"
        )
        selected = persist_acquisition_evaluation_artifact(
            store=case.store,
            event_log=case.events,
            record=case.basis(candidate_action_ref=foreign_action),
        )
    else:
        path, _manifest = case.store._paths(selected.artifact_id)
        original_blob = (path, path.read_bytes())
        assert path.stat().st_nlink == 1 and not path.is_symlink()
        path.write_bytes(b"corrupted-component-basis")
    decision = case.decision(selected)
    try:
        with pytest.raises((ValueError, RuntimeError), match=r"basis|owner|selected|integrity"):
            case.select(decision)
        assert not case.events.list_events(
            event_id=_candidate_evaluation_event_id(decision), limit=2
        )
    finally:
        if original_blob is not None:
            original_blob[0].write_bytes(original_blob[1])
    restored = case.decision(original_selected)
    restored_ref = case.select(restored)
    assert (
        read_acquisition_evaluation_artifact(
            store=case.store,
            event_log=case.events,
            ref=restored_ref,
            record_type=CandidateAcquisitionEvaluationDecision,
        )
        == restored
    )
