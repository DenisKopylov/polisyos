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
    from polisyos.runtime.quality import acquisition_executor
    from tests._helpers.acquisition_epoch_production import build_production_admission_case

    case = build_production_admission_case(tmp_path, monkeypatch)
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
        return original_verified_bytes(
            owner, context=context, artifact_ref=artifact_ref, role=role
        )

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
            if (
                self.deny_policy_admission_reads
                and str(observed_ref) == str(policy_admission_ref.artifact_id)
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
        return original_verified_bytes(
            owner, context=context, artifact_ref=artifact_ref, role=role
        )

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
