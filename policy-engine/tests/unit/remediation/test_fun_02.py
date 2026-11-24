"""FUN-02 regression coverage for truthful multi-fidelity funnel results."""

from __future__ import annotations

from fractions import Fraction
from math import ulp
from sys import float_info
from typing import Any
from unittest.mock import MagicMock

import pytest

from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import (
    FunnelStage,
    FunnelStageResult,
    UncertaintyEnvelope,
)
from polisyos.scientist.methods.search.objective import GDPGrowthObjective
from polisyos.scientist.methods.search.stages import StageResult


def _stage(
    level: int,
    *,
    objective: float = 0.0,
    promising: bool = True,
    feedback: dict[str, Any] | None = None,
    terminal_action: str | None = None,
) -> MagicMock:
    stage = MagicMock(spec=FunnelStage)
    stage.fidelity_level = level
    stage.stage_name = f"L{level}"
    stage.estimated_cost_usd = 0.1
    source = {"gdp_change": objective, "metric_units": {"gdp_change": "fixture-unit"}}
    assessment = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(source).score_assessment
    assert assessment is not None
    stage.evaluate.return_value = FunnelStageResult(
        policy_candidate={"candidate_id": "fun-02"},
        objective_value=assessment.value,
        score_status=assessment.status,
        score_assessment=assessment,
        simulation_results=source,
        is_promising=promising,
        stage_name=f"L{level}",
        feedback=feedback or {},
        uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        fidelity_level=level,
        terminal_action=terminal_action,
    )
    return stage


def _full_stage_result(*, ci_width: object, effect: object = 2.0) -> StageResult:
    return StageResult(
        policy_candidate={"candidate_id": "fun-02"},
        objective_value=-1.0,
        is_promising=True,
        stage_name="expensive",
        simulation_results={
            "ate": effect,
            "bootstrap": {"ci_width": ci_width},
        },
        feedback={"verdict": "APPROVE"},
    )


def test_l3_overlays_only_owned_config_and_preserves_caller_references() -> None:
    dataset = object()
    model = object()
    cas = object()
    future_l4_config = {"bootstrap_draws": 500}
    context = {
        "data_config": {"subsample_fraction": 1.0, "dataset": dataset},
        "estimation_config": {"n_bootstrap": 500, "model": model},
        "scenario_config": {"grid": "full"},
        "subgroup_config": {"top_k": 99},
        "model_config": {"scm_complexity": "full", "model": model},
        "cas": cas,
        "future_l4_config": future_l4_config,
    }
    engine = MagicMock()
    engine.run.return_value = {
        "simulation_results": {},
        "feedback": {"verdict": "APPROVE"},
    }

    Level3MediumFidelity(
        workflow_engine=engine,
        subsample_fraction=0.2,
        bootstrap_draws=50,
    ).evaluate({"candidate_id": "fun-02"}, context)

    state = engine.run.call_args.args[0]
    assert context["data_config"] == {"subsample_fraction": 1.0, "dataset": dataset}
    assert context["estimation_config"] == {"n_bootstrap": 500, "model": model}
    assert context["model_config"] == {"scm_complexity": "full", "model": model}
    assert state["data_config"] is not context["data_config"]
    assert state["estimation_config"] is not context["estimation_config"]
    assert state["model_config"] is not context["model_config"]
    assert state["data_config"]["dataset"] is dataset
    assert state["estimation_config"]["model"] is model
    assert state["model_config"]["model"] is model
    assert state["cas"] is cas
    assert state["future_l4_config"] is future_l4_config


def test_empty_funnel_is_not_evaluated_and_never_looks_like_zero_approval() -> None:
    result = FunnelOrchestrator([]).evaluate({}, {})

    assert result.is_promising is False
    assert result.objective_value is None
    assert result.feedback["verdict"] == "NOT_EVALUATED"
    assert result.feedback["funnel_evaluation_status"] == "not_evaluated"


def test_cap_before_first_stage_is_not_evaluated() -> None:
    stage = _stage(4)
    output = FunnelOrchestrator([stage], max_level=2).as_stage_b_callable()({}, {})

    assert output["is_promising"] is False
    assert output["objective_value"] is None
    assert output["feedback"]["verdict"] == "NOT_EVALUATED"
    assert output["feedback"]["funnel_action"] == "defer"
    stage.evaluate.assert_not_called()


def test_executed_zero_objective_remains_a_valid_result() -> None:
    result = FunnelOrchestrator([_stage(0, objective=0.0)]).evaluate({}, {})

    assert result.objective_value == 0.0
    assert result.is_promising is True
    assert result.feedback["verdict"] == "APPROVE"


@pytest.mark.parametrize(
    ("ci_width", "expected_level", "expected_method"),
    [
        (None, 1.0, "ci_width_missing"),
        ("broken", 1.0, "ci_width_invalid"),
        (float("nan"), 1.0, "ci_width_invalid"),
        (float("inf"), 1.0, "ci_width_invalid"),
        (-0.1, 1.0, "ci_width_invalid"),
        (True, 1.0, "ci_width_invalid"),
        (0.0, 0.0, "full_fidelity_bootstrap"),
        (0.4, 0.1, "full_fidelity_bootstrap"),
    ],
)
def test_l4_ci_width_preserves_missing_invalid_and_true_zero_semantics(
    ci_width: object,
    expected_level: float,
    expected_method: str,
) -> None:
    expensive_stage = MagicMock()
    expensive_stage.evaluate.return_value = _full_stage_result(ci_width=ci_width)
    result = Level4FullFidelity(expensive_stage=expensive_stage).evaluate({}, {})
    estimate = result.uncertainty_envelope.uncertainties[
        next(
            uncertainty_type
            for uncertainty_type in result.uncertainty_envelope.uncertainties
            if uncertainty_type.value == "statistical"
        )
    ]

    assert estimate.level == pytest.approx(expected_level)
    assert estimate.quantification_method == expected_method
    if expected_method == "ci_width_missing":
        assert "confidence-interval width missing" in estimate.source
    elif expected_method == "ci_width_invalid":
        assert "confidence-interval width invalid" in estimate.source


def _fraction_ci_uncertainty_oracle(ci_width: float, effect: float) -> float:
    """Round the exact binary-float ratio independently of the implementation."""
    if effect == 0.0:
        return 0.0 if ci_width == 0.0 else 1.0
    exact_ratio = Fraction.from_float(ci_width) / (2 * Fraction.from_float(abs(effect)))
    return float(min(Fraction(1), exact_ratio))


def _l3_result(*, ci_width: object, effect: object) -> FunnelStageResult:
    engine = MagicMock()
    engine.run.return_value = {
        "simulation_results": {
            "ate": effect,
            "bootstrap": {"ci_width": ci_width},
            "gdp_change": 0.0,
            "metric_units": {"gdp_change": "fixture-unit"},
        },
        "feedback": {"verdict": "APPROVE"},
    }
    return Level3MediumFidelity(
        workflow_engine=engine,
        expected_objective_unit="fixture-unit",
    ).evaluate({"candidate_id": "fun-02"}, {})


@pytest.mark.parametrize(
    ("ci_width", "effect"),
    [
        (1.0e308, 1.0e308),
        (float_info.max, float_info.max),
        (float.fromhex("0x0.0000000000001p-1022"), float.fromhex("0x0.0000000000001p-1022")),
        (0.4, 2.0),
        (float_info.max, float_info.max / 2.0),
        (float.fromhex("0x0.0000000000001p-1022"), float_info.max),
        (0.0, 2.0),
        (0.0, 0.0),
        (1.0, 0.0),
        (0.4, -2.0),
    ],
)
@pytest.mark.parametrize("fidelity", ["L3", "L4"])
def test_ci_width_ratio_matches_exact_rational_oracle_across_float_scales(
    ci_width: float,
    effect: float,
    fidelity: str,
) -> None:
    if fidelity == "L3":
        result = _l3_result(ci_width=ci_width, effect=effect)
        method = "bootstrap_reduced"
    else:
        expensive_stage = MagicMock()
        expensive_stage.evaluate.return_value = _full_stage_result(
            ci_width=ci_width,
            effect=effect,
        )
        result = Level4FullFidelity(expensive_stage=expensive_stage).evaluate({}, {})
        method = "full_fidelity_bootstrap"

    estimate = result.uncertainty_envelope.uncertainties[
        next(
            uncertainty_type
            for uncertainty_type in result.uncertainty_envelope.uncertainties
            if uncertainty_type.value == "statistical"
        )
    ]
    expected = _fraction_ci_uncertainty_oracle(ci_width, effect)

    assert abs(estimate.level - expected) <= ulp(expected)
    assert estimate.quantification_method == method


@pytest.mark.parametrize("fidelity", ["L3", "L4"])
@pytest.mark.parametrize(
    ("ci_width", "effect", "expected_method", "expected_reason"),
    [
        (10**400, 2.0, "ci_width_invalid", "confidence-interval width invalid"),
        (1.0, 10**400, "effect_invalid", "effect scale invalid"),
        (1.0, float("nan"), "effect_invalid", "effect scale invalid"),
        (1.0, True, "effect_invalid", "effect scale invalid"),
    ],
)
def test_ci_width_ratio_keeps_typed_invalid_boundaries(
    ci_width: object,
    effect: object,
    expected_method: str,
    expected_reason: str,
    fidelity: str,
) -> None:
    if fidelity == "L3":
        result = _l3_result(ci_width=ci_width, effect=effect)
    else:
        expensive_stage = MagicMock()
        expensive_stage.evaluate.return_value = _full_stage_result(
            ci_width=ci_width,
            effect=effect,
        )
        result = Level4FullFidelity(expensive_stage=expensive_stage).evaluate({}, {})
    estimate = result.uncertainty_envelope.uncertainties[
        next(
            uncertainty_type
            for uncertainty_type in result.uncertainty_envelope.uncertainties
            if uncertainty_type.value == "statistical"
        )
    ]

    assert estimate.level == 1.0
    assert estimate.quantification_method == expected_method
    assert expected_reason in estimate.source


def test_final_defer_overrides_intermediate_approve_without_erasing_stage_result() -> None:
    stage = _stage(
        0,
        feedback={"verdict": "APPROVE"},
        terminal_action="defer",
    )
    output = FunnelOrchestrator([stage]).as_stage_b_callable()({}, {})

    assert output["feedback"]["stage_verdict"] == "APPROVE"
    assert output["feedback"]["verdict"] == "DEFER"
    assert output["feedback"]["funnel_action"] == "defer"
    assert output["is_promising"] is False
    assert output["_funnel_result"].is_promising is True


def test_final_reject_overrides_intermediate_approve() -> None:
    stage = _stage(
        0,
        feedback={"verdict": "APPROVE"},
        terminal_action="reject",
    )
    result = FunnelOrchestrator([stage]).evaluate({}, {})

    assert result.feedback["stage_verdict"] == "APPROVE"
    assert result.feedback["verdict"] == "REJECT"
    assert result.is_promising is False
