"""Independent typed-coordinate consumers; synthetic fixtures, no history claim."""

import math
from unittest.mock import patch

import numpy as np
import pytest

from polisyos.scientist.methods.autotune.bayesian_generator import SearchSpace as PublicSpace
from polisyos.scientist.methods.search.objective import ObjectiveValue, OptimizationDirection
from polisyos.scientist.methods.search.strategies import _deps
from polisyos.scientist.methods.search.strategies import multi_objective as mo_module
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
    MOConfig,
)
from polisyos.scientist.methods.search.strategies.neural import (
    NeuralSearchConfig,
    NeuralSearchStrategy,
)
from polisyos.scientist.methods.search.strategies.resource_arbiter import (
    ResourceArbiter,
    ResourcePolicy,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    ParameterBounds,
    ParameterType,
)

native = pytest.mark.skipif(
    _deps.fit_gpytorch_mll is None,
    reason="UNRUN: required actual optional BoTorch/GPyTorch backend",
)


@pytest.mark.parametrize("public", [False, True])
def test_explicit_unsupported_affine_span_refuses_before_any_candidate(public):
    # Root-approved supported-domain limit.  This is a separate property from
    # the preserved4c midpoint/endpoint red; it does not claim a new midpoint.
    def make_domain():
        if public:
            return PublicSpace([{"name": "x", "lower": -1e308, "upper": 1e308}])
        return ParameterBounds("x", lower=-1e308, upper=1e308)

    with pytest.raises(ValueError, match="representable span"):
        make_domain()


def test_supported_log_endpoints_and_midpoint_follow_declared_geometry():
    space = SearchSpace([ParameterBounds("x", 1e-308, 1e308, dtype=ParameterType.LOG_CONTINUOUS)])
    for coordinate, expected in [(0.0, 1e-308), (0.5, 1.0), (1.0, 1e308)]:
        candidate = space.candidate_from_vector((coordinate,))
        assert math.isfinite(candidate.params["x"])
        assert 1e-308 <= candidate.params["x"] <= 1e308
        assert candidate.params["x"] == pytest.approx(expected, rel=2e-13, abs=0.0)
        assert candidate.params_normalized == pytest.approx((coordinate,), rel=2e-13, abs=2e-15)


def _space():
    return SearchSpace(
        [
            ParameterBounds("n", 0.2, 1.8, dtype=ParameterType.INTEGER),
            ParameterBounds("mode", dtype=ParameterType.CATEGORICAL, categories=(False, True)),
        ]
    )


def _rows(space):
    rows = []
    for index in range(6):
        mode = index % 2 == 1
        cost = 2.0 + int(mode) + index / 20
        benefit = 4.0 - 3 * int(mode) + index / 10
        rows.append(
            Evaluation(
                f"synthetic-coordinate-{index}",
                {"n": 1, "mode": mode},
                (0.5, 0.0 if mode else 1.0, 1.0 if mode else 0.0),
                [
                    ObjectiveValue("cost", cost, OptimizationDirection.MINIMIZE),
                    ObjectiveValue("benefit", benefit, OptimizationDirection.MAXIMIZE),
                ],
                benefit,  # Existing neural algorithm models a maximize scalar.
                True,
                metadata={"replica_id": str(index)},
            )
        )
    return rows


def _assert_execution(candidate):
    assert candidate.params["n"] == 1 and type(candidate.params["n"]) is int
    assert type(candidate.params["mode"]) is bool
    # Enumerated domain: ceil(.2)=floor(1.8)=1, normalized n=(1-.2)/1.6=.5.
    expected = (
        0.5,
        0.0 if candidate.params["mode"] else 1.0,
        1.0 if candidate.params["mode"] else 0.0,
    )
    assert candidate.params_normalized == expected


@native
def test_actual_multiobjective_fit_and_acquisition_then_typed_converter():
    space = _space()
    rows = _rows(space)
    strategy = MOBayesianOptimizer(
        space,
        ["cost", "benefit"],
        [OptimizationDirection.MINIMIZE, OptimizationDirection.MAXIMIZE],
        MOConfig(n_initial=3, seed=31, num_restarts=1, raw_samples=16),
        ResourceArbiter(
            ResourcePolicy(soft_rss_mb=1_000_000, hard_rss_mb=2_000_000, enable_cleanup=False)
        ),
    )
    with (
        patch.object(mo_module, "fit_gpytorch_mll", wraps=mo_module.fit_gpytorch_mll) as fit,
        patch.object(mo_module, "optimize_acqf", wraps=mo_module.optimize_acqf) as optimize,
    ):
        candidate = strategy.suggest(rows)
    assert fit.call_count == optimize.call_count == 1
    assert candidate.source_strategy == "ehvi", "A random fallback is not the real MO witness"
    np.testing.assert_allclose(
        strategy._train_X.cpu().numpy(),
        [(0.5, float(1 - i % 2), float(i % 2)) for i in range(6)],
    )
    expected_targets = [[-(2.0 + i % 2 + i / 20), 4.0 - 3 * (i % 2) + i / 10] for i in range(6)]
    np.testing.assert_allclose(strategy._train_Y.cpu().numpy(), expected_targets)
    _assert_execution(candidate)
    assert candidate.predicted_mean is candidate.predicted_std is None
    assert candidate.metadata["prediction_basis"] == "not_established_no_scalar_predictor"
    assert candidate.metadata["acquisition_value_basis"] == "relaxed_proposal"
    controlled = strategy._tensor_to_candidate(
        _deps.require_torch().tensor([0.24, 0.73, 0.37], dtype=_deps.require_torch().double),
        "synthetic-controlled-proposal",
        0.8,
    )
    assert controlled.params == {"n": 1, "mode": False}
    assert controlled.params_normalized == (0.5, 1.0, 0.0)
    assert controlled.metadata["relaxed_proposal"] == pytest.approx([0.24, 0.73, 0.37])


@native
def test_actual_neural_fit_recomputes_at_executed_action_after_adversarial_proposal():
    space = _space()
    strategy = NeuralSearchStrategy(space, NeuralSearchConfig(n_initial=3, seed=31))
    torch = _deps.require_torch()
    observed = {}
    real_model, real_acq, real_optimize = (
        _deps.SingleTaskGP,
        _deps.ExpectedImprovement,
        _deps.optimize_acqf,
    )

    def actual_model(*args, **kwargs):
        model = real_model(*args, **kwargs)
        real_posterior = model.posterior

        def posterior_at(*positional, **named):
            point = positional[0] if positional else named["X"]
            observed["last_posterior_point"] = point.detach().cpu().numpy().copy()
            return real_posterior(*positional, **named)

        model.posterior = posterior_at
        return model

    def actual_acquisition(*args, **kwargs):
        acquisition = real_acq(*args, **kwargs)
        real_forward = acquisition.forward

        def consume(point, *positional, **named):
            observed["last_acquisition_point"] = point.detach().cpu().numpy().copy()
            return real_forward(point, *positional, **named)

        acquisition.forward = consume
        return acquisition

    def optimize_then_adversarial_input(*args, **kwargs):
        proposal, value = real_optimize(*args, **kwargs)
        observed["actual_optimizer_ran"] = True
        # Keep the actual fit and acquisition path.  Feed an explicit unattainable
        # proposal and false acquisition proxy into the final mapping boundary.
        return (
            torch.tensor([[0.24, 0.73, 0.37]], dtype=proposal.dtype, device=proposal.device),
            torch.full_like(value, 987654321.0),
        )

    with (
        patch.object(_deps, "SingleTaskGP", side_effect=actual_model),
        patch.object(_deps, "ExpectedImprovement", side_effect=actual_acquisition),
        patch.object(_deps, "optimize_acqf", side_effect=optimize_then_adversarial_input),
        patch.object(_deps, "fit_gpytorch_mll", wraps=_deps.fit_gpytorch_mll) as fit,
    ):
        candidate = strategy.suggest(_rows(space))
    assert fit.call_count == 1 and observed.get("actual_optimizer_ran")
    assert candidate.source_strategy == "neural_gp", "A fallback is not the actual neural witness"
    _assert_execution(candidate)
    assert candidate.params == {"n": 1, "mode": False}
    np.testing.assert_allclose(observed["last_posterior_point"].reshape(-1, 3), [[0.5, 1.0, 0.0]])
    np.testing.assert_allclose(observed["last_acquisition_point"].reshape(-1, 3), [[0.5, 1.0, 0.0]])
    assert math.isfinite(candidate.acquisition_value) and candidate.acquisition_value != 987654321.0
    assert math.isfinite(candidate.predicted_mean) and math.isfinite(candidate.predicted_std)


@native
@pytest.mark.parametrize("malformed", ["missing", "nan"])
def test_multiobjective_incomplete_vector_is_excluded_or_explicitly_refused(malformed):
    space = SearchSpace([ParameterBounds("x")])
    strategy = MOBayesianOptimizer(
        space, ["cost", "benefit"], [OptimizationDirection.MINIMIZE, OptimizationDirection.MAXIMIZE]
    )
    complete = Evaluation(
        "complete",
        {"x": 0.2},
        (0.2,),
        [
            ObjectiveValue("cost", 1.0, OptimizationDirection.MINIMIZE),
            ObjectiveValue("benefit", 1.0, OptimizationDirection.MAXIMIZE),
        ],
        1.0,
        True,
    )
    objectives = [ObjectiveValue("benefit", 100.0, OptimizationDirection.MAXIMIZE)]
    if malformed == "nan":
        objectives.append(ObjectiveValue("cost", float("nan"), OptimizationDirection.MINIMIZE))
    invalid = Evaluation("invalid", {"x": 0.8}, (0.8,), objectives, 0.0, True)
    try:
        front = strategy.get_pareto_front([complete, invalid])
    except ValueError:
        return
    assert [row.candidate_id for row in front] == ["complete"], (
        "An incomplete/nonfinite declared objective vector cannot be a Pareto observation"
    )
