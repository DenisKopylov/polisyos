from __future__ import annotations

import hashlib
from unittest.mock import patch

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.id_engine import IdentificationStatus
from polisyos.foundry.methods.catalog.causal.strategic import StrategicFallbackMode
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.privacy_transportability import (
    DPGraphSourceKind,
    DPMechanismScope,
    DPUtilityManifest,
    DistortionToleranceMap,
    PrivateFactorBound,
    PrivateFactorMetric,
    PrivacyObservedMode,
    ValidityPredicate,
    ValidityPredicateKind,
    load_privacy_aware_transport_certificate,
)
from polisyos.ir.analytics.strategic import FiniteStrategicPayoffTable, StrategicSCM
from polisyos.ir.analytics.transportability import (
    SNodeOrigin,
    TransportMode,
    TransportabilityStatus,
    load_transportability_result,
)
from polisyos.ir.observation.bundles import (
    CounterfactualCheckBundle,
    ProxyIdentificationBundle,
    StrategicResponseSpecsBundle,
    TransportabilityCheckBundle,
)
from polisyos.ir.refs import (
    ArtifactRefModel,
    PrivacyAwareTransportCertificateRef,
    TransportabilityResultRef,
)
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


def _dp_manifest(
    *,
    error_bound: float = 0.02,
    max_factor_error: float = 0.03,
    privacy_mismatch_variables: tuple[str, ...] = (),
    fallback_queries: tuple[dict[str, object], ...] = (),
) -> DPUtilityManifest:
    return DPUtilityManifest(
        manifest_id="transport_dp_manifest",
        query_id="transport_readiness",
        source_domains=("source_a",),
        target_domain="target_t",
        dp_scope=(
            DPMechanismScope(
                domain_id="source_a",
                mechanism_id="laplace_source",
                mechanism_family="laplace",
                privacy_model="central",
                epsilon=2.0,
                released_statistics=("P_s(Y|do(X))",),
                public_channel_spec={"query_class": "laplace_histogram_v1"},
            ),
            DPMechanismScope(
                domain_id="target_t",
                mechanism_id="gaussian_target",
                mechanism_family="gaussian",
                privacy_model="central",
                epsilon=3.0,
                delta=1e-6,
                released_statistics=("P_t(Z)",),
                public_channel_spec={"query_class": "gaussian_histogram_v1"},
            ),
        ),
        private_factor_bounds=(
            PrivateFactorBound(
                factor_id="source_kernel",
                factor_expression="P_s(Y|do(X))",
                domain_id="source_a",
                metric=PrivateFactorMetric.LINF,
                error_bound=error_bound,
                confidence_level=0.95,
                estimator_kind="debias_laplace_histogram",
            ),
        ),
        validity_predicates=(
            ValidityPredicate(
                predicate_id="formula_error",
                predicate_kind=ValidityPredicateKind.FORMULA_ERROR,
                expression="eta_source <= 0.03",
                margin=0.03,
                sensitivity_by_factor={"source_kernel": 1.0},
            ),
        ),
        distortion_tolerance_map=DistortionToleranceMap(
            query_id="transport_readiness",
            factor_ids=("source_kernel",),
            factor_metrics={"source_kernel": PrivateFactorMetric.LINF},
            factor_error_bounds={"source_kernel": max_factor_error},
            predicate_margins={"formula_error": 0.03},
            sensitivity_matrix={"formula_error": {"source_kernel": 1.0}},
            utility_maps={
                "source_a": {"mechanism_to_error_contract": "laplace_histogram_v1"},
                "target_t": {"mechanism_to_error_contract": "gaussian_histogram_v1"},
            },
        ),
        privacy_mismatch_variables=privacy_mismatch_variables,
        graph_source_kind=DPGraphSourceKind.FIXED_EX_ANTE,
        graph_uncertainty_accounted=True,
        fallback_queries=fallback_queries,
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


def test_transportability_checker_applies_privacy_bounds_gate_and_persists_certificate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    checker = TransportabilityChecker(graph=_simple_graph(), store=store)
    bundle = TransportabilityCheckBundle(
        checks=[
            {
                "check_id": "privacy_bounds",
                "family": "budget_flows",
                "treatment": "X",
                "outcome": "Y",
                "source_regime_id": "r1",
                "target_regime_id": "r1",
                "source_context": {"context_id": "UA"},
                "target_context": {"context_id": "UA"},
                "dp_utility_manifest": _dp_manifest(
                    error_bound=0.08,
                    max_factor_error=0.03,
                    fallback_queries=(
                        {
                            "query": "P_t(Y)",
                            "mode": "descriptive_interval",
                        },
                    ),
                ).model_dump(mode="json"),
            }
        ]
    )

    entries = checker.run(bundle)
    result = load_transportability_result(
        store,
        TransportabilityResultRef.model_validate(
            entries[0].result_ref.model_dump(mode="json")
        ),
    )
    privacy_ref = PrivacyAwareTransportCertificateRef.model_validate(
        result.metadata["privacy_certificate_ref"]
    )
    certificate = load_privacy_aware_transport_certificate(store, privacy_ref)

    assert entries[0].status == "partially_identified"
    assert result.status is TransportabilityStatus.PARTIALLY_IDENTIFIED
    assert result.transport_mode is TransportMode.BOUNDS_ONLY
    assert result.metadata["privacy_observed_mode"] == "bounds_only"
    assert "tolerance_exceeded:source_kernel" in result.metadata["privacy_blocking_reasons"]
    assert certificate.privacy_observed_mode is PrivacyObservedMode.BOUNDS_ONLY


def test_transportability_checker_marks_privacy_mismatch_as_privacy_s_node(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    checker = TransportabilityChecker(graph=_simple_graph(), store=store)
    bundle = TransportabilityCheckBundle(
        checks=[
            {
                "check_id": "privacy_mismatch",
                "family": "budget_flows",
                "treatment": "X",
                "outcome": "Y",
                "source_regime_id": "r1",
                "target_regime_id": "r1",
                "source_context": {"context_id": "UA"},
                "target_context": {"context_id": "UA"},
                "dp_utility_manifest": _dp_manifest(
                    privacy_mismatch_variables=("Y",),
                ).model_dump(mode="json"),
            }
        ]
    )
    captured: dict[str, object] = {}

    class _FakeResult:
        status = IdentificationStatus.IDENTIFIED
        algorithm_version = "fake_transport"
        trace = ["privacy_s_node_seen"]
        estimand_ast = None
        hedge_certificate = None

    def _fake_tr_algorithm(*, treatment, outcome, selection_diagram):
        captured["variables"] = [node.target_variable for node in selection_diagram.s_nodes]
        captured["origins"] = [node.origin for node in selection_diagram.s_nodes]
        return _FakeResult()

    with patch(
        "polisyos.scientist.causal.readiness.tr_algorithm",
        side_effect=_fake_tr_algorithm,
    ):
        entries = checker.run(bundle)

    assert entries[0].cross_regime is True
    assert captured["variables"] == ["Y"]
    assert captured["origins"] == [SNodeOrigin.PRIVACY]


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
