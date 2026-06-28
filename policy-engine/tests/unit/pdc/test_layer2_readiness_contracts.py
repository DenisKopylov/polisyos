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
    decision_grade: str = "decision_admissible",
) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["shadow_design_candidate"],
        may_not_use_for=["publication_authority", "rollout_authority"],
        source_authority=source_authority,
        posture=posture,
        rule_version_refs=["repo://architecture/policy_design_case/cluster_ownership_map.toml"],
        evidence_kind="measurement",
        decision_grade=decision_grade,  # type: ignore[arg-type]
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


def test_authority_boundary_partial_evidence_downgrade_caps_grade_and_denials() -> None:
    boundary = _authority_boundary(posture="governed", decision_grade="decision_admissible")

    downgraded = boundary.with_partial_evidence_downgrade(
        limitation="observable subset only; causal pathway remains bounded",
        may_not_use_for=[
            "production_decision",
            "publication_without_limitation",
        ],
        decision_grade_cap="advisory_admissible",
        boundary_id="boundary-partial",
    )

    assert downgraded.boundary_id == "boundary-partial"
    assert downgraded.decision_grade == "advisory_admissible"
    assert downgraded.decision_grade != "decision_admissible"
    assert "observable subset only; causal pathway remains bounded" in downgraded.known_limits
    assert "production_decision" in downgraded.may_not_use_for
    assert "publication_without_limitation" in downgraded.may_not_use_for
    assert downgraded.permits_at_most(boundary)


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


def test_layer2_s10_forecast_posture_input_is_strict_and_exported() -> None:
    posture_model = pdc.Layer2S10ForecastPostureInput

    assert posture_model.model_config.get("extra") == "forbid"

    posture = posture_model(
        forecast_support_ref="pdc://layer2/s10/ua-msme/forecast-support",
        forecast_tier="observable_calibrated",
        forecast_authority_disposition_reason=(
            "Observable subset calibration supports a bounded forecast tier."
        ),
        forecast_support_label="validated_local_dynamic_model",
        forecast_calibration_record_ref="pdc://layer2/s10/ua-msme/calibration",
        design_graph_ref="pdc://layer2/s5/ua-msme/recursive-design-graph",
        prediction_context_ref="pdc://layer2/s10/ua-msme/prediction-context",
        policy_context_ref="policy-context://ua-msme/2022",
        candidate_design_ref="candidate://ua-msme/targeted-credit",
        baseline_design_ref="baseline://ua-msme/no-new-credit",
        alternative_design_refs=["alternative://ua-msme/cash-transfer"],
        prediction_horizon_ref="horizon://12-months",
        observable_subset_ref="pdc://layer2/s10/ua-msme/observable-subset",
        uncertainty_interval_refs=["interval://ua-msme/credit-access/95"],
        welfare_comparison_ref="pdc://layer2/s10/ua-msme/welfare-comparison",
        s5_forecast_support_ref="pdc://layer2/s5/ua-msme/system-effect-support",
        s6_firewall_status_refs=["pdc://layer2/s6/ua-msme/measurability-adequacy"],
        s8_value_choice_provenance_ref="pdc://layer2/s8/ua-msme/value-choice",
        s8_value_tradeoff_disclosure_ref="pdc://layer2/s8/ua-msme/tradeoff",
        source_contract_ref="source-contract://ua-msme/panel",
        method_validity_ref="method-validity://foundry/causal/local",
        credible_evaluation_evidence_ref="evidence://ua-msme/credible-evaluation",
        dynamic_equilibrium_check_ref="equilibrium-check://ua-msme/system-effect",
        sensitivity_analysis_ref="sensitivity://ua-msme/credit-access",
        authority_boundary=_authority_boundary().model_dump(mode="json"),
        may_not_use_for=[
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "s11_calibration",
        ],
        rule_version_ref="policyos.layer2.s10.outcome_prediction.v1",
    )

    assert posture.forecast_support_ref.endswith("/forecast-support")
    assert posture.design_graph_ref.startswith("pdc://layer2/s5/")
    assert posture.prediction_context_ref.startswith("pdc://layer2/s10/")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        posture_model.model_validate(
            {
                **posture.model_dump(mode="json"),
                "recommendation_authority": "publish",
            }
        )


def test_s11_predictive_posture_input_is_strict_and_exported() -> None:
    posture_model = pdc.Layer2S11PredictivePostureInput

    assert posture_model.model_config.get("extra") == "forbid"

    posture = posture_model(
        predictive_knowledge_ref="pdc://layer2/s11/ua-msme/predictive-knowledge",
        effective_predictive_posture="limited_by_weakest_boundary",
        axis_upgrade_refs=["pdc://layer2/s11/ua-msme/upgrade/measurability"],
        predictive_axis_rows=[
            {
                "axis": "measurability",
                "cell_ref": "SYSTEM.measurability",
                "effective_maturity": "predictive",
                "relaxation_decision": "relaxed_to_predictive",
            }
        ],
        proof_carrying_analytics_ref="pdc://layer2/s11/ua-msme/proof/credit-access",
        ir_analytics_bridge_ref="ir-analytics-bridge://ua-msme/credit-access",
        s10_forecast_support_ref="pdc://layer2/s10/ua-msme/forecast-support",
        s10_forecast_tier="observable_calibrated",
        s6_floor_status_refs=["pdc://layer2/s6/ua-msme/measurability-adequacy"],
        s6_axis_rows=[
            {
                "axis": "measurability",
                "cell_ref": "SYSTEM.measurability",
                "record_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
                "disposition": "limit",
            }
        ],
        s6_bridge_consumer_rows=[
            {
                "cell_ref": "SYSTEM.measurability",
                "consumer_ref": "KNOWLEDGE.epistemic_regime",
                "producer_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
                "disposition": "limit",
            }
        ],
        s6_constraint_store_update_refs=["constraint://s6/measurability"],
        s6_c3_authority_dimension_refs=[
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/measurability_adequacy"
        ],
        post_intervention_dgp_update_ref="pdc://layer2/s6/ua-msme/post-intervention-dgp",
        system_dynamics_handoff_required=True,
        s11_calibration_record_refs=["pdc://layer2/s11/ua-msme/calibration/measurability"],
        method_infrastructure_refs=["foundry://methods/calibration/local-causal"],
        forecast_quality_disposition="unchanged_s10_tier_consumed",
        regime_strategy_constraint_ref="constraint://s11/regime/measurability",
        residual_limitation_refs=["limitation://s11/measurability/current-run"],
        per_axis_predictive_calibration_threshold_ref=(
            "repo://architecture/policy_design_case/layer2_floor_governance.toml#s11"
        ),
        per_axis_predictive_calibration_denominator=4,
        per_axis_predictive_calibration_numerator=3,
        per_axis_predictive_calibration_pass_rate=0.75,
        per_axis_predictive_calibration_status="pass",
        weakest_boundary_reason="S11 inherits S6 fail-closed limits for reverted axes.",
        authority_boundary={
            "authoritative_for": [
                "per_axis_predictive_calibration",
                "predictive_axis_maturity_upgrade",
                "proof_carrying_analytics_validity",
            ],
            "may_not_use_for": [
                "production_authority",
                "production_recommendation",
                "production_claim_authority",
                "publication_authority",
                "claim_authority",
                "rich_simulation_authority",
                "s12_envelope_growth",
                "s13_accountability_closure",
                "s14_universality",
                "mandate_legitimacy_predictive_upgrade",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": ["policyos.layer2.s11.predictive_knowledge.v1"],
        },
        may_not_use_for=[
            "production_authority",
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "claim_authority",
            "rich_simulation_authority",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
            "mandate_legitimacy_predictive_upgrade",
        ],
        rule_version_ref="policyos.layer2.s11.predictive_knowledge.v1",
    )

    assert posture.predictive_knowledge_ref.endswith("/predictive-knowledge")
    assert posture.s10_forecast_support_ref.startswith("pdc://layer2/s10/")
    assert "production_authority" in posture.may_not_use_for

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        posture_model.model_validate(
            {
                **posture.model_dump(mode="json"),
                "recommendation_authority": "publish",
            }
        )


def test_layer2_s12_resource_economics_posture_input_is_strict_and_exported() -> None:
    posture_model = pdc.Layer2S12ResourceEconomicsPostureInput

    assert posture_model.model_config.get("extra") == "forbid"

    posture = posture_model(
        resource_allocation_policy_ref=(
            "pdc://layer2/s12/ua-msme/resource-allocation-policy"
        ),
        explore_exploit_posture="balanced_governed",
        explore_exploit_dial_ref="pdc://layer2/s7/ua-msme/explore-exploit-dial",
        delegation_contract_ref="pdc://layer2/s7/ua-msme/delegation-contract",
        voi_allocation_refs=[
            "voi-allocation://ua-msme/acquisition",
            "voi-allocation://ua-msme/refinement",
            "voi-allocation://ua-msme/attention",
        ],
        voi_site_count=3,
        typed_budget_refs=[
            "budget://ua-msme/compute",
            "budget://ua-msme/acquisition",
            "budget://ua-msme/expert-time",
            "budget://ua-msme/human-attention",
            "budget://ua-msme/legal-access",
        ],
        pareto_archive_ref="pdc://layer2/s8/ua-msme/allocation-pareto-archive",
        allocation_priority_rows=[
            {
                "priority_ref": "priority://ua-msme/acquisition/source-rights",
                "site": "acquisition",
                "budget_kind": "legal_access",
                "reason": "Source-rights gap blocks admissible substrate use.",
            }
        ],
        envelope_growth_ledger_ref="pdc://layer2/s12/ua-msme/envelope-growth-ledger",
        growth_thermometer_ref="pdc://layer2/s12/ua-msme/growth-thermometer",
        override_rate_trend="flat",
        reuse_rate_trend="improving",
        held_out_status="pending_s14",
        knowledge_governance_throughput_ledger_ref=(
            "pdc://layer2/s12/ua-msme/knowledge-throughput-ledger"
        ),
        residual_limitation_refs=["limitation://s12/no-production-authority"],
        authority_boundary={
            "authoritative_for": [
                "value_of_information_allocation",
                "explore_exploit_posture",
                "envelope_growth_ledger",
                "growth_thermometers",
                "knowledge_governance_throughput",
                "allocation_priority_input",
            ],
            "may_not_use_for": [
                "production_authority",
                "production_recommendation",
                "rollout_authority",
                "publication_authority",
                "claim_authority",
                "closeout_authority",
                "approval_authority",
                "scorecard_authority",
                "preference_learning_authority",
                "mdp_bandit_optimizer_authority",
                "budget_interchangeability",
                "mission_or_value_self_authorization",
                "floor_relaxation",
                "s13_envelope_shrink",
                "s13_accountability_closure",
                "s14_universality",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": ["policyos.layer2.s12.resource_economics.v1"],
        },
        may_not_use_for=[
            "production_authority",
            "production_recommendation",
            "rollout_authority",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
            "approval_authority",
            "scorecard_authority",
            "preference_learning_authority",
            "mdp_bandit_optimizer_authority",
            "budget_interchangeability",
            "mission_or_value_self_authorization",
            "floor_relaxation",
            "s13_envelope_shrink",
            "s13_accountability_closure",
            "s14_universality",
        ],
        rule_version_ref="policyos.layer2.s12.resource_economics.v1",
    )

    assert posture.voi_site_count >= 3
    assert len(posture.typed_budget_refs) == 5
    assert posture.held_out_status == "pending_s14"
    assert "production_recommendation" in posture.may_not_use_for

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        posture_model.model_validate(
            {
                **posture.model_dump(mode="json"),
                "allocation_recommendation_authority": "publish",
            }
        )


def test_layer2_s13_post_deploy_accountability_posture_input_is_strict_and_exported() -> None:
    posture_model = pdc.Layer2S13PostDeployAccountabilityPostureInput

    assert posture_model.model_config.get("extra") == "forbid"

    posture = posture_model(
        phase="post_deploy_finalized",
        accountability_posture_ref="pdc://layer2/s13/ua-msme/accountability-posture",
        deployment_dossier_ref="pdc://layer2/s13/ua-msme/deployment-dossier",
        divergence_record_refs=[
            "pdc://layer2/s13/ua-msme/divergence/seeded-disconfirmation"
        ],
        learning_update_proposal_refs=[
            "learning-proposal://ua-msme/envelope-shrink"
        ],
        envelope_revision_ref="envelope-revision://ua-msme/shrink/001",
        certified_envelope_delta_ref="certified-envelope-delta://ua-msme/s12-growth",
        assurance_case_delta_ref="assurance-delta://ua-msme/s13/weakened",
        attribution_status="attributed",
        attribution_classes=["design_error"],
        learning_change_control_classes=["reissue_required"],
        lifecycle_reissue_disposition="reissue_required",
        envelope_revision_direction="shrink",
        assurance_case_change="weakened",
        mape_k_trace_ref="mape-k://ua-msme/post-deploy",
        public_revision_state_ref="public-revision-state://ua-msme/s13/001",
        public_accountability_note_ref="public-note://ua-msme/s13/accountability",
        action_item_status="closed",
        action_item_closure_refs=["closure://ua-msme/s13/action-item/001"],
        human_decision_request_refs=["human-decision-request://ua-msme/s13/reissue"],
        human_decision_record_refs=["human-decision-record://ua-msme/s13/reissue"],
        oversight_effectiveness_ref="oversight://ua-msme/effectiveness/001",
        oversight_accountability_state="rubber_stamp_divergence_review_required",
        a_before_b_status="pass",
        historical_prior_influence_refs=[
            "historical-prior-influence:ua-msme/default-risk-route"
        ],
        replay_digest="sha256:" + "a" * 64,
        authority_boundary={
            "authoritative_for": [
                "post_deploy_accountability",
                "deployment_monitorability",
                "divergence_attribution",
                "learning_update_proposal",
                "post_deploy_mape_k_trace",
                "envelope_revision",
                "assurance_case_delta",
                "public_accountability_note",
            ],
            "may_not_use_for": [
                "production_rollout_authority",
                "recommendation_authority",
                "publication_authority",
                "approval_authority",
                "scorecard_authority",
                "pre_policy_evidence",
                "current_evidence_slot",
                "preference_learning",
                "automated_value_learning",
                "naive_ml_update",
                "s14_universality",
                "llm_attribution_authority",
                "local_governance_enum_for_reissue",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": ["policyos.layer2.s13.post_deploy_accountability.v1"],
        },
        may_not_use_for=[
            "production_rollout_authority",
            "recommendation_authority",
            "publication_authority",
            "approval_authority",
            "scorecard_authority",
            "pre_policy_evidence",
            "current_evidence_slot",
            "preference_learning",
            "automated_value_learning",
            "naive_ml_update",
            "s14_universality",
            "llm_attribution_authority",
            "local_governance_enum_for_reissue",
        ],
        rule_version_ref="policyos.layer2.s13.post_deploy_accountability.v1",
    )

    assert posture.phase == "post_deploy_finalized"
    assert posture.lifecycle_reissue_disposition == "reissue_required"
    assert posture.envelope_revision_direction == "shrink"
    assert "current_evidence_slot" in posture.may_not_use_for
    assert pdc.Layer2S13PostDeployAccountabilityPostureInput is posture_model

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        posture_model.model_validate(
            {
                **posture.model_dump(mode="json"),
                "local_s13_reissue_enum": "publish",
            }
        )
