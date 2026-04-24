from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

from polisyos.scientist.orchestrator.decision_card import (
    Confidence,
    DecisionCard,
    DiagnosticBadge,
    IssuesSummary,
    KeyMetric,
    Verdict,
    _extract_issues_summary,
    _extract_key_metrics,
)


class TestDecisionCard:
    def test_from_packet_deterministic_core_fields(self) -> None:
        packet = self._create_mock_packet()
        card1 = DecisionCard.from_packet(packet)
        card2 = DecisionCard.from_packet(packet)

        assert card1.source_hash == card2.source_hash
        assert card1.verdict == card2.verdict
        assert card1.confidence == card2.confidence
        assert card1.policy_summary == card2.policy_summary
        assert [m.name for m in card1.key_metrics] == [m.name for m in card2.key_metrics]
        assert [badge.label for badge in card1.diagnostic_badges] == [
            badge.label for badge in card2.diagnostic_badges
        ]

    def test_render_markdown_pure(self) -> None:
        card = DecisionCard(
            run_id="test_001",
            generated_at=datetime(2026, 1, 27, 12, 0, 0, tzinfo=UTC),
            verdict=Verdict.APPROVE,
            confidence=Confidence.HIGH,
            policy_summary="Test policy with 2 interventions",
            intervention_count=2,
            key_metrics=[KeyMetric(name="GDP Change", value=0.02, formatted="+2.00", unit="%")],
            diagnostic_badges=[DiagnosticBadge(label="transport:transportable", kind="ok")],
            issues=IssuesSummary(blocker_count=0, warning_count=1, info_count=0),
            total_duration_ms=1234,
        )

        markdown = card.render_markdown()
        assert "# Decision Card: test_001" in markdown
        assert "✅ **APPROVE**" in markdown
        assert "transport:transportable" in markdown
        assert "GDP Change" in markdown
        assert "**Blockers**: 0" in markdown

    def test_confidence_from_blockers(self) -> None:
        assert Confidence.from_blocker_count(0, 0) == Confidence.HIGH
        assert Confidence.from_blocker_count(0, 5) == Confidence.MEDIUM
        assert Confidence.from_blocker_count(1, 0) == Confidence.LOW
        assert Confidence.from_blocker_count(3, 10) == Confidence.LOW

    def test_extract_key_metrics_handles_missing(self) -> None:
        results = {"gdp_change": 0.015}
        metrics = _extract_key_metrics(results)
        assert len(metrics) == 1
        assert metrics[0].name == "GDP Change"
        assert metrics[0].formatted == "+1.50"

    def test_extract_key_metrics_empty_results(self) -> None:
        assert _extract_key_metrics(None) == []
        assert _extract_key_metrics({}) == []

    def test_extract_issues_summary(self) -> None:
        feedback = {
            "verdict": "NEEDS_REVISION",
            "issues": [
                {"severity": "blocker", "pass_id": "schema"},
                {"severity": "blocker", "pass_id": "schema"},
                {"severity": "warning", "pass_id": "budget"},
                {"severity": "info", "pass_id": "quality"},
            ],
        }
        summary = _extract_issues_summary(feedback)
        assert summary.blocker_count == 2
        assert summary.warning_count == 1
        assert summary.info_count == 1
        assert "schema" in summary.blocked_passes

    def test_to_dict_json_serializable(self) -> None:
        card = DecisionCard(
            run_id="test_002",
            generated_at=datetime.now(UTC),
            verdict=Verdict.REJECT,
            confidence=Confidence.LOW,
            policy_summary="Failed policy",
            issues=IssuesSummary(blocker_count=3, warning_count=0, info_count=0),
        )
        data = card.to_dict()
        serialized = json.dumps(data, default=str)
        assert serialized
        assert "REJECT" in serialized

    def _create_mock_packet(self):
        # Use a fixed generated_at to keep DecisionCard deterministic.
        return SimpleNamespace(
            run_id="mock_run_001",
            generated_at="2026-01-27T00:00:00+00:00",
            policy_ir=None,
            simulation_results={"gdp_change": 0.02, "gini_coefficient": 0.35},
            diagnostics_summary={
                "transport_status": "transportable",
                "legal_executed": False,
                "replay_readiness": "partial",
                "human_review_needed": True,
                "uncertainty_available": False,
            },
            feedback={"verdict": "APPROVE", "issues": []},
            evidence_ref=None,
            run_timeline=None,
            validation_trace=None,
        )
