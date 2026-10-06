"""UQP-01 witnesses for typed uncertainty failures and report persistence."""

from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState

pytestmark = pytest.mark.unit


def _normal_env(point: float, std: float) -> UncertaintyEnvelope:
    """Build a small Gaussian input envelope for propagation witnesses."""
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(point - 1.96 * std, point + 1.96 * std),
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        gate_eligible=True,
    )


def test_mc_missing_output_is_unknown_while_true_zero_remains_valid() -> None:
    """A missing MC metric cannot become an authoritative zero by fallback."""
    config = PropagationConfig(
        mc_n_samples=100,
        mc_batch_size=100,
        mc_min_valid_samples=50,
        mc_seed=17,
    )
    inputs = {"x": _normal_env(0.0, 1.0)}
    propagator = MonteCarloPropagator(config)

    missing = propagator.propagate(
        lambda **params: {"other": params["x"]},
        {"x": 0.0},
        inputs,
        ["missing"],
    )[0].envelope
    genuine_zero = propagator.propagate(
        lambda **params: {"zero": 0.0},
        {"x": 0.0},
        inputs,
        ["zero"],
    )[0].envelope

    assert missing.point_estimate == 0.0
    assert missing.distribution_family is DistributionFamily.UNKNOWN
    assert missing.confidence_level is None
    assert missing.confidence_interval != (0.0, 0.0)
    assert missing.gate_eligible is False
    assert missing.metadata["failure"] == "missing_output"
    assert missing.metadata["missing_output_count"] == 100

    assert genuine_zero.point_estimate == pytest.approx(0.0)
    assert genuine_zero.confidence_interval == (0.0, 0.0)
    assert genuine_zero.distribution_family is DistributionFamily.BOOTSTRAP
    assert genuine_zero.sample_size == 100
    assert genuine_zero.gate_eligible is False


def test_partial_node_persists_limitation_and_disables_gate(tmp_path) -> None:
    """The node consumer persists unresolved mapping and its non-authoritative gate."""
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_uqp01")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.uqp01"))

    input_envelope_ref = persist_uncertainty_envelope(
        store,
        _normal_env(1.0, 0.1),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=state_snapshot_ref,
            uncertainty_envelope_ref=input_envelope_ref,
        ),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"mapped": 1, "unmapped": 2}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    simulation_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    state = ExperimentState(
        run_id="R_uqp01",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(
                artifact_id=data_snapshot_ref.artifact_id,
            ),
        },
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: simulation_result_ref},
        params={
            "propagation_sensitivity": {"mapped": {"data_snapshot": 1.0}},
        },
    )

    outcome = PropagateUncertaintyNode().execute(ctx, state)

    assert outcome.status == "ok"
    report_ref = outcome.state.artifacts_index["propagation_report_ref"]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report["mapping_status"] == "partial"
    assert report["unmapped_metric_ids"] == ["unmapped"]
    assert report["diagnostics"][-1]["metric_id"] == "unmapped"
    assert report["diagnostics"][-1]["diagnostics"]["sensitivity_mapping"] == "unresolved"

    updated_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    updated_payload = from_canonical_bytes(store.get_bytes(updated_ref.artifact_id))
    updated_simulation = SimulationResult.model_validate(updated_payload)
    unresolved_ref = updated_simulation.uncertainty_envelopes["unmapped"]
    unresolved = load_uncertainty_envelope(store, unresolved_ref)
    assert unresolved.metadata["sensitivity_mapping"] == "unresolved"
    assert unresolved.gate_eligible is False
