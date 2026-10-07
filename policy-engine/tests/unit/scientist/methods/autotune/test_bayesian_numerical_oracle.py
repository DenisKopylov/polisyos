"""Independent physical arithmetic and actual public adapter numerical consumers."""

import json
from unittest.mock import patch

import pytest

from polisyos.core import artifacts
from polisyos.scientist.methods.autotune.bayesian_generator import (
    BayesianCandidateGenerator,
    SearchSpace,
)
from polisyos.scientist.methods.autotune.models import BenchmarkSplit, MetricDirection
from polisyos.scientist.methods.search.controller import SearchIteration
from polisyos.scientist.methods.search.objective import (
    ObjectiveValue,
    OptimizationDirection,
)
from polisyos.scientist.methods.search.strategies import bayesian as module
from polisyos.scientist.methods.search.strategies.types import StrategyState

torch = pytest.importorskip(
    "torch", reason="UNRUN: native numerical adapter requires Torch"
)
pytest.importorskip(
    "botorch", reason="UNRUN: native numerical adapter requires BoTorch"
)
pytest.importorskip(
    "gpytorch", reason="UNRUN: native numerical adapter requires GPyTorch"
)
pytestmark = [pytest.mark.integration]


def test_mixed_public_space_matches_independent_physical_encoding():
    space = SearchSpace(
        [
            {"name": "x", "lower": 0, "upper": 10},
            {"name": "n", "lower": 0.2, "upper": 1.8, "dtype": "integer"},
            {"name": "scale", "lower": 1, "upper": 100, "log_scale": True},
            {"name": "regime", "dtype": "categorical", "categories": ["A", "B"]},
        ]
    )
    physical = {"x": 3.0, "n": 1, "scale": 10.0, "regime": "B"}
    expected = (0.3, 0.5, 0.5, 0.0, 1.0)
    assert space.normalize(physical) == pytest.approx(expected)
    executed = space.candidate_from_vector((0.3, 0.12, 0.5, 0.25, 0.75))
    assert executed.params == pytest.approx(physical)
    assert executed.params_normalized == pytest.approx(expected)
    assert space.normalize(space.denormalize(expected)) == pytest.approx(expected)


@pytest.mark.skipif(
    module.fit_gpytorch_mll is None, reason="optional GP stack unavailable"
)
def test_default_public_suggestion_consumes_real_seeded_torch_design():
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0, "upper": 10}])
    )
    assert generator.botorch_available
    # This locked profile selects Torch's scramble, whose seed is not a
    # portable SciPy scramble.  Compute its expected draw without the adapter.
    independent = float(
        torch.quasirandom.SobolEngine(1, scramble=True, seed=42).draw(1)[0, 0]
    )
    candidate = generator.generate([], {"x": 7}, {"sentinel": 1})
    assert candidate["x"] == pytest.approx(10 * independent)
    assert candidate["_strategy_metadata"]["source"] == "sobol_init"
    assert "sentinel" not in candidate


@pytest.mark.skipif(
    module.fit_gpytorch_mll is None, reason="optional GP stack unavailable"
)
@pytest.mark.parametrize(
    "direction", [MetricDirection.MINIMIZE, MetricDirection.MAXIMIZE]
)
def test_full_history_identity_reaches_actual_directional_training_and_json(direction):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0, "upper": 10}]),
        primary_metric="cost",
        direction=direction,
        compare_split=BenchmarkSplit.SELECTION,
        n_initial=4,
        seed=31,
    )
    history = []
    for i, (x, cost) in enumerate([(2, 20.0), (4, 8.0), (6, 4.0), (8, 8.0)], start=1):
        identity = {
            "candidate_id": f"sha256:{i:064x}",
            "evaluation_id": f"sha256:{i + 100:064x}",
            "origin": "declared-numerical-fixture",
            "split": "selection",
        }
        history.append(
            {
                "candidate": {"x": x, "_strategy_metadata": identity},
                "stage_a_passed": True,
                "stage_b_result": {**identity, "params": {"x": x}, "cost": cost},
            }
        )
    # A result-free fifth record must never become a fifth zero-valued observation.
    history.append({"candidate": {"x": 1}, "stage_a_passed": True})
    evaluations = generator._history_to_evaluations(history)
    assert len([row for row in evaluations if row.is_valid]) == 4
    for i, row in enumerate(evaluations[:4], start=1):
        assert row.candidate_id == f"sha256:{i:064x}"
        assert row.metadata["evaluation_id"] == f"sha256:{i + 100:064x}"
        assert row.metadata["origin"] == "declared-numerical-fixture"
        assert row.metadata["split"] == "selection"
    expected_x = [[0.2], [0.4], [0.6], [0.8]]
    sign = -1 if direction == MetricDirection.MINIMIZE else 1
    expected_y = [[sign * cost] for cost in (20.0, 8.0, 4.0, 8.0)]
    strategy = generator._optimizer
    train_x, train_y = strategy._prepare_training_data(evaluations)
    assert train_x.tolist() == expected_x
    assert train_y.tolist() == expected_y
    with patch.object(module, "fit_gpytorch_mll", wraps=module.fit_gpytorch_mll) as fit:
        strategy._fit_gp(train_x, train_y)
        state = StrategyState.from_artifact(strategy.get_state().to_artifact())
        restored = BayesianCandidateGenerator(
            generator._search_space,
            primary_metric="cost",
            direction=direction,
            compare_split=BenchmarkSplit.SELECTION,
            n_initial=4,
            seed=31,
        )._optimizer
        restored.set_state(state)
    assert fit.call_count == 1
    assert restored._fitted_train_X.tolist() == expected_x
    assert restored._fitted_train_y_bo.tolist() == expected_y
    assert len(restored._fitted_record_ids) == 4


@pytest.mark.skipif(
    module.fit_gpytorch_mll is None, reason="optional GP stack unavailable"
)
@pytest.mark.parametrize("malformed", [False, True, 10**400])
def test_unmeasured_scalar_does_not_launder_through_history_into_training(malformed):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0, "upper": 10}]),
        primary_metric="cost",
        direction=MetricDirection.MINIMIZE,
    )
    evaluations = generator._history_to_evaluations(
        [
            {"candidate": {"x": 2}, "stage_b_result": {"cost": 10.0}},
            {"candidate": {"x": 4}, "stage_b_result": {"cost": malformed}},
        ]
    )
    assert [row.is_valid for row in evaluations] == [True, False]
    train_x, train_y = generator._optimizer._prepare_training_data(evaluations)
    assert train_x.tolist() == [[0.2]]
    assert train_y.tolist() == [[-10.0]]


@pytest.mark.skipif(
    module.fit_gpytorch_mll is None, reason="optional GP stack unavailable"
)
@pytest.mark.parametrize("malformed", ["false", "true", 0, 1, None, [], {}])
def test_present_untyped_stage_admission_is_rejected_without_scalar_fallback(malformed):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0, "upper": 10}]),
        primary_metric="cost",
        direction=MetricDirection.MINIMIZE,
    )
    with patch.object(
        generator, "_history_score", side_effect=AssertionError("scalar fallback")
    ):
        evaluations = generator._history_to_evaluations(
            [
                {
                    "candidate": {"x": 4},
                    "stage_a_passed": malformed,
                    "stage_b_result": {"cost": 0.0},
                    "objective_value": 0.0,
                }
            ]
        )
    assert len(evaluations) == 1
    assert evaluations[0].is_valid is False
    assert evaluations[0].metadata["invalid_reason"] == "malformed_stage_a_passed"
    assert generator._optimizer._effective_training_corpus(evaluations) == []


@pytest.mark.skipif(
    module.fit_gpytorch_mll is None, reason="optional GP stack unavailable"
)
@pytest.mark.parametrize(
    ("present", "value", "valid"),
    [(False, None, True), (True, True, True), (True, False, False)],
)
def test_absent_and_declared_boolean_stage_contract_is_preserved(present, value, valid):
    generator = BayesianCandidateGenerator(
        SearchSpace([{"name": "x", "lower": 0, "upper": 10}]), primary_metric="cost"
    )
    entry = {"candidate": {"x": 4}, "stage_b_result": {"cost": 2.0}}
    if present:
        entry["stage_a_passed"] = value
    assert generator._history_to_evaluations([entry])[0].is_valid is valid


@pytest.mark.parametrize(
    "direction", [MetricDirection.MINIMIZE, MetricDirection.MAXIMIZE]
)
def test_mixed_history_formats_reach_public_generate_and_fresh_cas_next_proposal(
    tmp_path, direction
):
    """Both original history forms cross the public caller without identity loss."""

    def receiver():
        return BayesianCandidateGenerator(
            SearchSpace([{"name": "x", "lower": 0, "upper": 10}]),
            primary_metric="cost",
            direction=direction,
            compare_split=BenchmarkSplit.SELECTION,
            n_initial=4,
            seed=31,
        )

    history = []
    for i, (x, cost) in enumerate([(2, 20.0), (4, 8.0), (6, 4.0), (8, 8.0)], start=1):
        identity = {
            "candidate_id": f"sha256:{i:064x}",
            "evaluation_id": f"sha256:{i + 100:064x}",
            "origin": "declared-mixed-public-caller-fixture",
            "split": "selection",
        }
        candidate = {"x": x, "_strategy_metadata": identity}
        outcome = {**identity, "params": {"x": x}, "cost": cost}
        if i % 2:
            history.append(
                {
                    "candidate": candidate,
                    "stage_a_passed": True,
                    "stage_b_result": outcome,
                }
            )
        else:
            history.append(
                SearchIteration(
                    iteration=i,
                    candidate=candidate,
                    objective_value=cost,
                    objective_details=[
                        ObjectiveValue(
                            "cost", cost, OptimizationDirection(direction.value)
                        )
                    ],
                    is_promising=True,
                    stage_a_passed=True,
                    stage_b_result=outcome,
                    duration_seconds=0.1,
                )
            )
    # This fifth input has no measured outcome and must not supply a numeric zero.
    history.append({"candidate": {"x": 1}, "stage_a_passed": True})
    generator = receiver()
    assert generator.botorch_available and generator._optimizer._model is None
    expected_x = [[0.2], [0.4], [0.6], [0.8]]
    sign = -1 if direction == MetricDirection.MINIMIZE else 1
    expected_y = [[sign * cost] for cost in (20.0, 8.0, 4.0, 8.0)]
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    with patch.object(module, "fit_gpytorch_mll", wraps=module.fit_gpytorch_mll) as fit:
        first = generator.generate(history, None, {})
        assert first["_strategy_metadata"]["source"] == "bayesian_acquisition"
        strategy = generator._optimizer
        assert strategy._fitted_train_X.tolist() == expected_x
        assert strategy._fitted_train_y_bo.tolist() == expected_y
        assert len(strategy._fitted_record_ids) == 4
        state = generator.get_state()
        assert len(state["history_rows"]) == 5
        assert state["history_rows"][4]["evaluation"] is None
        for i, row in enumerate(state["history_rows"][:4], start=1):
            evaluation = row["evaluation"]
            assert evaluation["candidate_id"] == f"sha256:{i:064x}"
            assert evaluation["metadata"]["evaluation_id"] == f"sha256:{i + 100:064x}"
            assert (
                evaluation["metadata"]["origin"]
                == "declared-mixed-public-caller-fixture"
            )
            assert evaluation["metadata"]["split"] == "selection"
            assert evaluation["params"]["x"] == (2, 4, 6, 8)[i - 1]
        ref = store.put_bytes(
            json.dumps(state, sort_keys=True, allow_nan=False).encode(),
            artifacts.PutOptions(
                kind="search.generator_state", media_type="application/json"
            ),
        )
        fresh_store = artifacts.FileSystemCAS(tmp_path / "cas")
        fresh = receiver()
        fresh.set_state(json.loads(fresh_store.get_bytes(ref)))
        assert fit.call_count == 1, (
            "Fresh restoration must load actual fitted state without MLL"
        )
        assert fresh._optimizer._fitted_train_X.tolist() == expected_x
        assert fresh._optimizer._fitted_train_y_bo.tolist() == expected_y
        next_live = generator.generate(history, None, {})
        next_fresh = fresh.generate(history, None, {})
        assert next_live["_strategy_metadata"]["source"] == "bayesian_acquisition"
        assert next_fresh["_strategy_metadata"]["source"] == "bayesian_acquisition"
        assert next_live["x"] == next_fresh["x"]
        assert fit.call_count == 1, (
            "An unchanged complete corpus does not justify a refit"
        )
    print(
        "ACTUAL_MIXED_HISTORY_PUBLIC_CAS",
        direction.value,
        str(ref.artifact_id),
        expected_x,
        expected_y,
        next_fresh["x"],
    )


@pytest.mark.parametrize("operation", ["set_state", "validate_checkpoint_history"])
@pytest.mark.parametrize(
    "mutation", ["empty", "truncated", "empty_count", "truncated_count"]
)
def test_public_wrapper_consumption_count_cannot_be_erased_with_paired_history(
    tmp_path, operation, mutation
):
    """Native iteration independently binds the converted consumed-row denominator."""

    def receiver():
        return BayesianCandidateGenerator(
            SearchSpace([{"name": "x", "lower": 0, "upper": 10}]),
            primary_metric="cost",
            n_initial=6,
            seed=31,
        )

    history = [
        {"candidate": {"x": 2}, "stage_b_result": {"cost": 2.0}},
        {"candidate": {"x": 4}, "stage_a_passed": True},
        {"candidate": {"x": 6}, "stage_b_result": {"cost": 1.0}},
    ]
    live = receiver()
    assert live.botorch_available
    first = live.generate(history, None, {})
    assert first["_strategy_metadata"]["source"] == "sobol_init"
    state = live.get_state()
    assert state["schema_version"] == "bayesian_candidate_generator.v3"
    assert state["consumed_history_count"] == state["strategy_state"]["iteration"] == 3
    assert state["strategy_state"]["model_state"] is None
    assert len(state["history_rows"]) == len(state["history_digests"]) == 3
    assert state["history_rows"][1]["evaluation"] is None
    immutable_native = json.dumps(
        state["strategy_state"], sort_keys=True, allow_nan=False
    )
    size = 0 if mutation.startswith("empty") else 1
    state["history_rows"] = state["history_rows"][:size]
    state["history_digests"] = state["history_digests"][:size]
    if mutation.endswith("_count"):
        state["consumed_history_count"] = size
    assert (
        json.dumps(state["strategy_state"], sort_keys=True, allow_nan=False)
        == immutable_native
    )
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        json.dumps(state, sort_keys=True, allow_nan=False).encode(),
        artifacts.PutOptions(
            kind="search.generator_state", media_type="application/json"
        ),
    )
    incoming = json.loads(artifacts.FileSystemCAS(tmp_path / "cas").get_bytes(ref))
    fresh = receiver()
    before = json.dumps(fresh.get_state(), sort_keys=True, allow_nan=False)
    with pytest.raises(ValueError, match="current-row coverage"):
        if operation == "set_state":
            fresh.set_state(incoming)
        else:
            fresh.validate_checkpoint_history(history, incoming)
    assert json.dumps(fresh.get_state(), sort_keys=True, allow_nan=False) == before
    assert fresh._optimizer._model is None


def test_public_wrapper_count_covers_unavailable_converted_rows_and_skips_unusable_params(
    tmp_path,
):
    """The supported denominator is converted native inputs, not every raw row."""

    def receiver():
        return BayesianCandidateGenerator(
            SearchSpace([{"name": "x", "lower": 0, "upper": 10}]),
            primary_metric="cost",
            n_initial=6,
            seed=31,
        )

    history = [
        {"candidate": {"x": 2}, "stage_b_result": {"cost": 2.0}},
        {"candidate": {"x": 4}, "stage_a_passed": True},
        {"candidate": {"outside_declared_space": 8}, "stage_b_result": {"cost": 9.0}},
        {"candidate": {"x": 6}, "stage_b_result": {"cost": 1.0}},
    ]
    live = receiver()
    assert live.botorch_available
    assert (
        live.generate(history, None, {})["_strategy_metadata"]["source"] == "sobol_init"
    )
    state = live.get_state()
    assert state["consumed_history_count"] == state["strategy_state"]["iteration"] == 3
    assert len(history) == 4 and len(state["history_rows"]) == 3
    assert state["history_rows"][1]["evaluation"] is None
    assert [row["input_index"] for row in state["history_rows"]] == [0, 1, 2]
    live.validate_checkpoint_history(history, state)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = store.put_bytes(
        json.dumps(state, sort_keys=True, allow_nan=False).encode(),
        artifacts.PutOptions(
            kind="search.generator_state", media_type="application/json"
        ),
    )
    fresh = receiver()
    saved = json.loads(artifacts.FileSystemCAS(tmp_path / "cas").get_bytes(ref))
    fresh.validate_checkpoint_history(history, saved)
    fresh.set_state(saved)
    next_live = live.generate(history, None, {})
    next_fresh = fresh.generate(history, None, {})
    assert next_live["x"] == next_fresh["x"]
    assert next_fresh["_strategy_metadata"]["source"] == "sobol_init"
    assert fresh._optimizer._model is None


def test_public_wrapper_warm_eight_cas_rows_and_zero_current_history_restore_without_refit(
    tmp_path,
):
    """Warm corpus is independent of the receiving converted-history cursor."""
    from dataclasses import replace

    import numpy as np

    pytest.importorskip(
        "hnswlib", reason="UNRUN: original CAS warm discovery needs HNSW"
    )
    from botorch.models import SingleTaskGP

    from polisyos.scientist.methods.autotune.warm_start import WarmStartBridge
    from polisyos.scientist.methods.search.strategies.transfer import (
        TransferLearningManager,
    )
    from tests.unit.scientist.methods.search.strategies.test_transfer import (
        measured_history,
    )

    store, index, manager, _, target, _, basis = measured_history(tmp_path, count=8)

    def receiver(receiving_manager):
        bridge = WarmStartBridge(receiving_manager)
        generator = BayesianCandidateGenerator(
            SearchSpace(bounds=basis.bounds["parameters"]),
            primary_metric="score",
            direction=MetricDirection.MINIMIZE,
            compare_split=BenchmarkSplit.SELECTION,
            n_initial=3,
            seed=19,
            warm_start_bridge=bridge,
            warm_start_fingerprint=target,
        )
        assert generator.botorch_available
        generator._optimizer._config = replace(
            generator._optimizer._config,
            num_restarts=2,
            raw_samples=32,
            refit_interval=20,
            fallback_on_failure=False,
        )
        return generator, bridge

    live, bridge = receiver(manager)
    warm = bridge.load_warm_start(target)
    assert len(warm) == len(live._optimizer._warm_evals) == 8
    expected_x = torch.tensor(
        [row.params_normalized for row in warm], dtype=torch.double
    )
    expected_y = torch.tensor([[-row.scalar_score] for row in warm], dtype=torch.double)
    raw_x = np.asarray([row.params_normalized for row in warm], dtype=np.float64)
    raw_y = np.asarray([-row.scalar_score for row in warm], dtype=np.float64)
    minimum, maximum = raw_x.min(axis=0), raw_x.max(axis=0)
    standardized_x = (raw_x - minimum) / (maximum - minimum)
    mean, sample_std = raw_y.mean(), raw_y.std(ddof=1)
    standardized_y = (raw_y - mean) / sample_std

    def assert_actual_backend_corpus(model):
        # Independent arithmetic from the original resolved rows, not model transforms.
        assert model.train_inputs[0].detach().cpu().numpy() == pytest.approx(
            standardized_x
        )
        assert model.train_targets.detach().cpu().numpy() == pytest.approx(
            standardized_y
        )
        assert model.input_transform.bounds.detach().cpu().numpy() == pytest.approx(
            np.vstack([minimum, maximum])
        )
        assert model.outcome_transform.means.item() == pytest.approx(mean)
        assert model.outcome_transform.stdvs.item() == pytest.approx(sample_std)

    with patch.object(module, "fit_gpytorch_mll", wraps=module.fit_gpytorch_mll) as fit:
        first = live.generate([], None, {})
        assert first["_strategy_metadata"]["source"] == "bayesian_acquisition"
        assert isinstance(live._optimizer._model, SingleTaskGP)
        assert_actual_backend_corpus(live._optimizer._model)
        state = live.get_state()
        assert (
            state["consumed_history_count"] == state["strategy_state"]["iteration"] == 0
        )
        assert state["history_rows"] == state["history_digests"] == []
        assert len(state["strategy_state"]["metadata"]["warm_evaluations"]) == 8
        assert torch.equal(live._optimizer._fitted_train_X.cpu(), expected_x)
        assert torch.equal(live._optimizer._fitted_train_y_bo.cpu(), expected_y)
        ref = store.put_bytes(
            json.dumps(state, sort_keys=True, allow_nan=False).encode(),
            artifacts.PutOptions(
                kind="search.generator_state", media_type="application/json"
            ),
        )
        fresh_store = artifacts.FileSystemCAS(tmp_path / "cas")
        fresh, _ = receiver(TransferLearningManager(fresh_store, index))
        saved = json.loads(fresh_store.get_bytes(ref))
        fresh.validate_checkpoint_history([], saved)
        ambient = torch.random.get_rng_state().clone()
        fresh.set_state(saved)
        assert torch.equal(torch.random.get_rng_state(), ambient)
        assert fit.call_count == 1, (
            "The fresh wrapper must restore actual fitted state without MLL"
        )
        assert isinstance(fresh._optimizer._model, SingleTaskGP)
        assert_actual_backend_corpus(fresh._optimizer._model)
        assert torch.equal(fresh._optimizer._fitted_train_X.cpu(), expected_x)
        assert torch.equal(fresh._optimizer._fitted_train_y_bo.cpu(), expected_y)
        assert {row.provenance_ref for row in fresh._optimizer._warm_evals} == {
            row.provenance_ref for row in warm
        }
        next_live = live.generate([], None, {})
        next_fresh = fresh.generate([], None, {})
        assert next_live["x"] == next_fresh["x"]
        assert next_fresh["_strategy_metadata"]["source"] == "bayesian_acquisition"
        assert fit.call_count == 1, (
            "Unchanged warm-only corpus does not justify a refit"
        )
    print(
        "ACTUAL_WRAPPER_V3_WARM_ZERO_CURRENT",
        str(ref.artifact_id),
        expected_x.tolist(),
        expected_y.tolist(),
    )
