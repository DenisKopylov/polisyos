"""Malformed direction must refuse before sampling or evaluator work."""

from __future__ import annotations

import pytest

from polisyos.scientist.methods.search.adversarial import (
    StressObjectiveDirectionError,
    run_stress_test,
)


@pytest.mark.parametrize("direction", [None, "maximize", "minimize", "unknown", True, 1])
def test_invalid_typed_direction_refuses_before_sampling_or_evaluation(direction):
    class InvalidObjective:
        @property
        def direction(self):
            return direction

    class UnreadablePlan:
        @property
        def parameter_specs(self):
            raise AssertionError("sampling began before direction admission")

    calls = []
    with pytest.raises(StressObjectiveDirectionError) as error:
        run_stress_test(
            adversarial_plan=UnreadablePlan(),
            base_objective=InvalidObjective(),
            stage_b_evaluator=lambda *args: calls.append(args),
        )
    assert error.value.code == "stress_objective_direction_not_established"
    assert calls == []
