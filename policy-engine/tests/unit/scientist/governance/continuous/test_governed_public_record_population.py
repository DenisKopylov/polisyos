"""Reconcile source inventory against independently admitted public records."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.governance.continuous import published_signature_custody as custody
from polisyos.scientist.governance.continuous.governed_public_record import (
    GovernedPublicRecordOwner,
    GovernedPublicRecordVerificationResponse,
)
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tests.unit.scientist.governance.continuous.test_governed_public_record import (
    NOW,
    appoint_synthetic_publication,
    build_governed_owner_case,
)


@pytest.fixture
def issued_owner(tmp_path: Path) -> tuple[GovernedPublicRecordOwner, tuple[str, ...]]:
    """Issue two real signatures using explicitly synthetic institutional evidence."""
    store = FileSystemCAS(tmp_path / "cas")
    owner, _, packet_ref, institution, slot = build_governed_owner_case(
        store=store,
        index_root=tmp_path,
        completed_batches=DecisionValidityService(store),
    )
    configured, _ = appoint_synthetic_publication(owner, packet_ref, institution, slot)
    record_ids = tuple(
        configured.issue(
            decision_id="packet-snapshot",
            decision_packet_ref=packet_ref,
            issued_at=NOW + timedelta(minutes=sequence),
        )
        for sequence in (1, 2)
    )
    assert len(set(record_ids)) == 2
    assert configured.issued_record_ids() == tuple(sorted(record_ids))
    return configured, tuple(sorted(record_ids))


class _InventoryView:
    """Change only the supplied set while retaining the real owner verifier."""

    def __init__(self, owner: GovernedPublicRecordOwner, record_ids: tuple[str, ...]) -> None:
        self.owner = owner
        self.record_ids = record_ids

    def issued_record_ids(self) -> tuple[str, ...]:
        return self.record_ids

    def verify(self, record_id: str) -> GovernedPublicRecordVerificationResponse:
        return self.owner.verify(record_id)


@pytest.mark.parametrize("change", ["omit", "add"])
def test_supplied_inventory_cannot_hide_or_invent_controlled_records(issued_owner, change):
    """The complete population works; altering only its supplied denominator closes admission."""
    owner, record_ids = issued_owner
    complete = custody.PublicVerificationRecordPopulationProvider(
        source=_InventoryView(owner, record_ids), admission_source=owner, store=owner.store
    ).resolve()
    assert isinstance(complete, custody.PersistedPublicSignaturePopulation)
    assert len(complete.snapshot.members) == 2

    supplied = record_ids[:1] if change == "omit" else (*record_ids, "gpr_" + "z" * 32)
    result = custody.PublicVerificationRecordPopulationProvider(
        source=_InventoryView(owner, supplied), admission_source=owner, store=owner.store
    ).resolve()

    assert isinstance(result, custody.PublicSignaturePopulationNonReceipt)
    assert result.reason == "governed_public_inventory_not_reconciled"
    assert result.predicate_provenance == "not_established"
    assert result.record_inspections == ()
    assert "controlled_governed_inventory_disagreement" in result.unresolved_by_construction
    reads = {receipt.boundary: receipt for receipt in result.inventory_reads}
    assert reads["report_source"].outcome == reads["admission_owner"].outcome == "read"
    assert reads["report_source"].record_ids == supplied
    assert reads["admission_owner"].record_ids == record_ids
    selected_inputs = {
        item.selector
        for item in reads["admission_owner"].input_reads
        if item.operation == "issued_index.read_bytes" and item.outcome == "read"
    }
    assert selected_inputs == {
        str(owner.index_root / "issued" / f"{record_id}.json") for record_id in record_ids
    }
    serialized = result.model_dump(mode="json")
    assert serialized["inventory_reads"][1]["input_reads"]
    assert "unselected_index_extensions" in reads["admission_owner"].unresolved_by_construction
