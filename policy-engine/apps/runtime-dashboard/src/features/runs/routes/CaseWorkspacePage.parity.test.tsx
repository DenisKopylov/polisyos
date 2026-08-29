/* eslint-disable testing-library/no-container, testing-library/no-node-access */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { presentRunPaper } from "@/features/runs/domain/runPaperPresentation";
import { decodeRunPaperDom } from "@/test/runPaperDomTwin";
import {
  availableRunPaperCaseFixture,
  runPaperPacketFixture,
} from "@/test/fixtures/runPaper";

const {
  useAcquisitionRoutesMock,
  useAuthzDecisionMock,
  useCaseInspectionMock,
} = vi.hoisted(() => ({
  useAcquisitionRoutesMock: vi.fn(),
  useAuthzDecisionMock: vi.fn(),
  useCaseInspectionMock: vi.fn(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthzDecision: () => useAuthzDecisionMock(),
}));

vi.mock("@/features/runs/api/useCaseInspection", () => ({
  useCaseInspection: (...args: unknown[]) => useCaseInspectionMock(...args),
}));

vi.mock("@/features/runs/api/useAcquisitionRoutes", () => ({
  useAcquisitionRoutes: (...args: unknown[]) =>
    useAcquisitionRoutesMock(...args),
}));

vi.mock("@/features/runs/components/AcquisitionApprovalFlow", () => ({
  AcquisitionApprovalFlow: ({ route }: { route: { route_id: string } }) => (
    <div data-testid="acquisition-approval-flow">{route.route_id}</div>
  ),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import CaseWorkspacePage from "./CaseWorkspacePage";

function renderPacket(
  packet = runPaperPacketFixture(),
  routes: readonly { route_id: string }[] = [],
) {
  useAuthzDecisionMock.mockReturnValue({
    can: (permission: string) => permission === "runs.review",
    kind: "verified",
  });
  useCaseInspectionMock.mockReturnValue({
    data: {
      packet,
      rawPacketBytes: new TextEncoder().encode(JSON.stringify(packet)),
    },
    isError: false,
    isLoading: false,
  });
  useAcquisitionRoutesMock.mockReturnValue({
    data: { packet: { routes, run_id: "run-1" } },
    isLoading: false,
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/runs/run-1/case"]}>
        <Routes>
          <Route path="/runs/:runId/case" element={<CaseWorkspacePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function required(container: HTMLElement, selector: string): HTMLElement {
  const element = container.querySelector(selector);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing case workspace test region: ${selector}`);
  }
  return element;
}

describe("CaseWorkspacePage MACHINE/rendered-DOM parity", () => {
  beforeEach(() => {
    useAuthzDecisionMock.mockReset();
    useAcquisitionRoutesMock.mockReset();
    useCaseInspectionMock.mockReset();
  });

  it.each([
    { name: "typed unavailable case", packet: runPaperPacketFixture() },
    {
      name: "available structural witness",
      packet: runPaperPacketFixture({
        case_record: availableRunPaperCaseFixture(),
      }),
    },
  ])("decodes the complete $name DOM from the rendered page", ({ packet }) => {
    const { container } = renderPacket(packet);
    expect(decodeRunPaperDom(container)).toEqual(presentRunPaper(packet));
  });

  it("rejects a removed rendered authority fact", () => {
    const packet = runPaperPacketFixture();
    const { container } = renderPacket(packet);
    expect(decodeRunPaperDom(container)).toEqual(presentRunPaper(packet));

    required(
      container,
      '[data-run-paper-path="/caseRecord/reason_code"]',
    ).remove();

    expect(() => decodeRunPaperDom(container)).toThrow();
  });

  it("rejects a synthetic artifact link", () => {
    const packet = runPaperPacketFixture();
    const { container } = renderPacket(packet);
    const anchor = document.createElement("a");
    anchor.href = "/api/v1/artifacts/synthetic";
    required(container, "[data-run-paper-document]").append(anchor);

    expect(() => decodeRunPaperDom(container)).toThrow(
      /unadmitted or missing link/iu,
    );
  });

  it("preserves the complete run-paper twin beside the acquisition flow", () => {
    const packet = runPaperPacketFixture();
    const { container } = renderPacket(packet, [
      { route_id: "sha256:route-current" },
    ]);

    expect(decodeRunPaperDom(container)).toEqual(presentRunPaper(packet));
    expect(
      container.querySelector("[data-testid='acquisition-approval-flow']"),
    ).not.toBeNull();
  });
});
