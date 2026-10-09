from __future__ import annotations

import logging

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty import (
    PropagateUncertaintyNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState


class _RecordingFileSystemCAS(FileSystemCAS):
    def __init__(self, root) -> None:
        super().__init__(root)
        self.read_selectors: list[ArtifactID | ArtifactRef | str] = []

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        self.read_selectors.append(artifact_id)
        return super().get_bytes(artifact_id)


def test_propagate_uncertainty_node_updates_simulation_result(tmp_path) -> None:
    store = _RecordingFileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_prop")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.propagate"))

    env_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store),
        UncertaintyEnvelope(
            point_estimate=1.0,
            confidence_interval=(0.8, 1.2),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.TRUST,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )

    state_snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(
            data_ref=state_snapshot_ref,
            uncertainty_envelope_ref=env_ref,
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
        Metrics(values={"applied_nodes": 1, "step_latency_ms": 12}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
    )
    simulation_result = SimulationResult(
        exec_plan_ref=ExecPlanRef.model_validate(exec_plan_ref.model_dump(mode="python")),
        metrics_ref=MetricsRef.model_validate(metrics_ref.model_dump(mode="python")),
    )
    simulation_result_options = PutOptions(
        kind="foundry.simulation_result",
        media_type="application/json",
    )
    default_view = store.put_json(
        simulation_result,
        simulation_result_options,
        canon_spec=CanonSpec(forbid_floats=False, max_depth=128),
    )
    selected_view = store.put_json(
        simulation_result,
        simulation_result_options,
        canon_spec=CanonSpec(forbid_floats=False, max_depth=64),
    )
    assert default_view.artifact_id == selected_view.artifact_id
    assert default_view.manifest_profile_sha256 != selected_view.manifest_profile_sha256
    sim_result_ref = selected_view

    state = ExperimentState(
        run_id="R_prop",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id),
        },
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref,
        },
        params={
            "propagation_mc_n_samples": 100,
            "propagation_mc_batch_size": 100,
            "propagation_sensitivity": {
                "applied_nodes": {"data_snapshot": 1.0},
                "step_latency_ms": {"data_snapshot": 1.0},
            },
        },
    )

    outcome = PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert any(
        getattr(selector, "manifest_profile_sha256", None) == sim_result_ref.manifest_profile_sha256
        for selector in store.read_selectors
    )

    updated_sim_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    payload = from_canonical_bytes(store.get_bytes(updated_sim_ref.artifact_id))
    updated_sim = SimulationResult.model_validate(payload)

    assert updated_sim.uncertainty_envelopes is not None
    assert set(updated_sim.uncertainty_envelopes.keys()) == {"applied_nodes", "step_latency_ms"}
    assert ARTIFACT_PROPAGATION_REPORT_REF in outcome.state.artifacts_index

    report_ref = outcome.state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF]
    report = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert report["methods"] == [PropagationMethod.DELTA_METHOD.value] * 2

    updated_manifest = store.get_manifest(updated_sim_ref)
    input_profiles = {item.role: item.manifest_profile_sha256 for item in updated_manifest.inputs}
    assert input_profiles["base_simulation_result"] == sim_result_ref.manifest_profile_sha256
    assert (
        input_profiles["propagation_report"]
        == updated_sim.propagation_report_ref.manifest_profile_sha256
    )
    assert (
        input_profiles["propagation_config"]
        == updated_sim.propagation_config_ref.manifest_profile_sha256
    )
    for metric_id, envelope_ref in updated_sim.uncertainty_envelopes.items():
        assert (
            input_profiles[f"metric_envelope.{metric_id}"] == envelope_ref.manifest_profile_sha256
        )
