from __future__ import annotations

from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.scientist.governance.passes.strategic_response_pass import StrategicResponsePass


def test_strategic_response_pass_blocks_blocked_fallback() -> None:
    issues = StrategicResponsePass().validate(
        PassContext(
            ir=None,
            state={
                "strategic_response": {
                    "fallback_mode": "blocked",
                    "equilibrium_selection_dependence": "runtime_precondition_blocked",
                    "blocked_reason": "missing_payoff_table",
                },
                "strategic_response_required": True,
            },
            registry_bundle=None,
            profile=ValidationProfile.mvp(),
            run_id="run_strategic",
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "STRATEGIC_RESPONSE_BLOCKED"


def test_strategic_response_pass_warns_on_bounds_fallback() -> None:
    issues = StrategicResponsePass().validate(
        PassContext(
            ir=None,
            state={
                "strategic_response": {
                    "fallback_mode": "strategic_bounds",
                    "equilibrium_selection_dependence": "deterministic",
                    "multiplicity_note": None,
                }
            },
            registry_bundle=None,
            profile=ValidationProfile.mvp(),
            run_id="run_strategic",
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "STRATEGIC_RESPONSE_APPROXIMATE"


def test_strategic_response_pass_requests_human_review_for_multiplicity_in_strict_mode() -> None:
    ctx = PassContext(
        ir=None,
        state={
            "strategic_response": {
                "fallback_mode": "exact_equilibrium",
                "equilibrium_selection_dependence": "tie_break_sensitive",
                "multiplicity_note": "Two equilibria remain plausible.",
            }
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="run_strategic",
    )

    issues = StrategicResponsePass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "HUMAN_REVIEW_REQUESTED"
    assert ctx.state["human_review_request"]["items"][0]["kind"] == "strategic_response_multiplicity"
