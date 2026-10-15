from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    FoundryExecutionInputBasisRef,
    Metrics,
    MetricsRef,
    SimulationResult,
)
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
        self.simulation_result_profile_writes: list[bool] = []

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        self.read_selectors.append(artifact_id)
        return super().get_bytes(artifact_id)

    def put_json(
        self,
        obj: object,
        opts: PutOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        if opts.kind == SimulationResult.ARTIFACT_KIND:
            self.simulation_result_profile_writes.append(return_selected_profile)
        return super().put_json(
            obj,
            opts,
            canon_spec,
            return_selected_profile=return_selected_profile,
        )


@pytest.mark.parametrize("schema_version", ["1.3", "1.4"])
def test_propagate_uncertainty_node_updates_simulation_result(tmp_path, schema_version) -> None:
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
    basis_ref = None
    execution_source_status = "not_recorded"
    if schema_version == SimulationResult.ARTIFACT_SCHEMA_VERSION:
        basis_payload_ref = store.put_json(
            {"schema_version": "1.0", "authority_purpose": "execution_input_identity_only"},
            PutOptions(
                kind="foundry.execution_input_basis",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.core.FoundryExecutionInputBasis",
                    version="1.0",
                ),
            ),
            return_selected_profile=True,
        )
        basis_ref = FoundryExecutionInputBasisRef.model_validate(
            basis_payload_ref.model_dump(mode="python")
        )
        execution_source_status = "single_step_basis"
    simulation_result = SimulationResult(
        schema_version=schema_version,
        exec_plan_ref=ExecPlanRef.model_validate(exec_plan_ref.model_dump(mode="python")),
        metrics_ref=MetricsRef.model_validate(metrics_ref.model_dump(mode="python")),
        execution_input_basis_ref=basis_ref,
        execution_source_status=execution_source_status,
    )
    simulation_result_options = PutOptions(
        kind="foundry.simulation_result",
        media_type="application/json",
        schema=SchemaInfo(
            name=SimulationResult.ARTIFACT_SCHEMA_NAME,
            version=simulation_result.schema_version,
        ),
    )
    default_view = store.put_json(
        simulation_result.to_artifact_payload(),
        simulation_result_options,
        canon_spec=CanonSpec(forbid_floats=False, max_depth=128),
    )
    selected_view = store.put_json(
        simulation_result.to_artifact_payload(),
        simulation_result_options,
        canon_spec=CanonSpec(forbid_floats=False, max_depth=64),
        return_selected_profile=True,
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

    wrong_profile_ref = sim_result_ref.model_copy(
        update={"manifest_profile_sha256": f"sha256:{'f' * 64}"}
    )
    wrong_profile_state = state.model_copy(
        update={
            "artifacts_index": state.artifacts_index
            | {ARTIFACT_SIMULATION_RESULT_REF: wrong_profile_ref}
        }
    )
    with pytest.raises(FileNotFoundError):
        PropagateUncertaintyNode().execute(ctx, wrong_profile_state)

    outcome = PropagateUncertaintyNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert any(
        getattr(selector, "manifest_profile_sha256", None) == sim_result_ref.manifest_profile_sha256
        for selector in store.read_selectors
    )

    updated_sim_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    updated_sim = validate_core_model_json_artifact(SimulationResult, store, updated_sim_ref)
    payload = from_canonical_bytes(store.get_bytes(updated_sim_ref))

    assert updated_sim.uncertainty_envelopes is not None
    assert updated_sim.schema_version == schema_version
    updated_manifest = store.get_manifest(updated_sim_ref)
    assert updated_manifest.artifact_schema.version == schema_version
    assert store.simulation_result_profile_writes == [False, True, True]
    assert updated_sim_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
        updated_manifest
    )
    assert updated_sim_ref.manifest_profile_sha256 is not None
    if basis_ref is not None:
        assert updated_sim.execution_input_basis_ref == basis_ref
        assert "execution_input_basis_ref" in payload
        assert "execution_source_status" in payload
    else:
        assert "execution_input_basis_ref" not in payload
        assert "execution_source_status" not in payload
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
