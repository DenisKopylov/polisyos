"""Real selected basis/decision links at the experiment record boundary.

The current-action, selection and intent owners are explicit upstream component
adapters. No verified experiment origin, PA2 permit or N5 result is fabricated.
The source/profile inputs, record constructors, CAS/event persistence, selected
manifest reads and the record-scope/link predicates under test remain real.
"""

from __future__ import annotations

from collections.abc import Iterator
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
    CandidateAcquisitionEvaluationDecision,
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
from tests.unit.runtime.quality.test_candidate_source_basis import _inputs


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
        cycle = SimpleNamespace(
            selected_candidate_ref="component-candidate",
            selected_candidate_content_hash="sha256:" + "4" * 64,
        )
        origin = SimpleNamespace(
            tenant_id=TENANT_ID,
            cell_id=CELL_ID,
            run_id="record-component-run",
            source_job_id="record-component-source",
            route_id="sha256:" + "5" * 64,
            effective_source_cycle=cycle,
            policy_scope=SimpleNamespace(
                compiled_ref=compiled_ref,
                design_problem_ref=problem_ref,
                design_problem_basis_ref=problem_ref,
            ),
        )
        selection = SimpleNamespace(
            profile_selection_ref=inputs.configured_profile.profile_selection_ref
        )
        action = SimpleNamespace(
            selection=selection,
            action_job_id="record-component-action",
            action_generation=1,
            candidate_source_ref=inputs.candidate_source_ref,
        )
        bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
        bridge.artifact_store = store
        bridge.event_log = events
        action_replays = []

        def replay_action(*args: object) -> tuple[object, ...]:
            action_replays.append(args)
            return selection, None, None, action

        monkeypatch.setattr(
            action_owner, "_current_candidate_experiment_reentry_action", replay_action
        )
        monkeypatch.setattr(
            action_owner,
            "read_candidate_experiment_acquisition_action",
            lambda **_kwargs: action,
        )
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
            return issue_candidate_acquisition_evaluation_basis(
                **{**common, **updates},
                preparation_inputs=inputs,
                prepared_n5_configuration=None,
                basis_role="prospective",
                values={"component_record_scope": "not_a_numerical_evaluation"},
                predicate_provenance="not_established",
                reason_codes=("component_evaluation_not_established",),
                limitations=("component_only_no_protected_action_or_n5",),
            )

        def decision(
            current_basis_ref: artifacts.ArtifactRef,
        ) -> CandidateAcquisitionEvaluationDecision:
            return issue_candidate_acquisition_evaluation_decision(
                **common,
                compiled_ref=str(compiled_ref.artifact_id),
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

        def select(record: object) -> artifacts.ArtifactRef:
            return dispatch._select_candidate_experiment_evaluation_artifact(
                bridge=bridge,
                origin=origin,
                pending_phase_ref="sha256:" + "6" * 64,
                candidate_action_ref=action_ref,
                record=record,
            )

        def read_current(
            basis_ref: artifacts.ArtifactRef, decision_ref: artifacts.ArtifactRef
        ) -> tuple[CandidateAcquisitionEvaluationBasis, CandidateAcquisitionEvaluationDecision]:
            owner = SimpleNamespace(
                bridge=bridge,
                origin=origin,
                pending_phase_ref="sha256:" + "6" * 64,
                candidate_action_ref=action_ref,
                current_basis_ref=basis_ref,
                decision_ref=decision_ref,
            )
            return dispatch._read_current_candidate_experiment_evaluation_records(owner)

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
            )
        finally:
            control.close()


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
    assert len(case.action_replays) == 2  # The decision and its own prospective-basis scope.
    assert (
        read_acquisition_evaluation_artifact(
            store=case.store,
            event_log=case.events,
            ref=reopened.current_basis_ref,
            record_type=CandidateAcquisitionEvaluationBasis,
        )
        == basis
    )


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
