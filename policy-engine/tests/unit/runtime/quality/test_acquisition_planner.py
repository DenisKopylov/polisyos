from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.control import DataDiscoverRequest, DataResolveRequest
from polisyos.data_requirement import (
    CapabilityRequirementResolution,
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
    AcquisitionCostBasisRecord,
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
    PlannerAcquisitionCostSchedule,
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
    load_planner_acquisition_cost_schedule,
    persist_acquisition_planner_report,
    plan_evidence_acquisition,
    plan_requirement_gap_acquisition,
    produce_acquisition_cost_basis_record,
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
_N7_DISCOVERY_CONTROL_FIELDS = tuple(
    sorted(set(DataDiscoverRequest.model_fields) - set(DataResolveRequest.model_fields))
)


def _install_recorded_file_catalog_supplier(monkeypatch: pytest.MonkeyPatch) -> str:
    """Register the shared recorded-file source used by the real owner fixture."""
    from polisyos.data_forge.domains.catalog.registry import (
        CatalogSourceRegistryEntry,
        CatalogSourceRegistrySpec,
    )
    from polisyos.data_forge.read_api import catalog as catalog_read_api

    source_id = "recorded_file"
    entry = CatalogSourceRegistryEntry(
        source_id=source_id,
        family="controlled_test_fixture",
        wave="T",
        endpoint="file://controlled-test-fixture",
        connector_id="files.tabular",
        execution_tier="transport_ready",
        run_lane="empirical",
        publish_blocking=True,
    )
    registry = CatalogSourceRegistrySpec(sources=(entry,))
    monkeypatch.setattr(catalog_read_api, "load_catalog_source_registry", lambda: registry)
    return source_id


def test_strict_cost_owner_rejects_unknown_default_zero_without_changing_legacy() -> None:
    """DS15-COST-BASIS: legacy fallback is candidate-only, never cost authority."""

    legacy = acquisition_owner._cost_basis_for_gap(
        missing_distribution="unregistered_distribution",
        suggested_experiment=None,
        alternative_identification=None,
    )

    assert legacy["basis_ref"] == "gap-cost-basis:unregistered-distribution:default"
    assert legacy["money_usd"] == 1250.0
    assert (
        produce_acquisition_cost_basis_record(
            missing_distribution="unregistered_distribution",
            strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
        )
        is None
    )


def test_strict_cost_owner_recomputes_schedule_rate_hash_and_total() -> None:
    """DS15-COST-BASIS: declarations stay fixed while decisive values drift."""

    schedule = load_planner_acquisition_cost_schedule()
    record = produce_acquisition_cost_basis_record(
        missing_distribution="administrative_tax_receipts",
        strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
        schedule=schedule,
    )

    assert isinstance(schedule, PlannerAcquisitionCostSchedule)
    assert isinstance(record, AcquisitionCostBasisRecord)
    assert record.total_amount == sum(item.amount for item in record.line_items)
    assert record.total_amount > 0

    schedule_payload = schedule.model_dump(mode="json")
    schedule_payload["rate_basis"]["expert_hour_usd"] += 1.0
    with pytest.raises(ValidationError, match="schedule_content_hash_mismatch"):
        PlannerAcquisitionCostSchedule.model_validate(schedule_payload)

    schedule_payload = schedule.model_dump(mode="json")
    schedule_payload["rate_basis"]["expert_hour_usd"] += 1.0
    schedule_payload["schedule_content_hash"] = _stable_json_hash(
        {key: value for key, value in schedule_payload.items() if key != "schedule_content_hash"}
    )
    drifted_schedule = PlannerAcquisitionCostSchedule.model_validate(schedule_payload)
    with pytest.raises(ValueError, match="cost_schedule_owner_drift"):
        produce_acquisition_cost_basis_record(
            missing_distribution="administrative_tax_receipts",
            strategy=AcquisitionStrategy.PUBLIC_REGISTRY,
            schedule=drifted_schedule,
        )

    schedule_payload = schedule.model_dump(mode="json")
    schedule_payload["rate_basis"] = dict.fromkeys(schedule_payload["rate_basis"], 0.0)
    schedule_payload["schedule_content_hash"] = _stable_json_hash(
        {key: value for key, value in schedule_payload.items() if key != "schedule_content_hash"}
    )
    with pytest.raises(ValidationError, match="schedule_rate_basis_invalid"):
        PlannerAcquisitionCostSchedule.model_validate(schedule_payload)

    schedule_payload = schedule.model_dump(mode="json")
    schedule_payload["schedule_content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="schedule_content_hash_mismatch"):
        PlannerAcquisitionCostSchedule.model_validate(schedule_payload)

    record_payload = record.model_dump(mode="json")
    record_payload["total_amount"] += 1.0
    with pytest.raises(ValidationError, match="cost_basis_total_mismatch"):
        AcquisitionCostBasisRecord.model_validate(record_payload)

    record_payload = record.model_dump(mode="json")
    record_payload["record_content_hash"] = "sha256:" + "0" * 64
    with pytest.raises(ValidationError, match="cost_basis_content_hash_mismatch"):
        AcquisitionCostBasisRecord.model_validate(record_payload)


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
    assert gap.metadata["candidate_binding"]["candidate_id"] == ("candidate_unresolved_lever")
    assert gap.metadata["satisfaction_status"] == "unsatisfied"
    assert report.status == "pass"
    assert len(report.acquisition_records) == 1
    assert report.acquisition_records[0].requirement_gap_ref == (gap.requirement_gap_id)
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
                "architecture/policy_design_case/layer3_gy_n10_cg1_l2_relation_census.json"
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
        lambda payload: payload["metadata"]["requirement"]["alternatives"][0].__setitem__(
            "satisfaction_status", "satisfied"
        ),
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
        coverage_ref=(f"repo://production_data/dataset_catalog.duckdb#variable/{variable_id}"),
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
    payload["metadata"]["availability"]["availability_content_hash"] = "sha256:" + "0" * 64

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
                "repo://production_data/dataset_catalog.duckdb#variable/employment_retention"
            ),
        )


def test_generation_cycle_bootstrap_census_classifies_read_only_entry_comparison() -> None:
    """Only a recomputed entry used as comparison evidence is a read-only check."""

    source = """
def _validate_n7_acq01_registry_binding(registration, persisted_entries):
    expected_entry = build_substrate_registry_entry(registration)
    return len(persisted_entries) == 1 and persisted_entries[0] == expected_entry

def _local_bootstrap(registration):
    return build_substrate_registry_entry(registration)
"""
    witness = contract._generation_cycle_substrate_call_census(
        source,
        source_label="fixture.py",
    )

    assert witness["owner_entry_recomputations"] == ["fixture.py:3:build_substrate_registry_entry"]
    assert witness["production_callers"] == ["fixture.py:7:build_substrate_registry_entry"]


def test_generation_cycle_bootstrap_census_detects_writer_inside_verifier() -> None:
    """Retained verifier markers cannot hide a write of the recomputed entry."""

    source = """
def _validate_n7_acq01_registry_binding(registration, persisted_entries, store):
    expected_entry = build_substrate_registry_entry(registration)
    matches = len(persisted_entries) == 1 and persisted_entries[0] == expected_entry
    return matches
"""
    writer_mutant = source.replace(
        "    return matches\n",
        "    store.put(expected_entry)\n    return matches\n",
    )
    witness = contract._generation_cycle_substrate_call_census(
        writer_mutant,
        source_label="fixture.py",
    )

    assert witness["owner_entry_recomputations"] == []
    assert witness["production_callers"] == ["fixture.py:3:build_substrate_registry_entry"]


def test_generation_cycle_bootstrap_authority_is_strangled() -> None:
    """The N7 checker derives both caller census and fail-closed owner refusal."""

    witness = contract.generation_cycle_substrate_fence(REPO_ROOT)

    assert witness["status"] == "strangled"
    assert witness["production_bootstrap_callers"] == []
    assert witness["owner_entry_recomputations"]
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

    by_family = {record.requirement_family: record for record in report.acquisition_records}
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

    assert by_gap["gap-scholar"].terminal_disposition is (AcquisitionDisposition.ACCEPTED_DEFICIT)
    assert by_gap["gap-scholar"].accepted_deficit_ref == ("accepted_deficit:gap-scholar")
    assert by_gap["gap-scholar"].limitation_ref is None
    assert by_gap["gap-facet"].terminal_disposition is (
        AcquisitionDisposition.PUBLISH_WITH_LIMITATION
    )
    assert by_gap["gap-facet"].limitation_ref == "limitation:gap-facet"
    assert by_gap["gap-facet"].commit_authority == "human_governed_commit_required"
    assert by_gap["gap-snapshot"].terminal_disposition is (AcquisitionDisposition.CLOSEOUT_BLOCK)
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


def _presence_bound_planner_report(shape: str) -> acquisition_owner.AcquisitionPlannerReport:
    report = plan_evidence_acquisition(
        run_id="run-presence-fixture",
        gaps=[
            AcquisitionGap(
                gap_id="gap-presence-fixture",
                gap_type=AcquisitionGapType.METHOD_OBLIGATION,
                claim_ref="claim://presence-fixture",
                authority_level=AuthorityLevel.GOVERNED,
                mandatory_gate_state=MandatoryGateState.NONE,
            )
        ],
        generated_at=datetime(2026, 7, 17, tzinfo=UTC),
    )
    payload = report.model_dump(mode="json")
    row = payload["acquisition_records"][0]
    field = "capability_requirement_resolutions"
    row.pop(field, None)
    if shape == "null":
        row[field] = None
    elif shape == "empty":
        row[field] = []
    elif shape == "nonempty":
        row[field] = [
            {
                "scope_profile_id": "profile:ua-2026",
                "query": {
                    "requirement_id": "data-requirement:profile:ua-2026:firm_survival",
                    "construct": "firm_survival",
                    "entity_scope": "firm",
                    "population_filter": {"type": "msmes"},
                    "geography": "UA",
                    "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
                    "claim_use": "claim_evidence_closeout",
                    "source_family_alias": "production_msme_panel",
                },
                "state": "not_established",
                "binding": None,
                "reason_codes": ["capability_resolver_not_established"],
            }
        ]
    elif shape != "absent":
        raise ValueError("unsupported presence case")
    typed = acquisition_owner.AcquisitionPlannerReport.model_validate(payload)
    return acquisition_owner.bind_acquisition_planner_report(
        typed, planning_context_hash="sha256:" + "1" * 64
    )


@pytest.mark.parametrize("shape", ["absent", "null", "empty", "nonempty"])
def test_n7_planner_report_preserves_full_resolution_presence_in_fresh_cas(
    tmp_path: Path, shape: str
) -> None:
    """The output binding survives actual CAS serialization with distinct presence states."""
    from polisyos.core import canon

    store = FileSystemCAS(tmp_path / "cas")
    report = _presence_bound_planner_report(shape)
    ref = acquisition_owner.persist_and_verify_acquisition_planner_report(store, report)
    fresh = FileSystemCAS(tmp_path / "cas")
    loaded = load_acquisition_planner_report(fresh, ref)
    manifest = fresh.get_manifest(ref)
    assert manifest.canon is not None and manifest.canon.exclude_none is False
    assert acquisition_owner._canonical_model_bytes(
        loaded
    ) == acquisition_owner._canonical_model_bytes(report)
    assert acquisition_owner.acquisition_planner_report_matches_context(
        loaded, planning_context_hash=report.planning_context_hash
    )
    assert (
        acquisition_owner._validate_persisted_planner_report(store=fresh, ref=ref, report=report)
        == ()
    )
    row = canon.from_canonical_bytes(fresh.get_bytes(ref))["acquisition_records"][0]
    field = "capability_requirement_resolutions"
    if shape == "absent":
        assert field not in row
    elif shape == "null":
        assert field in row and row[field] is None
    elif shape == "empty":
        assert row[field] == []
    else:
        assert len(row[field]) == 1
        assert row[field][0]["state"] == "not_established"


def test_n7_planner_old_lossy_profile_refuses_null_collapse_and_restores_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Legacy absence remains readable; lost explicit null cannot be inferred."""
    from polisyos.core import artifacts, canon

    store = FileSystemCAS(tmp_path / "cas")

    def old_writer(store, report):
        return store.put_json(
            report,
            artifacts.PutOptions(
                kind=acquisition_owner.ACQUISITION_PLANNER_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=acquisition_owner.ACQUISITION_PLANNER_SCHEMA_NAME,
                    version=acquisition_owner.ACQUISITION_PLANNER_SCHEMA_VERSION_SHORT,
                ),
                inputs=acquisition_owner.acquisition_report_inputs(report),
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )

    absent = _presence_bound_planner_report("absent")
    old_absent = old_writer(store, absent)
    assert (
        acquisition_owner._validate_persisted_planner_report(
            store=store, ref=old_absent, report=absent
        )
        == ()
    )
    assert acquisition_owner.acquisition_planner_report_matches_context(
        load_acquisition_planner_report(FileSystemCAS(tmp_path / "cas"), old_absent),
        planning_context_hash=absent.planning_context_hash,
    )

    explicit = _presence_bound_planner_report("null")
    old_explicit = old_writer(store, explicit)
    old_bytes = store.get_bytes(old_explicit)
    old_loaded = load_acquisition_planner_report(FileSystemCAS(tmp_path / "cas"), old_explicit)
    assert old_loaded == explicit  # Value equality does not prove wire presence.
    assert (
        "capability_requirement_resolutions"
        not in old_loaded.acquisition_records[0].model_fields_set
    )
    issues = acquisition_owner._validate_persisted_planner_report(
        store=store, ref=old_explicit, report=explicit
    )
    assert {row["code"] for row in issues} >= {
        "acquisition_planner_report_readback_mismatch",
        "acquisition_planner_report_context_binding_missing",
    }
    assert store.get_bytes(old_explicit) == old_bytes

    # Remove the presence-preserving writer while leaving the report and hash
    # markers intact. The actual post-write verifier must refuse, then recover.
    with monkeypatch.context() as local:
        local.setattr(acquisition_owner, "persist_acquisition_planner_report", old_writer)
        with pytest.raises(ValueError, match="acquisition_planner_report_readback_mismatch"):
            acquisition_owner.persist_and_verify_acquisition_planner_report(store, explicit)
    restored_ref = acquisition_owner.persist_and_verify_acquisition_planner_report(store, explicit)
    restored = load_acquisition_planner_report(FileSystemCAS(tmp_path / "cas"), restored_ref)
    assert acquisition_owner.acquisition_planner_report_matches_context(
        restored, planning_context_hash=explicit.planning_context_hash
    )
    assert restored.model_dump(mode="json") == explicit.model_dump(mode="json")

    # Keep report/action IDs and binding markers while changing the actual
    # action quantity. The selected CAS record must not be treated as equal.
    row = explicit.acquisition_records[0]
    changed_row = row.model_copy(update={"claim_ref": row.claim_ref + ":different"})
    changed_report = explicit.model_copy(update={"acquisition_records": (changed_row,)})
    assert {
        issue["code"]
        for issue in acquisition_owner._validate_persisted_planner_report(
            store=store, ref=restored_ref, report=changed_report
        )
    } == {"acquisition_planner_report_readback_mismatch"}
    bad_binding = explicit.model_copy(update={"planning_binding_hash": "sha256:" + "2" * 64})
    bad_binding_ref = persist_acquisition_planner_report(store, bad_binding)
    assert {
        issue["code"]
        for issue in acquisition_owner._validate_persisted_planner_report(
            store=store, ref=bad_binding_ref, report=bad_binding
        )
    } == {"acquisition_planner_report_context_binding_missing"}

    # A malformed typed caller value must return a refusal, not escape as a
    # JSON encoding exception or be normalized into a different report.
    row = explicit.acquisition_records[0]
    assert row.strategy_records
    bad_strategy = row.strategy_records[0].model_copy(update={"voi_expected_cost": float("nan")})
    bad_row = row.model_copy(update={"strategy_records": (bad_strategy, *row.strategy_records[1:])})
    bad_report = explicit.model_copy(update={"acquisition_records": (bad_row,)})
    python_cost = bad_report.model_dump(mode="python")["acquisition_records"][0][
        "strategy_records"
    ][0]["voi_expected_cost"]
    assert isinstance(python_cost, float) and math.isnan(python_cost)
    with pytest.raises(ValueError):
        persist_acquisition_planner_report(store, bad_report)
    assert acquisition_owner._validate_persisted_planner_report(
        store=store, ref=restored_ref, report=bad_report
    ) == ({"code": "acquisition_planner_report_content_invalid"},)
    # The writer's generic Core finite-value property must be exercised, not
    # just its marker: remove the preflight and test the same malformed report.
    with monkeypatch.context() as removed:
        removed.setattr(
            acquisition_owner, "_require_finite_numeric_projection", lambda report: None
        )
        assert (
            acquisition_owner._validate_persisted_planner_report(
                store=store, ref=restored_ref, report=bad_report
            )
            == ()
        )
    assert acquisition_owner._validate_persisted_planner_report(
        store=store, ref=restored_ref, report=bad_report
    ) == ({"code": "acquisition_planner_report_content_invalid"},)
    # Exercise both strategy collections and VOI fields with all non-finite
    # float categories, preserving report/action IDs and binding markers.
    for collection in ("strategy_records", "ineligible_strategy_records"):
        strategies = getattr(row, collection)
        assert strategies
        for field in ("voi_expected_value", "voi_expected_cost"):
            for value in (float("nan"), float("inf"), float("-inf")):
                changed = strategies[0].model_copy(update={field: value})
                changed_row = row.model_copy(update={collection: (changed, *strategies[1:])})
                changed_report = explicit.model_copy(update={"acquisition_records": (changed_row,)})
                assert acquisition_owner._validate_persisted_planner_report(
                    store=FileSystemCAS(tmp_path / "cas"), ref=restored_ref, report=changed_report
                ) == ({"code": "acquisition_planner_report_content_invalid"},)


def test_shared_model_bytes_keep_valid_json_projection_and_refuse_nested_nonfinite_numbers() -> (
    None
):
    """Keep the former JSON bytes while inspecting supported Python containers."""
    artifact = acquisition_owner.AcquisitionOwnerArtifact.from_payload(
        owner_component="fixture.owner",
        requirement_ref="fixture:requirement",
        artifact_ref="fixture:artifact",
        payload={"_type": "ordinary_fixture_data", "path": Path("fixture/input")},
        cost_usd=0.0,
        quality={
            "finite_values": {0.25, 0.75},
            "large_decimal": Decimal("1e10000"),
            "finite_complex": complex(1.0, 2.0),
            "huge_integer": 10**500,
        },
        rights={},
        binding_refs=(),
        journal_ref="fixture:journal",
    )
    expected = json.dumps(
        artifact.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    assert acquisition_owner._canonical_model_bytes(artifact) == expected
    invalid = (
        {"nested": [float("nan")]},
        {"nested": (float("inf"),)},
        {"nested": {float("-inf")}},
        {float("nan"): "key"},
        {"nested": frozenset({float("inf")})},
        {"nested": [Decimal("NaN"), Decimal("Infinity")]},
        {"nested": Decimal("sNaN")},
        {Decimal("NaN"): "key"},
        {"nested": complex(float("nan"), 0.0)},
        {"nested": complex(0.0, float("inf"))},
    )
    for value in invalid:
        changed = artifact.model_copy(update={"quality": value})
        with pytest.raises(
            acquisition_owner.AcquisitionPlannerBindingError,
            match="acquisition_model_nonfinite_numeric",
        ):
            acquisition_owner._canonical_model_bytes(changed)
    huge_fraction = artifact.model_copy(update={"quality": {"value": Fraction(10**500, 1)}})
    acquisition_owner._require_finite_numeric_projection(huge_fraction)


def test_n7_decimal_collision_must_not_preserve_actual_receipt_seal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falsify a string-to-nonfinite-Decimal collision on a real emitted receipt."""
    spec = _compiled_requirement_specs()[0]
    artifact = _captured_owner_artifact(
        owner_component="fabric.ingestion",
        requirement_ref=spec.requirement_id,
        artifact_ref="fabric://recorded/decimal-collision",
        acquired_family="production_msme_panel",
        source_id="fabric.production_msme_panel",
        candidate_id="design:credit",
        cost_usd=11.25,
    )
    artifact.quality["fixture_decimal_probe"] = "NaN"
    inputs = {
        "run_id": "run-n7-decimal-collision",
        "acquisition_request": {"cycle_index": 1},
        "data_requirement_specs": (spec,),
        "world_snapshot": AcquisitionWorldSnapshot(
            world_ref="world://before/decimal-collision",
            known_slots=("production_msme_panel",),
            substrate_registry=_substrate_registry().model_dump(mode="json"),
        ),
        "owner_gateway": RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={spec.requirement_id: artifact}
        ),
    }
    receipt = run_acquisition_closed_loop(**inputs)
    assert acquisition_owner.acquisition_receipt_has_verified_emission(receipt)
    emitted = receipt.owner_artifacts[0]
    assert emitted is artifact
    assert emitted.quality["fixture_decimal_probe"] == "NaN"
    refs = (receipt.content_hash, emitted.artifact_ref, emitted.content_hash)
    emitted.quality["fixture_decimal_probe"] = Decimal("NaN")
    assert refs == (receipt.content_hash, emitted.artifact_ref, emitted.content_hash)
    assert (
        receipt.model_dump(mode="json")["owner_artifacts"][0]["quality"]["fixture_decimal_probe"]
        == "NaN"
    )
    assert not acquisition_owner.acquisition_receipt_has_verified_emission(receipt)
    with pytest.raises(
        acquisition_owner.AcquisitionPlannerBindingError,
        match="acquisition_model_nonfinite_numeric",
    ):
        run_acquisition_closed_loop(**inputs)
    with monkeypatch.context() as removed:
        removed.setattr(acquisition_owner, "_require_finite_numeric_projection", lambda model: None)
        assert acquisition_owner.acquisition_receipt_has_verified_emission(receipt)
    assert not acquisition_owner.acquisition_receipt_has_verified_emission(receipt)
    emitted.quality["fixture_decimal_probe"] = "NaN"
    assert acquisition_owner.acquisition_receipt_has_verified_emission(receipt)


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
    assert set(receipt.grown_world_added_slots) == {"production_msme_panel"}
    assert {outcome.status for outcome in receipt.world_write_outcomes} == {"written", "rejected"}
    assert receipt.real_grounding_result_count == 0
    assert receipt.status == "completed_no_results"
    assert receipt.useful_design_rate_after == receipt.useful_design_rate_before
    rederivations = {row.design_id: row for row in receipt.grounding_rederivations}
    assert rederivations["design:credit"].status == "grounding_unavailable"
    assert rederivations["design:credit"].issue_codes == (
        "generation_result_problem_scope_unestablished",
    )
    assert rederivations["design:portfolio"].issue_codes == (
        "candidate_binding_missing_after_world_write",
    )
    assert set(receipt.affected_region.design_ids) == {
        "design:credit",
        "design:portfolio",
    }
    assert set(receipt.affected_region.rederived_design_ids) == set(
        receipt.affected_region.design_ids
    )
    assert {entry.sequence for entry in receipt.journal_entries} == {1, 2}
    assert any(
        issue["code"] == "acquisition_artifact_not_captured_from_owner"
        for issue in validate_acquisition_receipt(receipt)
    )

    clock_shifted_payload = receipt.model_dump(mode="json")
    clock_shifted_payload.pop("content_hash")
    clock_shifted_payload["generated_at"] = (
        receipt.generated_at + timedelta(seconds=1)
    ).isoformat()
    clock_shifted_payload["planner_report"]["generated_at"] = (
        receipt.planner_report.generated_at + timedelta(seconds=1)
    ).isoformat()
    clock_shifted = type(receipt).model_validate(clock_shifted_payload)
    assert clock_shifted.content_hash == receipt.content_hash

    semantic_change_payload = receipt.model_dump(mode="json")
    semantic_change_payload.pop("content_hash")
    semantic_change_payload["cost_summary_usd"] += 1.0
    semantic_change = type(receipt).model_validate(semantic_change_payload)
    assert semantic_change.content_hash != receipt.content_hash


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


def test_real_skg_capture_requires_source_bound_replay_before_audit_emission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.core import artifacts, canon
    from polisyos.runtime.quality.production_grounding_calibration import (
        _SOURCE_CANON,
        ProductionCG2CalibrationSource,
    )

    original = ProductionCG2CalibrationSource.produce

    def tampered_produce(self, request):
        ref = original(self, request)
        payload = canon.from_canonical_bytes(self._store.get_bytes(ref))
        # Leave purpose/status/provenance markers intact; substitute actual request bytes.
        payload["request"]["claim_ref"] = "claim:borrowed"
        return self._store.put_json(
            payload,
            artifacts.ArtifactWriteOptions(
                kind="runtime.production_grounding_source_resolution",
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name="runtime.production_grounding_source_resolution", version="1.0"
                ),
                producer=artifacts.ProducerInfo(component="candidate", version="1.0"),
            ),
            canon_spec=_SOURCE_CANON,
            return_selected_profile=True,
        )

    monkeypatch.setattr(ProductionCG2CalibrationSource, "produce", tampered_produce)
    gap = value_input_world_knowledge_requirement_gap(claim_ref="claim:actual")
    with pytest.raises(ValueError, match="production_grounding_source_replay_mismatch"):
        run_acquisition_closed_loop(
            run_id="n7-source-replay-tamper",
            acquisition_request={"cycle_index": 1},
            data_requirement_specs=(gap,),
            world_snapshot=AcquisitionWorldSnapshot(world_ref="world:actual"),
            owner_gateway=RealAcquisitionOwnerGateway(
                repo_root=tmp_path,
                artifact_store=FileSystemCAS(tmp_path / "n7-test-owner-cas"),
            ),
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
    assert receipt.grown_world_added_slots == ()
    assert receipt.grown_world_after_ref == world.world_ref
    assert receipt.world_write_outcomes[0].reason == "owner_response_no_substrate_registrations"
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


def test_real_owner_gateway_records_local_skg_response_without_network(tmp_path: Path) -> None:
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
        repo_root=tmp_path,
        artifact_store=FileSystemCAS(tmp_path / "n7-test-owner-cas"),
        captured_at=datetime(2026, 7, 5, tzinfo=UTC),
    )

    artifact = gateway.acquire(
        record=report.acquisition_records[0],
        compiled_requirement_spec=base_spec,
    )

    assert artifact is not None
    assert artifact.owner_component == "data_forge.skg"
    assert artifact.capture_provenance is not None
    assert (
        artifact.capture_provenance.owner_endpoint
        == "ProductionCG2CalibrationSource.produce/replay"
    )
    assert artifact.capture_provenance.network_call is False
    assert gateway.network_counter.network_calls == 0
    assert (
        artifact.payload["owner_response"]["owner_response_kind"]
        == "skg_exact_request_source_resolution"
    )
    resolution = artifact.payload["owner_response"]["resolution"]
    assert resolution["source_population"] is None
    assert "source_snapshot_unavailable" in resolution["refusal_reasons"]
    assert resolution["n8_admission"] == "blocked"
    assert artifact.payload.get("grounding_results") is None
    assert artifact.payload["acquired_substrate_registrations"] == []
    assert artifact.payload["candidate_bindings"] == []


def test_skg_source_capture_replays_exact_current_request_and_cannot_write_world(
    tmp_path: Path,
) -> None:
    import duckdb

    from polisyos.data_forge.read_api import academic

    path = tmp_path / "source.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE ac_skg_simulation_parameters AS SELECT 'n' || i numeric_id, "
            "'W1' openalex_id, 'avg_income' canonical_name, '[\"c1\"]' linked_claim_ids_json, "
            "'[\"e1\"]' linked_edges_json FROM range(30) t(i)"
        )
    source = academic.SourceSnapshot(
        path=path,
        reference="fixture://n7-source",
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    problem = _acquisition_design_problem()
    payload = problem.model_dump(mode="json")
    payload["outcome_of_interest"] = {
        "target_variable": "avg_income",
        "metric_id": "avg_income",
        "estimand": "average_treatment_effect",
        "direction": "maximize",
    }
    problem = DesignProblem.model_validate(payload)
    gap = value_input_world_knowledge_requirement_gap(claim_ref="claim:avg_income")
    from polisyos.runtime.quality.generation_cycle import GenerationCycleController

    controller = GenerationCycleController(repo_root=tmp_path)
    specs = controller._n7_data_requirement_specs(
        problem, acquisition_request={"requirement_gap": gap.model_dump(mode="json")}
    )
    assert len(specs) == 1
    assert specs[0].model_dump(mode="json") == gap.model_dump(mode="json")
    world = AcquisitionWorldSnapshot(world_ref="world:request-current", known_slots=("avg_income",))
    receipt = run_acquisition_closed_loop(
        run_id="n7-source-refusal",
        acquisition_request={"cycle_index": 1},
        data_requirement_specs=specs,
        world_snapshot=world,
        design_problem=problem,
        owner_gateway=RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            artifact_store=FileSystemCAS(tmp_path / "n7-test-owner-cas"),
            skg_source_snapshot=source,
        ),
    )
    assert len(receipt.owner_artifacts) == 1
    resolution = receipt.owner_artifacts[0].payload["owner_response"]["resolution"]
    assert resolution["request"]["design_problem"] == problem.model_dump(mode="json")
    assert resolution["request"]["world_snapshot"] == world.model_dump(mode="json")
    assert resolution["request"]["compiled_requirement"] == gap.model_dump(mode="json")
    assert resolution["source_population"]["row_count"] == 30
    assert resolution["target_variable"] == "avg_income"
    assert resolution["cg2_status"] == "cold_start"
    assert all(row.status == "no_result" for row in receipt.world_write_outcomes)
    assert receipt.grounding_rederivations == ()
    assert receipt.real_grounding_result_count == 0
    assert validate_acquisition_receipt(receipt) == ()


@pytest.mark.parametrize(
    "response_kind", ["skg_exact_request_source_resolution", "skg_local_schema_probe", "alternate"]
)
@pytest.mark.parametrize(
    "projection", ["acquired_substrate_registrations", "candidate_bindings", "grounding_results"]
)
def test_every_skg_intake_rejects_acquired_projection_even_with_valid_markers(
    tmp_path: Path, response_kind: str, projection: str
) -> None:
    spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    spec["required_method_families"] = ["causal_prior"]
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(spec,))[0]
    record = plan_requirement_gap_acquisition(
        run_id="skg-forgery", requirement_gaps=(gap,)
    ).acquisition_records[0]
    artifact = RealAcquisitionOwnerGateway(
        repo_root=tmp_path,
        artifact_store=FileSystemCAS(tmp_path / "n7-test-owner-cas"),
    ).acquire(record=record, compiled_requirement_spec=spec)
    payload = json.loads(json.dumps(artifact.payload))
    payload["owner_response"]["owner_response_kind"] = response_kind
    payload[projection] = [{"candidate": "self-issued"}]
    payload["raw_owner_response_hash"] = acquisition_owner._stable_content_hash(
        payload["owner_response"]
    )
    forged = acquisition_owner._artifact_from_owner_response(
        owner_component="data_forge.skg",
        owner_endpoint="ProductionCG2CalibrationSource.produce/replay",
        record=record,
        spec=spec,
        payload=payload,
        captured_at=datetime(2026, 7, 5, tzinfo=UTC),
        network_call=False,
        cost_usd=0.0,
    )
    receipt = run_acquisition_closed_loop(
        run_id="skg-forgery-replay",
        acquisition_request={"cycle_index": 1},
        data_requirement_specs=(spec,),
        world_snapshot=AcquisitionWorldSnapshot(world_ref="world:current"),
        owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={forged.requirement_ref: forged}
        ),
    )
    assert all(row.status == "rejected" for row in receipt.world_write_outcomes)


@pytest.mark.parametrize(
    ("scope_profile_id", "geography", "start", "end"),
    [
        ("scope-profile:8f1a", "UA", "2026-01-01", "2026-12-31"),
        ("scope-profile:c3d4", "PL", "2027-01-01", "2027-12-31"),
    ],
)
def test_real_owner_gateway_captures_catalog_plans_without_explore_or_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scope_profile_id: str,
    geography: str,
    start: str,
    end: str,
) -> None:
    from polisyos.core.contracts.control import FetchPlan, MetricCandidate
    from polisyos.data_forge.read_api.catalog import build_slice0_fixture_catalog_graph
    from polisyos.fabric.retrieval.executor import FetchExecutor
    from polisyos.fabric.retrieval.service import RetrievalService
    from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths

    fixture_graph = build_slice0_fixture_catalog_graph(tmp_path / "fixture-catalog")

    class _OwnedFixtureGraph:
        def __init__(self) -> None:
            self.closed = False

        def resolve_metric_bindings(self, metric_name: str, *, top_k: int = 20):
            assert not self.closed
            return fixture_graph.resolve_metric_bindings(metric_name, top_k=top_k)

        def close(self) -> None:
            self.closed = True
            fixture_graph.close()

    owned_graph = _OwnedFixtureGraph()
    opened_paths: list[tuple[Path, Path]] = []

    def _catalog_factory(db_path: Path, index_dir: Path) -> object:
        opened_paths.append((db_path, index_dir))
        return owned_graph

    def _unexpected_call(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("catalog plan capture must not explore or execute")

    monkeypatch.setattr(RetrievalService, "discover", _unexpected_call)
    monkeypatch.setattr(FetchExecutor, "preview", _unexpected_call)
    monkeypatch.setattr(FetchExecutor, "execute", _unexpected_call)

    base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    base_spec["requirement_id"] = f"opaque:catalog-plan-capture:{scope_profile_id}"
    base_spec["claim_id"] = f"opaque:claim:{scope_profile_id}"
    base_spec["required_data_families"] = (
        "msme_credit_access",
        "fixture_unresolved_metric",
    )
    base_spec["scope"].update(
        {
            "geography": geography,
            "jurisdiction": geography,
        }
    )
    base_spec["metadata"]["scope_profile"] = {
        "profile_id": scope_profile_id,
        "jurisdiction": geography,
        "time_window": {"start": start, "end": end},
        "time_role": "observation_time",
        "granularity": "firm-year",
        "required_constructs": [],
        "candidate_construct_proposals": [],
    }
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
    report = plan_requirement_gap_acquisition(
        run_id="run-n7-catalog-plan-capture",
        requirement_gaps=(gap,),
        generated_at=datetime(2026, 7, 17, tzinfo=UTC),
    )
    gateway = RealAcquisitionOwnerGateway(
        repo_root=tmp_path,
        dataset_catalog_factory=_catalog_factory,
        catalog_run_profile="prod_full",
        captured_at=datetime(2026, 7, 17, tzinfo=UTC),
    )

    artifact = gateway.acquire(
        record=report.acquisition_records[0],
        compiled_requirement_spec=base_spec,
    )

    assert artifact is not None
    raw_response = artifact.payload["owner_response"]
    assert raw_response["owner_response_kind"] == "fabric_catalog_resolution"
    assert raw_response["families"] == [
        "msme_credit_access",
        "fixture_unresolved_metric",
    ]
    assert raw_response["fetch_plan_count"] == len(raw_response["fetch_plans"])
    assert raw_response["candidate_count"] == len(raw_response["candidates"])
    assert raw_response["candidate_only"] is True
    assert raw_response["requirement_projection"]["disposition"] == "candidate_only"
    assert (
        raw_response["requirement_projection"]["capability_resolution_status"] == "not_established"
    )
    assert raw_response["data_needs"][0]["geography"] == geography
    assert raw_response["data_needs"][0]["time_start"] == start
    assert raw_response["data_needs"][0]["time_end"] == end
    assert raw_response["data_needs"][0]["granularity"] == "firm-year"
    assert raw_response["data_needs"][0]["quality_min"] == 0.8
    for raw_plan in raw_response["fetch_plans"]:
        plan = FetchPlan.model_validate(raw_plan)
        assert raw_plan == plan.model_dump(mode="json")
        assert plan.source_lane == "catalog"
        assert plan.quality_min == 0.8
        assert plan.metadata["execution_tier"] in {"fetchable", "transport_ready"}
    for raw_candidate in raw_response["candidates"]:
        candidate = MetricCandidate.model_validate(raw_candidate)
        assert raw_candidate == candidate.model_dump(mode="json")
    assert artifact.payload["acquired_substrate_registrations"] == []
    assert artifact.payload["candidate_bindings"] == []
    assert gateway.network_counter.network_calls == 0
    assert not (tmp_path / ".n7-live-cas").exists()

    canonical_path = default_substrate_catalog_paths(tmp_path).l1_dcat_path
    assert opened_paths == [(canonical_path, canonical_path.parent)]
    assert owned_graph.closed is True
    receipt = run_acquisition_closed_loop(
        run_id="run-n7-catalog-plan-no-world-growth",
        acquisition_request={
            "request_kind": "owner_grounding_evidence",
            "driver": "missing_supporting_data",
            "cycle_index": 1,
        },
        data_requirement_specs=(base_spec,),
        world_snapshot=AcquisitionWorldSnapshot(world_ref="world://before/catalog-plan"),
        owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={base_spec["requirement_id"]: artifact}
        ),
        generated_at=datetime(2026, 7, 17, tzinfo=UTC),
    )

    assert receipt.status == "completed_no_results"


@pytest.mark.parametrize(
    ("catalog_context", "reason_code"),
    [
        (
            {"budget_fields": {"cost_budget_usd": 0}, "availability_fields": {}},
            "catalog_zero_budget_unrepresentable",
        ),
        (
            {"budget_fields": {}, "availability_fields": {"availability_filters": []}},
            "catalog_availability_filter_unrepresentable",
        ),
    ],
)
def test_real_owner_gateway_refuses_unrepresentable_budget_or_availability_before_catalog(
    tmp_path: Path,
    catalog_context: dict[str, object],
    reason_code: str,
) -> None:
    calls: list[str] = []

    def forbidden_catalog_factory(_db_path: Path, _index_dir: Path) -> object:
        calls.append("catalog_opened")
        raise AssertionError("a refused requirement must not open the Catalog")

    base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    base_spec["requirement_id"] = f"data-requirement:projection-refusal:{reason_code}"
    base_spec["scope"]["geography"] = "UA"
    base_spec["scope"]["jurisdiction"] = "UA"
    base_spec["metadata"]["scope_profile"] = {
        "profile_id": "fixture:ua:2026",
        "jurisdiction": "UA",
        "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
        "time_role": "observation_time",
        "granularity": "annual",
        "required_constructs": [],
        "candidate_construct_proposals": [],
    }
    base_spec["catalog_request_context"] = catalog_context
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
    report = plan_requirement_gap_acquisition(
        run_id=f"run-projection-refusal-{reason_code}",
        requirement_gaps=(gap,),
        generated_at=datetime(2026, 7, 17, tzinfo=UTC),
    )
    gateway = RealAcquisitionOwnerGateway(
        repo_root=tmp_path,
        dataset_catalog_factory=forbidden_catalog_factory,
        catalog_run_profile="prod_full",
        captured_at=datetime(2026, 7, 17, tzinfo=UTC),
    )

    artifact = gateway.acquire(
        record=report.acquisition_records[0],
        compiled_requirement_spec=base_spec,
    )

    assert artifact is not None
    raw_response = artifact.payload["owner_response"]
    assert raw_response["owner_response_kind"] == "fabric_requirement_projection_refusal"
    assert raw_response["requirement_projection"]["reason_codes"] == [reason_code]
    assert artifact.payload["acquired_substrate_registrations"] == []
    assert artifact.payload["candidate_bindings"] == []
    assert calls == []


def test_n7_request_context_covers_all_declared_discovery_controls() -> None:
    request = dict.fromkeys(_N7_DISCOVERY_CONTROL_FIELDS, None)

    context = acquisition_owner._n7_catalog_request_context(request)

    assert context["budget_fields"] == request
    assert context["availability_fields"] == {}


def _assert_resolution_presence_round_trips(
    model: BaseModel, resolution: CapabilityRequirementResolution
) -> None:
    field = "capability_requirement_resolutions"
    model_type = type(model)
    present_payload = model.model_dump(mode="json")
    expected_resolution = resolution.model_dump(mode="json")
    assert present_payload[field] == [expected_resolution]

    absent_payload = present_payload.copy()
    absent_payload.pop(field)
    absent_payload.pop("content_hash", None)
    absent = model_type.model_validate(absent_payload)
    assert field not in absent.model_fields_set
    assert field not in absent.model_dump(mode="json")

    explicit_null_payload = absent.model_dump(mode="json")
    explicit_null_payload[field] = None
    explicit_null_payload.pop("content_hash", None)
    explicit_null = model_type.model_validate(explicit_null_payload)
    assert field in explicit_null.model_fields_set
    assert explicit_null.model_dump(mode="json")[field] is None

    non_null_payload = absent.model_dump(mode="json")
    non_null_payload[field] = [expected_resolution]
    non_null_payload.pop("content_hash", None)
    non_null = model_type.model_validate(non_null_payload)
    assert field in non_null.model_fields_set
    assert non_null.model_dump(mode="json")[field] == [expected_resolution]


def _assert_resolution_presence_schema(carrier: BaseModel) -> None:
    model_type = type(carrier)
    expected_properties = set(model_type.model_fields)
    expected_required = {
        name for name, field in model_type.model_fields.items() if field.is_required()
    }

    def schema_nodes(value: object) -> list[dict[str, object]]:
        if isinstance(value, dict):
            nodes = [value]
            for child in value.values():
                nodes.extend(schema_nodes(child))
            return nodes
        if isinstance(value, list):
            return [node for child in value for node in schema_nodes(child)]
        return []

    for mode in ("validation", "serialization"):
        schema = model_type.model_json_schema(mode=mode)
        properties = schema.get("properties", {})
        assert set(properties) == expected_properties
        assert set(schema.get("required", ())) == expected_required

        resolution_schema = properties["capability_requirement_resolutions"]
        assert "default" in resolution_schema
        assert resolution_schema["default"] is None
        nodes = schema_nodes(resolution_schema)
        assert any(node.get("type") == "null" for node in nodes)
        array_nodes = [node for node in nodes if node.get("type") == "array"]
        assert array_nodes
        item_refs = [
            node["$ref"] for node in schema_nodes(array_nodes[0].get("items", {})) if "$ref" in node
        ]
        assert item_refs
        definitions = schema.get("$defs", {})
        assert all(ref.rsplit("/", 1)[-1] in definitions for ref in item_refs)


def test_n7_closed_loop_forwards_typed_resolution_and_request_limits_to_fabric_owner() -> None:
    spec = _compiled_requirement_specs()[0]
    resolution = CapabilityRequirementResolution.model_validate(
        {
            "scope_profile_id": "profile:ua-2026",
            "query": {
                "requirement_id": "data-requirement:profile:ua-2026:firm_survival",
                "construct": "firm_survival",
                "entity_scope": "firm",
                "population_filter": {"type": "msmes"},
                "geography": "UA",
                "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
                "claim_use": "claim_evidence_closeout",
                "source_family_alias": "production_msme_panel",
            },
            "state": "not_established",
            "binding": None,
            "reason_codes": ["capability_resolver_not_established"],
        }
    )

    class _RecordingGateway:
        def __init__(self) -> None:
            self.spec: dict[str, object] | None = None

        def acquire(
            self,
            *,
            record: object,
            compiled_requirement_spec: dict[str, object],
        ) -> None:
            del record
            self.spec = dict(compiled_requirement_spec)
            return None

    gateway = _RecordingGateway()
    receipt = run_acquisition_closed_loop(
        run_id="run-n7-forward-scope-context",
        acquisition_request={
            "cycle_index": 1,
            "cost_budget_usd": 0,
            "availability_filters": [],
        },
        data_requirement_specs=(spec,),
        capability_requirement_resolutions=(resolution,),
        world_snapshot=AcquisitionWorldSnapshot(world_ref="world://n7-forward-scope"),
        owner_gateway=gateway,  # type: ignore[arg-type]
        generated_at=datetime(2026, 7, 17, tzinfo=UTC),
    )

    assert gateway.spec is not None
    assert gateway.spec["capability_requirement_resolutions"] == [
        resolution.model_dump(mode="json")
    ]
    requirement_gap = requirement_gaps_from_compiled_specs(
        data_requirement_specs=(spec,),
        capability_requirement_resolutions=(resolution,),
    )[0]
    acquisition_gap = requirement_gap.to_acquisition_gap()
    action_record = receipt.planner_report.acquisition_records[0]
    for carrier in (requirement_gap, acquisition_gap, action_record, receipt):
        _assert_resolution_presence_round_trips(carrier, resolution)
        _assert_resolution_presence_schema(carrier)
    assert gateway.spec["catalog_request_context"] == {
        "budget_fields": {"cost_budget_usd": 0},
        "availability_fields": {"availability_filters": []},
    }


@pytest.mark.parametrize(
    ("request_field", "request_value", "reason_code"),
    [
        *[
            (field, None, "catalog_budget_unrepresentable")
            for field in _N7_DISCOVERY_CONTROL_FIELDS
        ],
        ("time_budget_ms", 100, "catalog_budget_unrepresentable"),
        ("time_budget_ms", 0, "catalog_zero_budget_unrepresentable"),
        ("cost_budget_usd", 0, "catalog_zero_budget_unrepresentable"),
        ("availability_filters", [], "catalog_availability_filter_unrepresentable"),
    ],
)
def test_n7_closed_loop_limit_reaches_real_catalog_projection_before_catalog_open(
    tmp_path: Path,
    request_field: str,
    request_value: object,
    reason_code: str,
) -> None:
    catalog_calls: list[str] = []

    def forbidden_catalog_factory(_db_path: Path, _index_dir: Path) -> object:
        catalog_calls.append("opened")
        raise AssertionError("unrepresentable request limits must refuse before Catalog")

    spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    spec["scope"].update({"geography": "UA", "jurisdiction": "UA"})
    spec["metadata"]["scope_profile"] = {
        "profile_id": "scope-profile:ua-2026",
        "jurisdiction": "UA",
        "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
        "time_role": "observation_time",
        "granularity": "annual",
        "required_constructs": [],
        "candidate_construct_proposals": [],
    }
    gateway = RealAcquisitionOwnerGateway(
        repo_root=tmp_path,
        dataset_catalog_factory=forbidden_catalog_factory,
        catalog_run_profile="prod_full",
    )
    request = {"cycle_index": 1, request_field: request_value}

    receipt = run_acquisition_closed_loop(
        run_id=f"run-n7-limit-{request_field}",
        acquisition_request=request,
        data_requirement_specs=(spec,),
        world_snapshot=AcquisitionWorldSnapshot(world_ref="world://n7-limit"),
        owner_gateway=gateway,
        generated_at=datetime(2026, 7, 17, tzinfo=UTC),
    )

    assert len(receipt.owner_artifacts) == 1
    response = receipt.owner_artifacts[0].payload["owner_response"]
    assert response["owner_response_kind"] == "fabric_requirement_projection_refusal"
    assert response["requirement_projection"]["reason_codes"] == [reason_code]
    assert response["requirement_projection"]["authority_status"] == "not_established"
    assert receipt.owner_artifacts[0].payload["acquired_substrate_registrations"] == []
    assert receipt.owner_artifacts[0].payload["candidate_bindings"] == []
    assert receipt.grown_world_before_ref == receipt.grown_world_after_ref
    assert catalog_calls == []


@pytest.mark.parametrize(
    ("source_id", "connector_id", "expected_code"),
    [
        ("", "files.tabular", "catalog_source_identity_unresolved"),
        ("unregistered_fixture", "files.tabular", "catalog_source_unregistered"),
        (
            "recorded_file",
            "worldbank.wdi",
            "catalog_source_connector_mismatch",
        ),
    ],
)
def test_catalog_binding_must_join_registered_source_and_connector(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_id: str,
    connector_id: str,
    expected_code: str,
) -> None:
    """Missing, unknown, or cross-connector source identities refuse before planning."""
    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionError,
    )
    from polisyos.data_forge.domains.catalog.knowledge.types import MetricBindingMatch
    from polisyos.fabric.retrieval.service import RetrievalService

    _install_recorded_file_catalog_supplier(monkeypatch)

    class _SuppliedBindingCatalog:
        def resolve_metric_bindings(self, metric_name: str, *, top_k: int = 20):
            if metric_name != "metric.test":
                return []
            return [
                MetricBindingMatch(
                    metric_id=metric_name,
                    catalog_dataset_id="catalog-recorded-fixture",
                    connector_id=connector_id,
                    request_dataset_id="recorded.csv",
                    execution_tier="transport_ready",
                    source=source_id,
                    title="Controlled recorded fixture",
                )
            ]

    service = RetrievalService(
        curated_dir=tmp_path / "curated",
        dataset_catalog=_SuppliedBindingCatalog(),
    )
    request = DataResolveRequest(
        data_needs=[DataNeed(metric="metric.test", purpose="catalog identity control")],
        mode="hybrid",
        allow_explore_fallback=False,
    )

    with pytest.raises(CatalogSelectionError) as refusal:
        service.resolve(request, run_profile="prod_full")

    assert refusal.value.code == expected_code


def test_real_owner_gateway_refuses_catalog_route_without_selected_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent caller selection stays typed-unresolved instead of defaulting to production."""
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionError,
    )
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path, canonicalize_catalog_source=True, publish_current_catalog=True
    ) as owner:
        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:catalog-profile-unselected",
                "claim_id": "claim-catalog-profile-unselected",
                "required_data_families": ("metric.test",),
            }
        )
        base_spec["metadata"]["scope_profile"] = _catalog_capture_scope_profile()
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-n7-catalog-profile-unselected",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
        )

        with pytest.raises(CatalogSelectionError) as refusal:
            gateway.acquire(
                record=report.acquisition_records[0],
                compiled_requirement_spec=base_spec,
            )

    assert refusal.value.code == "catalog_run_profile_unresolved"


def test_real_owner_gateway_rejects_malformed_catalog_run_profile() -> None:
    from typing import cast

    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionError,
    )
    from polisyos.data_forge.domains.catalog.selection import CatalogRunProfile

    with pytest.raises(CatalogSelectionError) as refusal:
        RealAcquisitionOwnerGateway(
            repo_root=Path.cwd(),
            catalog_run_profile=cast("CatalogRunProfile", "not-a-catalog-run-profile"),
        )

    assert refusal.value.code == "unsupported_run_profile"


@pytest.mark.parametrize(
    ("case", "accepted", "allow_relative"),
    [
        ("file_uri_inside", True, False),
        ("relative_catalog_inside", True, True),
        ("relative_effective_inside", False, False),
        ("absolute_outside", False, False),
        ("symlink_escape", False, False),
        ("remote_scheme", False, False),
        ("non_file_scheme", False, False),
    ],
)
def test_local_fabric_capture_path_boundary_matrix(
    tmp_path: Path,
    case: str,
    accepted: bool,
    allow_relative: bool,
) -> None:
    from polisyos.fabric.retrieval.service import _capture_locator_view

    approved_root = tmp_path / "approved"
    approved_root.mkdir()
    inside = approved_root / "inside.csv"
    inside.write_text("value\n1\n", encoding="utf-8")
    outside = tmp_path / "outside.csv"
    outside.write_text("value\n2\n", encoding="utf-8")
    symlink = approved_root / "escape.csv"
    if case == "symlink_escape":
        try:
            symlink.symlink_to(outside)
        except OSError as exc:
            pytest.skip(f"symlinks unavailable: {exc}")

    locator = {
        "file_uri_inside": inside.as_uri(),
        "relative_catalog_inside": "inside.csv",
        "relative_effective_inside": "inside.csv",
        "absolute_outside": str(outside),
        "symlink_escape": str(symlink),
        "remote_scheme": "https://remote.invalid/inside.csv",
        "non_file_scheme": "s3://bucket/inside.csv",
    }[case]
    locator_view = _capture_locator_view(locator)
    if accepted:
        assert (
            acquisition_owner._resolve_local_fabric_capture_path(
                locator_view, approved_root=approved_root, allow_relative=allow_relative
            )
            == inside.resolve()
        )
    else:
        with pytest.raises(ValueError, match="fabric_fetch_capture_"):
            acquisition_owner._resolve_local_fabric_capture_path(
                locator_view, approved_root=approved_root, allow_relative=allow_relative
            )


def test_real_owner_gateway_capture_requires_runtime_store_before_factory_or_catalog(
    tmp_path: Path,
) -> None:
    """An injected service cannot supply the gateway's missing custody owner."""

    foreign_store = FileSystemCAS(tmp_path / "foreign-cas")
    factory_calls: list[object] = []
    catalog_calls: list[object] = []
    resolve_calls: list[object] = []
    execute_calls: list[object] = []

    class _InjectedService:
        artifact_store = foreign_store

        def resolve(self, request: object, *, run_profile: str) -> object:
            resolve_calls.append((request, run_profile))
            raise AssertionError("capture must stop before service resolution")

        def execute_fetch_plans(self, *args: object, **kwargs: object) -> object:
            execute_calls.append((args, kwargs))
            raise AssertionError("capture must stop before fetch execution")

    def _service_factory(*args: object) -> object:
        factory_calls.append(args)
        return _InjectedService()

    def _catalog_factory(*args: object) -> object:
        catalog_calls.append(args)
        raise AssertionError("capture must stop before catalog construction")

    base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    base_spec.update(
        {
            "requirement_id": "data-requirement:fetch-capture-missing-runtime-store",
            "claim_id": "claim-fetch-capture-missing-runtime-store",
            "required_data_families": ("metric.test",),
            "metadata": {
                "fabric_capture_mode": "persisted_payload",
                "scope_profile": _catalog_capture_scope_profile(),
            },
        }
    )
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
    report = plan_requirement_gap_acquisition(
        run_id="run-n7-fetch-capture-missing-runtime-store",
        requirement_gaps=(gap,),
        generated_at=datetime(2026, 7, 17, tzinfo=UTC),
    )
    gateway = RealAcquisitionOwnerGateway(
        repo_root=tmp_path,
        dataset_catalog_factory=_catalog_factory,
        retrieval_service_factory=_service_factory,
    )

    assert (
        gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )
        is None
    )
    assert factory_calls == []
    assert catalog_calls == []
    assert resolve_calls == []
    assert execute_calls == []
    assert foreign_store.iter_artifact_ids() == []


def test_real_owner_gateway_capture_rejects_injected_foreign_store_before_resolve(
    tmp_path: Path,
) -> None:
    """The factory must preserve the exact runtime store supplied by the caller."""

    from polisyos.runtime.http.resilience import guard_runtime_cas
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = guard_runtime_cas(
        FileSystemCAS(tmp_path / "runtime-cas").for_tenant("tenant-n7", cell_id="cell-a")
    )
    foreign_store = FileSystemCAS(tmp_path / "foreign-cas").for_tenant(
        "tenant-other", cell_id="cell-a"
    )
    factory_store_args: list[object] = []
    resolve_calls: list[object] = []
    execute_calls: list[object] = []

    class _InjectedService:
        artifact_store = foreign_store

        def resolve(self, request: object, *, run_profile: str) -> object:
            resolve_calls.append((request, run_profile))
            raise AssertionError("foreign store must be rejected before resolution")

        def execute_fetch_plans(self, *args: object, **kwargs: object) -> object:
            execute_calls.append((args, kwargs))
            raise AssertionError("foreign store must be rejected before execution")

    with build_recorded_file_fetch_owner(
        tmp_path, canonicalize_catalog_source=True, publish_current_catalog=True
    ) as owner:

        def _service_factory(_curated_dir: Path, store: object, _graph: object) -> object:
            factory_store_args.append(store)
            return _InjectedService()

        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:fetch-capture-foreign-store",
                "claim_id": "claim-fetch-capture-foreign-store",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-n7-fetch-capture-foreign-store",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=_service_factory,
            artifact_store=runtime_store,
        )

        assert (
            gateway.acquire(
                record=report.acquisition_records[0],
                compiled_requirement_spec=base_spec,
            )
            is None
        )

    assert factory_store_args == [runtime_store]
    assert resolve_calls == []
    assert execute_calls == []
    assert runtime_store.iter_artifact_ids() == []
    assert foreign_store.iter_artifact_ids() == []


def test_real_owner_gateway_opt_in_captures_real_fetch_custody_without_world_growth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The explicit capture lane records real CAS refs and remains resolve-only for N7."""

    from polisyos.core import artifacts, canon
    from polisyos.data_forge.read_api import catalog as catalog_read_api
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.retrieval import custody
    from polisyos.fabric.retrieval.custody import FabricFetchReceipt
    from polisyos.fabric.retrieval.service import RetrievalService
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    capture_root = tmp_path / "runtime-cas"
    runtime_store = guard_runtime_cas(
        FileSystemCAS(capture_root).for_tenant("tenant-n7", cell_id="cell-a")
    )
    foreign_store = FileSystemCAS(capture_root).for_tenant("tenant-other", cell_id="cell-a")
    services: list[RetrievalService] = []
    source_id = _install_recorded_file_catalog_supplier(monkeypatch)

    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        catalog_connector_params={},
        publish_current_catalog=True,
    ) as owner:
        owner.providers.registry.set_default_config(
            "files.tabular", ConnectionConfig(url="https://remote.invalid/unused-default.csv")
        )
        binding = owner.graph.resolve_metric_bindings("metric.test", top_k=1)[0]
        assert binding.source == source_id
        registered_source = catalog_read_api.load_catalog_source_registry().source_by_id(source_id)
        assert registered_source is not None
        assert registered_source.connector_id == binding.connector_id == "files.tabular"

        def _catalog_factory(_db_path: Path, _index_dir: Path) -> object:
            return owner.graph

        def _local_service_factory(curated_dir: Path, store: object, graph: object) -> object:
            assert store is runtime_store
            service = RetrievalService(
                curated_dir=curated_dir,
                artifact_store=store,
                dataset_catalog=graph,
                providers=owner.providers,
            )
            services.append(service)
            return service

        def _unexpected_replay(*args: object, **kwargs: object) -> None:
            del args, kwargs
            raise AssertionError("captured acceptance must not replay the source")

        monkeypatch.setattr(custody, "resolve_persisted_fetch", _unexpected_replay)

        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:fetch-capture",
                "claim_id": "claim-fetch-capture",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-n7-fetch-capture",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=_catalog_factory,
            retrieval_service_factory=_local_service_factory,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
            captured_at=datetime(2026, 7, 17, tzinfo=UTC),
        )

        artifact = gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )

        assert artifact is not None
        raw_response = artifact.payload["owner_response"]
        assert raw_response["owner_response_kind"] == "fabric_fetch_capture"
        assert raw_response["candidate_only"] is True
        assert raw_response["requirement_projection"]["disposition"] == "candidate_only"
        assert raw_response["captured_fetch_count"] == 1
        captured = raw_response["captured_fetches"][0]
        assert captured["plan"]["connector_id"] == "files.tabular"
        assert captured["plan"]["dataset_id"] == str(owner.csv_path)
        payload_ref = artifacts.ArtifactRef.model_validate(captured["payload_ref"])
        receipt_ref = artifacts.ArtifactRef.model_validate(captured["fetch_receipt_ref"])
        binding_ref = artifacts.ArtifactRef.model_validate(captured["catalog_binding_ref"])
        assert services[0].artifact_store is runtime_store
        capture_store = runtime_store
        assert capture_store.has(payload_ref.artifact_id)
        assert capture_store.has(receipt_ref.artifact_id)
        assert capture_store.has(binding_ref.artifact_id)
        assert not foreign_store.has(receipt_ref.artifact_id)
        with pytest.raises(PermissionError, match="not readable by tenant"):
            foreign_store.get_bytes(receipt_ref.artifact_id)
        captured_receipt = FabricFetchReceipt.model_validate(
            canon.from_canonical_bytes(capture_store.get_bytes(receipt_ref.artifact_id))
        )
        assert captured_receipt.catalog_binding_ref == binding_ref
        assert captured_receipt.result.data == payload_ref
        binding_manifest = capture_store.get_manifest(binding_ref.artifact_id)
        assert binding_manifest.kind == "fabric.catalog_fetch_binding"
        assert binding_manifest.media_type == "application/json"
        assert artifact.payload["acquired_substrate_registrations"] == []
        assert artifact.payload["candidate_bindings"] == []
        assert gateway.network_counter.network_calls == 0

        receipt = run_acquisition_closed_loop(
            run_id="run-n7-fetch-capture-no-world-growth",
            acquisition_request={
                "request_kind": "owner_grounding_evidence",
                "driver": "missing_supporting_data",
                "cycle_index": 1,
            },
            data_requirement_specs=(base_spec,),
            world_snapshot=AcquisitionWorldSnapshot(world_ref="world://before/fetch-capture"),
            owner_gateway=RecordedAcquisitionOwnerGateway(
                artifacts_by_requirement={base_spec["requirement_id"]: artifact}
            ),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        assert receipt.status == "completed_no_results"
        assert receipt.grown_world_added_slots == ()
        assert receipt.grown_world_after_ref == "world://before/fetch-capture"


def test_real_owner_gateway_capture_requires_explicit_local_service_without_remote_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.fabric.retrieval import service as retrieval_service

    remote_calls: list[dict[str, object]] = []

    def _remote_provider_trap(**kwargs: object) -> object:
        remote_calls.append(kwargs)
        raise AssertionError("metadata-only capture must not resolve global providers")

    monkeypatch.setattr(retrieval_service, "resolve_retrieval_providers", _remote_provider_trap)

    def _unexpected_catalog(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("metadata-only capture must not open the catalog")

    base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
    base_spec.update(
        {
            "requirement_id": "data-requirement:fetch-capture-no-service",
            "claim_id": "claim-fetch-capture-no-service",
            "required_data_families": ("metric.test",),
            "metadata": {
                "fabric_capture_mode": "persisted_payload",
                "scope_profile": _catalog_capture_scope_profile(),
            },
        }
    )
    gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
    report = plan_requirement_gap_acquisition(
        run_id="run-n7-fetch-capture-no-service",
        requirement_gaps=(gap,),
        generated_at=datetime(2026, 7, 17, tzinfo=UTC),
    )
    gateway = RealAcquisitionOwnerGateway(
        repo_root=tmp_path,
        dataset_catalog_factory=_unexpected_catalog,
    )

    assert (
        gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )
        is None
    )
    assert remote_calls == []
    assert not (tmp_path / ".n7-live-cas").exists()


@pytest.mark.parametrize("plan_count", [0, 2])
def test_real_owner_gateway_capture_requires_exactly_one_fetch_plan(
    tmp_path: Path,
    plan_count: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = FileSystemCAS(tmp_path / "cardinality-runtime-cas")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path, canonicalize_catalog_source=True, publish_current_catalog=True
    ) as owner:
        resolve_calls: list[object] = []

        def _catalog_factory(_db_path: Path, _index_dir: Path) -> object:
            return owner.graph

        def _service_factory(curated_dir: Path, _store: object, graph: object) -> object:
            service = RetrievalService(
                curated_dir=curated_dir,
                artifact_store=runtime_store,
                dataset_catalog=graph,
                providers=owner.providers,
            )

            class _CardinalityService:
                @property
                def artifact_store(self) -> object | None:
                    return service.artifact_store

                def resolve(self, request: object, *, run_profile: str) -> object:
                    resolve_calls.append((request, run_profile))
                    resolved = service.resolve(request, run_profile=run_profile)
                    assert resolved.fetch_plans
                    if plan_count == 0:
                        return replace(resolved, fetch_plans=[])
                    extra = resolved.fetch_plans[0].model_copy(
                        update={"plan_id": "plan-extra-cardinality"}
                    )
                    return replace(
                        resolved,
                        fetch_plans=[resolved.fetch_plans[0], extra],
                    )

                def execute_persisted_fetch_capture(
                    self, *args: object, **kwargs: object
                ) -> object:
                    del args, kwargs
                    raise AssertionError(
                        "invalid plan cardinality must fail before persisted capture"
                    )

                def execute_fetch_plans(self, *args: object, **kwargs: object) -> object:
                    del args, kwargs
                    raise AssertionError("invalid plan cardinality must fail before execute")

            return _CardinalityService()

        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": f"data-requirement:fetch-capture-plan-{plan_count}",
                "claim_id": f"claim-fetch-capture-plan-{plan_count}",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id=f"run-n7-fetch-capture-plan-{plan_count}",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=_catalog_factory,
            retrieval_service_factory=_service_factory,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        assert (
            gateway.acquire(
                record=report.acquisition_records[0],
                compiled_requirement_spec=base_spec,
            )
            is None
        )
        assert len(resolve_calls) == 1
        assert owner.requests == []


def test_real_owner_gateway_capture_rejects_remote_effective_connector_before_execute(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = FileSystemCAS(tmp_path / "remote-effective-runtime-cas")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path, canonicalize_catalog_source=True, publish_current_catalog=True
    ) as owner:
        profile = owner.providers.profiles.get("recorded_file_local")
        assert profile is not None
        owner.providers.registry.set_default_config(
            "files.tabular", ConnectionConfig(url=str(owner.csv_path))
        )
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        original_resolve = service.resolve

        def _resolve_then_change_profile(request: object, *, run_profile: str) -> object:
            resolved = original_resolve(request, run_profile=run_profile)
            assert len(resolved.fetch_plans) == 1
            owner.providers.profiles.register(
                profile.model_copy(update={"base_url": "https://remote.invalid/recorded.csv"}),
                override=True,
            )
            return resolved

        service.resolve = _resolve_then_change_profile  # type: ignore[method-assign]
        execute_calls: list[object] = []

        def _network_execute_trap(*args: object, **kwargs: object) -> object:
            execute_calls.append((args, kwargs))
            raise AssertionError("remote capture must be refused before execution")

        service.execute_persisted_fetch_capture = _network_execute_trap  # type: ignore[method-assign]

        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:fetch-capture-remote-effective",
                "claim_id": "claim-fetch-capture-remote-effective",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-n7-fetch-capture-remote-effective",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=lambda _curated_dir, _store, _graph: service,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        assert (
            gateway.acquire(
                record=report.acquisition_records[0],
                compiled_requirement_spec=base_spec,
            )
            is None
        )
        assert execute_calls == []
        assert owner.requests == []
        assert "fabric_fetch_capture_remote_locator" in caplog.text


def test_real_owner_gateway_capture_uses_owner_bound_profile_route_without_catalog_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core import artifacts, canon
    from polisyos.fabric.connectors.sources import file_tabular
    from polisyos.fabric.retrieval.custody import FabricFetchReceipt, _decode_payload
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = FileSystemCAS(tmp_path / "owner-bound-profile-route-cas")
    observed_urls: list[str] = []
    alternate_path = tmp_path / "effective-profile-route.csv"
    alternate_path.write_text("row_id,value\nprofile-route-b,909.5\n", encoding="utf-8")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        catalog_connector_params={},
        profile_base_url=str(alternate_path),
        publish_current_catalog=True,
    ) as owner:
        assert owner.csv_path != alternate_path
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        original_read = file_tabular.read_location_bytes

        async def _record_effective_route(config, *args, **kwargs):
            observed_urls.append(config.url)
            return await original_read(config, *args, **kwargs)

        monkeypatch.setattr(file_tabular, "read_location_bytes", _record_effective_route)
        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:owner-bound-profile-route",
                "claim_id": "claim-owner-bound-profile-route",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-owner-bound-profile-route",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=lambda _curated_dir, _store, _graph: service,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        artifact = gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )

        assert artifact is not None
        assert observed_urls == [str(alternate_path), str(alternate_path)]
        raw_response = artifact.payload["owner_response"]
        assert raw_response["captured_fetch_count"] == 1
        captured = raw_response["captured_fetches"][0]
        assert captured["plan"]["dataset_id"] == str(owner.csv_path)
        payload_ref = artifacts.ArtifactRef.model_validate(captured["payload_ref"])
        receipt_ref = artifacts.ArtifactRef.model_validate(captured["fetch_receipt_ref"])
        assert runtime_store.has(payload_ref.artifact_id)
        receipt = FabricFetchReceipt.model_validate(
            canon.from_canonical_bytes(runtime_store.get_bytes(receipt_ref.artifact_id))
        )
        assert receipt.result.data == payload_ref
        captured_data = _decode_payload(
            runtime_store.get_bytes(payload_ref.artifact_id), receipt.payload_encoding
        )
        assert captured_data["row_id"].tolist() == ["profile-route-b"]
        assert captured_data["value"].tolist() == [909.5]


def test_real_owner_gateway_capture_refuses_present_route_that_conflicts_with_profile_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = FileSystemCAS(tmp_path / "conflicting-profile-route-cas")
    alternate_path = tmp_path / "effective-profile-route.csv"
    alternate_path.write_text("row_id,value\nprofile-route-b,909.5\n", encoding="utf-8")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        catalog_connector_params={
            "url": str(tmp_path / "recorded.csv"),
            "path": str(tmp_path / "recorded.csv"),
        },
        profile_base_url=str(alternate_path),
        publish_current_catalog=True,
    ) as owner:
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        execute_calls: list[object] = []

        def _execute_trap(*args: object, **kwargs: object) -> object:
            execute_calls.append((args, kwargs))
            raise AssertionError("conflicting selected route must refuse before execution")

        service.execute_persisted_fetch_capture = _execute_trap  # type: ignore[method-assign]
        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:conflicting-profile-route",
                "claim_id": "claim-conflicting-profile-route",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-conflicting-profile-route",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=lambda _curated_dir, _store, _graph: service,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        assert (
            gateway.acquire(
                record=report.acquisition_records[0],
                compiled_requirement_spec=base_spec,
            )
            is None
        )
        assert execute_calls == []
        assert owner.requests == []
        assert runtime_store.iter_artifact_ids() == []
        assert "fabric_fetch_capture_catalog_config_mismatch" in caplog.text


def test_real_owner_gateway_capture_refuses_present_null_url_even_with_path_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = FileSystemCAS(tmp_path / "present-null-route-alias-cas")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        catalog_connector_params={"url": None, "path": str(tmp_path / "recorded.csv")},
        publish_current_catalog=True,
    ) as owner:
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        execute_calls: list[object] = []

        def _execute_trap(*args: object, **kwargs: object) -> object:
            execute_calls.append((args, kwargs))
            raise AssertionError("a present malformed route must refuse before execution")

        service.execute_persisted_fetch_capture = _execute_trap  # type: ignore[method-assign]
        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:present-null-route-alias",
                "claim_id": "claim-present-null-route-alias",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-present-null-route-alias",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=lambda _curated_dir, _store, _graph: service,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        assert (
            gateway.acquire(
                record=report.acquisition_records[0],
                compiled_requirement_spec=base_spec,
            )
            is None
        )
        assert execute_calls == []
        assert owner.requests == []
        assert runtime_store.iter_artifact_ids() == []
        assert "fabric_fetch_capture_catalog_locator_malformed" in caplog.text


@pytest.mark.parametrize(
    "effective_route_kind",
    ["relative", "space_prefixed_absolute", "tilde_relative"],
    ids=["relative", "space-prefixed-absolute", "tilde-relative"],
)
def test_real_owner_gateway_capture_rejects_effective_route_resolved_differently_by_connector(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    effective_route_kind: str,
) -> None:
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.sources._file_common import read_location_bytes
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    approved_root = tmp_path / "approved"
    runtime_store = FileSystemCAS(approved_root / "relative-effective-runtime-cas")
    approved_locator = approved_root / "inside.csv"
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path,
        catalog_source_locator=approved_locator,
        catalog_connector_params={},
        publish_current_catalog=True,
    ) as owner:
        if effective_route_kind == "relative":
            effective_locator = "inside.csv"
        elif effective_route_kind == "space_prefixed_absolute":
            effective_locator = f" {approved_locator}"
        else:
            monkeypatch.setenv("HOME", str(tmp_path))
            effective_locator = "~/approved/inside.csv"

        cwd_locator = tmp_path / Path(effective_locator)
        cwd_locator.parent.mkdir(parents=True, exist_ok=True)
        cwd_locator.write_text("row_id,value\ncwd-route,123.4\n", encoding="utf-8")
        assert not Path(effective_locator).is_absolute()
        assert cwd_locator.resolve() != approved_locator.resolve()
        monkeypatch.chdir(tmp_path)

        # Read through the exact helper the registered connector calls. The
        # whitespace-prefixed and tilde-relative inputs open a distinct CWD file,
        # not the in-root file that stripping or shell-home expansion would check.
        connector_bytes, _headers = asyncio.run(
            read_location_bytes(ConnectionConfig(url=effective_locator))
        )
        assert connector_bytes == cwd_locator.read_bytes()
        assert connector_bytes != approved_locator.read_bytes()

        profile = owner.providers.profiles.get("recorded_file_local")
        assert profile is not None
        owner.providers.registry.set_default_config(
            "files.tabular", ConnectionConfig(url=str(approved_locator))
        )
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        original_resolve = service.resolve

        def _resolve_then_change_profile(request: object, *, run_profile: str) -> object:
            resolved = original_resolve(request, run_profile=run_profile)
            assert len(resolved.fetch_plans) == 1
            owner.providers.profiles.register(
                profile.model_copy(update={"base_url": effective_locator}),
                override=True,
            )
            return resolved

        service.resolve = _resolve_then_change_profile  # type: ignore[method-assign]
        execute_calls: list[object] = []

        def _cwd_execute_trap(*args: object, **kwargs: object) -> object:
            execute_calls.append((args, kwargs))
            raise AssertionError("a route that resolves against CWD must fail before fetch")

        service.execute_persisted_fetch_capture = _cwd_execute_trap  # type: ignore[method-assign]
        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": f"data-requirement:fetch-capture-{effective_route_kind}",
                "claim_id": f"claim-fetch-capture-{effective_route_kind}",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id=f"run-n7-fetch-capture-{effective_route_kind}",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=approved_root,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=lambda _curated_dir, _store, _graph: service,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        assert (
            gateway.acquire(
                record=report.acquisition_records[0],
                compiled_requirement_spec=base_spec,
            )
            is None
        )
        assert cwd_locator.is_file()
        assert execute_calls == []
        assert owner.requests == []
        assert runtime_store.iter_artifact_ids() == []
        assert "fabric_fetch_capture_effective_config_relative" in caplog.text


def test_real_owner_gateway_capture_refuses_route_removed_after_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import Callable, Sequence

    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.contracts.control import FetchPlan
    from polisyos.fabric.retrieval.service import (
        ExecuteOutcome,
        FetchCapturePostflightView,
        FetchCapturePreflightView,
        RetrievalService,
    )
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = FileSystemCAS(tmp_path / "removed-after-preflight-cas")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path, canonicalize_catalog_source=True, publish_current_catalog=True
    ) as owner:
        route_path = owner.csv_path.resolve(strict=True)
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        original_capture = service.execute_persisted_fetch_capture

        def _remove_after_route_check(
            plans: Sequence[FetchPlan],
            *,
            preflight: Callable[[FetchCapturePreflightView], None],
            postflight: Callable[[FetchCapturePostflightView], None],
        ) -> ExecuteOutcome:
            def _check_then_remove(view: FetchCapturePreflightView) -> None:
                preflight(view)
                assert route_path.is_file()
                route_path.unlink()

            return original_capture(
                plans,
                preflight=_check_then_remove,
                postflight=postflight,
            )

        service.execute_persisted_fetch_capture = _remove_after_route_check  # type: ignore[method-assign]
        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:removed-after-route-preflight",
                "claim_id": "claim-removed-after-route-preflight",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-removed-after-route-preflight",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=lambda _curated_dir, _store, _graph: service,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        assert (
            gateway.acquire(
                record=report.acquisition_records[0],
                compiled_requirement_spec=base_spec,
            )
            is None
        )
        assert not route_path.exists()
        assert owner.requests == []
        assert runtime_store.iter_artifact_ids() == []


@pytest.mark.parametrize(
    ("route_key", "route_value", "refusal_code"),
    [
        ("url", "", "fabric_fetch_capture_catalog_locator_malformed"),
        ("url", " \t", "fabric_fetch_capture_local_path_unreadable"),
        ("path", "", "fabric_fetch_capture_catalog_locator_malformed"),
    ],
    ids=["blank-url", "whitespace-url", "blank-path"],
)
def test_real_owner_gateway_capture_rejects_blank_selected_route_before_fetch_or_cas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    route_key: str,
    route_value: str,
    refusal_code: str,
) -> None:
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = FileSystemCAS(tmp_path / f"blank-selected-route-{route_key}-cas")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        catalog_connector_params={route_key: route_value},
        publish_current_catalog=True,
    ) as owner:
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=lambda curated_dir, store, graph: RetrievalService(
                curated_dir=curated_dir,
                artifact_store=store,
                dataset_catalog=graph,
                providers=owner.providers,
            ),
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )
        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": f"data-requirement:blank-selected-route-{route_key}",
                "claim_id": f"claim-blank-selected-route-{route_key}",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id=f"run-blank-selected-route-{route_key}",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )

        artifact = gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )

        assert artifact is None
        assert owner.requests == []
        assert runtime_store.iter_artifact_ids() == []
        assert refusal_code in caplog.text


def test_real_owner_gateway_capture_rejects_sibling_catalog_before_fetch_or_cas(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from polisyos.core.contracts.control import DataNeed
    from polisyos.data_forge.read_api import catalog as catalog_api
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = FileSystemCAS(tmp_path / "sibling-catalog-capture-cas")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        publish_current_catalog=True,
    ) as owner:
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        resolved = service.resolve(
            DataResolveRequest(
                data_needs=[DataNeed(metric="metric.test")],
                mode="hybrid",
                allow_explore_fallback=False,
            ),
            run_profile="prod_full",
        )
        assert len(resolved.fetch_plans) == 1
        plan = resolved.fetch_plans[0]
        binding_kwargs = {
            "metric_id": plan.metric_id,
            "connector_id": plan.connector_id,
            "request_dataset_id": plan.dataset_id,
            "profile_id": plan.profile_id,
            "filters": plan.filters,
        }
        owner_binding = owner.graph.bind_fetch_target(**binding_kwargs)
        sibling_graph = catalog_api.DatasetCatalogGraph(
            owner.graph_path,
            owner.index_dir,
            overlay_path=tmp_path / "sibling-overlay.duckdb",
        )
        sibling_binding = sibling_graph.bind_fetch_target(**binding_kwargs)
        assert owner_binding.baseline == sibling_binding.baseline
        assert owner_binding.target == sibling_binding.target
        assert owner_binding.overlay_path != sibling_binding.overlay_path
        assert owner_binding.target.connector_params == sibling_binding.target.connector_params

        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:fetch-capture-sibling-catalog",
                "claim_id": "claim-fetch-capture-sibling-catalog",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-n7-fetch-capture-sibling-catalog",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: sibling_graph,
            retrieval_service_factory=lambda _curated_dir, _store, _graph: service,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        artifact = gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )

        assert artifact is None
        assert owner.requests == []
        assert runtime_store.iter_artifact_ids() == []
        assert "fabric_fetch_capture_catalog_binding_mismatch" in caplog.text


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_receipt",
        "foreign_payload",
        "foreign_binding",
        "tampered_receipt",
        "missing_binding",
        "tampered_binding",
    ],
)
def test_real_owner_gateway_capture_fails_closed_for_invalid_cas_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Capture mode never emits an owner artifact for an incomplete CAS chain."""

    from dataclasses import replace
    from typing import Any

    from polisyos.core import artifacts, canon
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
    from polisyos.fabric.retrieval import custody
    from polisyos.fabric.retrieval.custody import FabricFetchReceipt
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = build_artifact_store(
        ArtifactStoreConfig(backend="filesystem", root=str(tmp_path / "fetch-capture-cas"))
    )
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path, canonicalize_catalog_source=True, publish_current_catalog=True
    ) as owner:
        original_execute = RetrievalService.execute_fetch_plans
        original_get_bytes = FileSystemCAS.get_bytes
        original_get_manifest = FileSystemCAS.get_manifest
        intercepted_mutation: list[str] = []
        selected_mutation_refs: list[str] = []
        consumer_readback_refs: list[str] = []

        def _selected_artifact_id(selector: object) -> str:
            selected = getattr(selector, "artifact_id", selector)
            return str(selected)

        def _execute_and_mutate(
            service: RetrievalService,
            plans: list[object],
            *,
            persist_payload: bool = False,
            allow_fallback: bool = True,
            execution_binding: Any = None,
        ) -> object:
            outcome = original_execute(
                service,
                plans,
                persist_payload=persist_payload,
                allow_fallback=allow_fallback,
                execution_binding=execution_binding,
            )
            metric = outcome.data_context.metrics[0]
            if mutation == "missing_receipt":
                mutated_metric = metric.model_copy(update={"fetch_receipt_ref": None})
            elif mutation == "foreign_payload":
                foreign_payload_id = "sha256:" + "f" * 64
                selected_mutation_refs.append(foreign_payload_id)

                def _foreign_payload_manifest(store: FileSystemCAS, artifact_id: object) -> object:
                    selected_id = _selected_artifact_id(artifact_id)
                    if selected_id == foreign_payload_id:
                        intercepted_mutation.append("foreign_payload")
                        consumer_readback_refs.append(selected_id)
                    return original_get_manifest(store, artifact_id)

                monkeypatch.setattr(FileSystemCAS, "get_manifest", _foreign_payload_manifest)
                mutated_metric = metric.model_copy(
                    update={
                        "payload_ref": ArtifactRef.model_validate(
                            {
                                "artifact_id": foreign_payload_id,
                                "kind": "fabric.fetch_payload",
                                "media_type": "application/json",
                            }
                        )
                    }
                )
            elif mutation == "foreign_binding":
                plan = plans[0]
                receipt_ref = metric.fetch_receipt_ref
                assert receipt_ref is not None
                receipt_store = runtime_store
                receipt = FabricFetchReceipt.model_validate(
                    canon.from_canonical_bytes(
                        original_get_bytes(receipt_store, receipt_ref.artifact_id)
                    )
                )
                payload_ref = metric.payload_ref
                assert payload_ref is not None
                foreign_binding = owner.graph.bind_fetch_target(
                    metric_id=plan.metric_id,
                    connector_id=plan.connector_id,
                    request_dataset_id="fallback",
                    profile_id=plan.profile_id,
                    filters=plan.filters,
                )
                foreign_binding_ref = custody._put_json(
                    receipt_store,
                    foreign_binding,
                    kind="fabric.catalog_fetch_binding",
                    schema="polisyos.data_forge.catalog_fetch_binding.v1",
                    inputs=[],
                )
                selected_binding_id = str(foreign_binding_ref.artifact_id)
                selected_mutation_refs.append(selected_binding_id)

                def _foreign_binding_get_bytes(store: FileSystemCAS, artifact_id: object) -> bytes:
                    data = original_get_bytes(store, artifact_id)
                    selected_id = _selected_artifact_id(artifact_id)
                    if selected_id == selected_binding_id:
                        intercepted_mutation.append("foreign_binding")
                        consumer_readback_refs.append(selected_id)
                    return data

                monkeypatch.setattr(FileSystemCAS, "get_bytes", _foreign_binding_get_bytes)
                foreign_receipt = receipt.model_copy(
                    update={"catalog_binding_ref": foreign_binding_ref}
                )
                foreign_receipt_ref = custody._put_json(
                    receipt_store,
                    foreign_receipt,
                    kind="fabric.fetch_receipt",
                    schema="polisyos.fabric.fetch_receipt.v1",
                    inputs=[
                        artifacts.InputRef(
                            artifact_id=payload_ref.artifact_id,
                            role="fetched_payload",
                        ),
                        artifacts.InputRef(
                            artifact_id=foreign_binding_ref.artifact_id,
                            role="catalog_binding",
                        ),
                    ],
                )
                mutated_metric = metric.model_copy(
                    update={"fetch_receipt_ref": foreign_receipt_ref}
                )
            elif mutation == "tampered_receipt":
                receipt_ref = metric.fetch_receipt_ref
                assert receipt_ref is not None
                selected_receipt_id = str(receipt_ref.artifact_id)
                selected_mutation_refs.append(selected_receipt_id)

                def _tampered_get_bytes(store: FileSystemCAS, artifact_id: object) -> bytes:
                    data = original_get_bytes(store, artifact_id)
                    selected_id = _selected_artifact_id(artifact_id)
                    if selected_id == selected_receipt_id:
                        intercepted_mutation.append("tampered_receipt")
                        consumer_readback_refs.append(selected_id)
                        return data + b"tampered"
                    return data

                monkeypatch.setattr(FileSystemCAS, "get_bytes", _tampered_get_bytes)
                mutated_metric = metric
            else:
                receipt_ref = metric.fetch_receipt_ref
                assert receipt_ref is not None
                receipt_store = runtime_store
                receipt = FabricFetchReceipt.model_validate(
                    canon.from_canonical_bytes(
                        original_get_bytes(receipt_store, receipt_ref.artifact_id)
                    )
                )
                binding_ref = receipt.catalog_binding_ref
                selected_binding_id = str(binding_ref.artifact_id)
                selected_mutation_refs.append(selected_binding_id)
                if mutation == "missing_binding":

                    def _missing_binding_manifest(
                        store: FileSystemCAS, artifact_id: object
                    ) -> object:
                        selected_id = _selected_artifact_id(artifact_id)
                        if selected_id == selected_binding_id:
                            intercepted_mutation.append("missing_binding")
                            consumer_readback_refs.append(selected_id)
                            raise FileNotFoundError(selected_id)
                        return original_get_manifest(store, artifact_id)

                    monkeypatch.setattr(FileSystemCAS, "get_manifest", _missing_binding_manifest)
                else:

                    def _tampered_binding_get_bytes(
                        store: FileSystemCAS, artifact_id: object
                    ) -> bytes:
                        data = original_get_bytes(store, artifact_id)
                        selected_id = _selected_artifact_id(artifact_id)
                        if selected_id == selected_binding_id:
                            intercepted_mutation.append("tampered_binding")
                            consumer_readback_refs.append(selected_id)
                            return data + b"tampered"
                        return data

                    monkeypatch.setattr(FileSystemCAS, "get_bytes", _tampered_binding_get_bytes)
                mutated_metric = metric
            if mutation == "missing_receipt":
                assert metric.fetch_receipt_ref is not None
                selected_mutation_refs.append(str(metric.fetch_receipt_ref.artifact_id))
            mutated_context = outcome.data_context.model_copy(update={"metrics": [mutated_metric]})
            return replace(outcome, data_context=mutated_context)

        monkeypatch.setattr(RetrievalService, "execute_fetch_plans", _execute_and_mutate)

        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": f"data-requirement:fetch-capture-{mutation}",
                "claim_id": f"claim-fetch-capture-{mutation}",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id=f"run-n7-fetch-capture-{mutation}",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=lambda curated_dir, store, graph: RetrievalService(
                curated_dir=curated_dir,
                artifact_store=store,
                dataset_catalog=graph,
                providers=owner.providers,
            ),
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
            captured_at=datetime(2026, 7, 17, tzinfo=UTC),
        )

        artifact = gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )
        assert artifact is None
        if mutation == "missing_receipt":
            assert intercepted_mutation == []
            assert consumer_readback_refs == []
            assert "fabric_fetch_capture_refs_missing" in caplog.text
        else:
            assert intercepted_mutation == [mutation]
            assert len(selected_mutation_refs) == 1
            assert consumer_readback_refs == selected_mutation_refs


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
    assert receipt.fail_closed_reasons == (
        "owner_artifact_missing:data-requirement:claim-source-family",
    )
    assert receipt.useful_design_rate_after == 0.0
    assert "owner_validation_failed_closed" in {
        issue["code"] for issue in validate_acquisition_receipt(receipt)
    }


def test_n7_network_counter_fails_routine_offline_if_gateway_leaks_owner_call() -> None:
    counter = AcquisitionNetworkCallCounter()
    counter.record_call(owner_component="data_forge.openalex", endpoint="/works")

    assert counter.network_calls == 1
    assert counter.assert_offline_check()["code"] == "routine_check_hit_network"


def test_openalex_gateway_uses_academic_facade_and_keeps_response_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.data_forge.read_api import academic

    scholar_spec = _compiled_requirement_specs()[3]
    requirement_gap = requirement_gaps_from_compiled_specs(
        scholar_support_requirement_specs=(scholar_spec,)
    )[0]
    record = plan_requirement_gap_acquisition(
        run_id="run-openalex-facade-candidate",
        requirement_gaps=(requirement_gap,),
    ).acquisition_records[0]
    observed_requests: list[object] = []
    response = {
        "results": [
            {
                "id": "https://openalex.org/W123",
                "title": "Controlled candidate result",
                "publication_year": 2024,
                "cited_by_count": 3,
            }
        ],
        "meta": {"count": 1},
    }

    class _ControlledOpenAlexClient:
        def __init__(self, **_kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _ControlledOpenAlexClient:
            return self

        async def __aexit__(self, *_exc: object) -> None:
            return None

        async def list_works(self, request: object) -> dict[str, object]:
            observed_requests.append(request)
            return response

    monkeypatch.setattr(academic, "OpenAlexClient", _ControlledOpenAlexClient)
    counter = AcquisitionNetworkCallCounter()
    gateway = RealAcquisitionOwnerGateway(
        repo_root=tmp_path,
        network_counter=counter,
        allow_openalex_network=True,
        captured_at=datetime(2026, 7, 5, tzinfo=UTC),
    )

    artifact = gateway.acquire(
        record=record,
        compiled_requirement_spec=scholar_spec.model_dump(mode="json"),
    )

    assert artifact is not None
    assert artifact.owner_component == "data_forge.openalex"
    assert artifact.payload["owner_response"]["openalex"] == response
    assert artifact.payload["owner_response"]["owner_response_kind"] == "openalex_live_response"
    assert artifact.capture_provenance is not None
    assert artifact.capture_provenance.network_call is True
    assert counter.network_calls == 1
    assert len(observed_requests) == 1
    request = observed_requests[0]
    assert isinstance(request, academic.OpenAlexRequest)
    assert request.filter_expr == 'title.search:"policy"'
    assert request.sort == "cited_by_count:desc"
    assert request.per_page == 1
    assert request.select == "id,title,publication_year,cited_by_count"


def test_openalex_gateway_default_refuses_before_owner_call(tmp_path: Path) -> None:
    scholar_spec = _compiled_requirement_specs()[3]
    requirement_gap = requirement_gaps_from_compiled_specs(
        scholar_support_requirement_specs=(scholar_spec,)
    )[0]
    record = plan_requirement_gap_acquisition(
        run_id="run-openalex-facade-opt-out",
        requirement_gaps=(requirement_gap,),
    ).acquisition_records[0]
    counter = AcquisitionNetworkCallCounter()
    gateway = RealAcquisitionOwnerGateway(
        repo_root=tmp_path,
        network_counter=counter,
        captured_at=datetime(2026, 7, 5, tzinfo=UTC),
    )

    artifact = gateway.acquire(
        record=record,
        compiled_requirement_spec=scholar_spec.model_dump(mode="json"),
    )

    assert artifact is None
    assert counter.network_calls == 0


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("POLISYOS_N7_LIVE_OWNER_LANE") != "1",
    reason="cloud-gated N7 live owner lane; routine tests must not call the network",
)
def test_n7_cloud_live_owner_lane_calls_openalex_and_reenters_same_cycle() -> None:
    """Cloud lane: call a real owner once, then validate the normal N7 receipt path."""

    async def _fetch_openalex_payload() -> dict[str, object]:
        from polisyos.data_forge.read_api import academic as academic_read_api

        async with academic_read_api.OpenAlexClient(
            email=os.environ.get("OPENALEX_MAILTO", ""),
            max_rps=1,
            max_concurrent=1,
            timeout_seconds=30,
            max_retries=1,
        ) as client:
            return await client.list_works(
                academic_read_api.OpenAlexRequest(
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
                "candidate_content_hash": "sha256:"
                + _slug_for_test(candidate_id)[:64].ljust(64, "0"),
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


def _catalog_capture_scope_profile() -> dict[str, object]:
    """Supply an explicit test scope for the candidate-only local Catalog capture path."""

    return {
        "profile_id": "fixture:catalog-capture:ua-2026",
        "jurisdiction": None,
        "time_window": {"start": None, "end": None},
        "time_role": "observation_time",
        "granularity": "annual",
        "required_constructs": [],
        "candidate_construct_proposals": [],
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
        minimum_representativeness_class=(ParticipationRepresentativenessClass.REPRESENTATIVE),
        consent_redaction="redacted_microdata",
        dissent_handling="dissent_recorded",
        sponsor_disclosure="sponsor_disclosed",
    )
    return data_spec, legal_spec, method_spec, scholar_spec, participation_spec


def test_real_owner_gateway_store_removal_probe_refuses_before_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A root-local executor cannot satisfy markers while a runtime store is supplied."""
    from polisyos.core.artifacts.backends.config import ArtifactStoreConfig
    from polisyos.fabric.retrieval.service import RetrievalService
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_root = tmp_path / "runtime-cas"
    runtime_store = FileSystemCAS(runtime_root).for_tenant("tenant-n7", cell_id="cell-a")
    local_config = ArtifactStoreConfig(
        backend="filesystem", root=str(tmp_path / "unbound-local-cas")
    )
    execute_calls: list[object] = []
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path, canonicalize_catalog_source=True, publish_current_catalog=True
    ) as owner:

        def _local_service_factory(curated_dir: Path, _store: object, graph: object) -> object:
            service = RetrievalService(
                curated_dir=curated_dir,
                artifact_store_config=local_config,
                dataset_catalog=graph,
                providers=owner.providers,
            )
            original_execute = service.execute_fetch_plans

            def _track_execute(*args: object, **kwargs: object) -> object:
                execute_calls.append((args, kwargs))
                return original_execute(*args, **kwargs)

            service.execute_fetch_plans = _track_execute  # type: ignore[method-assign]
            return service

        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": "data-requirement:fetch-capture-store-removal",
                "claim_id": "claim-fetch-capture-store-removal",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id="run-n7-fetch-capture-store-removal",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=lambda _db_path, _index_dir: owner.graph,
            retrieval_service_factory=_local_service_factory,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        artifact = gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )

        assert artifact is None
        assert execute_calls == []
        assert runtime_store.iter_artifact_ids() == []


@pytest.mark.parametrize("mutation_point", ["after_guard", "between_preview_and_full"])
@pytest.mark.parametrize(
    "catalog_connector_params",
    [None, {}],
    ids=["catalog-selected-url", "owner-bound-profile-fallback"],
)
def test_real_owner_gateway_capture_uses_one_guarded_profile_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation_point: str,
    catalog_connector_params: dict[str, object] | None,
) -> None:
    from collections.abc import Callable, Sequence
    from typing import Any

    from polisyos.core import artifacts, canon
    from polisyos.core.contracts.control import FetchPlan
    from polisyos.fabric.connectors.base import ConnectionHandle
    from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
    from polisyos.fabric.connectors.sources.file_tabular import FileTabularConnector
    from polisyos.fabric.retrieval.custody import FabricFetchReceipt, _decode_payload
    from polisyos.fabric.retrieval.service import (
        FetchCapturePostflightView,
        FetchCapturePreflightView,
        RetrievalService,
    )
    from polisyos.ir.connectors import FetchRequest, FetchResult
    from polisyos.runtime.http.resilience import guard_runtime_cas
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = guard_runtime_cas(
        FileSystemCAS(tmp_path / "profile-snapshot-cas").for_tenant("tenant-n7", cell_id="cell-a")
    )
    observed_urls: list[str] = []
    observed_snapshots: list[tuple[str, str | None]] = []
    services: list[RetrievalService] = []
    monkeypatch.setenv("POLISYOS_RETRIEVAL_PROMOTION_ENABLED", "1")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        catalog_connector_params=catalog_connector_params,
        publish_current_catalog=True,
    ) as owner:
        profile = owner.providers.profiles.get("recorded_file_local")
        assert profile is not None
        captured_config = resolve_connection_config(profile)
        expected_config_fingerprint = captured_config.cache_scope_fingerprint
        expected_profile_fingerprint = captured_config.source_profile_fingerprint
        assert expected_profile_fingerprint is not None
        alternate_path = tmp_path / "profile-replacement.csv"
        alternate_path.write_text("row_id,value\nprofile-replacement,88.5\n", encoding="utf-8")
        replaced = False

        def _replace_profile() -> None:
            nonlocal replaced
            if replaced:
                return
            owner.providers.profiles.register(
                profile.model_copy(update={"base_url": str(alternate_path)}),
                override=True,
            )
            replaced = True

        original_fetch = FileTabularConnector.fetch

        async def _record_fetch(
            connector: FileTabularConnector,
            handle: ConnectionHandle,
            request: FetchRequest,
        ) -> FetchResult[Any]:
            observed_urls.append(handle.config.url)
            if mutation_point == "between_preview_and_full" and len(observed_urls) == 1:
                _replace_profile()
            return await original_fetch(connector, handle, request)

        monkeypatch.setattr(FileTabularConnector, "fetch", _record_fetch)

        def _catalog_factory(_db_path: Path, _index_dir: Path) -> object:
            return owner.graph

        def _service_factory(curated_dir: Path, store: object, graph: object) -> RetrievalService:
            service = RetrievalService(
                curated_dir=curated_dir,
                artifact_store=store,
                dataset_catalog=graph,
                providers=owner.providers,
            )
            services.append(service)
            original_capture = service.execute_persisted_fetch_capture

            def _observe_snapshot(
                plans: Sequence[FetchPlan],
                *,
                preflight: Callable[[FetchCapturePreflightView], None],
                postflight: Callable[[FetchCapturePostflightView], None],
            ) -> Any:
                def _preflight(view: FetchCapturePreflightView) -> None:
                    observed_snapshots.append(
                        (view.effective_config_fingerprint, view.source_profile_fingerprint)
                    )
                    preflight(view)

                def _postflight(view: FetchCapturePostflightView) -> None:
                    observed_snapshots.append(
                        (view.effective_config_fingerprint, view.source_profile_fingerprint)
                    )
                    postflight(view)

                return original_capture(plans, preflight=_preflight, postflight=_postflight)

            service.execute_persisted_fetch_capture = _observe_snapshot  # type: ignore[method-assign]
            if mutation_point == "after_guard":
                original_execute = service.execute_fetch_plans

                def _replace_after_guard(*args: object, **kwargs: object) -> object:
                    _replace_profile()
                    return original_execute(*args, **kwargs)

                service.execute_fetch_plans = _replace_after_guard  # type: ignore[method-assign]
            return service

        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": f"data-requirement:fetch-capture-profile-snapshot-{mutation_point}",
                "claim_id": f"claim-fetch-capture-profile-snapshot-{mutation_point}",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id=f"run-n7-fetch-capture-profile-snapshot-{mutation_point}",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=_catalog_factory,
            retrieval_service_factory=_service_factory,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        artifact = gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )

        assert artifact is not None
        assert replaced is True
        current_profile = owner.providers.profiles.get("recorded_file_local")
        assert current_profile is not None
        assert current_profile.base_url == str(alternate_path)
        assert (
            resolve_connection_config(current_profile).cache_scope_fingerprint
            != expected_config_fingerprint
        )
        assert observed_urls == [str(owner.csv_path), str(owner.csv_path)]
        assert observed_snapshots == [
            (expected_config_fingerprint, expected_profile_fingerprint),
            (expected_config_fingerprint, expected_profile_fingerprint),
        ]
        assert len(services) == 1
        assert services[0].list_promotion_candidates() == []

        raw_response = artifact.payload["owner_response"]
        assert raw_response["captured_fetch_count"] == 1
        captured = raw_response["captured_fetches"][0]
        assert captured["plan"]["dataset_id"] == str(owner.csv_path)
        payload_ref = artifacts.ArtifactRef.model_validate(captured["payload_ref"])
        receipt_ref = artifacts.ArtifactRef.model_validate(captured["fetch_receipt_ref"])
        receipt = FabricFetchReceipt.model_validate(
            canon.from_canonical_bytes(runtime_store.get_bytes(receipt_ref.artifact_id))
        )
        assert receipt.result.data == payload_ref
        captured_data = _decode_payload(
            runtime_store.get_bytes(payload_ref.artifact_id), receipt.payload_encoding
        )
        assert captured_data["row_id"].tolist() == [f"r-{index}" for index in range(12)]
        assert captured_data["value"].tolist() == [index + 0.5 for index in range(12)]


@pytest.mark.parametrize(
    "mutation_point",
    ["after_guard", "between_preview_and_full", "after_full_before_readback"],
)
def test_real_owner_gateway_capture_refuses_replaced_connector_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation_point: str,
) -> None:
    """A guarded local capture cannot cross into an overridden connector registration."""
    from collections.abc import Callable, Sequence
    from typing import Any

    from polisyos.core.contracts.control import FetchPlan
    from polisyos.fabric.connectors.base import ConnectionHandle
    from polisyos.fabric.connectors.sources.file_tabular import FileTabularConnector
    from polisyos.fabric.retrieval.service import (
        FetchCapturePostflightView,
        FetchCapturePreflightView,
        RetrievalService,
    )
    from polisyos.ir.connectors import FetchRequest, FetchResult
    from tests.unit.fabric.test_retrieval_fetch_custody import build_recorded_file_fetch_owner

    runtime_store = FileSystemCAS(tmp_path / f"registration-snapshot-{mutation_point}-cas")
    observed_urls: list[str] = []
    replacement_factory_calls: list[str] = []
    completed_cas_ids: list[str] = []
    services: list[RetrievalService] = []
    monkeypatch.setenv("POLISYOS_RETRIEVAL_PROMOTION_ENABLED", "1")
    _install_recorded_file_catalog_supplier(monkeypatch)
    with build_recorded_file_fetch_owner(
        tmp_path, canonicalize_catalog_source=True, publish_current_catalog=True
    ) as owner:
        registry = owner.providers.registry
        replaced = False

        def _replacement_factory() -> FileTabularConnector:
            replacement_factory_calls.append("replacement")
            return FileTabularConnector()

        def _replace_registration() -> None:
            nonlocal replaced
            if replaced:
                return
            registry.register(
                FileTabularConnector,
                override=True,
                factory=_replacement_factory,
            )
            replaced = True

        original_fetch = FileTabularConnector.fetch

        async def _record_fetch(
            connector: FileTabularConnector,
            handle: ConnectionHandle,
            request: FetchRequest,
        ) -> FetchResult[Any]:
            result = await original_fetch(connector, handle, request)
            observed_urls.append(handle.config.url)
            if mutation_point == "between_preview_and_full" and len(observed_urls) == 1:
                _replace_registration()
            return result

        monkeypatch.setattr(FileTabularConnector, "fetch", _record_fetch)

        def _catalog_factory(_db_path: Path, _index_dir: Path) -> object:
            return owner.graph

        def _service_factory(curated_dir: Path, store: object, graph: object) -> RetrievalService:
            service = RetrievalService(
                curated_dir=curated_dir,
                artifact_store=store,
                dataset_catalog=graph,
                providers=owner.providers,
            )
            services.append(service)
            original_capture = service.execute_persisted_fetch_capture

            def _capture_explore_lane(
                plans: Sequence[FetchPlan],
                *,
                preflight: Callable[[FetchCapturePreflightView], None],
                postflight: Callable[[FetchCapturePostflightView], None],
            ) -> Any:
                explore_plans = [
                    plan.model_copy(update={"source_lane": "explorelane"}) for plan in plans
                ]
                return original_capture(explore_plans, preflight=preflight, postflight=postflight)

            service.execute_persisted_fetch_capture = _capture_explore_lane  # type: ignore[method-assign]
            if mutation_point == "after_guard":
                original_execute = service.execute_fetch_plans

                def _replace_after_guard(*args: object, **kwargs: object) -> object:
                    _replace_registration()
                    return original_execute(*args, **kwargs)

                service.execute_fetch_plans = _replace_after_guard  # type: ignore[method-assign]
            elif mutation_point == "after_full_before_readback":
                original_execute = service.execute_fetch_plans

                def _replace_after_full(*args: object, **kwargs: object) -> object:
                    outcome: Any = original_execute(*args, **kwargs)
                    for metric in outcome.data_context.metrics:
                        for artifact_ref in (metric.payload_ref, metric.fetch_receipt_ref):
                            if artifact_ref is not None:
                                completed_cas_ids.append(artifact_ref.artifact_id)
                    _replace_registration()
                    return outcome

                service.execute_fetch_plans = _replace_after_full  # type: ignore[method-assign]
            return service

        base_spec = _compiled_requirement_specs()[0].model_dump(mode="json")
        base_spec.update(
            {
                "requirement_id": f"data-requirement:fetch-capture-registration-{mutation_point}",
                "claim_id": f"claim-fetch-capture-registration-{mutation_point}",
                "required_data_families": ("metric.test",),
                "metadata": {
                    "fabric_capture_mode": "persisted_payload",
                    "scope_profile": _catalog_capture_scope_profile(),
                },
            }
        )
        gap = requirement_gaps_from_compiled_specs(data_requirement_specs=(base_spec,))[0]
        report = plan_requirement_gap_acquisition(
            run_id=f"run-n7-fetch-capture-registration-{mutation_point}",
            requirement_gaps=(gap,),
            generated_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        gateway = RealAcquisitionOwnerGateway(
            repo_root=tmp_path,
            dataset_catalog_factory=_catalog_factory,
            retrieval_service_factory=_service_factory,
            artifact_store=runtime_store,
            catalog_run_profile="prod_full",
        )

        artifact = gateway.acquire(
            record=report.acquisition_records[0],
            compiled_requirement_spec=base_spec,
        )

        assert artifact is None
        assert replaced is True
        assert replacement_factory_calls == []
        assert len(services) == 1
        assert services[0].list_promotion_candidates() == []
        assert len(services) == 1
        assert services[0].list_promotion_candidates() == []
        expected_fetches = {
            "after_guard": 0,
            "between_preview_and_full": 1,
            "after_full_before_readback": 2,
        }[mutation_point]
        assert len(observed_urls) == expected_fetches
        if mutation_point == "after_full_before_readback":
            assert len(completed_cas_ids) == 2
            assert all(runtime_store.has(artifact_id) for artifact_id in completed_cas_ids)
        else:
            assert completed_cas_ids == []
            assert runtime_store.iter_artifact_ids() == []
