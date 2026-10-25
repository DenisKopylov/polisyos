from __future__ import annotations

import json
from collections.abc import ItemsView, Iterator, Mapping, Sequence
from pathlib import Path

import pytest

from polisyos.core import SecretPIIScanResult
from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality import public_export as public_export_module
from polisyos.runtime.quality.case_lifecycle import build_lifecycle_reissue_report
from polisyos.runtime.quality.design_problem import (
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import GenerationCycleController
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.public_export import (
    PublicExportRedactionError,
    assert_public_export_official_use_limits,
    build_public_export_bundle,
)
from polisyos.runtime.quality.rule_evolution import build_rule_evolution_registry
from tests._helpers.hds_quality import authority_envelope_for, sha
from tests._helpers.policy_design_case_projection import policy_design_case

REPO_ROOT = Path(__file__).resolve().parents[4]

S9_RULE_VERSION_REF = "policyos.layer2.s9.projection_lowering.v1"
S10_RULE_VERSION_REF = "policyos.layer2.s10.outcome_prediction.v1"
S11_RULE_VERSION_REF = "policyos.layer2.s11.predictive_knowledge.v1"
S12_RULE_VERSION_REF = "policyos.layer2.s12.resource_economics.v1"
S13_RULE_VERSION_REF = "policyos.layer2.s13.post_deploy_accountability.v1"
S14_RULE_VERSION_REF = "policyos.layer2.s14.universality_assurance.v1"


def _open_world_problem() -> DesignProblem:
    return DesignProblem(
        design_problem_id="public_open_world_problem",
        problem_statement="Project an explicit unknown deployment scope.",
        domain="generic_policy",
        nl_provenance=NLProvenance(
            raw_request="Project deployment scope.",
            source_surface="test_public_export",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="test-only",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-08-25",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="survival",
                description="Improve survival",
                metric_id="survival",
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="shadow_only",
                description="Remain shadow without owner evidence.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Remain shadow.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="survival",
            metric_id="survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="scope",
                    question="Who owns deployment scope?",
                    required_for="promotion",
                )
            ]
        ),
    )


@pytest.mark.asyncio
async def test_terminal_blocked_n6_refuses_public_n9_projection_before_receipt_parse(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.runtime.quality.test_generation_cycle import (
        _budget,
        _CgfGenerationPort,
    )

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _open_world_problem()
    blocked_run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        promotion_runtime=runtime,
        repo_root=REPO_ROOT,
    ).run(
        problem,
        budget_state=_budget(),
        max_cycles=1,
    )
    assert blocked_run.terminal_status == "blocked"
    assert blocked_run.promotion_port.receipts == ()
    assert blocked_run.promotion_port.reason == (
        "generation_cycle_blocked_before_n9:voi_safety_cap_reached_without_scheduler_stop"
    )

    def receipt_parser_must_not_run(cls, payload):
        del cls, payload
        raise AssertionError("blocked N6 reached the public N9 receipt parser")

    monkeypatch.setattr(
        public_export_module.CanonicalPromotionReceipt,
        "model_validate",
        classmethod(receipt_parser_must_not_run),
    )
    with pytest.raises(
        PublicExportRedactionError,
        match="generation_cycle_blocked_before_n9_cannot_supply_receipt",
    ):
        public_export_module.project_promotion_open_world_limitation(
            run=blocked_run,
            design_problem=problem,
            receipt={"candidate_id": "grafted"},
            resolver=runtime.resolver,
            repo_root=REPO_ROOT,
        )


@pytest.mark.parametrize(
    "schema_version",
    [
        pytest.param("policyos.runtime.generation_cycle_controller.v1"),
        pytest.param("policyos.runtime.generation_cycle_controller.v2"),
    ],
)
def test_persisted_historical_n6_cannot_supply_current_n9_receipt(
    schema_version: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Historical bytes replay, but cannot be promoted into current N9 input."""

    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleRun,
        validate_generation_cycle_run_history,
    )
    from tests.unit.runtime.quality.test_generation_cycle_history import (
        _tracked_n6_runs,
    )

    _tracked_json_file_count, occurrences = _tracked_n6_runs()
    matching_runs = tuple(
        row for row in occurrences if row[2].get("schema_version") == schema_version
    )
    assert matching_runs, f"no persisted N6 run for historical schema {schema_version}"
    path, pointer, payload = matching_runs[0]
    assert validate_generation_cycle_run_history(payload) == (), f"{path}{pointer}"
    run = GenerationCycleRun.model_validate(payload)
    assert run.schema_version == schema_version

    parsed_receipts: list[object] = []

    def receipt_parser_must_not_run(cls, receipt_payload):
        del cls
        parsed_receipts.append(receipt_payload)
        raise AssertionError("historical N6 reached the current N9 receipt parser")

    monkeypatch.setattr(
        public_export_module.CanonicalPromotionReceipt,
        "model_validate",
        classmethod(receipt_parser_must_not_run),
    )
    with pytest.raises(
        PublicExportRedactionError,
        match="generation_cycle_historical_run_not_current_n9_source",
    ) as error_info:
        public_export_module.project_promotion_open_world_limitation(
            run=run,
            design_problem=_open_world_problem(),
            receipt={"candidate_id": "must-not-be-parsed"},
            resolver=object(),  # type: ignore[arg-type]
        )
    assert error_info.value.code == "generation_cycle_historical_run_not_current_n9_source"
    assert parsed_receipts == []


def _s9_public_faithfulness_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "faithfulness_id": "layer2.s9.faithfulness.public",
        "faithfulness_ref": "pdc://layer2/s9/ua-msme/faithfulness/public",
        "render_ref": "pdc://layer2/s9/ua-msme/projection-render/public",
        "request_ref": "pdc://layer2/s9/ua-msme/projection-request/public",
        "canonical_design_record_ref": "pdc://layer2/s9/ua-msme/canonical-design-record",
        "canonical_design_record_digest": "sha256:" + "9" * 64,
        "source_revision_ref": "git://policyos/layer2/s9/red-first",
        "faithfulness_status": "pass",
        "issue_codes": [],
        "added_claim_refs": [],
        "hidden_blocker_refs": [],
        "hidden_limitation_refs": [],
        "tradeoff_direction_status": "preserved",
        "shadow_approval_status": "not_approved",
        "consumer_contract_ref": (
            "policyos.runtime.policy_design_case.projection_contract_verification.v1"
        ),
        "authority_boundary": {
            "authoritative_for": ["projection_faithfulness"],
            "may_not_use_for": [
                "production_recommendation",
                "production_claim_authority",
                "publication_authority",
                "claim_authority",
                "scorecard_authority",
                "runtime_closeout_authority",
                "s14_universality",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S9_RULE_VERSION_REF],
        },
        "rule_version_ref": S9_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _s10_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "forecast_tier": "observable_calibrated",
        "forecast_authority_disposition_reason": (
            "Observable subset calibration supports a bounded forecast tier."
        ),
        "observable_subset_calibration_status": "pass",
        "forecast_calibration_record_ref": "pdc://layer2/s10/ua-msme/calibration",
        "design_graph_ref": "pdc://layer2/s5/ua-msme/recursive-design-graph",
        "prediction_context_ref": "pdc://layer2/s10/ua-msme/prediction-context",
        "policy_context_ref": "policy-context://ua-msme/2022",
        "source_contract_ref": "source-contract://ua-msme/panel",
        "method_validity_ref": "method-validity://foundry/causal/local",
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "uncertainty_interval_refs": ["interval://ua-msme/credit-access/95"],
        "limitations": ["forecast support only; not recommendation authority"],
        "authority_boundary": {
            "authoritative_for": ["forecast_support_tiering"],
            "may_not_use_for": [
                "production_recommendation",
                "production_claim_authority",
                "publication_authority",
                "claim_authority",
                "closeout_authority",
                "s11_calibration",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S10_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
            "production_recommendation",
            "production_claim_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "s11_calibration",
        ],
        "rule_version_ref": S10_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _s11_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "s11_predictive_posture_ref": "pdc://layer2/s11/ua-msme/predictive-knowledge",
        "effective_predictive_posture": "limited_by_weakest_boundary",
        "predictive_axis_upgrade_refs": ["pdc://layer2/s11/ua-msme/upgrade/measurability"],
        "predictive_axis_rows": [
            {
                "axis": "measurability",
                "cell_ref": "SYSTEM.measurability",
                "effective_maturity": "predictive",
                "relaxation_decision": "relaxed_to_predictive",
            },
            {
                "axis": "strategic_response",
                "cell_ref": "OTHER_AGENTS.strategic_response",
                "effective_maturity": "fail_closed",
                "relaxation_decision": "reverted_fail_closed",
            },
        ],
        "per_axis_predictive_calibration_status": "pass",
        "per_axis_predictive_calibration_threshold_ref": (
            "repo://architecture/policy_design_case/layer2_floor_governance.toml#s11"
        ),
        "proof_carrying_analytics_ref": "pdc://layer2/s11/ua-msme/proof/credit-access",
        "ir_analytics_bridge_ref": "ir-analytics-bridge://ua-msme/credit-access",
        "residual_limitation_refs": ["limitation://s11/strategic-response/fail-closed"],
        "s11_public_limitation": (
            "Predictive relaxation is limited by calibration and proof-carrying checks."
        ),
        "weakest_boundary_reason": "strategic_response remains fail_closed under S6.",
        "authority_boundary": {
            "authoritative_for": [
                "per_axis_predictive_calibration",
                "predictive_axis_maturity_upgrade",
            ],
            "may_not_use_for": [
                "production_authority",
                "production_recommendation",
                "production_claim_authority",
                "publication_authority",
                "claim_authority",
                "runtime_closeout_authority",
                "rich_simulation_authority",
                "s12_envelope_growth",
                "s13_accountability_closure",
                "s14_universality",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S11_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
            "production_authority",
            "production_recommendation",
            "production_claim_authority",
            "publication_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "rich_simulation_authority",
        ],
        "limitations": ["S11 predictive relaxation remains calibration-limited and not authority."],
        "rule_version_ref": S11_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _g3_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload = _s11_public_projection_payload(
        proof_carrying_analytics_ref="pdc://layer3/g3/ua-msme/proof/credit-access",
        ir_analytics_bridge_ref="ir-analytics-bridge://layer3/g3/ua-msme",
    )
    payload["layer3_g3_public_export_projection"] = {
        "projection_ref": "pdc://layer3/g3/ua-msme/public-export-projection",
        "status": "pass",
        "certificate_resolution_report_ref": (
            "repo://architecture/policy_design_case/layer3_g3_certificate_resolution_report.json"
        ),
        "search_ledger_refs": [
            "repo://architecture/policy_design_case/layer3_g3_ir_analytics_search_ledgers.json"
        ],
        "redacted_search_frontier_refs": ["g3-search-frontier://ua-msme/resolved-proof-candidates"],
        "proof_carrying_analytics_refs": ["pdc://layer3/g3/ua-msme/proof/credit-access"],
        "ir_analytics_bridge_refs": ["ir-analytics-bridge://layer3/g3/ua-msme"],
        "method_requirement_refs": ["method-requirement://layer3/g3/ua-msme"],
        "s11_predictive_posture_refs": ["pdc://layer2/s11/ua-msme/predictive-knowledge"],
        "resolved_certificate_count": 1,
        "blocked_certificate_count": 0,
        "authority_boundary": {
            "authoritative_for": ["g3_public_projection_audit"],
            "may_not_use_for": [
                "claim_authority",
                "policy_recommendation",
                "closeout_authority",
                "publication_authority",
            ],
        },
        "may_not_use_for": [
            "claim_authority",
            "policy_recommendation",
            "closeout_authority",
            "publication_authority",
            "search_hit_as_certificate",
        ],
        "raw_proof_payload": {"theorem_family": "raw material must not reach PUBLIC"},
        "raw_cas_manifest": {"artifact_ids": ["secret-cas-id"]},
        "raw_query_ledger": {"sql": "select * from hidden_ir_catalog"},
    }
    payload.update(overrides)
    return payload


def _s12_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "s12_resource_posture_ref": "pdc://layer2/s12/ua-msme/resource-posture",
        "resource_allocation_policy_ref": ("pdc://layer2/s12/ua-msme/resource-allocation-policy"),
        "explore_exploit_posture": "balanced_governed",
        "explore_exploit_dial_ref": "pdc://layer2/s7/ua-msme/explore-exploit-dial",
        "voi_allocation_refs": [
            "voi-allocation://ua-msme/acquisition",
            "voi-allocation://ua-msme/refinement",
            "voi-allocation://ua-msme/attention",
        ],
        "voi_site_count": 3,
        "typed_budget_refs": [
            "budget://ua-msme/compute",
            "budget://ua-msme/acquisition",
            "budget://ua-msme/expert-time",
            "budget://ua-msme/human-attention",
            "budget://ua-msme/legal-access",
        ],
        "pareto_archive_ref": "pdc://layer2/s8/ua-msme/allocation-pareto-archive",
        "envelope_growth_ledger_ref": "pdc://layer2/s12/ua-msme/envelope-growth-ledger",
        "growth_thermometer_ref": "pdc://layer2/s12/ua-msme/growth-thermometer",
        "override_rate_trend": "flat",
        "reuse_rate_trend": "improving",
        "held_out_status": "pending_s14",
        "resource_allocation_disposition": "advisory_only",
        "s12_public_growth_limitation": (
            "Resource allocation is a governed growth limitation, not a recommendation."
        ),
        "authority_boundary": {
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
            "rule_version_refs": [S12_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
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
        "rule_version_ref": S12_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _s13_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "audience": "PUBLIC",
        "authority_role": "projection_only",
        "projection_policy": "reads_s13_post_deploy_accountability_posture",
        "accountability_posture_ref": "pdc://layer2/s13/ua-msme/accountability-posture",
        "deployment_dossier_ref": "pdc://layer2/s13/ua-msme/deployment-dossier",
        "divergence_record_refs": ["pdc://layer2/s13/ua-msme/divergence/seeded-disconfirmation"],
        "learning_update_proposal_refs": ["learning-proposal://ua-msme/envelope-shrink"],
        "envelope_revision_ref": "envelope-revision://ua-msme/shrink/001",
        "certified_envelope_delta_ref": "certified-envelope-delta://ua-msme/s12-growth",
        "assurance_case_delta_ref": "assurance-delta://ua-msme/s13/weakened",
        "attribution_status": "attributed",
        "attribution_classes": ["design_error"],
        "learning_change_control_classes": ["reissue_required"],
        "lifecycle_reissue_disposition": "reissue_required",
        "envelope_revision_direction": "shrink",
        "assurance_case_change": "weakened",
        "mape_k_trace_ref": "mape-k://ua-msme/post-deploy",
        "public_revision_state_ref": "public-revision-state://ua-msme/s13/001",
        "public_accountability_note_ref": "public-note://ua-msme/s13/accountability",
        "public_accountability_note": (
            "Post-deploy divergence is attributed and routed to reissue without "
            "rewriting the closed case."
        ),
        "public_revision_state": {
            "revision_state_id": "public-revision-state://ua-msme/s13/001",
            "affected_claim_ids": ["rec_1"],
            "unaffected_claim_ids": ["rec_2"],
            "public_diffs": [
                {
                    "claim_id": "rec_1",
                    "revision_kind": "post_deploy_accountability_note",
                    "public_reason": "Post-deploy divergence attributed to design error.",
                }
            ],
            "closed_case_historical_meaning": "preserved",
            "silent_upgrade_allowed": False,
            "authority_role": "projection_only",
            "may_not_use_for": [
                "claim_evidence_authority",
                "current_evidence_slot",
                "production_rollout_authority",
            ],
        },
        "closed_case_historical_meaning": "preserved",
        "authority_boundary": {
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
            "rule_version_refs": [S13_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
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
        "rule_version_ref": S13_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def test_public_export_redacts_sensitive_payloads_and_preserves_audit_semantics() -> None:
    authority_envelope = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=sha("3"),
    )
    public_bundle = build_public_export_bundle(
        run_id="run-public-redaction",
        title="Public MSME support audit",
        artifacts={
            "decision_artifact": {
                "claim_id": "rec_1",
                "claim_type": "recommendation",
                "text": "Target wartime credit support to eligible MSMEs.",
                "support_refs": {
                    "data_refs": ["production-msme-panel"],
                    "method_refs": ["causal.difference_in_differences"],
                    "norm_refs": ["norm.ua.credit_eligibility"],
                },
                "hidden_benchmark_answer": "gold answer is option B",
                "provider_credentials": {"api_key": "sk-secret-token"},
                "tenant_id": "tenant-1",
                "tenant_private_cas_ref": sha("4"),
                "private_prompt": "private system prompt for internal scoring",
                "restricted_source_material": "licensed source page text",
            }
        },
        authority_envelopes=[authority_envelope],
    )

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "Target wartime credit support" in rendered
    assert "production-msme-panel" in rendered
    assert "causal.difference_in_differences" in rendered
    assert "norm.ua.credit_eligibility" in rendered
    assert "gold answer is option B" not in rendered
    assert "sk-secret-token" not in rendered
    assert "tenant-1" not in rendered
    assert "private system prompt" not in rendered
    assert "licensed source page text" not in rendered
    assert public_bundle["artifacts"]["decision_artifact"]["hidden_benchmark_answer"].startswith(
        "[POLISYOS_SECRET_KEYED_SECRET_"
    )

    projection = public_bundle["semantic_audit"]["authority_projections"][0]
    assert projection["evidence_id"] == "evidence-policy_grounding_matrix"
    assert projection["artifact_kind"] == "policy_grounding_matrix"
    assert projection["schema_name"] == "runtime_quality.policy_grounding_matrix.v1"
    assert projection["phase"] == "quality_evidence"
    assert projection["source_authority_role"] == "producer_authority"
    assert projection["source_blocking_status"] == "non_blocking"
    assert projection["authority_role"] == "projection_only"
    assert projection["allowed_scorecard_authority_role"] == "not_authoritative"
    assert projection["tenant_redacted"] is True
    assert "tenant_fingerprint" not in projection
    assert public_bundle["official_use_limits"]["official_use"] == "public_audit_only"
    private_ref_marker = public_bundle["artifacts"]["decision_artifact"]["tenant_private_cas_ref"]
    assert isinstance(private_ref_marker, dict)
    assert private_ref_marker["redacted"] is True
    assert private_ref_marker["reason"] == "tenant_private_ref"

    from polisyos.runtime.http.services.public_decision_verification import _PUBLIC_DOCUMENT

    verified_document = _PUBLIC_DOCUMENT.validate_python(public_bundle, strict=True)
    assert (
        verified_document["artifacts"]["decision_artifact"]["tenant_private_cas_ref"]
        == private_ref_marker
    )
    assert (
        "tenant_fingerprint" not in verified_document["semantic_audit"]["authority_projections"][0]
    )

    assert public_bundle["evidence_class"] == "redacted_derived"
    assert public_bundle["official_use_limits"]["official_use"] == "public_audit_only"
    assert "scorecard_authority" in public_bundle["official_use_limits"]["may_not_be_used_for"]
    assert "approval_authority" in public_bundle["official_use_limits"]["may_not_be_used_for"]
    assert public_bundle["redaction_summary"]["redacted_path_count"] >= 5


@pytest.mark.asyncio
async def test_public_export_refuses_source_limited_run_before_open_world_projection(
    tmp_path,
) -> None:
    """Source-limited runs stop at custody before downstream currentness checks.

    This fixture has no preserved source store, so its truthful first refusal is
    source custody; it cannot demonstrate open-world currentness or risk output.
    """
    from tests.unit.runtime.quality.test_generation_cycle import (
        _budget,
        _CgfGenerationPort,
    )

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    problem = _open_world_problem()
    projector = getattr(
        public_export_module,
        "project_pre_n9_open_world_limitations",
        None,
    )
    assert callable(projector)

    run = await GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        promotion_runtime=runtime,
        repo_root=REPO_ROOT,
    ).run(
        problem,
        budget_state=_budget(),
        max_cycles=1,
    )
    assert run.terminal_status == "blocked"
    assert run.promotion_port.status == "not_promoted"
    assert run.promotion_port.receipts == ()
    assert run.promotion_port.reason == (
        "generation_cycle_blocked_before_n9:voi_safety_cap_reached_without_scheduler_stop"
    )

    with pytest.raises(PublicExportRedactionError) as error_info:
        projector(
            run=run,
            design_problem=problem,
            resolver=runtime.resolver,
            repo_root=REPO_ROOT,
        )
    assert error_info.value.code == "generation_cycle_source_preservation_not_established"


class _ItemsOmittingMapping(Mapping[str, object]):
    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def items(self) -> ItemsView[str, object]:
        return {"visible": self._values["visible"]}.items()


def test_public_mapping_copy_uses_iteration_and_getitem_not_items_override() -> None:
    source = _ItemsOmittingMapping({"visible": "kept", "omitted": "must survive"})

    assert public_export_module._copy_public_mapping(source, field="mapping probe") == {
        "visible": "kept",
        "omitted": "must survive",
    }


def test_public_export_authority_audit_enumerates_all_mapping_keys() -> None:
    artifacts = _ItemsOmittingMapping(
        {
            "visible": {"status": "limited"},
            "omitted": {"status": "limited"},
        }
    )

    bundle = build_public_export_bundle(
        run_id="run-mapping-completeness",
        artifacts=artifacts,
    )
    decisions = bundle["semantic_audit"]["authority_surface_decisions"]

    assert {item["artifact_key"] for item in decisions} == {"visible", "omitted"}


def test_public_export_redacts_complete_authority_projection_and_runtime_truth() -> None:
    email = "audit.fixture@example.org"
    sensitive_value = "password=projection-secret-value"
    envelope = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=sha("c"),
    )
    envelope["owner"] = email
    envelope["evidence_id"] = "authority-record@audit.fixture.example.org"
    envelope["schema_name"] = "runtime.reader " + sensitive_value
    envelope["producer_component"] = "runtime.reader " + sensitive_value
    bundle = build_public_export_bundle(
        run_id="run-public-authority-redaction",
        artifacts={"decision": {"status": "limited"}},
        authority_envelopes=[envelope],
        runtime_truth_preservation={
            "status": "not_established",
            "limitation": email,
        },
    )

    rendered = json.dumps(bundle, sort_keys=True)
    projection = bundle["semantic_audit"]["authority_projections"][0]
    reports = bundle["semantic_audit"]["secret_pii_scan_reports"]

    assert email not in rendered
    assert "authority-record@audit.fixture.example.org" not in rendered
    assert sensitive_value not in rendered
    assert "[POLISYOS_SECRET_EMAIL_" in rendered
    assert "[POLISYOS_SECRET_PASSWORD_ASSIGNMENT_" in rendered
    assert any(report["finding_kind"] == "email" for report in reports)
    assert any(report["finding_kind"] == "password_assignment" for report in reports)
    assert projection["authority_role"] == "projection_only"
    assert projection["source_authority_role"] == "producer_authority"
    assert projection["source_blocking_status"] == "non_blocking"
    assert projection["owner"].startswith("[POLISYOS_SECRET_EMAIL_")
    assert "[POLISYOS_SECRET_PASSWORD_ASSIGNMENT_" in projection["schema_name"]
    assert bundle["runtime_truth_preservation"]["status"] == "not_established"
    assert bundle["official_use_limits"]["official_use"] == "public_audit_only"


def test_complete_export_scan_redacts_raw_projection_when_inner_scan_markers_remain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = "authority.owner@audit.fixture.example.org"
    sensitive_value = "password=untrusted-artifact-secret"
    original_scan = public_export_module._scan_public_export_artifacts

    def preserve_only_inner_scan_markers(
        *, run_id: str, artifacts: Mapping[str, object]
    ) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, str]], dict[str, object]]:
        _safe_artifacts, reports, redactions, receipt = original_scan(
            run_id=run_id, artifacts=artifacts
        )
        return dict(artifacts), reports, redactions, receipt

    monkeypatch.setattr(
        public_export_module,
        "_scan_public_export_artifacts",
        preserve_only_inner_scan_markers,
    )
    envelope = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=sha("d"),
    )
    envelope["owner"] = email
    bundle = build_public_export_bundle(
        run_id="run-complete-redaction-probe",
        artifacts={"decision": {"authorization": sensitive_value}},
        authority_envelopes=[envelope],
    )

    rendered = json.dumps(bundle, sort_keys=True)
    reports = bundle["semantic_audit"]["secret_pii_scan_reports"]
    assert email not in rendered
    assert sensitive_value not in rendered
    assert "[POLISYOS_SECRET_EMAIL_" in rendered
    assert "[POLISYOS_SECRET_KEYED_SECRET_" in rendered
    assert any(report["finding_kind"] == "email" for report in reports)
    assert any(report["finding_kind"] == "keyed_secret" for report in reports)
    assert bundle["redaction_summary"]["redacted_path_count"] >= 2
    assert bundle["semantic_audit"]["strangle_receipts"]


def test_final_scan_rejects_same_marker_at_an_unverified_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_scan = public_export_module.scan_secret_and_pii
    generated: dict[str, str] = {}
    run_id = "run-complete-redaction-path-control"

    def relocate_verified_marker(
        value: object,
        *,
        scope: str,
        artifact_ref_or_route: str,
        sanitizer: object = None,
        redact: bool = True,
        block_on_findings: bool = False,
    ) -> SecretPIIScanResult:
        result = original_scan(
            value,
            scope=scope,
            artifact_ref_or_route=artifact_ref_or_route,
            sanitizer=sanitizer,
            redact=redact,
            block_on_findings=block_on_findings,
        )
        if artifact_ref_or_route == "public-export://complete-bundle":
            redacted_payload = result.redacted_payload
            assert isinstance(redacted_payload, Mapping)
            artifacts = redacted_payload.get("artifacts")
            assert isinstance(artifacts, Mapping)
            decision = artifacts.get("decision")
            assert isinstance(decision, Mapping)
            marker = decision.get("authorization")
            assert isinstance(marker, str)
            generated["marker"] = marker
        elif artifact_ref_or_route == (f"public-export://{run_id}/complete-bundle-final"):
            marker = generated["marker"]
            assert isinstance(value, dict)
            injected = json.loads(json.dumps(value))
            runtime_truth = injected.get("runtime_truth_preservation")
            assert isinstance(runtime_truth, dict)
            runtime_truth["authorization"] = marker
            return original_scan(
                injected,
                scope=scope,
                artifact_ref_or_route=artifact_ref_or_route,
                sanitizer=sanitizer,
                redact=redact,
                block_on_findings=block_on_findings,
            )
        return result

    monkeypatch.setattr(
        public_export_module,
        "scan_secret_and_pii",
        relocate_verified_marker,
    )
    with pytest.raises(PublicExportRedactionError) as error_info:
        build_public_export_bundle(
            run_id=run_id,
            artifacts={
                "decision": {
                    "authorization": "password=real-sensitive-value",
                }
            },
            runtime_truth_preservation={"status": "not_established"},
        )

    assert error_info.value.code == "public_export_complete_scan_residual"


def test_final_scan_blocks_when_complete_redaction_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_scan = public_export_module.scan_secret_and_pii
    original_inner_scan = public_export_module._scan_public_export_artifacts

    def preserve_raw_artifacts(
        *,
        run_id: str,
        artifacts: Mapping[str, object],
    ) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, str]], dict[str, object]]:
        _safe_artifacts, reports, redactions, receipt = original_inner_scan(
            run_id=run_id,
            artifacts=artifacts,
        )
        return dict(artifacts), reports, redactions, receipt

    def remove_complete_redaction(
        value: object,
        *,
        scope: str,
        artifact_ref_or_route: str,
        sanitizer: object = None,
        redact: bool = True,
        block_on_findings: bool = False,
    ) -> SecretPIIScanResult:
        if artifact_ref_or_route == "public-export://complete-bundle":
            return SecretPIIScanResult(redacted_payload=value)
        return original_scan(
            value,
            scope=scope,
            artifact_ref_or_route=artifact_ref_or_route,
            sanitizer=sanitizer,
            redact=redact,
            block_on_findings=block_on_findings,
        )

    monkeypatch.setattr(
        public_export_module,
        "_scan_public_export_artifacts",
        preserve_raw_artifacts,
    )
    monkeypatch.setattr(
        public_export_module,
        "scan_secret_and_pii",
        remove_complete_redaction,
    )
    with pytest.raises(PublicExportRedactionError) as error_info:
        build_public_export_bundle(
            run_id="run-final-scan-removal-control",
            artifacts={"decision": {"authorization": "password=raw-secret-value"}},
        )

    assert error_info.value.code == "public_export_complete_scan_residual"


def test_public_export_still_rejects_raw_authority_source_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_ref = sha("c")
    original_projection = public_export_module._authority_projection

    def reemit_raw_source_ref(envelope: object) -> dict[str, object]:
        projection = original_projection(envelope)
        projection["unredacted_source_ref"] = source_ref
        return projection

    monkeypatch.setattr(
        public_export_module,
        "_authority_projection",
        reemit_raw_source_ref,
    )
    envelope = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=source_ref,
    )
    with pytest.raises(PublicExportRedactionError) as error_info:
        build_public_export_bundle(
            run_id="run-authority-private-ref-removal-control",
            artifacts={"decision": {"status": "limited"}},
            authority_envelopes=[envelope],
        )

    assert error_info.value.code == "public_export_tenant_private_ref_leak"


def test_public_export_uses_canonical_secret_pii_scan_for_email_redaction() -> None:
    email = "audit.fixture@example.org"
    public_bundle = build_public_export_bundle(
        run_id="run-public-email-redaction",
        artifacts={"packet": {"contact": email, "note": "public"}},
    )

    rendered = json.dumps(public_bundle, sort_keys=True)
    reports = public_bundle["semantic_audit"]["secret_pii_scan_reports"]
    assert email not in rendered
    assert public_bundle["artifacts"]["packet"]["contact"].startswith("[POLISYOS_SECRET_EMAIL_")
    assert any(report["finding_kind"] == "email" for report in reports)
    assert public_bundle["redaction_summary"]["strangle_receipt"]["replacement_ref"] == (
        "polisyos.core.llm.sanitization.scan_secret_and_pii"
    )


def test_public_export_reads_policy_design_case_projection_without_exposing_authority() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-redaction",
        artifacts={
            "decision_artifact": {
                "claim_id": "rec_1",
                "text": "Target wartime credit support to eligible MSMEs.",
                "provider_credentials": {"api_key": "sk-secret-token"},
                "tenant_id": "tenant-sensitive",
            }
        },
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload={
            "public_export_classification": "public_redacted_projection",
            "decision_context": {"public_export_status": "publishable"},
            "publishability": "publishable",
        },
    )

    projection = public_bundle["projection_semantics"]
    assert projection["primary_state"] == "redacted"
    assert {"publishable", "redacted", "projection_only"} <= set(projection["states"])
    assert projection["authority_role"] == "projection_only"
    assert "scorecard_authority" in projection["may_not_be_used_for"]

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "Target wartime credit support" in rendered
    assert "sk-secret-token" not in rendered
    assert "tenant-sensitive" not in rendered


def test_public_export_blocks_scalar_welfare_without_frontier_provenance() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="scalar_welfare_aggregate_without_frontier",
    ):
        build_public_export_bundle(
            run_id="run-public-scalar-welfare",
            artifacts={
                "decision_artifact": {
                    "claim_id": "claim:welfare:1",
                    "text": "Publish selected welfare option.",
                },
                "welfare_score": 0.72,
            },
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload={
                "public_export_classification": "public_redacted_projection",
                "decision_context": {"public_export_status": "publishable"},
                "publishability": "publishable",
            },
        )


def test_public_export_blocks_unverified_candidate_in_public_artifact() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="candidate_firewall_candidate_unverified",
    ):
        build_public_export_bundle(
            run_id="run-public-candidate-firewall",
            artifacts={
                "public_summary": {
                    "claim_refs": ["hypothesis-candidate:public-claim-1"],
                    "hypothesis_ledger": {
                        "schema_version": "policyos.runtime.hypothesis_ledger.v1",
                        "run_id": "run-wave6f",
                        "job_id": "job-wave6f",
                        "entries": [
                            {
                                "candidate_id": "hypothesis-candidate:public-claim-1",
                                "candidate_ref": "hypothesis-candidate:public-claim-1",
                                "source_class": "llm_drafter",
                                "candidate_kind": "public_projection_claim",
                                "target_authority_slots": ["projection_authority"],
                                "target_claim_ids": ["rec_1"],
                                "prompt_fingerprint": "sha256:" + "1" * 64,
                                "tool_refs": ["tool-output:public-projection"],
                                "repair_decision_lineage": ["repair:none"],
                                "authority_envelope": {
                                    "authoritative_for": ["candidate_hypothesis"],
                                    "may_not_use_for": ["projection_authority"],
                                },
                                "admission_state": "candidate_unverified",
                            }
                        ],
                    },
                }
            },
            authority_envelopes=[],
        )


def test_public_export_rejects_omitted_blocked_claim_without_omission_manifest() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="public_export_omission_manifest_missing",
    ):
        build_public_export_bundle(
            run_id="run-public-omission",
            artifacts={
                "claims_manifest": {
                    "included_claim_ids": ["rec_2"],
                    "omitted_claim_ids": ["rec_1"],
                }
            },
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload={
                "authority_role": "final_decision_artifact",
                "closeout_verdict": {
                    "status": "blocked",
                    "verdict": "cannot_closeout",
                    "can_closeout": False,
                    "issues": [
                        {
                            "code": "blocked_claim_missing_anchor",
                            "severity": "fail",
                            "message": "Claim rec_1 is blocked.",
                            "claim_ids": ["rec_1"],
                        }
                    ],
                },
            },
        )


def test_public_export_surfaces_omission_manifest_and_projection_contract_status() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-omission",
        artifacts={
            "claims_manifest": {
                "included_claim_ids": ["rec_2"],
                "omitted_claim_ids": ["rec_1"],
            }
        },
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload={
            "authority_role": "final_decision_artifact",
            "audit_refs": ["audit://pdc/w5a/public-export"],
            "closeout_verdict": {
                "status": "blocked",
                "verdict": "cannot_closeout",
                "can_closeout": False,
                "issues": [
                    {
                        "code": "omitted_blocked_claim",
                        "severity": "omission",
                        "message": "Claim rec_1 is omitted from the public bundle.",
                        "claim_ids": ["rec_1"],
                        "module_id": "public_export",
                        "evidence_ref": sha("9"),
                    }
                ],
            },
        },
    )

    projection = public_bundle["projection_semantics"]
    assert projection["contract_verification_status"] == "pass"
    assert "audit://pdc/w5a/public-export" in projection["audit_refs"]
    assert projection["omission_manifest"][0]["claim_ids"] == ["rec_1"]
    assert public_bundle["semantic_audit"]["omission_manifest"] == projection["omission_manifest"]
    assert public_bundle["semantic_audit"]["projection_contract_verification"]["status"] == "pass"


def test_public_export_surfaces_rule_evolution_annotation_without_authority_upgrade() -> None:
    old_registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-05",
        version="2026.05",
        effective_at="2026-05-22T00:00:00+00:00",
        rule_refs=[
            {
                "requirement_id": "req.credit_support",
                "logic": {"predicate": "liquidity_gap", "threshold": 0.2},
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
            }
        ],
        taxonomy_refs=[
            {
                "taxonomy_id": "taxonomy.policy_obligation",
                "version": "2026.05",
                "ref": sha("a"),
            }
        ],
        evidence_ref=sha("b"),
        runtime_event_ref="event://rule-evolution/2026-05",
    )
    changed_registry = build_rule_evolution_registry(
        registry_id="rule-registry-2026-07",
        version="2026.07",
        effective_at="2026-07-01T00:00:00+00:00",
        previous_registry=old_registry,
        rule_refs=[
            {
                "requirement_id": "req.credit_support.v2",
                "logic": {"predicate": "liquidity_gap", "threshold": 0.35},
                "taxonomy_refs": ["taxonomy.policy_obligation.v1"],
                "authority_purpose": "admissibility",
            }
        ],
        taxonomy_refs=old_registry["taxonomy_refs"],
        alias_remaps=[
            {
                "from_requirement_id": "req.credit_support",
                "to_requirement_id": "req.credit_support.v2",
            }
        ],
        evidence_ref=sha("c"),
        runtime_event_ref="event://rule-evolution/2026-07",
    )

    public_bundle = build_public_export_bundle(
        run_id="run-public-rule-evolution",
        artifacts={
            "rule_evolution_public_annotation": changed_registry["public_annotation"],
        },
        authority_envelopes=[],
    )

    annotations = public_bundle["semantic_audit"]["rule_evolution_annotations"]
    assert annotations[0]["public_annotation_state"] == "semantic_change"
    assert annotations[0]["revalidation_state"] == "revalidation_required"
    assert annotations[0]["silent_upgrade_allowed"] is False
    assert public_bundle["authority_role"] == "projection_only"


def test_public_export_surfaces_lifecycle_public_revision_state_without_authority_upgrade() -> None:
    lifecycle_report = build_lifecycle_reissue_report(
        report_id="lifecycle-reissue-public",
        case_id="pdc-R_hds_red_control",
        claim_ids=["rec_1", "rec_2"],
        source_events=[
            {
                "event_id": "source-stale-rec-1",
                "event_type": "source_invalidation",
                "invalidation_type": "stale",
                "affected_claim_ids": ["rec_1"],
                "reason": "Primary data source freshness window expired.",
                "evidence_ref": sha("1"),
                "runtime_event_ref": "event://source/stale-rec-1",
                "occurred_at": "2026-07-02T00:00:00+00:00",
            }
        ],
        evidence_ref=sha("2"),
        runtime_event_ref="event://policy-design-case/lifecycle-reissue/public",
    )

    public_bundle = build_public_export_bundle(
        run_id="run-public-lifecycle",
        artifacts={
            "lifecycle_reissue_report": lifecycle_report,
        },
        authority_envelopes=[],
    )

    revision_states = public_bundle["semantic_audit"]["public_revision_states"]
    assert revision_states[0]["affected_claim_ids"] == ["rec_1"]
    assert revision_states[0]["unaffected_claim_ids"] == ["rec_2"]
    assert revision_states[0]["silent_upgrade_allowed"] is False
    assert revision_states[0]["authority_role"] == "projection_only"
    assert "claim_evidence_authority" in revision_states[0]["may_not_use_for"]
    assert public_bundle["authority_role"] == "projection_only"


@pytest.mark.parametrize(
    "recourse_pointer",
    [
        None,
        {
            "uri": "https://appeals.example.test/policy-design-case/run-public-redaction",
            "verification_status": "unreachable",
            "verified_at": "2026-05-22T10:00:00Z",
            "verification_ref": "runtime-event://recourse-pointer/unreachable",
        },
    ],
)
def test_public_export_blocks_high_stakes_contested_production_without_reachable_recourse(
    recourse_pointer: dict[str, object] | None,
) -> None:
    projection_payload: dict[str, object] = {
        "publishability": "publishable",
        "contestability_status": "contested",
        "stakes": "high_stakes",
        "authority_level": "production",
        "decision_context": {"public_export_status": "publishable"},
    }
    if recourse_pointer is not None:
        projection_payload["recourse_pointer"] = recourse_pointer

    with pytest.raises(
        PublicExportRedactionError,
        match="public_export_recourse_pointer_unreachable",
    ):
        build_public_export_bundle(
            run_id="run-public-redaction",
            artifacts={"decision_artifact": {"claim_id": "rec_1"}},
            authority_envelopes=[],
            policy_design_case={
                **policy_design_case(),
                "contestability_status": "contested",
                "stakes": "high_stakes",
            },
            projection_payload=projection_payload,
        )


def test_public_export_official_use_guard_rejects_authority_upgrade() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-redaction",
        artifacts={"summary": {"text": "Public summary."}},
        authority_envelopes=[],
    )
    public_bundle["authority_role"] = "producer_authority"

    with pytest.raises(PublicExportRedactionError, match="public_export_not_authority"):
        assert_public_export_official_use_limits(public_bundle)


def test_public_export_rejects_unexplained_replay_drift_even_with_scorecard_files() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="public_export_replay_drift_unexplained",
    ):
        build_public_export_bundle(
            run_id="run-public-redaction",
            artifacts={
                "quality_scorecard_file": "quality_scorecard.json",
                "quality_scorecard_summary": {
                    "quality_status": "pass",
                    "approval_state": "approval_ready",
                },
                "drift_explanation": {
                    "schema_version": "policyos.drift_explanation.v1",
                    "status": "unexplained_drift",
                    "production_readiness": "fail",
                    "summary": {
                        "difference_count": 1,
                        "unexplained_difference_count": 1,
                        "drift_sources": ["data"],
                        "max_impact": "high",
                    },
                },
            },
            authority_envelopes=[],
        )


def test_public_export_rejects_accepted_non_ready_replay_drift() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="public_export_replay_drift_unbounded",
    ):
        build_public_export_bundle(
            run_id="run-public-redaction",
            artifacts={
                "quality_scorecard_summary": {
                    "quality_status": "pass",
                    "approval_state": "approval_ready",
                },
                "drift_explanation": {
                    "schema_version": "policyos.drift_explanation.v1",
                    "status": "accepted_drift_non_ready",
                    "production_readiness": "fail",
                    "summary": {
                        "difference_count": 2,
                        "accepted_difference_count": 2,
                        "unexplained_difference_count": 0,
                        "drift_sources": ["registry"],
                        "max_impact": "high",
                    },
                    "blocking_failure": {
                        "code": "authority_replay_drift_unbounded",
                    },
                },
            },
            authority_envelopes=[],
        )


def _s14_public_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "public_export_classification": "public_redacted_projection",
        "decision_context": {"public_export_status": "publishable"},
        "s14_universality_assurance_ref": "pdc://layer2/s14/universality-assurance-case",
        "universality_claim_gate_ref": "pdc://layer2/s14/universality-claim-gate",
        "universality_claim_disposition": "universal_claim_limited",
        "declared_operation_envelope_ref": "pdc://layer2/s14/declared-envelope",
        "d4_corpus_track_coverage_ref": "pdc://layer2/s14/d4-corpus-track-coverage",
        "d4_corpus_track_coverage_status": "pass",
        "expert_oracle_bootstrap_ref": "pdc://layer2/s14/expert-oracle-bootstrap",
        "expert_oracle_seed_only_layer_refs": ["weak_gold", "shadow_candidate_pool"],
        "breadth_floor_config_ref": "pdc://layer2/s14/breadth-floor-config",
        "breadth_floor_status": "pass",
        "excluded_domain_refs": ["domain://defense-targeting"],
        "universality_baseline_comparison_ref": "pdc://layer2/s14/baseline-comparison",
        "baseline_comparison_status": "pass",
        "grounded_authority_coverage_ref": "pdc://layer2/s14/grounded-authority",
        "grounded_authority_status": "pass",
        "a_firewall_refs": ["pdc://layer2/s6/a-firewall/measurability"],
        "claim_evidence_binding_refs": ["claim-binding://s14/universal-envelope/001"],
        "value_choice_provenance_refs": ["value-choice://s8/s14/authorized-schedule"],
        "mandate_legitimacy_refs": ["mandate://s14/governance-board/universality"],
        "capacity_check_refs": ["capacity://s14/capacity-constrained-cases"],
        "evaluation_status_composition_ref": "pdc://layer2/s14/status-composition",
        "status_composition_limit_refs": ["limitation://s14/weak-gold-seed-only"],
        "envelope_revision_dynamics_ref": "pdc://layer2/s14/envelope-revision-dynamics",
        "envelope_revision_dynamics_status": "pass",
        "axis_scorecard_ref": "pdc://layer2/s14/axis-scorecard",
        "axis_scorecard_rows": [
            {
                "axis_ref": "ACTOR.state_capacity_feasibility",
                "declared_posture": "limited",
                "battery_status": "pass",
                "limitation_refs": ["limitation://s14/capacity"],
            }
        ],
        "out_of_envelope_axis_refs": ["SYSTEM.dynamics_feedback"],
        "not_tested_axis_refs": ["SYSTEM.dynamics_feedback"],
        "hard_corner_case_refs": ["sealed://s14/capacity-constrained-refugee-services"],
        "sealed_battery_run_ref": "pdc://layer2/s14/sealed-battery-run",
        "sealed_battery_freeze_hash": "sha256:" + "4" * 64,
        "sealed_battery_integrity_status": "pass",
        "mechanism_generality_report_ref": "pdc://layer2/s14/mechanism-generality",
        "mechanism_generality_status": "pass",
        "sublinear_marginal_bespoke_cost_status": "pass",
        "skeptic_defeater_refs": [
            "pdc://layer2/s14/defeater/bespoke_disguise_defeater",
            "pdc://layer2/s14/defeater/confident_theater_defeater",
            "pdc://layer2/s14/defeater/failure_boundary_defeater",
            "pdc://layer2/s14/defeater/single_axis_universality_defeater",
            "pdc://layer2/s14/defeater/frozen_once_defeater",
            "pdc://layer2/s14/defeater/first_call_defeater",
        ],
        "skeptic_defeater_statuses": {
            "bespoke_disguise_defeater": "pass",
            "confident_theater_defeater": "pass",
            "failure_boundary_defeater": "pass",
            "single_axis_universality_defeater": "pass",
            "frozen_once_defeater": "pass",
            "first_call_defeater": "pass",
        },
        "s9_projection_faithfulness_refs": ["pdc://layer2/s9/faithfulness/public"],
        "public_universality_limitation": (
            "Scoped universality is projection-only and limited to the declared envelope."
        ),
        "authority_boundary": {
            "authoritative_for": ["s14_universality_claim_gate"],
            "may_not_use_for": [
                "production_rollout_authority",
                "production_recommendation",
                "recommendation_authority",
                "publication_authority",
                "approval_authority",
                "claim_authority",
                "runtime_closeout_authority",
                "scorecard_authority",
                "preference_learning",
                "automated_value_learning",
                "aggregate_universal_score",
            ],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S14_RULE_VERSION_REF],
        },
        "may_not_be_used_for": [
            "production_rollout_authority",
            "production_recommendation",
            "recommendation_authority",
            "publication_authority",
            "approval_authority",
            "claim_authority",
            "runtime_closeout_authority",
            "scorecard_authority",
            "preference_learning",
            "automated_value_learning",
            "aggregate_universal_score",
        ],
        "rule_version_ref": S14_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def test_public_export_surfaces_limited_universality_claim_as_projection_only() -> None:
    from polisyos.runtime.quality.projection_semantics import (
        verify_s14_universality_projection_consumer_contract,
    )

    bundle = build_public_export_bundle(
        run_id="run-public-s14-universality",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s14_public_projection_payload(),
    )

    assert bundle["authority_role"] == "projection_only"
    semantic_audit = bundle["semantic_audit"]
    verification = semantic_audit["s14_universality_projection_contract_verification"]
    assert verification["status"] == "pass"
    projection = bundle["projection_semantics"]
    universality = semantic_audit["s14_universality_projection"]
    emitted_s14_verification = verify_s14_universality_projection_consumer_contract(
        projections={"public": universality},
    )
    assert emitted_s14_verification["status"] == verification["status"] == "pass"
    assert universality["universality_claim_disposition"] == "universal_claim_limited"
    assert universality["sealed_battery_freeze_hash"] is None
    assert (
        "semantic_audit.s14_universality_projection.sealed_battery_freeze_hash"
        in bundle["redaction_summary"]["erased_paths"]
    )
    assert projection["authority_role"] == "projection_only"
    assert "production_recommendation" in projection["may_not_be_used_for"]


def test_public_export_blocks_hidden_battery_material_and_gold_labels() -> None:
    bundle = build_public_export_bundle(
        run_id="run-public-s14-redaction",
        artifacts={
            "public_summary": {
                "safe_ref": "pdc://layer2/s14/sealed-battery-run",
                "sealed_fixture_contents": {"case_id": "s14-hidden"},
                "gold_labels": ["sealed expected boundary"],
                "expert_oracle_private_notes": "private oracle note",
            }
        },
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s14_public_projection_payload(),
    )

    serialized = json.dumps(bundle)
    assert "s14-hidden" not in serialized
    assert "sealed expected boundary" not in serialized
    assert "private oracle note" not in serialized
    assert bundle["artifacts"]["public_summary"]["sealed_fixture_contents"].startswith(
        "[POLISYOS_SECRET_KEYED_SECRET_"
    )
    assert bundle["redaction_summary"]["redacted_path_count"] >= 3


def test_public_export_blocks_s14_as_production_or_recommendation_authority() -> None:
    payload = _s14_public_projection_payload(
        authority_boundary={
            "authoritative_for": [
                "s14_universality_claim_gate",
                "production_rollout_authority",
                "recommendation_authority",
            ],
            "may_not_use_for": ["claim_authority"],
            "source_authority": "deterministic_producer",
            "posture": "shadow",
            "rule_version_refs": [S14_RULE_VERSION_REF],
        }
    )

    with pytest.raises(
        PublicExportRedactionError,
        match="s14_as_production_or_recommendation_authority",
    ):
        build_public_export_bundle(
            run_id="run-public-s14-authority-laundering",
            artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload=payload,
        )


def test_public_export_requires_s9_faithfulness_pass_for_projection_release() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match=r"s9_projection_faithfulness_failed|s9_projection_added_claim",
    ):
        build_public_export_bundle(
            run_id="run-public-s9-faithfulness",
            artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload={
                "public_export_classification": "public_redacted_projection",
                "decision_context": {"public_export_status": "publishable"},
                "s9_projection_faithfulness": _s9_public_faithfulness_payload(
                    faithfulness_status="fail",
                    issue_codes=["s9_projection_added_claim"],
                    added_claim_refs=["claim://ua-msme/new-public-benefit-claim"],
                ),
            },
        )


def test_public_export_blocks_s9_projection_that_hides_redacted_blocker() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="s9_redaction_hides_blocker",
    ):
        build_public_export_bundle(
            run_id="run-public-s9-redaction-blocker",
            artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload={
                "public_export_classification": "public_redacted_projection",
                "decision_context": {"public_export_status": "publishable"},
                "s9_projection_faithfulness": _s9_public_faithfulness_payload(
                    faithfulness_status="fail",
                    issue_codes=["s9_redaction_hides_blocker"],
                    hidden_blocker_refs=["pdc://layer2/s6/ua-msme/strategic-response-blocker"],
                ),
                "omission_manifest": [],
            },
        )


def test_public_export_without_s9_block_keeps_existing_projection_behavior() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-no-s9",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload={
            "public_export_classification": "public_redacted_projection",
            "decision_context": {"public_export_status": "publishable"},
            "publishability": "publishable",
        },
    )

    projection = public_bundle["projection_semantics"]
    assert projection["authority_role"] == "projection_only"
    assert projection["contract_verification_status"] == "pass"
    assert "s9_projection_faithfulness" not in projection
    assert public_bundle["semantic_audit"]["projection_contract_verification"]["status"] == "pass"


def test_s10_public_export_shows_forecast_tier_without_recommendation_authority() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s10-forecast",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s10_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    forecast = public_bundle["semantic_audit"]["s10_forecast_projection"]
    assert forecast["forecast_tier"] == "observable_calibrated"
    assert forecast["observable_subset_calibration_status"] == "pass"
    assert forecast["uncertainty_interval_refs"] == ["interval://ua-msme/credit-access/95"]
    assert public_bundle["semantic_audit"]["projection_extensions"]["limitations"]
    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "production_recommendation_text" not in rendered
    assert "recommendation_authority" not in rendered


def test_s10_machine_export_requires_calibration_and_source_refs() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="s10_machine_export_requires_calibration_and_source_refs",
    ):
        build_public_export_bundle(
            run_id="run-public-s10-machine-missing-refs",
            artifacts={"machine_summary": {"claim_refs": ["rec_1"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload=_s10_public_projection_payload(
                forecast_calibration_record_ref=None,
                source_contract_ref=None,
                method_validity_ref=None,
                credible_evaluation_evidence_ref=None,
            ),
        )


def test_s10_machine_export_preserves_design_graph_context_and_method_validity_refs() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s10-machine-refs",
        artifacts={"machine_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s10_public_projection_payload(),
    )

    s10_projection = public_bundle["semantic_audit"]["s10_forecast_projection"]
    assert s10_projection["design_graph_ref"] == ("pdc://layer2/s5/ua-msme/recursive-design-graph")
    assert s10_projection["prediction_context_ref"] == (
        "pdc://layer2/s10/ua-msme/prediction-context"
    )
    assert s10_projection["source_contract_ref"] == "source-contract://ua-msme/panel"
    assert s10_projection["method_validity_ref"] == "method-validity://foundry/causal/local"
    assert s10_projection["credible_evaluation_evidence_ref"] == (
        "evidence://ua-msme/credible-evaluation"
    )
    assert s10_projection["authority_boundary"]["may_not_use_for"]


def test_public_projection_does_not_promote_s11_to_recommendation_authority() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s11-predictive",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s11_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    s11_projection = public_bundle["semantic_audit"]["s11_predictive_projection"]
    assert s11_projection["s11_public_limitation"]
    assert "production_recommendation" in projection["may_not_be_used_for"]
    assert projection["authority_role"] == "projection_only"

    assert s11_projection["effective_predictive_posture"] == "limited_by_weakest_boundary"
    assert s11_projection["proof_carrying_analytics_ref"].startswith("pdc://layer2/s11/")

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "recommendation_authority" not in rendered
    assert "production_recommendation_text" not in rendered


def test_public_export_projects_g3_audit_refs_without_raw_proof_or_search_payloads() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-g3-analytics-search",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_g3_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    g3_projection = public_bundle["semantic_audit"]["layer3_g3_analytics_search_projection"]

    assert g3_projection["status"] == "pass"
    assert g3_projection["certificate_resolution_report_ref"].endswith(
        "layer3_g3_certificate_resolution_report.json"
    )
    assert g3_projection["resolved_certificate_count"] == 1
    assert "claim_authority" in projection["may_not_be_used_for"]
    assert g3_projection["authority_role"] == "projection_only"
    assert g3_projection["resolved_certificate_count"] == 1
    assert g3_projection["raw_proof_payload_exported"] is False
    assert g3_projection["raw_cas_manifest_exported"] is False
    assert g3_projection["raw_query_ledger_exported"] is False

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "raw material must not reach PUBLIC" not in rendered
    assert "secret-cas-id" not in rendered
    assert "select * from hidden_ir_catalog" not in rendered


def test_public_projection_shows_growth_limitation_without_allocation_authority() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s12-resource-economics",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s12_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    s12_projection = public_bundle["semantic_audit"]["s12_resource_projection"]
    assert s12_projection["s12_public_growth_limitation"]
    assert s12_projection["explore_exploit_posture"] == "balanced_governed"
    assert s12_projection["override_rate_trend"] == "flat"
    assert s12_projection["reuse_rate_trend"] == "improving"
    assert "production_recommendation" in projection["may_not_be_used_for"]
    assert projection["authority_role"] == "projection_only"

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert "allocation_recommendation_text" not in rendered
    assert "selected_policy_ref" not in rendered
    assert "allocation-policy://ua-msme/balanced-governed" not in rendered


def test_public_projection_surfaces_accountability_note_and_preserves_historical_meaning() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s13-accountability",
        artifacts={"public_summary": {"claim_refs": ["rec_1", "rec_2"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s13_public_projection_payload(),
    )

    projection = public_bundle["projection_semantics"]
    s13_projection = public_bundle["semantic_audit"]["s13_post_deploy_accountability_projection"]
    assert s13_projection["public_accountability_note"]
    assert s13_projection["envelope_revision_direction"] == "shrink"
    assert s13_projection["closed_case_historical_meaning"] == "preserved"
    assert projection["authority_role"] == "projection_only"
    assert "current_evidence_slot" in projection["may_not_be_used_for"]


def test_public_accountability_note_projects_existing_public_revision_state() -> None:
    public_bundle = build_public_export_bundle(
        run_id="run-public-s13-revision-state",
        artifacts={"public_summary": {"claim_refs": ["rec_1", "rec_2"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s13_public_projection_payload(),
    )

    revision_states = public_bundle["semantic_audit"]["public_revision_states"]
    accountability_projection = public_bundle["semantic_audit"][
        "s13_post_deploy_accountability_projection"
    ]

    assert revision_states[0]["affected_claim_ids"] == ["rec_1"]
    assert revision_states[0]["unaffected_claim_ids"] == ["rec_2"]
    assert revision_states[0]["silent_upgrade_allowed"] is False
    assert accountability_projection["public_revision_state_ref"] == (
        "public-revision-state://ua-msme/s13/001"
    )
    assert accountability_projection["public_accountability_note_ref"] == (
        "public-note://ua-msme/s13/accountability"
    )


def test_public_projection_reuses_public_revision_state_silent_upgrade_firewall() -> None:
    with pytest.raises(PublicExportRedactionError, match="silent_upgrade"):
        build_public_export_bundle(
            run_id="run-public-s13-silent-upgrade",
            artifacts={"public_summary": {"claim_refs": ["rec_1", "rec_2"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload=_s13_public_projection_payload(
                public_revision_state={
                    "revision_state_id": "public-revision-state://ua-msme/s13/bad",
                    "affected_claim_ids": ["rec_1"],
                    "unaffected_claim_ids": ["rec_2"],
                    "public_diffs": [],
                    "closed_case_historical_meaning": "changed",
                    "silent_upgrade_allowed": True,
                    "authority_role": "producer_authority",
                    "may_not_use_for": [],
                }
            ),
        )


@pytest.mark.asyncio
async def test_identity_current_source_limited_run_is_refused_before_n9_projection(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.runtime.quality.generation_cycle import GENERATION_CYCLE_SCHEMA_VERSION
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from tests.unit.runtime.quality.test_s8_blocked_generation_owner import (
        _owner_source_harness,
        _track_currentness_observations,
    )

    harness = await _owner_source_harness(
        tmp_path,
        disposition="stop",
        runtime_source_store=False,
        identity_current=True,
        monkeypatch=monkeypatch,
    )
    run = harness["run"]
    assert run.schema_version == GENERATION_CYCLE_SCHEMA_VERSION
    assert run.source_custody_limitation is not None
    assert run.source_custody_limitation.reason_code == "source_store_unavailable"
    observations = _track_currentness_observations(monkeypatch)

    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "projection-resolver"))
    # The currentness witness and exact source marker isolate the custody gate.
    # If that gate is removed, projection proceeds to the downstream open-world
    # checks and returns a different refusal, so this exact assertion turns red.
    with pytest.raises(PublicExportRedactionError) as refused:
        public_export_module.project_pre_n9_open_world_limitations(
            run=run,
            design_problem=harness["problem"],
            resolver=runtime.resolver,
            repo_root=harness["source_root"],
        )
    assert refused.value.code == "generation_cycle_source_custody_not_established"
    assert observations
    assert all(
        item
        == {
            "recorded_identity_status": "established",
            "recorded_deployment_identity": run.deployment_identity,
        }
        for item in observations
    )


def test_public_export_preserves_s10_welfare_mapping_as_projection_data() -> None:
    welfare_comparison = {
        "comparison_status": "limited",
        "evidence_ref": "welfare://comparison/source",
        "s8_value_choice_provenance_ref": "value-choice://s8/welfare",
        "s8_value_tradeoff_disclosure_ref": "value-tradeoff://s8/welfare",
    }
    public_bundle = build_public_export_bundle(
        run_id="run-public-s10-welfare-mapping",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s10_public_projection_payload(
            welfare_comparison=welfare_comparison,
        ),
    )

    projection = public_bundle["semantic_audit"]["s10_forecast_projection"]
    assert projection["welfare_comparison"] == welfare_comparison
    assert projection["authority_role"] == "projection_only"


def test_public_export_rejects_non_string_keys_in_s10_projection_mapping() -> None:
    with pytest.raises(
        PublicExportRedactionError,
        match="public_export_mapping_key_invalid",
    ):
        build_public_export_bundle(
            run_id="run-public-s10-invalid-welfare-mapping",
            artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
            authority_envelopes=[],
            policy_design_case=policy_design_case(),
            projection_payload=_s10_public_projection_payload(
                welfare_comparison={1: "not a public mapping key"},
            ),
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [("3", 3), (b"4", 4), (3, 3), (-2, 0), ("invalid", 0)],
)
def test_public_export_int_projection_preserves_supported_values(
    value: object,
    expected: int,
) -> None:
    assert public_export_module._int(value) == expected


def test_complete_export_intake_reads_full_authority_envelope_sequence() -> None:
    class HidingEnvelopeSequence(Sequence[Mapping[str, object]]):
        def __init__(self, values: list[Mapping[str, object]]) -> None:
            self._values = values

        def __getitem__(self, index: int) -> Mapping[str, object]:
            return self._values[index]

        def __len__(self) -> int:
            return len(self._values)

        def __iter__(self) -> Iterator[Mapping[str, object]]:
            return iter(self._values[:1])

    first = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=sha("a"),
    )
    first["owner"] = "first.audit@example.org"
    second = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=sha("b"),
    )
    second["owner"] = "second.audit@example.org"

    bundle = build_public_export_bundle(
        run_id="run-authority-envelope-sequence-intake",
        artifacts={"decision": {"status": "limited"}},
        authority_envelopes=HidingEnvelopeSequence([first, second]),
    )

    projections = bundle["semantic_audit"]["authority_projections"]
    rendered = json.dumps(bundle, sort_keys=True)
    assert len(projections) == 2
    assert "first.audit@example.org" not in rendered
    assert "second.audit@example.org" not in rendered
    assert sum("[POLISYOS_SECRET_EMAIL_" in item["owner"] for item in projections) == 2


def test_complete_export_recursively_scans_nested_mapping_and_sequence_subclasses() -> None:
    class HidingDict(dict[str, object]):
        def items(self) -> ItemsView[str, object]:
            return {"visible": self["visible"]}.items()

    class HidingMapping(Mapping[str, object]):
        def __init__(self, values: dict[str, object]) -> None:
            self._values = values

        def __getitem__(self, key: str) -> object:
            return self._values[key]

        def __iter__(self) -> Iterator[str]:
            return iter(self._values)

        def __len__(self) -> int:
            return len(self._values)

        def items(self) -> ItemsView[str, object]:
            return {"visible": self._values["visible"]}.items()

    secret = "pass" + "word=nested-private-secret-value"
    email = "nested.audit@example.org"
    hidden = HidingDict({"visible": f"contact {email}", "private_prompt": secret})

    generic_mapping = HidingMapping({"visible": f"contact {email}", "private_prompt": secret})

    for index, nested_input in enumerate((hidden, generic_mapping)):
        bundle = build_public_export_bundle(
            run_id=f"run-nested-mapping-intake-{index}",
            artifacts={"decision": {"status": "limited"}},
            runtime_truth_preservation={"nested": nested_input},
        )
        nested = bundle["runtime_truth_preservation"]["nested"]
        nested_mapping = nested if isinstance(nested, Mapping) else nested[1]
        reports = bundle["semantic_audit"]["secret_pii_scan_reports"]
        rendered = json.dumps(bundle, sort_keys=True)

        assert "[POLISYOS_SECRET_EMAIL_" in rendered
        assert email not in rendered
        assert bundle["semantic_audit"]["strangle_receipts"]
        assert bundle["redaction_summary"]["redacted_path_count"] >= 1
        assert isinstance(nested_mapping, Mapping)
        assert "private_prompt" in nested_mapping
        assert secret not in rendered
        assert "[POLISYOS_SECRET_KEYED_SECRET_" in rendered
        assert any(report["finding_kind"] == "keyed_secret" for report in reports)


def test_complete_export_recursively_scans_nested_sequence_subclasses() -> None:
    class HidingSequence(Sequence[object]):
        def __init__(self, values: list[object]) -> None:
            self._values = values

        def __getitem__(self, index: int) -> object:
            return self._values[index]

        def __len__(self) -> int:
            return len(self._values)

        def __iter__(self) -> Iterator[object]:
            return iter(self._values[:1])

    secret = "pass" + "word=nested-sequence-secret-value"
    bundle = build_public_export_bundle(
        run_id="run-nested-sequence-intake",
        artifacts={"decision": {"status": "limited"}},
        runtime_truth_preservation={
            "nested": HidingSequence(["visible", {"private_prompt": secret}])
        },
    )

    rendered = json.dumps(bundle, sort_keys=True)
    nested = bundle["runtime_truth_preservation"]["nested"]
    assert isinstance(nested, list)
    assert nested[0] == "visible"
    assert "private_prompt" in nested[1]
    assert secret not in rendered
    assert "[POLISYOS_SECRET_KEYED_SECRET_" in rendered
    assert bundle["semantic_audit"]["strangle_receipts"]


def test_public_export_rejects_non_string_nested_mapping_keys_before_collision() -> None:
    with pytest.raises(PublicExportRedactionError) as error_info:
        build_public_export_bundle(
            run_id="run-non-string-mapping-key",
            artifacts={"decision": {1: "integer key", "1": "string key"}},
        )

    assert error_info.value.code == "public_export_mapping_key_invalid"


def test_public_export_rejects_opaque_json_leaves_before_fastapi_encoding() -> None:
    from dataclasses import dataclass

    from fastapi.encoders import jsonable_encoder
    from pydantic import BaseModel

    marker = "password=raw-nested-export-marker"

    class NestedModel(BaseModel):
        password: str

    @dataclass
    class NestedDataclass:
        password: str

    class NestedObject:
        def __init__(self, password: str) -> None:
            self.password = password

    values: list[object] = [
        NestedModel(password=marker),
        NestedDataclass(password=marker),
        NestedObject(marker),
        object(),
        float("nan"),
        float("inf"),
        b"password=raw-nested-export-marker",
        bytearray(b"password=raw-nested-export-marker"),
        {marker},
        iter([marker]),
    ]

    for value in values:
        error_code: str | None = None
        bundle: dict[str, object] | None = None
        try:
            bundle = build_public_export_bundle(
                run_id="run-opaque-json-leaf",
                artifacts={"decision": {"status": "limited"}},
                runtime_truth_preservation={"nested": [{"untrusted": value}]},
            )
        except PublicExportRedactionError as exc:
            error_code = exc.code

        if error_code is not None:
            assert error_code == "public_export_value_invalid"
            continue

        assert bundle is not None
        wire_value = jsonable_encoder(bundle)
        assert marker not in repr(wire_value)
        pytest.fail(
            "opaque or non-finite input reached FastAPI's JSON encoder instead of failing closed"
        )


def test_public_export_refuses_cycles_in_supplied_json() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)

    with pytest.raises(PublicExportRedactionError) as error_info:
        build_public_export_bundle(
            run_id="run-cyclic-json",
            artifacts={"decision": {"status": "limited"}},
            runtime_truth_preservation={"nested": cyclic},
        )

    assert error_info.value.code == "public_export_payload_cycle"


def test_public_export_fastapi_encoding_preserves_valid_json_and_projection_status() -> None:
    from fastapi.encoders import jsonable_encoder

    supplied = {"nested": [None, True, 4, 2.5, "visible"]}
    bundle = build_public_export_bundle(
        run_id="run-valid-json-domain",
        artifacts={"decision": {"status": "limited"}},
        runtime_truth_preservation=supplied,
    )

    wire_value = jsonable_encoder(bundle)

    assert wire_value["runtime_truth_preservation"] == supplied
    assert wire_value["authority_role"] == "projection_only"
    assert_public_export_official_use_limits(wire_value)


def test_public_export_rejects_objects_with_string_coercion_at_text_boundary() -> None:
    class OpaqueText(str):
        def __str__(self) -> str:
            return "password=raw-export-text-marker"

    with pytest.raises(PublicExportRedactionError) as run_id_error:
        public_export_module.build_public_export_bundle(
            run_id=OpaqueText("run-opaque"),
            artifacts={},
        )
    assert run_id_error.value.code == "public_export_text_input_invalid"

    with pytest.raises(PublicExportRedactionError) as title_error:
        public_export_module.build_public_export_bundle(
            run_id="run-opaque-title",
            title=OpaqueText("title-opaque"),
            artifacts={},
        )
    assert title_error.value.code == "public_export_text_input_invalid"


def test_public_export_without_projection_does_not_create_a_verdict() -> None:
    bundle = build_public_export_bundle(
        run_id="run-public-export-without-pdc",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
    )

    assert bundle["semantic_audit"]["projection_contract_verification"] is None


def test_final_stage_redaction_normalization_is_scoped_to_owned_record_paths() -> None:
    private_ref = sha("f")
    redactions: list[dict[str, str]] = []
    candidate = {
        "s10_forecast_projection": {
            "private_basis": private_ref,
            "benign_placeholder": "[REDACTED]",
        },
        "authority_surface_decisions": [
            {
                "private_basis": private_ref,
                "benign_placeholder": "[REDACTED]",
            }
        ],
    }

    sanitized = public_export_module._redact_tenant_private_refs(
        candidate,
        path="semantic_audit",
        redactions=redactions,
    )
    tenant_private_paths = frozenset(
        row["path"] for row in redactions if row["reason"] == "tenant_private_ref"
    )
    assert "semantic_audit.s10_forecast_projection.private_basis" in tenant_private_paths
    assert "semantic_audit.authority_surface_decisions[0].private_basis" in tenant_private_paths

    final = public_export_module._remove_final_audit_redactions(
        sanitized,
        path=("semantic_audit",),
        tenant_private_paths=tenant_private_paths,
        scanner_redaction_paths=frozenset(),
    )

    assert isinstance(final, Mapping)
    stage_record = final["s10_forecast_projection"]
    outside_record = final["authority_surface_decisions"][0]
    assert isinstance(stage_record, Mapping)
    assert isinstance(outside_record, Mapping)
    assert stage_record["private_basis"] is None
    assert outside_record["private_basis"]["redacted"] is True
    assert stage_record["benign_placeholder"] == "[REDACTED]"
    assert outside_record["benign_placeholder"] == "[REDACTED]"


def test_public_export_reverifies_stage_contract_after_reference_redaction() -> None:
    from fastapi.encoders import jsonable_encoder

    from polisyos.runtime.quality.projection_semantics import (
        verify_s10_forecast_projection_consumer_contract,
    )

    private_ref = sha("f")
    bundle = build_public_export_bundle(
        run_id="run-public-s10-private-required-ref",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=_s10_public_projection_payload(
            design_graph_ref=private_ref,
        ),
    )

    wire = jsonable_encoder(bundle)
    semantic_audit = wire["semantic_audit"]
    stage_projection = semantic_audit["s10_forecast_projection"]
    final_verification = verify_s10_forecast_projection_consumer_contract(
        projections={"public": stage_projection},
    )
    aggregate_verification = semantic_audit["projection_contract_verification"]

    assert private_ref not in json.dumps(wire, sort_keys=True)
    assert stage_projection["design_graph_ref"] is None
    assert final_verification["status"] == "fail"
    assert (
        semantic_audit["s10_forecast_projection_contract_verification"]["status"]
        == final_verification["status"]
    )
    assert (
        aggregate_verification["s10_forecast_projection"]["status"] == final_verification["status"]
    )
    assert aggregate_verification["status"] == "fail"


def test_public_export_reverifies_all_emitted_stage_contracts_after_redaction() -> None:
    from fastapi.encoders import jsonable_encoder

    from polisyos.runtime.quality.projection_semantics import (
        verify_s9_projection_faithfulness_for_pdc_consumer_contract,
        verify_s10_forecast_projection_consumer_contract,
        verify_s11_predictive_projection_consumer_contract,
        verify_s12_resource_projection_consumer_contract,
        verify_s13_post_deploy_accountability_projection_consumer_contract,
        verify_s14_universality_projection_consumer_contract,
    )

    private_s10_ref = sha("a")
    private_g3_proof_ref = sha("b")
    projection_payload = _s10_public_projection_payload(design_graph_ref=private_s10_ref)
    g3_projection = _g3_public_projection_payload()["layer3_g3_public_export_projection"]
    assert isinstance(g3_projection, dict)
    g3_projection["proof_carrying_analytics_refs"] = [private_g3_proof_ref]
    stage_payloads = (
        _s11_public_projection_payload(),
        _s12_public_projection_payload(),
        _s13_public_projection_payload(),
        _s14_public_projection_payload(),
        {"layer3_g3_public_export_projection": g3_projection},
    )
    may_not_be_used_for = set(projection_payload["may_not_be_used_for"])
    authority_boundary = dict(projection_payload["authority_boundary"])
    boundary_may_not = set(authority_boundary["may_not_use_for"])
    for stage_payload in stage_payloads:
        for key, value in stage_payload.items():
            if key not in {"authority_boundary", "may_not_be_used_for", "rule_version_ref"}:
                projection_payload[key] = value
            if key == "may_not_be_used_for" and isinstance(value, list):
                may_not_be_used_for.update(value)
            if key == "authority_boundary" and isinstance(value, dict):
                boundary_may_not.update(value.get("may_not_use_for", []))
    authority_boundary["may_not_use_for"] = sorted(boundary_may_not)
    projection_payload["authority_boundary"] = authority_boundary
    projection_payload["may_not_be_used_for"] = sorted(may_not_be_used_for)
    projection_payload["s9_projection_faithfulness"] = _s9_public_faithfulness_payload()

    bundle = build_public_export_bundle(
        run_id="run-public-export-all-stage-redaction",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=projection_payload,
    )
    wire = jsonable_encoder(bundle)
    audit = wire["semantic_audit"]
    aggregate = audit["projection_contract_verification"]

    final_projection = wire["projection_semantics"]
    source_state = final_projection["source_state"]
    s9_payload = {
        **final_projection,
        "projection_policy": source_state["s9_projection_policy"],
        "source_revision_ref": source_state["s9_source_revision_ref"],
        "s9_projection_faithfulness": audit["projection_extensions"]["s9_projection_faithfulness"],
    }
    s9_verification = verify_s9_projection_faithfulness_for_pdc_consumer_contract(
        projections={"public": s9_payload},
        expected_closeout_truth=final_projection["closeout_truth"],
        expected_contested_record_ids=[
            row["contested_record_id"] for row in final_projection["contested_records"]
        ],
    )
    emitted_verifications = {
        "s10_forecast_projection": verify_s10_forecast_projection_consumer_contract(
            projections={"public": audit["s10_forecast_projection"]}
        ),
        "s11_predictive_projection": verify_s11_predictive_projection_consumer_contract(
            projections={"public": audit["s11_predictive_projection"]}
        ),
        "s12_resource_projection": verify_s12_resource_projection_consumer_contract(
            projections={"public": audit["s12_resource_projection"]}
        ),
        "s13_post_deploy_accountability_projection": (
            verify_s13_post_deploy_accountability_projection_consumer_contract(
                projections={"public": audit["s13_post_deploy_accountability_projection"]}
            )
        ),
        "s14_universality_projection": verify_s14_universality_projection_consumer_contract(
            projections={"public": audit["s14_universality_projection"]}
        ),
    }

    assert private_s10_ref not in json.dumps(wire, sort_keys=True)
    assert private_g3_proof_ref not in json.dumps(wire, sort_keys=True)
    assert audit["s10_forecast_projection"]["design_graph_ref"] is None
    assert audit["layer3_g3_analytics_search_projection"]["proof_carrying_analytics_refs"] == []
    for key, verification in emitted_verifications.items():
        assert audit[f"{key}_contract_verification"]["status"] == verification["status"]
        assert aggregate[key]["status"] == verification["status"]
    assert aggregate["s9_projection_faithfulness"]["status"] == s9_verification["status"]
    g3_verification = audit["layer3_g3_analytics_search_projection_contract_verification"]
    assert g3_verification["status"] == "fail"
    assert aggregate["layer3_g3_analytics_search_projection"]["status"] == g3_verification["status"]
    assert aggregate["s10_forecast_projection"]["status"] == "fail"
    assert aggregate["layer3_g3_analytics_search_projection"]["status"] == "fail"
    assert aggregate["status"] == "fail"
    assert (
        audit["projection_extensions"]["s9_projection_faithfulness"]["faithfulness_status"]
        == "pass"
    )


def test_public_export_composes_stage_audits_behind_typed_pdc_projection() -> None:
    from fastapi.encoders import jsonable_encoder

    from polisyos.core.contracts.policy_design_case_projection import (
        PolicyDesignCaseProjection,
    )
    from polisyos.runtime.quality.projection_semantics import (
        verify_policy_design_case_projection_consumer_contract,
    )

    projection_payload = _s10_public_projection_payload()
    stage_payloads = (
        _s11_public_projection_payload(),
        _s12_public_projection_payload(),
        _s13_public_projection_payload(),
        _s14_public_projection_payload(),
        _g3_public_projection_payload(),
    )
    may_not_be_used_for = set(projection_payload["may_not_be_used_for"])
    authority_boundary = dict(projection_payload["authority_boundary"])
    boundary_may_not = set(authority_boundary["may_not_use_for"])
    for stage_payload in stage_payloads:
        for key, value in stage_payload.items():
            if key not in {"authority_boundary", "may_not_be_used_for", "rule_version_ref"}:
                projection_payload[key] = value
            if key == "may_not_be_used_for" and isinstance(value, list):
                may_not_be_used_for.update(value)
            if key == "authority_boundary" and isinstance(value, dict):
                boundary_may_not.update(value.get("may_not_use_for", []))
    authority_boundary["may_not_use_for"] = sorted(boundary_may_not)
    projection_payload["authority_boundary"] = authority_boundary
    projection_payload["may_not_be_used_for"] = sorted(may_not_be_used_for)
    projection_payload["s9_projection_faithfulness"] = _s9_public_faithfulness_payload()

    bundle = build_public_export_bundle(
        run_id="run-public-export-composed-stage-audits",
        artifacts={"public_summary": {"claim_refs": ["rec_1"]}},
        authority_envelopes=[],
        policy_design_case=policy_design_case(),
        projection_payload=projection_payload,
    )
    wire = jsonable_encoder(bundle)
    projection = wire["projection_semantics"]
    semantic_audit = wire["semantic_audit"]
    typed = PolicyDesignCaseProjection.model_validate(projection)
    verification = verify_policy_design_case_projection_consumer_contract(
        projections={"public": projection},
        expected_closeout_truth=projection["closeout_truth"],
        expected_contested_record_ids=[
            row["contested_record_id"] for row in projection["contested_records"]
        ],
    )

    assert typed.redacted is True
    assert projection["contract_verification_status"] == verification["status"] == "pass"
    assert semantic_audit["projection_contract_verification"]["status"] == "pass"
    assert semantic_audit["s10_forecast_projection"]["forecast_tier"] == "observable_calibrated"
    assert (
        semantic_audit["s11_predictive_projection"]["effective_predictive_posture"]
        == "limited_by_weakest_boundary"
    )
    assert (
        semantic_audit["s12_resource_projection"]["explore_exploit_posture"] == "balanced_governed"
    )
    assert (
        semantic_audit["s13_post_deploy_accountability_projection"]["envelope_revision_direction"]
        == "shrink"
    )
    assert (
        semantic_audit["s14_universality_projection"]["universality_claim_disposition"]
        == "universal_claim_limited"
    )
    assert (
        semantic_audit["layer3_g3_analytics_search_projection"]["resolved_certificate_count"] == 1
    )
    assert (
        semantic_audit["projection_extensions"]["s9_projection_faithfulness"]["faithfulness_status"]
        == "pass"
    )
    assert "limitations" in semantic_audit["projection_extensions"]

    for forbidden_extra in (
        "forecast_tier",
        "effective_predictive_posture",
        "explore_exploit_posture",
        "public_accountability_note",
        "universality_claim_disposition",
        "layer3_g3_public_export_projection_status",
        "s9_projection_faithfulness",
    ):
        assert forbidden_extra not in projection


def test_public_projection_redacts_private_source_refs_and_reports_typed_status() -> None:
    from fastapi.encoders import jsonable_encoder

    from polisyos.core.contracts.policy_design_case_projection import (
        PolicyDesignCaseProjection,
    )
    from polisyos.runtime.quality.projection_semantics import (
        verify_policy_design_case_projection_consumer_contract,
    )

    private_ref = sha("a")
    bundle = build_public_export_bundle(
        run_id="run-private-source-ref-projection",
        artifacts={"decision": {"status": "limited"}},
        policy_design_case=policy_design_case(),
        projection_payload={"audit_refs": [private_ref, "audit://public"]},
    )

    wire_value = jsonable_encoder(bundle)
    projection = wire_value["projection_semantics"]
    typed = PolicyDesignCaseProjection.model_validate(projection)
    verification = verify_policy_design_case_projection_consumer_contract(
        projections={"public": projection},
        expected_closeout_truth=projection["closeout_truth"],
        expected_contested_record_ids=[
            row["contested_record_id"] for row in projection["contested_records"]
        ],
    )

    assert private_ref not in json.dumps(wire_value, sort_keys=True)
    assert wire_value["artifacts"]["decision"] == {"status": "limited"}
    assert projection["authority_role"] == "projection_only"
    assert typed.redacted is True
    assert projection["audit_refs"] == [
        "audit://public",
        "event://policy_design_case/profile/run-24",
    ]
    assert projection["contract_verification_status"] == verification["status"] == "pass"
    assert (
        wire_value["semantic_audit"]["projection_contract_verification"]["status"]
        == verification["status"]
    )
    assert any(
        redaction["reason"] == "tenant_private_ref"
        and redaction["path"].startswith("projection_semantics.")
        for redaction in wire_value["redaction_summary"]["upserted_redactions"]
    )


def test_graph_projection_redaction_recomputes_contract_and_fails_closed() -> None:
    from fastapi.encoders import jsonable_encoder

    from polisyos.core.contracts.policy_design_case_projection import (
        PolicyDesignCaseProjection,
    )
    from polisyos.pdc import compile_runtime_policy_design_case
    from polisyos.runtime.quality.projection_semantics import (
        verify_policy_design_case_projection_consumer_contract,
    )

    graph = compile_runtime_policy_design_case(
        run_id="run-public-export-graph-redaction",
        tenant_id="private-tenant",
        policy_design_case=policy_design_case(),
        claims=[
            {
                "claim_id": "claim-public-export-graph",
                "claim_type": "factual",
                "claim_use": "decision_support",
                "text": "Graph source remains limited after reference redaction.",
                "support_status": "supported",
                "publishability": "review_required",
                "readiness_level": "recommendation_ready",
                "obligation_refs": ["obligation:public-export-graph"],
            }
        ],
        claim_registry={
            "claims": [
                {
                    "claim_id": "claim-public-export-graph",
                    "data_refs": ["data:public-export-graph"],
                }
            ]
        },
        closeout_verdict={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "issues": [
                {
                    "code": "graph_source_blocker",
                    "severity": "fail",
                    "message": "The graph projection remains limited.",
                }
            ],
        },
    )
    private_graph_ref = graph.graph_ref
    bundle = build_public_export_bundle(
        run_id="run-public-export-graph-redaction",
        artifacts={
            "decision": {"status": "limited"},
            "sibling": {"public_fact": "preserved"},
        },
        runtime_pdc_graph=graph.model_dump(mode="json"),
    )

    wire_value = jsonable_encoder(bundle)
    projection = wire_value["projection_semantics"]
    typed = PolicyDesignCaseProjection.model_validate(projection)
    verification = verify_policy_design_case_projection_consumer_contract(
        projections={"public": projection},
        expected_closeout_truth=projection["closeout_truth"],
        expected_contested_record_ids=[
            row["contested_record_id"] for row in projection["contested_records"]
        ],
        runtime_pdc_graph=graph.model_dump(mode="json"),
    )

    assert private_graph_ref not in json.dumps(wire_value, sort_keys=True)
    assert projection["source_ref"] is None
    assert projection["source_ref_fingerprint"] is None
    assert typed.redacted is True
    assert verification["status"] == "fail"
    assert projection["contract_verification_status"] == "fail"
    assert wire_value["semantic_audit"]["projection_contract_verification"]["status"] == "fail"
    assert wire_value["artifacts"]["decision"] == {"status": "limited"}
    assert wire_value["artifacts"]["sibling"] == {"public_fact": "preserved"}


def test_public_export_accepts_declared_top_level_authority_model() -> None:
    from fastapi.encoders import jsonable_encoder

    from polisyos.runtime.quality.authority import EvidenceAuthorityEnvelope

    private_ref = sha("d")
    source = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=private_ref,
    )
    envelope = EvidenceAuthorityEnvelope.model_validate(source)

    bundle = build_public_export_bundle(
        run_id="run-typed-authority-envelope",
        artifacts={"decision": {"status": "limited"}},
        authority_envelopes=(envelope,),
    )
    wire_value = jsonable_encoder(bundle)
    projections = wire_value["semantic_audit"]["authority_projections"]

    assert len(projections) == 1
    assert projections[0]["authority_role"] == "projection_only"
    assert private_ref not in repr(wire_value)
