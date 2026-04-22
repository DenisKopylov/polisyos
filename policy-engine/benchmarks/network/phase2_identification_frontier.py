#!/usr/bin/env python3
"""Lightweight benchmark for Phase 2 network identification methods."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _path in (str(_SRC), str(_BENCH_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from polisyos.foundry.methods.catalog.network.analysis import (
    PeerEffectDecompositionEstimator,
)
from polisyos.foundry.methods.catalog.network.missingness import (
    NetworkMissingnessRequest,
    build_network_missingness_assessment,
)
from polisyos.foundry.methods.network import compute_embedding_fidelity_certificate
from tests.foundry.methods.catalog.network.test_embedding_fidelity import _ring_adjacency
from tests.foundry.methods.catalog.network.test_peer_effect_decomposition import _baseline_state

SUITE_ID = "phase2_network_identification"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--quiet", action="store_true", help="Suppress human-readable output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    peer_result = PeerEffectDecompositionEstimator.pure_step(
        _baseline_state(),
        {"weak_iv_threshold": 0.1, "ci_level": 0.9},
    )["result"]
    peer_effect = peer_result.peer_effect_decomposition

    adjacency = np.array(
        [
            [0.0, 1.0, 0.0, 0.0],
            [1.0, 0.0, 1.0, 0.0],
            [0.0, 1.0, 0.0, 1.0],
            [0.0, 0.0, 1.0, 0.0],
        ]
    )
    dyad_features = np.zeros((4, 4, 1), dtype=float)
    formation_events = (
        {"i": 0, "j": 1, "next_state": 1, "dyad_covariates": (0.2,)},
        {"i": 1, "j": 2, "next_state": 1, "dyad_covariates": (0.8,)},
        {"i": 2, "j": 3, "next_state": 1, "dyad_covariates": (1.1,)},
        {"i": 0, "j": 2, "next_state": 0, "dyad_covariates": (0.1,)},
        {"i": 1, "j": 3, "next_state": 0, "dyad_covariates": (0.3,)},
        {"i": 0, "j": 3, "next_state": 0, "dyad_covariates": (0.0,)},
    )

    from polisyos.foundry.methods.catalog.network.strategic import (
        StrategicNetworkFormationEstimator,
    )

    formation_result = StrategicNetworkFormationEstimator.pure_step(
        {
            "adjacency": adjacency,
            "dyad_features": dyad_features,
            "initial_adjacency": np.zeros_like(adjacency),
            "formation_events": formation_events,
        },
        {"prefer_event_history": True},
    )["result"]

    from polisyos.foundry.methods.catalog.network.protocols import NetworkData

    missingness = build_network_missingness_assessment(
        NetworkData(
            adjacency=np.array(
                [
                    [0.0, 1.0, 0.0],
                    [1.0, 0.0, 1.0],
                    [0.0, 1.0, 0.0],
                ]
            )
        ),
        NetworkMissingnessRequest(
            mode="design_based",
            missingness_type="link_censoring",
            estimands=("edge_count", "average_degree"),
            dyad_inclusion_probabilities=np.array(
                [
                    [1.0, 0.5, 0.5],
                    [0.5, 1.0, 0.5],
                    [0.5, 0.5, 1.0],
                ]
            ),
        ),
    )

    rng = np.random.default_rng(17)
    n_obs = 160
    separator = rng.normal(size=n_obs)
    treatment = 0.8 * separator + rng.normal(scale=0.25, size=n_obs)
    outcome = 1.4 * treatment + 0.9 * separator + rng.normal(scale=0.25, size=n_obs)
    left = 0.7 * separator + rng.normal(scale=0.3, size=n_obs)
    right = -0.5 * separator + rng.normal(scale=0.3, size=n_obs)
    embedding = np.column_stack([separator, separator + rng.normal(scale=0.05, size=n_obs)])
    embedding_certificate = compute_embedding_fidelity_certificate(
        {
            "adjacency_matrix": _ring_adjacency(n_obs),
            "embedding_matrix": embedding,
            "embedding_family": "node2vec",
            "separator_matrix": {"community_score": separator},
            "treatment": treatment,
            "outcome": outcome,
            "columns": {"left_aux": left, "right_aux": right},
            "ci_specs": [
                {
                    "name": "aux_independence",
                    "left": "left_aux",
                    "right": "right_aux",
                    "separator_names": ["community_score"],
                }
            ],
        }
    )

    payload = {
        "suite_id": SUITE_ID,
        "status": "pass",
        "metrics": {
            "peer_identified": 1.0 if peer_effect and peer_effect.diagnostics.identification_status == "identified" else 0.0,
            "formation_event_history_used": 1.0 if formation_result.formation_diagnostic and formation_result.formation_diagnostic.event_history_used else 0.0,
            "missingness_edge_count": float(missingness.estimands["edge_count"].estimate or 0.0),
            "embedding_status_green": 1.0 if embedding_certificate["status"] == "green" else 0.0,
        },
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding="utf-8")
    if not args.quiet:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
