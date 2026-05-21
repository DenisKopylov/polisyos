from __future__ import annotations

from polisyos.runtime.quality.consultation import (
    build_consultation_record,
    build_structured_expert_judgement_record,
    validate_consultation_record,
    validate_structured_expert_judgement_record,
)


def test_structured_expert_judgement_requires_judgement_not_data_classification() -> None:
    record = build_structured_expert_judgement_record(
        judgement_id="judgement-1",
        claim_ids=["rec_1"],
        elicitation_method="delphi",
        expert_provenance={
            "expert_id": "expert-1",
            "field": "wartime MSME finance",
            "credential_ref": "sha256:" + "1" * 64,
        },
        conflicts=[],
        uncertainty={"interval": [0.1, 0.4], "confidence": 0.8},
        classification="observed_data",
        evidence_ref="sha256:" + "2" * 64,
    )

    report = validate_structured_expert_judgement_record(record)

    assert report["status"] == "fail"
    assert "expert_judgement_classification_invalid" in {
        issue["code"] for issue in report["issues"]
    }


def test_consultation_record_surfaces_unresolved_objection_legitimacy_blockers() -> None:
    record = build_consultation_record(
        consultation_id="consultation-1",
        stakeholder_map={
            "stakeholders": [
                {"stakeholder_id": "msme", "name": "MSMEs"},
                {"stakeholder_id": "bank", "name": "Participating banks"},
            ]
        },
        consultation_plan={
            "plan_id": "plan-1",
            "comment_period": "2026-05-01/2026-05-14",
        },
        public_comments=[
            {
                "comment_id": "comment-1",
                "stakeholder_id": "bank",
                "summary": "Compliance burden is unresolved.",
            }
        ],
        objection_records=[
            {
                "objection_id": "objection-1",
                "claim_id": "rec_1",
                "severity": "high",
                "status": "unresolved",
                "comment_id": "comment-1",
            }
        ],
        response_to_comment_reasoning=[],
        evidence_ref="sha256:" + "3" * 64,
    )

    report = validate_consultation_record(record)

    assert report["status"] == "fail"
    assert report["summary"]["max_unresolved_objection_severity"] == "high"
    assert "consultation_unresolved_objection_legitimacy_blocker" in {
        issue["code"] for issue in report["issues"]
    }
