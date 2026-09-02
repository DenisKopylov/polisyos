from __future__ import annotations

import hashlib
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyEvent,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionTriggerRecord,
    DecisionTriggerSpec,
    DecisionTriggerType,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
    EpochTransitionVerificationReceipt,
    EpochValidityBatchTarget,
)
from polisyos.core.contracts.feedback import DecisionMonitoringContract
from polisyos.scientist.validation.decision_validity import (
    DecisionValidityService,
    _DecisionLineageState,
    _DecisionValidityStateStore,
    _load_baseline,
    _load_envelope,
)
from polisyos.runtime.quality.epoch_validity_cascade import (
    EpochDependencyDenominatorReceipt,
    EpochDependencyEdge,
    EpochDependencyGraph,
    EpochValidityTransitionArtifact,
    _canonical_bytes,
    _semantic_hash,
    resolve_owner_target_dispositions,
)


class _StoreWithRootProxy:
    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store
        self.root = store.root

    def __getattr__(self, name: str):
        return getattr(self._store, name)


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def test_concurrent_same_packet_persistence_has_no_fixed_temp_collision(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _DecisionValidityStateStore(FileSystemCAS(tmp_path))
    dedupe_key = "concurrent-packet-dedupe"
    destination = state._dedupe_path(dedupe_key)
    replace_barrier = threading.Barrier(2)
    original_replace = Path.replace
    errors: list[BaseException] = []

    def synchronized_replace(source: Path, target: Path) -> Path:
        if target == destination:
            replace_barrier.wait(5)
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", synchronized_replace)

    def persist(event_id: str) -> None:
        try:
            state.save_dedupe_event_id(dedupe_key, event_id)
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    event_ids = ("event-one", "event-two")
    writers = [threading.Thread(target=persist, args=(event_id,)) for event_id in event_ids]
    for writer in writers:
        writer.start()
    for writer in writers:
        writer.join(5)

    assert all(not writer.is_alive() for writer in writers)
    assert errors == []
    assert state.load_dedupe_event_id(dedupe_key) in event_ids
    assert [item for item in destination.parent.iterdir() if item.suffix == ".tmp"] == []


def test_atomic_dedupe_write_failure_cleans_only_owned_temp(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _DecisionValidityStateStore(FileSystemCAS(tmp_path))
    dedupe_key = "failed-packet-dedupe"
    destination = state._dedupe_path(dedupe_key)
    unrelated = destination.parent / ".unrelated.tmp"
    unrelated_payload = b"unrelated-temp-contents"
    unrelated.write_bytes(unrelated_payload)
    failure = OSError("injected_atomic_replace_failure")
    owned_temps: list[Path] = []
    original_replace = Path.replace

    def fail_destination_replace(source: Path, target: Path) -> Path:
        if target == destination:
            owned_temps.append(source)
            raise failure
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_destination_replace)

    with pytest.raises(OSError, match="injected_atomic_replace_failure") as caught:
        state.save_dedupe_event_id(dedupe_key, "event-failed")

    assert caught.value is failure
    assert not destination.exists()
    assert state.load_dedupe_event_id(dedupe_key) is None
    assert len(owned_temps) == 1
    assert owned_temps[0].parent == destination.parent
    assert owned_temps[0].suffix == ".tmp"
    assert not owned_temps[0].exists()
    assert unrelated.read_bytes() == unrelated_payload


def test_epoch_batch_rejects_fake_verifier_provenance_without_state(tmp_path) -> None:
    """A caller-shaped receipt cannot create the owner batch state."""

    store = FileSystemCAS(tmp_path)

    class _FakeVerifier:
        def verify(self, **_kwargs):
            return EpochTransitionVerificationReceipt(
                transition_artifact_ref=_put_json(
                    store,
                    {"transition": "fake"},
                    kind="chronology.epoch_transition",
                ),
                transition_content_hash="sha256:" + "1" * 64,
                requested_query_context_ref="sha256:" + "2" * 64,
                authority_purpose="decision_validity_epoch_transition",
                verifier_provenance_ref=_put_json(
                    store,
                    {"verifier": "caller"},
                    kind="chronology.epoch_transition_verifier",
                ),
                dependency_keys=("epoch::fixture",),
                dependency_denominator_ref="sha256:" + "3" * 64,
                adjudication_denominator_ref="sha256:" + "4" * 64,
                targets=(
                    EpochValidityBatchTarget(
                        packet_ref="sha256:" + "5" * 64,
                        decision_lineage_key="lineage_fixture",
                        dependency_key="epoch::fixture",
                        status=DecisionValidityStatus.STALE,
                        reason="epoch_advanced",
                    ),
                ),
                predicate_class="consumer_asserted",
            )

    service = DecisionValidityService(store, epoch_transition_verifier=_FakeVerifier())
    with pytest.raises(ValueError, match="verifier_provenance_untrusted"):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=_put_json(
                store,
                {"transition": "fake"},
                kind="chronology.epoch_transition",
            ),
            requested_query_context_ref="sha256:" + "2" * 64,
        )
    assert service.state_generation() == 0


def test_epoch_batch_rejects_corrupt_appointed_verifier_provenance_without_batch_state(
    tmp_path,
) -> None:
    store, service, verifier, transition, query_ref, _ = _epoch_batch_fixture(
        tmp_path,
        packet_count=1,
    )
    assert verifier.verifier_provenance_ref is not None
    before_generation = service.state_generation()
    provenance_blob, _ = store._paths(verifier.verifier_provenance_ref.artifact_id)
    provenance_blob.write_bytes(b"corrupt-appointed-verifier")

    with pytest.raises(ValueError, match="verifier_provenance_untrusted"):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )

    assert service.state_generation() == before_generation
    assert service._state.list_epoch_pending() == ()


class _AppointedEpochVerifier:
    def __init__(self, verifier_provenance_ref) -> None:
        self.verifier_provenance_ref = verifier_provenance_ref
        self.receipt: EpochTransitionVerificationReceipt | None = None

    def verify(self, **_kwargs):
        assert self.receipt is not None
        return self.receipt


def _epoch_batch_fixture(tmp_path, *, packet_count: int = 2):
    store = FileSystemCAS(tmp_path)
    provenance = _put_json(
        store,
        {"verifier": "appointed"},
        kind="chronology.epoch_transition_verifier",
    )
    verifier = _AppointedEpochVerifier(provenance)
    service = DecisionValidityService(store, epoch_transition_verifier=verifier)
    packet_rows = []
    for ordinal in range(packet_count):
        envelope = DecisionValidityEnvelope(
            decision_lineage_key=f"epoch_lineage_{ordinal}",
            policy_fingerprint=f"epoch_policy_{ordinal}",
            knowledge_basis=DecisionBasisSection(
                dependencies=[
                    DecisionDependencyRef(
                        kind=DecisionDependencyKind.SEMANTIC_EPOCH,
                        key="epoch::owner-fixture",
                        artifact_id="epoch-owner-fixture",
                    )
                ]
            ),
        )
        baseline = DecisionValidityEvaluation(
            decision_lineage_key=envelope.decision_lineage_key,
            status=DecisionValidityStatus.ACTIVE,
            dependency_keys=envelope.dependency_keys(),
        )
        packet = _put_json(
            store,
            {
                "schema_version": "3.4",
                "decision_validity_envelope": envelope.model_dump(mode="json"),
                "decision_validity_baseline": baseline.model_dump(mode="json"),
            },
            kind="scientist.decision_packet",
        )
        packet_ref = str(packet.artifact_id)
        service.register_decision_packet(
            packet_ref=packet_ref,
            envelope=envelope,
            baseline=baseline,
        )
        packet_rows.append((packet_ref, envelope.decision_lineage_key))
    transition = _put_json(
        store,
        {"transition": "epoch-owner-fixture"},
        kind="chronology.epoch_transition",
    )
    raw = store.get_bytes(transition.artifact_id)
    _, denominator_ref = service._resolve_epoch_target_denominator(
        dependency_keys=("epoch::owner-fixture",)
    )
    query_ref = "sha256:" + "2" * 64
    verifier.receipt = EpochTransitionVerificationReceipt(
        transition_artifact_ref=transition,
        transition_content_hash="sha256:" + hashlib.sha256(raw).hexdigest(),
        requested_query_context_ref=query_ref,
        authority_purpose="decision_validity_epoch_transition",
        verifier_provenance_ref=provenance,
        dependency_keys=("epoch::owner-fixture",),
        dependency_denominator_ref=denominator_ref,
        adjudication_denominator_ref="sha256:" + "4" * 64,
        targets=tuple(
            EpochValidityBatchTarget(
                packet_ref=packet_ref,
                decision_lineage_key=lineage,
                dependency_key="epoch::owner-fixture",
                status=DecisionValidityStatus.STALE,
                reason="epoch_advanced",
            )
            for packet_ref, lineage in packet_rows
        ),
        predicate_class="independently_reconciled",
    )
    return store, service, verifier, transition, query_ref, packet_rows


def _before_epoch_owner_state(
    service: DecisionValidityService,
    packet_refs: tuple[str, ...],
):
    """Capture every Decision-Validity value a refused sidecar must preserve."""

    packet_state = []
    for packet_ref in packet_refs:
        state = service._state.load_packet(packet_ref)
        assert state is not None
        packet_state.append(
            (
                service.read_current_projection(packet_ref),
                tuple(state.lifecycle_events),
                tuple(state.lifecycle_jobs),
                tuple(state.transition_history),
            )
        )
    return (
        tuple(packet_state),
        service._state.list_epoch_pending(),
        service.enumerate_completed_epoch_batch_evidence(),
        service._state.list_epoch_reconciliation_admission_bindings(),
    )


def test_epoch_denominator_reconciliation_receipt_refuses_distinct_member_sets(
    tmp_path,
) -> None:
    """A valid pair of owner projections cannot coerce a false member join."""

    store = FileSystemCAS(tmp_path / "cas")
    provenance = _put_json(
        store,
        {"verifier": "appointed"},
        kind="chronology.epoch_transition_verifier",
    )
    verifier = _AppointedEpochVerifier(provenance)
    service = DecisionValidityService(store, epoch_transition_verifier=verifier)
    query_ref = "sha256:" + "2" * 64
    authority_purpose = "decision_validity_epoch_transition"
    runtime_source = _put_json(
        store,
        {"runtime": "epoch-source"},
        kind="runtime.epoch_dependency_source",
    )
    runtime_target = _put_json(
        store,
        {"runtime": "epoch-target"},
        kind="runtime.epoch_dependency_target",
    )
    graph_edges = (
        EpochDependencyEdge(
            source_ref=runtime_source,
            target_ref=runtime_target,
            relation="invalidates",
            authority_purpose=authority_purpose,
        ),
    )
    graph = EpochDependencyGraph(
        edges=graph_edges,
        denominator_ref=_semantic_hash(
            "polisyos.epoch.dependency-graph.v1",
            {"edges": graph_edges},
        ),
    )
    runtime_denominator_payload = {
        "certificate_bindings": (),
        "dependency_graph": graph,
        "target_refs": (runtime_target,),
    }
    runtime_denominator = EpochDependencyDenominatorReceipt(
        denominator_ref=_semantic_hash(
            "polisyos.epoch.dependency-denominator.v1",
            runtime_denominator_payload,
        ),
        **runtime_denominator_payload,
        predicate_class="independently_reconciled",
    )
    target_vector = resolve_owner_target_dispositions(
        advisory_events=(),
        owner_dispositions=(),
        dependency_graph=graph,
    )
    transition_payload = {
        "previous_epoch_ref": "sha256:" + "1" * 64,
        "current_epoch_ref": "sha256:" + "3" * 64,
        "certificate_bindings": (),
        "dependency_graph": graph,
        "target_vector": target_vector,
        "dependency_denominator_ref": runtime_denominator.denominator_ref,
        "adjudication_denominator_ref": "sha256:" + "4" * 64,
        "requested_query_context_ref": query_ref,
        "authority_purpose": authority_purpose,
    }
    transition = EpochValidityTransitionArtifact(
        **transition_payload,
        transition_content_hash=_semantic_hash(
            "polisyos.epoch.validity-transition.v1",
            transition_payload,
        ),
    )
    transition_ref = store.put_bytes(
        _canonical_bytes(transition),
        ArtifactWriteOptions(
            kind="polisyos.epoch.validity_transition",
            media_type="application/vnd.polisyos.chronology+json",
        ),
    )
    transition_bytes = store.get_bytes(transition_ref.artifact_id)
    assert store.verify(transition_ref.artifact_id).ok
    assert EpochValidityTransitionArtifact.model_validate_json(transition_bytes) == transition

    distinct_scientist_owner = _put_json(
        store,
        {"scientist": "different-semantic-epoch-owner"},
        kind="scientist.semantic_epoch_owner",
    )
    assert str(distinct_scientist_owner.artifact_id) != str(runtime_target.artifact_id)
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="epoch_lineage_distinct_member_set",
        policy_fingerprint="epoch_policy_distinct_member_set",
        knowledge_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.SEMANTIC_EPOCH,
                    key="epoch::distinct-member-set",
                    artifact_id=str(distinct_scientist_owner.artifact_id),
                )
            ]
        ),
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
    )
    packet = _put_json(
        store,
        {
            "schema_version": "3.4",
            "decision_validity_envelope": envelope.model_dump(mode="json"),
            "decision_validity_baseline": baseline.model_dump(mode="json"),
        },
        kind="scientist.decision_packet",
    )
    packet_ref = str(packet.artifact_id)
    service.register_decision_packet(
        packet_ref=packet_ref,
        envelope=envelope,
        baseline=baseline,
    )
    scientist_targets, scientist_digest = service._resolve_epoch_target_denominator(
        dependency_keys=("epoch::distinct-member-set",),
    )
    assert scientist_targets == {
        (
            packet_ref,
            "epoch::distinct-member-set",
            "epoch_lineage_distinct_member_set",
        )
    }
    assert {str(runtime_target.artifact_id)} != {str(distinct_scientist_owner.artifact_id)}
    assert runtime_denominator.denominator_ref != scientist_digest

    from polisyos.runtime.quality.epoch_denominator_reconciliation import (
        EpochDenominatorReconciliationNonReceipt,
        EpochTransitionDenominatorReconciliationProducer,
    )

    snapshot = service.persist_epoch_impact_snapshot(
        dependency_keys=("epoch::distinct-member-set",),
        requested_query_context_ref=query_ref,
    )
    assert snapshot.snapshot.decision_impact_denominator_ref == scientist_digest
    assert {
        (target.packet_ref, target.dependency_key, target.decision_lineage_key)
        for target in snapshot.snapshot.targets
    } == scientist_targets
    verifier.receipt = EpochTransitionVerificationReceipt(
        transition_artifact_ref=transition_ref,
        transition_content_hash="sha256:" + hashlib.sha256(transition_bytes).hexdigest(),
        requested_query_context_ref=query_ref,
        authority_purpose=authority_purpose,
        verifier_provenance_ref=provenance,
        dependency_keys=("epoch::distinct-member-set",),
        dependency_denominator_ref=snapshot.snapshot.decision_impact_denominator_ref,
        adjudication_denominator_ref=transition.adjudication_denominator_ref,
        targets=tuple(
            EpochValidityBatchTarget(
                packet_ref=target.packet_ref,
                decision_lineage_key=target.decision_lineage_key,
                dependency_key=target.dependency_key,
                status=DecisionValidityStatus.STALE,
                reason="epoch_advanced",
            )
            for target in snapshot.snapshot.targets
        ),
        predicate_class="independently_reconciled",
    )
    before = _before_epoch_owner_state(service, (packet_ref,))

    outcome = EpochTransitionDenominatorReconciliationProducer(
        store=store,
        verifier_provenance_ref=provenance,
    ).produce_and_persist(
        transition_artifact_ref=transition_ref,
        scientist_snapshot_handle=snapshot.handle,
        requested_query_context_ref=query_ref,
        authority_purpose=authority_purpose,
    )

    assert isinstance(outcome, EpochDenominatorReconciliationNonReceipt)
    assert outcome.status == "rejected"
    assert outcome.code == "epoch_denominator_membership_mismatch"
    assert outcome.reconciliation_handle is None
    assert _before_epoch_owner_state(service, (packet_ref,)) == before


def test_epoch_batch_omitted_target_fails_closed(tmp_path) -> None:
    _, service, verifier, transition, query_ref, packet_rows = _epoch_batch_fixture(tmp_path)
    assert verifier.receipt is not None
    verifier.receipt = verifier.receipt.model_copy(
        update={"targets": verifier.receipt.targets[:-1]}
    )

    with pytest.raises(ValueError, match="target_denominator_mismatch"):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )

    assert service._state.list_epoch_pending() == ()
    assert all(
        service.read_current_projection(packet_ref).status == DecisionValidityStatus.ACTIVE
        for packet_ref, _ in packet_rows
    )


def test_epoch_batch_reconciles_complete_dependency_denominator(tmp_path) -> None:
    _, service, verifier, transition, query_ref, packet_rows = _epoch_batch_fixture(tmp_path)
    assert verifier.receipt is not None
    verifier.receipt = verifier.receipt.model_copy(
        update={"dependency_denominator_ref": "sha256:" + "9" * 64}
    )

    with pytest.raises(ValueError, match="dependency_denominator_unresolved"):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )

    assert service._state.list_epoch_pending() == ()
    assert all(
        service.read_current_projection(packet_ref).status == DecisionValidityStatus.ACTIVE
        for packet_ref, _ in packet_rows
    )


def test_owner_denominator_is_stable_across_operational_timestamp_updates(tmp_path) -> None:
    _, service, _, _, _, _ = _epoch_batch_fixture(tmp_path, packet_count=1)
    keys = ("epoch::owner-fixture",)
    _, before = service._resolve_epoch_target_denominator(dependency_keys=keys)
    owner = service._state.load_dependency(keys[0])
    assert owner is not None
    service._state.save_dependency(owner.model_copy(update={"updated_at": datetime.now(UTC)}))
    _, after = service._resolve_epoch_target_denominator(dependency_keys=keys)

    assert after == before


def test_owner_registration_cannot_escape_a_frozen_epoch_denominator(tmp_path) -> None:
    store, service, _, transition, query_ref, _ = _epoch_batch_fixture(
        tmp_path,
        packet_count=1,
    )
    registration_service = DecisionValidityService(store)
    enumerated = threading.Event()
    release = threading.Event()
    registration_done = threading.Event()
    errors: list[BaseException] = []
    real_resolve = service._resolve_epoch_target_denominator

    def pause_after_enumeration(**kwargs):
        result = real_resolve(**kwargs)
        enumerated.set()
        assert release.wait(5)
        return result

    service._resolve_epoch_target_denominator = pause_after_enumeration  # type: ignore[method-assign]

    def admit() -> None:
        try:
            service.admit_epoch_validity_batch(
                transition_artifact_ref=transition,
                requested_query_context_ref=query_ref,
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    envelope = DecisionValidityEnvelope(
        decision_lineage_key="epoch_lineage_late_concurrent",
        policy_fingerprint="epoch_policy_late_concurrent",
        knowledge_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.SEMANTIC_EPOCH,
                    key="epoch::owner-fixture",
                    artifact_id="epoch-owner-fixture",
                )
            ]
        ),
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
    )
    packet = _put_json(
        store,
        {
            "schema_version": "3.4",
            "decision_validity_envelope": envelope.model_dump(mode="json"),
            "decision_validity_baseline": baseline.model_dump(mode="json"),
        },
        kind="scientist.decision_packet",
    )

    def register() -> None:
        try:
            registration_service.register_decision_packet(
                packet_ref=str(packet.artifact_id),
                envelope=envelope,
                baseline=baseline,
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            errors.append(exc)
        finally:
            registration_done.set()

    admit_thread = threading.Thread(target=admit)
    admit_thread.start()
    assert enumerated.wait(5)
    register_thread = threading.Thread(target=register)
    register_thread.start()
    assert not registration_done.wait(0.1)
    release.set()
    admit_thread.join(5)
    register_thread.join(5)

    assert errors == []
    assert registration_done.is_set()


def test_one_packet_with_two_epoch_keys_is_applied_once_without_losing_relation(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    provenance = _put_json(
        store,
        {"verifier": "appointed"},
        kind="chronology.epoch_transition_verifier",
    )
    verifier = _AppointedEpochVerifier(provenance)
    service = DecisionValidityService(store, epoch_transition_verifier=verifier)
    keys = ("epoch::owner-a", "epoch::owner-b")
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="epoch_lineage_multi_key",
        policy_fingerprint="epoch_policy_multi_key",
        knowledge_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.SEMANTIC_EPOCH,
                    key=key,
                    artifact_id=f"artifact::{key}",
                )
                for key in keys
            ]
        ),
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
    )
    packet = _put_json(
        store,
        {
            "schema_version": "3.4",
            "decision_validity_envelope": envelope.model_dump(mode="json"),
            "decision_validity_baseline": baseline.model_dump(mode="json"),
        },
        kind="scientist.decision_packet",
    )
    packet_ref = str(packet.artifact_id)
    service.register_decision_packet(packet_ref=packet_ref, envelope=envelope, baseline=baseline)
    transition = _put_json(
        store,
        {"transition": "two-keys"},
        kind="chronology.epoch_transition",
    )
    transition_bytes = store.get_bytes(transition.artifact_id)
    _, denominator_ref = service._resolve_epoch_target_denominator(dependency_keys=keys)
    query_ref = "sha256:" + "2" * 64
    verifier.receipt = EpochTransitionVerificationReceipt(
        transition_artifact_ref=transition,
        transition_content_hash="sha256:" + hashlib.sha256(transition_bytes).hexdigest(),
        requested_query_context_ref=query_ref,
        authority_purpose="decision_validity_epoch_transition",
        verifier_provenance_ref=provenance,
        dependency_keys=keys,
        dependency_denominator_ref=denominator_ref,
        adjudication_denominator_ref="sha256:" + "4" * 64,
        targets=tuple(
            EpochValidityBatchTarget(
                packet_ref=packet_ref,
                decision_lineage_key=envelope.decision_lineage_key,
                dependency_key=key,
                status=DecisionValidityStatus.STALE,
                reason=f"epoch_advanced:{key}",
            )
            for key in keys
        ),
        predicate_class="independently_reconciled",
    )

    receipt = service.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )
    state = service._state.load_packet(packet_ref)

    assert receipt.affected_packet_refs == (packet_ref,)
    assert state is not None
    batch_events = [
        row
        for row in state.lifecycle_events
        if row.payload.get("epoch_batch_id") == receipt.batch_id
    ]
    assert len(batch_events) == 1
    assert tuple(batch_events[0].dependency_keys) == keys
    assert len(batch_events[0].payload["target_dispositions"]) == 2


def test_epoch_batch_persists_complete_pending_freeze_before_first_packet_write(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service, _, transition, query_ref, packet_rows = _epoch_batch_fixture(tmp_path)
    observed = []

    def crash_before_packet_write(**_kwargs):
        observed.append(service._state.list_epoch_pending())
        raise RuntimeError("injected_crash_before_first_packet")

    monkeypatch.setattr(service, "_apply_event_to_packet", crash_before_packet_write)
    with pytest.raises(RuntimeError, match="injected_crash_before_first_packet"):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )

    assert len(observed) == 1
    assert len(observed[0]) == 1
    assert {row.packet_ref for row in observed[0][0].targets} == {
        packet_ref for packet_ref, _ in packet_rows
    }
    assert all(
        service.read_current_projection(packet_ref).status == DecisionValidityStatus.STALE
        for packet_ref, _ in packet_rows
    )


def test_completed_epoch_batch_replay_is_idempotent(tmp_path) -> None:
    store, service, verifier, transition, query_ref, packet_rows = _epoch_batch_fixture(tmp_path)
    receipt = service.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )
    restarted = DecisionValidityService(store, epoch_transition_verifier=verifier)
    repeated = restarted.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )

    assert repeated == receipt
    assert restarted._state.list_epoch_pending() == ()
    assert set(receipt.affected_packet_refs) == {packet_ref for packet_ref, _ in packet_rows}
    evidence = restarted.resolve_completed_epoch_batch_evidence_by_id(batch_id=receipt.batch_id)
    assert evidence.receipt == receipt
    assert evidence.receipt.targets == verifier.receipt.targets
    assert evidence.batch_receipt_ref.kind == ("scientist.decision_validity_epoch_batch_receipt")
    assert evidence.batch_receipt_content_hash == (
        "sha256:" + hashlib.sha256(evidence.receipt_bytes).hexdigest()
    )


def test_strict_epoch_intake_fixture_does_not_establish_transition_producer(tmp_path) -> None:
    """Retain the frozen positive node as an explicit appointment residual.

    The appointed fixture proves the strict owner intake in isolation.  The
    production default separately proves that the absent transition signer and
    producer-identity authority cannot be laundered into that positive result.
    This node therefore does not close the generation-control half of GY-DEF23.
    """

    _, service, verifier, transition, query_ref, packet_rows = _epoch_batch_fixture(
        tmp_path,
        packet_count=2,
    )

    receipt = service.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )

    assert verifier.receipt is not None
    assert receipt.verifier_provenance_ref == verifier.verifier_provenance_ref
    assert receipt.affected_packet_refs == tuple(row[0] for row in packet_rows)
    assert all(
        service.read_current_projection(packet_ref).status == DecisionValidityStatus.STALE
        for packet_ref, _ in packet_rows
    )

    production_store = FileSystemCAS(tmp_path / "production-unappointed")
    production_transition = _put_json(
        production_store,
        {"transition": "unappointed"},
        kind="chronology.epoch_transition",
    )
    production_service = DecisionValidityService(production_store)
    with pytest.raises(ValueError, match="verifier_not_configured"):
        production_service.admit_epoch_validity_batch(
            transition_artifact_ref=production_transition,
            requested_query_context_ref=query_ref,
        )
    assert production_service.state_generation() == 0
    assert production_service._state.list_epoch_pending() == ()


def test_unchanged_epoch_with_new_owner_adjudication_requires_batch(tmp_path) -> None:
    _, service, verifier, transition, query_ref, _ = _epoch_batch_fixture(tmp_path)
    service.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )
    assert verifier.receipt is not None
    verifier.receipt = verifier.receipt.model_copy(
        update={"adjudication_denominator_ref": "sha256:" + "a" * 64}
    )

    with pytest.raises(
        ValueError,
        match="epoch_completed_verification_binding_mismatch",
    ):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )


def test_current_receipt_requires_matching_prior_completed_denominators(tmp_path) -> None:
    _, service, _, transition, query_ref, first_packet_rows = _epoch_batch_fixture(
        tmp_path,
        packet_count=1,
    )
    completed = service.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="epoch_lineage_late",
        policy_fingerprint="epoch_policy_late",
        knowledge_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.SEMANTIC_EPOCH,
                    key="epoch::owner-fixture",
                    artifact_id="epoch-owner-fixture",
                )
            ]
        ),
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
    )
    packet = _put_json(
        service._store,
        {
            "schema_version": "3.4",
            "decision_validity_envelope": envelope.model_dump(mode="json"),
            "decision_validity_baseline": baseline.model_dump(mode="json"),
        },
        kind="scientist.decision_packet",
    )
    service.register_decision_packet(
        packet_ref=str(packet.artifact_id),
        envelope=envelope,
        baseline=baseline,
    )

    repeated = service.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )

    assert repeated == completed
    assert repeated.affected_packet_refs == (first_packet_rows[0][0],)
    assert service.read_current_projection(str(packet.artifact_id)).status == (
        DecisionValidityStatus.ACTIVE
    )


def test_epoch_batch_crash_mid_batch_keeps_all_targets_non_current(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, service, verifier, transition, query_ref, packet_rows = _epoch_batch_fixture(tmp_path)
    original = service._apply_event_to_packet
    calls = 0

    def crash_on_second_packet(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected_mid_batch_crash")
        return original(**kwargs)

    monkeypatch.setattr(service, "_apply_event_to_packet", crash_on_second_packet)
    with pytest.raises(RuntimeError, match="injected_mid_batch_crash"):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )

    pending = service._state.list_epoch_pending()
    assert len(pending) == 1
    assert pending[0].applied_packet_refs == (packet_rows[0][0],)
    assert all(
        service.read_current_projection(packet_ref).status == DecisionValidityStatus.STALE
        for packet_ref, _ in packet_rows
    )

    monkeypatch.undo()
    restarted = DecisionValidityService(store, epoch_transition_verifier=verifier)
    completed = restarted.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )
    assert completed.affected_packet_refs == tuple(row[0] for row in packet_rows)
    assert restarted._state.list_epoch_pending() == ()
    for packet_ref, _ in packet_rows:
        state = restarted._state.load_packet(packet_ref)
        assert state is not None
        assert (
            len(
                [
                    row
                    for row in state.lifecycle_events
                    if row.payload.get("epoch_batch_id") == completed.batch_id
                ]
            )
            == 1
        )


def test_epoch_batch_resume_is_idempotent(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, service, verifier, transition, query_ref, packet_rows = _epoch_batch_fixture(
        tmp_path,
        packet_count=1,
    )
    original_save_pending = service._state.save_epoch_pending
    save_calls = 0

    def crash_after_packet_write(batch):
        nonlocal save_calls
        save_calls += 1
        if save_calls == 2:
            raise RuntimeError("injected_crash_after_packet_write")
        original_save_pending(batch)

    monkeypatch.setattr(service._state, "save_epoch_pending", crash_after_packet_write)
    with pytest.raises(RuntimeError, match="injected_crash_after_packet_write"):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )

    packet_ref = packet_rows[0][0]
    crashed_state = service._state.load_packet(packet_ref)
    assert crashed_state is not None
    assert len(crashed_state.lifecycle_events) == 1
    assert len(crashed_state.lifecycle_jobs) == 1

    monkeypatch.undo()
    restarted = DecisionValidityService(store, epoch_transition_verifier=verifier)
    completed = restarted.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )
    final_state = restarted._state.load_packet(packet_ref)

    assert final_state is not None
    assert completed.affected_packet_refs == (packet_ref,)
    assert len(final_state.lifecycle_events) == 1
    assert len(final_state.lifecycle_jobs) == 1
    assert (
        final_state.lifecycle_jobs[0].trigger_event_id == final_state.lifecycle_events[0].event_id
    )


def test_completed_batch_does_not_mask_corrupt_packet_owner_state(tmp_path) -> None:
    store, service, verifier, transition, query_ref, packet_rows = _epoch_batch_fixture(
        tmp_path,
        packet_count=1,
    )
    service.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )
    packet_ref = packet_rows[0][0]
    service._state._packet_path(packet_ref).write_text("{}", encoding="utf-8")
    restarted = DecisionValidityService(store, epoch_transition_verifier=verifier)

    with pytest.raises(RuntimeError, match="decision_validity_owner_state_corrupt"):
        restarted.read_current_projection(packet_ref)


def test_epoch_batch_pending_preserves_withdrawn_or_revoked_terminal(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, service, _, transition, query_ref, packet_rows = _epoch_batch_fixture(tmp_path)
    for (packet_ref, _), status in zip(
        packet_rows,
        (DecisionValidityStatus.WITHDRAWN, DecisionValidityStatus.REVOKED),
        strict=True,
    ):
        service.mark_packet_trigger(
            packet_ref=packet_ref,
            trigger=DecisionTriggerRecord(
                trigger_type=DecisionTriggerType.REVOKED,
                status=status,
                reason=f"owner_terminal:{status.value}",
            ),
        )

    def crash_before_packet_write(**_kwargs):
        raise RuntimeError("injected_pending_terminal_crash")

    monkeypatch.setattr(service, "_apply_event_to_packet", crash_before_packet_write)
    with pytest.raises(RuntimeError, match="injected_pending_terminal_crash"):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )

    assert tuple(
        service.read_current_projection(packet_ref).status for packet_ref, _ in packet_rows
    ) == (DecisionValidityStatus.WITHDRAWN, DecisionValidityStatus.REVOKED)


def test_generic_event_endpoint_cannot_admit_or_clear_epoch_batch(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, service, _, transition, query_ref, packet_rows = _epoch_batch_fixture(
        tmp_path,
        packet_count=1,
    )

    def crash_before_packet_write(**_kwargs):
        raise RuntimeError("injected_generic_route_pending_batch")

    monkeypatch.setattr(service, "_apply_event_to_packet", crash_before_packet_write)
    with pytest.raises(RuntimeError, match="injected_generic_route_pending_batch"):
        service.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )
    frozen = service._state.list_epoch_pending()
    monkeypatch.undo()

    with pytest.raises(ValueError, match="semantic_epoch_dependency_requires_owner_batch"):
        service.record_dependency_event(
            event=DecisionDependencyEvent(
                event_id="generic_epoch_bypass",
                dedupe_key="generic_epoch_bypass",
                trigger_type=DecisionTriggerType.HISTORICAL_SEMANTIC_REVISION,
                status=DecisionValidityStatus.ACTIVE,
                reason="caller_claimed_current",
                dependency_keys=["epoch::owner-fixture"],
            )
        )
    assert service._state.list_epoch_pending() == frozen
    assert service.read_current_projection(packet_rows[0][0]).status == DecisionValidityStatus.STALE


def test_decision_validity_service_records_events_dedupes_and_tracks_monitoring(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    service = DecisionValidityService(store)
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="lineage_fixture_001",
        policy_fingerprint="policy_fixture_v1",
        normative_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.NORM_PACK,
                    key="norm::fixture_primary",
                    label="Fixture norm pack",
                )
            ]
        ),
        data_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.DATASET,
                    key="dataset::fixture_primary",
                    label="Fixture dataset",
                )
            ]
        ),
        watched_triggers=[
            DecisionTriggerSpec(
                trigger_type=DecisionTriggerType.LAW_CHANGE,
                dependency_keys=["norm::fixture_primary"],
            )
        ],
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
    )
    monitoring_contract = DecisionMonitoringContract.model_validate(
        {
            "run_id": "R_validity_fixture",
            "decision_lineage_key": envelope.decision_lineage_key,
            "anchor_at": "2026-03-12T12:00:00Z",
            "metrics": [
                {
                    "metric_id": "policy_cost",
                    "source_metric_id": "policy_cost",
                    "baseline_value": 100.0,
                    "confirm_range": {"lower": 90.0, "upper": 110.0},
                    "refute_range": {"lower": 80.0, "upper": 120.0},
                    "window": {"start_offset_days": 0, "end_offset_days": 30, "grace_days": 7},
                }
            ],
        }
    )
    monitoring_contract_ref = _put_json(
        store,
        monitoring_contract.model_dump(mode="json"),
        kind="scientist.decision_monitoring_contract",
    )
    packet_ref = _put_json(
        store,
        {
            "schema_version": "3.4",
            "decision_validity_envelope": envelope.model_dump(mode="json"),
            "decision_validity_baseline": baseline.model_dump(mode="json"),
        },
        kind="scientist.decision_packet",
    )

    service.register_decision_packet(
        packet_ref=str(packet_ref.artifact_id),
        envelope=envelope,
        baseline=baseline,
        monitoring_contract_ref=str(monitoring_contract_ref.artifact_id),
    )

    initial_summary = service.get_summary(str(packet_ref.artifact_id))
    assert initial_summary["status"] == "active"
    assert len(initial_summary["lifecycle"]["scheduled_jobs"]) == 1
    assert initial_summary["lifecycle"]["scheduled_jobs"][0]["job_kind"] == "scheduled_monitoring"
    assert initial_summary["lifecycle"]["scheduled_jobs"][0]["state"] == "pending"

    event = DecisionDependencyEvent(
        event_id="decision_evt_fixture_001",
        dedupe_key="decision_evt_fixture_law_change",
        occurred_at=datetime(2026, 3, 12, 13, 0, tzinfo=UTC),
        trigger_type=DecisionTriggerType.LAW_CHANGE,
        status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
        reason="fixture_law_changed",
        dependency_keys=["norm::fixture_primary"],
        source_ref="law://fixture/2026-03-12",
    )

    first = service.record_dependency_event(event=event)
    second = service.record_dependency_event(event=event)

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW

    summary = service.get_summary(str(packet_ref.artifact_id), force=True)
    assert summary["status"] == "requires_human_review"
    assert len(summary["lifecycle"]["events"]) == 1
    assert len(summary["lifecycle"]["transitions"]) == 1
    assert summary["lifecycle"]["pending_reviews"][0]["trigger_type"] == "law_change"
    assert summary["recommended_action"] == "human_review"

    monitoring_report_ref = _put_json(
        store,
        {"schema_version": "1.0", "overall_verdict": "refuted"},
        kind="scientist.decision_monitoring_report",
    )
    reissue_plan_ref = _put_json(
        store,
        {"schema_version": "1.0", "candidate_action": "refresh_decision"},
        kind="scientist.decision_reissue_plan",
    )
    service.update_feedback_refs(
        str(packet_ref.artifact_id),
        monitoring_contract_ref=str(monitoring_contract_ref.artifact_id),
        monitoring_report_ref=str(monitoring_report_ref.artifact_id),
        reissue_plan_ref=str(reissue_plan_ref.artifact_id),
    )

    refreshed_summary = service.get_summary(str(packet_ref.artifact_id))
    assert refreshed_summary["lifecycle"]["scheduled_jobs"][0]["state"] == "completed"
    assert refreshed_summary["lifecycle"]["scheduled_jobs"][0]["payload"][
        "monitoring_report_ref"
    ] == str(monitoring_report_ref.artifact_id)
    assert refreshed_summary["lifecycle"]["reissue_candidates"] == [
        {"artifact_id": str(reissue_plan_ref.artifact_id)}
    ]


def test_decision_validity_service_applies_sticky_triggers_to_legacy_packets(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    service = DecisionValidityService(store)
    packet_ref = _put_json(
        store,
        {
            "schema_version": "3.4",
            "run_id": "R_legacy_fixture",
            "artifacts": {},
        },
        kind="scientist.decision_packet",
    )

    evaluation = service.mark_packet_trigger(
        packet_ref=str(packet_ref.artifact_id),
        trigger=DecisionTriggerRecord(
            trigger_type=DecisionTriggerType.CONTEXT_PROFILE_DRIFT,
            status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
            reason="target_applicability_changed",
        ),
    )

    assert evaluation.status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW
    summary = service.get_summary(str(packet_ref.artifact_id), force=True)
    assert summary["status"] == "requires_human_review"
    assert summary["review_required"] is True
    assert summary["lifecycle"]["pending_reviews"][0]["trigger_type"] == "context_profile_drift"


def test_decision_validity_service_accepts_protocol_store_proxy(tmp_path) -> None:
    base_store = FileSystemCAS(tmp_path)
    store = _StoreWithRootProxy(base_store)
    service = DecisionValidityService(store)
    packet_ref = _put_json(
        base_store,
        {"schema_version": "3.4", "run_id": "R_proxy_fixture", "artifacts": {}},
        kind="scientist.decision_packet",
    )

    evaluation = service.mark_packet_trigger(
        packet_ref=str(packet_ref.artifact_id),
        trigger=DecisionTriggerRecord(
            trigger_type=DecisionTriggerType.CONTEXT_PROFILE_DRIFT,
            status=DecisionValidityStatus.REQUIRES_HUMAN_REVIEW,
            reason="proxy_store_support",
        ),
    )

    assert evaluation.status == DecisionValidityStatus.REQUIRES_HUMAN_REVIEW


def test_decision_validity_state_store_load_model_assertion_is_not_swallowed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "lineage.json"
    path.write_text("{}", encoding="utf-8")

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("lineage-model-broken")

    monkeypatch.setattr(_DecisionLineageState, "model_validate", _boom)

    with pytest.raises(AssertionError, match="lineage-model-broken"):
        _DecisionValidityStateStore._load_model(path, _DecisionLineageState)


def test_load_envelope_assertion_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("envelope-broken")

    monkeypatch.setattr(DecisionValidityEnvelope, "model_validate", _boom)

    with pytest.raises(AssertionError, match="envelope-broken"):
        _load_envelope({"decision_validity_envelope": {}})


def test_load_baseline_assertion_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("baseline-broken")

    monkeypatch.setattr(DecisionValidityEvaluation, "model_validate", _boom)

    with pytest.raises(AssertionError, match="baseline-broken"):
        _load_baseline({"decision_validity_baseline": {}})
