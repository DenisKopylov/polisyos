from __future__ import annotations

import logging
import math
from pathlib import Path
from types import SimpleNamespace

import jax.numpy as jnp
import numpy as np
import pytest
from pydantic import TypeAdapter

import polisyos.foundry.calibration.calibrator as calibrator_module
import polisyos.scientist.nodes.builtins.simulate.propagate_welfare as propagate_welfare_module
import polisyos.scientist.nodes.builtins.simulate.welfare_draws as welfare_draws_module
import polisyos.scientist.nodes.builtins.simulate.welfare_types as welfare_types_module
from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    input_ref_from_artifact_ref,
    resolve_dependency_graph,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    CompileRequest,
    EquilibriumMultiplicityDiagnostics,
    EquilibriumMultiplicityReport,
    EquilibriumMultiplicityReportRef,
    EquilibriumSearchProtocol,
    ExecPlan,
    ExecPlanRef,
    ExecuteRequest,
    FeedbackResultRef,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
    FoundryExecConfig,
    FoundryExecutionInputBasisRef,
    FoundryInputBindingsRef,
    Metrics,
    MetricsRef,
    ParameterOverrideBundle,
    ParameterOverrideBundleRef,
    ProgramGraph,
    ProgramGraphRef,
    SimulationResult,
    SimulationResultRef,
    StateSnapshotRef,
)
from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.core.run.context import RunContext
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.calibration.execution_basis import load_calibration_execution_input_basis
from polisyos.foundry.calibration.report import (
    CalibrationCoordinateProjection,
    CalibrationReport,
    CalibrationUncertainty,
    put_calibration_config,
    put_calibration_report,
)
from polisyos.foundry.calibration.uncertainty_adapter import envelope_from_calibration_param
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane.bindings import build_input_bindings
from polisyos.foundry.execute import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.ir.analytics.calibration import (
    CalibrationConfig,
    CalibrationTarget,
    TrainableParamRef,
)
from polisyos.ir.analytics.decision_layer import load_social_weight_manifest
from polisyos.ir.analytics.dependence_structure import (
    build_dependence_structure,
    persist_dependence_structure,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    ParametricFitCarrier,
    PosteriorSamplesCarrier,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.analytics.welfare import (
    GEUncertaintyBundle,
    GEUncertaintyRepresentation,
    load_channel_decomposition_artifact,
    load_welfare_bundle,
    load_welfare_sample_bundle,
    persist_ge_uncertainty_bundle,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.registry.refs import ArtifactRefModel, UncertaintyEnvelopeRef
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact
from polisyos.scientist.feedback.core import build_parameter_override_bundle
from polisyos.scientist.nodes.builtins.decide.decision_packet.enrichment import (
    _build_welfare_section,
)
from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import (
    PropagateWelfareNode,
)
from polisyos.scientist.nodes.builtins.simulate.welfare_context import (
    _calibration_execution_source_join,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_CALIBRATION_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.phase3 import (
    Phase3CertificateStatus,
    phase3_gate_reference_blockers,
    resolve_phase3_gate,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


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
def test_propagate_welfare_node_writes_partial_bundle_for_pe_only(
    tmp_path,
    schema_version: str,
) -> None:
    store = _RecordingFileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_welfare_partial")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.welfare.partial"))

    env_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store),
        UncertaintyEnvelope(
            point_estimate=10.0,
            confidence_interval=(8.0, 12.0),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.TRUST,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            metadata={"param_name": "policy_value"},
        ),
    )
    snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=snapshot_ref, uncertainty_envelope_ref=env_ref),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.1.0"),
        ),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"policy_value": 10.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
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
    sim_result_ref = SimulationResultRef.model_validate(selected_view.model_dump(mode="python"))

    state = ExperimentState(
        run_id="R_welfare_partial",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id),
        },
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
        params={"welfare_weights": {"policy_value": 1.0}},
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
    wrong_profile_outcome = PropagateWelfareNode().execute(ctx, wrong_profile_state)
    assert wrong_profile_outcome.status == "skip"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in wrong_profile_outcome.state.artifacts_index
    assert store.simulation_result_profile_writes == [False, True]

    outcome = PropagateWelfareNode().execute(ctx, state)
    assert outcome.status == "ok"
    assert any(
        getattr(selector, "manifest_profile_sha256", None) == sim_result_ref.manifest_profile_sha256
        for selector in store.read_selectors
    )
    assert ARTIFACT_WELFARE_BUNDLE_REF in outcome.state.artifacts_index

    bundle_ref = outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    bundle = load_welfare_bundle(_ensure_ir_artifact_store(store), bundle_ref)
    assert bundle.point_estimate == 10.0
    assert bundle.credible_interval is not None
    assert bundle.robust_interval == (8.0, 12.0)
    assert bundle.status.value == "partial"
    assert "ge_operator_missing_pe_only" in bundle.warnings
    assert bundle.sample_bundle_ref is not None
    assert bundle.sensitivity_diagnostics_ref is not None

    sample_bundle = load_welfare_sample_bundle(
        _ensure_ir_artifact_store(store), bundle.sample_bundle_ref
    )
    assert len(sample_bundle.welfare_draws) >= 50

    bundle_manifest = store.get_manifest(bundle_ref)
    bundle_input_profiles = {
        item.role: item.manifest_profile_sha256 for item in bundle_manifest.inputs
    }
    assert bundle_input_profiles["simulation_result"] == sim_result_ref.manifest_profile_sha256
    assert bundle_input_profiles["metrics"] == simulation_result.metrics_ref.manifest_profile_sha256

    updated_sim_result_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    updated_sim = validate_core_model_json_artifact(SimulationResult, store, updated_sim_result_ref)
    updated_payload = from_canonical_bytes(store.get_bytes(updated_sim_result_ref))
    assert updated_sim.welfare_bundle_ref is not None
    updated_sim_manifest = store.get_manifest(updated_sim_result_ref)
    assert updated_sim.schema_version == schema_version
    assert updated_sim_manifest.artifact_schema.version == schema_version
    assert store.simulation_result_profile_writes == [False, True, True]
    assert updated_sim_result_ref.manifest_profile_sha256 == artifact_manifest_profile_sha256(
        updated_sim_manifest
    )
    if basis_ref is not None:
        assert updated_sim.execution_input_basis_ref == basis_ref
        assert "execution_input_basis_ref" in updated_payload
        assert "execution_source_status" in updated_payload
    else:
        assert "execution_input_basis_ref" not in updated_payload
        assert "execution_source_status" not in updated_payload
    updated_input_profiles = {
        item.role: item.manifest_profile_sha256 for item in updated_sim_manifest.inputs
    }
    assert (
        updated_input_profiles["base_simulation_result"] == sim_result_ref.manifest_profile_sha256
    )
    assert updated_input_profiles["welfare_bundle"] == bundle_ref.manifest_profile_sha256
    if basis_ref is not None:
        assert updated_input_profiles["execution_input_basis"] == basis_ref.manifest_profile_sha256


def test_propagate_welfare_node_skips_default_operational_metrics_without_welfare_inputs(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_welfare_default_skip",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.welfare.default_skip"),
    )

    snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(
            values={
                "applied_nodes": 1,
                "checked_constraints": 2,
                "failure_cards_recorded": 0,
                "step_latency_ms": 12.5,
            }
        ),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_welfare_default_skip",
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
        params={},
    )

    outcome = PropagateWelfareNode().execute(ctx, state)

    assert outcome.status == "skip"
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index
    assert outcome.events
    assert "welfare target" in outcome.events[0].message


def test_propagate_welfare_node_feeds_feedback_multiplicity_into_welfare_bundle(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_welfare_multiplicity",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.welfare.multiplicity"),
    )

    snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"policy_value": 10.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    multiplicity_report_ref_payload = store.put_json(
        EquilibriumMultiplicityReport(
            model_id="test_feedback_model",
            search_protocol=EquilibriumSearchProtocol(n_attempts=2),
            global_diagnostics=EquilibriumMultiplicityDiagnostics(
                num_attempts=2,
                num_converged=2,
                num_equilibria=2,
            ),
        ),
        PutOptions(
            kind="foundry.equilibrium_multiplicity_report",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.core.EquilibriumMultiplicityReport",
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    multiplicity_report_ref = EquilibriumMultiplicityReportRef(
        artifact_id=multiplicity_report_ref_payload.artifact_id
    )
    feedback_state = FeedbackStateSnapshot(
        variable_ids=["x"],
        values=[1.0],
        scales=[1.0],
        lower_bounds=[None],
        upper_bounds=[None],
        weights=[1.0],
    )
    feedback_result_ref_payload = store.put_json(
        FeedbackSolveResult(
            converged=True,
            initial_state=feedback_state,
            final_state=feedback_state,
            multiplicity_report_ref=multiplicity_report_ref,
        ),
        PutOptions(
            kind="foundry.feedback_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FeedbackSolveResult", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    feedback_result_ref = FeedbackResultRef(artifact_id=feedback_result_ref_payload.artifact_id)
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
            feedback_result_ref=feedback_result_ref,
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_welfare_multiplicity",
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
        params={
            "welfare_weights": {"policy_value": 1.0},
            "welfare_input_envelopes": {
                "policy_value": {
                    "point_estimate": 10.0,
                    "confidence_interval": [9.0, 11.0],
                    "confidence_level": 0.95,
                    "distribution_family": "normal",
                    "source": "manual",
                    "propagation_method": "none",
                    "interval_semantics": "confidence_interval",
                }
            },
        },
    )

    outcome = PropagateWelfareNode().execute(ctx, state)

    assert outcome.status == "ok"
    bundle = load_welfare_bundle(
        _ensure_ir_artifact_store(store), outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    )
    assert bundle.equilibrium_multiplicity.status == "multiple"
    assert bundle.equilibrium_multiplicity.selection_dependence is True
    assert bundle.equilibrium_multiplicity.report_ref is not None
    assert bundle.metadata["equilibrium_multiplicity_status"] == "multiple"


def test_propagate_welfare_node_materializes_social_weight_manifest(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_welfare_weights")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.welfare.weights"))

    snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"policy_value": 10.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_welfare_weights",
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
        params={
            "welfare_weights": {"policy_value": 1.0},
            "welfare_input_envelopes": {
                "policy_value": {
                    "point_estimate": 10.0,
                    "confidence_interval": [9.0, 11.0],
                    "confidence_level": 0.95,
                    "distribution_family": "normal",
                    "source": "manual",
                    "propagation_method": "none",
                    "interval_semantics": "confidence_interval",
                }
            },
            "welfare_social_weight_manifest": {
                "ref": "swr://policy.welfare/test@1.0.0#weights",
                "method_fqn": "policy.welfare.state_dependent_inverse_social_weights@1.0.0",
                "normalization": "mean_one",
                "income_grid": [0.0, 1.0],
                "weights_on_grid": [1.2, 0.8],
                "state_keys": ["income"],
            },
        },
    )

    outcome = PropagateWelfareNode().execute(ctx, state)

    assert outcome.status == "ok"
    bundle = load_welfare_bundle(
        _ensure_ir_artifact_store(store), outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    )
    assert bundle.social_weight_ref is not None
    assert bundle.social_weight_ref.kind == "ir.social_weight_manifest"
    manifest = load_social_weight_manifest(
        _ensure_ir_artifact_store(store), bundle.social_weight_ref
    )
    assert manifest.manifest_ref == "swr://policy.welfare/test@1.0.0#weights"
    assert manifest.state_keys == ("income",)
    assert bundle.metadata["source_social_weight_handle"] is None


def test_propagate_welfare_node_fails_on_singular_ge_operator(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_welfare_fail")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.welfare.fail"))

    snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"policy_value": 10.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

    state = ExperimentState(
        run_id="R_welfare_fail",
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
        params={
            "welfare_weights": {"policy_value": 1.0},
            "welfare_ge_technical_coefficients": [[1.0]],
        },
    )

    outcome = PropagateWelfareNode().execute(ctx, state)
    assert outcome.status == "fail"
    assert outcome.error is not None
    assert outcome.error.code == "ERROR_GE_OPERATOR_SINGULAR"


def test_welfare_report_producer_persists_channel_decomposition_artifact(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_welfare_channels"
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.welfare.channels"))

    from polisyos.scientist.nodes.builtins.simulate.welfare_reports import (
        _maybe_build_channel_decomposition_ref,
    )

    channel_ref = _maybe_build_channel_decomposition_ref(
        ctx,
        welfare_params={
            "channel_decomposition": {
                "target_kind": "social_welfare",
                "baseline_microdata": {
                    "overlap_ok": True,
                    "overlap_stats": {"min_propensity": 0.15},
                },
                "policy_basis": {
                    "basis_labels": ["delta_tax_rate", "delta_transfer"],
                    "step_vector": [0.02, 1.0],
                    "policy_class": "local_affine_tax_transfer",
                    "policy_rank_ok": True,
                    "timing_assumptions": ["policy -> behavior -> closure"],
                },
                "mechanical_inputs": {
                    "mechanical_vector": [0.6],
                    "observability_notes": ["statutory replay"],
                },
                "behavior_model": {
                    "behavioral_vector": [-0.24],
                    "first_stage_ok": True,
                    "first_stage_stats": {"behavior_f": 18.0},
                },
                "fiscal_state_model": {
                    "fiscal_feedback_vector": [0.16],
                    "first_stage_ok": True,
                    "first_stage_stats": {"fiscal_f": 14.0},
                },
                "instrument_set": {
                    "overid_ok": True,
                    "timing_ok": True,
                    "overid_stats": {"hansen_pvalue": 0.31},
                },
                "total_vector": [0.52],
            }
        },
        total_vector=np.asarray([0.52], dtype=float),
    )
    assert channel_ref is not None

    artifact = load_channel_decomposition_artifact(_ensure_ir_artifact_store(store), channel_ref)
    assert artifact.identification_status.value == "blocked"
    assert "upstream_input_owner_not_established" in artifact.blocking_reasons
    assert artifact.diagnostic_summary["candidate_identification_status"] == "identified"
    assert artifact.diagnostic_summary["input_owner_status"] == "not_established"
    assert artifact.mechanical_vector == (0.6,)
    assert artifact.behavioral_vector == (-0.24,)
    assert artifact.fiscal_feedback_vector == (0.16,)
    assert artifact.total_vector == (0.52,)


def test_propagate_welfare_node_supports_delta_and_dependence_sampling(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_welfare_delta")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.welfare.delta"))

    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": "sha256:" + "2" * 64,
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"m1": 2.0, "m2": 3.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    dependence_ref = persist_dependence_structure(
        _ensure_ir_artifact_store(store),
        build_dependence_structure(
            regime="panel",
            class_label="gaussian_copula",
            calibrated=True,
            recommended_covariance="cluster",
            source_method="unit_test",
            metadata={
                "parameter_order": ["theta_1", "theta_2"],
                "correlation_matrix": [[1.0, 0.5], [0.5, 1.0]],
            },
        ),
    )

    state = ExperimentState(
        run_id="R_welfare_delta",
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
        params={
            "welfare_metric_order": ["m1", "m2"],
            "welfare_weights": {"m1": 1.0, "m2": 1.0},
            "welfare_pe_sensitivity": {
                "m1": {"theta_1": 1.0},
                "m2": {"theta_2": 1.0},
            },
            "welfare_input_envelopes": {
                "theta_1": {
                    "point_estimate": 1.0,
                    "confidence_interval": [0.8, 1.2],
                    "confidence_level": 0.95,
                    "distribution_family": "normal",
                    "source": "manual",
                    "propagation_method": "none",
                    "interval_semantics": "confidence_interval",
                },
                "theta_2": {
                    "point_estimate": 1.0,
                    "confidence_interval": [0.7, 1.3],
                    "confidence_level": 0.95,
                    "distribution_family": "normal",
                    "source": "manual",
                    "propagation_method": "none",
                    "interval_semantics": "confidence_interval",
                },
            },
            "welfare_dependence_structure_ref": dependence_ref.model_dump(mode="json"),
            "welfare_credible_method": "delta",
        },
    )

    outcome = PropagateWelfareNode().execute(ctx, state)
    assert outcome.status == "ok"

    bundle = load_welfare_bundle(
        _ensure_ir_artifact_store(store), outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    )
    assert bundle.credible_interval is not None
    assert bundle.sample_bundle_ref is None
    assert bundle.diagnostics["credible_method"] == "delta"
    assert bundle.diagnostics["dependence_applied"] is True
    assert bundle.diagnostics["dependence_sampling"]["strategy"].startswith("gaussian_copula")
    assert "dependence_structure_present_but_not_applied" not in bundle.warnings


def test_propagate_welfare_uses_typed_normal_scale_independent_of_display_level(
    tmp_path,
) -> None:
    report = CalibrationReport(
        calibrated_params={"node.rate": 0.25},
        total_loss=0.01,
        uncertainties=CalibrationUncertainty(
            method="laplace",
            params=["node.rate"],
            covariance=[[1.0]],
            correlation=[[1.0]],
            std=[1.0],
        ),
        coordinate_projection=CalibrationCoordinateProjection(
            field_order=("node.rate",),
            coordinate_order=("node.rate",),
            matrix=((1.0,),),
        ),
    )
    envelope_80 = envelope_from_calibration_param(
        report,
        "node.rate",
        confidence_level=0.8,
    )
    envelope_95 = envelope_from_calibration_param(
        report,
        "node.rate",
        confidence_level=0.95,
    )
    assert envelope_80 is not None
    assert envelope_95 is not None
    display_envelopes: dict[float, UncertaintyEnvelope] = {
        0.8: envelope_80,
        0.95: envelope_95,
    }

    untyped_legacy_envelope = UncertaintyEnvelope(
        point_estimate=0.25,
        confidence_interval=display_envelopes[0.95].confidence_interval,
        confidence_level=0.95,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        metadata={"param_name": "node.rate"},
    )
    untyped_heuristic_envelope = untyped_legacy_envelope.model_copy(
        update={
            "confidence_level": None,
            "interval_semantics": IntervalSemantics.HEURISTIC_RANGE,
            "is_heuristic_ci": True,
            "gate_eligible": False,
        }
    )
    envelopes = [
        display_envelopes[0.8],
        display_envelopes[0.95],
        untyped_legacy_envelope,
        untyped_heuristic_envelope,
    ]

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"policy_value": 10.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    ge_matrix_artifact_ref = store.put_json(
        {"matrix": [[1.0]]},
        PutOptions(kind="ir.welfare_multiplier_matrix", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ge_matrix_ref = ArtifactRefModel.model_validate(ge_matrix_artifact_ref.model_dump(mode="json"))
    ge_uncertainty_ref = persist_ge_uncertainty_bundle(
        _ensure_ir_artifact_store(store),
        GEUncertaintyBundle(
            model_class="linearized_ge_io",
            representation=GEUncertaintyRepresentation.MULTIPLIER_INTERVALS,
            multiplier_shape=(1, 1),
            point_multiplier_ref=ge_matrix_ref,
            lower_multiplier_ref=ge_matrix_ref,
            upper_multiplier_ref=ge_matrix_ref,
        ),
    )

    def _state_for_envelope(
        run_id: str,
        envelope_refs: dict[str, UncertaintyEnvelopeRef],
    ) -> ExperimentState:
        return ExperimentState(
            run_id=run_id,
            artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
            params={
                "welfare_metric_order": ["policy_value"],
                "welfare_weights": {"policy_value": 1.0},
                "welfare_pe_sensitivity": {"policy_value": dict.fromkeys(envelope_refs, 1.0)},
                "welfare_input_envelopes": {
                    name: envelope_ref.model_dump(mode="json")
                    for name, envelope_ref in envelope_refs.items()
                },
                "welfare_ge_multiplier_semantics": "leontief_inverse",
                "welfare_ge_uncertainty_ref": ge_uncertainty_ref.model_dump(mode="json"),
                "welfare_social_weight_manifest": {
                    "ref": f"swr://phase3/{run_id}@1.0.0#weights",
                    "method_fqn": "policy.welfare.state_dependent_inverse_social_weights@1.0.0",
                    "normalization": "mean_one",
                    "income_grid": [0.0, 1.0],
                    "weights_on_grid": [1.2, 0.8],
                    "state_keys": ["income"],
                },
                "welfare_credible_method": "monte_carlo",
                "propagation_config": {
                    "mc_n_samples": 100,
                    "mc_min_valid_samples": 10,
                    "mc_seed": 31415,
                    "compute_sensitivity": False,
                },
            },
        )

    welfare_draws: list[tuple[float, ...]] = []
    persisted_envelope_refs: list[UncertaintyEnvelopeRef] = []
    status_observations: list[tuple[str, bool]] = []
    phase3_observations: list[tuple[bool, bool]] = []
    persisted_gate_observations: list[bool] = []
    for index, envelope in enumerate(envelopes):
        if index < 2:
            assert isinstance(envelope.distribution_payload, ParametricFitCarrier)
            assert envelope.distribution_payload.parameters["std"] == 1.0
        else:
            assert envelope.distribution_payload is None
        if not envelope.gate_eligible:
            assert envelope.confidence_level is None
            assert envelope.is_heuristic_ci is True

        envelope_ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(store), envelope)
        persisted_envelope_refs.append(envelope_ref)
        persisted_source = load_uncertainty_envelope(_ensure_ir_artifact_store(store), envelope_ref)
        if index < 2:
            assert isinstance(persisted_source.distribution_payload, ParametricFitCarrier)
        if not persisted_source.gate_eligible:
            assert persisted_source.confidence_level is None
            assert persisted_source.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
            assert persisted_source.is_heuristic_ci is True
            assert persisted_source.gate_eligible is False

        run_id = f"R_welfare_typed_scale_{index}"
        run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle,
            run_id=run_id,
        )
        ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger("test.welfare.typed_scale"),
        )
        state = _state_for_envelope(run_id, {"node.rate": envelope_ref})
        if index == 2:
            state.params["welfare_input_envelopes"]["node.unused"] = persisted_envelope_refs[
                0
            ].model_dump(mode="json")
        outcome = PropagateWelfareNode().execute(ctx, state)
        assert outcome.status == "ok"
        bundle = load_welfare_bundle(
            _ensure_ir_artifact_store(store),
            outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF],
        )
        status_observations.append(
            (
                bundle.status.value,
                "input_uncertainty_not_gate_eligible" in bundle.warnings,
            )
        )
        assert bundle.sample_bundle_ref is not None
        persisted_draws = load_welfare_sample_bundle(
            _ensure_ir_artifact_store(store), bundle.sample_bundle_ref
        )
        welfare_draws.append(persisted_draws.welfare_draws)

        phase3_gate = resolve_phase3_gate(ctx, outcome.state)
        phase3_observations.append(
            (
                phase3_gate.gate_passed,
                "phase3.welfare_not_ok" in phase3_gate.blocking_reasons,
            )
        )

        forged_pass = Phase3CertificateStatus.model_validate(
            {
                **phase3_gate.model_dump(mode="python"),
                "gate_passed": True,
                "blocking_reasons": [],
            }
        )
        persisted_gate_blockers = phase3_gate_reference_blockers(store, forged_pass)
        persisted_gate_observations.append("phase3.welfare_not_ok" in persisted_gate_blockers)

    assert all(
        math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
        for left, right in zip(welfare_draws[0], welfare_draws[1], strict=True)
    )
    assert all(
        math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
        for left, right in zip(welfare_draws[1], welfare_draws[2], strict=True)
    )
    observed = {
        "bundle_status_and_non_gate_warning": status_observations,
        "phase3_gate_pass_and_welfare_block": phase3_observations,
        "persisted_phase3_welfare_block": persisted_gate_observations,
    }
    assert observed == {
        "bundle_status_and_non_gate_warning": [
            ("degraded", True),
            ("degraded", True),
            ("ok", False),
            ("degraded", True),
        ],
        "phase3_gate_pass_and_welfare_block": [
            (False, True),
            (False, True),
            (True, False),
            (False, True),
        ],
        "persisted_phase3_welfare_block": [True, True, False, True],
    }, observed

    malformed_carrier = ParametricFitCarrier(
        family=DistributionFamily.NORMAL,
        parameters={"mean": 0.25},
    )
    malformed_envelope = display_envelopes[0.95].model_copy(
        update={"distribution_payload": malformed_carrier}
    )
    malformed_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store), malformed_envelope
    )
    malformed_run_id = "R_welfare_malformed_typed_scale"
    malformed_run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id=malformed_run_id,
    )
    malformed_ctx = ExecutionContext(
        store=store,
        run=malformed_run,
        logger=logging.getLogger("test.welfare.malformed_typed_scale"),
    )
    malformed_outcome = PropagateWelfareNode().execute(
        malformed_ctx,
        _state_for_envelope(malformed_run_id, {"node.rate": malformed_ref}),
    )
    assert malformed_outcome.status == "fail"
    assert malformed_outcome.error is not None
    assert malformed_outcome.error.code == "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE"
    assert malformed_outcome.error.details["failure_scope"] == "global"
    assert malformed_outcome.error.details["failure_stage"] == "sample_generation"
    assert malformed_outcome.error.details["draw_index"] == 0
    assert malformed_outcome.error.details["sampled_input_sha256"] is None
    assert malformed_outcome.error.details["execution_attempt_count"] == 0
    assert malformed_outcome.error.details["execution_attempts"] == []
    assert malformed_outcome.error.details["attempted_draw_count"] == 1
    assert malformed_outcome.error.details["simulation_attempt_count"] == 0
    assert malformed_outcome.error.details["retry_attempt_count"] == 0
    assert malformed_outcome.error.details["error_type"] == "_WelfareNodeFailure"
    assert malformed_outcome.error.details["error_message"] == (
        "Welfare input uncertainty does not declare a usable scale"
    )
    assert malformed_outcome.error.details["cause_type_chain"] == [
        "_WelfareNodeFailure",
        "ValueError",
    ]
    assert malformed_outcome.error.details["cause_chain_complete"] is True
    assert malformed_outcome.error.details["cause_chain_cycle_detected"] is False
    assert ARTIFACT_WELFARE_BUNDLE_REF not in malformed_outcome.state.artifacts_index

    mixed_run_id = "R_welfare_typed_scale_mixed_inputs"
    mixed_run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id=mixed_run_id,
    )
    mixed_ctx = ExecutionContext(
        store=store,
        run=mixed_run,
        logger=logging.getLogger("test.welfare.mixed_typed_scale"),
    )
    mixed_outcome = PropagateWelfareNode().execute(
        mixed_ctx,
        _state_for_envelope(
            mixed_run_id,
            {
                "node.rate": persisted_envelope_refs[1],
                "node.other": persisted_envelope_refs[2],
            },
        ),
    )
    assert mixed_outcome.status == "ok"
    mixed_bundle = load_welfare_bundle(
        _ensure_ir_artifact_store(store),
        mixed_outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF],
    )
    assert mixed_bundle.status.value == "degraded"
    assert "input_uncertainty_not_gate_eligible" in mixed_bundle.warnings
    assert "dependence_assumed_independent" in mixed_bundle.warnings


_B197_REPLAY_BY_STORE_ROOT: dict[str, SimulationResultRef] = {}


def _build_b197_tied_execution_source(store: FileSystemCAS):
    """Persist a real selected Foundry graph, plan, state, bindings, and baseline run."""
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    base_state = GlobalState.empty(n_agents=1, n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(
            income=jnp.asarray([100.0]),
            reported_income=jnp.asarray([100.0]),
        ),
        government_balance=jnp.asarray(0.0),
    )
    snapshot_payload_ref = put_state_snapshot(
        store,
        state=base_state,
        step=0,
        return_selected_profile=True,
    )
    state_snapshot_ref = StateSnapshotRef.model_validate(
        snapshot_payload_ref.model_dump(mode="python")
    )
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(state_snapshot_ref, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    selected_data_snapshot_ref = DataSnapshotRef.model_validate(
        data_snapshot_ref.model_dump(mode="python")
    )
    bindings = build_input_bindings(
        store,
        data_snapshot_ref=selected_data_snapshot_ref,
        registry_bundle_ref=registry.bundle_ref,
        return_selected_profile=True,
    )

    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="b197_tied", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="b197_tied",
            interventions=[
                {
                    "intervention_id": intervention_id,
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": "==",
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": "0.2"},
                    "priority": priority,
                }
                for intervention_id, priority in (("a", 0), ("b", 1))
            ],
        ),
        model_spec=ModelSpec(
            model_id="b197_tied",
            data_snapshot_ref=str(selected_data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        policy,
        candidate_id="b197_tied_candidate",
        metadata={"evidence_grade": "candidate", "purpose": "controlled B197 fixture"},
    )
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        inputs=[
            input_ref_from_artifact_ref(
                selected_data_snapshot_ref, role="world_model_data_snapshot"
            ),
            input_ref_from_artifact_ref(registry.bundle_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    selected_policy_ref = persist_trinity_bundle_artifact(
        _ensure_ir_artifact_store(store),
        policy,
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
    )
    policy_ref = ArtifactRef.model_validate(selected_policy_ref.model_dump(mode="python"))
    compiled = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry.bundle_ref,
            return_selected_profile=True,
        ),
    )
    assert compiled.ok and compiled.exec_plan_ref is not None
    source_plan = ExecPlan.model_validate(
        from_canonical_bytes(store.get_bytes(compiled.exec_plan_ref))
    )
    source_graph_ref = source_plan.program_ref
    source_graph = ProgramGraph.model_validate(
        from_canonical_bytes(store.get_bytes(source_graph_ref))
    )
    node_aliases = {"a": "A", "b": "B"}
    mapped_graph = source_graph.model_copy(
        update={
            "nodes": [
                node.model_copy(update={"node_id": node_aliases[node.node_id]})
                if node.node_id in node_aliases
                else node
                for node in source_graph.nodes
            ],
            "edges": [
                edge.model_copy(
                    update={
                        "src": node_aliases.get(edge.src, edge.src),
                        "dst": node_aliases.get(edge.dst, edge.dst),
                    }
                )
                for edge in source_graph.edges
            ],
            "entrypoints": [node_aliases.get(item, item) for item in source_graph.entrypoints],
            "notes": [
                *source_graph.notes,
                "Controlled B197 graph maps source interventions a/b to execution labels A/B.",
                "This identity fixture makes no source-authenticity or calibration-authority claim.",
            ],
        }
    )
    source_graph_manifest = store.get_manifest(source_graph_ref)
    selected_graph_ref = store.put_json(
        mapped_graph,
        PutOptions(
            kind=ProgramGraph.ARTIFACT_KIND,
            media_type=ProgramGraph.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ProgramGraph.ARTIFACT_SCHEMA_NAME,
                version=ProgramGraph.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=source_graph_manifest.inputs,
        ),
        return_selected_profile=True,
    )
    typed_graph_ref = ProgramGraphRef.model_validate(selected_graph_ref.model_dump(mode="python"))
    mapped_plan = source_plan.model_copy(
        update={
            "program_ref": typed_graph_ref,
            "order": [node_aliases.get(item, item) for item in source_plan.order],
            "notes": [
                note
                for note in source_plan.notes
                if not note.startswith("randomization:treasury_salts_v1")
            ],
        }
    )
    source_plan_manifest = store.get_manifest(compiled.exec_plan_ref)
    plan_inputs = [
        input_ref_from_artifact_ref(typed_graph_ref, role="program_graph")
        if item.role == "program_graph"
        else item
        for item in source_plan_manifest.inputs
        if item.role != "treasury_plan"
    ]
    selected_plan_payload_ref = store.put_json(
        mapped_plan,
        PutOptions(
            kind=ExecPlan.ARTIFACT_KIND,
            media_type=ExecPlan.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ExecPlan.ARTIFACT_SCHEMA_NAME,
                version=ExecPlan.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=plan_inputs,
        ),
        return_selected_profile=True,
    )
    selected_plan_ref = ExecPlanRef.model_validate(
        selected_plan_payload_ref.model_dump(mode="python")
    )
    initial_execution = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=selected_plan_ref,
            input_bindings_ref=bindings.input_bindings_ref,
            registry_bundle_ref=registry.bundle_ref,
            exec_config=FoundryExecConfig(seed=29),
            return_selected_profile=True,
        ),
    )
    assert initial_execution.ok
    assert initial_execution.simulation_result_ref is not None
    admitted = admit_execution_source(store, initial_execution.simulation_result_ref)
    assert admitted.basis is not None
    source_basis = admitted.basis
    selected_graph = ProgramGraph.model_validate(
        from_canonical_bytes(store.get_bytes(source_basis.program_graph_ref))
    )
    selected_plan = ExecPlan.model_validate(
        from_canonical_bytes(store.get_bytes(source_basis.exec_plan_ref))
    )
    registry_content = load_registry_bundle_content(store, source_basis.runtime_registry_ref)
    selected_state = load_state_snapshot(store, snapshot_ref=source_basis.base_state_snapshot_ref)
    return {
        "registry": registry,
        "source_basis": source_basis,
        "initial_simulation_ref": initial_execution.simulation_result_ref,
        "graph": selected_graph,
        "plan": selected_plan,
        "base_state": selected_state,
        "registry_content": registry_content,
    }


def _b197_replay_report(
    store: FileSystemCAS,
    source_basis,
    report_ref: ArtifactRef,
    report: CalibrationReport,
) -> SimulationResultRef:
    """Execute the selected graph again with the report's exact fitted values."""
    override = build_parameter_override_bundle(report)
    assert override is not None
    override_ref = store.put_json(
        override,
        PutOptions(
            kind=ParameterOverrideBundle.ARTIFACT_KIND,
            media_type=ParameterOverrideBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ParameterOverrideBundle.ARTIFACT_SCHEMA_NAME,
                version=ParameterOverrideBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(report_ref, role="calibration_report")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    replay = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=ExecPlanRef.model_validate(
                source_basis.exec_plan_ref.model_dump(mode="python")
            ),
            input_bindings_ref=FoundryInputBindingsRef.model_validate(
                source_basis.input_bindings_ref.model_dump(mode="python")
            ),
            registry_bundle_ref=source_basis.runtime_registry_ref,
            parameter_override_bundle_ref=ParameterOverrideBundleRef.model_validate(
                override_ref.model_dump(mode="python")
            ),
            exec_config=FoundryExecConfig(seed=29),
            return_selected_profile=True,
        ),
    )
    assert replay.ok
    assert replay.simulation_result_ref is not None
    return replay.simulation_result_ref


def _b197_legacy_report_inputs(store: FileSystemCAS, report_ref: ArtifactRef) -> list[InputRef]:
    """Retain only the selected config edge for deliberate legacy covariance fixtures."""
    return [
        edge for edge in store.get_manifest(report_ref).inputs if edge.role == "calibration_config"
    ]


def _run_b197_tied_calibrator(
    store: FileSystemCAS,
    *,
    incomplete_projection: bool = False,
    hessian_enabled: bool = True,
    seed_competing_profile: bool = False,
    caller_configs: list[CalibrationConfig] | None = None,
) -> tuple[ArtifactRef, CalibrationReport]:
    source = _build_b197_tied_execution_source(store)
    source_basis = source["source_basis"]
    graph = source["graph"]
    plan = source["plan"]
    base_state = source["base_state"]
    registry_content = source["registry_content"]
    tied_trainables = [
        TrainableParamRef(param_id="rate", node_id=node_id, tie_id="shared_rate")
        for node_id in ("A", "B")
    ]
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="gov_balance",
                model_metric_path="government_balance",
                fabric_query=None,
                # In the complete profile, both tied graph nodes move on one
                # coordinate and each taxes reported income 100, so dy/dr=200,
                # H=2*w*(dy/dr)^2=400 and sigma^2=1/H=.0025. In the incomplete
                # profile only A.rate is trainable while B.rate stays fixed;
                # then dy/dr=100, H=100 and sigma^2=.01.
                loss={"relative": False, "weight": 0.005},
            )
        ],
        trainables=tied_trainables[:1] if incomplete_projection else tied_trainables,
        max_steps=2,
        learning_rate=0.01,
        seed=0,
        hessian={"enabled": hessian_enabled, "damping": 1e-6},
    )
    config_before_run = config.model_copy(deep=True)
    if caller_configs is not None:
        caller_configs.append(config)
    if seed_competing_profile:
        profile_control_ref = store.put_bytes(
            b"b197 config manifest profile control",
            PutOptions(
                kind="test.calibration_config_profile_control",
                media_type="application/octet-stream",
            ),
        )
        seeded_config_ref = put_calibration_config(
            store,
            config,
            inputs=[
                input_ref_from_artifact_ref(
                    profile_control_ref,
                    role="test_profile_collision_control",
                )
            ],
        )
        assert seeded_config_ref.manifest_profile_sha256 is None
    inputs = CalibratorInputs(
        config=config,
        program_graph=graph,
        exec_plan=plan,
        base_state=base_state,
        mechanism_registry=registry_content.mechanism_registry,
        slot_registry=registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        selector_field_registry=registry_content.selector_field_registry,
        parameter_loader=lambda source_ref: from_canonical_bytes(store.get_bytes(source_ref))
        if isinstance(source_ref, ArtifactRef)
        else {},
        raw_targets={"gov_balance": jnp.asarray([36.0])},
        controls_seq=jnp.arange(1),
        constraint_registry=registry_content.constraint_registry,
        registry_bundle_ref=source_basis.runtime_registry_ref,
        mechanism_registry_ref=source_basis.runtime_registry_members.mechanism_registry,
        units_registry=registry_content.units_registry,
        units_registry_ref=source_basis.runtime_registry_members.units_registry,
        base_state_snapshot_ref=source_basis.base_state_snapshot_ref,
        exec_plan_ref=source_basis.exec_plan_ref,
    )

    artifact_ids_before_run = {str(item) for item in store.iter_artifact_ids()}
    report, report_ref = Calibrator(inputs).run_and_persist(store)
    if not hessian_enabled:
        assert report.uncertainties is None
        assert report.coordinate_projection is None
        assert report.coordinate_projection_status == "not_established"
        assert report.uncertainty_envelopes is None
    else:
        assert report.uncertainties is not None
        if incomplete_projection:
            assert report.coordinate_projection is None
            assert report.coordinate_projection_status == "incomplete"
            assert report.uncertainty_envelopes is None
        else:
            assert report.coordinate_projection_status == "complete"
            assert report.coordinate_projection is not None
            assert report.coordinate_projection.field_order == ("A.rate", "B.rate")
            assert report.coordinate_projection.coordinate_order == ("shared_rate",)
            assert report.coordinate_projection.matrix == ((1.0,), (1.0,))
    assert report.target_weights["gov_balance"] == pytest.approx(0.005)
    if hessian_enabled:
        expected_coordinate_variance = 0.01 if incomplete_projection else 0.0025
        assert report.uncertainties is not None
        assert report.uncertainties.covariance[0][0] == pytest.approx(
            expected_coordinate_variance,
            rel=1e-4,
        )

    report_manifest = store.get_manifest(report_ref)
    assert report_manifest.artifact_schema.version == "2.0"
    config_inputs = [item for item in report_manifest.inputs if item.role == "calibration_config"]
    assert len(config_inputs) == 1
    config_input = config_inputs[0]
    if seed_competing_profile:
        assert config_input.manifest_profile_sha256 is not None
        selected_config_ref = ArtifactRef(
            artifact_id=config_input.artifact_id,
            kind="foundry.calibration_config",
            media_type="application/json",
            manifest_profile_sha256=config_input.manifest_profile_sha256,
        )
        selected_config_manifest = store.get_manifest(selected_config_ref)
        default_config_manifest = store.get_manifest(config_input.artifact_id)
        assert selected_config_manifest.inputs == []
        assert default_config_manifest.inputs[0].role == "test_profile_collision_control"
    else:
        assert config_input.manifest_profile_sha256 is not None
    persisted_config_payload = from_canonical_bytes(store.get_bytes(config_input.artifact_id))
    assert CalibrationConfig.model_validate(persisted_config_payload) == config_before_run
    if caller_configs is None:
        assert config == config_before_run
    new_artifact_ids = {str(item) for item in store.iter_artifact_ids()} - artifact_ids_before_run
    basis_input = next(
        item for item in report_manifest.inputs if item.role == "calibration_execution_input_basis"
    )
    assert basis_input.manifest_profile_sha256 is not None
    basis_ref = ArtifactRef(
        artifact_id=basis_input.artifact_id,
        kind="foundry.calibration_execution_input_basis",
        media_type="application/json",
        manifest_profile_sha256=basis_input.manifest_profile_sha256,
    )
    basis = load_calibration_execution_input_basis(store, basis_ref)
    state_manifest = store.get_manifest(basis.base_state_snapshot_ref)
    state_blob_inputs = [edge for edge in state_manifest.inputs if edge.role == "state_blob"]
    assert len(state_blob_inputs) == 1
    assert new_artifact_ids <= {
        str(config_input.artifact_id),
        str(report_ref.artifact_id),
        str(basis_ref.artifact_id),
        str(basis.base_state_snapshot_ref.artifact_id),
        str(state_blob_inputs[0].artifact_id),
    }
    required_new_artifacts = {str(basis_ref.artifact_id)}
    if not seed_competing_profile:
        required_new_artifacts.add(str(config_input.artifact_id))
    assert required_new_artifacts <= new_artifact_ids
    assert basis.input_capture_status == "content_bound"
    assert all(item.status == "content_bound" for item in basis.parameter_inputs)
    assert all(item.source_status == "selected_source_matched" for item in basis.parameter_inputs)
    assert basis.program_graph_status == "selected_source_matched"
    assert basis.exec_plan_source_status == "selected_source_matched"
    assert basis.base_state_source_status == "selected_source_matched"
    assert (
        str(basis.base_state_snapshot_ref.artifact_id),
        basis.base_state_snapshot_ref.kind,
        basis.base_state_snapshot_ref.media_type,
        basis.base_state_snapshot_ref.manifest_profile_sha256,
    ) == (
        str(source_basis.base_state_snapshot_ref.artifact_id),
        source_basis.base_state_snapshot_ref.kind,
        source_basis.base_state_snapshot_ref.media_type,
        source_basis.base_state_snapshot_ref.manifest_profile_sha256,
    )
    persisted_payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    persisted = CalibrationReport.model_validate(persisted_payload)
    assert persisted == report
    assert persisted.schema_version == "2.0"
    if not hessian_enabled:
        assert persisted.uncertainties is None
        assert persisted.coordinate_projection is None
        assert persisted.coordinate_projection_status == "not_established"
        assert persisted.uncertainty_envelopes is None
    elif incomplete_projection:
        assert persisted.coordinate_projection is None
        assert persisted.coordinate_projection_status == "incomplete"
        assert persisted.uncertainty_envelopes is None
    else:
        for field_name in ("A.rate", "B.rate"):
            persisted_envelope = persisted_payload["uncertainty_envelopes"][field_name]
            assert "confidence_level" in persisted_envelope
            assert persisted_envelope["confidence_level"] is None
        assert persisted.coordinate_projection is not None
        assert persisted.coordinate_projection.field_order == ("A.rate", "B.rate")
    _B197_REPLAY_BY_STORE_ROOT[str(store.root)] = _b197_replay_report(
        store,
        source_basis,
        report_ref,
        persisted,
    )
    return report_ref, persisted


def _b197_execute_calibration_source(
    tmp_path,
    *,
    slot_registry_override=None,
    target_metric_path="government_balance",
    target_aggregation="none",
    caller_inputs_out=None,
):
    """Build the real compile→execute→calibrate→execute source join for B197."""
    store = FileSystemCAS(tmp_path)
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    state = GlobalState.empty(n_agents=2, n_firms=1)
    state = state.replace(
        agents=state.agents.replace(
            active=jnp.asarray([True, True]),
            income=jnp.asarray([10.0, 10.0]),
            reported_income=jnp.asarray([10.0, 10.0]),
        ),
        government_balance=jnp.asarray(-2.0),
        tax_rate=jnp.asarray(0.125),
    )
    snapshot = put_state_snapshot(store, state=state, step=0, return_selected_profile=True)
    state_ref = StateSnapshotRef.model_validate(snapshot.model_dump(mode="python"))
    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(state_ref, role="data_ref")],
        ),
        return_selected_profile=True,
    )
    selected_data_snapshot_ref = DataSnapshotRef.model_validate(
        data_snapshot_ref.model_dump(mode="python")
    )
    bindings = build_input_bindings(
        store,
        data_snapshot_ref=selected_data_snapshot_ref,
        registry_bundle_ref=registry.bundle_ref,
        return_selected_profile=True,
    )
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="b197_source", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="b197_source",
            interventions=[
                {
                    "intervention_id": "a",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": "==",
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": "0.5"},
                }
            ],
        ),
        model_spec=ModelSpec(
            model_id="b197_source",
            data_snapshot_ref=str(selected_data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    candidate = PolicyCandidateSchema.from_trinity_bundle(
        policy,
        candidate_id="b197_source_candidate",
        metadata={"evidence_grade": "candidate", "purpose": "controlled test fixture"},
    )
    candidate_ref = persist_policy_candidate_schema(
        store,
        candidate,
        inputs=[
            input_ref_from_artifact_ref(
                selected_data_snapshot_ref,
                role="world_model_data_snapshot",
            ),
            input_ref_from_artifact_ref(registry.bundle_ref, role="world_model_registry"),
        ],
        return_selected_profile=True,
    )
    selected_policy_ref = persist_trinity_bundle_artifact(
        _ensure_ir_artifact_store(store),
        policy,
        inputs=[input_ref_from_artifact_ref(candidate_ref, role="policy_candidate")],
    )
    policy_ref = ArtifactRef.model_validate(selected_policy_ref.model_dump(mode="python"))
    compiled = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=policy_ref,
            registry_bundle_ref=registry.bundle_ref,
            return_selected_profile=True,
        ),
    )
    assert compiled.ok
    initial_execution = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compiled.exec_plan_ref,
            input_bindings_ref=bindings.input_bindings_ref,
            registry_bundle_ref=registry.bundle_ref,
            exec_config=FoundryExecConfig(seed=29),
            return_selected_profile=True,
        ),
    )
    assert initial_execution.ok
    assert initial_execution.simulation_result_ref is not None
    initial_admission = admit_execution_source(store, initial_execution.simulation_result_ref)
    assert initial_admission.basis is not None
    source_basis = initial_admission.basis
    graph = ProgramGraph.model_validate(
        from_canonical_bytes(store.get_bytes(source_basis.program_graph_ref))
    )
    plan = ExecPlan.model_validate(
        from_canonical_bytes(store.get_bytes(source_basis.exec_plan_ref))
    )
    registry_content = load_registry_bundle_content(store, source_basis.runtime_registry_ref)
    base_state = load_state_snapshot(store, snapshot_ref=source_basis.base_state_snapshot_ref)
    mechanism_node = next(node for node in graph.nodes if node.mechanism_type == "income_tax")

    def load_selected_parameters(source):
        if isinstance(source, ArtifactRef):
            return from_canonical_bytes(store.get_bytes(source))
        return {}

    inputs = CalibratorInputs(
        config=CalibrationConfig(
            targets=[
                CalibrationTarget(
                    target_id="balance",
                    model_metric_path=target_metric_path,
                    aggregation=target_aggregation,
                    loss={"relative": False},
                )
            ],
            trainables=[TrainableParamRef(param_id="rate", node_id=mechanism_node.node_id)],
            max_steps=2,
            learning_rate=0.01,
            hessian={"enabled": True, "damping": 1e-6},
            seed=29,
        ),
        program_graph=graph,
        exec_plan=plan,
        base_state=base_state,
        mechanism_registry=registry_content.mechanism_registry,
        slot_registry=slot_registry_override or registry_content.slot_registry,
        merge_registry=registry_content.merge_registry,
        selector_field_registry=registry_content.selector_field_registry,
        parameter_loader=load_selected_parameters,
        raw_targets={"balance": jnp.asarray([0.0])},
        controls_seq=jnp.arange(1),
        constraint_registry=registry_content.constraint_registry,
        registry_bundle_ref=source_basis.runtime_registry_ref,
        mechanism_registry_ref=source_basis.runtime_registry_members.mechanism_registry,
        units_registry=registry_content.units_registry,
        units_registry_ref=source_basis.runtime_registry_members.units_registry,
        base_state_snapshot_ref=source_basis.base_state_snapshot_ref,
        exec_plan_ref=source_basis.exec_plan_ref,
    )
    if caller_inputs_out is not None:
        caller_inputs_out.append(inputs)
    report, report_ref = Calibrator(inputs).run_and_persist(store)
    basis_edge = next(
        edge
        for edge in store.get_manifest(report_ref).inputs
        if edge.role == "calibration_execution_input_basis"
    )
    basis_ref = ArtifactRef(
        artifact_id=basis_edge.artifact_id,
        kind="foundry.calibration_execution_input_basis",
        media_type="application/json",
        manifest_profile_sha256=basis_edge.manifest_profile_sha256,
    )
    captured_basis = load_calibration_execution_input_basis(store, basis_ref)
    override = build_parameter_override_bundle(report)
    assert override is not None
    override_ref = store.put_json(
        override,
        PutOptions(
            kind=ParameterOverrideBundle.ARTIFACT_KIND,
            media_type=ParameterOverrideBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ParameterOverrideBundle.ARTIFACT_SCHEMA_NAME,
                version=ParameterOverrideBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(report_ref, role="calibration_report")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    replay = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=source_basis.exec_plan_ref,
            input_bindings_ref=source_basis.input_bindings_ref,
            registry_bundle_ref=source_basis.runtime_registry_ref,
            parameter_override_bundle_ref=ParameterOverrideBundleRef.model_validate(
                override_ref.model_dump(mode="python")
            ),
            exec_config=FoundryExecConfig(seed=29),
            return_selected_profile=True,
        ),
    )
    assert replay.ok
    assert replay.simulation_result_ref is not None
    return (
        store,
        registry.bundle_ref,
        report,
        report_ref,
        captured_basis,
        replay.simulation_result_ref,
        mechanism_node.node_id,
        source_basis,
    )


def test_calibrator_preserves_selected_config_profile_through_fresh_consumers(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    caller_configs: list[CalibrationConfig] = []
    run_configs: list[CalibrationConfig] = []
    writer_configs: list[CalibrationConfig] = []
    config_refs = []
    run_calls = 0
    original_run = Calibrator.run
    original_put_config = calibrator_module.put_calibration_config

    def mutate_caller_then_run(calibrator: Calibrator) -> CalibrationReport:
        nonlocal run_calls
        run_calls += 1
        assert len(caller_configs) == 1
        caller_configs[0].schema_version = "9.9"
        run_configs.append(calibrator.inputs.config.model_copy(deep=True))
        return original_run(calibrator)

    def capture_config_write(store_arg, config_arg, **kwargs):
        writer_configs.append(config_arg.model_copy(deep=True))
        config_ref = original_put_config(store_arg, config_arg, **kwargs)
        config_refs.append(config_ref)
        return config_ref

    monkeypatch.setattr(Calibrator, "run", mutate_caller_then_run)
    monkeypatch.setattr(calibrator_module, "put_calibration_config", capture_config_write)
    report_ref, report = _run_b197_tied_calibrator(
        store,
        seed_competing_profile=True,
        caller_configs=caller_configs,
    )

    assert run_calls == 1
    assert len(config_refs) == 1
    assert caller_configs[0].schema_version == "9.9"
    assert run_configs[0].schema_version == "0.1"
    assert writer_configs[0] == run_configs[0]
    config_ref = config_refs[0]
    assert config_ref.manifest_profile_sha256 is not None
    report_manifest = store.get_manifest(report_ref)
    config_edges = [item for item in report_manifest.inputs if item.role == "calibration_config"]
    assert len(config_edges) == 1
    assert config_edges[0] == input_ref_from_artifact_ref(
        config_ref,
        role="calibration_config",
    )
    assert config_edges[0].artifact_id == config_ref.artifact_id
    assert config_edges[0].manifest_profile_sha256 == config_ref.manifest_profile_sha256

    selected_config_manifest = store.get_manifest(config_ref)
    assert selected_config_manifest.inputs == []
    persisted_config = CalibrationConfig.model_validate(
        from_canonical_bytes(store.get_bytes(config_ref.artifact_id))
    )
    assert persisted_config == writer_configs[0]
    exact_lineage = resolve_dependency_graph(store, report_ref)
    assert exact_lineage.is_complete
    selected_config_nodes = [
        node
        for node in exact_lineage.nodes.values()
        if str(node.artifact_id) == str(config_ref.artifact_id)
        and node.role == "calibration_config"
    ]
    assert len(selected_config_nodes) == 1
    assert selected_config_nodes[0].manifest_profile_sha256 == config_ref.manifest_profile_sha256

    sim_ref = _b197_simulation_result(store)
    _, welfare_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_selected_config_profile",
        method="delta",
        weights=[1.0, 1.0],
    )
    assert welfare_bundle.point_estimate == pytest.approx(2.0)

    profileless_report_ref = put_calibration_report(
        store,
        report,
        inputs=[
            InputRef(
                artifact_id=config_ref.artifact_id,
                role="calibration_config",
            )
        ],
    )
    assert profileless_report_ref.artifact_id == report_ref.artifact_id
    assert profileless_report_ref.manifest_profile_sha256 is not None
    profileless_manifest = store.get_manifest(profileless_report_ref)
    profileless_edge = next(
        item for item in profileless_manifest.inputs if item.role == "calibration_config"
    )
    assert profileless_edge.artifact_id == config_ref.artifact_id
    assert profileless_edge.role == "calibration_config"
    assert profileless_edge.manifest_profile_sha256 is None
    profileless_lineage = resolve_dependency_graph(store, profileless_report_ref)
    assert not profileless_lineage.is_complete
    refused_config_nodes = [
        node
        for node in profileless_lineage.nodes.values()
        if str(node.artifact_id) == str(config_ref.artifact_id)
        and node.role == "calibration_config"
    ]
    assert len(refused_config_nodes) == 1
    assert refused_config_nodes[0].status.value == "missing_manifest"


def test_b197_source_join_requires_selected_parameter_bytes_and_fresh_consumer_agreement(
    tmp_path,
) -> None:
    (
        store,
        registry_ref,
        report,
        report_ref,
        basis,
        simulation_ref,
        node_id,
        _initial_basis,
    ) = _b197_execute_calibration_source(tmp_path)
    assert report.coordinate_projection_status == "complete"
    assert basis.input_capture_status == "content_bound"
    assert basis.program_graph_status == "selected_source_matched"
    assert basis.exec_plan_source_status == "selected_source_matched"
    assert basis.base_state_source_status == "selected_source_matched"
    base_state_binding = next(
        item for item in basis.runtime_input_roster if item.input_name == "base_state"
    )
    assert base_state_binding.status == "selected_source_matched"
    assert base_state_binding.value_sha256 == base_state_binding.source_payload_sha256
    assert base_state_binding.value_sha256 != basis.base_state_checksum_sha256
    assert basis.registry_bundle_status == "selected_source_matched"
    assert basis.mechanism_registry_status == "selected_source_matched"
    assert basis.unit_registry_status == "selected_source_matched"
    assert len(basis.parameter_inputs) == 1
    parameter_input = basis.parameter_inputs[0]
    assert parameter_input.source_status == "selected_source_matched"
    assert parameter_input.source_payload_sha256 == parameter_input.payload_sha256
    assert report.calibrated_params.keys() == {f"{node_id}.rate"}

    source_join = _calibration_execution_source_join(
        _b197_execution_context(store, registry_ref, "R_b197_direct_source_join"),
        _b197_execution_state(simulation_ref, report_ref),
        report_ref=report_ref,
        report=report,
    )
    assert source_join[0] == "matched", source_join

    _outcome, positive_bundle = _run_b197_welfare(
        store,
        registry_ref,
        simulation_ref,
        report_ref,
        run_id="R_b197_source_join_positive",
        method="delta",
        labels=[node_id],
        weights=[1.0],
    )
    positive_report_id = ArtifactID.model_validate(
        positive_bundle.diagnostics["propagation_report_ref"]
    )
    positive_report = from_canonical_bytes(store.get_bytes(positive_report_id))
    assert positive_report["source_execution_status"] == "matched", positive_report
    assert (
        "calibration_external_source_attestation_not_established"
        in positive_report["source_execution_limitations"]
    )
    assert (
        "calibration_unit_definition_not_established"
        in positive_report["source_execution_limitations"]
    )
    assert (
        "calibration_physical_time_semantics_not_established"
        in positive_report["source_execution_limitations"]
    )
    assert (
        "calibration_noise_law_not_established" in positive_report["source_execution_limitations"]
    )
    assert (
        "calibration_authority_not_established" in positive_report["source_execution_limitations"]
    )

    selected_report_manifest = store.get_manifest(report_ref)
    config_edge = next(
        edge for edge in selected_report_manifest.inputs if edge.role == "calibration_config"
    )
    missing_basis_report_ref = put_calibration_report(
        store,
        report,
        inputs=[config_edge],
    )
    missing_basis_status = _calibration_execution_source_join(
        _b197_execution_context(store, registry_ref, "R_b197_source_join_missing_basis"),
        _b197_execution_state(simulation_ref, missing_basis_report_ref),
        report_ref=missing_basis_report_ref,
        report=report,
    )
    assert missing_basis_status[0] == "not_established"
    assert "source_execution_not_established" in missing_basis_status[1]
    assert not missing_basis_status[2]

    fake_basis_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("f" * 64),
        kind="foundry.calibration_execution_input_basis",
        media_type="application/json",
    )
    fake_basis_report_ref = put_calibration_report(
        store,
        report,
        inputs=[
            config_edge,
            input_ref_from_artifact_ref(
                fake_basis_ref,
                role="calibration_execution_input_basis",
            ),
        ],
    )
    fake_basis_status = _calibration_execution_source_join(
        _b197_execution_context(store, registry_ref, "R_b197_source_join_fake_basis"),
        _b197_execution_state(simulation_ref, fake_basis_report_ref),
        report_ref=fake_basis_report_ref,
        report=report,
    )
    assert fake_basis_status[0] == "mismatch"
    assert fake_basis_status[2] == ("calibration_execution_basis_invalid",)

    changed_override = build_parameter_override_bundle(report)
    assert changed_override is not None
    changed_override.overrides[node_id]["rate"] += 0.01
    changed_override_ref = store.put_json(
        changed_override,
        PutOptions(
            kind=ParameterOverrideBundle.ARTIFACT_KIND,
            media_type=ParameterOverrideBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ParameterOverrideBundle.ARTIFACT_SCHEMA_NAME,
                version=ParameterOverrideBundle.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(report_ref, role="calibration_report")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    changed_replay = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=_initial_basis.exec_plan_ref,
            input_bindings_ref=_initial_basis.input_bindings_ref,
            registry_bundle_ref=_initial_basis.runtime_registry_ref,
            parameter_override_bundle_ref=ParameterOverrideBundleRef.model_validate(
                changed_override_ref.model_dump(mode="python")
            ),
            exec_config=FoundryExecConfig(seed=29),
            return_selected_profile=True,
        ),
    )
    assert changed_replay.ok
    assert changed_replay.simulation_result_ref is not None
    changed_status = _calibration_execution_source_join(
        _b197_execution_context(store, registry_ref, "R_b197_source_join_changed_override"),
        _b197_execution_state(changed_replay.simulation_result_ref, report_ref),
        report_ref=report_ref,
        report=report,
    )
    assert changed_status[0] == "mismatch"
    assert "calibration_execution_parameter_overrides_mismatch" in changed_status[2]


def test_runtime_input_binding_recomputes_selected_registry_content() -> None:
    from polisyos.foundry.calibration.execution_basis import (
        CalibrationRuntimeInputBinding,
        canonical_input_sha256,
        reconcile_selected_runtime_input,
    )
    from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY

    selected = DEFAULT_SLOT_REGISTRY
    selected_spec = selected.slots["government.balance"]
    altered_spec = selected_spec.model_copy(update={"state_path": "agents.income"})
    altered = selected.model_copy(
        update={
            "slots": {
                **selected.slots,
                "government.balance": altered_spec,
            }
        }
    )
    selected_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("a" * 64),
        kind="ir.slot_registry",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    binding = CalibrationRuntimeInputBinding(
        input_name="slot_registry",
        usage="fit_required",
        source_role="runtime_registry_member",
        status="selected_source_mismatch",
        value_sha256=canonical_input_sha256(altered),
        source_ref=selected_ref,
        source_payload_sha256=canonical_input_sha256(selected),
    )

    assert (
        reconcile_selected_runtime_input(
            binding,
            selected_ref=selected_ref,
            selected_value=selected,
        )
        == "mismatch"
    )


def test_runtime_input_binding_recomputes_selected_base_state_value() -> None:
    from polisyos.foundry.calibration.execution_basis import canonical_input_sha256

    selected = GlobalState.empty(n_agents=1, n_firms=1).replace(tax_rate=jnp.asarray(0.125))
    altered = selected.replace(tax_rate=jnp.asarray(0.25))
    selected_ref = ArtifactRef(
        artifact_id=ArtifactID.from_sha256_hex("a" * 64),
        kind="foundry.state_snapshot",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    limitations: set[str] = set()

    binding = calibrator_module._runtime_input_binding(
        name="base_state",
        usage="fit_required",
        source_role="selected_base_state_snapshot",
        value=altered,
        active=True,
        selected_ref=selected_ref,
        selected_value=selected,
        limitations=limitations,
    )

    assert binding.status == "selected_source_mismatch"
    assert binding.source_ref == selected_ref
    assert binding.value_sha256 == canonical_input_sha256(altered)
    assert binding.source_payload_sha256 == canonical_input_sha256(selected)
    assert "runtime_input_selected_source_mismatch:base_state" in limitations


def test_calibration_state_blob_checksum_refuses_corrupt_bytes(tmp_path) -> None:
    from polisyos.core.artifacts.store import ArtifactIntegrityError

    store = FileSystemCAS(tmp_path)
    snapshot_ref = put_state_snapshot(
        store,
        state=GlobalState.empty(n_agents=1, n_firms=1),
        step=0,
        return_selected_profile=True,
    )
    snapshot_manifest = store.get_manifest(snapshot_ref)
    state_blob_edge = next(edge for edge in snapshot_manifest.inputs if edge.role == "state_blob")
    blob_path, _manifest_path = store._paths(state_blob_edge.artifact_id)
    blob_path.write_bytes(b"corrupt state bytes")

    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        calibrator_module._state_snapshot_blob_digest(store, snapshot_ref)


def test_persisted_basis_uses_pre_fit_input_snapshot(tmp_path, monkeypatch) -> None:
    from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY

    caller_inputs: list[CalibratorInputs] = []
    original_run = Calibrator.run
    altered_spec = DEFAULT_SLOT_REGISTRY.slots["government.balance"].model_copy(
        update={"state_path": "agents.income"}
    )
    altered_slots = DEFAULT_SLOT_REGISTRY.model_copy(
        update={
            "slots": {
                **DEFAULT_SLOT_REGISTRY.slots,
                "government.balance": altered_spec,
            }
        }
    )

    def mutate_caller_after_fit(self):
        report = original_run(self)
        assert caller_inputs
        caller_inputs[0].slot_registry = altered_slots
        return report

    monkeypatch.setattr(Calibrator, "run", mutate_caller_after_fit)
    (
        store,
        registry_ref,
        report,
        report_ref,
        basis,
        simulation_ref,
        _node_id,
        _initial_basis,
    ) = _b197_execute_calibration_source(
        tmp_path,
        target_metric_path="government.balance",
        target_aggregation="sum",
        caller_inputs_out=caller_inputs,
    )
    slot_binding = next(
        item for item in basis.runtime_input_roster if item.input_name == "slot_registry"
    )
    assert slot_binding.status == "selected_source_matched"
    assert slot_binding.value_sha256 == slot_binding.source_payload_sha256
    source_join = _calibration_execution_source_join(
        _b197_execution_context(store, registry_ref, "R_b197_pre_fit_input_snapshot"),
        _b197_execution_state(simulation_ref, report_ref),
        report_ref=report_ref,
        report=report,
    )
    assert source_join[0] == "matched", source_join


def test_fresh_welfare_recomputes_complete_runtime_registry_member_content(tmp_path) -> None:
    from polisyos.foundry.calibration.execution_basis import (
        CALIBRATION_RUNTIME_INPUT_NAMES,
        CalibrationExecutionInputBasis,
        CalibrationRuntimeInputBinding,
        canonical_input_sha256,
        put_calibration_execution_input_basis,
    )
    from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY

    original_spec = DEFAULT_SLOT_REGISTRY.slots["government.balance"]
    altered_spec = original_spec.model_copy(
        update={"description": "Government balance stock (content probe)"}
    )
    assert altered_spec.description != original_spec.description
    assert altered_spec.scope == original_spec.scope
    assert altered_spec.value_type == original_spec.value_type
    assert altered_spec.unit == original_spec.unit
    assert altered_spec.kind == original_spec.kind
    assert altered_spec.state_path == original_spec.state_path == "government_balance"
    assert altered_spec.reset_rule == original_spec.reset_rule
    altered_slot_registry = DEFAULT_SLOT_REGISTRY.model_copy(
        update={
            "slots": {
                **DEFAULT_SLOT_REGISTRY.slots,
                "government.balance": altered_spec,
            }
        }
    )
    (
        store,
        registry_ref,
        report,
        report_ref,
        basis,
        simulation_ref,
        _node_id,
        initial_basis,
    ) = _b197_execute_calibration_source(
        tmp_path,
        slot_registry_override=altered_slot_registry,
        target_metric_path="government.balance",
        target_aggregation="sum",
    )
    assert tuple(item.input_name for item in basis.runtime_input_roster) == (
        CALIBRATION_RUNTIME_INPUT_NAMES
    )
    slot_binding = next(
        item for item in basis.runtime_input_roster if item.input_name == "slot_registry"
    )
    selected_registry = load_registry_bundle_content(store, registry_ref)
    selected_slot_digest = canonical_input_sha256(selected_registry.slot_registry)
    assert basis.registry_bundle_ref == initial_basis.runtime_registry_ref
    assert slot_binding.source_ref == initial_basis.runtime_registry_members.slot_registry
    assert slot_binding.status == "selected_source_mismatch"
    assert slot_binding.source_payload_sha256 == selected_slot_digest
    assert slot_binding.value_sha256 == canonical_input_sha256(altered_slot_registry)
    assert slot_binding.value_sha256 != slot_binding.source_payload_sha256

    original_welfare = _run_b197_welfare(
        store,
        registry_ref,
        simulation_ref,
        report_ref,
        run_id="R_b197_runtime_slot_mismatch",
        method="delta",
        labels=["income_tax"],
        weights=[1.0],
    )[1]
    original_report_ref = ArtifactID.model_validate(
        original_welfare.diagnostics["propagation_report_ref"]
    )
    original_report = from_canonical_bytes(store.get_bytes(original_report_ref))
    assert original_report["source_execution_status"] == "mismatch", original_report

    # Falsify the producer's status while keeping the digest declaration and
    # every schema marker valid. The fresh consumer must still resolve and hash
    # the actual selected member bytes.
    false_match = CalibrationRuntimeInputBinding(
        **{
            **slot_binding.model_dump(mode="python"),
            "status": "selected_source_matched",
            "source_payload_sha256": slot_binding.value_sha256,
        }
    )
    false_roster = tuple(
        false_match if item.input_name == "slot_registry" else item
        for item in basis.runtime_input_roster
    )
    false_basis = CalibrationExecutionInputBasis.model_validate(
        {
            **basis.model_dump(mode="python"),
            "input_capture_status": "content_bound",
            "runtime_input_limitations": (),
            "runtime_input_roster": false_roster,
        }
    )
    basis_edge = next(
        edge
        for edge in store.get_manifest(report_ref).inputs
        if edge.role == "calibration_execution_input_basis"
    )
    basis_ref = ArtifactRef(
        artifact_id=basis_edge.artifact_id,
        kind="foundry.calibration_execution_input_basis",
        media_type="application/json",
        manifest_profile_sha256=basis_edge.manifest_profile_sha256,
    )
    false_basis_ref = put_calibration_execution_input_basis(
        store,
        false_basis,
        inputs=store.get_manifest(basis_ref).inputs,
    )
    config_edge = next(
        edge for edge in store.get_manifest(report_ref).inputs if edge.role == "calibration_config"
    )
    false_report_ref = put_calibration_report(
        store,
        report,
        inputs=[
            config_edge,
            input_ref_from_artifact_ref(
                false_basis_ref,
                role="calibration_execution_input_basis",
            ),
        ],
    )
    false_match_welfare = _run_b197_welfare(
        store,
        registry_ref,
        simulation_ref,
        false_report_ref,
        run_id="R_b197_runtime_slot_false_match",
        method="delta",
        labels=["income_tax"],
        weights=[1.0],
    )[1]
    false_match_output_ref = ArtifactID.model_validate(
        false_match_welfare.diagnostics["propagation_report_ref"]
    )
    false_match_output = from_canonical_bytes(store.get_bytes(false_match_output_ref))
    assert false_match_output["source_execution_status"] == "mismatch", false_match_output


def _b197_execution_context(store, registry_ref, run_id):
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.welfare.{run_id}"),
    )


def _b197_execution_state(simulation_ref, report_ref):
    return ExperimentState(
        run_id="R_b197_execution_source_join",
        inputs={INPUT_CALIBRATION_REPORT_REF: report_ref},
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: simulation_ref},
    )


def test_unassigned_calibration_field_stays_typed_partial_at_welfare_boundary(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    report_ref, report = _run_b197_tied_calibrator(store, incomplete_projection=True)
    assert report.coordinate_projection_status == "incomplete"
    assert report.uncertainty_envelopes is None
    sim_ref = _b197_simulation_result(store)

    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_incomplete_projection",
        method="delta",
        weights=[1.0, 1.0],
    )

    assert bundle.credible_interval is None
    assert bundle.status.value == "partial"
    assert "calibration_projection_incomplete" in bundle.warnings
    report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    manifest = store.get_manifest(report_id)
    assert any(
        item.role == "calibration_report" and str(item.artifact_id) == str(report_ref.artifact_id)
        for item in manifest.inputs
    )
    outer_ref = outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    outer_manifest = store.get_manifest(outer_ref.artifact_id)
    assert any(
        item.role == "calibration_report" and str(item.artifact_id) == str(report_ref.artifact_id)
        for item in outer_manifest.inputs
    )


def _b197_simulation_result(store: FileSystemCAS) -> SimulationResultRef:
    replay = _B197_REPLAY_BY_STORE_ROOT.get(str(store.root))
    if replay is not None:
        return replay
    source = _build_b197_tied_execution_source(store)
    return source["initial_simulation_ref"]


def _b197_dependence_structure_ref(
    store: FileSystemCAS,
    correlation_matrix: list[list[float]],
    parameter_order: list[str] | None = None,
):
    return persist_dependence_structure(
        _ensure_ir_artifact_store(store),
        build_dependence_structure(
            regime="panel",
            class_label="gaussian_copula",
            calibrated=True,
            recommended_covariance="cluster",
            source_method="b197_test_correlation",
            metadata={
                "parameter_order": parameter_order or ["A.rate", "B.rate"],
                "correlation_matrix": correlation_matrix,
            },
        ),
    )


def _run_b197_welfare(
    store: FileSystemCAS,
    registry_ref: ArtifactRefModel,
    sim_ref: SimulationResultRef,
    report_ref: ArtifactRef | None,
    *,
    run_id: str,
    method: str,
    weights: list[float],
    labels: list[str] | None = None,
    input_envelopes: dict[str, dict[str, object]] | None = None,
    dependence_structure_ref: dict[str, object] | None = None,
    welfare_config_overrides: dict[str, object] | None = None,
    require_success: bool = True,
) -> tuple[object, object | None]:
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.welfare.{run_id}"),
    )
    response_labels = labels or ["A", "B"]
    pe_sensitivity = {label: {f"{label}.rate": 1.0} for label in response_labels}
    if "C" in response_labels:
        pe_sensitivity["C"] = {"C.rate": 1.0}
    config: dict[str, object] = {
        "metric_order": response_labels,
        "pe_response": dict.fromkeys(response_labels, 1.0),
        "weights": weights,
        "pe_sensitivity": pe_sensitivity,
        "credible_method": method,
    }
    if input_envelopes is not None:
        config["input_envelopes"] = input_envelopes
    if dependence_structure_ref is not None:
        config["dependence_structure_ref"] = dependence_structure_ref
    config.update(welfare_config_overrides or {})
    input_refs = {INPUT_CALIBRATION_REPORT_REF: report_ref} if report_ref is not None else {}
    state = ExperimentState(
        run_id=run_id,
        inputs=input_refs,
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_ref},
        params={
            "welfare_config": config,
            "propagation_config": {
                "preferred_method": method,
                "delta_covariance_jitter": 1e-6,
                "mc_n_samples": 100,
                "mc_min_valid_samples": 50,
                "mc_seed": 0,
            },
        },
    )
    outcome = PropagateWelfareNode().execute(ctx, state)
    if outcome.status != "ok":
        if require_success:
            pytest.fail(f"welfare node did not succeed: {outcome.error}")
        return outcome, None
    bundle = load_welfare_bundle(
        _ensure_ir_artifact_store(store),
        outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF],
    )
    return outcome, bundle


def _run_b194_draw_execution_case(
    tmp_path,
    monkeypatch,
    simulation_fn,
    *,
    run_id: str,
    require_success: bool = True,
):
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    envelope_ref = _persist_empirical_welfare_envelope(store, (-1.0, 1.0))

    def build_simulation_fn(
        _ctx,
        *,
        context,
        available_envelopes,
        ge_condition_number_threshold,
    ):
        del context
        del ge_condition_number_threshold
        assert set(available_envelopes.envelopes) == {"C.rate"}
        return (
            simulation_fn,
            {"C.rate": 0.0},
            dict(available_envelopes.envelopes),
            {"C.rate": envelope_ref},
        )

    monkeypatch.setattr(
        propagate_welfare_module,
        "_build_simulation_fn",
        build_simulation_fn,
    )
    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        _b197_simulation_result(store),
        None,
        run_id=run_id,
        method="monte_carlo",
        weights=[1.0],
        labels=["C"],
        input_envelopes={"C.rate": envelope_ref.model_dump(mode="json")},
        require_success=require_success,
    )
    return store, outcome, bundle


def _core_artifact_ref(ref: ArtifactRef | ArtifactRefModel) -> ArtifactRef:
    """Normalize an IR reference while retaining its selected manifest view."""
    if isinstance(ref, ArtifactRef):
        return ref
    return ArtifactRef.model_validate(ref.model_dump(mode="python"))


def _manifest_has_input(
    store: FileSystemCAS,
    target_ref: ArtifactRef | ArtifactRefModel | ArtifactID | str,
    source_ref: ArtifactRef | ArtifactRefModel | InputRef,
    role: str,
) -> bool:
    manifest_ref = (
        _core_artifact_ref(target_ref)
        if isinstance(target_ref, (ArtifactRef, ArtifactRefModel))
        else target_ref
    )
    manifest = store.get_manifest(manifest_ref)
    source_profile = source_ref.manifest_profile_sha256
    return any(
        item.role == role
        and str(item.artifact_id) == str(source_ref.artifact_id)
        and item.manifest_profile_sha256 == source_profile
        for item in manifest.inputs
    )


def test_calibrator_tied_report_reaches_delta_and_monte_carlo_welfare(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    report_ref, report = _run_b197_tied_calibrator(store)
    assert report.uncertainty_envelopes is not None
    assert report.uncertainty_envelopes["A.rate"].metadata["covariance_row"] == pytest.approx(
        [0.0025, 0.0025], rel=0, abs=1e-9
    )
    sim_ref = _b197_simulation_result(store)

    delta_outcome, delta_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_tied_delta",
        method="delta",
        weights=[1.0, 1.0],
    )
    assert delta_bundle.point_estimate == pytest.approx(2.0)
    assert delta_bundle.diagnostics["delta_std"] == pytest.approx(0.1, rel=1e-4)
    delta_report_id = ArtifactID.model_validate(delta_bundle.diagnostics["propagation_report_ref"])
    delta_report = from_canonical_bytes(store.get_bytes(delta_report_id))
    assert delta_report["schema_version"] == "2.0"
    assert delta_report["covariance_order"] == ["A.rate", "B.rate"]
    assert delta_report["calibration_report_schema_version"] == "2.0"
    assert delta_report["calibration_projection_schema_version"] == "1.0"
    assert delta_report["uncertainty_status"] == "candidate"
    assert delta_report["independence_source_validated"] is False
    assert _manifest_has_input(
        store,
        ArtifactRef(
            artifact_id=delta_report_id,
            kind="foundry.welfare_propagation_report",
            media_type="application/json",
        ),
        report_ref,
        "calibration_report",
    )
    delta_bundle_ref = delta_outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    assert _manifest_has_input(
        store,
        delta_bundle_ref,
        report_ref,
        "calibration_report",
    )
    np.testing.assert_allclose(
        delta_report["covariance"],
        [[0.0025, 0.0025], [0.0025, 0.0025]],
        rtol=1e-6,
        atol=1e-9,
    )

    mc_outcome, mc_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_tied_mc_contrast",
        method="monte_carlo",
        weights=[1.0, -1.0],
    )
    assert mc_bundle.sample_bundle_ref is not None
    samples = load_welfare_sample_bundle(
        _ensure_ir_artifact_store(store), mc_bundle.sample_bundle_ref
    )
    assert len(samples.welfare_draws) == 100
    assert samples.metadata["calibration_covariance_order"] == ["A.rate", "B.rate"]
    assert samples.metadata["calibration_projection_schema_version"] == "1.0"
    assert samples.metadata["uncertainty_status"] == "candidate"
    assert samples.metadata["independence_source_validated"] is False
    assert _manifest_has_input(
        store,
        mc_bundle.sample_bundle_ref,
        report_ref,
        "calibration_report",
    )
    mc_report_id = ArtifactID.model_validate(mc_bundle.diagnostics["propagation_report_ref"])
    mc_report = from_canonical_bytes(store.get_bytes(mc_report_id))
    assert (
        mc_report["dependence_sampling"]["strategy"] == "calibration_report_optimizer_coordinates"
    )
    assert mc_report["dependence_sampling"]["preserves_singular_ties"] is True
    mc_report_ref = ArtifactRef(
        artifact_id=mc_report_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
    )
    assert _manifest_has_input(store, mc_report_ref, report_ref, "calibration_report")
    assert _manifest_has_input(
        store,
        mc_report_ref,
        mc_bundle.sample_bundle_ref,
        "sample_bundle",
    )
    mc_bundle_ref = mc_outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    assert _manifest_has_input(store, mc_bundle_ref, report_ref, "calibration_report")
    np.testing.assert_allclose(
        samples.metadata["calibration_covariance_matrix"],
        [[0.0025, 0.0025], [0.0025, 0.0025]],
        rtol=1e-6,
        atol=1e-9,
    )
    np.testing.assert_allclose(
        samples.welfare_draws,
        np.zeros(100),
        atol=1e-8,
        rtol=0,
    )

    # Reopen every producer artifact through a distinct CAS reader. The writer-side
    # objects above are not the consumer receipt for this source-to-welfare chain.
    fresh_store = FileSystemCAS(tmp_path)
    fresh_ir_store = _ensure_ir_artifact_store(fresh_store)
    fresh_calibration = CalibrationReport.model_validate(
        from_canonical_bytes(fresh_store.get_bytes(report_ref))
    )
    assert fresh_calibration.coordinate_projection is not None
    assert fresh_calibration.coordinate_projection.field_order == ("A.rate", "B.rate")
    assert fresh_calibration.uncertainty_envelopes is not None
    assert fresh_calibration.uncertainty_envelopes["A.rate"].metadata[
        "covariance_row"
    ] == pytest.approx([0.0025, 0.0025], rel=0, abs=1e-9)

    fresh_delta_ref = ArtifactRef(
        artifact_id=delta_report_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
    )
    fresh_delta_report = from_canonical_bytes(fresh_store.get_bytes(fresh_delta_ref))
    assert fresh_delta_report["covariance_order"] == ["A.rate", "B.rate"]
    np.testing.assert_allclose(
        fresh_delta_report["covariance"],
        [[0.0025, 0.0025], [0.0025, 0.0025]],
        rtol=1e-6,
        atol=1e-9,
    )
    fresh_delta_bundle_ref = delta_outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    fresh_delta_bundle = load_welfare_bundle(fresh_ir_store, fresh_delta_bundle_ref)
    assert fresh_delta_bundle.point_estimate == pytest.approx(2.0)
    assert _manifest_has_input(fresh_store, fresh_delta_ref, report_ref, "calibration_report")
    assert _manifest_has_input(
        fresh_store, fresh_delta_bundle_ref, report_ref, "calibration_report"
    )

    fresh_mc_samples = load_welfare_sample_bundle(fresh_ir_store, mc_bundle.sample_bundle_ref)
    assert len(fresh_mc_samples.welfare_draws) == 100
    assert fresh_mc_samples.metadata["calibration_covariance_order"] == ["A.rate", "B.rate"]
    np.testing.assert_allclose(
        fresh_mc_samples.metadata["calibration_covariance_matrix"],
        [[0.0025, 0.0025], [0.0025, 0.0025]],
        rtol=1e-6,
        atol=1e-9,
    )
    np.testing.assert_allclose(fresh_mc_samples.welfare_draws, np.zeros(100), atol=1e-8, rtol=0)
    fresh_mc_report_ref = ArtifactRef(
        artifact_id=mc_report_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
    )
    fresh_mc_report = from_canonical_bytes(fresh_store.get_bytes(fresh_mc_report_ref))
    assert fresh_mc_report["dependence_sampling"]["strategy"] == (
        "calibration_report_optimizer_coordinates"
    )
    assert _manifest_has_input(fresh_store, fresh_mc_report_ref, report_ref, "calibration_report")
    assert _manifest_has_input(
        fresh_store, fresh_mc_report_ref, mc_bundle.sample_bundle_ref, "sample_bundle"
    )
    fresh_mc_bundle_ref = mc_outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    fresh_mc_bundle = load_welfare_bundle(fresh_ir_store, fresh_mc_bundle_ref)
    assert fresh_mc_bundle.status == mc_bundle.status
    assert _manifest_has_input(fresh_store, fresh_mc_bundle_ref, report_ref, "calibration_report")


def test_real_calibration_display_level_preserves_persisted_welfare_law(
    tmp_path,
) -> None:
    """Display-only Hessian ranges preserve the persisted law and remain non-authoritative."""
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    report_ref, produced_report = _run_b197_tied_calibrator(store)
    assert produced_report.coordinate_projection_status == "complete"
    assert produced_report.uncertainty_envelopes is not None
    produced_envelope = produced_report.uncertainty_envelopes["A.rate"]
    assert isinstance(produced_envelope.distribution_payload, ParametricFitCarrier)
    producer_std = float(produced_envelope.distribution_payload.parameters["std"])

    # The adapter starts from the real persisted Calibrator report, not a hand-built report.
    fresh_store = FileSystemCAS(tmp_path)
    report_manifest = fresh_store.get_manifest(report_ref)
    config_inputs = [item for item in report_manifest.inputs if item.role == "calibration_config"]
    assert len(config_inputs) == 1
    persisted_config = CalibrationConfig.model_validate(
        from_canonical_bytes(fresh_store.get_bytes(config_inputs[0].artifact_id))
    )
    assert persisted_config.hessian.enabled is True
    persisted_report = CalibrationReport.model_validate(
        from_canonical_bytes(fresh_store.get_bytes(report_ref.artifact_id))
    )
    assert persisted_report == produced_report
    assert persisted_report.coordinate_projection_status == "complete"
    assert persisted_report.coordinate_projection is not None
    assert persisted_report.uncertainties is not None
    assert _manifest_has_input(fresh_store, report_ref, config_inputs[0], "calibration_config")

    sim_ref = _b197_simulation_result(fresh_store)
    observations: list[tuple[float, float, tuple[float, float], str, tuple[str, ...]]] = []
    display_widths: list[float] = []
    carrier_parameters: list[dict[str, float]] = []
    display_envelope_refs: list[UncertaintyEnvelopeRef] = []
    for display_level in (0.8, 0.95):
        envelope = envelope_from_calibration_param(
            persisted_report,
            "A.rate",
            confidence_level=display_level,
        )
        assert envelope is not None
        assert isinstance(envelope.distribution_payload, ParametricFitCarrier)
        assert envelope.distribution_payload.family is DistributionFamily.NORMAL
        numeric_policy = envelope.numeric_policy
        expected_mean = numeric_policy.canonicalize(persisted_report.calibrated_params["A.rate"])
        expected_std = numeric_policy.canonicalize(producer_std)
        assert expected_mean is not None
        assert expected_std is not None
        assert envelope.distribution_payload.parameters == {
            "mean": expected_mean,
            "std": expected_std,
        }
        metadata_std = envelope.metadata["std"]
        assert isinstance(metadata_std, float)
        assert numeric_policy.canonicalize(metadata_std) == expected_std
        carrier_parameters.append(dict(envelope.distribution_payload.parameters))
        assert envelope.metadata["requested_confidence_level"] == display_level
        assert envelope.confidence_level is None
        assert envelope.interval_semantics is IntervalSemantics.HEURISTIC_RANGE
        assert envelope.is_heuristic_ci is True
        assert envelope.gate_eligible is False
        display_widths.append(envelope.ci_width)

        envelope_ref = persist_uncertainty_envelope(
            _ensure_ir_artifact_store(fresh_store),
            envelope,
            inputs=[input_ref_from_artifact_ref(report_ref, role="calibration_report")],
        )
        persisted_envelope = load_uncertainty_envelope(
            _ensure_ir_artifact_store(fresh_store),
            envelope_ref,
        )
        assert persisted_envelope == envelope
        display_envelope_refs.append(envelope_ref)
        assert _manifest_has_input(
            fresh_store,
            envelope_ref,
            report_ref,
            "calibration_report",
        )

        outcome, bundle = _run_b197_welfare(
            fresh_store,
            registry_ref,
            sim_ref,
            None,
            run_id=f"R_b198_display_level_{int(display_level * 100)}",
            method="delta",
            weights=[1.0],
            labels=["A"],
            input_envelopes={"A.rate": envelope_ref.model_dump(mode="json")},
        )
        assert outcome.status == "ok"
        assert bundle is not None
        assert bundle.credible_interval is not None
        assert bundle.status.value == "partial"
        assert bundle.warnings == [
            "ge_operator_missing_pe_only",
            "input_uncertainty_not_gate_eligible",
        ]
        propagation_report_id = ArtifactID.model_validate(
            bundle.diagnostics["propagation_report_ref"]
        )
        report_refs = [
            ref
            for ref in outcome.artifacts
            if str(ref.artifact_id) == str(propagation_report_id)
            and ref.kind == "foundry.welfare_propagation_report"
        ]
        assert len(report_refs) == 1
        propagation_report_ref = report_refs[0]
        selected_report_manifest = fresh_store.get_manifest(
            _core_artifact_ref(propagation_report_ref)
        )
        selected_envelope_inputs = [
            item for item in selected_report_manifest.inputs if item.role == "input_envelope.A.rate"
        ]
        assert len(selected_envelope_inputs) == 1
        assert str(selected_envelope_inputs[0].artifact_id) == str(envelope_ref.artifact_id)
        assert (
            selected_envelope_inputs[0].manifest_profile_sha256
            == envelope_ref.manifest_profile_sha256
        )
        assert _manifest_has_input(
            fresh_store,
            propagation_report_ref,
            envelope_ref,
            "input_envelope.A.rate",
        )

        bundle_ref = outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
        selected_bundle_manifest = fresh_store.get_manifest(_core_artifact_ref(bundle_ref))
        selected_report_inputs = [
            item for item in selected_bundle_manifest.inputs if item.role == "propagation_report"
        ]
        assert len(selected_report_inputs) == 1
        assert str(selected_report_inputs[0].artifact_id) == str(propagation_report_ref.artifact_id)
        assert (
            selected_report_inputs[0].manifest_profile_sha256
            == propagation_report_ref.manifest_profile_sha256
        )

        if display_level == 0.95:
            default_report_ref = ArtifactRef(
                artifact_id=propagation_report_ref.artifact_id,
                kind=propagation_report_ref.kind,
                media_type=propagation_report_ref.media_type,
            )
            assert default_report_ref.manifest_profile_sha256 is None
            default_report_manifest = fresh_store.get_manifest(default_report_ref)
            default_envelope_inputs = [
                item
                for item in default_report_manifest.inputs
                if item.role == "input_envelope.A.rate"
            ]
            assert len(default_envelope_inputs) == 1
            assert str(default_envelope_inputs[0].artifact_id) == str(
                display_envelope_refs[0].artifact_id
            )
            assert (
                default_envelope_inputs[0].manifest_profile_sha256
                == display_envelope_refs[0].manifest_profile_sha256
            )
            assert str(default_envelope_inputs[0].artifact_id) != str(envelope_ref.artifact_id)
            assert not _manifest_has_input(
                fresh_store,
                default_report_ref,
                envelope_ref,
                "input_envelope.A.rate",
            )
        observations.append(
            (
                float(bundle.diagnostics["delta_std"]),
                bundle.point_estimate,
                bundle.credible_interval,
                bundle.status.value,
                tuple(bundle.warnings),
            )
        )

    assert display_widths[0] < display_widths[1]
    assert carrier_parameters[0] == carrier_parameters[1]
    assert observations[0][0] == pytest.approx(observations[1][0], rel=1e-12, abs=1e-12)
    assert observations[0][1] == pytest.approx(observations[1][1], rel=1e-12, abs=1e-12)
    np.testing.assert_allclose(observations[0][2], observations[1][2], rtol=1e-12, atol=1e-12)
    assert observations[0][3:] == observations[1][3:]


def test_hessian_disabled_producer_refuses_welfare_without_inventing_interval(
    tmp_path,
) -> None:
    """A genuine no-carrier report yields the observed explicit skip, never a guessed interval."""
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    report_ref, produced_report = _run_b197_tied_calibrator(store, hessian_enabled=False)
    assert produced_report.uncertainties is None
    assert produced_report.coordinate_projection is None
    assert produced_report.coordinate_projection_status == "not_established"
    assert produced_report.uncertainty_envelopes is None

    fresh_store = FileSystemCAS(tmp_path)
    report_manifest = fresh_store.get_manifest(report_ref)
    config_inputs = [item for item in report_manifest.inputs if item.role == "calibration_config"]
    assert len(config_inputs) == 1
    persisted_config = CalibrationConfig.model_validate(
        from_canonical_bytes(fresh_store.get_bytes(config_inputs[0].artifact_id))
    )
    assert persisted_config.hessian.enabled is False
    assert _manifest_has_input(fresh_store, report_ref, config_inputs[0], "calibration_config")
    persisted_report = CalibrationReport.model_validate(
        from_canonical_bytes(fresh_store.get_bytes(report_ref.artifact_id))
    )
    assert persisted_report.uncertainties is None
    assert persisted_report.coordinate_projection is None
    assert persisted_report.coordinate_projection_status == "not_established"
    assert persisted_report.uncertainty_envelopes is None

    selected_simulation_ref = _b197_simulation_result(fresh_store)
    source_join = _calibration_execution_source_join(
        _b197_execution_context(fresh_store, registry_ref, "R_b198_source_join_probe"),
        _b197_execution_state(selected_simulation_ref, report_ref),
        report_ref=report_ref,
        report=persisted_report,
    )
    assert source_join[0] == "matched", source_join

    outcome, bundle = _run_b197_welfare(
        fresh_store,
        registry_ref,
        selected_simulation_ref,
        report_ref,
        run_id="R_b198_hessian_disabled_no_carrier",
        method="delta",
        weights=[1.0, 1.0],
        require_success=False,
    )

    assert outcome.status == "skip", outcome
    assert outcome.error is None
    assert outcome.skip_blocker is None
    assert len(outcome.events) == 1
    event = outcome.events[0]
    assert event.level == "info"
    assert event.code is None
    assert event.attrs == {}
    assert event.message == "No PE or GE uncertainty supplied; skip welfare propagation"
    assert outcome.artifacts == []
    assert bundle is None
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index
    assert ARTIFACT_SIMULATION_RESULT_REF in outcome.state.artifacts_index
    retained_report_ref = outcome.state.inputs[INPUT_CALIBRATION_REPORT_REF]
    assert retained_report_ref == report_ref


@pytest.mark.parametrize("method", ["delta", "monte_carlo"])
@pytest.mark.parametrize(
    (
        "correlation_profile",
        "labels",
        "expected_point",
        "expected_unsupported_fields",
        "expected_correlated_fields",
    ),
    [
        (
            "calibration_to_external",
            ["A", "B"],
            2.0,
            ["B.rate"],
            ["A.rate", "B.rate"],
        ),
        (
            "external_to_external",
            ["A", "B", "C"],
            3.0,
            ["C.rate"],
            ["A.rate", "B.rate", "C.rate"],
        ),
    ],
    ids=["calibration-external", "external-external"],
)
def test_welfare_withholds_mixed_marginal_pearson_covariance(
    tmp_path,
    method: str,
    correlation_profile: str,
    labels: list[str],
    expected_point: float,
    expected_unsupported_fields: list[str],
    expected_correlated_fields: list[str],
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    source_report_ref, source_report = _run_b197_tied_calibrator(store)
    assert source_report.coordinate_projection is not None
    assert source_report.uncertainty_envelopes is not None

    # Keep one normal calibrated coordinate in the persisted report. External
    # fields cover both the direct calibration-to-extra pair and the
    # extra-to-extra boundary of the consumed joint block.
    single_field_payload = source_report.model_dump(mode="python")
    single_field_payload["calibrated_params"] = {
        "A.rate": source_report.calibrated_params["A.rate"]
    }
    single_field_payload["coordinate_projection"] = {
        "field_order": ["A.rate"],
        "coordinate_order": list(source_report.coordinate_projection.coordinate_order),
        "matrix": [list(source_report.coordinate_projection.matrix[0])],
    }
    single_field_payload["uncertainty_envelopes"] = {
        "A.rate": source_report.uncertainty_envelopes["A.rate"].model_dump(mode="python")
    }
    single_field_report = CalibrationReport.model_validate(single_field_payload)
    report_ref = put_calibration_report(
        store,
        single_field_report,
        inputs=_b197_legacy_report_inputs(store, source_report_ref),
    )
    assert store.get_manifest(report_ref).artifact_schema.version == "2.0"
    assert any(item.role == "calibration_config" for item in store.get_manifest(report_ref).inputs)

    uniform = UncertaintyEnvelope(
        point_estimate=0.5,
        confidence_interval=(0.0, 1.0),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=False,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.UNIFORM,
            parameters={"low": 0.0, "high": 1.0},
            support=(0.0, 1.0),
        ),
        metadata={"param_name": "B.rate", "std": 1.0 / math.sqrt(12.0)},
    )
    uniform_ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(store), uniform)
    input_envelope_refs = {"B.rate": uniform_ref.model_dump(mode="json")}
    if correlation_profile == "calibration_to_external":
        dependence_ref = _b197_dependence_structure_ref(
            store,
            [[1.0, 0.5], [0.5, 1.0]],
            parameter_order=["A.rate", "B.rate"],
        )
        calibration_envelope = source_report.uncertainty_envelopes["A.rate"]
        calibration_distribution = calibration_envelope.distribution_payload
        assert isinstance(calibration_distribution, ParametricFitCarrier)
        calibration_std = float(calibration_distribution.parameters["std"])
        expected_pairs = [("A.rate", "B.rate", 0.5 * calibration_std / math.sqrt(12.0), 1e-12)]
    else:
        normal = UncertaintyEnvelope(
            point_estimate=0.5,
            confidence_interval=(0.2, 0.8),
            confidence_level=None,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
            is_heuristic_ci=True,
            gate_eligible=False,
            distribution_payload=ParametricFitCarrier(
                family=DistributionFamily.NORMAL,
                parameters={"mean": 0.5, "std": 0.1},
            ),
            metadata={"param_name": "B.rate", "std": 0.1},
        )
        normal_ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(store), normal)
        input_envelope_refs = {
            "B.rate": normal_ref.model_dump(mode="json"),
            "C.rate": uniform_ref.model_dump(mode="json"),
        }
        dependence_ref = _b197_dependence_structure_ref(
            store,
            [
                [1.0, 0.2, 0.0],
                [0.2, 1.0, 0.5],
                [0.0, 0.5, 1.0],
            ],
            parameter_order=["A.rate", "B.rate", "C.rate"],
        )
        # The report-derived A.rate marginal is produced in JAX float32 and
        # later projected as float64; its source precision bounds this tiny pair.
        expected_pairs = [
            (
                "A.rate",
                "C.rate",
                -3.2698671302839551e-18,
                float(np.finfo(np.float32).eps),
            ),
            ("B.rate", "C.rate", 0.5 * 0.1 / math.sqrt(12.0), 1e-12),
        ]
    sim_ref = _b197_simulation_result(store)

    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id=f"R_b197_mixed_marginal_{method}",
        method=method,
        weights=[1.0] * len(labels),
        labels=labels,
        input_envelopes=input_envelope_refs,
        dependence_structure_ref=dependence_ref.model_dump(mode="json"),
    )

    assert bundle.point_estimate == pytest.approx(expected_point)
    assert bundle.status.value == "partial"
    assert bundle.credible_interval is None
    assert bundle.sample_bundle_ref is None
    assert "calibration_mixed_marginal_covariance_unsupported" in bundle.warnings

    propagation_report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    propagation_report = from_canonical_bytes(store.get_bytes(propagation_report_id))
    assert propagation_report["limitation_code"] == (
        "calibration_mixed_marginal_covariance_unsupported"
    )
    resolution = propagation_report["dependence_resolution"]
    assert resolution["unsupported_marginal_fields"] == expected_unsupported_fields
    assert resolution["correlated_fields"] == expected_correlated_fields
    assert resolution["covariance_order"] == sorted(set(input_envelope_refs) | {"A.rate"})
    observed_pairs = {
        (pair["left_field"], pair["right_field"]): pair["covariance"]
        for pair in resolution["nonzero_covariance_pairs"]
    }
    expected_pair_map = {
        (left, right): (covariance_value, relative_tolerance)
        for left, right, covariance_value, relative_tolerance in expected_pairs
    }
    assert set(observed_pairs) == set(expected_pair_map)
    for pair, (covariance_value, relative_tolerance) in expected_pair_map.items():
        assert observed_pairs[pair] == pytest.approx(
            covariance_value,
            rel=relative_tolerance,
            abs=0.0,
        )
    assert resolution["dependence_structure_ref"] == str(dependence_ref.artifact_id)

    propagation_report_ref = ArtifactRef(
        artifact_id=propagation_report_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
    )
    assert _manifest_has_input(store, propagation_report_ref, report_ref, "calibration_report")
    bundle_ref = outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    assert _manifest_has_input(store, bundle_ref, report_ref, "calibration_report")


def _b197_profile_envelope(
    field_name: str,
    *,
    family: DistributionFamily,
    std: float,
    covariance_order: list[str],
    covariance_row: list[float],
    point: float = 0.5,
) -> UncertaintyEnvelope:
    if family is DistributionFamily.NORMAL:
        return UncertaintyEnvelope(
            point_estimate=point,
            confidence_interval=(point - 2.0 * std, point + 2.0 * std),
            confidence_level=None,
            distribution_family=family,
            source=UncertaintySource.CALIBRATION,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
            is_heuristic_ci=True,
            gate_eligible=False,
            distribution_payload=ParametricFitCarrier(
                family=family,
                parameters={"mean": point, "std": std},
            ),
            metadata={
                "param_name": field_name,
                "std": std,
                "covariance_params": covariance_order,
                "covariance_row": covariance_row,
            },
        )

    low = point - math.sqrt(3.0) * std
    high = point + math.sqrt(3.0) * std
    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(low, high),
        confidence_level=None,
        distribution_family=family,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=False,
        distribution_payload=ParametricFitCarrier(
            family=family,
            parameters={"low": low, "high": high},
            support=(low, high),
        ),
        metadata={
            "param_name": field_name,
            "std": std,
            "covariance_params": covariance_order,
            "covariance_row": covariance_row,
        },
    )


def _b197_persist_covariance_profile_report(
    store: FileSystemCAS,
    *,
    fields: list[str],
    standard_deviations: list[float],
    families: list[DistributionFamily],
    covariance: np.ndarray,
) -> tuple[ArtifactRef, CalibrationReport]:
    source_ref, source_report = _run_b197_tied_calibrator(store)
    assert source_report.uncertainties is not None
    assert len(fields) == len(standard_deviations) == len(families)
    assert covariance.shape == (len(fields), len(fields))
    covariance_order = list(fields)
    correlation = covariance / np.outer(standard_deviations, standard_deviations)
    field_values = source_report.calibrated_params
    fallback_value = float(field_values.get("B.rate", 0.5))
    report_payload = source_report.model_dump(mode="python")
    report_payload["calibrated_params"] = {
        field: float(field_values.get(field, fallback_value)) for field in fields
    }
    report_payload["uncertainties"] = CalibrationUncertainty(
        method=source_report.uncertainties.method,
        params=fields,
        covariance=covariance.tolist(),
        correlation=correlation.tolist(),
        std=standard_deviations,
        damping=source_report.uncertainties.damping,
        hessian_rank=len(fields),
        hessian_condition=float(np.linalg.cond(covariance)),
        non_identifiable=[],
    ).model_dump(mode="python")
    report_payload["coordinate_projection"] = {
        "field_order": fields,
        "coordinate_order": fields,
        "matrix": np.eye(len(fields)).tolist(),
    }
    report_payload["coordinate_projection_status"] = "complete"
    report_payload["identifiability"] = None

    envelopes: dict[str, UncertaintyEnvelope] = {}
    for index, (field, family, std) in enumerate(
        zip(fields, families, standard_deviations, strict=True)
    ):
        envelopes[field] = _b197_profile_envelope(
            field,
            family=family,
            std=std,
            covariance_order=covariance_order,
            covariance_row=covariance[index].tolist(),
            point=float(report_payload["calibrated_params"][field]),
        )
    report_payload["uncertainty_envelopes"] = {
        field: envelope.model_dump(mode="python") for field, envelope in envelopes.items()
    }
    report_payload["uncertainty_envelope_refs"] = None

    report = CalibrationReport.model_validate(report_payload)
    report_ref = put_calibration_report(
        store,
        report,
        inputs=_b197_legacy_report_inputs(store, source_ref),
    )
    return report_ref, report


@pytest.mark.parametrize("method", ["delta", "monte_carlo"])
@pytest.mark.parametrize(
    ("scale_profile", "standard_deviations"),
    [
        ("scale_diverse", [1.0e4, 1.0e4, 1.0e-3]),
        ("scale_preserving", [1.0, 1.0, 1.0]),
    ],
    ids=["scale-diverse", "scale-preserving"],
)
def test_welfare_withholds_scale_diverse_mixed_marginal_covariance(
    tmp_path,
    method: str,
    scale_profile: str,
    standard_deviations: list[float],
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    correlation = np.asarray(
        [
            [1.0, 0.2, 0.2],
            [0.2, 1.0, 0.5],
            [0.2, 0.5, 1.0],
        ],
        dtype=np.float64,
    )
    assert float(np.linalg.det(correlation)) == pytest.approx(0.71)
    assert float(np.linalg.eigvalsh(correlation).min()) > 0.0
    covariance = correlation * np.outer(standard_deviations, standard_deviations)
    assert float(np.linalg.eigvalsh(covariance).min()) > 0.0

    report_ref, report = _b197_persist_covariance_profile_report(
        store,
        fields=["A.rate"],
        standard_deviations=[standard_deviations[0]],
        families=[DistributionFamily.NORMAL],
        covariance=np.asarray([[covariance[0, 0]]], dtype=np.float64),
    )
    external_fields = ["B.rate", "C.rate"]
    external_families = [DistributionFamily.NORMAL, DistributionFamily.UNIFORM]
    external_refs = {}
    for index, field in enumerate(external_fields, start=1):
        envelope = _b197_profile_envelope(
            field,
            family=external_families[index - 1],
            std=standard_deviations[index],
            covariance_order=external_fields,
            covariance_row=list(covariance[index, 1:]),
        )
        external_refs[field] = persist_uncertainty_envelope(
            _ensure_ir_artifact_store(store), envelope
        ).model_dump(mode="json")

    dependence_ref = _b197_dependence_structure_ref(
        store,
        correlation.tolist(),
        parameter_order=["A.rate", *external_fields],
    )
    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        _b197_simulation_result(store),
        report_ref,
        run_id=f"R_b197_scale_profile_{scale_profile}_{method}",
        method=method,
        labels=["A", "B", "C"],
        weights=[1.0, 1.0, 1.0],
        input_envelopes=external_refs,
        dependence_structure_ref=dependence_ref.model_dump(mode="json"),
    )

    # The fixture simulation has one unit metric for each requested label.
    expected_point = math.fsum([1.0 for _ in ("A", "B", "C")])
    assert bundle.point_estimate == pytest.approx(expected_point)
    assert bundle.credible_interval is None
    assert bundle.sample_bundle_ref is None
    assert bundle.status.value == "partial"
    assert "calibration_mixed_marginal_covariance_unsupported" in bundle.warnings

    propagation_report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    propagation_report = from_canonical_bytes(store.get_bytes(propagation_report_id))
    resolution = propagation_report["dependence_resolution"]
    assert propagation_report["limitation_code"] == (
        "calibration_mixed_marginal_covariance_unsupported"
    )
    assert resolution["covariance_order"] == ["A.rate", "B.rate", "C.rate"]
    assert resolution["covariance_predicate"] == ("exact_nonzero_in_admitted_finite_matrix")
    assert resolution["unsupported_marginal_fields"] == ["C.rate"]
    assert resolution["correlated_fields"] == ["A.rate", "B.rate", "C.rate"]
    observed_pairs = {
        (item["left_field"], item["right_field"]): item["covariance"]
        for item in resolution["nonzero_covariance_pairs"]
    }
    assert observed_pairs == {
        ("A.rate", "C.rate"): pytest.approx(covariance[0, 2]),
        ("B.rate", "C.rate"): pytest.approx(covariance[1, 2]),
    }
    assert resolution["dependence_structure_ref"] == str(dependence_ref.artifact_id)
    assert _manifest_has_input(
        store,
        ArtifactRef(
            artifact_id=propagation_report_id,
            kind="foundry.welfare_propagation_report",
            media_type="application/json",
        ),
        report_ref,
        "calibration_report",
    )
    bundle_ref = outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    assert _manifest_has_input(store, bundle_ref, report_ref, "calibration_report")


@pytest.mark.parametrize("method", ["delta", "monte_carlo"])
def test_welfare_reports_non_normal_calibration_coordinate_capability(
    tmp_path,
    method: str,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    standard_deviations = [1.0e4, 1.0e-3]
    covariance = np.diag(np.square(standard_deviations))
    report_ref, report = _b197_persist_covariance_profile_report(
        store,
        fields=["A.rate", "C.rate"],
        standard_deviations=standard_deviations,
        families=[DistributionFamily.NORMAL, DistributionFamily.UNIFORM],
        covariance=covariance,
    )

    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        _b197_simulation_result(store),
        report_ref,
        run_id=f"R_b197_independent_nonnormal_{method}",
        method=method,
        labels=["A", "C"],
        weights=[1.0, 1.0],
    )

    # The fixture simulation has one unit metric for each requested label.
    expected_point = math.fsum([1.0 for _ in ("A", "C")])
    assert bundle.point_estimate == pytest.approx(expected_point)
    assert "calibration_mixed_marginal_covariance_unsupported" not in bundle.warnings
    propagation_report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    propagation_report = from_canonical_bytes(store.get_bytes(propagation_report_id))
    if method == "delta":
        # Delta consumes the diagonal marginal variances without inventing a
        # dependence term; the zero off-diagonal profile is admissible here.
        assert bundle.credible_interval is not None
        assert bundle.sample_bundle_ref is None
        assert propagation_report.get("limitation_code") != (
            "calibration_mixed_marginal_covariance_unsupported"
        )
    else:
        # The report-coordinate Monte Carlo sampler currently admits only
        # Normal calibration coordinates. Preserve the honest typed limitation;
        # this fixture does not prove a production Uniform calibration producer.
        assert bundle.status.value == "partial"
        assert bundle.credible_interval is None
        assert bundle.sample_bundle_ref is None
        assert propagation_report["limitation_code"] == (
            "calibration_coordinate_distribution_unsupported"
        )
        assert propagation_report["dependence_resolution"]["uncovered_params"] == [
            "A.rate",
            "C.rate",
        ]
    bundle_ref = outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    assert _manifest_has_input(store, bundle_ref, report_ref, "calibration_report")


def test_monte_carlo_samples_independent_external_uniform_marginal_without_calibration(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    envelope = UncertaintyEnvelope(
        point_estimate=0.5,
        confidence_interval=(0.0, 1.0),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.MANUAL,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=False,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.UNIFORM,
            parameters={"low": 0.0, "high": 1.0},
            support=(0.0, 1.0),
        ),
        metadata={"param_name": "C.rate", "std": 1.0 / math.sqrt(12.0)},
    )
    envelope_ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(store), envelope)
    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        _b197_simulation_result(store),
        None,
        run_id="R_b197_external_uniform_mc",
        method="monte_carlo",
        labels=["C"],
        weights=[1.0],
        input_envelopes={"C.rate": envelope_ref.model_dump(mode="json")},
    )

    assert outcome.status == "ok"
    assert bundle.credible_interval is not None
    assert bundle.sample_bundle_ref is not None
    assert bundle.point_estimate == pytest.approx(1.0)
    samples = load_welfare_sample_bundle(_ensure_ir_artifact_store(store), bundle.sample_bundle_ref)
    assert len(samples.welfare_draws) == 100
    assert all(math.isfinite(value) for value in samples.welfare_draws)
    # The one declared external marginal is sampled independently as Uniform[0, 1].
    assert min(samples.welfare_draws) < 0.65
    assert max(samples.welfare_draws) > 1.35


def test_delta_report_binds_selected_input_envelope_profile_through_fresh_cas_readback(
    tmp_path,
) -> None:
    store = _RecordingFileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    envelope = UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-2.0, 2.0),
        confidence_level=None,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.MANUAL,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.NORMAL,
            parameters={"mean": 0.0, "std": 1.0},
        ),
        metadata={"param_name": "C.rate", "std": 1.0},
    )
    selected_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store),
        envelope,
        return_selected_profile=True,
    )
    assert selected_ref.manifest_profile_sha256 is not None

    core_profile_payload_ref = store.put_json(
        envelope.model_dump(mode="python", round_trip=True),
        PutOptions(
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            schema=SchemaInfo(
                name="ir.uncertainty_envelope",
                version=UncertaintyEnvelope.SCHEMA_VERSION,
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, max_depth=64),
        return_selected_profile=True,
    )
    core_profile_ref = UncertaintyEnvelopeRef.model_validate(
        core_profile_payload_ref.model_dump(mode="python")
    )
    assert core_profile_ref.artifact_id == selected_ref.artifact_id
    assert core_profile_ref.manifest_profile_sha256 != selected_ref.manifest_profile_sha256

    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        _b197_simulation_result(store),
        None,
        run_id="R_welfare_delta_selected_envelope_profile",
        method="delta",
        labels=["C"],
        weights=[1.0],
        input_envelopes={"C.rate": selected_ref.model_dump(mode="json")},
    )

    assert outcome.status == "ok"
    assert bundle.credible_interval is not None
    propagation_report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    report_ref = ArtifactRef(
        artifact_id=propagation_report_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
    )
    report_manifest = store.get_manifest(report_ref)
    input_rows = [
        item
        for item in report_manifest.inputs
        if item.role == "input_envelope.C.rate"
        and str(item.artifact_id) == str(selected_ref.artifact_id)
    ]
    assert len(input_rows) == 1
    assert input_rows[0].manifest_profile_sha256 == selected_ref.manifest_profile_sha256
    assert any(
        getattr(selector, "manifest_profile_sha256", None) == selected_ref.manifest_profile_sha256
        for selector in store.read_selectors
    )

    fresh_store = _RecordingFileSystemCAS(tmp_path)
    assert fresh_store.get_bytes(core_profile_ref.artifact_id) == fresh_store.get_bytes(
        selected_ref.artifact_id
    )
    from polisyos.ir.model_layer.canon import CanonViolation

    with pytest.raises(CanonViolation, match="ir_owned_artifact_profile_refused"):
        load_uncertainty_envelope(_ensure_ir_artifact_store(fresh_store), core_profile_ref)

    fresh_report = from_canonical_bytes(fresh_store.get_bytes(report_ref))
    assert fresh_report["schema_version"] == "1.0"
    fresh_manifest = fresh_store.get_manifest(report_ref)
    assert any(
        item.role == "input_envelope.C.rate"
        and item.manifest_profile_sha256 == selected_ref.manifest_profile_sha256
        for item in fresh_manifest.inputs
    )
    selected_envelope = load_uncertainty_envelope(
        _ensure_ir_artifact_store(fresh_store), selected_ref
    )
    assert selected_envelope.point_estimate == envelope.point_estimate
    assert any(
        getattr(selector, "manifest_profile_sha256", None) == selected_ref.manifest_profile_sha256
        for selector in fresh_store.read_selectors
    )

    corrupt_ref = selected_ref.model_copy(
        update={"manifest_profile_sha256": "sha256:" + ("0" * 64)}
    )
    with pytest.raises(CanonViolation, match="ir_owned_artifact_read_refused"):
        load_uncertainty_envelope(_ensure_ir_artifact_store(fresh_store), corrupt_ref)


def test_partial_welfare_draws_retain_terminal_outcomes_after_fresh_cas_readback(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    envelope = UncertaintyEnvelope(
        point_estimate=0.0,
        confidence_interval=(-1.0, 1.0),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.MANUAL,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=True,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.UNIFORM,
            parameters={"low": -1.0, "high": 1.0},
            support=(-1.0, 1.0),
        ),
        metadata={"param_name": "C.rate", "std": 1.0 / math.sqrt(3.0)},
    )
    envelope_ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(store), envelope)

    def build_failing_simulation_fn(
        _ctx,
        *,
        context,
        available_envelopes,
        ge_condition_number_threshold,
    ):
        del context
        del ge_condition_number_threshold
        assert set(available_envelopes.envelopes) == {"C.rate"}

        def simulation_fn(**params: float) -> dict[str, object]:
            rate = float(params["C.rate"])
            if rate < -0.75:
                raise propagate_welfare_module.WelfareSampleDomainError(
                    "the evaluator does not support this sampled input",
                    predicate_id="test.c_rate.lower_domain_bound",
                )
            value = 1.0 if rate == 0.0 else 2.0
            return {
                "welfare": value,
                "welfare_pe": value,
                "welfare_pe_components": (value,),
                "welfare_total_components": (value,),
                "welfare_ge": 0.0,
            }

        return (
            simulation_fn,
            {"C.rate": 0.0},
            dict(available_envelopes.envelopes),
            {"C.rate": envelope_ref},
        )

    monkeypatch.setattr(
        propagate_welfare_module,
        "_build_simulation_fn",
        build_failing_simulation_fn,
    )
    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        _b197_simulation_result(store),
        None,
        run_id="R_b194_partial_welfare_draws",
        method="monte_carlo",
        weights=[1.0],
        labels=["C"],
        input_envelopes={"C.rate": envelope_ref.model_dump(mode="json")},
    )

    assert outcome.status == "ok"
    assert bundle.status.value == "partial"
    assert "welfare_mc_incomplete_draws" in bundle.warnings
    assert bundle.credible_interval is None
    assert bundle.sample_bundle_ref is not None
    assert bundle.point_estimate == 1.0
    assert bundle.diagnostics["point_estimate_semantics"] == "nominal_input_evaluation"
    assert "welfare_mc_partial_nominal_point_conditional_mean" in bundle.warnings

    fresh_store = FileSystemCAS(tmp_path)
    fresh_ir_store = _ensure_ir_artifact_store(fresh_store)
    sample_bundle = load_welfare_sample_bundle(fresh_ir_store, bundle.sample_bundle_ref)
    persisted_bundle = load_welfare_bundle(
        fresh_ir_store,
        outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF],
    )
    report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    report = from_canonical_bytes(fresh_store.get_bytes(report_id))
    provenance = report["draw_outcome_provenance"]
    outcomes = provenance["outcomes"]
    successful = [row for row in outcomes if row["outcome_code"] == "success"]
    failures = [row for row in outcomes if row["outcome_code"] != "success"]

    assert provenance["requested_draw_count"] == 100
    assert provenance["attempted_draw_count"] == 100
    assert provenance["successful_draw_count"] == len(sample_bundle.welfare_draws)
    assert provenance["failed_draw_count"] == len(failures) > 0
    assert provenance["unattempted_draw_count"] == 0
    assert (
        provenance["successful_draw_count"]
        + provenance["failed_draw_count"]
        + provenance["unattempted_draw_count"]
        == provenance["requested_draw_count"]
    )
    assert provenance["outcome_denominator_complete"] is True
    assert [row["draw_index"] for row in outcomes] == list(range(100))
    assert [row["sample_index"] for row in successful] == list(
        range(len(sample_bundle.welfare_draws))
    )
    assert all(row["sampled_input_sha256"] for row in outcomes)
    assert all(row["outcome_code"] == "sample_domain_inapplicable" for row in failures)
    assert all(row["error_type"] == "WelfareSampleDomainError" for row in failures)
    assert all(
        row["error_message"] == "the evaluator does not support this sampled input"
        for row in failures
    )
    assert all(row["domain_declaration_grade"] == "consumer_asserted" for row in failures)
    assert all(row["domain_predicate_id"] == "test.c_rate.lower_domain_bound" for row in failures)
    assert all(row["execution_attempt_count"] == 1 for row in failures)
    assert all(row["sample_index"] is None for row in failures)
    assert provenance["summary_semantics"] == "successful_draws_only_conditional_on_execution"
    assert report["valid_draw_count"] == len(sample_bundle.welfare_draws)
    assert report["conditional_draw_summary"]["welfare_mean"] == pytest.approx(
        sum(sample_bundle.welfare_draws) / len(sample_bundle.welfare_draws)
    )
    assert report["conditional_draw_summary"]["welfare_mean"] == 2.0
    assert "draw_summary" not in report
    assert report["schema_version"] == "1.2"
    assert sample_bundle.metadata["draw_outcome_provenance"] == provenance
    assert persisted_bundle.status.value == "partial"
    assert persisted_bundle.point_estimate == 1.0
    assert persisted_bundle.credible_interval is None
    assert persisted_bundle.sample_bundle_ref == bundle.sample_bundle_ref
    consumer_context = ExecutionContext(
        store=fresh_store,
        run=RunContext.start(
            store=fresh_store,
            registry_bundle=registry_ref,
            run_id="R_b194_partial_welfare_packet_consumer",
        ),
        logger=logging.getLogger("test.welfare.partial.packet_consumer"),
    )
    welfare_summary = _build_welfare_section(
        consumer_context,
        {ARTIFACT_WELFARE_BUNDLE_REF: outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]},
    )
    assert welfare_summary is not None
    assert welfare_summary["point_estimate"] == 1.0
    assert welfare_summary["status"] == "partial"
    assert welfare_summary["credible_interval"] is None
    assert "welfare_mc_partial_nominal_point_conditional_mean" in welfare_summary["warnings"]
    assert welfare_summary["diagnostics"]["point_estimate_semantics"] == (
        "nominal_input_evaluation"
    )
    report_manifest = fresh_store.get_manifest(report_id)
    assert any(
        item.role == "sample_bundle"
        and str(item.artifact_id) == str(bundle.sample_bundle_ref.artifact_id)
        for item in report_manifest.inputs
    )
    bundle_manifest = fresh_store.get_manifest(
        outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF].artifact_id
    )
    assert any(
        item.role == "propagation_report" and str(item.artifact_id) == str(report_id)
        for item in bundle_manifest.inputs
    )


def test_welfare_mc_retries_explicit_transient_on_same_draw_before_fresh_cas_readback(
    tmp_path,
    monkeypatch,
) -> None:
    calls: list[float] = []

    def simulation_fn(**params: float) -> dict[str, object]:
        value = float(params["C.rate"])
        calls.append(value)
        if len(calls) == 2:
            shared_context = RuntimeError("shared cause and context diagnostic")
            error = PolicyOSError(
                "temporary evaluator transport failure",
                category=ErrorCategory.TRANSIENT,
                code="evaluation.transient",
            )
            error.__cause__ = shared_context
            error.__context__ = shared_context
            raise error
        return {
            "welfare": value,
            "welfare_pe": value,
            "welfare_pe_components": (value,),
            "welfare_total_components": (value,),
            "welfare_ge": 0.0,
        }

    _store, outcome, bundle = _run_b194_draw_execution_case(
        tmp_path,
        monkeypatch,
        simulation_fn,
        run_id="R_b194_retry_same_draw",
    )

    assert outcome.status == "ok"
    assert bundle is not None
    assert "welfare_mc_incomplete_draws" not in bundle.warnings
    assert bundle.credible_interval is not None
    assert calls[1] == calls[2]

    fresh_store = FileSystemCAS(tmp_path)
    report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    report = from_canonical_bytes(fresh_store.get_bytes(report_id))
    provenance = report["draw_outcome_provenance"]
    first_draw = provenance["outcomes"][0]
    assert first_draw["outcome_code"] == "success"
    assert provenance["schema_version"] == "1.2"
    assert first_draw["execution_attempt_count"] == 2
    assert [attempt["outcome_code"] for attempt in first_draw["execution_attempts"]] == [
        "transient_retry",
        "success",
    ]
    assert {attempt["sampled_input_sha256"] for attempt in first_draw["execution_attempts"]} == {
        first_draw["sampled_input_sha256"]
    }
    assert {attempt["draw_index"] for attempt in first_draw["execution_attempts"]} == {0}
    assert [attempt["attempt_number"] for attempt in first_draw["execution_attempts"]] == [1, 2]
    assert provenance["attempted_draw_count"] == 100
    assert provenance["simulation_attempt_count"] == 101
    assert provenance["retry_attempt_count"] == 1
    assert provenance["max_attempts_per_draw"] == 2
    assert provenance["successful_draw_count"] == 100
    assert provenance["failed_draw_count"] == 0


def test_welfare_mc_persistent_transient_is_bounded_and_withholds_interval(
    tmp_path,
    monkeypatch,
) -> None:
    calls: list[float] = []

    def simulation_fn(**params: float) -> dict[str, object]:
        value = float(params["C.rate"])
        calls.append(value)
        if len(calls) in {2, 3}:
            raise PolicyOSError(
                "persistent evaluator transport failure",
                category=ErrorCategory.TRANSIENT,
                code="evaluation.transient",
            )
        return {
            "welfare": value,
            "welfare_pe": value,
            "welfare_pe_components": (value,),
            "welfare_total_components": (value,),
            "welfare_ge": 0.0,
        }

    _store, outcome, bundle = _run_b194_draw_execution_case(
        tmp_path,
        monkeypatch,
        simulation_fn,
        run_id="R_b194_retry_exhausted",
    )

    assert outcome.status == "ok"
    assert bundle is not None
    assert bundle.status.value == "partial"
    assert bundle.credible_interval is None
    assert "welfare_mc_incomplete_draws" in bundle.warnings
    assert calls[1] == calls[2]

    fresh_store = FileSystemCAS(tmp_path)
    report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    report = from_canonical_bytes(fresh_store.get_bytes(report_id))
    provenance = report["draw_outcome_provenance"]
    first_draw = provenance["outcomes"][0]
    assert first_draw["outcome_code"] == "transient_retry_exhausted"
    assert first_draw["execution_attempt_count"] == 2
    assert [attempt["outcome_code"] for attempt in first_draw["execution_attempts"]] == [
        "transient_retry",
        "transient_retry_exhausted",
    ]
    assert (
        len({attempt["sampled_input_sha256"] for attempt in first_draw["execution_attempts"]}) == 1
    )
    assert {attempt["draw_index"] for attempt in first_draw["execution_attempts"]} == {0}
    assert [attempt["attempt_number"] for attempt in first_draw["execution_attempts"]] == [1, 2]
    assert provenance["attempted_draw_count"] == 100
    assert provenance["simulation_attempt_count"] == 101
    assert provenance["retry_attempt_count"] == 1
    assert provenance["successful_draw_count"] == 99
    assert provenance["failed_draw_count"] == 1
    assert provenance["summary_semantics"] == "successful_draws_only_conditional_on_execution"
    assert "draw_summary" not in report
    assert "conditional_draw_summary" in report


def test_welfare_mc_requires_explicit_sample_domain_signal_for_partial_draw(
    tmp_path,
    monkeypatch,
) -> None:
    calls: list[float] = []
    domain_error = propagate_welfare_module.WelfareSampleDomainError

    def simulation_fn(**params: float) -> dict[str, object]:
        value = float(params["C.rate"])
        calls.append(value)
        if len(calls) == 2:
            raise domain_error(
                "sampled input is outside the evaluator's declared domain",
                predicate_id="test.c_rate.evaluator_domain",
            )
        return {
            "welfare": value,
            "welfare_pe": value,
            "welfare_pe_components": (value,),
            "welfare_total_components": (value,),
            "welfare_ge": 0.0,
        }

    _store, outcome, bundle = _run_b194_draw_execution_case(
        tmp_path,
        monkeypatch,
        simulation_fn,
        run_id="R_b194_declared_sample_domain",
    )

    assert outcome.status == "ok"
    assert bundle is not None
    assert bundle.status.value == "partial"
    assert bundle.credible_interval is None
    assert "welfare_mc_incomplete_draws" in bundle.warnings

    fresh_store = FileSystemCAS(tmp_path)
    report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    report = from_canonical_bytes(fresh_store.get_bytes(report_id))
    provenance = report["draw_outcome_provenance"]
    first_draw = provenance["outcomes"][0]
    assert first_draw["outcome_code"] == "sample_domain_inapplicable"
    assert first_draw["execution_attempt_count"] == 1
    assert first_draw["sampled_input_sha256"]
    assert first_draw["domain_declaration_grade"] == "consumer_asserted"
    assert provenance["simulation_attempt_count"] == 100
    assert provenance["retry_attempt_count"] == 0
    assert provenance["failed_draw_count"] == 1
    assert provenance["summary_semantics"] == "successful_draws_only_conditional_on_execution"
    assert "draw_summary" not in report
    assert "conditional_draw_summary" in report


@pytest.mark.parametrize(
    ("failure_case", "expected_code", "expected_scope"),
    [
        ("permission", "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE", "global"),
        ("validation", "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE", "global"),
        ("typed_fatal", "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE", "global"),
        ("typed_validation", "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE", "global"),
        ("unknown", "ERROR_WELFARE_EVALUATION_SCOPE_UNKNOWN", "unknown"),
        ("cyclic_unknown", "ERROR_WELFARE_EVALUATION_SCOPE_UNKNOWN", "unknown"),
        ("domain_cycle", "ERROR_WELFARE_EVALUATION_SCOPE_UNKNOWN", "unknown"),
        ("transient_cycle", "ERROR_WELFARE_EVALUATION_SCOPE_UNKNOWN", "unknown"),
        ("domain_wrapped_permission", "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE", "global"),
        ("deep_domain_wrapped_permission", "ERROR_WELFARE_EVALUATION_SCOPE_UNKNOWN", "unknown"),
        ("transient_wrapped_validation", "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE", "global"),
    ],
)
def test_welfare_mc_does_not_launder_global_or_unknown_failures_as_draws(
    tmp_path,
    monkeypatch,
    failure_case: str,
    expected_code: str,
    expected_scope: str,
) -> None:
    calls: list[float] = []
    domain_error = propagate_welfare_module.WelfareSampleDomainError

    def raise_validation_error() -> None:
        TypeAdapter(int).validate_python("not an integer")

    def simulation_fn(**params: float) -> dict[str, float]:
        value = float(params["C.rate"])
        calls.append(value)
        if len(calls) == 2:
            if failure_case == "permission":
                raise PermissionError("evaluator access denied")
            if failure_case == "validation":
                raise_validation_error()
            if failure_case == "typed_fatal":
                raise PolicyOSError(
                    "fatal evaluator failure",
                    category=ErrorCategory.FATAL,
                    code="evaluation.fatal",
                )
            if failure_case == "typed_validation":
                raise PolicyOSError(
                    "evaluator contract violation",
                    category=ErrorCategory.VALIDATION,
                    code="evaluation.contract",
                )
            if failure_case == "unknown":
                raise RuntimeError("unclassified evaluator failure")
            if failure_case == "cyclic_unknown":
                error = RuntimeError("cyclic unclassified evaluator failure")
                error.__cause__ = error
                raise error
            if failure_case == "domain_cycle":
                error = domain_error(
                    "cyclic declared sample-domain failure",
                    predicate_id="test.c_rate.evaluator_domain",
                )
                error.__cause__ = error
                raise error
            if failure_case == "transient_cycle":
                error = PolicyOSError(
                    "cyclic transient evaluator failure",
                    category=ErrorCategory.TRANSIENT,
                    code="evaluation.transient",
                )
                error.__cause__ = error
                raise error
            if failure_case == "domain_wrapped_permission":
                try:
                    raise PermissionError("wrapped access denial")
                except PermissionError as exc:
                    raise domain_error(
                        "declared sample-domain failure",
                        predicate_id="test.c_rate.evaluator_domain",
                    ) from exc
            if failure_case == "deep_domain_wrapped_permission":
                cause: Exception = PermissionError("deep wrapped access denial")
                for _ in range(80):
                    wrapper = RuntimeError("bounded cause-chain wrapper")
                    wrapper.__cause__ = cause
                    cause = wrapper
                raise domain_error(
                    "declared sample-domain failure",
                    predicate_id="test.c_rate.evaluator_domain",
                ) from cause
            if failure_case == "transient_wrapped_validation":
                try:
                    raise_validation_error()
                except Exception as exc:
                    raise PolicyOSError(
                        "transient wrapper around a contract failure",
                        category=ErrorCategory.TRANSIENT,
                        code="evaluation.transient",
                    ) from exc
            raise AssertionError(f"unknown failure case {failure_case}")
        return {"welfare": value, "welfare_pe": value, "welfare_ge": 0.0}

    _store, outcome, bundle = _run_b194_draw_execution_case(
        tmp_path,
        monkeypatch,
        simulation_fn,
        run_id=f"R_b194_failure_{failure_case}",
        require_success=False,
    )

    assert outcome.status == "fail"
    assert bundle is None
    assert outcome.error.code == expected_code
    assert outcome.error.details["failure_scope"] == expected_scope
    assert outcome.error.details["draw_index"] == 0
    assert outcome.error.details["sampled_input_sha256"]
    assert outcome.error.details["execution_attempt_count"] == 1
    assert outcome.error.details["execution_attempts"][0]["draw_index"] == 0
    if expected_scope == "unknown":
        assert "domain_predicate_id" not in outcome.error.details
    if failure_case == "cyclic_unknown":
        assert outcome.error.details["cause_type_chain"] == ["RuntimeError"]
    if failure_case in {"domain_cycle", "transient_cycle"}:
        assert outcome.error.details["retry_attempt_count"] == 0
        assert outcome.error.details["cause_chain_cycle_detected"] is True
    if failure_case == "deep_domain_wrapped_permission":
        assert outcome.error.details["cause_type_chain"][-1] == "ExceptionChainTruncated"
    assert len(calls) == 2


def test_welfare_mc_sampling_failure_fails_without_drawing_a_replacement(
    tmp_path,
    monkeypatch,
) -> None:
    calls: list[float] = []

    def simulation_fn(**params: float) -> dict[str, float]:
        value = float(params["C.rate"])
        calls.append(value)
        return {"welfare": value, "welfare_pe": value, "welfare_ge": 0.0}

    def fail_sampling(*args, **kwargs):
        del args, kwargs
        raise PermissionError("sample source access denied")

    monkeypatch.setattr(propagate_welfare_module, "_sample_param_draw", fail_sampling)
    _store, outcome, bundle = _run_b194_draw_execution_case(
        tmp_path,
        monkeypatch,
        simulation_fn,
        run_id="R_b194_sampling_access_failure",
        require_success=False,
    )

    assert outcome.status == "fail"
    assert bundle is None
    assert outcome.error.code == "ERROR_WELFARE_GLOBAL_EVALUATION_FAILURE"
    assert outcome.error.details["failure_scope"] == "global"
    assert outcome.error.details["failure_stage"] == "sample_generation"
    assert outcome.error.details["draw_index"] == 0
    assert outcome.error.details["sampled_input_sha256"] is None
    assert outcome.error.details["execution_attempt_count"] == 0
    assert outcome.error.details["attempted_draw_count"] == 1
    assert outcome.error.details["simulation_attempt_count"] == 0
    assert outcome.error.details["retry_attempt_count"] == 0
    assert len(calls) == 1


def test_welfare_mc_default_ge_evaluator_declares_sampled_condition_domain_through_cas(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    envelope_ref = _persist_empirical_welfare_envelope(store, (-1.0, 1.0))
    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        _b197_simulation_result(store),
        None,
        run_id="R_b194_default_ge_sample_domain",
        method="monte_carlo",
        weights=[1.0],
        labels=["C"],
        input_envelopes={"C.rate": envelope_ref.model_dump(mode="json")},
        welfare_config_overrides={
            "ge_technical_coefficients": [[0.0]],
            "ge_entry_map": {"C.rate": [0, 0]},
        },
    )

    assert outcome.status == "ok"
    assert bundle is not None
    assert bundle.status.value == "partial"
    assert bundle.point_estimate == pytest.approx(1.0)
    assert bundle.credible_interval is None
    assert "welfare_mc_incomplete_draws" in bundle.warnings

    fresh_store = FileSystemCAS(tmp_path)
    fresh_ir_store = _ensure_ir_artifact_store(fresh_store)
    fresh_bundle = load_welfare_bundle(
        fresh_ir_store,
        outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF],
    )
    report_id = ArtifactID.model_validate(fresh_bundle.diagnostics["propagation_report_ref"])
    report = from_canonical_bytes(fresh_store.get_bytes(report_id))
    provenance = report["draw_outcome_provenance"]
    domain_rows = [
        row for row in provenance["outcomes"] if row["outcome_code"] == "sample_domain_inapplicable"
    ]
    assert domain_rows
    assert all(row["execution_attempt_count"] == 1 for row in domain_rows)
    assert all(row["sampled_input_sha256"] for row in domain_rows)
    assert all(
        row["domain_predicate_id"] == "welfare.ge_operator.condition_number_within_threshold"
        for row in domain_rows
    )
    assert all(row["domain_declaration_grade"] == "consumer_asserted" for row in domain_rows)
    assert len(report["conditional_draw_summary"]) > 0
    assert "draw_summary" not in report
    assert provenance["successful_draw_count"] + provenance["failed_draw_count"] == 100
    assert provenance["failed_draw_count"] == len(domain_rows)
    sample_bundle = load_welfare_sample_bundle(fresh_ir_store, fresh_bundle.sample_bundle_ref)
    assert len(sample_bundle.welfare_draws) == provenance["successful_draw_count"]
    assert sample_bundle.metadata["draw_outcome_provenance"] == provenance
    report_manifest = fresh_store.get_manifest(report_id)
    assert any(
        item.role == "sample_bundle"
        and str(item.artifact_id) == str(fresh_bundle.sample_bundle_ref.artifact_id)
        for item in report_manifest.inputs
    )


def _persist_empirical_welfare_envelope(
    store: FileSystemCAS,
    samples: tuple[float, ...],
    *,
    param_name: str = "C.rate",
    weights: tuple[float, ...] | None = None,
    sample_axis: str = "row",
    joint_sample_id: str | None = None,
) -> ArtifactRefModel:
    metadata = {"param_name": param_name}
    if joint_sample_id is not None:
        metadata["joint_sample_id"] = joint_sample_id
    envelope = UncertaintyEnvelope(
        point_estimate=float(np.mean(samples)),
        confidence_interval=(min(samples), max(samples)),
        confidence_level=0.95,
        distribution_family=DistributionFamily.BOOTSTRAP,
        source=UncertaintySource.BOOTSTRAP,
        propagation_method=PropagationMethod.MONTE_CARLO,
        interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        distribution_payload=PosteriorSamplesCarrier(
            samples=samples,
            sample_axis=sample_axis,
            weights=weights,
        ),
        sample_size=len(samples),
        gate_eligible=True,
        metadata=metadata,
    )
    return persist_uncertainty_envelope(_ensure_ir_artifact_store(store), envelope)


def test_welfare_uses_weighted_empirical_atoms_through_fresh_cas_consumer(
    tmp_path,
    monkeypatch,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    envelope_ref = _persist_empirical_welfare_envelope(
        store,
        (-1.0, 1.0),
        weights=(9.0, 1.0),
    )

    def build_empirical_simulation_fn(
        _ctx,
        *,
        context,
        available_envelopes,
        ge_condition_number_threshold: float,
    ):
        del context, ge_condition_number_threshold
        assert set(available_envelopes.envelopes) == {"C.rate"}

        def simulation_fn(**params: float) -> dict[str, object]:
            value = float(params["C.rate"])
            return {
                "welfare": value,
                "welfare_pe": value,
                "welfare_pe_components": (value,),
                "welfare_total_components": (value,),
                "welfare_ge": 0.0,
            }

        return (
            simulation_fn,
            {"C.rate": 0.0},
            dict(available_envelopes.envelopes),
            dict(available_envelopes.refs),
        )

    monkeypatch.setattr(
        propagate_welfare_module,
        "_build_simulation_fn",
        build_empirical_simulation_fn,
    )
    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        _b197_simulation_result(store),
        None,
        run_id="R_b192_empirical_marginal",
        method="monte_carlo",
        weights=[1.0],
        labels=["C"],
        input_envelopes={"C.rate": envelope_ref.model_dump(mode="json")},
    )

    assert bundle.status.value == "partial"
    assert bundle.sample_bundle_ref is not None
    fresh_store = FileSystemCAS(tmp_path)
    samples = load_welfare_sample_bundle(
        _ensure_ir_artifact_store(fresh_store), bundle.sample_bundle_ref
    )
    assert set(samples.welfare_draws) <= {-1.0, 1.0}
    assert samples.welfare_draws.count(-1.0) > 0.75 * len(samples.welfare_draws)
    assert samples.metadata["dependence_strategy"] == "empirical_weighted_marginal"
    assert samples.metadata["draw_outcome_provenance"]["outcome_denominator_complete"] is True
    envelope_input = envelope_ref.artifact_id
    sample_manifest = fresh_store.get_manifest(bundle.sample_bundle_ref.artifact_id)
    assert any(
        item.role == "input_envelope.C.rate" and str(item.artifact_id) == str(envelope_input)
        for item in sample_manifest.inputs
    )
    report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    report_manifest = fresh_store.get_manifest(report_id)
    assert any(
        item.role == "input_envelope.C.rate" and str(item.artifact_id) == str(envelope_input)
        for item in report_manifest.inputs
    )


@pytest.mark.parametrize(
    ("joint_ids", "paired_samples", "sample_axes", "should_sample", "expected_values"),
    [
        (("shared-rows", "shared-rows"), ((-1.0, 1.0), (-1.0, 1.0)), ("row", "row"), True, {1.0}),
        (
            ("shared-rows", "shared-rows"),
            ((-1.0, 1.0), (1.0, -1.0)),
            ("row", "row"),
            True,
            {-1.0, 3.0},
        ),
        ((None, None), ((-1.0, 1.0), (-1.0, 1.0)), ("row", "row"), False, set()),
        (("rows-a", "rows-b"), ((-1.0, 1.0), (-1.0, 1.0)), ("row", "row"), False, set()),
        (("shared-rows", "shared-rows"), ((-1.0, 1.0), (-1.0, 1.0)), ("", ""), False, set()),
        (("shared-rows", "shared-rows"), ((-1.0, 1.0), (-1.0, 1.0)), (" \t", " \t"), False, set()),
    ],
)
def test_welfare_preserves_only_declared_shared_empirical_rows(
    tmp_path,
    monkeypatch,
    joint_ids: tuple[str | None, str | None],
    paired_samples: tuple[tuple[float, ...], tuple[float, ...]],
    sample_axes: tuple[str, str],
    should_sample: bool,
    expected_values: set[float],
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    refs = {
        "A.rate": _persist_empirical_welfare_envelope(
            store,
            paired_samples[0],
            param_name="A.rate",
            sample_axis=sample_axes[0],
            joint_sample_id=joint_ids[0],
        ),
        "B.rate": _persist_empirical_welfare_envelope(
            store,
            paired_samples[1],
            param_name="B.rate",
            sample_axis=sample_axes[1],
            joint_sample_id=joint_ids[1],
        ),
    }

    def build_empirical_simulation_fn(
        _ctx,
        *,
        context,
        available_envelopes,
        ge_condition_number_threshold: float,
    ):
        del context, ge_condition_number_threshold
        assert set(available_envelopes.envelopes) == {"A.rate", "B.rate"}

        def simulation_fn(**params: float) -> dict[str, object]:
            difference = float(params["A.rate"] - params["B.rate"])
            component_values = (
                1.0 + float(params["A.rate"]),
                -float(params["B.rate"]),
            )
            return {
                "welfare": 1.0 + difference,
                "welfare_pe": 1.0 + difference,
                "welfare_pe_components": component_values,
                "welfare_total_components": component_values,
                "welfare_ge": 0.0,
            }

        return (
            simulation_fn,
            {
                name: envelope.point_estimate
                for name, envelope in available_envelopes.envelopes.items()
            },
            dict(available_envelopes.envelopes),
            dict(available_envelopes.refs),
        )

    monkeypatch.setattr(
        propagate_welfare_module,
        "_build_simulation_fn",
        build_empirical_simulation_fn,
    )
    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        _b197_simulation_result(store),
        None,
        run_id=f"R_b188_empirical_{'sampled' if should_sample else 'withheld'}",
        method="monte_carlo",
        weights=[1.0, 1.0],
        labels=["A", "B"],
        input_envelopes={name: ref.model_dump(mode="json") for name, ref in refs.items()},
    )

    assert outcome.status == "ok"
    assert bundle.status.value == "partial"
    report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    report_manifest = FileSystemCAS(tmp_path).get_manifest(report_id)
    for name, ref in refs.items():
        assert any(
            item.role == f"input_envelope.{name}" and str(item.artifact_id) == str(ref.artifact_id)
            for item in report_manifest.inputs
        )
    if should_sample:
        assert bundle.sample_bundle_ref is not None
        fresh_store = FileSystemCAS(tmp_path)
        persisted = load_welfare_sample_bundle(
            _ensure_ir_artifact_store(fresh_store), bundle.sample_bundle_ref
        )
        assert set(persisted.welfare_draws) == expected_values
        assert bundle.diagnostics["dependence_sampling"]["strategy"] == "empirical_joint_rows"
        assert (
            bundle.diagnostics["dependence_sampling"]["joint_identity_status"]
            == "declared_non_authoritative"
        )
        assert "dependence_assumed_independent" not in bundle.warnings
        sample_manifest = fresh_store.get_manifest(bundle.sample_bundle_ref.artifact_id)
        for name, ref in refs.items():
            assert any(
                item.role == f"input_envelope.{name}"
                and str(item.artifact_id) == str(ref.artifact_id)
                for item in sample_manifest.inputs
            )
        assert "empirical_joint_law_missing" not in bundle.diagnostics["limitation_codes"]
    else:
        assert bundle.sample_bundle_ref is None
        assert bundle.credible_interval is None
        assert "empirical_joint_law_missing" in bundle.diagnostics["limitation_codes"]


@pytest.mark.parametrize("method", ["delta", "monte_carlo"])
def test_welfare_withholds_interval_when_envelope_covariance_disagrees_with_projection(
    tmp_path,
    method: str,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    report_ref, report = _run_b197_tied_calibrator(store)
    assert report.uncertainty_envelopes is not None

    forged_envelopes = {}
    for field_name, envelope in report.uncertainty_envelopes.items():
        assert isinstance(envelope.distribution_payload, ParametricFitCarrier)
        forged_envelopes[field_name] = envelope.model_copy(
            update={
                "confidence_interval": (
                    envelope.point_estimate - 0.3,
                    envelope.point_estimate + 0.3,
                ),
                "distribution_payload": envelope.distribution_payload.model_copy(
                    update={
                        "parameters": {
                            "mean": envelope.point_estimate,
                            "std": 0.1,
                        }
                    }
                ),
                "metadata": {
                    **envelope.metadata,
                    "std": 0.1,
                    "covariance_params": ["A.rate", "B.rate"],
                    "covariance_row": [0.01, 0.01],
                },
            }
        )

    forged_block = np.asarray([[0.01, 0.01], [0.01, 0.01]], dtype=np.float64)
    assert np.linalg.eigvalsh(forged_block).min() >= -1e-12
    assert all(
        envelope.distribution_payload.parameters["std"] == pytest.approx(0.1)
        for envelope in forged_envelopes.values()
    )
    assert np.diag(forged_block) == pytest.approx([0.1**2, 0.1**2])

    forged_report = report.model_copy(update={"uncertainty_envelopes": forged_envelopes})
    forged_report_ref = put_calibration_report(
        store,
        forged_report,
        inputs=_b197_legacy_report_inputs(store, report_ref),
    )
    sim_ref = _b197_simulation_result(store)
    outcome, bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        forged_report_ref,
        run_id=f"R_b197_projection_conflict_{method}",
        method=method,
        weights=[1.0, 1.0],
    )

    assert bundle.point_estimate == pytest.approx(2.0)
    assert bundle.credible_interval is None
    assert bundle.status.value == "partial"
    assert "calibration_covariance_conflict" in bundle.warnings
    propagation_report_id = ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"])
    propagation_report = from_canonical_bytes(store.get_bytes(propagation_report_id))
    assert propagation_report["limitation_code"] == "calibration_covariance_conflict"
    resolution = propagation_report["dependence_resolution"]
    assert resolution["strategy"] == "calibration_report_projection_conflict"
    assert resolution["coordinate_order"] == ["shared_rate"]
    assert resolution["calibration_fields"] == ["A.rate", "B.rate"]
    np.testing.assert_allclose(
        resolution["projected_covariance"],
        [[0.0025, 0.0025], [0.0025, 0.0025]],
        atol=1e-10,
        rtol=0,
    )
    np.testing.assert_allclose(
        resolution["envelope_covariance"],
        forged_block,
        atol=1e-8,
        rtol=0,
    )
    propagation_report_ref = ArtifactRef(
        artifact_id=propagation_report_id,
        kind="foundry.welfare_propagation_report",
        media_type="application/json",
    )
    assert _manifest_has_input(
        store,
        propagation_report_ref,
        forged_report_ref,
        "calibration_report",
    )
    if method == "delta":
        assert bundle.pe_uncertainty_refs
        for name, envelope_ref in bundle.pe_uncertainty_refs.items():
            assert any(
                item.role == f"input_envelope.{name}"
                and str(item.artifact_id) == str(envelope_ref.artifact_id)
                and item.manifest_profile_sha256 == envelope_ref.manifest_profile_sha256
                for item in store.get_manifest(propagation_report_ref).inputs
            )
    bundle_ref = outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    assert _manifest_has_input(store, bundle_ref, forged_report_ref, "calibration_report")


def test_welfare_reconciles_external_overlap_before_using_calibration_covariance(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    report_ref, _ = _run_b197_tied_calibrator(store)
    sim_ref = _b197_simulation_result(store)

    matching_ref = _b197_dependence_structure_ref(
        store,
        [[1.0, 1.0], [1.0, 1.0]],
    )
    _, matching_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_matching_overlap",
        method="delta",
        weights=[1.0, 1.0],
        dependence_structure_ref=matching_ref.model_dump(mode="json"),
    )
    assert matching_bundle.point_estimate == pytest.approx(2.0)
    assert matching_bundle.credible_interval is not None
    assert matching_bundle.diagnostics["delta_std"] == pytest.approx(0.1, rel=1e-4)
    assert "calibration_covariance_conflict" not in matching_bundle.warnings

    conflicting_ref = _b197_dependence_structure_ref(
        store,
        [[1.0, 0.5], [0.5, 1.0]],
    )
    _, conflicting_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_conflicting_overlap",
        method="delta",
        weights=[1.0, 1.0],
        dependence_structure_ref=conflicting_ref.model_dump(mode="json"),
    )
    assert conflicting_bundle.point_estimate == pytest.approx(2.0)
    assert conflicting_bundle.credible_interval is None
    assert conflicting_bundle.status.value == "partial"
    assert "calibration_covariance_conflict" in conflicting_bundle.warnings


def test_welfare_suppresses_unproved_or_malformed_calibration_dependence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_ref = build_default_registry_bundle(store).bundle_ref
    report_ref, report = _run_b197_tied_calibrator(store)
    assert report.uncertainty_envelopes is not None
    sim_ref = _b197_simulation_result(store)

    missing_projection = report.model_copy(
        update={
            "coordinate_projection": None,
            "coordinate_projection_status": "not_established",
        }
    )
    assert missing_projection.uncertainty_envelopes["A.rate"].metadata["covariance_row"]
    calibration_inputs = _b197_legacy_report_inputs(store, report_ref)
    missing_projection_ref = put_calibration_report(
        store,
        missing_projection,
        inputs=calibration_inputs,
    )
    _, missing_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        missing_projection_ref,
        run_id="R_b197_missing_projection",
        method="delta",
        weights=[1.0, 1.0],
    )
    assert missing_bundle.point_estimate == pytest.approx(2.0)
    assert missing_bundle.credible_interval is None
    assert missing_bundle.status.value == "partial"
    assert "calibration_projection_missing" in missing_bundle.warnings

    malformed_envelopes = dict(report.uncertainty_envelopes)
    envelope_b = malformed_envelopes["B.rate"]
    malformed_envelopes["B.rate"] = envelope_b.model_copy(
        update={
            "metadata": {
                **envelope_b.metadata,
                "covariance_row": [0.0025],
            }
        }
    )
    malformed_report = report.model_copy(update={"uncertainty_envelopes": malformed_envelopes})
    malformed_ref = put_calibration_report(
        store,
        malformed_report,
        inputs=calibration_inputs,
    )
    _, malformed_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        malformed_ref,
        run_id="R_b197_malformed_covariance",
        method="delta",
        weights=[1.0, 1.0],
    )
    assert malformed_bundle.point_estimate == pytest.approx(2.0)
    assert malformed_bundle.credible_interval is None
    assert malformed_bundle.status.value == "partial"
    assert "calibration_covariance_invalid" in malformed_bundle.warnings

    unrelated = UncertaintyEnvelope(
        point_estimate=0.5,
        confidence_interval=(0.2, 0.8),
        confidence_level=None,
        distribution_family=DistributionFamily.NORMAL,
        source=UncertaintySource.CALIBRATION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
        is_heuristic_ci=True,
        gate_eligible=False,
        metadata={
            "param_name": "C.rate",
            "std": 0.1,
            "independence": "independent",
        },
    )
    _, mixed_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_unknown_cross_source",
        method="delta",
        weights=[1.0, 1.0, 1.0],
        labels=["A", "B", "C"],
        input_envelopes={"C.rate": unrelated.model_dump(mode="json")},
        dependence_structure_ref=_b197_dependence_structure_ref(
            store,
            [[1.0, 1.0], [1.0, 1.0]],
        ).model_dump(mode="json"),
    )
    # C.rate is centered at its nominal 0.5; this candidate input adds no
    # point-response delta, so the three baseline responses still sum to 3.
    assert mixed_bundle.point_estimate == pytest.approx(3.0)
    assert mixed_bundle.credible_interval is None
    assert mixed_bundle.status.value == "partial"
    assert "calibration_cross_source_dependence_unknown" in mixed_bundle.warnings

    full_zero_cross_ref = _b197_dependence_structure_ref(
        store,
        [
            [1.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        parameter_order=["A.rate", "B.rate", "C.rate"],
    )
    _, unproved_independence_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_unproved_zero_cross_block",
        method="delta",
        weights=[1.0, 1.0, 1.0],
        labels=["A", "B", "C"],
        input_envelopes={"C.rate": unrelated.model_dump(mode="json")},
        dependence_structure_ref=full_zero_cross_ref.model_dump(mode="json"),
    )
    assert unproved_independence_bundle.point_estimate == pytest.approx(3.0)
    assert unproved_independence_bundle.credible_interval is None
    assert unproved_independence_bundle.status.value == "partial"
    assert "calibration_cross_source_dependence_unknown" in (unproved_independence_bundle.warnings)

    conflicting_inline = report.uncertainty_envelopes["A.rate"].model_copy(
        update={"point_estimate": 0.3}
    )
    _, inline_conflict_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_conflicting_inline_field",
        method="delta",
        weights=[1.0, 1.0],
        input_envelopes={"A.rate": conflicting_inline.model_dump(mode="json")},
    )
    assert inline_conflict_bundle.point_estimate == pytest.approx(2.0)
    assert inline_conflict_bundle.credible_interval is None
    assert inline_conflict_bundle.status.value == "partial"
    assert "calibration_envelope_conflict" in inline_conflict_bundle.warnings

    same_value_different_origin = report.uncertainty_envelopes["A.rate"].model_dump(mode="json")
    _, equal_value_conflict_bundle = _run_b197_welfare(
        store,
        registry_ref,
        sim_ref,
        report_ref,
        run_id="R_b197_equal_value_distinct_origin",
        method="delta",
        weights=[1.0, 1.0],
        input_envelopes={"A.rate": same_value_different_origin},
    )
    assert equal_value_conflict_bundle.point_estimate == pytest.approx(2.0)
    assert equal_value_conflict_bundle.credible_interval is None
    assert equal_value_conflict_bundle.status.value == "partial"
    assert "calibration_envelope_conflict" in equal_value_conflict_bundle.warnings


def test_welfare_draw_failure_scope_uses_shared_foundry_classifier(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    error = PolicyOSError(
        "temporary evaluator transport failure",
        category=ErrorCategory.TRANSIENT,
        code="evaluation.transient",
    )

    def classify(exc, *, sample_domain_error_type=None, additional_global_error_types=()):
        calls.append(
            {
                "exc": exc,
                "sample_domain_error_type": sample_domain_error_type,
                "additional_global_error_types": additional_global_error_types,
            }
        )
        return SimpleNamespace(
            scope="unknown",
            chain=(exc,),
            chain_complete=False,
            cycle_detected=False,
        )

    monkeypatch.setattr(
        welfare_draws_module,
        "classify_evaluation_failure",
        classify,
        raising=False,
    )

    scope = welfare_draws_module._welfare_draw_failure_scope(
        error,
        sample_domain_error_type=propagate_welfare_module.WelfareSampleDomainError,
    )

    assert scope == "unknown"
    assert calls == [
        {
            "exc": error,
            "sample_domain_error_type": propagate_welfare_module.WelfareSampleDomainError,
            "additional_global_error_types": (welfare_types_module._WelfareNodeFailure,),
        }
    ]


def test_actual_welfare_node_1_1_tuple_flows_through_phase3_and_protected_packet(
    tmp_path: Path,
) -> None:
    from polisyos.foundry.methods.catalog.microsim.protocols import MicrosimResult
    from polisyos.ir.analytics.welfare import (
        ChannelIdentificationStatus,
        load_welfare_bundle,
    )
    from polisyos.ir.registry.refs import WelfareBundleRef
    from polisyos.scientist.nodes.builtins.decide.build_decision_packet import (
        BuildDecisionPacketNode,
    )
    from polisyos.scientist.nodes.builtins.state_keys import (
        INPUT_REGISTRY_BUNDLE_REF,
        INPUT_TRINITY_BUNDLE_REF,
    )

    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_welfare_current_tuple_e2e",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("test.welfare.current_tuple"),
    )
    snapshot_ref = store.put_json(
        {"state": {}},
        PutOptions(kind="foundry.state_snapshot", media_type="application/json"),
    )
    exec_plan_ref = store.put_json(
        {
            "program_ref": {
                "artifact_id": str(snapshot_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"policy_value": 10.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    simulation_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef.model_validate(exec_plan_ref.model_dump(mode="python")),
            metrics_ref=MetricsRef.model_validate(metrics_ref.model_dump(mode="python")),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    state = ExperimentState(
        run_id="R_welfare_current_tuple_e2e",
        artifacts_index={
            ARTIFACT_SIMULATION_RESULT_REF: SimulationResultRef.model_validate(
                simulation_ref.model_dump(mode="python")
            )
        },
        params={
            "welfare_weights": {"policy_value": 1.0},
            "welfare_input_envelopes": {
                "policy_value": {
                    "point_estimate": 10.0,
                    "confidence_interval": [9.0, 11.0],
                    "confidence_level": 0.95,
                    "distribution_family": "normal",
                    "source": "manual",
                    "propagation_method": "none",
                    "interval_semantics": "confidence_interval",
                }
            },
            "propagation_config": {"preferred_method": "delta"},
            "welfare_channel_decomposition": {
                "target_kind": "social_welfare",
                "baseline_microdata": {
                    "overlap_ok": True,
                    "overlap_stats": {"min_propensity": 0.15},
                },
                "policy_basis": {
                    "basis_labels": ["delta_tax_rate", "delta_transfer"],
                    "step_vector": [0.02, 1.0],
                    "policy_class": "local_affine_tax_transfer",
                    "policy_rank_ok": True,
                    "timing_assumptions": ["policy -> behavior -> closure"],
                },
                "mechanical_inputs": {"mechanical_vector": [0.6]},
                "behavior_model": {
                    "behavioral_vector": [-0.24],
                    "first_stage_ok": True,
                    "first_stage_stats": {"behavior_f": 18.0},
                },
                "fiscal_state_model": {
                    "fiscal_feedback_vector": [0.16],
                    "first_stage_ok": True,
                    "first_stage_stats": {"fiscal_f": 14.0},
                },
                "instrument_set": {
                    "overid_ok": True,
                    "timing_ok": True,
                    "overid_stats": {"hansen_pvalue": 0.31},
                },
                "total_vector": [0.52],
            },
        },
    )

    outcome = PropagateWelfareNode().execute(ctx, state)

    assert outcome.status == "ok", outcome.events
    welfare_ref = WelfareBundleRef.model_validate(
        outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF].model_dump(mode="json")
    )
    fresh_store = FileSystemCAS(tmp_path)
    fresh_ir_store = _ensure_ir_artifact_store(fresh_store)
    bundle = load_welfare_bundle(fresh_ir_store, welfare_ref)
    bundle_manifest = fresh_store.get_manifest(welfare_ref)
    bundle_payload = from_canonical_bytes(fresh_store.get_bytes(welfare_ref.artifact_id))
    assert bundle.schema_version == "1.1"
    assert bundle_manifest.artifact_schema.name == "ir.welfare_bundle"
    assert bundle_manifest.artifact_schema.version == "1.1"
    assert bundle_payload["schema_version"] == "1.1"
    assert bundle.channel_decomposition_ref is not None

    channel = load_channel_decomposition_artifact(fresh_ir_store, bundle.channel_decomposition_ref)
    assert channel.identification_status is ChannelIdentificationStatus.BLOCKED
    assert channel.diagnostic_summary["candidate_identification_status"] == "identified"
    assert channel.diagnostic_summary["input_owner_status"] == "not_established"
    assert channel.mechanical_vector == pytest.approx((0.6,))
    assert channel.behavioral_vector == pytest.approx((-0.24,))
    assert channel.fiscal_feedback_vector == pytest.approx((0.16,))
    assert channel.total_vector == pytest.approx((0.52,))

    phase3_state = ExperimentState(
        run_id="R_welfare_current_tuple_e2e",
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
        params={
            "microsim_result": MicrosimResult(
                disposable_income=[10.0],
                tax_liability=[1.0],
                benefit_income=[0.0],
                weighted_mean_disposable_income=10.0,
                weighted_gini=0.1,
                policy_revenue=1.0,
            ).model_dump(mode="json")
        },
    )
    gate = resolve_phase3_gate(ctx, phase3_state)
    assert gate.gate_passed is False
    assert "phase3.welfare_channel_input_owner_not_established" in gate.blocking_reasons
    assert gate.fiscal_feedback_required is False
    assert gate.fiscal_feedback_ref is None

    trinity_bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="welfare_packet", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(policy_id="welfare_packet"),
        model_spec=ModelSpec(
            model_id="welfare_packet",
            data_snapshot_ref=str(snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle.artifact_id),
        ),
    )
    selected_trinity_ref = persist_trinity_bundle_artifact(
        _ensure_ir_artifact_store(store), trinity_bundle
    )
    trinity_ref = ArtifactRef.model_validate(selected_trinity_ref.model_dump(mode="python"))
    packet_data_snapshot = store.put_json(
        {
            "data_ref": {
                "artifact_id": str(snapshot_ref.artifact_id),
                "kind": "foundry.state_snapshot",
                "media_type": "application/json",
            }
        },
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    packet_state = ExperimentState(
        run_id="R_welfare_current_tuple_e2e",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: packet_data_snapshot,
        },
        artifacts_index={ARTIFACT_WELFARE_BUNDLE_REF: welfare_ref},
    )
    packet_outcome = BuildDecisionPacketNode().execute(ctx, packet_state)
    assert packet_outcome.artifacts
    packet_payload = from_canonical_bytes(store.get_bytes(packet_outcome.artifacts[0].artifact_id))
    protected_channel = packet_payload["welfare"]["channel_decomposition_artifact"]
    assert protected_channel["identification_status"] == "blocked"
    assert protected_channel["authority_status"] == "not_established"
    for field in (
        "mechanical_vector",
        "behavioral_vector",
        "fiscal_feedback_vector",
        "total_vector",
    ):
        assert field not in protected_channel


def _run_ordered_b197_calibrator(store, *, flat=False):
    """Reuse the real selected compile/execution fixture for a two-row fit."""
    import jax

    from polisyos.foundry.calibration import OrderedBatchCalibrationProfile

    source = _build_b197_tied_execution_source(store)
    base = source["base_state"]
    doubled = base.replace(
        agents=base.agents.replace(
            income=base.agents.income * 2,
            reported_income=base.agents.reported_income * 2,
        )
    )
    profile = OrderedBatchCalibrationProfile(
        row_ids=("first", "second"),
        states=jax.tree.map(lambda a, b: jnp.stack((a, b)), base, doubled),
        row_times=jnp.asarray([20, 20] if flat else [0, 0], dtype=jnp.int32),
        row_keys=jax.random.split(jax.random.PRNGKey(83), 2),
        target_path="government_balance",
        targets=jnp.asarray([0.0, 0.0] if flat else [36.0, 72.0], dtype=jnp.float32),
        weights=jnp.asarray([1.0, 3.0], dtype=jnp.float32),
    )
    config = CalibrationConfig(
        targets=[
            CalibrationTarget(
                target_id="balance",
                model_metric_path="government_balance",
                loss={"relative": False, "weight": 0.005},
            )
        ],
        trainables=[
            TrainableParamRef(node_id=n, param_id="rate", tie_id="shared_rate") for n in ("A", "B")
        ],
        max_steps=2,
        learning_rate=0.01,
        hessian={"enabled": True, "damping": 1e-6},
    )
    registry = source["registry_content"]
    execution = source["source_basis"]
    report, report_ref = Calibrator(
        CalibratorInputs(
            config=config,
            program_graph=source["graph"],
            exec_plan=source["plan"],
            base_state=base,
            mechanism_registry=registry.mechanism_registry,
            slot_registry=registry.slot_registry,
            merge_registry=registry.merge_registry,
            selector_field_registry=registry.selector_field_registry,
            constraint_registry=registry.constraint_registry,
            parameter_loader=lambda ref: from_canonical_bytes(store.get_bytes(ref)),
            registry_bundle_ref=execution.runtime_registry_ref,
            mechanism_registry_ref=execution.runtime_registry_members.mechanism_registry,
            units_registry=registry.units_registry,
            units_registry_ref=execution.runtime_registry_members.units_registry,
            base_state_snapshot_ref=execution.base_state_snapshot_ref,
            exec_plan_ref=execution.exec_plan_ref,
            ordered_batch_profile=profile,
        )
    ).run_and_persist(store)
    simulation_ref = _b197_replay_report(store, execution, report_ref, report)
    edge = next(
        edge
        for edge in store.get_manifest(report_ref).inputs
        if edge.role == "calibration_execution_input_basis"
    )
    basis_ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind="foundry.calibration_execution_input_basis",
        media_type="application/json",
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    return source, report_ref, report, simulation_ref, basis_ref


@pytest.fixture(scope="module")
def ordered_batch_case(tmp_path_factory):
    path = tmp_path_factory.mktemp("ordered_batch_selected_case")
    store = FileSystemCAS(path)
    source, report_ref, report, simulation_ref, basis_ref = _run_ordered_b197_calibrator(store)
    return path, source, report_ref, report, simulation_ref, basis_ref


def _ordered_input_ref_for_basis(store, basis_ref):
    basis = load_calibration_execution_input_basis(store, basis_ref)
    assert basis.ordered_batch_input_ref is not None
    return basis, basis.ordered_batch_input_ref


@pytest.mark.parametrize(
    "mutation",
    [
        "time",
        "row_order",
        "selected_state",
        "missing_row_edge",
        "profileless_row_edge",
        "missing_config_edge",
        "duplicate_config_edge",
        "config_schema",
        "row_schema",
        "profileless_input",
        "unknown_input_version",
        "missing_basis_input_edge",
        "missing_basis_config_edge",
    ],
)
def test_batch_basis_fresh_consumer_reconciles_every_selected_input(ordered_batch_case, mutation):
    from polisyos.foundry.calibration.execution_basis import (
        canonical_input_sha256,
        resolve_calibration_ordered_batch_input,
    )

    path, source, report_ref, report, simulation_ref, basis_ref = ordered_batch_case
    store = FileSystemCAS(path)
    basis, input_ref = _ordered_input_ref_for_basis(store, basis_ref)
    assert basis.schema_version == "1.2"
    assert report.schema_version == "2.1"
    profile, resolved_values = resolve_calibration_ordered_batch_input(store, input_ref)
    assert tuple(row.row_id for row in profile.rows) == ("first", "second")
    assert basis.target_inputs[0].source_kind == "ordered_batch_profile"
    joined = _calibration_execution_source_join(
        _b197_execution_context(store, source["registry"].bundle_ref, f"R_ordered_{mutation}"),
        _b197_execution_state(simulation_ref, report_ref),
        report_ref=report_ref,
        report=report,
    )
    assert joined[0] == "matched", joined
    if mutation == "profileless_input":
        with pytest.raises(ValueError, match="requires_selected_profile"):
            resolve_calibration_ordered_batch_input(
                store, input_ref.model_copy(update={"manifest_profile_sha256": None})
            )
        return
    if mutation.startswith("missing_basis_"):
        role = (
            "ordered_batch_input"
            if mutation == "missing_basis_input_edge"
            else "calibration_config"
        )
        manifest = store.get_manifest(basis_ref)
        forged = store.put_json(
            from_canonical_bytes(store.get_bytes(basis_ref)),
            PutOptions(
                kind=basis_ref.kind,
                media_type="application/json",
                schema=manifest.artifact_schema,
                inputs=[edge for edge in manifest.inputs if edge.role != role],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError):
            load_calibration_execution_input_basis(FileSystemCAS(path), forged)
        return
    payload = from_canonical_bytes(store.get_bytes(input_ref))
    manifest = store.get_manifest(input_ref)
    inputs = list(manifest.inputs)
    schema = manifest.artifact_schema
    if mutation == "time":
        payload["row_times"][0] = 1
        values = dict(resolved_values)
        values["row_times"] = np.asarray(
            payload["row_times"], dtype=np.dtype(payload["row_times_dtype"])
        )
        payload["consumed_profile_sha256"] = canonical_input_sha256(values)
    elif mutation == "row_order":
        payload["rows"] = list(reversed(payload["rows"]))
    elif mutation == "selected_state":
        payload["rows"][0]["state_snapshot_ref"] = payload["rows"][1]["state_snapshot_ref"]
    elif mutation == "missing_row_edge":
        inputs = [edge for edge in inputs if edge.role != "ordered_batch_row.1"]
    elif mutation == "profileless_row_edge":
        inputs = [
            edge.model_copy(update={"manifest_profile_sha256": None})
            if edge.role == "ordered_batch_row.1"
            else edge
            for edge in inputs
        ]
    elif mutation == "missing_config_edge":
        inputs = [edge for edge in inputs if edge.role != "calibration_config"]
    elif mutation == "duplicate_config_edge":
        inputs.append(next(edge for edge in inputs if edge.role == "calibration_config"))
    elif mutation in {"config_schema", "row_schema"}:
        ref = (
            profile.calibration_config_ref
            if mutation == "config_schema"
            else profile.rows[0].state_snapshot_ref
        )
        old_manifest = store.get_manifest(ref)
        replacement = store.put_json(
            from_canonical_bytes(store.get_bytes(ref)),
            PutOptions(
                kind=ref.kind,
                media_type=ref.media_type,
                schema=SchemaInfo(
                    name=old_manifest.artifact_schema.name,
                    version="9.9",
                ),
                inputs=old_manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        role = "calibration_config" if mutation == "config_schema" else "ordered_batch_row.0"
        if mutation == "config_schema":
            payload["calibration_config_ref"] = replacement.model_dump(mode="json")
        else:
            payload["rows"][0]["state_snapshot_ref"] = replacement.model_dump(mode="json")
        inputs = [
            input_ref_from_artifact_ref(replacement, role=role) if edge.role == role else edge
            for edge in inputs
        ]
    elif mutation == "unknown_input_version":
        payload["schema_version"] = "1.1"
        schema = SchemaInfo(name=schema.name, version="1.1")
    forged = store.put_json(
        payload,
        PutOptions(
            kind=input_ref.kind,
            media_type="application/json",
            schema=schema,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError):
        resolve_calibration_ordered_batch_input(FileSystemCAS(path), forged)


@pytest.mark.parametrize("mutation", ["weights", "keys"])
def test_coherent_new_input_and_basis_cannot_replace_the_consumed_report_selection(
    ordered_batch_case,
    mutation,
    monkeypatch,
):
    from polisyos.foundry.calibration.execution_basis import (
        CalibrationExecutionInputBasis,
        canonical_input_sha256,
        put_calibration_execution_input_basis,
        resolve_calibration_ordered_batch_input,
    )

    path, source, report_ref, report, simulation_ref, basis_ref = ordered_batch_case
    store = FileSystemCAS(path)
    basis, input_ref = _ordered_input_ref_for_basis(store, basis_ref)
    input_model, values = resolve_calibration_ordered_batch_input(store, input_ref)
    payload = input_model.model_dump(mode="json")
    values = dict(values)
    field = "row_keys" if mutation == "keys" else "weights"
    values[field] = np.asarray(values[field])[::-1].copy()
    payload[field] = values[field].tolist()
    payload["consumed_profile_sha256"] = canonical_input_sha256(values)
    input_manifest = store.get_manifest(input_ref)
    forged_input = store.put_json(
        payload,
        PutOptions(
            kind=input_ref.kind,
            media_type="application/json",
            schema=input_manifest.artifact_schema,
            inputs=input_manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    new_input, _ = resolve_calibration_ordered_batch_input(store, forged_input)
    body = basis.model_dump(mode="json")
    digest = canonical_input_sha256(new_input)
    body["ordered_batch_input_ref"] = forged_input.model_dump(mode="json")
    body["ordered_batch_input_value_sha256"] = digest
    binding = body["runtime_input_roster"][-1]
    binding.update(
        source_ref=forged_input.model_dump(mode="json"),
        value_sha256=digest,
        source_payload_sha256=digest,
    )
    basis_inputs = [
        input_ref_from_artifact_ref(forged_input, role="ordered_batch_input")
        if edge.role == "ordered_batch_input"
        else edge
        for edge in store.get_manifest(basis_ref).inputs
    ]
    forged_basis = put_calibration_execution_input_basis(
        store,
        CalibrationExecutionInputBasis.model_validate(body),
        inputs=basis_inputs,
    )
    # Both records are individually coherent, but the actual report selected the original input.
    report_inputs = [
        input_ref_from_artifact_ref(forged_basis, role="calibration_execution_input_basis")
        if edge.role == "calibration_execution_input_basis"
        else edge
        for edge in store.get_manifest(report_ref).inputs
    ]
    manifest = store.get_manifest(report_ref)
    forged_report = store.put_json(
        report,
        PutOptions(
            kind=report_ref.kind,
            media_type="application/json",
            schema=manifest.artifact_schema,
            inputs=report_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    joined = _calibration_execution_source_join(
        _b197_execution_context(
            FileSystemCAS(path), source["registry"].bundle_ref, f"R_ordered_coherent_{mutation}"
        ),
        _b197_execution_state(simulation_ref, forged_report),
        report_ref=forged_report,
        report=report,
    )
    assert joined[0] == "mismatch", joined
    assert "calibration_ordered_report_input_scope_mismatch" in joined[2]
    # Observe both actual CAS publication entrypoints. An ID-set comparison
    # would miss publication of a new selected view for an existing payload.
    writes = []
    original_json, original_bytes = store.put_json, store.put_bytes

    def observe_json(*args, **kwargs):
        writes.append("put_json")
        return original_json(*args, **kwargs)

    def observe_bytes(*args, **kwargs):
        writes.append("put_bytes")
        return original_bytes(*args, **kwargs)

    monkeypatch.setattr(store, "put_json", observe_json)
    monkeypatch.setattr(store, "put_bytes", observe_bytes)
    with pytest.raises(ValueError, match="selected_consumed_input"):
        put_calibration_report(store, report, inputs=report_inputs)
    assert writes == []


@pytest.mark.parametrize("mutation", ["model", "loss", "metrics"])
def test_new_report_projection_is_recomputed_from_unchanged_selected_input(
    ordered_batch_case,
    mutation,
):
    path, source, report_ref, report, simulation_ref, _ = ordered_batch_case
    store = FileSystemCAS(path)
    altered = report.model_copy(deep=True)
    if mutation == "model":
        altered.series_comparison["balance"].model[0] += 17.0
    elif mutation == "loss":
        altered.total_loss += 17.0
    else:
        altered.fit_quality.aggregate.rmse += 17.0
    altered_ref = put_calibration_report(
        store, altered, inputs=store.get_manifest(report_ref).inputs
    )
    joined = _calibration_execution_source_join(
        _b197_execution_context(
            FileSystemCAS(path), source["registry"].bundle_ref, f"R_ordered_projection_{mutation}"
        ),
        _b197_execution_state(simulation_ref, altered_ref),
        report_ref=altered_ref,
        report=altered,
    )
    expected = {
        "model": "ordered_report_model_does_not_match_selected_final_forward",
        "loss": "ordered_report_loss_does_not_match_selected_objective",
        "metrics": "ordered_report_metrics_do_not_match_selected_projection",
    }
    assert joined[0] == "mismatch", joined
    assert expected[mutation] in joined[2]


@pytest.mark.parametrize("method", ["delta", "monte_carlo"])
def test_typed_batch_report_missing_basis_cannot_take_legacy_inference_fallback(
    ordered_batch_case,
    method,
):
    path, source, report_ref, report, simulation_ref, _ = ordered_batch_case
    store = FileSystemCAS(path)
    inputs = [
        edge
        for edge in store.get_manifest(report_ref).inputs
        if edge.role != "calibration_execution_input_basis"
    ]
    with pytest.raises(ValueError, match="exact_config_and_basis_edges"):
        put_calibration_report(store, report, inputs=inputs)
    manifest = store.get_manifest(report_ref)
    # A direct CAS writer can still present an untrusted selected view. The fresh consumer refuses inference.
    missing_basis = store.put_json(
        report,
        PutOptions(
            kind=report_ref.kind,
            media_type="application/json",
            schema=manifest.artifact_schema,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    outcome, bundle = _run_b197_welfare(
        FileSystemCAS(path),
        source["registry"].bundle_ref,
        simulation_ref,
        missing_basis,
        run_id=f"R_ordered_missing_basis_{method}",
        method=method,
        weights=[1.0, 1.0],
    )
    assert outcome.status == "ok"
    assert bundle.point_estimate == pytest.approx(2.0)
    assert bundle.credible_interval is None
    assert "calibration_generic_batch_inference_unavailable" in bundle.warnings
    result = from_canonical_bytes(
        store.get_bytes(ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"]))
    )
    assert result["source_execution_status"] == "not_established"
    assert result["calibration_inference_status"] == "curvature_only"


@pytest.mark.parametrize("method", ["delta", "monte_carlo"])
@pytest.mark.parametrize("flat", [False, True])
def test_generic_batch_curvature_is_not_inferential_welfare_uncertainty(
    tmp_path, method, flat
) -> None:
    store = FileSystemCAS(tmp_path)
    source, report_ref, report, simulation_ref, basis_ref = _run_ordered_b197_calibrator(
        store, flat=flat
    )
    assert report.uncertainties is not None
    if flat:
        assert report.uncertainties.hessian_rank == 0
        assert (
            report.execution_context["ordered_batch"]["hessian"]["condition_status"] == "non_finite"
        )
        assert "ordered_batch_hessian_condition_non_finite" in report.diagnostics
        assert report.execution_context["ordered_batch"]["hessian"]["raw_eigenvalues"] == [0.0]
    assert report.uncertainty_envelopes
    assert all(not envelope.gate_eligible for envelope in report.uncertainty_envelopes.values())
    fresh = FileSystemCAS(tmp_path)
    assert load_calibration_execution_input_basis(fresh, basis_ref).schema_version == "1.2"
    outcome, bundle = _run_b197_welfare(
        fresh,
        source["registry"].bundle_ref,
        simulation_ref,
        report_ref,
        run_id=f"R_ordered_curvature_{method}",
        method=method,
        weights=[1.0, 1.0],
    )
    assert outcome.status == "ok"
    assert bundle.point_estimate == pytest.approx(2.0)
    assert bundle.credible_interval is None
    assert bundle.status.value == "partial"
    assert "calibration_generic_batch_inference_unavailable" in bundle.warnings
    propagation = from_canonical_bytes(
        fresh.get_bytes(ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"]))
    )
    assert propagation["limitation_code"] == "calibration_generic_batch_inference_unavailable"
    assert propagation["calibration_inference_status"] == "curvature_only"
    assert propagation["source_execution_status"] == "matched"
    # The unrelated external marginal stays usable even when the batch report is present.
    external = UncertaintyEnvelope(
        point_estimate=0.5,
        confidence_interval=(0.0, 1.0),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.MANUAL,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=False,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.UNIFORM,
            parameters={"low": 0.0, "high": 1.0},
            support=(0.0, 1.0),
        ),
        metadata={"param_name": "C.rate", "std": 1.0 / math.sqrt(12.0)},
    )
    external_ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(store), external)
    _, external_bundle = _run_b197_welfare(
        FileSystemCAS(tmp_path),
        source["registry"].bundle_ref,
        simulation_ref,
        report_ref,
        run_id=f"R_ordered_external_{method}",
        method=method,
        labels=["C"],
        weights=[1.0],
        input_envelopes={"C.rate": external_ref.model_dump(mode="json")},
    )
    assert external_bundle.point_estimate == pytest.approx(1.0)
    assert external_bundle.credible_interval is not None


@pytest.mark.parametrize(
    "mode",
    [
        "selected",
        "missing_selection",
        "changed_metrics",
        "missing_basis",
        "missing_input",
        "malformed_basis",
        "profileless_basis",
        "missing_basis_edge",
        "duplicate_basis",
        "conflicting_input",
    ],
)
def test_autotune_actual_consumer_admits_only_replayed_new_batch_metrics(
    ordered_batch_case,
    tmp_path,
    mode,
):
    import json

    from polisyos.scientist.methods.autotune import (
        BenchmarkSplitManifest,
        BenchmarkSuite,
        persist_benchmark_evaluation,
        persist_benchmark_suite,
        persist_mutation_artifact,
    )
    from polisyos.scientist.methods.autotune.calibration import (
        CalibrationMetaEvaluator,
        CalibrationMetaSearchConfig,
    )

    path, source, report_ref, report, simulation_ref, basis_ref = ordered_batch_case
    store = FileSystemCAS(path)
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text("".join(json.dumps({"case_id": key}) + "\n" for key in ("sel", "hold")))
    split = tmp_path / "split.json"
    split.write_text(
        BenchmarkSplitManifest(
            suite_id="ordered_batch_metrics",
            suite_version="1.0",
            id_field="case_id",
            selection_ids=["sel"],
            holdout_ids=["hold"],
        ).model_dump_json()
    )
    suite_ref = persist_benchmark_suite(
        store,
        BenchmarkSuite(
            suite_id="ordered_batch_metrics",
            suite_version="1.0",
            kind="calibration_meta",
            dataset_path=str(dataset),
            split_manifest_path=str(split),
        ),
    )
    candidate_ref = persist_mutation_artifact(store, CalibrationMetaSearchConfig())
    returned = report
    if mode in {
        "missing_basis",
        "missing_input",
        "malformed_basis",
        "profileless_basis",
        "missing_basis_edge",
        "duplicate_basis",
        "conflicting_input",
    }:
        kind = {
            "missing_basis": "basis",
            "missing_input": "input",
            "malformed_basis": "malformed_basis",
            "profileless_basis": "profileless_basis",
            "missing_basis_edge": "missing_basis_edge",
            "duplicate_basis": "duplicate_basis",
            "conflicting_input": "conflicting_input",
        }[mode]
        returned, report_ref, _ = _ordered_report_with_unavailable_or_invalid_source(
            store,
            report_ref,
            report,
            basis_ref,
            kind,
        )
    if mode == "changed_metrics":
        returned = report.model_copy(deep=True)
        returned.fit_quality.aggregate.rmse = 0.0
        returned.fit_quality.aggregate.mae = 0.0
        report_ref = put_calibration_report(
            store,
            returned,
            inputs=store.get_manifest(report_ref).inputs,
        )
    result = CalibrationMetaEvaluator(store=FileSystemCAS(path)).evaluate(
        candidate_ref,
        suite_ref,
        {
            "calibration_runner": lambda *_args: (
                returned if mode == "missing_selection" else (returned, report_ref)
            )
        },
    )
    evaluation_ref = persist_benchmark_evaluation(store, result)
    persisted = from_canonical_bytes(FileSystemCAS(path).get_bytes(evaluation_ref))
    admission = persisted["metadata"]["calibration_metric_sources"]["holdout"][0]
    if mode in {
        "profileless_basis",
        "missing_basis_edge",
        "duplicate_basis",
        "conflicting_input",
        "malformed_basis",
        "missing_basis",
        "missing_input",
    }:
        # Exactly the SAME report payload, selected parent view and fresh store
        # go through the actual welfare join and public autotune evaluator.
        joined = _calibration_execution_source_join(
            _b197_execution_context(
                FileSystemCAS(path),
                source["registry"].bundle_ref,
                f"R_ordered_cross_consumer_{mode}",
            ),
            _b197_execution_state(simulation_ref, report_ref),
            report_ref=report_ref,
            report=returned,
        )
        _, bundle = _run_b197_welfare(
            FileSystemCAS(path),
            source["registry"].bundle_ref,
            simulation_ref,
            report_ref,
            run_id=f"R_ordered_cross_consumer_node_{mode}",
            method="delta",
            weights=[1.0, 1.0],
        )
    expected_source_status = {
        "selected": "matched",
        "missing_selection": "not_established",
        "changed_metrics": "mismatch",
        "missing_basis": "not_established",
        "missing_input": "not_established",
        "malformed_basis": "mismatch",
        "profileless_basis": "not_established",
        "missing_basis_edge": "not_established",
        "duplicate_basis": "mismatch",
        "conflicting_input": "mismatch",
    }[mode]
    if mode in {
        "profileless_basis",
        "missing_basis_edge",
        "duplicate_basis",
        "conflicting_input",
        "malformed_basis",
        "missing_basis",
        "missing_input",
    }:
        observed_sources = {"welfare": joined[0], "autotune": admission["metric_source_status"]}
        assert observed_sources == dict.fromkeys(observed_sources, expected_source_status), (
            observed_sources,
            joined,
            admission,
        )
    else:
        assert admission["metric_source_status"] == expected_source_status
    if mode == "selected":
        assert result.status == "ok"
        assert result.guardrails["calibration_metric_sources_ready"] is True
        assert result.sample_counts == {"selection": 1, "holdout": 1}
        aggregate = report.fit_quality.aggregate
        penalty = 0.0 if aggregate.r2 is None else max(0.0, 1.0 - aggregate.r2)
        fit = 1.0 / (1.0 + aggregate.rmse + aggregate.mae + penalty)
        runtime = 1.0 / (
            1.0
            + float(report.execution_context.get("runtime_seconds", 0.0) or 0.0)
            + len(report.loss_history) / 100.0
        )
        condition = max(float(report.uncertainties.hessian_condition), 1.0)
        curvature_score = 1.0 / (1.0 + math.log10(condition))
        assert result.holdout_metrics["aggregate_fit_quality"] == pytest.approx(
            0.7 * fit + 0.15 * runtime + 0.15 * curvature_score,
        )
    else:
        assert result.status == "limited"
        assert result.promotable is False
        assert result.guardrails["calibration_metric_sources_ready"] is False
        assert "aggregate_fit_quality" not in result.holdout_metrics
        assert result.sample_counts["holdout"] == 0
    if mode in {
        "profileless_basis",
        "missing_basis_edge",
        "duplicate_basis",
        "conflicting_input",
        "malformed_basis",
        "missing_basis",
        "missing_input",
    }:
        # Exactly the SAME report payload, selected parent view and fresh store
        # go through the actual welfare join and public autotune evaluator.
        if joined[0] == "not_established":
            assert not joined[2]
            assert "source_execution_not_established" in joined[1]
        else:
            assert joined[2]
        assert bundle.credible_interval is None
        if mode == "profileless_basis":
            edge = next(
                edge
                for edge in store.get_manifest(report_ref).inputs
                if edge.role == "calibration_execution_input_basis"
            )
            assert edge.manifest_profile_sha256 is None
            # The underlying basis exists and is readable. Only the exact
            # choice is absent; its default view cannot become evidence.
            assert store.get_bytes(edge.artifact_id)
            assert returned.model_dump(mode="json") == report.model_dump(mode="json")
    assert admission["inference_status"] == "unavailable_generic_loss"
    assert admission["evidence_grade"] == "candidate"


def test_selected_input_publisher_cannot_substitute_another_coherent_profile_before_fit(
    ordered_batch_case,
    monkeypatch,
):
    import polisyos.foundry.calibration.calibrator as producer
    from polisyos.foundry.calibration.execution_basis import (
        canonical_input_sha256,
        resolve_calibration_ordered_batch_input,
    )

    path, _, _, _, _, basis_ref = ordered_batch_case
    store = FileSystemCAS(path)
    _, input_ref = _ordered_input_ref_for_basis(store, basis_ref)
    profile, values = resolve_calibration_ordered_batch_input(store, input_ref)
    values = dict(values)
    values["weights"] = np.asarray(values["weights"])[::-1].copy()
    payload = profile.model_dump(mode="json")
    payload["weights"] = values["weights"].tolist()
    payload["consumed_profile_sha256"] = canonical_input_sha256(values)
    manifest = store.get_manifest(input_ref)
    foreign = store.put_json(
        payload,
        PutOptions(
            kind=input_ref.kind,
            media_type="application/json",
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    resolve_calibration_ordered_batch_input(store, foreign)
    monkeypatch.setattr(
        producer, "put_calibration_ordered_batch_input", lambda *_args, **_kwargs: foreign
    )
    fit_calls = []

    def forbid_fit(_self):
        fit_calls.append(True)
        raise AssertionError("fit must not start with a substituted selected input")

    monkeypatch.setattr(producer.Calibrator, "run", forbid_fit)
    with pytest.raises(ValueError, match="ordered_input_writer_returned_a_foreign_request"):
        _run_ordered_b197_calibrator(store)
    assert fit_calls == []


def test_new_batch_backend_unavailable_remains_limited_and_never_promotes_curvature(
    ordered_batch_case,
    monkeypatch,
):
    import polisyos.foundry.calibration.execution_basis as owner

    path, source, report_ref, report, simulation_ref, _ = ordered_batch_case
    monkeypatch.setattr(owner.platform, "machine", lambda: "unavailable-architecture")
    joined = _calibration_execution_source_join(
        _b197_execution_context(
            FileSystemCAS(path), source["registry"].bundle_ref, "R_ordered_backend"
        ),
        _b197_execution_state(simulation_ref, report_ref),
        report_ref=report_ref,
        report=report,
    )
    assert joined[0] == "not_established", joined
    assert "ordered_numeric_profile_unavailable" in joined[1]
    assert "calibration_batch_curvature_only" in joined[1]
    _, bundle = _run_b197_welfare(
        FileSystemCAS(path),
        source["registry"].bundle_ref,
        simulation_ref,
        report_ref,
        run_id="R_ordered_unavailable_welfare",
        method="delta",
        weights=[1.0, 1.0],
    )
    assert bundle.credible_interval is None
    assert "calibration_generic_batch_inference_unavailable" in bundle.warnings


def test_new_batch_scope_cannot_use_legacy_v1_wire_projection(ordered_batch_case):
    from polisyos.foundry.calibration.report import serialize_calibration_report_v1

    _, _, _, report, _, _ = ordered_batch_case
    with pytest.raises(ValueError, match="cannot_be_projected_as_legacy_v1"):
        serialize_calibration_report_v1(report)


def test_batch_report_preserves_actual_external_welfare_mean_quantile_and_weight_law(
    ordered_batch_case,
):
    path, source, report_ref, _, simulation_ref, _ = ordered_batch_case
    store = FileSystemCAS(path)
    external = UncertaintyEnvelope(
        point_estimate=0.5,
        confidence_interval=(0.0, 1.0),
        confidence_level=None,
        distribution_family=DistributionFamily.UNIFORM,
        source=UncertaintySource.MANUAL,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
        gate_eligible=False,
        distribution_payload=ParametricFitCarrier(
            family=DistributionFamily.UNIFORM,
            parameters={"low": 0.0, "high": 1.0},
            support=(0.0, 1.0),
        ),
        metadata={"param_name": "C.rate", "std": 1.0 / math.sqrt(12.0)},
    )
    external_ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(store), external)
    arrays = []
    for weight in (1.0, 2.0):
        _, bundle = _run_b197_welfare(
            FileSystemCAS(path),
            source["registry"].bundle_ref,
            simulation_ref,
            report_ref,
            run_id=f"R_ordered_external_weight_{weight}",
            method="monte_carlo",
            labels=["C"],
            weights=[weight],
            input_envelopes={"C.rate": external_ref.model_dump(mode="json")},
        )
        assert bundle.point_estimate == pytest.approx(weight)
        assert bundle.sample_bundle_ref is not None
        samples = load_welfare_sample_bundle(
            _ensure_ir_artifact_store(FileSystemCAS(path)), bundle.sample_bundle_ref
        )
        values = np.asarray(samples.welfare_draws, dtype=np.float64)
        components = np.asarray(samples.welfare_total_component_draws, dtype=np.float64)
        assert values.shape == (100,)
        assert components.shape == (100, 1)
        assert np.array_equal(values, weight * components[:, 0])
        assert bundle.credible_interval == pytest.approx(np.quantile(values, [0.025, 0.975]))
        propagation = from_canonical_bytes(
            store.get_bytes(ArtifactID.model_validate(bundle.diagnostics["propagation_report_ref"]))
        )
        assert propagation["draw_summary"]["welfare_mean"] == pytest.approx(float(np.mean(values)))
        assert propagation["calibration_inference_status"] == "curvature_only"
        assert propagation["source_execution_status"] == "matched"
        arrays.append(values)
    assert np.array_equal(arrays[1], 2.0 * arrays[0])


def _ordered_report_with_unavailable_or_invalid_source(store, report_ref, report, basis_ref, kind):
    """Use real Core writes with an actually absent selected view; never delete CAS bytes."""
    basis = load_calibration_execution_input_basis(store, basis_ref)
    assert basis.ordered_batch_input_ref is not None
    missing_profile = "sha256:" + "f" * 64
    original_input = basis.ordered_batch_input_ref
    report_body = report.model_dump(mode="python")
    if kind == "basis":
        selected_basis = basis_ref.model_copy(update={"manifest_profile_sha256": missing_profile})
        assert not store.has_manifest_view(selected_basis.artifact_id, missing_profile)
    elif kind in {"profileless_basis", "missing_basis_edge", "duplicate_basis"}:
        selected_basis = (
            basis_ref.model_copy(update={"manifest_profile_sha256": None})
            if kind == "profileless_basis"
            else basis_ref
        )
    else:
        basis_body = basis.model_dump(mode="json")
        inputs = list(store.get_manifest(basis_ref).inputs)
        if kind == "input":
            missing_input = original_input.model_copy(
                update={"manifest_profile_sha256": missing_profile}
            )
            assert not store.has_manifest_view(missing_input.artifact_id, missing_profile)
            basis_body["ordered_batch_input_ref"] = missing_input.model_dump(mode="json")
            basis_body["runtime_input_roster"][-1]["source_ref"] = missing_input.model_dump(
                mode="json"
            )
            inputs = [
                input_ref_from_artifact_ref(missing_input, role="ordered_batch_input")
                if edge.role == "ordered_batch_input"
                else edge
                for edge in inputs
            ]
            scope = report.ordered_batch_execution.model_copy(
                update={"selected_input_ref": missing_input}
            )
            report_body["ordered_batch_execution"] = scope.model_dump(mode="python")
        elif kind == "conflicting_input":
            alternate = store.put_json(
                from_canonical_bytes(store.get_bytes(original_input)),
                PutOptions(
                    kind=original_input.kind,
                    media_type=original_input.media_type,
                    schema=SchemaInfo(
                        name="polisyos.foundry.CalibrationOrderedBatchInput", version="9.9"
                    ),
                    inputs=store.get_manifest(original_input).inputs,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
            assert alternate.manifest_profile_sha256 != original_input.manifest_profile_sha256
            inputs = [
                input_ref_from_artifact_ref(alternate, role="ordered_batch_input")
                if edge.role == "ordered_batch_input"
                else edge
                for edge in inputs
            ]
        else:
            assert kind == "malformed_basis"
            basis_body["ordered_batch_input_value_sha256"] = "malformed-present-digest"
        manifest = store.get_manifest(basis_ref)
        selected_basis = store.put_json(
            basis_body,
            PutOptions(
                kind=basis_ref.kind,
                media_type=basis_ref.media_type,
                schema=manifest.artifact_schema,
                inputs=inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    manifest = store.get_manifest(report_ref)
    inputs = [
        input_ref_from_artifact_ref(selected_basis, role="calibration_execution_input_basis")
        if edge.role == "calibration_execution_input_basis"
        else edge
        for edge in manifest.inputs
    ]
    if kind == "missing_basis_edge":
        inputs = [edge for edge in inputs if edge.role != "calibration_execution_input_basis"]
    elif kind == "duplicate_basis":
        inputs.extend(
            edge for edge in tuple(inputs) if edge.role == "calibration_execution_input_basis"
        )
    selected_report = CalibrationReport.model_validate(report_body)
    selected_ref = store.put_json(
        selected_report,
        PutOptions(
            kind=report_ref.kind,
            media_type=report_ref.media_type,
            schema=manifest.artifact_schema,
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    return selected_report, selected_ref, selected_basis


@pytest.mark.parametrize("kind", ["basis", "input", "malformed_basis"])
def test_fresh_selected_reader_distinguishes_unavailable_evidence_from_present_corruption(
    ordered_batch_case,
    kind,
):
    from polisyos.foundry.calibration.execution_basis import replay_ordered_batch_report_projection

    path, source, report_ref, report, simulation_ref, basis_ref = ordered_batch_case
    store = FileSystemCAS(path)
    altered, selected_report, selected_basis = _ordered_report_with_unavailable_or_invalid_source(
        store,
        report_ref,
        report,
        basis_ref,
        kind,
    )
    fresh = FileSystemCAS(path)
    expected = "mismatch" if kind == "malformed_basis" else "not_established"
    status, codes = replay_ordered_batch_report_projection(fresh, selected_basis, selected_report)
    assert status == expected, codes
    joined = _calibration_execution_source_join(
        _b197_execution_context(fresh, source["registry"].bundle_ref, f"R_ordered_source_{kind}"),
        _b197_execution_state(simulation_ref, selected_report),
        report_ref=selected_report,
        report=altered,
    )
    assert joined[0] == expected, joined
    if kind == "malformed_basis":
        assert "calibration_execution_basis_invalid" in joined[2]
    else:
        assert "calibration_execution_input_unavailable" in joined[1]
        assert joined[2] == ()
    _, bundle = _run_b197_welfare(
        FileSystemCAS(path),
        source["registry"].bundle_ref,
        simulation_ref,
        selected_report,
        run_id=f"R_ordered_source_node_{kind}",
        method="delta",
        weights=[1.0, 1.0],
    )
    assert bundle.credible_interval is None
    expected_warning = (
        "calibration_execution_basis_invalid"
        if kind == "malformed_basis"
        else "calibration_generic_batch_inference_unavailable"
    )
    assert expected_warning in bundle.warnings


@pytest.mark.parametrize("setting", ["partitionable", "implementation"])
def test_selected_replay_binds_actual_prng_algorithm_context(ordered_batch_case, setting):
    import jax

    from polisyos.foundry.calibration.execution_basis import (
        CalibrationOrderedBatchBackendUnavailable,
        replay_ordered_batch_report_projection,
        resolve_calibration_ordered_batch_input,
    )

    path, source, report_ref, report, simulation_ref, basis_ref = ordered_batch_case
    store = FileSystemCAS(path)
    _, input_ref = _ordered_input_ref_for_basis(store, basis_ref)
    profile, _ = resolve_calibration_ordered_batch_input(store, input_ref)
    assert profile.jax_default_prng_impl == "threefry2x32"
    key = jnp.asarray(profile.row_keys[0], dtype=jnp.uint32)
    original_split = jax.random.split(key)
    context = (
        jax.threefry_partitionable(not profile.jax_threefry_partitionable)
        if setting == "partitionable"
        else jax.default_prng_impl("rbg")
    )
    with context:
        if setting == "partitionable":
            changed_split = jax.random.split(key)
            assert not jnp.array_equal(changed_split, original_split)
        else:
            assert jax.random.key_data(jax.random.key(91)).shape != key.shape
        with pytest.raises(
            CalibrationOrderedBatchBackendUnavailable, match="numeric_profile_unavailable"
        ):
            resolve_calibration_ordered_batch_input(FileSystemCAS(path), input_ref)
        status, codes = replay_ordered_batch_report_projection(
            FileSystemCAS(path), basis_ref, report_ref
        )
        assert status == "not_established", codes
        assert "ordered_numeric_profile_unavailable" in codes
        joined = _calibration_execution_source_join(
            _b197_execution_context(
                FileSystemCAS(path), source["registry"].bundle_ref, f"R_ordered_prng_{setting}"
            ),
            _b197_execution_state(simulation_ref, report_ref),
            report_ref=report_ref,
            report=report,
        )
        assert joined[0] == "not_established", joined
        assert "ordered_numeric_profile_unavailable" in joined[1]
    # The context manager restores the actual settings; no persistent configuration edit.
    assert resolve_calibration_ordered_batch_input(FileSystemCAS(path), input_ref)[0] == profile


def test_actual_selected_npz_and_typed_json_reach_fresh_welfare(ordered_batch_case):
    from io import BytesIO

    from polisyos.foundry.calibration import read_calibration_source
    from polisyos.foundry.execute import load_state_snapshot

    path, source, report_ref, report, simulation_ref, basis_ref = ordered_batch_case
    fresh = FileSystemCAS(path)
    basis = load_calibration_execution_input_basis(fresh, basis_ref)
    snapshot_ref = basis.base_state_snapshot_ref
    manifest = fresh.get_manifest(snapshot_ref)
    edge = next(edge for edge in manifest.inputs if edge.role == "state_blob")
    binary = read_calibration_source(
        fresh,
        role="state_blob",
        inputs=manifest.inputs,
        expected_kind="foundry.state_blob",
        expected_media_type="application/x-npz",
        decoder=lambda _ref, _manifest, value: value,
    )
    assert binary.status == "matched", binary
    assert binary.ref.artifact_id == edge.artifact_id
    assert fresh.get_manifest(binary.ref).canon is None
    # The same real producer NPZ exercises the public raw result contract. It
    # contains no JSON calibration config; the decoder may not turn that fact
    # into a qualified domain DTO, including through a native container.
    binary_manifest = fresh.get_manifest(binary.ref)
    coerced_config = CalibrationConfig.model_validate({"max_steps": "200"})
    foreign_ref = binary.ref.model_copy(update={"kind": "tests.foreign_state_blob"})
    foreign_manifest = binary_manifest.model_copy(update={"kind": "tests.foreign_state_blob"})
    raw_outputs = {
        "domain_model": coerced_config,
        "nested_domain_model": {"candidate": [coerced_config]},
        "foreign_ref": foreign_ref,
        "foreign_manifest": foreign_manifest,
    }
    observed_raw = {
        name: read_calibration_source(
            FileSystemCAS(path),
            role="state_blob",
            ref=binary.ref,
            expected_kind="foundry.state_blob",
            expected_media_type=None,
            decoder=lambda _ref, _manifest, _payload, output=output: output,
        )
        for name, output in raw_outputs.items()
    }
    selected_metadata = (
        read_calibration_source(
            FileSystemCAS(path),
            role="state_blob",
            ref=binary.ref,
            expected_media_type=None,
            decoder=decoder,
        )
        for decoder in (
            lambda selected, _manifest, _payload: selected,
            lambda _selected, selected_manifest, _payload: selected_manifest,
        )
    )
    ref_positive, manifest_positive = tuple(selected_metadata)
    assert ref_positive.status == manifest_positive.status == "matched"
    assert ref_positive.require_value() == binary.ref
    assert manifest_positive.require_value() == binary_manifest
    assert {name: result.status for name, result in observed_raw.items()} == dict.fromkeys(
        raw_outputs, "mismatch"
    ), "raw_npz_domain_and_metadata_projection_must_be_admitted_by_result_contract"
    assert all(result.value is None for result in observed_raw.values())
    with np.load(BytesIO(binary.require_value()), allow_pickle=False) as arrays:
        assert arrays.files
    state = load_state_snapshot(FileSystemCAS(path), snapshot_ref=snapshot_ref)
    assert state.agents.income.shape == source["base_state"].agents.income.shape
    joined = _calibration_execution_source_join(
        _b197_execution_context(
            FileSystemCAS(path), source["registry"].bundle_ref, "R_npz_json_positive"
        ),
        _b197_execution_state(simulation_ref, report_ref),
        report_ref=report_ref,
        report=report,
    )
    _, bundle = _run_b197_welfare(
        FileSystemCAS(path),
        source["registry"].bundle_ref,
        simulation_ref,
        report_ref,
        run_id="R_npz_json_positive_node",
        method="delta",
        weights=[1.0, 1.0],
    )
    assert joined[0] == "matched", joined
    assert bundle.credible_interval is None
    assert "calibration_generic_batch_inference_unavailable" in bundle.warnings


def _schema_numeric_paths(value, schema, root, path=()):
    """Derive real typed numeric fields from the owner's JSON schema and fixture."""
    if "$ref" in schema:
        selected = root
        for key in schema["$ref"].removeprefix("#/").split("/"):
            selected = selected[key]
        yield from _schema_numeric_paths(value, selected, root, path)
        return
    for key in ("anyOf", "oneOf", "allOf"):
        for branch in schema.get(key, ()):
            yield from _schema_numeric_paths(value, branch, root, path)
    if schema.get("type") in {"number", "integer"} and type(value) in {int, float}:
        if math.isfinite(value):
            yield path
    if isinstance(value, dict):
        for key, item in value.items():
            child = schema.get("properties", {}).get(key, schema.get("additionalProperties", {}))
            if isinstance(child, dict):
                yield from _schema_numeric_paths(item, child, root, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            prefix = schema.get("prefixItems", ())
            child = prefix[index] if index < len(prefix) else schema.get("items", {})
            if isinstance(child, dict):
                yield from _schema_numeric_paths(item, child, root, (*path, index))


@pytest.mark.parametrize(
    "contract", ["report", "basis", "input", "config", "snapshot", "graph", "plan"]
)
def test_selected_contract_models_reject_schema_numeric_string_coercion(
    ordered_batch_case, contract
):
    from copy import deepcopy

    from jsonschema import Draft202012Validator

    from polisyos.core.contracts.foundry import ExecPlan, ProgramGraph, StateSnapshot
    from polisyos.foundry.calibration import (
        CalibrationExecutionInputBasis,
        CalibrationOrderedBatchInput,
        read_calibration_model_source,
        resolve_calibration_ordered_batch_input,
    )

    path, _, report_ref, _, _, basis_ref = ordered_batch_case
    store = FileSystemCAS(path)
    basis, input_ref = _ordered_input_ref_for_basis(store, basis_ref)
    profile, _ = resolve_calibration_ordered_batch_input(store, input_ref)
    refs = {
        "report": (report_ref, CalibrationReport),
        "basis": (basis_ref, CalibrationExecutionInputBasis),
        "input": (input_ref, CalibrationOrderedBatchInput),
        "config": (basis.calibration_config_ref, CalibrationConfig),
        "snapshot": (profile.rows[0].state_snapshot_ref, StateSnapshot),
        "graph": (basis.program_graph_ref, ProgramGraph),
        "plan": (basis.exec_plan_ref, ExecPlan),
    }
    selected, model = refs[contract]
    manifest = store.get_manifest(selected)
    payload = from_canonical_bytes(store.get_bytes(selected))
    positive = read_calibration_model_source(
        FileSystemCAS(path),
        role=contract,
        ref=selected,
        expected_kind=selected.kind,
        expected_schema=manifest.artifact_schema.name,
        model=model,
        decoder=lambda _ref, _manifest, value: value,
    )
    assert positive.status == "matched", (contract, positive)
    schema = model.model_json_schema()
    validator = Draft202012Validator(schema)
    # The schema's own JSON view gives an independent wire-type oracle and
    # preserves genuine numeric|string unions as explicit exemptions.
    payload = positive.require_value().model_dump(mode="json", by_alias=True)
    if not validator.is_valid(payload):
        pytest.skip(
            f"{contract} model JSON view is outside this JSON-schema oracle; source strict read is separate"
        )
    paths = sorted(set(_schema_numeric_paths(payload, schema, schema)), key=repr)
    if not paths:
        pytest.skip(f"{contract} fixture has no schema-typed finite numeric leaf")
    # Every actual schema-directed finite numeric leaf is included. Any-typed
    # metadata is not falsely claimed to impose a numeric wire contract.
    checked = 0
    for location in paths:
        changed = deepcopy(payload)
        cursor = changed
        for key in location[:-1]:
            cursor = cursor[key]
        key = location[-1]
        cursor[key] = str(cursor[key])
        if validator.is_valid(changed):
            continue  # The actual schema permits that string branch; not a numeric-only gate.
        checked += 1
        altered = store.put_json(
            changed,
            PutOptions(
                kind=selected.kind,
                media_type=selected.media_type,
                schema=manifest.artifact_schema,
                inputs=manifest.inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False, exclude_none=False),
            return_selected_profile=True,
        )
        result = read_calibration_model_source(
            FileSystemCAS(path),
            role=contract,
            ref=altered,
            expected_kind=selected.kind,
            expected_schema=manifest.artifact_schema.name,
            model=model,
            decoder=lambda _ref, _manifest, value: value,
        )
        assert result.status == "mismatch", (contract, location, result)

    if checked == 0:
        pytest.skip(f"{contract} fixture has no numeric-only leaf under its actual schema")


@pytest.mark.parametrize("condition", ["missing_view", "missing_blob", "numeric_string"])
def test_actual_welfare_node_qualifies_report_before_any_evaluator(
    ordered_batch_case, tmp_path, monkeypatch, condition
):
    from polisyos.scientist.nodes.builtins.simulate import propagate_welfare as module

    path, source, report_ref, report, simulation_ref, _ = ordered_batch_case
    store = FileSystemCAS(path)
    manifest = store.get_manifest(report_ref)
    payload = report.model_dump(mode="python")
    payload["execution_context"] = {
        **payload["execution_context"],
        "source_intake_case": str(tmp_path),
    }
    if condition == "numeric_string":
        payload["total_loss"] = str(payload["total_loss"])
    selected = store.put_json(
        payload,
        PutOptions(
            kind=report_ref.kind,
            media_type=report_ref.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False, exclude_none=False),
        return_selected_profile=True,
    )
    assert selected.artifact_id != report_ref.artifact_id
    blob, _ = store._paths(selected.artifact_id)
    retained = blob.read_bytes()
    if condition == "missing_view":
        selected = selected.model_copy(update={"manifest_profile_sha256": "sha256:" + "f" * 64})
        assert not store.has_manifest_view(selected.artifact_id, selected.manifest_profile_sha256)
    elif condition == "missing_blob":
        assert store.has_manifest_view(selected.artifact_id, selected.manifest_profile_sha256)
        blob.unlink()
        assert store._layout.view_manifest_path(
            selected.artifact_id, selected.manifest_profile_sha256
        ).is_file()
    calls = []

    def no_evaluator(*_args, **_kwargs):
        calls.append("evaluator")
        pytest.fail("unqualified selected report reached the actual welfare evaluator")

    monkeypatch.setattr(module, "_build_simulation_fn", no_evaluator)
    monkeypatch.setattr(module, "_propagate_credible_interval", no_evaluator)
    escaped = None
    outcome = bundle = None
    try:
        outcome, bundle = _run_b197_welfare(
            FileSystemCAS(path),
            source["registry"].bundle_ref,
            simulation_ref,
            selected,
            run_id=f"R_report_intake_{condition}",
            method="delta",
            weights=[1.0, 1.0],
            require_success=False,
        )
    except (FileNotFoundError, PermissionError, ValueError, TypeError) as error:
        escaped = error
    finally:
        if condition == "missing_blob":
            blob.write_bytes(retained)
    assert escaped is None, f"untyped report intake escaped the actual node: {escaped!r}"
    assert outcome is not None
    assert outcome.status == "fail"
    assert outcome.error.code == "welfare.calibration_source_invalid"
    assert outcome.error.details["source_status"] == (
        "mismatch" if condition == "numeric_string" else "not_established"
    )
    assert not calls
    assert bundle is None
    assert outcome.artifacts == []
    assert ARTIFACT_WELFARE_BUNDLE_REF not in outcome.state.artifacts_index


def test_registry_selected_source_uses_strict_owner_for_each_consumed_member(ordered_batch_case):
    from copy import deepcopy
    from dataclasses import fields

    from jsonschema import Draft202012Validator

    from polisyos.foundry.calibration import read_calibration_registry_source

    path, _, _, _, _, basis_ref = ordered_batch_case
    store = FileSystemCAS(path)
    basis = load_calibration_execution_input_basis(store, basis_ref)
    ref = basis.registry_bundle_ref
    manifest = store.get_manifest(ref)
    payload = from_canonical_bytes(store.get_bytes(ref))
    positive = read_calibration_registry_source(FileSystemCAS(path), ref)
    assert positive.status == "matched", positive
    content = positive.require_value()
    checked = 0
    for field in fields(type(content)):
        if field.name == "bundle_ref" or getattr(content, field.name) is None:
            continue
        model_value = getattr(content, field.name)
        model = type(model_value)
        schema = model.model_json_schema()
        validator = Draft202012Validator(schema)
        value = model_value.model_dump(mode="json", by_alias=True)
        if not validator.is_valid(value):
            continue  # This member has no usable schema JSON view for this numeric oracle.
        selected = ArtifactRef.model_validate(payload[field.name])
        selected_manifest = store.get_manifest(selected)
        for location in sorted(set(_schema_numeric_paths(value, schema, schema)), key=repr):
            changed = deepcopy(value)
            cursor = changed
            for key in location[:-1]:
                cursor = cursor[key]
            cursor[location[-1]] = str(cursor[location[-1]])
            if validator.is_valid(changed):
                continue  # The owner's genuine string branch is not numeric-only.
            changed_ref = store.put_json(
                changed,
                PutOptions(
                    kind=selected.kind,
                    media_type=selected.media_type,
                    schema=selected_manifest.artifact_schema,
                    inputs=selected_manifest.inputs,
                ),
                canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=False, exclude_none=False),
                return_selected_profile=True,
            )
            changed_bundle = deepcopy(payload)
            changed_bundle[field.name] = changed_ref.model_dump(mode="json")
            edges = [
                input_ref_from_artifact_ref(changed_ref, role=edge.role)
                if edge.artifact_id == selected.artifact_id
                and edge.manifest_profile_sha256 == selected.manifest_profile_sha256
                else edge
                for edge in manifest.inputs
            ]
            bundle_ref = store.put_json(
                changed_bundle,
                PutOptions(
                    kind=ref.kind,
                    media_type=ref.media_type,
                    schema=manifest.artifact_schema,
                    inputs=edges,
                ),
                canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
                return_selected_profile=True,
            )
            result = read_calibration_registry_source(FileSystemCAS(path), bundle_ref)
            assert result.status == "mismatch", (field.name, location, result)
            checked += 1
            break  # One schema-derived discriminator per actual consumed member, not every field.
    if checked == 0:
        pytest.skip(
            "this registry fixture has no numeric-only schema leaf; strict positive is separate"
        )
