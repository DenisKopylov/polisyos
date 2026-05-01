from __future__ import annotations

import hashlib

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.claims.validators import legacy_claim_ledger_status
from polisyos.scientist.orchestrator.decision_card import DecisionCard, Verdict
from polisyos.scientist.research_dag.replay import legacy_research_dag_status
from tools.ci.check_scientist_best_in_class_phase2_0 import (
    ARTIFACT_SCHEMA_VERSION_BASELINES,
    LEGACY_PUBLIC_PACKET_FIELDS,
    WAVE2_ADDITIVE_PACKET_FIELDS,
    WAVE2_FEATURE_FLAG_DEFAULTS,
    validate_additive_packet_fields,
    validate_adr_compatibility_text,
    validate_schema_versions,
    validate_wave2_flag_defaults,
)


def test_legacy_decision_packet_without_wave2_fields_loads_as_legacy_missing() -> None:
    packet = {
        "schema_version": "3.4",
        "run_id": "legacy_packet",
        "generated_at": "2026-04-28T00:00:00+00:00",
        "policy_ir": {"policy_spec": {"interventions": [{"kind": "tax"}]}},
        "simulation_results": {"jobs_delta": 12.0},
        "governance": {"verdict": "APPROVE", "issues": []},
        "artifacts": {},
    }

    card = DecisionCard.from_packet(packet)

    assert card.run_id == "legacy_packet"
    assert card.verdict is Verdict.APPROVE
    assert legacy_claim_ledger_status(packet.get("claims_ref")) == "legacy_missing"
    assert legacy_research_dag_status(packet.get("research_dag_ref")) == "legacy_missing"


def test_wave2_packet_contract_is_additive_over_legacy_public_fields() -> None:
    removed = validate_additive_packet_fields(set(WAVE2_ADDITIVE_PACKET_FIELDS))

    assert removed == []
    assert LEGACY_PUBLIC_PACKET_FIELDS <= WAVE2_ADDITIVE_PACKET_FIELDS


def test_removed_legacy_public_field_fails_compatibility_check() -> None:
    proposed = set(WAVE2_ADDITIVE_PACKET_FIELDS)
    proposed.remove("run_id")

    removed = validate_additive_packet_fields(proposed)

    assert removed == ["run_id"]


def test_proposed_adr_removing_public_field_fails_compatibility_check() -> None:
    proposed_adr = """
# ADR-9999: Unsafe Packet Migration

## Status

Proposed

## Compatibility

This migration is additive, but it will remove legacy public field `run_id`.

## Rollout

Ship immediately.

## Rollback

Restore old packets.
"""

    assert validate_adr_compatibility_text(proposed_adr) == [
        "adr_removes_legacy_public_field:proposed_adr:run_id"
    ]


def test_wave2_feature_flags_are_not_production_on_by_default() -> None:
    assert validate_wave2_flag_defaults(WAVE2_FEATURE_FLAG_DEFAULTS) == []

    unsafe = dict(WAVE2_FEATURE_FLAG_DEFAULTS)
    unsafe["scientist.best_in_class.wave2.phase2_3.voi_scheduler"] = "production_on"

    assert validate_wave2_flag_defaults(unsafe) == [
        "wave2_flag_default_not_safe:"
        "scientist.best_in_class.wave2.phase2_3.voi_scheduler:production_on"
    ]


def test_artifact_schema_version_regression_is_rejected() -> None:
    assert validate_schema_versions(dict(ARTIFACT_SCHEMA_VERSION_BASELINES)) == []

    regressed = dict(ARTIFACT_SCHEMA_VERSION_BASELINES)
    regressed["ClaimLedger"] = "0.9"

    assert validate_schema_versions(regressed) == [
        "schema_version_regression:ClaimLedger:0.9<1.0"
    ]


def test_wave2_refs_remain_artifact_refs_not_free_form_strings() -> None:
    artifact_id = ArtifactID.model_validate(
        "sha256:" + hashlib.sha256(b"wave2_ref").hexdigest()
    )
    ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="scientist.wave2.runtime_contract_fixture",
        media_type="application/json",
    )

    assert str(ref.artifact_id).startswith("sha256:")
    assert ref.kind == "scientist.wave2.runtime_contract_fixture"
