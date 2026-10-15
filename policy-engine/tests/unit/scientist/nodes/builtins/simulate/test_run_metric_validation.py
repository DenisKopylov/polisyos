from __future__ import annotations

import logging

import pytest

from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    FoundryExecutionInputBasisRef,
    MetricObservationBundle,
    Metrics,
    MetricsRef,
    ModelOutputs,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.metric_validation_report import load_metric_validation_report
from polisyos.scientist.nodes.builtins.simulate.run_metric_validation import RunMetricValidationNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF,
    ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.metrics import persist_metric_observation_bundle


class _RecordingFileSystemCAS(FileSystemCAS):
    def __init__(self, root) -> None:
        super().__init__(root)
        self.simulation_result_profile_writes: list[bool] = []

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


@pytest.mark.parametrize(
    ("schema_version", "source_selected"),
    [("1.3", False), ("1.3", True), ("1.4", True)],
)
def test_run_metric_validation_node_persists_report_and_updates_simulation_result(
    tmp_path,
    schema_version: str,
    source_selected: bool,
) -> None:
    store = _RecordingFileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_metric_validation_node"
    )
    ctx = ExecutionContext(
        store=store, run=run, logger=logging.getLogger("test.metric_validation.node")
    )

    exec_plan_payload = store.put_json(
        {"order": ["noop"]},
        PutOptions(
            kind="foundry.exec_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ExecPlan", version="1.0"),
        ),
    )
    metrics_payload = store.put_json(
        Metrics(values={"roc_auc": 0.72, "accuracy": 0.75}).model_dump(mode="json"),
        PutOptions(
            kind="foundry.metrics",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.Metrics", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    bundle_ref = persist_metric_observation_bundle(
        store,
        MetricObservationBundle(
            dataset_id="holdout_v1",
            task="binary",
            sample_ids=["a", "b", "c", "d", "e", "f"],
            y_true=[0, 1, 0, 1, 1, 0],
            models={
                "baseline": ModelOutputs(
                    model_id="baseline",
                    y_pred=[0, 1, 0, 0, 1, 0],
                    y_score=[0.2, 0.9, 0.3, 0.4, 0.7, 0.2],
                ),
                "candidate": ModelOutputs(
                    model_id="candidate",
                    y_pred=[0, 1, 0, 1, 1, 0],
                    y_score=[0.1, 0.95, 0.25, 0.8, 0.75, 0.1],
                ),
            },
            metadata={"run_id": "R_metric_validation_node", "baseline_model_id": "baseline"},
        ),
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
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_payload.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_payload.artifact_id),
        metric_observation_bundle_ref=bundle_ref,
        execution_input_basis_ref=basis_ref,
        execution_source_status=execution_source_status,
    )
    simulation_result_payload = store.put_json(
        simulation_result.to_artifact_payload(),
        PutOptions(
            kind="foundry.simulation_result",
            media_type="application/json",
            schema=SchemaInfo(
                name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                version=simulation_result.schema_version,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=source_selected,
    )
    simulation_result_ref = SimulationResultRef.model_validate(
        simulation_result_payload.model_dump(mode="python")
    )

    state = ExperimentState(
        run_id="R_metric_validation_node",
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: SimulationResultRef(
                **simulation_result_ref.model_dump(mode="python")
            ),
            ARTIFACT_METRICS_REF: MetricsRef(artifact_id=metrics_payload.artifact_id),
            ARTIFACT_METRIC_OBSERVATION_BUNDLE_REF: bundle_ref,
        },
        params={
            "metric_validation": {
                "baseline_model_id": "baseline",
                "candidate_model_ids": ["candidate"],
                "metric_ids": ["roc_auc", "accuracy"],
                "n_resamples": 500,
                "random_seed": 7,
            }
        },
    )

    wrong_profile_ref = simulation_result_ref.model_copy(
        update={"manifest_profile_sha256": f"sha256:{'f' * 64}"}
    )
    wrong_profile_state = state.model_copy(
        update={
            "artifacts_index": state.artifacts_index
            | {ARTIFACT_SIMULATION_RESULT_REF: wrong_profile_ref}
        }
    )
    with pytest.raises(FileNotFoundError):
        RunMetricValidationNode().execute(ctx, wrong_profile_state)

    outcome = RunMetricValidationNode().execute(ctx, state)

    assert outcome.status == "ok"
    metric_validation_ref = outcome.state.artifacts_index[ARTIFACT_METRIC_VALIDATION_REPORT_REF]
    report = load_metric_validation_report(_ensure_ir_artifact_store(store), metric_validation_ref)
    assert report.dataset_id == "holdout_v1"
    assert {comparison.metric_id for comparison in report.comparisons} == {"roc_auc", "accuracy"}

    updated_sim_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    updated_simulation_result = validate_core_model_json_artifact(
        SimulationResult,
        store,
        updated_sim_ref,
    )
    updated_sim_payload = from_canonical_bytes(store.get_bytes(updated_sim_ref))
    assert updated_simulation_result.metric_observation_bundle_ref == bundle_ref
    assert updated_simulation_result.metric_validation_report_ref == metric_validation_ref
    assert updated_simulation_result.schema_version == schema_version
    updated_manifest = store.get_manifest(updated_sim_ref)
    assert updated_manifest.artifact_schema.version == schema_version
    assert store.simulation_result_profile_writes == [
        source_selected,
        source_selected or schema_version == SimulationResult.ARTIFACT_SCHEMA_VERSION,
    ]
    if source_selected or schema_version == SimulationResult.ARTIFACT_SCHEMA_VERSION:
        assert updated_sim_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
            updated_manifest
        )
        assert updated_sim_ref.manifest_profile_sha256 is not None
    else:
        assert updated_sim_ref.manifest_profile_sha256 is None
    if source_selected:
        input_profiles = {
            item.role: item.manifest_profile_sha256 for item in updated_manifest.inputs
        }
        assert (
            input_profiles["base_simulation_result"]
            == simulation_result_ref.manifest_profile_sha256
        )
    if basis_ref is not None:
        assert updated_simulation_result.execution_input_basis_ref == basis_ref
        assert "execution_input_basis_ref" in updated_sim_payload
        assert "execution_source_status" in updated_sim_payload
        input_profiles = {
            item.role: item.manifest_profile_sha256 for item in updated_manifest.inputs
        }
        assert input_profiles["execution_input_basis"] == basis_ref.manifest_profile_sha256
    else:
        assert "execution_input_basis_ref" not in updated_sim_payload
        assert "execution_source_status" not in updated_sim_payload
