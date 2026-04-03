from __future__ import annotations

import hashlib
import logging

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.observation.causal_readiness import load_causal_readiness_bundle
from polisyos.ir.refs import CausalReadinessBundleRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.run_causal_readiness import RunCausalReadinessNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_READINESS_BUNDLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)


def _build_ctx(tmp_path, *, run_id: str) -> ExecutionContext:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id=run_id)
    return ExecutionContext(store=store, run=run, logger=logging.getLogger(f"test.{run_id}"))


def _artifact_ref(seed: str, *, kind: str) -> dict[str, str]:
    return {
        "artifact_id": f"sha256:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}",
        "kind": kind,
        "media_type": "application/json",
    }


def _graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "C", "C_star"],
        edges=[
            CausalEdge(src="C", dst="X"),
            CausalEdge(src="C", dst="Y"),
            CausalEdge(src="C", dst="C_star"),
            CausalEdge(src="X", dst="Y"),
        ],
    )


def _strategic_payload() -> dict[str, object]:
    action_spaces = {"leader": ("low", "high"), "follower": ("stay", "switch")}
    return {
        "baseline_policy_value": 5.0,
        "strategic_scm": {
            "base_graph_ref": _artifact_ref("graph", kind="ir.causal_graph_model"),
            "strategic_agents": ["leader", "follower"],
            "utility_refs": {
                "leader": _artifact_ref("leader-payoff", kind="ir.strategic_payoff_table"),
                "follower": _artifact_ref("follower-payoff", kind="ir.strategic_payoff_table"),
            },
            "policy_rule_ref": _artifact_ref("policy", kind="ir.policy_recommendation"),
            "equilibrium_concept": "stackelberg",
            "compute_budget": {
                "max_llm_calls": 0.0,
                "max_sim_runs": 16.0,
                "max_wall_time_s": 30.0,
            },
        },
        "strategic_payoff_tables": {
            "leader": {
                "agent": "leader",
                "strategic_agents": ["leader", "follower"],
                "action_spaces": action_spaces,
                "payoffs": {
                    "leader=low|follower=stay": 1.0,
                    "leader=low|follower=switch": 0.0,
                    "leader=high|follower=stay": 2.0,
                    "leader=high|follower=switch": 3.0,
                },
            },
            "follower": {
                "agent": "follower",
                "strategic_agents": ["leader", "follower"],
                "action_spaces": action_spaces,
                "payoffs": {
                    "leader=low|follower=stay": 2.0,
                    "leader=low|follower=switch": 1.0,
                    "leader=high|follower=stay": 0.0,
                    "leader=high|follower=switch": 3.0,
                },
            },
        },
    }


def test_run_causal_readiness_node_persists_bundle_and_leaf_refs(tmp_path) -> None:
    ctx = _build_ctx(tmp_path, run_id="R_c4a")
    graph_ref = persist_causal_graph_model(ctx.store, _graph())
    state = ExperimentState(
        run_id="R_c4a",
        artifacts_index={
            ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF: ArtifactRef.model_validate(
                graph_ref.model_dump(mode="json")
            )
        },
        params={
            "measurement_model_by_family": {"labor_market": "known"},
            "proxy_identification_bundle": {
                "contract_target": {
                    "contract_id": "foundry.causal.proxy_measurement_data.v1",
                    "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
                },
                "proxy_channels": [
                    {
                        "family": "labor_market",
                        "proxy_variable": "C_star",
                        "latent_variable": "C",
                        "treatment_variable": "X",
                        "outcome_variable": "Y",
                        "target_contract": {
                            "contract_id": "foundry.causal.proxy_measurement_data.v1",
                            "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
                        },
                    }
                ],
            },
            "transportability_check_bundle": {
                "checks": [
                    {
                        "check_id": "same_regime",
                        "family": "budget_flows",
                        "treatment": "X",
                        "outcome": "Y",
                        "source_regime_id": "r1",
                        "target_regime_id": "r1",
                        "source_context": {"context_id": "UA"},
                        "target_context": {"context_id": "UA"},
                    }
                ]
            },
            "strategic_response_specs_bundle": {
                "expectations": [
                    {
                        "intervention_kind": "procurement_threshold_change",
                        "channels": ["procurement_channel"],
                    }
                ]
            },
            "strategic_channel_inputs": {"procurement_channel": _strategic_payload()},
            "counterfactual_check_bundle": {
                "queries": [
                    {
                        "query_id": "cf1",
                        "family": "budget_flows",
                        "query": {"outcome": "Y", "intervention": {"X": 1.0}},
                    }
                ]
            },
            "interference_loss_spec_bundle": {
                "specs": [
                    {
                        "spec_id": "spillover",
                        "family": "procurement_flows",
                        "graph_layer": "procurement",
                        "predicted_metric_path": "metrics.procurement_spillover",
                        "observed_spillover": [0.2, 0.4],
                        "adjacency": [[0.0, 1.0], [1.0, 0.0]],
                        "trust_weight": [1.0, 1.0],
                        "coverage_estimate": [1.0, 1.0],
                    }
                ]
            },
        },
    )

    outcome = RunCausalReadinessNode().execute(ctx, state)

    assert outcome.status == "ok"
    assert ARTIFACT_CAUSAL_READINESS_BUNDLE_REF in outcome.state.artifacts_index
    assert ARTIFACT_TRANSPORTABILITY_RESULT_REF in outcome.state.artifacts_index
    assert ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF in outcome.state.artifacts_index

    bundle_ref = outcome.state.artifacts_index[ARTIFACT_CAUSAL_READINESS_BUNDLE_REF]
    bundle = load_causal_readiness_bundle(
        ctx.store,
        CausalReadinessBundleRef.model_validate(bundle_ref.model_dump(mode="json")),
    )
    assert len(bundle.proxy_results) == 1
    assert bundle.proxy_results[0].status == "identified"
    assert len(bundle.transport_results) == 1
    assert len(bundle.strategic_results) == 1
    assert len(bundle.counterfactual_results) == 1
    assert len(bundle.interference_specs) == 1
