from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.judge_stack import (
    JudgeInputBundle,
    JudgeStack,
    SingleJudgeVerdict,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    _optional_runtime_number,
    _policy_runtime_numeric_inputs,
)
from polisyos.scientist.nodes.builtins.decide.run_policy_promotion import (
    _policy_runtime_numeric_inputs as _promotion_numeric_inputs,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def _candidate() -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(problem_id="numeric_probe", domain=ProblemDomain.FISCAL),
            policy_spec=PolicySpec(policy_id="numeric_probe"),
            model_spec=ModelSpec(
                model_id="numeric_probe",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id="numeric_probe",
    )


def _compute_verdict(state: ExperimentState) -> SingleJudgeVerdict:
    numbers = _promotion_numeric_inputs(state)
    bundle = JudgeInputBundle.model_construct(
        candidate=_candidate(),
        compute_cost_usd=numbers.compute_cost_usd,
        replay_cost_usd=numbers.replay_cost_usd,
        timeout_risk=numbers.timeout_risk,
    )
    return JudgeStack()._compute(bundle)


def test_promotion_numeric_inputs_preserve_missing_as_unknown_and_explicit_zero() -> None:
    absent_state = ExperimentState(run_id="numeric-absent", params={})
    absent_numbers = _promotion_numeric_inputs(absent_state)
    absent_verdict = _compute_verdict(absent_state)

    assert absent_numbers.compute_cost_usd is None
    assert absent_numbers.replay_cost_usd is None
    assert absent_numbers.timeout_risk is None
    assert "missing_compute_inputs" in {card.failure_type for card in absent_verdict.warnings}
    assert absent_verdict.metrics == {}

    zero_state = ExperimentState(
        run_id="numeric-zero",
        params={
            "estimated_compute_cost_usd": 0.0,
            "estimated_replay_cost_usd": 0.0,
            "timeout_risk": 0.0,
        },
    )
    zero_verdict = _compute_verdict(zero_state)

    assert not zero_verdict.warnings
    assert zero_verdict.metrics["timeout_risk"] == 0.0
    assert zero_verdict.metrics["replay_cost_ratio"] == 0.0


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (key, value)
        for key in (
            "estimated_compute_cost_usd",
            "estimated_replay_cost_usd",
            "timeout_risk",
        )
        for value in ("", [], {}, float("nan"), float("inf"), float("-inf"))
    ],
)
def test_promotion_numeric_inputs_reject_present_malformed_values(key: str, value: Any) -> None:
    state = ExperimentState.model_construct(run_id="numeric-malformed", params={key: value})

    with pytest.raises((TypeError, ValueError)):
        _policy_runtime_numeric_inputs(state)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(Decimal("0.5"), 0.5), ("0.25", 0.25), (b"0.125", 0.125), (0.0, 0.0)],
)
def test_optional_numeric_parser_keeps_supported_finite_float_inputs(
    value: Any,
    expected: float,
) -> None:
    assert _optional_runtime_number(value) == expected
