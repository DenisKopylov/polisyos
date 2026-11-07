"""Selected transfer history and neural cold-start checkpoint replay."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.methods.search.objective import (
    GDPGrowthObjective,
    configured_objective_rule_spec,
)
from polisyos.scientist.methods.search.strategies.neural import (
    NeuralSearchConfig,
    NeuralSearchStrategy,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    ParameterBounds,
    StrategyState,
)


def _source(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    manager = TransferLearningManager(store, object())
    space = SearchSpace([ParameterBounds("x", 0.0, 1.0)])
    objective = GDPGrowthObjective(expected_unit="fixture-unit")
    source = RunFingerprint(
        run_id="source-run",
        space_hash=space.sobol_space_fingerprint(),
        objective_names=[objective.name],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={objective.name: "fixture-unit"},
        origin="fixture",
        tenant_id="fixture",
        objective_directions={objective.name: objective.direction.value},
        objective_rule_specs={objective.name: configured_objective_rule_spec(objective) or ""},
    )

    measured = {"gdp_change": 0.1, "metric_units": {"gdp_change": "fixture-unit"}}
    value = objective.evaluate(measured)
    observation = Evaluation(
        candidate_id="candidate",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[value],
        scalar_score=value.raw_value,
        stage_a_passed=True,
        stage_b_result=measured,
        score_status=value.score_status,
        score_assessment=value.score_assessment,
    )
    ref = manager.register_run(source, [observation])
    assert ref is not None
    selected = source.model_copy(update={"history_ref": ref})
    target = source.model_copy(update={"run_id": "target-run"})
    assert len(manager.get_warm_start_evaluations([selected], target_fingerprint=target)) == 1
    return store, manager, space, selected, target


def _neural(space, manager, target):
    return NeuralSearchStrategy(
        space,
        NeuralSearchConfig(n_initial=10, seed=19),
        transfer_manager=manager,
        transfer_target=target,
    )


def test_selected_cas_warm_corpus_and_neural_next_sobol_survive_fresh_restore(tmp_path: Path):
    store, manager, space, source, target = _source(tmp_path)
    live = _neural(space, manager, target)
    live.warm_start_from_transfer([source], max_evaluations=10)
    first = live.suggest([])
    assert first.source_strategy == "neural_sobol_init"
    ref = store.put_bytes(
        live.get_state().to_artifact(),
        PutOptions(kind="search.strategy_state", media_type="application/octet-stream"),
        return_selected_profile=True,
    )
    fresh_store = FileSystemCAS(tmp_path / "cas")
    fresh_manager = TransferLearningManager(fresh_store, object())
    fresh = _neural(space, fresh_manager, target)
    fresh.set_state(StrategyState.from_artifact(fresh_store.get_bytes(ref)))
    expected, actual = live.suggest([]), fresh.suggest([])
    assert actual.source_strategy == expected.source_strategy == "neural_sobol_init"
    assert actual.params == expected.params
    assert len(fresh._warm_data) == len(live._warm_data) == 1
    assert fresh._sobol_cursor == live._sobol_cursor


def test_changed_history_bytes_refuse_fresh_neural_restore(tmp_path: Path):
    store, manager, space, source, target = _source(tmp_path)
    live = _neural(space, manager, target)
    live.warm_start_from_transfer([source], max_evaluations=10)
    saved = StrategyState.from_artifact(live.get_state().to_artifact())
    fresh = _neural(
        space, TransferLearningManager(FileSystemCAS(tmp_path / "cas"), object()), target
    )
    before = fresh.get_state().to_artifact()
    path, _ = store._paths(source.history_ref.artifact_id)
    path.write_bytes(b"changed source bytes with unchanged selected reference")
    with pytest.raises(ValueError):
        fresh.set_state(saved)
    assert fresh.get_state().to_artifact() == before


def test_changed_history_bytes_refuse_existing_live_consumer(tmp_path: Path):
    store, manager, space, source, target = _source(tmp_path)
    live = _neural(space, manager, target)
    live.warm_start_from_transfer([source], max_evaluations=10)
    before_iteration = live._iteration
    path, _ = store._paths(source.history_ref.artifact_id)
    path.write_bytes(b"changed source bytes with unchanged selected reference")
    with pytest.raises(ValueError):
        live.suggest([])
    assert live._iteration == before_iteration


def test_mutated_live_observation_is_not_equated_by_python_bool_int_equality(tmp_path: Path):
    _, manager, space, source, target = _source(tmp_path)
    live = _neural(space, manager, target)
    live.warm_start_from_transfer([source], max_evaluations=10)
    live._warm_data[0].stage_a_passed = 1
    with pytest.raises(ValueError, match="observations changed"):
        live.suggest([])


@pytest.mark.parametrize("field", ["score", "count", "target", "source_profile", "rng"])
def test_checkpoint_rejects_different_semantic_input_without_mutation(tmp_path: Path, field: str):
    _, manager, space, source, target = _source(tmp_path)
    live = _neural(space, manager, target)
    live.warm_start_from_transfer([source], max_evaluations=10)
    saved = StrategyState.from_artifact(live.get_state().to_artifact())
    if field == "score":
        saved.metadata["warm_values"][0]["scalar_score"] = 999.0
    elif field == "count":
        saved.metadata["warm_start_count"] = 2
    elif field == "target":
        saved.metadata["transfer_target"]["run_id"] = "another-target"
    elif field == "source_profile":
        saved.metadata["transfer_sources"][0]["history_ref"]["manifest_profile_sha256"] = "0" * 64
    else:
        saved.rng_state["python"]["codec_version"] = 999
    fresh = _neural(space, manager, target)
    before = fresh.get_state().to_artifact()
    with pytest.raises(ValueError):
        fresh.set_state(saved)
    assert fresh.get_state().to_artifact() == before


def test_changed_source_basis_does_not_enter_selected_corpus(tmp_path: Path):
    _, manager, space, source, target = _source(tmp_path)
    foreign = source.model_copy(deep=True)
    foreign.run_id = "foreign-run"
    foreign.units = {next(iter(foreign.units)): "other-unit"}
    live = _neural(space, manager, target)
    before = live.get_state().to_artifact()
    with pytest.raises(ValueError, match="source does not match"):
        live.warm_start_from_transfer([source, foreign], max_evaluations=10)
    assert live.get_state().to_artifact() == before


def test_two_valid_profiles_of_same_run_do_not_double_warm_corpus(tmp_path: Path):
    store, manager, space, source, target = _source(tmp_path)
    payload = from_canonical_bytes(store.get_bytes(source.history_ref))
    alternative = store.put_json(
        payload,
        PutOptions(kind="search.transfer.history", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False, max_depth=63),
        return_selected_profile=True,
    )
    assert alternative.artifact_id == source.history_ref.artifact_id
    assert alternative.manifest_profile_sha256 != source.history_ref.manifest_profile_sha256
    second = source.model_copy(update={"history_ref": alternative})
    live = _neural(space, manager, target)
    before = live.get_state().to_artifact()
    with pytest.raises(ValueError, match="duplicate source run"):
        live.warm_start_from_transfer([source, second], max_evaluations=10)
    assert live.get_state().to_artifact() == before


def test_unbound_warm_rows_and_legacy_checkpoint_are_not_silently_restored(tmp_path: Path):
    _, manager, space, source, target = _source(tmp_path)
    live = _neural(space, manager, target)
    rows = manager.get_warm_start_evaluations([source], target_fingerprint=target)
    live.warm_start(deepcopy(rows))
    with pytest.raises(ValueError, match="selected transfer corpus"):
        live.get_state()
    fresh = _neural(space, manager, target)
    state = fresh.get_state()
    del state.metadata["neural_state_profile"]
    with pytest.raises(ValueError, match="supported Sobol"):
        fresh.set_state(state)


def test_checkpoint_after_surrogate_use_refuses_unsupported_continuity(tmp_path: Path, monkeypatch):
    _, manager, space, source, target = _source(tmp_path)
    live = NeuralSearchStrategy(
        space,
        NeuralSearchConfig(n_initial=1, seed=19),
        transfer_manager=manager,
        transfer_target=target,
    )
    live.warm_start_from_transfer([source], max_evaluations=10)
    from polisyos.scientist.methods.search.strategies.types import PolicyCandidate

    monkeypatch.setattr(
        live,
        "_suggest_from_surrogate",
        lambda evaluations, pending: PolicyCandidate(params={"x": 0.5}, source_strategy="stub"),
    )
    assert live.suggest([]).source_strategy == "stub"
    with pytest.raises(ValueError, match="fitted-surrogate checkpoint"):
        live.get_state()
