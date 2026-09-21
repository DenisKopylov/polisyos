"""FUN-02 regression coverage for truthful multi-fidelity funnel results."""

from __future__ import annotations

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
    stage.evaluate.return_value = FunnelStageResult(
        policy_candidate={"candidate_id": "fun-02"},
        objective_value=objective,
        is_promising=promising,
        stage_name=f"L{level}",
        feedback=feedback or {},
        uncertainty_envelope=UncertaintyEnvelope.deterministic(),
        fidelity_level=level,
        terminal_action=terminal_action,
    )
    return stage


def _full_stage_result(*, ci_width: object) -> StageResult:
    return StageResult(
        policy_candidate={"candidate_id": "fun-02"},
        objective_value=-1.0,
        is_promising=True,
        stage_name="expensive",
        simulation_results={
            "ate": 2.0,
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
    assert result.objective_value == float("inf")
    assert result.feedback["verdict"] == "NOT_EVALUATED"
    assert result.feedback["funnel_evaluation_status"] == "not_evaluated"


def test_cap_before_first_stage_is_not_evaluated() -> None:
    stage = _stage(4)
    output = FunnelOrchestrator([stage], max_level=2).as_stage_b_callable()({}, {})

    assert output["is_promising"] is False
    assert output["objective_value"] == float("inf")
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
