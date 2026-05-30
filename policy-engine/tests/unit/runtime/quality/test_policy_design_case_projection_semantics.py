from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime

import pytest

from polisyos.core.contracts.policy_design_case_projection import (
    PolicyDesignCaseAudience,
    PolicyDesignCaseProjection,
)
from polisyos.participation_requirement import (
    ParticipationProvenanceCompiler,
    ParticipationProvenanceRecord,
    ParticipationSourceKind,
    evaluate_participation_requirement,
)
from polisyos.pdc import compile_runtime_policy_design_case
from polisyos.runtime.quality.projection_semantics import (
    PolicyDesignCaseProjectionError,
    assert_policy_design_projection_not_authority,
    build_policy_design_case_projection_contract_fixture,
    build_policy_design_case_projection_from_runtime_graph,
    build_policy_design_case_projection_semantics,
    verify_policy_design_case_projection_consumer_contract,
)
from tests._helpers.policy_design_case_projection import policy_design_case, sha


def test_projection_semantics_labels_publishable_without_minting_authority() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="final_artifact",
        source_payload={
            "artifact_kind": "publishable_decision_artifact",
            "publishability": "publishable",
            "decision_context": {"public_export_status": "publishable"},
            "authority_role": "final_decision_artifact",
        },
        source_ref=sha("9"),
        generated_at=datetime(2026, 5, 18, 9, 0, tzinfo=UTC),
    )

    assert projection["primary_state"] == "publishable"
    assert projection["authority_role"] == "projection_only"
    assert projection["projection_policy"] == "reads_policy_design_case_only"
    assert projection["source_authority_refs"]["policy_design_case_ref"] == sha("a")
    assert "publishable" in projection["states"]
    assert "projection_only" in projection["states"]
    assert {label["state"]: label["authority_role"] for label in projection["labels"]}[
        "publishable"
    ] == "projection_only"
    assert "scorecard_authority" in projection["may_not_be_used_for"]

    assert_policy_design_projection_not_authority(projection)


def test_projection_backend_consumes_runtime_pdc_graph_as_source_of_truth() -> None:
    graph = compile_runtime_policy_design_case(
        run_id="run-24",
        job_id="job-24",
        tenant_id="tenant-sensitive",
        policy_design_case=policy_design_case(),
        claims=[
            {
                "claim_id": "claim-graph-source",
                "claim_type": "factual",
                "claim_use": "decision_support",
                "text": "Graph-backed policy claim.",
                "support_status": "supported",
                "publishability": "review_required",
                "readiness_level": "recommendation_ready",
                "obligation_refs": ["obligation:graph-source"],
            }
        ],
        claim_registry={
            "runtime_claim_registry_ref": sha("1"),
            "claims": [
                {
                    "claim_id": "claim-graph-source",
                    "data_refs": ["data:graph-source"],
                    "selected_norm_refs": ["norm:graph-source"],
                    "method_output_refs": ["method:graph-source"],
                }
            ],
        },
        closeout_verdict={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "issues": [
                {
                    "code": "graph_source_blocker",
                    "severity": "fail",
                    "message": "The graph source carries the blocker.",
                    "module_id": "claim_registry",
                }
            ],
        },
        generated_at=datetime(2026, 5, 24, 12, 0, tzinfo=UTC),
    )

    projection = build_policy_design_case_projection_from_runtime_graph(
        runtime_pdc_graph=graph,
        surface="machine_projection",
        audience=PolicyDesignCaseAudience.MACHINE,
        generated_at=datetime(2026, 5, 24, 12, 1, tzinfo=UTC),
    )

    assert projection["source_ref"] == graph.graph_ref
    assert projection["projection_policy"] == "reads_runtime_policy_design_case_graph"
    assert projection["source_state"]["runtime_pdc_graph_ref"] == graph.graph_ref
    assert set(projection["source_state"]["runtime_pdc_graph_consumed_fields"]) <= set(
        type(graph).model_fields
    )
    assert projection["closeout_truth"]["blocker_codes"] == ["graph_source_blocker"]
    assert projection["authority_role"] == "projection_only"
    assert projection["authoritative_for"] == []

    verification = verify_policy_design_case_projection_consumer_contract(
        projections={"machine": projection},
        expected_closeout_truth=projection["closeout_truth"],
        runtime_pdc_graph=graph,
    )

    assert verification["status"] == "pass"
    assert verification["consumer_contracts"][0]["verified_fields"][-2:] == [
        "runtime_pdc_graph_ref",
        "runtime_pdc_graph_consumed_fields",
    ]


def test_projection_semantics_labels_public_exports_as_redacted_projection() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="public_export",
        source_payload={
            "public_export_classification": "public_redacted_projection",
            "evidence_class": "redacted_derived",
            "decision_context": {"public_export_status": "publishable"},
        },
        source_ref=sha("8"),
    )

    assert projection["primary_state"] == "redacted"
    assert projection["authority_role"] == "projection_only"
    assert projection["redacted"] is True
    assert {"redacted", "publishable", "projection_only"} <= set(projection["states"])
    assert "tenant-sensitive" not in str(projection)


def test_projection_semantics_rejects_projection_that_mints_claim_authority() -> None:
    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="dashboard",
        source_payload={"decision_context": {"public_export_status": "publishable"}},
    )
    projection["authority_role"] = "producer_authority"

    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="policy_design_projection_mints_authority",
    ):
        assert_policy_design_projection_not_authority(projection)


def test_projection_semantics_rejects_authority_bearing_projection_source() -> None:
    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="policy_design_projection_source_mints_authority",
    ):
        build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case(),
            surface="api_projection",
            source_payload={
                "authority_role": "producer_authority",
                "decision_context": {"public_export_status": "publishable"},
            },
        )


def test_projection_semantics_rejects_capability_binding_projection_laundering() -> None:
    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="capability_binding_projection_laundering",
    ):
        build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case(),
            surface="dashboard",
            source_payload={
                "authority_role": "projection_only",
                "capability_binding_results": [
                    {
                        "schema_version": "policyos.capability_binding_result.v1",
                        "binding_id": "binding:projection-laundered",
                        "status": "selected_exact",
                        "authority_role": "projection_only",
                        "authoritative_for": ["claim_evidence"],
                        "satisfies_claim_evidence": True,
                    }
                ],
            },
        )


def test_projection_semantics_blocks_unverified_candidate_projection_laundering() -> None:
    with pytest.raises(
        PolicyDesignCaseProjectionError,
        match="candidate_firewall_candidate_unverified",
    ):
        build_policy_design_case_projection_semantics(
            policy_design_case=policy_design_case(),
            surface="dashboard",
            source_payload={
                "authority_role": "projection_only",
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
                                "may_not_use_for": [
                                    "projection_authority",
                                    "claim_authority",
                                ],
                            },
                            "admission_state": "candidate_unverified",
                        }
                    ],
                },
            },
        )


def test_typed_projection_preserves_closeout_truth_across_audiences() -> None:
    closeout = {
        "schema_version": "policyos.runtime.can_i_closeout.reader_skeleton.v1",
        "status": "blocked",
        "verdict": "cannot_closeout",
        "can_closeout": False,
        "issues": [
            {
                "code": "claim_registry_missing_legal_anchor",
                "severity": "fail",
                "message": "Claim has global Lex refs but no per-claim legal anchor.",
                "module_id": "claim_registry",
                "owner": "team-scientist-evidence",
                "evidence_ref": sha("1"),
                "next_action": "Bind the Lex authority ref to claim rec_1.",
            }
        ],
    }
    source_payload = {
        "artifact_kind": "publishable_decision_artifact",
        "publishability": "publishable",
        "decision_context": {"public_export_status": "publishable"},
        "authority_role": "final_decision_artifact",
        "deficit_register": [
            {
                "deficit_id": "deficit-participation-frame",
                "deficit_family": "participation",
                "deficit_code": "summary_without_underlying_method",
                "claim_ids": ["rec_1"],
                "authority_level": "production",
                "audience_scope": "public",
                "disposition": "publish_with_limitation",
                "owner": "team-participation",
                "ttl_expires_at": "2026-06-01T00:00:00Z",
                "runtime_event_ref": "event://deficits/participation-frame",
                "evidence_ref": sha("2"),
                "public_limitation_note": (
                    "Participation prevalence is limited to sampled respondents."
                ),
            }
        ],
        "contested_records": [
            {
                "contested_record_id": "contest-rec-1",
                "case_ref": sha("3"),
                "claim_refs": ["rec_1"],
                "audience_visibility": ["public", "reviewer", "expert", "machine"],
                "contestability_status": "contested",
                "grounds": ["counterevidence"],
                "standing_or_actor_ref": "actor://msme-association",
                "counterevidence_refs": [sha("4")],
                "source_truth_conflict_refs": [sha("5")],
                "authority_profile": "production",
                "publication_effect": "review_before_publication",
                "reopening_trigger_refs": ["event://reopen/rec-1"],
                "lifecycle_event_refs": ["event://lifecycle/rec-1"],
                "recourse_outcome_refs": [],
                "ingestion_event_refs": [],
                "public_projection_effect": "show_contested_state",
            }
        ],
        "invariant_summary": {
            "status": "fail",
            "passing_count": 7,
            "failing_count": 1,
            "blocker_codes": ["claim_registry_missing_legal_anchor"],
            "evidence_refs": [sha("6")],
        },
    }

    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict=closeout,
        source_payload=source_payload,
        audiences=(
            PolicyDesignCaseAudience.PUBLIC,
            PolicyDesignCaseAudience.REVIEWER,
            PolicyDesignCaseAudience.EXPERT,
            PolicyDesignCaseAudience.MACHINE,
        ),
        generated_at=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )

    assert fixture["status"] == "pass"
    assert {
        row["audience"] for row in fixture["consumer_contracts"] if row["status"] == "pass"
    } == {"public", "reviewer", "expert", "machine"}
    projections = fixture["projections"]
    public = PolicyDesignCaseProjection.model_validate(projections["public"])
    machine = PolicyDesignCaseProjection.model_validate(projections["machine"])

    assert public.schema_version == "policyos.runtime.policy_design_case.projection.v1"
    assert public.authority_role == "projection_only"
    assert public.authoritative_for == ()
    assert "runtime_closeout_authority" in public.may_not_be_used_for
    assert public.closeout_truth.can_closeout is False
    assert public.closeout_truth.blocker_codes == ("claim_registry_missing_legal_anchor",)
    assert machine.closeout_truth == public.closeout_truth
    assert public.deficit_register[0].deficit_code == "summary_without_underlying_method"
    assert public.contested_records[0].contestability_status == "contested"
    assert public.projection_gaps[0].gap_code == "claim_registry_missing_legal_anchor"
    assert public.invariant_summary.status == "fail"
    assert public.redacted is True
    assert machine.redacted is False


def test_external_surface_fixture_surfaces_omissions_audit_refs_and_contract_status() -> None:
    closeout = {
        "schema_version": "policyos.runtime.can_i_closeout.reader_skeleton.v1",
        "status": "blocked",
        "verdict": "cannot_closeout",
        "can_closeout": False,
        "issues": [
            {
                "code": "blocked_claim_missing_anchor",
                "severity": "fail",
                "message": "Blocked claim is missing a claim-bound legal anchor.",
                "module_id": "claim_registry",
                "owner": "team-scientist-evidence",
                "evidence_ref": sha("1"),
            },
            {
                "code": "omitted_blocked_claim",
                "severity": "omission",
                "message": "Claim rec_1 is omitted from the public summary.",
                "claim_ids": ["rec_1"],
                "module_id": "public_export",
                "owner": "team-policyos-runtime",
                "evidence_ref": sha("2"),
            },
            {
                "code": "limited_participation_frame",
                "severity": "limitation",
                "message": "Participation evidence is sampled and cannot be generalized.",
                "claim_ids": ["rec_2"],
                "module_id": "participation",
                "owner": "team-participation",
                "evidence_ref": sha("3"),
            },
        ],
    }
    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict=closeout,
        source_payload={
            "authority_role": "final_decision_artifact",
            "audit_refs": ["audit://pdc/w5a/surface-truth"],
            "source_ref": sha("4"),
            "redaction_summary": {
                "erased_paths": ["claims.rec_1.private_basis"],
                "redacted_path_count": 1,
            },
        },
        generated_at=datetime(2026, 5, 23, 11, 0, tzinfo=UTC),
    )

    assert fixture["status"] == "pass"
    public = fixture["projections"]["public"]
    machine = fixture["projections"]["machine"]

    assert public["contract_verification_status"] == "pass"
    assert machine["contract_verification_status"] == "pass"
    assert "audit://pdc/w5a/surface-truth" in public["audit_refs"]
    assert public["omission_manifest"][0]["omission_code"] == "omitted_blocked_claim"
    assert public["omission_manifest"][0]["claim_ids"] == ["rec_1"]
    assert {gap["gap_family"] for gap in public["projection_gaps"]} >= {
        "closeout",
        "limitation",
        "omission",
    }
    assert public["closeout_truth"]["limitation_codes"] == ["limited_participation_frame"]
    assert public["closeout_truth"]["omission_codes"] == ["omitted_blocked_claim"]


def test_projection_contract_rejects_public_audience_hiding_blockers_or_contested_state() -> None:
    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "issues": [
                {
                    "code": "blocked_claim",
                    "severity": "fail",
                    "message": "Blocked claim cannot be hidden.",
                }
            ],
        },
        source_payload={
            "authority_role": "final_decision_artifact",
            "contested_records": [
                {
                    "contested_record_id": "contest-hidden",
                    "case_ref": sha("3"),
                    "claim_refs": ["rec_1"],
                    "audience_visibility": ["public"],
                    "contestability_status": "contested",
                    "grounds": ["dissent"],
                    "standing_or_actor_ref": "actor://affected",
                    "counterevidence_refs": [sha("4")],
                    "source_truth_conflict_refs": [],
                    "authority_profile": "production",
                    "publication_effect": "review_before_publication",
                    "reopening_trigger_refs": [],
                    "lifecycle_event_refs": [],
                    "recourse_outcome_refs": [],
                    "ingestion_event_refs": [],
                    "public_projection_effect": "show_contested_state",
                }
            ],
        },
    )
    public_projection = dict(fixture["projections"]["public"])
    public_projection["closeout_truth"] = {
        **dict(public_projection["closeout_truth"]),
        "blocker_codes": [],
        "blockers": [],
    }
    public_projection["contested_records"] = []

    result = verify_policy_design_case_projection_consumer_contract(
        projections={**fixture["projections"], "public": public_projection},
        expected_closeout_truth=fixture["expected_closeout_truth"],
        expected_contested_record_ids=fixture["expected_contested_record_ids"],
    )

    assert result["status"] == "fail"
    assert {issue["code"] for issue in result["issues"]} >= {
        "policy_design_projection_hides_closeout_blockers",
        "policy_design_projection_hides_contested_state",
    }


def test_projection_semantics_surfaces_participation_requirement_downgrades_safely() -> None:
    requirement = ParticipationProvenanceCompiler().compile(
        {
            "run_id": "run-w7e",
            "claims": [
                {
                    "claim_id": "claim-preference",
                    "claim_family": "preference",
                    "authority_level": "production",
                    "population_scope": "affected_population",
                    "text": "Affected population preference claim.",
                }
            ],
        }
    ).requirements[0]
    evaluation = evaluate_participation_requirement(
        requirement,
        [
            ParticipationProvenanceRecord(
                participation_ref="participation:thin-consultation",
                claim_refs=("claim-preference",),
                source_kind=ParticipationSourceKind.CONSULTATION,
                consultation_mode="consult",
                provenance_class="C_attributable_nonrepresentative",
                representativeness_class="nonrepresentative",
                sampling_or_recruitment_frame=None,
                affected_group_map={"groups": ["self_selected_msmes"]},
                consent_redaction_state="public_summary_only",
                dissent_state="recorded",
                sponsor_disclosure="agency_sponsor_disclosed",
                limitations=("raw transcript exists but is not public-safe",),
                evidence_ref=sha("7"),
                raw_material_ref="restricted://participation/raw/transcript-1",
            )
        ],
    )

    projection = build_policy_design_case_projection_semantics(
        policy_design_case=policy_design_case(),
        surface="public_export",
        source_payload={
            "public_export_classification": "public_redacted_projection",
            "evidence_class": "redacted_derived",
            "participation_requirement_evaluations": [
                evaluation.model_dump(mode="json")
            ],
        },
        audience=PolicyDesignCaseAudience.PUBLIC,
        source_ref=sha("8"),
    )

    assert projection["participation_requirements"][0]["claim_use_requested"] == "prevalence"
    assert projection["participation_requirements"][0]["claim_use_allowed"] == "qualitative"
    assert projection["participation_requirements"][0]["raw_materials_redacted"] is True
    assert "restricted://participation/raw/transcript-1" not in str(projection)
    assert "nonrepresentative_for_claim_scope" in {
        gap["gap_code"] for gap in projection["projection_gaps"]
    }
    assert projection["deficit_register"][0]["deficit_family"] == "participation"


def test_projection_contract_rejects_missing_omission_manifest_even_when_shape_passes() -> None:
    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict={
            "status": "blocked",
            "verdict": "cannot_closeout",
            "can_closeout": False,
            "issues": [
                {
                    "code": "omitted_blocked_claim",
                    "severity": "omission",
                    "message": "Claim rec_1 is omitted from the public summary.",
                    "claim_ids": ["rec_1"],
                    "module_id": "public_export",
                }
            ],
        },
        source_payload={"authority_role": "final_decision_artifact"},
    )
    public_projection = dict(fixture["projections"]["public"])
    public_projection["omission_manifest"] = []

    result = verify_policy_design_case_projection_consumer_contract(
        projections={**fixture["projections"], "public": public_projection},
        expected_closeout_truth=fixture["expected_closeout_truth"],
        expected_contested_record_ids=fixture["expected_contested_record_ids"],
    )

    assert result["status"] == "fail"
    assert "policy_design_projection_hides_omission_manifest" in {
        issue["code"] for issue in result["issues"]
    }


def test_projection_contract_rejects_machine_surface_without_reconstructable_refs() -> None:
    fixture = build_policy_design_case_projection_contract_fixture(
        policy_design_case=policy_design_case(),
        closeout_verdict={
            "status": "ready",
            "verdict": "can_closeout",
            "can_closeout": True,
            "issues": [],
        },
        source_payload={
            "authority_role": "final_decision_artifact",
            "source_ref": sha("7"),
            "audit_refs": ["audit://pdc/w5a/machine-contract"],
        },
    )
    machine_projection = {
        **dict(fixture["projections"]["machine"]),
        "source_ref": None,
        "source_ref_fingerprint": None,
        "source_authority_refs": {},
        "audit_refs": [],
    }

    result = verify_policy_design_case_projection_consumer_contract(
        projections={**fixture["projections"], "machine": machine_projection},
        expected_closeout_truth=fixture["expected_closeout_truth"],
        expected_contested_record_ids=fixture["expected_contested_record_ids"],
    )

    assert result["status"] == "fail"
    assert "policy_design_projection_machine_refs_missing" in {
        issue["code"] for issue in result["issues"]
    }


def test_high_stakes_contested_projection_records_unreachable_recourse_as_publication_blocker() -> (
    None
):
    projection = build_policy_design_case_projection_semantics(
        policy_design_case={
            **policy_design_case(),
            "contestability_status": "contested",
            "stakes": "high_stakes",
        },
        surface="public_export",
        source_payload={
            "publishability": "publishable",
            "contestability_status": "contested",
            "stakes": "high_stakes",
            "authority_level": "production",
            "decision_context": {"public_export_status": "publishable"},
            "recourse_pointer": {
                "uri": "https://appeals.example.test/pdc/run-24",
                "verification_status": "verified_reachable",
                "verified_at": "2026-05-18T09:30:00Z",
                "verification_ref": "event://recourse/verified",
                "source_kind": "llm_candidate",
            },
        },
        audience=PolicyDesignCaseAudience.PUBLIC,
        generated_at=datetime(2026, 5, 18, 10, 0, tzinfo=UTC),
    )

    typed = PolicyDesignCaseProjection.model_validate(projection)

    assert typed.primary_state == "blocked"
    assert "blocked" in typed.states
    assert typed.recourse_pointer is None
    assert {gap.gap_code for gap in typed.projection_gaps} >= {
        "public_export_recourse_pointer_unreachable"
    }
    assert {blocker.code for blocker in typed.closeout_truth.blockers} >= {
        "public_export_recourse_pointer_unreachable"
    }
