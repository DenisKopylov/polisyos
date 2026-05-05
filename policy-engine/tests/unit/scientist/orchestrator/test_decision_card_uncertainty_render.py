from __future__ import annotations

from polisyos.scientist.orchestrator.decision_card import (
    Confidence,
    DecisionCard,
    IssuesSummary,
    KeyMetric,
    Verdict,
)


def test_render_markdown_includes_ci_table_and_summary() -> None:
    card = DecisionCard(
        run_id="R_card_ci",
        verdict=Verdict.APPROVE,
        confidence=Confidence.HIGH,
        policy_summary="Policy summary",
        key_metrics=[
            KeyMetric(
                name="GDP Growth",
                value=2.5,
                formatted="+2.50",
                unit="%",
                ci_lower=2.1,
                ci_upper=2.9,
                ci_level=0.95,
            )
        ],
        issues=IssuesSummary(blocker_count=0, warning_count=1),
        total_duration_ms=120,
    )

    md = card.render_markdown()

    assert "| Metric | Value | 95% CI |" in md
    assert "[+2.10, +2.90]" in md
    assert "## Uncertainty Summary" in md
    assert "relative width" in md


def test_render_markdown_clips_uncertainty_bar() -> None:
    card = DecisionCard(
        run_id="R_card_clip",
        key_metrics=[
            KeyMetric(
                name="Volatile Metric",
                value=0.1,
                formatted="+0.10",
                ci_lower=-0.9,
                ci_upper=1.1,
                ci_level=0.95,
            )
        ],
    )

    md = card.render_markdown()
    assert "`████████████████████`" in md
