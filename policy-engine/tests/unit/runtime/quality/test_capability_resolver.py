from __future__ import annotations

# ruff: noqa: S101
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from polisyos.runtime.quality.capability_index import (
    AcquisitionStrategy,
    AuthorityEnvelope,
    CapabilityConflictRecord,
    CapabilityScope,
    CapabilitySourceAsset,
    EvidenceCapability,
    FailureModeNode,
    FreshnessEnvelope,
    QualityScore,
    RightsEnvelope,
)
from polisyos.runtime.quality.capability_resolver import (
    REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS,
    RequirementToCapabilityQuery,
    RequirementToCapabilityResolver,
)
from polisyos.runtime.quality.hypothesis_ledger import HypothesisLedger


def test_resolver_ranks_exact_observed_before_derived_proxy_and_records_rejections() -> None:
    resolver = RequirementToCapabilityResolver(
        capabilities=(
            _capability(
                capability_id="capability:firm_survival_proxy",
                evidence_mode="proxy_observational",
                identification_mode="proxy_identified",
                trust_tier="derived_proxy",
                construct_validity=0.7,
            ),
            _capability(
                capability_id="capability:firm_survival_exact",
                evidence_mode="observed",
                identification_mode="point_identified",
                trust_tier="authoritative_high_coverage",
                construct_validity=0.95,
            ),
            _capability(
                capability_id="capability:firm_survival_derived",
                evidence_mode="derived",
                identification_mode="partially_identified",
                trust_tier="authoritative_partial_coverage",
                construct_validity=0.9,
            ),
        ),
        capability_index_ref="capability-index:test-fixture",
    )

    result = resolver.resolve(_query())

    assert result.status == "selected_exact"
    assert result.selected_capability_ref == "capability:firm_survival_exact"
    assert result.construct_ref == "construct:firm_survival"
    assert result.capability_index_ref == "capability-index:test-fixture"
    assert {item["capability_ref"] for item in result.rejected_alternatives} == {
        "capability:firm_survival_derived",
        "capability:firm_survival_proxy",
    }
    assert all(item["rejection_reason"] for item in result.rejected_alternatives)
    assert all(item["rejection_severity"] for item in result.rejected_alternatives)


def test_unobserved_construct_returns_owned_acquisition_strategy() -> None:
    resolver = RequirementToCapabilityResolver(
        capabilities=(),
        failure_modes=(
            FailureModeNode(
                failure_id="failure:credit_program_enrollment:UA",
                construct="credit_program_enrollment",
                geography="UA",
                cause_class="data_source_unavailable",
                severity="blocking_governed_pilot",
                owner="team-data-acquisition",
                acquisition_strategy_refs=("acquisition:credit_registry:UA",),
                affected_authority_postures=("governed_pilot", "production"),
                detected_at="2026-05-25",
            ),
        ),
        acquisition_strategies=(
            AcquisitionStrategy(
                strategy_id="acquisition:credit_registry:UA",
                target_construct="credit_program_enrollment",
                owner=("team-data-acquisition", "team-legal-counsel"),
                authority_class="government_official_request",
                estimated_cost="low_dollar_amount",
                estimated_time="30_days",
                prerequisites=("legal_use_scope_review",),
                resulting_authority_envelope={
                    "governed_pilot": "admissible_after_review",
                    "production": "admissible_after_construct_validity_review",
                },
                contact_path="ops://team-data-acquisition#acquisitions",
            ),
        ),
        capability_index_ref="capability-index:test-fixture",
    )

    result = resolver.resolve(
        _query(
            requirement_id="data-requirement:credit-enrollment",
            construct="credit_program_enrollment",
            entity_scope="firm_or_program",
        )
    )

    assert result.status == "blocked_acquisition_required"
    assert result.selected_capability_ref is None
    assert "acquisition_required" in result.blocked_reasons
    assert result.acquisition_strategies[0]["strategy_id"] == "acquisition:credit_registry:UA"


def test_resolver_does_not_fabricate_credit_strategies_when_index_records_are_missing() -> None:
    resolver = RequirementToCapabilityResolver(
        capabilities=(),
        failure_modes=(
            FailureModeNode(
                failure_id="failure:credit_program_enrollment:UA",
                construct="credit_program_enrollment",
                geography="UA",
                cause_class="construct_not_observed",
                severity="blocking_production",
                owner="team-data-acquisition",
                acquisition_strategy_refs=(
                    "acquisition:acquire_from_nbu_registry",
                    "acquisition:derive_proxy_from_tax_relief_records",
                    "acquisition:simulation_only_dynamic_treatment",
                ),
                affected_authority_postures=("production",),
                detected_at="2026-05-25",
                status="blocked_construct_not_observed",
                gap_type="construct_gap",
            ),
        ),
        acquisition_strategies=(),
        capability_index_ref="capability-index:missing-strategies",
    )

    result = resolver.resolve(
        _query(
            requirement_id="data-requirement:credit-enrollment",
            construct="credit_program_enrollment",
            entity_scope="firm_or_program",
            authority_level="production",
        )
    )

    assert result.status == "blocked_construct_not_observed"
    assert result.acquisition_strategies == ()


def test_construct_conflict_marker_survives_resolver_selection() -> None:
    resolver = RequirementToCapabilityResolver(
        capabilities=(_capability(capability_id="capability:firm_survival_exact"),),
        conflicts=(
            CapabilityConflictRecord(
                conflict_id="conflict:firm_survival:empirical",
                construct="firm_survival",
                geography="UA",
                conflict_class="empirical",
                conflict_resolution_route="new_evidence",
                capability_refs=("capability:firm_survival_exact",),
            ),
        ),
        capability_index_ref="capability-index:test-fixture",
    )

    result = resolver.resolve(_query())

    assert result.status == "selected_with_conflict_marker"
    assert result.authority_envelope_result == "contested"
    assert result.conflict_markers[0]["conflict_id"] == "conflict:firm_survival:empirical"
    assert result.satisfies_claim_evidence is False


def test_population_filter_mismatch_is_rejected_before_selection() -> None:
    resolver = RequirementToCapabilityResolver(
        capabilities=(
            _capability(
                capability_id="capability:firm_survival_households",
                population="households",
            ),
        ),
        capability_index_ref="capability-index:test-fixture",
    )

    result = resolver.resolve(_query(population_filter={"type": "msme"}))

    assert result.status.startswith("blocked_")
    assert result.selected_capability_ref is None
    assert result.rejected_alternatives[0]["capability_ref"] == (
        "capability:firm_survival_households"
    )
    assert result.rejected_alternatives[0]["rejection_reason"] == (
        "population_filter_mismatch"
    )
    assert result.rejected_alternatives[0]["rejection_severity"] == "hard"


def test_llm_candidate_cannot_satisfy_selected_exact() -> None:
    ledger = HypothesisLedger.model_validate(
        {
            "run_id": "run-phase4",
            "job_id": "job-phase4",
            "entries": [
                {
                    "candidate_id": "candidate:llm-credit-registry",
                    "candidate_ref": "candidate:capability:credit_program_registry",
                    "source_class": "llm_candidate",
                    "candidate_kind": "candidate_capability",
                    "target_authority_slots": ["data_authority"],
                    "tool_refs": ["tool:formulator"],
                    "repair_decision_lineage": ["repair:phase4"],
                    "prompt_fingerprint": "sha256:phase4",
                    "content": {
                        "construct": "credit_program_enrollment",
                        "capability_ref": "capability:llm_credit_registry",
                    },
                }
            ],
        }
    )
    resolver = RequirementToCapabilityResolver(
        capabilities=(
            _capability(
                capability_id="capability:llm_credit_registry",
                construct="credit_program_enrollment",
                modality=("llm_candidate",),
                evidence_mode="candidate_unverified",
                source_assets=(),
                metadata={"llm_derived_construct": True, "producer_backed": False},
            ),
        ),
        capability_index_ref="capability-index:test-fixture",
    )

    result = resolver.resolve(
        _query(
            requirement_id="data-requirement:credit-enrollment",
            construct="credit_program_enrollment",
            entity_scope="firm_or_program",
        ),
        hypothesis_ledger=ledger,
    )

    assert result.status.startswith("blocked_")
    assert result.status not in {"selected_exact", "selected_derived"}
    assert result.satisfies_claim_evidence is False
    assert result.reviewer_queue[0]["admission_state"] == "candidate_unverified"
    assert result.reviewer_queue[0]["candidate_ref"] == (
        "candidate:capability:credit_program_registry"
    )
    assert result.rejected_alternatives[0]["rejection_reason"] == "llm_candidate_unverified"


@pytest.mark.property
@settings(max_examples=35, suppress_health_check=[HealthCheck.too_slow])
@given(
    construct=st.sampled_from(
        ["firm_survival", "credit_program_enrollment", "regional_displacement_pressure"]
    ),
    geography=st.sampled_from(["UA", "PL"]),
    authority_level=st.sampled_from(["research", "governed_pilot", "production"]),
)
def test_every_query_returns_selected_or_typed_blocked_with_reason(
    construct: str,
    geography: str,
    authority_level: str,
) -> None:
    resolver = RequirementToCapabilityResolver.default_fixture()

    result = resolver.resolve(
        _query(
            requirement_id=f"data-requirement:{construct}:{geography}:{authority_level}",
            construct=construct,
            geography=geography,
            authority_level=authority_level,
        )
    )

    assert result.status.startswith(("selected_", "blocked_"))
    assert result.blocked_reasons or result.binding_reasons
    assert result.status != "blocked"


def test_cross_modal_traceability_uses_same_construct_and_capability_index_ref() -> None:
    resolver = RequirementToCapabilityResolver(
        capabilities=(
            _capability(
                capability_id="capability:firm_survival_data",
                modality=("fabric_data",),
                evidence_mode="observed",
            ),
            _capability(
                capability_id="capability:firm_survival_scholar",
                modality=("scholar_claim",),
                evidence_mode="scholarly_causal_support",
                entity_scope="construct_pair",
            ),
        ),
        capability_index_ref="capability-index:test-fixture",
    )

    data = resolver.resolve(
        _query(required_modalities=("fabric_data",), claim_use="claim_evidence_closeout")
    )
    scholar = resolver.resolve(
        _query(
            required_modalities=("scholar_claim",),
            required_evidence_modes=("scholarly_causal_support",),
            claim_use="method_support",
            entity_scope="construct_pair",
        )
    )

    assert data.construct_ref == scholar.construct_ref == "construct:firm_survival"
    assert data.capability_index_ref == scholar.capability_index_ref == (
        "capability-index:test-fixture"
    )


def test_required_scenario_family_mappings_are_exact_phase4_contract() -> None:
    assert REQUIRED_SCENARIO_FAMILY_CONSTRUCT_MAPPINGS == {
        "production_msme_panel": "firm_survival",
        "regional_displacement_indicators": "regional_displacement_pressure",
        "credit_program_registry": "credit_program_enrollment",
    }


def _query(**overrides: Any) -> RequirementToCapabilityQuery:
    payload: dict[str, Any] = {
        "requirement_id": "data-requirement:firm-survival",
        "construct": "firm_survival",
        "entity_scope": "firm",
        "population_filter": {"type": "msme"},
        "geography": "UA",
        "time_window": {"start": "2022-02-01", "end": None},
        "authority_level": "governed_pilot",
        "claim_use": "claim_evidence_closeout",
        "required_evidence_modes": ("observed", "derived", "proxy_observational"),
        "forbidden_evidence_modes": ("simulation_only", "candidate_unverified"),
    }
    payload.update(overrides)
    return RequirementToCapabilityQuery.model_validate(payload)


def _capability(
    *,
    capability_id: str = "capability:firm_survival_exact",
    construct: str = "firm_survival",
    modality: tuple[str, ...] = ("fabric_data",),
    evidence_mode: str = "observed",
    geography: str = "UA",
    entity_scope: str = "firm",
    identification_mode: str = "point_identified",
    trust_tier: str = "authoritative_high_coverage",
    construct_validity: float = 0.95,
    population: str = "registered_firms",
    source_assets: tuple[CapabilitySourceAsset, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EvidenceCapability:
    assets = source_assets
    if assets is None:
        assets = (
            CapabilitySourceAsset(
                ref=f"asset:{capability_id}",
                source_layer="L4",
                asset_type="parquet",
                role="observation",
            ),
        )
    return EvidenceCapability(
        capability_id=capability_id,
        construct=construct,
        modality=modality,
        evidence_mode=evidence_mode,
        concept_spine_refs=(f"concept:{construct}",),
        scope=CapabilityScope(
            geography=geography,
            entity_scope=entity_scope,
            population=population,
            schema_regime="ukraine_schema_v2",
            time_start="2022-02-01",
        ),
        identification_mode=identification_mode,
        trust_tier=trust_tier,
        quality_score=QualityScore(
            composite=construct_validity,
            breakdown={"construct_validity": construct_validity},
        ),
        source_assets=assets,
        authority_envelope=AuthorityEnvelope(
            research="admissible",
            governed_pilot="admissible",
            production="admissible",
            authoritative_for=("claim_evidence",),
        ),
        lineage_refs=(f"lineage:{capability_id}",),
        freshness_envelope=FreshnessEnvelope(freshness_class="fresh_for_governed_pilot"),
        rights_envelope=RightsEnvelope(access_class="government_administrative"),
        metadata=metadata or {},
    )
