from __future__ import annotations

from polisyos.ir.analytics.diagnostic_dashboard import DiagnosticDashboardData
from polisyos.ir.analytics.survey_raking import SurveyRakingDiagnosticReport


def test_dashboard_includes_raking_convergence_and_weight_stability() -> None:
    report = SurveyRakingDiagnosticReport(
        decision="warn",
        converged=True,
        stop_reason="converged_warn_tolerance",
        n_obs=100,
        population_total=100.0,
        n_sweeps=12,
        max_rel_margin_error=5e-5,
        rms_rel_margin_error=1e-5,
        max_logweight_change=1e-7,
        improvement_ratio_5=1.05,
        monotonicity_share=0.85,
        worst_margin="region",
        worst_category="north",
        ess=42.0,
        ess_fraction=0.42,
        kish_deff=2.38,
        cv_weights=1.18,
        top1_weight_share=0.17,
        top5_weight_share=0.31,
        max_g_weight_ratio=3.4,
        min_g_weight_ratio=0.35,
        structural_zero_count=0,
        sparse_category_count=1,
        vif_lb_max=1.7,
        target_totals={"region=north": 55.0},
        achieved_totals={"region=north": 54.998},
        blocking_reasons=(),
        warnings=("ess_fraction_warn",),
        recommendations=("Review sparse categories.",),
    )

    dashboard = DiagnosticDashboardData.from_node_outputs(
        run_id="run-1",
        query_str="microsim raking",
        node_outputs={"raking": {"diagnostics": report, "result": {}}},
    )

    assert dashboard.raking_convergence is not None
    assert dashboard.weight_stability is not None
    assert dashboard.raking_convergence["decision"] == "warn"
    assert dashboard.weight_stability["ess_fraction"] == 0.42
    assert dashboard.has_weighting_issues is True
    assert dashboard.n_warnings == 1
