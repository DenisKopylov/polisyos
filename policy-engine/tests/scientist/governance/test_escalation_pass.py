"""Tests for EscalationPass."""

from __future__ import annotations

import pytest

from polisyos.scientist.governance.passes.escalation_pass import EscalationPass


class TestEscalationPass:
    def test_pass_id(self):
        assert EscalationPass().pass_id == "escalation"

    def test_low_impact_no_issues(self, pass_context_factory):
        ctx = pass_context_factory(state={"impact_score": 0.3})
        issues = EscalationPass().validate(ctx)
        assert len(issues) == 0

    def test_high_impact_needs_review(self, pass_context_factory):
        ctx = pass_context_factory(state={"impact_score": 0.95})
        issues = EscalationPass().validate(ctx)
        assert any(i.code == "ESCALATION_HUMAN_REVIEW_REQUIRED" for i in issues)

    def test_high_impact_reviewed(self, pass_context_factory):
        ctx = pass_context_factory(state={"impact_score": 0.95, "human_reviewed": True})
        issues = EscalationPass().validate(ctx)
        assert not any(i.code == "ESCALATION_HUMAN_REVIEW_REQUIRED" for i in issues)

    def test_medium_impact_needs_ack(self, pass_context_factory):
        ctx = pass_context_factory(state={"impact_score": 0.85})
        issues = EscalationPass().validate(ctx)
        assert any(i.code == "ESCALATION_ACKNOWLEDGE_REQUIRED" for i in issues)

    def test_critical_conflicts(self, pass_context_factory):
        ctx = pass_context_factory(state={
            "unresolved_conflicts": [{"severity": "critical"}],
        })
        issues = EscalationPass().validate(ctx)
        assert any(i.code == "ESCALATION_CRITICAL_CONFLICTS" for i in issues)

    def test_no_impact_score(self, pass_context_factory):
        ctx = pass_context_factory(state={})
        issues = EscalationPass().validate(ctx)
        assert len(issues) == 0
