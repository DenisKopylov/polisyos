"""Behavioral tests for the policy-free epoch validity cascade."""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path

import pytest

from polisyos.core import artifacts, contracts
from polisyos.runtime.quality import epoch_validity_cascade as cascade
from polisyos.runtime.quality import semantic_epoch as semantic_epoch_runtime
from polisyos.runtime.quality.epoch_validity_cascade import (
    AdvisoryPerturbationEvent,
    DerivationRecipeBinding,
    EpochCertificateBinding,
    EpochDependencyDenominatorReceipt,
    EpochDependencyEdge,
    EpochDependencyGraph,
    EpochPerturbationAdjudicationReceipt,
    EpochTransitionSigningNonReceipt,
    EpochValidityTransitionArtifact,
    EpochValidityTransitionProducer,
    NoEpochTransitionSigningAuthority,
    OwnerAdjudicatedTargetDisposition,
    _framed_semantic_hash,
    _semantic_hash,
    advisory_perturbation_from_monitor_event,
    bind_certificate_to_epoch,
    build_epoch_validity_transition,
    persist_advisory_perturbation_event,
    resolve_advisory_perturbation_event,
    resolve_owner_target_dispositions,
)
from polisyos.runtime.quality.semantic_epoch import SemanticEpochManifest
from polisyos.runtime.quality.semantic_epoch_store import (
    FileSemanticEpochHistoryRepository,
)
from polisyos.scientist.governance.continuous.monitors import (
    GovernanceMonitorEvent,
    persist_governance_monitor_event,
)


def _digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def _ref(label: str, *, kind: str = "test.artifact") -> artifacts.ArtifactRef:
    return artifacts.ArtifactRef(
        artifact_id=artifacts.ArtifactID(_digest(label)),
        kind=kind,
        media_type="application/octet-stream",
    )


def _graph(
    *targets: artifacts.ArtifactRef,
    authority_purpose: str = "decision_validity",
) -> EpochDependencyGraph:
    source = _ref("source")
    edges = tuple(
        EpochDependencyEdge(
            source_ref=source,
            target_ref=target,
            relation="invalidates",
            authority_purpose=authority_purpose,
        )
        for target in targets
    )
    return EpochDependencyGraph(
        edges=edges,
        denominator_ref=_semantic_hash("polisyos.epoch.dependency-graph.v1", {"edges": edges}),
    )


def _epoch_scope(label: str = "transition-scope") -> semantic_epoch_runtime.EpochScopeIdentity:
    return semantic_epoch_runtime.build_epoch_scope_identity(
        schema_profile="polisyos.epoch.transition-test-scope.v1",
        identity_bytes=label.encode(),
    )


def _epoch_manifest(
    *,
    scope: semantic_epoch_runtime.EpochScopeIdentity,
    label: str,
    predecessors: tuple[str, ...],
    authority_purpose: str = "decision_validity",
) -> SemanticEpochManifest:
    values: dict[str, object] = {
        "schema_version": "polisyos.epoch.semantic-manifest.v1",
        "scope_identity": scope.model_dump(mode="json"),
        "authority_purpose": authority_purpose,
        "valid_effect_coordinate_ref": _digest("valid-effect"),
        "visibility_knowledge_cutoff_ref": _digest("knowledge-cutoff"),
        "purpose_admission_cutoff_ref": _digest("purpose-cutoff"),
        "requested_query_context_ref": _digest(f"query:{label}"),
        "boundary_registry_content_hash": _digest("boundary-registry"),
        "facet_registry_content_hash": _digest("facet-registry"),
        "boundary_denominator_hash": _digest(f"boundary:{label}"),
        "facet_denominator_hash": _digest("facet-denominator"),
        "boundary_semantic_hashes": [_digest(f"boundary-semantic:{label}")],
        "facet_semantic_hashes": [_digest("facet-semantic")],
        "predecessor_refs": list(predecessors),
    }
    manifest_hash = semantic_epoch_runtime._model_hash(
        semantic_epoch_runtime._MANIFEST_PREFIX,
        values,
    )
    return SemanticEpochManifest(
        **values,
        manifest_content_hash=manifest_hash,
        epoch_ref=semantic_epoch_runtime._sha256(
            semantic_epoch_runtime._EPOCH_PREFIX,
            manifest_hash.encode(),
        ),
    )


def _persist_epoch_manifest(
    store: artifacts.FileSystemCAS,
    manifest: SemanticEpochManifest,
) -> artifacts.ArtifactRef:
    raw = contracts.chronology._frame_record(contracts.epoch.canonical_epoch_bytes(manifest))
    return store.put_bytes(
        raw,
        artifacts.ArtifactWriteOptions(
            kind="epoch.semantic_manifest",
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )


def _epoch_history_entry(
    manifest: SemanticEpochManifest,
    manifest_ref: artifacts.ArtifactRef,
) -> semantic_epoch_runtime.EpochHistoryEntry:
    return semantic_epoch_runtime.EpochHistoryEntry(
        epoch_ref=manifest.epoch_ref,
        manifest_ref=manifest_ref,
        manifest_content_hash=manifest.manifest_content_hash,
        native_member_ref=manifest_ref,
        native_member_content_hash=str(manifest_ref.artifact_id),
        predecessor_refs=manifest.predecessor_refs,
    )


def _epoch_history_hash(
    *,
    scope: semantic_epoch_runtime.EpochScopeIdentity,
    authority_purpose: str,
    entries: tuple[semantic_epoch_runtime.EpochHistoryEntry, ...],
    heads: tuple[str, ...],
) -> str:
    raw = contracts.chronology._frame_record(
        contracts.epoch.canonical_epoch_bytes(
            {
                "schema_version": "polisyos.epoch.scope-history.v1",
                "scope": scope.model_dump(mode="json"),
                "authority_purpose": authority_purpose,
                "entries": [entry.model_dump(mode="json") for entry in entries],
                "head_refs": list(heads),
            }
        )
    )
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _append_epoch_manifest(
    history: FileSemanticEpochHistoryRepository,
    *,
    scope: semantic_epoch_runtime.EpochScopeIdentity,
    manifest: SemanticEpochManifest,
    manifest_ref: artifacts.ArtifactRef,
    expected_heads: tuple[str, ...],
    resulting_entries: tuple[semantic_epoch_runtime.EpochHistoryEntry, ...],
    resulting_heads: tuple[str, ...],
) -> semantic_epoch_runtime.EpochHistoryAppendReceipt:
    return history.append_if_current(
        expected_head_refs=expected_heads,
        manifest_ref=manifest_ref,
        native_member_ref=manifest_ref,
        predecessor_refs=manifest.predecessor_refs,
        expected_resulting_history_snapshot_hash=_epoch_history_hash(
            scope=scope,
            authority_purpose=manifest.authority_purpose,
            entries=resulting_entries,
            heads=resulting_heads,
        ),
    )


def _put_epoch_dummy(
    store: artifacts.FileSystemCAS,
    *,
    kind: str,
) -> artifacts.ArtifactRef:
    return store.put_bytes(
        kind.encode(),
        artifacts.ArtifactWriteOptions(
            kind=kind,
            media_type="application/vnd.polisyos.epoch+json",
        ),
    )


def _persist_epoch_receipt(
    store: artifacts.FileSystemCAS,
    *,
    manifest: SemanticEpochManifest,
    manifest_ref: artifacts.ArtifactRef,
    history_receipt_ref: artifacts.ArtifactRef,
    epoch_ref: str | None = None,
) -> semantic_epoch_runtime.PersistedSemanticEpochProductionReceipt:
    return semantic_epoch_runtime.persist_semantic_epoch_production_receipt(
        store=store,
        receipt=semantic_epoch_runtime.SemanticEpochProductionReceipt(
            production_mode="ordinary",
            status="appended",
            prepared_epoch_ref=None,
            admitted_boundary_evidence_ref=None,
            epoch_ref=manifest.epoch_ref if epoch_ref is None else epoch_ref,
            semantic_manifest_ref=manifest_ref,
            owner_denominator_receipt_refs=(),
            history_append_receipt_ref=history_receipt_ref,
            chronology_bundle_ref=_put_epoch_dummy(
                store,
                kind="chronology.full_prefix.bundle",
            ),
            chronology_verification_ref=_put_epoch_dummy(
                store,
                kind="chronology.verifier.result",
            ),
            requested_query_context_ref=manifest.requested_query_context_ref,
            failure_codes=(),
        ),
    )


@dataclass(frozen=True)
class _TransitionHistoryFixture:
    store: artifacts.FileSystemCAS
    history: FileSemanticEpochHistoryRepository
    scope: semantic_epoch_runtime.EpochScopeIdentity
    previous: SemanticEpochManifest
    previous_ref: artifacts.ArtifactRef
    previous_receipt: semantic_epoch_runtime.PersistedSemanticEpochProductionReceipt
    current: SemanticEpochManifest
    current_ref: artifacts.ArtifactRef
    current_receipt: semantic_epoch_runtime.PersistedSemanticEpochProductionReceipt


def _transition_history_fixture(tmp_path: Path) -> _TransitionHistoryFixture:
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    history = FileSemanticEpochHistoryRepository(
        root=tmp_path / "history",
        artifacts=store,
    )
    scope = _epoch_scope()
    previous = _epoch_manifest(scope=scope, label="previous", predecessors=())
    previous_ref = _persist_epoch_manifest(store, previous)
    previous_entry = _epoch_history_entry(previous, previous_ref)
    previous_append = _append_epoch_manifest(
        history,
        scope=scope,
        manifest=previous,
        manifest_ref=previous_ref,
        expected_heads=(),
        resulting_entries=(previous_entry,),
        resulting_heads=(previous.epoch_ref,),
    )
    assert previous_append.history_receipt_ref is not None
    previous_receipt = _persist_epoch_receipt(
        store,
        manifest=previous,
        manifest_ref=previous_ref,
        history_receipt_ref=previous_append.history_receipt_ref,
    )
    current = _epoch_manifest(
        scope=scope,
        label="current",
        predecessors=(previous.epoch_ref,),
    )
    current_ref = _persist_epoch_manifest(store, current)
    current_entry = _epoch_history_entry(current, current_ref)
    current_append = _append_epoch_manifest(
        history,
        scope=scope,
        manifest=current,
        manifest_ref=current_ref,
        expected_heads=(previous.epoch_ref,),
        resulting_entries=(previous_entry, current_entry),
        resulting_heads=(current.epoch_ref,),
    )
    assert current_append.history_receipt_ref is not None
    current_receipt = _persist_epoch_receipt(
        store,
        manifest=current,
        manifest_ref=current_ref,
        history_receipt_ref=current_append.history_receipt_ref,
    )
    return _TransitionHistoryFixture(
        store=store,
        history=history,
        scope=scope,
        previous=previous,
        previous_ref=previous_ref,
        previous_receipt=previous_receipt,
        current=current,
        current_ref=current_ref,
        current_receipt=current_receipt,
    )


def _transition_history_adapter(
    fixture: _TransitionHistoryFixture,
):
    return cascade.FileSemanticEpochTransitionHistoryAdapter(
        artifacts=fixture.store,
        history=fixture.history,
    )


def test_file_transition_history_adapter_resolves_exact_declared_predecessor(
    tmp_path: Path,
) -> None:
    fixture = _transition_history_fixture(tmp_path)

    previous, current = _transition_history_adapter(fixture).resolve_transition_manifests(
        previous_epoch_ref=fixture.previous_ref,
        current_epoch_receipt_ref=fixture.current_receipt.receipt_ref,
        authority_purpose="decision_validity",
    )

    assert previous == fixture.previous
    assert current == fixture.current


def test_file_transition_history_adapter_rejects_receipt_profile_substitution(
    tmp_path: Path,
) -> None:
    fixture = _transition_history_fixture(tmp_path)
    substituted = fixture.current_receipt.receipt_ref.model_copy(
        update={"kind": "epoch.not_a_production_receipt"}
    )

    with pytest.raises(ValueError, match="epoch transition receipt artifact profile mismatch"):
        _transition_history_adapter(fixture).resolve_transition_manifests(
            previous_epoch_ref=fixture.previous_ref,
            current_epoch_receipt_ref=substituted,
            authority_purpose="decision_validity",
        )


def test_file_transition_history_adapter_rejects_receipt_manifest_substitution(
    tmp_path: Path,
) -> None:
    fixture = _transition_history_fixture(tmp_path)
    substituted = _persist_epoch_receipt(
        fixture.store,
        manifest=fixture.previous,
        manifest_ref=fixture.previous_ref,
        history_receipt_ref=fixture.current_receipt.history_append_receipt_ref,
        epoch_ref=fixture.current.epoch_ref,
    )

    with pytest.raises(ValueError, match="epoch transition receipt semantic manifest mismatch"):
        _transition_history_adapter(fixture).resolve_transition_manifests(
            previous_epoch_ref=fixture.previous_ref,
            current_epoch_receipt_ref=substituted.receipt_ref,
            authority_purpose="decision_validity",
        )


@pytest.mark.parametrize("changed_field", ["scope", "purpose"])
def test_file_transition_history_adapter_rejects_previous_from_another_owner_scope(
    tmp_path: Path,
    changed_field: str,
) -> None:
    fixture = _transition_history_fixture(tmp_path)
    other = _epoch_manifest(
        scope=_epoch_scope("other-scope") if changed_field == "scope" else fixture.scope,
        label=f"other-{changed_field}",
        predecessors=(),
        authority_purpose=(
            "claim_lifecycle" if changed_field == "purpose" else "decision_validity"
        ),
    )
    other_ref = _persist_epoch_manifest(fixture.store, other)
    diagnostic = (
        "epoch transition manifest scope mismatch"
        if changed_field == "scope"
        else "epoch transition manifest purpose mismatch"
    )

    with pytest.raises(ValueError, match=diagnostic):
        _transition_history_adapter(fixture).resolve_transition_manifests(
            previous_epoch_ref=other_ref,
            current_epoch_receipt_ref=fixture.current_receipt.receipt_ref,
            authority_purpose="decision_validity",
        )


def test_file_transition_history_adapter_rejects_missing_or_ambiguous_predecessor(
    tmp_path: Path,
) -> None:
    fixture = _transition_history_fixture(tmp_path / "missing")
    unrecorded = _epoch_manifest(
        scope=fixture.scope,
        label="unrecorded",
        predecessors=(),
    )
    unrecorded_ref = _persist_epoch_manifest(fixture.store, unrecorded)
    with pytest.raises(ValueError, match="epoch transition previous epoch is not declared"):
        _transition_history_adapter(fixture).resolve_transition_manifests(
            previous_epoch_ref=unrecorded_ref,
            current_epoch_receipt_ref=fixture.current_receipt.receipt_ref,
            authority_purpose="decision_validity",
        )

    store = artifacts.FileSystemCAS(tmp_path / "ambiguous" / "cas")
    history = FileSemanticEpochHistoryRepository(
        root=tmp_path / "ambiguous" / "history",
        artifacts=store,
    )
    scope = _epoch_scope("ambiguous")
    left = _epoch_manifest(scope=scope, label="left", predecessors=())
    left_ref = _persist_epoch_manifest(store, left)
    left_entry = _epoch_history_entry(left, left_ref)
    _append_epoch_manifest(
        history,
        scope=scope,
        manifest=left,
        manifest_ref=left_ref,
        expected_heads=(),
        resulting_entries=(left_entry,),
        resulting_heads=(left.epoch_ref,),
    )
    right = _epoch_manifest(scope=scope, label="right", predecessors=())
    right_ref = _persist_epoch_manifest(store, right)
    right_entry = _epoch_history_entry(right, right_ref)
    branch_heads = tuple(sorted((left.epoch_ref, right.epoch_ref)))
    _append_epoch_manifest(
        history,
        scope=scope,
        manifest=right,
        manifest_ref=right_ref,
        expected_heads=(left.epoch_ref,),
        resulting_entries=(left_entry, right_entry),
        resulting_heads=branch_heads,
    )
    merged = _epoch_manifest(scope=scope, label="merged", predecessors=branch_heads)
    merged_ref = _persist_epoch_manifest(store, merged)
    merged_entry = _epoch_history_entry(merged, merged_ref)
    merged_append = _append_epoch_manifest(
        history,
        scope=scope,
        manifest=merged,
        manifest_ref=merged_ref,
        expected_heads=branch_heads,
        resulting_entries=(left_entry, right_entry, merged_entry),
        resulting_heads=(merged.epoch_ref,),
    )
    assert merged_append.history_receipt_ref is not None
    merged_receipt = _persist_epoch_receipt(
        store,
        manifest=merged,
        manifest_ref=merged_ref,
        history_receipt_ref=merged_append.history_receipt_ref,
    )
    adapter = cascade.FileSemanticEpochTransitionHistoryAdapter(
        artifacts=store,
        history=history,
    )

    with pytest.raises(ValueError, match="epoch transition previous epoch is ambiguous"):
        adapter.resolve_transition_manifests(
            previous_epoch_ref=left_ref,
            current_epoch_receipt_ref=merged_receipt.receipt_ref,
            authority_purpose="decision_validity",
        )


def test_file_transition_history_adapter_rejects_non_head_current_epoch(
    tmp_path: Path,
) -> None:
    fixture = _transition_history_fixture(tmp_path)

    with pytest.raises(ValueError, match="epoch transition current epoch is not the sole head"):
        _transition_history_adapter(fixture).resolve_transition_manifests(
            previous_epoch_ref=fixture.previous_ref,
            current_epoch_receipt_ref=fixture.previous_receipt.receipt_ref,
            authority_purpose="decision_validity",
        )


@pytest.mark.parametrize("corrupt_artifact", ["receipt", "manifest"])
def test_file_transition_history_adapter_rejects_corrupt_exact_bytes(
    tmp_path: Path,
    corrupt_artifact: str,
) -> None:
    fixture = _transition_history_fixture(tmp_path)
    artifact_id = (
        fixture.current_receipt.receipt_ref.artifact_id
        if corrupt_artifact == "receipt"
        else fixture.current_ref.artifact_id
    )
    blob_path, _ = fixture.store.get_paths(artifact_id)
    blob_path.write_bytes(blob_path.read_bytes() + b"corrupt")
    diagnostic = (
        "epoch transition receipt CAS readback failed"
        if corrupt_artifact == "receipt"
        else "epoch transition semantic manifest CAS readback failed"
    )

    with pytest.raises(ValueError, match=diagnostic):
        _transition_history_adapter(fixture).resolve_transition_manifests(
            previous_epoch_ref=fixture.previous_ref,
            current_epoch_receipt_ref=fixture.current_receipt.receipt_ref,
            authority_purpose="decision_validity",
        )


@pytest.mark.parametrize(
    ("source_class", "event_type", "expected_action"),
    [
        ("incident", "incident", "invalidate"),
        ("appeal", "policy_context_drift", "reissue"),
        ("correction", "source_invalidation", "supersede"),
        ("retraction", "source_invalidation", "withdraw"),
        ("legal_change", "policy_context_drift", "supersede"),
        ("discovered_bias", "fairness_drift", "invalidate"),
    ],
)
def test_persisted_monitor_bridge_preserves_each_perturbation_class_and_scope(
    tmp_path,
    source_class: str,
    event_type: str,
    expected_action: str,
) -> None:
    store = artifacts.FileSystemCAS(tmp_path / source_class)
    packet_ref = _ref(f"{source_class}-packet", kind="scientist.decision_packet")
    evidence_ref = _ref(f"{source_class}-evidence")
    perturbation_payloads = {
        "incident": {
            "source_class": "incident",
            "incident_report_ref": evidence_ref,
        },
        "appeal": {
            "source_class": "appeal",
            "appeal_evidence_ref": evidence_ref,
            "affected_instance_ref": packet_ref,
            "scope": "instance",
        },
        "correction": {
            "source_class": "correction",
            "evidence_validity_event_ref": evidence_ref,
            "replacement_refs": [_ref("correction-replacement")],
        },
        "retraction": {
            "source_class": "retraction",
            "evidence_validity_event_ref": evidence_ref,
        },
        "legal_change": {
            "source_class": "legal_change",
            "legal_change_evidence_ref": evidence_ref,
        },
        "discovered_bias": {
            "source_class": "discovered_bias",
            "bias_evidence_ref": evidence_ref,
        },
    }
    persisted_monitor = persist_governance_monitor_event(
        store,
        GovernanceMonitorEvent.model_validate(
            {
                "event_id": f"event-{source_class}",
                "decision_packet_ref": packet_ref,
                "event_type": event_type,
                "severity": "warning",
                "reason": f"Content-bound {source_class} perturbation.",
                "observed_epoch_ref": _digest(f"{source_class}-epoch"),
                "perturbation": perturbation_payloads[source_class],
            }
        ),
    )

    derived = advisory_perturbation_from_monitor_event(persisted_monitor)
    persisted_ref = persist_advisory_perturbation_event(
        store=store,
        persisted_monitor_event=persisted_monitor,
    )
    loaded = resolve_advisory_perturbation_event(store=store, ref=persisted_ref)

    assert loaded == derived
    assert loaded.source_class == source_class
    assert loaded.event_kind == expected_action
    assert loaded.scope == ("instance" if source_class == "appeal" else "dependency_descendants")
    assert loaded.event_ref == persisted_monitor.event_ref
    manifest = store.get_manifest(persisted_ref.artifact_id)
    assert [(str(row.artifact_id), row.role) for row in manifest.inputs] == [
        (str(persisted_monitor.event_ref.artifact_id), "governance_monitor_event")
    ]


def test_outer_query_context_uses_the_frozen_canonicalization_domain() -> None:
    with pytest.raises(ValueError, match="float"):
        _framed_semantic_hash("outer", {"value": 0.5})

    assert _framed_semantic_hash("outer", {"value": None}) != _framed_semantic_hash("outer", {})


def test_recipe_binding_cannot_project_execution() -> None:
    calls: list[str] = []

    class _ExecutableLookingRecipe(DerivationRecipeBinding):
        def execute(self) -> None:
            calls.append("executed")

    recipe = _ExecutableLookingRecipe(
        recipe_ref=_ref("recipe", kind="epoch.derivation_recipe"),
        recipe_content_hash=_digest("recipe-content"),
        recipe_schema_profile_ref=_digest("recipe-schema"),
        input_roles=("certificate",),
    )
    epoch = SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch"))

    binding = bind_certificate_to_epoch(
        certificate_ref=_ref("certificate", kind="decision.certificate"),
        certificate_content_hash=_digest("certificate-content"),
        epoch=epoch,
        input_certificate_refs=(),
        recipe=recipe,
        canonical_producer_ref="producer://decision-validity",
        authority_purpose="decision_validity",
        native_coordinate_refs=(_digest("valid"),),
        rule_schema_profile_refs=(_digest("rule"),),
    )

    assert binding.epoch_ref == _digest("epoch")
    assert hasattr(recipe, "execute")
    assert calls == []
    assert not hasattr(binding, "execute")

    source_root = Path(__file__).resolve().parents[4] / "src"
    execution_calls: list[str] = []
    parsed_files = 0
    for source_path in source_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        parsed_files += 1
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            receiver = node.func.value
            if (
                node.func.attr in {"execute", "run", "invoke"}
                and isinstance(receiver, ast.Name)
                and "recipe" in receiver.id.lower()
            ):
                execution_calls.append(
                    f"{source_path.relative_to(source_root)}:{node.lineno}:"
                    f"{receiver.id}.{node.func.attr}"
                )
    assert parsed_files > 0
    assert execution_calls == []


def test_certificate_binding_hash_governs_every_authority_input() -> None:
    recipe = DerivationRecipeBinding(
        recipe_ref=_ref("recipe", kind="epoch.derivation_recipe"),
        recipe_content_hash=_digest("recipe-content"),
        recipe_schema_profile_ref=_digest("recipe-schema"),
        input_roles=("certificate",),
    )
    binding = bind_certificate_to_epoch(
        certificate_ref=_ref("certificate", kind="decision.certificate"),
        certificate_content_hash=_digest("certificate-content"),
        epoch=SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch")),
        input_certificate_refs=(_ref("input", kind="decision.certificate"),),
        recipe=recipe,
        canonical_producer_ref="producer://decision-validity",
        authority_purpose="decision_validity",
        native_coordinate_refs=(_digest("valid"),),
        rule_schema_profile_refs=(_digest("rule"),),
    )
    mutations = {
        "certificate_ref": _ref("other-certificate", kind="decision.certificate"),
        "certificate_content_hash": _digest("other-certificate-content"),
        "epoch_ref": _digest("other-epoch"),
        "input_certificate_refs": (),
        "recipe": recipe.model_copy(update={"recipe_content_hash": _digest("other-recipe")}),
        "canonical_producer_ref": "producer://other",
        "authority_purpose": "claim_lifecycle",
        "native_coordinate_refs": (_digest("other-valid"),),
        "rule_schema_profile_refs": (_digest("other-rule"),),
    }

    for field, value in mutations.items():
        payload = binding.model_dump(mode="python")
        payload[field] = value
        with pytest.raises(
            ValueError,
            match="epoch_certificate_binding_content_mismatch",
        ):
            EpochCertificateBinding.model_validate(payload)


def test_same_advisory_event_follows_changed_canonical_owner_disposition() -> None:
    target = _ref("owner-target")
    graph = _graph(target)
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("owner-event"),
        target_ref=target,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )

    def owner(disposition: str, evidence: str) -> OwnerAdjudicatedTargetDisposition:
        return OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition=disposition,
            owner_evidence_ref=_ref(evidence),
            owner_evidence_content_hash=_digest(f"{evidence}-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        )

    first = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=(owner("invalidate", "owner-first"),),
        dependency_graph=graph,
    )
    second = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=(owner("annotation_only", "owner-second"),),
        dependency_graph=graph,
    )

    assert first.rows[0].disposition == "invalidate"
    assert second.rows[0].disposition == "annotation_only"
    assert first.vector_content_hash != second.vector_content_hash


def test_linked_invalidation_preserves_historically_authentic_certificate_bytes() -> None:
    recipe = DerivationRecipeBinding(
        recipe_ref=_ref("history-recipe", kind="epoch.derivation_recipe"),
        recipe_content_hash=_digest("history-recipe-content"),
        recipe_schema_profile_ref=_digest("history-recipe-schema"),
        input_roles=("certificate",),
    )
    binding = bind_certificate_to_epoch(
        certificate_ref=_ref("historical-certificate", kind="decision.certificate"),
        certificate_content_hash=_digest("historical-certificate-content"),
        epoch=SemanticEpochManifest.model_construct(epoch_ref=_digest("historical-epoch")),
        input_certificate_refs=(),
        recipe=recipe,
        canonical_producer_ref="producer://decision-validity",
        authority_purpose="decision_validity",
        native_coordinate_refs=(_digest("historical-valid"),),
        rule_schema_profile_refs=(_digest("historical-rule"),),
    )
    original_bytes = binding.model_dump_json()
    target = binding.certificate_ref
    graph = _graph(target)
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("later-invalidation"),
        target_ref=target,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("later-epoch"),
    )
    owner = OwnerAdjudicatedTargetDisposition(
        target_ref=target,
        event_ref=event.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("later-owner"),
        owner_evidence_content_hash=_digest("later-owner-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )

    vector = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=(owner,),
        dependency_graph=graph,
    )

    assert vector.rows[0].disposition == "invalidate"
    assert EpochCertificateBinding.model_validate_json(original_bytes) == binding
    assert binding.epoch_ref == _digest("historical-epoch")


def test_owner_dispositions_preserve_mixed_append_only_history() -> None:
    first = _ref("target-a")
    second = _ref("target-b")
    graph = _graph(first, second)
    event_a = AdvisoryPerturbationEvent(
        event_ref=_ref("event-a"),
        target_ref=first,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    event_b = AdvisoryPerturbationEvent(
        event_ref=_ref("event-b"),
        target_ref=second,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="annotation_only",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    owner_a = OwnerAdjudicatedTargetDisposition(
        target_ref=first,
        event_ref=event_a.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("owner-a"),
        owner_evidence_content_hash=_digest("owner-a-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )
    owner_b = OwnerAdjudicatedTargetDisposition(
        target_ref=second,
        event_ref=event_b.event_ref,
        disposition="annotation_only",
        owner_evidence_ref=_ref("owner-b"),
        owner_evidence_content_hash=_digest("owner-b-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )

    vector = resolve_owner_target_dispositions(
        advisory_events=(event_b, event_a),
        owner_dispositions=(owner_a, owner_b),
        dependency_graph=graph,
    )

    assert {row.disposition for row in vector.rows} == {
        "annotation_only",
        "invalidate",
    }
    assert tuple(str(row.target_ref.artifact_id) for row in vector.rows) == tuple(
        sorted(str(row.target_ref.artifact_id) for row in vector.rows)
    )

    conflicting = owner_a.model_copy(update={"disposition": "reissue"})
    contested = resolve_owner_target_dispositions(
        advisory_events=(event_a,),
        owner_dispositions=(owner_a, conflicting),
        dependency_graph=_graph(first),
    )
    assert contested.rows[0].disposition == "contested"


def test_owner_disposition_cannot_nominate_a_target_outside_denominator() -> None:
    target = _ref("target")
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("event"),
        target_ref=target,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("epoch"),
    )
    owner = OwnerAdjudicatedTargetDisposition(
        target_ref=target,
        event_ref=event.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("owner"),
        owner_evidence_content_hash=_digest("owner-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )

    with pytest.raises(ValueError, match="outside_dependency_denominator"):
        resolve_owner_target_dispositions(
            advisory_events=(event,),
            owner_dispositions=(owner,),
            dependency_graph=_graph(_ref("other")),
        )


def test_disposition_requires_exact_target_and_authority_purpose() -> None:
    target = _ref("target")
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("event"),
        target_ref=target,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="invalidate",
        authority_purpose="claim_lifecycle",
        observed_epoch_ref=_digest("epoch"),
    )
    owner = OwnerAdjudicatedTargetDisposition(
        target_ref=target,
        event_ref=event.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("owner"),
        owner_evidence_content_hash=_digest("owner-content"),
        authority_purpose="claim_lifecycle",
        predicate_class="independently_reconciled",
    )

    with pytest.raises(ValueError, match="advisory_event_authority_purpose_mismatch"):
        resolve_owner_target_dispositions(
            advisory_events=(event,),
            owner_dispositions=(owner,),
            dependency_graph=_graph(target),
        )

    accepted_event = event.model_copy(update={"authority_purpose": "decision_validity"})
    with pytest.raises(ValueError, match="owner_disposition_authority_purpose_mismatch"):
        resolve_owner_target_dispositions(
            advisory_events=(accepted_event,),
            owner_dispositions=(owner,),
            dependency_graph=_graph(target),
        )

    wrong_kind = target.model_copy(update={"kind": "wrong.kind"})
    with pytest.raises(ValueError, match="outside_dependency_denominator"):
        resolve_owner_target_dispositions(
            advisory_events=(accepted_event.model_copy(update={"target_ref": wrong_kind}),),
            owner_dispositions=(),
            dependency_graph=_graph(target),
        )


def test_disposition_vector_is_invariant_to_transport_order() -> None:
    target = _ref("target")
    events = tuple(
        AdvisoryPerturbationEvent(
            event_ref=_ref(f"event-{index}"),
            target_ref=target,
            source_class="incident",
            scope="dependency_descendants",
            event_kind="invalidate",
            authority_purpose="decision_validity",
            observed_epoch_ref=_digest("epoch"),
        )
        for index in range(2)
    )
    owners = tuple(
        OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition="invalidate",
            owner_evidence_ref=_ref(f"owner-{index}"),
            owner_evidence_content_hash=_digest(f"owner-{index}-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        )
        for index, event in enumerate(events)
    )

    forward = resolve_owner_target_dispositions(
        advisory_events=events,
        owner_dispositions=owners,
        dependency_graph=_graph(target),
    )
    reverse = resolve_owner_target_dispositions(
        advisory_events=tuple(reversed(events)),
        owner_dispositions=tuple(reversed(owners)),
        dependency_graph=_graph(target),
    )

    assert reverse == forward
    assert reverse.vector_content_hash == forward.vector_content_hash


def test_exact_graph_propagates_to_descendants_and_stops_at_sibling() -> None:
    root = _ref("root")
    child = _ref("child")
    grandchild = _ref("grandchild")
    sibling = _ref("sibling")
    edges = (
        EpochDependencyEdge(
            source_ref=root,
            target_ref=child,
            relation="invalidates",
            authority_purpose="decision_validity",
        ),
        EpochDependencyEdge(
            source_ref=child,
            target_ref=grandchild,
            relation="invalidates",
            authority_purpose="decision_validity",
        ),
        EpochDependencyEdge(
            source_ref=root,
            target_ref=sibling,
            relation="unaffected_sibling",
            authority_purpose="claim_lifecycle",
        ),
    )
    graph = EpochDependencyGraph(
        edges=edges,
        denominator_ref=_semantic_hash("polisyos.epoch.dependency-graph.v1", {"edges": edges}),
    )
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("root-event"),
        target_ref=root,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    owners = tuple(
        OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition="invalidate",
            owner_evidence_ref=_ref(f"owner-{label}"),
            owner_evidence_content_hash=_digest(f"owner-{label}-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        )
        for label, target in (("child", child), ("grandchild", grandchild))
    )

    vector = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=owners,
        dependency_graph=graph,
    )
    by_target = {str(row.target_ref.artifact_id): row for row in vector.rows}

    assert by_target[str(child.artifact_id)].disposition == "invalidate"
    assert by_target[str(grandchild.artifact_id)].disposition == "invalidate"
    assert by_target[str(sibling.artifact_id)].disposition == "unchanged"
    assert by_target[str(child.artifact_id)].advisory_event_refs == (event.event_ref,)
    assert by_target[str(grandchild.artifact_id)].advisory_event_refs == (event.event_ref,)

    with pytest.raises(ValueError, match="outside_dependency_denominator"):
        resolve_owner_target_dispositions(
            advisory_events=(event.model_copy(update={"target_ref": _ref("root-copy")}),),
            owner_dispositions=(),
            dependency_graph=graph,
        )


def test_six_source_classes_remain_distinct_and_appeal_stays_instance_scoped() -> None:
    upstream = _ref("six-class-upstream")
    root = _ref("six-class-root")
    child = _ref("six-class-child")
    edges = (
        EpochDependencyEdge(
            source_ref=upstream,
            target_ref=root,
            relation="invalidates",
            authority_purpose="decision_validity",
        ),
        EpochDependencyEdge(
            source_ref=root,
            target_ref=child,
            relation="invalidates",
            authority_purpose="decision_validity",
        ),
    )
    graph = EpochDependencyGraph(
        edges=edges,
        denominator_ref=_semantic_hash("polisyos.epoch.dependency-graph.v1", {"edges": edges}),
    )
    source_classes = (
        "incident",
        "appeal",
        "correction",
        "retraction",
        "legal_change",
        "discovered_bias",
    )
    events = tuple(
        AdvisoryPerturbationEvent(
            event_ref=_ref(f"six-class-{source_class}"),
            target_ref=root,
            source_class=source_class,
            scope="instance" if source_class == "appeal" else "dependency_descendants",
            event_kind="invalidate",
            authority_purpose="decision_validity",
            observed_epoch_ref=_digest("six-class-old-epoch"),
        )
        for source_class in source_classes
    )

    vector = resolve_owner_target_dispositions(
        advisory_events=events,
        owner_dispositions=(),
        dependency_graph=graph,
    )
    by_target = {str(row.target_ref.artifact_id): row for row in vector.rows}

    assert by_target[str(root.artifact_id)].source_classes == tuple(sorted(source_classes))
    assert by_target[str(root.artifact_id)].disposition == "review_required"
    assert "appeal" not in by_target[str(child.artifact_id)].source_classes
    assert by_target[str(child.artifact_id)].source_classes == tuple(
        sorted(source_class for source_class in source_classes if source_class != "appeal")
    )
    with pytest.raises(ValueError, match="appeal_perturbation_requires_instance_scope"):
        AdvisoryPerturbationEvent(
            event_ref=_ref("overbroad-appeal"),
            target_ref=root,
            source_class="appeal",
            scope="dependency_descendants",
            event_kind="invalidate",
            authority_purpose="decision_validity",
            observed_epoch_ref=_digest("six-class-old-epoch"),
        )


def test_annotation_cannot_cancel_an_authority_transition() -> None:
    target = _ref("annotation-target")
    event = AdvisoryPerturbationEvent(
        event_ref=_ref("annotation-event"),
        target_ref=target,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="annotation_only",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    owner_rows = (
        OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition="annotation_only",
            owner_evidence_ref=_ref("annotation-owner"),
            owner_evidence_content_hash=_digest("annotation-owner-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        ),
        OwnerAdjudicatedTargetDisposition(
            target_ref=target,
            event_ref=event.event_ref,
            disposition="invalidate",
            owner_evidence_ref=_ref("invalidate-owner"),
            owner_evidence_content_hash=_digest("invalidate-owner-content"),
            authority_purpose="decision_validity",
            predicate_class="independently_reconciled",
        ),
    )

    vector = resolve_owner_target_dispositions(
        advisory_events=(event,),
        owner_dispositions=owner_rows,
        dependency_graph=_graph(target),
    )

    assert vector.rows[0].disposition == "invalidate"


def test_dependency_and_adjudication_receipts_bind_complete_denominators() -> None:
    target = _ref("bound-target")
    graph = _graph(target)
    dependency_payload = {
        "certificate_bindings": (),
        "dependency_graph": graph,
        "target_refs": (target,),
    }
    outer_denominator_ref = cascade.epoch_dependency_outer_denominator_ref(
        certificate_bindings=(),
        dependency_graph=graph,
    )
    assert outer_denominator_ref == _semantic_hash(
        "polisyos.epoch.dependency-denominator.v1", dependency_payload
    )
    dependency = EpochDependencyDenominatorReceipt(
        denominator_ref=outer_denominator_ref,
        **dependency_payload,
        predicate_class="independently_reconciled",
    )
    assert dependency.target_refs == (target,)
    with pytest.raises(ValueError, match="epoch_dependency_target_denominator_mismatch"):
        EpochDependencyDenominatorReceipt.model_validate(
            {**dependency.model_dump(mode="json"), "target_refs": []}
        )

    event = AdvisoryPerturbationEvent(
        event_ref=_ref("bound-event"),
        target_ref=target,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=_digest("old-epoch"),
    )
    owner = OwnerAdjudicatedTargetDisposition(
        target_ref=target,
        event_ref=event.event_ref,
        disposition="invalidate",
        owner_evidence_ref=_ref("bound-owner"),
        owner_evidence_content_hash=_digest("bound-owner-content"),
        authority_purpose="decision_validity",
        predicate_class="independently_reconciled",
    )
    adjudication_payload = {
        "advisory_events": (event,),
        "owner_dispositions": (owner,),
    }
    receipt = EpochPerturbationAdjudicationReceipt(
        denominator_ref=_semantic_hash(
            "polisyos.epoch.perturbation-adjudication-denominator.v1",
            adjudication_payload,
        ),
        **adjudication_payload,
        predicate_class="independently_reconciled",
    )
    assert receipt.owner_dispositions == (owner,)
    with pytest.raises(ValueError, match="epoch_perturbation_adjudication_denominator_mismatch"):
        EpochPerturbationAdjudicationReceipt.model_validate(
            {
                **receipt.model_dump(mode="json"),
                "owner_dispositions": [],
            }
        )


def test_signed_transition_preimage_binds_owner_purpose_and_both_denominators() -> None:
    target = _ref("transition-target")
    graph = _graph(target)
    vector = resolve_owner_target_dispositions(
        advisory_events=(),
        owner_dispositions=(),
        dependency_graph=graph,
    )
    adjudication_denominator_ref = _digest("transition-adjudication-denominator")
    outer_denominator_ref = cascade.epoch_dependency_outer_denominator_ref(
        certificate_bindings=(),
        dependency_graph=graph,
    )
    assert outer_denominator_ref != graph.denominator_ref

    transition = build_epoch_validity_transition(
        previous_epoch=SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch-old")),
        current_epoch=SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch-new")),
        certificates=(),
        dependency_graph=graph,
        target_vector=vector,
        dependency_denominator_ref=outer_denominator_ref,
        adjudication_denominator_ref=adjudication_denominator_ref,
        requested_query_context_ref=_digest("transition-query"),
        authority_purpose="decision_validity",
    )

    assert transition.dependency_denominator_ref == outer_denominator_ref
    assert transition.adjudication_denominator_ref == adjudication_denominator_ref
    assert transition.authority_purpose == "decision_validity"
    for field, mutation, diagnostic in (
        (
            "dependency_denominator_ref",
            _digest("other-dependency-denominator"),
            "epoch_validity_transition_content_mismatch",
        ),
        (
            "adjudication_denominator_ref",
            _digest("other-adjudication-denominator"),
            "epoch_validity_transition_content_mismatch",
        ),
        ("authority_purpose", "claim_lifecycle", "epoch_validity_transition_content_mismatch"),
    ):
        payload = transition.model_dump(mode="json")
        payload[field] = mutation
        with pytest.raises(ValueError, match=diagnostic):
            EpochValidityTransitionArtifact.model_validate(payload)


def test_unappointed_transition_signer_returns_typed_negative_before_owner_reads() -> None:
    class NoOwnerCalls:
        def __getattr__(self, name: str):
            raise AssertionError(f"unappointed signer must precede owner read: {name}")

    producer = EpochValidityTransitionProducer(
        dependency_inventory=NoOwnerCalls(),  # type: ignore[arg-type]
        adjudications=NoOwnerCalls(),  # type: ignore[arg-type]
        epoch_history=NoOwnerCalls(),  # type: ignore[arg-type]
        signed_artifacts=NoOwnerCalls(),  # type: ignore[arg-type]
        signing_authority=NoEpochTransitionSigningAuthority(),
    )

    result = producer.produce_and_persist(
        previous_epoch_ref=_ref("previous-epoch"),
        current_epoch_receipt_ref=_ref("current-receipt"),
        requested_query_context_ref=_digest("transition-query"),
        authority_purpose="decision_validity",
    )

    assert result == EpochTransitionSigningNonReceipt(
        status="not_established",
        code="epoch_transition_signer_not_established",
        predicate_class="not_established",
    )
