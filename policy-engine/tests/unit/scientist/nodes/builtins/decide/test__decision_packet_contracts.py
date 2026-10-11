from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, cast

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
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
from polisyos.scientist.orchestration.engine.state import ExperimentState


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


def test_manifest_input_builder_preserves_full_source_profiles_across_the_packet() -> None:
    artifact_id = "sha256:" + "a" * 64
    selected_a = ArtifactRef(
        artifact_id=artifact_id,
        kind="fabric.data_snapshot",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "1" * 64,
    )
    selected_b = selected_a.model_copy(update={"manifest_profile_sha256": "sha256:" + "2" * 64})
    legacy = ArtifactRef(
        artifact_id="sha256:" + "b" * 64,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )
    state = ExperimentState(
        run_id="R_packet_lineage_profiles",
        inputs={"selected_a": selected_a, "selected_b": selected_b, "legacy": legacy},
    )
    payload = {
        "inputs": {
            "selected_a": artifact_id,
            "selected_b": artifact_id,
            "legacy": str(legacy.artifact_id),
        },
        "uncertainty": {
            "source_ref": selected_a.model_dump(mode="json"),
        },
    }

    edges = serialization._build_manifest_inputs(payload, source_state=state)
    by_role = {edge.role: edge for edge in edges}

    assert by_role["input.selected_a"].manifest_profile_sha256 == selected_a.manifest_profile_sha256
    assert by_role["input.selected_b"].manifest_profile_sha256 == selected_b.manifest_profile_sha256
    assert by_role["input.legacy"].manifest_profile_sha256 is None
    assert (
        by_role["uncertainty.source_ref"].manifest_profile_sha256
        == selected_a.manifest_profile_sha256
    )

    ambiguous_payload = {"uncertainty": {"nested_source": artifact_id}}
    with pytest.raises(ValueError, match="decision_packet_manifest_input_profile_ambiguous"):
        serialization._build_manifest_inputs(ambiguous_payload, source_state=state)
