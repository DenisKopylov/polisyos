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
        )


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
    first = guard_runtime_cas(case.store)
    second = guard_runtime_cas(artifacts.FileSystemCAS(case.store.root))
    unrelated = build_epoch_deployment(case.config)
    wrong = artifacts.FileSystemCAS(tmp_path / "wrong-root")
    writes = []
    original_put = type(case.store).put_bytes

    def record_put(store, data, opts):
        if store is case.store:
            writes.append(opts.kind)
        return original_put(store, data, opts)

    monkeypatch.setattr(type(case.store), "put_bytes", record_put)
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
        assert deployment.attestation_state() == original_attestation
        assert deployment._runtime_artifact_store() is deployment._state().store
    finally:
        first.close()
        second.close()
