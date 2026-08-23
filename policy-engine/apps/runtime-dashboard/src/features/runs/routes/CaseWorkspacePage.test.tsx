import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import {
  availableRunPaperCaseFixture,
  runPaperPacketFixture,
} from "@/test/fixtures/runPaper";

const {
  downloadRunPaperPacketMock,
  useAuthzDecisionMock,
  useCaseInspectionMock,
} = vi.hoisted(() => ({
  downloadRunPaperPacketMock: vi.fn(),
  useAuthzDecisionMock: vi.fn(),
  useCaseInspectionMock: vi.fn(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthzDecision: () => useAuthzDecisionMock(),
}));

vi.mock("@/features/runs/api/useCaseInspection", () => ({
  useCaseInspection: (...args: unknown[]) => useCaseInspectionMock(...args),
}));

vi.mock("@/features/runs/components/runPaperExport", () => ({
  downloadRunPaperPacket: (...args: unknown[]) =>
    downloadRunPaperPacketMock(...args),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import CaseWorkspacePage from "./CaseWorkspacePage";

function renderCase(entry = "/runs/run-1/case?paper_projection_hash=pin") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/runs/:runId/case" element={<CaseWorkspacePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CaseWorkspacePage", () => {
  beforeEach(() => {
    useAuthzDecisionMock.mockReset();
    useCaseInspectionMock.mockReset();
    downloadRunPaperPacketMock.mockReset();
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.review",
      kind: "verified",
    });
  });

  it("authorizes before query", () => {
    useAuthzDecisionMock.mockReturnValue({ kind: "unknown" });
    const { rerender } = renderCase();
    expect(
      screen.getByTestId("case-inspection-access-unsettled"),
    ).toBeInTheDocument();
    expect(useCaseInspectionMock).not.toHaveBeenCalled();

    useAuthzDecisionMock.mockReturnValue({
      can: () => false,
      kind: "verified",
    });
    rerender(
      <MemoryRouter initialEntries={["/runs/run-1/case"]}>
        <Routes>
          <Route path="/runs/:runId/case" element={<CaseWorkspacePage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      screen.getByTestId("case-inspection-access-denied"),
    ).toBeInTheDocument();
    expect(useCaseInspectionMock).not.toHaveBeenCalled();
  });

  it("renders the typed unavailable refusal and exports the captured bytes", async () => {
    const user = userEvent.setup();
    const packet = runPaperPacketFixture();
    const rawPacketBytes = new TextEncoder().encode(
      ` ${JSON.stringify(packet)}\n`,
    );
    useCaseInspectionMock.mockReturnValue({
      data: { packet, rawPacketBytes },
      isError: false,
      isLoading: false,
    });

    renderCase();

    const refusal = screen.getByTestId("case-inspection-unavailable");
    expect(refusal).toHaveTextContent("artifact_missing");
    expect(refusal).toHaveTextContent("producer_missing");
    expect(refusal).toHaveTextContent("case-record-not-run-bound");
    expect(refusal).toHaveTextContent("team-runtime");
    if (packet.case_record.availability !== "artifact_missing") {
      throw new Error("Fixture must carry the typed-unavailable case arm");
    }
    for (const deniedUse of packet.case_record.may_not_use_for) {
      expect(refusal).toHaveTextContent(deniedUse);
    }
    expect(refusal).not.toHaveTextContent(/loading|ready|false/iu);
    expect(screen.getByTestId("case-stage-trace")).toHaveAttribute(
      "id",
      "stage-trace",
    );
    const documentRoot = screen.getByTestId("case-workspace-document");
    expect(documentRoot).not.toHaveAttribute("data-paper-payload");
    expect(documentRoot).not.toHaveAttribute("data-print-document");
    expect(within(documentRoot).getAllByRole("link")).toHaveLength(
      packet.artifact_links.length,
    );

    await user.click(
      screen.getByRole("button", { name: "pages.runs.report.exportMachine" }),
    );
    expect(downloadRunPaperPacketMock).toHaveBeenCalledTimes(1);
    expect(downloadRunPaperPacketMock).toHaveBeenCalledWith(
      packet.run.run_id,
      rawPacketBytes,
    );
    expect(useCaseInspectionMock).toHaveBeenCalledWith(
      "run-1",
      "?paper_projection_hash=pin",
    );
    expect(useCaseInspectionMock).toHaveBeenCalledTimes(1);
  });

  it("keeps available authority states and negative object kinds distinct", () => {
    const packet = runPaperPacketFixture({
      case_record: availableRunPaperCaseFixture(),
    });
    useCaseInspectionMock.mockReturnValue({
      data: {
        packet,
        rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
      },
      isError: false,
      isLoading: false,
    });

    renderCase();

    const available = screen.getByTestId("case-inspection-available");
    expect(available).toHaveTextContent("current_valid");
    expect(available).toHaveTextContent("admitted_to_claim");
    expect(available).toHaveTextContent("governed_promoted");
    for (const kind of ["blocker", "limitation", "objection", "abstention"]) {
      expect(available).toHaveTextContent(`${kind} fixture statement`);
    }
  });
});
