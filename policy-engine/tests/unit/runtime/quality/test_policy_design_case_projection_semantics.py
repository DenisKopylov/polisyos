from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime

import pytest

from polisyos.runtime.quality.projection_semantics import (
    PolicyDesignCaseProjectionError,
    assert_policy_design_projection_not_authority,
    build_policy_design_case_projection_semantics,
)
from tests._helpers.policy_design_case_projection import policy_design_case, sha


def test_projection_semantics_labels_publishable_without_minting_authority() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="final_artifact",
        source_payload={
            "artifact_kind": "publishable_decision_artifact",
            "publishability": "publishable",
            "decision_context": {"public_export_status": "publishable"},
            "authority_role": "final_decision_artifact",
        },
        source_ref=sha("9"),
        generated_at=datetime(2026, 5, 18, 9, 0, tzinfo=UTC),
    )

    assert projection["primary_state"] == "publishable"
    assert projection["authority_role"] == "projection_only"
    assert projection["projection_policy"] == "reads_policy_design_case_only"
    assert projection["source_authority_refs"]["policy_design_case_ref"] == sha("a")
    assert "publishable" in projection["states"]
    assert "projection_only" in projection["states"]
    assert {label["state"]: label["authority_role"] for label in projection["labels"]}[
        "publishable"
    ] == "projection_only"
    assert "scorecard_authority" in projection["may_not_be_used_for"]

    assert_policy_design_projection_not_authority(projection)


def test_projection_semantics_labels_public_exports_as_redacted_projection() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="public_export",
        source_payload={
            "public_export_classification": "public_redacted_projection",
            "evidence_class": "redacted_derived",
            "decision_context": {"public_export_status": "publishable"},
        },
        source_ref=sha("8"),
    )

    assert projection["primary_state"] == "redacted"
    assert projection["authority_role"] == "projection_only"
    assert projection["redacted"] is True
    assert {"redacted", "publishable", "projection_only"} <= set(projection["states"])
    assert "tenant-sensitive" not in str(projection)


def test_projection_semantics_rejects_projection_that_mints_claim_authority() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="dashboard",
        source_payload={"decision_context": {"public_export_status": "publishable"}},
    )
    projection["authority_role"] = "producer_authority"

    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="policy_design_projection_mints_authority",
    ):
        assert_policy_design_projection_not_authority(projection)


def test_projection_semantics_rejects_authority_bearing_projection_source() -> None:
    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="policy_design_projection_source_mints_authority",
    ):
        build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case(),
            surface="api_projection",
            source_payload={
                "authority_role": "producer_authority",
                "decision_context": {"public_export_status": "publishable"},
            },
        )
