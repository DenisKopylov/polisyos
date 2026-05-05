"""Tests for FreshnessPass."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from polisyos.scientist.governance.passes.freshness_pass import FreshnessPass


class TestFreshnessPass:
    def test_pass_id(self):
        assert FreshnessPass().pass_id == "freshness"

    def test_fresh_data(self, pass_context_factory):
        recent = (datetime.now(UTC) - timedelta(days=5)).isoformat()
        ctx = pass_context_factory(
            state={
                "data_sources": [{"name": "ds1", "last_updated": recent}],
            }
        )
        issues = FreshnessPass().validate(ctx)
        assert len(issues) == 0

    def test_stale_data_warning(self, pass_context_factory):
        old = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        ctx = pass_context_factory(
            state={
                "data_sources": [{"name": "ds1", "last_updated": old}],
            }
        )
        issues = FreshnessPass(warn_after_days=90).validate(ctx)
        assert any(i.code == "FRESHNESS_STALE" for i in issues)

    def test_critical_staleness_blocker(self, pass_context_factory):
        very_old = (datetime.now(UTC) - timedelta(days=400)).isoformat()
        ctx = pass_context_factory(
            state={
                "data_sources": [{"name": "ds1", "last_updated": very_old}],
            }
        )
        issues = FreshnessPass(block_after_days=365).validate(ctx)
        assert any(i.code == "FRESHNESS_CRITICAL" for i in issues)

    def test_no_timestamp(self, pass_context_factory):
        ctx = pass_context_factory(
            state={
                "data_sources": [{"name": "ds1"}],
            }
        )
        issues = FreshnessPass().validate(ctx)
        assert any(i.code == "FRESHNESS_NO_TIMESTAMP" for i in issues)

    def test_knowledge_metadata(self, pass_context_factory):
        old = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        ctx = pass_context_factory(
            state={
                "knowledge_metadata": {"last_updated": old},
            }
        )
        issues = FreshnessPass(warn_after_days=90).validate(ctx)
        assert any(i.code == "FRESHNESS_STALE" for i in issues)
