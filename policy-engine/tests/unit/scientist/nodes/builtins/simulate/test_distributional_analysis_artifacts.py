"""Behavior tests for distributional artifact summaries and CAS persistence."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.artifacts.store import PutOptions
from polisyos.foundry.methods.catalog.causal.density_ratio import (
    compute_scalar_distributional_effect,
)
from polisyos.ir.analytics.distributional import (
    load_discrete_distribution_summary,
    load_ot_coupling_summary,
    load_quantile_shift_summary,
    load_tail_risk_delta_summary,
)
from polisyos.scientist.nodes.builtins.simulate.distributional_analysis_artifacts import (
    _maybe_none,
    _persist_scalar_artifacts,
)


def test_scalar_artifacts_persist_and_reload_with_paired_sample_invariants(
    execution_context,
    cas_store,
) -> None:
    baseline = np.asarray([10.0, 12.0, 15.0, 18.0, 21.0, 25.0])
    counterfactual = np.asarray([11.0, 14.0, 17.0, 20.0, 24.0, 28.0])
    result = compute_scalar_distributional_effect(
        baseline,
        counterfactual,
        n_bins=4,
        quantiles=(0.25, 0.5, 0.75),
        tail_probs=(0.8, 0.9),
    )
    source_ref = cas_store.put_json(
        {"source": "paired-scalar-input"},
        PutOptions(kind="test.distributional_input", media_type="application/json"),
    )
    inputs = [InputRef(artifact_id=source_ref.artifact_id, role="distributional_input")]
    persisted = _persist_scalar_artifacts(
        execution_context,
        outcome_name="income",
        baseline_values=baseline,
        counterfactual_values=counterfactual,
        result=result,
        inputs=inputs,
        coupling_assumptions=["scenario_level_ot_coupling"],
        metadata={"run_id": "R_artifact_round_trip"},
    )

    store = ensure_ir_artifact_store(cas_store)
    baseline_summary = load_discrete_distribution_summary(
        store, persisted.baseline_distribution_ref
    )
    counterfactual_summary = load_discrete_distribution_summary(
        store, persisted.counterfactual_distribution_ref
    )
    quantile_summary = load_quantile_shift_summary(store, persisted.quantile_shift_ref)
    tail_summary = load_tail_risk_delta_summary(store, persisted.tail_risk_delta_ref)
    coupling_summary = load_ot_coupling_summary(store, persisted.coupling_ref)

    assert baseline_summary.metadata["distribution_role"] == "baseline"
    assert counterfactual_summary.metadata["distribution_role"] == "counterfactual"
    assert baseline_summary.sample_size == len(baseline)
    assert counterfactual_summary.sample_size == len(counterfactual)
    assert sum(item.sample_count for item in baseline_summary.bins) == len(baseline)
    assert sum(item.sample_count for item in counterfactual_summary.bins) == len(counterfactual)
    assert sum(item.probability for item in baseline_summary.bins) == pytest.approx(1.0)
    assert sum(item.probability for item in counterfactual_summary.bins) == pytest.approx(1.0)
    assert len(quantile_summary.entries) == 3
    assert len(tail_summary.entries) == 2
    transport = np.asarray(coupling_summary.transport_matrix, dtype=float)
    assert transport.shape == (
        len(coupling_summary.source_support),
        len(coupling_summary.target_support),
    )
    assert float(np.sum(transport)) == pytest.approx(1.0, abs=1e-6)
    assert persisted.coupling_diagnostics.mass_conservation_error == pytest.approx(
        result.mass_conservation_error
    )
    assert persisted.coupling_diagnostics.identifiability_assumptions == [
        "scenario_level_ot_coupling"
    ]

    permuted = compute_scalar_distributional_effect(
        baseline[::-1],
        counterfactual[::-1],
        n_bins=4,
        quantiles=(0.25, 0.5, 0.75),
        tail_probs=(0.8, 0.9),
    )
    assert permuted.wasserstein_distance == pytest.approx(result.wasserstein_distance)
    assert permuted.quantile_shift.shifts == pytest.approx(result.quantile_shift.shifts)
    assert _maybe_none(float("inf")) is None
    assert _maybe_none(float("nan")) is None
