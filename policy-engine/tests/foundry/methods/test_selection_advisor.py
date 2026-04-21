from __future__ import annotations

import time

import pytest

from polisyos.core.contracts.execution_plan import MethodCatalogEntry, MethodCatalogSnapshot
from polisyos.foundry.methods.catalog import ensure_all_methods_registered
from polisyos.foundry.methods.catalog_snapshot import build_method_catalog_snapshot
from polisyos.foundry.methods.selection import (
    DataCharacteristics,
    MethodAdvisorQuery,
    MethodSelectionCriteria,
    advise_methods,
    build_advisor_execution_context,
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
    assert [row["fqn"] for row in result.capability_matrix] == [entry.fqn for entry in result.recommended]
    assert result.capability_matrix[0]["truthfulness_tier"] == "exact"
    assert result.payload[0]["truthfulness_tier"] == "exact"
    assert result.payload[0]["implementation_depth_tier"] == "production_method"
    assert result.payload[0]["advisor_score"] > result.payload[1]["advisor_score"]
    assert result.payload[0]["truthfulness_depth_score"] > result.payload[1]["truthfulness_depth_score"]
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
            if entry.fqn in {
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
