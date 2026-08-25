from __future__ import annotations

# ruff: noqa: S101
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from polisyos.runtime.quality.capability_authority import (
    AUTHORITY_FACTOR_NAMES,
    CapabilityAuthorityContext,
    CapabilityAuthorityFactorName,
    CapabilityDiscoveryAuthorityResolver,
    compose_capability_authority,
)
from polisyos.runtime.quality.capability_index import (
    AuthorityEnvelope,
    CapabilityScope,
    CapabilitySourceAsset,
    EvidenceCapability,
    FreshnessEnvelope,
    QualityScore,
    RightsEnvelope,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "fixtures/capability_authority/mixed_outcomes_v1.json"
)


def test_discovery_authority_stays_bridge_missing_for_caller_shaped_binding() -> None:
    resolver = CapabilityDiscoveryAuthorityResolver(production_approval_resolver=None)
    context = CapabilityAuthorityContext(
        packet_ref="sha256:" + "1" * 64,
        tenant_id="tenant-a",
        run_id="run-a",
        expected_consumer="capability-discovery",
        expected_audience="REVIEWER",
        binding_claim={
            "capability_ref": "capability:method:generated",
            "content_digest": "sha256:" + "2" * 64,
            "authority_purpose": "review_capability_candidates",
            "expected_consumer": "capability-discovery",
            "expected_audience": "REVIEWER",
            "owner_signature_ref": "self-attested",
        },
    )

    result = resolver.resolve(
        capability_ref="capability:method:generated",
        content_digest="sha256:" + "2" * 64,
        authority_purpose="review_capability_candidates",
        audience="REVIEWER",
        context=context,
        observed_at=datetime(2026, 8, 25, tzinfo=UTC),
    )

    assert result.state == "bridge_missing"
    assert "not_established" in result.reason_codes
    assert "owner_binding_not_independently_verified" in result.reason_codes
    assert result.binding_ref is None
    assert result.currentness_ref is None


@pytest.mark.parametrize(
    ("binding_override", "expected_reason"),
    [
        ({"capability_ref": "capability:wrong"}, "owner_binding_resource_mismatch"),
        ({"content_digest": "sha256:" + "9" * 64}, "owner_binding_digest_mismatch"),
        ({"authority_purpose": "publish"}, "owner_binding_purpose_mismatch"),
        ({"expected_consumer": "wrong-consumer"}, "owner_binding_consumer_mismatch"),
        ({"expected_audience": "MACHINE"}, "owner_binding_audience_mismatch"),
        ({"expires_at": "2026-08-24T00:00:00+00:00"}, "owner_binding_expired"),
        ({"owner_signature_ref": ""}, "owner_binding_unsigned"),
    ],
)
def test_owner_binding_corruptions_remain_not_established(
    binding_override: dict[str, str],
    expected_reason: str,
) -> None:
    binding = {
        "capability_ref": "capability:method:generated",
        "content_digest": "sha256:" + "2" * 64,
        "authority_purpose": "review_capability_candidates",
        "expected_consumer": "capability-discovery",
        "expected_audience": "REVIEWER",
        "expires_at": "2026-08-26T00:00:00+00:00",
        "owner_signature_ref": "self-attested",
        **binding_override,
    }
    resolver = CapabilityDiscoveryAuthorityResolver(production_approval_resolver=None)
    result = resolver.resolve(
        capability_ref="capability:method:generated",
        content_digest="sha256:" + "2" * 64,
        authority_purpose="review_capability_candidates",
        audience="REVIEWER",
        context=CapabilityAuthorityContext(
            packet_ref="sha256:" + "1" * 64,
            tenant_id="tenant-a",
            run_id="run-a",
            expected_consumer="capability-discovery",
            expected_audience="REVIEWER",
            binding_claim=binding,
        ),
        observed_at=datetime(2026, 8, 25, tzinfo=UTC),
    )

    assert result.state == "bridge_missing"
    assert "not_established" in result.reason_codes
    assert expected_reason in result.reason_codes
    assert result.binding_ref is None


def _capability(
    *,
    capability_id: str = "capability:firm_survival_exact",
    construct: str = "firm_survival",
    modality: tuple[str, ...] = ("fabric_data",),
    evidence_mode: str = "observed",
    trust_tier: str = "authoritative_high_coverage",
    identification_mode: str = "point_identified",
    construct_validity: float = 0.95,
    schema_regime: str = "ukraine_schema_v2",
    freshness_class: str = "fresh_for_production",
    claim_evidence_use_allowed: bool = True,
    lineage_refs: tuple[str, ...] = ("source_snapshot:ua-20260410",),
    source_assets: tuple[CapabilitySourceAsset, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EvidenceCapability:
    assets = (
        source_assets
        if source_assets is not None
        else (
            CapabilitySourceAsset(
                ref=f"asset:{capability_id}",
                source_layer="L4",
                asset_type="parquet",
                role="observation",
            ),
        )
    )
    return EvidenceCapability(
        capability_id=capability_id,
        construct=construct,
        modality=modality,
        evidence_mode=evidence_mode,
        concept_spine_refs=(f"concept:{construct}",),
        scope=CapabilityScope(
            geography="UA",
            schema_regime=schema_regime,
            entity_scope="firm",
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
            may_not_use_for=(),
        ),
        lineage_refs=lineage_refs,
        freshness_envelope=FreshnessEnvelope(freshness_class=freshness_class),
        rights_envelope=RightsEnvelope(
            access_class="government_administrative",
            claim_evidence_use_allowed=claim_evidence_use_allowed,
        ),
        metadata=metadata or {},
    )


def test_exact_capability_composes_to_selected_exact_for_production() -> None:
    result = compose_capability_authority(
        _capability(),
        posture="production",
        claim_use="claim_evidence_closeout",
        required_schema_regime="ukraine_schema_v2",
    )

    assert result.status == "selected_exact"
    assert result.authority_envelope_result == "admissible"
    assert result.satisfies_claim_evidence is True
    assert result.minimum_factor.status == "pass"
    assert {factor.name for factor in result.factors} == set(AUTHORITY_FACTOR_NAMES)


@pytest.mark.parametrize(
    ("factor_name", "capability_kwargs", "context_kwargs", "expected_status"),
    [
        (
            "trust_tier",
            {"trust_tier": "weak_anchor"},
            {},
            "blocked_authority_boundary",
        ),
        (
            "identification_mode",
            {"identification_mode": "bounds_only"},
            {},
            "blocked_authority_boundary",
        ),
        (
            "construct_validity",
            {"construct_validity": 0.35},
            {},
            "blocked_construct_validity_below_floor",
        ),
        (
            "schema_regime",
            {"schema_regime": "prewar_schema_v1"},
            {"required_schema_regime": "ukraine_schema_v2"},
            "blocked_schema_regime_mismatch",
        ),
        (
            "time_scope",
            {"freshness_class": "stale_for_production"},
            {},
            "blocked_freshness",
        ),
        (
            "legal_authority",
            {"metadata": {"authority_factors": {"legal_authority": 0.0}}},
            {},
            "blocked_authority_boundary",
        ),
        (
            "rights_access",
            {"claim_evidence_use_allowed": False},
            {},
            "blocked_rights_boundary",
        ),
        (
            "effective_independence",
            {"metadata": {"authority_factors": {"effective_independence": 0.3}}},
            {},
            "selected_proxy_with_limitation",
        ),
        (
            "historical_prior",
            {"evidence_mode": "historical_prior", "modality": ("historical_pdc_artifact",)},
            {},
            "blocked_authority_boundary",
        ),
    ],
)
def test_each_authority_factor_can_degrade_or_block_binding(
    factor_name: CapabilityAuthorityFactorName,
    capability_kwargs: dict[str, Any],
    context_kwargs: dict[str, Any],
    expected_status: str,
) -> None:
    result = compose_capability_authority(
        _capability(**capability_kwargs),
        posture="production",
        claim_use="claim_evidence_closeout",
        **context_kwargs,
    )

    factor = result.factor_by_name(factor_name)
    assert factor.value < factor.threshold
    assert result.status == expected_status
    assert result.authority_envelope_result != "admissible"


@pytest.mark.property
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
@given(
    trust_tier=st.sampled_from(
        [
            "authoritative_high_coverage",
            "authoritative_partial_coverage",
            "administrative_noisy",
            "derived_proxy",
            "weak_anchor",
        ]
    ),
    identification_mode=st.sampled_from(
        ["point_identified", "partially_identified", "proxy_identified", "bounds_only"]
    ),
    construct_validity=st.sampled_from([0.75, 0.8, 0.9, 1.0]),
)
def test_simulation_only_cannot_satisfy_production_authority(
    trust_tier: str,
    identification_mode: str,
    construct_validity: float,
) -> None:
    result = compose_capability_authority(
        _capability(
            evidence_mode="simulation_only",
            modality=("simulation_state",),
            trust_tier=trust_tier,
            identification_mode=identification_mode,
            construct_validity=construct_validity,
            metadata={
                "authority_factors": {
                    "legal_authority": 1.0,
                    "rights_access": 1.0,
                    "effective_independence": 1.0,
                }
            },
        ),
        posture="production",
        claim_use="claim_evidence_closeout",
    )

    assert result.status == "blocked_authority_boundary"
    assert result.satisfies_claim_evidence is False
    assert "simulation_only_cannot_satisfy_production_claim_evidence" in result.blocked_reasons


@pytest.mark.property
@settings(max_examples=40, suppress_health_check=[HealthCheck.too_slow])
@given(
    factor_name=st.sampled_from(AUTHORITY_FACTOR_NAMES),
    value=st.floats(min_value=0.0, max_value=0.69, allow_nan=False, allow_infinity=False),
)
def test_capability_with_below_floor_factor_degrades(
    factor_name: CapabilityAuthorityFactorName,
    value: float,
) -> None:
    capability = _capability(
        metadata={"authority_factors": {factor_name: value}},
        claim_evidence_use_allowed=(factor_name != "rights_access"),
    )
    if factor_name == "historical_prior":
        capability = _capability(
            evidence_mode="observed",
            metadata={"authority_factors": {"historical_prior": value}},
        )

    result = compose_capability_authority(
        capability,
        posture="production",
        claim_use="claim_evidence_closeout",
    )

    assert result.factor_by_name(factor_name).value < result.factor_by_name(factor_name).threshold
    assert result.authority_envelope_result != "admissible"
    assert result.satisfies_claim_evidence is False


def test_context_only_cannot_satisfy_claim_evidence_closeout() -> None:
    result = compose_capability_authority(
        _capability(
            evidence_mode="context_only",
            trust_tier="weak_anchor",
            identification_mode="context_only",
        ),
        posture="governed_pilot",
        claim_use="claim_evidence_closeout",
    )

    assert result.status == "selected_context_only"
    assert result.satisfies_claim_evidence is False
    assert "context_only_cannot_satisfy_claim_evidence_closeout" in result.limitations


def test_historical_pdc_prior_cannot_satisfy_current_claim_evidence() -> None:
    result = compose_capability_authority(
        _capability(
            evidence_mode="historical_prior",
            modality=("historical_pdc_artifact",),
            capability_id="capability:historical_prior_only",
        ),
        posture="production",
        claim_use="claim_evidence_closeout",
    )

    assert result.status == "blocked_authority_boundary"
    assert result.satisfies_claim_evidence is False
    assert "historical_prior_firewall_current_claim_evidence" in result.blocked_reasons


def test_llm_candidate_cannot_satisfy_evidence_without_producer_backed_capability() -> None:
    result = compose_capability_authority(
        _capability(
            capability_id="capability:llm_construct_candidate",
            modality=("llm_candidate",),
            evidence_mode="candidate_unverified",
            source_assets=(),
            metadata={"llm_derived_construct": True, "producer_backed": False},
        ),
        posture="governed_pilot",
        claim_use="claim_evidence_closeout",
    )

    assert result.status == "blocked_authority_boundary"
    assert result.satisfies_claim_evidence is False
    assert "llm_candidate_without_producer_backing" in result.blocked_reasons


def test_authority_factor_metadata_cannot_raise_canonical_rights_boundary() -> None:
    result = compose_capability_authority(
        _capability(
            capability_id="capability:rights_override_attempt",
            claim_evidence_use_allowed=False,
            metadata={"authority_factors": {"rights_access": 1.0}},
        ),
        posture="production",
        claim_use="claim_evidence_closeout",
    )

    assert result.factor_by_name("rights_access").value == 0.0
    assert result.status == "blocked_rights_boundary"
    assert result.satisfies_claim_evidence is False


def test_capability_authority_envelope_blocks_forbidden_production_claim_use() -> None:
    capability = _capability().model_copy(
        update={
            "authority_envelope": AuthorityEnvelope(
                research="admissible",
                governed_pilot="admissible",
                production="blocked_authority_boundary",
                may_not_use_for=("production_claim_evidence",),
            ),
        }
    )

    result = compose_capability_authority(
        capability,
        posture="production",
        claim_use="production_claim_evidence",
    )

    assert result.factor_by_name("legal_authority").value == 0.0
    assert result.status == "blocked_authority_boundary"
    assert result.satisfies_claim_evidence is False
    assert "capability_authority_envelope_blocked" in result.blocked_reasons


def test_llm_derived_construct_metadata_requires_producer_backed_capability() -> None:
    result = compose_capability_authority(
        _capability(
            capability_id="capability:llm_metadata_candidate",
            metadata={"llm_derived_construct": True, "producer_backed": False},
        ),
        posture="production",
        claim_use="claim_evidence_closeout",
    )

    assert result.status == "blocked_authority_boundary"
    assert result.satisfies_claim_evidence is False
    assert "llm_candidate_without_producer_backing" in result.blocked_reasons


def test_independence_collapse_above_floor_degrades_even_when_posture_threshold_passes() -> None:
    selected = _capability(
        capability_id="capability:firm_survival_selected",
        lineage_refs=("source_snapshot:shared", "calibration_run:shared", "method:shared"),
    )
    candidate = _capability(
        capability_id="capability:firm_survival_near_duplicate",
        lineage_refs=(
            "source_snapshot:shared",
            "calibration_run:shared",
            "method:shared",
            "source_snapshot:unique",
        ),
    )

    result = compose_capability_authority(
        candidate,
        posture="research",
        claim_use="claim_evidence_closeout",
        selected_capabilities=(selected,),
    )

    assert result.factor_by_name("effective_independence").value == 0.25
    assert result.factor_by_name("effective_independence").status == "pass"
    assert result.status == "selected_proxy_with_limitation"
    assert result.satisfies_claim_evidence is False
    assert "effective_independence_collapse_above_0_7" in result.limitations


def test_independence_collapse_degrades_authority() -> None:
    """Required Phase 7 negative-test id for W8.F effective independence."""

    test_independence_collapse_above_floor_degrades_even_when_posture_threshold_passes()


def test_proxy_capability_requires_construct_validity_for_governed_pilot() -> None:
    result = compose_capability_authority(
        _capability(
            capability_id="capability:proxy_without_governed_validity",
            evidence_mode="proxy_observational",
            trust_tier="administrative_noisy",
            identification_mode="proxy_identified",
            construct_validity=0.45,
        ),
        posture="governed_pilot",
        claim_use="claim_evidence_closeout",
    )

    assert result.status == "blocked_construct_validity_below_floor"
    assert result.satisfies_claim_evidence is False
    assert (
        result.factor_by_name("construct_validity").value
        < result.factor_by_name("construct_validity").threshold
    )


def test_historical_prior_can_seed_reviewer_attention_without_satisfying_claim_evidence() -> None:
    result = compose_capability_authority(
        _capability(
            evidence_mode="historical_prior",
            modality=("historical_pdc_artifact",),
            capability_id="capability:historical_prior_attention",
        ),
        posture="research",
        claim_use="reviewer_attention",
    )

    assert result.status == "selected_context_only"
    assert result.authority_envelope_result == "limited"
    assert result.satisfies_claim_evidence is False
    assert "historical_prior_advisory_only" in result.limitations
    assert "historical_prior_firewall_current_claim_evidence" not in result.blocked_reasons


@pytest.mark.parametrize(
    ("context_kwargs", "expected_status", "expected_reason"),
    [
        (
            {"construct_observed": False},
            "blocked_construct_not_observed",
            "construct_not_observed",
        ),
        (
            {"acquisition_required": True},
            "blocked_acquisition_required",
            "acquisition_required",
        ),
        (
            {"resolver_budget_exceeded": True},
            "blocked_resolver_budget_exceeded",
            "resolver_budget_exceeded",
        ),
    ],
)
def test_resolver_context_can_emit_remaining_blocked_statuses(
    context_kwargs: dict[str, Any],
    expected_status: str,
    expected_reason: str,
) -> None:
    result = compose_capability_authority(
        _capability(),
        posture="production",
        claim_use="claim_evidence_closeout",
        **context_kwargs,
    )

    assert result.status == expected_status
    assert result.satisfies_claim_evidence is False
    assert expected_reason in result.blocked_reasons


def test_construct_conflict_marker_preserved_through_resolver() -> None:
    conflict_marker = {
        "conflict_id": "conflict:firm_survival:empirical",
        "construct": "firm_survival",
        "conflict_class": "empirical",
        "conflict_resolution_route": "new_evidence",
        "capability_refs": ["capability:firm_survival_exact"],
    }

    result = compose_capability_authority(
        _capability(),
        posture="production",
        claim_use="claim_evidence_closeout",
        conflict_markers=(conflict_marker,),
    )

    assert result.status == "selected_with_conflict_marker"
    assert result.authority_envelope_result == "contested"
    assert result.satisfies_claim_evidence is False
    assert result.conflict_markers[0]["conflict_class"] == "empirical"

    admitted = compose_capability_authority(
        _capability(),
        posture="production",
        claim_use="claim_evidence_closeout",
        conflict_markers=(conflict_marker,),
        human_reviewer_admitted_conflicts=True,
    )

    assert admitted.status == "selected_exact"
    assert admitted.satisfies_claim_evidence is True
    assert "conflict_marker_human_reviewer_admitted" in admitted.binding_reasons


def test_mixed_outcome_fixture_expected_statuses_and_reasons() -> None:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert fixture["schema_version"] == "policyos.capability_authority.mixed_outcomes.v1"
    assert len(fixture["cases"]) >= 8

    seen_case_ids: set[str] = set()
    for case in fixture["cases"]:
        seen_case_ids.add(case["case_id"])
        result = compose_capability_authority(
            _capability(**case["capability"]),
            posture=case.get("posture", "production"),
            claim_use=case.get("claim_use", "claim_evidence_closeout"),
            selected_capabilities=tuple(_capability(**item) for item in case.get("selected", [])),
            conflict_markers=tuple(case.get("conflict_markers", [])),
            required_schema_regime=case.get("required_schema_regime"),
        )

        assert result.status == case["expected_status"], case["case_id"]
        if "expected_authority_envelope_result" in case:
            assert result.authority_envelope_result == case["expected_authority_envelope_result"], (
                case["case_id"]
            )
        if "expected_satisfies_claim_evidence" in case:
            assert result.satisfies_claim_evidence is case["expected_satisfies_claim_evidence"], (
                case["case_id"]
            )
        reasoning = " ".join(
            [
                *result.binding_reasons,
                *result.limitations,
                *result.blocked_reasons,
            ]
        )
        for expected in case["expected_reasoning"]:
            assert expected in reasoning, case["case_id"]

    assert {
        "exact",
        "exact_plus_proxy",
        "proxy_legal_gap",
        "scholar_only",
        "simulation_only",
        "historical_prior_only",
        "independence_collapsed",
        "conflict_marked",
        "rights_blocked",
    } <= seen_case_ids
