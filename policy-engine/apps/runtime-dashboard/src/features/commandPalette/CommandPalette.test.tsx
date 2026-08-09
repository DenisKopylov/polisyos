import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { mockRuntimeGetFailure, mockRuntimeGetSuccess } from "@/test/runtimeApi";

const {
  cycleDensityMock,
  locationPathnameMock,
  navigateMock,
  toggleThemeMock,
  useFeatureFlagsMock,
  useGlobalShortcutMock,
  useMaybeAuthzMock,
} = vi.hoisted(() => ({
  cycleDensityMock: vi.fn(),
  locationPathnameMock: vi.fn(),
  navigateMock: vi.fn(),
  toggleThemeMock: vi.fn(),
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

vi.mock("@/app/authz/AuthzProvider", () => ({
  useMaybeAuthz: () => useMaybeAuthzMock(),
}));

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  useFeatureFlags: () => useFeatureFlagsMock(),
}));

vi.mock("@polisyos/atlas-ui", () => ({
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

import { CommandPalette } from "./CommandPalette";

const ownerCapabilityManifest = {
  meta: {
    generated_at: "2026-08-09T00:00:00Z",
    request_id: "command-palette-owner-manifest",
    source_kinds: ["core_run"],
  },
  runtime_api_version: "2.0.0",
  shell_flavor: "atlas",
  default_execution_profile: "dev",
  default_locale: "en",
  supported_execution_profiles: ["dev"],
  supported_locales: ["en"],
  state_store_backend: "sqlite",
  worker_backend: "embedded",
  workspaces: [],
  features: [
    {
      key: "evaluator_reports",
      label: "Evaluator reports",
      description: "Owner-issued enabled capability.",
      category: "governance",
      enabled: true,
      stage: "active",
    },
    {
      key: "promotion_lane",
      label: "Promotion lane",
      description: "Owner-issued disabled capability.",
      category: "evidence",
      enabled: false,
      stage: "deferred",
    },
    {
      key: "source_profiles",
      label: "Source profiles",
      description: "Owner-issued enabled capability.",
      category: "evidence",
      enabled: true,
      stage: "active",
    },
  ],
  constraints: {},
};

function renderCommandPalette() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <CommandPalette />
    </QueryClientProvider>,
  );
}

describe("CommandPalette", () => {
  beforeEach(() => {
    cycleDensityMock.mockReset();
    locationPathnameMock.mockReset();
    navigateMock.mockReset();
    toggleThemeMock.mockReset();
    useFeatureFlagsMock.mockReset();
    useGlobalShortcutMock.mockReset();
    useMaybeAuthzMock.mockReset();
    locationPathnameMock.mockReturnValue("/runs/run-1/overview");
    mockRuntimeGetSuccess(ownerCapabilityManifest);
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

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("routes theme toggles through the theme provider", async () => {
    const user = userEvent.setup();
    renderCommandPalette();

    await user.click(
      screen.getByRole("button", { name: /commandPalette\.toggleTheme/i }),
    );

    expect(toggleThemeMock).toHaveBeenCalledTimes(1);
  });

  it("routes density cycling through the density provider", async () => {
    const user = userEvent.setup();
    renderCommandPalette();

    await user.click(
      screen.getByRole("button", { name: /commandPalette\.cycleDensity/i }),
    );

    expect(cycleDensityMock).toHaveBeenCalledTimes(1);
  });

  it("opens contextual run surfaces from the surface registry", async () => {
    const user = userEvent.setup();
    renderCommandPalette();

    await user.click(
      screen.getByRole("button", { name: /pages\.runs\.tabs\.causal/i }),
    );

    expect(navigateMock).toHaveBeenCalledWith("/runs/run-1/causal");
  });

  it("opens nested workspace surfaces from the surface registry", async () => {
    const user = userEvent.setup();
    renderCommandPalette();

    await user.click(
      await screen.findByRole("button", {
        name: /surfaceRegistry\.panels\.freshnessBraid\.label/i,
      }),
    );

    expect(navigateMock).toHaveBeenCalledWith(
      "/evidence?runId=run-1&surface=freshness-braid",
    );
  });

  it("makes registered aliases searchable in command values", async () => {
    renderCommandPalette();

    expect(
      await screen.findByRole("button", {
        name: /surfaceRegistry\.panels\.freshnessBraid\.label/i,
      }),
    ).toHaveAttribute("data-value", expect.stringContaining("source lag"));
  });

  it("hides contextual run surfaces outside a run route", () => {
    locationPathnameMock.mockReturnValue("/runs");

    renderCommandPalette();

    expect(
      screen.queryByRole("button", { name: /pages\.runs\.tabs\.causal/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps fixed surfaces visible while loading capability discovery hides gates", () => {
    mockRuntimeGetFailure(500, {
      code: "capabilities_unavailable",
      detail: "Capability manifest is unavailable",
      status: 500,
    });

    renderCommandPalette();

    expect(
      screen.getByRole("button", { name: /pages\.runs\.tabs\.causal/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /pages\.runs\.tabs\.governance/i }),
    ).not.toBeInTheDocument();
  });

  it("shows only capability-required entries enabled by owner discovery", async () => {
    renderCommandPalette();

    expect(
      await screen.findByRole("button", {
        name: /pages\.runs\.tabs\.governance/i,
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /pages\.runs\.tabs\.evidence/i }),
    ).not.toBeInTheDocument();
  });
});
