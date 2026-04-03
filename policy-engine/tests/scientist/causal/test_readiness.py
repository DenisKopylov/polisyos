from __future__ import annotations

import hashlib

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.strategic import StrategicFallbackMode
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.strategic import FiniteStrategicPayoffTable, StrategicSCM
from polisyos.ir.observation.bundles import (
    CounterfactualCheckBundle,
    ProxyIdentificationBundle,
    StrategicResponseSpecsBundle,
    TransportabilityCheckBundle,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.causal.readiness import (
    CounterfactualQueryRunner,
    ProxyIdentificationRunner,
    StrategicResponseRunner,
    TransportabilityChecker,
)
from polisyos.scientist.kernel.budgets import ComputeBudget


def _artifact_ref(seed: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel.model_validate(
        {
            "artifact_id": f"sha256:{hashlib.sha256(seed.encode('utf-8')).hexdigest()}",
            "kind": kind,
            "media_type": "application/json",
        }
    )


def _proxy_graph(*, invalid: bool = False) -> CausalGraphModel:
    edges = [
        CausalEdge(src="C", dst="X"),
        CausalEdge(src="C", dst="Y"),
        CausalEdge(src="C", dst="C_star"),
        CausalEdge(src="X", dst="Y"),
    ]
    if invalid:
        edges.append(CausalEdge(src="C_star", dst="Y"))
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y", "C", "C_star"],
        edges=edges,
    )


def _simple_graph() -> CausalGraphModel:
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )


def _strategic_contract() -> StrategicSCM:
    return StrategicSCM(
        base_graph_ref=_artifact_ref("graph", kind="ir.causal_graph_model"),
        strategic_agents=("leader", "follower"),
        utility_refs={
            "leader": _artifact_ref("leader-payoff", kind="ir.strategic_payoff_table"),
            "follower": _artifact_ref("follower-payoff", kind="ir.strategic_payoff_table"),
        },
        policy_rule_ref=_artifact_ref("policy", kind="ir.policy_recommendation"),
        equilibrium_concept="stackelberg",
        compute_budget=ComputeBudget(max_llm_calls=0.0, max_sim_runs=16.0, max_wall_time_s=30.0),
    )


def _payoff_tables() -> dict[str, FiniteStrategicPayoffTable]:
    action_spaces = {
        "leader": ("low", "high"),
        "follower": ("stay", "switch"),
    }
    return {
        "leader": FiniteStrategicPayoffTable(
            agent="leader",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 1.0,
                "leader=low|follower=switch": 0.0,
                "leader=high|follower=stay": 2.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
        "follower": FiniteStrategicPayoffTable(
            agent="follower",
            strategic_agents=("leader", "follower"),
            action_spaces=action_spaces,
            payoffs={
                "leader=low|follower=stay": 2.0,
                "leader=low|follower=switch": 1.0,
                "leader=high|follower=stay": 0.0,
                "leader=high|follower=switch": 3.0,
            },
        ),
    }


def test_proxy_identification_runner_returns_identified_and_oracle_needed() -> None:
    bundle = ProxyIdentificationBundle(
        contract_target={
            "contract_id": "foundry.causal.proxy_measurement_data.v1",
            "contract_fqn": "polisyos.foundry.methods.catalog.causal.protocols.ProxyMeasurementData",
        },
        proxy_channels=[
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
    )
    valid = ProxyIdentificationRunner(graph=_proxy_graph()).run(
        bundle,
        measurement_models={"labor_market": "known"},
    )
    invalid = ProxyIdentificationRunner(graph=_proxy_graph(invalid=True)).run(
        bundle,
        measurement_models={"labor_market": "known"},
    )

    assert valid[0].status == "identified"
    assert valid[0].estimand_ast is not None
    assert invalid[0].status == "oracle_needed"
    assert invalid[0].normalized_reason is not None


def test_transportability_checker_short_circuits_same_regime_and_persists_cross_regime(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    checker = TransportabilityChecker(graph=_simple_graph(), store=store)
    bundle = TransportabilityCheckBundle(
        checks=[
            {
                "check_id": "same_regime",
                "family": "budget_flows",
                "treatment": "X",
                "outcome": "Y",
                "source_regime_id": "r1",
                "target_regime_id": "r1",
                "source_context": {"context_id": "UA"},
                "target_context": {"context_id": "UA"},
            },
            {
                "check_id": "cross_regime",
                "family": "procurement_flows",
                "treatment": "X",
                "outcome": "Y",
                "source_regime_id": "r1",
                "target_regime_id": "r2",
                "explicit_s_nodes": [
                    {
                        "target_variable": "Y",
                        "context_dimension": "procurement_regime",
                        "source_value": 0.0,
                        "target_value": 1.0,
                        "delta": 1.0,
                        "severity": "high",
                    }
                ],
            },
        ]
    )

    entries = checker.run(bundle)

    assert entries[0].status == "identified"
    assert entries[0].cross_regime is False
    assert entries[0].result_ref is not None
    assert entries[1].cross_regime is True
    assert entries[1].status in {"identified", "blocked"}
    assert entries[1].result_ref is not None


def test_strategic_response_runner_returns_performative_shift(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    causal_component_ref = _artifact_ref("causal", kind="ir.causal_effect_report")
    bundle = StrategicResponseSpecsBundle(
        expectations=[
            {
                "intervention_kind": "procurement_threshold_change",
                "channels": ["procurement_channel"],
            }
        ]
    )
    runner = StrategicResponseRunner(
        store=store,
        causal_component_ref=causal_component_ref,
        run_metadata={"run_id": "R_test"},
    )

    entries = runner.run(
        bundle,
        channel_payloads={
            "procurement_channel": {
                "baseline_policy_value": 5.0,
                "strategic_scm": _strategic_contract().model_dump(mode="json"),
                "strategic_payoff_tables": {
                    key: table.model_dump(mode="json") for key, table in _payoff_tables().items()
                },
            }
        },
    )

    assert len(entries) == 1
    assert entries[0].status == "ready"
    assert entries[0].fallback_mode == StrategicFallbackMode.EXACT_EQUILIBRIUM.value
    assert entries[0].performative_shift == 3.0
    assert entries[0].strategic_response_bundle_ref is not None


def test_counterfactual_query_runner_reports_identified_and_blocked() -> None:
    bundle = CounterfactualCheckBundle(
        queries=[
            {
                "query_id": "identified",
                "family": "budget_flows",
                "query": {
                    "outcome": "Y",
                    "intervention": {"X": 1.0},
                },
            },
            {
                "query_id": "blocked",
                "family": "budget_flows",
                "query": {
                    "outcome": "Y",
                    "intervention": {"X": 1.0},
                    "evidence": {"X": 0.0},
                },
            },
        ]
    )

    entries = CounterfactualQueryRunner(graph=_simple_graph()).run(bundle)

    assert entries[0].status == "identified"
    assert entries[0].estimand_ast is not None
    assert entries[1].status != "identified"
    assert entries[1].normalized_reason is not None

