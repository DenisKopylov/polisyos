"""Distinguishing witnesses for CAL-04 final evaluation and Hessian reuse."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.calibration import calibrator as calibrator_module
from polisyos.foundry.calibration.calibrator import (
    Calibrator,
    CalibratorInputs,
    _hessian_reuse_key_matches,
    _HessianReuseKey,
    _select_lower_loss_state,
)
from polisyos.foundry.calibration.pure_executor import TrainableHandle
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget

pytestmark = pytest.mark.unit


class _FakeBundle:
    """Small bundle whose trainable value is the JAX objective coordinate."""

    def __init__(self, theta: object = 0.0) -> None:
        self.theta = jnp.asarray(theta)
        self.nodes = [
            SimpleNamespace(
                node_id="synthetic",
                mechanism=SimpleNamespace(),
            )
        ]
        self.trainables = [
            TrainableHandle(
                node_index=0,
                node_id="synthetic",
                mechanism_type="synthetic",
                field_name="theta",
                lower=None,
                upper=None,
            )
        ]


def _calibrator_config(
    *,
    learning_rate: float = 0.5,
    max_steps: int = 1,
    seed_strategy: str = "fixed",
    hessian: bool = False,
    multi_start: int | None = None,
) -> CalibrationConfig:
    """Build a one-dimensional calibration objective for real ``Calibrator.run``."""
    return CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="objective",
                model_metric_path="objective",
                loss={"relative": False},
            )
        ],
        max_steps=max_steps,
        learning_rate=learning_rate,
        seed=7,
        seed_strategy=seed_strategy,
        hessian={"enabled": hessian},
        multi_start=(
            {"n_starts": multi_start, "perturbation_scale": 0.1}
            if multi_start is not None
            else None
        ),
    )


def _make_fake_calibrator(
    monkeypatch: pytest.MonkeyPatch,
    config: CalibrationConfig,
    scan,
    *,
    target_value: float = 1.0,
) -> tuple[Calibrator, _FakeBundle]:
    """Wire a real ``Calibrator.run`` to a parameter-connected synthetic scan."""
    bundle = _FakeBundle()

    monkeypatch.setattr(calibrator_module.jax, "jit", lambda function: function)
    monkeypatch.setattr(calibrator_module, "is_hpc_observability_enabled", lambda: False)
    monkeypatch.setattr(
        calibrator_module,
        "extract_trainable_values",
        lambda _bundle: [jnp.asarray(0.0, dtype=jnp.float32)],
    )

    def apply_values(current: _FakeBundle, values: list[object]) -> _FakeBundle:
        updated = _FakeBundle(values[0])
        updated.nodes = current.nodes
        updated.trainables = current.trainables
        return updated

    monkeypatch.setattr(calibrator_module, "apply_trainable_values", apply_values)
    monkeypatch.setattr(calibrator_module, "run_pure_scan", scan)

    inputs = CalibratorInputs(
        config=config,
        program_graph=SimpleNamespace(),
        exec_plan=SimpleNamespace(),
        base_state=SimpleNamespace(),
        mechanism_registry=SimpleNamespace(),
        slot_registry=SimpleNamespace(slots={}),
        merge_registry=SimpleNamespace(),
        selector_field_registry=None,
        parameter_loader=lambda _value: {},
        raw_targets={"objective": jnp.asarray([target_value], dtype=jnp.float32)},
        controls_seq=jnp.asarray([0], dtype=jnp.int32),
    )
    calibrator = Calibrator(inputs)
    monkeypatch.setattr(calibrator, "_build_bundle", lambda: bundle)
    return calibrator, bundle


def _quadratic_scan(_base_state, *, steps, root_key, bundle, metric_paths, controls_seq):
    """Return the real JAX quadratic coordinate used by the run witnesses."""
    del steps, root_key, metric_paths, controls_seq
    return _base_state, {"objective": jnp.reshape(bundle.theta, (1,))}


def test_last_produced_iterate_can_replace_previous_state_only_when_evaluated() -> None:
    """An evaluated 0.5 candidate wins, while an evaluated overshoot at 4 loses."""
    previous = _select_lower_loss_state(
        previous_loss=1.0,
        previous_state=0.0,
        candidate_loss=0.25,
        candidate_state=0.5,
    )
    overshoot = _select_lower_loss_state(
        previous_loss=1.0,
        previous_state=0.0,
        candidate_loss=9.0,
        candidate_state=4.0,
    )

    assert previous == (0.25, 0.5)
    assert overshoot == (1.0, 0.0)


def test_hessian_reuse_requires_point_coordinates_weights_seed_and_numeric_policy() -> None:
    """A cached Hessian is reusable only for the exact objective identity."""
    base = _HessianReuseKey(
        flat_theta=(0.25,),
        param_names=("rate",),
        weights=(1.0,),
        seed=7,
        seed_strategy="fixed",
        steps=2,
        dtype="float32",
        damping=1e-6,
        rank_tol=1e-6,
        max_params=None,
        fidelity_mode="relaxed",
        fidelity_temperature=1.0,
        fidelity_force_override=True,
    )

    assert _hessian_reuse_key_matches(base, base)
    assert not _hessian_reuse_key_matches(None, base)
    assert not _hessian_reuse_key_matches(base, None)
    assert not _hessian_reuse_key_matches(None, None)
    assert not _hessian_reuse_key_matches(
        base,
        base.__class__(**{**base.__dict__, "flat_theta": (0.5,)}),
    )
    assert not _hessian_reuse_key_matches(
        base,
        base.__class__(**{**base.__dict__, "weights": (2.0,)}),
    )
    assert not _hessian_reuse_key_matches(
        base,
        base.__class__(**{**base.__dict__, "seed": 8}),
    )
    assert not _hessian_reuse_key_matches(
        base,
        base.__class__(**{**base.__dict__, "rank_tol": 1e-5}),
    )


def test_hessian_key_rejects_nonfinite_point_even_when_shape_matches() -> None:
    """A malformed point cannot inherit a diagnostic result by tuple shape."""
    finite = _HessianReuseKey(
        flat_theta=(0.25,),
        param_names=("rate",),
        weights=(1.0,),
        seed=7,
        seed_strategy="fixed",
        steps=2,
        dtype="float32",
        damping=1e-6,
        rank_tol=1e-6,
        max_params=None,
        fidelity_mode="relaxed",
        fidelity_temperature=1.0,
        fidelity_force_override=True,
    )
    malformed = finite.__class__(**{**finite.__dict__, "flat_theta": (np.nan,)})

    assert not _hessian_reuse_key_matches(finite, malformed)


@pytest.mark.parametrize(
    ("learning_rate", "candidate_should_win"),
    [
        (0.5, True),  # f(x)=(x-1)^2: the final iterate improves the initial loss.
        (4.0, False),  # The overshoot x=4 has loss 9 and must not replace loss 1.
    ],
)
def test_real_calibrator_run_evaluates_and_selects_last_iterate(
    monkeypatch: pytest.MonkeyPatch,
    learning_rate: float,
    candidate_should_win: bool,
) -> None:
    """A one-step budget selects by evaluated loss, not optimizer provenance.

    The production optimizer is Adam, so the exact first iterate is subject to
    its epsilon and dtype policy; the distinguishing contract is improvement
    versus rejection of the overshoot, not an SGD-exact coordinate of 0.5.
    """
    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(learning_rate=learning_rate),
        _quadratic_scan,
    )

    report = calibrator.run()
    theta = report.calibrated_params["synthetic.theta"]

    if candidate_should_win:
        assert 0.0 < theta < 1.0
        assert report.total_loss < 1.0
    else:
        assert theta == pytest.approx(0.0)
        assert report.total_loss == pytest.approx(1.0)
    assert report.total_loss == pytest.approx((theta - 1.0) ** 2)
    assert len(report.loss_history) == 1


def test_real_calibrator_final_forward_feeds_all_report_projections_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One final parameter-connected scan supplies consistent report projections."""
    calls = 0

    def counting_scan(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _quadratic_scan(*args, **kwargs)

    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(learning_rate=0.5),
        counting_scan,
    )

    def unexpected_hessian(*_args, **_kwargs):
        pytest.fail("Disabled Hessian configuration must not compute curvature")

    monkeypatch.setattr(calibrator_module, "compute_hessian", unexpected_hessian)

    report = calibrator.run()
    assert report.uncertainties is None

    # One scan is the optimizer's pre-update objective; the second is the
    # evaluated final iterate whose snapshot feeds all report projections.
    assert calls == 2
    theta = report.calibrated_params["synthetic.theta"]
    model = report.series_comparison["objective"].model
    assert model == pytest.approx([theta])
    assert 0.0 < theta < 1.0
    expected_loss = (theta - 1.0) ** 2
    assert report.total_loss == pytest.approx(expected_loss)
    assert report.per_target_loss["objective"] == pytest.approx(expected_loss)
    assert report.total_loss < 1.0


@pytest.mark.parametrize("seed_strategy", ["fixed", "step"])
def test_stationary_checked_snapshot_has_no_identical_final_scan(
    monkeypatch: pytest.MonkeyPatch, seed_strategy: str
) -> None:
    """A checked stationary point at replica0 feeds the final report directly."""
    calls = 0

    def scan(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _quadratic_scan(*args, **kwargs)

    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(seed_strategy=seed_strategy),
        scan,
        target_value=0.0,
    )
    report = calibrator.run()
    assert calls == 1
    assert report.total_loss == 0.0
    assert report.calibrated_params["synthetic.theta"] == 0.0
    assert report.series_comparison["objective"].model == [0.0]
    with monkeypatch.context() as removed:
        removed.setattr(calibrator_module, "_state_values_equal", lambda *_args: False)
        before = calls
        redundant = calibrator.run()
    assert calls - before == 2
    assert redundant.calibrated_params == report.calibrated_params
    assert redundant.series_comparison == report.series_comparison
    assert redundant.total_loss == report.total_loss


def test_different_points_with_equal_loss_keep_checked_point_and_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A scalar tie cannot substitute candidate2's trace for checked baseline0."""
    scans = 0
    comparisons = []
    actual_selection = calibrator_module._select_lower_loss_state

    def scan(*args, **kwargs):
        nonlocal scans
        scans += 1
        return _quadratic_scan(*args, **kwargs)

    def record_selection(**kwargs):
        comparisons.append(kwargs)
        return actual_selection(**kwargs)

    # This orchestration witness selects a real exact SGD step, 0→2, for
    # (x−1)^2. Native Adam/Foundry execution is qualified separately.
    calibrator, _ = _make_fake_calibrator(monkeypatch, _calibrator_config(learning_rate=1.0), scan)
    monkeypatch.setattr(
        calibrator_module.optax,
        "adam",
        lambda learning_rate: calibrator_module.optax.sgd(learning_rate),
    )
    monkeypatch.setattr(calibrator_module, "_select_lower_loss_state", record_selection)
    report = calibrator.run()
    assert scans == 2 and len(comparisons) == 1
    assert float(comparisons[0]["previous_state"][0]) == 0.0
    assert float(comparisons[0]["candidate_state"][0]) == 2.0
    assert comparisons[0]["previous_loss"] == comparisons[0]["candidate_loss"] == 1.0
    assert report.total_loss == 1.0
    assert report.calibrated_params["synthetic.theta"] == 0.0
    assert report.series_comparison["objective"].model == [0.0]


def test_failed_final_comparison_keeps_actual_checked_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Budget denial after the step preserves the checked point and original loss."""
    calls = 0

    def scan(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("controlled forward budget exhausted")
        return _quadratic_scan(*args, **kwargs)

    calibrator, _ = _make_fake_calibrator(monkeypatch, _calibrator_config(learning_rate=0.5), scan)
    report = calibrator.run()
    assert calls == 2
    assert report.calibrated_params["synthetic.theta"] == 0.0
    assert report.total_loss == 1.0
    assert report.per_target_loss["objective"] == 1.0
    assert report.series_comparison["objective"].model == [0.0]
    assert report.loss_history == [1.0]
    assert any("Last iterate evaluation failed" in value for value in report.diagnostics)


def test_real_jax_nonfinite_update_keeps_last_checked_state() -> None:
    """A finite value with a non-finite derivative does not admit a NaN update."""
    # This witness exercises the same value/grad path as Calibrator.run while
    # avoiding a resource-bearing run: sqrt(0) is finite but its derivative is
    # non-finite, so the produced optimizer state must remain unselected.
    value = jnp.asarray(0.0, dtype=jnp.float32)

    def objective(x):
        return jnp.square(jnp.sqrt(x))

    value_at_zero, gradient_at_zero = jax.value_and_grad(objective)(value)

    assert float(value_at_zero) == pytest.approx(0.0)
    assert not bool(jnp.all(jnp.isfinite(gradient_at_zero)))
    assert _select_lower_loss_state(
        previous_loss=0.0,
        previous_state=0.0,
        candidate_loss=float("nan"),
        candidate_state=float("nan"),
    ) == (0.0, 0.0)


def test_real_calibrator_nonfinite_update_keeps_finite_last_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calibrator.run keeps the finite checked state after a non-finite update."""

    def nonfinite_gradient_scan(
        _base_state, *, steps, root_key, bundle, metric_paths, controls_seq
    ):
        del steps, root_key, metric_paths, controls_seq
        return _base_state, {"objective": jnp.reshape(jnp.sqrt(bundle.theta), (1,))}

    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(learning_rate=0.5),
        nonfinite_gradient_scan,
        target_value=0.0,
    )

    report = calibrator.run()

    assert report.calibrated_params["synthetic.theta"] == pytest.approx(0.0)
    assert report.total_loss == pytest.approx(0.0)
    assert any("Non-finite gradients" in item for item in report.diagnostics)


def _concrete_key_tuple(root_key: object) -> tuple[int, ...] | None:
    """Observe concrete keys; only JAX tracers lack a materialized host value."""
    if isinstance(root_key, jax.core.Tracer):
        return None
    return tuple(int(value) for value in np.asarray(root_key).reshape(-1))


def test_concrete_key_observer_does_not_treat_none_as_a_tracer() -> None:
    with pytest.raises(TypeError):
        _concrete_key_tuple(None)


def test_concrete_key_capture_propagates_unexpected_conversion_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only traced values are skipped; broken concrete-key conversion must surface."""

    def fail_conversion(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("unexpected key conversion failure")

    assert _concrete_key_tuple(jax.random.PRNGKey(0)) is not None
    monkeypatch.setattr(np, "asarray", fail_conversion)
    with pytest.raises(RuntimeError, match="unexpected key conversion failure"):
        _concrete_key_tuple(object())


def test_step_seeded_finalist_comparison_uses_one_final_replica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step-varying training replicas are not mixed during final selection."""
    concrete_keys: list[tuple[int, ...]] = []
    comparisons = []
    actual_selection = calibrator_module._select_lower_loss_state

    def observe_selection(**kwargs):
        comparisons.append(kwargs)
        return actual_selection(**kwargs)

    monkeypatch.setattr(calibrator_module, "_select_lower_loss_state", observe_selection)

    def seeded_scan(base_state, *, steps, root_key, bundle, metric_paths, controls_seq):
        concrete_key = _concrete_key_tuple(root_key)
        if concrete_key is not None:
            concrete_keys.append(concrete_key)
        noise = jax.random.normal(root_key, shape=())
        return base_state, {"objective": jnp.reshape(bundle.theta + noise, (1,))}

    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(max_steps=2, seed_strategy="step"),
        seeded_scan,
    )

    report = calibrator.run()

    assert len(concrete_keys) >= 2
    assert len(comparisons) == 1
    # The best checked point may already have an exact replica0 snapshot.
    # Requiring two adjacent fresh scans would reject legitimate snapshot
    # reuse. Check the actual values compared, independently, instead.
    final_key = jax.random.fold_in(jax.random.PRNGKey(7), 0)
    assert concrete_keys[-1] == _concrete_key_tuple(final_key)
    assert any(key != concrete_keys[-1] for key in concrete_keys)
    noise = float(jax.random.normal(final_key, shape=()))
    comparison = comparisons[0]
    wrong_key = jax.random.fold_in(jax.random.PRNGKey(7), 1)
    wrong_noise = float(jax.random.normal(wrong_key, shape=()))
    wrong_replica_distinguished = False
    for state_name, loss_name in (
        ("previous_state", "previous_loss"),
        ("candidate_state", "candidate_loss"),
    ):
        theta = float(comparison[state_name][0])
        residual = np.float32(theta + noise) - np.float32(1.0)
        expected = float(np.float32(residual * residual))
        assert comparison[loss_name] == pytest.approx(expected, rel=1e-6, abs=1e-6)
        wrong_residual = np.float32(theta + wrong_noise) - np.float32(1.0)
        wrong_loss = float(np.float32(wrong_residual * wrong_residual))
        wrong_replica_distinguished |= not np.isclose(expected, wrong_loss, rtol=1e-6, atol=1e-6)
    assert wrong_replica_distinguished
    selected_theta = report.calibrated_params["synthetic.theta"]
    assert report.series_comparison["objective"].model == pytest.approx(
        [selected_theta + noise], rel=1e-6, abs=1e-6
    )
    assert report.total_loss == pytest.approx(
        float(np.float32(np.float32(selected_theta + noise) - 1.0) ** 2),
        rel=1e-6,
        abs=1e-6,
    )


def test_fixed_seed_keeps_final_candidate_on_the_same_replica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fixed-seed training and final evaluation retain one stochastic replica."""
    concrete_keys: list[tuple[int, ...]] = []

    def seeded_scan(base_state, *, steps, root_key, bundle, metric_paths, controls_seq):
        concrete_key = _concrete_key_tuple(root_key)
        if concrete_key is not None:
            concrete_keys.append(concrete_key)
        noise = jax.random.normal(root_key, shape=())
        return base_state, {"objective": jnp.reshape(bundle.theta + noise, (1,))}

    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(max_steps=2, seed_strategy="fixed"),
        seeded_scan,
    )

    calibrator.run()

    assert concrete_keys
    assert all(key == concrete_keys[0] for key in concrete_keys)


def test_multi_start_reuses_selected_hessian_without_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N starts produce N Hessians when the selected identity is unchanged."""
    real_compute_hessian = calibrator_module.compute_hessian
    hessian_calls: list[tuple[float, ...]] = []
    parameter_connected: list[bool] = []

    def recording_compute(loss_fn, flat_theta, param_names, **kwargs):
        point = jnp.asarray(flat_theta)
        hessian_calls.append(tuple(float(value) for value in np.asarray(point).reshape(-1)))
        before = float(loss_fn(point))
        after = float(loss_fn(point + 0.125))
        parameter_connected.append(before != after)
        return real_compute_hessian(loss_fn, point, param_names, **kwargs)

    monkeypatch.setattr(calibrator_module, "compute_hessian", recording_compute)
    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(hessian=True, multi_start=2),
        _quadratic_scan,
    )

    report = calibrator.run()

    assert len(hessian_calls) == 2
    assert all(parameter_connected)
    assert report.uncertainties is not None
    assert "Hessian reused from selected start" in report.diagnostics


def test_multi_start_recomputes_hessian_after_identity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deliberate identity mismatch forces one final parameter-connected recompute."""
    real_make_key = calibrator_module._make_hessian_reuse_key
    key_calls = 0
    hessian_calls = 0

    def mismatching_key(*args, **kwargs):
        nonlocal key_calls
        key = real_make_key(*args, **kwargs)
        key_calls += 1
        if key_calls == 3:  # two run-local keys, then the final selected key
            return replace(key, damping=key.damping + 1.0)
        return key

    real_compute_hessian = calibrator_module.compute_hessian

    def recording_compute(loss_fn, flat_theta, param_names, **kwargs):
        nonlocal hessian_calls
        hessian_calls += 1
        return real_compute_hessian(loss_fn, flat_theta, param_names, **kwargs)

    monkeypatch.setattr(calibrator_module, "_make_hessian_reuse_key", mismatching_key)
    monkeypatch.setattr(calibrator_module, "compute_hessian", recording_compute)
    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(hessian=True, multi_start=2),
        _quadratic_scan,
    )

    report = calibrator.run()

    assert key_calls == 3
    assert hessian_calls == 3
    assert report.uncertainties is not None
    assert "Hessian reused from selected start" not in report.diagnostics


@pytest.mark.parametrize("mismatched_final_point", [False, True])
def test_actual_reuse_consumer_preserves_quartic_point_curvature(
    monkeypatch: pytest.MonkeyPatch, mismatched_final_point: bool
) -> None:
    """A constant-Hessian fixture cannot stand in for exact-point reuse."""
    real_compute = calibrator_module.compute_hessian
    real_key = calibrator_module._make_hessian_reuse_key
    calls = []
    key_calls = 0

    def quartic_scan(base_state, *, bundle, **_kwargs):
        return base_state, {"objective": jnp.reshape(jnp.square(bundle.theta), (1,))}

    def record_compute(function, point, names, **kwargs):
        result = real_compute(function, point, names, **kwargs)
        assert result.strategy == "exact" and result.fallback_cause is None
        coordinate = float(np.asarray(point)[0])
        np.testing.assert_allclose(
            result.raw_eigenvalues, [12.0 * coordinate**2], rtol=1e-6, atol=1e-6
        )
        calls.append((coordinate, result))
        return result

    def point_key(*args, **kwargs):
        nonlocal key_calls
        key_calls += 1
        key = real_key(*args, **kwargs)
        if mismatched_final_point and key_calls == 3:
            return replace(key, flat_theta=(key.flat_theta[0] + 0.25,))
        return key

    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(learning_rate=1e-10, hessian=True, multi_start=2),
        quartic_scan,
        target_value=0.0,
    )
    monkeypatch.setattr(
        calibrator_module, "extract_trainable_values", lambda _bundle: [jnp.float32(0.25)]
    )
    monkeypatch.setattr(calibrator_module, "compute_hessian", record_compute)
    monkeypatch.setattr(calibrator_module, "_make_hessian_reuse_key", point_key)
    report = calibrator.run()
    assert len(calls) == (3 if mismatched_final_point else 2)
    assert not np.isclose(calls[0][0], calls[1][0], rtol=1e-6, atol=1e-6)
    assert not np.isclose(
        calls[0][1].raw_eigenvalues[0], calls[1][1].raw_eigenvalues[0], rtol=1e-6, atol=1e-6
    )
    selected = report.calibrated_params["synthetic.theta"]
    expected_curvature = 12.0 * selected**2
    expected_covariance = 1.0 / (expected_curvature + calibrator.inputs.config.hessian.damping)
    assert report.uncertainties is not None
    np.testing.assert_allclose(
        report.uncertainties.covariance, [[expected_covariance]], rtol=1e-6, atol=1e-6
    )
    assert ("Hessian reused from selected start" in report.diagnostics) is (
        not mismatched_final_point
    )
