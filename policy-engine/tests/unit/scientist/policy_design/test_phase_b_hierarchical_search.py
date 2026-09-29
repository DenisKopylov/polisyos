from __future__ import annotations

import pytest

from polisyos.scientist.methods.search.pareto_registry import ParetoRegistry
from polisyos.scientist.methods.search.readiness import DecisionReadiness, DecisionReadinessContract
from polisyos.scientist.methods.search.transfer_context import TransferContext
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    ObjectiveStack,
    PolicyEvaluationBundle,
    PolicyEvaluationRankStatus,
    PolicyEvaluationVector,
    assess_policy_evaluation_rank,
)
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
    _run_blueprint_parameter_search,
)
from polisyos.scientist.policy_design.translator import TranslatorInputBundle

from .test_phase_b_output import _candidate, _evaluation_vector


def test_policy_rank_assessment_marks_non_finite_channels_and_derived_coordinates() -> None:
    evaluation = _evaluation_vector(_candidate())
    policy_value = evaluation.primary["policy_value"].model_copy(update={"value": float("inf")})
    invalid = evaluation.model_copy(update={"primary": {"policy_value": policy_value}})

    assessment = assess_policy_evaluation_rank(
        invalid,
        candidate_id="candidate_non_finite",
        rank_coordinates={
            "rank.policy_value": float("inf"),
            "rank.welfare_plus_employment": 1e308 + 1e308,
        },
    )

    assert assessment.status is PolicyEvaluationRankStatus.UNASSESSED
    assert assessment.candidate_id == "candidate_non_finite"
    assert assessment.rank_key is None
    issues = {item.coordinate_id: item.reason for item in assessment.invalid_coordinates}
    assert issues["primary.policy_value.value"] == "non_finite"
    assert issues["rank.policy_value"] == "non_finite"
    assert issues["rank.welfare_plus_employment"] == "non_finite"


def test_policy_rank_assessment_marks_missing_required_axis_unassessed() -> None:
    evaluation = _evaluation_vector(_candidate())

    assessment = assess_policy_evaluation_rank(
        evaluation,
        rank_coordinates={"rank.policy_value": 1.0},
        required_channel_ids=("employment",),
    )

    assert assessment.status is PolicyEvaluationRankStatus.UNASSESSED
    assert assessment.candidate_id == evaluation.candidate_id
    assert assessment.rank_key is None
    assert {
        (issue.coordinate_id, issue.reason) for issue in assessment.invalid_coordinates
    } == {("objective.employment", "missing")}


def _rankable_evaluation(candidate_id: str) -> PolicyEvaluationVector:
    baseline = _evaluation_vector(_candidate())
    primary = dict(baseline.primary)
    primary.update(
        {
            name: ObjectiveChannelValue(
                name=name,
                kind=ObjectiveKind.PRIMARY,
                value=value,
                direction=ObjectiveDirection.MAXIMIZE,
            )
            for name, value in (("welfare", 1.0), ("employment", 1.0))
        }
    )
    return baseline.model_copy(
        update={"candidate_id": candidate_id, "primary": primary}
    )


def test_blueprint_ranking_excludes_non_finite_rows_independent_of_input_order() -> None:
    candidate = _candidate()
    baseline = _rankable_evaluation("rankable_base")
    finite = baseline.model_copy(update={"candidate_id": "finite_candidate"})
    policy_value = baseline.primary["policy_value"]
    positive_infinity = baseline.model_copy(
        update={
            "candidate_id": "infinite_candidate",
            "primary": {"policy_value": policy_value.model_copy(update={"value": float("inf")})},
        }
    )
    nan = baseline.model_copy(
        update={
            "candidate_id": "nan_candidate",
            "primary": {"policy_value": policy_value.model_copy(update={"value": float("nan")})},
        }
    )

    def _warm_start(
        candidate_id: str,
        evaluation: PolicyEvaluationVector,
    ) -> dict[str, object]:
        return {
            "candidate": {"candidate_id": candidate_id},
            "stage_b_result": {
                "policy_evaluation": evaluation.model_dump(mode="python"),
            },
        }

    for invalid_id, invalid in (
        ("infinite_candidate", positive_infinity),
        ("nan_candidate", nan),
    ):
        for initial_evaluations in (
            [_warm_start(invalid_id, invalid), _warm_start("finite_candidate", finite)],
            [_warm_start("finite_candidate", finite), _warm_start(invalid_id, invalid)],
        ):
            result = _run_blueprint_parameter_search(
                loop_id="finite_rank_probe",
                adapter=object(),
                max_iterations=0,
                stage_b_evaluator=lambda *_: {},
                stage_a_evaluator=lambda *_: (0.0, True),
                context={},
                initial_evaluations=initial_evaluations,
            )

            assert result.best_candidate == {"candidate_id": "finite_candidate"}
            unassessed = result.telemetry["unassessed_policy_evaluation_ranks"]
            assert [item["candidate_id"] for item in unassessed] == [invalid_id]
            assert unassessed[0]["invalid_coordinates"]


def test_blueprint_ranking_keeps_finite_winner_stable_under_permutation() -> None:
    candidate = _candidate()
    baseline = _rankable_evaluation("rankable_base")
    lower = baseline.model_copy(
        update={
            "candidate_id": "lower_candidate",
            "primary": {
                "policy_value": baseline.primary["policy_value"].model_copy(update={"value": 1.0})
            },
        }
    )
    higher = baseline.model_copy(
        update={
            "candidate_id": "higher_candidate",
            "primary": {
                "policy_value": baseline.primary["policy_value"].model_copy(update={"value": 2.0})
            },
        }
    )

    def _warm_start(
        candidate_id: str,
        evaluation: PolicyEvaluationVector,
    ) -> dict[str, object]:
        return {
            "candidate": {"candidate_id": candidate_id},
            "stage_b_result": {"policy_evaluation": evaluation.model_dump(mode="python")},
        }

    for initial_evaluations in (
        [
            _warm_start("lower_candidate", lower),
            _warm_start("higher_candidate", higher),
        ],
        [
            _warm_start("higher_candidate", higher),
            _warm_start("lower_candidate", lower),
        ],
    ):
        result = _run_blueprint_parameter_search(
            loop_id="finite_rank_control",
            adapter=object(),
            max_iterations=0,
            stage_b_evaluator=lambda *_: {},
            stage_a_evaluator=lambda *_: (0.0, True),
            context={},
            initial_evaluations=initial_evaluations,
        )

        assert result.best_candidate == {"candidate_id": "higher_candidate"}


def test_blueprint_keeps_malformed_present_distinct_from_missing_policy_evaluation() -> None:
    def _evaluate(stage_b_result: dict[str, object]):
        adapter = type(
            "StaticAdapter",
            (),
            {"generate": lambda self, *_: {"candidate_id": "candidate", "x": 0.5}},
        )()
        return _run_blueprint_parameter_search(
            loop_id="evaluation_status_probe",
            adapter=adapter,
            max_iterations=1,
            stage_b_evaluator=lambda *_: stage_b_result,
            stage_a_evaluator=lambda *_: (0.0, True),
            context={},
            initial_evaluations=[],
        )

    malformed = _evaluate(
        {
            "policy_evaluation": {"primary": "malformed"},
            "feedback": {"verdict": "APPROVE"},
        }
    )
    absent = _evaluate({"feedback": {"verdict": "APPROVE"}})

    assert malformed.best_candidate is None
    assert malformed.history[0].policy_evaluation_status == "invalid"
    assert malformed.history[0].policy_evaluation_error == "policy_evaluation_parse_failed"
    assert absent.history[0].policy_evaluation_status == "missing"
    assert absent.history[0].policy_evaluation_error is None


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
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            require_explicit_parameter_bounds=False,
            allow_legacy_shadow_inferred_bounds=True,
        )
    )

    structures = coordinator.generate_structure_candidates(candidate)

    assert any(item.source == "deterministic_base" for item in structures)
    assert any(item.source == "fallback_variant" for item in structures)
    assert any(item.source == "rollout_mutation" for item in structures)


def test_build_parameter_search_spec_extracts_bounds_and_paths() -> None:
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            require_explicit_parameter_bounds=False,
            allow_legacy_shadow_inferred_bounds=True,
        )
    )
    spec = coordinator.build_parameter_search_spec(_candidate())

    assert "tax_rate" in spec.parameter_paths
    assert any(
        bound.name == "tax_rate" and bound.lower == 0.05 and bound.upper == 0.2
        for bound in spec.search_space.bounds
    )
    assert any(bound.name.startswith("schedule::") for bound in spec.search_space.bounds)


def test_explicit_schedule_search_reuses_referenced_parameter_bounds() -> None:
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            require_explicit_parameter_bounds=True,
        )
    )

    spec = coordinator.build_parameter_search_spec(_candidate())

    assert any(
        bound.name == "schedule::schedule_tax_rate"
        and bound.lower == 0.05
        and bound.upper == 0.2
        for bound in spec.search_space.bounds
    )


def test_phase2_parameter_search_blocks_missing_explicit_bounds() -> None:
    candidate = _candidate()
    parameter = candidate.trinity_bundle.policy_spec.parameters[0].model_copy(
        update={"min_value": None, "max_value": None}
    )
    policy_spec = candidate.trinity_bundle.policy_spec.model_copy(
        update={"parameters": [parameter]}
    )
    candidate = candidate.model_copy(
        update={
            "trinity_bundle": candidate.trinity_bundle.model_copy(
                update={"policy_spec": policy_spec}
            ),
            "parameter_schedule": [],
        }
    )
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            require_explicit_parameter_bounds=True,
        )
    )

    with pytest.raises(ValueError, match="no default zero may be used"):
        coordinator.build_parameter_search_spec(candidate)


def test_default_parameter_search_blocks_missing_bounds_instead_of_inference() -> None:
    candidate = _candidate()
    parameter = candidate.trinity_bundle.policy_spec.parameters[0].model_copy(
        update={"min_value": None, "max_value": None}
    )
    policy_spec = candidate.trinity_bundle.policy_spec.model_copy(
        update={"parameters": [parameter]}
    )
    candidate = candidate.model_copy(
        update={
            "trinity_bundle": candidate.trinity_bundle.model_copy(
                update={"policy_spec": policy_spec}
            ),
            "parameter_schedule": [],
        }
    )
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(enable_hybrid_seeds=False)
    )

    with pytest.raises(ValueError, match="no default zero may be used"):
        coordinator.build_parameter_search_spec(candidate)


def test_legacy_inferred_bounds_require_explicit_shadow_opt_in() -> None:
    coordinator = HierarchicalSearchCoordinator(
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            require_explicit_parameter_bounds=False,
        )
    )

    with pytest.raises(ValueError, match="legacy-shadow/candidate-only"):
        coordinator.build_parameter_search_spec(_candidate())


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
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            max_parameter_iterations=3,
            require_explicit_parameter_bounds=False,
            allow_legacy_shadow_inferred_bounds=True,
        ),
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


def test_parameter_search_registry_intake_keeps_nonfinite_full_vector_unassessed(
    tmp_path,
) -> None:
    candidate = _candidate()
    registry = ParetoRegistry(tmp_path / "registry")
    coordinator = HierarchicalSearchCoordinator(
        pareto_registry=registry,
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            max_parameter_iterations=1,
            require_explicit_parameter_bounds=False,
            allow_legacy_shadow_inferred_bounds=True,
        ),
    )
    structure = coordinator.generate_structure_candidates(candidate)[0]
    template = _evaluation_vector(structure.candidate)
    non_finite_channel = ObjectiveChannelValue(
        name="registry_only_quality",
        kind=ObjectiveKind.SECONDARY,
        value=float("inf"),
        direction=ObjectiveDirection.MAXIMIZE,
    )
    invalid_evaluation = template.model_copy(
        update={"secondary": {**template.secondary, non_finite_channel.name: non_finite_channel}}
    )

    result = coordinator.run_parameter_search(
        structure,
        loop_id="loop_nonfinite_registry_intake",
        stage_b_evaluator=lambda *_: {
            "simulation_results": {"gdp_change": 0.1},
            "policy_evaluation": invalid_evaluation.model_dump(mode="python"),
        },
    )
    snapshot = registry.get_snapshot("loop_nonfinite_registry_intake")
    view = snapshot.view_assessments["global_feasible"]

    assert result.iterations_completed == 1
    assert snapshot.entries
    assert snapshot.frontiers["global_feasible"] == []
    assert view.assessed_count == 0
    assert set(view.unassessed_candidate_hashes) == set(snapshot.entries)
    assert any(
        "secondary.registry_only_quality.value" in coordinates
        for coordinates in view.non_finite_coordinate_ids_by_candidate_hash.values()
    )


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
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            max_parameter_iterations=2,
            require_explicit_parameter_bounds=False,
            allow_legacy_shadow_inferred_bounds=True,
        ),
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
        config=HierarchicalSearchConfig(
            enable_hybrid_seeds=False,
            max_parameter_iterations=2,
            require_explicit_parameter_bounds=False,
            allow_legacy_shadow_inferred_bounds=True,
        ),
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
