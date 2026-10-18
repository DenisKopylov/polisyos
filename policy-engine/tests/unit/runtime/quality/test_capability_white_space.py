from __future__ import annotations

# ruff: noqa: S101
from collections import Counter, defaultdict
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

    assert result.capability_index is not None
    source_nodes = result.capability_index.white_space
    expected_constructs = {
        "corrected_firm_panels_registration_code_period_id_arrears_amount_debt_amount_region_code_agent_id_source_snapshot_id_schema_version_record_hash_selection_term_corrected_exit_bias",
        "firm_fundamentals",
        "fixture_effect",
        "fixture_survival_ukraine_firm_fundamentals_annual_panel",
        "logistics_friction",
        "logistics_mobility_displacement_cell_id_region_code_mobility_pressure_period_id",
        "survival_hazard_estimates_duration_event_risk_signal_wage_arrears",
    }
    source_constructs = {node.construct_id for node in source_nodes}
    assert source_constructs == expected_constructs

    report = build_capability_white_space_report_from_duckdb(result.primary_duckdb_path)

    assert report["schema_version"] == "policyos.capability_white_space_report.v1"
    assert report["validation"]["status"] == "pass"
    assert report["summary"]["construct_count"] == 7
    assert report["groupings"] == {
        "by_construct": _expected_grouping(source_nodes, "construct_id"),
        "by_domain": _expected_grouping(source_nodes, "domain"),
        "by_authority_posture": _expected_grouping(source_nodes, "authority_posture"),
        "by_producer_owner": _expected_grouping(source_nodes, "producer_owner"),
    }
    expected_groups = _expected_composite_groups(source_nodes)
    actual_groups = {
        (
            row["construct"],
            row["domain"],
            row["authority_posture"],
            row["producer_owner"],
        ): row
        for row in report["groups"]
    }
    assert set(actual_groups) == set(expected_groups)
    for key, failure_ids in expected_groups.items():
        assert actual_groups[key]["count"] == len(failure_ids)
        assert actual_groups[key]["failure_ids"] == sorted(failure_ids)


def test_controlled_credit_candidate_routes_are_consumed_without_authority_promotion() -> None:
    failure_mode, candidate_strategies = _controlled_credit_candidate_routes()
    report = build_capability_white_space_report(
        failure_modes=(failure_mode,),
        acquisition_strategies=candidate_strategies,
    )
    expected_ids = {
        "acquisition:acquire_from_nbu_registry",
        "acquisition:derive_proxy_from_tax_relief_records",
        "acquisition:simulation_only_dynamic_treatment",
    }
    report_strategies = {row["strategy_id"]: row for row in report["acquisition_strategies"]}

    # These supplied rows exercise consumers, not the fixture compiler's producer.
    assert report["validation"]["status"] == "pass"
    assert set(report_strategies) == expected_ids
    assert set(failure_mode.acquisition_strategy_refs) == expected_ids
    assert report["groupings"]["by_construct"]["credit_program_enrollment"]["count"] == 1
    assert set(report["groups"][0]["acquisition_strategy_refs"]) == expected_ids

    direct = report_strategies["acquisition:acquire_from_nbu_registry"]
    proxy = report_strategies["acquisition:derive_proxy_from_tax_relief_records"]
    simulation = report_strategies["acquisition:simulation_only_dynamic_treatment"]
    assert direct["resulting_authority_envelope"] == {
        "research": "admissible",
        "governed_pilot": "admissible",
        "production": "admissible_after_construct_validity_review",
    }
    assert proxy["resulting_authority_envelope"] == {
        "research": "context_only",
        "governed_pilot": "blocked_acquisition_required",
        "production": "blocked_acquisition_required",
    }
    assert simulation["resulting_authority_envelope"] == {
        "research": "advisory_context_only",
        "governed_pilot": "advisory_context_only",
        "production": "blocked_simulation_only",
    }
    assert (
        len(
            {
                tuple(sorted(row["resulting_authority_envelope"].items()))
                for row in report_strategies.values()
            }
        )
        == 3
    )
    for strategy in report_strategies.values():
        assert strategy["owner_team"]
        assert strategy["estimated_cost"]
        assert strategy["estimated_time"]
        assert strategy["prerequisites"]
        assert strategy["contact_path"]
        assert strategy["ttl"]
        assert strategy["review_cadence"]
        assert strategy["escalation_owner"]

    resolver = RequirementToCapabilityResolver(
        capabilities=(),
        failure_modes=(failure_mode,),
        acquisition_strategies=candidate_strategies,
        capability_index_ref="capability-index:controlled-candidate-fixture",
    )
    result = resolver.resolve(
        RequirementToCapabilityQuery(
            requirement_id="data-requirement:credit-program-enrollment",
            construct="credit_program_enrollment",
            entity_scope="firm_or_program",
            population_filter={"type": "msme"},
            geography="UA",
            authority_level="production",
            claim_use="claim_evidence_closeout",
        )
    )

    assert result.status == "blocked_acquisition_required"
    assert result.selected_capability_ref is None
    assert result.satisfies_claim_evidence is False
    assert {row["strategy_id"] for row in result.acquisition_strategies} == expected_ids


def test_simulation_only_candidate_is_rejected_for_production_claim_evidence() -> None:
    failure_mode, candidate_strategies = _controlled_credit_candidate_routes()
    simulation_strategy = next(
        strategy
        for strategy in candidate_strategies
        if strategy.strategy_id == "acquisition:simulation_only_dynamic_treatment"
    )
    simulation_failure = failure_mode.model_copy(
        update={"acquisition_strategy_refs": (simulation_strategy.strategy_id,)}
    )
    simulation_capability = EvidenceCapability(
        capability_id="capability:credit_program_enrollment_simulation_candidate",
        construct="credit_program_enrollment",
        modality=("simulation_state",),
        evidence_mode="simulation_only",
        concept_spine_refs=("concept:credit_program_enrollment",),
        scope=CapabilityScope(
            geography="UA",
            entity_scope="firm_or_program",
            population="msme",
        ),
        identification_mode="simulation_only",
        trust_tier="simulation_context",
        quality_score=QualityScore(composite=0.95, breakdown={"simulation_fit": 0.95}),
        source_assets=(),
        authority_envelope=AuthorityEnvelope(
            research="advisory_context_only",
            governed_pilot="blocked_simulation_only",
            production="admissible",
            authoritative_for=("production_claim_evidence",),
        ),
        freshness_envelope=FreshnessEnvelope(freshness_class="synthetic"),
        rights_envelope=RightsEnvelope(access_class="internal"),
    )
    resolver = RequirementToCapabilityResolver(
        capabilities=(simulation_capability,),
        failure_modes=(simulation_failure,),
        acquisition_strategies=(simulation_strategy,),
        capability_index_ref="capability-index:simulation-negative-control",
    )

    result = resolver.resolve(
        RequirementToCapabilityQuery(
            requirement_id="data-requirement:credit-program-enrollment",
            construct="credit_program_enrollment",
            entity_scope="firm_or_program",
            population_filter={"type": "msme"},
            geography="UA",
            authority_level="production",
            claim_use="claim_evidence_closeout",
        )
    )

    assert result.status.startswith("blocked_")
    assert result.selected_capability_ref is None
    assert result.satisfies_claim_evidence is False
    assert any(
        row["capability_ref"] == simulation_capability.capability_id
        and row["rejection_reason"] == "evidence_mode_forbidden"
        for row in result.rejected_alternatives
    )


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
                    detected_at="controlled-test-candidate",
                    status="blocked_construct_not_observed",
                    gap_type="construct_gap",
                    domain=("uncategorized",),
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


def _controlled_credit_candidate_routes() -> tuple[
    FailureModeNode,
    tuple[AcquisitionStrategy, ...],
]:
    """Build supplied candidate rows for the white-space report/resolver consumers.

    These rows exercise typed consumers; they are not emitted by the fixture compiler.
    Their route envelopes and lifecycle values are supplied test data, not verified active
    status or producer provenance.
    """

    strategies = (
        AcquisitionStrategy(
            strategy_id="acquisition:acquire_from_nbu_registry",
            target_construct="credit_program_enrollment",
            owner=("team-data-acquisition", "team-legal-counsel"),
            authority_class="government_official_request",
            estimated_cost="low_dollar_amount",
            estimated_time="30_days",
            prerequisites=("NBU FOI request approval", "Legal review of data-use scope"),
            resulting_authority_envelope={
                "research": "admissible",
                "governed_pilot": "admissible",
                "production": "admissible_after_construct_validity_review",
            },
            contact_path="ops://team-data-acquisition#acquisitions",
            owner_team="team-data-acquisition",
            legal_counsel_owner="team-legal-counsel",
            ttl="P30D",
            review_cadence="P14D",
            escalation_owner="team-data-acquisition",
            requires_construct_validity_review=True,
        ),
        AcquisitionStrategy(
            strategy_id="acquisition:derive_proxy_from_tax_relief_records",
            target_construct="credit_program_enrollment",
            owner=("team-data-acquisition",),
            authority_class="proxy_with_degraded_authority",
            estimated_cost="low_dollar_amount",
            estimated_time="30_days",
            prerequisites=("legal_use_scope_review", "producer_handshake"),
            resulting_authority_envelope={
                "research": "context_only",
                "governed_pilot": "blocked_acquisition_required",
                "production": "blocked_acquisition_required",
            },
            contact_path="ops://team-data-acquisition#acquisitions",
            owner_team="team-data-acquisition",
            ttl="P30D",
            review_cadence="P14D",
            escalation_owner="team-data-acquisition",
            requires_construct_validity_review=True,
        ),
        AcquisitionStrategy(
            strategy_id="acquisition:simulation_only_dynamic_treatment",
            target_construct="credit_program_enrollment",
            owner=("team-data-acquisition",),
            authority_class="simulation_only",
            estimated_cost="low_dollar_amount",
            estimated_time="30_days",
            prerequisites=("explicit_simulation_only_scope",),
            resulting_authority_envelope={
                "research": "advisory_context_only",
                "governed_pilot": "advisory_context_only",
                "production": "blocked_simulation_only",
            },
            contact_path="ops://team-data-acquisition#acquisitions",
            owner_team="team-data-acquisition",
            ttl="P30D",
            review_cadence="P14D",
            escalation_owner="team-data-acquisition",
            requires_construct_validity_review=False,
        ),
    )
    failure_mode = FailureModeNode(
        failure_id="failure:construct_not_observed:credit_program_enrollment:UA",
        construct="credit_program_enrollment",
        geography="UA",
        cause_class="construct_not_observed",
        severity="blocking_production",
        owner="team-data-acquisition",
        acquisition_strategy_refs=tuple(strategy.strategy_id for strategy in strategies),
        affected_authority_postures=("governed_pilot", "production"),
        detected_at="controlled-test-candidate",
        status="blocked_construct_not_observed",
        gap_type="construct_gap",
        domain=("uncategorized",),
        producer_owner="team-data-acquisition",
        authority_posture="production",
    )
    return failure_mode, strategies


def _expected_grouping(
    nodes: tuple[FailureModeNode, ...],
    dimension: str,
) -> dict[str, dict[str, object]]:
    grouped_ids: dict[str, set[str]] = defaultdict(set)
    counts: Counter[str] = Counter()
    for node in nodes:
        if dimension == "domain":
            values = node.domain or ("uncategorized",)
        elif dimension == "producer_owner":
            values = (node.producer_owner or node.owner,)
        else:
            values = (str(getattr(node, dimension)),)
        for value in values:
            grouped_ids[value].add(node.failure_id)
            counts[value] += 1
    return {
        key: {"count": counts[key], "failure_ids": sorted(grouped_ids[key])}
        for key in sorted(grouped_ids)
    }


def _expected_composite_groups(
    nodes: tuple[FailureModeNode, ...],
) -> dict[tuple[str, str, str, str], set[str]]:
    grouped_ids: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    for node in nodes:
        for domain in node.domain or ("uncategorized",):
            key = (
                node.construct_id,
                domain,
                node.authority_posture,
                node.producer_owner or node.owner,
            )
            grouped_ids[key].add(node.failure_id)
    return dict(grouped_ids)


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
