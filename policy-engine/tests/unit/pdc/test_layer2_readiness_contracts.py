from __future__ import annotations

import pytest
from pydantic import ValidationError

import polisyos.pdc as pdc
import polisyos.runtime.quality as runtime_quality
from polisyos.pdc import (
    AuthorityBoundary,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    CertifiedOperationEnvelope,
    DesignRecordV0,
    MinimalSeedManifest,
)

S9_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s9_projection_lowering.v1"
S9_RULE_VERSION_REF = "policyos.layer2.s9.projection_lowering.v1"
SOURCE_DESIGN_RECORD_REF = "pdc://layer2/s2/ua-msme/design-record-v0"
SOURCE_DESIGN_RECORD_DIGEST = "sha256:" + "2" * 64
CANONICAL_RECORD_REF = "pdc://layer2/s9/ua-msme/canonical-design-record"
SOURCE_REVISION_REF = "git://policyos/layer2/s9/red-first"


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


def _source_design_record() -> DesignRecordV0:
    return DesignRecordV0(
        record_id="design.record.ua_msme.s9_shadow",
        candidate_ref="candidate.ua_msme.credit_guarantee.s9_shadow",
        candidate_source="deterministic_producer",
        projection_status="shadow",
        authority_boundary=_authority_boundary(),
        axis_positions=[
            AxisPositionDeclaration(
                cluster="ACTOR",
                axis="value_choice_provenance",
                position="authorized_value_schedule_required",
                evidence_refs=["pdc://layer2/s8/ua-msme/value-choice-provenance"],
                authority_purpose="shadow_design_search_replay",
                rule_version_ref="policyos.layer2.s2.design_search.v1",
            )
        ],
        firewall_status=[
            AxisFirewallStatus(
                cell_ref="ACTOR.value_choice_provenance",
                status="block",
                pattern_ids=["P20"],
                reason="Ranked value choice requires authorized S8 provenance.",
                maturity="fail_closed",
                rule_version_ref="policyos.layer2.s8.value_choice.v1",
            )
        ],
        envelope=CertifiedOperationEnvelope(
            envelope_id="envelope.ua_msme.s9_shadow",
            domains=["ukrainian_msme_credit"],
            posture_scopes=["shadow"],
            epistemic_regime_scopes=["ignorance"],
            actor_scopes=["public_credit_program_operator"],
            method_scopes=["design_record_schema_only"],
            certified_for=["shadow_replay"],
            not_certified_for=["publication_authority", "rollout_authority"],
            cluster_authority_dimension_refs=[
                "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/mandate_legitimacy"
            ],
            rule_version_ref="policyos.layer2.s2.design_search.v1",
        ),
        ledger_refs=[
            "pdc://layer2/s2/ua-msme/search-ledger",
            "pdc://layer2/s5/ua-msme/recursive-design-graph",
            "pdc://layer2/s8/ua-msme/value-choice-provenance",
        ],
        projection_audiences=["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    )


def _canonical_payload(**overrides: object) -> dict[str, object]:
    source = _source_design_record()
    payload: dict[str, object] = {
        "schema_version": S9_SCHEMA_VERSION,
        "record_id": "layer2.s9.canonical-design-record.ua-msme",
        "record_ref": CANONICAL_RECORD_REF,
        "source_design_record_ref": SOURCE_DESIGN_RECORD_REF,
        "source_design_record_digest": SOURCE_DESIGN_RECORD_DIGEST,
        "source_revision_ref": SOURCE_REVISION_REF,
        "canonical_design_record_revision_ref": (
            "pdc://layer2/s9/ua-msme/canonical-design-record/revision/001"
        ),
        "recursive_design_graph_refs": ["pdc://layer2/s5/ua-msme/recursive-design-graph"],
        "claim_bound_evidence_portfolio_refs": ["claim-portfolio://ua-msme/evidence-bound"],
        "pareto_tradeoff_value_choice_refs": ["pdc://layer2/s8/ua-msme/value-tradeoff"],
        "axis_position_refs": [item.cell_ref for item in source.axis_positions],
        "firewall_status_refs": [item.cell_ref for item in source.firewall_status],
        "certified_envelope_ref": source.envelope.envelope_id,
        "search_ledger_refs": list(source.ledger_refs),
        "counterexample_refinement_refs": [
            "pdc://layer2/s2/ua-msme/counterexample/001",
            "pdc://layer2/s2/ua-msme/refinement/001",
        ],
        "assurance_case_refs": ["pdc://layer2/s9/ua-msme/assurance/projection"],
        "limitation_refs": ["pdc://layer2/s6/ua-msme/measurability-limitation"],
        "abstention_refs": ["pdc://layer2/s2/ua-msme/abstention/budget-gap"],
        "lowering_artifact_refs": ["pdc://layer2/s9/ua-msme/lowering/machine-contract"],
        "projection_audiences": list(source.projection_audiences),
        "projection_status": source.projection_status,
        "authority_boundary": source.authority_boundary.model_dump(mode="json"),
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _maturity_report_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "design_record_ref": SOURCE_DESIGN_RECORD_REF,
        "canonical_design_record_ref": CANONICAL_RECORD_REF,
        "design_record_schema_version": "policyos.policy_design_case.layer2_readiness.v1",
        "canonical_design_record_schema_version": S9_SCHEMA_VERSION,
        "source_revision_ref": SOURCE_REVISION_REF,
        "axis_position_refs": ["ACTOR.value_choice_provenance"],
        "firewall_status_refs": ["ACTOR.value_choice_provenance"],
        "ledger_refs": [
            "pdc://layer2/s2/ua-msme/search-ledger",
            "pdc://layer2/s5/ua-msme/recursive-design-graph",
            "pdc://layer2/s8/ua-msme/value-choice-provenance",
        ],
        "assurance_case_refs": ["pdc://layer2/s9/ua-msme/assurance/projection"],
        "limitation_refs": ["pdc://layer2/s6/ua-msme/measurability-limitation"],
        "abstention_refs": ["pdc://layer2/s2/ua-msme/abstention/budget-gap"],
        "lowering_artifact_refs": ["pdc://layer2/s9/ua-msme/lowering/machine-contract"],
        "projection_audiences": ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
        "missing_maturity_fields": [],
        "authority_boundary": _authority_boundary().model_dump(mode="json"),
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def test_canonical_design_record_requires_full_narrow_waist_refs_for_s9() -> None:
    record = pdc.CanonicalDesignRecord.model_validate(_canonical_payload())

    assert record.source_design_record_ref == SOURCE_DESIGN_RECORD_REF
    assert record.recursive_design_graph_refs
    assert record.claim_bound_evidence_portfolio_refs
    assert record.pareto_tradeoff_value_choice_refs
    assert record.axis_position_refs == ["ACTOR.value_choice_provenance"]
    assert record.firewall_status_refs == ["ACTOR.value_choice_provenance"]
    assert record.certified_envelope_ref == "envelope.ua_msme.s9_shadow"
    assert record.search_ledger_refs

    with pytest.raises(ValidationError):
        pdc.CanonicalDesignRecord.model_validate(
            _canonical_payload(pareto_tradeoff_value_choice_refs=[])
        )


def test_canonical_design_record_preserves_v0_shadow_projection_status() -> None:
    source = _source_design_record()
    record = pdc.CanonicalDesignRecord.model_validate(
        _canonical_payload(
            projection_status=source.projection_status,
            authority_boundary=source.authority_boundary.model_dump(mode="json"),
        )
    )

    assert source.projection_status == "shadow"
    assert record.projection_status == "shadow"
    assert record.authority_boundary.posture == "shadow"
    assert "publication_authority" in record.authority_boundary.may_not_use_for


def test_design_record_maturity_report_requires_s2_s5_s8_refs_for_s9() -> None:
    report = runtime_quality.DesignRecordMaturityReport.model_validate(
        _maturity_report_payload()
    )

    assert report.design_record_ref == SOURCE_DESIGN_RECORD_REF
    assert report.canonical_design_record_ref == CANONICAL_RECORD_REF
    assert "pdc://layer2/s2/ua-msme/search-ledger" in report.ledger_refs
    assert "pdc://layer2/s5/ua-msme/recursive-design-graph" in report.ledger_refs
    assert "pdc://layer2/s8/ua-msme/value-choice-provenance" in report.ledger_refs
    assert report.missing_maturity_fields == []

    with pytest.raises(ValidationError):
        runtime_quality.DesignRecordMaturityReport.model_validate(
            _maturity_report_payload(
                ledger_refs=["pdc://layer2/s2/ua-msme/search-ledger"],
                missing_maturity_fields=["s5_recursive_design_graph_refs"],
            )
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
