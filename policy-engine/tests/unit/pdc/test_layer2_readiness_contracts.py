from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.pdc import (
    AuthorityBoundary,
    AxisFirewallStatus,
    CertifiedOperationEnvelope,
    DesignRecordV0,
    MinimalSeedManifest,
)


def _authority_boundary(
    *,
    source_authority: str = "deterministic_producer",
    posture: str = "shadow",
) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["shadow_design_candidate"],
        may_not_use_for=["publication_authority", "rollout_authority"],
        source_authority=source_authority,
        posture=posture,
        rule_version_refs=["repo://architecture/policy_design_case/cluster_ownership_map.toml"],
    )


def test_minimal_seed_manifest_requires_launch_firewalls_and_budgets() -> None:
    manifest = MinimalSeedManifest(
        manifest_id="layer2.s0.seed",
        facet_primitives=["construct", "instrument", "actor", "time_role"],
        instrument_modality_primitives=["cash_transfer", "credit_guarantee"],
        projection_primitives=["status", "limitation", "authority_boundary"],
        launch_firewalls=["P15", "P25"],
        budgets={
            "compute": "bounded",
            "acquisition": "bounded",
            "expert_time": "bounded",
            "human_attention": "bounded",
            "legal_access": "bounded",
        },
        principal_set_explore_exploit="principal_set_explicit_governed_balance",
        owned_by="team-policyos-runtime",
        rule_version_refs=["repo://docs/reference/policy-design-case-failure-patterns.md"],
    )

    assert manifest.schema_version == "policyos.policy_design_case.layer2_readiness.v1"


def test_minimal_seed_manifest_rejects_missing_p15_or_p25() -> None:
    with pytest.raises(ValidationError, match="launch_firewalls must include P15 and P25"):
        MinimalSeedManifest(
            manifest_id="layer2.s0.seed",
            facet_primitives=["construct"],
            instrument_modality_primitives=["cash_transfer"],
            projection_primitives=["status"],
            launch_firewalls=["P15"],
            budgets={"compute": "bounded"},
            principal_set_explore_exploit="principal_set_explicit_governed_balance",
            owned_by="team-policyos-runtime",
            rule_version_refs=["repo://docs/reference/policy-design-case-failure-patterns.md"],
        )


def test_design_record_v0_blocks_llm_candidate_from_governed_authority() -> None:
    with pytest.raises(ValidationError, match="llm_candidate cannot carry governed"):
        DesignRecordV0(
            record_id="design.record.ua_msme.001",
            candidate_ref="candidate.ua_msme.credit_guarantee.001",
            candidate_source="llm_candidate",
            projection_status="governed",
            authority_boundary=_authority_boundary(
                source_authority="llm_candidate",
                posture="shadow",
            ),
            axis_positions=[],
            firewall_status=[],
            envelope=CertifiedOperationEnvelope(
                envelope_id="envelope.ua_msme.shadow",
                domains=["ukrainian_msme_credit"],
                posture_scopes=["shadow"],
                epistemic_regime_scopes=[],
                actor_scopes=["public_credit_program_operator"],
                method_scopes=["design_record_schema_only"],
                certified_for=["shadow_replay"],
                not_certified_for=["publication_authority", "rollout_authority"],
                rule_version_ref="repo://architecture/policy_design_case/layer2_readiness_manifest.json",
            ),
            ledger_refs=[],
            projection_audiences=["MACHINE", "REVIEWER"],
        )


def test_axis_firewall_maturity_is_qualifier_not_ratchet_state() -> None:
    status = AxisFirewallStatus(
        cell_ref="ACTOR.state_capacity_feasibility",
        status="block",
        pattern_ids=["P21"],
        reason="No capacity feasibility producer is available yet.",
        maturity="fail_closed",
        rule_version_ref="repo://architecture/policy_design_case/cluster_ownership_map.toml",
    )

    assert status.maturity == "fail_closed"


def test_certified_operation_envelope_separates_posture_from_epistemic_regime() -> None:
    envelope = CertifiedOperationEnvelope(
        envelope_id="envelope.ua_msme.shadow",
        domains=["ukrainian_msme_credit"],
        posture_scopes=["shadow"],
        epistemic_regime_scopes=["ignorance"],
        actor_scopes=["public_credit_program_operator"],
        method_scopes=["design_record_schema_only"],
        certified_for=["shadow_replay"],
        not_certified_for=["publication_authority", "rollout_authority"],
        rule_version_ref="repo://architecture/policy_design_case/layer2_readiness_manifest.json",
    )

    assert envelope.posture_scopes == ["shadow"]
    assert envelope.epistemic_regime_scopes == ["ignorance"]

    with pytest.raises(ValidationError):
        CertifiedOperationEnvelope(
            envelope_id="envelope.ua_msme.bad",
            domains=["ukrainian_msme_credit"],
            posture_scopes=["shadow"],
            epistemic_regime_scopes=["shadow"],
            actor_scopes=["public_credit_program_operator"],
            method_scopes=["design_record_schema_only"],
            certified_for=["shadow_replay"],
            not_certified_for=["publication_authority", "rollout_authority"],
            rule_version_ref="repo://architecture/policy_design_case/layer2_readiness_manifest.json",
        )


def test_certified_operation_envelope_carries_cluster_authority_dimension_refs() -> None:
    envelope = CertifiedOperationEnvelope(
        envelope_id="envelope.ua_msme.shadow",
        domains=["ukrainian_msme_credit"],
        posture_scopes=["shadow"],
        epistemic_regime_scopes=["ignorance"],
        actor_scopes=["public_credit_program_operator"],
        method_scopes=["design_record_schema_only"],
        certified_for=["shadow_replay"],
        not_certified_for=["publication_authority", "rollout_authority"],
        cluster_authority_dimension_refs=[
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/measurability_adequacy"
        ],
        rule_version_ref="repo://architecture/policy_design_case/layer2_readiness_manifest.json",
    )

    assert envelope.cluster_authority_dimension_refs == [
        "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/measurability_adequacy"
    ]


def test_design_record_v0_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AuthorityBoundary(
            authoritative_for=["shadow_design_candidate"],
            may_not_use_for=["publication_authority"],
            source_authority="deterministic_producer",
            posture="shadow",
            rule_version_refs=["repo://architecture/policy_design_case/cluster_ownership_map.toml"],
            unexpected="not allowed",
        )
