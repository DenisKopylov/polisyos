from __future__ import annotations

from polisyos.core.contracts.lex import IssueSeverity
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.foundry.methods.catalog.survey.protocols import SAEResult
from polisyos.scientist.governance.passes.causal_frontier_leakage_pass import (
    CausalFrontierLeakagePass,
)


def _diagnostics(blr: float) -> dict[str, float | int | str]:
    return {
        "blr": blr,
        "pli": 0.4,
        "variance_inflation_ratio": 1.2,
        "singletons_after_cut": 1,
        "tau_unrestricted": 0.2,
        "tau_constrained": 0.5,
        "alert_level": "red" if blr >= 0.15 else "amber",
    }


def test_causal_frontier_leakage_pass_ignores_missing_diagnostics() -> None:
    ctx = PassContext(
        ir=None,
        state={},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_frontier_missing",
    )

    assert CausalFrontierLeakagePass().validate(ctx) == []


def test_causal_frontier_leakage_pass_warns_in_mvp() -> None:
    ctx = PassContext(
        ir=None,
        state={"causal_frontier_diagnostics": _diagnostics(0.08)},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_frontier_warn",
    )

    issues = CausalFrontierLeakagePass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "CAUSAL_FRONTIER_BOUNDARY_LEAKAGE"
    assert issues[0].severity == IssueSeverity.WARNING


def test_causal_frontier_leakage_pass_blocks_in_strict() -> None:
    result = SAEResult(
        method_name="survey.estimation.causal_frontier_fay_herriot",
        statistics={"diagnostics": _diagnostics(0.22)},
    )
    ctx = PassContext(
        ir=None,
        state={"sae_result": result},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_frontier_block",
    )

    issues = CausalFrontierLeakagePass().validate(ctx)

    assert len(issues) == 1
    assert issues[0].code == "CAUSAL_FRONTIER_BOUNDARY_LEAKAGE"
    assert issues[0].severity == IssueSeverity.BLOCKER
