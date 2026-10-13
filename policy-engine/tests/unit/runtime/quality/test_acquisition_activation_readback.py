from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from tests._helpers.semantic_epoch_native import _real_epoch_scenario
from tests.unit.runtime.quality.test_acquisition_executor import (
    _activate_real_epoch_scenario,
)


def test_active_owner_readback_uses_physical_membership_and_does_not_activate_pending(
    tmp_path: Path,
) -> None:
    scenario = _real_epoch_scenario(tmp_path)
    _, activated = _activate_real_epoch_scenario(scenario)
    resolved = scenario.overlay.read_activated_semantic_epoch_admission(
        receipt_ref=activated.receipt_ref,
        artifact_store=scenario.store,
        passport=scenario.passport,
        authority=scenario.authority,
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
            receipt_ref=activated.receipt_ref,
            artifact_store=scenario.store,
            passport=scenario.passport,
            authority=scenario.authority,
        )


def test_profileless_legacy_production_receipt_cannot_activate_semantic_epoch(
    tmp_path: Path,
) -> None:
    """Historical bytes remain intact, but absence cannot create a current active state."""
    from polisyos.core import artifacts
    from polisyos.core.contracts import chronology as chronology_contract
    from polisyos.core.contracts import epoch as epoch_contract
    from polisyos.data_forge.domains.catalog.knowledge.overlay import OverlayAdmissionError
    from polisyos.runtime.quality import semantic_epoch
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

    with pytest.raises(OverlayAdmissionError) as refusal:
        scenario.overlay.activate_semantic_epoch(
            pending_receipt=scenario.pending,
            production_receipt=legacy,
            artifact_store=scenario.store,
        )
    assert refusal.value.code == "semantic_epoch_production_profile_missing"
    assert scenario.store.get_bytes(ref.artifact_id) == raw

    con = duckdb.connect(str(scenario.overlay.overlay_path), read_only=True)
    try:
        row = con.execute(
            "SELECT epoch_activation_state, semantic_epoch_production_receipt_ref, "
            "activated_overlay_receipt_ref FROM acquisition_epochs WHERE epoch_id = ?",
            [scenario.pending.epoch_id],
        ).fetchone()
    finally:
        con.close()
    assert row == ("pending_epoch_activation", None, None)
