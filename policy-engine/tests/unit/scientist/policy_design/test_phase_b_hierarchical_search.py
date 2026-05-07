from __future__ import annotations

from polisyos.scientist.policy_design.objectives import ObjectiveStack, PolicyEvaluationBundle
from polisyos.scientist.policy_design.output import (
    ChampionPolicyDossier,
    ConstraintSatisfactionEntry,
    ConstraintSatisfactionReport,
    SubgroupImpactReport,
    UncertaintyReport,
)
from polisyos.scientist.policy_design.schema import FallbackVariant
from polisyos.scientist.policy_design.search import (
    HierarchicalSearchConfig,
    HierarchicalSearchCoordinator,
)
from polisyos.scientist.policy_design.translator import TranslatorInputBundle
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
from polisyos.scientist.methods.search.readiness import DecisionReadiness, DecisionReadinessContract
from polisyos.scientist.methods.search.transfer_context import TransferContext

from .test_phase_b_output import _candidate, _evaluation_vector


def test_generate_structure_candidates_includes_deterministic_variants() -> None:
    candidate = _candidate()
    fallback = candidate.model_copy(update={"candidate_id": "candidate_policy_fallback"})
    candidate = candidate.model_copy(
        update={
            "fallback_variants": [
                FallbackVariant(
                    variant_id="fallback_1",
                    trinity_bundle=fallback.trinity_bundle,
                    notes=[],
                )
            ]
        }
    )
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(enable_hybrid_seeds=False)
    )

    structures = coordinator.generate_structure_candidates(candidate)

    assert any(item.source == "deterministic_base" for item in structures)
    assert any(item.source == "fallback_variant" for item in structures)
    assert any(item.source == "rollout_mutation" for item in structures)


def test_build_parameter_search_spec_extracts_bounds_and_paths() -> None:
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(enable_hybrid_seeds=False)
    )
    spec = coordinator.build_parameter_search_spec(_candidate())

    assert "tax_rate" in spec.parameter_paths
    assert any(
        bound.name == "tax_rate" and bound.lower == 0.05 and bound.upper == 0.2
        for bound in spec.search_space.bounds
    )
    assert any(bound.name.startswith("schedule::") for bound in spec.search_space.bounds)


def test_build_optimizer_objective_spec_derives_multi_objective_surface() -> None:
    candidate = _candidate()
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(enable_hybrid_seeds=False)
    )

    spec = coordinator.build_optimizer_objective_spec(candidate)
    template = ObjectiveStack().evaluate(PolicyEvaluationBundle(candidate=candidate))
    expected_names = list(
        dict.fromkeys(
            [
                *template.primary.keys(),
                *template.secondary.keys(),
                *template.penalties.keys(),
            ]
        )
    )

    assert spec.objective_names == expected_names
    assert len(spec.constraint_extractors) == len(template.hard_constraints)
    assert set(spec.frontier_projection_names) == set(
        template.frontier_objectives("global_feasible")
    )


def test_parameter_search_updates_shared_pareto_registry(tmp_path) -> None:
    candidate = _candidate()
    registry = ParetoRegistry(tmp_path / "registry")
    coordinator = HierarchicalSearchCoordinator(
        pareto_registry=registry,
        config=HierarchicalSearchConfig(enable_hybrid_seeds=False, max_parameter_iterations=3),
    )
    structure = coordinator.generate_structure_candidates(candidate)[0]

    result = coordinator.run_parameter_search(
        structure,
        loop_id="loop_search",
        stage_b_evaluator=lambda candidate_payload, context: {
            "simulation_results": {
                "gdp_change": float(
                    candidate_payload["trinity_bundle"]["policy_spec"]["interventions"][0][
                        "params"
                    ]["rate"]
                )
            },
            "policy_evaluation": _evaluation_vector(structure.candidate).model_dump(mode="json"),
        },
    )

    snapshot = registry.get_snapshot("loop_search")
    assert result.iterations_completed >= 1
    assert snapshot.entries
    assert snapshot.frontiers["global_feasible"]


def test_parameter_search_uses_transfer_warm_start_without_mixing_seed_only_entries(
    tmp_path,
) -> None:
    candidate = _candidate()
    registry = ParetoRegistry(tmp_path / "registry")
    registry.update(
        "loop_source",
        candidate_hash=f"{candidate.candidate_hash()}::seed",
        evaluation=_evaluation_vector(candidate).model_copy(
            update={"candidate_id": "seed_candidate"}
        ),
        candidate_id="seed_candidate",
        policy_family="core_family",
        seed_payload=candidate.model_dump(mode="json"),
        transfer_context=TransferContext(
            task_family="policy",
            domain="fiscal",
            run_id="loop_source",
            tenant_hash="tenant-a",
        ),
    )
    coordinator = HierarchicalSearchCoordinator(
        pareto_registry=registry,
        config=HierarchicalSearchConfig(enable_hybrid_seeds=False, max_parameter_iterations=2),
    )
    structure = coordinator.generate_structure_candidates(candidate)[0]

    result = coordinator.run_parameter_search(
        structure,
        loop_id="loop_target",
        initial_context={"domain": "labor", "tenant_hash": "tenant-a"},
        stage_b_evaluator=lambda candidate_payload, context: {
            "simulation_results": {"gdp_change": 0.1},
            "policy_evaluation": _evaluation_vector(structure.candidate).model_dump(mode="json"),
        },
    )

    snapshot = registry.get_snapshot("loop_target")
    assert result.telemetry["frontier_seed_count"] >= 1
    assert result.telemetry["cross_domain_seed_count"] >= 1
    assert snapshot.entries
    assert all(entry.seed_only is False for entry in snapshot.entries.values())


def test_parameter_search_does_not_promote_infeasible_candidates_to_feasible_frontier(
    tmp_path,
) -> None:
    candidate = _candidate()
    registry = ParetoRegistry(tmp_path / "registry")
    coordinator = HierarchicalSearchCoordinator(
        pareto_registry=registry,
        config=HierarchicalSearchConfig(enable_hybrid_seeds=False, max_parameter_iterations=2),
    )
    structure = coordinator.generate_structure_candidates(candidate)[0]

    infeasible_vector = _evaluation_vector(structure.candidate).model_copy(
        update={
            "feasible": False,
            "blocking_reasons": ["budget_cap"],
        }
    )
    result = coordinator.run_parameter_search(
        structure,
        loop_id="loop_infeasible",
        stage_b_evaluator=lambda candidate_payload, context: {
            "simulation_results": {"gdp_change": 0.1},
            "policy_evaluation": infeasible_vector.model_dump(mode="json"),
        },
    )

    snapshot = registry.get_snapshot("loop_infeasible")
    assert result.iterations_completed >= 1
    assert snapshot.entries
    assert snapshot.frontiers["global_feasible"] == []
    assert all(entry.evaluation.feasible is False for entry in snapshot.entries.values())


def test_generate_structure_candidates_marks_degraded_hybrid_seeds_when_gateway_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "polisyos.scientist.policy_design.search.create_traced_gateway_client",
        lambda **kwargs: None,
    )
    candidate = _candidate()
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(enable_hybrid_seeds=True, max_hybrid_seeds=2),
    )

    structures = coordinator.generate_structure_candidates(candidate)
    hybrid = [item for item in structures if item.source == "hybrid_seed_degraded"]

    assert hybrid
    assert len(hybrid) <= 2
    assert len({item.candidate_hash for item in hybrid}) == len(hybrid)
    assert all(item.metadata["hybrid_gateway_available"] is False for item in hybrid)
    assert all(item.metadata["hybrid_degraded_reason"] == "gateway_unavailable" for item in hybrid)
    assert any(
        item.candidate.transport_assumptions or item.candidate.evidence_assumptions
        for item in hybrid
    )


def test_narrative_search_does_not_mutate_readiness_or_frontier(tmp_path) -> None:
    candidate = _candidate()
    registry = ParetoRegistry(tmp_path / "registry")
    coordinator = HierarchicalSearchCoordinator(
        pareto_registry=registry,
        config=HierarchicalSearchConfig(enable_hybrid_seeds=False),
    )
    readiness = DecisionReadinessContract(
        readiness_level=DecisionReadiness.RECOMMENDATION_READY,
        required_judges_passed=["structural"],
        required_uncertainty_bounds={},
        mandatory_human_gate=False,
        assumptions_must_be_surfaced=["Elasticity remains stable in the policy horizon."],
        expiry_conditions=["freshness_violation"],
        evidence_depth_required="replicated",
    )
    bundle = TranslatorInputBundle(
        dossier=ChampionPolicyDossier(
            candidate_id=candidate.candidate_id,
            candidate_hash=candidate.candidate_hash(),
            readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
            executive_summary="Candidate candidate_policy is assessed at recommendation_ready.",
            objective_summary={"policy_value": 1.0},
            constraint_summary=[
                ConstraintSatisfactionEntry(
                    constraint_name="policy_budget_constraint",
                    status="near_binding",
                )
            ],
            subgroup_harms=[],
            surfaced_assumptions=readiness.assumptions_must_be_surfaced,
            uncertainty_summary={"statistical": 0.2},
            transport_summary={},
            governance_summary={},
            stress_summary={},
        ),
        readiness_contract=readiness,
        constraint_report=ConstraintSatisfactionReport(
            candidate_id=candidate.candidate_id,
            feasible=True,
            constraints=[
                ConstraintSatisfactionEntry(
                    constraint_name="policy_budget_constraint",
                    status="near_binding",
                )
            ],
        ),
        subgroup_report=SubgroupImpactReport(candidate_id=candidate.candidate_id),
        uncertainty_report=UncertaintyReport(
            candidate_id=candidate.candidate_id,
            readiness_level=DecisionReadiness.RECOMMENDATION_READY.value,
            uncertainties={"statistical": 0.2},
            binding_types=[],
        ),
    )

    before = registry.get_snapshot("loop_narrative")
    variants = coordinator.run_narrative_search([(candidate.candidate_hash(), bundle)])
    after = registry.get_snapshot("loop_narrative")

    assert variants
    assert bundle.readiness_contract.readiness_level == DecisionReadiness.RECOMMENDATION_READY
    assert before.entries == after.entries
