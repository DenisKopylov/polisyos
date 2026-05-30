from __future__ import annotations

# ruff: noqa: S101
from polisyos.ir.analytics.cross_graph import (
    CrossGraphEvidenceProfile,
    CrossGraphEvidenceSummary,
    EvidenceNeed,
    EvidenceNeedAssessment,
    EvidenceNeedType,
    EvidenceStatus,
    LegalStatus,
    ObservabilityStatus,
)
from polisyos.runtime.quality.capability_authority import compose_capability_authority
from polisyos.runtime.quality.capability_index import (
    AuthorityEnvelope,
    CapabilityScope,
    CapabilitySourceAsset,
    EvidenceCapability,
    FreshnessEnvelope,
    QualityScore,
    RightsEnvelope,
)
from polisyos.runtime.quality.claim_registry import claim_registry_rows_by_id
from polisyos.scientist.cross_graph.conflict import (
    ConflictSeverity,
    EvidenceConflict,
)
from polisyos.scientist.cross_graph.conflict_materializer import (
    construct_conflict_markers_for_capability,
    materialize_cross_graph_conflicts,
    validate_conflict_backstop_coverage,
)


def _registry_row() -> dict[str, object]:
    return {
        "schema_version": "policyos.runtime.claim_registry.v1",
        "claims": [
            {
                "claim_id": "rec_credit_guarantee",
                "claim_family": "recommendation",
                "scenario_requirement_refs": ["scenario.req.credit_support"],
                "data_refs": ["source.msme_panel"],
                "selected_norm_refs": ["norm.ua.credit_guarantee"],
                "method_output_refs": ["foundry.did.msme_survival"],
                "portfolio_refs": ["portfolio.rec_credit_guarantee"],
                "argument_refs": ["argument.rec_credit_guarantee"],
                "warrant_refs": ["warrant.rec_credit_guarantee"],
                "rebuttal_refs": ["rebuttal.rec_credit_guarantee"],
                "counter_evidence_refs": ["counter.baseline"],
                "limitation_refs": ["limitation.rec_credit_guarantee"],
                "accepted_deficit_refs": ["deficit.recency.msme_panel"],
                "assumption_gate_refs": ["assumption-gate.rec_credit_guarantee"],
                "uncertainty_refs": ["uncertainty.rec_credit_guarantee"],
            }
        ],
    }


def _conflicting_profile() -> CrossGraphEvidenceProfile:
    need = EvidenceNeed(
        need_id="legal_applicability_need:credit_guarantee",
        need_type=EvidenceNeedType.LEGAL_APPLICABILITY_NEED,
        source_path="policy_spec.interventions[0]",
    )
    assessment = EvidenceNeedAssessment(
        need=need,
        legal_status=LegalStatus.PROHIBITED,
        observability_status=ObservabilityStatus.DIRECT,
        evidence_status=EvidenceStatus.SUPPORTED,
        confidence=0.45,
        requires_expert_review=True,
        provenance_refs=["lex:blocker:credit_guarantee", "scholar:study:msme_credit"],
    )
    return CrossGraphEvidenceProfile(
        summary=CrossGraphEvidenceSummary(total_needs=1),
        needs=[assessment],
    )


def _capability() -> EvidenceCapability:
    return EvidenceCapability(
        capability_id="capability:firm_survival_exact",
        construct="firm_survival",
        modality=("fabric_data",),
        evidence_mode="observed",
        concept_spine_refs=("concept:firm_survival",),
        scope=CapabilityScope(
            geography="UA",
            schema_regime="ukraine_schema_v2",
            entity_scope="firm",
        ),
        identification_mode="point_identified",
        trust_tier="authoritative_high_coverage",
        quality_score=QualityScore(
            composite=0.95,
            breakdown={"construct_validity": 0.95},
        ),
        source_assets=(
            CapabilitySourceAsset(
                ref="asset:firm-survival",
                source_layer="L4",
                asset_type="parquet",
                role="observation",
            ),
        ),
        authority_envelope=AuthorityEnvelope(
            research="admissible",
            governed_pilot="admissible",
            production="admissible",
        ),
        lineage_refs=("source_snapshot:ua-20260410",),
        freshness_envelope=FreshnessEnvelope(freshness_class="fresh_for_production"),
        rights_envelope=RightsEnvelope(access_class="government_administrative"),
    )


def test_materializer_bridges_detector_conflict_to_registry_and_portfolio() -> None:
    result = materialize_cross_graph_conflicts(
        _conflicting_profile(),
        run_id="run-w8e",
        claim_id_by_need_id={
            "legal_applicability_need:credit_guarantee": ["rec_credit_guarantee"]
        },
        claim_registry=_registry_row(),
        portfolio_designs=[
            {
                "portfolio_id": "portfolio.rec_credit_guarantee",
                "claim_ids": ["rec_credit_guarantee"],
            }
        ],
        producer_handshake_refs=["producer-handshake:run-w8e"],
    )

    assert result.issues == ()
    assert len(result.conflict_records) == 1
    record = result.conflict_records[0]
    assert record["conflict_type"] == "legal"
    assert record["resolution_route"] == "legal_hierarchy"
    assert record["detection_phase"] == "post_hoc_backstop"
    assert record["producer_handshake_refs"] == ["producer-handshake:run-w8e"]

    registry_row = claim_registry_rows_by_id(result.claim_registry)["rec_credit_guarantee"]
    assert registry_row["conflict_refs"] == [record["conflict_id"]]
    assert record["conflict_id"] in registry_row["counter_evidence_refs"]
    assert result.portfolio_index["conflict_refs_by_portfolio"] == {
        "portfolio.rec_credit_guarantee": [record["conflict_id"]]
    }


def test_backstop_detector_conflict_without_w8e_record_blocks_closeout() -> None:
    detector_conflict = EvidenceConflict(
        need_id="legal_applicability_need:credit_guarantee",
        dimension="legal_vs_academic",
        conflicting_sources=["legal", "academic"],
        severity=ConflictSeverity.HIGH,
        description="Legal prohibits what academic evidence supports",
    )

    issues = validate_conflict_backstop_coverage(
        [detector_conflict],
        conflict_records=[],
    )

    assert issues == (
        {
            "code": "policy_design_conflict_materialization_missing",
            "severity": "fail",
            "layer": "scientist_cross_graph",
            "phase": "w8e_conflict_materializer",
            "need_id": "legal_applicability_need:credit_guarantee",
            "missing_evidence_type": "conflict_record",
            "closeout_blocking": True,
            "message": (
                "ConflictDetector found conflict legal_vs_academic for "
                "legal_applicability_need:credit_guarantee, but no W8.E "
                "first-class conflict record materialized it."
            ),
            "next_action": (
                "Run materialize_cross_graph_conflicts and bind the emitted conflict "
                "record into claim_registry conflict_refs and the portfolio index."
            ),
        },
    )


def test_materializer_reports_claim_binding_gap_instead_of_detached_record() -> None:
    result = materialize_cross_graph_conflicts(
        _conflicting_profile(),
        run_id="run-w8e",
        claim_id_by_need_id={},
        claim_registry=_registry_row(),
    )

    assert result.conflict_records == ()
    assert result.issues[0]["code"] == "policy_design_conflict_claim_binding_missing"
    assert result.issues[0]["closeout_blocking"] is True


def test_construct_conflict_marker_exposes_conflict_class_through_binding_output() -> None:
    materialized = materialize_cross_graph_conflicts(
        _conflicting_profile(),
        run_id="run-w8e",
        claim_id_by_need_id={
            "legal_applicability_need:credit_guarantee": ["rec_credit_guarantee"]
        },
        claim_registry=_registry_row(),
    )
    record = {
        **materialized.conflict_records[0],
        "metadata": {
            **materialized.conflict_records[0].get("metadata", {}),
            "construct": "firm_survival",
            "conflict_class": "empirical",
            "capability_refs": ["capability:firm_survival_exact"],
        },
    }

    markers = construct_conflict_markers_for_capability(
        _capability(),
        conflict_records=(record,),
    )
    binding = compose_capability_authority(
        _capability(),
        posture="production",
        claim_use="claim_evidence_closeout",
        conflict_markers=markers,
    )

    assert markers[0]["conflict_class"] == "empirical"
    assert binding.status == "selected_with_conflict_marker"
    assert binding.conflict_markers[0]["conflict_class"] == "empirical"
