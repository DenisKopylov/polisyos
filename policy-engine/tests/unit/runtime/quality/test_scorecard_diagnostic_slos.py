from __future__ import annotations

# ruff: noqa: S101
from datetime import UTC, datetime, timedelta

from polisyos.runtime.quality.diagnostic_slos import (
    build_diagnostic_slo_report,
    pass_observations_for_all_diagnostic_slos,
)
from tests._helpers.hds_quality import blocking_codes, complete_quality_evidence, scorecard_for


def test_missing_diagnostic_slo_report_blocks_serious_scorecard_closeout() -> None:
    evidence = complete_quality_evidence()
    evidence.pop("diagnostic_slo_report", None)

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "diagnostic_slo_evidence_missing" in blocking_codes(scorecard)


def test_stale_or_over_budget_diagnostic_slo_report_blocks_serious_scorecard_closeout() -> None:
    now = datetime(2026, 5, 15, 8, 30, tzinfo=UTC)
    observations = pass_observations_for_all_diagnostic_slos(
        observed_at=now,
        evidence_ref="cas://sha256/" + "a" * 64,
    )
    observations["required_runtime_ref_verification_rate"] = {
        "value": 0.8,
        "observed_at": now.isoformat(),
        "evidence_ref": "cas://sha256/" + "b" * 64,
    }
    observations["trace_continuity"] = {
        "value": 1.0,
        "observed_at": (now - timedelta(days=3)).isoformat(),
        "evidence_ref": "cas://sha256/" + "c" * 64,
    }
    evidence = complete_quality_evidence()
    evidence["diagnostic_slo_report"] = build_diagnostic_slo_report(
        observations=observations,
        run_id="R_hds_red_control",
        owner="team-assurance",
        now=now,
    )

    scorecard = scorecard_for(quality_evidence=evidence)

    assert blocking_codes(scorecard) >= {
        "diagnostic_slo_evidence_stale",
        "diagnostic_slo_error_budget_burned",
    }
