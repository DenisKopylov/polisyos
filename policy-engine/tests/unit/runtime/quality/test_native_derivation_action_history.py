"""Native route history and selector-component controls.

History checks exercise receipt persistence only. The attempt-pointer test
proves selected-manifest addressing only; neither proves paid acquisition. The
explicit quote fixtures do not establish a current source grant or replace the
served native-action test.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.http.services.control.run_lifecycle import AcquisitionRouteLoopAuthoritySink
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_planner import (
    persist_native_derivation_leaf_cost_profile,
    produce_acquisition_cost_basis_record,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoopReceipt,
    AcquisitionRoutePhaseReceipt,
    NativeDerivationLeafProviderSelection,
)
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests.unit.runtime.quality.test_native_derivation_leaf_cost_profile import (
    _profile,
    _profile_scope,
    _put_selected_fact,
)


def _owners(tmp_path: Path):
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite")
    events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=store, event_log=events, control_store=control
    )
    return store, control, events, sink


def _native_requested(store, *, index: int, now: datetime):
    scope, quote = _profile_scope(store)
    scope = scope.model_copy(
        update={
            "source_node_id": f"leaf-{index}",
            "requirement_gap_id": f"gap-{index}",
            "compiled_requirement_ref": f"compiled-{index}",
            "planner_record_id": f"record-{index}",
        }
    )
    profile_ref = persist_native_derivation_leaf_cost_profile(
        store, _profile(scope, quote, now=now)
    )
    cost = produce_acquisition_cost_basis_record(
        missing_distribution=scope.missing_distribution,
        strategy=scope.strategy,
        owner_declared_profile_ref=profile_ref,
        store=store,
        expected_scope=scope,
        now=now,
    )
    assert cost is not None
    provider = NativeDerivationLeafProviderSelection(
        source_node_id=scope.source_node_id,
        supplier_ref=scope.selected_supplier_ref,
        authority_entry_id="acquisition-authority:sha256:" + str(index) * 64,
        connector_id="demonstration.connector",
    )
    phase = AcquisitionRoutePhaseReceipt(
        schema_version="AcquisitionRoutePhaseReceipt@1.3",
        receipt_id=f"native-job-{index}.requested",
        tenant_id=scope.tenant_id,
        cell_id=scope.cell_id,
        run_id=scope.run_id,
        source_job_id=scope.source_job_id,
        route_id="sha256:" + str(index) * 64,
        action_generation=1,
        job_id=f"native-job-{index}",
        compiled_ref="sha256:" + "a" * 64,
        planner_report_hash="sha256:" + "b" * 64,
        cost_basis_hash=cost.record_content_hash,
        decision_ref="sha256:" + "c" * 64,
        coarse_phase="requested",
        receipt_phase="requested",
        recovery_state="none",
        owner_declared_profile_ref=profile_ref,
        native_leaf_provider_selection=provider,
        generated_at=now,
    )
    return phase


def test_two_native_leaf_actions_keep_distinct_events_and_selected_terminal_profiles(
    tmp_path: Path,
) -> None:
    """Different leaf generations both start at one without colliding events."""
    store, control, events, sink = _owners(tmp_path)
    now = datetime.now(UTC)
    heads = []
    phase_heads = []
    for index in (1, 2):
        requested = _native_requested(store, index=index, now=now)
        requested_head = sink.persist_phase(requested)
        executing = requested.model_copy(
            update={
                "receipt_id": f"native-job-{index}.executing",
                "coarse_phase": "executing",
                "receipt_phase": "executing",
                "predecessor_receipt_ref": requested_head.receipt_ref,
                "generated_at": now + timedelta(microseconds=1),
            }
        )
        executing_head = sink.persist_phase(executing)
        no_growth = _put_selected_fact(
            store, kind="test.controlled_no_growth", name=f"no-growth-{index}"
        )
        terminal = AcquisitionRouteLoopReceipt(
            **{
                key: getattr(executing, key)
                for key in (
                    "tenant_id",
                    "cell_id",
                    "run_id",
                    "source_job_id",
                    "route_id",
                    "action_generation",
                    "job_id",
                    "compiled_ref",
                    "planner_report_hash",
                    "cost_basis_hash",
                    "decision_ref",
                    "owner_declared_profile_ref",
                    "native_leaf_provider_selection",
                )
            },
            schema_version="AcquisitionRouteLoopReceipt@1.2",
            receipt_id=f"native-job-{index}.terminal",
            terminal_outcome="quarantined_no_growth",
            predecessor_receipt_ref=executing_head.receipt_ref,
            owner_receipt_refs=(str(no_growth.artifact_id),),
            generated_at=now + timedelta(microseconds=2),
        )
        heads.append(sink.persist_terminal(terminal))
        phase_heads.append(requested_head)

    fresh = AcquisitionRouteLoopAuthoritySink(
        artifact_store=store, event_log=events, control_store=control
    )
    assert heads[0].durable_event_id != heads[1].durable_event_id
    assert phase_heads[0].durable_event_id != phase_heads[1].durable_event_id
    for head in heads:
        assert head.action_generation == 1
        assert head.receipt_manifest_profile_sha256 is not None
        history = fresh.verify_action_head(head)
        assert history.latest_receipt.terminal_outcome == "quarantined_no_growth"
        assert len(history.phase_chain) == 3
        assert all(
            row.receipt.owner_declared_profile_ref is not None for row in history.phase_chain
        )

    # Poison only the ancestor's default manifest. The selected sidecar and
    # original SQL pin stay intact: a correct reader still opens the history.
    selected = phase_heads[0]
    artifact_id = artifacts.ArtifactID.model_validate(selected.receipt_ref)
    default = store._manifest_path_for_ref(artifact_id, None)
    default_bytes = default.read_bytes()
    poisoned = json.loads(default_bytes)
    poisoned["producer"]["component"] = "tests.untrusted_default_view"
    default.write_text(json.dumps(poisoned, sort_keys=True, separators=(",", ":")))
    path = store._manifest_path_for_ref(artifact_id, selected.receipt_manifest_profile_sha256)
    held = path.with_suffix(path.suffix + ".held")
    try:
        assert (
            fresh.verify_action_head(heads[0]).latest_receipt.terminal_outcome
            == "quarantined_no_growth"
        )
        # Without the selected ancestor view the poisoned default cannot stand
        # in for the actual SQL-selected profile, even though payload bytes match.
        path.rename(held)
        try:
            with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
                fresh.verify_action_head(heads[0])
        finally:
            held.rename(path)
        assert (
            fresh.verify_action_head(heads[0]).latest_receipt.terminal_outcome
            == "quarantined_no_growth"
        )
    finally:
        default.write_bytes(default_bytes)


def test_legacy_requested_wire_and_event_id_do_not_gain_native_fields(tmp_path: Path) -> None:
    store, _control, _events, sink = _owners(tmp_path)
    native = _native_requested(store, index=1, now=datetime.now(UTC))
    legacy = AcquisitionRoutePhaseReceipt.model_validate(
        {
            **native.model_dump(
                mode="python",
                exclude={"owner_declared_profile_ref", "native_leaf_provider_selection"},
            ),
            "schema_version": "AcquisitionRoutePhaseReceipt@1.0",
            "job_id": "legacy-job",
            "receipt_id": "legacy-job.requested",
        }
    )
    head = sink.persist_phase(legacy)
    assert head.durable_event_id == "evt_acquisition_1_requested"
    assert head.receipt_manifest_profile_sha256 is None
    assert "owner_declared_profile_ref" not in legacy.model_dump(mode="json")
    assert "native_leaf_provider_selection" not in legacy.model_dump(mode="json")


def test_native_attempt_pointer_selects_exact_attempt_view_without_default_fallback(
    tmp_path: Path,
) -> None:
    """Exercise pointer selector semantics over real CAS views, not acquisition proof."""
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    fresh_reader = artifacts.FileSystemCAS(tmp_path / "cas")
    payload = {"selector_component_fixture": "attempt-payload", "schema_version": "1.1"}
    selected = store.put_json(
        payload,
        artifacts.PutOptions(
            kind="runtime_quality.acquisition_world_growth_attempt",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name="AcquisitionWorldGrowthAttempt", version="1.1"),
            producer=artifacts.ProducerInfo(
                component="tests.original_attempt_selector", version="1.0"
            ),
        ),
        return_selected_profile=True,
    )
    assert selected.kind == "runtime_quality.acquisition_world_growth_attempt"
    assert selected.manifest_profile_sha256 is not None
    selected_manifest = fresh_reader.get_manifest(selected)
    assert selected_manifest.artifact_schema is not None
    assert selected_manifest.artifact_schema.name == "AcquisitionWorldGrowthAttempt"
    assert selected_manifest.artifact_schema.version == "1.1"
    pointer = tmp_path / "selected.attempt.json"
    AcquisitionWorldGrowthBridge._write_pointer(
        pointer, str(selected.artifact_id), selected_ref=selected
    )

    selected_ref = AcquisitionWorldGrowthBridge._attempt_pointer_ref(pointer, require_selected=True)
    assert selected_ref == selected
    assert AcquisitionWorldGrowthBridge._attempt_pointer_id(selected_ref) == str(
        selected.artifact_id
    )
    assert fresh_reader.get_manifest(selected_ref) == selected_manifest

    # The default view can be changed by another writer without changing the
    # pointer's retained exact selector or the reader's chosen selected view.
    default_path = fresh_reader._manifest_path_for_ref(selected.artifact_id, None)
    default_bytes = default_path.read_bytes()
    poisoned = json.loads(default_bytes)
    poisoned["producer"]["component"] = "tests.competing_default_producer"
    default_path.write_text(json.dumps(poisoned, sort_keys=True, separators=(",", ":")))
    selected_path = fresh_reader._manifest_path_for_ref(
        selected.artifact_id, selected.manifest_profile_sha256
    )
    selected_bytes = selected_path.read_bytes()
    held_path = selected_path.with_suffix(selected_path.suffix + ".held")
    try:
        assert (
            AcquisitionWorldGrowthBridge._attempt_pointer_ref(pointer, require_selected=True)
            == selected
        )
        assert artifacts.FileSystemCAS(tmp_path / "cas").get_manifest(
            selected_ref
        ).producer.component != ("tests.competing_default_producer")
        selected_path.rename(held_path)
        with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
            artifacts.FileSystemCAS(tmp_path / "cas").get_manifest(selected_ref)
        assert (
            AcquisitionWorldGrowthBridge._attempt_pointer_ref(pointer, require_selected=True)
            == selected
        )
    finally:
        if held_path.exists():
            held_path.rename(selected_path)
        assert selected_path.read_bytes() == selected_bytes
        default_path.write_bytes(default_bytes)
    assert artifacts.FileSystemCAS(tmp_path / "cas").get_manifest(selected_ref) == (
        selected_manifest
    )

    legacy_pointer = tmp_path / "legacy.attempt.json"
    AcquisitionWorldGrowthBridge._write_pointer(legacy_pointer, str(selected.artifact_id))
    assert AcquisitionWorldGrowthBridge._attempt_pointer_ref(
        legacy_pointer, require_selected=False
    ) == str(selected.artifact_id)
    with pytest.raises(ValueError, match="native_paid_attempt_selected_profile_required"):
        AcquisitionWorldGrowthBridge._attempt_pointer_ref(legacy_pointer, require_selected=True)

    wrong_kind_path = tmp_path / "wrong-kind.attempt.json"
    with pytest.raises(ValueError, match="acquisition_attempt_pointer_selected_profile_mismatch"):
        AcquisitionWorldGrowthBridge._write_pointer(
            wrong_kind_path,
            str(selected.artifact_id),
            selected_ref=selected.model_copy(update={"kind": "unrelated.kind"}),
        )
    assert not wrong_kind_path.exists()

    other = store.put_json(
        {"selector_component_fixture": "different-payload"},
        artifacts.PutOptions(
            kind="runtime_quality.acquisition_world_growth_attempt",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name="AcquisitionWorldGrowthAttempt", version="1.1"),
        ),
        return_selected_profile=True,
    )
    wrong_id_path = tmp_path / "wrong-id.attempt.json"
    with pytest.raises(ValueError, match="acquisition_attempt_pointer_selected_profile_mismatch"):
        AcquisitionWorldGrowthBridge._write_pointer(
            wrong_id_path, str(selected.artifact_id), selected_ref=other
        )
    assert not wrong_id_path.exists()


@pytest.mark.parametrize("persistence_path", ["growth", "candidate_experiment"])
def test_native_writer_recovery_uses_canonical_authority_view_inventory(
    tmp_path: Path,
    persistence_path: str,
) -> None:
    """Reconcile actual writer/CAS/event identity; this is not a paid source result."""
    store, control, events, _sink = _owners(tmp_path)
    phase = _native_requested(store, index=1, now=datetime.now(UTC))
    source = _put_selected_fact(store, kind="test.writer_input", name="writer-input")
    closure = SimpleNamespace(
        tenant_id=phase.tenant_id,
        cell_id=phase.cell_id,
        run_id=phase.run_id,
        source_job_id=phase.source_job_id,
        compiled_ref=str(source.artifact_id),
        route_id=phase.route_id,
        cost_basis_hash=phase.cost_basis_hash,
    )
    # Isolate the already canonical persistence mechanism. Neither this body
    # nor the local writer scope is offered as valid acquisition evidence.
    payload = {
        "selector_component_fixture": "canonical-authority-writer",
        "action_phase_ref": "sha256:" + "d" * 64,
    }
    kind = "runtime_quality.acquisition_world_growth_attempt"
    schema = "AcquisitionWorldGrowthAttempt"
    generic = store.put_json(
        payload,
        artifacts.PutOptions(
            kind=kind,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=schema, version="1.1"),
            producer=artifacts.ProducerInfo(component="tests.generic_view", version="1.0"),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    assert store.get_manifest(str(generic.artifact_id)).authority is None

    def writer(current_store):
        bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
        bridge.artifact_store = current_store
        bridge.event_log = RuntimeDiagnosticEventLog(store=control, artifact_store=current_store)
        return bridge

    def persist(current_store):
        bridge = writer(current_store)
        if persistence_path == "growth":
            return bridge._persist(
                closure, payload, kind, schema, "admission_pending", return_selected_profile=True
            )
        origin = SimpleNamespace(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
            policy_ref=source,
            policy_scope=SimpleNamespace(compiled_ref=source),
        )
        return bridge._persist_candidate_experiment_receipt(
            origin=origin,
            payload=payload,
            kind=kind,
            schema=schema,
            schema_version="1.1",
            phase="admission_pending",
            artifact_inputs=(),
        )

    selected = persist(store)
    assert isinstance(selected, artifacts.ArtifactRef)
    assert selected.artifact_id == generic.artifact_id
    assert selected.manifest_profile_sha256 != generic.manifest_profile_sha256
    assert store.get_manifest(selected).authority is not None
    assert store.get_manifest(str(generic.artifact_id)).authority is None
    original_manifest = store.get_manifest(selected)
    rows_before = events.list_events(run_id=closure.run_id, job_id=closure.source_job_id)
    assert len(rows_before) == 1
    original_event = rows_before[0].event
    expected_event_prefix = (
        "evt_acquisition_growth_" if persistence_path == "growth" else "evt_candidate_experiment_"
    )
    assert original_event.event_id.startswith(expected_event_prefix)
    subject_path = "acquisition" if persistence_path == "growth" else "candidate-experiment"
    assert original_event.event_subject == f"run/{closure.run_id}/{subject_path}/admission_pending"

    fresh = artifacts.FileSystemCAS(tmp_path / "cas")
    assert persist(fresh) == selected
    assert fresh.get_manifest(selected) == original_manifest
    assert events.list_events(run_id=closure.run_id, job_id=closure.source_job_id)[0].event == (
        original_event
    )

    # The non-authority default cannot replace a lost selected owner view, and
    # idempotent replay must not publish another event or recreate that view.
    selected_path = store._manifest_path_for_ref(
        selected.artifact_id, selected.manifest_profile_sha256
    )
    held_path = selected_path.with_suffix(selected_path.suffix + ".held")
    selected_path.rename(held_path)
    try:
        with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
            persist(artifacts.FileSystemCAS(tmp_path / "cas"))
        assert not selected_path.exists()
        assert len(events.list_events(run_id=closure.run_id, job_id=closure.source_job_id)) == 1
    finally:
        held_path.rename(selected_path)
    assert persist(artifacts.FileSystemCAS(tmp_path / "cas")) == selected


def test_native_selected_writer_and_provider_preflight_refuse_backend_without_inventory(
    tmp_path: Path,
) -> None:
    """An unsupported legacy-default backend cannot start selected Native work."""
    store, control, events, _sink = _owners(tmp_path)

    class DefaultOnlyStore:
        def __getattr__(self, name):
            if name == "inventory_snapshot":
                raise AttributeError(name)
            return getattr(store, name)

    bridge = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = DefaultOnlyStore()
    bridge.event_log = events
    subject = _put_selected_fact(store, kind="test.inventory_subject", name="known-quote")
    supported = AcquisitionWorldGrowthBridge.__new__(AcquisitionWorldGrowthBridge)
    supported.artifact_store = store
    supported._require_profile_inventory(subject)
    closure = SimpleNamespace(
        native_derivation_leaf_scope=object(), owner_declared_profile_ref=subject
    )
    with pytest.raises(ValueError, match="acquisition_world_growth_profile_inventory_unavailable"):
        bridge.require_native_derivation_provider_bindings(closure, ())
    assert events.list_events(limit=10) == []
    assert control.list_diagnostic_events(limit=10) == []
    with pytest.raises(ValueError, match="acquisition_world_growth_profile_inventory_unavailable"):
        bridge._persist(
            SimpleNamespace(
                tenant_id="tenant-a", cell_id="cell-a", run_id="run-a", source_job_id="job-a"
            ),
            {"selector_component_fixture": "unsupported-inventory"},
            "runtime_quality.acquisition_world_growth_attempt",
            "AcquisitionWorldGrowthAttempt",
            "admission_pending",
            return_selected_profile=True,
        )
    assert events.list_events(limit=10) == []
