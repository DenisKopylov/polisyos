"""Fixed projection semantics and actual typed numerical-output controls."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core import artifacts
from polisyos.runtime.quality import joint_simulation_horizon as horizon
from polisyos.runtime.quality import n5_replay_numerical_projection as projection
from polisyos.runtime.quality.n5_replay_appointment import N5ReplayComparatorProfile


def _comparator() -> N5ReplayComparatorProfile:
    return N5ReplayComparatorProfile(
        numerical_projection_schema=projection.N5_NUMERICAL_RESULT_PROJECTION_SCHEMA,
        excluded_time_identity_paths=projection.N5_REPLAY_EXCLUDED_TIME_IDENTITY_PATHS,
    )


@pytest.fixture(scope="module")
def actual_ncm_result() -> horizon.JointSimulationResult:
    """Run the real NCM producer, without content capture or protected admission."""
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

    request = _request().model_copy(
        update={"horizon": horizon.HorizonSpec(start=0, end=0), "replications": 2}
    )
    return horizon.JointSimulationHorizonController().run(request)


def _project_fields(
    result: horizon.JointSimulationResult,
) -> projection.N5NumericalResultProjectionV1:
    """Exercise the pure typed-output adapter, not the public source-admission API."""
    return projection.N5NumericalResultProjectionV1(
        numerical_output=projection._project_result_fields(result),
        completed_physical_units=len(result.physical_work_observations),
    )


def test_census_is_complete_disjoint_over_actual_canonical_model_fields() -> None:
    for name, roles in projection.N5_TYPED_FIELD_ROLES.items():
        assert set(roles) == set(getattr(horizon, name).model_fields), name
        assert set(roles.values()) <= {"numerical", "evidence", "invariant"}


def test_real_typed_result_persists_reopens_and_compares_exactly(
    actual_ncm_result: horizon.JointSimulationResult, tmp_path: Path
) -> None:
    # The real producer computes 1 + 2x + 3y + 5xy: individual effects 2/3,
    # joint effect 10 and interaction 5. No expected number comes from the adapter.
    joint = actual_ncm_result.trajectory_for("joint", ("income_subsidy", "balance_grant"))
    assert joint.points[0].outcomes["firm_survival"] == 11.0
    assert joint.points[0].effect["firm_survival"] == 10.0
    assert actual_ncm_result.interaction_terms[0].by_step[0] == 5.0
    original = _project_fields(actual_ncm_result)
    store = artifacts.FileSystemCAS(tmp_path / "projection-cas")
    selected = store.put_bytes(
        original.model_dump_json().encode(),
        artifacts.ArtifactWriteOptions(
            kind="runtime.quality.n5_numerical_result_projection", media_type="application/json"
        ),
        return_selected_profile=True,
    )
    reopened_store = artifacts.FileSystemCAS(tmp_path / "projection-cas")
    assert reopened_store.verify(selected).ok
    reopened = projection.N5NumericalResultProjectionV1.model_validate_json(
        reopened_store.get_bytes(selected)
    )
    comparison = projection.compare_n5_numerical_projection_bytes(
        original.numerical_bytes(), reopened.numerical_bytes(), comparator=_comparator()
    )
    assert comparison.status == "equal"
    assert comparison.protected_use_allowed is False
    assert reopened.independent_verification == "not_established"
    sampling = reopened.numerical_output["trajectories"][0]["points"][0]["replication_sampling"]
    assert len(sampling["samples"]) == 2
    assert sampling["outcomes_standard_error"] == {"firm_survival": 0.0}


def test_raw_draw_order_change_cannot_hide_behind_same_mean_or_standard_error() -> None:
    # Reversing the seed-associated draws preserves the distribution, mean and
    # standard error, but is a different same-seed implementation replay.
    samples = [
        horizon.ReplicationSample(
            seed=seed,
            engine_state={"intervention": {}},
            outcomes={"y": value},
            effects={"y": value},
        )
        for seed, value in [(7, 1.0), (8, 3.0)]
    ]
    first = horizon.ReplicationSamplingSummary(
        status="estimated",
        replicate_count=2,
        seeds=(7, 8),
        samples=tuple(samples),
        outcomes_standard_error={"y": 1.0},
        effects_standard_error={"y": 1.0},
    )
    changed_samples = tuple(
        sample.model_copy(update={"outcomes": {"y": value}, "effects": {"y": value}})
        for sample, value in zip(samples, (3.0, 1.0), strict=True)
    )
    second = first.model_copy(update={"samples": changed_samples})
    assert horizon.ReplicationSamplingSummary.model_validate(second.model_dump()) == second
    assert first.outcomes_standard_error == second.outcomes_standard_error
    assert projection._typed(first, "ncm_parallel_worlds") != projection._typed(
        second, "ncm_parallel_worlds"
    )


def test_real_conditional_comparator_retains_baseline_draws_and_numeric_contract() -> None:
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

    base = _request()
    plan = base.engine_plan[0]
    assert plan.ncm_spec is not None
    equations = [
        equation.model_copy(
            update={
                "equation_params": {
                    "noise_expression": "u + (2.0 * income_delta) + (3.0 * balance_delta) "
                    "+ (5.0 * income_delta * balance_delta)"
                }
            }
        )
        if equation.variable == "firm_survival"
        else equation
        for equation in plan.ncm_spec.structural_equations
    ]
    request = base.model_copy(
        update={
            "horizon": horizon.HorizonSpec(start=0, end=0),
            "replications": 2,
            "engine_plan": (
                plan.model_copy(
                    update={
                        "ncm_spec": plan.ncm_spec.model_copy(
                            update={"structural_equations": equations}
                        )
                    }
                ),
            ),
            "evidence_state": base.baseline_state,
            "comparator_profile": horizon.NCMConditionalComparatorProfile(
                outcome_units={"firm_survival": "synthetic_outcome_unit"}
            ),
        }
    )
    result = horizon.JointSimulationHorizonController().run(request)
    output = _project_fields(result).numerical_output
    observed = output["diagnostics"]["ncm_conditional_comparator"]
    assert observed["samples"] == [
        {"seed": request.seed, "outcomes": {"firm_survival": 1.0}},
        {"seed": request.seed + 1, "outcomes": {"firm_survival": 1.0}},
    ]
    assert "physical_work_event_id" not in observed["samples"][0]
    tolerance = output["diagnostics"]["interaction_numerical_tolerance"]
    assert tolerance["status"] == "qualified"
    assert tolerance["contract"]["scopes"]
    assert tolerance["contract"]["residuals"]
    repeated = horizon.JointSimulationHorizonController().run(request)
    assert projection.project_n5_diagnostic_freshness_bytes(result) == (
        projection.project_n5_diagnostic_freshness_bytes(repeated)
    )


def test_unqualified_same_draw_comparator_preserves_declared_unit_difference() -> None:
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

    base = _request()  # Its intercept-one SCM intentionally has no qualified tolerance.
    outputs = []
    for unit in ("USD", "EUR"):
        request = base.model_copy(
            update={
                "horizon": horizon.HorizonSpec(start=0, end=0),
                "replications": 2,
                "evidence_state": base.baseline_state,
                "comparator_profile": horizon.NCMConditionalComparatorProfile(
                    outcome_units={"firm_survival": unit}
                ),
            }
        )
        result = horizon.JointSimulationHorizonController().run(request)
        outputs.append(_project_fields(result))
    original, replay = outputs
    before = original.numerical_output["diagnostics"]["ncm_conditional_comparator"]
    after = replay.numerical_output["diagnostics"]["ncm_conditional_comparator"]
    assert before["samples"] == after["samples"]
    for observed, unit in ((before, "USD"), (after, "EUR")):
        assert observed["request"]["outcome_units"] == {"firm_survival": unit}
        assert observed["request"]["outcome_units_status"] == (
            "declared_candidate_not_independently_grounded"
        )
    assert original.numerical_output["diagnostics"]["interaction_numerical_tolerance"] == {
        "status": "not_established"
    }
    assert (
        projection.compare_n5_numerical_projection_bytes(
            original.numerical_bytes(), replay.numerical_bytes(), comparator=_comparator()
        ).status
        == "mismatch"
    )
    unexpected = deepcopy(result.diagnostics)
    unexpected["ncm_conditional_comparator"]["request"]["new_numeric_basis"] = 4.0
    with pytest.raises(ValueError, match="field_role_not_established"):
        projection._root_diagnostics(unexpected)


def test_single_draw_preserves_unestimated_error_and_refuses_extra_instance_fields() -> None:
    summary = horizon.ReplicationSamplingSummary(
        status="standard_error_not_estimated",
        replicate_count=1,
        seeds=(7,),
        samples=(
            horizon.ReplicationSample(
                seed=7, engine_state={"intervention": {}}, outcomes={"y": 1.0}, effects={"y": 0.0}
            ),
        ),
        outcomes_standard_error={"y": None},
        effects_standard_error={"y": None},
    )
    observed = projection._typed(summary, "ncm_parallel_worlds")
    assert observed["status"] == "standard_error_not_estimated"
    assert observed["effects_standard_error"] == {"y": None}
    object.__setattr__(summary.samples[0], "undeclared_number", 8.0)
    with pytest.raises(ValueError, match="denominator_not_established"):
        projection._typed(summary, "ncm_parallel_worlds")


@pytest.mark.parametrize("path", ["standard_error", "interaction", "residual", "time_role"])
def test_mean_unchanged_cannot_hide_numerical_or_semantic_change(
    actual_ncm_result: horizon.JointSimulationResult, path: str
) -> None:
    original = _project_fields(actual_ncm_result)
    changed = deepcopy(original.numerical_output)
    if path == "standard_error":
        changed["trajectories"][0]["points"][0]["replication_sampling"]["effects_standard_error"][
            "firm_survival"
        ] = 0.125
    elif path == "interaction":
        changed["interaction_terms"][0]["replication_sampling_by_step"]["0"]["samples"][0][
            "effects"
        ]["derived_effect"] += 1.0
    elif path == "residual":
        changed["higher_order_residuals"] = {"firm_survival": {"0": 0.5}}
    else:
        changed["horizon"]["valid_time_role"] = "different_model_coordinate"
    replay = original.model_copy(update={"numerical_output": changed})
    comparison = projection.compare_n5_numerical_projection_bytes(
        original.numerical_bytes(), replay.numerical_bytes(), comparator=_comparator()
    )
    assert comparison.status == "mismatch"
    assert comparison.mismatch_policy == "final_no_retry"


def test_known_work_identity_is_excluded_but_unknown_output_is_refused(
    actual_ncm_result: horizon.JointSimulationResult,
) -> None:
    original = _project_fields(actual_ncm_result)
    changed = actual_ncm_result.model_copy(deep=True)
    changed.diagnostics["physical_work_observations"][0]["duration_seconds"] += 1.0
    # This lower-level field adapter grants no source/receipt admission. The
    # public owner separately rejects this now-invalid evidence before projection.
    assert _project_fields(changed).numerical_bytes() == original.numerical_bytes()
    changed.diagnostics["new_numerical_diagnostic"] = 4.0
    with pytest.raises(ValueError, match="field_role_not_established"):
        _project_fields(changed)


def test_unknown_nested_state_and_typed_subclass_refuse(
    actual_ncm_result: horizon.JointSimulationResult,
) -> None:
    changed = actual_ncm_result.model_copy(deep=True)
    changed.trajectories[0].points[0].replication_sampling.samples[0].engine_state[
        "new_numeric"
    ] = 8.0
    with pytest.raises(ValueError, match="field_role_not_established"):
        _project_fields(changed)

    class ExtendedPoint(horizon.TrajectoryPoint):
        extra_number: float = 1.0

    extended = ExtendedPoint(step=0, outcomes={"y": 1.0}, effect={"y": 0.0})
    with pytest.raises(ValueError, match="field_role_not_established"):
        projection._typed(extended, "ncm_parallel_worlds")


@pytest.mark.parametrize("change", ["schema", "extra", "missing", "duplicate", "reordered"])
def test_exclusion_manifest_and_projection_schema_cannot_be_weakened(change: str) -> None:
    profile = _comparator()
    paths = profile.excluded_time_identity_paths
    updates = {
        "schema": {"numerical_projection_schema": "legacy.or.unrecognized.v1"},
        "extra": {"excluded_time_identity_paths": (*paths, "trajectories")},
        "missing": {"excluded_time_identity_paths": paths[:-1]},
        "duplicate": {"excluded_time_identity_paths": (*paths, paths[0])},
        "reordered": {"excluded_time_identity_paths": tuple(reversed(paths))},
    }
    with pytest.raises(ValueError, match="comparator_not_established"):
        projection.require_supported_n5_replay_comparator(
            profile.model_copy(update=updates[change])
        )


def test_legacy_profile_remains_wire_readable_but_not_executable() -> None:
    legacy = N5ReplayComparatorProfile(
        numerical_projection_schema="test.n5.numeric_projection.v1",
        excluded_time_identity_paths=("recorded_at",),
    )
    assert N5ReplayComparatorProfile.model_validate_json(legacy.model_dump_json()) == legacy
    with pytest.raises(ValueError, match="comparator_not_established"):
        projection.require_supported_n5_replay_comparator(legacy)


def test_partial_and_non_numerical_effects_do_not_become_projection(
    actual_ncm_result: horizon.JointSimulationResult,
) -> None:
    changed = actual_ncm_result.model_copy(deep=True)
    changed.diagnostics["physical_work_interruption"] = "n5_physical_work_failed"
    with pytest.raises(ValueError, match="field_role_not_established"):
        _project_fields(changed)
    changed = actual_ncm_result.model_copy(deep=True)
    changed.world_credal_state_after["firm_survival"]["low"] = 0.3
    with pytest.raises(ValueError, match="non_numerical_effect_not_established"):
        _project_fields(changed)


def test_semantic_program_state_strips_locators_recursively_preserves_aggregation() -> None:
    state = {
        "simulation_result_ref": {"artifact_id": "run-one"},
        "semantic_input_notes": ["source-note"],
        "outcome_aggregation_basis": {
            "population_mean": {
                "method": "mean",
                "unit": "USD",
                "element_count": 4,
                "effective_weight_sum": 4.0,
            }
        },
        "replication_count": 1,
        "replication_seeds": [7],
        "replication_engine_states": [{"simulation_result_ref": {"artifact_id": "run-two"}}],
    }
    output = projection._state(state, "program_graph")
    assert output["outcome_aggregation_basis"]["population_mean"]["effective_weight_sum"] == 4.0
    assert "simulation_result_ref" not in output
    assert output["replication_engine_states"] == [{}]
    paired = projection._state(
        {"source_scope_engine_states": {"joint": state}}, "program_graph", derived=True
    )
    assert paired["source_scope_engine_states"]["joint"] == output
    with pytest.raises(ValueError, match="field_role_not_established"):
        projection._state({"source_scope_engine_states": {"joint": state}}, "program_graph")


def test_strict_projection_contract_and_binary64_signed_zero(
    actual_ncm_result: horizon.JointSimulationResult,
) -> None:
    with pytest.raises(ValidationError):
        projection.N5NumericalResultProjectionV1(
            numerical_output={}, completed_physical_units=1, protected_use_allowed=True
        )
    left = _project_fields(actual_ncm_result)
    right = left.model_copy(deep=True)
    left.numerical_output["marginal_effects"] = {"x": {"0": {"y": 0.0}}}
    right.numerical_output["marginal_effects"] = {"x": {"0": {"y": -0.0}}}
    assert left.numerical_bytes() != right.numerical_bytes()


@pytest.mark.integration
def test_public_projection_requires_actual_content_completion_and_persists(
    tmp_path: Path,
) -> None:
    """Exercise real candidate capture; run only against a frozen native profile."""
    from polisyos.runtime.quality import n5_candidate_content as content
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

    store = artifacts.FileSystemCAS(tmp_path / "public-cas")
    request = _request().model_copy(update={"horizon": horizon.HorizonSpec(start=0, end=0)})
    input_ref = store.put_json(
        json.loads(request.model_dump_json()),
        artifacts.ArtifactWriteOptions(kind="test.n5.source_input", media_type="application/json"),
        return_selected_profile=True,
    )
    controller = horizon.JointSimulationHorizonController()
    scope = content.CandidateN5ContentRun(
        controller=controller, request=request, input_ref=input_ref
    )
    token = content._ACTIVE.set(scope)
    try:
        raw = controller.run(request)
    finally:
        content._ACTIVE.reset(token)
    actual = content.bind_candidate_n5_content_observation(raw, scope=scope)
    observed = projection.project_n5_numerical_result_v1(
        actual,
        input_ref=input_ref,
        expected_request=request,
        prepared_configuration=controller._prepared_configuration,
        store=store,
    )
    assert observed.completed_physical_units == 3
    assert observed.protected_use_allowed is False
    persisted = store.put_bytes(
        observed.model_dump_json().encode(),
        artifacts.ArtifactWriteOptions(kind="test.n5.projection"),
        return_selected_profile=True,
    )
    fresh_store = artifacts.FileSystemCAS(tmp_path / "public-cas")
    fresh = projection.N5NumericalResultProjectionV1.model_validate_json(
        fresh_store.get_bytes(persisted)
    )
    assert (
        projection.compare_n5_numerical_projection_bytes(
            observed.numerical_bytes(), fresh.numerical_bytes(), comparator=_comparator()
        ).status
        == "equal"
    )
    with pytest.raises(ValueError, match="content_observation_missing"):
        projection.project_n5_numerical_result_v1(
            raw,
            input_ref=input_ref,
            expected_request=request,
            prepared_configuration=controller._prepared_configuration,
            store=fresh_store,
        )


def test_diagnostic_freshness_validates_joins_and_ignores_only_work_occurrence(
    actual_ncm_result: horizon.JointSimulationResult,
) -> None:
    """Two genuine executions compare numerically, while changed evidence still matters."""
    from tests.unit.runtime.quality.test_joint_simulation_horizon import _request

    request = _request().model_copy(
        update={"horizon": horizon.HorizonSpec(start=0, end=0), "replications": 2}
    )
    other = horizon.JointSimulationHorizonController().run(request)
    first_ids = {work.event_id for work in actual_ncm_result.physical_work_observations}
    assert first_ids.isdisjoint(work.event_id for work in other.physical_work_observations)
    first = projection.project_n5_diagnostic_freshness_bytes(actual_ncm_result)
    assert first == projection.project_n5_diagnostic_freshness_bytes(other)

    def rehashed(wire: dict) -> horizon.JointSimulationResult:
        payload = {key: value for key, value in wire.items() if key != "receipt"}
        wire["receipt"] = horizon.build_content_bound_simulation_receipt(
            engine_kind=wire["receipt"]["engine_kind"],
            payload=payload,
            diagnostics=wire["diagnostics"],
        ).model_dump(mode="json")
        return horizon.JointSimulationResult.model_validate(wire)

    status = actual_ncm_result.model_dump(mode="json")
    status["diagnostics"]["invocation_quota_capacity"] = "protected_profile_configured"
    assert first != projection.project_n5_diagnostic_freshness_bytes(rehashed(status))

    broken_join = actual_ncm_result.model_dump(mode="json")
    broken_join["trajectories"][0]["diagnostics"]["physical_work_event_ids"][0] = "a" * 32
    with pytest.raises(ValueError, match="n5_physical_work_trajectory_binding_mismatch"):
        rehashed(broken_join)

    changed_draw = actual_ncm_result.model_dump(mode="json")
    changed_draw["trajectories"][0]["points"][0]["replication_sampling"]["samples"][0]["outcomes"][
        "firm_survival"
    ] += 1
    with pytest.raises(ValueError):
        rehashed(changed_draw)

    changed_seed = actual_ncm_result.model_dump(mode="json")
    changed_seed["trajectories"][0]["points"][0]["replication_sampling"]["samples"][0]["seed"] += 1
    with pytest.raises(ValueError):
        rehashed(changed_seed)

    changed_state = actual_ncm_result.model_dump(mode="json")
    changed_state["trajectories"][0]["points"][0]["replication_sampling"]["samples"][0][
        "engine_state"
    ]["intervention"]["income_delta"] = 123.0
    with pytest.raises(ValueError):
        rehashed(changed_state)

    changed_interaction = actual_ncm_result.model_dump(mode="json")
    changed_interaction["interaction_terms"][0]["by_step"]["0"] += 1.0
    with pytest.raises(ValueError):
        rehashed(changed_interaction)

    unknown = actual_ncm_result.model_dump(mode="json")
    unknown["diagnostics"]["unexpected_scope"] = "not-classified"
    with pytest.raises(ValueError, match="n5_diagnostic_root_role_not_established"):
        projection.project_n5_diagnostic_freshness_bytes(rehashed(unknown))


@pytest.mark.parametrize("engine", ["system_dynamics", "coupled_des_abm", "program_graph"])
def test_diagnostic_freshness_real_engine_variants(engine: str, tmp_path: Path) -> None:
    """Compare two real invocations with the existing selected engine plans."""
    from tests.unit.runtime.quality.test_joint_simulation_horizon import (
        _coupling_graph,
        _program_graph_plan,
        _request,
        _shared_resource_stock_flow_fallback_request,
    )

    if engine == "system_dynamics":
        request = _shared_resource_stock_flow_fallback_request(
            candidate_order=("system_dynamics", "method_registry_estimator")
        )
    elif engine == "coupled_des_abm":
        request = _request(policy_domain="unemployment_claims_benefit").model_copy(
            update={
                "coupling_graph": _coupling_graph("shared_resource"),
                "selected_outcomes": ("final_queue_length",),
                "baseline_state": {"final_queue_length": 0.0},
                "engine_plan": (
                    horizon.EnginePlan(
                        engine_kind="coupled_des_abm",
                        objective_ref="objective://claims-queue",
                        eligibility_conditions=(
                            "unemployment_claims",
                            "benefit_queue",
                            "service_queue",
                        ),
                        variable_map={
                            "agents.income": "benefit_amount",
                            "government.balance": "service_rate",
                        },
                        coupled_state={
                            "initial_income": [1000.0, 600.0, 400.0],
                            "initial_savings": [0.0, 0.0, 0.0],
                            "is_employed": [0.0, 0.0, 0.0],
                        },
                        coupled_params={
                            "benefit_amount": 0.0,
                            "service_rate": 0.5,
                            "initial_queue_length": 0.0,
                            "seed": 7,
                        },
                    ),
                ),
            }
        )
    else:
        request = _request().model_copy(
            update={
                "engine_plan": (_program_graph_plan(tmp_path),),
                "selected_outcomes": ("mean_income",),
                "baseline_state": {"mean_income": 0.0},
            }
        )
    controller = horizon.JointSimulationHorizonController()
    first, second = controller.run(request), controller.run(request)
    assert first.engine_decisions[0].engine_kind == engine
    assert first.engine_decisions[0].decision == "selected"
    assert {work.event_id for work in first.physical_work_observations}.isdisjoint(
        work.event_id for work in second.physical_work_observations
    )
    store = request.engine_plan[0].program_store if engine == "program_graph" else None
    if engine == "program_graph":
        with pytest.raises(
            ValueError, match="n5_diagnostic_program_graph_metrics_owner_not_established"
        ):
            projection.project_n5_diagnostic_freshness_bytes(first)
        with pytest.raises(ValueError, match="n5_diagnostic_metrics_ref_not_established"):
            projection.project_n5_diagnostic_freshness_bytes(first, store=store)
        return
    left = projection.project_n5_diagnostic_freshness_bytes(first, store=store)
    right = projection.project_n5_diagnostic_freshness_bytes(second, store=store)
    assert left == right


def test_diagnostic_selected_program_graph_actual_producer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selected method-metric plan emits actual profile-bound PG evidence."""
    from polisyos.foundry.methods.registry import MethodRegistry
    from tests.unit.foundry.runtime.test_method_metric_capture import (
        _make_graph_and_plan,
        _ReturnsMetricScalar,
        _test_environment_manifest,
    )
    from tests.unit.runtime.quality.test_joint_simulation_horizon import (
        _program_graph_plan,
        _request,
    )

    store = artifacts.FileSystemCAS(tmp_path / "selected-program-cas")
    base = _program_graph_plan(tmp_path, store=store)
    graph_ref, plan_ref = _make_graph_and_plan(store)
    registry = MethodRegistry.get_instance()
    registry.register(_ReturnsMetricScalar, override=True)
    monkeypatch.setattr(
        "polisyos.foundry.execute._internal.graph.capture_environment",
        lambda **_kwargs: _test_environment_manifest(),
    )
    plan = base.model_copy(
        update={
            "program_graph_ref": graph_ref,
            "exec_plan_ref": plan_ref,
            "program_parameter_overrides_by_atom": {},
        }
    )
    request = _request().model_copy(
        update={
            "engine_plan": (plan,),
            "horizon": horizon.HorizonSpec(start=0, end=0),
            "selected_outcomes": ("mean_income",),
            "baseline_state": {"mean_income": 0.0},
        }
    )
    first = horizon.JointSimulationHorizonController().run(request)
    second = horizon.JointSimulationHorizonController().run(request)
    assert first.engine_decisions[0].decision == "selected"
    assert first.trajectories and second.trajectories
    assert all(
        point.engine_state["metrics_artifact_ref"]["manifest_profile_sha256"]
        for trajectory in first.trajectories
        for point in trajectory.points
    )
    for result in (first, second):
        with pytest.raises(
            ValueError, match="n5_diagnostic_method_execution_owner_not_established"
        ):
            projection.project_n5_diagnostic_freshness_bytes(result, store=store)

    malformed = first.model_dump(mode="json")
    malformed["trajectories"][0]["diagnostics"]["method_execution_sources"][0]["step"] += 1
    payload = {key: value for key, value in malformed.items() if key != "receipt"}
    malformed["receipt"] = horizon.build_content_bound_simulation_receipt(
        engine_kind=malformed["receipt"]["engine_kind"],
        payload=payload,
        diagnostics=malformed["diagnostics"],
    ).model_dump(mode="json")
    changed = horizon.JointSimulationResult.model_validate(malformed)
    with pytest.raises(ValueError, match="n5_diagnostic_metrics_source_join_not_established"):
        projection.project_n5_diagnostic_freshness_bytes(changed, store=store)
