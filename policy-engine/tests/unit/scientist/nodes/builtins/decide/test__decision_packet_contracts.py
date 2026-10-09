from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, cast

from polisyos.scientist.nodes.builtins.decide import build_decision_packet as runtime
from polisyos.scientist.nodes.builtins.decide._decision_packet_contracts import (
    ClaimLedgerAttachment,
    _ClaimLedgerAttachment,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet import (
    api,
    builder,
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


def test_decision_validity_preparation_is_owned_by_validation() -> None:
    prepare = validation.__prepare_decision_validity__

    assert prepare.__module__ == validation.__name__
    assert builder.__prepare_decision_validity__ is prepare
    assert not hasattr(validation, "_prepare_decision_validity")


def test_decision_packet_section_owners_preserve_legacy_aliases() -> None:
    package = builder.__package__
    moved_helpers = (
        ("causal_sections", "_build_causal_section"),
        ("strategic_sections", "_build_strategic_section"),
        ("outcome_sections", "_build_distributional_section"),
        ("basis_sections", "_build_normative_basis"),
        ("uncertainty_sections", "_build_uncertainty_bounds"),
    )

    for owner_name, name in moved_helpers:
        owner_path = f"{package}.{owner_name}"
        assert importlib.util.find_spec(owner_path) is not None, owner_path
        owner = importlib.import_module(owner_path)
        implementation = getattr(owner, name)
        assert implementation.__module__ == owner.__name__
        assert getattr(enrichment, name) is implementation
        assert getattr(api, name) is implementation
        assert getattr(runtime, name) is implementation


def test_claim_ledger_attachment_write_paths_and_state_update_are_characterized() -> None:
    claims_ref = cast("Any", object())
    attachment = ClaimLedgerAttachment(
        claims_ref=claims_ref,
        authority_status="current",
    )
    state = SimpleNamespace(artifacts_index={})

    assert attachment.artifacts == [claims_ref]
    assert attachment.write_paths == (f"artifacts_index.{ARTIFACT_CLAIMS_REF}",)

    attachment.apply_to_state(cast("Any", state))
    assert state.artifacts_index == {ARTIFACT_CLAIMS_REF: claims_ref}
