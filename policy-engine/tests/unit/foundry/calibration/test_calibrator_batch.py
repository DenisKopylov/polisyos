"""Exercise configured cross-sectional calibration through report CAS readback."""

from dataclasses import replace
from datetime import date

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, ProgramGraphRef, ProgramNode
from polisyos.foundry.calibration import pure_executor
from polisyos.foundry.calibration.calibrator import (
    CalibrationBatchInputs,
    Calibrator,
    CalibratorInputs,
)
from polisyos.foundry.calibration.measurement import (
    CalibrationTargetBundleCompiler,
    MeasurementAwareLossConfig,
)
from polisyos.foundry.calibration.report import (
    load_calibration_report,
    put_calibration_config,
    put_calibration_report,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.analytics.calibration import CalibrationConfig, CalibrationTarget
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.ir.observation.contracts import (
    EntityScope,
    IdentificationMode,
    ObservationFamily,
    ObservationPanel,
    ObservationRecord,
)


def _inputs(*, gaussian=False):
    states = []
    for income, clock in ((100.0, 17), (200.0, 29)):
        state = GlobalState.empty(n_agents=1, n_firms=1)
        states.append(
            state.replace(
                agents=state.agents.replace(
                    income=jnp.array([income], dtype=jnp.float32),
                    reported_income=jnp.array([income], dtype=jnp.float32),
                ),
                government_balance=jnp.array(0.0, dtype=jnp.float32),
                step=jnp.array(clock, dtype=jnp.int32),
            )
        )
    artifact = ArtifactID.from_sha256_hex("0" * 64)
    node = ProgramNode(
        node_id="tax",
        node_kind="mechanism",
        mechanism_type="income_tax",
        outputs=["agents.income", "government.balance"],
    )
    graph = ProgramGraph(
        ir_ref=ArtifactRef(
            artifact_id=artifact, kind="ir.trinity_bundle", media_type="application/json"
        ),
        nodes=[node],
        edges=[],
        entrypoints=[],
    )
    plan = ExecPlan(program_ref=ProgramGraphRef(artifact_id=artifact), order=["tax"])
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="balance",
                model_metric_path="government_balance",
                loss={"relative": False},
            )
        ],
        seed=19,
        max_steps=1,
        learning_rate=1e-9,
    )
    return CalibratorInputs(
        config=config,
        program_graph=graph,
        exec_plan=plan,
        base_state=states[0],
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=lambda _: {
            "params": {"rate": 0.25},
            "schedule": {"start_step": 1, "end_step": 1},
        },
        raw_targets={"balance": (0.0, 50.0)},
        gaussian_observation_std={"balance": 10.0} if gaussian else None,
        batch_inputs=CalibrationBatchInputs(
            states=tuple(states), times=(0, 1), row_ids=("inactive", "active")
        ),
    )


def _assert_batch_report(report):
    comparison = report.series_comparison["balance"]
    assert comparison.model == pytest.approx([0.0, 50.0], abs=1e-5)
    assert comparison.real == [0.0, 50.0]
    assert comparison.time == [0.0, 1.0]
    assert report.total_loss == pytest.approx(0.0, abs=1e-9)
    context = report.execution_context["batch_rows"]
    assert context["row_ids"] == ["inactive", "active"]
    assert context["schedule_times"] == [0, 1]
    assert context["state_steps"] == [17, 29]
    expected_keys = [
        np.asarray(jax.random.fold_in(jax.random.PRNGKey(19), i)).tolist() for i in range(2)
    ]
    assert context["row_keys"] == expected_keys
    assert expected_keys[0] != expected_keys[1]
    assert context["population_law_basis"] == "not_established"


@pytest.mark.parametrize("gaussian", [False, True])
def test_configured_calibrator_batch_objective_hessian_and_persisted_rows(tmp_path, gaussian):
    inputs = _inputs(gaussian=gaussian)
    report = Calibrator(inputs).run()
    _assert_batch_report(report)
    curvature = report.execution_context["curvature_diagnostic"]
    assert curvature["raw_eigenvalues"] == pytest.approx([400.0 if gaussian else 40000.0])
    if gaussian:
        assert report.uncertainties.covariance == [[pytest.approx(0.0025)]]
        assert report.execution_context["objective_profile"]["gate_eligible"] is False
    else:
        assert report.uncertainties is None
        assert curvature["covariance_unavailable_reason"] == "generic_objective_curvature_only"
    store = FileSystemCAS(tmp_path)
    config_ref = put_calibration_config(store, inputs.config)
    ref = put_calibration_report(
        store,
        report,
        inputs=[InputRef(artifact_id=config_ref.artifact_id, role="calibration_config")],
    )
    loaded = load_calibration_report(store, ref)
    _assert_batch_report(loaded)
    assert loaded == report


def test_batch_present_but_scan_proxy_fails_same_row_oracle(monkeypatch):
    # Preserve the callable and report metadata while removing row state/time execution.
    def fake_batch(state, *, times, keys, bundle, metric_paths):
        return pure_executor.run_pure_scan(
            jax.tree_util.tree_map(lambda value: value[0], state),
            steps=len(times),
            root_key=keys[0],
            bundle=bundle,
            metric_paths=metric_paths,
        )

    _assert_batch_report(Calibrator(_inputs()).run())
    monkeypatch.setattr(pure_executor, "run_pure_batch", fake_batch)
    with pytest.raises(AssertionError):
        _assert_batch_report(Calibrator(_inputs()).run())


@pytest.mark.parametrize(
    "invalid", ["controls", "time_axis", "target_length", "target_ids", "step_seed"]
)
def test_batch_unsupported_or_mismatched_inputs_fail_before_producer_callback(invalid):
    inputs = _inputs()
    calls = []
    inputs.parameter_loader = lambda _: calls.append("loaded")
    if invalid == "controls":
        inputs.controls_seq = jnp.arange(2)
    elif invalid == "time_axis":
        inputs.config = inputs.config.model_copy(update={"time_axis": [0.0, 1.0]})
    elif invalid == "target_length":
        inputs.raw_targets = {"balance": [0.0]}
    elif invalid == "target_ids":
        inputs.raw_targets = {"other": [0.0, 50.0]}
    else:
        inputs.config = inputs.config.model_copy(update={"seed_strategy": "step"})
    with pytest.raises(ValueError, match="Cross-sectional|batch"):
        Calibrator(inputs).run()
    assert calls == []


@pytest.mark.parametrize(
    "times,row_ids",
    [((0,), ("a", "b")), ((0, -1), ("a", "b")), ((0, 1), ("a", "a")), ((0, True), ("a", "b"))],
)
def test_batch_row_identity_and_time_axes_are_strict(times, row_ids):
    with pytest.raises(ValueError, match="batch"):
        replace(_inputs().batch_inputs, times=times, row_ids=row_ids)


def test_batch_objective_identity_binds_ordered_state_time_and_keys():
    inputs = _inputs()
    first = Calibrator(inputs).run()
    repeated = Calibrator(inputs).run()
    assert (
        first.execution_context["objective_identity"]
        == repeated.execution_context["objective_identity"]
    )
    states = tuple(reversed(inputs.batch_inputs.states))
    inputs.batch_inputs = replace(inputs.batch_inputs, states=states)
    second = Calibrator(inputs).run()
    assert (
        first.execution_context["objective_identity"]
        != second.execution_context["objective_identity"]
    )


def test_objective_identity_binds_loader_resolved_schedule():
    inputs = _inputs()
    first = Calibrator(inputs).run()
    inputs.parameter_loader = lambda _: {
        "params": {"rate": 0.25},
        "schedule": {"start_step": 1, "end_step": 2},
    }
    second = Calibrator(inputs).run()
    _assert_batch_report(first)
    _assert_batch_report(second)
    assert (
        first.execution_context["objective_identity"]
        != second.execution_context["objective_identity"]
    )


def _measurement_inputs():
    inputs = _inputs()
    panel = ObservationPanel(
        panel_id="synthetic_objective_binding_fixture",
        family=ObservationFamily.LABOR_MARKET,
        time_grain=TimeFrequency.MONTH,
        records=[
            ObservationRecord(
                observation_id=f"synthetic_row_{index}",
                family=ObservationFamily.LABOR_MARKET,
                time_grain=TimeFrequency.MONTH,
                period_start=date(2024, index + 1, 1),
                period_end=date(2024, index + 1, [31, 29][index]),
                entity_scope=EntityScope.CELL,
                cell_id="fixture_cell",
                metric_id="balance",
                observed_value=value,
                unit="currency",
                coverage_estimate=1.0,
                trust_weight=trust,
                source_id="synthetic_fixture",
                source_version="fixture.v1",
                regime_id="fixture_regime",
                schema_regime_id="fixture_schema.v1",
                identification_mode=IdentificationMode.PROXY_IDENTIFIED,
                proxy_source_id="synthetic_fixture",
            )
            for index, (value, trust) in enumerate(((0.0, 1.0), (50.0, 0.1)))
        ],
    )
    bundle = CalibrationTargetBundleCompiler().compile(panel)
    target_id = bundle.targets[0].target_id
    # Admit exact mathematical weights for this synthetic oracle; this override
    # is not evidence for the source's trust tier or producer provenance.
    bundle = replace(bundle, trust_weight={target_id: jnp.array([1.0, 0.1])})
    inputs.batch_inputs = None
    inputs.raw_targets = None
    inputs.measurement_bundle = bundle
    inputs.config = inputs.config.model_copy(
        update={"targets": [inputs.config.targets[0].model_copy(update={"target_id": target_id})]}
    )
    inputs.parameter_loader = lambda _: {
        "params": {"rate": 0.25},
        "schedule": {"start_step": 0, "end_step": 10},
    }
    return inputs, target_id


def test_native_measurement_quality_changes_identity_and_matches_weighted_hessian():
    inputs, target_id = _measurement_inputs()
    first = Calibrator(inputs).run()
    inputs.measurement_bundle = replace(
        inputs.measurement_bundle, trust_weight={target_id: jnp.array([0.1, 1.0])}
    )
    second = Calibrator(inputs).run()
    for report, weights in ((first, [1.0, 0.1]), (second, [0.1, 1.0])):
        expected_loss = weights[0] * 625.0 / sum(weights)
        expected_hessian = 2 * (weights[0] * 100**2 + weights[1] * 200**2) / sum(weights)
        assert report.total_loss == pytest.approx(expected_loss, rel=1e-6)
        assert report.execution_context["curvature_diagnostic"]["raw_eigenvalues"] == pytest.approx(
            [expected_hessian], rel=1e-6
        )
        assert report.execution_context["objective_identity_status"] == "content_bound"
    assert (
        first.execution_context["objective_identity"]
        != second.execution_context["objective_identity"]
    )
    # The old config/observed/model proxy is unchanged across this true objective delta.
    assert first.calibrated_params == pytest.approx(second.calibrated_params)
    assert first.series_comparison == second.series_comparison


def test_native_measurement_policy_is_part_of_effective_objective_identity():
    inputs, target_id = _measurement_inputs()
    inputs.measurement_bundle = replace(
        inputs.measurement_bundle, censoring_mask={target_id: jnp.array([True, False])}
    )
    first = Calibrator(inputs).run()
    inputs.measurement_loss_config = MeasurementAwareLossConfig(censoring_discount=0.1)
    second = Calibrator(inputs).run()
    assert first.total_loss != pytest.approx(second.total_loss)
    assert (
        first.execution_context["objective_identity"]
        != second.execution_context["objective_identity"]
    )


def test_custom_measurement_adapter_freezes_outputs_and_does_not_claim_functional_identity():
    inputs, _ = _measurement_inputs()
    calls = []

    class CustomAdapter:
        def adapt(self, **_):
            calls.append("adapted")
            return {"effective_weight": jnp.array([1.0, 0.1])}

    inputs.measurement_loss_adapter = CustomAdapter()
    report = Calibrator(inputs).run()
    assert calls == ["adapted"]
    assert report.execution_context["objective_identity_status"] == "not_established"
    assert "Hessian reused from selected start" not in report.diagnostics
