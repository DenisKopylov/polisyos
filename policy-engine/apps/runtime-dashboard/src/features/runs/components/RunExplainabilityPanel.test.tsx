import { screen } from "@testing-library/react";

import type { RunInspectorSummary } from "@/features/runs/context/RunInspectorContext";
import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import { renderWithProviders } from "@/test/render";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import type { GeneratedProjectionAuthority } from "@/shared/lib/domain/projectionFailClosed";

import { RunExplainabilityPanel } from "./RunExplainabilityPanel";

vi.mock("@/shared/charts", () => ({
  RadarChart: () => <div data-testid="synthetic-evidence-coverage" />,
}));

function summaryFixture(): RunInspectorSummary {
  return {
    artifactRefs: [],
    decisionHeadline: "Owner decision headline",
    decisionScore: untracedDecisionQuantity({
      metricId: "run.decision_score",
      point: null,
    }),
    decisionView: null,
    evidenceContext: {
      dataNeeds: [{ needId: "need-1" }],
      fetchPlans: [{ planId: "plan-1" }],
    },
    governanceIssues: [],
    governanceSummary: {
      blocker: 1,
      info: 0,
      unknown: 0,
      warning: 2,
    },
    impactRows: [],
    pipeline: {
      evaluator: {
        diagnostics: [],
        reasons: ["Owner evaluator reason"],
        verdict: "future_evaluator_verdict",
      },
      preflight: {
        diagnostics: [
          {
            message: "Owner preflight diagnostic",
            severity: "future_preflight_severity",
          },
        ],
        notes: [],
      },
      reproducibility: {
        notes: [],
        readiness: "future_reproducibility_readiness",
        why_partial: [],
      },
    },
    primaryIssue: null,
    run: {
      started_at: "2026-07-22T08:00:00Z",
      status: "future_run_state",
    },
    transportStatus: "future_transport_state",
  } as unknown as RunInspectorSummary;
}

describe("RunExplainabilityPanel authority bindings", () => {
  it("keeps derived explainability summaries diagnostic and reserves recorded provenance for lineage DTOs", () => {
    renderWithProviders(
      <RunExplainabilityPanel level="deep" summary={summaryFixture()} />,
    );

    for (const label of [
      "Evidence needs identified",
      "Evidence collection planned",
      "Analysis executed",
      "Governance review",
    ]) {
      expect(
        screen.getByText(label, { selector: "[data-provenance-source]" }),
      ).toHaveAttribute("data-provenance-source", "diagnostic-summary");
    }
  });

  it("does not synthesize evidence coverage benchmarks or a local conclusion", () => {
    renderWithProviders(
      <RunExplainabilityPanel level="deep" summary={summaryFixture()} />,
    );

    expect(
      screen.queryByTestId("synthetic-evidence-coverage"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Decision concluded")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Decision ready for review."),
    ).not.toBeInTheDocument();
  });

  it("keeps preflight evaluator and reproducibility vocabularies out of decision-grade presentation", () => {
    renderWithProviders(
      <RunExplainabilityPanel level="deep" summary={summaryFixture()} />,
    );

    const ownerLabels = [
      ["Preflight", "future_preflight_severity"],
      ["Evaluator", "future_evaluator_verdict"],
      ["Reproducibility", "future_reproducibility_readiness"],
    ] as const;
    for (const [label, ownerStatus] of ownerLabels) {
      const item = screen.getByRole("button", {
        name: `${label}: ${ownerStatus}`,
      });
      expect(item).not.toHaveAttribute("data-decision-grade-presentation");
    }
  });

  it("does not pass an evaluator verdict through the decision-grade bridge", () => {
    const summary = summaryFixture();
    summary.decisionScore.lineage.status = "verified";
    summary.decisionView = {
      confidence: null,
      diagnosticsBadges: [],
      distributional: null,
      generatedAt: null,
      interventionCount: 0,
      issues: {
        blockedPasses: [],
        blockerCount: null,
        infoCount: null,
        warningCount: null,
      },
      keyMetrics: [],
      metricComparisons: [],
      metricValidationFamilyAdjustment: null,
      policySummary: "Owner policy summary",
      runId: "owner-run",
      sourceKind: "decision_card",
      totalDurationMs: 0,
      verdict: "future_owner_decision_grade",
    } satisfies DecisionCardViewModel;

    renderWithProviders(
      <RunExplainabilityPanel level="glance" summary={summary} />,
    );

    expect(screen.getByText("future_owner_decision_grade")).toHaveAttribute(
      "data-decision-grade-presentation",
      "unrecognized",
    );
    expect(
      screen.queryByText("future_evaluator_verdict"),
    ).not.toBeInTheDocument();
    expect(screen.getByText("unrecognized")).toBeVisible();
  });

  it("preserves producer projection blockers through the rebound blocker card", () => {
    const summary = summaryFixture();
    summary.decisionScore.lineage.status = "verified";
    const projection = {
      authority_role: "projection_only",
      closeout_truth: {
        blockers: [
          {
            code: "future_owner_blocker",
            message: "Owner-supplied blocker message",
            severity: "future_owner_severity",
          },
        ],
        can_closeout: false,
        status: "future_owner_status",
        verdict: "future_owner_verdict",
      },
      evidence_class: "future_owner_evidence_class",
      generated_at: "2026-07-22T08:00:00Z",
      may_not_be_used_for: ["runtime_closeout_authority"],
      primary_state: "future_owner_primary_state",
      projection_policy: "reads_policy_design_case_only",
      provenance_kind: "runtime_projection",
      states: ["future_owner_projection_state"],
      surface: "run_explainability",
    } satisfies GeneratedProjectionAuthority;
    summary.run!.policy_design_case_projection = projection;

    renderWithProviders(
      <RunExplainabilityPanel level="summary" summary={summary} />,
    );

    expect(screen.getByTestId("blocker-card")).toHaveAttribute(
      "data-producer-blocker-code",
      "future_owner_blocker",
    );
    expect(screen.getByText("Owner-supplied blocker message")).toBeVisible();
    expect(screen.getByText("future_owner_severity")).toHaveAttribute(
      "data-owner-severity",
      "future_owner_severity",
    );
  });
});
