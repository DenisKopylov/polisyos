"""Exercise the actual ordered fit, numeric domain, scalar rows and exact keys."""

from dataclasses import replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, ProgramGraphRef, ProgramNode
from polisyos.foundry.calibration.calibrator import (
    Calibrator,
    CalibratorInputs,
    OrderedBatchCalibrationProfile,
    _hessian_reuse_key_matches,
    _make_hessian_reuse_key,
    evaluate_ordered_batch_objective,
)
from polisyos.foundry.calibration.pure_executor import PreparedNode, StaticBundle, apply_nodes
from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.kernel.mechanisms import DEFAULT_MECHANISM_REGISTRY
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _inputs() -> CalibratorInputs:
    aid = ArtifactID.from_sha256_hex("0" * 64)
    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        outputs=["agents.income", "government.balance"],
    )
    graph = ProgramGraph(
        ir_ref=ArtifactRef(
            artifact_id=aid, kind="ir.trinity_bundle", media_type="application/json"
        ),
        nodes=[node],
        edges=[],
        entrypoints=[],
    )
    plan = ExecPlan(program_ref=ProgramGraphRef(artifact_id=aid), order=["tax"])

    def state(income: float) -> GlobalState:
        value = GlobalState.empty(n_agents=5, n_firms=1)
        incomes = jnp.full((5,), income, dtype=jnp.float32)
        return value.replace(agents=value.agents.replace(income=incomes, reported_income=incomes))

    states = jax.tree.map(lambda a, b: jnp.stack((a, b)), state(100), state(300))
    profile = OrderedBatchCalibrationProfile(
        row_ids=("five", "fifteen"),
        states=states,
        row_times=jnp.array([0, 0], dtype=jnp.int32),
        row_keys=jax.random.split(jax.random.PRNGKey(7), 2),
        target_path="government_balance",
        targets=jnp.array([50.0, 150.0], dtype=jnp.float32),
        weights=jnp.array([1.0, 1.0], dtype=jnp.float32),
    )
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="balance",
                model_metric_path="government_balance",
                loss={"relative": False, "scale": "none"},
            )
        ],
        max_steps=60,
        learning_rate=0.1,
        hessian={"enabled": False},
    )
    return CalibratorInputs(
        config=config,
        program_graph=graph,
        exec_plan=plan,
        base_state=state(100),
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=lambda _: {
            "params": {"rate": 0.3},
            "schedule": {"start_step": 0, "end_step": 10},
        },
        ordered_batch_profile=profile,
    )


def test_real_ordered_batch_run_uses_each_row_in_selected_report() -> None:
    report = Calibrator(_inputs()).run()
    assert report.calibrated_params["tax.rate"] == pytest.approx(0.1, rel=0.2)
    assert report.series_comparison["balance"].model == pytest.approx([50.0, 150.0], rel=0.2)
    assert report.series_comparison["balance"].real == [50.0, 150.0]
    assert report.series_comparison["balance"].time == [0.0, 0.0]
    assert report.total_loss < 5.0


@pytest.mark.parametrize(
    "weights",
    [
        [0.0, 0.0],
        [-0.5, 1.0],
        [float("nan"), 1.0],
        [float("inf"), 1.0],
        [3e38, 3e38],
    ],
)
def test_ordered_batch_transformed_domain_never_accepts_invalid_support(weights) -> None:
    inputs = _inputs()
    profile = replace(inputs.ordered_batch_profile, weights=jnp.array(weights, dtype=jnp.float32))
    bundle = Calibrator(inputs)._build_bundle()
    for result in (
        evaluate_ordered_batch_objective(profile, bundle=bundle),
        jax.jit(lambda p: evaluate_ordered_batch_objective(p, bundle=bundle))(profile),
    ):
        assert not bool(result.valid)
        assert bool(jnp.isinf(result.objective))
    with pytest.raises(ValueError, match="invalid numeric support"):
        Calibrator(replace(inputs, ordered_batch_profile=profile)).run()


@pytest.mark.parametrize("targets", [[float("nan"), 0.0], [1e30, 1e30]])
def test_transformed_invalid_target_or_overflow_cannot_report_valid(targets) -> None:
    inputs = _inputs()
    profile = replace(inputs.ordered_batch_profile, targets=jnp.array(targets, dtype=jnp.float32))
    bundle = Calibrator(inputs)._build_bundle()
    result = jax.jit(lambda p: evaluate_ordered_batch_objective(p, bundle=bundle))(profile)
    assert not bool(result.valid)
    assert bool(jnp.isinf(result.objective))


def test_configured_epsilon_priority_and_weighted_fit_metrics_are_consumed() -> None:
    inputs = _inputs()
    config = inputs.config.model_copy(deep=True)
    config.max_steps = 1
    config.targets[0].loss.epsilon = 1.0
    config.targets[0].loss.weight = 2.0
    profile = replace(
        inputs.ordered_batch_profile,
        targets=jnp.array([150.0, 10000.0], dtype=jnp.float32),
        weights=jnp.array([1.0, 0.0], dtype=jnp.float32),
    )
    report = Calibrator(replace(inputs, config=config, ordered_batch_profile=profile)).run()
    residual = report.series_comparison["balance"].model[0] - 150.0
    assert report.total_loss == pytest.approx(2.0 * (residual / 2.0) ** 2, abs=1e-8)
    assert report.per_target_loss["balance"] == pytest.approx(report.total_loss)
    assert report.fit_quality.aggregate.n == 1
    assert report.fit_quality.aggregate.mse == pytest.approx(residual**2, abs=1e-8)
    assert report.fit_quality.aggregate.mae == pytest.approx(abs(residual), abs=1e-8)
    assert report.fit_quality.aggregate == report.fit_quality.per_target["balance"]


@pytest.mark.parametrize("change", ["resample", "step_keys", "alternate_targets", "align"])
def test_unsupported_batch_combinations_refuse_before_optimization(change) -> None:
    inputs = _inputs()
    config = inputs.config.model_copy(deep=True)
    if change == "resample":
        config.time_axis = [0.0, 0.5]
    elif change == "step_keys":
        config.seed_strategy = "step"
    elif change == "align":
        config.targets[0].align.method = "ffill"
    else:
        inputs = replace(inputs, raw_targets={"balance": jnp.array([999.0, 999.0])})
    with pytest.raises(ValueError, match="ordered_batch_profile"):
        Calibrator(replace(inputs, config=config)).run()


def test_exact_row_profile_and_loss_config_change_hessian_identity() -> None:
    inputs = _inputs()
    profile = inputs.ordered_batch_profile
    config = inputs.config
    from polisyos.foundry.calibration.execution_basis import canonical_input_sha256

    first = _make_hessian_reuse_key(
        jnp.array([0.3]),
        ["tax.rate"],
        jnp.array([1.0]),
        config,
        steps=2,
        objective_input_sha256=canonical_input_sha256({"profile": profile, "config": config}),
    )
    altered = replace(profile, row_keys=profile.row_keys[::-1])
    second = _make_hessian_reuse_key(
        jnp.array([0.3]),
        ["tax.rate"],
        jnp.array([1.0]),
        config,
        steps=2,
        objective_input_sha256=canonical_input_sha256({"profile": altered, "config": config}),
    )
    assert _hessian_reuse_key_matches(first, first)
    assert not _hessian_reuse_key_matches(first, second)


def test_ordered_batch_matches_independent_scalar_rows_and_exact_keys() -> None:
    class _Noise:
        def emit_patches(self, state, key, *, target_mask=None):
            del state, target_mask
            noise = jax.random.uniform(key, dtype=jnp.float32)
            return {"government.balance": [{"delta": noise}]}, key

    rows = 3
    states = jax.tree.map(
        lambda leaf: jnp.stack([leaf] * rows), GlobalState.empty(n_agents=1, n_firms=1)
    )
    keys = jax.random.split(jax.random.PRNGKey(73), rows)
    times = jnp.array([0, 1, 20], dtype=jnp.int32)
    bundle = StaticBundle(
        nodes=[
            PreparedNode(
                node_id="noise",
                mechanism_type="noise",
                rank=0,
                start=0,
                end=10,
                mechanism=_Noise(),
                outputs=["government.balance"],
            )
        ],
        incoming_dependencies={},
        slot_registry=DEFAULT_SLOT_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        trainables=[],
    )
    profile = OrderedBatchCalibrationProfile(
        row_ids=("a", "b", "inactive"),
        states=states,
        row_times=times,
        row_keys=keys,
        target_path="government_balance",
        targets=jnp.zeros(rows),
        weights=jnp.ones(rows),
    )
    result = jax.jit(lambda p: evaluate_ordered_batch_objective(p, bundle=bundle))(profile)
    expected_keys = jnp.stack([jax.random.split(keys[0])[1], jax.random.split(keys[1])[1], keys[2]])
    expected = np.array(
        [
            float(jax.random.uniform(expected_keys[0], dtype=jnp.float32)),
            float(jax.random.uniform(expected_keys[1], dtype=jnp.float32)),
            0.0,
        ]
    )
    np.testing.assert_array_equal(result.final_row_keys, expected_keys)
    np.testing.assert_allclose(result.predictions, expected, rtol=0, atol=1e-7)
    assert result.objective == pytest.approx(float(np.mean(expected**2)), rel=1e-6)
    assert bool(result.valid)
    single = replace(
        profile,
        row_ids=(profile.row_ids[0],),
        states=jax.tree.map(lambda leaf: leaf[:1], states),
        row_times=times[:1],
        row_keys=keys[:1],
        targets=profile.targets[:1],
        weights=profile.weights[:1],
    )
    one = evaluate_ordered_batch_objective(single, bundle=bundle)
    np.testing.assert_array_equal(one.final_row_keys[0], result.final_row_keys[0])
    assert float(one.predictions[0]) == pytest.approx(expected[0], abs=1e-7)
    for i in range(rows):
        row = jax.tree.map(lambda leaf, index=i: leaf[index], states)
        scalar, scalar_key = apply_nodes(row, keys[i], bundle=bundle, t=times[i])
        np.testing.assert_array_equal(scalar_key, result.final_row_keys[i])
        assert float(scalar.government_balance) == pytest.approx(expected[i], abs=1e-7)
    order = np.array([2, 0, 1])
    permuted = replace(
        profile,
        row_ids=tuple(profile.row_ids[i] for i in order),
        states=jax.tree.map(lambda leaf: leaf[order], states),
        row_times=times[order],
        row_keys=keys[order],
        targets=profile.targets[order],
        weights=profile.weights[order],
    )
    permuted_result = jax.jit(lambda p: evaluate_ordered_batch_objective(p, bundle=bundle))(
        permuted
    )
    np.testing.assert_allclose(permuted_result.predictions, expected[order], rtol=0, atol=1e-7)
    np.testing.assert_array_equal(permuted_result.final_row_keys, expected_keys[order])
    assert permuted_result.objective == pytest.approx(float(result.objective), rel=1e-6)

    original_partitionability = bool(jax.config.jax_threefry_partitionable)
    with jax.threefry_partitionable(not original_partitionability):
        changed = evaluate_ordered_batch_objective(profile, bundle=bundle)
        changed_keys = jnp.stack(
            [jax.random.split(keys[0])[1], jax.random.split(keys[1])[1], keys[2]]
        )
        np.testing.assert_array_equal(changed.final_row_keys, changed_keys)
        assert not np.array_equal(changed_keys[:2], expected_keys[:2])
        assert not np.allclose(np.asarray(changed.predictions[:2]), expected[:2], rtol=0, atol=1e-7)
    assert bool(jax.config.jax_threefry_partitionable) == original_partitionability


@pytest.mark.parametrize("priority", [1e-50, 1e40])
def test_effective_target_priority_underflow_or_overflow_refuses(priority) -> None:
    inputs = _inputs()
    config = inputs.config.model_copy(deep=True)
    config.targets[0].loss.weight = priority
    with pytest.raises(ValueError, match="effective target priority"):
        Calibrator(replace(inputs, config=config)).run()


def test_integer_weight_accumulation_is_not_a_supported_float_profile() -> None:
    inputs = _inputs()
    profile = replace(
        inputs.ordered_batch_profile, weights=jnp.array([2000000000, 2000000000], dtype=jnp.int32)
    )
    bundle = Calibrator(inputs)._build_bundle()
    for call in [
        lambda: evaluate_ordered_batch_objective(profile, bundle=bundle),
        lambda: jax.jit(lambda p: evaluate_ordered_batch_objective(p, bundle=bundle))(profile),
    ]:
        with pytest.raises(ValueError, match="require float32 or float64"):
            call()


def test_real_ordered_objective_jit_gradient_and_hessian_match_quadratic() -> None:
    from polisyos.foundry.calibration.pure_executor import apply_trainable_values

    inputs = _inputs()
    bundle = Calibrator(inputs)._build_bundle()
    profile = inputs.ordered_batch_profile

    def objective(rate):
        return evaluate_ordered_batch_objective(
            profile,
            bundle=apply_trainable_values(bundle, [rate]),
            loss_config=inputs.config.targets[0].loss,
        ).objective

    rate = jnp.asarray(0.2, dtype=jnp.float32)
    # Five incomes100/300 give slopes500/1500, with independent targets50/150.
    slopes = np.asarray([500.0, 1500.0])
    residual = slopes * float(rate) - np.asarray([50.0, 150.0])
    epsilon_scale = (1 + inputs.config.targets[0].loss.epsilon) ** 2
    expected_value = float(np.mean(residual**2) / epsilon_scale)
    expected_grad = float(2 * np.mean(slopes * residual) / epsilon_scale)
    expected_hessian = float(2 * np.mean(slopes**2) / epsilon_scale)
    assert float(jax.jit(objective)(rate)) == pytest.approx(expected_value, rel=1e-5)
    assert float(jax.jit(jax.grad(objective))(rate)) == pytest.approx(expected_grad, rel=1e-5)
    assert float(jax.jit(jax.hessian(objective))(rate)) == pytest.approx(expected_hessian, rel=1e-5)


def test_parameter_dependent_off_target_nonfinite_state_cannot_win(monkeypatch) -> None:
    import equinox as eqx

    from polisyos.foundry.calibration.pure_executor import apply_trainable_values

    class _OffTarget(eqx.Module):
        rate: jax.Array

        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            invalid = jnp.where(self.rate > 0.32, jnp.nan, 0.0)
            return {
                "agents.income": [{"delta": jnp.full_like(state.agents.income, invalid)}],
                "government.balance": [{"delta": self.rate}],
            }, key

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        lambda _name, params, **_kwargs: _OffTarget(jnp.asarray(params["rate"], dtype=jnp.float32)),
    )
    inputs = _inputs()
    profile = replace(inputs.ordered_batch_profile, targets=jnp.ones(2, dtype=jnp.float32))
    bundle = Calibrator(inputs)._build_bundle()
    invalid_bundle = apply_trainable_values(bundle, [jnp.asarray(0.5, dtype=jnp.float32)])
    invalid = jax.jit(lambda p: evaluate_ordered_batch_objective(p, bundle=invalid_bundle))(profile)
    assert not bool(invalid.valid)
    assert bool(jnp.isinf(invalid.objective))
    assert bool(jnp.all(jnp.isnan(invalid.final_states.agents.income)))
    config = inputs.config.model_copy(deep=True)
    config.max_steps = 1
    config.learning_rate = 1.0
    report = Calibrator(replace(inputs, config=config, ordered_batch_profile=profile)).run()
    # A numerically invalid off-target update may not replace the last valid state.
    assert report.calibrated_params["tax.rate"] == pytest.approx(0.3, abs=1e-6)
    assert np.isfinite(report.total_loss)
    assert report.series_comparison["balance"].model == pytest.approx([0.3, 0.3], abs=1e-6)


def test_finite_first_profile_explicitly_refuses_untouched_optional_sentinels() -> None:
    from polisyos.foundry.contracts.state import FeedbackState

    inputs = _inputs()
    profile = inputs.ordered_batch_profile
    sentinel = FeedbackState.empty(n_feedback=1)
    states = profile.states.replace(
        feedback_state=jax.tree.map(lambda value: jnp.stack((value, value)), sentinel)
    )
    result = evaluate_ordered_batch_objective(
        replace(profile, states=states),
        bundle=Calibrator(inputs)._build_bundle(),
    )
    assert not bool(result.valid)
    assert bool(jnp.isinf(result.objective))
    with pytest.raises(ValueError, match="invalid numeric support"):
        Calibrator(replace(inputs, ordered_batch_profile=replace(profile, states=states))).run()


def test_positive_row_weight_underflow_is_explicitly_invalid_in_effective_reduction() -> None:
    if not jax.config.x64_enabled:
        pytest.skip("float64 source witness requires a separately pre-enabled measured x64 profile")
    inputs = _inputs()
    profile = replace(
        inputs.ordered_batch_profile, weights=jnp.asarray([1e-50, 1.0], dtype=jnp.float64)
    )
    bundle = Calibrator(inputs)._build_bundle()
    result = jax.jit(lambda value: evaluate_ordered_batch_objective(value, bundle=bundle))(profile)
    assert not bool(result.valid)
    assert bool(jnp.isinf(result.objective))
    with pytest.raises(ValueError, match="invalid numeric support"):
        Calibrator(replace(inputs, ordered_batch_profile=profile)).run()


@pytest.mark.parametrize(
    "case",
    [
        "empty",
        "target_rank",
        "weight_rank",
        "key_shape",
        "key_dtype",
        "time_dtype",
        "duplicate_ids",
        "state_axis",
        "vector_target",
    ],
)
def test_ordered_profile_structure_refuses_broadcasting_and_empty_adversaries(case) -> None:
    inputs = _inputs()
    profile = inputs.ordered_batch_profile
    changes = {
        "empty": {"row_ids": ()},
        "target_rank": {"targets": profile.targets[:, None]},
        "weight_rank": {"weights": profile.weights[:, None]},
        "key_shape": {"row_keys": profile.row_keys[:, 0]},
        "key_dtype": {"row_keys": profile.row_keys.astype(jnp.int32)},
        "time_dtype": {"row_times": profile.row_times.astype(jnp.float32)},
        "duplicate_ids": {"row_ids": ("same", "same")},
        "state_axis": {"states": jax.tree.map(lambda value: value[:1], profile.states)},
        "vector_target": {"target_path": "agents.income"},
    }[case]
    with pytest.raises(ValueError):
        evaluate_ordered_batch_objective(
            replace(profile, **changes), bundle=Calibrator(inputs)._build_bundle()
        )


@pytest.mark.parametrize("weights", [[-1e-50, 1.0], [float("nan"), 1.0], [float("inf"), 1.0]])
def test_original_float64_weight_domain_survives_effective_float32_projection(weights) -> None:
    if not jax.config.x64_enabled:
        pytest.skip("float64 source witness requires a separately pre-enabled measured x64 profile")
    inputs = _inputs()
    profile = replace(inputs.ordered_batch_profile, weights=jnp.asarray(weights, dtype=jnp.float64))
    bundle = Calibrator(inputs)._build_bundle()
    for result in (
        evaluate_ordered_batch_objective(profile, bundle=bundle),
        jax.jit(lambda value: evaluate_ordered_batch_objective(value, bundle=bundle))(profile),
    ):
        assert not bool(result.valid)
        assert bool(jnp.isinf(result.objective))
    with pytest.raises(ValueError, match="invalid numeric support"):
        Calibrator(replace(inputs, ordered_batch_profile=profile)).run()


def test_typed_source_dtype_is_preserved_or_refused_before_outer_jit_conversion() -> None:
    inputs = _inputs()
    original = np.asarray([1.0, 2.0], dtype=np.float64)
    if not jax.config.x64_enabled:
        with pytest.raises(ValueError, match="source dtype is unavailable"):
            replace(inputs.ordered_batch_profile, weights=original)
        return
    profile = replace(inputs.ordered_batch_profile, weights=original)
    assert profile.weights.dtype == np.dtype("float64")
    bundle = Calibrator(inputs)._build_bundle()
    eager = evaluate_ordered_batch_objective(profile, bundle=bundle)
    transformed = jax.jit(lambda value: evaluate_ordered_batch_objective(value, bundle=bundle))(
        profile
    )
    assert bool(eager.valid) and bool(transformed.valid)
    assert float(transformed.objective) == pytest.approx(float(eager.objective))


def test_default_profile_zero_individual_weight_remains_a_real_positive() -> None:
    inputs = _inputs()
    profile = replace(
        inputs.ordered_batch_profile, weights=jnp.asarray([0.0, 1.0], dtype=jnp.float32)
    )
    bundle = Calibrator(inputs)._build_bundle()
    for result in (
        evaluate_ordered_batch_objective(profile, bundle=bundle),
        jax.jit(lambda value: evaluate_ordered_batch_objective(value, bundle=bundle))(profile),
    ):
        assert bool(result.valid)
        residual = float(result.predictions[1] - profile.targets[1])
        assert float(result.objective) == pytest.approx(
            (residual / (1.0 + inputs.config.targets[0].loss.epsilon)) ** 2
        )
