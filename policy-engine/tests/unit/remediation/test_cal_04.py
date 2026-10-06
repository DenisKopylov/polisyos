"""Distinguishing witnesses for CAL-04 final evaluation and Hessian reuse."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, ProgramGraphRef
from polisyos.foundry.calibration import calibrator as calibrator_module
from polisyos.foundry.calibration.calibrator import (
    Calibrator,
    CalibratorInputs,
    _hessian_reuse_key_matches,
    _HessianReuseKey,
    _select_lower_loss_state,
)
from polisyos.foundry.calibration.pure_executor import PreparedNode, TrainableHandle
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.mechanisms.fiscal import IncomeTax
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)

pytestmark = pytest.mark.unit


class _FakeBundle:
    """Small bundle whose trainable value is the JAX objective coordinate."""

    def __init__(self, theta: object = 0.0) -> None:
        self.theta = jnp.asarray(theta)
        self.nodes = [
            PreparedNode(
                node_id="synthetic",
                mechanism_type="synthetic",
                rank=0,
                start=0,
                end=0,
                outputs=["objective"],
                mechanism=IncomeTax(rate=0.0, n_agents=1),
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

    dummy_id = ArtifactID.from_sha256_hex("0" * 64)
    graph = ProgramGraph(
        ir_ref=ArtifactRef(
            artifact_id=dummy_id, kind="ir.trinity_bundle", media_type="application/json"
        ),
        nodes=[],
        edges=[],
        entrypoints=[],
    )
    inputs = CalibratorInputs(
        config=config,
        program_graph=graph,
        exec_plan=ExecPlan(program_ref=ProgramGraphRef(artifact_id=dummy_id), order=[]),
        base_state=GlobalState.empty(n_agents=1, n_firms=1),
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
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
    assert not _hessian_reuse_key_matches(
        base, replace(base, objective_identity="changed-input-or-model-law")
    )
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

    report = calibrator.run()

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


def test_step_seeded_finalist_comparison_uses_one_final_replica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step-varying training replicas are not mixed during final selection."""
    concrete_keys: list[tuple[int, ...]] = []

    def seeded_scan(base_state, *, steps, root_key, bundle, metric_paths, controls_seq):
        # Differentiated scans have abstract keys; only concrete finalists are recorded.
        with suppress(Exception):
            concrete_keys.append(tuple(int(value) for value in np.asarray(root_key).reshape(-1)))
        noise = jax.random.normal(root_key, shape=())
        return base_state, {"objective": jnp.reshape(bundle.theta + noise, (1,))}

    calibrator, _ = _make_fake_calibrator(
        monkeypatch,
        _calibrator_config(max_steps=2, seed_strategy="step"),
        seeded_scan,
    )

    calibrator.run()

    assert len(concrete_keys) >= 2
    assert concrete_keys[-1] == concrete_keys[-2]


def test_fixed_seed_keeps_final_candidate_on_the_same_replica(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fixed-seed training and final evaluation retain one stochastic replica."""
    concrete_keys: list[tuple[int, ...]] = []

    def seeded_scan(base_state, *, steps, root_key, bundle, metric_paths, controls_seq):
        with suppress(Exception):
            concrete_keys.append(tuple(int(value) for value in np.asarray(root_key).reshape(-1)))
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
    assert report.uncertainties is None
    assert report.execution_context["curvature_diagnostic"]["raw_rank"] == 1
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
    assert report.uncertainties is None
    assert report.execution_context["curvature_diagnostic"]["raw_rank"] == 1
    assert "Hessian reused from selected start" not in report.diagnostics


def test_custom_auxiliary_callback_does_not_reuse_a_matching_hessian(monkeypatch):
    calls = []
    real_compute = calibrator_module.compute_hessian

    def recording_compute(*args, **kwargs):
        calls.append("hessian")
        return real_compute(*args, **kwargs)

    class CustomPenalty:
        component_name = "opaque_custom_penalty"

        def compute(self, *, traces):
            return jnp.sum(traces["objective"] * 0.0), {}

    monkeypatch.setattr(calibrator_module, "compute_hessian", recording_compute)
    calibrator, _ = _make_fake_calibrator(
        monkeypatch, _calibrator_config(hessian=True, multi_start=2), _quadratic_scan
    )
    calibrator.inputs.aux_loss_components = (CustomPenalty(),)
    report = calibrator.run()
    assert len(calls) == 3  # two starts plus uncached final diagnostic
    assert report.execution_context["objective_identity_status"] == "not_established"
    assert "Hessian reused from selected start" not in report.diagnostics
