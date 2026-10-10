from __future__ import annotations

# ruff: noqa: S101
from polisyos.runtime.quality.projection_semantics import (
    build_policy_design_case_projection_semantics,
)
from tests._helpers.policy_design_case_projection import policy_design_case


def test_contested_source_state_blocks_a_publishable_projection_label() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="public_export",
        source_payload={
            "artifact_kind": "final_decision_artifact",
            "authority_role": "final_decision_artifact",
            "status": "contested",
            "publishability": "publishable",
        },
    )

    assert "contested" in projection["states"]
    assert "publishable" not in projection["states"]
    assert projection["primary_state"] == "contested"
    assert projection["authority_role"] == "projection_only"
    assert projection["authoritative_for"] == []
