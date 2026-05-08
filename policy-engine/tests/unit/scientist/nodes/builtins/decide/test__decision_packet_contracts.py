from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from polisyos.scientist.nodes.builtins.decide import build_decision_packet as runtime
from polisyos.scientist.nodes.builtins.decide._decision_packet_contracts import (
    ClaimLedgerAttachment,
    _ClaimLedgerAttachment,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet import api, builder
from polisyos.scientist.nodes.builtins.decide.decision_packet import (
    enrichment,
    serialization,
    validation,
)
from polisyos.scientist.nodes.builtins.state_keys import ARTIFACT_CLAIMS_REF


def test_decision_packet_contracts_are_reexported_from_runtime_module() -> None:
    assert runtime._ClaimLedgerAttachment is _ClaimLedgerAttachment
    assert _ClaimLedgerAttachment is ClaimLedgerAttachment


def test_decision_packet_split_modules_preserve_legacy_api_aliases() -> None:
    assert runtime.BuildDecisionPacketNode is api.BuildDecisionPacketNode
    assert api.BuildDecisionPacketNode is builder.BuildDecisionPacketNode
    assert runtime._build_policy_summary is enrichment._build_policy_summary
    assert runtime._build_manifest_inputs is serialization._build_manifest_inputs
    assert runtime._decision_packet_degraded is validation._decision_packet_degraded


def test_decision_packet_split_modules_own_moved_helpers() -> None:
    assert enrichment._build_policy_summary.__module__ == enrichment.__name__
    assert serialization._build_manifest_inputs.__module__ == serialization.__name__
    assert validation._decision_packet_degraded.__module__ == validation.__name__


def test_claim_ledger_attachment_write_paths_and_state_update_are_characterized() -> None:
    claims_ref = cast("Any", object())
    attachment = ClaimLedgerAttachment(claims_ref=claims_ref)
    state = SimpleNamespace(artifacts_index={})

    assert attachment.artifacts == [claims_ref]
    assert attachment.write_paths == (f"artifacts_index.{ARTIFACT_CLAIMS_REF}",)

    attachment.apply_to_state(cast("Any", state))
    assert state.artifacts_index == {ARTIFACT_CLAIMS_REF: claims_ref}
