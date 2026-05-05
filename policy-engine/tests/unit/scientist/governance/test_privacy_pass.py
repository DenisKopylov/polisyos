from __future__ import annotations

from polisyos.core.governance.passes.base import IssueSeverity
from polisyos.scientist.governance.passes.privacy_pass import PrivacyPass


class TestPrivacyPassPIITier:
    def test_pii_tier_high_warning(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={"pii_tier": "high"},
            profile=strict_profile,
        )
        issues = PrivacyPass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "PII_TIER_HIGH"
        assert issues[0].severity is IssueSeverity.WARNING

    def test_pii_tier_sensitive_warning(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={"pii_tier": "sensitive"},
            profile=strict_profile,
        )
        issues = PrivacyPass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "PII_TIER_HIGH"
        assert issues[0].severity is IssueSeverity.WARNING

    def test_pii_tier_low_no_issues(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={"pii_tier": "low"},
            profile=strict_profile,
        )
        issues = PrivacyPass().validate(ctx)
        assert issues == []

    def test_no_pii_tier_no_issues(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={},
            profile=strict_profile,
        )
        issues = PrivacyPass().validate(ctx)
        assert issues == []


class TestPrivacyPassAccessTier:
    def test_sensitive_access_tier_warning(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={
                "data_view_requests": [{"access_tier": "sensitive"}],
            },
            profile=strict_profile,
        )
        issues = PrivacyPass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "SENSITIVE_ACCESS_TIER"
        assert issues[0].severity is IssueSeverity.WARNING

    def test_unknown_access_tier_warning(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={
                "data_view_requests": [{"access_tier": "top_secret"}],
            },
            profile=strict_profile,
        )
        issues = PrivacyPass().validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "ACCESS_TIER_UNKNOWN"
        assert issues[0].severity is IssueSeverity.WARNING

    def test_public_access_tier_no_issues(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={
                "data_view_requests": [{"access_tier": "public"}],
            },
            profile=strict_profile,
        )
        issues = PrivacyPass().validate(ctx)
        assert issues == []

    def test_empty_requests_no_issues(self, pass_context_factory, strict_profile):
        ctx = pass_context_factory(
            state={"data_view_requests": []},
            profile=strict_profile,
        )
        issues = PrivacyPass().validate(ctx)
        assert issues == []
