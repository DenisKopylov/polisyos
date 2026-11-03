"""Replay compiler and COV planning together without claiming source admission."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.runtime.quality import acquisition_planner as owner
from tests.unit.runtime.quality.test_n7_descriptor_source_join import _compilation, _source_gap


def _cov_gap(*, candidate_id: str = "candidate-source-join") -> owner.AcquisitionRequirementGap:
    return owner.grounding_coverage_requirement_gap(
        candidate_id=candidate_id,
        candidate_content_hash="sha256:" + "1" * 64,
        design_problem_ref="sha256:" + "2" * 64,
        authority_level=owner.AuthorityLevel.RESEARCH,
        issue_codes=("cgf_disposition_missing",),
        evidence_refs=("fixture://grounding-evidence",),
        grounding_report_ref="fixture://grounding-report",
    )


def _inputs():
    labor = _compilation("labor.unemployment_rate", "total_labor_force")
    gdp = _compilation("economic.gdp", "national_economy")
    return {
        "source_gap": _source_gap(),
        "accompanying_requirement_gaps": (_cov_gap(),),
        "specs": (*labor.specs, *gdp.specs),
        "capability_resolutions": (
            *labor.capability_requirement_resolutions,
            *gdp.capability_requirement_resolutions,
        ),
    }


def test_mixed_planner_replays_all_compiler_rows_and_unsatisfied_cov() -> None:
    inputs = _inputs()
    planning = owner._n7_candidate_n5_l1_obligation_gaps(**inputs)
    cov = inputs["accompanying_requirement_gaps"][0]
    source = inputs["source_gap"]
    assert len(planning) == len(inputs["specs"]) + 1
    assert planning[-1] == cov.to_acquisition_gap()
    assert planning[-1].metadata["satisfaction_status"] == "unsatisfied"
    assert planning[-1].metadata["authority_purpose"] == "routing_only"
    selected = [gap for gap in planning if gap.requirement_gap_ref == source.requirement_gap_id]
    assert len(selected) == 1
    assert selected[0].compiled_requirement_ref != source.compiled_requirement_ref
    assert {gap.compiled_requirement_ref for gap in planning[:-1]} == {
        spec.requirement_id for spec in inputs["specs"]
    }
    report = owner.plan_evidence_acquisition(
        run_id="mixed-obligation-component",
        gaps=planning,
        generated_at=datetime(2026, 11, 3, tzinfo=UTC),
    )
    assert owner._n7_candidate_n5_l1_planner_records_match(**inputs, report=report)
    assert report.acquisition_records[-1].requirement_gap_ref == cov.requirement_gap_id
    assert (
        report.acquisition_records[-1].requirement_schema_version == cov.requirement_schema_version
    )
    assert report.acquisition_records[-1].claim_ref == cov.claim_ref

    # A reader must not accept a dropped, duplicated, reordered or altered row.
    records = report.acquisition_records
    for altered in (
        records[:-1],
        (*records, records[-1]),
        (*records[:-2], records[-1], records[-2]),
        (*records[:-1], records[-1].model_copy(update={"claim_ref": "foreign-claim"})),
    ):
        assert not owner._n7_candidate_n5_l1_planner_records_match(
            **inputs, report=report.model_copy(update={"acquisition_records": altered})
        )
    assert not owner._n7_candidate_n5_l1_planner_records_match(
        **{**inputs, "accompanying_requirement_gaps": ()}, report=report
    )
    for changed in (
        {"status": "blocked" if report.status != "blocked" else "pass"},
        {"summary": {**report.summary, "limited": report.summary.get("limited", 0) + 1}},
        {"authority_boundary": {"authoritative_for": ("unverified_claim",)}},
        {"basis_limitation_code": "requirement_basis_not_established_candidate_only"},
    ):
        assert not owner._n7_candidate_n5_l1_planner_records_match(
            **inputs, report=report.model_copy(update=changed)
        )


@pytest.mark.parametrize("fault", ["non_cov", "foreign_candidate", "duplicate", "tampered"])
def test_mixed_projection_refuses_unbound_or_invented_companion(fault: str) -> None:
    inputs = _inputs()
    cov = inputs["accompanying_requirement_gaps"][0]
    if fault == "non_cov":
        accompanying = (inputs["source_gap"],)
    elif fault == "foreign_candidate":
        accompanying = (_cov_gap(candidate_id="foreign-candidate"),)
    elif fault == "duplicate":
        accompanying = (cov, cov)
    else:
        accompanying = (cov.model_copy(update={"claim_ref": "tampered"}),)
    with pytest.raises(ValueError):
        owner._n7_candidate_n5_l1_obligation_gaps(
            **{**inputs, "accompanying_requirement_gaps": accompanying}
        )


def test_mixed_projection_refuses_missing_or_ambiguous_descriptor() -> None:
    inputs = _inputs()
    for altered in (
        {**inputs, "source_gap": _source_gap("global.government_debt")},
        {**inputs, "specs": (*inputs["specs"], inputs["specs"][0])},
    ):
        with pytest.raises(ValueError, match="compiler_join_not_established"):
            owner._n7_candidate_n5_l1_obligation_gaps(**altered)


def test_mixed_projection_permits_no_cov_only_when_caller_establishes_none() -> None:
    inputs = {**_inputs(), "accompanying_requirement_gaps": ()}
    planning = owner._n7_candidate_n5_l1_obligation_gaps(**inputs)
    assert len(planning) == len(inputs["specs"])
    assert all(gap.metadata.get("source") != "cgf_grounding_coverage" for gap in planning)


def test_legacy_loop_refuses_mixed_dispatch_before_any_owner_call() -> None:
    inputs = _inputs()
    report = owner.plan_evidence_acquisition(
        run_id="mixed-standalone-refusal",
        gaps=owner._n7_candidate_n5_l1_obligation_gaps(**inputs),
        generated_at=datetime(2026, 11, 3, tzinfo=UTC),
    )

    class CountingGateway:
        calls = 0

        def acquire(self, **_kwargs: object) -> None:
            self.calls += 1

    gateway = CountingGateway()
    with pytest.raises(
        owner.AcquisitionPlannerBindingError, match="n7_mixed_obligation_dispatch_not_established"
    ):
        owner.run_acquisition_closed_loop(
            run_id=report.run_id,
            acquisition_request={
                "cycle_index": 0,
                "n7_source_join_rule": owner._N7_CANDIDATE_N5_L1_OBLIGATIONS_RULE,
            },
            data_requirement_specs=inputs["specs"],
            world_snapshot=owner.AcquisitionWorldSnapshot(world_ref="world://before"),
            owner_gateway=gateway,
            planner_report=report,
        )
    assert gateway.calls == 0
    assert report.acquisition_records[-1].requirement_gap_ref == (
        inputs["accompanying_requirement_gaps"][0].requirement_gap_id
    )
