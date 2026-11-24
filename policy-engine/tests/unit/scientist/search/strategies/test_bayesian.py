from __future__ import annotations

import json
import math
from dataclasses import asdict

import pytest

from polisyos.scientist.methods.search.objective import (
    _configured_search_metric_profile_fingerprint,
)
from polisyos.scientist.methods.search.strategies import bayesian as bayesian_module
from polisyos.scientist.methods.search.strategies._deps import fit_gpytorch_mll
from polisyos.scientist.methods.search.strategies.bayesian import (
    BayesianConfig,
    BayesianOptimizer,
    BayesianProposalExhaustedError,
)
from polisyos.scientist.methods.search.strategies.resource_arbiter import (
    ResourceArbiter,
    ResourcePolicy,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.transfer import TransferLearningManager
from polisyos.scientist.methods.search.strategies.types import (
    ParameterBounds,
    ParameterType,
    PolicyCandidate,
    StrategyState,
)

from .conftest import make_evaluation


def test_bayesian_cold_start_uses_sobol(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=3, seed=1))
    c0 = strategy.suggest([])
    c1 = strategy.suggest(
        [make_evaluation(candidate_id="e0", params=c0.params, score=1.0, space=simple_space)]
    )
    assert c0.source_strategy == "sobol_init"
    assert c1.source_strategy == "sobol_init"


def test_bayesian_no_dependency_fallback(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=1, seed=2))
    evaluations = [
        make_evaluation(candidate_id="e0", params={"x": 0.0}, score=1.0, space=simple_space),
        make_evaluation(candidate_id="e1", params={"x": 1.0}, score=0.5, space=simple_space),
        make_evaluation(candidate_id="e2", params={"x": -1.0}, score=0.2, space=simple_space),
    ]
    candidate = strategy.suggest(evaluations)
    if fit_gpytorch_mll is None:
        assert candidate.source_strategy == "random_no_botorch"
    else:
        assert candidate.source_strategy in {
            "bayesian_acquisition",
            "random_fallback",
            "random_hard_limit",
            "random_insufficient_data",
            "random_duplicate_avoidance",
        }


def test_bayesian_state_roundtrip_without_deps(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=1, seed=5))
    evals = [
        make_evaluation(candidate_id="e0", params={"x": 0.0}, score=1.0, space=simple_space),
        make_evaluation(candidate_id="e1", params={"x": 1.0}, score=0.5, space=simple_space),
    ]
    _ = strategy.suggest(evals)
    state = strategy.get_state()

    restored = BayesianOptimizer(simple_space, BayesianConfig(n_initial=1, seed=999))
    restored.set_state(state)
    assert restored.get_state().iteration == state.iteration


def test_warm_start_rejections_survive_public_state_artifact_without_entering_corpus(
    simple_space: SearchSpace,
) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(seed=19))
    compatibility = {
        "search_space_fingerprint": simple_space.sobol_space_fingerprint(),
        "input_transform_fingerprint": "Normalize[0,1]",
        "outcome_transform_fingerprint": "Standardize[m=1]",
        "noise_model_fingerprint": "GaussianLikelihood[inferred]",
        "objective_fingerprint": "scalar_score[minimize]",
        "context_fingerprint": "context/rejection-audit",
    }
    records = [
        make_evaluation(
            candidate_id=f"full-record-identity/{index}",
            params={"x": float(index - 2)},
            score=float(index),
            space=simple_space,
        )
        for index in range(6)
    ]
    for index, evaluation in enumerate(records):
        evaluation.provenance_ref = f"origin/rejection-audit/{index}"
        evaluation.metadata = {
            "replicate_id": f"replica-{index}",
            "seed": index,
            "warm_start_compatibility": dict(compatibility),
            "payload": {"retained": [index]},
        }
    accepted, *rejected = records
    rejected[0].stage_a_passed = False
    rejected[1].provenance_ref = None
    rejected[2].params_normalized = (0.25, 0.75)
    rejected[3].metadata.pop("warm_start_compatibility")
    rejected[4].metadata["warm_start_compatibility"]["context_fingerprint"] = "foreign"
    reasons = [
        "invalid outcome",
        "missing provenance_ref",
        "incompatible normalized parameters",
        "missing or incompatible warm-start fingerprint",
        "incompatible context fingerprint",
    ]
    expected = json.loads(
        json.dumps(
            [
                {"reason": reason, "evaluation": asdict(evaluation)}
                for reason, evaluation in zip(reasons, rejected, strict=True)
            ],
            default=str,
        )
    )
    assert strategy.warm_start(records) is None
    assert strategy._select_training_subset([]) == [accepted]
    # Retain each rejected occurrence, including repeated complete record identities.
    strategy.warm_start([rejected[1]])
    expected.append(expected[1])
    rejected[0].metadata["payload"]["retained"].append("changed by caller")
    state = StrategyState.from_artifact(strategy.get_state().to_artifact())
    history = state.metadata["warm_start_rejections"]
    assert history["version"] == 1
    assert history["complete"] is True
    assert history["records"] == expected
    assert strategy._select_training_subset([]) == [accepted]
    restored = BayesianOptimizer(simple_space, BayesianConfig(seed=19))
    restored.set_state(state)
    restored_state = StrategyState.from_artifact(restored.get_state().to_artifact())
    assert restored_state.metadata["warm_start_rejections"] == history
    # A checkpoint from before this ledger cannot fabricate its discarded rejections.
    state.metadata.pop("warm_start_rejections")
    restored.set_state(state)
    legacy_history = restored.get_state().metadata["warm_start_rejections"]
    assert legacy_history == {"version": 1, "complete": False, "records": []}
    restored.warm_start([rejected[1]])
    assert restored.get_state().metadata["warm_start_rejections"]["complete"] is False
    assert len(restored.get_state().metadata["warm_start_rejections"]["records"]) == 1


def test_canonical_warm_start_rejects_raw_native_profile_before_context_admission(
    simple_space: SearchSpace,
) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(seed=23))
    evaluation = make_evaluation(
        candidate_id="warm-foreign-context",
        params={"x": 0.25},
        score=0.5,
        space=simple_space,
    )
    evaluation.provenance_ref = "origin/warm-foreign-context"
    evaluation.metadata = {
        "warm_start_compatibility": {
            "profile_kind": "configured_native_gp",
            "optimizer_fqn": (
                "polisyos.scientist.methods.search.strategies.bayesian.BayesianOptimizer"
            ),
            "optimizer_config_fingerprint": "config/profile",
            "proposal_source": "bayesian_acquisition",
            "search_space_fingerprint": simple_space.sobol_space_fingerprint(),
            "input_transform_fingerprint": "Normalize[0,1]",
            "input_transform_state_fingerprint": "transform/fit-state",
            "outcome_transform_fingerprint": "Standardize[m=1]",
            "outcome_transform_state_fingerprint": "outcome/fit-state",
            "noise_model_fingerprint": "GaussianLikelihood[inferred]",
            "noise_model_state_fingerprint": "likelihood/fit-state",
            "objective_fingerprint": "objective/source",
            "context_fingerprint": "context/source",
            "training_corpus_fingerprint": "corpus/fitted-source",
            "training_observation_count": 3,
            "gp_model_fqn": "botorch.models.gp_regression.SingleTaskGP",
            "warm_start_eligible": True,
        }
    }

    strategy.warm_start(
        [evaluation],
        target_context_fingerprint="context/target",
        target_objective_fingerprint="objective/source",
    )

    assert strategy.warm_start_accepted_count == 0
    assert strategy._select_training_subset([]) == []
    assert strategy.warm_start_rejections[-1]["reason"] == (
        "native GP profile lacks fresh fit-basis admission"
    )


def test_canonical_warm_start_rejects_self_described_native_profile_with_matching_context(
    simple_space: SearchSpace,
) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(seed=31))
    evaluation = make_evaluation(
        candidate_id="warm-forged-native-profile",
        params={"x": 0.25},
        score=0.5,
        space=simple_space,
    )
    evaluation.provenance_ref = "origin/warm-forged-native-profile"
    evaluation.metadata = {
        "warm_start_compatibility": {
            "profile_kind": "configured_native_gp",
            "warm_start_eligible": True,
            "context_fingerprint": "context/target",
            "objective_fingerprint": "objective/target",
            "search_space_fingerprint": simple_space.sobol_space_fingerprint(),
        }
    }

    strategy.warm_start(
        [evaluation],
        target_context_fingerprint="context/target",
        target_objective_fingerprint="objective/target",
    )

    assert strategy.warm_start_accepted_count == 0
    assert strategy.warm_start_rejections[-1]["reason"] == (
        "native GP profile lacks fresh fit-basis admission"
    )


def _warm_planning_records(simple_space: SearchSpace):
    """The existing admitted warm fixture, including duplicate and independent replica."""
    compatibility = {
        "search_space_fingerprint": simple_space.sobol_space_fingerprint(),
        "input_transform_fingerprint": "Normalize[0,1]",
        "outcome_transform_fingerprint": "Standardize[m=1]",
        "noise_model_fingerprint": "GaussianLikelihood[inferred]",
        "objective_fingerprint": "scalar_score[minimize]",
        "context_fingerprint": "context/run-1",
    }
    warm = [
        make_evaluation(
            candidate_id=f"warm-{index}",
            params={"x": -3.5 + index},
            score=float(index),
            space=simple_space,
        )
        for index in range(6)
    ]
    for index, evaluation in enumerate(warm):
        evaluation.provenance_ref = f"origin/run-1/evaluation-{index}"
        evaluation.metadata = {
            "replicate_id": f"replica-{index}",
            "seed": index,
            "warm_start_compatibility": dict(compatibility),
        }
    warm[2].metadata.update(replicate_id="replica-1", seed=1)
    duplicate = make_evaluation(
        candidate_id="warm-2", params={"x": -1.5}, score=2.0, space=simple_space
    )
    duplicate.provenance_ref = "origin/run-1/evaluation-2"
    duplicate.metadata = dict(warm[2].metadata)
    replica = make_evaluation(
        candidate_id="warm-2-replica", params={"x": -1.5}, score=2.25, space=simple_space
    )
    replica.provenance_ref = "origin/run-1/evaluation-2-replica"
    replica.metadata = {
        "replicate_id": "replica-2",
        "seed": 2,
        "warm_start_compatibility": dict(compatibility),
    }
    warm.extend([duplicate, replica])
    current = make_evaluation(
        candidate_id="current-0", params={"x": 4.0}, score=8.0, space=simple_space
    )
    current.provenance_ref = "origin/run-2/evaluation-0"
    current.metadata = {
        "replicate_id": "current-0",
        "seed": 101,
        "warm_start_compatibility": dict(compatibility),
    }
    return warm, [current]


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("batch", [False, True])
def test_whole_and_warm_split_use_the_same_permitted_acquisition_plan(
    simple_space: SearchSpace, monkeypatch: pytest.MonkeyPatch, reverse: bool, batch: bool
) -> None:
    """Observed corpus and routes with a fitted native GP and controlled optimizer draws."""
    warm, current = _warm_planning_records(simple_space)
    if reverse:
        warm.reverse()
    config = BayesianConfig(
        n_initial=6, seed=21, adaptive_acquisition=True, fallback_on_failure=False
    )
    whole = BayesianOptimizer(simple_space, config)
    split = BayesianOptimizer(simple_space, config)
    split.warm_start(warm)
    expected = whole._effective_training_corpus([*warm, *current])
    assert len(expected) == 8
    assert sum(e.candidate_id == "warm-2" for e in expected) == 1
    assert any(e.candidate_id == "warm-2-replica" for e in expected)

    def observe_run(strategy, evaluations):
        observed = {"training": [], "planning": [], "fit": [], "routes": []}
        prepare = strategy._prepare_training_data
        fit = strategy._fit_gp
        select = strategy._select_acquisition

        def observe_prepare(records):
            observed["training"].append([e.candidate_id for e in records])
            return prepare(records)

        def observe_fit(x, y_bo):
            observed["fit"].append((x.tolist(), y_bo.tolist()))
            fit(x, y_bo)

        def observe_select(records, y_bo):
            observed["planning"].append([e.candidate_id for e in records])
            return select(records, y_bo)

        def controlled_optimize(**kwargs):
            observed["routes"].append(type(kwargs["acq_function"]).__name__)
            q = kwargs["q"]
            candidates = strategy._torch.linspace(0.61, 0.71, q, dtype=strategy._torch.float64)
            return candidates.reshape(q, 1), strategy._torch.tensor(1.0)

        monkeypatch.setattr(strategy, "_prepare_training_data", observe_prepare)
        monkeypatch.setattr(strategy, "_fit_gp", observe_fit)
        monkeypatch.setattr(strategy, "_select_acquisition", observe_select)
        monkeypatch.setattr(bayesian_module, "optimize_acqf", controlled_optimize)
        result = (
            strategy.suggest_batch(evaluations, batch_size=2)
            if batch
            else [strategy.suggest(evaluations)]
        )
        assert all(c.source_strategy in {"bayesian_acquisition", "batch_qei"} for c in result)
        assert strategy._iteration == len(evaluations)
        return observed

    whole_result = observe_run(whole, [*warm, *current])
    split_result = observe_run(split, current)
    expected_ids = [e.candidate_id for e in expected]
    assert whole_result["training"] == split_result["training"] == [expected_ids]
    assert whole_result["fit"] == split_result["fit"]
    if batch:
        assert whole_result["planning"] == split_result["planning"] == []
        assert whole_result["routes"] == split_result["routes"] == ["qExpectedImprovement"]
    else:
        # Optimizing and recomputing the emitted prediction consume the same corpus.
        assert whole_result["planning"] == split_result["planning"] == [expected_ids, expected_ids]
        expected_route = "UpperConfidenceBound" if reverse else "ExpectedImprovement"
        assert whole_result["routes"] == split_result["routes"] == [expected_route]


@pytest.mark.parametrize("batch", [False, True])
def test_whole_and_warm_split_use_the_same_actual_cold_sobol_plan(
    simple_space: SearchSpace, batch: bool
) -> None:
    """Actual sampler inputs/parameters agree; current-request iteration stays separate."""
    warm, current = _warm_planning_records(simple_space)
    warm = warm[:2]
    config = BayesianConfig(n_initial=6, seed=21)
    whole = BayesianOptimizer(simple_space, config)
    split = BayesianOptimizer(simple_space, config)
    split.warm_start(warm)
    corpus = whole._effective_training_corpus([*warm, *current])
    assert len(corpus) == 3 < config.n_initial
    whole_candidates = (
        whole.suggest_batch([*warm, *current], batch_size=2)
        if batch
        else [whole.suggest([*warm, *current])]
    )
    split_candidates = (
        split.suggest_batch(current, batch_size=2) if batch else [split.suggest(current)]
    )
    assert all(c.source_strategy == "sobol_init" for c in [*whole_candidates, *split_candidates])
    assert [c.params for c in whole_candidates] == [c.params for c in split_candidates]
    assert [c.params_normalized for c in whole_candidates] == [
        c.params_normalized for c in split_candidates
    ]
    assert whole._iteration == 3
    assert split._iteration == 1


def test_duplicate_detection_uses_canonical_integer_and_category_execution() -> None:
    space = SearchSpace(
        bounds=[
            ParameterBounds(name="budget_steps", lower=0, upper=1, dtype=ParameterType.INTEGER),
            ParameterBounds(
                name="regime",
                dtype=ParameterType.CATEGORICAL,
                categories=("A", "B"),
            ),
        ]
    )
    strategy = BayesianOptimizer(space, BayesianConfig(seed=13))
    pending = PolicyCandidate(
        candidate_id="replica-a",
        params={"budget_steps": 0, "regime": "A"},
        params_normalized=(0.12, 0.80, 0.20),
    )
    proposal = PolicyCandidate(
        candidate_id="replica-b",
        params={"budget_steps": 0, "regime": "A"},
        params_normalized=(0.24, 0.60, 0.40),
    )

    assert proposal.params_normalized != pending.params_normalized
    assert strategy._is_duplicate(proposal, [pending])

    different_integer = PolicyCandidate(
        candidate_id="different-integer",
        params={"budget_steps": 1, "regime": "A"},
        params_normalized=(0.86, 0.80, 0.20),
    )
    different_category = PolicyCandidate(
        candidate_id="different-category",
        params={"budget_steps": 0, "regime": "B"},
        params_normalized=(0.12, 0.20, 0.80),
    )

    assert not strategy._is_duplicate(different_integer, [pending])
    assert not strategy._is_duplicate(different_category, [pending])


def test_duplicate_detection_keeps_pending_action_with_relabelled_replica_in_scope() -> None:
    space = SearchSpace(
        bounds=[
            ParameterBounds(name="budget_steps", lower=0, upper=1, dtype=ParameterType.INTEGER),
            ParameterBounds(
                name="regime",
                dtype=ParameterType.CATEGORICAL,
                categories=("A", "B"),
            ),
        ]
    )
    strategy = BayesianOptimizer(space, BayesianConfig(seed=13))
    pending = PolicyCandidate(
        candidate_id="replica-seed-17",
        params={"budget_steps": 0, "regime": "A"},
        params_normalized=(0.12, 0.80, 0.20),
        metadata={"replicate_id": "replicate-1", "seed": 17},
    )
    proposal = PolicyCandidate(
        candidate_id="replica-seed-23",
        params={"budget_steps": 0, "regime": "A"},
        params_normalized=(0.24, 0.60, 0.40),
        metadata={"replicate_id": "replicate-1", "seed": 23},
    )

    assert proposal.params_normalized != pending.params_normalized
    assert strategy._is_duplicate(proposal, [pending])


def test_duplicate_detection_does_not_accept_implicit_or_cosmetic_replica() -> None:
    space = _integer_space(1)
    strategy = BayesianOptimizer(space)
    pending = PolicyCandidate(params={"n": 0}, metadata={"seed": 17})
    proposal = PolicyCandidate(params={"n": 0}, metadata={"seed": 23})
    assert strategy._is_duplicate(proposal, [pending])

    pending.metadata = {"replicate_id": "original", "seed": 17}
    proposal.metadata = {"replicate_id": "renamed", "seed": 17}
    assert strategy._is_duplicate(proposal, [pending])


def test_duplicate_detection_uses_unrounded_continuous_execution(
    simple_space: SearchSpace,
) -> None:
    strategy = BayesianOptimizer(simple_space)
    left = PolicyCandidate(params={"x": 1.0}, params_normalized=(0.6,))
    right = PolicyCandidate(params={"x": math.nextafter(1.0, math.inf)}, params_normalized=(0.6,))
    assert not strategy._is_duplicate(right, [left])


@pytest.mark.parametrize("completed", [False, True])
def test_replica_labels_cannot_reissue_occupied_action(
    monkeypatch: pytest.MonkeyPatch, completed: bool
) -> None:
    space = _integer_space(1)
    optimizer = BayesianOptimizer(space, BayesianConfig(n_initial=0))
    monkeypatch.setattr(optimizer, "_botorch_ready", False)
    labels = {"replicate_id": "claimed-1", "seed": 7}
    prior = make_evaluation(candidate_id="observed", params={"n": 0}, score=1.0, space=space)
    prior.provenance_ref = "origin/committed-result"
    prior.metadata = labels
    occupied = PolicyCandidate(params={"n": 0}, metadata=labels)
    draws = iter(
        (
            PolicyCandidate(params={"n": 0}, metadata={"replica_id": "claimed-2", "seed": 8}),
            PolicyCandidate(params={"n": 1}),
        )
    )
    monkeypatch.setattr(optimizer, "_random_candidate", lambda *, source: next(draws))

    result = optimizer.suggest(
        [prior] if completed else [], pending=[] if completed else [occupied]
    )

    assert result.params == {"n": 1}


def test_training_uses_each_committed_origin_once_and_keeps_distinct_replica(
    simple_space: SearchSpace,
) -> None:
    optimizer = BayesianOptimizer(simple_space)
    rows = [
        make_evaluation(
            candidate_id=f"proposal-{i}", params={"x": 1.0}, score=2.0, space=simple_space
        )
        for i in range(3)
    ]
    first, transport_alias, independent = rows
    first.provenance_ref = transport_alias.provenance_ref = "origin/physical-run-1"
    independent.provenance_ref = "origin/physical-run-2"
    for i, row in enumerate(rows):
        row.metadata = {"replicate_id": f"label-{i}", "seed": i}

    assert optimizer._effective_training_corpus(rows) == [first, independent]
    with pytest.raises(RuntimeError, match="observation provenance"):
        optimizer._prepare_training_data(rows)


@pytest.mark.parametrize("change", ["parameters", "score"])
def test_training_withholds_conflicting_rows_of_same_origin(
    simple_space: SearchSpace, change: str
) -> None:
    optimizer = BayesianOptimizer(simple_space)
    first = make_evaluation(
        candidate_id="original", params={"x": 1.0}, score=2.0, space=simple_space
    )
    edited = make_evaluation(
        candidate_id="renamed",
        params={"x": 2.0 if change == "parameters" else 1.0},
        score=3.0 if change == "score" else 2.0,
        space=simple_space,
    )
    first.provenance_ref = edited.provenance_ref = "origin/physical-run-1"
    independent = make_evaluation(
        candidate_id="independent", params={"x": 3.0}, score=4.0, space=simple_space
    )
    independent.provenance_ref = "origin/physical-run-2"

    assert optimizer._effective_training_corpus([first, edited, first, independent]) == [
        independent
    ]


def test_sparse_provenance_cannot_inflate_generic_corpus_with_cosmetic_ids(
    simple_space: SearchSpace,
) -> None:
    optimizer = BayesianOptimizer(simple_space)
    first = make_evaluation(candidate_id="a", params={"x": 1.0}, score=2.0, space=simple_space)
    alias = make_evaluation(candidate_id="b", params={"x": 1.0}, score=2.0, space=simple_space)
    another_action = make_evaluation(
        candidate_id="other", params={"x": 2.0}, score=2.0, space=simple_space
    )

    assert optimizer._effective_training_corpus([first, alias, another_action]) == [
        first,
        another_action,
    ]


def test_duplicate_detection_preserves_declared_categorical_value_types() -> None:
    space = SearchSpace(
        bounds=[
            ParameterBounds(name="regime", dtype=ParameterType.CATEGORICAL, categories=(True, 1))
        ]
    )
    strategy = BayesianOptimizer(space)
    boolean = PolicyCandidate(params=space.denormalize((1.0, 0.0)))
    integer = PolicyCandidate(params=space.denormalize((0.0, 1.0)))

    assert type(boolean.params["regime"]) is bool
    assert type(integer.params["regime"]) is int
    assert not strategy._is_duplicate(integer, [boolean])


def _integer_space(upper: int) -> SearchSpace:
    return SearchSpace(
        bounds=[ParameterBounds(name="n", lower=0, upper=upper, dtype=ParameterType.INTEGER)]
    )


def test_cold_sobol_excludes_pending_effective_integer_action() -> None:
    space = _integer_space(1)
    config = BayesianConfig(seed=13)
    pending = BayesianOptimizer(space, config).suggest([])
    optimizer = BayesianOptimizer(space, config)

    candidate = optimizer.suggest([], pending=[pending])

    assert candidate.params == {"n": 1 - pending.params["n"]}


def test_binary_batch_retains_only_remaining_candidate_and_reports_exact_exhaustion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = _integer_space(1)
    optimizer = BayesianOptimizer(space, BayesianConfig(n_initial=1, seed=13))
    monkeypatch.setattr(optimizer, "_botorch_ready", False)
    completed = make_evaluation(
        candidate_id="completed-n0", params={"n": 0}, score=1.0, space=space
    )

    with pytest.raises(BayesianProposalExhaustedError) as error:
        optimizer.suggest_batch([completed], batch_size=3)

    assert error.value.reason == "finite_domain_exhausted"
    assert [item.params for item in error.value.partial_candidates] == [{"n": 1}]


def test_bounded_proposal_search_does_not_claim_a_free_action_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = _integer_space(99)
    optimizer = BayesianOptimizer(space, BayesianConfig(n_initial=1, seed=13))
    monkeypatch.setattr(optimizer, "_botorch_ready", False)
    sampled = []
    completed = [
        make_evaluation(
            candidate_id=f"completed-{n}",
            params={"n": n},
            score=1.0,
            space=space,
            valid=n == 0,
        )
        for n in range(99)
    ]

    def draw_occupied_action() -> float:
        sampled.append(0)
        return 0.0

    monkeypatch.setattr(optimizer._rng, "random", draw_occupied_action)

    with pytest.raises(BayesianProposalExhaustedError) as error:
        optimizer.suggest(completed)

    assert error.value.reason == "proposal_search_budget_exhausted"
    assert len(sampled) == 20
    assert not error.value.partial_candidates


def test_small_domain_census_finds_a_free_action_after_duplicate_draws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = _integer_space(3)
    optimizer = BayesianOptimizer(space, BayesianConfig(n_initial=1, seed=13))
    monkeypatch.setattr(optimizer, "_botorch_ready", False)
    monkeypatch.setattr(optimizer._rng, "random", lambda: 0.0)
    completed = [
        make_evaluation(candidate_id=f"completed-{n}", params={"n": n}, score=1.0, space=space)
        for n in range(3)
    ]

    candidate = optimizer.suggest(completed)

    assert candidate.params == {"n": 3}
    assert candidate.source_strategy == "discrete_enumeration"


def test_completed_action_blocks_only_on_the_frozen_measurement_basis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = _integer_space(1)
    optimizer = BayesianOptimizer(
        space,
        BayesianConfig(n_initial=0),
        objective_name="score",
        objective_source_direction="minimize",
        objective_source_unit="unit",
    )
    objective = _configured_search_metric_profile_fingerprint("score", "minimize", "unit")
    assert objective is not None
    optimizer.set_search_run_profile(
        context_fingerprint="current-context",
        objective_fingerprint=objective,
        objective_unit="unit",
    )
    monkeypatch.setattr(optimizer, "_botorch_ready", False)
    monkeypatch.setattr(optimizer._rng, "random", lambda: 0.0)
    completed = make_evaluation(
        candidate_id="n0-without-trainable-score",
        params={"n": 0},
        score=1.0,
        space=space,
        valid=False,
    )
    completed.metadata["warm_start_compatibility"] = {
        "search_space_fingerprint": space.sobol_space_fingerprint(),
        "objective_fingerprint": objective,
        "context_fingerprint": "foreign-context",
    }

    assert optimizer.suggest([completed]).params == {"n": 0}
    completed.metadata["warm_start_compatibility"]["context_fingerprint"] = "current-context"
    assert optimizer.suggest([completed]).params == {"n": 1}


def test_historical_time_unknown_cannot_enter_generic_bayesian_training() -> None:
    space = _integer_space(1)
    config = BayesianConfig(n_initial=1, seed=13)
    without_history = BayesianOptimizer(space, config).suggest([], attempted_count=1)
    current = make_evaluation(
        candidate_id="new", params=without_history.params, score=3.0, space=space
    )
    retained = TransferLearningManager._serialize_evaluation(current)
    del retained["timestamp"]
    historical = TransferLearningManager._deserialize_evaluation(retained, "retained-run")
    optimizer = BayesianOptimizer(space, config)

    assert historical.timestamp is None
    assert historical.scalar_score == 3.0
    assert optimizer._effective_training_corpus([historical, current]) == [current]
    candidate = optimizer.suggest([historical])
    assert candidate.source_strategy == "sobol_init"
    assert candidate.params == without_history.params


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_hard_limit_batch_preserves_completed_and_pending_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = _integer_space(4)
    arbiter = ResourceArbiter(ResourcePolicy(hard_rss_mb=0, soft_rss_mb=0, enable_cleanup=False))
    optimizer = BayesianOptimizer(space, BayesianConfig(n_initial=1), resource_arbiter=arbiter)
    completed = make_evaluation(candidate_id="completed", params={"n": 0}, score=1.0, space=space)
    pending = PolicyCandidate(params={"n": 1})
    proposed_draws = iter((0.0, 0.25, 0.5, 0.5, 0.75))
    monkeypatch.setattr(optimizer._rng, "random", lambda: next(proposed_draws))

    proposals = optimizer.suggest_batch([completed], batch_size=2, pending=[pending])

    assert [p.params for p in proposals] == [{"n": 2}, {"n": 3}]
    assert [p.source_strategy for p in proposals] == ["random_hard_limit", "random_hard_limit"]


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_qei_batch_checks_effective_action_before_accepting_backend_proposals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space = _integer_space(7)
    optimizer = BayesianOptimizer(
        space, BayesianConfig(n_initial=1, num_restarts=3, raw_samples=32)
    )
    completed = [
        make_evaluation(
            candidate_id=f"completed-{n}", params={"n": n}, score=float(n**2), space=space
        )
        for n in range(3)
    ]

    def backend_points(*, acq_function, bounds, q, **_: object):
        assert q == 3
        assert acq_function.model is optimizer._model
        return bounds.new_tensor([[0.0], [3.0 / 7], [3.2 / 7]]), None

    monkeypatch.setattr(bayesian_module, "optimize_acqf", backend_points)
    proposed_draws = iter((0.0, 4.0 / 7, 4.0 / 7, 5.0 / 7))
    monkeypatch.setattr(optimizer._rng, "random", lambda: next(proposed_draws))

    proposals = optimizer.suggest_batch(completed, batch_size=3)

    assert [p.params for p in proposals] == [{"n": 3}, {"n": 4}, {"n": 5}]
    assert [p.source_strategy for p in proposals] == [
        "batch_qei",
        "random_duplicate_avoidance",
        "random_duplicate_avoidance",
    ]


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_bayesian_batch_shape_when_deps_available(simple_space: SearchSpace) -> None:
    strategy = BayesianOptimizer(simple_space, BayesianConfig(n_initial=1, seed=8))
    evaluations = [
        make_evaluation(
            candidate_id=f"e{i}",
            params={"x": float(i - 2)},
            score=float((i - 2) ** 2),
            space=simple_space,
        )
        for i in range(6)
    ]
    batch = strategy.suggest_batch(evaluations, batch_size=3)
    assert len(batch) == 3


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_bayesian_warm_start_reaches_gp_training_before_initial_threshold(
    simple_space: SearchSpace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warm history and current observations form one compatible GP corpus."""
    strategy = BayesianOptimizer(
        simple_space,
        BayesianConfig(n_initial=6, num_restarts=3, raw_samples=32, seed=21),
    )
    compatibility = {
        "search_space_fingerprint": simple_space.sobol_space_fingerprint(),
        "input_transform_fingerprint": "Normalize[0,1]",
        "outcome_transform_fingerprint": "Standardize[m=1]",
        "noise_model_fingerprint": "GaussianLikelihood[inferred]",
        "objective_fingerprint": "scalar_score[minimize]",
        "context_fingerprint": "context/run-1",
    }
    warm = [
        make_evaluation(
            candidate_id=f"warm-{index}",
            params={"x": -3.5 + index},
            score=float(index),
            space=simple_space,
        )
        for index in range(6)
    ]
    for index, evaluation in enumerate(warm):
        evaluation.provenance_ref = f"origin/run-1/evaluation-{index}"
        evaluation.metadata = {
            "replicate_id": f"replica-{index}",
            "seed": index,
            "warm_start_compatibility": dict(compatibility),
        }
    warm[2].provenance_ref = "origin/run-1/evaluation-2"
    warm[2].metadata = {
        "replicate_id": "replica-1",
        "seed": 1,
        "warm_start_compatibility": dict(compatibility),
    }
    duplicate = make_evaluation(
        candidate_id="warm-2",
        params={"x": -1.5},
        score=2.0,
        space=simple_space,
    )
    duplicate.provenance_ref = "origin/run-1/evaluation-2"
    duplicate.metadata = {
        "replicate_id": "replica-1",
        "seed": 1,
        "warm_start_compatibility": dict(compatibility),
    }
    independent_replica = make_evaluation(
        candidate_id="warm-2-replica",
        params={"x": -1.5},
        score=2.25,
        space=simple_space,
    )
    independent_replica.provenance_ref = "origin/run-1/evaluation-2-replica"
    independent_replica.metadata = {
        "replicate_id": "replica-2",
        "seed": 2,
        "warm_start_compatibility": dict(compatibility),
    }
    warm.extend([duplicate, independent_replica])
    malformed = make_evaluation(
        candidate_id="warm-foreign-basis",
        params={"x": 4.5},
        score=7.0,
        space=simple_space,
    )
    malformed.provenance_ref = "origin/run-1/foreign-basis"
    malformed.metadata = {"replicate_id": "foreign-basis", "seed": 99}
    malformed.params_normalized = (0.25, 0.75)
    warm.append(malformed)
    incompatible_context = make_evaluation(
        candidate_id="warm-incompatible-context",
        params={"x": 3.75},
        score=7.25,
        space=simple_space,
    )
    incompatible_context.provenance_ref = "origin/run-1/incompatible-context"
    incompatible_context.metadata = {
        "replicate_id": "incompatible-context",
        "seed": 98,
        "warm_start_compatibility": {
            **compatibility,
            "context_fingerprint": "context/foreign",
        },
    }
    warm.append(incompatible_context)
    unbound = make_evaluation(
        candidate_id="warm-unbound",
        params={"x": 4.25},
        score=7.5,
        space=simple_space,
    )
    unbound.metadata = {"replicate_id": "unbound", "seed": 100}
    warm.append(unbound)
    current = [
        make_evaluation(
            candidate_id="current-0",
            params={"x": 4.0},
            score=8.0,
            space=simple_space,
        )
    ]
    current[0].provenance_ref = "origin/run-2/evaluation-0"
    current[0].metadata = {
        "replicate_id": "current-0",
        "seed": 101,
        "warm_start_compatibility": dict(compatibility),
    }

    strategy.warm_start(warm)
    history = StrategyState.from_artifact(strategy.get_state().to_artifact()).metadata[
        "warm_start_rejections"
    ]
    assert history["complete"] is True
    assert [record["evaluation"]["candidate_id"] for record in history["records"]] == [
        "warm-foreign-basis",
        "warm-incompatible-context",
        "warm-unbound",
    ]
    assert [record["reason"] for record in history["records"]] == [
        "incompatible normalized parameters",
        "incompatible context fingerprint",
        "missing provenance_ref",
    ]
    observed_corpus: list[tuple[tuple[tuple[float, ...], ...], tuple[float, ...]]] = []
    observed_ids: list[tuple[str, ...]] = []
    original_prepare = strategy._prepare_training_data

    def observe_prepare(evaluations):
        observed_ids.append(tuple(evaluation.candidate_id for evaluation in evaluations))
        return original_prepare(evaluations)

    original_fit = strategy._fit_gp

    def observe_fit(x, y_bo):
        x_rows = tuple(tuple(float(value) for value in row) for row in x.detach().cpu().tolist())
        y_rows = tuple(float(row[0]) for row in y_bo.detach().cpu().tolist())
        observed_corpus.append((x_rows, y_rows))
        return original_fit(x, y_bo)

    monkeypatch.setattr(strategy, "_prepare_training_data", observe_prepare)
    monkeypatch.setattr(strategy, "_fit_gp", observe_fit)
    candidate = strategy.suggest(current)

    assert len(observed_ids) == 1
    expected_ids = [evaluation.candidate_id for evaluation in warm[:6]] + [
        "warm-2-replica",
        "current-0",
    ]
    assert sorted(observed_ids[0]) == sorted(expected_ids)
    assert "warm-foreign-basis" not in observed_ids[0]
    assert "warm-incompatible-context" not in observed_ids[0]
    assert "warm-unbound" not in observed_ids[0]
    assert len(observed_corpus) == 1
    observed_x, observed_y = observed_corpus[0]
    expected_by_id = {evaluation.candidate_id: evaluation for evaluation in [*warm, *current]}
    expected_evaluations = [expected_by_id[candidate_id] for candidate_id in observed_ids[0]]
    expected_x = tuple(
        tuple(float(value) for value in evaluation.params_normalized)
        for evaluation in expected_evaluations
    )
    expected_y = tuple(-float(evaluation.scalar_score) for evaluation in expected_evaluations)
    for actual_row, expected_row in zip(observed_x, expected_x, strict=True):
        assert actual_row == pytest.approx(expected_row)
    assert observed_y == pytest.approx(expected_y)
    assert candidate.source_strategy == "bayesian_acquisition"
    assert candidate.acquisition_value is not None
    assert candidate.predicted_mean is not None
    assert candidate.predicted_std is not None
    assert math.isfinite(candidate.acquisition_value)
    assert math.isfinite(candidate.predicted_mean)
    assert math.isfinite(candidate.predicted_std)


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_bayesian_no_refit_preserves_learned_gp_state_with_new_observation(
    simple_space: SearchSpace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-refit-interval observation conditions the fitted GP instead of resetting it."""
    strategy = BayesianOptimizer(
        simple_space,
        BayesianConfig(
            n_initial=1,
            num_restarts=3,
            raw_samples=32,
            refit_interval=10,
            seed=22,
        ),
    )
    fit_calls = 0
    original_fit = bayesian_module.fit_gpytorch_mll

    def observe_fit(mll):
        nonlocal fit_calls
        fit_calls += 1
        return original_fit(mll)

    monkeypatch.setattr(bayesian_module, "fit_gpytorch_mll", observe_fit)
    initial = [
        make_evaluation(
            candidate_id=f"initial-{index}",
            params={"x": -3.5 + index},
            score=float((index - 3) ** 2),
            space=simple_space,
        )
        for index in range(8)
    ]
    strategy.suggest(initial)
    assert strategy._model is not None
    model_before = strategy._model
    learned_before = {
        name: parameter.detach().clone() for name, parameter in model_before.named_parameters()
    }
    transform_state_before = {}
    for attribute in ("input_transform", "outcome_transform"):
        transform = getattr(model_before, attribute, None)
        assert transform is not None
        transform_state_before[attribute] = {
            name: value.detach().clone() for name, value in transform.state_dict().items()
        }
    expanded = [
        *initial,
        make_evaluation(
            candidate_id="new-observation",
            params={"x": 4.0},
            score=0.25,
            space=simple_space,
        ),
    ]
    strategy.suggest(expanded)

    assert fit_calls == 1
    assert strategy._model is not None
    model_train_X = strategy._model._original_train_inputs
    assert model_train_X is not None
    model_train_X = model_train_X.reshape(-1, model_train_X.shape[-1])
    actual_train_rows = tuple(
        tuple(float(value) for value in row) for row in model_train_X.detach().cpu().tolist()
    )
    expected_train_rows = tuple(
        tuple(float(value) for value in evaluation.params_normalized) for evaluation in expanded
    )
    assert len(actual_train_rows) == len(expected_train_rows) == 9
    for actual_row, expected_row in zip(actual_train_rows, expected_train_rows, strict=True):
        assert actual_row == pytest.approx(expected_row)
    learned_after = dict(strategy._model.named_parameters())
    assert set(learned_before).issubset(learned_after)
    for name, parameter in learned_before.items():
        assert strategy._torch.equal(parameter, learned_after[name].detach())
    for attribute, before_state in transform_state_before.items():
        transform_after = getattr(strategy._model, attribute, None)
        assert transform_after is not None
        after_state = transform_after.state_dict()
        assert set(after_state) == set(before_state)
        for name, value in before_state.items():
            assert strategy._torch.equal(value, after_state[name].detach())

    changed_observation = make_evaluation(
        candidate_id="new-observation",
        params={"x": 4.0},
        score=0.5,
        space=simple_space,
    )
    strategy.suggest([*initial, changed_observation])
    assert fit_calls == 2


@pytest.mark.skipif(fit_gpytorch_mll is None, reason="BoTorch stack not installed")
def test_restored_append_preserves_actual_full_refit_boundary_and_learned_basis(
    simple_space: SearchSpace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real GP state continuation conditions before the actual scheduled refit."""
    from dataclasses import replace

    config = BayesianConfig(
        n_initial=1,
        refit_interval=50,
        num_restarts=3,
        raw_samples=32,
        seed=109,
        fallback_on_failure=False,
    )
    actual_fit = bayesian_module.fit_gpytorch_mll
    fit_sizes = []

    def record_fit(mll):
        fit_sizes.append(int(mll.model.train_inputs[0].shape[-2]))
        return actual_fit(mll)

    monkeypatch.setattr(bayesian_module, "fit_gpytorch_mll", record_fit)
    original = BayesianOptimizer(simple_space, config)
    observations = [
        make_evaluation(
            candidate_id=f"state-{i}",
            params={"x": -3.5 + i},
            score=float((i - 3) ** 2),
            space=simple_space,
        )
        for i in range(8)
    ]
    assert original.suggest(observations).source_strategy == "bayesian_acquisition"
    state = original.get_state()
    learned = {name: value.detach().clone() for name, value in original._model.named_parameters()}
    restored = BayesianOptimizer(simple_space, config)
    restored.set_state(state)
    expanded = [
        *observations,
        make_evaluation(
            candidate_id="state-new", params={"x": 4.0}, score=0.25, space=simple_space
        ),
    ]
    assert restored.suggest(expanded).source_strategy == "bayesian_acquisition"
    assert fit_sizes == [8]
    assert restored._last_refit_iteration == original._last_refit_iteration == 8
    assert restored._last_train_size == original._last_train_size == 8
    for name, parameter in restored._model.named_parameters():
        assert restored._torch.equal(parameter.detach(), learned[name])
    conditioned_state = restored.get_state()
    assert len(conditioned_state.metadata["gp_continuation"]["fitted_train_X"]) == 9
    assert conditioned_state.metadata["gp_continuation"]["last_train_size"] == 8
    second_restore = BayesianOptimizer(simple_space, config)
    second_restore.set_state(conditioned_state)
    assert second_restore.suggest(expanded).source_strategy == "bayesian_acquisition"
    assert fit_sizes == [8]
    # Original missing counter bytes cannot be inferred from current row count.
    legacy = replace(
        state, metadata={k: v for k, v in state.metadata.items() if k != "gp_continuation"}
    )
    with pytest.raises(ValueError, match="not established"):
        BayesianOptimizer(simple_space, config).set_state(legacy)
    invalid = dict(state.metadata["gp_continuation"], last_train_size=True)
    with pytest.raises(ValueError, match="invalid full-refit counters"):
        BayesianOptimizer(simple_space, config).set_state(
            replace(state, metadata={**state.metadata, "gp_continuation": invalid})
        )
    foreign = dict(state.metadata["gp_continuation"], space_fingerprint="foreign")
    with pytest.raises(ValueError, match="search space differs"):
        BayesianOptimizer(simple_space, config).set_state(
            replace(state, metadata={**state.metadata, "gp_continuation": foreign})
        )
