from __future__ import annotations

import pytest

from tests._helpers.hds_quality import (
    HDS_XFAIL_REASON,
    blocking_codes,
    complete_job_payload,
    scorecard_for,
    sha,
)

HDS_RED_XFAIL = pytest.mark.xfail(strict=True, reason=HDS_XFAIL_REASON)


@HDS_RED_XFAIL
def test_missing_serious_diagnostic_event_blocks_closeout() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            details={
                "diagnostic_event_log_ref": None,
                "diagnostic_events": [],
            }
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "serious_diagnostic_event_missing" in blocking_codes(scorecard)


@HDS_RED_XFAIL
def test_sampled_away_serious_diagnostic_event_blocks_closeout() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            details={
                "diagnostic_event_log_ref": sha("e"),
                "diagnostic_events": [
                    {
                        "event_name": "policy_grounding_matrix.persisted",
                        "severity": "serious",
                        "sampling": {"decision": "sampled_away", "rate": 0.01},
                        "artifact_ref": sha("8"),
                    }
                ],
            }
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "serious_diagnostic_event_sampled_away" in blocking_codes(scorecard)


@HDS_RED_XFAIL
def test_diagnostic_event_ref_must_match_runtime_cas_ref() -> None:
    scorecard = scorecard_for(
        job_payload=complete_job_payload(
            details={
                "policy_grounding_matrix_ref": sha("8"),
                "diagnostic_event_log_ref": sha("e"),
                "diagnostic_events": [
                    {
                        "event_name": "policy_grounding_matrix.persisted",
                        "severity": "serious",
                        "sampling": {"decision": "always_record"},
                        "artifact_ref": sha("9"),
                        "runtime_cas_ref": sha("9"),
                    }
                ],
            }
        )
    )

    assert scorecard["quality_status"] == "fail"
    assert "diagnostic_event_ref_mismatch" in blocking_codes(scorecard)
