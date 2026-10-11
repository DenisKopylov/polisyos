import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import {
  authorityAbstainingRunPaperPacketFixture,
  runPaperPacketFixture,
} from "@/test/fixtures/runPaper";
import { evidenceArtifactRefKey } from "@/shared/lib/domain/evidence";

const {
  downloadRunPaperPacketMock,
  useAuthzDecisionMock,
  useEpochStalenessMock,
  useRunPaperMock,
} = vi.hoisted(() => ({
  downloadRunPaperPacketMock: vi.fn(),
  useAuthzDecisionMock: vi.fn(),
  useEpochStalenessMock: vi.fn(),
  useRunPaperMock: vi.fn(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthzDecision: () => useAuthzDecisionMock(),
}));

vi.mock("@/features/runs/api/useRunPaper", () => ({
  useRunPaper: (...args: unknown[]) => useRunPaperMock(...args),
}));

vi.mock("@/features/runs/api/useEpochStaleness", () => ({
  useEpochStaleness: (...args: unknown[]) => useEpochStalenessMock(...args),
}));

vi.mock("@/features/runs/components/runPaperExport", () => ({
  downloadRunPaperPacket: (...args: unknown[]) =>
    downloadRunPaperPacketMock(...args),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
  useOptionalI18n: () => ({ t: (key: string) => key }),
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
    useEpochStalenessMock.mockReset();
    useRunPaperMock.mockReset();
    downloadRunPaperPacketMock.mockReset();
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.review",
      kind: "verified",
    });
    useEpochStalenessMock.mockReturnValue({ data: undefined });
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
    const identity = within(documentRoot).getByTestId("run-paper-identity");
    const timeSemantics = within(documentRoot).getByTestId(
      "run-paper-time-semantics",
    );
    expect(
      within(identity).queryByTestId("time-semantics-valid-at"),
    ).not.toBeInTheDocument();
    expect(
      within(timeSemantics).getByTestId("time-semantics-valid-at"),
    ).toBeInTheDocument();
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

  it("renders same-blob run-paper profiles as separate selected links", () => {
    const packet = runPaperPacketFixture();
    const original = packet.artifact_links[0];
    if (!original) {
      throw new Error("Fixture must carry a run-paper artifact link");
    }
    const firstProfile = `sha256:${"a".repeat(64)}`;
    const secondProfile = `sha256:${"b".repeat(64)}`;
    const selectedLink = (profile: string) => ({
      artifact_ref: {
        ...original.artifact_ref,
        manifest_profile_sha256: profile,
      },
      href: `/api/v1/artifacts/${original.artifact_ref.artifact_id}?${new URLSearchParams(
        { manifest_profile_sha256: profile },
      ).toString()}`,
      relation: "run_output" as const,
    });
    packet.artifact_links = [
      selectedLink(firstProfile),
      selectedLink(secondProfile),
    ];
    useRunPaperMock.mockReturnValue({
      data: {
        packet,
        rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
      },
      isError: false,
      isLoading: false,
    });

    renderReport();

    const firstLink = packet.artifact_links[0];
    const secondLink = packet.artifact_links[1];
    if (!firstLink || !secondLink) {
      throw new Error("Fixture must carry both selected profile links");
    }
    const firstKey = evidenceArtifactRefKey(firstLink.artifact_ref);
    const secondKey = evidenceArtifactRefKey(secondLink.artifact_ref);
    const expectedProfileByRefKey = new Map([
      [firstKey, firstProfile],
      [secondKey, secondProfile],
    ]);
    const expectedLinkByRefKey = new Map([
      [firstKey, firstLink],
      [secondKey, secondLink],
    ]);
    const artifactRows = within(
      screen.getByTestId("run-paper-document"),
    ).getAllByRole("listitem");
    const renderedProfileRefKeys = artifactRows.flatMap((row) =>
      within(row)
        .queryAllByRole("link")
        .map((link) => link.getAttribute("data-run-paper-artifact-ref-key"))
        .filter((refKey): refKey is string => refKey !== null),
    );
    expect([...renderedProfileRefKeys].sort()).toEqual(
      [firstKey, secondKey].sort(),
    );

    for (const [refKey, expectedProfile] of expectedProfileByRefKey) {
      const expectedLink = expectedLinkByRefKey.get(refKey);
      if (!expectedLink) {
        throw new Error(
          "Fixture must bind each profile key to its source link",
        );
      }
      const matchingRows = artifactRows.flatMap((row) =>
        within(row)
          .queryAllByRole("link")
          .filter(
            (link) =>
              link.getAttribute("data-run-paper-artifact-ref-key") === refKey,
          )
          .map((link) => ({ link, row })),
      );
      expect(matchingRows).toHaveLength(1);
      const selectedRow = matchingRows[0];
      if (!selectedRow) {
        throw new Error("Each selected profile key must resolve to one row");
      }
      const rowProfileLinks = within(selectedRow.row)
        .queryAllByRole("link")
        .filter((link) => link.hasAttribute("data-run-paper-artifact-ref-key"));
      expect(rowProfileLinks).toHaveLength(1);
      expect(rowProfileLinks[0]).toBe(selectedRow.link);
      expect(selectedRow.link).toHaveAttribute("href", expectedLink.href);
      expect(
        within(selectedRow.row).getAllByText(new RegExp(expectedProfile, "u")),
      ).toHaveLength(1);
    }
  });

  it("renders the bound record and each authority-abstaining nonreceipt", () => {
    const packet = authorityAbstainingRunPaperPacketFixture();
    useRunPaperMock.mockReturnValue({
      data: {
        packet,
        rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
      },
      isError: false,
      isLoading: false,
    });

    renderReport();

    const abstaining = screen.getByTestId(
      "run-paper-case-authority-abstaining",
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
