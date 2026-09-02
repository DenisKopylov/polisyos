from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, CanonInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
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
from polisyos.runtime.quality import semantic_epoch as semantic_epoch_runtime
from polisyos.runtime.quality.epoch_validity_cascade import (
    EpochDependencyDenominatorReceipt,
    EpochDependencyEdge,
    EpochDependencyGraph,
    EpochValidityTransitionArtifact,
    _canonical_bytes,
    _semantic_hash,
    build_epoch_validity_transition,
    resolve_owner_target_dispositions,
)
from polisyos.scientist.validation.decision_validity import (
    DecisionValidityService,
    _DecisionLineageState,
    _DecisionValidityStateStore,
    _load_baseline,
    _load_envelope,
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


def _register_reconciliation_packet(
    service: DecisionValidityService,
    store: FileSystemCAS,
    *,
    dependency_key: str,
    dependency_artifact_id: str,
    lineage_key: str,
    policy_fingerprint: str | None = None,
) -> str:
    """Register one real semantic-epoch packet for reconciliation coverage."""

    envelope = DecisionValidityEnvelope(
        decision_lineage_key=lineage_key,
        policy_fingerprint=policy_fingerprint or f"policy_{lineage_key}",
        knowledge_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.SEMANTIC_EPOCH,
                    key=dependency_key,
                    artifact_id=dependency_artifact_id,
                )
            ]
        ),
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=lineage_key,
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
    return packet_ref


def _semantic_epoch_manifest(
    *,
    scope: semantic_epoch_runtime.EpochScopeIdentity,
    label: str,
    requested_query_context_ref: str,
    predecessor_refs: tuple[str, ...],
) -> semantic_epoch_runtime.SemanticEpochManifest:
    """Build one valid, self-bound manifest for a Runtime transition fixture."""

    def digest(value: str) -> str:
        return "sha256:" + hashlib.sha256(value.encode()).hexdigest()

    values: dict[str, object] = {
        "schema_version": "polisyos.epoch.semantic-manifest.v1",
        "scope_identity": scope.model_dump(mode="json"),
        "authority_purpose": "decision_validity_epoch_transition",
        "valid_effect_coordinate_ref": digest("valid-effect"),
        "visibility_knowledge_cutoff_ref": digest("knowledge-cutoff"),
        "purpose_admission_cutoff_ref": digest("purpose-cutoff"),
        "requested_query_context_ref": requested_query_context_ref,
        "boundary_registry_content_hash": digest("boundary-registry"),
        "facet_registry_content_hash": digest("facet-registry"),
        "boundary_denominator_hash": digest(f"boundary:{label}"),
        "facet_denominator_hash": digest("facet-denominator"),
        "boundary_semantic_hashes": [digest(f"boundary-semantic:{label}")],
        "facet_semantic_hashes": [digest("facet-semantic")],
        "predecessor_refs": list(predecessor_refs),
    }
    manifest_content_hash = semantic_epoch_runtime._model_hash(
        semantic_epoch_runtime._MANIFEST_PREFIX,
        values,
    )
    return semantic_epoch_runtime.SemanticEpochManifest(
        **values,
        manifest_content_hash=manifest_content_hash,
        epoch_ref=semantic_epoch_runtime._sha256(
            semantic_epoch_runtime._EPOCH_PREFIX,
            manifest_content_hash.encode(),
        ),
    )


def _valid_epoch_impact_snapshot_contract():
    from polisyos.core.contracts.decision_validity import (
        DecisionValidityEpochImpactOwnerRow,
        DecisionValidityEpochImpactSnapshot,
        DecisionValidityEpochImpactTarget,
    )

    owner_rows = (
        DecisionValidityEpochImpactOwnerRow(
            dependency_key="epoch::a",
            dependency_kind=DecisionDependencyKind.SEMANTIC_EPOCH,
            artifact_id="sha256:" + "a" * 64,
            packet_refs=("packet-a",),
            lineage_keys=("lineage-a",),
        ),
        DecisionValidityEpochImpactOwnerRow(
            dependency_key="epoch::b",
            dependency_kind=DecisionDependencyKind.SEMANTIC_EPOCH,
            artifact_id="sha256:" + "b" * 64,
            packet_refs=("packet-b",),
            lineage_keys=("lineage-b",),
        ),
    )
    targets = (
        DecisionValidityEpochImpactTarget(
            packet_ref="packet-a",
            dependency_key="epoch::a",
            decision_lineage_key="lineage-a",
        ),
        DecisionValidityEpochImpactTarget(
            packet_ref="packet-b",
            dependency_key="epoch::b",
            decision_lineage_key="lineage-b",
        ),
    )
    return DecisionValidityEpochImpactSnapshot.build(
        requested_query_context_ref="sha256:" + "c" * 64,
        requested_dependency_keys=("epoch::a", "epoch::b"),
        owner_rows=owner_rows,
        targets=targets,
    )


@pytest.mark.parametrize(
    "case",
    [
        "requested-key-order",
        "requested-key-duplicate",
        "owner-row-order",
        "owner-row-duplicate",
        "packet-order",
        "packet-duplicate",
        "lineage-order",
        "lineage-duplicate",
        "target-order",
        "target-duplicate",
        "wrong-kind",
        "self-hash",
    ],
)
def test_epoch_impact_snapshot_contract_rejects_noncanonical_members(case: str) -> None:
    """Canonical snapshot membership cannot be reordered, duplicated, or substituted."""

    from pydantic import ValidationError

    from polisyos.core.contracts.decision_validity import DecisionValidityEpochImpactSnapshot

    valid = _valid_epoch_impact_snapshot_contract()
    payload = valid.model_dump(mode="json")
    if case == "requested-key-order":
        payload["requested_dependency_keys"] = list(reversed(payload["requested_dependency_keys"]))
    elif case == "requested-key-duplicate":
        payload["requested_dependency_keys"] = ["epoch::a", "epoch::a"]
    elif case == "owner-row-order":
        payload["owner_rows"] = list(reversed(payload["owner_rows"]))
    elif case == "owner-row-duplicate":
        payload["owner_rows"] = [payload["owner_rows"][0], payload["owner_rows"][0]]
    elif case == "packet-order":
        payload["owner_rows"][0]["packet_refs"] = ["packet-z", "packet-a"]
    elif case == "packet-duplicate":
        payload["owner_rows"][0]["packet_refs"] = ["packet-a", "packet-a"]
    elif case == "lineage-order":
        payload["owner_rows"][0]["lineage_keys"] = ["lineage-z", "lineage-a"]
    elif case == "lineage-duplicate":
        payload["owner_rows"][0]["lineage_keys"] = ["lineage-a", "lineage-a"]
    elif case == "target-order":
        payload["targets"] = list(reversed(payload["targets"]))
    elif case == "target-duplicate":
        payload["targets"] = [payload["targets"][0], payload["targets"][0]]
    elif case == "wrong-kind":
        payload["owner_rows"][0]["dependency_kind"] = DecisionDependencyKind.DATASET.value
    else:
        payload["snapshot_content_hash"] = "sha256:" + "f" * 64

    with pytest.raises(ValidationError):
        DecisionValidityEpochImpactSnapshot.model_validate(payload)


def test_epoch_impact_snapshot_persists_exact_manifest_and_readback(tmp_path) -> None:
    """Snapshot authority is exact CAS bytes plus its fixed manifest profile."""

    store = FileSystemCAS(tmp_path / "cas")
    service = DecisionValidityService(store)
    epoch_owner = _put_json(store, {"epoch": "owner"}, kind="runtime.epoch_target")
    packet_ref = _register_reconciliation_packet(
        service,
        store,
        dependency_key="epoch::snapshot",
        dependency_artifact_id=str(epoch_owner.artifact_id),
        lineage_key="lineage-snapshot",
    )

    persisted = service.persist_epoch_impact_snapshot(
        dependency_keys=("epoch::snapshot",),
        requested_query_context_ref="sha256:" + "c" * 64,
    )
    exact = service.resolve_epoch_impact_snapshot(handle=persisted.handle)
    manifest = store.get_manifest(persisted.handle.snapshot_ref.artifact_id)

    assert exact == persisted
    assert exact.snapshot_bytes == store.get_bytes(persisted.handle.snapshot_ref.artifact_id)
    assert exact.snapshot_bytes == to_canonical_bytes(
        exact.snapshot.model_dump(mode="json"), CanonSpec()
    )
    assert exact.handle.snapshot_content_hash == exact.snapshot.snapshot_content_hash
    assert exact.snapshot.targets[0].packet_ref == packet_ref
    assert exact.handle.snapshot_ref.kind == "scientist.decision_validity_epoch_impact_snapshot"
    assert exact.handle.snapshot_ref.media_type == "application/json"
    assert manifest.kind == exact.handle.snapshot_ref.kind
    assert manifest.media_type == exact.handle.snapshot_ref.media_type
    assert manifest.artifact_schema == SchemaInfo(
        name="polisyos.decision-validity.epoch-impact-snapshot.v1",
        version="1.0",
    )
    assert manifest.canon == CanonInfo.from_spec(CanonSpec())
    assert str(exact.handle.snapshot_ref.artifact_id) == (
        "sha256:" + hashlib.sha256(exact.snapshot_bytes).hexdigest()
    )

    for bad_ref in (
        exact.handle.snapshot_ref.model_copy(update={"kind": "wrong.kind"}),
        exact.handle.snapshot_ref.model_copy(update={"media_type": "application/octet-stream"}),
    ):
        with pytest.raises(
            RuntimeError,
            match="decision_validity_epoch_impact_snapshot_unresolved",
        ):
            service.resolve_epoch_impact_snapshot(
                handle=exact.handle.model_copy(update={"snapshot_ref": bad_ref})
            )


def test_epoch_impact_snapshot_preserves_two_packets_in_one_lineage(tmp_path) -> None:
    """The owner keeps both packet targets while deduplicating their shared lineage."""

    store = FileSystemCAS(tmp_path / "cas")
    service = DecisionValidityService(store)
    epoch_owner = _put_json(store, {"epoch": "owner"}, kind="runtime.epoch_target")
    packet_refs = tuple(
        sorted(
            _register_reconciliation_packet(
                service,
                store,
                dependency_key="epoch::shared-lineage",
                dependency_artifact_id=str(epoch_owner.artifact_id),
                lineage_key="lineage-shared",
                policy_fingerprint=f"policy-shared-{version}",
            )
            for version in ("v1", "v2")
        )
    )
    assert len(set(packet_refs)) == 2

    persisted = service.persist_epoch_impact_snapshot(
        dependency_keys=("epoch::shared-lineage",),
        requested_query_context_ref="sha256:" + "c" * 64,
    )

    assert persisted.snapshot.owner_rows[0].packet_refs == packet_refs
    assert persisted.snapshot.owner_rows[0].lineage_keys == ("lineage-shared",)
    assert tuple(
        (target.packet_ref, target.decision_lineage_key)
        for target in persisted.snapshot.targets
    ) == tuple((packet_ref, "lineage-shared") for packet_ref in packet_refs)


@pytest.mark.parametrize("profile_failure", ["schema", "canon", "noncanonical-bytes"])
def test_epoch_impact_snapshot_exact_reader_rejects_profile_or_byte_drift(
    tmp_path,
    profile_failure: str,
) -> None:
    """A shaped snapshot DTO cannot substitute for exact manifest and byte verification."""

    from polisyos.core.contracts.decision_validity import DecisionValidityEpochImpactSnapshotHandle

    snapshot = _valid_epoch_impact_snapshot_contract()
    canonical = to_canonical_bytes(snapshot.model_dump(mode="json"), CanonSpec())
    raw = canonical if profile_failure != "noncanonical-bytes" else b" " + canonical
    schema = SchemaInfo(
        name=(
            "wrong.snapshot.schema"
            if profile_failure == "schema"
            else "polisyos.decision-validity.epoch-impact-snapshot.v1"
        ),
        version="1.0",
    )
    canon = CanonInfo.from_spec(
        CanonSpec(forbid_floats=False) if profile_failure == "canon" else CanonSpec()
    )
    store = FileSystemCAS(tmp_path / profile_failure)
    ref = store.put_bytes(
        raw,
        ArtifactWriteOptions(
            kind="scientist.decision_validity_epoch_impact_snapshot",
            media_type="application/json",
            schema=schema,
            canon=canon,
        ),
    )
    service = DecisionValidityService(store)

    with pytest.raises(
        RuntimeError,
        match="decision_validity_epoch_impact_snapshot_unresolved",
    ):
        service.resolve_epoch_impact_snapshot(
            handle=DecisionValidityEpochImpactSnapshotHandle(
                snapshot_ref=ref,
                snapshot_content_hash=snapshot.snapshot_content_hash,
            )
        )


def test_strict_snapshot_refuses_nullable_owner_but_legacy_digest_is_unchanged(tmp_path) -> None:
    """Strict persistence must not strengthen the nullable legacy owner resolver."""

    store = FileSystemCAS(tmp_path / "cas")
    service = DecisionValidityService(store)
    packet_ref = _register_reconciliation_packet(
        service,
        store,
        dependency_key="epoch::nullable",
        dependency_artifact_id="sha256:" + "a" * 64,
        lineage_key="lineage-nullable",
    )
    owner = service._state.load_dependency("epoch::nullable")
    assert owner is not None
    service._state.save_dependency(owner.model_copy(update={"artifact_id": None}))
    expected_rows = [
        {
            "dependency_key": "epoch::nullable",
            "dependency_kind": "semantic_epoch",
            "artifact_id": None,
            "packet_refs": [packet_ref],
            "lineage_keys": ["lineage-nullable"],
        }
    ]
    expected_digest = "sha256:" + hashlib.sha256(
        json.dumps(expected_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    targets, digest = service._resolve_epoch_target_denominator(
        dependency_keys=("epoch::nullable",)
    )
    assert targets == {(packet_ref, "epoch::nullable", "lineage-nullable")}
    assert digest == expected_digest
    before_ids = tuple(store.iter_artifact_ids())

    with pytest.raises(ValueError, match="epoch_impact_snapshot_artifact_id_unresolved"):
        service.persist_epoch_impact_snapshot(
            dependency_keys=("epoch::nullable",),
            requested_query_context_ref="sha256:" + "c" * 64,
        )

    assert tuple(store.iter_artifact_ids()) == before_ids


def _valid_epoch_reconciliation_binding(*, batch_id: str = "batch-a", **updates):
    from polisyos.core.contracts.decision_validity import (
        EpochDenominatorReconciliationAdmissionBinding,
    )

    values = {
        "batch_id": batch_id,
        "transition_artifact_ref": ArtifactRef(
            artifact_id="sha256:" + "1" * 64,
            kind="polisyos.epoch.validity_transition",
            media_type="application/vnd.polisyos.chronology+json",
        ),
        "transition_content_hash": "sha256:" + "2" * 64,
        "requested_query_context_ref": "sha256:" + "3" * 64,
        "decision_impact_denominator_ref": "sha256:" + "4" * 64,
        "scientist_snapshot_ref": ArtifactRef(
            artifact_id="sha256:" + "5" * 64,
            kind="scientist.decision_validity_epoch_impact_snapshot",
            media_type="application/json",
        ),
        "scientist_snapshot_content_hash": "sha256:" + "6" * 64,
        "verifier_provenance_ref": ArtifactRef(
            artifact_id="sha256:" + "7" * 64,
            kind="chronology.epoch_transition_verifier",
            media_type="application/json",
        ),
        "reconciliation_receipt_ref": ArtifactRef(
            artifact_id="sha256:" + "8" * 64,
            kind="polisyos.epoch.transition_denominator_reconciliation_receipt",
            media_type="application/vnd.polisyos.chronology+json",
        ),
        "reconciliation_receipt_content_hash": "sha256:" + "9" * 64,
    }
    values.update(updates)
    return EpochDenominatorReconciliationAdmissionBinding.build(**values)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        (
            "transition_artifact_ref",
            ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="polisyos.epoch.validity_transition",
                media_type="application/vnd.polisyos.chronology+json",
            ),
        ),
        ("transition_content_hash", "sha256:" + "a" * 64),
        ("requested_query_context_ref", "sha256:" + "a" * 64),
        ("decision_impact_denominator_ref", "sha256:" + "a" * 64),
        (
            "scientist_snapshot_ref",
            ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="scientist.decision_validity_epoch_impact_snapshot",
                media_type="application/json",
            ),
        ),
        ("scientist_snapshot_content_hash", "sha256:" + "a" * 64),
        (
            "verifier_provenance_ref",
            ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="chronology.epoch_transition_verifier",
                media_type="application/json",
            ),
        ),
        (
            "reconciliation_receipt_ref",
            ArtifactRef(
                artifact_id="sha256:" + "a" * 64,
                kind="polisyos.epoch.transition_denominator_reconciliation_receipt",
                media_type="application/vnd.polisyos.chronology+json",
            ),
        ),
        ("reconciliation_receipt_content_hash", "sha256:" + "a" * 64),
    ],
)
def test_epoch_reconciliation_admission_binding_is_idempotent_and_conflicts(
    tmp_path,
    field: str,
    replacement: object,
) -> None:
    """The first valid binding wins; identical retries alone are idempotent."""

    state = _DecisionValidityStateStore(FileSystemCAS(tmp_path / field))
    binding = _valid_epoch_reconciliation_binding()
    with state.owner_transaction(), state.epoch_batch_transaction():
        assert state.save_epoch_reconciliation_admission_binding(binding) == binding
        assert state.save_epoch_reconciliation_admission_binding(binding) == binding
        with pytest.raises(
            ValueError,
            match="epoch_denominator_reconciliation_admission_conflict",
        ):
            state.save_epoch_reconciliation_admission_binding(
                _valid_epoch_reconciliation_binding(**{field: replacement})
            )
    assert state.load_epoch_reconciliation_admission_binding(binding.batch_id) == binding
    assert state.list_epoch_reconciliation_admission_bindings() == (binding,)
    assert binding.handle.reconciliation_receipt_ref == binding.reconciliation_receipt_ref
    assert "handle" not in binding.model_dump(mode="json")


def test_epoch_reconciliation_admission_binding_supports_path_state_store(tmp_path) -> None:
    """The write-once binding works with the state store's accepted Path constructor."""

    state = _DecisionValidityStateStore(tmp_path)
    binding = _valid_epoch_reconciliation_binding()

    with state.owner_transaction(), state.epoch_batch_transaction():
        assert state.save_epoch_reconciliation_admission_binding(binding) == binding

    assert state.load_epoch_reconciliation_admission_binding(binding.batch_id) == binding


@pytest.mark.parametrize(
    "corruption", ["malformed", "noncanonical", "address", "self-hash"]
)
def test_epoch_reconciliation_admission_binding_rejects_corrupt_winner(
    tmp_path,
    corruption: str,
) -> None:
    """Malformed, noncanonical, or misaddressed winner state is owner corruption."""

    state = _DecisionValidityStateStore(FileSystemCAS(tmp_path / corruption))
    requested = _valid_epoch_reconciliation_binding(batch_id="batch-requested")
    path = state._epoch_reconciliation_admissions / (
        f"{state.make_key(requested.batch_id)}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if corruption == "malformed":
        path.write_bytes(b"{not-json")
    elif corruption == "noncanonical":
        path.write_bytes(
            json.dumps(requested.model_dump(mode="json"), indent=2).encode("utf-8")
        )
    else:
        winner = _valid_epoch_reconciliation_binding(
            batch_id=("batch-requested" if corruption == "self-hash" else "batch-other")
        )
        winner_payload = winner.model_dump(mode="json")
        if corruption == "self-hash":
            winner_payload["binding_content_hash"] = "sha256:" + "f" * 64
        path.write_bytes(to_canonical_bytes(winner_payload, CanonSpec()))

    with pytest.raises(RuntimeError, match="decision_validity_owner_state_corrupt"):
        state.load_epoch_reconciliation_admission_binding(requested.batch_id)


def test_no_reconciliation_reader_preserves_legacy_admission_and_lazy_state(tmp_path) -> None:
    """A reader-unaware service retains legacy admission behavior and filesystem effects."""

    store, service, _, transition, query_ref, packet_rows = _epoch_batch_fixture(
        tmp_path,
        packet_count=1,
    )
    binding_dir = tmp_path / "decision_validity" / "epoch_reconciliation_admissions"
    assert not binding_dir.exists()
    assert all(
        store.get_manifest(artifact_id).kind
        != "scientist.decision_validity_epoch_impact_snapshot"
        for artifact_id in store.iter_artifact_ids()
    )

    receipt = service.admit_epoch_validity_batch(
        transition_artifact_ref=transition,
        requested_query_context_ref=query_ref,
    )
    restarted = DecisionValidityService(store)

    assert receipt.schema_version == "polisyos.decision-validity.epoch-batch-receipt.v1"
    assert receipt.dependency_denominator_ref == service._resolve_epoch_target_denominator(
        dependency_keys=("epoch::owner-fixture",)
    )[1]
    assert service._state.list_epoch_pending() == ()
    assert service._state.list_epoch_reconciliation_admission_bindings() == ()
    assert not binding_dir.exists()
    assert all(
        store.get_manifest(artifact_id).kind
        != "scientist.decision_validity_epoch_impact_snapshot"
        for artifact_id in store.iter_artifact_ids()
    )
    assert (
        service.read_current_projection(packet_rows[0][0]).status
        == DecisionValidityStatus.STALE
    )
    with pytest.raises(ValueError, match="verifier_not_configured"):
        restarted.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )


@pytest.mark.parametrize("runtime_membership", ["empty", "other"])
def test_epoch_reconciliation_receipt_rejects_unmapped_zero_impact_owner(
    runtime_membership: str,
) -> None:
    """Every Scientist owner artifact must join Runtime even without impact targets."""

    from pydantic import ValidationError

    from polisyos.core.contracts.decision_validity import (
        DecisionValidityEpochImpactOwnerRow,
        DecisionValidityEpochImpactSnapshot,
        EpochTransitionDenominatorReconciliationReceipt,
    )

    owner = DecisionValidityEpochImpactOwnerRow(
        dependency_key="epoch::zero-impact",
        dependency_kind=DecisionDependencyKind.SEMANTIC_EPOCH,
        artifact_id="sha256:" + "a" * 64,
        packet_refs=(),
        lineage_keys=(),
    )
    snapshot = DecisionValidityEpochImpactSnapshot.build(
        requested_query_context_ref="sha256:" + "b" * 64,
        requested_dependency_keys=(owner.dependency_key,),
        owner_rows=(owner,),
        targets=(),
    )
    runtime_target_refs = (
        ()
        if runtime_membership == "empty"
        else (
            ArtifactRef(
                artifact_id="sha256:" + "c" * 64,
                kind="runtime.epoch_dependency_target",
                media_type="application/json",
            ),
        )
    )

    with pytest.raises(ValidationError, match="epoch_denominator_membership_mismatch"):
        EpochTransitionDenominatorReconciliationReceipt.build(
            requested_query_context_ref=snapshot.requested_query_context_ref,
            verifier_provenance_ref=ArtifactRef(
                artifact_id="sha256:" + "d" * 64,
                kind="chronology.epoch_transition_verifier",
                media_type="application/json",
            ),
            transition_artifact_ref=ArtifactRef(
                artifact_id="sha256:" + "e" * 64,
                kind="polisyos.epoch.validity_transition",
                media_type="application/vnd.polisyos.chronology+json",
            ),
            transition_content_hash="sha256:" + "f" * 64,
            epoch_dependency_denominator_ref="sha256:" + "1" * 64,
            runtime_target_refs=runtime_target_refs,
            scientist_snapshot_ref=ArtifactRef(
                artifact_id="sha256:" + "2" * 64,
                kind="scientist.decision_validity_epoch_impact_snapshot",
                media_type="application/json",
            ),
            scientist_snapshot_content_hash=snapshot.snapshot_content_hash,
            decision_impact_denominator_ref=snapshot.decision_impact_denominator_ref,
            requested_dependency_keys=snapshot.requested_dependency_keys,
            scientist_owner_rows=snapshot.owner_rows,
            scientist_targets=snapshot.targets,
            mapping_rows=(),
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


def test_epoch_denominator_reconciliation_receipt_bridges_both_owner_definitions(
    tmp_path,
) -> None:
    """One Runtime target can reconcile to two frozen Scientist members."""

    store = FileSystemCAS(tmp_path / "cas")
    provenance = _put_json(
        store,
        {"verifier": "appointed"},
        kind="chronology.epoch_transition_verifier",
    )
    verifier = _AppointedEpochVerifier(provenance)
    service = DecisionValidityService(store, epoch_transition_verifier=verifier)
    epoch_key = "epoch::reconciliation-owner"
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
    epoch_scope = semantic_epoch_runtime.build_epoch_scope_identity(
        schema_profile="polisyos.epoch.decision-validity-test-scope.v1",
        identity_bytes=b"epoch-denominator-reconciliation",
    )
    previous_epoch = _semantic_epoch_manifest(
        scope=epoch_scope,
        label="reconciliation-previous",
        requested_query_context_ref=query_ref,
        predecessor_refs=(),
    )
    current_epoch = _semantic_epoch_manifest(
        scope=epoch_scope,
        label="reconciliation-current",
        requested_query_context_ref=query_ref,
        predecessor_refs=(previous_epoch.epoch_ref,),
    )
    assert previous_epoch.epoch_ref != current_epoch.epoch_ref
    transition = build_epoch_validity_transition(
        previous_epoch=previous_epoch,
        current_epoch=current_epoch,
        certificates=(),
        dependency_graph=graph,
        target_vector=resolve_owner_target_dispositions(
            advisory_events=(),
            owner_dispositions=(),
            dependency_graph=graph,
        ),
        dependency_denominator_ref=runtime_denominator.denominator_ref,
        adjudication_denominator_ref="sha256:" + "4" * 64,
        requested_query_context_ref=query_ref,
        authority_purpose=authority_purpose,
    )
    transition_ref = store.put_bytes(
        _canonical_bytes(transition),
        ArtifactWriteOptions(
            kind="polisyos.epoch.validity_transition",
            media_type="application/vnd.polisyos.chronology+json",
        ),
    )
    transition_bytes = store.get_bytes(transition_ref.artifact_id)
    transition_raw_hash = "sha256:" + hashlib.sha256(transition_bytes).hexdigest()
    assert store.verify(transition_ref.artifact_id).ok
    assert EpochValidityTransitionArtifact.model_validate_json(transition_bytes) == transition

    packet_refs = tuple(
        _register_reconciliation_packet(
            service,
            store,
            dependency_key=epoch_key,
            dependency_artifact_id=str(runtime_target.artifact_id),
            lineage_key=f"epoch_lineage_reconciliation_{ordinal}",
        )
        for ordinal in range(2)
    )
    scientist_targets, scientist_digest = service._resolve_epoch_target_denominator(
        dependency_keys=(epoch_key,)
    )
    assert scientist_targets == {
        (packet_refs[0], epoch_key, "epoch_lineage_reconciliation_0"),
        (packet_refs[1], epoch_key, "epoch_lineage_reconciliation_1"),
    }
    assert len(scientist_targets) == 2
    assert len({target[0] for target in scientist_targets}) == 2
    assert len({target[2] for target in scientist_targets}) == 2
    assert runtime_denominator.denominator_ref != scientist_digest

    from polisyos.runtime.quality.epoch_denominator_reconciliation import (
        EpochTransitionDenominatorReconciliationHandle,
        EpochTransitionDenominatorReconciliationProducer,
        EpochTransitionDenominatorReconciliationReader,
        PersistedEpochTransitionDenominatorReconciliation,
    )

    snapshot = service.persist_epoch_impact_snapshot(
        dependency_keys=(epoch_key,),
        requested_query_context_ref=query_ref,
    )
    assert snapshot.snapshot.decision_impact_denominator_ref == scientist_digest
    assert {
        (target.packet_ref, target.dependency_key, target.decision_lineage_key)
        for target in snapshot.snapshot.targets
    } == scientist_targets

    verifier.receipt = EpochTransitionVerificationReceipt(
        transition_artifact_ref=transition_ref,
        transition_content_hash=transition_raw_hash,
        requested_query_context_ref=query_ref,
        authority_purpose=authority_purpose,
        verifier_provenance_ref=provenance,
        dependency_keys=(epoch_key,),
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
    producer = EpochTransitionDenominatorReconciliationProducer(
        store=store,
        verifier_provenance_ref=provenance,
    )
    produced = producer.produce_and_persist(
        transition_artifact_ref=transition_ref,
        scientist_snapshot_handle=snapshot.handle,
        requested_query_context_ref=query_ref,
        authority_purpose=authority_purpose,
    )
    assert isinstance(produced, PersistedEpochTransitionDenominatorReconciliation)
    first_handle = produced.handle
    reader = EpochTransitionDenominatorReconciliationReader(
        store=store,
        verifier_provenance_ref=provenance,
    )

    # The first sidecar is resolved from CAS, not reconstructed from a DTO.
    first_exact = reader.resolve_exact(handle=first_handle)
    first_receipt = first_exact.receipt
    assert first_exact.receipt_bytes == store.get_bytes(
        first_handle.reconciliation_receipt_ref.artifact_id
    )
    assert first_receipt.transition_artifact_ref == transition_ref
    assert first_receipt.transition_content_hash == transition_raw_hash
    assert first_receipt.scientist_snapshot_ref == snapshot.handle.snapshot_ref
    assert first_receipt.scientist_snapshot_content_hash == snapshot.handle.snapshot_content_hash
    assert first_receipt.epoch_dependency_denominator_ref == runtime_denominator.denominator_ref
    assert first_receipt.decision_impact_denominator_ref == (
        snapshot.snapshot.decision_impact_denominator_ref
    )
    assert (
        first_receipt.epoch_dependency_denominator_ref
        != first_receipt.decision_impact_denominator_ref
    )
    assert tuple(row.runtime_target_ref for row in first_receipt.mapping_rows) == (
        runtime_target,
        runtime_target,
    )
    assert {
        (row.packet_ref, row.dependency_key, row.decision_lineage_key)
        for row in first_receipt.mapping_rows
    } == scientist_targets
    assert {row.dependency_artifact_id for row in first_receipt.mapping_rows} == {
        str(runtime_target.artifact_id)
    }

    service = DecisionValidityService(
        store,
        epoch_transition_verifier=verifier,
        epoch_denominator_reconciliation_reader=reader,
    )
    receipt = service.admit_epoch_validity_batch(
        transition_artifact_ref=transition_ref,
        requested_query_context_ref=query_ref,
    )
    binding_rows = service._state.list_epoch_reconciliation_admission_bindings()
    assert len(binding_rows) == 1
    binding = binding_rows[0]
    assert binding.batch_id == receipt.batch_id
    assert binding.reconciliation_receipt_ref == first_handle.reconciliation_receipt_ref
    assert binding.reconciliation_receipt_content_hash == (
        first_handle.reconciliation_receipt_content_hash
    )
    assert binding.scientist_snapshot_ref == snapshot.handle.snapshot_ref
    assert receipt.dependency_denominator_ref == snapshot.snapshot.decision_impact_denominator_ref
    assert receipt.dependency_denominator_ref != first_receipt.epoch_dependency_denominator_ref
    assert receipt.targets == tuple(
        EpochValidityBatchTarget(
            packet_ref=target.packet_ref,
            decision_lineage_key=target.decision_lineage_key,
            dependency_key=target.dependency_key,
            status=DecisionValidityStatus.STALE,
            reason="epoch_advanced",
        )
        for target in snapshot.snapshot.targets
    )
    assert all(
        service.read_current_projection(packet_ref).status == DecisionValidityStatus.STALE
        for packet_ref in packet_refs
    )
    assert service._state.list_epoch_pending() == ()
    completed = service.enumerate_completed_epoch_batch_evidence()
    assert len(completed) == 1
    assert completed[0].receipt == receipt

    late_packet_ref = _register_reconciliation_packet(
        service,
        store,
        dependency_key=epoch_key,
        dependency_artifact_id=str(runtime_target.artifact_id),
        lineage_key="epoch_lineage_reconciliation_late_live",
    )
    assert service.read_current_projection(late_packet_ref).status == DecisionValidityStatus.ACTIVE
    later_snapshot = service.persist_epoch_impact_snapshot(
        dependency_keys=(epoch_key,),
        requested_query_context_ref=query_ref,
    )
    assert len(later_snapshot.snapshot.targets) == 3
    assert later_snapshot.snapshot.decision_impact_denominator_ref != scientist_digest
    later = producer.produce_and_persist(
        transition_artifact_ref=transition_ref,
        scientist_snapshot_handle=later_snapshot.handle,
        requested_query_context_ref=query_ref,
        authority_purpose=authority_purpose,
    )
    assert isinstance(later, PersistedEpochTransitionDenominatorReconciliation)
    assert later.handle != first_handle
    later_exact = reader.resolve_exact(handle=later.handle)
    assert later_exact.handle == later.handle
    assert later_exact.receipt_bytes == store.get_bytes(
        later.handle.reconciliation_receipt_ref.artifact_id
    )
    assert later_exact.receipt.transition_artifact_ref == transition_ref
    assert later_exact.receipt.transition_content_hash == transition_raw_hash
    assert later_exact.receipt.scientist_snapshot_ref == later_snapshot.handle.snapshot_ref
    assert later_exact.receipt.scientist_snapshot_content_hash == (
        later_snapshot.handle.snapshot_content_hash
    )
    assert later_exact.receipt.verifier_provenance_ref == provenance
    assert {
        (row.packet_ref, row.dependency_key, row.decision_lineage_key)
        for row in later_exact.receipt.mapping_rows
    } == {
        (target.packet_ref, target.dependency_key, target.decision_lineage_key)
        for target in later_snapshot.snapshot.targets
    }
    restarted_reader = EpochTransitionDenominatorReconciliationReader(
        store=store,
        verifier_provenance_ref=provenance,
    )
    restarted = DecisionValidityService(
        store,
        epoch_transition_verifier=verifier,
        epoch_denominator_reconciliation_reader=restarted_reader,
    )
    before_replay = _before_epoch_owner_state(
        restarted,
        (*packet_refs, late_packet_ref),
    )
    repeated = restarted.admit_epoch_validity_batch(
        transition_artifact_ref=transition_ref,
        requested_query_context_ref=query_ref,
    )
    after_replay = _before_epoch_owner_state(
        restarted,
        (*packet_refs, late_packet_ref),
    )

    assert repeated == receipt
    assert after_replay == before_replay
    assert restarted._state.list_epoch_pending() == ()
    assert restarted._state.list_epoch_reconciliation_admission_bindings() == (binding,)
    assert restarted.enumerate_completed_epoch_batch_evidence()[0].receipt == receipt
    assert (
        restarted.read_current_projection(late_packet_ref).status
        == DecisionValidityStatus.ACTIVE
    )
    replay_binding = restarted._state.list_epoch_reconciliation_admission_bindings()[0]
    replay_exact = restarted_reader.resolve_exact(
        handle=EpochTransitionDenominatorReconciliationHandle(
            reconciliation_receipt_ref=replay_binding.reconciliation_receipt_ref,
            reconciliation_receipt_content_hash=replay_binding.reconciliation_receipt_content_hash,
        )
    )
    assert replay_exact.handle == first_handle
    assert replay_exact.receipt_bytes == first_exact.receipt_bytes
    assert replay_exact.receipt == first_exact.receipt
    assert replay_binding.reconciliation_receipt_ref != later.handle.reconciliation_receipt_ref


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
