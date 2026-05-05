"""Tests for RateLimiterPass."""

from __future__ import annotations

from polisyos.scientist.governance.passes.rate_limiter_pass import RateLimiterPass


class TestRateLimiterPass:
    def test_pass_id(self):
        assert RateLimiterPass().pass_id == "rate_limiter"

    def test_within_limits(self, pass_context_factory):
        ctx = pass_context_factory(
            state={
                "usage": {"llm_calls": 10, "dataset_queries": 50},
            }
        )
        issues = RateLimiterPass().validate(ctx)
        assert len(issues) == 0

    def test_exceeded_limit(self, pass_context_factory):
        ctx = pass_context_factory(
            state={
                "usage": {"llm_calls": 150},
            }
        )
        issues = RateLimiterPass(max_llm_calls=100).validate(ctx)
        assert any(i.code == "RATE_LIMIT_EXCEEDED" for i in issues)

    def test_approaching_limit(self, pass_context_factory):
        ctx = pass_context_factory(
            state={
                "usage": {"llm_calls": 85},
            }
        )
        issues = RateLimiterPass(max_llm_calls=100).validate(ctx)
        assert any(i.code == "RATE_LIMIT_APPROACHING" for i in issues)

    def test_no_usage_data(self, pass_context_factory):
        ctx = pass_context_factory(state={})
        issues = RateLimiterPass().validate(ctx)
        assert len(issues) == 0
