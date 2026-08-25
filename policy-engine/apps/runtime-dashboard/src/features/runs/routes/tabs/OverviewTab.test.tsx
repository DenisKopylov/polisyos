import { screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { renderWithProviders } from "@/test/render";

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useParams: () => ({ runId: "run-1" }) };
});
vi.mock("@/api/hooks/useGovernanceDebug", () => ({
  useSuspenseGovernanceDebug: () => ({
    data: {
      debug: {
        issues: [
          { code: "known", message: "Known blocker", severity: "fail" },
          {
            code: "novel",
            message: "Novel severity",
            severity: "future_owner_severity",
          },
        ],
      },
    },
  }),
}));
vi.mock("@/api/hooks/useRunEvidenceContext", () => ({
  useSuspenseRunEvidenceContext: () => ({ data: { context: {} } }),
}));
vi.mock("@/api/hooks/useRunTimeline", () => ({
  useSuspenseRunTimeline: () => ({ data: { timeline: { events: [] } } }),
}));
vi.mock("@/api/hooks/useArtifactContent", () => ({
  useSuspenseArtifactContent: vi.fn(),
}));
vi.mock("@/app/authz/AuthzProvider", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/app/authz/AuthzProvider")>();
  return { ...actual, usePermission: () => false };
});
vi.mock("@/app/providers/FeatureFlagProvider", async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import("@/app/providers/FeatureFlagProvider")
    >();
  return { ...actual, useFeatureFlag: () => false };
});
vi.mock("@/features/runs/context/RunInspectorContext", () => ({
  useRunInspector: () => ({
    blockerCount: 2,
    decisionHeadline: "Decision",
    evidenceContext: { dataNeeds: [], fetchPlans: [], promotionCandidates: [] },
    primaryDecisionArtifactId: null,
    run: { run_id: "run-1" },
  }),
}));
vi.mock("@/shared/components/FeatureAsyncBoundary", () => ({
  FeatureAsyncBoundary: ({ children }: { children: ReactNode }) => children,
}));
vi.mock("@/features/runs/components/RunExplainabilityPanel", () => ({
  RunExplainabilityPanel: () => null,
}));
vi.mock("@/features/whatif", () => ({ ScenarioWorkbench: () => null }));

import OverviewTab from "./OverviewTab";

describe("OverviewTab", () => {
  it("renders governance severity only through the private issuer", () => {
    renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-governance-severity-known"),
    ).toHaveAttribute("data-authority-recognition", "unrecognized");
    expect(
      screen.getByTestId("overview-governance-severity-known"),
    ).toHaveAttribute("data-presentation-tone", "neutral");
    expect(
      screen.getByTestId("overview-governance-severity-novel"),
    ).toHaveAttribute("data-authority-recognition", "unrecognized");
    expect(
      screen.getByTestId("overview-governance-severity-novel"),
    ).toHaveAttribute("data-presentation-tone", "neutral");
  });
});
