from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal_discovery import (
    LATENT_CARDINALITY_EVIDENCE_KEY,
    AlgebraicConstraintFamily,
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    ConstraintEvaluationResult,
    DataCharacteristics,
    DataType,
    DimensionRegime,
    LatentAssumptionCard,
    LatentBlockEvidence,
    LatentBlockProposal,
    LatentBlockStatus,
    LatentCardinalityEvidencePayload,
    LatentCardinalityIdentificationSpec,
    LatentCausalRole,
    LatentDiscoveryBundle,
    LatentGraphStatus,
    LatentIdentifiabilityStatus,
    LatentPromotionEvidence,
    LatentTrustLevel,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
from polisyos.ir.analytics.causal_queries import CausalQuery, QueryType
from polisyos.ir.refs import ArtifactRefModel
from polisyos.scientist.discovery.aggregator import EvidenceWeightedAggregator
from polisyos.scientist.discovery.output import (
    DiscoveryArtifactBuilder,
    DiscoveryArtifactBuildInput,
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
    merge_latent_discovery_hypotheses,
)
from polisyos.scientist.discovery.portfolio import PortfolioCandidate, PortfolioRunResult
from polisyos.scientist.discovery.prior_miner import PriorMiner, PriorMinerConfig
from polisyos.scientist.discovery.priors import GraphPriorBuilder, PriorKnowledgeBundle
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
from polisyos.scientist.discovery.utility_judge import (
    DownstreamUtilityJudge,
    UtilityJudgeInput,
)
from polisyos.scientist.search import (
    ActionableSideInformation,
    persist_actionable_side_information,
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
            CausalEdge(
                src=src,
                dst=dst,
                combined_confidence=0.9,
                evidence_refs=[f"prov:{src}->{dst}"],
            )
            for src, dst in edge_specs
        ],
        discovery_method="unit",
    )


def _promotion_ref(ch: str, *, kind: str) -> ArtifactRefModel:
    seed = ch.lower()
    if seed not in "0123456789abcdef":
        seed = format(sum(ord(symbol) for symbol in seed) % 16, "x")
    return ArtifactRefModel(
        artifact_id=f"sha256:{seed * 64}",
        kind=kind,
        media_type="application/json",
    )


def _conditional_promotion_evidence() -> LatentPromotionEvidence:
    return LatentPromotionEvidence(
        observable_implication_refs=[
            _promotion_ref("a", kind="scientist.latent.observable_implication")
        ],
        local_misspecification_test_refs=[
            _promotion_ref("b", kind="scientist.latent.local_misspecification")
        ],
        environment_stability_ref=_promotion_ref(
            "c", kind="scientist.latent.environment_stability"
        ),
        rival_explanation_audit_ref=_promotion_ref(
            "d", kind="scientist.latent.rival_explanation_audit"
        ),
        external_evidence_refs=[_promotion_ref("e", kind="scientist.latent.external_evidence")],
        replication_refs=[_promotion_ref("f", kind="scientist.latent.replication")],
        hidden_benchmark_ref=_promotion_ref("g", kind="scientist.latent.hidden_benchmark"),
        reviewer_decision_ref=_promotion_ref("h", kind="scientist.latent.reviewer_decision"),
        scope_regime=["linear_nongaussian", "metric_invariant"],
        invariance_level="metric",
    )


def _separation_diagnostics() -> dict[str, object]:
    return {
        "resolution_label": "latent_confounding",
        "design": {
            "n_env": 2,
            "proxy_blocks": ["W", "Z"],
            "repeated_indicator_blocks": ["R"],
        },
        "measurement_block": {
            "status": "passed",
            "tetrad_test": "passed",
            "invariance_test": "supported",
        },
        "proxy_block": {
            "status": "passed",
            "bridge_test": "proximal_bridge_solved",
            "bridge_stability": "stable",
        },
        "environment_block": {
            "status": "passed",
            "residual_invariance": "not_restored",
            "post_calibration_shift": "stable_shift",
        },
        "separated_pairs": ["measurement_vs_confounding"],
        "support_scope": ["proximal-complete"],
    }


def _incomplete_separation_diagnostics() -> dict[str, object]:
    payload = _separation_diagnostics()
    payload["design"] = {
        "n_env": 1,
        "proxy_blocks": ["W"],
        "repeated_indicator_blocks": [],
    }
    return payload


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


def test_merge_latent_bundle_promotes_trust_from_separation_diagnostics() -> None:
    latent_bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=["U_income"],
        inducing_environments=["region_a", "region_b"],
        identification_conditions=["proximal bridge completeness"],
        falsification_tests=["negative_control_outcome"],
        trust_level=LatentTrustLevel.RESEARCH,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="latent_separation_scope",
                title="Stage 9.2 scope",
                description="Two proxy blocks and repeated indicators support pairwise separation.",
            )
        ],
        no_promotion_reasons=["latent_discovery_proof_only"],
        metadata={"separation_diagnostics": _separation_diagnostics()},
    )
    hypothesis = _hypothesis(
        "pc_main",
        DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
        DiscoveryMethod.PC,
        [("X", "Y")],
    ).model_copy(update={"latent_discovery": latent_bundle})

    merged = merge_latent_discovery_hypotheses(
        [hypothesis],
        ranking_order=["pc_main"],
        shortlist=[],
    )

    assert merged is not None
    assert merged.trust_level is LatentTrustLevel.CONDITIONAL
    assert merged.readiness_cap == "proof_only"
    assert merged.promotion_allowed is False
    assert merged.metadata["separation_diagnostics"]["resolution_label"] == "latent_confounding"
    assert merged.metadata["separation_diagnostics"]["separated_pairs"] == [
        "measurement_vs_confounding"
    ]


def test_merge_latent_bundle_preserves_conditional_promotion_cap() -> None:
    latent_bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=["U_income"],
        inducing_environments=["region_a", "region_b"],
        identification_conditions=["proximal bridge completeness"],
        falsification_tests=["negative_control_outcome"],
        trust_level=LatentTrustLevel.CONDITIONAL,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="latent_stage_9_3_scope",
                title="Stage 9.3 scope",
                description="Observable implications and replication support bounded latent use.",
            )
        ],
        readiness_cap="bounds_ready",
        promotion_allowed=True,
        no_promotion_reasons=[],
        not_for_decision_support=False,
        promotion_evidence=_conditional_promotion_evidence(),
    )
    hypothesis = _hypothesis(
        "pc_main",
        DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
        DiscoveryMethod.PC,
        [("X", "Y")],
    ).model_copy(update={"latent_discovery": latent_bundle})

    merged = merge_latent_discovery_hypotheses(
        [hypothesis],
        ranking_order=["pc_main"],
        shortlist=[],
    )

    assert merged is not None
    assert merged.trust_level is LatentTrustLevel.CONDITIONAL
    assert merged.readiness_cap == "bounds_ready"
    assert merged.promotion_allowed is True
    assert merged.not_for_decision_support is False
    assert merged.promotion_evidence is not None


def test_merge_latent_bundle_preserves_cardinality_metadata() -> None:
    block = LatentBlockProposal(
        latent_id="U_01",
        block_size=1,
        role=LatentCausalRole.MEDIATOR,
        status=LatentBlockStatus.IDENTIFIED,
        graph_status=LatentGraphStatus.IDENTIFIED,
        anchor_variables=["x_take_up_1", "x_take_up_2", "x_take_up_3"],
        informative_environment_contrasts=["pre_reform_vs_post_reform"],
        evidence=LatentBlockEvidence(
            gin_supported=True,
            atomic_structure_supported=True,
            shift_localized=True,
            minimal_decomposition_supported=True,
            role_rule_supported=True,
            pure_child_count=3,
            neighbor_count=3,
            rank=1,
        ),
    )
    spec = LatentCardinalityIdentificationSpec(
        identifiability_status=LatentIdentifiabilityStatus.FULL,
        latent_blocks=[block],
        ambiguity_notes=["moderator_role_requires_interaction_extension"],
    )
    latent_bundle = spec.to_bundle(
        inducing_environments=["pre_reform", "post_reform"],
        falsification_tests=["environment_holdout"],
        trust_level=LatentTrustLevel.RESEARCH,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="latent_cardinality_scope",
                title="Stage 9.1 scope",
                description="Cardinality is identified only inside the ME-LiNGLaH-S envelope.",
            )
        ],
        no_promotion_reasons=["latent_discovery_proof_only"],
        metadata=spec.bundle_metadata(),
    )
    hypothesis = _hypothesis(
        "gin_main",
        DiscoveryAlgorithmFamily.FUNCTIONAL,
        DiscoveryMethod.ANM,
        [("X", "Y")],
    ).model_copy(update={"latent_discovery": latent_bundle})

    merged = merge_latent_discovery_hypotheses(
        [hypothesis],
        ranking_order=["gin_main"],
        shortlist=[],
    )

    assert merged is not None
    assert merged.metadata["model_class"] == "ME-LiNGLaH-S"
    assert merged.metadata["identifiability_status"] == "full"
    assert merged.metadata["latent_blocks"][0]["latent_id"] == "U_01"
    assert merged.metadata["ambiguity_notes"] == ["moderator_role_requires_interaction_extension"]
    assert merged.latent_cardinality_spec() is not None
    assert merged.latent_cardinality_spec().latent_blocks[0].role is LatentCausalRole.MEDIATOR


def test_merge_latent_bundle_validates_replicated_separation_diagnostics() -> None:
    assumptions = [
        LatentAssumptionCard(
            assumption_id="latent_separation_scope",
            title="Stage 9.2 scope",
            description="Replicated diagnostics support the same pairwise separation.",
        )
    ]
    latent_bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=["U_income"],
        inducing_environments=["region_a", "region_b"],
        identification_conditions=["proximal bridge completeness"],
        falsification_tests=["negative_control_outcome"],
        trust_level=LatentTrustLevel.RESEARCH,
        assumption_cards=assumptions,
        no_promotion_reasons=["latent_discovery_proof_only"],
        metadata={"separation_diagnostics": _separation_diagnostics()},
    )
    alt_bundle = latent_bundle.model_copy(
        update={
            "assumption_cards": assumptions,
            "metadata": {"separation_diagnostics": _separation_diagnostics()},
        }
    )
    hypotheses = [
        _hypothesis(
            "pc_main",
            DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
            DiscoveryMethod.PC,
            [("X", "Y")],
        ).model_copy(update={"latent_discovery": latent_bundle}),
        _hypothesis(
            "fci_replication",
            DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
            DiscoveryMethod.FCI,
            [("X", "Y")],
        ).model_copy(update={"latent_discovery": alt_bundle}),
    ]

    merged = merge_latent_discovery_hypotheses(
        hypotheses,
        ranking_order=["pc_main", "fci_replication"],
        shortlist=[],
    )

    assert merged is not None
    assert merged.trust_level is LatentTrustLevel.VALIDATED
    assert merged.readiness_cap == "proof_only"
    assert merged.promotion_allowed is False
    assert (
        merged.metadata["separation_diagnostics"]["replication"]["independent_discovery_hypothesis"]
        is True
    )


def test_merge_latent_bundle_keeps_research_when_any_separation_source_is_incomplete() -> None:
    latent_bundle = LatentDiscoveryBundle(
        proposed_latent_nodes=["U_income"],
        inducing_environments=["region_a", "region_b"],
        identification_conditions=["proximal bridge completeness"],
        falsification_tests=["negative_control_outcome"],
        trust_level=LatentTrustLevel.RESEARCH,
        assumption_cards=[
            LatentAssumptionCard(
                assumption_id="latent_separation_scope",
                title="Stage 9.2 scope",
                description="Diagnostics must be complete before trust promotion.",
            )
        ],
        no_promotion_reasons=["latent_discovery_proof_only"],
        metadata={"separation_diagnostics": _separation_diagnostics()},
    )
    incomplete_bundle = latent_bundle.model_copy(
        update={"metadata": {"separation_diagnostics": _incomplete_separation_diagnostics()}}
    )
    hypotheses = [
        _hypothesis(
            "pc_main",
            DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
            DiscoveryMethod.PC,
            [("X", "Y")],
        ).model_copy(update={"latent_discovery": latent_bundle}),
        _hypothesis(
            "fci_replication",
            DiscoveryAlgorithmFamily.CONSTRAINT_BASED,
            DiscoveryMethod.FCI,
            [("X", "Y")],
        ).model_copy(update={"latent_discovery": incomplete_bundle}),
    ]

    merged = merge_latent_discovery_hypotheses(
        hypotheses,
        ranking_order=["pc_main", "fci_replication"],
        shortlist=[],
    )

    assert merged is not None
    assert merged.trust_level is LatentTrustLevel.RESEARCH
    assert merged.readiness_cap == "proof_only"
    assert merged.promotion_allowed is False


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
            metadata={"separation_diagnostics": _separation_diagnostics()},
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
        source_reports["pc_main"]
        .algebraic_constraints.violated_constraints_preview[0]
        .constraint_id
        == "ci:X_Y"
    )
    assert merged_latent is not None
    assert merged_latent.readiness_cap == "proof_only"
    assert merged_latent.promotion_allowed is False
    assert merged_latent.metadata["source_hypothesis_ids"] == ["pc_main"]
    assert audit.latent_discovery_summary["resolution_label"] == "latent_confounding"
    assert audit.latent_discovery_summary["separated_pairs"] == ["measurement_vs_confounding"]


def test_discovery_artifact_builder_uses_automatic_latent_producer_paths(tmp_path) -> None:
    report = CausalDiscoveryReport(
        method="pc",
        graph=_graph([("W_anchor", "X"), ("W_anchor", "Y"), ("X", "Y")]),
        metadata={
            LATENT_CARDINALITY_EVIDENCE_KEY: LatentCardinalityEvidencePayload(
                model_class="ME-LiNGLaH-S",
                treatment_variable="X",
                outcome_variable="Y",
                inducing_environments=["region_a", "region_b"],
                latent_blocks=[
                    LatentBlockProposal(
                        latent_id="U_auto",
                        block_size=1,
                        role=LatentCausalRole.CONFOUNDER,
                        status=LatentBlockStatus.PARTIAL,
                        graph_status=LatentGraphStatus.PARTIAL,
                        anchor_variables=["W_anchor"],
                        informative_environment_contrasts=["region_a_vs_region_b"],
                        evidence=LatentBlockEvidence(
                            gin_supported=True,
                            atomic_structure_supported=True,
                            shift_localized=True,
                            minimal_decomposition_supported=True,
                            role_rule_supported=False,
                            pure_child_count=2,
                            neighbor_count=3,
                            rank=1,
                        ),
                    )
                ],
            ).model_dump(mode="json"),
            "latent_separation_measurement": {
                "status": "passed",
                "tetrad_test": "single_signal_tetrad_passed",
                "invariance_test": "measurement_invariance_passed",
                "repeated_indicator_blocks": ["R_block"],
            },
            "latent_separation_proxy": {
                "status": "passed",
                "bridge_test": "proximal_bridge_solved",
                "bridge_stability": "cross_environment_stable",
                "proxy_blocks": ["W", "Z"],
            },
            "latent_separation_environment": {
                "status": "passed",
                "residual_invariance": "post_calibration_residual_invariance_failed",
                "post_calibration_shift": "not_restored",
                "environments": ["region_a", "region_b"],
                "n_env": 2,
            },
            "latent_separation_design": {
                "environments": ["region_a", "region_b"],
                "proxy_blocks": ["W", "Z"],
                "repeated_indicator_blocks": ["R_block"],
            },
        },
    )
    hypothesis = graph_hypothesis_from_report(report, hypothesis_id="pc_auto")
    stability = BootstrapStabilityReport(
        bootstrap_mode=BootstrapMode.ROW,
        config=BootstrapStabilityConfig(n_resamples=2),
        summaries=[
            HypothesisStabilitySummary(
                hypothesis_id="pc_auto",
                edge_selection_frequency={
                    "W_anchor->X": 0.9,
                    "W_anchor->Y": 0.9,
                    "X->Y": 0.8,
                },
                mean_edge_stability=0.87,
                adjustment_set_stability=0.75,
                completed_resamples=2,
            )
        ],
    )
    utility = DownstreamUtilityJudge().evaluate(
        UtilityJudgeInput(
            hypotheses=[hypothesis],
            stability_report=stability,
            causal_query=_query(),
        )
    )
    matrix = EvidenceWeightedAggregator().aggregate([hypothesis], stability, utility)
    store = FileSystemCAS(tmp_path)

    bundle_ref = DiscoveryArtifactBuilder().build(
        store,
        DiscoveryArtifactBuildInput(
            run_id="R_discovery_latent_auto",
            task_id="task_discovery_latent_auto",
            variable_names=["W_anchor", "X", "Y"],
            causal_query=_query(),
            hypotheses=[hypothesis],
            portfolio_result=PortfolioRunResult(
                candidates=[
                    PortfolioCandidate(
                        hypothesis=hypothesis,
                        source_report=report,
                        method_params={"significance_level": 0.05},
                    )
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
    merged_latent = load_merged_latent_discovery_bundle(store, bundle)

    assert merged_latent is not None
    assert merged_latent.proposed_latent_nodes == [
        "U_auto|block_size=1|role=confounder|status=identified"
    ]
    assert merged_latent.trust_level is LatentTrustLevel.CONDITIONAL
    assert merged_latent.readiness_cap == "proof_only"
    assert merged_latent.metadata["separation_diagnostics"]["resolution_label"] == (
        "latent_confounding"
    )
