from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from polisyos.foundry.methods.catalog.causal._econml_adapter import build_hte_data
from polisyos.foundry.methods.catalog.causal.dml import DoubleMachineLearning
from polisyos.foundry.methods.catalog.causal.protocols import (
    HTEObservationalData,
    RDDObservationalData,
)
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.foundry.methods.components.io import materialize_method_input
from polisyos.ir.analytics.causal import EstimationStatus


def _rdd_vectors() -> tuple[np.ndarray, np.ndarray, float]:
    running_variable = np.linspace(-1.0, 1.0, 201)
    cutoff = 0.2
    outcome = 0.4 * running_variable + 2.5 * (running_variable >= cutoff)
    return outcome, running_variable, cutoff


def _hte_payload() -> dict[str, np.ndarray]:
    n_obs = 40
    return {
        "outcome": np.linspace(0.0, 1.0, n_obs),
        "treatment": np.asarray([0, 1] * (n_obs // 2)),
        "covariates": np.column_stack(
            (np.linspace(-1.0, 1.0, n_obs), np.ones(n_obs, dtype=float))
        ),
    }


def test_rdd_bound_vectors_keep_cutoff_from_typed_fallback_and_reach_estimator() -> None:
    outcome, running_variable, cutoff = _rdd_vectors()
    fallback = RDDObservationalData(
        outcome=np.zeros_like(outcome),
        running_variable=np.zeros_like(running_variable),
        cutoff=cutoff,
    )

    state = materialize_method_input(
        method_class=RegressionDiscontinuity,
        signature=RegressionDiscontinuity.signature,
        bound_inputs={"outcome": outcome, "running_variable": running_variable},
        fallback_state=fallback,
    )

    assert isinstance(state, RDDObservationalData)
    assert state.cutoff == cutoff
    assert np.array_equal(state.outcome, outcome)
    assert np.array_equal(state.running_variable, running_variable)
    report = RegressionDiscontinuity.pure_step(
        state,
        {"bandwidth": 0.5, "kernel": "uniform", "manipulation_test": False},
    )["report"]
    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(2.5, abs=1e-8)


def test_rdd_bound_vectors_without_any_cutoff_fail_closed() -> None:
    outcome, running_variable, _cutoff = _rdd_vectors()

    with pytest.raises(ValidationError, match="cutoff"):
        materialize_method_input(
            method_class=RegressionDiscontinuity,
            signature=RegressionDiscontinuity.signature,
            bound_inputs={"outcome": outcome, "running_variable": running_variable},
            fallback_state={},
        )


@pytest.mark.parametrize("structured", [False, True], ids=["mapping", "typed-model"])
def test_dml_input_materializer_preserves_existing_structured_hte_payloads(
    structured: bool,
) -> None:
    payload = _hte_payload()
    source: HTEObservationalData | dict[str, np.ndarray]
    source = HTEObservationalData(**payload) if structured else payload

    state = materialize_method_input(
        method_class=DoubleMachineLearning,
        signature=DoubleMachineLearning.signature,
        bound_inputs={"hte_data": source},
        fallback_state={},
    )

    assert isinstance(state, HTEObservationalData)
    adapted = build_hte_data(state)
    assert np.array_equal(adapted.y, payload["outcome"])
    assert np.array_equal(adapted.t, payload["treatment"])
    assert np.array_equal(adapted.x, payload["covariates"])


def test_dml_input_materializer_rejects_matrix_without_a_column_contract() -> None:
    payload = _hte_payload()
    matrix = np.column_stack(
        (payload["outcome"], payload["treatment"], payload["covariates"])
    )

    with pytest.raises(ValidationError):
        materialize_method_input(
            method_class=DoubleMachineLearning,
            signature=DoubleMachineLearning.signature,
            bound_inputs={"hte_data": matrix},
            fallback_state={},
        )
