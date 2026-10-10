from __future__ import annotations

from unittest.mock import patch

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.governance.passes.base import PassContext
from polisyos.core.governance.profiles import ProfileLevel, ValidationProfile
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.analytics.cross_graph import EvidenceStatus, load_cross_graph_evidence_profile
from polisyos.ir.analytics.literature import (
    EnvironmentAuditReport,
    LiteratureCausalPrior,
    persist_literature_causal_prior,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ConstraintSpec, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.governance.passes.cross_graph_evidence_pass import CrossGraphEvidencePass
from polisyos.scientist.governance.preflight import preflight_checks
from polisyos.scientist.methods.discovery.aggregator import EvidenceWeightedAggregator
from polisyos.scientist.methods.discovery.priors import (
    GraphPriorBuilder,
    GraphPriorBundle,
    HypothesisIdentificationEvidence,
    PriorEdge,
    load_graph_prior_bundle,
    persist_graph_prior_bundle,
)
from polisyos.scientist.methods.discovery.schema import (
    ComputeFootprint,
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
    GraphHypothesis,
)
from polisyos.scientist.methods.discovery.stability import (
    BootstrapMode,
    BootstrapStabilityConfig,
    BootstrapStabilityReport,
    HypothesisStabilitySummary,
)
from polisyos.scientist.methods.discovery.utility_judge import (
    DownstreamUtilityJudge,
    UtilityJudgeInput,
)
from polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence import (
    CompileCrossGraphEvidenceNode,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    INPUT_GRAPH_PRIOR_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.state_branching import (
    branch_state as real_branch_state,
)


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem1",
            domain="social",
            hard_constraints=[
                ConstraintSpec(
                    constraint_id="budget_cap",
                    value=1,
                    slot_id="budget",
                )
            ],
        ),
        policy_spec=PolicySpec(policy_id="policy1"),
        model_spec=ModelSpec(
            model_id="model1",
            data_snapshot_ref="sha256:" + ("0" * 64),
        ),
    )


def test_compilation_without_trinity(execution_context, minimal_state):
    """With enabled config but no Trinity bundle, produces a policy_request_only profile."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
            }
        }
    )
    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)
    assert outcome.status == "ok"
    assert ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF in outcome.state.artifacts_index
    summary = outcome.state.params.get("cross_graph_evidence_summary")
    assert summary is not None
    assert outcome.state.params.get("cross_graph_benchmark_summary") is not None


def test_compilation_skips_when_not_expected(execution_context, minimal_state):
    """When config is disabled, compilation is skipped."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": False},
            }
        }
    )
    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert outcome.state.params.get("cross_graph_evidence_expected") is False


def test_compilation_skips_fast_governance(execution_context, minimal_state):
    """FAST governance profile skips cross-graph evidence."""
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
                "governance_profile": "fast",
            }
        }
    )
    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)
    assert outcome.status == "skip"
    assert outcome.state.params.get("cross_graph_evidence_expected") is False


def test_compilation_enriches_profile_from_graph_prior_bundle(
    execution_context, minimal_state, cas_store
):
    graph_prior_bundle = GraphPriorBundle(
        high_confidence_edges=[
            PriorEdge(
                edge_key="X->Y",
                src="X",
                dst="Y",
                presence_confidence=0.8,
                orientation_confidence=0.7,
                provenance_refs=["paper:1"],
                supporting_hypothesis_ids=["identified"],
            )
        ],
        required_edges=[
            PriorEdge(
                edge_key="A->B",
                src="A",
                dst="B",
                presence_confidence=0.9,
                orientation_confidence=0.85,
                provenance_refs=["paper:2"],
                supporting_hypothesis_ids=["identified"],
            )
        ],
        hypothesis_identification={
            "identified": HypothesisIdentificationEvidence(
                identification_status="identified",
                identifiability_score=1.0,
                reasons=["identifiability:identified"],
            )
        },
    )
    bundle_ref = persist_graph_prior_bundle(cas_store, graph_prior_bundle)
    state = minimal_state.model_copy(
        update={
            "inputs": {
                **minimal_state.inputs,
                INPUT_GRAPH_PRIOR_BUNDLE_REF: bundle_ref,
            },
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
            },
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    profile_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    fresh_store = FileSystemCAS(cas_store.root)
    profile = load_cross_graph_evidence_profile(
        _ensure_ir_artifact_store(fresh_store), profile_ref
    )
    assert any(need.need.cause == "A" and need.need.effect == "B" for need in profile.needs)
    assert any(need.need.cause == "X" and need.need.effect == "Y" for need in profile.needs)
    assert all(
        need.evidence_status is EvidenceStatus.INSUFFICIENT
        and need.requires_expert_review
        and "discovery_hypothesis_identification_limited" in need.blocking_reasons
        for need in profile.needs
        if need.need.source_path == "scientist.discovery.graph_prior_bundle"
    )
    assert "graph_prior_bundle_enriched" in profile.notes


def test_pag_identification_limit_survives_discovery_cas_and_strict_gate(
    execution_context,
    minimal_state,
    cas_store,
):
    """A complete discovery producer chain preserves PAG limits through a fresh strict consumer."""
    from dataclasses import replace

    from polisyos.scientist.methods.discovery.output import (
        DiscoveryArtifactBuilder,
        DiscoveryArtifactBuildInput,
        load_discovery_artifact_bundle,
    )
    from polisyos.scientist.methods.discovery.priors import PriorKnowledgeBundle
    from polisyos.scientist.methods.discovery.workers import DiscoveryWorkerBundle

    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )
    hypothesis = GraphHypothesis(
        hypothesis_id="fci_pag_limited",
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
        method=DiscoveryMethod.FCI,
        graph=CausalGraphModel(
            graph_type=GraphType.PAG,
            nodes=["X", "Y"],
            edges=[
                CausalEdge(
                    src="X",
                    dst="Y",
                    mark_src=EdgeMark.CIRCLE,
                    mark_dst=EdgeMark.ARROW,
                    evidence_refs=["fixture:pag-edge"],
                )
            ],
            discovery_method="fci",
        ),
        edge_confidence={"X->Y": 1.0},
        compute_footprint=ComputeFootprint(),
    )
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=5),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id=hypothesis.hypothesis_id,
                edge_selection_frequency={"X->Y": 1.0},
                mean_edge_stability=1.0,
                completed_resamples=5,
            )
        ],
    )
    utility_report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability,
            causal_query=query,
        )
    )
    score = utility_report.scores[0]
    assert score.identification_status == "oracle_needed"
    assert "identifiability:unsupported_static_admg_profile" in score.reasons

    matrix = EvidenceWeightedAggregator().aggregate([hypothesis], stability, utility_report)
    assert matrix.entries[0].supporting_hypothesis_ids == [hypothesis.hypothesis_id]
    assert matrix.entries[0].presence_confidence >= GraphPriorBuilder.REQUIRED_PRESENCE_THRESHOLD
    graph_prior = GraphPriorBuilder().build(matrix, utility_report)
    assert graph_prior.required_edges
    assert graph_prior.required_edges[0].supporting_hypothesis_ids == [hypothesis.hypothesis_id]
    assert any(
        "unsupported_static_admg_profile" in limitation
        for limitation in graph_prior.hypothesis_identification[
            hypothesis.hypothesis_id
        ].limitations
    )

    bundle_ref = DiscoveryArtifactBuilder().build(
        cas_store,
        DiscoveryArtifactBuildInput(
            run_id="run-pag-limited-source-chain",
            task_id="task-pag-limited-source-chain",
            variable_names=["X", "Y"],
            causal_query=query,
            hypotheses=[hypothesis],
            edge_confidence_matrix=matrix,
            bootstrap_stability_report=stability,
            downstream_utility_report=utility_report,
            graph_prior_bundle=graph_prior,
            prior_knowledge_bundle=PriorKnowledgeBundle(),
            worker_bundle=DiscoveryWorkerBundle(),
        ),
    )
    fresh_store = FileSystemCAS(cas_store.root)
    bundle = load_discovery_artifact_bundle(fresh_store, bundle_ref)
    graph_prior_ref = bundle.graph_prior_bundle_ref
    assert graph_prior_ref.manifest_profile_sha256 is not None
    root_manifest = fresh_store.get_manifest(graph_prior_ref)
    expected_root_edges = {
        (
            str(bundle.downstream_utility_report_ref.artifact_id),
            "downstream_utility_report",
            bundle.downstream_utility_report_ref.manifest_profile_sha256,
        ),
        (
            str(bundle.edge_confidence_matrix_ref.artifact_id),
            "edge_confidence_matrix",
            bundle.edge_confidence_matrix_ref.manifest_profile_sha256,
        ),
        (
            str(bundle.bootstrap_stability_report_ref.artifact_id),
            "bootstrap_stability_report",
            bundle.bootstrap_stability_report_ref.manifest_profile_sha256,
        ),
    }
    actual_root_edges = [
        (str(item.artifact_id), item.role, item.manifest_profile_sha256)
        for item in root_manifest.inputs
    ]
    assert len(expected_root_edges) == 3
    assert len(actual_root_edges) == len(expected_root_edges)
    assert len(set(actual_root_edges)) == len(actual_root_edges)
    assert set(actual_root_edges) == expected_root_edges
    assert all(profile is not None for _, _, profile in expected_root_edges)

    utility_ref = bundle.downstream_utility_report_ref
    assert utility_ref.manifest_profile_sha256 is not None
    utility_manifest = fresh_store.get_manifest(utility_ref)
    expected_utility_edges = {
        (
            str(bundle.discovery_task_profile_ref.artifact_id),
            "discovery_task_profile",
            bundle.discovery_task_profile_ref.manifest_profile_sha256,
        ),
        (
            str(bundle.graph_hypothesis_set_ref.artifact_id),
            "graph_hypothesis_set",
            bundle.graph_hypothesis_set_ref.manifest_profile_sha256,
        ),
    }
    actual_utility_edges = [
        (str(item.artifact_id), item.role, item.manifest_profile_sha256)
        for item in utility_manifest.inputs
    ]
    assert len(expected_utility_edges) == 2
    assert len(actual_utility_edges) == len(expected_utility_edges)
    assert len(set(actual_utility_edges)) == len(actual_utility_edges)
    assert set(actual_utility_edges) == expected_utility_edges
    assert all(profile is not None for _, _, profile in expected_utility_edges)

    fresh_graph_prior = load_graph_prior_bundle(fresh_store, graph_prior_ref)
    identification = fresh_graph_prior.hypothesis_identification[hypothesis.hypothesis_id]
    assert identification.identification_status == "oracle_needed"
    assert any(
        "unsupported_static_admg_profile" in limitation
        for limitation in identification.limitations
    )

    state = minimal_state.model_copy(
        update={
            "inputs": {
                **minimal_state.inputs,
                INPUT_GRAPH_PRIOR_BUNDLE_REF: graph_prior_ref,
            },
            "params": {"cross_graph_evidence_config": {"enabled": True}},
        }
    )
    outcome = CompileCrossGraphEvidenceNode().execute(
        replace(execution_context, store=fresh_store),
        state,
    )
    assert outcome.status == "ok"
    profile_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    fresh_profile = load_cross_graph_evidence_profile(
        _ensure_ir_artifact_store(FileSystemCAS(cas_store.root)),
        profile_ref,
    )
    discovery_needs = [
        need
        for need in fresh_profile.needs
        if need.need.source_path.startswith("scientist.discovery.graph_prior_bundle")
    ]
    assert discovery_needs
    assert all(need.evidence_status is EvidenceStatus.INSUFFICIENT for need in discovery_needs)
    assert all(need.requires_expert_review for need in discovery_needs)
    assert all(
        "discovery_hypothesis_identification_limited" in need.blocking_reasons
        for need in discovery_needs
    )
    assert all(
        any(
            diagnostic.code == "cross_graph.discovery_prior.identification_limited"
            and any(
                row["hypothesis_id"] == hypothesis.hypothesis_id
                and row["identification_status"] == "oracle_needed"
                and row["verification_status"] == "recomputed"
                and row["verification_reason"] == "source_projection_matches_current_algorithm"
                and any(
                    "unsupported_static_admg_profile" in limitation
                    for limitation in row["limitations"]
                )
                for row in diagnostic.details["hypothesis_identification"]
            )
            for diagnostic in need.diagnostics
        )
        for need in discovery_needs
    )

    governance_context = PassContext(
        ir=None,
        state={
            "_store": FileSystemCAS(cas_store.root),
            "artifacts_index": {
                ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF: profile_ref,
            },
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_pag_limited",
    )
    issues = CrossGraphEvidencePass().validate(governance_context)
    limitation_issues = [
        issue
        for issue in issues
        if issue.code == "CROSS_GRAPH_DISCOVERY_IDENTIFICATION_LIMITED"
    ]
    assert limitation_issues
    assert all(issue.severity.value == "blocker" for issue in limitation_issues)

    preflight_profile = ValidationProfile(
        level=ProfileLevel.STRICT,
        pass_ids=frozenset({"cross_graph_evidence"}),
    )
    preflight_state, gate_request = preflight_checks(
        {
            "run_id": "R_pag_limited",
            "cross_graph_evidence_profile": fresh_profile.model_dump(mode="json"),
        },
        profile=preflight_profile,
    )
    assert gate_request is not None
    assert any(
        issue["code"] == "CROSS_GRAPH_DISCOVERY_IDENTIFICATION_LIMITED"
        for issue in preflight_state["validation_blockers"]
    )



def test_actual_discovery_producer_source_chain_is_recomputed_by_fresh_consumer(
    execution_context,
    minimal_state,
    cas_store,
):
    """Fresh CAS consumption replays a mixed-direction dominant edge and exact selected bases."""
    from dataclasses import replace

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.scientist import DownstreamUtilityReportRef
    from polisyos.scientist.methods.discovery.aggregator import EvidenceWeightedAggregator
    from polisyos.scientist.methods.discovery.output import (
        DiscoveryArtifactBuilder,
        DiscoveryArtifactBuildInput,
        load_discovery_artifact_bundle,
    )
    from polisyos.scientist.methods.discovery.priors import (
        GraphPriorBuilder,
        PriorKnowledgeBundle,
        load_graph_prior_bundle,
    )
    from polisyos.scientist.methods.discovery.schema import (
        ComputeFootprint,
        DiscoveryAlgorithmFamily,
        DiscoveryMethod,
        GraphHypothesis,
    )
    from polisyos.scientist.methods.discovery.stability import (
        BootstrapMode,
        BootstrapStabilityConfig,
        BootstrapStabilityReport,
        HypothesisStabilitySummary,
    )
    from polisyos.scientist.methods.discovery.utility_judge import (
        DownstreamUtilityJudge,
        UtilityJudgeConfig,
        UtilityJudgeInput,
    )
    from polisyos.scientist.methods.discovery.workers import DiscoveryWorkerBundle
    from polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence import (
        _source_verified_identification_rows,
    )

    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )

    def _hypothesis(hypothesis_id, extra_src, extra_dst, stability_value):
        graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=["X", "Y", "A", "B"],
            edges=[
                CausalEdge(
                    src="X",
                    dst="Y",
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                    evidence_refs=[f"fixture:{hypothesis_id}:query-edge"],
                ),
                CausalEdge(
                    src=extra_src,
                    dst=extra_dst,
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                    evidence_refs=[f"fixture:{hypothesis_id}:skeleton-edge"],
                ),
            ],
            discovery_method="controlled_actual_producer",
        )
        return (
            GraphHypothesis(
                hypothesis_id=hypothesis_id,
                algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
                method=DiscoveryMethod.PC,
                graph=graph,
                resolved_graph=graph.model_copy(deep=True),
                compute_footprint=ComputeFootprint(),
            ),
            HypothesisStabilitySummary(
                hypothesis_id=hypothesis_id,
                edge_selection_frequency={
                    "X->Y": 1.0,
                    f"{extra_src}->{extra_dst}": stability_value,
                },
                adjustment_set_stability=stability_value,
                mean_edge_stability=stability_value,
                completed_resamples=3,
            ),
        )

    dominant, dominant_summary = _hypothesis("actual-dominant-forward", "A", "B", 1.0)
    opposite, opposite_summary = _hypothesis("actual-opposite-sibling", "B", "A", 0.05)
    hypotheses = [dominant, opposite]
    hypothesis_ids = {item.hypothesis_id for item in hypotheses}
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=3),
        summaries=[dominant_summary, opposite_summary],
    )
    utility = DownstreamUtilityJudge(
        config=UtilityJudgeConfig(
            identifiability_weight=0.0,
            stability_weight=1.0,
            transportability_weight=0.0,
            estimation_quality_weight=0.0,
            discovery_consistency_weight=0.0,
        )
    ).evaluate(
        UtilityJudgeInput(
            hypotheses=hypotheses,
            stability_report=stability,
            causal_query=query,
        )
    )
    matrix = EvidenceWeightedAggregator().aggregate(hypotheses, stability, utility)
    dominant_entry = next(entry for entry in matrix.entries if entry.edge_key == "A->B")
    assert set(dominant_entry.supporting_hypothesis_ids) == hypothesis_ids
    assert dominant_entry.presence_confidence >= 0.85
    assert dominant_entry.orientation_confidence >= 0.80
    graph_prior = GraphPriorBuilder().build(matrix, utility)
    dominant_prior = next(edge for edge in graph_prior.required_edges if edge.edge_key == "A->B")
    assert set(dominant_prior.supporting_hypothesis_ids) == hypothesis_ids

    bundle_ref = DiscoveryArtifactBuilder().build(
        cas_store,
        DiscoveryArtifactBuildInput(
            run_id="run-actual-mixed-source",
            task_id="task-actual-mixed-source",
            variable_names=["X", "Y", "A", "B"],
            causal_query=query,
            hypotheses=hypotheses,
            edge_confidence_matrix=matrix,
            bootstrap_stability_report=stability,
            downstream_utility_report=utility,
            graph_prior_bundle=graph_prior,
            prior_knowledge_bundle=PriorKnowledgeBundle(),
            worker_bundle=DiscoveryWorkerBundle(),
        ),
    )
    fresh_store = FileSystemCAS(cas_store.root)
    bundle = load_discovery_artifact_bundle(fresh_store, bundle_ref)
    graph_prior_ref = bundle.graph_prior_bundle_ref
    assert graph_prior_ref.manifest_profile_sha256 is not None
    root_manifest = fresh_store.get_manifest(graph_prior_ref)
    required_input_roles = {
        "downstream_utility_report",
        "edge_confidence_matrix",
        "bootstrap_stability_report",
    }
    assert {item.role for item in root_manifest.inputs} & required_input_roles == required_input_roles
    report_input = next(
        item for item in root_manifest.inputs if item.role == "downstream_utility_report"
    )
    assert report_input.manifest_profile_sha256 is not None
    report_manifest = fresh_store.get_manifest(
        DownstreamUtilityReportRef.model_validate(
            {
                "artifact_id": str(report_input.artifact_id),
                "manifest_profile_sha256": report_input.manifest_profile_sha256,
            }
        )
    )
    assert all(
        item.manifest_profile_sha256 is not None
        for item in report_manifest.inputs
        if item.role in {"discovery_task_profile", "graph_hypothesis_set"}
    )

    fresh_prior = load_graph_prior_bundle(fresh_store, graph_prior_ref)
    fresh_dominant_prior = next(
        edge for edge in fresh_prior.required_edges if edge.edge_key == "A->B"
    )
    assert set(fresh_dominant_prior.supporting_hypothesis_ids) == hypothesis_ids
    rows = _source_verified_identification_rows(fresh_store, graph_prior_ref, fresh_prior)
    assert set(rows) == hypothesis_ids
    assert all(row["verification_status"] == "recomputed" for row in rows.values())
    assert all(row["source_basis"]["same_basis"] is True for row in rows.values())
    assert all(
        "resolved_graph_used_for_identifiability" in row["warnings"]
        for row in rows.values()
    )
    assert all(
        row["source_refs"]["graph_prior_bundle"]["payload_sha256"]
        == root_manifest.integrity.sha256
        for row in rows.values()
    )
    assert all(
        row["source_refs"][name]["manifest_profile_sha256"] is not None
        and len(row["source_refs"][name]["payload_sha256"]) == 64
        for row in rows.values()
        for name in ("edge_confidence_matrix", "bootstrap_stability_report")
    )

    state = minimal_state.model_copy(
        update={
            "inputs": {
                **minimal_state.inputs,
                INPUT_GRAPH_PRIOR_BUNDLE_REF: graph_prior_ref,
            },
            "params": {"cross_graph_evidence_config": {"enabled": True}},
        }
    )
    from polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence import (
        CompileCrossGraphEvidenceNode,
    )

    outcome = CompileCrossGraphEvidenceNode().execute(
        replace(execution_context, store=fresh_store),
        state,
    )
    profile_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    profile = load_cross_graph_evidence_profile(
        _ensure_ir_artifact_store(FileSystemCAS(cas_store.root)),
        profile_ref,
    )
    source_needs = [
        need
        for need in profile.needs
        if need.need.source_path == "scientist.discovery.graph_prior_bundle"
    ]
    assert source_needs
    assert all(need.evidence_status is EvidenceStatus.SUPPORTED for need in source_needs)
    assert all(not need.requires_expert_review for need in source_needs)

def test_compilation_records_degraded_source_statuses_when_sources_missing(
    execution_context,
    minimal_state,
    cas_store,
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {
                    "enabled": True,
                    "academic_db_path": "/tmp/missing-academic.duckdb",
                    "datasets_db_path": "/tmp/missing-datasets.duckdb",
                    "legal_db_path": "/tmp/missing-legal.duckdb",
                },
            }
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    profile_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    profile = load_cross_graph_evidence_profile(_ensure_ir_artifact_store(cas_store), profile_ref)
    assert profile.source_statuses["academic"].status.value == "missing_path"
    assert profile.source_statuses["datasets"].status.value == "missing_path"
    assert profile.source_statuses["legal"].status.value == "missing_path"
    assert profile.source_statuses["benchmark"].status.value == "missing_config"
    assert profile.benchmark_summary["status"] == "degraded"


def test_compilation_writes_backlog_for_unresolved_needs(
    execution_context,
    minimal_state,
    tmp_path,
):
    backlog_path = tmp_path / "cross-graph-backlog.json"
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {
                    "enabled": True,
                    "backlog_output_path": str(backlog_path),
                },
            }
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert backlog_path.exists()


def test_compilation_appends_academic_demand_backlog_when_configured(
    execution_context,
    minimal_state,
    tmp_path,
):
    backlog_path = tmp_path / "cross-graph-backlog.json"
    academic_backlog_path = tmp_path / "academic-demand-backlog.jsonl"
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {
                    "enabled": True,
                    "backlog_output_path": str(backlog_path),
                    "academic_demand_backlog_path": str(academic_backlog_path),
                },
            }
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert backlog_path.exists()
    assert academic_backlog_path.exists()


def test_compilation_persists_degraded_profile_for_invalid_config(
    execution_context,
    minimal_state,
    cas_store,
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {
                    "enabled": True,
                    "unknown_field": "boom",
                },
            }
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    profile_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    profile = load_cross_graph_evidence_profile(_ensure_ir_artifact_store(cas_store), profile_ref)
    assert profile.summary.status == "degraded"
    assert profile.diagnostics[0].code == "cross_graph.invalid_config"
    assert profile.benchmark_summary["reason"] == "invalid_config"


def test_compilation_passes_literature_prior_context_into_compiler(
    execution_context,
    minimal_state,
    cas_store,
    monkeypatch,
):
    trinity_ref = cas_store.put_json(
        _bundle(),
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="ir.trinity_bundle", version="1.0"),
        ),
    )
    prior_ref = persist_literature_causal_prior(
        _ensure_ir_artifact_store(cas_store),
        LiteratureCausalPrior(
            environment_audit=EnvironmentAuditReport(
                status="warning",
                n_environments=2,
                ks_passed=False,
                ks_rejected_variables=[0],
            ),
            metadata={"build_status": "ok"},
        ),
    )
    captured: dict[str, object] = {}

    def _fake_compile(self, bundle, **kwargs):
        del self, bundle
        captured.update(kwargs)
        from polisyos.ir.analytics.cross_graph import (
            CrossGraphEvidenceProfile,
            CrossGraphEvidenceSummary,
        )

        return CrossGraphEvidenceProfile(
            summary=CrossGraphEvidenceSummary(status="ok", total_needs=0),
            notes=["compiled"],
        )

    monkeypatch.setattr(
        "polisyos.scientist.cross_graph.compiler.CrossGraphEvidenceCompiler.compile",
        _fake_compile,
    )

    state = minimal_state.model_copy(
        update={
            "inputs": {
                **minimal_state.inputs,
                INPUT_TRINITY_BUNDLE_REF: trinity_ref,
            },
            "artifacts_index": {
                **minimal_state.artifacts_index,
                ARTIFACT_LITERATURE_PRIOR_REF: prior_ref,
            },
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
            },
        }
    )

    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert captured["literature_prior"] is not None
    assert captured["literature_prior_ref"] == str(prior_ref.artifact_id)


def test_compilation_target_context_assertion_not_swallowed(
    execution_context, minimal_state, monkeypatch: pytest.MonkeyPatch
):
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
                "target_context": {"country": "US", "year": 2025},
            }
        }
    )

    def _boom(*args, **kwargs):
        del args, kwargs
        raise AssertionError("target-context-broken")

    monkeypatch.setattr(
        "polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence.ContextProfile.model_validate",
        _boom,
    )

    with pytest.raises(AssertionError, match="target-context-broken"):
        CompileCrossGraphEvidenceNode().execute(execution_context, state)


def test_compilation_uses_branch_state_for_declared_outputs(execution_context, minimal_state):
    state = minimal_state.model_copy(
        update={
            "params": {
                "cross_graph_evidence_config": {"enabled": True},
            }
        }
    )
    state.params["nested"] = {"baseline": True}
    observed: dict[str, tuple[str, ...]] = {}

    def _spy_branch(base_state, *, write_paths=()):
        observed["write_paths"] = tuple(write_paths)
        return real_branch_state(base_state, write_paths=write_paths)

    with patch(
        "polisyos.scientist.nodes.builtins.planning.compile_cross_graph_evidence.branch_state",
        _spy_branch,
    ):
        outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)

    assert outcome.status == "ok"
    assert observed["write_paths"] == (
        "artifacts_index.cross_graph_evidence_profile_ref",
        "params.cross_graph_evidence_expected",
        "params.cross_graph_evidence_summary",
        "params.cross_graph_benchmark_summary",
    )
    assert state.params["nested"] == {"baseline": True}
    assert ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF not in state.artifacts_index
    assert outcome.state.params["cross_graph_evidence_expected"] is True
    assert ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF in outcome.state.artifacts_index

@pytest.mark.parametrize(
    (
        "graph_type",
        "resolved_to_dag",
        "same_status_different_basis",
        "forge_report",
        "link_report",
        "profileless_root",
        "wrong_root_schema",
        "wrong_root_schema_version_only",
        "forge_aggregated_matrix",
        "forge_edge_coordinates_only",
        "forge_edge_lag_only",
        "expected_status",
        "verification",
        "verification_reason",
    ),
    [
        (GraphType.DAG, False, False, False, True, False, False, False, False, False, False, EvidenceStatus.SUPPORTED, "recomputed", "source_projection_matches_current_algorithm"),
        (GraphType.PAG, False, False, False, True, False, False, False, False, False, False, EvidenceStatus.INSUFFICIENT, "recomputed", "source_projection_matches_current_algorithm"),
        (GraphType.PAG, False, False, True, True, False, False, False, False, False, False, EvidenceStatus.INSUFFICIENT, "not_established", "utility_report_source_projection_mismatch"),
        (GraphType.DAG, False, False, False, False, False, False, False, False, False, False, EvidenceStatus.INSUFFICIENT, "not_established", "downstream_utility_report_input_missing_or_ambiguous"),
        (GraphType.PAG, True, False, False, True, False, False, False, False, False, False, EvidenceStatus.INSUFFICIENT, "not_established", "aggregation_report_graph_basis_mismatch"),
        (GraphType.DAG, False, True, False, True, False, False, False, False, False, False, EvidenceStatus.INSUFFICIENT, "not_established", "aggregation_report_graph_basis_mismatch"),
        (GraphType.DAG, False, False, False, True, True, False, False, False, False, False, EvidenceStatus.INSUFFICIENT, "not_established", "graph_prior_manifest_profile_missing"),
        (GraphType.DAG, False, False, False, True, False, True, False, False, False, False, EvidenceStatus.INSUFFICIENT, "not_established", "source_artifact_schema_mismatch"),
        (GraphType.DAG, False, False, False, True, False, False, True, False, False, False, EvidenceStatus.INSUFFICIENT, "not_established", "source_artifact_schema_mismatch"),
        (GraphType.DAG, False, False, False, True, False, False, False, True, False, False, EvidenceStatus.INSUFFICIENT, "not_established", "edge_confidence_matrix_source_projection_mismatch"),
        (GraphType.DAG, False, False, False, True, False, False, False, False, True, False, EvidenceStatus.INSUFFICIENT, "not_established", "graph_prior_source_projection_mismatch"),
        (GraphType.DAG, False, False, False, True, False, False, False, False, False, True, EvidenceStatus.INSUFFICIENT, "not_established", "graph_prior_source_projection_mismatch"),
    ],
)
def test_identification_source_is_recomputed_before_prior_support(
    execution_context,
    minimal_state,
    cas_store,
    graph_type,
    resolved_to_dag,
    same_status_different_basis,
    forge_report,
    link_report,
    profileless_root,
    wrong_root_schema,
    wrong_root_schema_version_only,
    forge_aggregated_matrix,
    forge_edge_coordinates_only,
    forge_edge_lag_only,
    expected_status,
    verification,
    verification_reason,
):
    """The complete persisted aggregation must replay from selected producer sources."""
    from polisyos.core.artifacts.manifest import input_ref_from_artifact_ref
    from polisyos.core.canon import CanonSpec
    from polisyos.core.contracts.scientist import GraphPriorBundleRef
    from polisyos.scientist.methods.discovery.aggregator import (
        EvidenceWeightedAggregator,
        persist_edge_confidence_matrix,
    )
    from polisyos.scientist.methods.discovery.artifact_refs import profile_bound_written_ref
    from polisyos.scientist.methods.discovery.output import (
        DiscoveryTaskProfile,
        GraphHypothesisSet,
        persist_discovery_task_profile,
        persist_graph_hypothesis_set,
    )
    from polisyos.scientist.methods.discovery.priors import (
        GRAPH_PRIOR_BUNDLE_SCHEMA_NAME,
        GraphPriorBuilder,
        persist_graph_prior_bundle,
    )
    from polisyos.scientist.methods.discovery.schema import persist_graph_hypothesis
    from polisyos.scientist.methods.discovery.stability import persist_bootstrap_stability_report
    from polisyos.scientist.methods.discovery.utility_judge import (
        identify_hypothesis_identification_status,
        persist_downstream_utility_report,
    )

    hypothesis_id = f"source-bound-{graph_type.value}"
    query = CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )
    resolved_graph = None
    if resolved_to_dag or same_status_different_basis:
        resolved_nodes = ["X", "Y"]
        resolved_edges = [
            CausalEdge(
                src="X",
                dst="Y",
                mark_src=EdgeMark.TAIL,
                mark_dst=EdgeMark.ARROW,
                evidence_refs=["fixture:resolved-edge"],
            )
        ]
        if same_status_different_basis:
            resolved_nodes.extend(["A", "B"])
            resolved_edges.append(
                CausalEdge(
                    src="A",
                    dst="B",
                    mark_src=EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                    evidence_refs=["fixture:unrelated-resolved-edge"],
                )
            )
        resolved_graph = CausalGraphModel(
            graph_type=GraphType.DAG,
            nodes=resolved_nodes,
            edges=resolved_edges,
            discovery_method="controlled_resolved_dag_fixture",
        )
    source_hypothesis = GraphHypothesis(
        hypothesis_id=hypothesis_id,
        algorithm_family=DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
        method=DiscoveryMethod.FCI if graph_type is GraphType.PAG else DiscoveryMethod.PC,
        graph=CausalGraphModel(
            graph_type=graph_type,
            nodes=["X", "Y"],
            edges=[
                CausalEdge(
                    src="X",
                    dst="Y",
                    mark_src=EdgeMark.CIRCLE if graph_type is GraphType.PAG else EdgeMark.TAIL,
                    mark_dst=EdgeMark.ARROW,
                    evidence_refs=["fixture:source-bound-edge"],
                )
            ],
            discovery_method="controlled_source_fixture",
        ),
        resolved_graph=resolved_graph,
        compute_footprint=ComputeFootprint(),
    )
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=3),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id=hypothesis_id,
                edge_selection_frequency={"X->Y": 1.0},
                mean_edge_stability=1.0,
                completed_resamples=3,
            )
        ],
    )
    report = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[source_hypothesis],
            stability_report=stability,
            causal_query=query,
        )
    )
    if same_status_different_basis:
        report_projection = identify_hypothesis_identification_status(source_hypothesis, query)
        raw_projection = identify_hypothesis_identification_status(
            source_hypothesis.model_copy(update={"resolved_graph": None}), query
        )
        assert report_projection.identification_status == raw_projection.identification_status
        assert report_projection.identifiability_score == raw_projection.identifiability_score
    source_score = report.scores[0]
    if forge_report:
        assert graph_type is GraphType.PAG
        assert source_score.identification_status == "oracle_needed"
        source_score = source_score.model_copy(
            update={
                "identification_status": "identified",
                "identifiability_score": 1.0,
                "reasons": ["identifiability:identified"],
                "warnings": [],
                "blocking_certificates": [],
            }
        )
        report = report.model_copy(update={"scores": [source_score]})

    task_id = f"task-{hypothesis_id}"
    run_id = f"run-{hypothesis_id}"
    task_profile_ref = persist_discovery_task_profile(
        cas_store,
        DiscoveryTaskProfile(
            task_id=task_id,
            run_id=run_id,
            variable_names=["X", "Y"],
            causal_query=query,
        ),
    )
    hypothesis_ref = persist_graph_hypothesis(cas_store, source_hypothesis)
    hypothesis_set_ref = persist_graph_hypothesis_set(
        cas_store,
        GraphHypothesisSet(
            graph_hypothesis_refs=[hypothesis_ref],
            ranking_order=[hypothesis_id],
            metadata={"run_id": run_id, "task_id": task_id},
        ),
        inputs=[input_ref_from_artifact_ref(task_profile_ref, role="discovery_task_profile")],
    )
    matrix = EvidenceWeightedAggregator().aggregate([source_hypothesis], stability, report)
    if forge_aggregated_matrix:
        matrix = matrix.model_copy(update={"hypothesis_weights": {hypothesis_id: 0.5}})
    matrix_ref = persist_edge_confidence_matrix(cas_store, matrix)
    stability_ref = persist_bootstrap_stability_report(cas_store, stability)
    utility_report_ref = persist_downstream_utility_report(
        cas_store,
        report,
        inputs=[
            input_ref_from_artifact_ref(task_profile_ref, role="discovery_task_profile"),
            input_ref_from_artifact_ref(hypothesis_set_ref, role="graph_hypothesis_set"),
        ],
    )
    graph_prior = GraphPriorBuilder().build(matrix, report)
    if forge_edge_coordinates_only or forge_edge_lag_only:
        updates = {"src": "A"} if forge_edge_coordinates_only else {"lag": 1}
        graph_prior = graph_prior.model_copy(
            update={
                field_name: [
                    edge.model_copy(update=updates)
                    for edge in getattr(graph_prior, field_name)
                ]
                for field_name in ("high_confidence_edges", "required_edges")
            }
        )

    root_inputs = [
        input_ref_from_artifact_ref(matrix_ref, role="edge_confidence_matrix"),
        input_ref_from_artifact_ref(stability_ref, role="bootstrap_stability_report"),
    ]
    if link_report:
        root_inputs.append(
            input_ref_from_artifact_ref(utility_report_ref, role="downstream_utility_report")
        )
    else:
        root_inputs.append(
            input_ref_from_artifact_ref(task_profile_ref, role="unrelated_task_profile")
        )
    if wrong_root_schema or wrong_root_schema_version_only:
        schema_name = (
            "test.invalid.GraphPriorBundle"
            if wrong_root_schema
            else GRAPH_PRIOR_BUNDLE_SCHEMA_NAME
        )
        raw_ref = cas_store.put_json(
            graph_prior.model_copy(
                update={"metadata": {**graph_prior.metadata, "wrong_schema_probe": True}}
            ),
            PutOptions(
                kind="scientist.graph_prior_bundle",
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version="1.0"),
                inputs=root_inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        graph_prior_ref = profile_bound_written_ref(
            cas_store,
            GraphPriorBundleRef.model_validate(raw_ref.model_dump(mode="json")),
        )
    else:
        graph_prior_ref = persist_graph_prior_bundle(cas_store, graph_prior, inputs=root_inputs)
    if profileless_root:
        graph_prior_ref = graph_prior_ref.model_copy(update={"manifest_profile_sha256": None})
    state = minimal_state.model_copy(
        update={
            "inputs": {
                **minimal_state.inputs,
                INPUT_GRAPH_PRIOR_BUNDLE_REF: graph_prior_ref,
            },
            "params": {"cross_graph_evidence_config": {"enabled": True}},
        }
    )
    outcome = CompileCrossGraphEvidenceNode().execute(execution_context, state)
    profile_ref = outcome.state.artifacts_index[ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF]
    profile = load_cross_graph_evidence_profile(
        _ensure_ir_artifact_store(cas_store),
        profile_ref,
    )
    needs = [
        need
        for need in profile.needs
        if need.need.source_path == "scientist.discovery.graph_prior_bundle"
    ]
    assert needs
    assert all(need.evidence_status is expected_status for need in needs)
    assert all(
        need.requires_expert_review is (expected_status is EvidenceStatus.INSUFFICIENT)
        for need in needs
    )
    diagnostics = [
        diagnostic
        for need in needs
        for diagnostic in need.diagnostics
        if diagnostic.code == "cross_graph.discovery_prior.identification_limited"
    ]
    if expected_status is EvidenceStatus.INSUFFICIENT:
        assert diagnostics
        row = diagnostics[0].details["hypothesis_identification"][0]
        assert row["verification_status"] == verification
        assert row["verification_reason"] == verification_reason
        if forge_report:
            assert row["identification_status"] == "identified"
        if resolved_to_dag:
            assert row["reported_identification_status"] == "identified"
            assert row["identification_status"] == "identified"
            assert row["source_basis"]["same_basis"] is False
        if same_status_different_basis:
            assert row["reported_identification_status"] == row["identification_status"]
            assert row["source_basis"]["same_basis"] is False
        if profileless_root:
            assert row["source_refs"]["graph_prior_bundle"]["manifest_profile_sha256"] is None
    else:
        assert not diagnostics
