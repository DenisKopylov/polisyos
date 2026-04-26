from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import ExecPlanRef, Metrics, MetricsRef, SimulationResult
from polisyos.core.contracts.foundry import (
    EquilibriumMultiplicityDiagnostics,
    EquilibriumMultiplicityReport,
    EquilibriumMultiplicityReportRef,
    EquilibriumSearchProtocol,
    FeedbackResultRef,
    FeedbackSolveResult,
    FeedbackStateSnapshot,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.decision_layer import load_social_weight_manifest
from polisyos.ir.analytics.dependence_structure import (
    build_dependence_structure,
    persist_dependence_structure,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.analytics.welfare import (
    load_channel_decomposition_artifact,
    load_welfare_bundle,
    load_welfare_sample_bundle,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.simulate.propagate_welfare import (
    PropagateWelfareNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_DATA_SNAPSHOT_REF,
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
