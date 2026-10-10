from __future__ import annotations

from copy import deepcopy

from polisyos.runtime.quality.case_lifecycle import build_lifecycle_reissue_report
from polisyos.runtime.quality.ddm_monitoring import (
    build_implementation_monitoring_evaluation_record,
)
from tests._helpers.hds_quality import policy_design_phase27_records


def test_ddm_foreign_claim_is_visible_to_lifecycle_scope_reconciliation() -> None:
    """A partly matching DDM event is not allowed to hide its outside claim id."""

    source = policy_design_phase27_records()["implementation_monitoring_evaluation"]
    ddm_events = deepcopy(source["ddm_monitoring"])
    ddm_events["shift_events"][0]["affected_claim_ids"] = [
        "rec_1",
        "claim/outside-closed-case",
    ]
    monitoring = build_implementation_monitoring_evaluation_record(
        record_id="implementation-monitoring-scope-reconciliation",
        case_id=source["case_id"],
        claim_ids=source["claim_ids"],
        implementation_contract=source["implementation_contract"],
        monitoring_plan=source["monitoring_plan"],
        evaluation_design=source["evaluation_design"],
        ddm_events=ddm_events,
        publication_authority_ref=source["publication_order"]["publication_authority_ref"],
        created_before_publication_authority=True,
        evidence_ref=source["evidence_ref"],
        runtime_event_ref="event://ddm/scope-reconciliation",
    )

    report = build_lifecycle_reissue_report(
        report_id="lifecycle-ddm-scope-reconciliation",
        case_id=monitoring["case_id"],
        claim_ids=("rec_1", "rec_2"),
        implementation_monitoring_evaluation=monitoring,
    )

    unknown_scope = next(
        issue
        for issue in report["issues"]
        if issue["code"] == "policy_design_lifecycle_event_unknown_claim_scope"
    )
    assert unknown_scope["unknown_claim_ids"] == ["claim/outside-closed-case"]
    states = {row["claim_id"]: row for row in report["claim_revision_states"]}
    assert states["rec_1"]["lifecycle_action"] != "none"
    assert states["rec_2"]["current_validity"] == "current"
    assert report["status"] == "fail"
