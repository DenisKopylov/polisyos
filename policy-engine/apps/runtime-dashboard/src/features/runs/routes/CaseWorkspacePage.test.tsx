import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import {
  availableRunPaperCaseFixture,
  authorityAbstainingRunPaperPacketFixture,
  runPaperPacketFixture,
} from "@/test/fixtures/runPaper";
import { server } from "@/test/msw/server";
import {
  availableHumanDecisionGate,
  humanDecisionReviewEffectivenessFixture,
  humanDecisionSourceRef,
  producerMissingHumanDecisionGate,
} from "@/test/fixtures/humanDecision";

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
    server.use(
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () => HttpResponse.json(humanDecisionReviewEffectivenessFixture()),
      ),
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("authorizes before human-decision query and mutation", async () => {
    const sourceRef = humanDecisionSourceRef;
    let reads = 0;
    let writes = 0;
    server.use(
      http.get("*/api/v1/runs/:runId/human-decision-gate", () => {
        reads += 1;
        return HttpResponse.json(producerMissingHumanDecisionGate());
      }),
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () => HttpResponse.json(humanDecisionReviewEffectivenessFixture()),
      ),
      http.post("*/api/v1/runs/:runId/human-decisions", () => {
        writes += 1;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    const entry =
      `/runs/run-1/case?source_kind=agent_action_authority&source_ref=` +
      `${encodeURIComponent(sourceRef)}&action_kind=data_request`;

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
    const sourceRef = humanDecisionSourceRef;
    const packet = producerMissingHumanDecisionGate();
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
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () => HttpResponse.json(humanDecisionReviewEffectivenessFixture()),
      ),
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
      `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(sourceRef)}&action_kind=data_request`,
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

  it("downloads verified evidence bytes before revalidating the action gate", async () => {
    const digest =
      "sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824";
    const opened = availableHumanDecisionGate();
    opened.decision_request!.five_rights_binding.required_information_refs = [
      digest,
    ];
    opened.exposure.required_artifact_digests = [
      opened.continuation!.basis_digest,
      digest,
    ];
    opened.exposure.completed_artifact_digests = [
      opened.continuation!.basis_digest,
      digest,
    ];
    const blocked = structuredClone(opened);
    blocked.exposure.completed_artifact_digests = [
      blocked.continuation!.basis_digest,
    ];
    blocked.status = "blocked";
    blocked.reasons = [
      {
        code: "DS9-EVIDENCE-EXPOSURE-INCOMPLETE",
        message: "Evidence must be opened.",
        status: "blocked",
      },
    ];
    blocked.reason_codes = ["DS9-EVIDENCE-EXPOSURE-INCOMPLETE"];
    blocked.submission = null;
    const events: string[] = [];
    let gateReads = 0;
    server.use(
      http.get("*/api/v1/runs/:runId/human-decision-gate", () => {
        gateReads += 1;
        if (gateReads > 1) events.push("revalidate");
        return HttpResponse.json(gateReads === 1 ? blocked : opened);
      }),
      http.get(
        "*/api/v1/runs/:runId/human-decision-evidence/:digest/content",
        () => {
          events.push("evidence");
          return new HttpResponse("hello", {
            headers: {
              "Cache-Control": "no-store",
              "Content-Encoding": "identity",
              "Content-Type": "text/plain",
              ETag: `"${digest}"`,
              "X-Content-Type-Options": "nosniff",
              "X-PolicyOS-Exposure-Session":
                opened.exposure.exposure_session_ref!,
            },
          });
        },
      ),
      http.get(
        "*/api/v1/runs/:runId/human-decisions/review-effectiveness",
        () => HttpResponse.json(humanDecisionReviewEffectivenessFixture()),
      ),
    );
    useCaseInspectionMock.mockReturnValue({
      data: {
        packet: runPaperPacketFixture(),
        rawPacketBytes: new TextEncoder().encode("{}"),
      },
      isError: false,
      isLoading: false,
    });
    let evidenceBlob: Blob | null = null;
    vi.spyOn(URL, "createObjectURL").mockImplementation((blob) => {
      evidenceBlob = blob as Blob;
      events.push("download");
      return "blob:evidence";
    });
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(
      () => undefined,
    );

    renderCase(
      `/runs/run-1/case?source_kind=agent_action_authority&source_ref=${encodeURIComponent(humanDecisionSourceRef)}&action_kind=data_request`,
    );
    await userEvent
      .setup()
      .click(await screen.findByRole("button", { name: /openEvidence/i }));

    await waitFor(() => expect(gateReads).toBe(2));
    expect(events).toEqual(["evidence", "download", "revalidate"]);
    expect(evidenceBlob).not.toBeNull();
    const bytes = await new Promise<ArrayBuffer>((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () =>
        reject(reader.error ?? new Error("evidence blob read failed"));
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.readAsArrayBuffer(evidenceBlob!);
    });
    expect(new TextDecoder().decode(bytes)).toBe("hello");
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
    expect(useCaseInspectionMock).toHaveBeenCalled();
    expect(
      useCaseInspectionMock.mock.calls.every(
        ([runId, search]) =>
          runId === "run-1" && search === "?paper_projection_hash=pin",
      ),
    ).toBe(true);
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

  it("renders the bound record and each authority-abstaining nonreceipt", () => {
    const packet = authorityAbstainingRunPaperPacketFixture();
    useCaseInspectionMock.mockReturnValue({
      data: {
        packet,
        rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
      },
      isError: false,
      isLoading: false,
    });

    renderCase();

    const abstaining = screen.getByTestId(
      "case-inspection-authority-abstaining",
    );
    for (const value of [
      "case.fixture",
      "binding.fixture",
      "case.design.fixture",
      "run-1",
      "tenant-a",
      "cell-a",
      "abstained",
      `sha256:${"c".repeat(64)}`,
      `sha256:${"9".repeat(64)}`,
      "generation_cycle_grounding_authority",
      "hypothesis_ledger_admission_authority",
      "layer3_g4_promotion_authority",
      "polisyos.runtime.quality.generation_cycle.GroundingStatus",
      "polisyos.runtime.quality.hypothesis_ledger.HypothesisAdmissionState",
      "polisyos.runtime.quality.proving_ground.governed_promotion_gate.Layer3G4PromotionRecord.promotion_state",
      "grounding_state",
      "grounded_case_projection",
      "admission_state",
      "admitted_case_projection",
      "promotion_state",
      "governed_case_projection",
      "available_run_paper_case",
      "not_established",
      "absent/unallocated",
    ]) {
      expect(abstaining).toHaveTextContent(value);
    }
  });
});
