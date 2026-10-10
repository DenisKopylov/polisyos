"""Behavior tests for ordinal-poverty helper paths."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.ir.analytics.distributional import load_ordinal_poverty_report
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_ordinal import (
    _coerce_ordinal_category_matrix,
    _coerce_ordinal_weights,
    _maybe_build_ordinal_poverty_report,
    _run_ordinal_poverty_estimate,
)


def test_ordinal_estimate_is_row_order_invariant_and_report_round_trips(
    execution_context,
    minimal_state,
    cas_store,
    artifact_ref_factory,
) -> None:
    categories = np.asarray(
        [
            [1, 1, 1],
            [4, 4, 3],
            [2, 1, 1],
            [3, 4, 3],
            [1, 3, 2],
            [2, 4, 3],
            [3, 2, 2],
            [4, 1, 1],
        ],
        dtype=object,
    )
    counterfactual = np.asarray(
        [
            [2, 2, 2],
            [4, 4, 3],
            [3, 2, 2],
            [3, 4, 3],
            [2, 3, 2],
            [3, 4, 3],
            [3, 3, 2],
            [4, 2, 2],
        ],
        dtype=object,
    )
    config = {
        "category_orders": [[1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3]],
        "deprivation_cutoffs": [2, 2, 1],
        "dimension_names": ["health", "education", "housing"],
        "poverty_cutoff_K": 2 / 3,
    }

    default_weights = _coerce_ordinal_weights(None, n_dimensions=3)
    equal_weights = _coerce_ordinal_weights([1 / 3, 1 / 3, 1 / 3], n_dimensions=3)
    np.testing.assert_allclose(default_weights, equal_weights)

    estimate = _run_ordinal_poverty_estimate(
        config,
        category_matrix=categories,
        label="baseline",
    )
    permuted = _run_ordinal_poverty_estimate(
        config,
        category_matrix=categories[[6, 2, 0, 7, 1, 5, 3, 4]],
        label="baseline",
    )
    assert permuted.n_agents == estimate.n_agents
    assert permuted.n_poor == estimate.n_poor
    assert permuted.headcount_h == pytest.approx(estimate.headcount_h)
    assert permuted.ordinal_intensity_a == pytest.approx(estimate.ordinal_intensity_a)
    assert permuted.ordinal_adjusted_headcount_q == pytest.approx(
        estimate.ordinal_adjusted_headcount_q
    )

    source_ref = artifact_ref_factory(kind="foundry.simulation_result")
    state = minimal_state.model_copy(deep=True)
    state.params["ordinal_poverty"] = {
        **config,
        "baseline_category_matrix": categories.tolist(),
        "counterfactual_category_matrix": counterfactual.tolist(),
    }
    resolution = _maybe_build_ordinal_poverty_report(
        execution_context,
        state,
        artifact_inputs=[InputRef(artifact_id=source_ref.artifact_id, role="simulation_result")],
        sim_result_ref=source_ref,
        baseline_agent_count=len(categories),
        counterfactual_agent_count=len(counterfactual),
    )

    assert resolution.ref is not None
    assert resolution.summary["status"] == "included"
    assert resolution.metadata["ordinal_poverty_status"] == "included"
    loaded = load_ordinal_poverty_report(ensure_ir_artifact_store(cas_store), resolution.ref)
    assert loaded.baseline.n_agents == len(categories)
    assert loaded.counterfactual is not None
    assert loaded.counterfactual.n_agents == len(counterfactual)


def test_ordinal_shape_and_weight_failures_remain_skipped_without_report(
    execution_context,
    minimal_state,
    artifact_ref_factory,
) -> None:
    matrix = _coerce_ordinal_category_matrix(
        [[1, 1], [2, 2]],
        name="baseline",
        expected_agents=2,
    )
    assert matrix.shape == (2, 2)
    with pytest.raises(ValueError, match="row count must match agent count"):
        _coerce_ordinal_category_matrix(
            [[1, 1], [2, 2]],
            name="baseline",
            expected_agents=3,
        )
    with pytest.raises(ValueError, match="sum to a positive value"):
        _coerce_ordinal_weights([0.0, 0.0], n_dimensions=2)

    source_ref = artifact_ref_factory(kind="foundry.simulation_result")
    state = minimal_state.model_copy(deep=True)
    state.params["ordinal_poverty"] = {
        "category_orders": [[1, 2], [1, 2]],
        "deprivation_cutoffs": [1, 1],
        "baseline_category_matrix": [[1, 1], [2, 2]],
    }
    resolution = _maybe_build_ordinal_poverty_report(
        execution_context,
        state,
        artifact_inputs=[InputRef(artifact_id=source_ref.artifact_id, role="simulation_result")],
        sim_result_ref=source_ref,
        baseline_agent_count=3,
        counterfactual_agent_count=3,
    )

    assert resolution.ref is None
    assert resolution.summary["status"] == "skipped"
    assert resolution.metadata["ordinal_poverty_status"] == "skipped"
    assert "row count must match agent count" in resolution.metadata["ordinal_poverty_reason"]
