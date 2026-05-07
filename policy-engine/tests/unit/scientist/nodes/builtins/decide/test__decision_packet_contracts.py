from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from polisyos.scientist.nodes.builtins.decide import build_decision_packet as runtime
from polisyos.scientist.nodes.builtins.decide._decision_packet_contracts import (
    ClaimLedgerAttachment,
    _ClaimLedgerAttachment,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CLAIMS_REF


def test_decision_packet_contracts_are_reexported_from_runtime_module() -> None:
    assert runtime._ClaimLedgerAttachment is _ClaimLedgerAttachment
    assert _ClaimLedgerAttachment is ClaimLedgerAttachment


def test_claim_ledger_attachment_write_paths_and_state_update_are_characterized() -> None:
    claims_ref = cast("Any", object())
    attachment = ClaimLedgerAttachment(claims_ref=claims_ref)
    state = SimpleNamespace(artifacts_index={})

    assert attachment.artifacts == [claims_ref]
    assert attachment.write_paths == (f"artifacts_index.{ARTIFACT_CLAIMS_REF}",)

    attachment.apply_to_state(cast("Any", state))
    assert state.artifacts_index == {ARTIFACT_CLAIMS_REF: claims_ref}
