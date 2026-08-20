import type { ComponentType } from "react";
import { screen } from "@testing-library/react";

import type { RunInspectorSummary } from "@/features/runs/context/RunInspectorContext";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import { renderWithProviders } from "@/test/render";

import { RunExplainabilityPanel } from "./RunExplainabilityPanel";

function summaryFixture(): RunInspectorSummary {
  return {
    artifactRefs: [],
    decisionHeadline: "Diagnostic run headline",
    decisionScore: untracedDecisionQuantity({
      metricId: "run.decision_score",
      point: null,
    }),
    decisionView: null,
    evidenceContext: null,
    governanceIssues: [],
    governanceSummary: null,
    impactRows: [],
    pipeline: null,
    primaryIssue: null,
    run: {
      run_id: "route-run-that-must-not-select-a-domain-row",
      started_at: "2026-07-29T09:00:00Z",
      status: "owner-run-state",
    },
    transportStatus: "owner-transport-state",
  } as unknown as RunInspectorSummary;
}

describe("RunExplainabilityPanel Cycle Board strangle", () => {
  it("ignores the retired governed-projection prop bundle", () => {
    const LegacyCall = RunExplainabilityPanel as ComponentType<{
      cacheObservation?: unknown;
      governedProjection?: unknown;
      projectionError?: boolean;
      projectionLoading?: boolean;
      summary: RunInspectorSummary;
    }>;

    renderWithProviders(
      <LegacyCall
        cacheObservation={{ posture: "stale" }}
        governedProjection={{
          packet: {
            absence_reason: "owner artifact is not present",
            availability: "artifact_missing",
            projection_id: "depth-n-cycle-board",
          },
          payload: null,
        }}
        projectionError
        projectionLoading
        summary={summaryFixture()}
      />,
    );

    expect(
      screen.queryByTestId("governed-depth-projection"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("governed-depth-projection-interaction"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("time-semantics-cache-posture"),
    ).not.toBeInTheDocument();
  });
});
