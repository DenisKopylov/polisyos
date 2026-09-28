from __future__ import annotations

import logging
import math

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import (
    EquilibriumMultiplicityDiagnostics,
    EquilibriumMultiplicityReport,
    EquilibriumMultiplicityReportRef,
    EquilibriumSearchProtocol,
    ExecPlanRef,
    FeedbackResultRef,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
    Metrics,
    MetricsRef,
    SimulationResult,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.calibration.report import CalibrationReport, CalibrationUncertainty
from polisyos.foundry.calibration.uncertainty_adapter import envelope_from_calibration_param
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
from polisyos.ir.registry.refs import ArtifactRefModel, UncertaintyEnvelopeRef
from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import (
    PropagateWelfareNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.phase3 import (
    Phase3CertificateStatus,
    phase3_gate_reference_blockers,
    resolve_phase3_gate,
)


def test_propagate_welfare_node_writes_partial_bundle_for_pe_only(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_welfare_partial")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.welfare.partial"))

    env_ref = persist_uncertainty_envelope(
        store,
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
    sim_result_ref = store.put_json(
        SimulationResult(
            exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
            metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        ),
        PutOptions(kind="foundry.simulation_result", media_type="application/json"),
    )

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
    assert ARTIFACT_WELFARE_BUNDLE_REF in outcome.state.artifacts_index

    bundle = load_welfare_bundle(store, outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF])
    assert bundle.point_estimate == 10.0
    assert bundle.credible_interval is not None
    assert bundle.robust_interval == (8.0, 12.0)
    assert bundle.status.value == "partial"
    assert "ge_operator_missing_pe_only" in bundle.warnings
    assert bundle.sample_bundle_ref is not None
    assert bundle.sensitivity_diagnostics_ref is not None

    sample_bundle = load_welfare_sample_bundle(store, bundle.sample_bundle_ref)
    assert len(sample_bundle.welfare_draws) >= 50

    updated_payload = from_canonical_bytes(
        store.get_bytes(outcome.state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF].artifact_id)
    )
    updated_sim = SimulationResult.model_validate(updated_payload)
    assert updated_sim.welfare_bundle_ref is not None


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
    bundle = load_welfare_bundle(store, outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF])
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
    bundle = load_welfare_bundle(store, outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF])
    assert bundle.social_weight_ref is not None
    assert bundle.social_weight_ref.kind == "ir.social_weight_manifest"
    manifest = load_social_weight_manifest(store, bundle.social_weight_ref)
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
        store,
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

    bundle = load_welfare_bundle(store, outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF])
    assert bundle.channel_decomposition_ref is not None

    artifact = load_channel_decomposition_artifact(store, bundle.channel_decomposition_ref)
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
        store,
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

    bundle = load_welfare_bundle(store, outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF])
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
    ge_matrix_ref = ArtifactRefModel.model_validate(
        ge_matrix_artifact_ref.model_dump(mode="json")
    )
    ge_uncertainty_ref = persist_ge_uncertainty_bundle(
        store,
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
                "welfare_pe_sensitivity": {
                    "policy_value": dict.fromkeys(envelope_refs, 1.0)
                },
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

        envelope_ref = persist_uncertainty_envelope(store, envelope)
        persisted_envelope_refs.append(envelope_ref)
        persisted_source = load_uncertainty_envelope(store, envelope_ref)
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
            state.params["welfare_input_envelopes"]["node.unused"] = (
                persisted_envelope_refs[0].model_dump(mode="json")
            )
        outcome = PropagateWelfareNode().execute(ctx, state)
        assert outcome.status == "ok"
        bundle = load_welfare_bundle(
            store,
            outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF],
        )
        status_observations.append(
            (
                bundle.status.value,
                "input_uncertainty_not_gate_eligible" in bundle.warnings,
            )
        )
        assert bundle.sample_bundle_ref is not None
        persisted_draws = load_welfare_sample_bundle(store, bundle.sample_bundle_ref)
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
        persisted_gate_observations.append(
            "phase3.welfare_not_ok" in persisted_gate_blockers
        )

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
    malformed_ref = persist_uncertainty_envelope(store, malformed_envelope)
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
        store,
        mixed_outcome.state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF],
    )
    assert mixed_bundle.status.value == "degraded"
    assert "input_uncertainty_not_gate_eligible" in mixed_bundle.warnings
    assert "dependence_assumed_independent" in mixed_bundle.warnings
