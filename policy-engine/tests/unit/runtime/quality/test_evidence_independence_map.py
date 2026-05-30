from __future__ import annotations

# ruff: noqa: S101
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

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
from polisyos.runtime.quality.evidence_independence import (
    INDEPENDENCE_MAP_SCHEMA_VERSION,
    EvidenceIndependenceError,
    build_evidence_independence_map,
    effective_independence_factor_for_capability,
    validate_evidence_independence_map_record,
)
from polisyos.runtime.quality.evidence_portfolio import (
    EVIDENCE_PORTFOLIO_DESIGN_SCHEMA_VERSION,
)
from tests._helpers.hds_quality import sha

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPO_ROOT / "schemas/runtime_quality/policy_design_independence_map_v1.schema.json"
)


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
                "strand_id": "data-method-literature",
                "claim_id": "rec_1",
                "authority_level": "production",
                "candidate_data_source_families": [
                    "production_msme_panel",
                    "administrative_credit_registry",
                ],
                "candidate_method_families": [
                    "causal_effect_estimation",
                    "quasi_experimental_panel",
                ],
                "defensible_specification_space": {
                    "primary_estimand": "ATT",
                    "allowed_models": ["two_way_fixed_effects", "event_study"],
                },
                "inclusion_rules": [
                    "Include production datasets with firm survival and credit exposure.",
                ],
                "exclusion_rules": [
                    "Exclude fixture or survey-only sources without legal use rights.",
                ],
                "disconfirming_lines": [
                    {
                        "line_id": "placebo-pre-period",
                        "required": True,
                        "evidence_family": "negative_control",
                    }
                ],
                "synthesis_rules": {"strategy": "triangulate_independent_lines"},
                "stopping_rules": {
                    "minimum_effective_independent_evidence_count": 2,
                },
                "cost_proportionality": {"budget_tier": "standard"},
            }
        ],
        "candidate_data_source_families": [
            "production_msme_panel",
            "administrative_credit_registry",
        ],
        "candidate_method_families": [
            "causal_effect_estimation",
            "quasi_experimental_panel",
        ],
        "inclusion_rules": ["Prefer production administrative sources."],
        "exclusion_rules": ["Reject local fixture sources."],
        "disconfirming_lines": ["placebo-pre-period"],
        "synthesis_rules": {"strategy": "triangulate_independent_lines"},
        "stopping_rules": {"minimum_effective_independent_evidence_count": 2},
        "cost_proportionality": {"budget_tier": "standard"},
        "cas_ref": sha("1"),
        "runtime_event_ref": sha("2"),
    }


def _evidence_line(*, cluster: int, index: int) -> dict[str, Any]:
    method_variant = "primary" if index % 2 == 0 else "equivalent"
    return {
        "schema_version": "policyos.runtime.policy_design_case.evidence_line.v1",
        "line_id": f"line-{cluster}-{index}",
        "portfolio_id": "portfolio-rec-1",
        "portfolio_strand_id": "data-method-literature",
        "claim_id": "rec_1",
        "evidence_strand": "data",
        "source_lineage": {
            "source_id": f"production-msme-panel-{cluster}",
            "source_ref": sha(f"source-{cluster}"),
            "lineage_refs": [sha(f"lineage-{cluster}")],
            "corpus_id": f"credit-registry-corpus-{cluster}",
            "corpus_ancestry": [f"national-credit-registry-{cluster}"],
        },
        "corpus_ancestry": [f"national-credit-registry-{cluster}"],
        "author_pool": [f"analysis-cell-{cluster}"],
        "institution_pool": [f"policy-lab-{cluster}"],
        "preprocessing_pipeline_id": f"winsorize-linkage-v{cluster}",
        "method_id": f"foundry.did.cluster{cluster}.{method_variant}",
        "method_assumptions": [
            f"parallel trends holds for cluster {cluster}",
            f"no anticipatory treatment for cluster {cluster}",
        ],
        "identification_strategy_id": f"did-att-identification-{cluster}",
        "shared_failure_modes": [f"registry-linkage-bias-{cluster}"],
        "specification_id": f"did.att.spec-{index}",
        "producer_identity": {
            "component": "polisyos.foundry.methods.causal",
            "version": "2026.05.17+wave17",
            "owner": "team-science-quality",
        },
        "execution_context": {
            "run_id": "run-policy-design-1",
            "job_id": f"job-evidence-line-{cluster}-{index}",
            "tenant_id": "tenant-prod",
            "trace_id": f"trace-evidence-line-{cluster}-{index}",
        },
        "evidence_ref": sha(f"evidence-{cluster}-{index}"),
        "runtime_event_ref": sha(f"event-{cluster}-{index}"),
    }


def _capability(
    *,
    capability_id: str,
    lineage_refs: tuple[str, ...],
) -> EvidenceCapability:
    return EvidenceCapability(
        capability_id=capability_id,
        construct="firm_survival",
        modality=("fabric_data",),
        evidence_mode="observed",
        concept_spine_refs=("concept:firm_survival",),
        scope=CapabilityScope(
            geography="UA",
            schema_regime="ukraine_schema_v2",
            entity_scope="firm",
            time_start="2022-02-01",
        ),
        identification_mode="point_identified",
        trust_tier="authoritative_high_coverage",
        quality_score=QualityScore(
            composite=0.95,
            breakdown={"construct_validity": 0.95},
        ),
        source_assets=(
            CapabilitySourceAsset(
                ref=f"asset:{capability_id}",
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
        lineage_refs=lineage_refs,
        freshness_envelope=FreshnessEnvelope(freshness_class="fresh_for_production"),
        rights_envelope=RightsEnvelope(access_class="government_administrative"),
    )


def _consensus_reports() -> list[dict[str, Any]]:
    return [
        {
            "status": "pass",
            "consensus_set": [
                f"foundry.did.cluster{cluster}.primary",
                f"foundry.did.cluster{cluster}.equivalent",
            ],
        }
        for cluster in range(4)
    ]


def _equivalence_reports() -> list[dict[str, Any]]:
    return [
        {
            "verdict": "pass_strict",
            "source_method_id": f"foundry.did.cluster{cluster}.primary",
            "target_method_id": f"foundry.did.cluster{cluster}.equivalent",
            "certificate_ref": sha(f"equivalence-{cluster}"),
        }
        for cluster in range(4)
    ]


def test_independence_map_collapses_400_raw_lines_to_small_effective_count() -> None:
    lines = [
        _evidence_line(cluster=cluster, index=index)
        for cluster in range(4)
        for index in range(100)
    ]

    independence_map = build_evidence_independence_map(
        lines,
        portfolio_designs=[_portfolio_design()],
        method_consensus_reports=_consensus_reports(),
        method_equivalence_reports=_equivalence_reports(),
        map_id="independence-map-rec-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )

    assert independence_map["schema_version"] == INDEPENDENCE_MAP_SCHEMA_VERSION
    assert independence_map["raw_evidence_line_count"] == 400
    assert independence_map["effective_independent_evidence_count"] == 4
    assert len(independence_map["collapse_clusters"]) == 4
    assert {cluster["raw_line_count"] for cluster in independence_map["collapse_clusters"]} == {
        100
    }
    assert {
        cluster["collapse_dimensions"]["method_cluster_id"]
        for cluster in independence_map["collapse_clusters"]
    } == {
        "foundry.did.cluster0.primary",
        "foundry.did.cluster1.primary",
        "foundry.did.cluster2.primary",
        "foundry.did.cluster3.primary",
    }
    assert independence_map["effective_mass_report"]["raw_evidence_line_count"] == 400
    assert (
        independence_map["effective_mass_report"]["effective_independent_evidence_count"]
        == 4
    )
    assert independence_map["effective_mass_report"]["effective_support_mass"] == 4.0
    assert independence_map["effective_mass_report"]["dominant_collapse_reasons"]
    assert all(
        cluster["collapse_reasons"]
        for cluster in independence_map["collapse_clusters"]
        if cluster["raw_line_count"] > 1
    )


def test_effective_independence_factor_degrades_overlapping_capability_lineage() -> None:
    first = _capability(
        capability_id="capability:firm_survival_admin",
        lineage_refs=("source_snapshot:shared", "calibration_run:shared"),
    )
    second = _capability(
        capability_id="capability:firm_survival_duplicate",
        lineage_refs=("source_snapshot:shared", "calibration_run:shared"),
    )

    factor = effective_independence_factor_for_capability(
        second,
        selected_capabilities=(first,),
    )
    result = compose_capability_authority(
        second,
        posture="production",
        claim_use="claim_evidence_closeout",
        selected_capabilities=(first,),
    )

    assert factor.value < 0.5
    assert factor.collapse_ratio > 0.7
    assert result.factor_by_name("effective_independence").value == factor.value
    assert result.status == "selected_proxy_with_limitation"
    assert result.authority_envelope_result == "limited"


def test_independence_map_preserves_counterevidence_as_separate_effective_mass() -> None:
    lines = [
        {
            **_evidence_line(cluster=0, index=0),
            "line_id": "support-line-1",
            "polarity": "support",
        },
        {
            **_evidence_line(cluster=0, index=1),
            "line_id": "support-line-2",
            "polarity": "support",
        },
        {
            **_evidence_line(cluster=0, index=2),
            "line_id": "counter-line-1",
            "polarity": "counterevidence",
        },
    ]

    independence_map = build_evidence_independence_map(
        lines,
        portfolio_designs=[_portfolio_design()],
        method_consensus_reports=_consensus_reports(),
        method_equivalence_reports=_equivalence_reports(),
        map_id="independence-map-rec-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )

    mass = independence_map["effective_mass_report"]
    assert independence_map["raw_evidence_line_count"] == 3
    assert independence_map["effective_independent_evidence_count"] == 1
    assert mass["raw_support_line_count"] == 2
    assert mass["raw_counterevidence_line_count"] == 1
    assert mass["effective_support_mass"] == 1.0
    assert mass["effective_counterevidence_mass"] == 1.0
    assert mass["balance_status"] == "mixed"
    assert mass["counterevidence_line_ids"] == ["counter-line-1"]
    assert "dependent_evidence_collapsed" in mass["limiting_deficits"]


def test_independence_map_rejects_collapsed_cluster_without_reasons() -> None:
    valid = build_evidence_independence_map(
        [_evidence_line(cluster=0, index=0), _evidence_line(cluster=0, index=1)],
        portfolio_designs=[_portfolio_design()],
        method_consensus_reports=_consensus_reports(),
        method_equivalence_reports=_equivalence_reports(),
        map_id="independence-map-rec-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )
    invalid = deepcopy(valid)
    invalid["collapse_clusters"][0].pop("collapse_reasons")

    with pytest.raises(
        EvidenceIndependenceError,
        match="policy_design_independence_collapse_reasons_missing",
    ):
        validate_evidence_independence_map_record(
            invalid,
            evidence_lines=[
                _evidence_line(cluster=0, index=0),
                _evidence_line(cluster=0, index=1),
            ],
            portfolio_designs=[_portfolio_design()],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_independence_map_keeps_graded_weights_behind_feature_flag_and_config() -> None:
    valid = build_evidence_independence_map(
        [_evidence_line(cluster=0, index=0)],
        portfolio_designs=[_portfolio_design()],
        method_consensus_reports=_consensus_reports(),
        method_equivalence_reports=_equivalence_reports(),
        map_id="independence-map-rec-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )
    invalid = deepcopy(valid)
    invalid["graded_independence"] = {
        "enabled": True,
        "feature_flag": "policy_design_case.graded_independence_weights",
        "feature_flag_enabled": False,
        "authority_posture": "advisory_only",
        "governed_config": {
            "owner": "team-science-quality",
            "version": "2026-05-17.provisional",
            "status": "provisional",
        },
    }

    with pytest.raises(
        EvidenceIndependenceError,
        match="policy_design_independence_graded_feature_flag_disabled",
    ):
        validate_evidence_independence_map_record(invalid)


def test_independence_map_classifies_rare_domain_scarcity_without_support_inflation() -> None:
    independence_map = build_evidence_independence_map(
        [_evidence_line(cluster=0, index=0)],
        portfolio_designs=[_portfolio_design()],
        method_consensus_reports=_consensus_reports(),
        method_equivalence_reports=_equivalence_reports(),
        map_id="independence-map-rec-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
        rare_domain_context={
            "scarcity_kind": "scarcity_structural",
            "limitation_ref": sha("rare-domain-limitation"),
            "monitoring_plan_ref": sha("rare-domain-monitoring"),
            "minimum_effective_independent_evidence_count": 3,
        },
    )

    scarcity = independence_map["rare_domain_scarcity"]
    assert scarcity["status"] == "scarcity_structural"
    assert scarcity["support_inflation_allowed"] is False
    assert scarcity["effective_support_mass_after_scarcity"] == 1.0
    assert "scarcity_structural" in independence_map["effective_mass_report"][
        "limiting_deficits"
    ]

    invalid = deepcopy(independence_map)
    invalid["rare_domain_scarcity"]["effective_support_mass_after_scarcity"] = 3.0
    with pytest.raises(
        EvidenceIndependenceError,
        match="policy_design_independence_scarcity_support_inflation",
    ):
        validate_evidence_independence_map_record(invalid)


def test_independence_map_rejects_raw_count_without_effective_count() -> None:
    valid = build_evidence_independence_map(
        [_evidence_line(cluster=0, index=0)],
        portfolio_designs=[_portfolio_design()],
        method_consensus_reports=_consensus_reports(),
        method_equivalence_reports=_equivalence_reports(),
        map_id="independence-map-rec-1",
        producer_execution_started_at="2026-05-17T09:00:00+00:00",
    )
    invalid = deepcopy(valid)
    invalid.pop("effective_independent_evidence_count")

    with pytest.raises(
        EvidenceIndependenceError,
        match="policy_design_independence_effective_count_missing",
    ):
        validate_evidence_independence_map_record(
            invalid,
            evidence_lines=[_evidence_line(cluster=0, index=0)],
            portfolio_designs=[_portfolio_design()],
            producer_execution_started_at="2026-05-17T09:00:00+00:00",
        )


def test_independence_map_json_schema_requires_raw_and_effective_counts() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == INDEPENDENCE_MAP_SCHEMA_VERSION
    assert set(schema["required"]) >= {
        "raw_evidence_line_count",
        "effective_independent_evidence_count",
        "collapse_clusters",
        "effective_mass_report",
        "graded_independence",
        "rare_domain_scarcity",
    }
    assert "collapse_reasons" in schema["properties"]["collapse_clusters"]["items"][
        "properties"
    ]
