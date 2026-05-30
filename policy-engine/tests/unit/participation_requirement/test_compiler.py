from __future__ import annotations

# ruff: noqa: S101
import json
from typing import TYPE_CHECKING

from polisyos.participation_requirement import (
    ParticipationProvenanceCompiler,
    ParticipationProvenanceRecord,
    ParticipationSourceKind,
    compile_participation_requirements,
    evaluate_participation_requirement,
    participation_requirement_bundle_audit_surface,
    write_participation_requirement_bundle,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_compiler_emits_production_prevalence_spec_from_preference_claim() -> None:
    bundle = compile_participation_requirements(
        {
            "run_id": "run-w7e",
            "claims": [
                {
                    "claim_id": "claim-preference",
                    "claim_family": "preference",
                    "claim_use": "decision_support",
                    "text": "Affected MSMEs prefer the guarantee design.",
                    "authority_level": "production",
                    "population_scope": "affected_population",
                    "obligation_refs": ["obl-participation"],
                    "facet_refs": ["facet-msme"],
                }
            ],
        }
    )

    assert bundle.schema_version == "policyos.participation_requirement.bundle.v1"
    assert bundle.metadata["capability_reality_label"] == "implemented"
    assert len(bundle.requirements) == 1

    requirement = bundle.requirements[0]
    assert requirement.claim_id == "claim-preference"
    assert requirement.claim_use_requested == "prevalence"
    assert requirement.required_modes == ("survey",)
    assert requirement.minimum_provenance_class == "A_representative_population"
    assert requirement.required_sampling_frame == "scope_matched_sampling_frame"
    assert requirement.representativeness_config.methodology_owner == "team-methodology"
    assert requirement.representativeness_config.governance_owner == "team-governance"
    assert "show_participation_gaps" in requirement.public_projection_obligations
    assert "raw_transcripts_must_be_redacted" in requirement.privacy_constraints
    assert "participation_evidence_authority" in requirement.authority_boundary.may_not_use_for


def test_thin_consultation_downgrades_prevalence_without_blocking_case() -> None:
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
    consultation = ParticipationProvenanceRecord(
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
        limitations=("self-selected consultation; no scope-matched frame",),
        evidence_ref="sha256:" + "1" * 64,
    )

    evaluation = evaluate_participation_requirement(requirement, [consultation])

    assert evaluation.status == "downgraded"
    assert evaluation.claim_use_requested == "prevalence"
    assert evaluation.claim_use_allowed == "qualitative"
    assert evaluation.case_closeout_effect == "limited_closeout"
    assert evaluation.blocker_code is None
    assert evaluation.downgrade_reason == "nonrepresentative_for_claim_scope"
    assert evaluation.public_projection_rows[0].public_projection_effect == "show_limitation"
    assert evaluation.deficit_records[0].disposition == "publish_with_limitation"


def test_llm_speculation_cannot_satisfy_legitimacy_requirement() -> None:
    requirement = ParticipationProvenanceCompiler().compile(
        {
            "run_id": "run-w7e",
            "claims": [
                {
                    "claim_id": "claim-legitimacy",
                    "claim_family": "legitimacy",
                    "claim_use": "participation_legitimacy",
                    "authority_level": "governed",
                    "population_scope": "affected_population",
                    "text": "The process is legitimate for affected groups.",
                }
            ],
        }
    ).requirements[0]
    llm_summary = ParticipationProvenanceRecord(
        participation_ref="hypothesis-candidate:participation-summary",
        claim_refs=("claim-legitimacy",),
        source_kind=ParticipationSourceKind.LLM_SPECULATION,
        provenance_class="D_unverifiable_or_speculative",
        representativeness_class="unknown",
        affected_group_map={},
        consent_redaction_state="not_applicable_context_only",
        dissent_state="not_recorded",
        sponsor_disclosure=None,
        limitations=("LLM-generated summary without real participation provenance.",),
    )

    evaluation = evaluate_participation_requirement(requirement, [llm_summary])

    assert evaluation.status == "blocked"
    assert evaluation.claim_use_allowed == "context-only"
    assert evaluation.blocker_code == "llm_speculation_not_participation"
    assert evaluation.case_closeout_effect == "affected_claim_blocked"
    assert "participation_authority" in evaluation.authority_boundary.may_not_use_for


def test_participation_requirement_bundle_is_persisted_for_projection_replay(
    tmp_path: Path,
) -> None:
    bundle = compile_participation_requirements(
        {
            "run_id": "run-w7e",
            "claims": [
                {
                    "claim_id": "claim-preference",
                    "claim_family": "preference",
                    "claim_use": "decision_support",
                    "text": "Affected MSMEs prefer the guarantee design.",
                    "authority_level": "production",
                    "population_scope": "affected_population",
                }
            ],
        }
    )

    path = write_participation_requirement_bundle(bundle, tmp_path)
    persisted = json.loads(path.read_text(encoding="utf-8"))
    surface = participation_requirement_bundle_audit_surface(bundle)

    assert path.name == "run-w7e-participation-requirements.json"
    assert persisted["schema_version"] == "policyos.participation_requirement.bundle.v1"
    assert persisted["runtime_event_ref"] == "event://participation-requirement/run-w7e"
    assert surface["surface"] == "participation_requirement.audit_surface"
    assert surface["summary"]["requirement_count"] == 1
    assert surface["authority_boundary"]["authoritative_for"] == [
        "participation_provenance_requirements",
        "participation_projection_preconditions",
        "participation_claim_use_downgrades",
    ]


def test_participation_consumes_capability_graph_consent_envelope_and_source_limits() -> None:
    requirement = ParticipationProvenanceCompiler().compile(
        {
            "run_id": "run-w7e-phase5",
            "claims": [
                {
                    "claim_id": "claim-legitimacy",
                    "claim_family": "legitimacy",
                    "claim_use": "participation_legitimacy",
                    "authority_level": "governed",
                    "population_scope": "affected_population",
                    "text": "The wartime MSME credit process is legitimate for affected groups.",
                }
            ],
        }
    ).requirements[0]

    evaluation = evaluate_participation_requirement(
        requirement,
        records=[],
        capability_bindings=[
            {
                "requirement_id": requirement.requirement_id,
                "status": "selected_proxy_with_limitation",
                "selected_capability_ref": "capability:participation_legitimacy_signal",
                "construct_ref": "construct:civic_legitimacy_signal",
                "capability_index_ref": "capability-index:phase5",
                "construct_registry_ref": "construct-registry:v1",
                "authority_composition_rule_ref": "capability-authority-v1.0",
                "modality": ["participation_provenance", "civic_legitimacy_signal"],
                "evidence_mode": "participation_attestation",
                "metadata": {
                    "source_kind": "consultation",
                    "provenance_class": "B_structured_deliberative_or_process",
                    "representativeness_class": "structured_subgroup_or_role",
                    "affected_group_map": {"groups": ["registered_msmes"]},
                    "consent_envelope": {
                        "consent_redaction_state": "process_safe_public_summary",
                        "source_limitations": ["self_selected_process"],
                    },
                    "sponsor_disclosure": "agency_sponsor_disclosed",
                    "dissent_state": "recorded",
                    "evidence_ref": "participation-evidence:consultation-2022",
                },
            }
        ],
    )

    row = evaluation.public_projection_rows[0]

    assert evaluation.status == "satisfied"
    assert evaluation.capability_ref == "capability:participation_legitimacy_signal"
    assert evaluation.construct_ref == "construct:civic_legitimacy_signal"
    assert evaluation.capability_index_ref == "capability-index:phase5"
    assert evaluation.construct_registry_ref == "construct-registry:v1"
    assert evaluation.authority_composition_rule_ref == "capability-authority-v1.0"
    assert evaluation.consent_envelope["consent_redaction_state"] == (
        "process_safe_public_summary"
    )
    assert "self_selected_process" in evaluation.source_limitations
    assert row.evidence_ref == "participation-evidence:consultation-2022"


def test_participation_consumes_all_phase5_provenance_capability_classes() -> None:
    requirement = ParticipationProvenanceCompiler().compile(
        {
            "run_id": "run-w7e-phase5-all-classes",
            "claims": [
                {
                    "claim_id": "claim-legitimacy",
                    "claim_family": "legitimacy",
                    "claim_use": "participation_legitimacy",
                    "authority_level": "governed",
                    "population_scope": "affected_population",
                    "text": "The process has affected-person legitimacy.",
                }
            ],
        }
    ).requirements[0]
    capability_classes = {
        "participation_provenance": "capability:affected_person_process_record",
        "civic_legitimacy_signal": "capability:civic_legitimacy_signal",
        "value_choice_provenance": "capability:value_choice_record",
    }

    for construct, capability_ref in capability_classes.items():
        evaluation = evaluate_participation_requirement(
            requirement,
            records=[],
            capability_bindings=[
                {
                    "requirement_id": requirement.requirement_id,
                    "status": "selected_proxy_with_limitation",
                    "selected_capability_ref": capability_ref,
                    "construct_ref": f"construct:{construct}",
                    "capability_index_ref": "capability-index:phase5",
                    "construct_registry_ref": "construct-registry:v1",
                    "authority_composition_rule_ref": "capability-authority-v1.0",
                    "modality": [construct],
                    "evidence_mode": "participation_attestation",
                    "metadata": {
                        "source_kind": "consultation",
                        "provenance_class": "B_structured_deliberative_or_process",
                        "representativeness_class": "structured_subgroup_or_role",
                        "affected_group_map": {"groups": ["registered_msmes"]},
                        "consent_envelope": {
                            "consent_redaction_state": "process_safe_public_summary",
                            "source_limitations": [f"{construct}_source_limit"],
                        },
                        "sponsor_disclosure": "agency_sponsor_disclosed",
                        "dissent_state": "recorded",
                        "evidence_ref": f"participation-evidence:{construct}",
                    },
                }
            ],
        )

        assert evaluation.status == "satisfied"
        assert evaluation.capability_ref == capability_ref
        assert evaluation.construct_ref == f"construct:{construct}"
        assert evaluation.consent_envelope["consent_redaction_state"] == (
            "process_safe_public_summary"
        )
        assert f"{construct}_source_limit" in evaluation.source_limitations


def test_absent_participation_capability_emits_typed_limitation_not_silent_pass() -> None:
    requirement = ParticipationProvenanceCompiler().compile(
        {
            "run_id": "run-w7e-phase5-missing",
            "claims": [
                {
                    "claim_id": "claim-legitimacy",
                    "claim_family": "legitimacy",
                    "claim_use": "participation_legitimacy",
                    "authority_level": "governed",
                    "population_scope": "affected_population",
                    "text": "The process is legitimate.",
                }
            ],
        }
    ).requirements[0]

    evaluation = evaluate_participation_requirement(requirement, records=[])

    assert evaluation.status == "missing"
    assert evaluation.blocker_code == "participation_provenance_missing"
    assert evaluation.metadata["typed_limitation"] == "participation_evidence_absent"
