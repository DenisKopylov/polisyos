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


def test_strategic_response_pass_blocks_when_decomposition_is_blocked() -> None:
    issues = StrategicResponsePass().validate(
        PassContext(
            ir=None,
            state={
                "strategic_response": {
                    "fallback_mode": "exact_equilibrium",
                    "equilibrium_selection_dependence": "deterministic",
                    "multiplicity_note": None,
                    "decomposition_status": "blocked",
                    "decomposition_failure_code": "decomposition_cross_world_anchor_undefined",
                }
            },
            registry_bundle=None,
            profile=ValidationProfile.mvp(),
            run_id="run_strategic_decomposition_blocked",
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "STRATEGIC_DECOMPOSITION_BLOCKED"


def test_strategic_response_pass_warns_when_decomposition_is_bounded() -> None:
    issues = StrategicResponsePass().validate(
        PassContext(
            ir=None,
            state={
                "strategic_response": {
                    "fallback_mode": "exact_equilibrium",
                    "equilibrium_selection_dependence": "tie_break_sensitive",
                    "multiplicity_note": "Two equilibria induce different strategic shifts.",
                    "decomposition_status": "bounded",
                }
            },
            registry_bundle=None,
            profile=ValidationProfile.mvp(),
            run_id="run_strategic_decomposition_bounded",
        )
    )

    assert len(issues) == 2
    assert {issue.code for issue in issues} == {
        "STRATEGIC_DECOMPOSITION_BOUNDED",
        "STRATEGIC_RESPONSE_MULTIPLICITY",
    }


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


def test_strategic_response_pass_requests_human_review_for_mfg_selection() -> None:
    ctx = PassContext(
        ir=None,
        state={
            "strategic_response": {
                "fallback_mode": "exact_equilibrium",
                "equilibrium_selection_dependence": "deterministic",
                "multiplicity_note": None,
                "decomposition_status": "exact",
                "mfg_uniqueness_status": "local_stable_branch",
                "mfg_selection_rule": "stable_branch",
            }
        },
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="run_strategic_mfg",
    )

    issues = StrategicResponsePass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "HUMAN_REVIEW_REQUESTED"
    assert (
        ctx.state["human_review_request"]["items"][0]["kind"]
        == "strategic_response_mfg_equilibrium_selection"
    )


def test_strategic_response_pass_warns_when_mfg_numerics_provenance_is_missing() -> None:
    issues = StrategicResponsePass().validate(
        PassContext(
            ir=None,
            state={
                "strategic_response": {
                    "fallback_mode": "exact_equilibrium",
                    "equilibrium_selection_dependence": "deterministic",
                    "multiplicity_note": None,
                    "decomposition_status": "exact",
                    "mfg_uniqueness_status": "unique",
                    "mfg_selection_rule": "none",
                    "mfg_has_numerics_provenance": False,
                    "mfg_has_solver_residual": False,
                    "mfg_has_mass_conservation": False,
                }
            },
            registry_bundle=None,
            profile=ValidationProfile.mvp(),
            run_id="run_strategic_mfg_missing_provenance",
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "STRATEGIC_MFG_NUMERICS_PROVENANCE_MISSING"


def test_strategic_response_pass_requests_human_review_for_uncertified_iterated_loop() -> None:
    ctx = PassContext(
        ir=None,
        state={
            "strategic_response": {
                "fallback_mode": "exact_equilibrium",
                "equilibrium_selection_dependence": "deterministic",
                "multiplicity_note": None,
                "performative_loop": {
                    "analysis_scope": "iterated_loop",
                    "proof_family": "stateful_lipschitz",
                    "stability_status": "uncertified",
                    "reason_code": "global_contraction_failed",
                    "recommended_action": "single_shot_only",
                    "human_summary": "Global contraction could not be certified for unattended retraining.",
                },
            }
        },
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="run_strategic",
    )

    issues = StrategicResponsePass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "HUMAN_REVIEW_REQUESTED"
    assert ctx.state["human_review_request"]["items"][0]["kind"] == "strategic_performative_loop"


def test_strategic_response_pass_blocks_certified_unstable_iterated_loop() -> None:
    issues = StrategicResponsePass().validate(
        PassContext(
            ir=None,
            state={
                "strategic_response": {
                    "fallback_mode": "exact_equilibrium",
                    "equilibrium_selection_dependence": "deterministic",
                    "performative_loop": {
                        "analysis_scope": "iterated_loop",
                        "proof_family": "stateful_lipschitz",
                        "stability_status": "certified_unstable",
                        "reason_code": "local_spectral_radius_gt_one",
                        "recommended_action": "block_auto_iteration",
                        "human_summary": "Closed-loop Jacobian exceeds unit spectral radius.",
                    },
                }
            },
            registry_bundle=None,
            profile=ValidationProfile.mvp(),
            run_id="run_strategic",
        )
    )

    assert len(issues) == 1
    assert issues[0].code == "PERFORMATIVE_LOOP_UNSTABLE"
