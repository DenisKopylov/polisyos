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
    store = FileSystemCAS(
        tmp_path / "cas",
        ownership_enforced=True,
        ownership_requires_scope=False,
    )
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


def test_locator_inspection_oserror_is_invalid_not_absent(issued_owner, monkeypatch):
    """An uninspectable controlled locator cannot become an absent-input success."""
    owner, record_ids = issued_owner
    locator = owner.index_root / "issued" / f"{record_ids[0]}.json"
    original_lstat = Path.lstat
    original_stat = Path.stat

    def denied_for_locator(path, *args, **kwargs):
        if path == locator:
            raise PermissionError("synthetic locator inspection denial")
        return original_lstat(path, *args, **kwargs)

    def denied_stat_for_locator(path, *args, **kwargs):
        if path == locator:
            raise PermissionError("synthetic locator inspection denial")
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", denied_for_locator)
    monkeypatch.setattr(Path, "stat", denied_stat_for_locator)
    result = custody.PublicVerificationRecordPopulationProvider(
        source=_InventoryView(owner, record_ids), admission_source=owner, store=owner.store
    ).resolve()

    assert isinstance(result, custody.PublicSignaturePopulationNonReceipt)
    assert result.reason == "governed_public_inventory_unresolvable"
    owner_read = next(item for item in result.inventory_reads if item.boundary == "admission_owner")
    assert owner_read.outcome == "read_failed"
    assert any(
        item.operation == "issued_index.lstat"
        and item.selector == str(locator)
        and item.outcome == "invalid"
        for item in owner_read.input_reads
    )
    assert not any(
        item.selector == str(locator) and item.outcome == "absent"
        for item in owner_read.input_reads
    )


def _preserve_locator(locator: Path, tmp_path: Path) -> Path:
    """Move a fixture locator into an exclusive sibling directory without clobbering."""
    preserved_directory = tmp_path.parent / f"{tmp_path.name}-preserved-locators"
    preserved_directory.mkdir(exist_ok=False)
    preserved_locator = preserved_directory / locator.name
    locator.rename(preserved_locator)
    return preserved_locator

def test_absent_locator_is_reconciled_as_absent(issued_owner, tmp_path: Path):
    """A genuine missing locator remains recoverable through its owner transaction."""
    owner, record_ids = issued_owner
    locator = owner.index_root / "issued" / f"{record_ids[0]}.json"
    original_raw = locator.read_bytes()
    preserved_locator = _preserve_locator(locator, tmp_path)

    result = custody.PublicVerificationRecordPopulationProvider(
        source=_InventoryView(owner, record_ids), admission_source=owner, store=owner.store
    ).resolve()

    assert isinstance(result, custody.PersistedPublicSignaturePopulation)
    assert locator.is_file()
    assert preserved_locator.read_bytes() == original_raw
    owner_read = next(item for item in result.inventory_reads if item.boundary == "admission_owner")
    assert any(
        item.operation == "issued_index.lstat"
        and item.selector == str(locator)
        and item.outcome == "absent"
        for item in owner_read.input_reads
    )


def _resolve_with_locator_race(issued_owner, monkeypatch, tmp_path: Path, *, suffix: bytes):
    owner, record_ids = issued_owner
    raced_record_id = record_ids[0]
    locator = owner.index_root / "issued" / f"{raced_record_id}.json"
    expected_raw = locator.read_bytes()
    preserved_locator = _preserve_locator(locator, tmp_path)
    original_replay = owner._record_and_replay_public_read_closure
    races = []

    def replay_then_race(index):
        closure = original_replay(index)
        if index.record_id == raced_record_id:
            with locator.open("xb") as stream:
                stream.write(expected_raw + suffix)
            races.append(index.record_id)
        return closure

    monkeypatch.setattr(owner, "_record_and_replay_public_read_closure", replay_then_race)
    result = custody.PublicVerificationRecordPopulationProvider(
        source=_InventoryView(owner, record_ids), admission_source=owner, store=owner.store
    ).resolve()
    assert preserved_locator.read_bytes() == expected_raw
    return result, locator, races, preserved_locator


def test_locator_race_refuses_bytes_that_differ_from_owner_intent(
    issued_owner, monkeypatch, tmp_path: Path
):
    """A byte-different JSON encoding cannot replace the intended locator."""
    result, locator, races, preserved_locator = _resolve_with_locator_race(
        issued_owner, monkeypatch, tmp_path, suffix=b"\n"
    )

    assert races
    assert preserved_locator.is_file()
    assert isinstance(result, custody.PublicSignaturePopulationNonReceipt)
    assert result.reason == "governed_public_inventory_unresolvable"
    owner_read = next(item for item in result.inventory_reads if item.boundary == "admission_owner")
    assert owner_read.outcome == "read_failed"
    assert any(
        item.operation == "issued_index.read_bytes"
        and item.selector == str(locator)
        and item.outcome == "read"
        for item in owner_read.input_reads
    )


def test_locator_race_accepts_exact_owner_intent_bytes(issued_owner, monkeypatch, tmp_path: Path):
    """An atomic-publication race accepts the identical intended bytes."""
    result, locator, races, preserved_locator = _resolve_with_locator_race(
        issued_owner, monkeypatch, tmp_path, suffix=b""
    )

    assert races
    assert preserved_locator.is_file()
    assert isinstance(result, custody.PersistedPublicSignaturePopulation)
    owner_read = next(item for item in result.inventory_reads if item.boundary == "admission_owner")
    assert any(
        item.operation == "issued_index.read_bytes"
        and item.selector == str(locator)
        and item.outcome == "read"
        for item in owner_read.input_reads
    )
