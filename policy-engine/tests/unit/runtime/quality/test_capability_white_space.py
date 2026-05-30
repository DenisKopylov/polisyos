from __future__ import annotations

# ruff: noqa: S101
from pathlib import Path

import pytest

from polisyos.runtime.quality.capability_index import (
    AcquisitionStrategy,
    AuthorityEnvelope,
    CapabilityScope,
    CapabilitySourceAsset,
    EvidenceCapability,
    FailureModeNode,
    FreshnessEnvelope,
    QualityScore,
    RightsEnvelope,
)
from polisyos.runtime.quality.capability_index_compiler import (
    CapabilityIndexCompilerConfig,
    build_white_space_nodes,
    compile_capability_index,
    create_capability_index_fixture_inputs,
)
from polisyos.runtime.quality.capability_resolver import (
    RequirementToCapabilityQuery,
    RequirementToCapabilityResolver,
)
from polisyos.runtime.quality.capability_white_space import (
    WhiteSpaceValidationError,
    build_capability_white_space_report,
    build_capability_white_space_report_from_duckdb,
)


def test_fixture_white_space_report_groups_by_construct_domain_authority_and_owner(
    tmp_path: Path,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "out",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )

    report = build_capability_white_space_report_from_duckdb(result.primary_duckdb_path)

    assert report["schema_version"] == "policyos.capability_white_space_report.v1"
    assert report["validation"]["status"] == "pass"
    assert report["groupings"]["by_construct"]["credit_program_enrollment"]["count"] >= 1
    assert report["groupings"]["by_domain"]["msme_credit"]["count"] >= 1
    assert report["groupings"]["by_authority_posture"]["production"]["count"] >= 1
    assert report["groupings"]["by_producer_owner"]["team-data-acquisition"]["count"] >= 1
    assert report["groups"], "missing construct/domain/posture/owner grouped rows must fail"


def test_credit_program_enrollment_has_three_owned_distinct_strategies(
    tmp_path: Path,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "out",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )

    report = build_capability_white_space_report_from_duckdb(result.primary_duckdb_path)
    strategies = {
        row["strategy_id"]: row
        for row in report["acquisition_strategies"]
        if row["target_construct"] == "credit_program_enrollment"
    }

    assert set(strategies) == {
        "acquisition:acquire_from_nbu_registry",
        "acquisition:derive_proxy_from_tax_relief_records",
        "acquisition:simulation_only_dynamic_treatment",
    }
    assert len(
        {
            tuple(sorted(strategy["resulting_authority_envelope"].items()))
            for strategy in strategies.values()
        }
    ) == 3
    for strategy in strategies.values():
        assert strategy["owner_team"]
        assert strategy["estimated_cost"]
        assert strategy["estimated_time"]
        assert strategy["prerequisites"]
        assert strategy["contact_path"]
        assert strategy["ttl"]
        assert strategy["review_cadence"]
        assert strategy["escalation_owner"]
        if strategy["authority_class"] == "government_official_request":
            assert strategy["legal_counsel_owner"]


def test_acquisition_strategy_without_owner_fails_validation() -> None:
    with pytest.raises(ValueError, match="owner"):
        AcquisitionStrategy(
            strategy_id="acquisition:ownerless",
            target_construct="credit_program_enrollment",
            owner=(),
            authority_class="government_official_request",
            estimated_cost="low_dollar_amount",
            estimated_time="30_days",
            prerequisites=("legal_use_scope_review",),
            resulting_authority_envelope={
                "research": "admissible",
                "governed_pilot": "admissible_after_review",
                "production": "admissible_after_construct_validity_review",
            },
            contact_path="ops://team-data-acquisition#acquisitions",
        )


def test_production_admissible_strategy_requires_construct_validity_review() -> None:
    with pytest.raises(ValueError, match="requires_construct_validity_review"):
        AcquisitionStrategy(
            strategy_id="acquisition:unsafe-production",
            target_construct="credit_program_enrollment",
            owner=("team-data-acquisition", "team-legal-counsel"),
            authority_class="government_official_request",
            estimated_cost="low_dollar_amount",
            estimated_time="30_days",
            prerequisites=("legal_use_scope_review",),
            resulting_authority_envelope={
                "research": "admissible",
                "governed_pilot": "admissible_after_review",
                "production": "admissible",
            },
            contact_path="ops://team-data-acquisition#acquisitions",
            requires_construct_validity_review=False,
        )


def test_orphan_failure_mode_strategy_ref_fails_validation() -> None:
    with pytest.raises(WhiteSpaceValidationError, match="orphan acquisition_strategy_ref"):
        build_capability_white_space_report(
            failure_modes=(
                FailureModeNode(
                    failure_id="failure:construct_not_observed:credit_program_enrollment:UA",
                    construct="credit_program_enrollment",
                    geography="UA",
                    cause_class="construct_gap",
                    severity="blocking_production",
                    owner="team-data-acquisition",
                    acquisition_strategy_refs=("acquisition:missing",),
                    affected_authority_postures=("production",),
                    detected_at="2026-05-25",
                    status="blocked_construct_not_observed",
                    gap_type="construct_gap",
                    domain=("msme_credit",),
                    producer_owner="team-data-acquisition",
                    authority_posture="production",
                ),
            ),
            acquisition_strategies=(),
        )


def test_white_space_nodes_distinguish_rights_freshness_sample_validity_and_legal_gaps() -> None:
    nodes = build_white_space_nodes(
        (
            _capability(
                capability_id="capability:rights-gap",
                rights=RightsEnvelope(
                    access_class="government_administrative",
                    claim_evidence_use_allowed=False,
                ),
                production_authority="blocked_rights_boundary",
            ),
            _capability(
                capability_id="capability:freshness-gap",
                freshness=FreshnessEnvelope(freshness_class="stale_release_snapshot"),
                production_authority="blocked_freshness",
            ),
            _capability(
                capability_id="capability:sample-gap",
                construct="regional_displacement_pressure",
                entity_scope="cell_or_region",
                row_count=1,
                production_authority="blocked_construct_validity_below_floor",
            ),
            _capability(
                capability_id="capability:validity-gap",
                construct_validity=0.4,
                production_authority="blocked_construct_validity_below_floor",
            ),
            _capability(
                capability_id="capability:legal-gap",
                production_authority="blocked_legal_authority_missing",
            ),
        )
    )

    assert {node.gap_type for node in nodes} >= {
        "rights_gap",
        "freshness_gap",
        "sample_size_gap",
        "construct_validity_gap",
        "legal_authority_gap",
    }


def test_failure_mode_strategy_refs_are_reachable_from_resolver_output(
    tmp_path: Path,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "out",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )
    report = build_capability_white_space_report_from_duckdb(result.primary_duckdb_path)
    resolver = RequirementToCapabilityResolver.from_duckdb(result.primary_duckdb_path)

    for node in report["failure_modes"]:
        result = resolver.resolve(
            RequirementToCapabilityQuery(
                requirement_id=f"data-requirement:{node['construct']}",
                construct=node["construct"],
                entity_scope=_entity_scope_for_construct(node["construct"]),
                population_filter={"type": "msme"},
                geography=node["geography"],
                authority_level=node["authority_posture"],
                claim_use="claim_evidence_closeout",
            )
        )
        assert result.status.startswith("blocked_")
        resolver_strategy_refs = {row["strategy_id"] for row in result.acquisition_strategies}
        for strategy_ref in node["acquisition_strategy_refs"]:
            assert strategy_ref in resolver_strategy_refs


def _entity_scope_for_construct(construct: str) -> str:
    if construct == "regional_displacement_pressure":
        return "region"
    if construct == "credit_program_enrollment":
        return "firm_or_program"
    return "firm"


def _capability(
    *,
    capability_id: str,
    construct: str = "firm_survival",
    entity_scope: str = "firm",
    production_authority: str = "blocked_construct_validity_below_floor",
    construct_validity: float = 0.8,
    row_count: int = 100,
    freshness: FreshnessEnvelope | None = None,
    rights: RightsEnvelope | None = None,
) -> EvidenceCapability:
    return EvidenceCapability(
        capability_id=capability_id,
        construct=construct,
        modality=("fabric_data",),
        evidence_mode="observed",
        concept_spine_refs=(f"concept:{construct}",),
        scope=CapabilityScope(geography="UA", entity_scope=entity_scope),
        identification_mode="point_identified",
        trust_tier="authoritative_high_coverage",
        quality_score=QualityScore(
            composite=construct_validity,
            breakdown={"construct_validity": construct_validity},
        ),
        source_assets=(
            CapabilitySourceAsset(
                ref=f"asset:{capability_id}",
                source_layer="L4",
                asset_type="parquet",
                role="observation",
                row_count=row_count,
            ),
        ),
        authority_envelope=AuthorityEnvelope(
            research="admissible",
            governed_pilot="admissible",
            production=production_authority,
        ),
        freshness_envelope=freshness
        or FreshnessEnvelope(freshness_class="fresh_for_governed_pilot"),
        rights_envelope=rights or RightsEnvelope(access_class="government_administrative"),
    )
