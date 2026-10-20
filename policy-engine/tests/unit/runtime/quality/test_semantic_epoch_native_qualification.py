from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.contracts import chronology as contract
from polisyos.runtime.quality.chronology_qualification import QualificationConsumer


def test_signed_native_epoch_policy_recomputes_and_persists_qualification(tmp_path: Path) -> None:
    from tests._helpers.semantic_epoch_native import make_native_epoch_case

    case = make_native_epoch_case(tmp_path)
    result = QualificationConsumer.from_deployment(case.deployment).qualify(
        request=case.query, adapter=case.adapter
    )
    assert isinstance(result, contract.NativeChronologyQualified)
    assert result.proof_result.verified_member_count == 1
    assert case.store.verify(result.projection_receipt.artifact_ref.artifact_id).ok


@pytest.mark.parametrize(
    ("manifest_profile", "expected_code"),
    [
        ("wrong_valid_profile", "canon_profile_typed_artifact_profile_mismatch"),
        ("absent", "canon_profile_absent"),
    ],
)
def test_native_history_manifest_profile_refuses_before_payload_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest_profile: str,
    expected_code: str,
) -> None:
    import json

    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts.manifest import CanonInfo
    from polisyos.core.canon.canon_json import CanonSpec
    from tests._helpers.semantic_epoch_native import make_native_epoch_case

    case = make_native_epoch_case(tmp_path)
    target_ref = case.staged.history_snapshot_ref
    assert target_ref.manifest_profile_sha256 is None
    wrong_canon = CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    profile_reads: list[str] = []
    payload_reads: list[str] = []
    original_get_raw_manifest = type(case.store).get_raw_manifest_bytes
    original_get_manifest = type(case.store).get_manifest
    original_verify = type(case.store).verify
    original_get_bytes = type(case.store).get_bytes

    def is_target(selector: object) -> bool:
        return getattr(selector, "artifact_id", selector) == target_ref.artifact_id

    def replace_raw_manifest(
        store: object,
        selector: object,
        *,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        raw = original_get_raw_manifest(
            store,
            selector,
            manifest_profile_sha256=manifest_profile_sha256,
        )
        if not is_target(selector):
            return raw
        profile_reads.append("raw")
        manifest = json.loads(raw)
        if manifest_profile == "absent":
            manifest.pop("canon", None)
        else:
            manifest["canon"] = wrong_canon.model_dump(mode="json")
        return json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode()

    def replace_typed_manifest(store: object, selector: object) -> object:
        manifest = original_get_manifest(store, selector)
        if is_target(selector):
            profile_reads.append("typed")
            return manifest.model_copy(update={"canon": wrong_canon})
        return manifest

    def record_verify(store: object, selector: object) -> object:
        if is_target(selector):
            payload_reads.append("verify")
        return original_verify(store, selector)

    def record_get_bytes(store: object, selector: object) -> bytes:
        if is_target(selector):
            payload_reads.append("get_bytes")
        return original_get_bytes(store, selector)

    monkeypatch.setattr(type(case.store), "get_raw_manifest_bytes", replace_raw_manifest)
    monkeypatch.setattr(type(case.store), "get_manifest", replace_typed_manifest)
    monkeypatch.setattr(type(case.store), "verify", record_verify)
    monkeypatch.setattr(type(case.store), "get_bytes", record_get_bytes)

    owner = case.deployment._state().chronology_policy_owner
    assert owner is not None
    with pytest.raises(CanonicalProfileRefusalError) as refused:
        owner._native(case.query)

    assert refused.value.code == expected_code
    assert profile_reads == (["raw"] if manifest_profile == "absent" else ["raw", "typed"])
    assert payload_reads == []


def test_actual_prepared_writer_schema_absence_is_exact_before_payload_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid but wrong schema cannot replace the actual prepared-writer contract."""
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core import artifacts
    from polisyos.core.artifacts import PutOptions
    from polisyos.core.contracts import epoch as epoch_contract
    from tests._helpers.semantic_epoch_native import make_native_epoch_case

    case = make_native_epoch_case(tmp_path)
    prepared_ref = case.scenario.prepared.prepared_epoch_ref
    producer_manifest = case.store.get_manifest(prepared_ref)
    prepared_bytes = case.store.get_bytes(prepared_ref)
    expected_inputs = [
        artifacts.input_ref_from_artifact_ref(
            case.scenario.prepared.stamp.semantic_manifest_ref,
            role="semantic_manifest",
        )
    ]
    assert prepared_ref.manifest_profile_sha256 is not None
    assert producer_manifest.artifact_schema is None
    assert producer_manifest.inputs == expected_inputs
    assert (
        epoch_contract.load_verified_epoch_statement(
            store=case.store,
            ref=prepared_ref,
            expected_kind="epoch.prepared",
        )["status"]
        == "prepared"
    )

    wrong_schema_ref = case.store.put_bytes(
        prepared_bytes,
        PutOptions(
            kind="epoch.prepared",
            media_type="application/vnd.polisyos.epoch+json",
            schema=artifacts.SchemaInfo(
                name="polisyos.runtime.PreparedSemanticEpoch", version="1.0"
            ),
            canon=producer_manifest.canon,
            inputs=expected_inputs,
        ),
        return_selected_profile=True,
    )
    assert wrong_schema_ref.artifact_id == prepared_ref.artifact_id
    assert wrong_schema_ref.manifest_profile_sha256 != prepared_ref.manifest_profile_sha256
    assert case.store.get_bytes(wrong_schema_ref) == prepared_bytes
    assert case.store.get_manifest(wrong_schema_ref).inputs == expected_inputs

    payload_reads: list[str] = []
    original_verify = type(case.store).verify
    original_get_bytes = type(case.store).get_bytes

    def record_verify(store: object, selector: object) -> object:
        if getattr(selector, "artifact_id", selector) == wrong_schema_ref.artifact_id:
            payload_reads.append("verify")
        return original_verify(store, selector)

    def record_get_bytes(store: object, selector: object) -> bytes:
        if getattr(selector, "artifact_id", selector) == wrong_schema_ref.artifact_id:
            payload_reads.append("get_bytes")
        return original_get_bytes(store, selector)

    monkeypatch.setattr(type(case.store), "verify", record_verify)
    monkeypatch.setattr(type(case.store), "get_bytes", record_get_bytes)
    with pytest.raises(CanonicalProfileRefusalError) as refused:
        epoch_contract.load_verified_epoch_statement(
            store=case.store,
            ref=wrong_schema_ref,
            expected_kind="epoch.prepared",
        )

    assert refused.value.code == "canon_profile_typed_artifact_profile_mismatch"
    assert payload_reads == []


def test_native_member_bytes_cannot_be_replaced_with_receipt_markers(tmp_path: Path) -> None:
    from tests._helpers.semantic_epoch_native import make_native_epoch_case

    case = make_native_epoch_case(tmp_path)
    candidate = case.adapter.reconcile_candidate(case.query)
    candidate = contract.NativeChronologyCandidate.model_validate(
        candidate.model_copy(update={"ordered_members": (), "member_predicates": ()}).model_dump(
            mode="python"
        )
    )

    class Counterfeit:
        def reconcile_candidate(self, request):
            assert request == case.query
            return candidate

    result = QualificationConsumer.from_deployment(case.deployment).qualify(
        request=case.query, adapter=Counterfeit()
    )
    assert not isinstance(result, contract.NativeChronologyQualified)
    assert result.failure.code == "policy_owner_relation_not_established"


def test_real_epoch_finalization_activation_and_native_readback(tmp_path: Path) -> None:
    from polisyos.runtime.quality.acquisition_executor import (
        resolve_activated_semantic_epoch_admission,
    )
    from tests._helpers.semantic_epoch_native import (
        finalize_native_epoch_case,
        make_native_epoch_case,
    )

    case = make_native_epoch_case(tmp_path)
    finalized = finalize_native_epoch_case(case)
    resolved = resolve_activated_semantic_epoch_admission(
        receipt=finalized.receipt,
        artifact_store=case.store,
        overlay=case.scenario.overlay,
        authority=case.scenario.authority,
        epoch_deployment=case.deployment,
    )
    production_manifest_ref = finalized.production.semantic_manifest_ref
    assert production_manifest_ref is not None
    selected_profile = production_manifest_ref.manifest_profile_sha256
    assert selected_profile is not None
    history = case.scenario.history.resolve_scope_history(
        scope=case.scenario.query.scope_identity,
        authority_purpose=case.scenario.query.authority_purpose,
    )
    matching_entries = tuple(
        entry for entry in history.entries if entry.epoch_ref == finalized.production.epoch_ref
    )
    assert len(matching_entries) == 1
    history_entry = matching_entries[0]
    assert history_entry.manifest_ref == production_manifest_ref
    assert history_entry.native_member_ref == production_manifest_ref
    assert history_entry.manifest_ref.manifest_profile_sha256 == selected_profile
    assert history_entry.native_member_ref.manifest_profile_sha256 == selected_profile
    assert resolved.admitted_observation_count == 2
    assert resolved.receipt_ref == finalized.activated.receipt_ref
    assert finalized.production.chronology_projection_ref is not None
    assert finalized.production.status == "appended"
    with pytest.raises(RuntimeError):
        resolve_activated_semantic_epoch_admission(
            receipt=finalized.receipt,
            artifact_store=case.store,
            overlay=case.scenario.overlay,
            authority=case.scenario.authority,
        )


def test_activation_selected_receipt_refuses_before_payload_or_integrity_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.runtime.quality.acquisition_executor import (
        SemanticEpochAdmissionResolutionError,
        resolve_activated_semantic_epoch_admission,
    )
    from tests._helpers.semantic_epoch_native import (
        finalize_native_epoch_case,
        make_native_epoch_case,
    )

    case = make_native_epoch_case(tmp_path)
    finalized = finalize_native_epoch_case(case)
    selected_ref = finalized.receipt.semantic_epoch_production_receipt_ref
    unselected_ref = selected_ref.model_copy(update={"manifest_profile_sha256": None})
    receipt = finalized.receipt.model_copy(
        update={"semantic_epoch_production_receipt_ref": unselected_ref}
    )
    observed: list[str] = []
    original_get_bytes = type(case.store).get_bytes
    original_verify = type(case.store).verify

    def record_get_bytes(store, ref):
        if getattr(ref, "artifact_id", ref) == selected_ref.artifact_id:
            observed.append("get_bytes")
        return original_get_bytes(store, ref)

    def record_verify(store, ref):
        if getattr(ref, "artifact_id", ref) == selected_ref.artifact_id:
            observed.append("verify")
        return original_verify(store, ref)

    monkeypatch.setattr(type(case.store), "get_bytes", record_get_bytes)
    monkeypatch.setattr(type(case.store), "verify", record_verify)
    with pytest.raises(SemanticEpochAdmissionResolutionError) as refused:
        resolve_activated_semantic_epoch_admission(
            receipt=receipt,
            artifact_store=case.store,
            overlay=case.scenario.overlay,
            authority=case.scenario.authority,
            epoch_deployment=case.deployment,
        )

    assert "canon_profile_selection_unverified" in refused.value.detail
    assert observed == []


def test_active_read_revalidates_current_source_authority_before_positive_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.runtime.quality.acquisition_executor import (
        SemanticEpochAdmissionResolutionError,
        resolve_activated_semantic_epoch_admission,
    )
    from tests._helpers.semantic_epoch_native import (
        finalize_native_epoch_case,
        make_native_epoch_case,
    )

    case = make_native_epoch_case(tmp_path)
    finalized = finalize_native_epoch_case(case)

    def authority_no_longer_resolves(_entry_id: str) -> object:
        raise ValueError("the current authority owner is unavailable")

    monkeypatch.setattr(case.scenario.authority, "resolve", authority_no_longer_resolves)
    with pytest.raises(SemanticEpochAdmissionResolutionError) as refused:
        resolve_activated_semantic_epoch_admission(
            receipt=finalized.receipt,
            artifact_store=case.store,
            overlay=case.scenario.overlay,
            authority=case.scenario.authority,
            epoch_deployment=case.deployment,
        )
    assert refused.value.code == "basis_mismatch"
    assert "acquisition_authority_unresolved" in refused.value.detail


def test_production_wrapper_activates_the_actual_signed_live_epoch_basis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core.artifacts import validate_core_model_json_artifact
    from polisyos.core.contracts import DataSnapshot
    from polisyos.core.contracts import epoch as epoch_contract
    from polisyos.runtime.quality import acquisition_executor
    from tests._helpers.acquisition_epoch_production import build_production_admission_case

    case = build_production_admission_case(tmp_path, monkeypatch)
    assert case.negative.admitted_boundary_evidence_ref is not None
    admitted = epoch_contract.AdmittedAcquisitionBoundaryEvidence.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=case.store,
            ref=case.negative.admitted_boundary_evidence_ref,
            expected_kind="epoch.admitted_acquisition_boundary_evidence",
        )
    )
    candidate = epoch_contract.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=case.store,
            ref=admitted.semantic_candidate_ref,
            expected_kind="epoch.acquisition_semantic_boundary_candidate",
        )
    )
    source_snapshot = validate_core_model_json_artifact(
        DataSnapshot,
        case.store,
        case.evidence.data_snapshot_ref,
    )
    assert candidate.source_record_ref == source_snapshot.data_ref
    assert candidate.source_record_ref.manifest_profile_sha256 is not None

    activation = acquisition_executor.admit_acquisition_with_production_semantic_epoch(
        **case.call_args, epoch_deployment=case.deployment
    )
    assert isinstance(activation, acquisition_executor.ActivatedSemanticEpochAdmissionReceipt), (
        activation.model_dump_json()
    )
    assert activation.prepared_epoch_ref == case.negative.prepared_epoch_ref
    resolved = acquisition_executor.resolve_activated_semantic_epoch_admission(
        receipt=activation,
        artifact_store=case.store,
        overlay=case.overlay,
        authority=case.authority,
        epoch_deployment=case.deployment,
    )
    assert resolved.admitted_observation_count == 2


def test_runtime_store_scope_retains_native_writer_after_consumer_construction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core import artifacts
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from polisyos.runtime.quality.epoch_deployment import build_epoch_deployment
    from tests._helpers.semantic_epoch_native import make_native_epoch_case

    case = make_native_epoch_case(tmp_path)
    deployment = case.deployment
    original_attestation = deployment.attestation_state()
    signed_admission_ref = deployment._state().config.predicate_policy_admission_refs[0]
    _, admission_record, _ = deployment._signed_model(
        signed_admission_ref,
        contract.PredicatePolicyAdmissionStatement,
        "predicate_policy_admission",
    )
    policy_admission_ref = admission_record.artifact_ref
    observed_policy_stores: list[object] = []
    first = guard_runtime_cas(case.store)
    second = guard_runtime_cas(artifacts.FileSystemCAS(case.store.root))
    unrelated = build_epoch_deployment(case.config)
    wrong = artifacts.FileSystemCAS(tmp_path / "wrong-root")
    writes = []
    original_put = type(case.store).put_bytes
    original_verified_bytes = contract.ChronologyPredicatePolicyArtifacts._verified_bytes

    def record_put(store, data, opts):
        if store is case.store:
            writes.append(opts.kind)
        return original_put(store, data, opts)

    def observe_policy_store(owner, *, context, artifact_ref, role):
        if role == "admission" and artifact_ref == policy_admission_ref:
            observed_policy_stores.append(owner._store)
        return original_verified_bytes(owner, context=context, artifact_ref=artifact_ref, role=role)

    monkeypatch.setattr(type(case.store), "put_bytes", record_put)
    monkeypatch.setattr(
        contract.ChronologyPredicatePolicyArtifacts,
        "_verified_bytes",
        observe_policy_store,
    )
    try:
        with (
            pytest.raises(ValueError, match="backing differs"),
            deployment.composition_scope(runtime_artifact_store=wrong),
        ):
            pytest.fail("different backing must not enter composition")
        with deployment.composition_scope(runtime_artifact_store=first):
            assert deployment._runtime_artifact_store() is first
            for affiliate in deployment._state().runtime_store_affiliates:
                assert affiliate._runtime_artifact_store() is first
            consumer = QualificationConsumer.from_deployment(deployment)
            assert consumer._owner._store is first
            assert consumer._owner._policy_store is first
            with deployment.composition_scope(runtime_artifact_store=second):
                assert deployment._runtime_artifact_store() is second
            assert deployment._runtime_artifact_store() is first
            with unrelated.composition_scope(runtime_artifact_store=second):
                assert unrelated._runtime_artifact_store() is second
                assert deployment._runtime_artifact_store() is first
        assert deployment._runtime_artifact_store() is deployment._state().store
        result = consumer.qualify(request=case.query, adapter=case.adapter)
        assert isinstance(result, contract.NativeChronologyQualified), result
        assert result.projection_receipt.artifact_ref.kind in writes
        assert result.persisted_proof.artifact_ref.kind in writes
        assert observed_policy_stores
        assert all(store is first for store in observed_policy_stores)
        assert deployment.attestation_state() == original_attestation
        assert deployment._runtime_artifact_store() is deployment._state().store
    finally:
        first.close()
        second.close()


def test_native_qualification_fails_when_scoped_policy_admission_read_is_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from tests._helpers.semantic_epoch_native import make_native_epoch_case

    case = make_native_epoch_case(tmp_path)
    deployment = case.deployment
    signed_admission_ref = deployment._state().config.predicate_policy_admission_refs[0]
    _, admission_record, _ = deployment._signed_model(
        signed_admission_ref,
        contract.PredicatePolicyAdmissionStatement,
        "predicate_policy_admission",
    )
    policy_admission_ref = admission_record.artifact_ref
    raw_admission_bytes = case.store.get_bytes(policy_admission_ref.artifact_id)
    raw_root = type(case.store)(case.store.root)
    assert raw_root.get_bytes(policy_admission_ref.artifact_id) == raw_admission_bytes

    class DenyingRuntimeStore:
        """Deny only this scoped runtime read while retaining a readable raw peer."""

        root = case.store.root

        def __init__(self):
            self.deny_policy_admission_reads = False
            self.denied_reads: list[str] = []

        def get_bytes(self, artifact_id):
            observed_ref = getattr(artifact_id, "artifact_id", artifact_id)
            if self.deny_policy_admission_reads and str(observed_ref) == str(
                policy_admission_ref.artifact_id
            ):
                self.denied_reads.append(str(observed_ref))
                raise PermissionError("runtime-bound policy admission read denied")
            return case.store.get_bytes(artifact_id)

        def __getattr__(self, name):
            return getattr(case.store, name)

        def close(self):
            # The guard owns this adapter, not the underlying case store.
            return None

    denied_store = DenyingRuntimeStore()
    runtime_store = guard_runtime_cas(denied_store)
    original_verified_bytes = contract.ChronologyPredicatePolicyArtifacts._verified_bytes

    def deny_only_policy_loader_read(owner, *, context, artifact_ref, role):
        if role == "admission" and artifact_ref == policy_admission_ref:
            denied_store.deny_policy_admission_reads = True
            try:
                return original_verified_bytes(
                    owner, context=context, artifact_ref=artifact_ref, role=role
                )
            finally:
                denied_store.deny_policy_admission_reads = False
        return original_verified_bytes(owner, context=context, artifact_ref=artifact_ref, role=role)

    monkeypatch.setattr(
        contract.ChronologyPredicatePolicyArtifacts,
        "_verified_bytes",
        deny_only_policy_loader_read,
    )
    consumer = QualificationConsumer.from_deployment(
        deployment, runtime_artifact_store=runtime_store
    )

    class StopAfterPolicyReads:
        def reconcile_candidate(self, request):
            raise RuntimeError("stop before native owner verification")

    try:
        result = consumer.qualify(adapter=StopAfterPolicyReads(), request=case.query)
    finally:
        runtime_store.close()

    assert not isinstance(result, contract.NativeChronologyQualified)
    assert result.failure.code == "policy_bytes_missing"
    assert denied_store.denied_reads == [str(policy_admission_ref.artifact_id)]
    assert raw_root.get_bytes(policy_admission_ref.artifact_id) == raw_admission_bytes
