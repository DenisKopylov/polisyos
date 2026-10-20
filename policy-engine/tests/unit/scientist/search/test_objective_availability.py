from __future__ import annotations

from types import SimpleNamespace

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.contracts import SearchIteration
from polisyos.scientist.methods.search.lessons import success_lesson_from_outcome
from polisyos.scientist.methods.search.lifecycle import _SearchLifecycleOwner
from polisyos.scientist.methods.search.objective import (
    BudgetDeficitObjective,
    CompositeObjective,
    EmploymentObjective,
    GDPGrowthObjective,
    ObjectiveScoreStatus,
    ObjectiveValue,
    OptimizationDirection,
    _assess_default_search_objective,
    _assess_search_metric,
    _configured_search_metric_binding,
    _configured_search_metric_profile_fingerprint,
    configured_objective_rule_spec,
    objective_value_matches_rule,
    score_assessment_matches_source,
)
from polisyos.scientist.methods.search.strategies.bayesian import BayesianOptimizer
from polisyos.scientist.methods.search.strategies.errors import (
    OptionalDependencyUnavailableError,
)
from polisyos.scientist.methods.search.strategies.multi_objective import (
    MOBayesianOptimizer,
)
from polisyos.scientist.methods.search.strategies.space import SearchSpace
from polisyos.scientist.methods.search.strategies.transfer import (
    RunFingerprint,
    TransferLearningManager,
)
from polisyos.scientist.methods.search.strategies.types import (
    Evaluation,
    ParameterBounds,
)
from polisyos.scientist.methods.search.voi_scheduler import (
    PredictiveVOIScheduler,
    VOIModelSnapshot,
    VOIObservation,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    selection_score,
)
from polisyos.scientist.policy_design.objectives import (
    ObjectiveChannelValue,
    ObjectiveDirection,
    ObjectiveKind,
    ObjectiveStack,
    PolicyEvaluationBundle,
    PolicyEvaluationVector,
    _policy_vector_channel_rule_spec,
)
from polisyos.scientist.policy_design.search import (
    _diagnostic_policy_score,
    _history_record,
    _policy_rank_key,
)

_FIXTURE_UNIT_FIELDS = {
    "gdp_change",
    "gov_balance",
    "government_balance",
    "budget_deficit",
    "deficit",
    "gini_coefficient",
    "employment_rate",
    "score",
}


def _with_fixture_units(source: dict[str, object]) -> dict[str, object]:
    """Attach only the explicit synthetic unit to values present in this fixture."""
    unit_map = source.get("metric_units")
    units = dict(unit_map) if isinstance(unit_map, dict) else {}
    containers = [source]
    for key in ("simulation_results", "metrics"):
        nested = source.get(key)
        if isinstance(nested, dict):
            containers.append(nested)
    for container in containers:
        for name in _FIXTURE_UNIT_FIELDS:
            if name in container and container[name] is not None:
                units.setdefault(name, "fixture-unit")
    source["metric_units"] = units
    return source


def _runtime_vector(
    *,
    values: dict[str, float],
    invocation: dict[str, object] | None = None,
) -> tuple[PolicyEvaluationVector, dict[str, object]]:
    runtime = invocation or {
        "evaluation_attempt_id": "attempt-01",
        "requested_draw_count": 0,
        "requested_draw_source": "fixture",
        "effective_estimation_config_sha256": "a" * 64,
    }
    source = {
        "objective_channels": dict(values),
        "metric_units": {f"channel:primary:{name}": "fixture-unit" for name in values},
        "feasible": True,
        "blocking_reasons": [],
        "bootstrap": dict(runtime),
    }
    primary = {
        name: ObjectiveChannelValue(
            name=name,
            kind=ObjectiveKind.PRIMARY,
            value=value,
            direction=ObjectiveDirection.MAXIMIZE,
            expected_unit="fixture-unit",
        )
        for name, value in values.items()
    }
    vector = PolicyEvaluationVector(
        primary=primary, metadata={"policy_runtime_invocation": runtime}
    )
    vector = vector.with_runtime_score_assessment(runtime)
    return vector.with_score_source_results(source), source


def _evaluation(
    *,
    candidate_id: str,
    objective_source: dict[str, object],
) -> Evaluation:
    objective = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(
        _with_fixture_units(objective_source)
    )
    assert objective.score_assessment is not None
    return Evaluation(
        candidate_id=candidate_id,
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[objective],
        scalar_score=objective.score_assessment.value,
        stage_a_passed=True,
        stage_b_result=objective_source,
        score_status=objective.score_status,
        score_assessment=objective.score_assessment,
    )


def test_default_scalar_requires_its_complete_basis_but_other_objectives_do_not() -> None:
    fiscal_only = {"budget_deficit": 100.0}
    selected_fiscal = BudgetDeficitObjective(expected_unit="fixture-unit").evaluate(
        _with_fixture_units(fiscal_only)
    )
    assert selected_fiscal.score_status is ObjectiveScoreStatus.AVAILABLE
    assert selected_fiscal.raw_value == 100.0

    missing_gdp = _assess_default_search_objective({"budget_deficit": 100.0})
    assert missing_gdp.objective_value is None
    assert missing_gdp.score_status is ObjectiveScoreStatus.UNAVAILABLE

    same_gdp_unknown = _assess_default_search_objective({"gdp_change": 0.0})
    same_gdp_known = _assess_default_search_objective(
        _with_fixture_units({"gdp_change": 0.0, "budget_deficit": 100.0}),
        expected_unit="fixture-unit",
    )
    assert same_gdp_unknown.objective_value is None
    assert same_gdp_known.score_status is ObjectiveScoreStatus.AVAILABLE
    assert same_gdp_known.objective_value == 50.0


def test_missing_or_malformed_default_operands_never_become_zero() -> None:
    malformed_cases = (
        {"gdp_change": None, "budget_deficit": 100.0},
        {"gdp_change": True, "budget_deficit": 100.0},
        {"gdp_change": "bad", "budget_deficit": 100.0},
        {"gdp_change": float("inf"), "budget_deficit": 100.0},
    )
    assert (
        _assess_default_search_objective(
            _with_fixture_units({"gdp_change": 0.0, "budget_deficit": 100.0}),
            expected_unit="fixture-unit",
        ).score_status
        is ObjectiveScoreStatus.AVAILABLE
    )
    for source in malformed_cases:
        assessment = _assess_default_search_objective(
            _with_fixture_units(source), expected_unit="fixture-unit"
        )
        assert assessment.objective_value is None
        assert assessment.score_status is ObjectiveScoreStatus.INVALID


def test_fiscal_reader_reconciles_both_supplied_alias_groups_without_inventing_precedence() -> None:
    objective = BudgetDeficitObjective(expected_unit="fixture-unit")

    contradicting = objective.evaluate(
        _with_fixture_units({"gov_balance": -100.0, "budget_deficit": 20.0})
    )
    assert contradicting.score_status is ObjectiveScoreStatus.INVALID
    assert contradicting.raw_value != contradicting.raw_value  # invalid diagnostic is NaN
    assert not score_assessment_matches_source(
        contradicting.score_assessment,
        _with_fixture_units({"gov_balance": -100.0, "budget_deficit": 20.0}),
    )

    nested_conflict = objective.evaluate(
        _with_fixture_units({"gov_balance": -100.0, "simulation_results": {"budget_deficit": 20.0}})
    )
    assert nested_conflict.score_status is ObjectiveScoreStatus.INVALID
    assert not score_assessment_matches_source(
        nested_conflict.score_assessment,
        _with_fixture_units(
            {"gov_balance": -100.0, "simulation_results": {"budget_deficit": 20.0}}
        ),
    )

    matching = objective.evaluate(
        _with_fixture_units({"government_balance": -100.0, "deficit": 100.0})
    )
    assert matching.score_status is ObjectiveScoreStatus.AVAILABLE
    assert matching.raw_value == 100.0
    assert score_assessment_matches_source(
        matching.score_assessment,
        _with_fixture_units({"government_balance": -100.0, "deficit": 100.0}),
    )

    null_primary_fallback = objective.evaluate(
        _with_fixture_units({"gov_balance": None, "budget_deficit": 100.0})
    )
    assert null_primary_fallback.score_status is ObjectiveScoreStatus.AVAILABLE
    assert null_primary_fallback.raw_value == 100.0
    assert score_assessment_matches_source(
        null_primary_fallback.score_assessment,
        _with_fixture_units({"gov_balance": None, "budget_deficit": 100.0}),
    )

    malformed_primary = objective.evaluate(
        _with_fixture_units({"gov_balance": "bad", "budget_deficit": 100.0})
    )
    malformed_alternate = objective.evaluate(
        _with_fixture_units({"gov_balance": -100.0, "budget_deficit": "bad"})
    )
    assert malformed_primary.score_status is ObjectiveScoreStatus.INVALID
    assert malformed_alternate.score_status is ObjectiveScoreStatus.INVALID

    missing_fiscal = objective.evaluate(
        _with_fixture_units({"gov_balance": None, "budget_deficit": None})
    )
    assert missing_fiscal.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert not score_assessment_matches_source(
        null_primary_fallback.score_assessment,
        _with_fixture_units({"gov_balance": None, "budget_deficit": 90.0}),
    )

    true_zero = objective.evaluate(_with_fixture_units({"gov_balance": 0.0, "budget_deficit": 0.0}))
    assert true_zero.score_status is ObjectiveScoreStatus.AVAILABLE
    assert true_zero.raw_value == 0.0
    assert score_assessment_matches_source(
        true_zero.score_assessment, _with_fixture_units({"gov_balance": 0.0, "budget_deficit": 0.0})
    )


def test_selected_rule_binding_is_generic_over_labels_and_rejects_wrong_rule() -> None:
    source = {
        "gdp_change": 0.0,
        "gov_balance": -100.0,
        "budget_deficit": 100.0,
    }
    gdp = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(_with_fixture_units(source))
    assert gdp.score_assessment is not None
    relabeled_gdp = gdp.__class__(
        name="budget_deficit",
        raw_value=gdp.raw_value,
        direction=gdp.direction,
        weight=gdp.weight,
        is_satisfied=gdp.is_satisfied,
        threshold=gdp.threshold,
        score_status=gdp.score_status,
        score_assessment=gdp.score_assessment,
    )
    assert objective_value_matches_rule(
        relabeled_gdp,
        source,
        expected_name="budget_deficit",
        expected_direction=gdp.direction,
        expected_rule_spec=configured_objective_rule_spec(
            GDPGrowthObjective(expected_unit="fixture-unit")
        )
        or "",
    )
    budget_rule = (
        configured_objective_rule_spec(BudgetDeficitObjective(expected_unit="fixture-unit")) or ""
    )
    assert not objective_value_matches_rule(
        relabeled_gdp,
        source,
        expected_name="budget_deficit",
        expected_direction=BudgetDeficitObjective(expected_unit="fixture-unit").direction,
        expected_rule_spec=budget_rule,
    )
    wrong_rule_evaluation = Evaluation(
        candidate_id="wrong-rule-under-fiscal-label",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[relabeled_gdp],
        scalar_score=0.0,
        stage_a_passed=True,
        stage_b_result=source,
        score_status=gdp.score_status,
        score_assessment=gdp.score_assessment,
    )
    optimizer = object.__new__(MOBayesianOptimizer)
    optimizer._objective_names = ["budget_deficit"]
    optimizer._directions = [BudgetDeficitObjective(expected_unit="fixture-unit").direction]
    optimizer._objective_rule_specs = {"budget_deficit": budget_rule}
    optimizer._negate_mask = [1.0]
    assert wrong_rule_evaluation.is_valid
    assert not optimizer._has_complete_objective_basis(wrong_rule_evaluation)
    wrong_rule_fingerprint = RunFingerprint(
        run_id="wrong-rule-run",
        space_hash="synthetic-space-v1",
        objective_names=["budget_deficit"],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={"budget_deficit": "fixture-unit"},
        origin="synthetic-fixture",
        tenant_id="fixture",
        objective_directions={
            "budget_deficit": BudgetDeficitObjective(expected_unit="fixture-unit").direction.value
        },
        objective_rule_specs={"budget_deficit": budget_rule},
    )
    assert not TransferLearningManager._evaluation_matches_fingerprint(
        wrong_rule_evaluation, wrong_rule_fingerprint
    )

    custom_gdp = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(
        _with_fixture_units(source)
    )
    custom_gdp = ObjectiveValue(
        name="budget_deficit",
        raw_value=custom_gdp.raw_value,
        direction=custom_gdp.direction,
        score_status=custom_gdp.score_status,
        score_assessment=custom_gdp.score_assessment,
    )
    custom_expected = object.__new__(MOBayesianOptimizer)
    custom_expected._objective_names = ["budget_deficit"]
    custom_expected._directions = [GDPGrowthObjective(expected_unit="fixture-unit").direction]
    custom_expected._objective_rule_specs = {
        "budget_deficit": configured_objective_rule_spec(
            GDPGrowthObjective(expected_unit="fixture-unit")
        )
        or ""
    }
    custom_expected._negate_mask = [-1.0]
    custom_evaluation = Evaluation(
        candidate_id="configured-gdp-with-custom-label",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[custom_gdp],
        scalar_score=0.0,
        stage_a_passed=True,
        stage_b_result=source,
        score_status=custom_gdp.score_status,
        score_assessment=custom_gdp.score_assessment,
    )
    assert custom_expected._has_complete_objective_basis(custom_evaluation)

    fiscal_zero = BudgetDeficitObjective(expected_unit="fixture-unit").evaluate(
        _with_fixture_units({"gov_balance": 0.0, "budget_deficit": 0.0})
    )
    assert objective_value_matches_rule(
        fiscal_zero,
        {"gov_balance": 0.0, "budget_deficit": 0.0},
        expected_name="budget_deficit",
        expected_direction=BudgetDeficitObjective(expected_unit="fixture-unit").direction,
        expected_rule_spec=budget_rule,
    )


def test_marker_cannot_upgrade_absent_or_conflicting_fiscal_source() -> None:
    marker_only = _assess_default_search_objective(
        {
            "gdp_change": 0.0,
            "budget_deficit_objective_usable": True,
            "budget_deficit_objective_value": 0.0,
        }
    )
    conflict = _assess_default_search_objective(
        {
            "gdp_change": 0.0,
            "gov_balance": -100.0,
            "budget_deficit_objective_usable": True,
            "budget_deficit_objective_value": 0.0,
        }
    )
    assert marker_only.score_status is ObjectiveScoreStatus.INVALID
    assert marker_only.objective_value is None
    assert conflict.score_status is ObjectiveScoreStatus.INVALID
    assert conflict.objective_value is None


def test_runtime_vector_assessment_fails_after_source_or_invocation_binding_is_stripped() -> None:
    vector, source = _runtime_vector(values={"policy_value": 0.25, "employment": 0.1})
    score, status = vector.legacy_scalar_proxy_for_search(source)
    assert status is ObjectiveScoreStatus.AVAILABLE
    assert score == vector.legacy_scalar_proxy
    assert vector.frontier_objectives("global_feasible", source)
    persisted = PolicyEvaluationVector.model_validate(vector.model_dump(mode="json"))
    assert persisted.legacy_scalar_proxy_for_search() == (
        vector.legacy_scalar_proxy,
        ObjectiveScoreStatus.AVAILABLE,
    )
    assert persisted.frontier_objectives("global_feasible")
    stripped_basis = PolicyEvaluationVector.model_validate(
        {
            key: value
            for key, value in vector.model_dump(mode="json").items()
            if key != "score_source"
        }
    )
    assert stripped_basis.legacy_scalar_proxy_for_search()[1] is (
        ObjectiveScoreStatus.NOT_ESTABLISHED
    )

    stripped = vector.model_copy(update={"metadata": {}})
    assert stripped.legacy_scalar_proxy_for_search(source) == (
        None,
        ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    assert stripped.frontier_objectives("global_feasible", source) == {}

    changed_source = {
        **source,
        "objective_channels": {"policy_value": 0.25, "employment": 0.1001},
    }
    assert vector.legacy_scalar_proxy_for_search(changed_source) == (
        None,
        ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    changed_feasibility = {**source, "feasible": False, "blocking_reasons": ["budget"]}
    assert vector.legacy_scalar_proxy_for_search(changed_feasibility)[1] is (
        ObjectiveScoreStatus.NOT_ESTABLISHED
    )
    changed_blockers = {**source, "blocking_reasons": ["budget"]}
    assert vector.legacy_scalar_proxy_for_search(changed_blockers)[1] is (
        ObjectiveScoreStatus.NOT_ESTABLISHED
    )
    missing_formula_operands = {
        "objective_channels": source["objective_channels"],
        "bootstrap": source["bootstrap"],
    }
    assert vector.legacy_scalar_proxy_for_search(missing_formula_operands)[1] is (
        ObjectiveScoreStatus.NOT_ESTABLISHED
    )

    blocked_source = {**source, "feasible": False, "blocking_reasons": ["budget"]}
    blocked_vector = (
        vector.model_copy(
            update={"feasible": False, "blocking_reasons": ["budget"], "score_source": None}
        )
        .with_runtime_score_assessment(source["bootstrap"])
        .with_score_source_results(blocked_source)
    )
    assert blocked_vector.legacy_scalar_proxy_for_search(blocked_source) == (
        blocked_vector.legacy_scalar_proxy,
        ObjectiveScoreStatus.AVAILABLE,
    )


def test_vector_score_requires_bound_source_payload_not_a_producer_label() -> None:
    vector, source = _runtime_vector(values={"policy_value": 0.0, "employment": 0.1})
    assert vector.score_assessment is not None
    assert vector.score_assessment.status is ObjectiveScoreStatus.AVAILABLE
    assert "source_kind" not in vector.score_assessment.rule_spec
    assert vector.legacy_scalar_proxy_for_search(source)[1] is ObjectiveScoreStatus.AVAILABLE

    unbound = vector.model_copy(update={"score_source": None})
    assert unbound.legacy_scalar_proxy_for_search(source) == (
        None,
        ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    changed_source = {
        **source,
        "objective_channels": {"policy_value": 0.0, "employment": 0.1001},
    }
    assert vector.legacy_scalar_proxy_for_search(changed_source) == (
        None,
        ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    changed_embedded_source = vector.model_copy(
        update={
            "score_source": {
                **dict(vector.score_source or {}),
                "objective_channels": {"policy_value": 0.0, "employment": 0.1001},
            }
        }
    )
    assert changed_embedded_source.legacy_scalar_proxy_for_search()[1] is (
        ObjectiveScoreStatus.NOT_ESTABLISHED
    )
    stripped_runtime = vector.model_copy(update={"metadata": {}})
    assert stripped_runtime.legacy_scalar_proxy_for_search(source)[1] is (
        ObjectiveScoreStatus.NOT_ESTABLISHED
    )


def test_runtime_selection_consumer_refuses_unbound_or_empty_score() -> None:
    vector, _ = _runtime_vector(values={"policy_value": 0.0, "employment": 0.1})
    assert selection_score(vector) == 0.0
    with pytest.raises(ValueError, match="not source-bound"):
        selection_score(vector.model_copy(update={"score_source": None}))
    with pytest.raises(ValueError, match="not source-bound"):
        selection_score(PolicyEvaluationVector())


def test_success_lesson_does_not_turn_missing_score_into_numeric_zero() -> None:
    unscored = SimpleNamespace(
        final_result=SimpleNamespace(
            stage_name="funnel_L4_full",
            fidelity_level=4,
            objective_value=None,
            score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
            score_assessment=None,
        ),
        final_action="complete",
        candidate_hash="candidate-unscored",
    )
    lesson = success_lesson_from_outcome(unscored, source_run_id="run-unscored")
    assert "objective" not in lesson.summary
    assert lesson.metadata["objective_score_status"] == "not_established"

    known_zero = SimpleNamespace(
        final_result=SimpleNamespace(
            stage_name="funnel_L4_full",
            fidelity_level=4,
            objective_value=0.0,
            score_status=ObjectiveScoreStatus.AVAILABLE,
            score_assessment=SimpleNamespace(value=0.0, status=ObjectiveScoreStatus.AVAILABLE),
        ),
        final_action="complete",
        candidate_hash="candidate-zero",
    )
    zero_lesson = success_lesson_from_outcome(known_zero, source_run_id="run-zero")
    assert "objective 0.0000" in zero_lesson.summary


def test_objective_stack_scalar_stays_unbound_until_source_is_emitted() -> None:
    vector = ObjectiveStack().evaluate(
        PolicyEvaluationBundle(simulation_metrics={"gdp_change": 0.0})
    )
    assert vector.score_assessment is not None
    assert vector.score_assessment.status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert vector.legacy_scalar_proxy_for_search() == (
        None,
        ObjectiveScoreStatus.NOT_ESTABLISHED,
    )

    empty = PolicyEvaluationVector()
    assert empty.legacy_scalar_proxy_for_search() == (
        None,
        ObjectiveScoreStatus.NOT_ESTABLISHED,
    )


def test_recomputed_objective_assessment_rejects_consistently_forged_source_values() -> None:
    source = {"gdp_change": 0.0}
    assessment = (
        GDPGrowthObjective(expected_unit="fixture-unit")
        .evaluate(_with_fixture_units(source))
        .score_assessment
    )
    assert assessment is not None
    assert score_assessment_matches_source(assessment, _with_fixture_units(source))
    assert not score_assessment_matches_source(assessment, _with_fixture_units({"gdp_change": 2.0}))


def test_objective_score_requires_exact_selected_and_observed_unit_binding() -> None:
    configured = GDPGrowthObjective(expected_unit="percentage-points")
    source = {"gdp_change": 0.0, "metric_units": {"gdp_change": "percentage-points"}}
    available = configured.evaluate(source)
    assert available.score_status is ObjectiveScoreStatus.AVAILABLE
    assert available.raw_value == 0.0
    assert available.score_assessment is not None
    assert available.score_assessment.source_unit_bindings == (("gdp_change", "percentage-points"),)
    assert "metric_units.gdp_change" in available.score_assessment.source_field_names
    assert score_assessment_matches_source(available.score_assessment, _with_fixture_units(source))

    no_selected_unit = GDPGrowthObjective().evaluate(source)
    no_observed_unit = configured.evaluate({"gdp_change": 0.0})
    wrong_observed_unit = configured.evaluate(
        {"gdp_change": 0.0, "metric_units": {"gdp_change": "fraction"}}
    )
    malformed_observed_unit = configured.evaluate(
        {"gdp_change": 0.0, "metric_units": {"gdp_change": 7}}
    )
    assert no_selected_unit.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert no_observed_unit.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert wrong_observed_unit.score_status is ObjectiveScoreStatus.INVALID
    assert malformed_observed_unit.score_status is ObjectiveScoreStatus.INVALID

    null_alias_fallback = BudgetDeficitObjective(expected_unit="currency-unit").evaluate(
        {
            "gov_balance": None,
            "budget_deficit": 0.0,
            "metric_units": {"budget_deficit": "currency-unit"},
        }
    )
    assert null_alias_fallback.score_status is ObjectiveScoreStatus.AVAILABLE
    assert null_alias_fallback.raw_value == 0.0
    conflicted_units = BudgetDeficitObjective(expected_unit="currency-unit").evaluate(
        {
            "gov_balance": -2.0,
            "budget_deficit": 2.0,
            "metric_units": {
                "gov_balance": "currency-unit",
                "budget_deficit": "other-currency",
            },
        }
    )
    assert conflicted_units.score_status is ObjectiveScoreStatus.INVALID


def test_policy_vector_axis_requires_selected_and_source_unit_without_scalar_gate() -> None:
    source = {
        "objective_channels": {"policy_value": 0.0, "employment": 0.5},
        "metric_units": {"channel:primary:policy_value": "ratio"},
        "feasible": True,
        "blocking_reasons": [],
    }
    vector = PolicyEvaluationVector(
        primary={
            "policy_value": ObjectiveChannelValue(
                name="policy_value",
                kind=ObjectiveKind.PRIMARY,
                value=0.0,
                direction=ObjectiveDirection.MAXIMIZE,
                expected_unit="ratio",
            ),
            "employment": ObjectiveChannelValue(
                name="employment",
                kind=ObjectiveKind.PRIMARY,
                value=0.5,
                direction=ObjectiveDirection.MAXIMIZE,
            ),
        }
    ).with_score_source_results(source)
    selected_rule = _policy_vector_channel_rule_spec(vector.primary["policy_value"], "primary")
    [policy_value, employment] = vector.as_legacy_objectives(source)
    assert policy_value.score_status is ObjectiveScoreStatus.AVAILABLE
    assert policy_value.raw_value == 0.0
    assert employment.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert vector.legacy_scalar_proxy_for_search(source) == (
        None,
        ObjectiveScoreStatus.UNAVAILABLE,
    )

    evaluation = Evaluation(
        candidate_id="selected-channel-only",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[policy_value],
        scalar_score=None,
        stage_a_passed=True,
        stage_b_result={
            "simulation_results": source,
            "policy_evaluation": vector.model_dump(mode="json"),
        },
    )
    optimizer = object.__new__(MOBayesianOptimizer)
    optimizer._objective_names = ["policy_value"]
    optimizer._directions = [OptimizationDirection.MAXIMIZE]
    optimizer._objective_rule_specs = {"policy_value": selected_rule}
    optimizer._negate_mask = [1.0]
    assert not evaluation.is_valid
    assert optimizer._has_complete_objective_basis(evaluation)
    assert optimizer._objective_vector(evaluation) == [0.0]

    mutated_source = {**source, "metric_units": {}}
    mutated_evaluation = Evaluation(
        candidate_id="unit-removed",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[policy_value],
        scalar_score=None,
        stage_a_passed=True,
        stage_b_result={
            "simulation_results": mutated_source,
            "policy_evaluation": vector.model_dump(mode="json"),
        },
    )
    assert not optimizer._has_complete_objective_basis(mutated_evaluation)

    mismatched_source = {
        **source,
        "metric_units": {"channel:primary:policy_value": "other-ratio"},
    }
    mismatched_evaluation = Evaluation(
        candidate_id="unit-mismatch",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[policy_value],
        scalar_score=None,
        stage_a_passed=True,
        stage_b_result={
            "simulation_results": mismatched_source,
            "policy_evaluation": vector.model_dump(mode="json"),
        },
    )
    assert not optimizer._has_complete_objective_basis(mismatched_evaluation)

    malformed_source = {
        **source,
        "metric_units": {"channel:primary:policy_value": 1},
    }
    malformed_evaluation = Evaluation(
        candidate_id="malformed-unit",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[policy_value],
        scalar_score=None,
        stage_a_passed=True,
        stage_b_result={
            "simulation_results": malformed_source,
            "policy_evaluation": vector.model_dump(mode="json"),
        },
    )
    assert not optimizer._has_complete_objective_basis(malformed_evaluation)

    unconfigured = vector.model_copy(
        update={
            "primary": {
                "policy_value": vector.primary["policy_value"].model_copy(
                    update={"expected_unit": None}
                ),
                "employment": vector.primary["employment"],
            }
        }
    )
    [unconfigured_policy_value, _] = unconfigured.as_legacy_objectives(source)
    assert unconfigured_policy_value.score_status is ObjectiveScoreStatus.UNAVAILABLE


def test_policy_rank_and_stopping_history_exclude_unavailable_values() -> None:
    unavailable_vector, source = _runtime_vector(values={"policy_value": 0.25})
    assert _policy_rank_key(unavailable_vector, source) is None
    assert _diagnostic_policy_score(unavailable_vector, source) is not None

    valid_vector, valid_source = _runtime_vector(values={"policy_value": 0.25, "employment": 0.1})
    assert _policy_rank_key(valid_vector, valid_source) is not None

    iteration = SearchIteration(
        iteration=1,
        candidate={},
        objective_value=50.0,
        objective_details=[],
        is_promising=True,
        stage_a_passed=True,
        stage_b_result={"simulation_results": {"budget_deficit": 100.0}},
        duration_seconds=0.0,
        score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    assert "objective_value" not in _history_record(iteration)
    lifecycle_history = _SearchLifecycleOwner._to_history_dict(SimpleNamespace(), iteration)
    assert "objective_value" not in lifecycle_history


def test_multi_objective_training_requires_each_configured_coordinate() -> None:
    source = {"gdp_change": 0.0}
    selected = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(
        _with_fixture_units(source)
    )
    evaluation = Evaluation(
        candidate_id="missing-employment-coordinate",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[selected],
        scalar_score=selected.raw_value,
        stage_a_passed=True,
        stage_b_result=source,
        score_status=selected.score_status,
        score_assessment=selected.score_assessment,
    )
    optimizer = object.__new__(MOBayesianOptimizer)
    optimizer._objective_names = ["gdp_growth", "employment"]
    optimizer._directions = [
        GDPGrowthObjective(expected_unit="fixture-unit").direction,
        GDPGrowthObjective(expected_unit="fixture-unit").direction,
    ]
    optimizer._objective_rule_specs = {
        "gdp_growth": configured_objective_rule_spec(
            GDPGrowthObjective(expected_unit="fixture-unit")
        )
        or "",
        "employment": configured_objective_rule_spec(
            GDPGrowthObjective(expected_unit="fixture-unit")
        )
        or "",
    }
    optimizer._negate_mask = [-1.0, 1.0]
    assert evaluation.is_valid
    assert not optimizer._has_complete_objective_basis(evaluation)
    with pytest.raises(ValueError, match="objective basis is missing 'employment'"):
        optimizer._objective_vector(evaluation)


def test_selected_composite_axis_requires_every_configured_operand() -> None:
    objective = CompositeObjective(
        objectives=[
            GDPGrowthObjective(expected_unit="fixture-unit"),
            BudgetDeficitObjective(expected_unit="fixture-unit"),
        ]
    )
    source = {"gdp_change": 0.0}
    selected = objective.evaluate(_with_fixture_units(source))
    assert selected.score_status is ObjectiveScoreStatus.UNAVAILABLE
    assert selected.score_assessment is not None
    assert selected.score_assessment.status is ObjectiveScoreStatus.UNAVAILABLE

    evaluation = Evaluation(
        candidate_id="composite-missing-fiscal-operand",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[selected],
        scalar_score=None,
        stage_a_passed=True,
        stage_b_result=source,
        score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    optimizer = object.__new__(MOBayesianOptimizer)
    optimizer._objective_names = ["composite"]
    optimizer._directions = [objective.direction]
    optimizer._objective_rule_specs = {"composite": configured_objective_rule_spec(objective) or ""}
    optimizer._negate_mask = [1.0]
    optimizer._space = SimpleNamespace(dim=1)
    optimizer._config = SimpleNamespace(max_train_size=4)

    assert not optimizer._has_complete_objective_basis(evaluation)
    assert optimizer._select_training_subset([evaluation]) == []


def test_mo_selected_gdp_basis_does_not_require_an_unrelated_scalar() -> None:
    source = {"gdp_change": 0.0}
    selected = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(
        _with_fixture_units(source)
    )
    evaluation = Evaluation(
        candidate_id="gdp-only-selected-axis",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[selected],
        scalar_score=None,
        stage_a_passed=True,
        stage_b_result=source,
        score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    optimizer = object.__new__(MOBayesianOptimizer)
    optimizer._objective_names = ["gdp_growth"]
    optimizer._directions = [GDPGrowthObjective(expected_unit="fixture-unit").direction]
    optimizer._objective_rule_specs = {
        "gdp_growth": configured_objective_rule_spec(
            GDPGrowthObjective(expected_unit="fixture-unit")
        )
        or ""
    }
    optimizer._negate_mask = [1.0]
    optimizer._space = SimpleNamespace(dim=1)
    optimizer._config = SimpleNamespace(max_train_size=4)

    assert not evaluation.is_valid  # no scalar aggregate is available
    assert optimizer._has_complete_objective_basis(evaluation)
    assert optimizer._select_training_subset([evaluation]) == [evaluation]
    assert optimizer._objective_vector(evaluation) == [0.0]
    optimizer._botorch_ready = False
    unavailable = Evaluation(
        candidate_id="missing-selected-gdp",
        params={"x": 0.75},
        params_normalized=(0.75,),
        objectives=[],
        scalar_score=None,
        stage_a_passed=True,
        stage_b_result={},
        score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    assert optimizer.get_pareto_front([unavailable, evaluation]) == [evaluation]
    assert optimizer.get_pareto_front([unavailable]) == []

    evaluation.stage_b_result = {"gdp_change": 0.0, "budget_deficit": 0.0}
    extra_axis = BudgetDeficitObjective(expected_unit="fixture-unit").evaluate(
        _with_fixture_units({"gdp_change": 0.0, "budget_deficit": 0.0})
    )
    evaluation.objectives.append(extra_axis)
    assert not optimizer._has_complete_objective_basis(evaluation)


def test_selected_vector_survives_transfer_persistence_and_mo_admission(tmp_path) -> None:
    source = {"gdp_change": 0.0, "employment_rate": 0.5}
    objectives = [
        GDPGrowthObjective(expected_unit="fixture-unit").evaluate(_with_fixture_units(source)),
        EmploymentObjective(expected_unit="fixture-unit").evaluate(_with_fixture_units(source)),
    ]
    evaluation = Evaluation(
        candidate_id="selected-vector-source",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=objectives,
        scalar_score=None,
        stage_a_passed=True,
        stage_b_result=source,
        score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    directions = {item.name: item.direction.value for item in objectives}
    rules = {
        item.name: configured_objective_rule_spec(
            GDPGrowthObjective(expected_unit="fixture-unit")
            if item.name == "gdp_growth"
            else EmploymentObjective(expected_unit="fixture-unit")
        )
        or ""
        for item in objectives
    }
    fingerprint = RunFingerprint(
        run_id="source-run",
        space_hash="synthetic-space-v1",
        objective_names=[item.name for item in objectives],
        bounds={"x": [0.0, 1.0]},
        split="selection",
        units={item.name: "fixture-unit" for item in objectives},
        origin="synthetic-fixture",
        tenant_id="fixture",
        objective_directions=directions,
        objective_rule_specs=rules,
    )
    writer = TransferLearningManager(FileSystemCAS(tmp_path / "cas"), object())
    history_ref = writer.register_run(fingerprint, [evaluation])
    assert history_ref is not None
    source_fingerprint = fingerprint.model_copy(update={"history_ref": history_ref})
    target_fingerprint = fingerprint.model_copy(update={"run_id": "target-run"})

    reader = TransferLearningManager(FileSystemCAS(tmp_path / "cas"), object())
    [restored] = reader.get_warm_start_evaluations(
        [source_fingerprint], max_evals=1, target_fingerprint=target_fingerprint
    )
    optimizer = object.__new__(MOBayesianOptimizer)
    optimizer._objective_names = [item.name for item in objectives]
    optimizer._directions = [item.direction for item in objectives]
    optimizer._objective_rule_specs = rules
    optimizer._negate_mask = [1.0, 1.0]
    optimizer._space = SimpleNamespace(dim=1)
    optimizer._config = SimpleNamespace(max_train_size=4)

    assert restored.scalar_score is None
    assert not restored.is_valid
    assert optimizer._has_complete_objective_basis(restored)
    assert optimizer._select_training_subset([restored]) == [restored]
    assert optimizer._objective_vector(restored) == [0.0, 0.5]


def test_transfer_history_rechecks_assessment_and_demotes_legacy_or_stripped_rows() -> None:
    source = {"gdp_change": 0.0}
    evaluation = _evaluation(candidate_id="source-bound", objective_source=source)
    serialized = TransferLearningManager._serialize_evaluation(evaluation)
    assert serialized["history_schema_version"] == "5"
    selected = RunFingerprint(
        run_id="run-01",
        space_hash="space",
        objective_names=["gdp_growth"],
        objective_directions={
            "gdp_growth": GDPGrowthObjective(expected_unit="fixture-unit").direction.value
        },
        objective_rule_specs={
            "gdp_growth": configured_objective_rule_spec(
                GDPGrowthObjective(expected_unit="fixture-unit")
            )
            or ""
        },
    )
    restored = TransferLearningManager._deserialize_evaluation(
        serialized, "run-01", expected_fingerprint=selected
    )
    assert restored.is_valid
    assert restored.score_assessment == evaluation.score_assessment

    legacy = dict(serialized)
    legacy.pop("score_assessment")
    legacy.pop("score_status")
    legacy["objectives"] = [dict(serialized["objectives"][0])]
    legacy["objectives"][0].pop("score_assessment")
    legacy["objectives"][0].pop("score_status")
    migrated = TransferLearningManager._deserialize_evaluation(
        legacy, "old-run", expected_fingerprint=selected
    )
    assert migrated.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert not migrated.is_valid
    assert migrated.scalar_score == 0.0

    stripped_source = dict(serialized)
    stripped_source.pop("stage_b_result")
    demoted = TransferLearningManager._deserialize_evaluation(
        stripped_source, "run-02", expected_fingerprint=selected
    )
    assert demoted.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert not demoted.is_valid
    assert demoted.scalar_score == 0.0


def test_voi_snapshot_roundtrip_binds_nested_source_and_demotes_unbound_rows() -> None:
    source = {
        "simulation_results": {"gdp_change": 0.0, "unselected_metric": 99.0},
        "unrelated_payload": {"raw": "not part of the selected basis"},
    }
    objective = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(
        _with_fixture_units(source)
    )
    scheduler = PredictiveVOIScheduler()
    scheduler.observe_stage_result(
        candidate_id="voi-bound",
        stage_level=1,
        actual_objective_value=objective.raw_value,
        score_assessment=objective.score_assessment,
        objective_source=source,
        actual_promising=True,
        duration_seconds=1.0,
        compute_cost_usd=None,
        compute_cost_origin="unknown",
        disagreement=0.0,
    )
    wire = scheduler.snapshot().model_dump(mode="json")
    assert wire["schema_version"] == "1.3"
    restored = VOIModelSnapshot.model_validate(wire)
    observation = restored.observations[0]
    assert observation.score_status is ObjectiveScoreStatus.AVAILABLE
    expected_source = {
        "simulation_results": {"gdp_change": 0.0},
        "metric_units": {"gdp_change": "fixture-unit"},
    }
    assert observation.objective_source == expected_source
    assert observation.actual_objective_value == 0.0
    assert observation.score_assessment is not None
    assert score_assessment_matches_source(observation.score_assessment, expected_source)

    missing_unit_wire = dict(wire)
    missing_unit_wire["observations"] = [dict(wire["observations"][0])]
    missing_unit_wire["observations"][0]["objective_source"] = {
        "simulation_results": {"gdp_change": 0.0}
    }
    missing_unit = VOIModelSnapshot.model_validate(missing_unit_wire).observations[0]
    assert missing_unit.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert missing_unit.actual_objective_value is None

    wrong_unit_wire = dict(wire)
    wrong_unit_wire["observations"] = [dict(wire["observations"][0])]
    wrong_unit_wire["observations"][0]["objective_source"] = {
        **expected_source,
        "metric_units": {"gdp_change": "different-unit"},
    }
    wrong_unit = VOIModelSnapshot.model_validate(wrong_unit_wire).observations[0]
    assert wrong_unit.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert wrong_unit.actual_objective_value is None

    legacy_wire = dict(wire)
    legacy_wire["observations"] = [dict(wire["observations"][0])]
    legacy_wire["observations"][0].pop("objective_source")
    legacy = VOIModelSnapshot.model_validate(legacy_wire).observations[0]
    assert legacy.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert legacy.actual_objective_value is None
    assert legacy.disagreement is None
    assert legacy.metadata["legacy_unbound_actual_objective_value"] == 0.0

    untyped = dict(wire["observations"][0])
    untyped.pop("score_assessment")
    untyped.pop("objective_source")
    untyped["actual_objective_value"] = 99.0
    untyped["disagreement"] = 0.0
    demoted = VOIObservation.model_validate(untyped)
    assert demoted.score_status is ObjectiveScoreStatus.NOT_ESTABLISHED
    assert demoted.actual_objective_value is None
    assert demoted.disagreement is None


def test_voi_snapshot_preserves_malformed_selected_unit_status() -> None:
    source = {"gdp_change": 0.0, "metric_units": {"gdp_change": 7}}
    objective = GDPGrowthObjective(expected_unit="fixture-unit").evaluate(source)
    assert objective.score_assessment is not None
    assert objective.score_assessment.status is ObjectiveScoreStatus.INVALID
    scheduler = PredictiveVOIScheduler()
    scheduler.observe_stage_result(
        candidate_id="voi-malformed-unit",
        stage_level=1,
        actual_objective_value=None,
        score_assessment=objective.score_assessment,
        objective_source=source,
        actual_promising=False,
        duration_seconds=1.0,
        compute_cost_usd=None,
        compute_cost_origin="unknown",
    )

    restored = VOIModelSnapshot.model_validate(
        scheduler.snapshot().model_dump(mode="json")
    ).observations[0]
    assert restored.score_status is ObjectiveScoreStatus.INVALID
    assert restored.actual_objective_value is None
    assert restored.objective_source == source
    assert restored.score_assessment is not None
    assert score_assessment_matches_source(restored.score_assessment, source)


def test_voi_snapshot_projects_only_selected_policy_vector_channel() -> None:
    vector, simulation_source = _runtime_vector(
        values={"policy_value": 0.0, "unselected_metric": 4.0}
    )
    selected = next(
        item
        for item in vector.as_legacy_objectives(simulation_source)
        if item.name == "policy_value"
    )
    assert selected.score_assessment is not None
    objective_source = {
        "policy_evaluation": vector.model_dump(mode="python"),
        "simulation_results": simulation_source,
        "unrelated_payload": {"raw": "not part of the selected basis"},
    }
    scheduler = PredictiveVOIScheduler()
    scheduler.observe_stage_result(
        candidate_id="voi-vector-bound",
        stage_level=1,
        actual_objective_value=selected.raw_value,
        score_assessment=selected.score_assessment,
        objective_source=objective_source,
        actual_promising=True,
        duration_seconds=1.0,
        compute_cost_usd=None,
        compute_cost_origin="unknown",
    )

    observation = VOIModelSnapshot.model_validate(
        scheduler.snapshot().model_dump(mode="json")
    ).observations[0]
    assert observation.score_status is ObjectiveScoreStatus.AVAILABLE
    assert observation.objective_source is not None
    assert "unrelated_payload" not in observation.objective_source
    projected_vector = observation.objective_source["policy_evaluation"]
    assert list(projected_vector) == ["primary"]
    assert list(projected_vector["primary"]) == ["policy_value"]
    projected_source = observation.objective_source["simulation_results"]
    assert projected_source["objective_channels"] == {"policy_value": 0.0}
    assert score_assessment_matches_source(
        observation.score_assessment, observation.objective_source
    )


def test_bayesian_scalar_admission_uses_selected_run_rule_and_normalizes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def optional_stack_unavailable() -> None:
        raise OptionalDependencyUnavailableError("constructor binding test")

    monkeypatch.setattr(
        "polisyos.scientist.methods.search.strategies.bayesian.require_botorch",
        optional_stack_unavailable,
    )
    source = {"metrics": {"budget_deficit": 17.0, "gdp_change": 100.0}}
    for source_direction, expected_score in (("maximize", -17.0), ("minimize", 17.0)):
        binding = _configured_search_metric_binding(
            "budget_deficit", source_direction, "fixture-unit"
        )
        assert binding is not None
        name, direction, rule_spec = binding
        assert direction is OptimizationDirection.MINIMIZE
        assessment = _assess_search_metric(
            _with_fixture_units(source), name, source_direction, "fixture-unit"
        )
        assert assessment.status is ObjectiveScoreStatus.AVAILABLE
        assert assessment.value == expected_score
        selected = ObjectiveValue(
            name=name,
            raw_value=expected_score,
            direction=direction,
            score_status=assessment.status,
            score_assessment=assessment,
        )
        evaluation = Evaluation(
            candidate_id=f"configured-{source_direction}",
            params={"x": 0.25},
            params_normalized=(0.25,),
            objectives=[selected],
            scalar_score=expected_score,
            stage_a_passed=True,
            stage_b_result=source,
            score_status=assessment.status,
            score_assessment=assessment,
        )
        optimizer = BayesianOptimizer(
            SearchSpace(bounds=[ParameterBounds(name="x", lower=0.0, upper=1.0)]),
            objective_name=name,
            objective_source_direction=source_direction,
            objective_source_unit="fixture-unit",
        )
        assert optimizer._selected_objective_name == name
        assert optimizer._selected_objective_direction is direction
        assert optimizer._selected_objective_rule_spec == rule_spec
        assert optimizer._score_is_admissible(evaluation)

        # The same public label and a self-consistent GDP assessment cannot be
        # admitted to the configured fiscal coordinate.
        wrong_assessment = _assess_search_metric(
            _with_fixture_units(source), "gdp_change", "maximize", "fixture-unit"
        )
        wrong_label = ObjectiveValue(
            name=name,
            raw_value=float(wrong_assessment.value),
            direction=direction,
            score_status=wrong_assessment.status,
            score_assessment=wrong_assessment,
        )
        wrong = Evaluation(
            candidate_id=f"wrong-rule-{source_direction}",
            params={"x": 0.5},
            params_normalized=(0.5,),
            objectives=[wrong_label],
            scalar_score=float(wrong_assessment.value),
            stage_a_passed=True,
            stage_b_result=source,
            score_status=wrong_assessment.status,
            score_assessment=wrong_assessment,
        )
        assert wrong.is_valid
        assert not optimizer._score_is_admissible(wrong)

        # Replaying the unchanged declaration against a changed source must fail.
        evaluation.stage_b_result = {"metrics": {"budget_deficit": 18.0, "gdp_change": 100.0}}
        assert not optimizer._score_is_admissible(evaluation)

    # Direct BO remains a generic candidate-only numeric optimizer; it does not
    # manufacture a configured warm-start or policy-objective binding.
    candidate_only = object.__new__(BayesianOptimizer)
    candidate_only._selected_objective_name = None
    candidate_only._selected_objective_direction = None
    candidate_only._selected_objective_rule_spec = None
    assert candidate_only._score_is_admissible(wrong)
    unbound_numeric = Evaluation(
        candidate_id="generic-external-score",
        params={"x": 0.75},
        params_normalized=(0.75,),
        objectives=[],
        scalar_score=3.5,
        stage_a_passed=True,
        score_status=ObjectiveScoreStatus.NOT_ESTABLISHED,
    )
    assert candidate_only._score_is_admissible(unbound_numeric)
    assert candidate_only._objective_binding_payload() is None


def test_configured_bayesian_binding_keeps_custom_metric_labels_and_rejects_rule_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def optional_stack_unavailable() -> None:
        raise OptionalDependencyUnavailableError("constructor binding test")

    monkeypatch.setattr(
        "polisyos.scientist.methods.search.strategies.bayesian.require_botorch",
        optional_stack_unavailable,
    )
    custom_metric = "local_welfare_index"
    binding = _configured_search_metric_binding(custom_metric, "maximize")
    assert binding is not None
    name, direction, rule_spec = binding
    assert name == custom_metric
    assert direction is OptimizationDirection.MINIMIZE

    source = {"metrics": {custom_metric: 42.0, "budget_deficit": 17.0}}
    assessment = _assess_search_metric(
        _with_fixture_units(source), custom_metric, "maximize", "fixture-unit"
    )
    assert assessment.status is ObjectiveScoreStatus.AVAILABLE
    assert assessment.value == -42.0
    selected = ObjectiveValue(
        name=name,
        raw_value=-42.0,
        direction=direction,
        score_status=assessment.status,
        score_assessment=assessment,
    )
    evaluation = Evaluation(
        candidate_id="custom-selected-rule",
        params={"x": 0.25},
        params_normalized=(0.25,),
        objectives=[selected],
        scalar_score=-42.0,
        stage_a_passed=True,
        stage_b_result=source,
        score_status=assessment.status,
        score_assessment=assessment,
    )
    optimizer = BayesianOptimizer(
        SearchSpace(bounds=[ParameterBounds(name="x", lower=0.0, upper=1.0)]),
        objective_name=custom_metric,
        objective_source_direction="maximize",
    )
    assert optimizer._selected_objective_rule_spec == rule_spec
    assert optimizer._score_is_admissible(evaluation)

    with pytest.raises(TypeError):
        BayesianOptimizer(
            SearchSpace(bounds=[ParameterBounds(name="x", lower=0.0, upper=1.0)]),
            objective_name=custom_metric,
            objective_source_direction="maximize",
            objective_rule_spec=configured_objective_rule_spec(
                GDPGrowthObjective(expected_unit="fixture-unit")
            ),
        )


def test_search_objective_profile_fingerprint_binds_configured_unit() -> None:
    usd = _configured_search_metric_profile_fingerprint(
        "budget_deficit", "maximize", "USD per resident"
    )
    eur = _configured_search_metric_profile_fingerprint(
        "budget_deficit", "maximize", "EUR per resident"
    )
    direction = _configured_search_metric_profile_fingerprint(
        "budget_deficit", "minimize", "USD per resident"
    )
    unknown_unit = _configured_search_metric_profile_fingerprint("budget_deficit", "maximize", None)
    assert all(
        isinstance(value, str) and len(value) == 64 for value in (usd, eur, direction, unknown_unit)
    )
    assert len({usd, eur, direction, unknown_unit}) == 4
    assert (
        _configured_search_metric_profile_fingerprint(
            "budget_deficit",
            "maximize",
            12,  # type: ignore[arg-type]
        )
        is None
    )
