"""Exercise configured cross-sectional calibration through report CAS readback."""

from dataclasses import replace

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
