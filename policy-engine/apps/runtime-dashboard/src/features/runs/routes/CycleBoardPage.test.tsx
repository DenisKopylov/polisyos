import { render, screen } from "@testing-library/react";

import { cycleBoardProjectionPacketFixture } from "@/test/fixtures/depthNCycleBoard";

const {
  cycleBoardMock,
  useAuthzDecisionMock,
  useDepthNCycleBoardProjectionMock,
} = vi.hoisted(() => ({
  cycleBoardMock: vi.fn(),
  useAuthzDecisionMock: vi.fn(),
  useDepthNCycleBoardProjectionMock: vi.fn(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthzDecision: () => useAuthzDecisionMock(),
}));

vi.mock("@/features/runs/api/useDepthNCycleBoardProjection", () => ({
  useDepthNCycleBoardProjection: () => useDepthNCycleBoardProjectionMock(),
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

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

import CycleBoardPage from "./CycleBoardPage";

const packet = cycleBoardProjectionPacketFixture();
const projection = { packet, payload: packet.payload };

describe("CycleBoardPage authorization boundary", () => {
  beforeEach(() => {
    cycleBoardMock.mockReset();
    useAuthzDecisionMock.mockReset();
    useDepthNCycleBoardProjectionMock.mockReset();
    useDepthNCycleBoardProjectionMock.mockReturnValue({
      data: projection,
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
    expect(screen.queryByTestId("cycle-board")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /export/iu }),
    ).not.toBeInTheDocument();
  });

  it("mounts exactly one REVIEWER/EXPERT board query after runs.review", () => {
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.review",
      isWorkspaceAllowed: () => true,
      kind: "verified",
    });

    render(<CycleBoardPage />);

    expect(useDepthNCycleBoardProjectionMock).toHaveBeenCalledTimes(1);
    expect(cycleBoardMock).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("cycle-board")).toHaveAttribute(
      "data-audiences",
      "REVIEWER,EXPERT",
    );
    expect(screen.getByTestId("cycle-board")).not.toHaveAttribute(
      "data-audiences",
      expect.stringContaining("PUBLIC"),
    );
  });
});
