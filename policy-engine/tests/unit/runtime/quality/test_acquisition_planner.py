from __future__ import annotations

from datetime import UTC, datetime

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
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionDisposition,
    AcquisitionGap,
    AcquisitionGapType,
    AcquisitionRequirementGap,
    AcquisitionStrategy,
    AuthorityLevel,
    MandatoryGateState,
    RequirementGapFamily,
    acquisition_gaps_from_capability_failure_modes,
    acquisition_planner_scorecard_gates,
    acquisition_report_deficit_records,
    load_acquisition_planner_report,
    persist_acquisition_planner_report,
    plan_evidence_acquisition,
    plan_requirement_gap_acquisition,
    requirement_gaps_from_compiled_specs,
)
from polisyos.runtime.quality.capability_index import FailureModeNode
from polisyos.runtime.quality.scorecard import build_quality_scorecard
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
