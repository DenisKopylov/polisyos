from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.causal import build_block_stratified_network_causal_data
from polisyos.foundry.methods.network import SBMStratificationResult


def test_block_causal_bridge_flags_low_support_blocks() -> None:
    labels = np.array([0, 0, 0, 1, 1, 1], dtype=int)
    stratification = SBMStratificationResult(
        method_name="sbm_stratification",
        labels=labels,
        responsibilities=np.full((6, 2), 0.5),
        co_clustering=np.eye(6),
        block_connectivity=np.array([[0.8, 0.1], [0.1, 0.7]]),
        degree_correction=np.ones(6),
        stability={"overall_stability": 0.9},
        positivity_report={"status": "not_evaluated"},
        metadata={"node_ids": [f"u{i}" for i in range(6)]},
    )

    treatment = np.array([1, 1, 1, 0, 0, 1], dtype=float)
    outcome = np.linspace(0.0, 1.0, num=6)
    causal_data, bridge = build_block_stratified_network_causal_data(
        outcome=outcome,
        treatment=treatment,
        stratification=stratification,
        min_treated_per_block=1,
        min_control_per_block=1,
    )

    assert np.array_equal(causal_data.cluster_id, labels)
    assert not bridge.positivity_passed
    assert len(bridge.block_support) == 2
    assert any(not report.positivity_passed for report in bridge.block_support)
    assert "block_0_positivity_low_support" in bridge.warnings
