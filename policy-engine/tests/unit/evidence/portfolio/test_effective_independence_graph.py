from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy
from typing import Any

import pytest

from polisyos.evidence.portfolio.effective_independence_graph import (
    EFFECTIVE_INDEPENDENCE_GRAPH_SCHEMA_VERSION,
    EffectiveIndependenceGraphError,
    annotate_pdc_graph_with_effective_independence,
    build_effective_independence_graph,
    validate_effective_independence_graph_record,
)
from polisyos.runtime.quality.evidence_independence import (
    GRADED_INDEPENDENCE_FEATURE_FLAG,
    build_evidence_independence_map,
)
from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
)
from tests._helpers.hds_quality import sha


def _portfolio_design() -> dict[str, object]:
    return {
        "schema_version": EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
        "portfolio_id": "portfolio-rec-1",
        "claim_ids": ["rec_1"],
        "predeclared": True,
        "declared_at": "2026-05-17T08:00:00+00:00",
        "declared_before_producer_execution": True,
        "authority_level": "production",
        "strands": [
            {
                "strand_id": "literature-strand",
                "claim_id": "rec_1",
                "authority_level": "production",
                "candidate_data_source_families": ["academic_evidence"],
                "candidate_method_families": ["quasi_experimental_panel"],
                "defensible_specification_space": {"primary_estimand": "ATT"},
                "inclusion_rules": ["Include independent scholar publications."],
                "exclusion_rules": ["Exclude repeated reports of the same study."],
                "disconfirming_lines": [{"line_id": "counter-required", "required": True}],
                "synthesis_rules": {"strategy": "effective_independence"},
                "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
                "cost_proportionality": {"budget_tier": "standard"},
            }
        ],
        "candidate_data_source_families": ["academic_evidence"],
        "candidate_method_families": ["quasi_experimental_panel"],
        "inclusion_rules": ["Prefer production-ready evidence lines."],
        "exclusion_rules": ["Reject raw-count inflation."],
        "disconfirming_lines": ["counter-required"],
        "synthesis_rules": {"strategy": "effective_independence"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "standard"},
        "cas_ref": sha("portfolio"),
        "runtime_event_ref": sha("portfolio-event"),
    }


def _line(
    line_id: str,
    *,
    primary_source: str,
    study_id: str,
    polarity: str = "support",
    quality: float = 1.0,
    institution: str = "policy-lab",
    method_family: str = "difference_in_differences",
    dataset: str = "dataset-a",
    snapshot: str = "snapshot-a",
    preprocessing: str = "prep-a",
    identification: str = "did-identification",
    concept_spine: str = "concept-spine:msme-credit",
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": line_id,
        "portfolio_id": "portfolio-rec-1",
        "portfolio_strand_id": "literature-strand",
        "claim_id": "rec_1",
        "evidence_strand": "literature",
        "polarity": polarity,
        "quality_score": quality,
        "source_refs": [f"source:{line_id}"],
        "primary_source": primary_source,
        "retrieval_path": f"scholar-search:{line_id}",
        "source_lineage": {
            "source_id": primary_source,
            "source_ref": f"source:{line_id}",
            "lineage_refs": [f"lineage:{line_id}"],
            "corpus_id": dataset,
            "corpus_ancestry": [dataset],
            "snapshot_id": snapshot,
            "preprocessing": preprocessing,
            "transformation_lineage": [f"transform:{dataset}:{preprocessing}"],
            "retrieval_path": f"scholar-search:{line_id}",
        },
        "underlying_study_id": study_id,
        "legal_authority": ["research-use-permit-2026"],
        "author_ids": ["author:policy-eval-cell"],
        "institution_ids": [institution],
        "sponsor_ids": ["public-interest-fund"],
        "dataset_id": dataset,
        "corpus_ancestry": [dataset],
        "snapshot_id": snapshot,
        "subject_pool": "msme-credit-applicants",
        "preprocessing_pipeline_id": preprocessing,
        "transformation_lineage": [f"transform:{dataset}:{preprocessing}"],
        "method_id": f"foundry.{method_family}.{line_id}",
        "method_family": method_family,
        "method_assumptions": ["parallel-trends", "no-anticipation"],
        "identification_strategy_id": identification,
        "shared_failure_modes": ["selection-on-unobservables"],
        "proof_reuse_status": "fresh_proof",
        "llm_generation_path": {
            "model": "none",
            "prompt_ref": "deterministic-producer",
            "retrieval_ref": f"scholar-search:{line_id}",
        },
        "simulation_dgp": {
            "dgp_ref": "not_simulated",
            "calibration_ref": "not_applicable",
            "assumption_family": "not_applicable",
        },
        "participation_sample_frame": "not_participation_evidence",
        "concept_spine_refs": [concept_spine],
        "jurisdiction": "UA",
        "time_roles": {
            "publication_time": "2025-01-01",
            "retrieval_time": "2026-05-17T09:00:00+00:00",
            "legal_valid_time": "2026-01-01/2026-12-31",
        },
        "specification_id": f"spec:{line_id}",
        "producer_identity": {
            "component": "polisyos.scholar.evidence",
            "version": "2026.05.24+w8f",
            "owner": "team-science-quality",
        },
        "execution_context": {
            "run_id": "run-w8f",
            "job_id": f"job:{line_id}",
            "tenant_id": "tenant-prod",
            "trace_id": f"trace:{line_id}",
        },
        "evidence_ref": sha(f"evidence:{line_id}"),
        "runtime_event_ref": sha(f"event:{line_id}"),
    }


def _graded_config() -> dict[str, Any]:
    return {
        "owner": "team-science-quality",
        "version": "2026-05-24.provisional",
        "status": "provisional",
        "weights": {
            "method_family": 0.25,
            "author_institution_sponsor": 0.20,
            "concept_spine": 0.10,
        },
    }


def test_graph_hard_collapses_multiple_publications_from_same_study() -> None:
    graph = build_effective_independence_graph(
        [
            _line("pub-1", primary_source="journal-a", study_id="study-42"),
            _line("pub-2", primary_source="working-paper", study_id="study-42"),
            _line("pub-3", primary_source="policy-report", study_id="study-42"),
        ],
        portfolio_designs=[_portfolio_design()],
        graph_id="effective-independence-graph-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )

    assert graph["schema_version"] == EFFECTIVE_INDEPENDENCE_GRAPH_SCHEMA_VERSION
    assert graph["raw_evidence_line_count"] == 3
    assert graph["hard_effective_line_count"] == 1
    assert graph["hard_collapse_clusters"][0]["collapse_reasons"][0]["reason_code"] == (
        "same_study_reported_multiple_times"
    )
    assert graph["mass_report"]["hard_effective_support_count"] == 1
    assert graph["mass_report"]["graded_effective_support_mass"] == 1.0
    assert graph["mass_report"]["raw_count_authority"] == "diagnostic_only"


def test_graph_graded_partial_collapse_uses_quality_times_novelty_mass() -> None:
    graph = build_effective_independence_graph(
        [
            _line(
                "line-a",
                primary_source="journal-a",
                study_id="study-a",
                quality=0.8,
            ),
            _line(
                "line-b",
                primary_source="journal-b",
                study_id="study-b",
                quality=0.6,
                dataset="dataset-b",
                snapshot="snapshot-b",
                preprocessing="prep-b",
                identification="synthetic-control",
            ),
        ],
        portfolio_designs=[_portfolio_design()],
        graph_id="effective-independence-graph-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
        feature_flags={GRADED_INDEPENDENCE_FEATURE_FLAG: True},
        graded_independence_config=_graded_config(),
    )

    pair = graph["graded_calculus"]["pairwise_dependencies"][0]
    assert pair["dependence_score"] == pytest.approx(0.55)
    assert pair["independence_score"] == pytest.approx(0.45)
    assert pair["overlap_contributions"] == [
        {"dimension": "method_family", "weight": 0.25, "overlap": 1.0, "contribution": 0.25},
        {
            "dimension": "author_institution_sponsor",
            "weight": 0.2,
            "overlap": 1.0,
            "contribution": 0.2,
        },
        {"dimension": "concept_spine", "weight": 0.1, "overlap": 1.0, "contribution": 0.1},
    ]
    assert graph["mass_report"]["line_contributions"] == [
        {
            "line_id": "line-a",
            "polarity": "support",
            "quality": 0.8,
            "novelty": 1.0,
            "mass": 0.8,
            "formula": "quality(a) * novelty(a | S)",
        },
        {
            "line_id": "line-b",
            "polarity": "support",
            "quality": 0.6,
            "novelty": pytest.approx(0.45),
            "mass": pytest.approx(0.27),
            "formula": "quality(a) * novelty(a | S)",
        },
    ]
    assert graph["mass_report"]["graded_effective_support_mass"] == pytest.approx(1.07)


def test_graph_classifies_structural_scarcity_without_support_inflation() -> None:
    graph = build_effective_independence_graph(
        [_line("line-a", primary_source="journal-a", study_id="study-a")],
        portfolio_designs=[_portfolio_design()],
        graph_id="effective-independence-graph-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
        rare_domain_context={
            "scarcity_kind": "scarcity_structural",
            "minimum_effective_independent_evidence_count": 3,
            "accepted_deficit_ref": "deficit:single-independent-line-reviewed",
            "review_status": "reviewed",
        },
    )

    scarcity = graph["scarcity_path"]
    assert scarcity["status"] == "scarcity_structural"
    assert scarcity["support_inflation_allowed"] is False
    assert scarcity["effective_support_mass_after_scarcity"] == 1.0
    assert scarcity["closeout_path"] == ("lower_authority_closeout_or_reviewed_single_line_deficit")
    assert "scarcity_structural" in graph["mass_report"]["limiting_deficits"]

    invalid = deepcopy(graph)
    invalid["scarcity_path"]["effective_support_mass_after_scarcity"] = 3.0
    with pytest.raises(
        EffectiveIndependenceGraphError,
        match="policy_design_effective_independence_scarcity_support_inflation",
    ):
        validate_effective_independence_graph_record(invalid)


def test_graph_preserves_counterevidence_separately_from_support() -> None:
    graph = build_effective_independence_graph(
        [
            _line("support-a", primary_source="journal-a", study_id="study-42"),
            _line(
                "counter-a",
                primary_source="journal-a",
                study_id="study-42",
                polarity="counterevidence",
            ),
        ],
        portfolio_designs=[_portfolio_design()],
        graph_id="effective-independence-graph-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
        feature_flags={GRADED_INDEPENDENCE_FEATURE_FLAG: True},
        graded_independence_config=_graded_config(),
    )

    assert graph["hard_effective_line_count"] == 2
    assert graph["mass_report"]["support_line_ids"] == ["support-a"]
    assert graph["mass_report"]["counterevidence_line_ids"] == ["counter-a"]
    assert graph["mass_report"]["hard_effective_support_count"] == 1
    assert graph["mass_report"]["hard_effective_counterevidence_count"] == 1
    assert graph["counterevidence_policy"]["collapse_across_support"] == "forbidden"
    assert graph["graded_calculus"]["pairwise_dependencies"][0]["collapse_eligible"] is False
    assert (
        graph["graded_calculus"]["pairwise_dependencies"][0]["exclusion_reason"]
        == "counterevidence_preserved_separately"
    )


def test_graph_annotates_runtime_pdc_graph_claims_with_effective_independence_ref() -> None:
    graph = build_effective_independence_graph(
        [_line("line-a", primary_source="journal-a", study_id="study-a")],
        portfolio_designs=[_portfolio_design()],
        graph_id="effective-independence-graph-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )

    annotated = annotate_pdc_graph_with_effective_independence(
        {"graph_id": "pdc-graph-1", "claims": [{"claim_id": "rec_1"}]},
        graph,
    )

    assert annotated["effective_independence_graph_refs"] == ["effective-independence-graph-1"]
    assert annotated["claims"][0]["effective_independence_refs"] == [
        "effective-independence-graph-1"
    ]
    assert (
        annotated["claims"][0]["effective_independence_summary"]["graded_effective_support_mass"]
        == 1.0
    )


def test_w4b_independence_map_exposes_feature_flagged_graded_graph() -> None:
    independence_map = build_evidence_independence_map(
        [
            _line(
                "line-a",
                primary_source="journal-a",
                study_id="study-a",
                quality=0.8,
            ),
            _line(
                "line-b",
                primary_source="journal-b",
                study_id="study-b",
                quality=0.6,
                dataset="dataset-b",
                snapshot="snapshot-b",
                preprocessing="prep-b",
                identification="synthetic-control",
            ),
        ],
        portfolio_designs=[_portfolio_design()],
        map_id="independence-map-rec-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
        feature_flags={GRADED_INDEPENDENCE_FEATURE_FLAG: True},
        graded_independence_config=_graded_config(),
    )

    graded = independence_map["graded_independence"]
    assert graded["enabled"] is True
    assert graded["effective_independence_graph_ref"] == (
        "effective-independence-graph:independence-map-rec-1"
    )
    assert graded["pairwise_model"] == "D(a,b)=min(0.95,sum(weight_c*overlap_c));I(a,b)=1-D(a,b)"
    assert graded["graded_effective_support_mass"] == pytest.approx(1.07)
