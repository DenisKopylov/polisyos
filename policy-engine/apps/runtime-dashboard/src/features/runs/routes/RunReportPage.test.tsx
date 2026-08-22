import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { runPaperPacketFixture } from "@/test/fixtures/runPaper";

const { downloadRunPaperPacketMock, useAuthzDecisionMock, useRunPaperMock } =
  vi.hoisted(() => ({
    downloadRunPaperPacketMock: vi.fn(),
    useAuthzDecisionMock: vi.fn(),
    useRunPaperMock: vi.fn(),
  }));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthzDecision: () => useAuthzDecisionMock(),
}));

vi.mock("@/features/runs/api/useRunPaper", () => ({
  useRunPaper: (...args: unknown[]) => useRunPaperMock(...args),
}));

vi.mock("@/features/runs/components/runPaperExport", () => ({
  downloadRunPaperPacket: (...args: unknown[]) =>
    downloadRunPaperPacketMock(...args),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/app/providers/TelemetryProvider", () => ({
  useTelemetryReadyMark: vi.fn(),
}));

vi.mock("@/features/runs/context/RunInspectorContext", () => ({
  RunInspectorProvider: ({ children }: { children: React.ReactNode }) =>
    children,
  useRunInspector: () => ({
    artifactRefs: [],
    blockerCount: 0,
    decisionHeadline: "legacy-local-state-must-not-render",
    decisionScore: {},
    governanceIssues: [],
    run: null,
    runDetailsQuery: { isError: false },
    transportStatus: "legacy",
  }),
}));

vi.mock("@/api/hooks/useRunTimeline", () => ({
  useRunTimeline: () => ({ data: { timeline: { events: [] } } }),
}));

vi.mock("@/api/hooks/useRunErrors", () => ({
  useRunErrors: () => ({ data: { errors: [] } }),
}));

import RunReportPage from "./RunReportPage";

function renderReport(entry = "/runs/run-1/report?paper_projection_hash=pin") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/runs/:runId/report" element={<RunReportPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RunReportPage", () => {
  beforeEach(() => {
    window.localStorage.setItem("operator-craft", "DS8_BROWSER_LOCAL_SENTINEL");
    useAuthzDecisionMock.mockReset();
    useRunPaperMock.mockReset();
    downloadRunPaperPacketMock.mockReset();
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.review",
      kind: "verified",
    });
  });

  it("does not mount the paper query before verified review authorization", () => {
    useAuthzDecisionMock.mockReturnValue({ kind: "unknown" });
    const { rerender } = renderReport();
    expect(
      screen.getByTestId("run-paper-access-unsettled"),
    ).toBeInTheDocument();
    expect(useRunPaperMock).not.toHaveBeenCalled();

    useAuthzDecisionMock.mockReturnValue({
      can: () => false,
      kind: "verified",
    });
    rerender(
      <MemoryRouter initialEntries={["/runs/run-1/report"]}>
        <Routes>
          <Route path="/runs/:runId/report" element={<RunReportPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("run-paper-access-denied")).toBeInTheDocument();
    expect(useRunPaperMock).not.toHaveBeenCalled();
  });

  it("renders only packet facts and exports the exact captured bytes", async () => {
    const user = userEvent.setup();
    const packet = runPaperPacketFixture();
    const rawPacketBytes = new TextEncoder().encode(
      ` ${JSON.stringify(packet)}\n`,
    );
    useRunPaperMock.mockReturnValue({
      data: { packet, rawPacketBytes },
      isError: false,
      isLoading: false,
    });

    renderReport();

    const documentRoot = screen.getByTestId("run-paper-document");
    expect(documentRoot).toHaveAttribute("data-print-document", "true");
    expect(documentRoot).toHaveTextContent("artifact_missing");
    expect(documentRoot).toHaveTextContent("producer_missing");
    expect(documentRoot).toHaveTextContent("case-record-not-run-bound");
    expect(documentRoot).toHaveTextContent("team-runtime");
    expect(documentRoot).toHaveTextContent(packet.run.status);
    expect(documentRoot).toHaveTextContent(packet.run.run_terminality);
    expect(documentRoot).toHaveTextContent(packet.projection_hash);
    expect(documentRoot).not.toHaveTextContent("DS8_BROWSER_LOCAL_SENTINEL");
    expect(documentRoot).not.toHaveTextContent(
      "legacy-local-state-must-not-render",
    );
    expect(within(documentRoot).queryAllByRole("button")).toHaveLength(0);
    expect(within(documentRoot).queryAllByRole("textbox")).toHaveLength(0);
    expect(within(documentRoot).queryAllByRole("combobox")).toHaveLength(0);
    expect(within(documentRoot).queryAllByRole("slider")).toHaveLength(0);
    const links = within(documentRoot).getAllByRole("link");
    expect(links).toHaveLength(packet.artifact_links.length);
    expect(links[0]).toHaveAttribute("href", packet.artifact_links[0].href);
    expect(links[0]).toHaveAttribute("data-paper-link-eligible", "true");

    await user.click(
      screen.getByRole("button", { name: "pages.runs.report.exportMachine" }),
    );
    expect(downloadRunPaperPacketMock).toHaveBeenCalledTimes(1);
    expect(downloadRunPaperPacketMock).toHaveBeenCalledWith(
      packet.run.run_id,
      rawPacketBytes,
    );
    expect(useRunPaperMock).toHaveBeenCalledWith(
      "run-1",
      "?paper_projection_hash=pin",
    );
    expect(useRunPaperMock).toHaveBeenCalledTimes(1);
    expect(screen.queryAllByTestId("run-paper-document")).toHaveLength(1);
  });
});
