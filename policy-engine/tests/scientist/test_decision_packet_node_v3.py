from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_METRICS_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)


def test_build_decision_packet_node_emits_v3_payload_and_manifest_inputs(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_v3")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"applied_nodes": 1, "status": "ok"}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    governance_ref = store.put_json(
        GovernanceReport(verdict="approve", issues=[]),
        PutOptions(kind="scientist.governance_report", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_v3",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={ARTIFACT_METRICS_REF: metrics_ref},
        reports_index={REPORT_GOVERNANCE_REPORT_REF: governance_ref},
        params={"random_seed": 123},
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    manifest = store.get_manifest(packet_ref.artifact_id)
    roles = {item.role for item in manifest.inputs}

    assert payload["schema_version"] == "3.1"
    assert payload["seed"] == 123
    assert payload["replay"]["strategy_hint"] == "scientist"
    assert payload["uncertainty"]["envelope_count"] == 0
    assert payload["inputs"]["trinity_bundle_ref"] == str(trinity_ref.artifact_id)
    assert payload["artifacts"]["metrics_ref"] == str(metrics_ref.artifact_id)
    assert payload["artifacts"]["governance_report_ref"] == str(governance_ref.artifact_id)
    assert "input.trinity_bundle_ref" in roles
    assert "input.registry_bundle_ref" in roles
    assert "input.data_snapshot_ref" in roles
    assert "artifact.metrics_ref" in roles
    assert "artifact.governance_report_ref" in roles


def test_build_decision_packet_node_accepts_float_uncertainty_bounds(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_unc")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet"))

    trinity_ref = store.put_json(
        {"trinity": {}},
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
        ),
    )
    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(state_snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"applied_nodes": 1, "step_latency_ms": 12}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
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
    env_ref = persist_uncertainty_envelope(
        store,
        UncertaintyEnvelope(
            point_estimate=12.0,
            confidence_interval=(10.0, 15.0),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.DELTA_METHOD,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
            uncertainty_envelopes={"step_latency_ms": env_ref},
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_packet_unc",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_METRICS_REF: metrics_ref,
            ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    bounds = payload["uncertainty_bounds"]

    assert isinstance(bounds, dict)
    assert bounds["step_latency_ms_lower"] == 10.0
    assert bounds["step_latency_ms_upper"] == 15.0
