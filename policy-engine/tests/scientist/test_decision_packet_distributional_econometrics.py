from __future__ import annotations

import logging

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.causal import ProofBundle, persist_proof_bundle
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    CouplingDiagnostics,
    DimensionBreakdown,
    DistributionalBoundUniformity,
    DistributionalCouplingStatus,
    DistributionalEffectBundle,
    DistributionalJustification,
    DistributionalProofArtifact,
    DistributionalProofTarget,
    DistributionalReport,
    ImpactDirection,
    MetricUnit,
    persist_distributional_effect_bundle,
    persist_distributional_proof_artifact,
    persist_distributional_report,
)
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle, persist_causal_evidence_bundle
from polisyos.ir.analytics.kernel_causal import (
    KernelEstimatorSpec,
    KernelEstimatorTemplate,
    KernelSpec,
    KernelTargetRepresentation,
    persist_kernel_estimator_spec,
)
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    persist_uncertainty_envelope,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.decide.build_decision_packet import BuildDecisionPacketNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF,
    ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF,
    ARTIFACT_DISTRIBUTIONAL_REPORT_REF,
    ARTIFACT_ECONOMETRIC_ENVELOPE_REF,
    ARTIFACT_ECONOMETRIC_EVIDENCE_REF,
    ARTIFACT_ECONOMETRIC_RESULT_REF,
    INPUT_DATA_SNAPSHOT_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)


def test_decision_packet_includes_distributional_and_econometric_sections(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_dist")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.dist"))

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

    distributional_ref = persist_distributional_report(
        store,
        DistributionalReport(
            breakdowns=[
                DimensionBreakdown(
                    dimension=CohortDimension.INCOME_QUINTILE,
                    dimension_label="Income Quintiles",
                    primary_metric="income_change_pct",
                    primary_metric_unit=MetricUnit.PERCENT,
                    cohorts=[
                        CohortImpact(
                            cohort_id="Q1",
                            cohort_label="Q1",
                            population_share=0.5,
                            metric_deltas={"income_change_pct": -2.0},
                            impact_direction=ImpactDirection.NEGATIVE,
                            is_vulnerable=True,
                        ),
                        CohortImpact(
                            cohort_id="Q5",
                            cohort_label="Q5",
                            population_share=0.5,
                            metric_deltas={"income_change_pct": 3.0},
                            impact_direction=ImpactDirection.POSITIVE,
                        ),
                    ],
                )
            ]
        ),
    )
    proof_ref = persist_proof_bundle(
        store,
        ProofBundle(
            proof_status="identified",
            proof_stratum="A0_trusted",
            theorem_family="id_algorithm",
            completeness_regime="complete",
            implementation_coverage="stage5.3",
            proof_trace=["distribution_law"],
        ),
    )
    marginal_proof_ref = persist_distributional_proof_artifact(
        store,
        DistributionalProofArtifact(
            base_proof_ref=proof_ref,
            target=DistributionalProofTarget.CDF,
            theorem_family="identified_distribution_law",
            bound_uniformity=DistributionalBoundUniformity.IDENTIFIED,
        ),
    )
    coupling_proof_ref = persist_distributional_proof_artifact(
        store,
        DistributionalProofArtifact(
            target=DistributionalProofTarget.COUPLING,
            theorem_family="ot_coupling_scenario",
            coupling_status=DistributionalCouplingStatus.SCENARIO_ONLY,
        ),
    )
    baseline_distribution_ref = store.put_json(
        {"distribution": "baseline"},
        PutOptions(kind="ir.discrete_distribution_summary", media_type="application/json"),
    )
    counterfactual_distribution_ref = store.put_json(
        {"distribution": "counterfactual"},
        PutOptions(kind="ir.discrete_distribution_summary", media_type="application/json"),
    )
    coupling_ref = store.put_json(
        {"coupling": "scenario"},
        PutOptions(kind="ir.ot_coupling_summary", media_type="application/json"),
    )
    distributional_bundle_ref = persist_distributional_effect_bundle(
        store,
        DistributionalEffectBundle(
            outcome_name="income",
            distributional_query_kind="interventional_law",
            justification=DistributionalJustification.SCENARIO,
            marginal_law_justification=DistributionalJustification.IDENTIFIED,
            coupling_justification=DistributionalJustification.SCENARIO,
            baseline_distribution_ref=ArtifactRefModel.model_validate(
                baseline_distribution_ref.model_dump()
            ),
            counterfactual_distribution_ref=ArtifactRefModel.model_validate(
                counterfactual_distribution_ref.model_dump()
            ),
            coupling_ref=ArtifactRefModel.model_validate(coupling_ref.model_dump()),
            coupling_diagnostics=CouplingDiagnostics(
                mass_conservation_error=0.0,
                source_marginal_l1_error=0.0,
                target_marginal_l1_error=0.0,
                weighting_mode="uniform",
                identifiability_assumptions=["scenario_level_ot_coupling"],
            ),
            marginal_law_proof_ref=marginal_proof_ref,
            distributional_proof_ref=marginal_proof_ref,
            coupling_proof_ref=coupling_proof_ref,
            causal_assumptions=["positivity", "scenario_level_ot_coupling"],
            readiness_cap="simulation_ready",
            metadata={
                "proof_kernel": {
                    "status": "identified",
                    "theorem_family": "identified_distribution_law",
                }
            },
        ),
    )

    econometric_result_ref = store.put_json(
        {
            "result": {
                "method_name": "iv_2sls",
                "params": {"x_endog": 2},
                "std_errors": {"x_endog": 1},
            }
        },
        PutOptions(kind="scientist.method_result.econometrics.iv", media_type="application/json"),
    )
    econometric_evidence_ref = store.put_json(
        {"method_fqn": "econometrics.iv.two_stage_least_squares@1.0.0"},
        PutOptions(kind="scientist.method_evidence", media_type="application/json"),
    )
    econometric_envelope_ref = persist_uncertainty_envelope(
        store,
        UncertaintyEnvelope(
            point_estimate=1.8,
            confidence_interval=(1.4, 2.2),
            confidence_level=0.95,
            distribution_family=DistributionFamily.NORMAL,
            source=UncertaintySource.CAUSAL,
            propagation_method=PropagationMethod.NONE,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_dist",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_DISTRIBUTIONAL_EFFECT_BUNDLE_REF: distributional_bundle_ref,
            ARTIFACT_DISTRIBUTIONAL_REPORT_REF: distributional_ref,
            ARTIFACT_ECONOMETRIC_RESULT_REF: econometric_result_ref,
            ARTIFACT_ECONOMETRIC_EVIDENCE_REF: econometric_evidence_ref,
            ARTIFACT_ECONOMETRIC_ENVELOPE_REF: econometric_envelope_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["artifacts"]["distributional_report_ref"] == str(distributional_ref.artifact_id)
    assert payload["artifacts"]["distributional_effect_bundle_ref"] == str(
        distributional_bundle_ref.artifact_id
    )
    assert payload["distributional"]["report_ref"] == str(distributional_ref.artifact_id)
    assert payload["distributional"]["effect_bundle_ref"] == str(
        distributional_bundle_ref.artifact_id
    )
    assert payload["distributional"]["marginal_law_justification"] == "identified"
    assert payload["distributional"]["coupling_justification"] == "scenario"
    assert payload["distributional"]["distributional_proof_ref"] == str(
        marginal_proof_ref.artifact_id
    )
    assert payload["distributional"]["coupling_proof_ref"] == str(coupling_proof_ref.artifact_id)
    assert payload["distributional"]["proof_kernel_status"] == "identified"
    assert payload["distributional"]["proof_kernel_theorem_family"] == "identified_distribution_law"
    assert payload["econometrics"]["result_ref"] == str(econometric_result_ref.artifact_id)
    assert payload["econometrics"]["envelope_ref"] == str(econometric_envelope_ref.artifact_id)
    assert payload["uncertainty_bounds"]["econometric_effect_point"] == 1.8


def test_decision_packet_includes_kernel_summary_from_causal_method_evidence(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_packet_kernel")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.packet.kernel"))

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
    proof_ref = persist_proof_bundle(
        store,
        ProofBundle(
            proof_status="identified",
            proof_stratum="A0_trusted",
            theorem_family="id_algorithm",
            completeness_regime="complete",
            implementation_coverage="stage14.1",
            proof_trace=["kernel_lowering_ready"],
        ),
    )
    kernel_spec_ref = persist_kernel_estimator_spec(
        store,
        KernelEstimatorSpec(
            estimand_hash="deadbeefcafefeed",
            proof_bundle_ref=proof_ref,
            template=KernelEstimatorTemplate.DR_CME,
            target_representation=KernelTargetRepresentation.EFFECT_OPERATOR,
            output_kernel=KernelSpec(name="gaussian_rbf", characteristic=True),
            input_kernels={
                "treatment": KernelSpec(name="gaussian_rbf", characteristic=True),
                "outcome": KernelSpec(name="gaussian_rbf", characteristic=True),
            },
            variable_roles={"treatment": ("T",), "outcome": ("Y",)},
            required_side_conditions=("positivity",),
            diagnostics_plan=("kernel_effect_norm", "kernel_characteristic"),
        ),
    )
    evidence_ref = persist_causal_evidence_bundle(
        store,
        EvidenceBundle(
            run_id="R_packet_kernel",
            query_str="E[Y|do(T=1)] - E[Y|do(T=0)]",
            identification_status="identified",
            algorithm_version="kernel_v1",
            proof_bundle_ref=proof_ref,
            kernel_estimator_spec_ref=kernel_spec_ref,
        ),
    )

    state = ExperimentState(
        run_id="R_packet_kernel",
        inputs={
            INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            INPUT_REGISTRY_BUNDLE_REF: registry_bundle,
            INPUT_DATA_SNAPSHOT_REF: data_snapshot_ref,
        },
        artifacts_index={
            ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF: evidence_ref,
        },
    )

    outcome = BuildDecisionPacketNode().execute(ctx, state)
    packet_ref = outcome.artifacts[0]
    payload = from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))

    assert payload["artifacts"]["causal_method_evidence_ref"] == str(evidence_ref.artifact_id)
    assert payload["causal"]["causal_method_evidence_ref"] == str(evidence_ref.artifact_id)
    assert payload["causal"]["proof_bundle_ref"] == str(proof_ref.artifact_id)
    assert payload["causal"]["kernel_estimator_spec_ref"] == str(kernel_spec_ref.artifact_id)
    assert payload["causal"]["kernel_summary"]["template"] == "dr_cme"
    assert payload["causal"]["kernel_summary"]["target_representation"] == "effect_operator"
    assert payload["causal"]["kernel_summary"]["operator_ready"] is True
    assert payload["causal"]["kernel_summary"]["non_promotable"] is False
