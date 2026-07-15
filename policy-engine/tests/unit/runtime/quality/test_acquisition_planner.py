from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.data_requirement import (
    DataQualityMinimums,
    DataRequirementScope,
    DataRequirementSpec,
)
from polisyos.legal_requirement import LegalAuthorityRequirementSpec, LegalAuthorityType
from polisyos.method_requirement import (
    MethodIdentificationClass,
    MethodValidityRequirementSpec,
)
from polisyos.participation_requirement import (
    ParticipationAuthorityLevel,
    ParticipationClaimPurpose,
    ParticipationClaimUse,
    ParticipationPopulationScope,
    ParticipationProvenanceClass,
    ParticipationProvenanceRequirementSpec,
    ParticipationRepresentativenessClass,
    ParticipationSourceKind,
)
from polisyos.runtime.quality import acquisition_planner as acquisition_owner
from polisyos.runtime.quality.acquisition_planner import (
    ACQUISITION_FAMILY_DENOMINATOR,
    AcquisitionCaptureProvenance,
    AcquisitionDisposition,
    AcquisitionFamily,
    AcquisitionGap,
    AcquisitionGapType,
    AcquisitionNetworkCallCounter,
    AcquisitionOwnerArtifact,
    AcquisitionPlanner,
    AcquisitionRequirementGap,
    AcquisitionStrategy,
    AcquisitionWorldSnapshot,
    AuthorityLevel,
    MandatoryGateState,
    RealAcquisitionOwnerGateway,
    RecordedAcquisitionOwnerGateway,
    RequiredDataGap,
    RequirementGapFamily,
    acquisition_gaps_from_capability_failure_modes,
    acquisition_planner_scorecard_gates,
    acquisition_report_deficit_records,
    acquisition_request_from_world_acquirable,
    acquisition_strangle_receipt,
    l1_variable_availability_requirement_gap,
    load_acquisition_planner_report,
    persist_acquisition_planner_report,
    plan_evidence_acquisition,
    plan_requirement_gap_acquisition,
    rank_acquisition_candidates_by_family,
    requirement_gaps_from_compiled_specs,
    run_acquisition_closed_loop,
    validate_acquisition_receipt,
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.capability_index import FailureModeNode
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.scorecard import build_quality_scorecard
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from polisyos.scholar_requirement import (
    ScholarDependentCorpusCollapseRule,
    ScholarSupportRequirementSpec,
)
from polisyos.scientist.methods.search.voi_models import (
    VOIDecisionRecord,
    VOIDecisionType,
    VOIRunReport,
    acquisition_voi_metadata,
    stable_voi_decision_id,
)
from tools.quality.validation import check_layer3_gy_acquisition_contract as contract

REPO_ROOT = Path(__file__).resolve().parents[4]


def _acquisition_design_problem() -> DesignProblem:
    """Build real research authority for acquisition grounding rederivation."""

    return DesignProblem.model_validate(
        {
            "design_problem_id": "n7_acquisition_grounding_probe",
            "problem_statement": "Ground acquired evidence against the affected world region.",
            "domain": "acquisition_grounding_probe",
            "nl_provenance": {
                "raw_request": "Acquire and ground the missing evidence.",
                "source_surface": "test_acquisition_planner",
            },
            "authority_profile": {
                "requester_authority": "research_lab",
                "requested_authority_level": "research",
                "mandate": "Test acquisition rederivation without promotion authority.",
            },
            "jurisdiction_time": {
                "region": "probe_region",
                "valid_time": "2026",
                "as_of": "2026-07-15",
                "policy_time": "2026",
                "data_time": "2026",
            },
            "objectives": [
                {
                    "objective_id": "ground_acquired_evidence",
                    "description": "Ground acquired evidence.",
                    "metric_id": "grounded_evidence",
                }
            ],
            "constraints": [
                {
                    "constraint_id": "no_fabricated_authority",
                    "description": "Acquisition cannot fabricate grounding authority.",
                    "admissibility_basis": "request_text",
                    "source_text": "Do not fabricate grounding authority.",
                }
            ],
            "stakeholders": [
                {
                    "stakeholder_id": "evidence_consumers",
                    "name": "Evidence consumers",
                    "role": "consumer",
                }
            ],
            "outcome_of_interest": {
                "target_variable": "grounded_evidence",
                "metric_id": "grounded_evidence",
                "estimand": "owner_grounding_status",
            },
            "candidate_lever_space": {
                "allowed_operator_kinds": ["evidence_acquisition"],
                "candidate_levers": [
                    {
                        "lever_id": "acquire_evidence",
                        "operator_kind": "evidence_acquisition",
                        "instrument": "Owner evidence acquisition",
                        "target_slot": "grounded_evidence",
                    }
                ],
            },
            "evidence_acquisition_needs": {"needs": []},
        }
    )


def test_grounding_coverage_gap_is_content_bound_and_planner_routable() -> None:
    """A CG refusal must reach N7 as an unsatisfied owner-evidence need."""

    gap = acquisition_owner.grounding_coverage_requirement_gap(
        candidate_id="candidate_unresolved_lever",
        candidate_content_hash="sha256:" + "1" * 64,
        design_problem_ref="sha256:" + "2" * 64,
        issue_codes=("unknown_blocked", "cg2_relation_not_bind_eligible"),
        evidence_refs=("sha256:" + "3" * 64,),
        authority_level="research",
        grounding_report_ref="sha256:" + "4" * 64,
    )
    report = plan_requirement_gap_acquisition(
        run_id="run-grounding-coverage-gap",
        requirement_gaps=(gap,),
    )

    assert gap.requirement_family is RequirementGapFamily.DATA
    assert gap.metadata["source"] == "cgf_grounding_coverage"
    assert gap.metadata["candidate_binding"]["candidate_id"] == (
        "candidate_unresolved_lever"
    )
    assert gap.metadata["satisfaction_status"] == "unsatisfied"
    assert report.status == "pass"
    assert len(report.acquisition_records) == 1
    assert report.acquisition_records[0].requirement_gap_ref == (
        gap.requirement_gap_id
    )
    assert report.acquisition_records[0].terminal_disposition.value == "acquire"


def test_value_input_world_knowledge_gap_is_one_unsatisfied_any_of_requirement() -> None:
    gap = value_input_world_knowledge_requirement_gap(
        claim_ref="claim:value-input-world-knowledge",
    )

    assert isinstance(gap, AcquisitionRequirementGap)
    assert gap.requirement_family is RequirementGapFamily.DATA
    assert gap.gap_type is AcquisitionGapType.DATA_SNAPSHOT_RELEASE
    assert gap.missing_requirement_fields == (
        "world_knowledge:any_of(owner_rollout_assignment,certified_skg_identity_bridge)",
    )
    assert gap.metadata == {
        "schema_version": "policyos.runtime.value_input_world_knowledge_gap.v1",
        "source": "n8_value_input_world_knowledge",
        "acquisition_family": AcquisitionFamily.ID.value,
        "authority_purpose": "routing_only",
        "requirement": {
            "operator": "any_of",
            "alternatives": [
                {
                    "alternative_id": "owner_rollout_assignment",
                    "satisfaction_status": "unsatisfied",
                },
                {
                    "alternative_id": "certified_skg_identity_bridge",
                    "satisfaction_status": "unsatisfied",
                },
            ],
        },
        "satisfaction_status": "unsatisfied",
        "census_evidence": {
            "artifact_ref": (
                "architecture/policy_design_case/"
                "layer3_gy_n10_cg1_l2_relation_census.json"
            ),
            "content_hash": (
                "sha256:c6822ee88e9815508799f65e829086ef30e8809c00bca26bfa529dae3deea60c"
            ),
            "authority_purpose": "costing_and_provenance_only",
        },
    }

    report = plan_requirement_gap_acquisition(
        run_id="run-n8-value-input-acquisition",
        requirement_gaps=(gap,),
    )
    assert len(report.acquisition_records) == 1
    assert report.acquisition_records[0].terminal_disposition is AcquisitionDisposition.ACQUIRE
    assert "source_family_satisfaction" in report.authority_boundary["may_not_use_for"]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload["metadata"]["census_evidence"].__setitem__(
            "content_hash",
            "sha256:" + "0" * 64,
        ),
        lambda payload: payload["metadata"]["census_evidence"].__setitem__(
            "content_hash",
            "sha256:b06c1667128178a68dc9031ec52eaff260856bd062b5bfff73c51baeee8481d0",
        ),
        lambda payload: payload["metadata"]["requirement"].__setitem__(
            "alternatives",
            [
                {
                    "alternative_id": "owner_rollout_assignment",
                    "satisfaction_status": "unsatisfied",
                }
            ],
        ),
        lambda payload: payload["metadata"].__setitem__(
            "satisfaction_status",
            "satisfied",
        ),
        lambda payload: payload["metadata"].__setitem__(
            "authority_purpose",
            "satisfaction_authority",
        ),
        lambda payload: payload["metadata"]["requirement"]["alternatives"][
            0
        ].__setitem__("satisfaction_status", "satisfied"),
    ],
    ids=(
        "wrong-committed-census-hash",
        "superseded-census-hash",
        "missing-any-of-alternative",
        "fake-aggregate-satisfaction",
        "fake-satisfaction-authority",
        "fake-alternative-satisfaction",
    ),
)
def test_value_input_world_knowledge_gap_rejects_untrusted_metadata(mutator: object) -> None:
    payload = value_input_world_knowledge_requirement_gap(
        claim_ref="claim:value-input-world-knowledge",
    ).model_dump(mode="json")

    assert callable(mutator)
    mutator(payload)

    with pytest.raises(ValueError):
        AcquisitionRequirementGap.model_validate(payload)


def test_value_input_world_knowledge_gap_identity_cannot_bypass_metadata_validation() -> None:
    payload = value_input_world_knowledge_requirement_gap(
        claim_ref="claim:value-input-world-knowledge",
    ).model_dump(mode="json")
    payload["metadata"].pop("source")
    payload["metadata"].pop("schema_version")
    payload["metadata"]["satisfaction_status"] = "satisfied"

    with pytest.raises(ValueError):
        AcquisitionRequirementGap.model_validate(payload)


def _unavailable_l1_variable(
    variable_id: str = "employment_retention",
) -> L1VariableAvailability:
    return L1VariableAvailability(
        variable_id=variable_id,
        status="unavailable",
        dataset_count=0,
        metric_binding_count=0,
        observation_count=0,
        coverage_ref=(
            "repo://production_data/dataset_catalog.duckdb#variable/"
            f"{variable_id}"
        ),
    )


def test_l1_variable_availability_gap_routes_exact_owner_absence() -> None:
    availability = _unavailable_l1_variable()
    gap = l1_variable_availability_requirement_gap(
        candidate_id="candidate_employment_retention",
        candidate_content_hash="sha256:" + "3" * 64,
        design_problem_ref="sha256:" + "4" * 64,
        availability=availability,
        authority_level=AuthorityLevel.PRODUCTION,
    )

    assert gap.requirement_family is RequirementGapFamily.DATA
    assert gap.gap_type is AcquisitionGapType.DATA_SNAPSHOT_RELEASE
    assert gap.claim_ref == "value-claim:candidate_employment_retention"
    assert gap.producer_output_ref == availability.coverage_ref
    assert gap.missing_requirement_fields == (
        "canonical_variable_observations:employment_retention",
    )
    assert gap.metadata["source"] == "l1_dcat_variable_availability"
    assert gap.metadata["satisfaction_status"] == "unsatisfied"
    assert gap.metadata["availability"]["observation_count"] == 0

    report = plan_requirement_gap_acquisition(
        run_id="run-first-vertical-data-gap",
        requirement_gaps=(gap,),
    )
    assert report.status == "pass"
    assert len(report.acquisition_records) == 1
    record = report.acquisition_records[0]
    assert record.recommended_strategy is AcquisitionStrategy.PRODUCTION_SNAPSHOT_BUILD
    assert record.terminal_disposition is AcquisitionDisposition.ACQUIRE
    assert record.producer_output_ref == availability.coverage_ref


def test_l1_variable_availability_gap_rejects_available_or_tampered_evidence() -> None:
    available = L1VariableAvailability(
        variable_id="avg_income",
        status="available",
        dataset_count=1,
        metric_binding_count=1,
        observation_count=4,
        coverage_ref="repo://production_data/dataset_catalog.duckdb#variable/avg_income",
    )
    with pytest.raises(ValueError, match="l1_variable_is_not_an_acquisition_gap"):
        l1_variable_availability_requirement_gap(
            candidate_id="candidate_avg_income",
            candidate_content_hash="sha256:" + "5" * 64,
            design_problem_ref="sha256:" + "6" * 64,
            availability=available,
            authority_level=AuthorityLevel.PRODUCTION,
        )

    payload = l1_variable_availability_requirement_gap(
        candidate_id="candidate_employment_retention",
        candidate_content_hash="sha256:" + "3" * 64,
        design_problem_ref="sha256:" + "4" * 64,
        availability=_unavailable_l1_variable(),
        authority_level=AuthorityLevel.PRODUCTION,
    ).model_dump(mode="json")
    payload["metadata"]["availability"]["availability_content_hash"] = (
        "sha256:" + "0" * 64
    )

    with pytest.raises(ValueError, match="l1_variable_availability_hash_mismatch"):
        AcquisitionRequirementGap.model_validate(payload)


def test_l1_variable_availability_rejects_incoherent_unavailable_counts() -> None:
    with pytest.raises(ValueError, match="l1_unavailable_counts_nonzero"):
        L1VariableAvailability(
            variable_id="employment_retention",
            status="unavailable",
            dataset_count=0,
            metric_binding_count=0,
            observation_count=1,
            coverage_ref=(
                "repo://production_data/dataset_catalog.duckdb#variable/"
                "employment_retention"
            ),
        )


def test_generation_cycle_bootstrap_authority_is_strangled() -> None:
    """The N7 checker derives both caller census and fail-closed owner refusal."""

    witness = contract.generation_cycle_substrate_fence(REPO_ROOT)

    assert witness["status"] == "strangled"
    assert witness["production_bootstrap_callers"] == []
    assert witness["bootstrap_authority_literals"] == []
    assert witness["owner_absence_reason"] == "n7_substrate_registry_unresolved"
    assert witness["fabricated_registry"] is False


def _decision(
    *,
    run_id: str,
    gap_id: str,
    strategy: str,
    value: float,
    cost: float = 0.1,
) -> VOIDecisionRecord:
    return VOIDecisionRecord(
        decision_id=stable_voi_decision_id(
            run_id=run_id,
            decision_type=VOIDecisionType.SOURCE_VERIFICATION,
            subject_id=f"{gap_id}:{strategy}",
        ),
        run_id=run_id,
        decision_type=VOIDecisionType.SOURCE_VERIFICATION,
        recommended_action=strategy,
        expected_value=value,
        expected_cost=cost,
        expected_risk_reduction=max(0.0, value / 10),
        explanation=f"{strategy} has candidate VOI for {gap_id}.",
        metadata={"gap_id": gap_id, "strategy": strategy},
    )


def _voi_report(run_id: str, decisions: list[VOIDecisionRecord]) -> VOIRunReport:
    return VOIRunReport(
        run_id=run_id,
        decisions=decisions,
        total_expected_cost=sum(decision.expected_cost for decision in decisions),
        calibration_status="shadow",
        metadata={"artifact_ref": f"cas://voi/{run_id}"},
    )


def test_planner_consumes_compiled_requirement_gaps_for_each_requirement_family() -> None:
    data_spec, legal_spec, method_spec, scholar_spec, participation_spec = (
        _compiled_requirement_specs()
    )

    gaps = requirement_gaps_from_compiled_specs(
        data_requirement_specs=[data_spec],
        legal_authority_requirement_specs=[legal_spec],
        method_validity_requirement_specs=[method_spec],
        scholar_support_requirement_specs=[scholar_spec],
        participation_provenance_requirement_specs=[participation_spec],
    )
    report = plan_requirement_gap_acquisition(
        run_id="run-acq-w7g-1",
        requirement_gaps=gaps,
    )

    assert {gap.requirement_family for gap in gaps} == {
        RequirementGapFamily.DATA,
        RequirementGapFamily.LEGAL_AUTHORITY,
        RequirementGapFamily.METHOD_VALIDITY,
        RequirementGapFamily.SCHOLAR_SUPPORT,
        RequirementGapFamily.PARTICIPATION_PROVENANCE,
    }
    assert {gap.gap_type for gap in gaps} == {
        AcquisitionGapType.SCENARIO_SOURCE_FAMILY,
        AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY,
        AcquisitionGapType.METHOD_OBLIGATION,
        AcquisitionGapType.ACADEMIC_SCHOLAR_SUPPORT,
        AcquisitionGapType.PARTICIPATION_AFFECTED_PERSON_CLAIM,
    }
    assert len(report.acquisition_records) == 5

    by_family = {
        record.requirement_family: record for record in report.acquisition_records
    }
    data_record = by_family[RequirementGapFamily.DATA.value]
    legal_record = by_family[RequirementGapFamily.LEGAL_AUTHORITY.value]
    method_record = by_family[RequirementGapFamily.METHOD_VALIDITY.value]
    scholar_record = by_family[RequirementGapFamily.SCHOLAR_SUPPORT.value]
    participation_record = by_family[RequirementGapFamily.PARTICIPATION_PROVENANCE.value]

    assert data_record.compiled_requirement_ref == data_spec.requirement_id
    assert data_record.requirement_gap_ref == (
        "requirement-gap:data_requirement:data-requirement:claim-source-family"
    )
    assert data_record.scenario_requirement_refs == (
        data_spec.requirement_id,
        "production_msme_panel",
    )
    assert data_record.missing_requirement_fields == (
        "required_data_family:production_msme_panel",
        "mandatory_facet:source_contract_ref",
        "mandatory_facet:lineage_refs",
    )
    assert data_record.recommended_strategy is AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION
    assert data_record.terminal_disposition is AcquisitionDisposition.ACQUIRE

    assert legal_record.compiled_requirement_ref == legal_spec.requirement_id
    assert legal_record.authority_level is AuthorityLevel.PRODUCTION
    assert legal_record.mandatory_gate_state is MandatoryGateState.NON_OVERRIDABLE
    assert method_record.compiled_requirement_ref == method_spec.requirement_id
    assert scholar_record.compiled_requirement_ref == scholar_spec.requirement_id
    assert participation_record.compiled_requirement_ref == participation_spec.requirement_id
    assert participation_record.mandatory_gate_state is MandatoryGateState.NON_OVERRIDABLE


def test_planner_consumes_capability_failure_mode_nodes_as_acquisition_gaps() -> None:
    gaps = acquisition_gaps_from_capability_failure_modes(
        [
            FailureModeNode(
                failure_id="failure:construct_not_observed:credit_program_enrollment:UA",
                construct="credit_program_enrollment",
                geography="UA",
                cause_class="construct_not_observed",
                severity="blocking_production",
                owner="team-data-acquisition",
                acquisition_strategy_refs=("acquisition:acquire_from_nbu_registry",),
                affected_authority_postures=("production",),
                detected_at="2026-05-25",
                status="blocked_construct_not_observed",
                gap_type="construct_gap",
                domain=("msme_credit",),
                producer_owner="team-data-acquisition",
                authority_posture="production",
            )
        ],
        claim_ref="claim:credit-program-enrollment",
    )

    assert len(gaps) == 1
    assert gaps[0].gap_type is AcquisitionGapType.SCENARIO_SOURCE_FAMILY
    assert gaps[0].authority_level is AuthorityLevel.PRODUCTION
    assert gaps[0].mandatory_gate_state is MandatoryGateState.NON_OVERRIDABLE
    assert gaps[0].missing_requirement_fields == (
        "construct:credit_program_enrollment",
        "failure_mode:blocked_construct_not_observed",
        "gap_type:construct_gap",
    )
    assert gaps[0].metadata["capability_failure_mode_ref"] == (
        "failure:construct_not_observed:credit_program_enrollment:UA"
    )


def test_requirement_gap_planning_filters_voi_before_ranking() -> None:
    data_spec = _compiled_requirement_specs()[0]
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=[data_spec])[0]

    report = plan_requirement_gap_acquisition(
        run_id="run-acq-w7g-2",
        requirement_gaps=[gap],
        voi_report=_voi_report(
            "run-acq-w7g-2",
            [
                _decision(
                    run_id="run-acq-w7g-2",
                    gap_id=gap.requirement_gap_id,
                    strategy="academic_retrieval",
                    value=30.0,
                ),
                _decision(
                    run_id="run-acq-w7g-2",
                    gap_id=gap.requirement_gap_id,
                    strategy="proxy_with_degraded_authority",
                    value=20.0,
                ),
                _decision(
                    run_id="run-acq-w7g-2",
                    gap_id=gap.requirement_gap_id,
                    strategy="source_contract_remediation",
                    value=1.0,
                ),
            ],
        ),
    )

    record = report.acquisition_records[0]

    assert isinstance(gap, AcquisitionRequirementGap)
    assert record.requirement_gap_ref == gap.requirement_gap_id
    assert record.recommended_strategy is AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION
    assert record.terminal_disposition is AcquisitionDisposition.ACQUIRE
    assert record.strategy_records[0].strategy == "source_contract_remediation"
    assert {
        item.strategy: item.eligibility_reason
        for item in record.ineligible_strategy_records
        if item.strategy in {"academic_retrieval", "proxy_with_degraded_authority"}
    } == {
        "academic_retrieval": "non_overridable_mandatory_gate_dominates_voi",
        "proxy_with_degraded_authority": "non_overridable_mandatory_gate_dominates_voi",
    }


def test_requirement_gap_voi_metadata_binds_ranking_to_compiled_requirement_gap() -> None:
    data_spec = _compiled_requirement_specs()[0].model_copy(
        update={
            "metadata": {
                "mandatory_gate_state": "none",
            }
        }
    )
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=[data_spec])[0]
    decision = VOIDecisionRecord(
        decision_id=stable_voi_decision_id(
            run_id="run-acq-w7g-3",
            decision_type=VOIDecisionType.SOURCE_VERIFICATION,
            subject_id=f"{gap.requirement_gap_id}:public_registry",
        ),
        run_id="run-acq-w7g-3",
        decision_type=VOIDecisionType.SOURCE_VERIFICATION,
        recommended_action="source_contract_remediation",
        expected_value=4.0,
        expected_cost=0.5,
        expected_risk_reduction=0.4,
        explanation="Requirement-gap VOI should bind through W7.G metadata.",
        metadata=acquisition_voi_metadata(
            requirement_gap_id=gap.requirement_gap_id,
            acquisition_strategy="public_registry",
            requirement_family=gap.requirement_family.value,
        ),
    )

    report = plan_requirement_gap_acquisition(
        run_id="run-acq-w7g-3",
        requirement_gaps=[gap],
        voi_report=_voi_report("run-acq-w7g-3", [decision]),
    )

    record = report.acquisition_records[0]

    assert record.recommended_strategy is AcquisitionStrategy.PUBLIC_REGISTRY
    assert record.strategy_records[0].voi_decision_ref == decision.decision_id
    assert record.strategy_records[0].voi_rank == 1


def test_non_overridable_gate_blocks_even_when_voi_prefers_proxy() -> None:
    report = plan_evidence_acquisition(
        run_id="run-acq-1",
        gaps=[
            AcquisitionGap(
                gap_id="gap-legal-authority",
                gap_type=AcquisitionGapType.LEGAL_COMPETENCE_AUTHORITY,
                claim_ref="claim://recommendation/legal-authority",
                authority_level=AuthorityLevel.PRODUCTION,
                mandatory_gate_state=MandatoryGateState.NON_OVERRIDABLE,
                mandatory_gate_refs=("gate://legal-competence",),
            )
        ],
        voi_report=_voi_report(
            "run-acq-1",
            [
                _decision(
                    run_id="run-acq-1",
                    gap_id="gap-legal-authority",
                    strategy="proxy_with_degraded_authority",
                    value=10.0,
                ),
                _decision(
                    run_id="run-acq-1",
                    gap_id="gap-legal-authority",
                    strategy="survey",
                    value=9.0,
                ),
            ],
        ),
    )

    record = report.acquisition_records[0]

    assert record.recommended_strategy is AcquisitionStrategy.CLOSEOUT_BLOCK
    assert record.terminal_disposition is AcquisitionDisposition.CLOSEOUT_BLOCK
    assert record.blocker_ref == "blocker:gap-legal-authority:closeout_block"
    assert record.limitation_ref is None
    assert record.accepted_deficit_ref is None
    assert record.next_actions[0].action == "block_closeout"
    assert {item.strategy for item in record.ineligible_strategy_records} >= {
        "proxy_with_degraded_authority",
        "survey",
    }


def test_voi_ranking_is_filtered_by_eligibility_before_recommendation() -> None:
    report = plan_evidence_acquisition(
        run_id="run-acq-2",
        gaps=[
            AcquisitionGap(
                gap_id="gap-source-family",
                gap_type=AcquisitionGapType.SCENARIO_SOURCE_FAMILY,
                claim_ref="claim://recommendation/source-family",
                scenario_requirement_refs=("scenario:req:production_msme_panel",),
                authority_level=AuthorityLevel.PRODUCTION,
                mandatory_gate_state=MandatoryGateState.NONE,
            )
        ],
        voi_report=_voi_report(
            "run-acq-2",
            [
                _decision(
                    run_id="run-acq-2",
                    gap_id="gap-source-family",
                    strategy="academic_retrieval",
                    value=20.0,
                ),
                _decision(
                    run_id="run-acq-2",
                    gap_id="gap-source-family",
                    strategy="source_contract_remediation",
                    value=1.0,
                ),
            ],
        ),
    )

    record = report.acquisition_records[0]

    assert record.recommended_strategy is AcquisitionStrategy.SOURCE_CONTRACT_REMEDIATION
    assert record.terminal_disposition is AcquisitionDisposition.ACQUIRE
    assert "academic_retrieval" in record.ineligible_strategies
    assert record.strategy_records[0].strategy == "source_contract_remediation"
    assert record.strategy_records[0].eligible is True


def test_deficit_limitation_and_block_states_remain_distinct() -> None:
    report = plan_evidence_acquisition(
        run_id="run-acq-3",
        gaps=[
            AcquisitionGap(
                gap_id="gap-scholar",
                gap_type=AcquisitionGapType.ACADEMIC_SCHOLAR_SUPPORT,
                claim_ref="claim://research/scholar",
                authority_level=AuthorityLevel.RESEARCH,
                mandatory_gate_state=MandatoryGateState.NONE,
            ),
            AcquisitionGap(
                gap_id="gap-facet",
                gap_type=AcquisitionGapType.FACET,
                claim_ref="claim://governed/facet",
                scenario_requirement_refs=("scenario:req:lineage",),
                authority_level=AuthorityLevel.GOVERNED,
                mandatory_gate_state=MandatoryGateState.OVERRIDABLE_BY_GOVERNED_COMMIT,
                limitation_permitted=True,
                decision_owner_ref="review://governed-owner/facet",
            ),
            AcquisitionGap(
                gap_id="gap-snapshot",
                gap_type=AcquisitionGapType.DATA_SNAPSHOT_RELEASE,
                claim_ref="claim://production/snapshot",
                authority_level=AuthorityLevel.PRODUCTION,
                mandatory_gate_state=MandatoryGateState.NON_OVERRIDABLE,
                mandatory_gate_refs=("gate://official-snapshot",),
            ),
        ],
        voi_report=_voi_report(
            "run-acq-3",
            [
                _decision(
                    run_id="run-acq-3",
                    gap_id="gap-scholar",
                    strategy="accepted_deficit",
                    value=3.0,
                ),
                _decision(
                    run_id="run-acq-3",
                    gap_id="gap-facet",
                    strategy="publish_with_limitation",
                    value=4.0,
                ),
                _decision(
                    run_id="run-acq-3",
                    gap_id="gap-snapshot",
                    strategy="proxy_with_degraded_authority",
                    value=10.0,
                ),
            ],
        ),
    )

    by_gap = {record.gap_id: record for record in report.acquisition_records}

    assert by_gap["gap-scholar"].terminal_disposition is (
        AcquisitionDisposition.ACCEPTED_DEFICIT
    )
    assert by_gap["gap-scholar"].accepted_deficit_ref == (
        "accepted_deficit:gap-scholar"
    )
    assert by_gap["gap-scholar"].limitation_ref is None
    assert by_gap["gap-facet"].terminal_disposition is (
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION
    )
    assert by_gap["gap-facet"].limitation_ref == "limitation:gap-facet"
    assert by_gap["gap-facet"].commit_authority == "human_governed_commit_required"
    assert by_gap["gap-snapshot"].terminal_disposition is (
        AcquisitionDisposition.CLOSEOUT_BLOCK
    )
    assert by_gap["gap-snapshot"].blocker_ref == "blocker:gap-snapshot:closeout_block"

    deficits = acquisition_report_deficit_records(
        report,
        ttl_expires_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    dispositions = {item["deficit_id"]: item["disposition"] for item in deficits}
    assert dispositions == {
        "accepted_deficit:gap-scholar": "accepted_deficit",
        "limitation:gap-facet": "publish_with_limitation",
        "blocker:gap-snapshot:closeout_block": "hard_block",
    }


def test_acquisition_planner_report_persists_as_first_class_artifact(
    store: FileSystemCAS,
) -> None:
    report = plan_evidence_acquisition(
        run_id="run-acq-4",
        gaps=[
            AcquisitionGap(
                gap_id="gap-method",
                gap_type=AcquisitionGapType.METHOD_OBLIGATION,
                claim_ref="claim://method",
                authority_level=AuthorityLevel.GOVERNED,
                mandatory_gate_state=MandatoryGateState.NONE,
            )
        ],
    )

    ref = persist_acquisition_planner_report(store, report)
    loaded = load_acquisition_planner_report(store, ref)

    assert loaded == report
    assert str(ref.artifact_id)


def test_scorecard_surfaces_acquisition_blockers_as_runtime_closeout_failures() -> None:
    report = plan_evidence_acquisition(
        run_id="run-acq-5",
        gaps=[
            AcquisitionGap(
                gap_id="gap-participation",
                gap_type=AcquisitionGapType.PARTICIPATION_AFFECTED_PERSON_CLAIM,
                claim_ref="claim://production/participation-prevalence",
                authority_level=AuthorityLevel.PRODUCTION,
                mandatory_gate_state=MandatoryGateState.NON_OVERRIDABLE,
                mandatory_gate_refs=("gate://participation-process",),
            )
        ],
        voi_report=_voi_report(
            "run-acq-5",
            [
                _decision(
                    run_id="run-acq-5",
                    gap_id="gap-participation",
                    strategy="publish_with_limitation",
                    value=12.0,
                )
            ],
        ),
    )

    gates = acquisition_planner_scorecard_gates(
        report.model_dump(mode="json"),
        canary_kind="production",
    )
    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-acq",
        run_id="run-acq-5",
        execution_status="completed",
        job_payload={"progress": {"details": {}}},
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence={"acquisition_planner_report": report.model_dump(mode="json")},
    )
    codes = {gate["code"] for gate in scorecard["quality_gates"]}

    assert gates[0]["code"] == "acquisition_planner_closeout_block"
    assert gates[0]["blocking"] is True
    assert "acquisition_planner_closeout_block" in codes
    assert "acquisition_planner_closeout_block" in {
        failure["code"] for failure in scorecard["blocking_quality_failures"]
    }


def test_n7_closed_loop_compiles_all_specs_and_reenters_same_cycle() -> None:
    data_spec = _compiled_requirement_specs()[0]
    second_spec = data_spec.model_copy(
        update={
            "requirement_id": "data-requirement:claim-calibration-panel",
            "claim_id": "claim-calibration-panel",
            "required_data_families": ("tax_admin_panel",),
        }
    )
    world = AcquisitionWorldSnapshot(
        world_ref="world://before/n7",
        known_slots=("production_msme_panel",),
        dependency_index={
            "production_msme_panel": ("design:credit", "design:portfolio"),
            "tax_admin_panel": ("design:tax", "design:portfolio"),
        },
        design_revalidation_stages={
            "design:credit": ("identification", "calibration", "value_set", "grounding"),
            "design:portfolio": ("identification", "calibration", "value_set", "grounding"),
            "design:tax": ("identification", "calibration", "value_set", "grounding"),
        },
        substrate_registry=_substrate_registry().model_dump(mode="json"),
    )
    gateway = RecordedAcquisitionOwnerGateway(
        artifacts_by_requirement={
            data_spec.requirement_id: _captured_owner_artifact(
                owner_component="fabric.ingestion",
                requirement_ref=data_spec.requirement_id,
                artifact_ref="fabric://recorded/production-msme-panel",
                acquired_family="production_msme_panel",
                source_id="fabric.production_msme_panel",
                candidate_id="design:credit",
                cost_usd=11.25,
            ),
            second_spec.requirement_id: _captured_owner_artifact(
                owner_component="data_forge.skg",
                requirement_ref=second_spec.requirement_id,
                artifact_ref="skg://recorded/tax-admin-panel",
                acquired_family="tax_admin_panel",
                source_id="skg.tax_admin_panel",
                candidate_id="design:tax",
                cost_usd=7.5,
            ),
        }
    )

    receipt = run_acquisition_closed_loop(
        run_id="run-n7-closed-loop",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "missing_supporting_data",
            "counterexample_ref": "pdc://gy/n6/counterexample/001",
            "cycle_index": 3,
        },
        data_requirement_specs=(data_spec, second_spec),
        world_snapshot=world,
        design_problem=_acquisition_design_problem(),
        owner_gateway=gateway,
        useful_design_rate_before=0.0,
    )

    assert receipt.compiled_spec_count == 2
    assert receipt.source_cycle_index == 3
    assert receipt.reentry_cycle_index == 3
    assert receipt.grown_world_before_ref == "world://before/n7"
    assert receipt.grown_world_after_ref != receipt.grown_world_before_ref
    assert set(receipt.grown_world_added_slots) == {"production_msme_panel", "tax_admin_panel"}
    assert {outcome.status for outcome in receipt.world_write_outcomes} == {"written"}
    assert receipt.real_grounding_result_count == 2
    assert receipt.useful_design_rate_after > 0.0
    assert set(receipt.affected_region.design_ids) == {
        "design:credit",
        "design:portfolio",
        "design:tax",
    }
    assert set(receipt.affected_region.rederived_design_ids) == set(
        receipt.affected_region.design_ids
    )
    assert {entry.sequence for entry in receipt.journal_entries} == {1, 2}
    assert validate_acquisition_receipt(receipt) == ()


def test_n7_missing_design_problem_refuses_grounding_rederive_without_crash() -> None:
    """World growth without real problem authority cannot mint grounding."""

    data_spec = _compiled_requirement_specs()[0]
    receipt = run_acquisition_closed_loop(
        run_id="run-n7-missing-design-problem",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "missing_supporting_data",
            "counterexample_ref": "pdc://gy/n7/counterexample/missing-problem",
            "cycle_index": 3,
        },
        data_requirement_specs=(data_spec,),
        world_snapshot=AcquisitionWorldSnapshot(
            world_ref="world://before/missing-design-problem",
            known_slots=("production_msme_panel",),
            dependency_index={"production_msme_panel": ("design:credit",)},
            design_revalidation_stages={
                "design:credit": (
                    "identification",
                    "calibration",
                    "value_set",
                    "grounding",
                )
            },
            substrate_registry=_substrate_registry().model_dump(mode="json"),
        ),
        owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={
                data_spec.requirement_id: _captured_owner_artifact(
                    owner_component="fabric.ingestion",
                    requirement_ref=data_spec.requirement_id,
                    artifact_ref="fabric://recorded/missing-design-problem",
                    acquired_family="production_msme_panel",
                    source_id="fabric.production_msme_panel",
                    candidate_id="design:credit",
                    cost_usd=11.25,
                )
            }
        ),
        useful_design_rate_before=0.0,
    )

    assert receipt.real_grounding_result_count == 0
    assert receipt.status == "completed_no_results"
    assert receipt.grounding_rederivations[0].issue_codes == (
        "design_problem_unavailable_after_world_write",
    )
    assert any(
        reason.endswith(":design_problem_unavailable_after_world_write")
        for reason in receipt.fail_closed_reasons
    )


def test_n7_no_result_records_costed_gap_without_forcing_useful_rate() -> None:
    data_spec = _compiled_requirement_specs()[0]
    owner_response = {"owner_response_kind": "fabric_retrieval_no_result", "rows": []}
    payload = {
        "owner_response_kind": "real_owner_capture",
        "owner_response": owner_response,
        "raw_owner_response_hash": _stable_json_hash(owner_response),
        "acquired_substrate_registrations": [],
        "candidate_bindings": [],
    }
    world = AcquisitionWorldSnapshot(
        world_ref="world://before/no-result",
        known_slots=("production_msme_panel",),
        dependency_index={"production_msme_panel": ("design:credit",)},
        design_revalidation_stages={
            "design:credit": ("identification", "calibration", "value_set", "grounding")
        },
        substrate_registry=_substrate_registry().model_dump(mode="json"),
    )
    gateway = RecordedAcquisitionOwnerGateway(
        artifacts_by_requirement={
            data_spec.requirement_id: AcquisitionOwnerArtifact.from_payload(
                owner_component="fabric.retrieval",
                requirement_ref=data_spec.requirement_id,
                artifact_ref="fabric://recorded/no-result",
                payload=payload,
                cost_usd=3.75,
                quality={"query_validated": True},
                rights={"license": "recorded-open"},
                binding_refs=(),
                journal_ref="journal://n7/no-result/001",
                capture_provenance=_capture_provenance(
                    owner_component="fabric.retrieval",
                    endpoint="RetrievalService.resolve",
                    request={"requirement_ref": data_spec.requirement_id},
                    response=payload,
                ),
            )
        }
    )

    receipt = run_acquisition_closed_loop(
        run_id="run-n7-no-result",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "missing_supporting_data",
            "counterexample_ref": "pdc://gy/n6/counterexample/002",
            "cycle_index": 4,
        },
        data_requirement_specs=(data_spec,),
        world_snapshot=world,
        owner_gateway=gateway,
        useful_design_rate_before=0.0,
    )

    assert receipt.status == "completed_no_results"
    assert receipt.real_grounding_result_count == 0
    assert receipt.no_result_costed_gap is True
    assert receipt.useful_design_rate_after == 0.0
    assert receipt.cost_summary_usd > 0
    assert validate_acquisition_receipt(receipt) == ()


def test_n7_fake_artifact_grounded_true_for_nonexistent_slot_stays_costed_gap() -> None:
    data_spec = _compiled_requirement_specs()[0]
    receipt = run_acquisition_closed_loop(
        run_id="run-n7-fake-grounding",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "missing_supporting_data",
            "counterexample_ref": "pdc://gy/n6/counterexample/fake",
            "cycle_index": 1,
        },
        data_requirement_specs=(data_spec,),
        world_snapshot=AcquisitionWorldSnapshot(
            world_ref="world://before/fake-grounding",
            known_slots=("production_msme_panel",),
            dependency_index={"production_msme_panel": ("design:credit",)},
            design_revalidation_stages={
                "design:credit": ("identification", "calibration", "value_set", "grounding")
            },
            substrate_registry=_substrate_registry().model_dump(mode="json"),
        ),
        owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={
                data_spec.requirement_id: AcquisitionOwnerArtifact.from_payload(
                    owner_component="fake.nonexistent.owner",
                    requirement_ref=data_spec.requirement_id,
                    artifact_ref="fake://recorded/ghost",
                    payload={
                        "world_slots": ["ghost.nonexistent_world_slot"],
                        "grounding_results": [{"candidate_id": "design:credit", "grounded": True}],
                    },
                    cost_usd=4.25,
                    quality={"completeness": 1.0},
                    rights={"license": "fake"},
                    binding_refs=(),
                    journal_ref="journal://n7/fake-ghost/001",
                    capture_provenance=_capture_provenance(
                        owner_component="fake.nonexistent.owner",
                        endpoint="fake.nonexistent.owner.acquire",
                        request={"requirement_ref": data_spec.requirement_id},
                        response={
                            "world_slots": ["ghost.nonexistent_world_slot"],
                            "grounding_results": [
                                {"candidate_id": "design:credit", "grounded": True}
                            ],
                        },
                    ),
                )
            }
        ),
        useful_design_rate_before=0.0,
    )

    assert receipt.real_grounding_result_count == 0
    assert receipt.useful_design_rate_after == 0.0
    assert receipt.no_result_costed_gap is True
    assert receipt.grown_world_after_ref == receipt.grown_world_before_ref
    assert any(
        reason.startswith("world_write_rejected:data-requirement:claim-source-family")
        for reason in receipt.fail_closed_reasons
    )


def test_n7_receipt_validation_rejects_uncaptured_owner_artifact() -> None:
    data_spec = _compiled_requirement_specs()[0]
    artifact = _captured_owner_artifact(
        owner_component="fabric.ingestion",
        requirement_ref=data_spec.requirement_id,
        artifact_ref="fabric://recorded/uncaptured",
        acquired_family="production_msme_panel",
        source_id="fabric.production_msme_panel",
        candidate_id="design:credit",
        cost_usd=4.25,
    ).model_copy(update={"capture_provenance": None})
    receipt = run_acquisition_closed_loop(
        run_id="run-n7-content-bind",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "missing_supporting_data",
            "counterexample_ref": "pdc://gy/n6/counterexample/003",
            "cycle_index": 1,
        },
        data_requirement_specs=(data_spec,),
        world_snapshot=AcquisitionWorldSnapshot(
            world_ref="world://before/content-bind",
            known_slots=("production_msme_panel",),
            dependency_index={"production_msme_panel": ("design:credit",)},
            design_revalidation_stages={
                "design:credit": ("identification", "calibration", "value_set", "grounding")
            },
            substrate_registry=_substrate_registry().model_dump(mode="json"),
        ),
        owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={data_spec.requirement_id: artifact}
        ),
    )

    issue_codes = {issue["code"] for issue in validate_acquisition_receipt(receipt)}

    assert "acquisition_artifact_not_captured_from_owner" in issue_codes


def test_n7_receipt_validation_rejects_fabricated_provenance_without_raw_owner_response() -> None:
    data_spec = _compiled_requirement_specs()[0]
    payload = {
        "owner_response_kind": "acquisition_owner_raw_response",
        "acquired_substrate_registrations": [
            _registration(
                source_id="fabric.production_msme_panel",
                family_id="production_msme_panel",
                snapshot_id="snapshot:production_msme_panel:2026-07-05",
            ).model_dump(mode="json")
        ],
        "candidate_bindings": [
            {
                "candidate_id": "design:credit",
                "candidate_content_hash": "sha256:" + "d" * 64,
                "target_world_slots": ["production_msme_panel"],
            }
        ],
    }
    artifact = AcquisitionOwnerArtifact.from_payload(
        owner_component="fabric.ingestion",
        requirement_ref=data_spec.requirement_id,
        artifact_ref="fabric://recorded/fabricated-provenance",
        payload=payload,
        cost_usd=4.25,
        quality={"capture": "fabricated"},
        rights={"license": "recorded-open"},
        binding_refs=("design:credit",),
        journal_ref="journal://n7/fabricated-provenance/001",
        capture_provenance=_capture_provenance(
            owner_component="fabric.ingestion",
            endpoint="fabric.ingestion.acquire",
            request={"requirement_ref": data_spec.requirement_id},
            response=payload,
        ),
    )
    receipt = run_acquisition_closed_loop(
        run_id="run-n7-fabricated-provenance",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "missing_supporting_data",
            "counterexample_ref": "pdc://gy/n6/counterexample/fabricated-provenance",
            "cycle_index": 1,
        },
        data_requirement_specs=(data_spec,),
        world_snapshot=AcquisitionWorldSnapshot(
            world_ref="world://before/fabricated-provenance",
            known_slots=("production_msme_panel",),
            dependency_index={"production_msme_panel": ("design:credit",)},
            design_revalidation_stages={
                "design:credit": ("identification", "calibration", "value_set", "grounding")
            },
            substrate_registry=_substrate_registry().model_dump(mode="json"),
        ),
        owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={data_spec.requirement_id: artifact}
        ),
    )

    issue_codes = {issue["code"] for issue in validate_acquisition_receipt(receipt)}

    assert "acquisition_provenance_not_recomputable_from_real_owner" in issue_codes


def test_real_owner_gateway_records_local_skg_response_without_network() -> None:
    base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    base_spec["requirement_id"] = "data-requirement:claim-skg-source-family"
    base_spec["claim_id"] = "claim-skg-source-family"
    base_spec["required_data_families"] = ("tax_admin_panel",)
    base_spec["required_method_families"] = ("skg_schema_probe",)
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
    report = plan_requirement_gap_acquisition(
        run_id="run-n7-real-skg-owner",
        requirement_gaps=(gap,),
        generated_at=datetime(2026, 7, 5, tzinfo=UTC),
    )
    gateway = RealAcquisitionOwnerGateway(
        repo_root=Path("."),
        captured_at=datetime(2026, 7, 5, tzinfo=UTC),
    )

    artifact = gateway.acquire(
        record=report.acquisition_records[0],
        compiled_requirement_spec=base_spec,
    )

    assert artifact is not None
    assert artifact.owner_component == "data_forge.skg"
    assert artifact.capture_provenance is not None
    assert artifact.capture_provenance.owner_endpoint == "skg_store.ensure_skg_schema"
    assert artifact.capture_provenance.network_call is False
    assert gateway.network_counter.network_calls == 0
    assert artifact.payload["owner_response"]["owner_response_kind"] == "skg_local_schema_probe"
    assert artifact.payload["owner_response"]["table_count"] > 0
    assert artifact.payload.get("grounding_results") is None
    assert artifact.payload["acquired_substrate_registrations"]


def test_n7_lossy_required_data_adapter_is_strangled() -> None:
    multi_gap = RequiredDataGap(
        missing_distributions=("local_tourism_site_traffic", "administrative_tax_receipts"),
        suggested_experiment="site-count intercept survey",
    )

    plans = AcquisitionPlanner().plans_from_required_data(
        multi_gap,
        workspace_id="ws-lossless",
    )

    assert [plan.costed_plan["missing_distribution"] for plan in plans] == [
        "local_tourism_site_traffic",
        "administrative_tax_receipts",
    ]
    with pytest.raises(ValueError, match="lossless_multi_gap_planning_required"):
        AcquisitionPlanner().plan_from_required_data(multi_gap, workspace_id="ws-lossless")
    assert acquisition_strangle_receipt().status == "strangled"


def test_n7_id_family_prefers_many_frontier_width_shrinkers() -> None:
    ranked = rank_acquisition_candidates_by_family(
        [
            {
                "candidate_id": "single-design",
                "family": AcquisitionFamily.ID,
                "frontier_width_shrinkage_by_design": {"design:a": 0.55},
            },
            {
                "candidate_id": "many-designs",
                "family": AcquisitionFamily.ID,
                "frontier_width_shrinkage_by_design": {
                    "design:a": 0.25,
                    "design:b": 0.25,
                    "design:c": 0.25,
                },
            },
        ]
    )

    assert ranked[0]["candidate_id"] == "many-designs"
    assert ranked[0]["score"] > ranked[1]["score"]


def test_n7_grounding_blocker_compiles_to_acquisition_request_and_denominator_hooks() -> None:
    request = acquisition_request_from_world_acquirable(
        {
            "completion_id": "cg3-world-acquirable-001",
            "blocker_kind": "world_slot",
            "world_slot": "cells.distress_score",
            "claim_ref": "claim:distress-score-grounding",
            "needed_evidence": ("measurement", "mechanism"),
        }
    )

    assert request["request_kind"] == "grounding_acquisition"
    assert request["acquisition_family"] == AcquisitionFamily.CERT.value
    assert request["target_world_slot"] == "cells.distress_score"
    assert set(ACQUISITION_FAMILY_DENOMINATOR) == {
        "ID",
        "CERT",
        "COV",
        "HV",
        "HKG",
        "ADV",
        "AUD",
        "SAFE",
    }
    assert request["compiles_to_n7"] is True


def test_n7_owner_validation_fails_closed_for_unresolvable_target() -> None:
    data_spec = _compiled_requirement_specs()[0]

    receipt = run_acquisition_closed_loop(
        run_id="run-n7-fail-closed",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "missing_supporting_data",
            "counterexample_ref": "pdc://gy/n6/counterexample/004",
            "cycle_index": 2,
        },
        data_requirement_specs=(data_spec,),
        world_snapshot=AcquisitionWorldSnapshot(
            world_ref="world://before/fail-closed",
            known_slots=("production_msme_panel",),
            dependency_index={"production_msme_panel": ("design:credit",)},
            design_revalidation_stages={
                "design:credit": ("identification", "calibration", "value_set", "grounding")
            },
            substrate_registry=_substrate_registry().model_dump(mode="json"),
        ),
        owner_gateway=RecordedAcquisitionOwnerGateway(artifacts_by_requirement={}),
        useful_design_rate_before=0.0,
    )

    assert receipt.status == "blocked"
    assert receipt.fail_closed_reasons == ("owner_artifact_missing:data-requirement:claim-source-family",)
    assert receipt.useful_design_rate_after == 0.0
    assert "owner_validation_failed_closed" in {
        issue["code"] for issue in validate_acquisition_receipt(receipt)
    }


def test_n7_network_counter_fails_routine_offline_if_gateway_leaks_owner_call() -> None:
    counter = AcquisitionNetworkCallCounter()
    counter.record_call(owner_component="data_forge.openalex", endpoint="/works")

    assert counter.network_calls == 1
    assert counter.assert_offline_check()["code"] == "routine_check_hit_network"


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("POLISYOS_N7_LIVE_OWNER_LANE") != "1",
    reason="cloud-gated N7 live owner lane; routine tests must not call the network",
)
def test_n7_cloud_live_owner_lane_calls_openalex_and_reenters_same_cycle() -> None:
    """Cloud lane: call a real owner once, then validate the normal N7 receipt path."""

    async def _fetch_openalex_payload() -> dict[str, object]:
        from polisyos.data_forge.domains.academic.openalex.client import (
            OpenAlexClient,
            OpenAlexRequest,
        )

        async with OpenAlexClient(
            email=os.environ.get("OPENALEX_MAILTO", ""),
            max_rps=1,
            max_concurrent=1,
            timeout_seconds=30,
            max_retries=1,
        ) as client:
            return await client.list_works(
                OpenAlexRequest(
                    filter_expr='title.search:"minimum wage"',
                    sort="cited_by_count:desc",
                    per_page=1,
                    select="id,title,publication_year,cited_by_count",
                )
            )

    data_spec = _compiled_requirement_specs()[0]
    payload = asyncio.run(_fetch_openalex_payload())
    results = payload.get("results")
    assert isinstance(results, list)
    assert results
    artifact = AcquisitionOwnerArtifact.from_payload(
        owner_component="data_forge.openalex",
        requirement_ref=data_spec.requirement_id,
        artifact_ref=str(results[0].get("id") or "openalex://works/live-n7"),
        payload=_owner_payload(
            acquired_family="openalex.live_claim_support",
            source_id="openalex.works",
            candidate_id="design:live-openalex",
            extra={"openalex_result": results[0]},
        ),
        cost_usd=0.0,
        quality={"owner": "openalex", "live_result_count": len(results)},
        rights={"source": "OpenAlex"},
        binding_refs=("claim-source-family",),
        journal_ref="journal://n7/live-openalex/001",
        capture_provenance=_capture_provenance(
            owner_component="data_forge.openalex",
            endpoint="OpenAlexClient.list_works",
            request={"filter": 'title.search:"minimum wage"', "per_page": 1},
            response=payload,
            network_call=True,
        ),
    )

    receipt = run_acquisition_closed_loop(
        run_id="run-n7-live-owner-cloud-lane",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "missing_supporting_data",
            "counterexample_ref": "pdc://gy/n6/counterexample/live",
            "cycle_index": 9,
        },
        data_requirement_specs=(data_spec,),
        world_snapshot=AcquisitionWorldSnapshot(
            world_ref="world://before/live-openalex",
            known_slots=(),
            dependency_index={"openalex.live_claim_support": ("design:live-openalex",)},
            design_revalidation_stages={
                "design:live-openalex": (
                    "identification",
                    "calibration",
                    "value_set",
                    "grounding",
                )
            },
            substrate_registry=_substrate_registry(
                family_ids=("production_msme_panel", "openalex.live_claim_support")
            ).model_dump(mode="json"),
        ),
        design_problem=_acquisition_design_problem(),
        owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={data_spec.requirement_id: artifact}
        ),
        useful_design_rate_before=0.0,
    )

    assert receipt.reentry_cycle_index == 9
    assert receipt.real_grounding_result_count == 1
    assert receipt.useful_design_rate_after > 0.0
    assert validate_acquisition_receipt(receipt) == ()


def _capture_provenance(
    *,
    owner_component: str,
    endpoint: str,
    request: dict[str, object],
    response: dict[str, object],
    network_call: bool = False,
) -> AcquisitionCaptureProvenance:
    return AcquisitionCaptureProvenance.from_owner_response(
        owner_component=owner_component,
        owner_endpoint=endpoint,
        owner_request=request,
        owner_response=response,
        captured_at=datetime(2026, 7, 5, tzinfo=UTC),
        capture_mode="live_owner" if network_call else "local_substrate_owner",
        network_call=network_call,
    )


def _captured_owner_artifact(
    *,
    owner_component: str,
    requirement_ref: str,
    artifact_ref: str,
    acquired_family: str,
    source_id: str,
    candidate_id: str,
    cost_usd: float,
) -> AcquisitionOwnerArtifact:
    payload = _owner_payload(
        acquired_family=acquired_family,
        source_id=source_id,
        candidate_id=candidate_id,
    )
    return AcquisitionOwnerArtifact.from_payload(
        owner_component=owner_component,
        requirement_ref=requirement_ref,
        artifact_ref=artifact_ref,
        payload=payload,
        cost_usd=cost_usd,
        quality={"capture": "real_owner_recording"},
        rights={"license": "recorded-open"},
        binding_refs=(candidate_id,),
        journal_ref=f"journal://n7/{acquired_family}/001",
        capture_provenance=_capture_provenance(
            owner_component=owner_component,
            endpoint=f"{owner_component}.acquire",
            request={"requirement_ref": requirement_ref},
            response=payload,
        ),
    )


def _owner_payload(
    *,
    acquired_family: str,
    source_id: str,
    candidate_id: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    owner_response: dict[str, object] = {
        "owner_response_kind": "recorded_unit_owner_response",
        "acquired_family": acquired_family,
        "source_id": source_id,
        "candidate_id": candidate_id,
    }
    payload: dict[str, object] = {
        "owner_response_kind": "real_owner_capture",
        "owner_response": owner_response,
        "raw_owner_response_hash": _stable_json_hash(owner_response),
        "acquired_substrate_registrations": [
            _registration(
                source_id=source_id,
                family_id=acquired_family,
                snapshot_id=f"snapshot:{acquired_family}:2026-07-05",
            ).model_dump(mode="json")
        ],
        "candidate_bindings": [
            {
                "candidate_id": candidate_id,
                "candidate_content_hash": "sha256:" + _slug_for_test(candidate_id)[:64].ljust(64, "0"),
                "target_world_slots": [acquired_family],
            }
        ],
    }
    if extra:
        payload.update(extra)
    return payload


def _substrate_registry(
    family_ids: tuple[str, ...] = ("production_msme_panel", "tax_admin_panel"),
) -> SubstrateRegistry:
    entries = [
        build_substrate_registry_entry(
            _registration(
                source_id=f"baseline.{family_id}",
                family_id=family_id,
                snapshot_id=f"baseline:{family_id}",
            )
        )
        for family_id in family_ids
    ]
    return build_substrate_registry(
        entries,
        producer_ref="tests.unit.runtime.quality.test_acquisition_planner",
        source_catalog_refs=("test://s0/substrate-registry",),
    )


def _registration(*, source_id: str, family_id: str, snapshot_id: str) -> SubstrateRegistration:
    return SubstrateRegistration(
        source_id=source_id,
        family_id=family_id,
        layer=SubstrateLayer.L1,
        coverage=SubstrateCoverage(
            coverage_score=0.92,
            coverage_kind="recorded_owner_response",
            coverage_rule_ref=f"test://coverage/{family_id}",
            dataset_count=1,
            metric_binding_count=1,
            observation_count=1,
        ),
        trust_tier=SubstrateTrustTier(
            tier="recorded",
            trust_cap=0.82,
            trust_multiplier=0.82,
            authority_ref=f"test://trust/{family_id}",
        ),
        identification_mode="observed_panel",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"manifest:{family_id}",
            authority_ref=f"test://schema/{family_id}",
        ),
        data_version="2026-07-05",
        snapshot_id=snapshot_id,
        source_snapshot_id=snapshot_id,
        provenance_refs=(f"test://provenance/{source_id}",),
        authority_refs=(f"test://authority/{family_id}",),
    )


def _slug_for_test(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum()) or "candidate"


def _stable_json_hash(value: dict[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _compiled_requirement_specs() -> tuple[
    DataRequirementSpec,
    LegalAuthorityRequirementSpec,
    MethodValidityRequirementSpec,
    ScholarSupportRequirementSpec,
    ParticipationProvenanceRequirementSpec,
]:
    data_spec = DataRequirementSpec(
        requirement_id="data-requirement:claim-source-family",
        claim_id="claim-source-family",
        required_data_families=("production_msme_panel",),
        scope=DataRequirementScope(
            population="msmes",
            geography="state_or_region",
            time="annual",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(min_quality_score=0.8, min_completeness=0.95),
        missingness_tolerance=0.02,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        concept_spine_refs=("concept:msme",),
        authority_profile_refs=("authority_profile.production",),
    )
    legal_spec = LegalAuthorityRequirementSpec(
        requirement_id="legal-requirement:claim-authority",
        claim_ref="claim:legal-authority",
        claim_id="claim-legal-authority",
        authority_types=(LegalAuthorityType.IMPLEMENTING,),
        required_instrument_classes=("credit_guarantee",),
        authority_profile_ref="production",
    )
    method_spec = MethodValidityRequirementSpec(
        requirement_id="method-requirement:claim-method",
        run_id="run-acq-w7g",
        claim_id="claim-method",
        identification_class=MethodIdentificationClass.POINT,
        method_expectations=["causal_effect_estimation"],
        required_method_families=["causal_effect_estimation"],
        authority_profile_refs=["authority_profile.governed"],
    )
    scholar_spec = ScholarSupportRequirementSpec(
        requirement_id="scholar-support:claim-scholar",
        claim_id="claim-scholar",
        claim_text="Credit guarantees improve MSME survival.",
        claim_type="causal",
        authority_level="production",
        required_publication_tier="peer_reviewed",
        recency_days=730,
        required_replication_count=2,
        required_independence_breadth=2,
        required_citation_network_depth=2,
        dependent_corpus_collapse_rules=[
            ScholarDependentCorpusCollapseRule(
                rule_id="collapse-study",
                collapse_on="underlying_study_id",
            )
        ],
    )
    participation_spec = ParticipationProvenanceRequirementSpec(
        requirement_id="participation-requirement:claim-preference",
        run_id="run-acq-w7g",
        claim_id="claim-preference",
        claim_family="preference",
        claim_purpose=ParticipationClaimPurpose.PREFERENCE,
        claim_use_requested=ParticipationClaimUse.PREVALENCE,
        authority_level=ParticipationAuthorityLevel.PRODUCTION,
        population_scope=ParticipationPopulationScope.AFFECTED_POPULATION,
        required_modes=(ParticipationSourceKind.SURVEY,),
        required_sampling_frame="scope_matched_sampling_frame",
        minimum_provenance_class=ParticipationProvenanceClass.A_REPRESENTATIVE_POPULATION,
        minimum_representativeness_class=(
            ParticipationRepresentativenessClass.REPRESENTATIVE
        ),
        consent_redaction="redacted_microdata",
        dissent_handling="dissent_recorded",
        sponsor_disclosure="sponsor_disclosed",
    )
    return data_spec, legal_spec, method_spec, scholar_spec, participation_spec
