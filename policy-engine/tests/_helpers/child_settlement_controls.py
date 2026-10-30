"""Adversarial real-owner controls for a completed child settlement journal."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts._atomic_write import AtomicFileWriter
from polisyos.core.artifacts.child_release import (
    ChildReleaseUnavailableError,
    _head_path,
    resolve_recorded_child_settlement,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.child_release import ChildJobReleaseLocator, ChildJobSessionClaim
    from polisyos.core.artifacts.store import FileSystemCAS


def assert_recorded_settlement_controls(
    served: FileSystemCAS,
    owner: object,
    intent_locator: ChildJobReleaseLocator,
    intent: ChildJobSessionClaim,
    monkeypatch: pytest.MonkeyPatch,
    expected_owner_error: type[Exception],
) -> None:
    """Use actual release/DB state; corrupt and restore only its test-owned journal."""
    receipt = resolve_recorded_child_settlement(
        served, intent_locator=intent_locator, expected_intent=intent
    )
    assert receipt.classification == "settlement_journal_recorded"
    path = _head_path(served.root, intent.release_id).with_name(
        intent.release_id + ".settlement.json"
    )
    original = path.read_bytes()
    assert receipt.journal_sha256 == "sha256:" + hashlib.sha256(original).hexdigest()
    value = json.loads(original)
    try:
        for field, bad_value in (("status", "pending"), ("total", value["total"] + 1)):
            altered = dict(value)
            altered[field] = bad_value
            AtomicFileWriter.write_atomic(path, json.dumps(altered).encode(), durable_parent=True)
            with pytest.raises(
                ChildReleaseUnavailableError, match="settlement_journal_not_settled"
            ):
                resolve_recorded_child_settlement(
                    served, intent_locator=intent_locator, expected_intent=intent
                )
        duplicate = original.rstrip()[:-1] + b', "status": "settled"}'
        AtomicFileWriter.write_atomic(path, duplicate, durable_parent=True)
        with pytest.raises(ChildReleaseUnavailableError, match="settlement_journal_unavailable"):
            resolve_recorded_child_settlement(
                served, intent_locator=intent_locator, expected_intent=intent
            )
    finally:
        AtomicFileWriter.write_atomic(path, original, durable_parent=True)
    forged = intent_locator.model_copy(update={"event_id": 2**62})
    with pytest.raises(
        ChildReleaseUnavailableError, match="settlement_intent_unavailable"
    ) as failed:
        resolve_recorded_child_settlement(served, intent_locator=forged, expected_intent=intent)
    assert type(failed.value.__cause__) is expected_owner_error
    # Removal control: bypass only the real intent owner, keeping every byte and
    # selected release/record unchanged; the same forged locator now passes.
    with monkeypatch.context() as patch:
        patch.setattr(type(owner), "verify_intent", lambda self, locator, claim: None)
        assert (
            resolve_recorded_child_settlement(
                served, intent_locator=forged, expected_intent=intent
            ).classification
            == "settlement_journal_recorded"
        )
