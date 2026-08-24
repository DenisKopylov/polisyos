import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import {
  availableRunPaperCaseFixture,
  runPaperPacketFixture,
} from "@/test/fixtures/runPaper";
import { server } from "@/test/msw/server";

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

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("authorizes before human-decision query and mutation", async () => {
    const sourceRef = `sha256:${"a".repeat(64)}`;
    let reads = 0;
    let writes = 0;
    server.use(
      http.get("*/api/v1/runs/:runId/human-decision-gate", () => {
        reads += 1;
        return HttpResponse.json({
          status: "producer_missing",
          reason_codes: ["DS9-DECISION-PRODUCER-MISSING"],
          source_kind: "agent_action_authority",
          source_ref: sourceRef,
        });
      }),
      http.post("*/api/v1/runs/:runId/human-decisions", () => {
        writes += 1;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const entry =
      `/runs/run-1/case?source_kind=agent_action_authority&source_ref=` +
      encodeURIComponent(sourceRef);

    useAuthzDecisionMock.mockReturnValue({ kind: "unknown" });
    const unsettled = renderCase(entry);
    expect(
      screen.getByTestId("case-inspection-access-unsettled"),
    ).toBeInTheDocument();
    await Promise.resolve();
    expect({ reads, writes }).toEqual({ reads: 0, writes: 0 });
    unsettled.unmount();

    useAuthzDecisionMock.mockReturnValue({
      kind: "verified",
      can: () => false,
    });
    const denied = renderCase(entry);
    expect(
      screen.getByTestId("case-inspection-access-denied"),
    ).toBeInTheDocument();
    await Promise.resolve();
    expect({ reads, writes }).toEqual({ reads: 0, writes: 0 });
    denied.unmount();

    useCaseInspectionMock.mockReturnValue({
      data: {
        packet: runPaperPacketFixture(),
        rawPacketBytes: new TextEncoder().encode("{}"),
      },
      isError: false,
      isLoading: false,
    });
    useAuthzDecisionMock.mockReturnValue({
      kind: "verified",
      can: (permission: string) => permission === "runs.review",
    });
    renderCase(entry);
    await waitFor(() => expect(reads).toBe(1));
    expect(writes).toBe(0);
  });

  it("MACHINE export bytes equal the one human-decision response bytes", async () => {
    const sourceRef = `sha256:${"a".repeat(64)}`;
    const packet = {
      status: "producer_missing",
      reason_codes: ["DS9-DECISION-PRODUCER-MISSING"],
      source_kind: "agent_action_authority",
      source_ref: sourceRef,
    };
    const wire = ` ${JSON.stringify(packet)}\n`;
    let reads = 0;
    server.use(
      http.get("*/api/v1/runs/:runId/human-decision-gate", () => {
        reads += 1;
        return new HttpResponse(wire, {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }),
    );
    useCaseInspectionMock.mockReturnValue({
      data: {
        packet: runPaperPacketFixture(),
        rawPacketBytes: new TextEncoder().encode('{"paper":"different"}'),
      },
      isError: false,
      isLoading: false,
    });
    let blob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((value) => {
      blob = value as Blob;
      return "blob:human-decision";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );

    renderCase(
      `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}`,
    );
    const user = userEvent.setup();
    await user.click(
      await screen.findByTestId("human-decision-machine-export"),
    );

    expect(reads).toBe(1);
    expect(downloadRunPaperPacketMock).not.toHaveBeenCalled();
    expect(blob).not.toBeNull();
    const bytes = await new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () =>
        reject(reader.error ?? new Error("Failed to read decision Blob"));
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.readAsArrayBuffer(blob!);
    });
    expect(Array.from(new Uint8Array(bytes))).toEqual(
      Array.from(new TextEncoder().encode(wire)),
    );
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
