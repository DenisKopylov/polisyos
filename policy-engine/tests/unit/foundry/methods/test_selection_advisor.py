from __future__ import annotations

import time
from dataclasses import replace

import numpy as np
import pytest
from polisyos.core.contracts.execution_plan import MethodCatalogEntry, MethodCatalogSnapshot
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog_snapshot import build_method_catalog_snapshot
from polisyos.foundry.methods.consensus import (
    ConsensusTarget,
    EstimandSpec,
    run_cross_method_consensus,
)
from polisyos.foundry.methods.selection import (
    AdvisorValuePolicy,
    DataCharacteristics,
    MethodAdvisorQuery,
    MethodSelectionCriteria,
    advise_methods,
    advise_methods_for_analyst,
    build_advisor_execution_context,
    pareto_advise_methods,
)
from polisyos.foundry.methods.selection_history import MethodExecutionRecord, SelectionHistoryStore


def _entry(
    fqn: str,
    *,
    family: str,
    variant: str,
    execution_backend: str = "numpy",
    runnable: bool = True,
    truthfulness_tier: str = "exact",
    implementation_depth_tier: str = "production_method",
    declared_truthfulness_tier: str | None = None,
    data_modalities: list[str] | None = None,
    advisor_cost: dict[str, object] | None = None,
    advisor_accuracy: dict[str, object] | None = None,
) -> MethodCatalogEntry:
    namespace_name, version = fqn.split("@", 1)
    namespace, name = namespace_name.rsplit(".", 1)
    data_modalities = data_modalities or ["cross-section"]
    capability_matrix = {
        "kind": "pure",
        "execution_backend": execution_backend,
        "runtime_stack": [execution_backend],
        "truthfulness_tier": truthfulness_tier,
        "implementation_depth_tier": implementation_depth_tier,
        "declared_truthfulness_tier": declared_truthfulness_tier,
        "effective_truthfulness_tier": truthfulness_tier,
        "backend_available": runnable,
        "runnable": runnable,
    }
    if advisor_cost is not None:
        capability_matrix["advisor_cost"] = advisor_cost
    if advisor_accuracy is not None:
        capability_matrix["advisor_accuracy"] = advisor_accuracy
    return MethodCatalogEntry(
        fqn=fqn,
        namespace=namespace,
        name=name,
        version=version,
        backend=execution_backend,
        execution_backend=execution_backend,
        kind="pure",
        family=family,
        variant=variant,
        fidelity_tier="high",
        data_modalities=data_modalities,
        runtime_stack=[execution_backend],
        runnable=runnable,
        capability_matrix=capability_matrix,
        truthfulness_tier=truthfulness_tier,
        implementation_depth_tier=implementation_depth_tier,
        implementation_depth_notes=f"{implementation_depth_tier} note",
        declared_truthfulness_tier=declared_truthfulness_tier,
        effective_truthfulness_tier=truthfulness_tier,
        truthfulness_status="catalog_only" if declared_truthfulness_tier else "runtime_only",
        truthfulness_notes=f"{truthfulness_tier} note",
        effect_semantics={"method_kind": "pure"},
        shape_semantics={"input_arity": 1},
        dependency_semantics={"hard_requires": []},
        typical_min_obs=500,
    )


def _consensus_estimand(*, time_horizon: str | None = None) -> EstimandSpec:
    return EstimandSpec(
        query_id="q-cross-method",
        estimand_id="ate",
        outcome="outcome",
        treatment_or_exposure="treatment",
        covariates_or_conditioning=("x1", "x2"),
        adjustment_set=("x1", "x2"),
        population="analysis_population",
        time_horizon=time_horizon,
        unit="points",
        target_role="causal",
    )


def _consensus_target(
    result_id: str,
    *,
    family: str,
    point: float,
    se: float = 0.1,
    estimand: EstimandSpec | None = None,
) -> ConsensusTarget:
    return ConsensusTarget(
        result_id=result_id,
        method_family=family,
        method_name=result_id,
        estimand=estimand or _consensus_estimand(),
        target_kind="causal_effect",
        point=np.asarray([point], dtype=float),
        covariance=np.asarray([[se * se]], dtype=float),
    )


def test_method_advisor_returns_ranked_payload_and_capability_matrix() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "causal.treatment_effects.tmle@1.0.0",
                family="causal.treatment_effects",
                variant="tmle",
                truthfulness_tier="exact",
                implementation_depth_tier="production_method",
            ),
            _entry(
                "causal.treatment_effects.proxy_score@1.0.0",
                family="causal.treatment_effects",
                variant="proxy_score",
                truthfulness_tier="unverified",
                implementation_depth_tier="heuristic_baseline",
            ),
            _entry(
                "survey.weighting.horvitz_thompson@1.0.0",
                family="survey.weighting",
                variant="horvitz_thompson",
                data_modalities=["survey"],
            ),
        ],
    )

    query = MethodAdvisorQuery(
        criteria=MethodSelectionCriteria(
            preferred_family="causal.treatment_effects",
            preferred_variant="tmle",
            minimum_fidelity_tier="high",
            required_data_modalities=("cross-section",),
        ),
        data=DataCharacteristics(n_obs=2_000),
        limit=2,
    )

    result = advise_methods(snapshot, query)

    assert [entry.fqn for entry in result.recommended] == [
        "causal.treatment_effects.tmle@1.0.0",
        "causal.treatment_effects.proxy_score@1.0.0",
    ]
    assert [row["fqn"] for row in result.payload] == [entry.fqn for entry in result.recommended]
    assert [row["fqn"] for row in result.capability_matrix] == [
        entry.fqn for entry in result.recommended
    ]
    assert result.capability_matrix[0]["truthfulness_tier"] == "exact"
    assert result.payload[0]["truthfulness_tier"] == "exact"
    assert result.payload[0]["implementation_depth_tier"] == "production_method"
    assert result.payload[0]["advisor_score"] > result.payload[1]["advisor_score"]
    assert (
        result.payload[0]["truthfulness_depth_score"]
        > result.payload[1]["truthfulness_depth_score"]
    )
    assert [item.fqn for item in result.score_trace] == [
        "causal.treatment_effects.tmle@1.0.0",
        "causal.treatment_effects.proxy_score@1.0.0",
    ]

    assert result.calibrated_regret_certificate is not None
    assert result.calibrated_regret_certificate.loss_profile_id == "balanced"
    assert result.calibrated_regret_certificate.tier_source == "static_catalog"
    assert result.calibrated_regret_certificate.status == "INSUFFICIENT_LOGGING"
    assert result.family_summary == (
        {
            "family": "causal.treatment_effects",
            "count": 2,
            "truthfulness_tiers": ["exact", "unverified"],
            "deepest_truthfulness_tier": "exact",
            "truthfulness_depth_score": 3,
            "implementation_depth_tiers": ["heuristic_baseline", "production_method"],
            "deepest_implementation_depth_tier": "production_method",
            "catalog_depth_score": 3,
            "frontier_method_count": 0,
        },
    )


def test_method_advisor_strict_phase5_blocks_missing_consensus() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "causal.treatment_effects.tmle@1.0.0",
                family="causal.treatment_effects",
                variant="tmle",
            )
        ],
    )
    query = MethodAdvisorQuery(
        criteria=MethodSelectionCriteria(preferred_family="causal.treatment_effects"),
        require_cross_method_consensus=True,
    )

    result = advise_methods(snapshot, query)

    assert result.recommended == ()
    assert result.cross_method_consensus is not None
    assert result.cross_method_consensus.status == "not_enough_methods"
    assert result.cross_method_consensus.recommendation_allowed is False


def test_method_advisor_prefers_production_depth_over_heuristic_baseline() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.evaluation.rigorous@1.0.0",
                family="policy.evaluation",
                variant="rigorous",
                truthfulness_tier="exact",
                implementation_depth_tier="production_method",
            ),
            _entry(
                "policy.evaluation.quick_proxy@1.0.0",
                family="policy.evaluation",
                variant="quick_proxy",
                truthfulness_tier="approximate_calibrated",
                implementation_depth_tier="heuristic_baseline",
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.evaluation",
                minimum_fidelity_tier="high",
                required_data_modalities=("cross-section",),
            ),
            data=DataCharacteristics(n_obs=2_000),
            limit=2,
        ),
    )

    assert [entry.fqn for entry in result.recommended] == [
        "policy.evaluation.rigorous@1.0.0",
        "policy.evaluation.quick_proxy@1.0.0",
    ]
    assert result.family_summary == (
        {
            "family": "policy.evaluation",
            "count": 2,
            "truthfulness_tiers": ["approximate_calibrated", "exact"],
            "deepest_truthfulness_tier": "exact",
            "truthfulness_depth_score": 3,
            "implementation_depth_tiers": ["heuristic_baseline", "production_method"],
            "deepest_implementation_depth_tier": "production_method",
            "catalog_depth_score": 3,
            "frontier_method_count": 0,
        },
    )


def test_method_advisor_certificate_marks_ambiguous_rank_when_gap_crosses_zero() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.choice.primary@1.0.0",
                family="policy.choice",
                variant="primary",
                truthfulness_tier="exact",
            ),
            _entry(
                "policy.choice.runner_up@1.0.0",
                family="policy.choice",
                variant="runner_up",
                truthfulness_tier="exact",
            ),
        ],
    )
    history = SelectionHistoryStore()
    now = time.time()
    for idx in range(4):
        history.record(
            MethodExecutionRecord(
                method_fqn="policy.choice.primary@1.0.0",
                timestamp=now + idx,
                latency_ms=40.0,
                success=True,
                candidate_fqns=(
                    "policy.choice.primary@1.0.0",
                    "policy.choice.runner_up@1.0.0",
                ),
                selected_rank=1,
                selection_propensity=0.5,
                realized_loss_components={"coverage_shortfall": 0.40, "failure_penalty": 0.0},
                shadow_loss_estimates={"policy.choice.runner_up@1.0.0": 0.15},
            )
        )
        history.record(
            MethodExecutionRecord(
                method_fqn="policy.choice.runner_up@1.0.0",
                timestamp=now + 100 + idx,
                latency_ms=45.0,
                success=True,
                candidate_fqns=(
                    "policy.choice.primary@1.0.0",
                    "policy.choice.runner_up@1.0.0",
                ),
                selected_rank=2,
                selection_propensity=0.5,
                realized_loss_components={"coverage_shortfall": 0.41, "failure_penalty": 0.0},
                shadow_loss_estimates={"policy.choice.primary@1.0.0": 0.14},
            )
        )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.choice"),
            limit=2,
        ),
        history=history,
    )

    cert = result.calibrated_regret_certificate
    assert cert is not None
    assert cert.status == "AMBIGUOUS_RANK"
    assert cert.ope_estimator == "shadow_replay"
    assert cert.top1_vs_top2_gap_cs is not None
    assert cert.top1_vs_top2_gap_cs.lower <= 0.0 <= cert.top1_vs_top2_gap_cs.upper


def test_method_advisor_applies_runtime_truthfulness_downgrade_from_history() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.runtime.posterior@1.0.0",
                family="policy.runtime",
                variant="posterior",
                truthfulness_tier="asymptotic",
                declared_truthfulness_tier="asymptotic",
            ),
            _entry(
                "policy.runtime.calibrated@1.0.0",
                family="policy.runtime",
                variant="calibrated",
                truthfulness_tier="approximate_calibrated",
                declared_truthfulness_tier="approximate_calibrated",
            ),
        ],
    )
    history = SelectionHistoryStore()
    now = time.time()
    history.record(
        MethodExecutionRecord(
            method_fqn="policy.runtime.posterior@1.0.0",
            timestamp=now,
            latency_ms=50.0,
            success=True,
            runtime_truthfulness_tier="unverified",
            effective_truthfulness_tier="unverified",
            truthfulness_status="runtime_downgraded",
            truthfulness_scope="posterior",
            truthfulness_evidence_ref="cas://truthfulness/posterior",
        )
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.runtime"),
            limit=2,
        ),
        history=history,
    )

    assert [entry.fqn for entry in result.recommended] == [
        "policy.runtime.calibrated@1.0.0",
        "policy.runtime.posterior@1.0.0",
    ]
    assert result.payload[1]["truthfulness_tier"] == "unverified"
    assert result.payload[1]["runtime_truthfulness_tier"] == "unverified"
    assert result.payload[1]["truthfulness_status"] == "runtime_downgraded"
    assert result.capability_matrix[1]["truthfulness_tier"] == "unverified"
    assert result.calibrated_regret_certificate is not None
    assert result.calibrated_regret_certificate.tier_source == "runtime_validated"


def test_method_advisor_uses_declared_hmc_and_nuts_truthfulness_before_runtime_history() -> None:
    ensure_all_methods_registered()
    full_snapshot = build_method_catalog_snapshot(run_id="R_phase0_truthfulness")
    snapshot = MethodCatalogSnapshot(
        snapshot_id="phase0-truthfulness",
        entries=tuple(
            entry
            for entry in full_snapshot.entries
            if entry.fqn
            in {
                "bayesian.sampling.hmc@1.0.0",
                "bayesian.sampling.nuts@1.0.0",
            }
        ),
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(runnable_only=False),
            data=DataCharacteristics(n_obs=1_000),
            limit=2,
            runnable_only=False,
        ),
    )

    assert {entry.fqn for entry in result.recommended} == {
        "bayesian.sampling.hmc@1.0.0",
        "bayesian.sampling.nuts@1.0.0",
    }
    for row in result.payload:
        assert row["truthfulness_tier"] == "asymptotic"
        assert row["declared_truthfulness_tier"] == "asymptotic"
        assert row["truthfulness_status"] == "catalog_only"


def test_method_advisor_builds_execution_context_with_full_candidate_slate() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.telemetry.primary@1.0.0",
                family="policy.telemetry",
                variant="primary",
                truthfulness_tier="exact",
            ),
            _entry(
                "policy.telemetry.alt@1.0.0",
                family="policy.telemetry",
                variant="alt",
                truthfulness_tier="approximate_calibrated",
            ),
            _entry(
                "policy.telemetry.fallback@1.0.0",
                family="policy.telemetry",
                variant="fallback",
                truthfulness_tier="unverified",
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.telemetry"),
            limit=2,
        ),
    )

    context = build_advisor_execution_context(
        result,
        selection_propensity=0.25,
        shadow_loss_estimates={"policy.telemetry.alt@1.0.0": 0.2},
    )

    assert context is not None
    assert context.loss_profile_id == "balanced"
    assert context.candidate_fqns == (
        "policy.telemetry.primary@1.0.0",
        "policy.telemetry.alt@1.0.0",
        "policy.telemetry.fallback@1.0.0",
    )
    assert context.selected_rank == 1
    assert context.selection_propensity == pytest.approx(0.25)
    assert set(context.advisor_score_vector) == set(context.candidate_fqns)
    assert context.shadow_loss_estimates["policy.telemetry.alt@1.0.0"] == pytest.approx(0.2)


def test_method_advisor_certificate_validates_separated_top1_rank() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.rank.safe@1.0.0",
                family="policy.rank",
                variant="safe",
                truthfulness_tier="exact",
            ),
            _entry(
                "policy.rank.risky@1.0.0",
                family="policy.rank",
                variant="risky",
                truthfulness_tier="exact",
            ),
        ],
    )
    history = SelectionHistoryStore()
    now = time.time()
    for idx in range(32):
        history.record(
            MethodExecutionRecord(
                method_fqn="policy.rank.safe@1.0.0",
                timestamp=now + idx,
                latency_ms=30.0,
                success=True,
                candidate_fqns=(
                    "policy.rank.safe@1.0.0",
                    "policy.rank.risky@1.0.0",
                ),
                selected_rank=1,
                selection_propensity=0.5,
                realized_loss_components={"coverage_shortfall": 0.05, "failure_penalty": 0.0},
                shadow_loss_estimates={"policy.rank.risky@1.0.0": 0.65},
            )
        )
        history.record(
            MethodExecutionRecord(
                method_fqn="policy.rank.risky@1.0.0",
                timestamp=now + 100 + idx,
                latency_ms=90.0,
                success=False,
                candidate_fqns=(
                    "policy.rank.safe@1.0.0",
                    "policy.rank.risky@1.0.0",
                ),
                selected_rank=2,
                selection_propensity=0.5,
                realized_loss_components={"coverage_shortfall": 0.80, "failure_penalty": 1.0},
                shadow_loss_estimates={"policy.rank.safe@1.0.0": 0.05},
            )
        )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.rank"),
            limit=2,
            loss_profile_id="coverage_strict",
        ),
        history=history,
    )

    cert = result.calibrated_regret_certificate
    assert cert is not None
    assert cert.loss_profile_id == "coverage_strict"
    assert cert.status == "VALID"
    assert cert.observed_regret_cs is not None
    assert cert.certified_regret_upper is not None
    assert cert.observed_regret_cs.upper <= cert.certified_regret_upper
    assert cert.top1_vs_top2_gap_cs is not None
    assert cert.top1_vs_top2_gap_cs.lower > 0.0


def test_method_advisor_cost_filter_excludes_over_budget_high_value_method() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="cost-filter",
        entries=[
            _entry(
                "policy.cost.expensive@1.0.0",
                family="policy.cost",
                variant="expensive",
                advisor_cost={
                    "estimated_total_ms": 160.0,
                    "upper_ms": 160.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.cost.feasible@1.0.0",
                family="policy.cost",
                variant="feasible",
                advisor_cost={
                    "estimated_total_ms": 40.0,
                    "upper_ms": 40.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.cost",
                preferred_variant="expensive",
            ),
            cost_policy="filter",
            cost_budget={"max_total_ms": 100.0},
            limit=2,
        ),
    )

    assert [entry.fqn for entry in result.recommended] == ["policy.cost.feasible@1.0.0"]
    assert result.advisor_optimization is not None
    assert result.advisor_optimization.status == "FILTERED"
    assert result.advisor_optimization.certificate is not None
    assert result.advisor_optimization.certificate.infeasible_method_ids == (
        "policy.cost.expensive@1.0.0",
    )
    assert result.payload[0]["cost_estimate"]["feasible"] is True


def test_pareto_advisor_returns_nondominated_budget_feasible_frontier() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="pareto",
        entries=[
            _entry(
                "policy.pareto.accurate@1.0.0",
                family="policy.pareto",
                variant="accurate",
                advisor_cost={
                    "estimated_total_ms": 50.0,
                    "upper_ms": 50.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.pareto.dominated@1.0.0",
                family="policy.pareto",
                variant="dominated",
                advisor_cost={
                    "estimated_total_ms": 80.0,
                    "upper_ms": 80.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.pareto.cheap@1.0.0",
                family="policy.pareto",
                variant="cheap",
                advisor_cost={
                    "estimated_total_ms": 10.0,
                    "upper_ms": 10.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.pareto",
                preferred_variant="accurate",
            ),
            cost_budget={"max_total_ms": 100.0},
            limit=3,
        ),
        value_policy=AdvisorValuePolicy(accuracy_weight=1.0),
    )

    assert optimization.success is True
    assert optimization.status == "PARETO_OPTIMAL"
    assert optimization.x == "policy.pareto.accurate@1.0.0"
    assert {score.method_id for score in optimization.pareto_front} == {
        "policy.pareto.accurate@1.0.0",
        "policy.pareto.cheap@1.0.0",
    }
    assert "policy.pareto.dominated@1.0.0" not in {
        score.method_id for score in optimization.pareto_front
    }
    assert all(score.spend_upper <= 100.0 for score in optimization.pareto_front)


def test_pareto_advisor_budget_certificate_records_exact_feasibility() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="certificate",
        entries=[
            _entry(
                "policy.cert.safe@1.0.0",
                family="policy.cert",
                variant="safe",
                advisor_cost={
                    "estimated_total_ms": 25.0,
                    "upper_ms": 30.0,
                    "bound_type": "EXACT_BOUND",
                    "estimator_version": "test-cost.v1",
                },
            ),
            _entry(
                "policy.cert.over@1.0.0",
                family="policy.cert",
                variant="over",
                advisor_cost={
                    "estimated_total_ms": 95.0,
                    "upper_ms": 120.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.cert",
                preferred_variant="safe",
            ),
            cost_budget={"max_total_ms": 100.0},
        ),
    )

    certificate = optimization.certificate
    assert certificate is not None
    assert certificate.feasible is True
    assert certificate.selected_method_id == "policy.cert.safe@1.0.0"
    assert certificate.estimated_cost_upper == pytest.approx(30.0)
    assert certificate.slack_lower_bound == pytest.approx(70.0)
    assert certificate.bound_type == "EXACT_BOUND"
    assert certificate.confidence == pytest.approx(1.0)
    assert certificate.cost_model_version == "test-cost.v1"


def test_pareto_advisor_heuristic_cost_estimate_downgrades_certificate() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="heuristic",
        entries=[
            _entry(
                "causal.dml.heuristic@1.0.0",
                family="causal.dml",
                variant="heuristic",
            ),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="causal.dml"),
            data=DataCharacteristics(n_obs=100),
            cost_budget={"max_total_ms": 1_000_000.0},
        ),
    )

    certificate = optimization.certificate
    assert certificate is not None
    assert certificate.bound_type == "HEURISTIC_POINT_ESTIMATE"
    assert certificate.confidence is None
    assert any("heuristic" in obligation for obligation in certificate.proof_obligations)


def test_cost_policy_ignore_preserves_legacy_advisor_ordering() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="ignore-compat",
        entries=[
            _entry("policy.compat.a@1.0.0", family="policy.compat", variant="a"),
            _entry("policy.compat.b@1.0.0", family="policy.compat", variant="b"),
        ],
    )
    query = MethodAdvisorQuery(
        criteria=MethodSelectionCriteria(
            preferred_family="policy.compat",
            preferred_variant="b",
        ),
        limit=2,
    )

    legacy = advise_methods(snapshot, query)
    explicit_ignore = advise_methods(snapshot, replace(query, cost_policy="ignore"))

    assert [entry.fqn for entry in legacy.recommended] == [
        entry.fqn for entry in explicit_ignore.recommended
    ]
    assert legacy.advisor_optimization is None
    assert explicit_ignore.advisor_optimization is None


def test_pareto_advisor_infeasible_budget_reports_relaxations() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="infeasible",
        entries=[
            _entry(
                "policy.infeasible.cheaper@1.0.0",
                family="policy.infeasible",
                variant="cheaper",
                advisor_cost={
                    "estimated_total_ms": 80.0,
                    "upper_ms": 90.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.infeasible.accurate@1.0.0",
                family="policy.infeasible",
                variant="accurate",
                advisor_cost={
                    "estimated_total_ms": 120.0,
                    "upper_ms": 140.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.infeasible",
                preferred_variant="accurate",
            ),
            cost_policy="pareto",
            cost_budget={"max_total_ms": 50.0},
        ),
    )

    optimization = result.advisor_optimization
    assert optimization is not None
    assert optimization.success is False
    assert optimization.status == "INFEASIBLE_BUDGET"
    assert result.recommended == ()
    assert optimization.diagnostics["min_required_budget_point"] == pytest.approx(80.0)
    assert optimization.diagnostics["min_required_budget_upper"] == pytest.approx(90.0)
    assert optimization.diagnostics["cheapest_candidate"] == "policy.infeasible.cheaper@1.0.0"
    assert optimization.diagnostics["highest_accuracy_over_budget_candidate"] == (
        "policy.infeasible.accurate@1.0.0"
    )
    relaxations = optimization.diagnostics["closest_feasible_relaxations"]
    assert relaxations[0]["method_id"] == "policy.infeasible.cheaper@1.0.0"
    assert relaxations[0]["required_budget"]["ms_limit"] == pytest.approx(90.0)


def test_pareto_advisor_multi_resource_budget_blocks_memory_overrun() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="multi-resource",
        entries=[
            _entry(
                "policy.resource.memory_hungry@1.0.0",
                family="policy.resource",
                variant="memory_hungry",
                advisor_cost={
                    "estimated_total_ms": 20.0,
                    "upper_ms": 20.0,
                    "estimated_memory_mb": 512.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
            _entry(
                "policy.resource.small@1.0.0",
                family="policy.resource",
                variant="small",
                advisor_cost={
                    "estimated_total_ms": 30.0,
                    "upper_ms": 30.0,
                    "estimated_memory_mb": 64.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(
                preferred_family="policy.resource",
                preferred_variant="memory_hungry",
            ),
            cost_policy="filter",
            cost_budget={"max_total_ms": 100.0, "max_memory_mb": 128.0},
            limit=2,
        ),
    )

    optimization = result.advisor_optimization
    assert optimization is not None
    assert [entry.fqn for entry in result.recommended] == ["policy.resource.small@1.0.0"]
    hungry = next(
        score
        for score in optimization.candidates
        if score.method_id == "policy.resource.memory_hungry@1.0.0"
    )
    assert hungry.feasible is False
    assert "memory_limit" in hungry.violations


def test_pareto_advisor_calibrated_probabilistic_certificate_confidence() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="calibrated-cost",
        entries=[
            _entry(
                "policy.calibrated.safe@1.0.0",
                family="policy.calibrated",
                variant="safe",
                advisor_cost={
                    "estimated_total_ms": 70.0,
                    "upper_ms": 85.0,
                    "bound_type": "CALIBRATED_PROBABILISTIC_BOUND",
                    "coverage_confidence": 0.95,
                    "calibration_scope": "unit-test",
                },
            )
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.calibrated"),
            cost_budget={"max_total_ms": 100.0},
            risk_delta=0.05,
        ),
    )

    certificate = optimization.certificate
    assert certificate is not None
    assert certificate.bound_type == "CALIBRATED_PROBABILISTIC_BOUND"
    assert certificate.confidence == pytest.approx(0.95)
    assert certificate.delta == pytest.approx(0.05)
    assert certificate.calibration_scope == "unit-test"


def test_robust_pareto_keeps_candidate_when_uncertainty_overlaps() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="robust-frontier",
        entries=[
            _entry(
                "policy.robust.nominal_winner@1.0.0",
                family="policy.robust",
                variant="nominal_winner",
                advisor_cost={
                    "estimated_total_ms": 40.0,
                    "lower_ms": 35.0,
                    "upper_ms": 45.0,
                    "bound_type": "CALIBRATED_PROBABILISTIC_BOUND",
                },
                advisor_accuracy={
                    "accuracy": 0.80,
                    "accuracy_lower": 0.70,
                    "accuracy_upper": 0.90,
                },
            ),
            _entry(
                "policy.robust.uncertain_alt@1.0.0",
                family="policy.robust",
                variant="uncertain_alt",
                advisor_cost={
                    "estimated_total_ms": 42.0,
                    "lower_ms": 39.0,
                    "upper_ms": 50.0,
                    "bound_type": "CALIBRATED_PROBABILISTIC_BOUND",
                },
                advisor_accuracy={
                    "accuracy": 0.78,
                    "accuracy_lower": 0.72,
                    "accuracy_upper": 0.88,
                },
            ),
        ],
    )

    point = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.robust"),
            cost_budget={"max_total_ms": 100.0},
            dominance_mode="point",
        ),
    )
    robust = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.robust"),
            cost_budget={"max_total_ms": 100.0},
            dominance_mode="robust",
        ),
    )

    assert {score.method_id for score in point.pareto_front} == {
        "policy.robust.nominal_winner@1.0.0"
    }
    assert {score.method_id for score in robust.pareto_front} == {
        "policy.robust.nominal_winner@1.0.0",
        "policy.robust.uncertain_alt@1.0.0",
    }


def test_pareto_advisor_no_cost_model_when_heuristics_disabled() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="no-cost-model",
        entries=[
            _entry("policy.no_cost.a@1.0.0", family="policy.no_cost", variant="a"),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.no_cost"),
            cost_budget={"max_total_ms": 100.0},
            allow_heuristic_cost_estimate=False,
        ),
    )

    assert optimization.success is False
    assert optimization.status == "NO_COST_MODEL"


def test_pareto_advisor_requires_declared_accuracy_when_requested() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="no-accuracy",
        entries=[
            _entry(
                "policy.no_accuracy.a@1.0.0",
                family="policy.no_accuracy",
                variant="a",
                advisor_cost={
                    "estimated_total_ms": 10.0,
                    "upper_ms": 10.0,
                    "bound_type": "EXACT_BOUND",
                },
            ),
        ],
    )

    optimization = pareto_advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.no_accuracy"),
            cost_budget={"max_total_ms": 100.0},
            require_declared_accuracy_estimate=True,
        ),
    )

    assert optimization.success is False
    assert optimization.status == "NO_ACCURACY_ESTIMATE"


def test_cross_method_consensus_passes_when_methods_agree() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method"},
        (
            _consensus_target("regression_adjusted", family="regression", point=0.20),
            _consensus_target("dml", family="double_ml", point=0.22),
        ),
    )

    assert consensus.status == "pass"
    assert consensus.recommendation_allowed is True
    assert consensus.global_cmd_score < 1.0
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.metric == "z_score"


def test_cross_method_consensus_refuses_and_classifies_isolated_family() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method"},
        (
            _consensus_target("regression_adjusted", family="regression", point=0.00),
            _consensus_target("dml", family="double_ml", point=0.02),
            _consensus_target("iv_2sls", family="iv", point=0.46),
        ),
    )

    assert consensus.status in {"refuse", "hard_refuse"}
    assert consensus.recommendation_allowed is False
    assert consensus.user_message == "Methods disagree, no recommendation."
    assert consensus.global_cmd_score > 1.0
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.adjusted_q_value is not None
    assert consensus.worst_pair.adjusted_q_value <= 0.01
    assert consensus.likely_misspecification.status == "likely_misspecified_family"
    assert consensus.likely_misspecification.likely_family == "iv"
    assert consensus.consensus_set == ("dml", "regression_adjusted")


def test_cross_method_consensus_marks_estimand_mismatch_not_disagreement() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method"},
        (
            _consensus_target(
                "one_week",
                family="prediction",
                point=0.10,
                estimand=_consensus_estimand(time_horizon="one_week"),
            ),
            _consensus_target(
                "one_month",
                family="prediction",
                point=0.40,
                estimand=_consensus_estimand(time_horizon="one_month"),
            ),
        ),
    )

    assert consensus.status == "not_comparable"
    assert consensus.recommendation_allowed is True
    assert consensus.likely_misspecification.status == "estimand_mismatch"
    assert consensus.global_cmd_score == 0.0


def test_cross_method_consensus_transforms_log_scale_before_comparing() -> None:
    identity_estimand = _consensus_estimand()
    log_estimand = replace(identity_estimand, scale="log")

    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method", "scale": "identity"},
        (
            _consensus_target(
                "identity_scale",
                family="regression",
                point=2.0,
                se=0.2,
                estimand=identity_estimand,
            ),
            ConsensusTarget(
                result_id="log_scale",
                method_family="bayesian",
                method_name="log_scale",
                estimand=log_estimand,
                target_kind="causal_effect",
                point=np.asarray([np.log(2.0)], dtype=float),
                covariance=np.asarray([[0.1 * 0.1]], dtype=float),
            ),
        ),
    )

    assert consensus.status == "pass"
    assert consensus.noncomparable_method_ids == ()
    assert all(
        check.estimand is not None and check.estimand.scale == "identity"
        for check in consensus.pairwise
        if check.comparable
    )
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.point_j == pytest.approx((2.0,))


def test_cross_method_consensus_warns_when_disagreement_is_not_decision_relevant() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method"},
        (
            _consensus_target("positive_a", family="regression", point=0.20, se=0.01),
            _consensus_target("positive_b", family="double_ml", point=0.50, se=0.01),
        ),
    )

    assert consensus.status == "warn"
    assert consensus.recommendation_allowed is True
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.adjusted_q_value is not None
    assert consensus.worst_pair.adjusted_q_value <= 0.01
    assert consensus.worst_pair.decision_relevant is False


def test_cross_method_consensus_refuses_statistical_conflict_in_strict_mode() -> None:
    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method", "strict_consensus_validation": True},
        (
            _consensus_target("positive_a", family="regression", point=0.20, se=0.01),
            _consensus_target("positive_b", family="double_ml", point=0.50, se=0.01),
        ),
    )

    assert consensus.status in {"refuse", "hard_refuse"}
    assert consensus.recommendation_allowed is False
    assert consensus.user_message == "Methods disagree, no recommendation."
    assert consensus.worst_pair is not None
    assert consensus.worst_pair.decision_relevant is True


def test_cross_method_consensus_runs_distributional_diagnostics() -> None:
    central = np.linspace(-1.0, 1.0, 80, dtype=float).reshape(-1, 1)
    split_tail = np.concatenate(
        [
            np.linspace(-4.0, -3.0, 40, dtype=float),
            np.linspace(3.0, 4.0, 40, dtype=float),
        ]
    ).reshape(-1, 1)

    consensus = run_cross_method_consensus(
        {"query_id": "q-cross-method", "strict_consensus_validation": True},
        (
            ConsensusTarget(
                result_id="central_predictive",
                method_family="prediction",
                method_name="central_predictive",
                estimand=_consensus_estimand(),
                target_kind="causal_effect",
                point=np.asarray([0.0], dtype=float),
                covariance=np.asarray([[1.0]], dtype=float),
                samples=central,
            ),
            ConsensusTarget(
                result_id="tail_predictive",
                method_family="prediction",
                method_name="tail_predictive",
                estimand=_consensus_estimand(),
                target_kind="causal_effect",
                point=np.asarray([0.0], dtype=float),
                covariance=np.asarray([[1.0]], dtype=float),
                samples=split_tail,
            ),
        ),
        distribution_permutations=399,
    )

    distribution_checks = [
        check for check in consensus.pairwise if check.projection == "distribution"
    ]
    assert distribution_checks
    assert distribution_checks[0].metric == "energy_distance"
    assert distribution_checks[0].adjusted_q_value is not None
    assert distribution_checks[0].adjusted_q_value <= 0.01
    assert consensus.status == "refuse"
    assert consensus.recommendation_allowed is False


def test_method_advisor_suppresses_recommendations_when_consensus_refuses() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry(
                "policy.consensus.primary@1.0.0",
                family="policy.consensus",
                variant="primary",
                truthfulness_tier="exact",
            ),
            _entry(
                "policy.consensus.alt@1.0.0",
                family="policy.consensus",
                variant="alt",
                truthfulness_tier="exact",
            ),
        ],
    )

    result = advise_methods(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.consensus"),
            limit=2,
        ),
        consensus_results=(
            _consensus_target("primary_output", family="regression", point=0.0),
            _consensus_target("alt_output", family="iv", point=0.40),
        ),
    )

    assert result.cross_method_consensus is not None
    assert result.cross_method_consensus.status == "refuse"
    assert result.recommended == ()
    assert result.payload == ()
    assert [item.fqn for item in result.score_trace] == [
        "policy.consensus.alt@1.0.0",
        "policy.consensus.primary@1.0.0",
    ]


def test_analyst_advisor_requires_strict_cross_method_consensus() -> None:
    snapshot = MethodCatalogSnapshot(
        snapshot_id="snapshot",
        entries=[
            _entry("policy.strict.primary@1.0.0", family="policy.strict", variant="primary"),
            _entry("policy.strict.alt@1.0.0", family="policy.strict", variant="alt"),
        ],
    )

    result = advise_methods_for_analyst(
        snapshot,
        MethodAdvisorQuery(
            criteria=MethodSelectionCriteria(preferred_family="policy.strict"),
            limit=2,
        ),
        consensus_results=(_consensus_target("primary_output", family="regression", point=0.0),),
    )

    assert result.query.require_cross_method_consensus is True
    assert result.query.cost_policy == "annotate"
    assert result.cross_method_consensus is not None
    assert result.cross_method_consensus.status == "not_enough_methods"
    assert result.cross_method_consensus.recommendation_allowed is False
    assert result.recommended == ()
