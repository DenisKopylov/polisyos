"""Native witnesses for the training measure shared by calibration consumers.

All model outputs, derivatives and updates come from the real tax mechanism,
scan, JAX and Optax. Recording wrappers only retain the functions actually
submitted to those consumers; their computations are delegated unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
import numpy.testing as npt
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, ProgramGraphRef, ProgramNode
from polisyos.foundry.calibration import calibrator as calibrator_module
from polisyos.foundry.calibration.bijectors import make_bijector
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.calibration.measurement import (
    CalibrationTargetBundle,
    CalibrationTargetBundleCompiler,
    DefaultMeasurementAwareLossAdapter,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget, TargetLossConfig
from polisyos.ir.kernel.constraints import ConstraintRegistry, ConstraintSpec
from polisyos.ir.kernel.mechanisms import DEFAULT_MECHANISM_REGISTRY
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.compiler import (
    CalibrationSplitLabel,
    CalibrationSplitPlan,
    CalibrationSplitter,
    CalibrationSplitWindow,
)
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
    SourceConfidenceTier,
)

_RTOL = 1e-6
_ATOL = 1e-6


def _compile_observations(
    rows: Sequence[tuple[str, int, float]],
    evaluation_label: CalibrationSplitLabel = CalibrationSplitLabel.HOLDOUT,
    *,
    trust_weight: float | Mapping[tuple[str, int], float] = 1.0,
    training_end_month: int = 1,
) -> CalibrationTargetBundle:
    """Compile fixed synthetic observations using the existing split contract."""
    records = [
        ObservationRecord(
            observation_id=f"training_support_{cell}_{month}",
            family=ObservationFamily.BUDGET_FLOWS,
            time_grain=TimeFrequency.MONTH,
            period_start=date(2024, month, 1),
            period_end=date(2024, month, 1),
            entity_scope=EntityScope.CELL,
            cell_id=cell,
            metric_id="government_balance",
            observed_value=value,
            unit="currency",
            coverage_estimate=1.0,
            trust_weight=(
                trust_weight[(cell, month)] if isinstance(trust_weight, Mapping) else trust_weight
            ),
            source_id="controlled_training_support",
            source_version="fixture.v1",
            regime_id="fixture",
            schema_regime_id="fixture.v1",
            identification_mode=IdentificationMode.POINT_IDENTIFIED,
            source_confidence_tier=SourceConfidenceTier.CORE,
        )
        for cell, month, value in rows
    ]
    panel = ObservationPanel(
        panel_id="controlled_training_support_panel",
        family=ObservationFamily.BUDGET_FLOWS,
        time_grain=TimeFrequency.MONTH,
        records=records,
    )
    splitter = CalibrationSplitter(
        split_plan=CalibrationSplitPlan(
            windows=[
                CalibrationSplitWindow(
                    label=CalibrationSplitLabel.TRAIN,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, training_end_month, 1),
                ),
                CalibrationSplitWindow(
                    label=evaluation_label, start_date=date(2024, training_end_month + 1, 1)
                ),
            ]
        )
    )
    return CalibrationTargetBundleCompiler(splitter=splitter).compile(panel)


def _tax_inputs(
    measured: CalibrationTargetBundle,
    *,
    initial_rate: float = 0.4,
    initial_balance: float = 9.5,
    weights: Sequence[float] | None = None,
    relative: bool = True,
    penalty: bool = False,
    multi_start: int | None = None,
    grad_norm: bool = False,
) -> CalibratorInputs:
    """Build a real one-agent tax program, active only on the first model tick."""
    dummy = ArtifactID.from_sha256_hex("0" * 64)
    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        outputs=["agents.income", "government.balance"],
    )
    graph = ProgramGraph(
        ir_ref=ArtifactRef(
            artifact_id=dummy, kind="ir.trinity_bundle", media_type="application/json"
        ),
        nodes=[node],
        edges=[],
        entrypoints=[],
    )
    plan = ExecPlan(program_ref=ProgramGraphRef(artifact_id=dummy), order=["tax"])
    base = GlobalState.empty(n_agents=1, n_firms=1)
    base = base.replace(
        agents=base.agents.replace(
            income=jnp.ones(1, dtype=jnp.float32),
            reported_income=jnp.ones(1, dtype=jnp.float32),
            active=jnp.ones(1, dtype=bool),
        ),
        government_balance=jnp.asarray(initial_balance, dtype=jnp.float32),
    )
    targets = [
        CalibrationTarget(
            target_id=target.target_id,
            model_metric_path="government_balance",
            loss=TargetLossConfig(
                kind="mse",
                relative=relative,
                epsilon=1e-8,
                weight=1.0 if weights is None else weights[index],
            ),
        )
        for index, target in enumerate(measured.targets)
    ]
    config = CalibrationConfig(
        targets=targets,
        steps=len(next(iter(measured.observed_value.values()))),
        max_steps=1,
        learning_rate=0.1,
        seed=7,
        seed_strategy="fixed",
        clip_grad_norm=None,
        hessian={"enabled": True, "damping": 0.0},
        grad_norm={"enabled": grad_norm, "lr": 0.0},
        multi_start=(
            {"n_starts": multi_start, "perturbation_scale": 1e-12}
            if multi_start is not None
            else None
        ),
        constraint_loss={"enabled": penalty, "mode": "final", "weight": 6.0},
        constraint_values={"constant_reported_income": 0.0} if penalty else {},
    )
    registry = ConstraintRegistry(
        constraints={
            "constant_reported_income": ConstraintSpec(
                constraint_id="constant_reported_income",
                slot_id="agents.reported_income",
                operator="==",
            )
        }
    )
    return CalibratorInputs(
        config=config,
        program_graph=graph,
        exec_plan=plan,
        base_state=base,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=lambda _node: {
            "params": {"rate": initial_rate},
            "schedule": {"start_step": 0, "end_step": 0},
        },
        constraint_registry=registry if penalty else None,
        measurement_bundle=measured,
        controls_seq=jnp.arange(config.steps, dtype=jnp.int32),
    )


def _record_native_objectives(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Callable]]:
    """Observe actual consumer functions while delegating every computation."""
    recorded: dict[str, list[Callable]] = {"optimizer": [], "physical": [], "gradnorm": []}
    actual_value_and_grad = jax.value_and_grad
    actual_compute_hessian = calibrator_module.compute_hessian
    actual_jit = jax.jit

    def value_and_grad(function: Callable, *args: Any, **kwargs: Any) -> Callable:
        if function.__name__ == "loss_fn":
            recorded["optimizer"].append(function)
        return actual_value_and_grad(function, *args, **kwargs)

    def compute_hessian(function: Callable, *args: Any, **kwargs: Any) -> Any:
        recorded["physical"].append(function)
        return actual_compute_hessian(function, *args, **kwargs)

    def jit(function: Callable, *args: Any, **kwargs: Any) -> Callable:
        if getattr(function, "__name__", None) == "gradnorm_update":
            recorded["gradnorm"].append(function)
        return actual_jit(function, *args, **kwargs)

    monkeypatch.setattr(calibrator_module.jax, "value_and_grad", value_and_grad)
    monkeypatch.setattr(calibrator_module, "compute_hessian", compute_hessian)
    monkeypatch.setattr(calibrator_module.jax, "jit", jit)
    return recorded


def _derivatives(function: Callable, point: jax.Array) -> tuple[jax.Array, ...]:
    """Evaluate eager and compiled derivatives of an actual consumer closure."""
    return (
        function(point),
        jax.grad(function)(point),
        jax.hessian(function)(point),
        jax.jit(function)(point),
        jax.jit(jax.grad(function))(point),
        jax.jit(jax.hessian(function))(point),
    )


@pytest.mark.parametrize(
    "evaluation_label",
    [CalibrationSplitLabel.VALIDATION, CalibrationSplitLabel.TEST, CalibrationSplitLabel.HOLDOUT],
)
def test_evaluation_values_do_not_change_native_fit_or_optimizer_step(
    monkeypatch: pytest.MonkeyPatch, evaluation_label: CalibrationSplitLabel
) -> None:
    """Even finite float32 evaluation overflow cannot enter the training graph."""
    recorded = _record_native_objectives(monkeypatch)
    physical_point = jnp.asarray([0.4], dtype=jnp.float32)
    actual_results = []
    reports = []
    for evaluation_value in (10.0, 30.0, float(np.float32(3e38))):
        measured = _compile_observations(
            [("fit", 1, 10.0), ("fit", 2, evaluation_value)], evaluation_label
        )
        target_id = measured.targets[0].target_id
        original_values = np.asarray(measured.observed_value[target_id]).copy()
        labels = measured.split_label[target_id]
        reports.append(Calibrator(_tax_inputs(measured)).run())
        report = reports[-1]
        fit = report.execution_context["measurement_fit"][target_id]
        assert fit["role"] == "train"
        assert fit["effective_support_count"] == 1
        partitions = fit["evaluation_partitions"]
        training = partitions["train"]
        assert training["rows"] == training["observed_rows"] == training["training_rows"] == 1
        assert training["contributes_to_training"] is True
        evaluation = partitions[evaluation_label.value]
        assert evaluation["rows"] == evaluation["observed_rows"] == 1
        assert evaluation["training_rows"] == 0
        assert evaluation["contributes_to_training"] is False
        assert evaluation["status"] == "available"
        # These finite float32 observations have representable float64 MSE.
        expected_metric = (
            report.series_comparison[target_id].model[-1] - float(original_values[-1])
        ) ** 2
        npt.assert_allclose(evaluation["metrics"]["mse"], expected_metric, rtol=_RTOL, atol=_ATOL)
        assert report.execution_context["fit_quality_scope"] == (
            "all_aligned_rows_descriptive_float64; training objective is per_target_loss"
        )
        assert recorded["physical"]
        actual_results.append(_derivatives(recorded["physical"][-1], physical_point))
        npt.assert_array_equal(measured.observed_value[target_id], original_values)
        assert measured.split_label[target_id] == labels == ("train", evaluation_label.value)

    # Real trace = 9.5+r on both ticks; training scale10 is frozen.
    # F(r)=(r-.5)^2/100, F'(.4)=-.002, F''(.4)=.02.
    expected = (0.0001, [-0.002], [[0.02]], 0.0001, [-0.002], [[0.02]])
    for results in actual_results:
        for actual, oracle in zip(results, expected, strict=True):
            npt.assert_allclose(actual, oracle, rtol=_RTOL, atol=_ATOL)
        for actual, baseline in zip(results, actual_results[0], strict=True):
            npt.assert_allclose(actual, baseline, rtol=_RTOL, atol=_ATOL)
    for report in reports:
        assert np.isfinite(report.total_loss)
        assert report.calibrated_params["tax.rate"] > 0.4
        npt.assert_allclose(report.loss_history, reports[0].loss_history, rtol=_RTOL, atol=_ATOL)
        npt.assert_allclose(
            report.grad_norm_history, reports[0].grad_norm_history, rtol=_RTOL, atol=_ATOL
        )
        npt.assert_allclose(
            report.calibrated_params["tax.rate"],
            reports[0].calibrated_params["tax.rate"],
            rtol=_RTOL,
            atol=_ATOL,
        )
        npt.assert_allclose(report.total_loss, reports[0].total_loss, rtol=_RTOL, atol=_ATOL)
        assert report.target_weights == reports[0].target_weights
    if evaluation_label == CalibrationSplitLabel.HOLDOUT:
        changed_training = _compile_observations([("fit", 1, 12.0), ("fit", 2, 10.0)])
        Calibrator(_tax_inputs(changed_training)).run()
        changed = _derivatives(recorded["physical"][-1], physical_point)
        expected_changed = (
            4.41 / 144,
            [-4.2 / 144],
            [[2 / 144]],
            4.41 / 144,
            [-4.2 / 144],
            [[2 / 144]],
        )
        for actual, oracle in zip(changed, expected_changed, strict=True):
            npt.assert_allclose(actual, oracle, rtol=_RTOL, atol=_ATOL)
        assert not np.isclose(
            float(changed[0]), float(actual_results[0][0]), rtol=_RTOL, atol=_ATOL
        )


@pytest.mark.parametrize(
    ("weights", "linear", "constant"),
    [([9.0, 1.0], 36.0, 96.0), ([1.0, 9.0], 164.0, 736.0)],
    ids=["prioritize_first", "prioritize_second"],
)
@pytest.mark.parametrize("multi_start", [None, 2], ids=["single", "restarts"])
def test_shared_native_consumers_match_independent_tax_quadratic(
    monkeypatch: pytest.MonkeyPatch,
    weights: list[float],
    linear: float,
    constant: float,
    multi_start: int | None,
) -> None:
    """Both Hessian routes, GradNorm inputs and report share one real objective."""
    measured = _compile_observations([("first", 1, 1.0), ("second", 1, 9.0)])
    recorded = _record_native_objectives(monkeypatch)
    report = Calibrator(
        _tax_inputs(
            measured,
            initial_rate=0.5,
            initial_balance=-0.5,
            weights=weights,
            relative=False,
            penalty=True,
            multi_start=multi_start,
            grad_norm=True,
        )
    ).run()
    assert recorded["optimizer"] and recorded["physical"] and recorded["gradnorm"]
    physical = recorded["physical"][0]
    point = jnp.asarray([0.5], dtype=jnp.float32)
    expected = (constant, [-linear], [[20.0]], constant, [-linear], [[20.0]])
    for actual, oracle in zip(_derivatives(physical, point), expected, strict=True):
        npt.assert_allclose(actual, oracle, rtol=_RTOL, atol=_ATOL)
    central = (physical(point + 0.125) - 2 * physical(point) + physical(point - 0.125)) / 0.125**2
    npt.assert_allclose(central, 20.0, rtol=1e-5, atol=1e-5)

    optimizer = recorded["optimizer"][0]
    priority = jnp.asarray(weights, dtype=jnp.float32)
    step = jnp.asarray(0, dtype=jnp.int32)

    def optimizer_scalar(value: jax.Array) -> jax.Array:
        return optimizer([value[0]], priority, step)[0]

    u = jnp.zeros(1, dtype=jnp.float32)
    optimizer_expected = (constant, [-linear / 4], [[1.25]], constant, [-linear / 4], [[1.25]])
    for actual, oracle in zip(_derivatives(optimizer_scalar, u), optimizer_expected, strict=True):
        npt.assert_allclose(actual, oracle, rtol=_RTOL, atol=_ATOL)
    total, (base, constraint, prior, auxiliary, _traces) = optimizer([u[0]], priority, step)
    npt.assert_allclose(base, [1.0, 81.0], rtol=_RTOL, atol=_ATOL)
    npt.assert_allclose([constraint, prior, auxiliary], [6.0, 0.0, 0.0], rtol=_RTOL, atol=_ATOL)
    npt.assert_allclose(total - jnp.sum(base * priority), 6.0, rtol=_RTOL, atol=_ATOL)

    def penalty(value: jax.Array) -> jax.Array:
        return optimizer([value[0]], priority, step)[1][1]

    npt.assert_allclose(jax.grad(penalty)(u), [0.0], rtol=_RTOL, atol=_ATOL)
    npt.assert_allclose(jax.hessian(penalty)(u), [[0.0]], rtol=_RTOL, atol=_ATOL)

    def components(value: jax.Array) -> jax.Array:
        return optimizer([value[0]], priority, step)[1][0]

    component_jacobian = jax.jacrev(components)(u)[:, 0]
    npt.assert_allclose(component_jacobian, [-0.5, -4.5], rtol=_RTOL, atol=_ATOL)
    gradnorm = recorded["gradnorm"][0]
    fixed_weights, component_norms = gradnorm([u[0]], priority, base, base, step)
    npt.assert_allclose(fixed_weights, priority, rtol=_RTOL, atol=_ATOL)
    npt.assert_allclose(
        component_norms, jnp.abs(priority * component_jacobian), rtol=_RTOL, atol=_ATOL
    )
    rate = report.calibrated_params["tax.rate"]
    theta = rate - 0.5
    expected_base = np.square(np.asarray([theta - 1.0, theta - 9.0]))
    npt.assert_allclose(
        report.total_loss, 10 * theta**2 - linear * theta + constant, rtol=_RTOL, atol=_ATOL
    )
    npt.assert_allclose(
        list(report.per_target_loss.values()), expected_base * weights, rtol=_RTOL, atol=_ATOL
    )
    npt.assert_allclose(
        report.total_loss - sum(report.per_target_loss.values()), 6.0, rtol=_RTOL, atol=_ATOL
    )


@pytest.mark.parametrize("zero_quality_training_target", [False, True])
def test_evaluation_only_target_has_no_native_contribution_with_supported_sibling(
    monkeypatch: pytest.MonkeyPatch,
    zero_quality_training_target: bool,
) -> None:
    """A masked extreme target contributes zero through eager and JIT autodiff."""
    excluded_month = 1 if zero_quality_training_target else 2
    measured = _compile_observations(
        [("fit", 1, 10.0), ("excluded", excluded_month, float(np.float32(3e38)))],
        trust_weight={
            ("fit", 1): 1.0,
            ("excluded", excluded_month): 0.0 if zero_quality_training_target else 1.0,
        },
    )
    recorded = _record_native_objectives(monkeypatch)
    report = Calibrator(_tax_inputs(measured)).run()
    excluded_id = next(
        target.target_id for target in measured.targets if target.target_id.endswith(".excluded")
    )
    assert report.per_target_loss[excluded_id] == 0.0
    assert np.isfinite(report.total_loss)
    fits = report.execution_context["measurement_fit"]
    assert fits[excluded_id]["role"] == "train"
    assert fits[excluded_id]["effective_support_count"] == 0
    if not zero_quality_training_target:
        placeholder = fits[excluded_id]["evaluation_partitions"]["train"]
        assert placeholder == {
            "status": "unavailable",
            "reason": "no_observed_support",
            "rows": 1,
            "observed_rows": 0,
            "training_rows": 0,
            "contributes_to_training": False,
        }
    optimizer = recorded["optimizer"][0]
    excluded_index = list(measured.target_ids()).index(excluded_id)
    priority = jnp.ones(len(measured.targets), dtype=jnp.float32)
    bijector = make_bijector(0.0, 1.0)
    point = jnp.asarray([bijector.inverse(jnp.asarray(0.4, dtype=jnp.float32))])

    def excluded(value: jax.Array) -> jax.Array:
        return optimizer([value[0]], priority, jnp.asarray(0, dtype=jnp.int32))[1][0][
            excluded_index
        ]

    for actual, oracle in zip(
        _derivatives(excluded, point), (0.0, [0.0], [[0.0]], 0.0, [0.0], [[0.0]]), strict=True
    ):
        npt.assert_allclose(actual, oracle, rtol=_RTOL, atol=_ATOL)
    # A concrete invalid rate is refused by the actual fiscal input guard
    # before producing a prediction. The distinct prediction-only guard is
    # exercised below with a valid rate and a nonfinite excluded state slot.
    with pytest.raises(ValueError, match="tax rate must be finite"):
        excluded(jnp.asarray([jnp.nan], dtype=jnp.float32))


@pytest.mark.parametrize("zero_training_quality", [False, True])
def test_corpus_without_training_support_stops_before_native_optimizer(
    monkeypatch: pytest.MonkeyPatch,
    zero_training_quality: bool,
) -> None:
    """Evaluation support alone cannot admit a successful zero-loss fit."""
    measured = _compile_observations(
        [("excluded", 1 if zero_training_quality else 2, 10.0)],
        trust_weight=0.0 if zero_training_quality else 1.0,
    )
    recorded = _record_native_objectives(monkeypatch)
    with pytest.raises(ValueError, match="no.*support"):
        Calibrator(_tax_inputs(measured)).run()
    assert recorded["optimizer"] == []


@pytest.mark.parametrize("relative_quality", [(1.0, 1.0), (0.75, 0.25)])
def test_small_positive_quality_preserves_native_fit_under_common_scaling(
    monkeypatch: pytest.MonkeyPatch,
    relative_quality: tuple[float, float],
) -> None:
    """Residual epsilon cannot erase a positive, computationally valid measure."""
    recorded = _record_native_objectives(monkeypatch)
    reports = []
    derivatives = []
    for factor in (1.0, 1e-9):
        measured = _compile_observations(
            [("fit", 1, 10.0), ("fit", 2, 12.0)],
            trust_weight={
                ("fit", 1): relative_quality[0] * factor,
                ("fit", 2): relative_quality[1] * factor,
            },
            training_end_month=2,
        )
        report = Calibrator(_tax_inputs(measured)).run()
        reports.append(report)
        target_id = measured.targets[0].target_id
        fit = report.execution_context["measurement_fit"][target_id]
        assert fit["effective_support_count"] == 2
        assert fit["role"] == "train"
        derivatives.append(
            _derivatives(recorded["physical"][-1], jnp.asarray([0.4], dtype=jnp.float32))
        )
    # The frozen scale is mean_abs([10,12])=11, independent of quality.
    fractions = np.asarray(relative_quality) / sum(relative_quality)
    residuals = np.asarray([-0.1, -2.1])
    loss = float(np.dot(fractions, residuals**2) / 121)
    gradient = float(2 * np.dot(fractions, residuals) / 121)
    expected = (loss, [gradient], [[2 / 121]], loss, [gradient], [[2 / 121]])
    for observed in derivatives:
        for actual, oracle in zip(observed, expected, strict=True):
            npt.assert_allclose(actual, oracle, rtol=_RTOL, atol=_ATOL)
    npt.assert_allclose(
        reports[1].calibrated_params["tax.rate"],
        reports[0].calibrated_params["tax.rate"],
        rtol=_RTOL,
        atol=_ATOL,
    )
    npt.assert_allclose(reports[1].loss_history, reports[0].loss_history, rtol=_RTOL, atol=_ATOL)
    npt.assert_allclose(
        reports[1].grad_norm_history, reports[0].grad_norm_history, rtol=_RTOL, atol=_ATOL
    )
    npt.assert_allclose(reports[1].total_loss, reports[0].total_loss, rtol=_RTOL, atol=_ATOL)


class _HostQualityAdapter:
    """Supply declared quality while delegating every other adaptation."""

    def __init__(self, weights: Sequence[float]) -> None:
        self.weights = np.asarray(weights, dtype=np.float64)

    def adapt(self, **kwargs):
        adapted = DefaultMeasurementAwareLossAdapter().adapt(**kwargs)
        return {**adapted, "sample_quality_weight": self.weights}


@pytest.mark.parametrize("malformed", ["quality_shape", "split_length"])
def test_quality_and_split_shapes_refuse_before_native_optimizer(monkeypatch, malformed) -> None:
    """Neither a quality column nor a truncated split can broadcast into a fit."""
    from dataclasses import replace

    measured = _compile_observations([("fit", 1, 10.0), ("fit", 2, 11.0)], training_end_month=2)
    inputs = _tax_inputs(measured)
    if malformed == "quality_shape":
        inputs = replace(inputs, measurement_loss_adapter=_HostQualityAdapter(np.ones((2, 1))))
        reason = "Measurement quality weights must match target shape"
    else:
        target_id = measured.targets[0].target_id
        malformed_bundle = replace(measured, split_label={target_id: ("train",)})
        inputs = replace(inputs, measurement_bundle=malformed_bundle)
        reason = "Training split.*does not match target shape"
    recorded = _record_native_objectives(monkeypatch)
    with pytest.raises(ValueError, match=reason):
        Calibrator(inputs).run()
    assert not recorded["optimizer"]


def test_host_quality_common_scale_is_normalized_before_backend_conversion() -> None:
    """A tiny positive host measure preserves its represented ratios and fit."""
    from dataclasses import replace

    measured = _compile_observations([("fit", 1, 10.0), ("fit", 2, 11.0)], training_end_month=2)
    reports = [
        Calibrator(
            replace(
                _tax_inputs(measured),
                measurement_loss_adapter=_HostQualityAdapter([magnitude, magnitude]),
            )
        ).run()
        for magnitude in (1.0, 1e-300)
    ]
    npt.assert_allclose(reports[0].total_loss, reports[1].total_loss, rtol=_RTOL, atol=_ATOL)
    npt.assert_allclose(
        reports[0].calibrated_params["tax.rate"],
        reports[1].calibrated_params["tax.rate"],
        rtol=_RTOL,
        atol=_ATOL,
    )
    assert (
        reports[1].execution_context["measurement_fit"][measured.targets[0].target_id][
            "effective_support_count"
        ]
        == 2
    )


def test_unrepresentable_relative_quality_refuses_before_optimizer(monkeypatch) -> None:
    """A lost relative row cannot masquerade as fully represented fit support."""
    from dataclasses import replace

    measured = _compile_observations([("fit", 1, 10.0), ("fit", 2, 11.0)], training_end_month=2)
    recorded = _record_native_objectives(monkeypatch)
    inputs = replace(
        _tax_inputs(measured),
        measurement_loss_adapter=_HostQualityAdapter([1.0, 1e-300]),
    )
    with pytest.raises(
        ValueError, match="measurement_fit_relative_weight_below_float32_resolution"
    ):
        Calibrator(inputs).run()
    assert not recorded["optimizer"]


def test_removing_prearithmetic_support_exposes_real_evaluation_overflow(monkeypatch) -> None:
    """The real forward fails when only its computational support repair is removed."""
    measured = _compile_observations([("fit", 1, 10.0), ("fit", 2, float(np.float32(3e38)))])
    inputs = _tax_inputs(measured)
    baseline = Calibrator(inputs).run()
    assert np.isfinite(baseline.total_loss)
    actual_pointwise = calibrator_module.pointwise_base_loss

    def without_prearithmetic_support(predicted, observed, config, scale, **kwargs):
        assert "support_mask" in kwargs
        # Keep the same source observations, weights, actual scan/backend,
        # finite-result selector and assertions; remove only the repaired
        # computational view before residual/nonlinear arithmetic.
        return actual_pointwise(predicted, observed, config, scale)

    with monkeypatch.context() as removed:
        removed.setattr(calibrator_module, "pointwise_base_loss", without_prearithmetic_support)
        with pytest.raises(ValueError, match="No run has a finite loss"):
            Calibrator(inputs).run()
    restored = Calibrator(inputs).run()
    npt.assert_allclose(restored.total_loss, baseline.total_loss, rtol=_RTOL, atol=_ATOL)
    assert restored.calibrated_params == baseline.calibrated_params


def test_excluded_nonfinite_prediction_is_not_hidden_by_supported_sibling(monkeypatch) -> None:
    """A valid rate cannot hide an invalid model slot behind zero fit support."""
    from dataclasses import replace

    measured = _compile_observations([("fit", 1, 10.0), ("excluded", 2, 30.0)])
    inputs = _tax_inputs(measured)
    targets = [
        target.model_copy(update={"model_metric_path": "agents.income", "aggregation": "mean"})
        if target.target_id.endswith(".fit")
        else target
        for target in inputs.config.targets
    ]
    inputs = replace(
        inputs,
        config=inputs.config.model_copy(update={"targets": targets}),
        base_state=inputs.base_state.replace(
            government_balance=jnp.asarray(jnp.nan, dtype=jnp.float32)
        ),
    )
    with pytest.raises(ValueError, match="No run has a finite loss"):
        Calibrator(inputs).run()
    actual_pointwise = calibrator_module.pointwise_base_loss

    def remove_original_prediction_guard(predicted, observed, config, scale, **kwargs):
        support = kwargs["support_mask"]
        return actual_pointwise(
            jnp.where(support, predicted, jnp.zeros_like(predicted)),
            observed,
            config,
            scale,
            **kwargs,
        )

    with monkeypatch.context() as removed:
        removed.setattr(calibrator_module, "pointwise_base_loss", remove_original_prediction_guard)
        invalid = Calibrator(inputs).run()
    assert np.isfinite(invalid.total_loss)
    excluded_id = next(
        target.target_id for target in targets if target.target_id.endswith(".excluded")
    )
    assert all(np.isnan(value) for value in invalid.series_comparison[excluded_id].model)
    with pytest.raises(ValueError, match="No run has a finite loss"):
        Calibrator(inputs).run()
