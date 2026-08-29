/* eslint-disable testing-library/no-node-access -- the reported member is React children, not DOM traversal */
import { render, screen } from "@testing-library/react";

import { cycleBoardProjectionPacketFixture } from "@/test/fixtures/depthNCycleBoard";

const {
  cycleBoardMock,
  confidenceLedgerRiskSpendMock,
  useAuthzDecisionMock,
  useConfidenceLedgerRiskSpendMock,
  useDepthNCycleBoardProjectionMock,
} = vi.hoisted(() => ({
  cycleBoardMock: vi.fn(),
  confidenceLedgerRiskSpendMock: vi.fn(),
  useAuthzDecisionMock: vi.fn(),
  useConfidenceLedgerRiskSpendMock: vi.fn(),
  useDepthNCycleBoardProjectionMock: vi.fn(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthzDecision: () => useAuthzDecisionMock(),
}));

vi.mock("@/features/runs/api/useDepthNCycleBoardProjection", () => ({
  useDepthNCycleBoardProjection: () => useDepthNCycleBoardProjectionMock(),
}));

vi.mock("@/features/runs/api/useConfidenceLedgerRiskSpend", () => ({
  useConfidenceLedgerRiskSpend: () => useConfidenceLedgerRiskSpendMock(),
}));

vi.mock("@/features/runs/components/CycleBoard", () => ({
  CycleBoard: (props: {
    projection: { packet: { intended_audiences: string[] } };
  }) => {
    cycleBoardMock(props);
    return (
      <section
        data-audiences={props.projection.packet.intended_audiences.join(",")}
        data-testid="cycle-board"
      >
        Cycle Board
      </section>
    );
  },
}));

vi.mock("@/features/runs/components/ConfidenceLedgerRiskSpend", () => ({
  ConfidenceLedgerRiskSpend: (props: { projection: unknown }) => {
    confidenceLedgerRiskSpendMock(props);
    return (
      <section data-testid="confidence-ledger-risk-spend">Risk spend</section>
    );
  },
}));

vi.mock("@/shared/components/ErrorBoundary", async () => {
  const React = await import("react");
  class TestPanelErrorBoundary extends React.Component<
    { body: string; children: React.ReactNode; title: string },
    { failed: boolean }
  > {
    state = { failed: false };

    static getDerivedStateFromError() {
      return { failed: true };
    }

    render() {
      return this.state.failed ? (
        <section>
          {this.props.title}: {this.props.body}
        </section>
      ) : (
        this.props.children
      );
    }
  }
  return { PanelErrorBoundary: TestPanelErrorBoundary };
});

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import CycleBoardPage from "./CycleBoardPage";

const packet = cycleBoardProjectionPacketFixture();
const projection = { packet, payload: packet.payload };
const riskSpendProjection = {
  capturedResponseBytes: Object.freeze({
    byteLength: 3,
    copy: () => new Uint8Array([1, 2, 3]),
  }),
  packet: {
    absence_reason: "governed confidence-ledger source is absent",
    availability: "artifact_missing",
  },
};

describe("CycleBoardPage authorization boundary", () => {
  beforeEach(() => {
    cycleBoardMock.mockReset();
    confidenceLedgerRiskSpendMock.mockReset();
    useAuthzDecisionMock.mockReset();
    useConfidenceLedgerRiskSpendMock.mockReset();
    useDepthNCycleBoardProjectionMock.mockReset();
    useDepthNCycleBoardProjectionMock.mockReturnValue({
      data: projection,
      error: null,
      isError: false,
      isLoading: false,
    });
    useConfidenceLedgerRiskSpendMock.mockReturnValue({
      data: riskSpendProjection,
      error: null,
      isError: false,
      isLoading: false,
    });
  });

  it("does not mount the query while authorization is unsettled", () => {
    useAuthzDecisionMock.mockReturnValue({ kind: "unknown" });

    render(<CycleBoardPage />);

    expect(
      screen.getByTestId("cycle-board-access-unsettled"),
    ).toBeInTheDocument();
    expect(useDepthNCycleBoardProjectionMock).not.toHaveBeenCalled();
    expect(useConfidenceLedgerRiskSpendMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId("cycle-board")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /export/iu }),
    ).not.toBeInTheDocument();
  });

  it("denies runs.view-only before any query or export mounts", () => {
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.view",
      isWorkspaceAllowed: () => true,
      kind: "verified",
    });

    render(<CycleBoardPage />);

    expect(screen.getByTestId("cycle-board-access-denied")).toBeInTheDocument();
    expect(useDepthNCycleBoardProjectionMock).not.toHaveBeenCalled();
    expect(useConfidenceLedgerRiskSpendMock).not.toHaveBeenCalled();
    expect(screen.queryByTestId("cycle-board")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /export/iu }),
    ).not.toBeInTheDocument();
  });

  it("mounts exactly one board and risk-spend query after runs.review", () => {
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.review",
      isWorkspaceAllowed: () => true,
      kind: "verified",
    });

    render(<CycleBoardPage />);

    expect(useDepthNCycleBoardProjectionMock).toHaveBeenCalledTimes(1);
    expect(useConfidenceLedgerRiskSpendMock).toHaveBeenCalledTimes(1);
    expect(cycleBoardMock).toHaveBeenCalledTimes(1);
    expect(confidenceLedgerRiskSpendMock).toHaveBeenCalledTimes(1);
    expect(cycleBoardMock.mock.calls[0]?.[0]).not.toHaveProperty(
      "acquisitionGrowth",
    );
    expect(screen.getByTestId("cycle-board")).toHaveAttribute(
      "data-audiences",
      "REVIEWER,EXPERT",
    );
    expect(screen.getByTestId("cycle-board")).not.toHaveAttribute(
      "data-audiences",
      expect.stringContaining("PUBLIC"),
    );
  });

  it("keeps the risk-spend sibling rendered while the Cycle Board query is loading", () => {
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.review",
      isWorkspaceAllowed: () => true,
      kind: "verified",
    });
    useDepthNCycleBoardProjectionMock.mockReturnValue({
      data: undefined,
      error: null,
      isError: false,
      isLoading: true,
    });

    render(<CycleBoardPage />);

    expect(screen.getByTestId("confidence-ledger-risk-spend")).toBeVisible();
    expect(screen.queryByTestId("cycle-board")).not.toBeInTheDocument();
  });

  it("keeps the Cycle Board sibling rendered while risk-spend loading fails", () => {
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.review",
      isWorkspaceAllowed: () => true,
      kind: "verified",
    });
    useConfidenceLedgerRiskSpendMock.mockReturnValue({
      data: undefined,
      error: new Error("risk spend failed"),
      isError: true,
      isLoading: false,
    });

    render(<CycleBoardPage />);

    expect(screen.getByTestId("cycle-board")).toBeVisible();
    expect(
      screen.getByText("pages.cycleBoard.confidenceLedger.loadErrorTitle"),
    ).toBeVisible();
    expect(
      screen.queryByTestId("confidence-ledger-risk-spend"),
    ).not.toBeInTheDocument();
  });

  it("contains a risk-spend render exception without blanking the Cycle Board sibling", () => {
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.review",
      isWorkspaceAllowed: () => true,
      kind: "verified",
    });
    confidenceLedgerRiskSpendMock.mockImplementation(() => {
      throw new Error("risk render failed");
    });

    render(<CycleBoardPage />);

    expect(screen.getByTestId("cycle-board")).toBeVisible();
    expect(screen.getByText(/confidenceLedger\.boundaryTitle/iu)).toBeVisible();
  });
});
