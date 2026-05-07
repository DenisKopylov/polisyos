import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  cycleDensityMock,
  isCapabilityEnabledMock,
  locationPathnameMock,
  navigateMock,
  toggleThemeMock,
  useCapabilitiesMock,
  useFeatureFlagsMock,
  useGlobalShortcutMock,
  useMaybeAuthzMock,
} = vi.hoisted(() => ({
  cycleDensityMock: vi.fn(),
  isCapabilityEnabledMock: vi.fn(),
  locationPathnameMock: vi.fn(),
  navigateMock: vi.fn(),
  toggleThemeMock: vi.fn(),
  useCapabilitiesMock: vi.fn(),
  useFeatureFlagsMock: vi.fn(),
  useGlobalShortcutMock: vi.fn(),
  useMaybeAuthzMock: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    ...actual,
    useLocation: () => ({
      hash: "",
      key: "test",
      pathname: locationPathnameMock(),
      search: "",
      state: null,
    }),
    useNavigate: () => navigateMock,
  };
});

vi.mock("@/api/hooks/useCapabilities", () => ({
  useCapabilities: () => useCapabilitiesMock(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useMaybeAuthz: () => useMaybeAuthzMock(),
}));

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  useFeatureFlags: () => useFeatureFlagsMock(),
}));

vi.mock("@/shared/ui/Command", () => ({
  CommandDialog: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CommandInput: ({ placeholder }: { placeholder?: string }) => (
    <input aria-label={placeholder} />
  ),
  CommandList: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CommandEmpty: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CommandGroup: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  CommandItem: ({
    children,
    onSelect,
    value,
  }: {
    children: React.ReactNode;
    onSelect?: () => void;
    value?: string;
  }) => (
    <button type="button" data-value={value} onClick={onSelect}>
      {children}
    </button>
  ),
  CommandSeparator: () => <hr />,
  CommandShortcut: ({ children }: { children: React.ReactNode }) => (
    <span>{children}</span>
  ),
}));

vi.mock("@/app/providers/ThemeProvider", () => ({
  useTheme: () => ({
    resolvedTheme: "dark",
    toggleTheme: toggleThemeMock,
  }),
}));

vi.mock("@/app/providers/DensityProvider", () => ({
  useDensity: () => ({
    cycleDensity: cycleDensityMock,
    density: "comfortable",
  }),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock("@/shared/lib/hooks", () => ({
  useGlobalShortcut: (...args: unknown[]) => useGlobalShortcutMock(...args),
}));

vi.mock("@/shared/lib/capabilities", () => ({
  isCapabilityEnabled: (...args: unknown[]) => isCapabilityEnabledMock(...args),
}));

import { CommandPalette } from "./CommandPalette";

describe("CommandPalette", () => {
  beforeEach(() => {
    cycleDensityMock.mockReset();
    isCapabilityEnabledMock.mockReset();
    locationPathnameMock.mockReset();
    navigateMock.mockReset();
    toggleThemeMock.mockReset();
    useCapabilitiesMock.mockReset();
    useFeatureFlagsMock.mockReset();
    useGlobalShortcutMock.mockReset();
    useMaybeAuthzMock.mockReset();
    isCapabilityEnabledMock.mockReturnValue(true);
    locationPathnameMock.mockReturnValue("/runs/run-1/overview");
    useCapabilitiesMock.mockReturnValue({ data: undefined, isLoading: false });
    useFeatureFlagsMock.mockReturnValue({
      flags: {
        enableLexKnowledge: true,
        enablePlatformHealth: true,
        enableRunsWorkspace: true,
        enableScenarioComposer: true,
      },
    });
    useMaybeAuthzMock.mockReturnValue({
      can: () => true,
      isWorkspaceAllowed: () => true,
    });
  });

  it("routes theme toggles through the theme provider", async () => {
    const user = userEvent.setup();
    render(<CommandPalette />);

    await user.click(
      screen.getByRole("button", { name: /commandPalette\.toggleTheme/i }),
    );

    expect(toggleThemeMock).toHaveBeenCalledTimes(1);
  });

  it("routes density cycling through the density provider", async () => {
    const user = userEvent.setup();
    render(<CommandPalette />);

    await user.click(
      screen.getByRole("button", { name: /commandPalette\.cycleDensity/i }),
    );

    expect(cycleDensityMock).toHaveBeenCalledTimes(1);
  });

  it("opens contextual run surfaces from the surface registry", async () => {
    const user = userEvent.setup();
    render(<CommandPalette />);

    await user.click(
      screen.getByRole("button", { name: /pages\.runs\.tabs\.causal/i }),
    );

    expect(navigateMock).toHaveBeenCalledWith("/runs/run-1/causal");
  });

  it("opens nested workspace surfaces from the surface registry", async () => {
    const user = userEvent.setup();
    render(<CommandPalette />);

    await user.click(
      screen.getByRole("button", {
        name: /surfaceRegistry\.panels\.freshnessBraid\.label/i,
      }),
    );

    expect(navigateMock).toHaveBeenCalledWith(
      "/evidence?runId=run-1&surface=freshness-braid",
    );
  });

  it("makes registered aliases searchable in command values", () => {
    render(<CommandPalette />);

    expect(
      screen.getByRole("button", {
        name: /surfaceRegistry\.panels\.freshnessBraid\.label/i,
      }),
    ).toHaveAttribute("data-value", expect.stringContaining("source lag"));
  });

  it("hides contextual run surfaces outside a run route", () => {
    locationPathnameMock.mockReturnValue("/runs");

    render(<CommandPalette />);

    expect(
      screen.queryByRole("button", { name: /pages\.runs\.tabs\.causal/i }),
    ).not.toBeInTheDocument();
  });
});
