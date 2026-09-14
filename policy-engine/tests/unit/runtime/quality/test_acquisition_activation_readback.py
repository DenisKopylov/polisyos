from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from tests.unit.runtime.quality.test_acquisition_executor import (
    _activate_real_epoch_scenario,
    _real_epoch_scenario,
)


def test_active_owner_readback_uses_physical_membership_and_does_not_activate_pending(
    tmp_path: Path,
) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    _, activated = _activate_real_epoch_scenario(scenario)
    resolved = scenario.overlay.read_activated_semantic_epoch_admission(
        receipt_ref=activated.receipt_ref, artifact_store=scenario.store
    )
    assert resolved.admitted_observation_count == activated.admitted_observation_count == 2
    assert resolved.receipt_ref == activated.receipt_ref
    assert resolved.replayed
    con = duckdb.connect(str(scenario.overlay.overlay_path))
    try:
        con.execute(
            "UPDATE acquisition_epochs SET epoch_activation_state='pending_epoch_activation', "
            "semantic_epoch_production_receipt_ref=NULL, activated_overlay_receipt_ref=NULL"
        )
    finally:
        con.close()
    with pytest.raises(RuntimeError):
        scenario.overlay.read_activated_semantic_epoch_admission(
            receipt_ref=activated.receipt_ref, artifact_store=scenario.store
        )


def test_legacy_positive_activation_preserves_bytes_without_native_qualification(
    tmp_path: Path,
) -> None:
    """The prior transaction grammar remains readable, without new native authority."""
    from polisyos.core import artifacts
    from polisyos.core.contracts import chronology as chronology_contract
    from polisyos.core.contracts import epoch as epoch_contract
    from polisyos.runtime.quality import acquisition_executor, semantic_epoch
    from tests.unit.runtime.quality.test_acquisition_executor import (
        _test_positive_production_receipt,
    )

    scenario = _real_epoch_scenario(tmp_path)
    prior = _test_positive_production_receipt(scenario)
    statement = epoch_contract.load_verified_epoch_statement(
        store=scenario.store,
        ref=prior.receipt_ref,
        expected_kind="epoch.production_receipt",
        expected_media_type="application/vnd.polisyos.epoch-production-receipt+json",
    )
    statement.pop("chronology_projection_ref")
    raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
    ref = scenario.store.put_bytes(
        raw,
        artifacts.PutOptions(kind=prior.receipt_ref.kind, media_type=prior.receipt_ref.media_type),
    )
    legacy = semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate(
        {
            **statement,
            "receipt_ref": ref,
            "receipt_content_hash": epoch_contract.epoch_semantic_content_hash(
                domain="polisyos.epoch.production-receipt.v1", value=statement
            ),
        }
    )
    active = scenario.overlay.activate_semantic_epoch(
        pending_receipt=scenario.pending,
        production_receipt=legacy,
        artifact_store=scenario.store,
    )
    reread = scenario.overlay.read_activated_semantic_epoch_admission(
        receipt_ref=active.receipt_ref, artifact_store=scenario.store
    )
    assert reread.semantic_epoch_production_receipt_ref == ref
    assert scenario.store.get_bytes(ref.artifact_id) == raw
    assert legacy.chronology_projection_ref is None
    admitted = epoch_contract.AdmittedAcquisitionBoundaryEvidence.model_validate(
        epoch_contract.load_verified_epoch_statement(
            store=scenario.store,
            ref=legacy.admitted_boundary_evidence_ref,
            expected_kind="epoch.admitted_acquisition_boundary_evidence",
        )
    )
    receipt = acquisition_executor.ActivatedSemanticEpochAdmissionReceipt(
        passport_ref=admitted.passport_ref,
        prepared_epoch_ref=admitted.prepared_epoch_ref,
        pending_overlay_receipt_ref=admitted.pending_overlay_receipt_ref,
        semantic_epoch_production_receipt_ref=ref,
        overlay_admission_receipt_ref=active.receipt_ref,
        native_membership_receipt_ref=admitted.native_membership_receipt_ref,
        semantic_denominator_receipt_ref=admitted.semantic_denominator_receipt_ref,
        semantic_projection_verification_receipt_ref=admitted.semantic_projection_verification_receipt_ref,
        semantic_epoch_stamp=admitted.semantic_epoch_stamp,
        activation_state="active",
    )
    with pytest.raises(RuntimeError):
        acquisition_executor.resolve_activated_semantic_epoch_admission(
            receipt=receipt,
            artifact_store=scenario.store,
            overlay=scenario.overlay,
        )
