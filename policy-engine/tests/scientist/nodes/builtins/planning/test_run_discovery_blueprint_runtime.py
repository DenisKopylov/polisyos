from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from polisyos.ir.analytics.causal_graph import CausalGraphModel, GraphType
from polisyos.scientist.discovery.portfolio import PortfolioRunnerConfig
from polisyos.scientist.discovery.schema import DiscoveryMethod
from polisyos.scientist.engine.state_branching import branch_state as real_branch_state
from polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime import (
    RunDiscoveryBlueprintRuntimeNode,
    _measure_seed_reproducibility,
    _resolve_causal_query,
    _resolve_s_nodes,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF,
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_PRIOR_KNOWLEDGE_BUNDLE_REF,
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


def test_resolve_s_nodes_assertion_is_not_swallowed(minimal_state, monkeypatch: pytest.MonkeyPatch):
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


def test_run_discovery_blueprint_runtime_uses_branch_state_for_declared_outputs(
    execution_context, minimal_state, artifact_ref_factory
):
    bundle_ref = artifact_ref_factory(kind="scientist.discovery_artifact_bundle")
    graph_prior_ref = artifact_ref_factory(kind="scientist.graph_prior_bundle")
    prior_knowledge_ref = artifact_ref_factory(kind="scientist.prior_knowledge_bundle")
    hypothesis = SimpleNamespace(hypothesis_id="h1")
    portfolio_result = SimpleNamespace(
        candidates=[SimpleNamespace(hypothesis=hypothesis)],
        data_characteristics=MagicMock(),
    )
    baseline_utility_report = SimpleNamespace(
        recommended_shortlist=["h1"],
        metadata={},
    )
    utility_report = SimpleNamespace(
        recommended_shortlist=["h1"],
        metadata={"channel_coverage": {"transportability": True, "benchmark": True}},
    )
    graph_prior_bundle = MagicMock()
    graph_prior_bundle.metadata = {}
    graph_prior_bundle.model_copy.return_value = MagicMock()
    prior_knowledge_bundle = SimpleNamespace(status="ok")
    bundle = SimpleNamespace(
        graph_prior_bundle_ref=graph_prior_ref,
        prior_knowledge_bundle_ref=prior_knowledge_ref,
    )

    state = minimal_state.model_copy(deep=True)
    state.params["discovery_data"] = [[1.0, 2.0], [2.0, 3.0]]
    state.params["discovery_variable_names"] = ["X", "Y"]
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with (
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.branch_state",
            _spy_branch,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime._discovery_state_from_params",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.normalize_evidence_sources_config",
            return_value=SimpleNamespace(academic_db_path=None, academic_index_dir=None),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime._resolve_causal_query",
            return_value=MagicMock(),
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.GraphDiscoveryPortfolioRunner",
        ) as portfolio_runner_cls,
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.BootstrapStabilityAnalyzer",
        ) as stability_cls,
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.DownstreamUtilityJudge",
        ) as utility_cls,
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.UtilityJudgeInput",
            side_effect=lambda **kwargs: kwargs,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime._resolve_selection_diagram",
            return_value=None,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime._resolve_s_nodes",
            return_value=[],
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime._load_shortlist_benchmark_reports",
            return_value=[],
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.EvidenceWeightedAggregator",
        ) as aggregator_cls,
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime._measure_seed_reproducibility",
            return_value={"h1": 1.0},
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.GraphPriorBuilder",
        ) as prior_builder_cls,
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.PriorMiner",
        ) as prior_miner_cls,
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.DiscoveryArtifactBuilder",
        ) as artifact_builder_cls,
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.DiscoveryArtifactBuildInput",
            side_effect=lambda **kwargs: kwargs,
        ),
        patch(
            "polisyos.scientist.nodes.builtins.planning.run_discovery_blueprint_runtime.load_discovery_artifact_bundle",
            return_value=bundle,
        ),
    ):
        portfolio_runner_cls.return_value.run.return_value = portfolio_result
        stability_cls.return_value.analyze.return_value = MagicMock()
        utility_cls.return_value.evaluate.side_effect = [
            baseline_utility_report,
            utility_report,
        ]
        aggregator_cls.return_value.aggregate.return_value = MagicMock()
        prior_builder_cls.return_value.build.return_value = graph_prior_bundle
        prior_miner_cls.return_value.mine.return_value = prior_knowledge_bundle
        artifact_builder_cls.return_value.build.return_value = bundle_ref
        outcome = RunDiscoveryBlueprintRuntimeNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "params.graph_prior_bundle_ref",
        "params.prior_knowledge_bundle_ref",
        "params.discovery_artifact_bundle_ref",
        "inputs.graph_prior_bundle_ref",
        "inputs.prior_knowledge_bundle_ref",
        "artifacts_index.discovery_artifact_bundle_ref",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF not in state.artifacts_index
    assert INPUT_GRAPH_PRIOR_BUNDLE_REF not in state.inputs
    assert INPUT_PRIOR_KNOWLEDGE_BUNDLE_REF not in state.inputs
    assert outcome.state.artifacts_index[ARTIFACT_DISCOVERY_ARTIFACT_BUNDLE_REF] == bundle_ref
    assert outcome.state.inputs[INPUT_GRAPH_PRIOR_BUNDLE_REF] == graph_prior_ref
    assert outcome.state.inputs[INPUT_PRIOR_KNOWLEDGE_BUNDLE_REF] == prior_knowledge_ref
