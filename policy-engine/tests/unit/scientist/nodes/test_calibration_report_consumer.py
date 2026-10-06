"""Canonical report reader requirement at the existing legacy consumer."""

import json
import logging
import runpy
from types import SimpleNamespace

import pytest

from polisyos.core.artifacts import FileSystemCAS, InputRef, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.calibration.report import (
    CalibrationReport,
    put_calibration_config,
    put_calibration_report,
)
from polisyos.ir.analytics.calibration import CalibrationConfig
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
    _collect_input_envelopes,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_CALIBRATION_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _fixture(tmp_path):
    store = FileSystemCAS(tmp_path)
    config = put_calibration_config(store, CalibrationConfig())
    env = UncertaintyEnvelope(
        point_estimate=0.2,
        confidence_interval=(0.1, 0.3),
        confidence_level=None,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL, parameters={"mean": 0.2, "std": 0.05}
        ),
    )
    report = CalibrationReport(
        total_loss=0, calibrated_params={"A.rate": 0.2}, uncertainty_envelopes={"A.rate": env}
    )
    inputs = [InputRef(artifact_id=config.artifact_id, role="calibration_config")]
    valid = put_calibration_report(store, report, inputs=inputs)
    return store, report, inputs, valid


def test_actual_legacy_consumer_accepts_valid_canonical_report(tmp_path):
    store, report, inputs, valid = _fixture(tmp_path)
    assert set(
        _collect_input_envelopes(
            SimpleNamespace(store=store),
            SimpleNamespace(inputs={INPUT_CALIBRATION_REPORT_REF: valid}),
        )
    ) == {"A.rate"}


def _node_fixture(store, report_ref, sensitivity):
    registry = build_default_registry_bundle(store).bundle_ref
    ctx = ExecutionContext(
        store=store,
        run=RunContext.start(store=store, registry_bundle=registry, run_id="B197_legacy"),
        logger=logging.getLogger("b197.legacy"),
    )
    metrics = store.put_json(
        Metrics(values={"y": 0.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    plan = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(metrics.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    sim = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="B197_legacy",
        inputs={INPUT_CALIBRATION_REPORT_REF: report_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim},
        params={
            "propagation_config": {
                "preferred_method": "monte_carlo",
                "mc_n_samples": 100,
                "mc_min_valid_samples": 50,
                "compute_sensitivity": False,
            },
            "propagation_sensitivity": {"y": sensitivity},
        },
    )
    return ctx, state


@pytest.mark.parametrize(
    "kind,schema,version",
    [
        ("foundry.funnel_calibration_report", "polisyos.foundry.CalibrationReport", "2.0"),
        ("foundry.calibration_report", "polisyos.foundry.FunnelCalibrationReport", "2.0"),
        ("foundry.calibration_report", "polisyos.foundry.CalibrationReport", "1.0"),
    ],
)
def test_legacy_node_refuses_same_bytes_wrong_cas_profile_before_dispatch(
    tmp_path, monkeypatch, kind, schema, version
):
    from polisyos.foundry.uncertainty import PropagationDispatcher

    store, report, inputs, valid = _fixture(tmp_path)
    forged = store.put_json(
        report,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema, version=version),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    assert forged.artifact_id == valid.artifact_id
    fresh = FileSystemCAS(tmp_path)
    ctx, state = _node_fixture(fresh, forged, {"A.rate": 1.0})
    calls = 0
    propagation_calls = 0
    from polisyos.scientist.nodes.builtins.simulate import propagate_uncertainty as node

    original_build = node._build_propagation_fn
    original_propagate = PropagationDispatcher.propagate

    def counted_build(*args, **kwargs):
        fn, mapped = original_build(*args, **kwargs)

        def counted(**params):
            nonlocal calls
            calls += 1
            return fn(**params)

        counted._sensitivity_map = fn._sensitivity_map
        return counted, mapped

    def counted_propagate(*args, **kwargs):
        nonlocal propagation_calls
        propagation_calls += 1
        return original_propagate(*args, **kwargs)

    monkeypatch.setattr(node, "_build_propagation_fn", counted_build)
    monkeypatch.setattr(PropagationDispatcher, "propagate", counted_propagate)
    error = None
    try:
        PropagateUncertaintyNode().execute(ctx, state)
    except ValueError as exc:
        error = str(exc)
    print(
        json.dumps(
            {
                "callback_count": calls,
                "propagation_entry_count": propagation_calls,
                "refusal": error,
                "kind": kind,
                "schema": schema,
                "version": version,
            }
        )
    )
    assert calls == propagation_calls == 0
    assert error is not None


def test_actual_tied_calibrator_v2_reaches_fresh_legacy_node(tmp_path):
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.ir.analytics.uncertainty import PosteriorSamplesCarrier

    helper = runpy.run_path(
        "tests/unit/scientist/nodes/builtins/simulate/test_propagate_welfare.py"
    )
    store = FileSystemCAS(tmp_path)
    report_ref, report = helper["_run_b197_tied_calibrator"](store)
    assert report.schema_version == "2.0"
    fresh = FileSystemCAS(tmp_path)
    ctx, state = _node_fixture(fresh, report_ref, {"A.rate": 1.0, "B.rate": -1.0})
    outcome = PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"
    sim = SimulationResult.model_validate(
        from_canonical_bytes(
            fresh.get_bytes(
                outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF].artifact_id
            )
        )
    )
    envelope = load_uncertainty_envelope(fresh, sim.uncertainty_envelopes["y"])
    assert envelope.gate_eligible is False
    assert isinstance(envelope.distribution_payload, PosteriorSamplesCarrier)
    samples = envelope.distribution_payload.samples
    assert len(samples) == 100
    assert max(abs(value) for value in samples) < 1e-12
    receipt = from_canonical_bytes(
        fresh.get_bytes(outcome.state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF].artifact_id)
    )
    assert receipt["mapped_params"] == ["A.rate", "B.rate"]


def test_invalid_explicit_report_cannot_hide_behind_valid_snapshot(tmp_path, monkeypatch):
    from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
    from polisyos.foundry.uncertainty import PropagationDispatcher
    from polisyos.ir.analytics.uncertainty import persist_uncertainty_envelope
    from polisyos.scientist.nodes.builtins.state_keys import INPUT_DATA_SNAPSHOT_REF

    store, report, inputs, valid = _fixture(tmp_path)
    forged = store.put_json(
        report,
        PutOptions(
            kind="foundry.funnel_calibration_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.CalibrationReport", version="2.0"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
    )
    env_ref = persist_uncertainty_envelope(store, report.uncertainty_envelopes["A.rate"])
    data = store.put_json(
        {"value": 1.0},
        PutOptions(kind="test.observed", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    snapshot = store.put_json(
        DataSnapshot(data_ref=data, uncertainty_envelope_ref=env_ref),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    fresh = FileSystemCAS(tmp_path)
    ctx, state = _node_fixture(fresh, forged, {"A.rate": 1.0})
    state.inputs[INPUT_DATA_SNAPSHOT_REF] = DataSnapshotRef(artifact_id=snapshot.artifact_id)
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("invalid explicit calibration input must precede propagation")

    monkeypatch.setattr(PropagationDispatcher, "propagate", counted)
    with pytest.raises(ValueError, match="kind/schema"):
        PropagateUncertaintyNode().execute(ctx, state)
    assert calls == 0
