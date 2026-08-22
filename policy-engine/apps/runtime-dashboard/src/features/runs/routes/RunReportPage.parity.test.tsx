/* eslint-disable testing-library/no-node-access */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { presentRunPaper } from "@/features/runs/domain/runPaperPresentation";
import { decodeRunPaperDom } from "@/test/runPaperDomTwin";
import {
  availableRunPaperCaseFixture,
  runPaperPacketFixture,
} from "@/test/fixtures/runPaper";

const { useAuthzDecisionMock, useRunPaperMock } = vi.hoisted(() => ({
  useAuthzDecisionMock: vi.fn(),
  useRunPaperMock: vi.fn(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthzDecision: () => useAuthzDecisionMock(),
}));

vi.mock("@/features/runs/api/useRunPaper", () => ({
  useRunPaper: (...args: unknown[]) => useRunPaperMock(...args),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import RunReportPage from "./RunReportPage";

function renderPacket(packet = runPaperPacketFixture()) {
  useAuthzDecisionMock.mockReturnValue({
    can: (permission: string) => permission === "runs.review",
    kind: "verified",
  });
  useRunPaperMock.mockReturnValue({
    data: {
      packet,
      rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
    },
    isError: false,
    isLoading: false,
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/runs/run-1/report"]}>
        <Routes>
          <Route path="/runs/:runId/report" element={<RunReportPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function required(container: HTMLElement, selector: string): HTMLElement {
  const element = container.querySelector(selector);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing run paper test region: ${selector}`);
  }
  return element;
}

describe("RunReportPage MACHINE/rendered-DOM parity", () => {
  beforeEach(() => {
    useAuthzDecisionMock.mockReset();
    useRunPaperMock.mockReset();
  });

  it.each([
    {
      name: "typed unavailable case",
      packet: runPaperPacketFixture(),
    },
    {
      name: "available case with every issue kind",
      packet: runPaperPacketFixture({
        case_record: availableRunPaperCaseFixture(),
      }),
    },
  ])(
    "decodes the complete $name DOM to the packet presentation",
    ({ packet }) => {
      const { container } = renderPacket(packet);
      expect(screen.getByTestId("run-paper-document")).toBeInTheDocument();
      expect(decodeRunPaperDom(container)).toEqual(presentRunPaper(packet));
    },
  );

  it.each([
    {
      apply: (container: HTMLElement) => {
        required(container, '[data-run-paper-path="/caseRecord"]').remove();
      },
      name: "removed fact",
    },
    {
      apply: (container: HTMLElement) => {
        const node = required(
          container,
          '[data-run-paper-path="/caseRecord/design_record/record_id"]',
        );
        node.parentElement?.append(node.cloneNode(true));
      },
      name: "duplicate fact",
    },
    {
      apply: (container: HTMLElement) => {
        const node = required(
          container,
          '[data-run-paper-path="/caseRecord/design_record/record_id"]',
        );
        node.setAttribute(
          "data-run-paper-raw",
          JSON.stringify({
            kind: "string",
            path: "/caseRecord/design_record/record_id",
            value: "Недоступно",
          }),
        );
      },
      name: "localized authority fact",
    },
    {
      apply: (container: HTMLElement) => {
        const anchor = document.createElement("a");
        anchor.href = "/api/v1/artifacts/synthetic";
        anchor.textContent = "synthetic";
        required(container, "[data-run-paper-document]").append(anchor);
      },
      name: "synthetic link",
    },
  ])("rejects a rendered $name mutation", ({ apply }) => {
    const packet = runPaperPacketFixture({
      case_record: availableRunPaperCaseFixture(),
    });
    const { container } = renderPacket(packet);
    expect(decodeRunPaperDom(container)).toEqual(presentRunPaper(packet));

    apply(container);

    expect(() => decodeRunPaperDom(container)).toThrow();
  });

  it("requires an empty admitted-link roster to render zero anchors", () => {
    const packet = runPaperPacketFixture({ artifact_links: [] });
    const { container } = renderPacket(packet);
    expect(decodeRunPaperDom(container)).toEqual(presentRunPaper(packet));
    expect(
      screen.getByTestId("run-paper-document").querySelectorAll("a[href]"),
    ).toHaveLength(0);
  });
});
