from __future__ import annotations

import logging
import math

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    EquilibriumMultiplicityDiagnostics,
    EquilibriumMultiplicityReport,
    EquilibriumMultiplicityReportRef,
    EquilibriumSearchProtocol,
    ExecPlan,
    ExecPlanRef,
    FeedbackResultRef,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
    Metrics,
    MetricsRef,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.calibration.report import (
    CalibrationCoordinateProjection,
    CalibrationReport,
    CalibrationUncertainty,
    put_calibration_config,
    put_calibration_report,
)
from polisyos.foundry.calibration.uncertainty_adapter import envelope_from_calibration_param
from polisyos.foundry.contracts.state import GlobalState
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
from polisyos.ir.kernel.mechanisms import DEFAULT_MECHANISM_REGISTRY
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY
from polisyos.ir.registry.refs import ArtifactRefModel, UncertaintyEnvelopeRef
from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import (
    PropagateWelfareNode,
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


class _RecordingFileSystemCAS(FileSystemCAS):
    def __init__(self, root) -> None:
        super().__init__(root)
        self.read_selectors: list[ArtifactID | ArtifactRef | str] = []

    def get_bytes(self, artifact_id: ArtifactID | ArtifactRef | str) -> bytes:
        self.read_selectors.append(artifact_id)
        return super().get_bytes(artifact_id)


def test_propagate_welfare_node_writes_partial_bundle_for_pe_only(tmp_path) -> None:
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
    sim_result_ref = SimulationResultRef.model_validate(selected_view.model_dump(mode="python"))

    state = ExperimentState(
        run_id="R_welfare_partial",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id),
        },
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
        params={"welfare_weights": {"policy_value": 1.0}},
    )

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

    updated_payload = from_canonical_bytes(
        store.get_bytes(outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF].artifact_id)
    )
    updated_sim = SimulationResult.model_validate(updated_payload)
    assert updated_sim.welfare_bundle_ref is not None
    updated_sim_result_ref = outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF]
    updated_sim_manifest = store.get_manifest(updated_sim_result_ref)
    updated_input_profiles = {
        item.role: item.manifest_profile_sha256 for item in updated_sim_manifest.inputs
    }
    assert (
        updated_input_profiles["base_simulation_result"] == sim_result_ref.manifest_profile_sha256
    )
    assert updated_input_profiles["welfare_bundle"] == bundle_ref.manifest_profile_sha256


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


def test_propagate_welfare_node_persists_channel_decomposition_artifact(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store, registry_bundle=registry_bundle, run_id="R_welfare_channels"
    )
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.welfare.channels"))

    env_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store),
        UncertaintyEnvelope(
            point_estimate=0.52,
            confidence_interval=(0.40, 0.64),
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
                "artifact_id": "sha256:" + "1" * 64,
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
        },
        PutOptions(kind="foundry.exec_plan", media_type="application/json"),
    )
    metrics_ref = store.put_json(
        Metrics(values={"policy_value": 1.52}),
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
        run_id="R_welfare_channels",
        inputs={
            INPUT_DATA_SNAPSHOT_REF: DataSnapshotRef(artifact_id=data_snapshot_ref.artifact_id),
        },
        artifacts_index={ARTIFACT_SIMULATION_RESULT_REF: sim_result_ref},
        params={
            "welfare_metric_order": ["policy_value"],
            "welfare_weights": {"policy_value": 1.0},
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
            },
        },
    )

    outcome = PropagateWelfareNode().execute(ctx, state)
    assert outcome.status == "ok"

    bundle = load_welfare_bundle(
        _ensure_ir_artifact_store(store), outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF]
    )
    assert bundle.channel_decomposition_ref is not None

    artifact = load_channel_decomposition_artifact(
        _ensure_ir_artifact_store(store), bundle.channel_decomposition_ref
    )
    assert artifact.identification_status.value == "identified"
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
    assert malformed_outcome.error.code == "ERROR_WELFARE_UNCERTAINTY_SCALE_INVALID"

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


def _run_b197_tied_calibrator(
    store: FileSystemCAS,
    *,
    incomplete_projection: bool = False,
) -> tuple[ArtifactRef, CalibrationReport]:
    dummy_id = ArtifactID.from_sha256_hex("0" * 64)
    graph_ref = ArtifactRef(
        artifact_id=dummy_id,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )
    nodes = [
        ProgramNode(
            node_id=node_id,
            node_kind="mechanism",
            mechanism_type="income_tax",
            params_ref=None,
            outputs=["agents.income", "government.balance"],
        )
        for node_id in ("A", "B")
    ]
    graph = ProgramGraph(
        ir_ref=graph_ref,
        nodes=nodes,
        edges=[],
        entrypoints=[],
    )
    plan = ExecPlan(program_ref=ProgramGraphRef(artifact_id=dummy_id), order=["A", "B"])
    base_state = GlobalState.empty(n_agents=1, n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(
            income=jnp.asarray([100.0]),
            reported_income=jnp.asarray([100.0]),
        ),
        government_balance=jnp.asarray(0.0),
    )
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
        hessian={"enabled": True, "damping": 1e-6},
    )
    config_ref = put_calibration_config(store, config)
    inputs = CalibratorInputs(
        config=config,
        program_graph=graph,
        exec_plan=plan,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        parameter_loader=lambda _node: {
            "params": {"rate": 0.2},
            "schedule": {"start_step": 0, "end_step": 10},
        },
        raw_targets={"gov_balance": jnp.asarray([36.0])},
        controls_seq=jnp.arange(1),
    )

    report = Calibrator(inputs).run()
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
    expected_coordinate_variance = 0.01 if incomplete_projection else 0.0025
    assert report.uncertainties.covariance[0][0] == pytest.approx(
        expected_coordinate_variance,
        rel=1e-4,
    )

    report_ref = put_calibration_report(
        store,
        report,
        inputs=[InputRef(artifact_id=str(config_ref.artifact_id), role="calibration_config")],
    )
    report_manifest = store.get_manifest(report_ref)
    assert report_manifest.artifact_schema.version == "2.0"
    assert any(item.role == "calibration_config" for item in report_manifest.inputs)
    persisted_payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    persisted = CalibrationReport.model_validate(persisted_payload)
    assert persisted.schema_version == "2.0"
    if incomplete_projection:
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
    return report_ref, persisted


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
        Metrics(values={"A": 1.0, "B": 1.0, "C": 1.0}),
        PutOptions(kind="foundry.metrics", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    sim_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )
    return sim_ref


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
) -> tuple[object, object]:
    run = RunContext.start(store=store, registry_bundle=registry_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger(f"test.welfare.{run_id}"),
    )
    response_labels = labels or ["A", "B"]
    pe_sensitivity = {
        label: {f"{label}.rate": 1.0} for label in response_labels if label in {"A", "B"}
    }
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
    assert outcome.status == "ok", outcome.error
    bundle = load_welfare_bundle(
        _ensure_ir_artifact_store(store),
        outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF],
    )
    return outcome, bundle


def _manifest_has_input(store: FileSystemCAS, target_ref, source_ref, role: str) -> bool:
    manifest = store.get_manifest(target_ref.artifact_id)
    return any(
        item.role == role and str(item.artifact_id) == str(source_ref.artifact_id)
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
        inputs=store.get_manifest(source_report_ref).inputs,
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
        expected_pairs = [("A.rate", "B.rate", 0.5 * calibration_std / math.sqrt(12.0))]
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
        expected_pairs = [
            ("A.rate", "C.rate", -3.2698671302839551e-18),
            ("B.rate", "C.rate", 0.5 * 0.1 / math.sqrt(12.0)),
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
        (left, right): covariance_value for left, right, covariance_value in expected_pairs
    }
    assert set(observed_pairs) == set(expected_pair_map)
    for pair, covariance_value in expected_pair_map.items():
        assert observed_pairs[pair] == pytest.approx(
            covariance_value,
            rel=1e-12,
            abs=1e-30,
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
        inputs=store.get_manifest(source_ref).inputs,
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
        inputs=store.get_manifest(report_ref).inputs,
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
    calibration_inputs = store.get_manifest(report_ref).inputs
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
