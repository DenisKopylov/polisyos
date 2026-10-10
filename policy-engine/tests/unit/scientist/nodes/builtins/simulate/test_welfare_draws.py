from __future__ import annotations

import pytest

from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import (
    WelfareSampleDomainError,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_draws import (
    _run_welfare_monte_carlo_draws,
    _sample_param_draw,
    _validate_monte_carlo_draw_set,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_types import _WelfareNodeFailure


def _envelope() -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=1.0,
        confidence_interval=(0.0, 2.0),
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata={"param_name": "rate"},
    )


def _run_draws(simulation_fn):
    return _run_welfare_monte_carlo_draws(
        PropagationConfig(mc_n_samples=100, mc_seed=17),
        input_envelopes={"rate": _envelope()},
        dependence_sampler={"applied": False, "strategy": "independent_marginals"},
        coordinate_sampler=None,
        empirical_sampler=None,
        simulation_fn=simulation_fn,
        sample_domain_error_type=WelfareSampleDomainError,
        sample_param_draw=_sample_param_draw,
        calibration_resolution=None,
    )


def test_transient_retry_reuses_one_sample_and_counts_every_attempt() -> None:
    evaluator_inputs: list[float] = []

    def evaluate(**params: float) -> dict[str, float]:
        evaluator_inputs.append(params["rate"])
        if len(evaluator_inputs) == 1:
            raise PolicyOSError(
                "one transient evaluation failure",
                category=ErrorCategory.TRANSIENT,
                code="test.transient",
            )
        value = params["rate"]
        return {"welfare": value, "welfare_pe": value, "welfare_ge": 0.0}

    draws = _run_draws(evaluate)

    first = draws.terminal_outcomes[0]
    attempts = first["execution_attempts"]
    assert first["outcome_code"] == "success"
    assert [attempt["outcome_code"] for attempt in attempts] == [
        "transient_retry",
        "success",
    ]
    assert len({attempt["sampled_input_sha256"] for attempt in attempts}) == 1
    assert evaluator_inputs[0] == evaluator_inputs[1]
    assert draws.requested_draw_count == draws.counters.attempted_draw_count == 100
    assert draws.counters.simulation_attempt_count == 101
    assert draws.counters.retry_attempt_count == 1
    assert len(draws.welfare) == 100
    _validate_monte_carlo_draw_set(draws)


def test_draw_set_validation_rejects_retry_with_changed_sample_digest() -> None:
    def evaluate(**params: float) -> dict[str, float]:
        value = params["rate"]
        return {"welfare": value, "welfare_pe": value, "welfare_ge": 0.0}

    draws = _run_draws(evaluate)
    first_attempt = draws.terminal_outcomes[0]["execution_attempts"][0]
    first_attempt["sampled_input_sha256"] = "f" * 64

    with pytest.raises(_WelfareNodeFailure) as failure:
        _validate_monte_carlo_draw_set(draws)

    assert failure.value.error.code == "ERROR_MONTE_CARLO_NOT_CONVERGED"
    assert failure.value.error.details["draw_index"] == 0
    assert failure.value.error.details["attempt_number"] == 1


def test_draw_set_validation_rejects_missing_terminal_outcome() -> None:
    def evaluate(**params: float) -> dict[str, float]:
        value = params["rate"]
        return {"welfare": value, "welfare_pe": value, "welfare_ge": 0.0}

    draws = _run_draws(evaluate)
    draws.terminal_outcomes.pop()

    with pytest.raises(_WelfareNodeFailure) as failure:
        _validate_monte_carlo_draw_set(draws)

    assert failure.value.error.code == "ERROR_MONTE_CARLO_NOT_CONVERGED"
    assert failure.value.error.details == {
        "attempted_draw_count": 100,
        "terminal_outcome_count": 99,
    }


def test_global_evaluator_failure_does_not_become_a_failed_draw_or_redraw() -> None:
    calls: list[float] = []

    def evaluate(**params: float) -> dict[str, float]:
        calls.append(params["rate"])
        raise PermissionError("evaluator access is not available")

    with pytest.raises(_WelfareNodeFailure) as failure:
        _run_draws(evaluate)

    assert failure.value.error.code == "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE"
    assert failure.value.error.details["failure_scope"] == "global"
    assert failure.value.error.details["attempted_draw_count"] == 1
    assert failure.value.error.details["simulation_attempt_count"] == 1
    assert failure.value.error.details["retry_attempt_count"] == 0
    assert len(calls) == 1
