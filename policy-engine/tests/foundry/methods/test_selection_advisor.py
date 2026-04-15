from __future__ import annotations

from polisyos.core.contracts.execution_plan import MethodCatalogEntry, MethodCatalogSnapshot
from polisyos.foundry.methods.selection import (
    DataCharacteristics,
    MethodAdvisorQuery,
    MethodSelectionCriteria,
    advise_methods,
)


def _entry(
    fqn: str,
    *,
    family: str,
    variant: str,
    execution_backend: str = "numpy",
    runnable: bool = True,
    truthfulness_tier: str = "production_method",
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
                truthfulness_tier="production_method",
            ),
            _entry(
                "causal.treatment_effects.proxy_score@1.0.0",
                family="causal.treatment_effects",
                variant="proxy_score",
                truthfulness_tier="heuristic_baseline",
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
    assert result.capability_matrix[0]["truthfulness_tier"] == "production_method"
    assert result.payload[0]["truthfulness_tier"] == "production_method"
    assert result.payload[0]["truthfulness_depth_score"] > result.payload[1]["truthfulness_depth_score"]
    assert result.family_summary == (
        {
            "family": "causal.treatment_effects",
            "count": 2,
            "truthfulness_tiers": ["heuristic_baseline", "production_method"],
            "deepest_truthfulness_tier": "production_method",
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
                truthfulness_tier="production_method",
            ),
            _entry(
                "policy.evaluation.quick_proxy@1.0.0",
                family="policy.evaluation",
                variant="quick_proxy",
                truthfulness_tier="heuristic_baseline",
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
            "truthfulness_tiers": ["heuristic_baseline", "production_method"],
            "deepest_truthfulness_tier": "production_method",
            "catalog_depth_score": 3,
            "frontier_method_count": 0,
        },
    )
