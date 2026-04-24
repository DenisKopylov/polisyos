from __future__ import annotations

from polisyos.scientist.search.strategies.advanced_policy import (
    AdvancedSearchPolicyConfig,
    AdvancedSearchPolicyRolloutStatus,
    ASHAScheduler,
    BOHBSampler,
    CMAESExplorer,
    ConstraintSpec,
    ExplicitConstraintPropagator,
    GaussianProcessCheapStageSurrogate,
    LearnedRoutingPolicy,
    LearnedVOIPolicy,
    PopulationBasedTrainingScheduler,
    PopulationMember,
    RoutingTrainingExample,
    VOITrainingExample,
    build_advanced_search_policy_report,
)
from polisyos.scientist.search.strategies.space import SearchSpace
from polisyos.scientist.search.strategies.types import (
    Evaluation,
    EvaluationStatus,
    ParameterBounds,
)


def _space() -> SearchSpace:
    return SearchSpace([ParameterBounds(name="x", lower=0.0, upper=1.0)])


def _eval(candidate_id: str, score: float, fidelity: int, x: float) -> Evaluation:
    return Evaluation(
        candidate_id=candidate_id,
        params={"x": x},
        params_normalized=(x,),
        objectives=[],
        scalar_score=score,
        stage_a_passed=True,
        status=EvaluationStatus.SUCCESS,
        metadata={"fidelity": fidelity},
    )


def test_advanced_policy_report_blocks_default_enable_without_offline_gate() -> None:
    report = build_advanced_search_policy_report(
        AdvancedSearchPolicyConfig(enable_bohb=True, default_enable_requested=True)
    )

    assert report.offline_gate_passed is False
    assert report.default_enable_eligible is False
    assert report.rollout_status == AdvancedSearchPolicyRolloutStatus.OFFLINE_GATED
    assert "missing_offline_validation_ref" in report.default_enable_blockers


def test_advanced_policy_report_marks_baseline_only_when_only_safe_policy_is_enabled() -> None:
    report = build_advanced_search_policy_report(
        AdvancedSearchPolicyConfig(enable_constraint_propagation=True)
    )

    assert report.rollout_status == AdvancedSearchPolicyRolloutStatus.BASELINE_ONLY
    assert report.default_enable_eligible is False


def test_constraints_are_propagated_before_expensive_stage() -> None:
    propagator = ExplicitConstraintPropagator(
        [
            ConstraintSpec(
                name="budget",
                metric_key="cost",
                comparator="<=",
                threshold=10.0,
                rationale="Budget must fit deployment cap.",
            )
        ]
    )

    result = propagator.evaluate("candidate-a", {"cost": 12.5})

    assert result.feasible is False
    assert result.blockers == ["budget"]
    assert result.penalty > 0


def test_asha_promotes_only_top_rung_candidates() -> None:
    evaluations = [
        _eval("a", 0.9, 1, 0.1),
        _eval("b", 0.7, 1, 0.2),
        _eval("c", 0.1, 1, 0.3),
    ]

    scheduler = ASHAScheduler(eta=3, max_fidelity=9)
    best = scheduler.decide(evaluations, evaluations[0])
    worst = scheduler.decide(evaluations, evaluations[-1])

    assert best.action == "promote"
    assert best.next_fidelity == 3
    assert worst.action == "stop"


def test_bohb_cma_and_gp_surrogate_are_deterministic_and_bounded() -> None:
    space = _space()
    evaluations = [
        _eval("a", 0.2, 1, 0.1),
        _eval("b", 0.9, 1, 0.8),
        _eval("c", 0.7, 1, 0.7),
        _eval("d", 0.1, 1, 0.0),
    ]

    bohb = BOHBSampler(space, seed=7)
    bohb_candidates = bohb.suggest_batch(evaluations, 3)
    assert len(bohb_candidates) == 3
    assert all(0.0 <= item.params["x"] <= 1.0 for item in bohb_candidates)

    cma = CMAESExplorer(space, seed=7)
    cma.update(evaluations)
    cma_candidates = cma.suggest_batch(3)
    assert len(cma_candidates) == 3
    assert all(0.0 <= item.params["x"] <= 1.0 for item in cma_candidates)

    gp = GaussianProcessCheapStageSurrogate()
    gp.fit(evaluations)
    means, stds = gp.predict([(0.8,), (0.2,)])
    assert len(means) == 2
    assert len(stds) == 2
    assert means[0] > means[1]


def test_learned_voi_routing_and_pbt_surfaces() -> None:
    voi = LearnedVOIPolicy()
    voi.fit(
        [
            VOITrainingExample(features={"cheap_score": 0.1}, realized_value=0.2),
            VOITrainingExample(features={"cheap_score": 1.0}, realized_value=0.9),
        ]
    )
    assert voi.score({"cheap_score": 1.0}) > voi.score({"cheap_score": 0.1})

    router = LearnedRoutingPolicy()
    router.fit(
        [
            RoutingTrainingExample(features={"risk": 0.1}, route="cheap", reward=1.0),
            RoutingTrainingExample(features={"risk": 0.9}, route="full", reward=1.0),
        ]
    )
    assert router.route({"risk": 0.85}) == "full"

    pbt = PopulationBasedTrainingScheduler(seed=1)
    next_population = pbt.step(
        [
            PopulationMember(member_id="a", params={"x": 0.8}, score=0.9),
            PopulationMember(member_id="b", params={"x": 0.2}, score=0.1),
        ]
    )
    assert len(next_population) == 2
    assert next_population[1].metadata["exploited_parent"] == "a"
