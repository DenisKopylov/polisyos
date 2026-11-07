"""Selected producer-profile controls for historical candidate re-entry.

These tests exercise actual CAS and diagnostic owners at the checkpoint replay
boundary. They do not claim a completed N6/N5 continuation; that needs the
served producer chain in addition to this immutable owner check.
"""

from __future__ import annotations

import hashlib
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthBridge,
    CandidateAcquisitionWorldCheckpoint,
)
from polisyos.runtime.quality.candidate_source_reentry_history import (
    _owner_record,
    _require_n4_origin,
    _require_world_creation_time,
    _retained_world_values,
    _same_view,
    _Scope,
)
from polisyos.runtime.quality.data_state_substrate import build_candidate_acquisition_world
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.world_model_record import (
    load_world_model_record,
    persist_world_model_record,
    world_model_artifact_views,
)
from tests.unit.runtime.quality.test_authority_reconciliation import _runtime_context
from tests.unit.runtime.quality.test_candidate_acquisition_world import (
    CELL_ID,
    TENANT_ID,
    TRANSACTION_TIME,
)
from tests.unit.runtime.quality.test_candidate_source_basis import _case_with_explicit_empty_prior

_KIND = "runtime_quality.acquisition_candidate_world_checkpoint"
_PRODUCER = "polisyos.runtime.acquisition_world_growth"
_PHASE = "candidate_world_prepared"
_COMPILED = "sha256:" + "c" * 64
_SCOPE = _Scope(
    "tenant-history",
    "cell-history",
    "run-history",
    "job-source",
    "job-action",
    "sha256:" + "a" * 64,
    2,
)


@dataclass(frozen=True)
class _CheckpointCase:
    store: artifacts.FileSystemCAS
    events: RuntimeDiagnosticEventLog
    checkpoint: CandidateAcquisitionWorldCheckpoint
    ref: artifacts.ArtifactRef
    event_id: str
    inputs: tuple[artifacts.InputRef, ...]
    compiled_ref: str | artifacts.ArtifactRef


def _checkpoint_case(
    tmp_path: Path,
    control: ControlPlaneStore,
    *,
    corruption: Literal["parent", "missing_parent", "producer", "closure_job", "closure_route"]
    | None = None,
    typed_compiled_ref: bool = False,
) -> _CheckpointCase:
    """Persist a test-owned checkpoint through the actual authority writer."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)

    def parent(name: str, kind: str) -> artifacts.ArtifactRef:
        return store.put_json(
            {"test_owned_input": name, "authority_purpose": "candidate_only"},
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    action_ref = parent("action", "runtime_quality.acquisition_candidate_action_receipt")
    compiled_ref: str | artifacts.ArtifactRef = _COMPILED
    if typed_compiled_ref:
        compiled_ref = parent(
            "compiled",
            "runtime_quality.test_candidate_experiment_compiled_input",
        )
    compiled_id = (
        str(compiled_ref.artifact_id)
        if type(compiled_ref) is artifacts.ArtifactRef
        else compiled_ref
    )
    checkpoint = CandidateAcquisitionWorldCheckpoint(
        candidate_action_ref=action_ref,
        intent_ref=parent("intent", "runtime_quality.acquisition_candidate_world_intent"),
        candidate_source_ref=parent("source", "runtime.quality.candidate_acquisition_source"),
        base_data_snapshot_ref=parent("base", "fabric.data_snapshot"),
        data_snapshot_ref=parent("candidate", "fabric.data_snapshot"),
        world_model_ref=parent("world", "runtime.quality.world_model_record"),
        action_phase_ref="sha256:" + "b" * 64,
        tenant_id=_SCOPE.tenant_id,
        cell_id=_SCOPE.cell_id,
        run_id=_SCOPE.run_id,
        action_job_id=_SCOPE.action_job_id,
        route_id=_SCOPE.route_id,
        transaction_time=datetime(2026, 11, 3, 12, tzinfo=UTC),
    )
    payload = checkpoint.model_dump(mode="json")
    identity = hashlib.sha256(
        canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
    ).hexdigest()
    action_identity = hashlib.sha256(
        canon.to_canonical_bytes(action_ref.model_dump(mode="json"))
    ).hexdigest()
    event_id = "evt_candidate_world_checkpoint_" + action_identity
    inputs = AcquisitionWorldGrowthBridge._candidate_world_checkpoint_inputs(checkpoint)
    actual_inputs = list(inputs)
    if corruption == "parent":
        actual_inputs[0] = actual_inputs[0].model_copy(update={"role": "unselected_action"})
    if corruption == "missing_parent":
        actual_inputs.pop()
    input_ids = tuple(
        dict.fromkeys((compiled_id, *(str(row.artifact_id) for row in actual_inputs)))
    )
    context = _runtime_context(compiled_id)
    context.update(
        evidence_id=identity,
        owner="team-runtime-quality",
        reader_contract=_KIND + ".reader",
        tenant_id=_SCOPE.tenant_id,
        cell_id=_SCOPE.cell_id,
        run_id=_SCOPE.run_id,
        job_id=_SCOPE.action_job_id if corruption == "closure_job" else _SCOPE.source_job_id,
        phase=_PHASE,
        same_input_closure={
            "closure_id": identity,
            "status": "closed",
            "tenant_id": _SCOPE.tenant_id,
            "cell_id": _SCOPE.cell_id,
            "run_id": _SCOPE.run_id,
            "job_id": _SCOPE.action_job_id if corruption == "closure_job" else _SCOPE.source_job_id,
            "closure_sha256": "sha256:" + "d" * 64
            if corruption == "closure_route"
            else _SCOPE.route_id,
            "evidence_input_refs": input_ids,
        },
        input_refs=input_ids,
        effective_mode_ref=_SCOPE.route_id,
    )
    result = write_runtime_authority_artifact(
        store,
        events,
        payload,
        artifacts.ArtifactWriteOptions(
            kind=_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="polisyos.runtime.CandidateAcquisitionWorldCheckpoint", version="1.1"
            ),
            producer=artifacts.ProducerInfo(
                component=_PRODUCER, version="unselected" if corruption == "producer" else "1.0"
            ),
            governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
            inputs=actual_inputs,
        ),
        **context,
        event_id=event_id,
        event_source=_PRODUCER,
        event_type="polisyos.runtime.diagnostic.producer_execution.v1",
        event_subject="run/" + _SCOPE.run_id + "/acquisition/" + _PHASE,
        state_before=None,
        state_after=_PHASE,
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    assert result.cas_ref.manifest_profile_sha256
    return _CheckpointCase(
        store,
        events,
        checkpoint,
        result.cas_ref,
        event_id,
        inputs,
        compiled_ref,
    )


def _read(
    case: _CheckpointCase,
    *,
    store: artifacts.ArtifactStore | None = None,
    events: RuntimeDiagnosticEventLog | None = None,
) -> CandidateAcquisitionWorldCheckpoint:
    return _owner_record(
        store=store or case.store,
        events=events or case.events,
        ref=case.ref,
        record_type=CandidateAcquisitionWorldCheckpoint,
        kind=_KIND,
        schema="polisyos.runtime.CandidateAcquisitionWorldCheckpoint",
        version="1.1",
        phase=_PHASE,
        event_id=case.event_id,
        inputs=case.inputs,
        compiled_ref=case.compiled_ref,
        scope=_SCOPE,
    )


def test_historical_checkpoint_projects_typed_compiled_ref_to_selected_scope_id(
    tmp_path: Path,
) -> None:
    """A real selected compiled CAS ref binds its ID in the exact owner closure."""
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "events.sqlite3")
    ) as control:
        case = _checkpoint_case(tmp_path, control, typed_compiled_ref=True)
        assert type(case.compiled_ref) is artifacts.ArtifactRef
        assert case.compiled_ref.manifest_profile_sha256 is not None
        assert case.store.verify(case.compiled_ref).ok

        manifest = case.store.get_manifest(case.ref)
        closure = manifest.same_input_closure
        assert closure is not None
        assert closure.evidence_input_refs[0] == str(case.compiled_ref.artifact_id)
        assert closure.tenant_id == _SCOPE.tenant_id
        assert closure.cell_id == _SCOPE.cell_id
        assert closure.run_id == _SCOPE.run_id
        assert closure.job_id == _SCOPE.source_job_id
        assert closure.closure_sha256 == _SCOPE.route_id

        assert _read(case) == case.checkpoint


def test_historical_checkpoint_reopens_exact_owner_without_live_job_or_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cold read keeps the source-job event distinct from the action job."""
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "events.sqlite3")
    ) as control:
        case = _checkpoint_case(tmp_path, control)
        reader = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)
        before = case.store.manifest_inventory_snapshot(kind=_KIND)
        event_ids = tuple(row.event.event_id for row in case.events.list_events(limit=100))

        def refuse(*args: object, **kwargs: object) -> None:
            del args, kwargs
            pytest.fail("historical checkpoint replay attempted a live job read or write")

        monkeypatch.setattr(control, "current_execution_job_record", refuse)
        monkeypatch.setattr(control, "current_execution_job_admission", refuse)
        assert not hasattr(reader, "put_json")
        assert not hasattr(reader, "put_bytes")
        assert _read(case, store=reader) == case.checkpoint
        assert (
            case.events.list_events(event_id=case.event_id, limit=2)[0].event.job_id
            == _SCOPE.source_job_id
        )
        assert case.store.manifest_inventory_snapshot(kind=_KIND) == before
        assert tuple(row.event.event_id for row in case.events.list_events(limit=100)) == event_ids


@pytest.mark.parametrize(
    "corruption", ["parent", "missing_parent", "producer", "closure_job", "closure_route"]
)
def test_historical_checkpoint_refuses_real_owner_profile_substitutions(
    tmp_path: Path,
    corruption: Literal["parent", "missing_parent", "producer", "closure_job", "closure_route"],
) -> None:
    """Valid bytes and a durable event cannot repair another selected owner profile."""
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "events.sqlite3")
    ) as control:
        case = _checkpoint_case(tmp_path, control, corruption=corruption)
        assert case.store.verify(case.ref).ok
        assert case.events.list_events(event_id=case.event_id, limit=2)
        with pytest.raises(ValueError, match="candidate_reentry_history_owner_profile_mismatch"):
            _read(case)


def test_historical_checkpoint_requires_durable_event_in_addition_to_selected_cas(
    tmp_path: Path,
) -> None:
    """The actual CAS side alone cannot make a producer-owned checkpoint replayable."""
    with (
        closing(
            ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "events.sqlite3")
        ) as control,
        closing(
            ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "empty-events.sqlite3")
        ) as empty_control,
    ):
        case = _checkpoint_case(tmp_path, control)
        assert _read(case) == case.checkpoint
        empty_events = RuntimeDiagnosticEventLog(store=empty_control, artifact_store=case.store)
        with pytest.raises(ValueError):
            _read(case, events=empty_events)


def test_historical_checkpoint_never_falls_back_to_a_sibling_manifest(tmp_path: Path) -> None:
    """Removing the selected profile refuses even while identical bytes remain."""
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "events.sqlite3")
    ) as control:
        case = _checkpoint_case(tmp_path, control)
        sibling = case.store.put_json(
            case.checkpoint.model_dump(mode="json"),
            artifacts.ArtifactWriteOptions(
                kind=_KIND,
                media_type="application/json",
                producer=artifacts.ProducerInfo(component="test.sibling", version="1"),
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        assert sibling.artifact_id == case.ref.artifact_id
        assert sibling.manifest_profile_sha256 != case.ref.manifest_profile_sha256
        assert _read(case) == case.checkpoint
        selected_path = case.store._manifest_path_for_ref(
            case.ref.artifact_id, case.ref.manifest_profile_sha256
        )
        held_path = selected_path.with_name(selected_path.name + ".held")
        selected_path.rename(held_path)
        try:
            reader = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)
            assert reader.verify(sibling).ok
            with pytest.raises(
                ValueError, match="candidate_reentry_history_selected_profile_invalid"
            ):
                _read(case, store=reader)
        finally:
            held_path.rename(selected_path)
        assert _read(case) == case.checkpoint


def test_real_world_builder_clock_is_verified_without_rebinding_retained_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual world emission owns its new clock; retained scope stays load-bearing.

    This is a real candidate-source/DataSnapshot/native-world producer fixture,
    not proof of the separate action/N6 receipt chain.
    """
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _case_with_explicit_empty_prior(tmp_path, monkeypatch)
        built = build_candidate_acquisition_world(
            case.store,
            problem=case.problem,
            base_world_model=case.base.record,
            substrate_registry=case.substrate_registry,
            substrate_registry_artifact_ref=case.substrate_registry_ref,
            materialization=case.materialization,
            workspace_dir=tmp_path / "actual-candidate-world",
            transaction_time=TRANSACTION_TIME,
            authority=case.source_case.authority,
        )
        ref = built.world_model.record_ref
        original_bytes = case.store.get_bytes(ref)
        reader = artifacts.FileSystemCAS.open_existing_read_only(case.store.root)
        selected = load_world_model_record(reader, ref)
        assert selected.created_at != case.base.record.created_at
        _require_world_creation_time(selected)
        retained = _retained_world_values(selected)
        assert retained == _retained_world_values(case.base.record)
        assert retained["population_scope"] == case.base.record.population_scope
        assert retained["region_or_jurisdiction"] == case.base.record.region_or_jurisdiction
        assert retained["resolution"] == case.base.record.resolution
        assert "created_at" not in retained

        # The ordinary WMR schema deliberately permits strings. Persist invalid
        # producer clocks through that actual owner to exercise our stricter
        # historical clock boundary after the same selected positive above.
        for created_at in ("2026-11-03T12:00:00", "unestablished-clock"):
            invalid = selected.model_copy(update={"created_at": created_at})
            invalid_ref = persist_world_model_record(
                case.store, invalid, return_selected_profile=True
            )
            invalid_read = load_world_model_record(reader, invalid_ref)
            with pytest.raises(
                ValueError, match="candidate_reentry_history_world_created_at_invalid"
            ):
                _require_world_creation_time(invalid_read)
        assert case.store.get_bytes(ref) == original_bytes
        assert load_world_model_record(reader, ref).created_at == selected.created_at
        views = world_model_artifact_views(selected)
        bindings = load_input_bindings(reader, views.input_bindings_ref)
        owned_state = bindings.bound_state_snapshot_ref
        assert type(owned_state) is StateSnapshotRef
        assert type(views.bound_state_snapshot_ref) is artifacts.ArtifactRef
        assert _same_view(reader, owned_state, views.bound_state_snapshot_ref)
        qualified_state = artifacts.profile_bound_ref(reader, owned_state)
        state_manifest = case.store.get_manifest(qualified_state)
        foreign_profile = case.store.put_bytes(
            case.store.get_bytes(qualified_state),
            artifacts.ArtifactWriteOptions(
                kind=qualified_state.kind,
                media_type=qualified_state.media_type,
                schema=state_manifest.artifact_schema,
                canon=state_manifest.canon,
                inputs=state_manifest.inputs,
                governance=state_manifest.governance,
                tenant_context=state_manifest.tenant_context,
                producer=artifacts.ProducerInfo(component="test.foreign-state-view", version="1"),
            ),
            return_selected_profile=True,
        )
        assert foreign_profile.artifact_id == qualified_state.artifact_id
        assert foreign_profile.manifest_profile_sha256 != qualified_state.manifest_profile_sha256
        assert not _same_view(reader, qualified_state, foreign_profile)


def test_reissued_n4_origin_keeps_selected_root_across_multiple_occurrences(
    tmp_path: Path,
) -> None:
    """Reference binding retains the actual root view, not the immediate parent.

    These are test-owned CAS selectors for the binding rule. The full source
    reader must separately reopen V3/context/model bytes before using the rule.
    """
    store = artifacts.FileSystemCAS(tmp_path / "origins")
    options = artifacts.ArtifactWriteOptions(
        kind="runtime.quality.n4_candidate_scenario_source", media_type="application/json"
    )
    root = store.put_json({"fixture_origin": "root"}, options, return_selected_profile=True)
    parent = store.put_json(
        {"fixture_origin": "next", "origin_source_ref": root.model_dump(mode="json")},
        options,
        return_selected_profile=True,
    )
    _require_n4_origin(actual_origin_ref=root, prior_source_ref=root, prior_origin_ref=None)
    _require_n4_origin(actual_origin_ref=root, prior_source_ref=parent, prior_origin_ref=root)
    with pytest.raises(ValueError, match="candidate_reentry_history_n4_origin_mismatch"):
        _require_n4_origin(actual_origin_ref=parent, prior_source_ref=parent, prior_origin_ref=root)
    sibling = store.put_json(
        {"fixture_origin": "root"},
        artifacts.ArtifactWriteOptions(
            kind=options.kind,
            media_type=options.media_type,
            producer=artifacts.ProducerInfo(component="test.unselected-origin", version="1"),
        ),
        return_selected_profile=True,
    )
    assert sibling.artifact_id == root.artifact_id
    assert sibling.manifest_profile_sha256 != root.manifest_profile_sha256
    with pytest.raises(ValueError, match="candidate_reentry_history_n4_origin_mismatch"):
        _require_n4_origin(
            actual_origin_ref=sibling, prior_source_ref=parent, prior_origin_ref=root
        )
