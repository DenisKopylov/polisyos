import {
  metricIdentifiability,
  parseDecisionCardPayload,
} from "@/shared/lib/domain/decision";

describe("decision domain", () => {
  it("preserves every generated identifiability member and rejects extensions as unknown", () => {
    const generatedMembers = [
      "assumed",
      "estimated",
      "identified",
      "unknown",
    ] as const;

    for (const identifiability of generatedMembers) {
      const parsed = parseDecisionCardPayload({
        feedback: { issues: [], verdict: "review" },
        metric_significance: {
          score: { effect_size: { identifiability, point: 0.5 } },
        },
        simulation_results: { score: 0.5 },
      });

      expect(parsed?.keyMetrics[0]?.identifiability).toBe(identifiability);
    }

    const extension = parseDecisionCardPayload({
      feedback: { issues: [], verdict: "review" },
      metric_significance: {
        score: {
          effect_size: {
            identifiability: "novel_owner_extension",
            point: 0.5,
          },
        },
      },
      simulation_results: { score: 0.5 },
    });

    expect(extension?.keyMetrics[0]).not.toHaveProperty("identifiability");
    expect(metricIdentifiability(extension?.keyMetrics[0] ?? {})).toBe(
      "unknown",
    );
  });

  it("parses decision-card payloads with explicit badges and distributional tuples", () => {
    const parsed = parseDecisionCardPayload({
      confidence: "medium",
      diagnostic_badges: [
        { kind: "ok", label: "transport:direct" },
        { kind: "??", label: "custom:unknown" },
        { kind: "warn", label: "warn" },
        { kind: "fail", label: "fail" },
        { kind: "unknown", label: "unknown" },
        { kind: "ok", label: "trimmed-away" },
      ],
      distributional: {
        breakdowns: [
          [
            "Region",
            [
              {
                cohort_label: "North",
                direction: "down",
                is_vulnerable: true,
                population_share: "0.4",
                primary_delta: "-0.6",
              },
              {
                cohort_label: "South",
                direction: "up",
                population_share: "0.6",
                primary_delta: "0.3",
              },
            ],
          ],
        ],
        gini_after: "0.25",
        gini_before: "0.3",
        gini_delta: "-0.05",
        losers_count: "2",
        losers_share: "0.2",
        winners_count: "10",
        winners_share: "0.8",
      },
      generated_at: "2026-03-09T10:00:00Z",
      issues: {
        blocked_passes: ["transport", null],
        blocker_count: "1",
        info_count: "3",
        warning_count: "2",
      },
      key_metrics: [
        {
          ci_level: "0.9",
          ci_lower: "10",
          ci_upper: "15",
          name: "GDP Change",
          unit: "%",
          value: "12.5",
        },
        {
          value: "n/a",
        },
      ],
      intervention_count: "2",
      policy_summary: "Explicit summary",
      run_id: "run-card",
      total_duration_ms: "1200",
      verdict: "approved",
    });

    expect(parsed).toEqual({
      confidence: "MEDIUM",
      diagnosticsBadges: [
        { kind: "ok", label: "transport:direct" },
        { kind: "unknown", label: "custom:unknown" },
        { kind: "warn", label: "warn" },
        { kind: "fail", label: "fail" },
        { kind: "unknown", label: "unknown" },
      ],
      distributional: {
        breakdowns: [
          {
            dimensionLabel: "Region",
            rows: [
              {
                cohortLabel: "North",
                direction: "down",
                isVulnerable: true,
                populationShare: 0.4,
                primaryDelta: -0.6,
              },
              {
                cohortLabel: "South",
                direction: "up",
                isVulnerable: false,
                populationShare: 0.6,
                primaryDelta: 0.3,
              },
            ],
          },
        ],
        giniAfter: 0.25,
        giniBefore: 0.3,
        giniDelta: -0.05,
        losersCount: 2,
        losersShare: 0.2,
        vulnerableLosersCount: 1,
        winnersCount: 10,
        winnersShare: 0.8,
      },
      generatedAt: "2026-03-09T10:00:00Z",
      interventionCount: 2,
      issues: {
        blockedPasses: ["transport"],
        blockerCount: 1,
        infoCount: 3,
        warningCount: 2,
      },
      keyMetrics: [
        {
          ciLevel: 0.9,
          ciLower: 10,
          ciUpper: 15,
          formatted: "+12.50",
          name: "GDP Change",
          unit: "%",
          value: 12.5,
        },
      ],
      metricComparisons: [],
      metricValidationFamilyAdjustment: null,
      policySummary: "Explicit summary",
      runId: "run-card",
      sourceKind: "decision_card",
      totalDurationMs: 1200,
      verdict: "APPROVE",
    });
  });

  it("parses decision-packet payloads with governance-derived summaries", () => {
    const parsed = parseDecisionCardPayload({
      diagnostics_summary: {
        human_review_needed: true,
        legal_executed: false,
        replay_readiness: "incomplete",
        transport_status: "non_transportable",
        uncertainty_available: false,
      },
      distributional: {
        breakdowns: [
          {
            cohorts: [
              {
                cohort_label: "Low income",
                delta: "-0.7",
                impact_direction: "down",
                is_vulnerable: true,
                population_share: "0.2",
              },
              {
                cohort_label: "High income",
                delta: "0.1",
                impact_direction: "up",
                population_share: "0.8",
              },
            ],
            dimension_label: "Income",
          },
        ],
        losers_count: "4",
        losers_share: "0.25",
        overall_gini_after: "0.35",
        overall_gini_before: "0.4",
        overall_gini_delta: "-0.05",
        winners_count: "12",
        winners_share: "0.75",
      },
      feedback: {
        issues: [
          { pass_id: "transport", severity: "blocker" },
          { severity: "warning" },
          { severity: "info" },
        ],
        verdict: "fail",
      },
      generated_at: "2026-03-09T11:00:00Z",
      policy_ir: {
        policy_spec: {
          interventions: [{}, {}],
        },
      },
      run_id: "run-packet",
      run_timeline: {
        summary: {
          duration_ms: "4567",
        },
      },
      simulation_results: {
        custom_metric: 5,
        gdp_change: 0.12,
        unemployment_change: -0.01,
      },
      metric_significance: {
        gdp_change: {
          alpha: 0.05,
          effect_size: {
            identifiability: "assumed",
            method: "bayesian",
            point: 0.12,
          },
          p_adj: 0.01,
          p_value: 0.01,
          significant: true,
          test_label: "DeLong AUC",
        },
      },
      metric_validation_comparisons: [
        {
          alpha: 0.05,
          assumption_warnings: ["paired_test"],
          baseline_model_id: "baseline",
          baseline_value: 0.71,
          candidate_model_id: "candidate",
          candidate_value: 0.76,
          ci_high: 0.08,
          ci_level: 0.95,
          ci_low: 0.01,
          delta_value: 0.05,
          effect_size: 0.05,
          family_id: "holdout_v1:baseline_vs_candidate",
          family_scope: "per_candidate",
          metric_direction: "higher_is_better",
          metric_id: "accuracy",
          p_adj: 0.02,
          p_value: 0.02,
          significant: true,
          statistic: 0.8,
          test_id: "mcnemar_exact",
          test_label: "McNemar exact",
        },
      ],
      metric_validation_family_adjustment: {
        alpha: 0.05,
        dependency_assumption: "arbitrary",
        error_rate_target: "FWER",
        hypotheses_total: 1,
        method: "holm",
      },
      uncertainty_bounds: {
        gdp_change_ci_level: 0.95,
        gdp_change_lower: 0.1,
        gdp_change_upper: 0.14,
      },
    });

    expect(parsed).toEqual({
      confidence: "LOW",
      diagnosticsBadges: [
        { kind: "fail", label: "transport:non_transportable" },
        { kind: "warn", label: "legal:not_run" },
        { kind: "fail", label: "replay:incomplete" },
        { kind: "warn", label: "human-review:required" },
        { kind: "warn", label: "uncertainty:not_available" },
      ],
      distributional: {
        breakdowns: [
          {
            dimensionLabel: "Income",
            rows: [
              {
                cohortLabel: "Low income",
                direction: "down",
                isVulnerable: true,
                populationShare: 0.2,
                primaryDelta: -0.7,
              },
              {
                cohortLabel: "High income",
                direction: "up",
                isVulnerable: false,
                populationShare: 0.8,
                primaryDelta: 0.1,
              },
            ],
          },
        ],
        giniAfter: 0.35,
        giniBefore: 0.4,
        giniDelta: -0.05,
        losersCount: 4,
        losersShare: 0.25,
        vulnerableLosersCount: 1,
        winnersCount: 12,
        winnersShare: 0.75,
      },
      generatedAt: "2026-03-09T11:00:00Z",
      interventionCount: 2,
      issues: {
        blockedPasses: ["transport"],
        blockerCount: 1,
        infoCount: 1,
        warningCount: 1,
      },
      keyMetrics: [
        {
          ciLevel: 0.95,
          ciLower: 0.1,
          ciUpper: 0.14,
          alpha: 0.05,
          effectSize: 0.12,
          formatted: "+12.00",
          identifiability: "assumed",
          name: "GDP Change",
          pAdj: 0.01,
          pValue: 0.01,
          significant: true,
          testLabel: "DeLong AUC",
          uncertaintyMethod: "bayesian",
          unit: "%",
          value: 12,
        },
        {
          ciLevel: null,
          ciLower: null,
          ciUpper: null,
          formatted: "-1.00",
          name: "Unemployment Change",
          unit: "%",
          value: -1,
        },
      ],
      metricComparisons: [
        {
          alpha: 0.05,
          assumptionWarnings: ["paired_test"],
          baselineModelId: "baseline",
          baselineValue: 0.71,
          calibrationWarnings: [],
          candidateModelId: "candidate",
          candidateValue: 0.76,
          ciHigh: 0.08,
          ciLevel: 0.95,
          ciLow: 0.01,
          deltaValue: 0.05,
          effectSize: 0.05,
          familyId: "holdout_v1:baseline_vs_candidate",
          familyScope: "per_candidate",
          id: "baseline:candidate:accuracy:0",
          metricDirection: "higher_is_better",
          metricId: "accuracy",
          metricLabel: "Accuracy",
          pAdj: 0.02,
          pValue: 0.02,
          resamplingMethod: null,
          sampleSizeEffective: null,
          significant: true,
          statistic: 0.8,
          testId: "mcnemar_exact",
          testLabel: "McNemar exact",
        },
      ],
      metricValidationFamilyAdjustment: {
        alpha: 0.05,
        dependencyAssumption: "arbitrary",
        errorRateTarget: "FWER",
        hypothesesTotal: 1,
        method: "holm",
      },
      policySummary: "Policy with 2 intervention(s)",
      runId: "run-packet",
      sourceKind: "decision_packet",
      totalDurationMs: 4567,
      verdict: "REJECT",
    });
  });

  it("falls back to inferred confidence, metrics, and policy summaries", () => {
    const parsed = parseDecisionCardPayload({
      feedback: {
        issues: [{ severity: "warning" }],
        verdict: "pass",
      },
      policy_ir: {},
      run_id: "run-fallback",
      simulation_results: {
        custom_score: 1.25,
        schema_version: "v1",
      },
    });

    expect(parsed).toMatchObject({
      confidence: "MEDIUM",
      keyMetrics: [
        {
          formatted: "+1.25",
          name: "Custom Score",
          value: 1.25,
        },
      ],
      policySummary: "Policy data attached",
      verdict: "APPROVE",
    });
    expect(parseDecisionCardPayload({ run_id: "no-shape" })).toBeNull();
    expect(parseDecisionCardPayload(null)).toBeNull();
  });
});
