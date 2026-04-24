from __future__ import annotations

from unittest.mock import MagicMock

from polisyos.core.governance.passes.base import IssueSeverity
from polisyos.ir.connectors import QualityTier
from polisyos.scientist.governance.passes.quality_gate_pass import QualityGatePass


def _make_freshness(
    *, is_fresh: bool = True, data_age_seconds: int | None = None, message: str = "ok"
):
    f = MagicMock()
    f.is_fresh = is_fresh
    f.data_age_seconds = data_age_seconds
    f.message = message
    return f


def _make_quality_report(
    *,
    tier: QualityTier = QualityTier.GOLD,
    grade: str = "A",
    score: float = 0.95,
    violations: list | None = None,
    is_fresh: bool = True,
    data_age_seconds: int | None = None,
):
    report = MagicMock()
    report.tier = tier
    report.grade = grade
    report.score = score
    report.violations = violations or []
    report.freshness_status = _make_freshness(
        is_fresh=is_fresh,
        data_age_seconds=data_age_seconds,
    )
    return report


def _make_violation(
    *,
    field_name: str = "col_a",
    message: str = "bad value",
    severity: str = "error",
    rule_type: str = "range",
    expected: str = ">0",
    actual: str = "-1",
):
    v = MagicMock()
    v.field_name = field_name
    v.message = message
    v.severity = severity
    v.rule_type = rule_type
    v.expected = expected
    v.actual = actual
    return v


class TestQualityGatePassSkip:
    def test_not_in_profile_and_no_force_run_skips(self, pass_context_factory, fast_profile):
        """FAST profile does not include 'quality' in pass_ids, so skip."""
        ctx = pass_context_factory(state={}, profile=fast_profile)
        issues = QualityGatePass().validate(ctx)
        assert issues == []

    def test_force_run_no_data_warning(self, pass_context_factory, fast_profile):
        """force_run=True with no evidence_bundle or data_quality_report."""
        ctx = pass_context_factory(state={}, profile=fast_profile)
        issues = QualityGatePass(force_run=True).validate(ctx)
        assert len(issues) == 1
        assert issues[0].code == "NO_EVIDENCE_BUNDLE"
        assert issues[0].severity is IssueSeverity.WARNING


class TestQualityGatePassWithQualityReport:
    def test_bronze_strict_blocker(self, pass_context_factory, strict_profile):
        report = _make_quality_report(tier=QualityTier.BRONZE, grade="C", score=0.40)
        ctx = pass_context_factory(
            state={"data_quality_report": report},
            profile=strict_profile,
        )
        issues = QualityGatePass().validate(ctx)
        codes = {i.code for i in issues}
        assert "QUALITY_BRONZE_TIER" in codes
        bronze_issue = next(i for i in issues if i.code == "QUALITY_BRONZE_TIER")
        assert bronze_issue.severity is IssueSeverity.BLOCKER

    def test_bronze_mvp_warning(self, pass_context_factory, mvp_profile):
        report = _make_quality_report(tier=QualityTier.BRONZE, grade="C", score=0.40)
        ctx = pass_context_factory(
            state={"data_quality_report": report},
            profile=mvp_profile,
        )
        # MVP does not have 'quality' in pass_ids, so use force_run
        issues = QualityGatePass(force_run=True).validate(ctx)
        codes = {i.code for i in issues}
        assert "QUALITY_BRONZE_TIER" in codes
        bronze_issue = next(i for i in issues if i.code == "QUALITY_BRONZE_TIER")
        assert bronze_issue.severity is IssueSeverity.WARNING

    def test_stale_data_strict_blocker(self, pass_context_factory, strict_profile):
        report = _make_quality_report(
            is_fresh=False,
            data_age_seconds=86400 * 90,
        )
        report.freshness_status.message = "Data is 90 days old"
        ctx = pass_context_factory(
            state={"data_quality_report": report},
            profile=strict_profile,
        )
        issues = QualityGatePass().validate(ctx)
        staleness_issues = [i for i in issues if i.code == "DATA_STALENESS"]
        assert len(staleness_issues) == 1
        assert staleness_issues[0].severity is IssueSeverity.BLOCKER

    def test_critical_violations_strict_blocker(self, pass_context_factory, strict_profile):
        violation = _make_violation(severity="error", rule_type="range")
        report = _make_quality_report(violations=[violation])
        ctx = pass_context_factory(
            state={"data_quality_report": report},
            profile=strict_profile,
        )
        issues = QualityGatePass().validate(ctx)
        range_issues = [i for i in issues if i.code == "QUALITY_RANGE"]
        assert len(range_issues) == 1
        assert range_issues[0].severity is IssueSeverity.BLOCKER

    def test_good_quality_passes(self, pass_context_factory, strict_profile):
        report = _make_quality_report(
            tier=QualityTier.GOLD,
            grade="A",
            score=0.95,
        )
        ctx = pass_context_factory(
            state={"data_quality_report": report},
            profile=strict_profile,
        )
        issues = QualityGatePass().validate(ctx)
        # No bronze tier, no staleness, no violations -> clean
        assert all(i.code not in {"QUALITY_BRONZE_TIER", "DATA_STALENESS"} for i in issues)


class TestQualityGatePassWithEvidenceBundle:
    def test_unusable_quality_blocker(self, pass_context_factory, strict_profile):
        """Evidence bundle with a metric that computes to UNUSABLE quality."""
        from polisyos.fabric.quality import QualityIndicators, QualityLevel

        indicators = MagicMock(spec=QualityIndicators)
        evidence_bundle = MagicMock()
        evidence_bundle.quality_indicators = {"metric_a": indicators}
        evidence_bundle.sources = []

        # Make MetricFitness.from_indicators return UNUSABLE
        from unittest.mock import patch

        fitness_mock = MagicMock()
        fitness_mock.level = QualityLevel.UNUSABLE
        fitness_mock.fail_reasons = ["Too many nulls", "No variance"]

        with patch(
            "polisyos.scientist.governance.passes.quality_gate_pass.MetricFitness.from_indicators",
            return_value=fitness_mock,
        ):
            ctx = pass_context_factory(
                state={"evidence_bundle": evidence_bundle},
                profile=strict_profile,
            )
            issues = QualityGatePass().validate(ctx)
            codes = {i.code for i in issues}
            assert "QUALITY_UNUSABLE" in codes
            unusable = next(i for i in issues if i.code == "QUALITY_UNUSABLE")
            assert unusable.severity is IssueSeverity.BLOCKER

    def test_invalid_indicator_payload_emits_explicit_issue(
        self,
        pass_context_factory,
        strict_profile,
    ):
        evidence_bundle = MagicMock()
        evidence_bundle.quality_indicators = {"metric_a": {"invalid": True}}
        evidence_bundle.sources = []

        ctx = pass_context_factory(
            state={"evidence_bundle": evidence_bundle},
            profile=strict_profile,
        )

        issues = QualityGatePass().validate(ctx)

        explicit = next(issue for issue in issues if issue.code == "QUALITY_INDICATORS_INVALID")
        assert explicit.severity is IssueSeverity.WARNING
