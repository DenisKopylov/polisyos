from __future__ import annotations

from polisyos.core.governance.passes.base import IssueSeverity
from polisyos.scientist.governance.passes.fabric_trust_gate_pass import FabricTrustGatePass


def test_fabric_trust_gate_caps_missing_lineage_and_unknown_quality(
    pass_context_factory,
    strict_profile,
) -> None:
    ctx = pass_context_factory(
        profile=strict_profile,
        state={
            "fabric_decision_data": [
                {
                    "id": "fabric_decision_data:policy_cost",
                    "quality": {
                        "status": "unknown_quality",
                        "quality_surface": "policy_cost",
                        "remediation_link": "policyos://quality/policy_cost",
                    },
                    "lineage": {
                        "id": "untraced",
                        "status": "untraced",
                        "reason_code": "fixture_missing_lineage",
                    },
                    "access": {"classification": "public"},
                }
            ]
        },
    )

    issues = FabricTrustGatePass(force_run=True).validate(ctx)

    codes = {issue.code for issue in issues}
    assert {"FABRIC_QUALITY_UNKNOWN", "FABRIC_LINEAGE_MISSING"} <= codes
    assert all(issue.severity is IssueSeverity.BLOCKER for issue in issues)
    assert ctx.state["fabric_readiness_cap"] == {
        "level": "research_artifact",
        "reason": "FABRIC_QUALITY_UNKNOWN",
    }


def test_fabric_trust_gate_caps_low_source_trust_scorecard(
    pass_context_factory,
    strict_profile,
) -> None:
    ctx = pass_context_factory(
        profile=strict_profile,
        state={
            "fabric_source_scorecards": {
                "scorecards": {
                    "demo.low_trust": {
                        "grade": "D",
                        "status": "breached",
                        "metrics": [
                            {
                                "name": "source_trust",
                                "score": 0.25,
                                "reason": "source_trust=low",
                            }
                        ],
                    }
                }
            }
        },
    )

    issues = FabricTrustGatePass(force_run=True).validate(ctx)

    assert [issue.code for issue in issues] == ["FABRIC_SOURCE_TRUST_LOW"]
    assert ctx.state["fabric_readiness_cap"]["level"] == "research_artifact"
