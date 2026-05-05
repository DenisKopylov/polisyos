from __future__ import annotations

import numpy as np
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import (
    FeedbackFixedPointCandidate,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
)
from polisyos.foundry.analysis.attractors import (
    build_attractor_analysis_result,
    build_attractor_ensemble_analysis_result,
    build_feedback_attractor_analysis_result,
    classify_terminal_regime,
    largest_lyapunov_exponent,
    load_attractor_analysis_result,
    persist_attractor_analysis_result,
)


def test_classify_terminal_regime_detects_fixed_point() -> None:
    trajectory = np.ones((16, 2), dtype=float)

    regime = classify_terminal_regime(trajectory, tolerance=1.0e-8, rtol=0.0)

    assert regime.kind == "fixed_point"
    assert regime.existence_status == "numerically_confirmed"
    assert regime.equilibrium == (1.0, 1.0)


def test_classify_terminal_regime_detects_limit_cycle() -> None:
    trajectory = np.asarray([[0.0], [1.0]] * 24, dtype=float)

    regime = classify_terminal_regime(
        trajectory,
        tolerance=1.0e-8,
        rtol=0.0,
        window=24,
        max_period=6,
    )

    assert regime.kind == "limit_cycle"
    assert regime.period == 2


def test_largest_lyapunov_exponent_detects_logistic_chaos() -> None:
    def step(x: np.ndarray) -> np.ndarray:
        return np.asarray([4.0 * x[0] * (1.0 - x[0])], dtype=float)

    def jacobian(x: np.ndarray) -> np.ndarray:
        return np.asarray([[4.0 - 8.0 * x[0]]], dtype=float)

    exponent = largest_lyapunov_exponent(
        step,
        np.asarray([0.12345], dtype=float),
        n_steps=500,
        renorm_every=1,
        jacobian_map=jacobian,
    )

    assert exponent > 0.3


def test_attractor_analysis_result_roundtrips_through_cas(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    trajectory = np.ones((8, 2), dtype=float)
    result = build_attractor_analysis_result(
        trajectory,
        ["income", "wealth"],
        analysis_id="analysis_fixed",
        tolerance=1.0e-8,
        rtol=0.0,
    )

    ref = persist_attractor_analysis_result(store, result)
    loaded = load_attractor_analysis_result(store, ref)

    assert loaded.analysis_id == "analysis_fixed"
    assert loaded.kind == "foundry.attractor_analysis_result"
    assert loaded.state_projection.variables == ["income", "wealth"]
    assert loaded.attractors[0].kind == "fixed_point"
    assert loaded.attractors[0].state_representation.equilibrium == {
        "income": 1.0,
        "wealth": 1.0,
    }


def test_multi_start_ensemble_builds_basin_map() -> None:
    fixed_a = np.zeros((12, 1), dtype=float)
    fixed_b = np.ones((12, 1), dtype=float)

    result, basin_map = build_attractor_ensemble_analysis_result(
        [fixed_a, fixed_b, fixed_b],
        ["stock"],
        initial_states=[{"stock": 0.0}, {"stock": 0.5}, {"stock": 0.8}],
        seeds=[1, 2, 3],
        tolerance=1.0e-8,
        rtol=0.0,
    )

    assert len(result.attractors) == 2
    assert basin_map.analysis_id == result.analysis_id
    assert basin_map.basin_measure_estimates == {"A1": 1 / 3, "A2": 2 / 3}
    assert [sample.attractor_id for sample in basin_map.samples] == ["A1", "A2", "A2"]


def test_feedback_solve_lifts_to_multiple_fixed_point_attractors() -> None:
    state = FeedbackStateSnapshot(
        variable_ids=["tax_rate"],
        values=[0.5],
        scales=[1.0],
        lower_bounds=[0.0],
        upper_bounds=[1.0],
        weights=[1.0],
    )
    alternative = FeedbackFixedPointCandidate(
        state=state.model_copy(update={"values": [0.8]}),
        residual_norm=1.0e-9,
    )
    feedback_result = FeedbackSolveResult(
        converged=True,
        initial_state=state.model_copy(update={"values": [0.1]}),
        final_state=state,
        alternative_fixed_points=[alternative],
    )

    result = build_feedback_attractor_analysis_result(feedback_result)

    assert [attractor.kind for attractor in result.attractors] == ["fixed_point", "fixed_point"]
    assert result.attractors[1].state_representation.equilibrium == {"tax_rate": 0.8}
