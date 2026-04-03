from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    ConstraintEvaluationResult,
    DataCharacteristics,
    DataType,
    DimensionRegime,
    LatentAssumptionCard,
    LatentDiscoveryBundle,
    LatentTrustLevel,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.scientist.discovery.aggregator import EvidenceWeightedAggregator
from polisyos.scientist.discovery.output import (
    DiscoveryArtifactBuildInput,
    DiscoveryArtifactBuilder,
    SeedVariationStatus,
    load_active_disambiguation_plan,
    load_discovery_artifact_bundle,
    load_discovery_audit_bundle,
    load_discovery_task_profile,
    load_graph_hypotheses_for_bundle,
    load_graph_hypothesis_set,
    load_merged_latent_discovery_bundle,
    load_refutation_report,
    load_reproducibility_report,
    load_source_discovery_reports_for_bundle,
)
from polisyos.scientist.discovery.portfolio import PortfolioCandidate, PortfolioRunResult
from polisyos.scientist.discovery.prior_miner import PriorMiner, PriorMinerConfig
from polisyos.scientist.discovery.priors import GraphPriorBuilder
from polisyos.scientist.discovery.priors import PriorKnowledgeBundle
from polisyos.scientist.discovery.schema import (
    ComputeFootprint,
    DiscoveryAlgorithmFamily,
    DiscoveryMethod,
    GraphHypothesis,
    graph_hypothesis_from_report,
)
from polisyos.scientist.discovery.stability import (
    BootstrapMode,
    BootstrapStabilityConfig,
    BootstrapStabilityReport,
    HypothesisStabilitySummary,
)
from polisyos.scientist.search import (
    ActionableSideInformation,
    persist_actionable_side_information,
)
from polisyos.scientist.discovery.utility_judge import (
    DownstreamUtilityJudge,
    UtilityJudgeInput,
)


def _query() -> CausalQuery:
    return CausalQuery(
        query_type=QueryType.INTERVENTIONAL,
        treatment_variable="X",
        treatment_value=1.0,
        outcome_variable="Y",
    )


def _graph(edge_specs: list[tuple[str, str]]) -> CausalGraphModel:
    nodes = sorted({node for src, dst in edge_specs for node in (src, dst)} | {"Z"})
    return CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=sorted(nodes),
        edges=[
            CausalEdge(src=src, dst=dst, combined_confidence=0.9, evidence_refs=[f"prov:{src}->{dst}"])
            for src, dst in edge_specs
        ],
        discovery_method="unit",
    )


def _hypothesis(
    hypothesis_id: str,
    family: DiscoveryAlgorithmFamily,
    method: DiscoveryMethod,
    edges: list[tuple[str, str]],
) -> GraphHypothesis:
    return GraphHypothesis(
        hypothesis_id=hypothesis_id,
        algorithm_family=family,
        method=method,
        graph=_graph(edges),
        edge_confidence={f"{src}->{dst}": 0.9 for src, dst in edges},
        compute_footprint=ComputeFootprint(method_params={"alpha": 0.1, "__seed__": 7}),
    )


def test_discovery_artifact_builder_creates_full_bundle_with_typed_placeholders(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "mock.duckdb"
    db_path.write_text("", encoding="utf-8")
    index_dir = tmp_path / "index"
    index_dir.mkdir()

    class FakeQuery:
        def __init__(self, db_path: str, index_dir: str) -> None:
            self.db_path = db_path
            self.index_dir = index_dir

        def query_prior_for_variables(self, variables, **kwargs):
            del variables, kwargs
            return [
                {
                    "src": "X",
                    "dst": "Y",
                    "direction": "positive",
                    "confidence": 0.8,
                    "n_articles": 4,
                    "article_refs": ["oa:1"],
                    "candidate_layer": "hybrid",
                    "quality_signals": {"layers": ["exact"]},
                    "evidence_strength": "meta_analysis",
                }
            ]

        def latest_skg_version_id(self):
            return 9

        def skg_snapshot_ref(self, *, version_id=None):
            return f"duckdb:///tmp/mock.duckdb#v{version_id}"

        def close(self):
            return None

    monkeypatch.setattr("polisyos.scientist.discovery.prior_miner.SKGQuery", FakeQuery)

    hypotheses = [
        _hypothesis(
            "pc_main",
            DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
            DiscoveryMethod.PC,
            [("X", "Y")],
        ),
        _hypothesis(
            "dagma_alt",
            DiscoveryAlgorithmFamily.SCORE_BASED,
            DiscoveryMethod.DAGMA,
            [("Y", "X")],
        ),
    ]
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=5),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id="pc_main",
                edge_selection_frequency={"X->Y": 0.9},
                mean_edge_stability=0.9,
                adjustment_set_stability=0.8,
                completed_resamples=5,
            ),
            HypothesisStabilitySummary(
                hypothesis_id="dagma_alt",
                edge_selection_frequency={"Y->X": 0.8},
                mean_edge_stability=0.8,
                adjustment_set_stability=0.6,
                completed_resamples=5,
            ),
        ],
    )
    utility = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=hypotheses,
            stability_report=stability,
            causal_query=_query(),
        )
    )
    matrix = EvidenceWeightedAggregator().aggregate(hypotheses, stability, utility)
    graph_prior_bundle = GraphPriorBuilder().build(matrix, utility)
    prior_knowledge_bundle = PriorMiner(
        config=PriorMinerConfig(
            academic_db_path=str(db_path),
            academic_index_dir=str(index_dir),
        )
    ).mine(graph_prior_bundle)

    store = FileSystemCAS(tmp_path)
    side_info_ref = persist_actionable_side_information(
        store,
        ActionableSideInformation(candidate_id="discovery_task"),
    )
    bundle_ref = DiscoveryArtifactBuilder().build(
        store,
        DiscoveryArtifactBuildInput(
            run_id="R_discovery",
            task_id="task_discovery",
            variable_names=["X", "Y", "Z"],
            causal_query=_query(),
            data_characteristics=DataCharacteristics(
                data_type=DataType.CROSS_SECTIONAL,
                n_samples=100,
                n_variables=3,
                dimension_regime=DimensionRegime.LOW_DIM,
                estimated_density=0.5,
                has_mixed_types=False,
                suspected_latent_confounders=False,
            ),
            hypotheses=hypotheses,
            edge_confidence_matrix=matrix,
            bootstrap_stability_report=stability,
            downstream_utility_report=utility,
            graph_prior_bundle=graph_prior_bundle,
            prior_knowledge_bundle=prior_knowledge_bundle,
            source_refs={
                "input_dataset": ArtifactRef(
                    artifact_id="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    kind="test.dataset",
                    media_type="application/json",
                )
            },
            audit_refs=[side_info_ref],
            actionable_side_information_refs=[side_info_ref],
        ),
    )

    bundle = load_discovery_artifact_bundle(store, bundle_ref)
    task_profile = load_discovery_task_profile(store, bundle.discovery_task_profile_ref)
    hypothesis_set = load_graph_hypothesis_set(store, bundle.graph_hypothesis_set_ref)
    refutation = load_refutation_report(store, bundle.refutation_report_ref)
    reproducibility = load_reproducibility_report(store, bundle.reproducibility_report_ref)
    disambiguation = load_active_disambiguation_plan(store, bundle.active_disambiguation_plan_ref)
    audit = load_discovery_audit_bundle(store, bundle.discovery_audit_bundle_ref)

    assert bundle.prior_knowledge_bundle_ref is not None
    assert bundle.graph_prior_bundle_ref is not None
    assert task_profile.run_id == "R_discovery"
    assert len(hypothesis_set.graph_hypothesis_refs) == 2
    assert hypothesis_set.ranking_order == [score.hypothesis_id for score in utility.scores]
    assert refutation.status == "ready"
    assert refutation.skeptic_findings
    assert refutation.data_profile.diagnostics
    assert refutation.worker_provenance
    assert refutation.targeted_edge_keys
    assert reproducibility.status == "complete"
    assert reproducibility.seed_variation_status == "estimated"
    assert reproducibility.seed_variation_score is not None
    assert disambiguation.status == "ready"
    assert disambiguation.actions
    assert disambiguation.metadata["target_context"]["worker_findings"]["targeted_edge_keys"]
    assert str(audit.source_refs["input_dataset"].artifact_id) == (
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    assert "edge_confidence_matrix_ref" in audit.output_refs
    assert "graph_prior_bundle_ref" in audit.output_refs
    assert audit.metadata["worker_bundle"]["skeptic_findings"]
    assert audit.metadata["artifact_bundle_ref_omitted_due_to_parent_cycle"] is True
    assert [ref.artifact_id for ref in bundle.actionable_side_information_refs] == [
        side_info_ref.artifact_id
    ]
    assert [ref.artifact_id for ref in audit.actionable_side_information_refs] == [
        side_info_ref.artifact_id
    ]


def test_discovery_artifact_builder_marks_measured_seed_reproducibility_when_replay_scores_present(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "mock.duckdb"
    db_path.write_text("", encoding="utf-8")
    index_dir = tmp_path / "index"
    index_dir.mkdir()

    class FakeQuery:
        def __init__(self, db_path: str, index_dir: str) -> None:
            self.db_path = db_path
            self.index_dir = index_dir

        def query_prior_for_variables(self, variables, **kwargs):
            del variables, kwargs
            return []

        def latest_skg_version_id(self):
            return 11

        def skg_snapshot_ref(self, *, version_id=None):
            return f"duckdb:///tmp/mock.duckdb#v{version_id}"

        def close(self):
            return None

    monkeypatch.setattr("polisyos.scientist.discovery.prior_miner.SKGQuery", FakeQuery)

    hypotheses = [
        _hypothesis(
            "pc_main",
            DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
            DiscoveryMethod.PC,
            [("X", "Y")],
        ),
        _hypothesis(
            "dagma_alt",
            DiscoveryAlgorithmFamily.SCORE_BASED,
            DiscoveryMethod.DAGMA,
            [("Y", "X")],
        ),
    ]
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=5),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id="pc_main",
                edge_selection_frequency={"X->Y": 0.9},
                mean_edge_stability=0.9,
                adjustment_set_stability=0.8,
                completed_resamples=5,
            ),
            HypothesisStabilitySummary(
                hypothesis_id="dagma_alt",
                edge_selection_frequency={"Y->X": 0.8},
                mean_edge_stability=0.8,
                adjustment_set_stability=0.6,
                completed_resamples=5,
            ),
        ],
    )
    utility = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=hypotheses,
            stability_report=stability,
            causal_query=_query(),
        )
    )
    matrix = EvidenceWeightedAggregator().aggregate(hypotheses, stability, utility)
    graph_prior_bundle = GraphPriorBuilder().build(matrix, utility)
    prior_knowledge_bundle = PriorMiner(
        config=PriorMinerConfig(
            academic_db_path=str(db_path),
            academic_index_dir=str(index_dir),
        )
    ).mine(graph_prior_bundle)
    store = FileSystemCAS(tmp_path)

    bundle_ref = DiscoveryArtifactBuilder().build(
        store,
        DiscoveryArtifactBuildInput(
            run_id="R_discovery_measured",
            task_id="task_discovery_measured",
            variable_names=["X", "Y", "Z"],
            causal_query=_query(),
            hypotheses=hypotheses,
            edge_confidence_matrix=matrix,
            bootstrap_stability_report=stability,
            downstream_utility_report=utility,
            graph_prior_bundle=graph_prior_bundle,
            prior_knowledge_bundle=prior_knowledge_bundle,
            seed_replay_scores={"pc_main": 0.94, "dagma_alt": 0.87},
            metadata={"strict_mode": True},
        ),
    )

    bundle = load_discovery_artifact_bundle(store, bundle_ref)
    reproducibility = load_reproducibility_report(store, bundle.reproducibility_report_ref)

    assert reproducibility.seed_variation_status is SeedVariationStatus.MEASURED
    assert reproducibility.seed_variation_score == 0.905
    assert any("measured" in note for note in reproducibility.notes)


def test_discovery_artifact_builder_persists_source_reports_and_merges_latent_bundle(
    tmp_path,
) -> None:
    report_main = CausalDiscoveryReport(
        method="pc",
        graph=_graph([("X", "Y")]),
        algebraic_constraints=AlgebraicConstraintReport(
            severity="warning",
            violated_constraints_preview=[
                ConstraintEvaluationResult(
                    constraint_id="ci:X_Y",
                    family=AlgebraicConstraintFamily.CI,
                    status="violated",
                    severity="blocker",
                )
            ],
        ),
        latent_discovery=LatentDiscoveryBundle(
            proposed_latent_nodes=["U_income"],
            inducing_environments=["region"],
            identification_conditions=["proxy_quality"],
            falsification_tests=["negative_control_outcome"],
            trust_level=LatentTrustLevel.RESEARCH,
            assumption_cards=[
                LatentAssumptionCard(
                    assumption_id="latent_card",
                    title="Latent confounding remains research-only",
                    description="Observed proxies may still mask latent confounding.",
                )
            ],
            no_promotion_reasons=["latent_discovery_proof_only"],
        ),
        metadata={"algebraic_constraint_severity": "warning"},
    )
    report_alt = CausalDiscoveryReport(
        method="dagma",
        graph=_graph([("Y", "X")]),
        algebraic_constraints=AlgebraicConstraintReport(severity="info"),
        metadata={"algebraic_constraint_severity": "info"},
    )
    hypotheses = [
        graph_hypothesis_from_report(report_main, hypothesis_id="pc_main"),
        graph_hypothesis_from_report(report_alt, hypothesis_id="dagma_alt"),
    ]
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=3),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id="pc_main",
                edge_selection_frequency={"X->Y": 0.9},
                mean_edge_stability=0.9,
                adjustment_set_stability=0.8,
                completed_resamples=3,
            ),
            HypothesisStabilitySummary(
                hypothesis_id="dagma_alt",
                edge_selection_frequency={"Y->X": 0.7},
                mean_edge_stability=0.7,
                adjustment_set_stability=0.6,
                completed_resamples=3,
            ),
        ],
    )
    utility = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=hypotheses,
            stability_report=stability,
            causal_query=_query(),
        )
    )
    matrix = EvidenceWeightedAggregator().aggregate(hypotheses, stability, utility)
    store = FileSystemCAS(tmp_path)

    bundle_ref = DiscoveryArtifactBuilder().build(
        store,
        DiscoveryArtifactBuildInput(
            run_id="R_discovery_latent",
            task_id="task_discovery_latent",
            variable_names=["X", "Y", "Z"],
            causal_query=_query(),
            hypotheses=hypotheses,
            portfolio_result=PortfolioRunResult(
                candidates=[
                    PortfolioCandidate(
                        hypothesis=hypotheses[0],
                        source_report=report_main,
                        method_params={"significance_level": 0.05},
                    ),
                    PortfolioCandidate(
                        hypothesis=hypotheses[1],
                        source_report=report_alt,
                        method_params={"significance_level": 0.05},
                    ),
                ]
            ),
            edge_confidence_matrix=matrix,
            bootstrap_stability_report=stability,
            downstream_utility_report=utility,
            graph_prior_bundle=GraphPriorBuilder().build(matrix, utility),
            prior_knowledge_bundle=PriorKnowledgeBundle(),
        ),
    )

    bundle = load_discovery_artifact_bundle(store, bundle_ref)
    audit = load_discovery_audit_bundle(store, bundle.discovery_audit_bundle_ref)
    loaded_hypotheses = load_graph_hypotheses_for_bundle(store, bundle)
    source_reports = load_source_discovery_reports_for_bundle(store, bundle)
    merged_latent = load_merged_latent_discovery_bundle(store, bundle)

    assert set(audit.discovery_report_refs_by_hypothesis) == {"pc_main", "dagma_alt"}
    assert all(
        hypothesis.source_discovery_report_ref is not None for hypothesis in loaded_hypotheses
    )
    assert source_reports["pc_main"].algebraic_constraints is not None
    assert (
        source_reports["pc_main"].algebraic_constraints.violated_constraints_preview[0].constraint_id
        == "ci:X_Y"
    )
    assert merged_latent is not None
    assert merged_latent.readiness_cap == "proof_only"
    assert merged_latent.promotion_allowed is False
    assert merged_latent.metadata["source_hypothesis_ids"] == ["pc_main"]
