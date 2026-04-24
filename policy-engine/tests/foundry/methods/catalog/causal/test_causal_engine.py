"""Unit tests for CausalEngine orchestrator."""

import dataclasses

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.causal.causal_engine import (
    CausalEngine,
    DataReadinessBlockedError,
)
from polisyos.foundry.methods.catalog.causal.estimand_compiler import ExecutorGraph, ExecutorNode
from polisyos.foundry.methods.catalog.causal.id_engine import (
    IdentificationResult,
    IdentificationStatus,
)
from polisyos.foundry.methods.catalog.causal.protocols import (
    DynamicTreatmentData,
    EventProcessObservationalData,
    PanelObservationalData,
)
from polisyos.ir.analytics.causal import (
    build_data_readiness_report,
    load_data_readiness_report,
    load_proof_bundle,
    proof_bundle_from_identification_result,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.dependence_structure import (
    build_dependence_structure,
    persist_dependence_structure,
)
from polisyos.ir.analytics.dp_robustness import (
    DPEffectiveValidity,
    DPGraphProvenance,
    DPGraphProvenanceSource,
    DPHardBlock,
    DPLocalStability,
    DPMechanismFamily,
    DPMechanismSpec,
    DPReleasedStatistics,
    DPReleaseScope,
    DPRobustnessStatus,
    DPSensitivityNorm,
    build_dp_distortion_model,
    build_dp_robustness_certificate,
    load_dp_robustness_certificate,
)
from polisyos.ir.analytics.dual_certificate import (
    load_dual_certificate_bundle,
    validate_dual_certificate_bundle,
)
from polisyos.ir.analytics.dynamic_causal_semantics import (
    DynamicReductionStatus,
    DynamicSemanticsFamily,
)
from polisyos.ir.analytics.dynamic_regime import (
    ContinuousTimeQuery,
    DynamicTreatmentRegime,
    InterventionInterpolationPolicy,
    RegimeRule,
    TemporalIdentificationCertificate,
    TemporalIdentificationTheoremFamily,
    TemporalInterventionSemantics,
    TemporalInterventionTrajectory,
    TemporalLawObject,
    TemporalObservabilityRegime,
    TemporalQueryMode,
    TemporalSamplingScheme,
    TemporalTargetFunctional,
    load_dynamic_treatment_regime,
    load_effect_trajectory_bundle,
    load_temporal_identification_certificate,
    load_temporal_intervention_trajectory,
    persist_temporal_intervention_trajectory,
)
from polisyos.ir.analytics.estimand import DistributionLawQuery, StochasticPolicy
from polisyos.ir.analytics.evidence_bundle import EvidenceBundle, load_causal_evidence_bundle
from polisyos.ir.analytics.interventions import (
    CompositeIntervention,
    EdgeAssignment,
    EdgeIntervention,
    InterferenceIntervention,
    InterferencePolicySpec,
    InterventionQuery,
    ModifiedTreatmentPolicySpec,
    MTPIntervention,
    NodeIntervention,
    PathIntervention,
    QueryTarget,
    QueryTargetKind,
    StochasticIntervention,
    StochasticPolicySpec,
    TransportIntervention,
    VariableAssignment,
    load_intervention_certificate,
    load_intervention_query,
)
from polisyos.ir.analytics.local_independence import (
    LocalIndependenceWeightingCertificateRef,
    load_local_independence_weighting_certificate,
)
from polisyos.ir.analytics.microsim_calibration import (
    build_microsim_calibration_report,
    persist_microsim_calibration_report,
)
from polisyos.ir.analytics.mobility import MobilityReport, persist_mobility_report
from polisyos.ir.analytics.negative_certificate import (
    BlockingType,
    NegativeCertificate,
    load_negative_certificate,
)
from polisyos.ir.analytics.partial_identification import load_bounds_bundle
from polisyos.ir.analytics.proof_composability import (
    load_proof_composability_certificate,
    load_proof_witness_index,
)
from polisyos.ir.analytics.proximal import (
    ProximalIdentificationCertificate,
    ProxyAnnotation,
    SpatialProxySpec,
    load_bridge_plausibility_report,
    load_proximal_identification_certificate,
)
from polisyos.ir.analytics.survey_quality import (
    SurveyRequestedRegime,
    SurveyValidatedRegime,
    build_survey_quality_certificate,
    persist_survey_quality_certificate,
)
from polisyos.ir.artifacts import get_json_artifact
from polisyos.ir.governance.phase1 import load_phase1_flagship_dataset_ids
from polisyos.ir.refs import (
    ArtifactRefModel,
    DynamicTreatmentRegimeRef,
    EffectTrajectoryBundleRef,
    InterventionCertificateRef,
    InterventionQueryRef,
    ProofBundleRef,
    TemporalInterventionTrajectoryRef,
)


def make_dag(directed_edges):
    """Build a CausalGraphModel from a list of (src, dst) directed edges."""
    nodes = list({n for e in directed_edges for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed_edges
    ]
    return CausalGraphModel(graph_type=GraphType.DAG, nodes=nodes, edges=edges)


def make_confounded(directed_edges, bidirected_edges):
    """Build graph with both directed and bidirected (confounding) edges."""
    nodes = list({n for e in directed_edges + bidirected_edges for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed_edges
    ]
    for s, d in bidirected_edges:
        edges.append(CausalEdge(src=s, dst=d, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))
    # PAG allows mixed edge marks including bidirected arrows
    return CausalGraphModel(graph_type=GraphType.PAG, nodes=nodes, edges=edges)


def make_admg_confounded(directed_edges, bidirected_edges):
    """Build an ADMG with directed and bidirected confounding edges."""
    nodes = list({n for e in directed_edges + bidirected_edges for n in e})
    edges = [
        CausalEdge(src=s, dst=d, mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW)
        for s, d in directed_edges
    ]
    for s, d in bidirected_edges:
        edges.append(CausalEdge(src=s, dst=d, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))
    return CausalGraphModel(graph_type=GraphType.ADMG, nodes=nodes, edges=edges)


def _artifact_id(ch: str) -> str:
    return f"sha256:{ch * 64}"


def _artifact_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(ch),
        kind=kind,
        media_type="application/json",
    )


def _tabular_direct_wrapper_data(
    *,
    treatment_key: str,
    outcome_key: str,
) -> dict[str, np.ndarray]:
    treatment = np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype=int)
    covariates = np.array(
        [
            [-1.0, 0.2],
            [-0.6, 0.0],
            [-0.2, 0.1],
            [0.1, -0.1],
            [0.4, 0.3],
            [0.7, -0.2],
            [1.0, 0.4],
            [1.3, -0.3],
        ],
        dtype=float,
    )
    outcome = 0.5 + 1.2 * treatment + 0.4 * covariates[:, 0]
    return {
        treatment_key: treatment,
        outcome_key: outcome,
        "covariates": covariates,
    }


def _laplace_dp_certificate(
    *,
    epsilon: float,
    sample_size: int,
    cell_count: int,
    min_denominator_margin: float,
    lipschitz_upper_bound: float,
    policy_tolerance: float,
) -> object:
    mechanism = DPMechanismSpec(
        family=DPMechanismFamily.LAPLACE,
        epsilon=epsilon,
        sensitivity_norm=DPSensitivityNorm.L1,
        sensitivity_value=1.0,
    )
    release_scope = DPReleaseScope(
        released_statistics=DPReleasedStatistics.FULL_HISTOGRAM,
        cell_count_k=cell_count,
        sample_size_n=sample_size,
    )
    return build_dp_robustness_certificate(
        proof_status="identified",
        mechanism=mechanism,
        release_scope=release_scope,
        graph_provenance=DPGraphProvenance(
            source=DPGraphProvenanceSource.TRUSTED_EXTERNAL,
        ),
        distortion_model=build_dp_distortion_model(
            mechanism,
            release_scope,
            alpha=0.01,
        ),
        local_stability=DPLocalStability(
            min_denominator_margin=min_denominator_margin,
            lipschitz_upper_bound=lipschitz_upper_bound,
            policy_tolerance=policy_tolerance,
        ),
    )


def _identified_result(
    *,
    treatment: str = "X",
    outcome: str = "Y",
) -> IdentificationResult:
    return IdentificationResult(
        status=IdentificationStatus.IDENTIFIED,
        estimand_ast=None,
        hedge_certificate=None,
        trace=[],
        required_distributions=[],
        query_str=f"P({outcome}|do({treatment}))",
    )


def _seed_phase1_gate_store(
    store: FileSystemCAS,
    *,
    certified_dataset_ids: tuple[str, ...] | None = None,
) -> dict[str, object]:
    dataset_ids = tuple(certified_dataset_ids or load_phase1_flagship_dataset_ids())
    certificate_refs: dict[str, object] = {}
    for dataset_id in dataset_ids:
        certificate = build_survey_quality_certificate(
            target_estimand="E[Y]",
            estimator_id="survey.dr.design_missingness@1.0.0",
            dataset_id=dataset_id,
            data_origin="government",
            regime_requested=SurveyRequestedRegime.POPULATION_MAR,
            regime_validated=SurveyValidatedRegime.BOTH_VALID,
            estimate=1.0,
            standard_error=0.1,
            overall_pass=True,
        )
        certificate_refs[dataset_id] = persist_survey_quality_certificate(store, certificate)

    for regime, covariance in (
        ("panel", "driscoll_kraay"),
        ("areal", "conley_spatial_hac"),
        ("network_adjacent", "network_hac"),
    ):
        persist_dependence_structure(
            store,
            build_dependence_structure(
                regime=regime,
                class_label="shared",
                calibrated=True,
                recommended_covariance=covariance,
                source_method=f"tests.phase1.{regime}",
            ),
        )

    persist_microsim_calibration_report(
        store,
        build_microsim_calibration_report(
            compatibility_status="compatible",
            exact_feasible=True,
        ),
    )
    persist_mobility_report(
        store,
        MobilityReport(
            analysis_type="transition_matrix",
            status="ok",
            summary_metrics={"n_obs": 10},
        ),
    )
    return {
        "dataset_ids": dataset_ids,
        "certificate_refs": certificate_refs,
    }


def _government_dynamic_data(
    dataset_id: str,
    *,
    survey_quality_certificate_ref: object | None = None,
    survey_quality_certificate: object | None = None,
) -> DynamicTreatmentData:
    metadata: dict[str, object] = {
        "dataset_id": dataset_id,
        "data_origin": "government",
    }
    if survey_quality_certificate_ref is not None:
        metadata["survey_quality_certificate_ref"] = survey_quality_certificate_ref
    if survey_quality_certificate is not None:
        metadata["survey_quality_certificate"] = survey_quality_certificate
    return TestCausalEngineTemporal._dynamic_data().model_copy(update={"metadata": metadata})


class TestCausalEngineIdentify:
    def setup_method(self):
        self.engine = CausalEngine(registry=None, knowledge_base=None)

    def test_backdoor_graph_returns_identified(self):
        # Z -> X -> Y, Z -> Y (classical backdoor: Z is confounder)
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        result = self.engine.identify("X", "Y", graph)
        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED

    def test_non_identifiable_returns_negative_cert(self):
        # Bow-arc: X -> Y with bidirected X <-> Y (non-identifiable)
        graph = make_confounded([("X", "Y")], [("X", "Y")])
        result = self.engine.identify("X", "Y", graph)
        # May return HEDGE_FOUND as IdentificationResult or NegativeCertificate
        if isinstance(result, IdentificationResult):
            assert result.status in {
                IdentificationStatus.HEDGE_FOUND,
                IdentificationStatus.ORACLE_NEEDED,
                IdentificationStatus.PAG_AMBIGUOUS,  # Track B: PAG graphs may return this
            }
        else:
            assert isinstance(result, NegativeCertificate)
            assert result.blocking_type == BlockingType.HEDGE_STRUCTURE

    def test_identify_uses_proximal_fallback_after_hedge(self):
        graph = make_admg_confounded(
            [("X", "A"), ("X", "Y"), ("Z", "A"), ("A", "Y")],
            [("A", "Y"), ("A", "Z"), ("Y", "W")],
        )

        result = self.engine.identify(
            "A",
            "Y",
            graph,
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
            ),
        )

        assert isinstance(result, ProximalIdentificationCertificate)
        assert result.metadata["upstream_identification_status"] == "hedge_found"
        assert result.proxies.treatment_inducing == ("Z",)
        assert result.identified_functionals[0].expression == "E[h(W, 1, X) - h(W, 0, X)]"

    def test_identify_soft_policy_uses_proximal_lifting_after_hedge(self):
        graph = make_admg_confounded(
            [("X", "A"), ("X", "Y"), ("Z", "A"), ("A", "Y")],
            [("A", "Y"), ("A", "Z"), ("Y", "W")],
        )

        result = self.engine.identify(
            "A",
            "Y",
            graph,
            policy=StochasticPolicy(
                policy_type="soft",
                conditioning_vars=("X",),
                policy_expr="pi(A|X)",
            ),
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
            ),
        )

        assert isinstance(result, ProximalIdentificationCertificate)
        assert result.metadata["policy_lifting"] == "stochastic_policy_mixture"
        assert result.metadata["policy_type"] == "soft"
        assert result.metadata["policy_expr"] == "pi(A|X)"

    def test_identify_with_z_interventions(self):
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        result = self.engine.identify("X", "Y", graph, z_interventions=frozenset({"Z"}))
        assert isinstance(result, (IdentificationResult, NegativeCertificate))

    def test_identify_with_conditions(self):
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        result = self.engine.identify("X", "Y", graph, conditions=frozenset({"Z"}))
        assert isinstance(result, (IdentificationResult, NegativeCertificate))

    def test_identify_returns_valid_status(self):
        graph = make_dag([("X", "Y")])
        result = self.engine.identify("X", "Y", graph)
        if isinstance(result, IdentificationResult):
            assert result.status in list(IdentificationStatus)

    def test_identify_frozenset_treatment(self):
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])
        result = self.engine.identify(frozenset({"X"}), frozenset({"Y"}), graph)
        assert isinstance(result, (IdentificationResult, NegativeCertificate))

    def test_identify_distribution_law_returns_distribution_ast(self):
        graph = make_dag([("tax_policy", "income")])
        query = DistributionLawQuery(
            outcome_variables=("income",),
            intervention_set=("tax_policy",),
            support_space="real",
            representation="cdf",
        )

        result = self.engine.identify(
            "tax_policy",
            "income",
            graph,
            distribution_query=query,
        )

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "dist_id_v1"
        assert result.estimand_ast is not None
        assert result.estimand_ast.root.node_type == "distribution_law"
        assert result.metadata["query_kind"] == "distribution_law"
        assert result.metadata["distributional_query_kind"] == "interventional_law"
        assert result.metadata["generator_type"] == "halfline_cdf"
        proof = proof_bundle_from_identification_result(result)
        assert proof.metadata["query_kind"] == "distribution_law"
        assert proof.metadata["distributional_query_kind"] == "interventional_law"

    def test_identify_conditional_distribution_law_uses_idc_wrapper(self):
        graph = make_dag([("region", "tax_policy"), ("tax_policy", "income"), ("region", "income")])
        query = DistributionLawQuery(
            outcome_variables=("income",),
            intervention_set=("tax_policy",),
            conditioning=("region",),
            support_space="real",
            representation="cdf",
        )

        result = self.engine.identify(
            "tax_policy",
            "income",
            graph,
            distribution_query=query,
        )

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "dist_idc_v1"
        assert result.metadata["conditioning_variables"] == ["region"]

    def test_identify_distribution_law_nonidentifiable_returns_negative_certificate(self):
        graph = CausalGraphModel(
            graph_type=GraphType.ADMG,
            nodes=["tax_policy", "income"],
            edges=[
                CausalEdge(
                    src="tax_policy",
                    dst="income",
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                ),
                CausalEdge(
                    src="tax_policy",
                    dst="income",
                    mark_src=EdgeMark.ARROW,
                    mark_dst=EdgeMark.ARROW,
                ),
            ],
        )
        query = DistributionLawQuery(
            outcome_variables=("income",),
            intervention_set=("tax_policy",),
            support_space="real",
            representation="cdf",
        )

        result = self.engine.identify(
            "tax_policy",
            "income",
            graph,
            distribution_query=query,
        )

        assert isinstance(result, NegativeCertificate)
        assert result.blocking_type == BlockingType.HEDGE_STRUCTURE
        assert result.quantitative_diagnostics["query_kind"] == "distribution_law"
        assert result.quantitative_diagnostics["generator_type"] == "halfline_cdf"

    def test_identify_cyclic_graph_reduces_to_acyclic_backend_when_cycle_is_irrelevant(self):
        graph = CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["X", "Y", "A", "B"],
            edges=[
                CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="B", dst="A", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            ],
        )

        result = self.engine.identify("X", "Y", graph)

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "dynamic_acyclic_reduction_v1"
        assert result.metadata["dynamic_semantics"]["reduction_status"] == "validated_reduction"
        proof = proof_bundle_from_identification_result(result)
        assert proof.proof_stratum == "A1_dynamic"
        assert proof.completeness_regime == "sound_incomplete"
        assert proof.dynamic_semantics is not None
        assert (
            proof.dynamic_semantics.reduction_status is DynamicReductionStatus.VALIDATED_REDUCTION
        )

    def test_identify_cyclic_distribution_query_requires_validated_reduction(self):
        graph = CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["tax_policy", "income", "A", "B"],
            edges=[
                CausalEdge(
                    src="tax_policy",
                    dst="income",
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                ),
                CausalEdge(src="A", dst="B", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="B", dst="A", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            ],
        )
        query = DistributionLawQuery(
            outcome_variables=("income",),
            intervention_set=("tax_policy",),
            support_space="real",
            representation="cdf",
        )

        result = self.engine.identify(
            "tax_policy",
            "income",
            graph,
            distribution_query=query,
        )

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "dynamic_acyclic_reduction_v1"
        assert result.metadata["query_kind"] == "distribution_law"
        assert result.metadata["dynamic_semantics"]["reduction_status"] == "validated_reduction"

    def test_identify_cyclic_conditional_query_blocks_without_validated_reduction(self):
        graph = CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["X", "Y", "Z"],
            edges=[
                CausalEdge(src="X", dst="Y", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="Y", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="Z", dst="X", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            ],
            metadata={
                "well_posedness_spec": {
                    "A": [
                        [0.0, 0.2, 0.0],
                        [0.1, 0.0, 0.0],
                        [0.0, 0.0, 0.0],
                    ]
                }
            },
        )

        result = self.engine.identify("X", "Y", graph, conditions=frozenset({"Z"}))

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.ORACLE_NEEDED
        assert result.algorithm_version == "dynamic_semantics_oracle_v1"
        dynamic_semantics = result.metadata["dynamic_semantics"]
        assert dynamic_semantics["reduction_status"] == "blocked"
        assert dynamic_semantics["well_posedness_witness"]["status"] == "proved"

    def test_identify_attaches_intervention_metadata_for_legacy_queries(self):
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

        result = self.engine.identify("X", "Y", graph, conditions=frozenset({"Z"}))

        assert isinstance(result, IdentificationResult)
        assert result.metadata["query_kind"] == "intervention"
        assert result.metadata["intervention_type"] == "node"
        proof = proof_bundle_from_identification_result(result)
        assert proof.metadata["intervention_certificate"]["query"]["target"]["conditioning"] == [
            "Z"
        ]

    def test_identify_shift_policy_uses_mtp_node_and_certificate(self):
        graph = make_dag([("W", "A"), ("A", "Y"), ("W", "Y")])

        result = self.engine.identify(
            "A",
            "Y",
            graph,
            policy=StochasticPolicy(
                policy_type="shift",
                conditioning_vars=("W",),
                shift_delta=1.0,
                policy_expr="A+1",
            ),
        )

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.estimand_ast is not None
        assert result.estimand_ast.root.node_type == "modified_treatment_policy"
        assert result.metadata["intervention_type"] == "mtp"

    def test_identify_multi_target_mtp_is_documented_v1_oracle_needed(self):
        graph = make_dag([("W", "A"), ("W", "B"), ("A", "Y"), ("B", "Y"), ("W", "Y")])
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.EXPECTATION,
                outcome_variables=("Y",),
            ),
            intervention=MTPIntervention(
                policies=(
                    ModifiedTreatmentPolicySpec(
                        target="A",
                        policy_expr="A+1",
                        natural_treatment="A",
                        covariates=("W",),
                    ),
                    ModifiedTreatmentPolicySpec(
                        target="B",
                        policy_expr="B+1",
                        natural_treatment="B",
                        covariates=("W",),
                    ),
                )
            ),
        )

        result = self.engine.identify("A", "Y", graph, intervention_query=query)

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.ORACLE_NEEDED
        assert result.algorithm_version == "mtp_g_formula_v1"
        assert result.metadata["intervention_type"] == "mtp"
        assert "multi-target modified treatment policies are not yet executable" in result.trace

    def test_identify_accepts_explicit_edge_intervention_query(self):
        graph = make_dag([("X", "Y")])
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DISTRIBUTION,
                outcome_variables=("Y",),
            ),
            intervention=EdgeIntervention(
                assignments=(EdgeAssignment(source="X", target="Y", value=1),)
            ),
        )

        result = self.engine.identify("X", "Y", graph, intervention_query=query)

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.estimand_ast is not None
        assert result.estimand_ast.root.node_type == "edge_intervention"
        proof = proof_bundle_from_identification_result(result)
        assert proof.metadata["intervention_type"] == "edge"

    def test_identify_path_query_returns_negative_certificate_for_recanting_witness(self):
        graph = make_dag([("X", "M"), ("M", "Y"), ("X", "Y")])
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DISTRIBUTION,
                outcome_variables=("Y",),
            ),
            intervention=PathIntervention(
                active_paths=(("X", "M", "Y"),),
                frozen_paths=(("X", "Y"),),
                natural_value_vars=("M",),
            ),
        )

        result = self.engine.identify("X", "Y", graph, intervention_query=query)

        assert isinstance(result, NegativeCertificate)
        assert result.blocking_type == BlockingType.SEMANTICS_NOT_WELL_DEFINED
        assert result.quantitative_diagnostics["witness_variables"] == ["M"]

    def test_identify_sigma_stochastic_query_uses_sigma_backend(self):
        graph = make_dag([("X", "Y")])
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.EXPECTATION,
                outcome_variables=("Y",),
            ),
            intervention=StochasticIntervention(
                policies=(
                    StochasticPolicySpec(
                        target="X",
                        distribution_expr="pi(X)",
                    ),
                ),
                semantics="sigma_calculus",
            ),
        )

        result = self.engine.identify("X", "Y", graph, intervention_query=query)

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "sigma_calculus_v1"
        assert result.estimand_ast is not None
        assert result.estimand_ast.root.node_type == "stochastic_intervention"
        proof = proof_bundle_from_identification_result(result)
        assert proof.metadata["intervention_type"] == "stochastic"
        assert proof.metadata["intervention_identification_status"] == "identified"

    def test_identify_sigma_transport_query_uses_sigma_transport_backend(self):
        graph = make_dag([("X", "Y")])
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.EXPECTATION,
                outcome_variables=("Y",),
            ),
            intervention=TransportIntervention(
                source_domain="source",
                target_domain="target",
                selection_nodes=("X",),
                soft_transport=True,
                base_intervention=StochasticIntervention(
                    policies=(
                        StochasticPolicySpec(
                            target="X",
                            distribution_expr="pi(X)",
                        ),
                    ),
                    semantics="sigma_calculus",
                ),
            ),
        )

        result = self.engine.identify("X", "Y", graph, intervention_query=query)

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "sigma_transport_v1"
        assert result.estimand_ast is not None
        assert result.estimand_ast.root.node_type == "stochastic_intervention"
        proof = proof_bundle_from_identification_result(result)
        assert proof.metadata["intervention_type"] == "transport"

    def test_identify_non_uniform_edge_query_uses_edge_g_formula_backend(self):
        graph = make_dag([("X", "M"), ("X", "Y"), ("M", "Y")])
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DISTRIBUTION,
                outcome_variables=("Y",),
            ),
            intervention=EdgeIntervention(
                assignments=(
                    EdgeAssignment(source="X", target="M", value=0),
                    EdgeAssignment(source="X", target="Y", value=1),
                ),
                semantics="edge_g_formula",
            ),
        )

        result = self.engine.identify("X", "Y", graph, intervention_query=query)

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "edge_g_formula_v1"
        assert result.estimand_ast is not None
        assert result.estimand_ast.root.node_type == "edge_intervention"

    def test_identify_path_query_uses_path_id_backend_when_recanting_witness_absent(self):
        graph = make_dag([("X", "M"), ("M", "Y")])
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DECOMPOSITION,
                outcome_variables=("Y",),
            ),
            intervention=PathIntervention(
                active_paths=(("X", "M", "Y"),),
                natural_value_vars=("M",),
            ),
        )

        result = self.engine.identify("X", "Y", graph, intervention_query=query)

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "path_intervention_v1"
        assert result.estimand_ast is not None
        assert result.estimand_ast.root.node_type == "path_specific"

    def test_identify_path_query_uses_proximal_mediation_template_under_hidden_confounding(self):
        graph = make_admg_confounded(
            [
                ("X", "A"),
                ("X", "M"),
                ("X", "Y"),
                ("Z", "A"),
                ("A", "M"),
                ("M", "Y"),
                ("A", "Y"),
            ],
            [("A", "Y"), ("A", "Z"), ("Y", "W")],
        )
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DECOMPOSITION,
                outcome_variables=("Y",),
            ),
            intervention=PathIntervention(
                active_paths=(("A", "M", "Y"),),
                frozen_paths=(("A", "Y"),),
                natural_value_vars=("M",),
            ),
        )

        result = self.engine.identify(
            "A",
            "Y",
            graph,
            intervention_query=query,
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
            ),
        )

        assert isinstance(result, IdentificationResult)
        assert result.status is IdentificationStatus.ORACLE_NEEDED
        assert result.algorithm_version == "proximal_mediation_thm1_dukes_2023"
        assert result.estimand_ast is not None
        assert result.estimand_ast.root.node_type == "path_specific"
        assert "proximal_mediation" in result.estimand_ast.identification_method
        cert_payload = result.metadata["proximal_mediation_certificate"]
        assert cert_payload["query"]["mediator"] == "M"
        assert cert_payload["query"]["target_effect"] == "nie"
        proof = proof_bundle_from_identification_result(result)
        assert proof.proof_status == "oracle_needed"
        assert proof.theorem_family == "proximal_mediation_thm1_dukes_2023"

    def test_identify_path_query_promotes_to_identified_when_oracle_assumptions_are_accepted(self):
        graph = make_admg_confounded(
            [
                ("X", "A"),
                ("X", "M"),
                ("X", "Y"),
                ("Z", "A"),
                ("A", "M"),
                ("M", "Y"),
                ("A", "Y"),
            ],
            [("A", "Y"), ("A", "Z"), ("Y", "W")],
        )
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DECOMPOSITION,
                outcome_variables=("Y",),
            ),
            intervention=PathIntervention(
                active_paths=(("A", "M", "Y"),),
                frozen_paths=(("A", "Y"),),
                natural_value_vars=("M",),
            ),
        )

        result = self.engine.identify(
            "A",
            "Y",
            graph,
            intervention_query=query,
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
                accept_oracle_assumptions=True,
            ),
        )

        assert isinstance(result, IdentificationResult)
        assert result.status is IdentificationStatus.IDENTIFIED
        assert result.metadata["oracle_assumptions_accepted"] is True
        proof = proof_bundle_from_identification_result(result)
        assert proof.proof_status == "identified"

    def test_identify_path_query_rejects_forbidden_z_to_m_edge_in_proximal_template(self):
        graph = make_admg_confounded(
            [
                ("X", "A"),
                ("X", "M"),
                ("X", "Y"),
                ("Z", "A"),
                ("Z", "M"),
                ("A", "M"),
                ("M", "Y"),
                ("A", "Y"),
            ],
            [("A", "Y"), ("A", "Z"), ("Y", "W")],
        )
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DECOMPOSITION,
                outcome_variables=("Y",),
            ),
            intervention=PathIntervention(
                active_paths=(("A", "M", "Y"),),
                frozen_paths=(("A", "Y"),),
                natural_value_vars=("M",),
            ),
        )

        result = self.engine.identify(
            "A",
            "Y",
            graph,
            intervention_query=query,
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
            ),
        )

        assert isinstance(result, NegativeCertificate)
        assert result.blocking_type is BlockingType.PROXIMAL_CONDITION_FAILED
        assert result.quantitative_diagnostics["failed_check"] == "no_direct_edge_Z_to_M"

    def test_identify_clustered_interference_query_returns_constructive_negative_certificate(self):
        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["A_0", "Y_0", "A_1", "Y_1"],
            edges=[
                CausalEdge(src="A_0", dst="Y_0", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="A_1", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="A_0", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            ],
            metadata={
                "cluster_map": {
                    "A_0": "0",
                    "Y_0": "0",
                    "A_1": "1",
                    "Y_1": "1",
                }
            },
        )
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DISTRIBUTION,
                outcome_variables=("Y",),
            ),
            intervention=InterferenceIntervention(
                policies=(
                    InterferencePolicySpec(
                        target="A",
                        policy_expr="cluster_policy(A, E)",
                        exposure_vars=("E",),
                    ),
                ),
                exposure_map_ref="fractional",
                interference_mode="cluster",
                fallback_mode="clustered",
            ),
        )

        result = self.engine.identify("A", "Y", graph, intervention_query=query)

        assert isinstance(result, NegativeCertificate)
        assert result.blocking_type == BlockingType.SEMANTICS_NOT_WELL_DEFINED
        assert (
            result.quantitative_diagnostics["algorithm_version"] == "interference_intervention_v1"
        )
        assert (
            result.quantitative_diagnostics["interference_certificate"]["fallback_mode"]
            == "clustered"
        )
        assert "Exposure augmentation" in " ".join(result.quantitative_diagnostics["proof_trace"])

    def test_identify_interference_query_identifies_when_no_cross_unit_edges_exist(self):
        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["A_0", "Y_0", "A_1", "Y_1"],
            edges=[
                CausalEdge(src="A_0", dst="Y_0", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="A_1", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            ],
            metadata={
                "cluster_map": {
                    "A_0": "0",
                    "Y_0": "0",
                    "A_1": "1",
                    "Y_1": "1",
                }
            },
        )
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DISTRIBUTION,
                outcome_variables=("Y",),
            ),
            intervention=InterferenceIntervention(
                policies=(
                    InterferencePolicySpec(
                        target="A",
                        policy_expr="cluster_policy(A, E)",
                        exposure_vars=("E",),
                    ),
                ),
                exposure_map_ref="fractional",
                interference_mode="cluster",
                fallback_mode="clustered",
            ),
        )

        result = self.engine.identify("A", "Y", graph, intervention_query=query)

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.algorithm_version == "interference_intervention_v1"
        assert result.metadata["interference_certificate"]["fallback_mode"] == "clustered"
        proof = proof_bundle_from_identification_result(result)
        assert proof.metadata["intervention_type"] == "interference"

    def test_identify_interference_query_surfaces_simplicial_star_local_certificate(self):
        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["A_0", "Y_0", "A_1", "Y_1", "A_2", "Y_2"],
            edges=[
                CausalEdge(src="A_0", dst="Y_0", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="A_1", dst="Y_1", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
                CausalEdge(src="A_2", dst="Y_2", mark_src=EdgeMark.TAIL, mark_dst=EdgeMark.ARROW),
            ],
            metadata={
                "topology": {
                    "reduction_policy": "full_complex",
                    "candidate_topology": "audited_or_fdr_controlled",
                    "simplices": [
                        ["A_0", "A_1", "A_2"],
                        ["Y_0", "Y_1", "Y_2"],
                    ],
                    "exposure_operator": {
                        "locality_scope": "closed_star",
                        "exposure_states": [
                            "direct_only",
                            "pairwise_exposed",
                            "simplex_exposed",
                        ],
                        "exposure_consistency": True,
                        "assignment_design": "bernoulli",
                        "design_positivity": True,
                        "bounded_star_overlap": True,
                        "inference_regime": "conditional_randomization",
                        "selection_stage": "pre_outcome",
                    },
                }
            },
        )
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DISTRIBUTION,
                outcome_variables=("Y",),
            ),
            intervention=InterferenceIntervention(
                policies=(
                    InterferencePolicySpec(
                        target="A",
                        policy_expr="simplicial_policy(A, E)",
                        exposure_vars=("E",),
                    ),
                ),
                exposure_map_ref="count",
                interference_mode="full_complex",
                fallback_mode="unsupported",
            ),
        )

        result = self.engine.identify("A", "Y", graph, intervention_query=query)

        assert isinstance(result, IdentificationResult)
        assert result.status == IdentificationStatus.IDENTIFIED
        assert result.metadata["interference_certificate"]["supported_query_family"] == (
            "cluster_projection_queries"
        )
        assert result.metadata["interference_certificate"]["fallback_mode"] == "clustered"
        assert result.metadata["interference_certificate"]["mode_requested"] == "complex"
        assert result.metadata["interference_certificate"]["mode_used"] == "clustered"
        assert result.metadata["interference_certificate"]["fallback_triggered"] is True
        assert result.metadata["interference_mode_requested"] == "complex"
        assert result.metadata["interference_mode_used"] == "clustered"
        assert result.metadata["interference_fallback_triggered"] is True
        assert result.metadata["interference_estimand_label"] == "clustered_exposure_effect"
        assert (
            "known_simplicial_complex"
            in result.metadata["interference_certificate"]["exposure_assumptions"]
        )

    def test_identify_rejects_ill_typed_intervention_query(self):
        graph = make_dag([("A", "Y"), ("W", "A"), ("W", "Y")])
        query = InterventionQuery(
            target=QueryTarget(outcome_variables=("Y",)),
            intervention=CompositeIntervention(
                steps=(
                    NodeIntervention(assignments=(VariableAssignment(variable="A", value=1),)),
                    MTPIntervention(
                        policies=(
                            ModifiedTreatmentPolicySpec(
                                target="A",
                                policy_expr="A+1",
                                natural_treatment="A",
                                covariates=("W",),
                            ),
                        )
                    ),
                )
            ),
        )

        result = self.engine.identify("A", "Y", graph, intervention_query=query)

        assert isinstance(result, NegativeCertificate)
        assert result.blocking_type == BlockingType.INTERVENTION_TYPECHECK


class TestCausalEngineCompile:
    def setup_method(self):
        self.engine = CausalEngine(registry=None, knowledge_base=None)
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

    def _get_identified_result(self):
        result = self.engine.identify("X", "Y", self.graph)
        if not isinstance(result, IdentificationResult):
            pytest.skip("Identification failed, cannot test compilation")
        if result.status != IdentificationStatus.IDENTIFIED:
            pytest.skip(f"Not identified (status={result.status}), cannot test compilation")
        return result

    def test_compile_returns_executor_graph(self):
        from polisyos.foundry.methods.catalog.causal.estimand_compiler import ExecutorGraph

        result = self._get_identified_result()
        eg = self.engine.compile(result, n_obs=500, covariate_dim=3)
        assert isinstance(eg, ExecutorGraph)

    def test_compile_nodes_nonempty(self):
        result = self._get_identified_result()
        eg = self.engine.compile(result, n_obs=500)
        assert len(eg.nodes) > 0

    def test_compile_raises_on_non_identified(self):
        result = make_confounded([("X", "Y")], [("X", "Y")])
        non_id_result = self.engine.identify("X", "Y", result)
        if (
            isinstance(non_id_result, IdentificationResult)
            and non_id_result.estimand_ast is not None
        ):
            pytest.skip("Unexpectedly identified")
        if isinstance(non_id_result, NegativeCertificate):
            pytest.skip("Returns NegativeCertificate — cannot test ValueError from compile")
        with pytest.raises((ValueError, Exception)):
            self.engine.compile(non_id_result)


class TestCausalEngineAudit:
    def setup_method(self):
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

    def _get_result(self, engine: CausalEngine):
        return engine.identify("X", "Y", self.graph)

    def test_audit_returns_evidence_bundle(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import (
                _make_dummy_identification_result,
            )

            result = _make_dummy_identification_result("X", "Y")
        bundle = engine.audit(result, None, run_id="test-run-1")
        assert isinstance(bundle, EvidenceBundle)

    def test_audit_run_id_preserved(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import (
                _make_dummy_identification_result,
            )

            result = _make_dummy_identification_result("X", "Y")
        bundle = engine.audit(result, None, run_id="my-unique-run")
        assert bundle.run_id == "my-unique-run"

    def test_audit_created_at_is_iso_string(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import (
                _make_dummy_identification_result,
            )

            result = _make_dummy_identification_result("X", "Y")
        bundle = engine.audit(result, None, run_id="r1")
        assert isinstance(bundle.created_at, str)
        assert "T" in bundle.created_at  # ISO format contains 'T'

    def test_audit_identification_status_in_bundle(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import (
                _make_dummy_identification_result,
            )

            result = _make_dummy_identification_result("X", "Y")
        bundle = engine.audit(result, None, run_id="r2")
        assert isinstance(bundle.identification_status, str)
        assert len(bundle.identification_status) > 0
        assert bundle.proof_bundle_ref is not None
        assert load_proof_bundle(store, bundle.proof_bundle_ref).proof_status == "identified"

    def test_audit_schema_report_in_diagnostics(self, tmp_path):
        from polisyos.foundry.methods.catalog.causal.schema_resolver import SchemaResolutionReport

        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = self._get_result(engine)
        if isinstance(result, NegativeCertificate):
            from polisyos.foundry.methods.catalog.causal.causal_engine import (
                _make_dummy_identification_result,
            )

            result = _make_dummy_identification_result("X", "Y")
        schema = SchemaResolutionReport(support_warnings=["overlap concern"], is_feasible=True)
        bundle = engine.audit(result, None, run_id="r3", schema_report=schema)
        assert "schema_warnings_count" in bundle.diagnostic_scores

    def test_audit_persists_dp_robustness_certificate_on_proof_bundle(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        result = _identified_result()

        certificate = _laplace_dp_certificate(
            epsilon=8.0,
            sample_size=100_000,
            cell_count=8,
            min_denominator_margin=0.1,
            lipschitz_upper_bound=2.0,
            policy_tolerance=0.01,
        )
        result = dataclasses.replace(
            result,
            metadata={
                **dict(result.metadata),
                "dp_robustness_certificate": certificate.model_dump(mode="json"),
            },
        )

        bundle = engine.audit(result, None, run_id="dp-audit")

        assert bundle.proof_bundle_ref is not None
        proof = load_proof_bundle(store, bundle.proof_bundle_ref)
        assert proof.dp_robustness_ref is not None
        assert proof.metadata["dp_effective_status"] == "identified"
        loaded_cert = load_dp_robustness_certificate(store, proof.dp_robustness_ref)
        assert loaded_cert == certificate

    def test_audit_persists_intervention_query_and_certificate_refs(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        graph = make_dag([("X", "Y")])
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DISTRIBUTION,
                outcome_variables=("Y",),
            ),
            intervention=EdgeIntervention(
                assignments=(EdgeAssignment(source="X", target="Y", value=1),)
            ),
        )

        result = engine.identify("X", "Y", graph, intervention_query=query)
        assert isinstance(result, IdentificationResult)

        bundle = engine.audit(result, None, run_id="typed-audit", graph=graph)

        assert bundle.proof_bundle_ref is not None
        proof = load_proof_bundle(store, bundle.proof_bundle_ref)
        query_ref = InterventionQueryRef.model_validate(proof.metadata["intervention_query_ref"])
        certificate_ref = InterventionCertificateRef.model_validate(
            proof.metadata["intervention_certificate_ref"]
        )
        assert load_intervention_query(store, query_ref) == query
        loaded_certificate = load_intervention_certificate(store, certificate_ref)
        assert loaded_certificate.query == query
        assert proof.query_ref == str(query_ref.artifact_id)

    def test_audit_persists_stage_2_2_proof_trace_and_witness_index(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

        result = engine.identify("X", "Y", graph)
        assert isinstance(result, IdentificationResult)

        bundle = engine.audit(result, None, run_id="stage-2-2-audit", graph=graph)

        assert bundle.proof_bundle_ref is not None
        proof = load_proof_bundle(store, bundle.proof_bundle_ref)
        assert proof.proof_trace_ref is not None
        assert proof.witness_index_ref is not None
        assert proof.composability_certificate_ref is not None
        assert proof.proof_support_projection_hash is not None
        assert proof.composability_status == "reusable"
        assert proof.metadata["composability_status"] == "reusable"

        trace_bundle = load_causal_evidence_bundle(store, proof.proof_trace_ref)
        witness_index = load_proof_witness_index(store, proof.witness_index_ref)
        certificate = load_proof_composability_certificate(
            store,
            proof.composability_certificate_ref,
        )
        trace_step_ids = {step.step_id for step in trace_bundle.proof_steps}

        assert trace_bundle.query_str
        assert trace_bundle.proof_steps
        assert witness_index.witnesses
        assert certificate.status.value == "reusable"
        assert certificate.proof_trace_ref == proof.proof_trace_ref
        assert certificate.witness_index_ref == proof.witness_index_ref
        assert set(witness_index.step_to_witness_ids).issubset(trace_step_ids)


class TestCausalEngineRun:
    def setup_method(self):
        self.graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

    def test_run_returns_triple(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        result = engine.run("X", "Y", self.graph)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_run_bundle_is_evidence_bundle(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        _, bundle, _ = engine.run("X", "Y", self.graph)
        assert isinstance(bundle, EvidenceBundle)
        assert bundle.proof_bundle_ref is not None
        assert bundle.data_readiness_report_ref is not None
        assert load_proof_bundle(store, bundle.proof_bundle_ref).proof_status == "identified"
        assert load_data_readiness_report(store, bundle.data_readiness_report_ref).decision in {
            "pass",
            "warn",
            "unknown",
        }

    def test_run_no_negative_cert_for_identifiable(self, tmp_path):
        engine = CausalEngine(registry=None, artifact_store=FileSystemCAS(tmp_path / "cas"))
        _, bundle, cert = engine.run("X", "Y", self.graph)
        # Backdoor graph should be identifiable → no negative cert
        if bundle.identification_status == "identified":
            assert cert is None

    def test_run_negative_cert_for_non_identifiable(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        graph = make_confounded([("X", "Y")], [("X", "Y")])
        report, bundle, cert = engine.run("X", "Y", graph)
        # Should get negative cert or HEDGE_FOUND
        assert (
            report is None
            or cert is not None
            or bundle.identification_status in {"hedge_found", "oracle_needed"}
        )
        if cert is not None:
            assert cert.recovery_plan is not None
            assert bundle.proof_bundle_ref is not None
            assert bundle.negative_certificate_ref is not None
            restored_cert = load_negative_certificate(store, bundle.negative_certificate_ref)
            assert restored_cert.blocking_type == cert.blocking_type
            if cert.bounds_bundle is None:
                assert bundle.data_readiness_report_ref is not None
            else:
                assert bundle.bounds_bundle_ref is not None
                restored_bounds = load_bounds_bundle(store, bundle.bounds_bundle_ref)
                assert restored_bounds.lower_bound == cert.bounds_bundle.lower_bound

    def test_run_returns_proximal_proof_bundle_without_negative_certificate(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        graph = make_admg_confounded(
            [("X", "A"), ("X", "Y"), ("Z", "A"), ("A", "Y")],
            [("A", "Y"), ("A", "Z"), ("Y", "W")],
        )

        report, bundle, cert = engine.run(
            "A",
            "Y",
            graph,
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
            ),
        )

        assert report is None
        assert cert is None
        assert bundle.identification_status == "identified"
        assert bundle.proof_bundle_ref is not None
        assert bundle.data_readiness_report_ref is not None

        proof_bundle = load_proof_bundle(store, bundle.proof_bundle_ref)
        readiness = load_data_readiness_report(store, bundle.data_readiness_report_ref)

        assert proof_bundle.metadata["method"] == "proximal_bridge"
        assert proof_bundle.metadata["proximal_certificate"]["query"]["treatment"] == ["A"]
        assert proof_bundle.proximal_certificate_ref is not None
        assert load_proximal_identification_certificate(
            store, proof_bundle.proximal_certificate_ref
        ).query.treatment == ("A",)
        assert readiness.measurement_quality == "proxy_only"

    def test_run_executes_proximal_bridge_diagnostics_when_proxy_arrays_available(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        graph = make_admg_confounded(
            [("X", "A"), ("X", "Y"), ("Z", "A"), ("A", "Y")],
            [("A", "Y"), ("A", "Z"), ("Y", "W")],
        )
        rng = np.random.default_rng(552)
        n_obs = 240
        x = rng.normal(size=n_obs)
        latent = 0.7 * x + rng.normal(scale=0.5, size=n_obs)
        logits = 0.35 * x + 0.8 * latent
        treatment = (rng.uniform(size=n_obs) < (1.0 / (1.0 + np.exp(-logits)))).astype(float)
        z_proxy = latent + rng.normal(scale=0.25, size=n_obs)
        w_proxy = 0.9 * latent + 0.2 * x + rng.normal(scale=0.25, size=n_obs)
        y = 1.1 * treatment + 0.45 * x + latent + rng.normal(scale=0.25, size=n_obs)

        report, bundle, cert = engine.run(
            "A",
            "Y",
            graph,
            data_dict={"A": treatment, "Y": y, "X": x, "Z": z_proxy, "W": w_proxy},
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
            ),
        )

        assert report is not None
        assert cert is None
        assert report.status.value == "success"
        assert report.metadata["bridge_plausibility_report"]["severity"] in {"green", "yellow"}
        assert bundle.identification_status == "identified"
        assert "bridge_residual_r" in bundle.diagnostic_scores
        assert bundle.proof_bundle_ref is not None
        assert bundle.data_readiness_report_ref is not None

    def test_run_routes_spatial_proximal_certificate_into_spatial_bridge_execution(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        graph = make_admg_confounded(
            [
                ("X1", "A"),
                ("X1", "Y"),
                ("X2", "A"),
                ("X2", "Y"),
                ("Z1", "A"),
                ("Z2", "A"),
                ("A", "Y"),
            ],
            [
                ("A", "Y"),
                ("A", "Z1"),
                ("A", "Z2"),
                ("Y", "W1"),
                ("Y", "W2"),
            ],
        )

        rng = np.random.default_rng(2405)
        n_obs = 180
        adjacency = np.zeros((n_obs, n_obs), dtype=float)
        for idx in range(n_obs):
            adjacency[idx, (idx - 1) % n_obs] = 1.0
            adjacency[idx, (idx + 1) % n_obs] = 1.0
            adjacency[idx, (idx - 2) % n_obs] = 1.0
            adjacency[idx, (idx + 2) % n_obs] = 1.0

        x1 = rng.normal(size=n_obs)
        x2 = rng.normal(size=n_obs)
        latent = 0.45 * x1 - 0.25 * x2 + rng.normal(scale=0.4, size=n_obs)
        treatment_logits = 0.4 * x1 + 0.2 * x2 + 0.8 * latent
        treatment = (rng.uniform(size=n_obs) < (1.0 / (1.0 + np.exp(-treatment_logits)))).astype(
            float
        )
        spillover_treatment = adjacency @ treatment / np.maximum(adjacency.sum(axis=1), 1.0)
        outcome = (
            0.9 * treatment
            + 0.2 * spillover_treatment
            + 0.3 * x1
            + 0.15 * x2
            + 0.8 * latent
            + rng.normal(scale=0.25, size=n_obs)
        )
        z1 = latent + rng.normal(scale=0.15, size=n_obs)
        z2 = 0.85 * latent + 0.1 * x1 + rng.normal(scale=0.15, size=n_obs)
        w1 = 0.9 * latent + 0.05 * x2 + rng.normal(scale=0.15, size=n_obs)
        w2 = 0.8 * latent + 0.1 * x1 + rng.normal(scale=0.15, size=n_obs)

        report, bundle, cert = engine.run(
            "A",
            "Y",
            graph,
            data_dict={
                "A": treatment,
                "Y": outcome,
                "X1": x1,
                "X2": x2,
                "Z1": z1,
                "Z2": z2,
                "W1": w1,
                "W2": w2,
                "adjacency_matrix": adjacency,
                "model_family": "sdm",
            },
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z1", "Z2"),
                outcome_inducing=("W1", "W2"),
                covariates=("X1", "X2"),
                spatial_proxy_specs=(
                    SpatialProxySpec(
                        proxy_variables=("Z1", "Z2"),
                        weight_matrix_ref="weights:ring4",
                        proxy_construction="buffered_ring_lag",
                        lag_orders=(2, 3),
                        buffer_radius=1,
                        time_mode="contemporaneous",
                        allowed_roles=("treatment_inducing",),
                        spillover_radius_claim=1,
                    ),
                    SpatialProxySpec(
                        proxy_variables=("W1", "W2"),
                        weight_matrix_ref="weights:ring4",
                        proxy_construction="pre_treatment_ring_lag",
                        lag_orders=(3, 4),
                        buffer_radius=2,
                        time_mode="pre_treatment",
                        allowed_roles=("outcome_inducing",),
                        spillover_radius_claim=1,
                    ),
                ),
            ),
        )

        assert cert is None
        assert report is not None
        assert report.status.value == "success"
        assert report.metadata["spatial_model_family"] == "sdm"
        assert report.metadata["bridge_plausibility_report"]["severity"] in {"green", "yellow"}
        assert bundle.identification_status == "identified"
        assert bundle.algorithm_version == "proximal_spatial_id_v1"
        assert "bridge_moran_i" in bundle.diagnostic_scores
        assert "bridge_ring_instability" in bundle.diagnostic_scores
        assert "buffer_exclusion_falsification" in bundle.diagnostic_scores
        assert bundle.proof_bundle_ref is not None
        assert bundle.data_readiness_report_ref is not None

        proof_bundle = load_proof_bundle(store, bundle.proof_bundle_ref)
        readiness = load_data_readiness_report(store, bundle.data_readiness_report_ref)
        assert proof_bundle.metadata["method"] == "spatial_proximal_bridge"
        assert proof_bundle.theorem_family == "proximal_spatial_id_v1"
        assert proof_bundle.proximal_certificate_ref is not None
        assert proof_bundle.bridge_plausibility_report_ref is not None
        assert proof_bundle.metadata["spatial_model_family"] == "sdm"
        assert proof_bundle.metadata["weight_matrix_hash"]
        assert proof_bundle.metadata["impact_functionals_declared"] == [
            "tau",
            "ADE",
            "AIE",
            "ATE_total",
        ]
        assert readiness.measurement_quality == "proxy_only"
        assert "bridge_moran_i" in readiness.metrics
        assert "bridge_ring_instability" in readiness.metrics

        restored_cert = load_proximal_identification_certificate(
            store,
            proof_bundle.proximal_certificate_ref,
        )
        assert restored_cert.metadata["method"] == "spatial_proximal_bridge"
        restored_bridge = load_bridge_plausibility_report(
            store,
            proof_bundle.bridge_plausibility_report_ref,
        )
        assert restored_bridge.buffer_exclusion_falsification is False

    def test_run_path_specific_proximal_returns_bounds_when_oracle_not_accepted(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        graph = make_admg_confounded(
            [
                ("X", "A"),
                ("X", "M"),
                ("X", "Y"),
                ("Z", "A"),
                ("A", "M"),
                ("M", "Y"),
                ("A", "Y"),
            ],
            [("A", "Y"), ("A", "Z"), ("Y", "W")],
        )
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DECOMPOSITION,
                outcome_variables=("Y",),
            ),
            intervention=PathIntervention(
                active_paths=(("A", "M", "Y"),),
                frozen_paths=(("A", "Y"),),
                natural_value_vars=("M",),
            ),
        )
        rng = np.random.default_rng(917)
        n_obs = 260
        x = rng.normal(size=n_obs)
        latent = 0.6 * x + rng.normal(scale=0.45, size=n_obs)
        logits = 0.45 * x + 0.8 * latent
        treatment = (rng.uniform(size=n_obs) < (1.0 / (1.0 + np.exp(-logits)))).astype(float)
        mediator = 0.9 * treatment + 0.35 * x + 0.5 * latent + rng.normal(scale=0.3, size=n_obs)
        z_proxy = latent + rng.normal(scale=0.25, size=n_obs)
        w_proxy = 0.75 * latent + 0.25 * x + rng.normal(scale=0.25, size=n_obs)
        outcome = (
            0.75 * treatment
            + 0.95 * mediator
            + 0.25 * x
            + latent
            + rng.normal(scale=0.3, size=n_obs)
        )

        report, bundle, cert = engine.run(
            "A",
            "Y",
            graph,
            data_dict={
                "A": treatment,
                "M": mediator,
                "Y": outcome,
                "X": x,
                "Z": z_proxy,
                "W": w_proxy,
            },
            intervention_query=query,
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
            ),
        )

        assert report is None
        assert cert is not None
        assert cert.blocking_type is BlockingType.COMPLETENESS_UNLIKELY
        assert bundle.proof_bundle_ref is not None
        assert bundle.bounds_bundle_ref is not None
        proof_bundle = load_proof_bundle(store, bundle.proof_bundle_ref)
        restored_bounds = load_bounds_bundle(store, bundle.bounds_bundle_ref)
        assert proof_bundle.proof_status == "oracle_needed"
        assert restored_bounds.metadata["source"] == "proximal_mediation_v1_fallback"
        assert restored_bounds.lower_bound < restored_bounds.upper_bound

    def test_run_path_specific_proximal_executes_when_oracle_is_accepted(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        graph = make_admg_confounded(
            [
                ("X", "A"),
                ("X", "M"),
                ("X", "Y"),
                ("Z", "A"),
                ("A", "M"),
                ("M", "Y"),
                ("A", "Y"),
            ],
            [("A", "Y"), ("A", "Z"), ("Y", "W")],
        )
        query = InterventionQuery(
            target=QueryTarget(
                target_kind=QueryTargetKind.DECOMPOSITION,
                outcome_variables=("Y",),
            ),
            intervention=PathIntervention(
                active_paths=(("A", "M", "Y"),),
                frozen_paths=(("A", "Y"),),
                natural_value_vars=("M",),
            ),
        )
        rng = np.random.default_rng(1017)
        n_obs = 260
        x = rng.normal(size=n_obs)
        latent = 0.55 * x + rng.normal(scale=0.45, size=n_obs)
        logits = 0.4 * x + 0.75 * latent
        treatment = (rng.uniform(size=n_obs) < (1.0 / (1.0 + np.exp(-logits)))).astype(float)
        mediator = 0.85 * treatment + 0.4 * x + 0.45 * latent + rng.normal(scale=0.3, size=n_obs)
        z_proxy = latent + rng.normal(scale=0.25, size=n_obs)
        w_proxy = 0.8 * latent + 0.2 * x + rng.normal(scale=0.25, size=n_obs)
        outcome = (
            0.7 * treatment + 1.0 * mediator + 0.3 * x + latent + rng.normal(scale=0.3, size=n_obs)
        )

        report, bundle, cert = engine.run(
            "A",
            "Y",
            graph,
            data_dict={
                "A": treatment,
                "M": mediator,
                "Y": outcome,
                "X": x,
                "Z": z_proxy,
                "W": w_proxy,
            },
            intervention_query=query,
            proximal_annotation=ProxyAnnotation(
                treatment_inducing=("Z",),
                outcome_inducing=("W",),
                covariates=("X",),
                accept_oracle_assumptions=True,
            ),
        )

        assert cert is None
        assert report is not None
        assert report.status.value == "success"
        assert bundle.identification_status == "identified"
        assert bundle.proof_bundle_ref is not None
        proof_bundle = load_proof_bundle(store, bundle.proof_bundle_ref)
        assert proof_bundle.proof_status == "identified"
        assert report.metadata["bridge_plausibility_report"]["severity"] in {"green", "yellow"}

    def test_audit_persists_dual_certificate_for_exact_bounds_bundle(self, tmp_path):
        from polisyos.foundry.methods.catalog.causal.bounds_engine import BoundsEngineMethod

        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        bounds_result = BoundsEngineMethod.pure_step(
            {
                "outcome": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                "treatment": [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
            },
            {"use_auto_bounds": True, "has_monotone": True},
        )
        negative_cert = NegativeCertificate(
            blocking_type=BlockingType.HEDGE_STRUCTURE,
            blocking_description="Synthetic hedge for audit persistence test.",
            constructive_message="Need fallback evidence.",
        )

        bundle = engine.audit(
            None,
            None,
            run_id="audit-dual-cert",
            negative_certificate=negative_cert,
            bounds_bundle=bounds_result["bounds_report"],
            dual_certificate_payload=bounds_result.get("dual_certificate_payload"),
        )

        assert bundle.bounds_bundle_ref is not None

        restored_bounds = load_bounds_bundle(store, bundle.bounds_bundle_ref)
        assert restored_bounds.dual_certificate_ref is not None
        assert restored_bounds.sharpness_status == "sharp"

        dual_cert = load_dual_certificate_bundle(store, restored_bounds.dual_certificate_ref)
        validation = validate_dual_certificate_bundle(dual_cert)
        assert validation.ok, validation.errors

    def test_run_skips_estimator_execution_when_preflight_blocks(self, tmp_path, monkeypatch):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=object(), artifact_store=store)
        graph = make_dag([("Z", "X"), ("X", "Y"), ("Z", "Y")])

        identified = engine.identify("X", "Y", graph)
        if not isinstance(identified, IdentificationResult):
            pytest.skip("Identification unexpectedly returned a NegativeCertificate.")
        if identified.status != IdentificationStatus.IDENTIFIED:
            pytest.skip(f"Expected identified query, got {identified.status}.")

        block_report = build_data_readiness_report(
            sample_size=120,
            measurement_quality="known_good",
            fallback_data_available=True,
            support_mismatch={"passes_support_check": False},
        )
        monkeypatch.setattr(
            engine,
            "compile",
            lambda *args, **kwargs: ExecutorGraph(
                nodes=(), edges=(), nuisance_schedule=(), run_id="run"
            ),
        )
        monkeypatch.setattr(
            engine,
            "_run_readiness_preflight",
            lambda **kwargs: (block_report, {}),
        )

        def _unexpected_estimate(*args, **kwargs):
            raise AssertionError(
                "estimate() should not run when readiness preflight blocks execution"
            )

        monkeypatch.setattr(engine, "estimate", _unexpected_estimate)

        report, bundle, cert = engine.run(
            "X",
            "Y",
            graph,
            data_dict={
                "X": np.array([0.0, 1.0, 0.0, 1.0]),
                "Y": np.array([1.0, 2.0, 1.5, 2.5]),
                "Z": np.array([0.0, 0.0, 1.0, 1.0]),
            },
        )

        assert report is None
        assert cert is None
        assert bundle.data_readiness_report_ref is not None
        readiness = load_data_readiness_report(store, bundle.data_readiness_report_ref)
        assert readiness.decision == "block"
        assert readiness.can_run_estimation is False

    def test_run_readiness_preflight_allows_estimators_without_diagnostic_nodes(self):
        engine = CausalEngine(registry=object())
        executor_graph = ExecutorGraph(
            nodes=(
                ExecutorNode(
                    node_id="twin_network",
                    method_fqn="causal.structural.twin_network_query",
                    method_version="1.0.0",
                    params={},
                    depends_on=(),
                    reads_slots=(),
                    writes_slots=(),
                    is_nuisance=False,
                    dataset_ref=None,
                    skip_if_failed=(),
                ),
            ),
            edges=(),
            nuisance_schedule=(),
            run_id="ctf",
        )

        readiness, outputs = engine._run_readiness_preflight(
            executor_graph=executor_graph,
            data_dict={
                "X": np.array([0.0, 1.0, 0.0, 1.0]),
                "Y": np.array([1.0, 2.0, 1.5, 2.5]),
            },
            sample_size=120,
            fallback_data_available=True,
        )

        assert outputs == {}
        assert readiness.decision == "warn"
        assert readiness.can_run_estimation is True

    def test_run_returns_bounds_and_skips_compile_when_dp_status_is_bounded(
        self, tmp_path, monkeypatch
    ):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=object(), artifact_store=store)
        identified = _identified_result()

        certificate = _laplace_dp_certificate(
            epsilon=0.5,
            sample_size=1_000,
            cell_count=32,
            min_denominator_margin=1.0,
            lipschitz_upper_bound=100.0,
            policy_tolerance=0.001,
        ).model_copy(
            update={
                "effective_validity": DPEffectiveValidity(
                    status=DPRobustnessStatus.BOUNDED,
                    reason="DP distortion exceeds point-estimate tolerance",
                    effect_interval=(-0.12, -0.03),
                    tolerance_met=False,
                ),
                "hard_block": DPHardBlock(blocked=False),
            }
        )
        identified = dataclasses.replace(
            identified,
            metadata={
                **dict(identified.metadata),
                "dp_robustness_certificate": certificate.model_dump(mode="json"),
            },
        )

        monkeypatch.setattr(engine, "identify", lambda *args, **kwargs: identified)

        def _unexpected_compile(*args, **kwargs):
            raise AssertionError("compile() should not run for bounded DP releases")

        def _unexpected_estimate(*args, **kwargs):
            raise AssertionError("estimate() should not run for bounded DP releases")

        monkeypatch.setattr(engine, "compile", _unexpected_compile)
        monkeypatch.setattr(engine, "estimate", _unexpected_estimate)

        report, bundle, cert = engine.run(
            "X",
            "Y",
            self.graph,
            data_dict={
                "X": np.array([0.0, 1.0, 0.0, 1.0]),
                "Y": np.array([1.0, 2.0, 1.5, 2.5]),
                "Z": np.array([0.0, 0.0, 1.0, 1.0]),
            },
        )

        assert report is None
        assert cert is None
        assert bundle.proof_bundle_ref is not None
        assert bundle.bounds_bundle_ref is not None
        assert bundle.data_readiness_report_ref is not None

        readiness = load_data_readiness_report(store, bundle.data_readiness_report_ref)
        assert readiness.decision == "warn"
        assert readiness.can_run_estimation is False
        assert readiness.dp_distortion is not None
        assert readiness.dp_distortion["effective_status"] == "bounded"

        proof = load_proof_bundle(store, bundle.proof_bundle_ref)
        assert proof.metadata["dp_effective_status"] == "bounded"
        assert proof.dp_robustness_ref is not None

        bounds = load_bounds_bundle(store, bundle.bounds_bundle_ref)
        assert bounds.lower_bound == -0.12
        assert bounds.upper_bound == -0.03
        assert bounds.metadata["dp_effective_status"] == "bounded"


class TestCausalEngineTemporal:
    @staticmethod
    def _panel_data() -> PanelObservationalData:
        outcome = np.array(
            [
                [0.0, 0.2, 0.4, 1.6],
                [0.0, 0.2, 0.4, 0.5],
                [0.1, 0.1, 0.3, 0.4],
            ],
            dtype=float,
        )
        return PanelObservationalData(
            outcome=outcome,
            treatment=np.array([1, 0, 0], dtype=int),
            time_treatment=3,
            time_index=np.array([0.0, 1.0, 2.0, 3.0], dtype=float),
        )

    @staticmethod
    def _intervention() -> TemporalInterventionTrajectory:
        return TemporalInterventionTrajectory(
            time_points=(0.0, 1.0, 2.0, 3.0),
            values=(0.0, 0.0, 0.0, 1.0),
            time_scale="days",
            interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
        )

    @classmethod
    def _query(
        cls,
        intervention_ref: ArtifactRefModel | None = None,
        *,
        query_mode: TemporalQueryMode = TemporalQueryMode.FIXED_INTERVENTION,
        outcome_process: str = "treated_outcome",
        horizon_end: float = 3.0,
        sampling_scheme: TemporalSamplingScheme = TemporalSamplingScheme.REGULAR_GRID,
        target_functional: TemporalTargetFunctional = TemporalTargetFunctional.EFFECT_PATH,
        metadata: dict[str, object] | None = None,
    ) -> ContinuousTimeQuery:
        return ContinuousTimeQuery(
            intervention_trajectory_ref=(
                intervention_ref
                if intervention_ref is not None
                or query_mode is TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY
                else _artifact_ref("a", kind="ir.temporal_intervention_trajectory")
            ),
            query_mode=query_mode,
            outcome_process=outcome_process,
            horizon_start=0.0,
            horizon_end=horizon_end,
            target_functional=target_functional,
            sampling_scheme=sampling_scheme,
            time_scale="days",
            interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def _identification_certificate(
        *,
        theorem_family: TemporalIdentificationTheoremFamily = (
            TemporalIdentificationTheoremFamily.NSDE_FIXED_OBSERVED_CHANNEL_V1
        ),
    ) -> TemporalIdentificationCertificate:
        if theorem_family is TemporalIdentificationTheoremFamily.NCDE_FIXED_OBSERVED_CHANNEL_V1:
            return TemporalIdentificationCertificate(
                theorem_family=theorem_family,
                identified_functionals=(
                    TemporalTargetFunctional.EFFECT_PATH,
                    TemporalTargetFunctional.INTEGRAL_EFFECT,
                ),
                intervention_semantics=TemporalInterventionSemantics.SURGICAL_REPLACEMENT,
                observability_regime=TemporalObservabilityRegime.FULL_STATE,
                law_object=TemporalLawObject.CANONICAL_CONTROL_PATH,
                canonical_control_required=True,
                control_canonicalization=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
                assumptions=("full_state_observability", "canonical_control_path"),
            )
        return TemporalIdentificationCertificate(
            theorem_family=theorem_family,
            identified_functionals=(
                TemporalTargetFunctional.EFFECT_PATH,
                TemporalTargetFunctional.INTEGRAL_EFFECT,
            ),
            intervention_semantics=TemporalInterventionSemantics.SURGICAL_REPLACEMENT,
            observability_regime=TemporalObservabilityRegime.FULL_STATE,
            law_object=TemporalLawObject.SEMIMARTINGALE_CHARACTERISTICS,
            assumptions=("full_state_observability", "weak_uniqueness_after_intervention"),
        )

    @staticmethod
    def _dynamic_data() -> DynamicTreatmentData:
        rng = np.random.default_rng(123)
        n_units, n_periods = 220, 3
        state = np.zeros((n_units, n_periods), dtype=float)
        treatment = np.zeros((n_units, n_periods), dtype=int)
        state[:, 0] = rng.normal(0.0, 1.0, size=n_units)
        for t in range(n_periods):
            probs = 1.0 / (1.0 + np.exp(-(0.2 + 0.2 * state[:, t])))
            treatment[:, t] = rng.binomial(1, probs)
            if t < n_periods - 1:
                state[:, t + 1] = (
                    0.55 * state[:, t]
                    + 0.45 * treatment[:, t] * (state[:, t] > 0.0)
                    - 0.20 * treatment[:, t] * (state[:, t] <= 0.0)
                    + rng.normal(0.0, 0.25, size=n_units)
                )
        reward = (1.4 * treatment * (state > 0.0) - 0.7 * treatment * (state <= 0.0)).sum(axis=1)
        outcome = reward + 0.25 * state[:, 0] + rng.normal(0.0, 0.30, size=n_units)
        return DynamicTreatmentData(
            outcome=outcome,
            treatment_sequence=treatment,
            covariate_sequence=state[:, :, np.newaxis],
            time_ids=np.arange(n_periods, dtype=float),
            variable_names=["state"],
        )

    @staticmethod
    def _event_process_data() -> EventProcessObservationalData:
        outcome_events = np.array(
            [
                [0, 0, 1, 0],
                [0, 1, 0, 0],
                [0, 0, 0, 1],
                [0, 0, 1, 0],
                [0, 0, 0, 0],
                [0, 0, 0, 1],
            ],
            dtype=int,
        )
        return EventProcessObservationalData(
            outcome_events=outcome_events,
            censoring_events=np.zeros_like(outcome_events, dtype=int),
            policy_weights=np.array(
                [
                    [1.0, 1.0, 1.8, 1.8],
                    [1.0, 1.2, 1.2, 1.2],
                    [1.0, 1.0, 1.0, 1.7],
                    [1.0, 1.0, 1.5, 1.5],
                    [1.0, 1.0, 1.0, 1.0],
                    [1.0, 1.0, 1.0, 1.6],
                ],
                dtype=float,
            ),
            baseline_weights=np.ones((6, 4), dtype=float),
            time_index=np.array([0.0, 1.0, 2.5, 4.0], dtype=float),
            metadata={"time_scale": "days", "process_family": "event_log"},
        )

    def test_temporal_causal_effect_persists_bundle(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        intervention_ref = persist_temporal_intervention_trajectory(store, self._intervention())

        trajectory = engine.temporal_causal_effect(
            self._panel_data(),
            self._query(intervention_ref),
            method="linear_sde",
        )

        assert trajectory.effect_bundle is not None
        assert "effect_bundle_artifact_id" in trajectory.metadata
        bundle_ref = EffectTrajectoryBundleRef(
            artifact_id=trajectory.metadata["effect_bundle_artifact_id"]
        )
        restored = load_effect_trajectory_bundle(store, bundle_ref)
        assert restored.query_ref.kind == "ir.continuous_time_query"
        assert restored.trajectory_ref.kind == "ir.temporal_trajectory"
        assert restored.confidence_band_ref.kind == "ir.temporal_confidence_band"
        assert restored.solver_diagnostics_ref.kind == "ir.temporal_solver_diagnostics"
        assert restored.metadata["intervention_contract_status"] == "resolved_artifact"
        assert restored.continuous_time_degraded is False
        assert restored.metadata["proof_bundle_artifact_id"]
        diagnostics_payload = get_json_artifact(store, restored.solver_diagnostics_ref.artifact_id)
        assert diagnostics_payload["schema_name"] == "ir.temporal_solver_diagnostics"
        assert diagnostics_payload["schema_version"] == "1.1"
        assert (
            diagnostics_payload["causal_translation_certificate"]["status"]
            == "certified_restricted"
        )
        assert diagnostics_payload["causal_translation_certificate"]["evidence"]["theory_refs"]
        assert diagnostics_payload["causal_equivalence_note"]

        proof_ref = ProofBundleRef.model_validate(restored.metadata["proof_bundle_ref"])
        proof = load_proof_bundle(store, proof_ref)
        assert proof.proof_status == "oracle_needed"
        assert proof.dynamic_semantics is not None
        assert (
            proof.dynamic_semantics.semantics_family
            is DynamicSemanticsFamily.LOCAL_INDEPENDENCE_GRAPH
        )
        assert proof.dynamic_semantics.reduction_status is DynamicReductionStatus.BLOCKED

    def test_identify_continuous_time_query_marks_validated_local_independence(self):
        engine = CausalEngine(registry=None, knowledge_base=None)
        query = self._query(
            metadata={
                "graph_semantics": "local_independence",
                "graphical_oracle": "mu",
                "causal_validity_verified": True,
                "identification_via_reweighting": True,
                "eliminable_processes": ["latent_noise"],
                "intervention_targets": ["treatment"],
            }
        )

        proof = engine.identify_continuous_time_query(query)

        assert proof.proof_status == "identified"
        assert proof.proof_stratum == "A1_dynamic"
        assert proof.dynamic_semantics is not None
        assert (
            proof.dynamic_semantics.semantics_family
            is DynamicSemanticsFamily.LOCAL_INDEPENDENCE_GRAPH
        )
        assert (
            proof.dynamic_semantics.reduction_status is DynamicReductionStatus.VALIDATED_REDUCTION
        )
        assert proof.dynamic_semantics.continuous_time_attachment is not None
        assert proof.dynamic_semantics.continuous_time_attachment.eliminable_processes == (
            "latent_noise",
        )
        assert proof.estimand_ast is not None
        assert proof.estimand_ast["theorem_family"] == "local_independence_weighting_v1"
        assert proof.estimand_ast["verification_status"] == "identified"
        assert "causal_validity_intensity_replacement" in proof.assumptions
        assert "independent_censoring_local" in proof.assumptions
        assert "LI_WEIGHTING_IDENTIFY" in proof.proof_trace

    def test_temporal_causal_effect_persists_validated_local_independence_proof(self, tmp_path):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        intervention_ref = persist_temporal_intervention_trajectory(store, self._intervention())

        trajectory = engine.temporal_causal_effect(
            self._panel_data(),
            self._query(
                intervention_ref,
                metadata={
                    "graph_semantics": "local_independence",
                    "graphical_oracle": "delta",
                    "causal_validity_verified": True,
                    "identification_via_reweighting": True,
                    "eliminable_processes": ["hidden_process"],
                    "intervention_targets": ["treated_outcome"],
                },
            ),
            method="linear_sde",
        )

        assert trajectory.effect_bundle is not None
        bundle = trajectory.effect_bundle
        proof_ref = ProofBundleRef.model_validate(bundle.metadata["proof_bundle_ref"])
        proof = load_proof_bundle(store, proof_ref)
        assert proof.proof_status == "identified"
        assert proof.dynamic_semantics is not None
        assert (
            proof.dynamic_semantics.reduction_status is DynamicReductionStatus.VALIDATED_REDUCTION
        )
        assert proof.metadata["local_independence_certificate_ref"]["kind"] == (
            "ir.local_independence_weighting_certificate"
        )
        certificate = load_local_independence_weighting_certificate(
            store,
            LocalIndependenceWeightingCertificateRef.model_validate(
                proof.metadata["local_independence_certificate_ref"]
            ),
        )
        assert certificate.verification_status == "identified"
        assert certificate.graph.process_family == "counting_process"
        assert certificate.graphical_checks.eliminability.checked is True
        assert bundle.metadata["local_independence_certificate_ref"]["kind"] == (
            "ir.local_independence_weighting_certificate"
        )
        assert trajectory.metadata["proof_status"] == "identified"

    def test_temporal_causal_effect_event_process_persists_temporal_identification_certificate(
        self,
        tmp_path,
    ):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        intervention_ref = persist_temporal_intervention_trajectory(
            store,
            TemporalInterventionTrajectory(
                time_points=(0.0, 1.0, 2.0, 3.0, 4.0),
                values=(0.0, 0.0, 1.0, 1.0, 1.0),
                time_scale="days",
                interpolation_policy=InterventionInterpolationPolicy.PIECEWISE_CONSTANT,
            ),
        )

        trajectory = engine.temporal_causal_effect(
            self._event_process_data(),
            self._query(
                intervention_ref,
                outcome_process="event",
                horizon_end=4.0,
                sampling_scheme=TemporalSamplingScheme.IRREGULAR_GRID,
                target_functional=TemporalTargetFunctional.CUMULATIVE_INCIDENCE,
                metadata={
                    "preferred_backend": "event_process_weighting",
                    "process_family": "event_log",
                    "graph_semantics": "local_independence",
                    "graphical_oracle": "delta",
                    "causal_validity_verified": True,
                    "identification_via_reweighting": True,
                    "independent_censoring_verified": True,
                    "eliminability_verified": True,
                    "intervention_targets": ["X"],
                },
            ),
            method="event_process_weighting",
        )

        assert trajectory.effect_bundle is not None
        bundle = trajectory.effect_bundle
        assert bundle.identification_certificate_ref is not None
        temporal_certificate = load_temporal_identification_certificate(
            store,
            bundle.identification_certificate_ref,
        )
        assert (
            temporal_certificate.theorem_family
            is TemporalIdentificationTheoremFamily.LOCAL_INDEPENDENCE_WEIGHTING_V1
        )
        assert bundle.metadata["temporal_identification_certificate_ref"]["kind"] == (
            "ir.temporal_identification_certificate"
        )
        assert bundle.metadata["backend_target"] == "event_process_weighting"
        assert trajectory.effect_path[-1] > 0.0

    def test_identify_continuous_time_query_accepts_neural_theorem_certificate(
        self,
        tmp_path,
    ):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)
        intervention_ref = persist_temporal_intervention_trajectory(store, self._intervention())
        certificate = self._identification_certificate()
        query = self._query(
            intervention_ref,
            metadata={
                "preferred_backend": "neural_sde",
                "temporal_identification_certificate": certificate.model_dump(mode="json"),
            },
        )

        proof = engine.identify_continuous_time_query(
            query,
            identification_certificate=certificate,
            query_ref=_artifact_id("b"),
        )

        assert proof.proof_status == "identified"
        assert proof.theorem_family == "nsde_fixed_observed_channel_v1"
        assert proof.dynamic_semantics is not None
        assert proof.dynamic_semantics.semantics_family is DynamicSemanticsFamily.IOSCM
        assert proof.dynamic_semantics.intervention_scope is not None
        assert proof.dynamic_semantics.intervention_scope.kind.value == "mechanism_swap"
        assert proof.metadata["temporal_identification_certificate_ref"]["kind"] == (
            "ir.temporal_identification_certificate"
        )
        assert proof.metadata["identification_scope"]["support_status"] == "on_support"
        assert proof.metadata["identification_scope"]["scope_covered"] is True

    def test_temporal_causal_effect_passes_neural_identification_certificate_to_compiler(self):
        engine = CausalEngine(registry=None, knowledge_base=None)

        trajectory = engine.temporal_causal_effect(
            self._panel_data(),
            self._query(),
            intervention=self._intervention(),
            method="neural_sde",
            identification_certificate=self._identification_certificate(),
        )

        assert trajectory.path_representation.value == "neural_sde"
        assert trajectory.solver_family == "law_invariant_nsde"
        assert trajectory.metadata["identification_scope"]["theorem_family"] == (
            "nsde_fixed_observed_channel_v1"
        )
        assert trajectory.metadata["identification_support_status"] == "on_support"

    def test_temporal_causal_effect_requires_intervention_source(self):
        engine = CausalEngine(registry=None, knowledge_base=None)

        with pytest.raises(Exception, match="intervention"):
            engine.temporal_causal_effect(
                self._panel_data(),
                self._query(),
                method="linear_sde",
            )

    def test_temporal_causal_effect_optimal_policy_discovery_persists_policy_lineage(
        self,
        tmp_path,
    ):
        store = FileSystemCAS(tmp_path / "cas")
        engine = CausalEngine(registry=None, artifact_store=store)

        trajectory = engine.temporal_causal_effect(
            self._dynamic_data(),
            self._query(
                intervention_ref=None,
                query_mode=TemporalQueryMode.OPTIMAL_POLICY_DISCOVERY,
                outcome_process="state",
                horizon_end=2.0,
            ),
            method="linear_sde",
        )

        assert trajectory.effect_bundle is not None
        bundle = trajectory.effect_bundle
        assert bundle.metadata["execution_contract_kind"] == "optimal_policy_discovery"
        assert bundle.metadata["policy_artifact_ref"] is not None
        assert bundle.metadata["derived_schedule_ref"] is not None

        policy_ref = DynamicTreatmentRegimeRef.model_validate(
            bundle.metadata["policy_artifact_ref"]
        )
        derived_ref = TemporalInterventionTrajectoryRef.model_validate(
            bundle.metadata["derived_schedule_ref"]
        )
        restored_policy = load_dynamic_treatment_regime(store, policy_ref)
        restored_schedule = load_temporal_intervention_trajectory(store, derived_ref)

        assert isinstance(restored_policy, DynamicTreatmentRegime)
        assert restored_policy.rule in {RegimeRule.THRESHOLD, RegimeRule.ALWAYS_TREAT}
        assert len(restored_schedule.values) == 3


@pytest.mark.parametrize(
    ("label", "callable_factory"),
    [
        (
            "dynamic_causal_effect",
            lambda engine: lambda: engine.dynamic_causal_effect(data={}, method="ice_g"),
        ),
        (
            "temporal_causal_effect",
            lambda engine: lambda: engine.temporal_causal_effect(
                data={},
                query=TestCausalEngineTemporal._query(intervention_ref=None),
                intervention=TestCausalEngineTemporal._intervention(),
                method="linear_sde",
            ),
        ),
        (
            "mediation_analysis",
            lambda engine: lambda: engine.mediation_analysis(
                data={},
                treatment="X",
                outcome="Y",
                mediators=["M"],
                method="linear",
            ),
        ),
        (
            "interference_effect",
            lambda engine: lambda: engine.interference_effect(
                data={},
                treatment="T",
                outcome="Y",
                method="network_aipw",
            ),
        ),
        (
            "fairness_audit",
            lambda engine: lambda: engine.fairness_audit(
                data={},
                protected="A",
                outcome="Y",
                method="tv_decomposition",
            ),
        ),
    ],
)
def test_direct_estimation_wrappers_block_on_missing_readiness(label, callable_factory):
    engine = CausalEngine(registry=None, knowledge_base=None)
    wrapped_call = callable_factory(engine)

    with pytest.raises(DataReadinessBlockedError) as exc_info:
        wrapped_call()

    assert exc_info.value.report.decision == "unknown", label
    assert exc_info.value.report.can_run_estimation is False, label


def test_dynamic_causal_effect_runs_with_verified_readiness(monkeypatch):
    from polisyos.foundry.methods.catalog.causal.g_computation import ICEGFormula
    from polisyos.ir.analytics.dynamic_regime import GComputationResult

    engine = CausalEngine(registry=None, knowledge_base=None)

    def _fake_pure_step(state, params):
        return {
            "g_result": GComputationResult(
                counterfactual_mean=1.25,
                confidence_interval=(0.9, 1.6),
                confidence_level=0.95,
                standard_error=0.1,
                regime=str(params.get("regime", "always_treat")),
                n_units=220,
                n_periods=3,
                method="ice_g",
            )
        }

    monkeypatch.setattr(ICEGFormula, "pure_step", staticmethod(_fake_pure_step))

    result = engine.dynamic_causal_effect(
        data=TestCausalEngineTemporal._dynamic_data(),
        method="ice_g",
    )

    assert result.method == "ice_g"
    assert result.counterfactual_mean == pytest.approx(1.25)


def test_dynamic_causal_effect_blocks_government_data_without_survey_certificate(
    monkeypatch, tmp_path
):
    from polisyos.foundry.methods.catalog.causal.g_computation import ICEGFormula

    store = FileSystemCAS(tmp_path / "cas")
    seeded = _seed_phase1_gate_store(store)
    dataset_id = seeded["dataset_ids"][0]
    engine = CausalEngine(registry=None, artifact_store=store)

    def _fake_pure_step(state, params):  # pragma: no cover - should never execute
        raise AssertionError("estimator should not run when readiness is blocked")

    monkeypatch.setattr(ICEGFormula, "pure_step", staticmethod(_fake_pure_step))

    with pytest.raises(DataReadinessBlockedError) as exc_info:
        engine.dynamic_causal_effect(
            data=_government_dynamic_data(dataset_id),
            method="ice_g",
        )

    assert (
        "survey_quality_certificate_missing_for_government_dataset"
        in exc_info.value.report.blocking_reasons
    )


def test_dynamic_causal_effect_blocks_failing_government_certificate(monkeypatch, tmp_path):
    from polisyos.foundry.methods.catalog.causal.g_computation import ICEGFormula

    store = FileSystemCAS(tmp_path / "cas")
    seeded = _seed_phase1_gate_store(store)
    dataset_id = seeded["dataset_ids"][0]
    engine = CausalEngine(registry=None, artifact_store=store)

    def _fake_pure_step(state, params):  # pragma: no cover - should never execute
        raise AssertionError("estimator should not run when readiness is blocked")

    monkeypatch.setattr(ICEGFormula, "pure_step", staticmethod(_fake_pure_step))
    failing_certificate = build_survey_quality_certificate(
        target_estimand="E[Y]",
        estimator_id="survey.dr.design_missingness@1.0.0",
        dataset_id=dataset_id,
        data_origin="government",
        regime_requested=SurveyRequestedRegime.MNAR_SHADOW,
        regime_validated=SurveyValidatedRegime.MNAR_UNIDENTIFIED,
        estimate=1.0,
        standard_error=0.1,
        overall_pass=False,
        blocking_reasons=("mnar_shadow_requires_shadow_variables",),
    ).model_dump(mode="json")

    with pytest.raises(DataReadinessBlockedError) as exc_info:
        engine.dynamic_causal_effect(
            data=_government_dynamic_data(
                dataset_id,
                survey_quality_certificate=failing_certificate,
            ),
            method="ice_g",
        )

    assert "survey_quality_failed" in exc_info.value.report.blocking_reasons


def test_dynamic_causal_effect_blocks_when_flagship_coverage_is_incomplete(monkeypatch, tmp_path):
    from polisyos.foundry.methods.catalog.causal.g_computation import ICEGFormula

    all_dataset_ids = tuple(load_phase1_flagship_dataset_ids())
    store = FileSystemCAS(tmp_path / "cas")
    seeded = _seed_phase1_gate_store(store, certified_dataset_ids=all_dataset_ids[:2])
    dataset_id = all_dataset_ids[0]
    engine = CausalEngine(registry=None, artifact_store=store)

    def _fake_pure_step(state, params):  # pragma: no cover - should never execute
        raise AssertionError("estimator should not run when readiness is blocked")

    monkeypatch.setattr(ICEGFormula, "pure_step", staticmethod(_fake_pure_step))

    with pytest.raises(DataReadinessBlockedError) as exc_info:
        engine.dynamic_causal_effect(
            data=_government_dynamic_data(
                dataset_id,
                survey_quality_certificate_ref=seeded["certificate_refs"][dataset_id].model_dump(
                    mode="json"
                ),
            ),
            method="ice_g",
        )

    assert "phase1_flagship_dataset_coverage_incomplete" in exc_info.value.report.blocking_reasons


def test_dynamic_causal_effect_runs_for_government_data_after_phase1_gate(monkeypatch, tmp_path):
    from polisyos.foundry.methods.catalog.causal.g_computation import ICEGFormula
    from polisyos.ir.analytics.dynamic_regime import GComputationResult

    store = FileSystemCAS(tmp_path / "cas")
    seeded = _seed_phase1_gate_store(store)
    dataset_id = seeded["dataset_ids"][0]
    engine = CausalEngine(registry=None, artifact_store=store)

    def _fake_pure_step(state, params):
        return {
            "g_result": GComputationResult(
                counterfactual_mean=1.4,
                confidence_interval=(1.0, 1.8),
                confidence_level=0.95,
                standard_error=0.1,
                regime=str(params.get("regime", "always_treat")),
                n_units=220,
                n_periods=3,
                method="ice_g",
            )
        }

    monkeypatch.setattr(ICEGFormula, "pure_step", staticmethod(_fake_pure_step))

    result = engine.dynamic_causal_effect(
        data=_government_dynamic_data(
            dataset_id,
            survey_quality_certificate_ref=seeded["certificate_refs"][dataset_id].model_dump(
                mode="json"
            ),
        ),
        method="ice_g",
    )

    assert result.method == "ice_g"
    assert result.counterfactual_mean == pytest.approx(1.4)


def test_mediation_analysis_runs_with_verified_readiness(monkeypatch):
    from polisyos.foundry.methods.catalog.causal.mediation import NaturalEffectEstimator

    engine = CausalEngine(registry=None, knowledge_base=None)
    data = _tabular_direct_wrapper_data(treatment_key="X", outcome_key="Y")
    data["M"] = np.asarray([0.1, 0.4, 0.2, 0.6, 0.3, 0.7, 0.5, 0.8], dtype=float)

    def _fake_pure_step(state, params):
        assert params["treatment_variable"] == "X"
        return {
            "mediation_result": {
                "natural_direct_effect": 0.7,
                "natural_indirect_effect": 0.3,
            }
        }

    monkeypatch.setattr(NaturalEffectEstimator, "pure_step", staticmethod(_fake_pure_step))

    result = engine.mediation_analysis(
        data=data,
        treatment="X",
        outcome="Y",
        mediators=["M"],
        method="linear",
    )

    assert result["natural_direct_effect"] == pytest.approx(0.7)
    assert result["natural_indirect_effect"] == pytest.approx(0.3)


def test_interference_effect_runs_with_verified_readiness(monkeypatch):
    from polisyos.foundry.methods.catalog.causal.interference import NetworkAIPWEstimator

    engine = CausalEngine(registry=None, knowledge_base=None)
    data = _tabular_direct_wrapper_data(treatment_key="T", outcome_key="Y")
    data["adjacency_matrix"] = np.eye(len(data["T"]), dtype=float)

    def _fake_pure_step(state, params):
        assert params["treatment_variable"] == "T"
        return {
            "result": {
                "average_direct_effect": 0.8,
                "average_spillover_effect": 0.2,
            }
        }

    monkeypatch.setattr(NetworkAIPWEstimator, "pure_step", staticmethod(_fake_pure_step))

    result = engine.interference_effect(
        data=data,
        treatment="T",
        outcome="Y",
        method="network_aipw",
    )

    assert result["average_direct_effect"] == pytest.approx(0.8)
    assert result["average_spillover_effect"] == pytest.approx(0.2)


def test_fairness_audit_runs_with_verified_readiness(monkeypatch):
    from polisyos.foundry.methods.catalog.causal.fairness import TVFairnessDecomposer

    engine = CausalEngine(registry=None, knowledge_base=None)
    data = _tabular_direct_wrapper_data(treatment_key="A", outcome_key="Y")

    def _fake_pure_step(state, params):
        assert params["protected_variable"] == "A"
        return {
            "fairness_report": {
                "total_disparity": 0.9,
                "explained_share": 0.4,
            }
        }

    monkeypatch.setattr(TVFairnessDecomposer, "pure_step", staticmethod(_fake_pure_step))

    result = engine.fairness_audit(
        data=data,
        protected="A",
        outcome="Y",
        method="tv_decomposition",
    )

    assert result["total_disparity"] == pytest.approx(0.9)
    assert result["explained_share"] == pytest.approx(0.4)
