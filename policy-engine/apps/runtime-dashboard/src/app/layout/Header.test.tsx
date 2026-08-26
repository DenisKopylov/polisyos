import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const { useRunsSampleMock } = vi.hoisted(() => ({
  useRunsSampleMock: vi.fn(),
}));

vi.mock("@/features/runs", () => ({
  useRunsSample: () => useRunsSampleMock(),
}));
vi.mock("@/api/hooks/useCapabilitySearch", () => ({
  createCapabilitySearchRequest: () => ({}),
  useCapabilitySearch: () => ({ data: undefined }),
}));
vi.mock("@/api/hooks/useHealth", () => ({
  useHealth: () => ({
    data: { status: "ok" },
    isError: false,
    isLoading: false,
  }),
}));
vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthzDecision: () => ({
    isWorkspaceAllowed: () => true,
    kind: "verified",
  }),
}));
vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  useFeatureFlags: () => ({ flags: { enableAtlasV2: false } }),
}));
vi.mock("@/app/providers/InterfaceModeProvider", () => ({
  useInterfaceMode: () => ({ isClerk: false, mode: "analyst" }),
}));
vi.mock("@/app/providers/ThemeProvider", () => ({
  useTheme: () => ({ theme: "light", toggleTheme: vi.fn() }),
}));
vi.mock("@/app/providers/RunsLiveProvider", () => ({
  useRunsLiveStatus: () => ({ lastEventAt: null, status: "offline" }),
}));
vi.mock("@/app/workspaces", () => ({
  getWorkspaceNavigationWithOptions: () => [],
  resolveWorkspaceKey: () => "runsDecisions",
  WORKSPACES: {
    runsDecisions: {
      resolveHeader: () => ({
        eyebrowKey: "eyebrow",
        subtitleKey: "subtitle",
        titleKey: "title",
      }),
    },
  },
}));
vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    locale: "en",
    setLocale: vi.fn(),
    t: (key: string) => key,
  }),
}));
vi.mock("@/shared/ui/trust-view", () => ({
  TrustViewToggle: () => null,
}));

import Header from "./Header";

function renderHeader() {
  return render(
    <MemoryRouter initialEntries={["/runs"]}>
      <Header />
    </MemoryRouter>,
  );
}

describe("Header", () => {
  it("does not present a stable review queue when owner facts are absent", () => {
    useRunsSampleMock.mockReturnValue({ data: undefined });

    renderHeader();

    const review = screen.getByText("shell.header.checking", {
      selector: '[data-authority-source="review_required_aggregate"]',
    });
    expect(review).toHaveAttribute(
      "data-authority-recognition",
      "unrecognized",
    );
    expect(review).toHaveTextContent("shell.header.checking");
    expect(
      screen.queryByText("shell.header.queueStable"),
    ).not.toBeInTheDocument();
  });

  it("derives review-required and stable labels from complete owner facts", () => {
    useRunsSampleMock.mockReturnValue({
      data: { runs: [{ decision_review_required: true }] },
    });
    const view = renderHeader();
    let review = screen.getByText("shell.header.runsInReview", {
      selector: '[data-authority-source="review_required_aggregate"]',
    });
    expect(review).toHaveAttribute("data-presentation-tone", "warn");
    expect(review).toHaveTextContent("shell.header.runsInReview");

    useRunsSampleMock.mockReturnValue({
      data: { runs: [{ decision_review_required: false }] },
    });
    view.rerender(
      <MemoryRouter initialEntries={["/runs"]}>
        <Header />
      </MemoryRouter>,
    );
    review = screen.getByText("shell.header.queueStable", {
      selector: '[data-authority-source="review_required_aggregate"]',
    });
    expect(review).toHaveAttribute("data-presentation-tone", "ok");
    expect(review).toHaveTextContent("shell.header.queueStable");
  });
});
