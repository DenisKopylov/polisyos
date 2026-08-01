import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const { useRunDetailsMock } = vi.hoisted(() => ({
  useRunDetailsMock: vi.fn(),
}));

vi.mock("@/api/hooks/useRunDetails", () => ({
  useRunDetails: (...args: unknown[]) => useRunDetailsMock(...args),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/shared/telemetry/performance", () => ({
  markUiMilestone: vi.fn(),
  measureUiLatency: vi.fn(),
}));

vi.mock("@/shared/components/FeatureAsyncBoundary", () => ({
  FeatureAsyncBoundary: ({ children }: { children: React.ReactNode }) =>
    children,
}));

vi.mock("@/shared/charts", () => ({
  BSTSVisualization: () => null,
  DiDVisualization: () => <output data-testid="method-visualization" />,
  ForestPlot: () => null,
  MetaLearnerViz: () => null,
  RDDVisualization: () => null,
  SyntheticControlViz: () => null,
}));

vi.mock("@/features/causal", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/causal")>();

  return {
    ...actual,
    AdjustmentSetHighlight: () => null,
    CausalGraphCanvas: ({
      edges,
    }: {
      edges: Array<Record<string, unknown>>;
    }) => (
      <output data-testid="causal-draft-edges">{JSON.stringify(edges)}</output>
    ),
    EdgeDetailPanel: () => null,
    IdentificationOverlay: () => null,
    NodeDetailPanel: () => null,
    PathAnalysisPanel: ({
      paths,
    }: {
      paths: Array<Record<string, unknown>>;
    }) => (
      <output data-testid="causal-draft-paths">{JSON.stringify(paths)}</output>
    ),
    TransportOverlay: () => null,
  };
});

import CausalTab from "./CausalTab";

describe("CausalTab", () => {
  beforeEach(() => {
    window.localStorage.clear();
    useRunDetailsMock.mockReset();
    useRunDetailsMock.mockReturnValue({
      data: { run: { artifacts: [] } },
      isLoading: false,
    });
  });

  it("keeps local causal drafts out of identified effect authority slots", async () => {
    window.localStorage.setItem(
      "polisyos:atlas:causal-draft:run-local",
      JSON.stringify({
        graph: {
          adjustmentSet: [],
          edges: [
            {
              estimate: 0.5,
              id: "treatment-mediator",
              source: "treatment",
              status: "identified",
              target: "mediator",
            },
            {
              estimate: 0.4,
              id: "mediator-outcome",
              source: "mediator",
              status: "identified",
              target: "outcome",
            },
          ],
          methodData: { estimate: 0.5 },
          methodology: "did",
          nodes: [
            { id: "treatment", kind: "treatment", label: "Treatment" },
            { id: "mediator", kind: "mediator", label: "Mediator" },
            { id: "outcome", kind: "outcome", label: "Outcome" },
          ],
          paths: [],
        },
      }),
    );

    render(
      <MemoryRouter initialEntries={["/runs/run-local/causal"]}>
        <Routes>
          <Route path="/runs/:runId/causal" element={<CausalTab />} />
        </Routes>
      </MemoryRouter>,
    );

    const edges = await screen.findByTestId("causal-draft-edges");
    const paths = screen.getByTestId("causal-draft-paths");

    expect(edges).not.toHaveTextContent('"status":"identified"');
    expect(edges).not.toHaveTextContent("estimate");
    expect(paths).not.toHaveTextContent("totalEffect");
    expect(screen.queryByTestId("method-visualization")).not.toBeInTheDocument();
    expect(screen.getByText("phase32.causal.draft")).toBeInTheDocument();
  });
});
