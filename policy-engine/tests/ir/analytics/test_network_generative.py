from __future__ import annotations

import numpy as np

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.network_generative import (
    BlockSupportReport,
    CausalBlockBridge,
    load_causal_block_bridge,
    persist_causal_block_bridge,
)
from polisyos.ir.refs import CausalBlockBridgeRef


def test_causal_block_bridge_round_trip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bridge = CausalBlockBridge(
        cluster_id=np.array([0, 0, 1, 1], dtype=int),
        node_to_block={"u0": 0, "u1": 0, "u2": 1, "u3": 1},
        block_support=(
            BlockSupportReport(
                block_id=0,
                n_units=2,
                n_treated=1,
                n_control=1,
                treated_share=0.5,
                positivity_passed=True,
            ),
            BlockSupportReport(
                block_id=1,
                n_units=2,
                n_treated=1,
                n_control=1,
                treated_share=0.5,
                positivity_passed=True,
            ),
        ),
        positivity_passed=True,
        aggregate_exposures={"treatment_share_by_block": {"0": 0.5, "1": 0.5}},
    )

    ref = persist_causal_block_bridge(store, bridge)
    assert isinstance(ref, CausalBlockBridgeRef)
    loaded = load_causal_block_bridge(store, ref)
    assert np.array_equal(np.asarray(loaded.cluster_id, dtype=int), np.array([0, 0, 1, 1], dtype=int))
    assert loaded.node_to_block == bridge.node_to_block
    assert loaded.block_support == bridge.block_support
