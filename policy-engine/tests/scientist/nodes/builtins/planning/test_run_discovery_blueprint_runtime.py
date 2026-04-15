from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.scientist.discovery.portfolio import PortfolioRunnerConfig
from polisyos.scientist.discovery.schema import DiscoveryMethod
from polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime import (
    _measure_seed_reproducibility,
    _resolve_causal_query,
    _resolve_s_nodes,
)


def test_resolve_causal_query_assertion_is_not_swallowed(
    minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "discovery_query": {
                    "query_type": "interventional",
                    "treatment_variable": "X",
                    "treatment_value": 1.0,
                    "outcome_variable": "Y",
                    "n_samples": 128,
                }
            }
        }
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("discovery-query-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.CausalQuery.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="discovery-query-broken"):
        _resolve_causal_query(state, ["X", "Y"])


def test_resolve_s_nodes_assertion_is_not_swallowed(
    minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = minimal_state.model_copy(
        update={"params": {"discovery_s_nodes": [{"selection_variable": "S_X"}]}}
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("s-node-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.SNode.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="s-node-broken"):
        _resolve_s_nodes(state, None)


def test_measure_seed_reproducibility_assertion_is_not_swallowed(
    monkeypatch: pytest.MonkeyPatch,
):
    graph = CausalGraphModel(graph_type=GraphType.DAG, nodes=["X", "Y"], edges=[])
    hypothesis = SimpleNamespace(
        hypothesis_id="h1",
        method=DiscoveryMethod.PC,
        graph=graph,
        resolved_graph=None,
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("seed-replay-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.run_discovery_method",
        _boom,
    )

    with pytest.raises(AssertionError, match="seed-replay-broken"):
        _measure_seed_reproducibility(
            discovery_state=SimpleNamespace(
                data=np.asarray([[1.0, 2.0], [2.0, 3.0]]),
                variable_names=["X", "Y"],
            ),
            portfolio_config=PortfolioRunnerConfig(),
            shortlist=[hypothesis],
        )
