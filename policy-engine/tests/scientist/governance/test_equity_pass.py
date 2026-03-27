from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.distributional import (
    CohortDimension,
    CohortImpact,
    DimensionBreakdown,
    DistributionalReport,
    ImpactDirection,
    MetricUnit,
    WinnersLosersEntry,
    WinnersLosersTable,
    persist_distributional_report,
)
from polisyos.scientist.governance.passes.base import IssueSeverity, PassContext
from polisyos.scientist.governance.passes.equity_pass import EquityPass
from polisyos.scientist.governance.profiles import ValidationProfile


def _build_report(*, vulnerable_delta: float = -8.0, gini_delta: float = 0.03) -> DistributionalReport:
    breakdown = DimensionBreakdown(
        dimension=CohortDimension.INCOME_QUINTILE,
        dimension_label="Income Quintiles",
        primary_metric="income_change_pct",
        primary_metric_unit=MetricUnit.PERCENT,
        cohorts=[
            CohortImpact(
                cohort_id="Q1",
                cohort_label="Q1",
                population_share=0.5,
                metric_deltas={"income_change_pct": vulnerable_delta},
                impact_direction=ImpactDirection.NEGATIVE,
                is_vulnerable=True,
            ),
            CohortImpact(
                cohort_id="Q5",
                cohort_label="Q5",
                population_share=0.5,
                metric_deltas={"income_change_pct": 2.0},
                impact_direction=ImpactDirection.POSITIVE,
                is_vulnerable=False,
            ),
        ],
        gini_before=0.30,
        gini_after=0.30 + gini_delta,
    )

    winners_losers = WinnersLosersTable(
        winners=[
            WinnersLosersEntry(
                cohort_id="Q5",
                cohort_label="Q5",
                dimension=CohortDimension.INCOME_QUINTILE,
                net_impact=2.0,
                impact_direction=ImpactDirection.POSITIVE,
                population_share=0.3,
            )
        ],
        losers=[
            WinnersLosersEntry(
                cohort_id="Q1",
                cohort_label="Q1",
                dimension=CohortDimension.INCOME_QUINTILE,
                net_impact=vulnerable_delta,
                impact_direction=ImpactDirection.NEGATIVE,
                population_share=0.7,
                is_vulnerable=True,
            )
        ],
        canonical_dimension=CohortDimension.INCOME_QUINTILE,
    )

    return DistributionalReport(
        breakdowns=[breakdown],
        winners_losers=winners_losers,
        overall_gini_before=0.30,
        overall_gini_after=0.30 + gini_delta,
    )


def test_equity_pass_strict_emits_blockers(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    report_ref = persist_distributional_report(store, _build_report())

    ctx = PassContext(
        ir=None,
        state={
            "artifacts_index": {"distributional_report_ref": report_ref},
            "_store": store,
        },
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_equity_strict",
    )

    issues = EquityPass().validate(ctx)

    assert any(issue.code == "EQUITY_GINI_INCREASE" for issue in issues)
    assert any(issue.code == "EQUITY_VULNERABLE_DISPROPORTIONATE" for issue in issues)
    assert any(issue.code == "EQUITY_EXCESSIVE_LOSERS" for issue in issues)
    assert all(issue.severity == IssueSeverity.BLOCKER for issue in issues)


def test_equity_pass_mvp_emits_warning_for_vulnerable_loss() -> None:
    ctx = PassContext(
        ir=None,
        state={"distributional_report": _build_report(gini_delta=0.0)},
        registry_bundle=None,
        profile=ValidationProfile.mvp(),
        run_id="R_equity_mvp",
    )

    issues = EquityPass().validate(ctx)

    assert any(issue.code == "EQUITY_VULNERABLE_DISPROPORTIONATE" for issue in issues)
    assert all(issue.severity == IssueSeverity.WARNING for issue in issues)


def test_equity_pass_without_report_returns_empty() -> None:
    ctx = PassContext(
        ir=None,
        state={},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_equity_none",
    )

    assert EquityPass().validate(ctx) == []


def test_equity_pass_single_non_vulnerable_group_no_disproportionate_issue() -> None:
    """Non-vulnerable cohorts should not trigger EQUITY_VULNERABLE_DISPROPORTIONATE."""
    breakdown = DimensionBreakdown(
        dimension=CohortDimension.INCOME_QUINTILE,
        dimension_label="Income Quintiles",
        primary_metric="income_change_pct",
        primary_metric_unit=MetricUnit.PERCENT,
        cohorts=[
            CohortImpact(
                cohort_id="Q3",
                cohort_label="Q3",
                population_share=0.5,
                metric_deltas={"income_change_pct": -10.0},
                impact_direction=ImpactDirection.NEGATIVE,
                is_vulnerable=False,
            ),
            CohortImpact(
                cohort_id="Q4",
                cohort_label="Q4",
                population_share=0.5,
                metric_deltas={"income_change_pct": 2.0},
                impact_direction=ImpactDirection.POSITIVE,
                is_vulnerable=False,
            ),
        ],
        gini_before=0.30,
        gini_after=0.30,
    )
    winners_losers = WinnersLosersTable(
        winners=[],
        losers=[
            WinnersLosersEntry(
                cohort_id="Q3",
                cohort_label="Q3",
                dimension=CohortDimension.INCOME_QUINTILE,
                net_impact=-10.0,
                impact_direction=ImpactDirection.NEGATIVE,
                population_share=0.3,
                is_vulnerable=False,
            )
        ],
        canonical_dimension=CohortDimension.INCOME_QUINTILE,
    )
    report = DistributionalReport(
        breakdowns=[breakdown],
        winners_losers=winners_losers,
        overall_gini_before=0.30,
        overall_gini_after=0.30,
    )
    ctx = PassContext(
        ir=None,
        state={"distributional_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_equity_single_group",
    )
    issues = EquityPass().validate(ctx)
    assert not any(i.code == "EQUITY_VULNERABLE_DISPROPORTIONATE" for i in issues)


def test_equity_pass_gini_below_threshold_no_issue() -> None:
    """Gini delta below the threshold should NOT trigger EQUITY_GINI_INCREASE."""
    report = _build_report(vulnerable_delta=-1.0, gini_delta=0.019)
    ctx = PassContext(
        ir=None,
        state={"distributional_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_equity_gini_boundary",
    )
    issues = EquityPass().validate(ctx)
    gini_issues = [i for i in issues if i.code == "EQUITY_GINI_INCREASE"]
    assert len(gini_issues) == 0


def test_equity_pass_vulnerable_exactly_at_threshold_no_issue() -> None:
    """Vulnerable loss exactly at threshold (-5.0%) should NOT trigger."""
    report = _build_report(vulnerable_delta=-5.0, gini_delta=0.0)
    ctx = PassContext(
        ir=None,
        state={"distributional_report": report},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_equity_vuln_boundary",
    )
    issues = EquityPass().validate(ctx)
    vuln_issues = [i for i in issues if i.code == "EQUITY_VULNERABLE_DISPROPORTIONATE"]
    assert len(vuln_issues) == 0


def test_equity_pass_invalid_dict_report_returns_empty() -> None:
    """Invalid dict for distributional_report should be silently skipped."""
    ctx = PassContext(
        ir=None,
        state={"distributional_report": {"invalid": True}},
        registry_bundle=None,
        profile=ValidationProfile.strict(),
        run_id="R_equity_bad_dict",
    )
    issues = EquityPass().validate(ctx)
    assert issues == []
