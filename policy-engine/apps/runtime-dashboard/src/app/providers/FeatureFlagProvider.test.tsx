import { render, screen, waitFor } from "@testing-library/react";

import {
  FeatureFlagProvider,
  useFeatureFlag,
  useFeatureFlags,
} from "@/app/providers/FeatureFlagProvider";
import { AuthzProvider, useAuthz } from "@/app/authz/AuthzProvider";
import {
  FEATURE_FLAG_CACHE_TTL_MS,
  FEATURE_FLAG_MANIFEST_CACHE_KEY,
  FEATURE_FLAG_MANIFEST_VERSION,
} from "@/shared/lib/featureFlags";

const { trackMock } = vi.hoisted(() => ({
  trackMock: vi.fn(),
}));

const { useAuthMeMock } = vi.hoisted(() => ({
  useAuthMeMock: vi.fn(),
}));

vi.mock("@/app/providers/TelemetryProvider", () => ({
  useTelemetry: () => ({
    track: trackMock,
  }),
}));

vi.mock("@/api/hooks/useAuthMe", () => ({
  useAuthMe: () => useAuthMeMock(),
}));

function FeatureFlagProbe() {
  const { diagnostic, source, status } = useFeatureFlags();
  const lexEnabled = useFeatureFlag("enableLexKnowledge");
  const composerEnabled = useFeatureFlag("enableScenarioComposer");

  return (
    <div>
      <span data-testid="feature-flag-status">{status.label}</span>
      <span data-testid="feature-flag-source">{source}</span>
      <span data-testid="feature-flag-diagnostic">{diagnostic?.code ?? "none"}</span>
      <span data-testid="feature-flag-lex">{String(lexEnabled)}</span>
      <span data-testid="feature-flag-composer">{String(composerEnabled)}</span>
    </div>
  );
}

function FeatureFlagRenderProbe({ observed }: { observed: boolean[] }) {
  observed.push(useFeatureFlag("enableLexKnowledge"));
  return null;
}

function PermissionFloorProbe() {
  const authz = useAuthz();
  const composerEnabled = useFeatureFlag("enableScenarioComposer");

  return (
    <output>
      {JSON.stringify({
        canLaunch: authz.can("runs.launch"),
        composerEnabled,
      })}
    </output>
  );
}

function renderFeatureFlags(props?: {
  overrides?: Record<string, boolean>;
  remoteUrl?: string;
}) {
  return render(
    <FeatureFlagProvider {...props}>
      <FeatureFlagProbe />
    </FeatureFlagProvider>,
  );
}

const strictManifest = (flags: Record<string, boolean>) => ({
  schemaVersion: FEATURE_FLAG_MANIFEST_VERSION,
  flags,
  ttlMs: FEATURE_FLAG_CACHE_TTL_MS,
  updatedAt: Date.now(),
});

const readyIdentity = (tenantId: string, userId: string, permissions: string[] = []) => ({
  data: {
    meta: {
      generated_at: "2026-08-16T00:00:00Z",
      request_id: `feature-flags-${tenantId}-${userId}`,
      source_kinds: [],
    },
    user_id: userId,
    display_name: userId,
    tenant_id: tenantId,
    principal_type: "user" as const,
    cell_id: "cell-a",
    roles: [],
    permissions,
    mfa_verified: true,
    feature_overrides: {},
  },
  isError: false,
  isFetching: false,
  isLoading: false,
  isSuccess: true,
});

describe("FeatureFlagProvider", () => {
  beforeEach(() => {
    trackMock.mockReset();
    vi.restoreAllMocks();
    window.localStorage.clear();
    Object.defineProperty(window, "__RUNTIME_DASHBOARD_FLAGS__", {
      configurable: true,
      value: undefined,
      writable: true,
    });
    vi.stubGlobal("fetch", vi.fn());
    useAuthMeMock.mockReturnValue({
      data: undefined,
      isError: false,
      isFetching: true,
      isLoading: true,
      isSuccess: false,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads remote flags, persists the manifest cache, and exposes remote source", async () => {
    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a"));
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(
        JSON.stringify({
          ...strictManifest({ enableLexKnowledge: false }),
          ttlMs: 30_000,
        }),
        {
          headers: { "Content-Type": "application/json" },
          status: 200,
        },
      ),
    );
    Object.defineProperty(window, "__RUNTIME_DASHBOARD_FLAGS__", {
      configurable: true,
      value: { enableLexKnowledge: true },
      writable: true,
    });

    render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="/flags.json">
          <FeatureFlagProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );

    expect(screen.getByTestId("feature-flag-status")).toHaveTextContent(
      "loading",
    );
    await waitFor(() =>
      expect(screen.getByTestId("feature-flag-status")).toHaveTextContent(
        "ready",
      ),
    );

    expect(screen.getByTestId("feature-flag-source")).toHaveTextContent(
      "remote",
    );
    expect(screen.getByTestId("feature-flag-lex")).toHaveTextContent("false");
    expect(window.localStorage.getItem(FEATURE_FLAG_MANIFEST_CACHE_KEY)).toContain(
      '"tenantId":"tenant-a"',
    );
    expect(trackMock).toHaveBeenCalledWith("feature-flags.remote.loaded", {
      flagCount: 1,
      source: "remote",
      url: "/flags.json",
      version: FEATURE_FLAG_MANIFEST_VERSION,
    });
  });

  it("uses a ready Authz scope for strict cache fallback", async () => {
    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a"));
    window.localStorage.setItem(
      FEATURE_FLAG_MANIFEST_CACHE_KEY,
      JSON.stringify({
        ...strictManifest({ enableLexKnowledge: false }),
        registryVersion: FEATURE_FLAG_MANIFEST_VERSION,
        tenantId: "tenant-a",
        userId: "user-a",
      }),
    );
    (fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("network down"),
    );

    render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="/flags.json">
          <FeatureFlagProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("feature-flag-source")).toHaveTextContent(
        "cache",
      ),
    );
    expect(screen.getByTestId("feature-flag-status")).toHaveTextContent(
      "ready",
    );
    expect(screen.getByTestId("feature-flag-lex")).toHaveTextContent("false");
    expect(trackMock).toHaveBeenCalledWith("feature-flags.remote.cache_hit", {
      flagCount: 1,
      url: "/flags.json",
      version: FEATURE_FLAG_MANIFEST_VERSION,
    });
  });

  it("reports remote failures without cache as an error state", async () => {
    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a"));
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("boom", { status: 500 }),
    );

    render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="/flags.json">
          <FeatureFlagProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("feature-flag-status")).toHaveTextContent(
        "error",
      ),
    );
    expect(screen.getByTestId("feature-flag-source")).toHaveTextContent("env");
    expect(trackMock).toHaveBeenCalledWith("feature-flags.remote.failed", {
      message: "Feature flag manifest request failed with status 500",
      url: "/flags.json",
    });
  });

  it("uses prop overrides as the highest-precedence source without fetching", () => {
    Object.defineProperty(window, "__RUNTIME_DASHBOARD_FLAGS__", {
      configurable: true,
      value: { enableScenarioComposer: false },
      writable: true,
    });

    renderFeatureFlags({
      overrides: { enableScenarioComposer: true },
      remoteUrl: "",
    });

    expect(screen.getByTestId("feature-flag-status")).toHaveTextContent(
      "ready",
    );
    expect(screen.getByTestId("feature-flag-source")).toHaveTextContent(
      "props",
    );
    expect(screen.getByTestId("feature-flag-composer")).toHaveTextContent(
      "true",
    );
    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects a remote manifest atomically and exposes its typed diagnostic", async () => {
    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a"));
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(
        JSON.stringify(strictManifest({ enableLexKnowledge: false, permission: true })),
        { headers: { "Content-Type": "application/json" }, status: 200 },
      ),
    );

    render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="/flags.json">
          <FeatureFlagProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("feature-flag-status")).toHaveTextContent("error"),
    );
    expect(screen.getByTestId("feature-flag-lex")).toHaveTextContent("true");
    expect(screen.getByTestId("feature-flag-diagnostic")).toHaveTextContent(
      "forbidden_auth_pseudo_key",
    );
  });

  it("preserves an invalid remote diagnostic while safely using a valid scoped cache", async () => {
    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a"));
    window.localStorage.setItem(
      FEATURE_FLAG_MANIFEST_CACHE_KEY,
      JSON.stringify({
        ...strictManifest({ enableLexKnowledge: false }),
        registryVersion: FEATURE_FLAG_MANIFEST_VERSION,
        tenantId: "tenant-a",
        userId: "user-a",
      }),
    );
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(
        JSON.stringify(strictManifest({ enableLexKnowledge: true, permission: true })),
        { headers: { "Content-Type": "application/json" }, status: 200 },
      ),
    );

    render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="/flags.json">
          <FeatureFlagProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("feature-flag-source")).toHaveTextContent("cache"),
    );
    expect(screen.getByTestId("feature-flag-lex")).toHaveTextContent("false");
    expect(screen.getByTestId("feature-flag-diagnostic")).toHaveTextContent(
      "forbidden_auth_pseudo_key",
    );
  });

  it("does not paint or write a scoped cache identity before Authz is ready", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify(strictManifest({ enableLexKnowledge: false })), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      }),
    );

    renderFeatureFlags({ remoteUrl: "/flags.json" });

    await waitFor(() => expect(screen.getByTestId("feature-flag-status")).toHaveTextContent("loading"));
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.getByTestId("feature-flag-lex")).toHaveTextContent("true");
    expect(window.localStorage.getItem(FEATURE_FLAG_MANIFEST_CACHE_KEY)).toBeNull();
  });

  it("snapshots the ready identity once before deriving the strict cache scope", () => {
    let tenantReads = 0;
    let userReads = 0;
    const identity = readyIdentity("tenant-a", "user-a");
    const data = Object.defineProperties(
      { ...identity.data },
      {
        tenant_id: {
          configurable: true,
          get: () => {
            tenantReads += 1;
            if (tenantReads > 1) {
              throw new Error("tenant identity was reread");
            }
            return "tenant-a";
          },
        },
        user_id: {
          configurable: true,
          get: () => {
            userReads += 1;
            if (userReads > 1) {
              throw new Error("user identity was reread");
            }
            return "user-a";
          },
        },
      },
    );
    useAuthMeMock.mockReturnValue({ ...identity, data });

    expect(() => renderFeatureFlags({ remoteUrl: "" })).not.toThrow();
    expect(tenantReads).toBe(1);
    expect(userReads).toBe(1);
    expect(screen.getByTestId("feature-flag-status")).toHaveTextContent("ready");
  });

  it("snapshots a rejected remote diagnostic before projecting and tracking it", async () => {
    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a"));
    let messageReads = 0;
    const rejected = Object.defineProperty(new Error(), "message", {
      configurable: true,
      get: () => {
        messageReads += 1;
        if (messageReads > 1) {
          throw new Error("remote diagnostic was reread");
        }
        return "first rejected remote diagnostic";
      },
    });
    (fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(rejected);

    render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="/flags.json">
          <FeatureFlagProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("feature-flag-status")).toHaveTextContent("error"),
    );
    expect(messageReads).toBe(1);
    expect(screen.getByTestId("feature-flag-diagnostic")).toHaveTextContent(
      "invalid_feature_flag_manifest",
    );
    expect(trackMock).toHaveBeenCalledWith("feature-flags.remote.failed", {
      message: "first rejected remote diagnostic",
      url: "/flags.json",
    });
  });

  it("contains a rejected proxy whose prototype cannot be inspected", async () => {
    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a"));
    const rejected = new Proxy(
      {},
      {
        getPrototypeOf: () => {
          throw new Error("rejected proxy prototype escaped");
        },
      },
    );
    (fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(rejected);

    render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="/flags.json">
          <FeatureFlagProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("feature-flag-status")).toHaveTextContent("error"),
    );
    expect(screen.getByTestId("feature-flag-diagnostic")).toHaveTextContent(
      "invalid_feature_flag_manifest",
    );
  });

  it("projects a terminal identity failure instead of indefinite loading", () => {
    useAuthMeMock.mockReturnValue({
      data: undefined,
      isError: true,
      isFetching: false,
      isLoading: false,
      isSuccess: false,
    });

    renderFeatureFlags({ remoteUrl: "/flags.json" });

    expect(screen.getByTestId("feature-flag-status")).toHaveTextContent("error");
    expect(screen.getByTestId("feature-flag-diagnostic")).toHaveTextContent(
      "cache_scope_required",
    );
    expect(fetch).not.toHaveBeenCalled();
  });

  it("does not reuse tenant A cache bytes after remounting as tenant B", async () => {
    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a"));
    window.localStorage.setItem(
      FEATURE_FLAG_MANIFEST_CACHE_KEY,
      JSON.stringify({
        ...strictManifest({ enableLexKnowledge: false }),
        registryVersion: FEATURE_FLAG_MANIFEST_VERSION,
        tenantId: "tenant-a",
        userId: "user-a",
      }),
    );
    (fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("offline"));

    const first = render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="/flags.json">
          <FeatureFlagProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("feature-flag-lex")).toHaveTextContent("false"),
    );
    first.unmount();

    useAuthMeMock.mockReturnValue(readyIdentity("tenant-b", "user-b"));
    render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="/flags.json">
          <FeatureFlagProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );
    await waitFor(() =>
      expect(screen.getByTestId("feature-flag-status")).toHaveTextContent("error"),
    );
    expect(screen.getByTestId("feature-flag-lex")).toHaveTextContent("true");
    expect(screen.getByTestId("feature-flag-diagnostic")).toHaveTextContent(
      "cache_scope_mismatch",
    );
  });

  it("does not paint tenant A flags for a delimiter-colliding tenant B identity", () => {
    const observed: boolean[] = [];
    useAuthMeMock.mockReturnValue(readyIdentity("tenant\u0000segment", "user-a"));
    window.localStorage.setItem(
      FEATURE_FLAG_MANIFEST_CACHE_KEY,
      JSON.stringify({
        ...strictManifest({ enableLexKnowledge: false }),
        registryVersion: FEATURE_FLAG_MANIFEST_VERSION,
        tenantId: "tenant\u0000segment",
        userId: "user-a",
      }),
    );

    const view = render(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="">
          <FeatureFlagRenderProbe observed={observed} />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );
    expect(observed.at(-1)).toBe(false);

    observed.length = 0;
    useAuthMeMock.mockReturnValue(
      readyIdentity("tenant", "segment\u0000user-a"),
    );
    view.rerender(
      <AuthzProvider>
        <FeatureFlagProvider remoteUrl="">
          <FeatureFlagRenderProbe observed={observed} />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );

    expect(observed.length).toBeGreaterThan(0);
    expect(observed).not.toContain(false);
    expect(window.localStorage.getItem(FEATURE_FLAG_MANIFEST_CACHE_KEY)).toContain(
      '"tenantId":"tenant\\u0000segment"',
    );
  });

  it("keeps rollout flags and Authz permissions on separate permission floors", () => {
    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a", []));
    const deniedByAuthz = render(
      <AuthzProvider>
        <FeatureFlagProvider overrides={{ enableScenarioComposer: true }} remoteUrl="">
          <PermissionFloorProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );
    expect(JSON.parse(screen.getByRole("status").textContent ?? "{}")).toEqual({
      canLaunch: false,
      composerEnabled: true,
    });
    deniedByAuthz.unmount();

    useAuthMeMock.mockReturnValue(readyIdentity("tenant-a", "user-a", ["runs.launch"]));
    render(
      <AuthzProvider>
        <FeatureFlagProvider overrides={{ enableScenarioComposer: false }} remoteUrl="">
          <PermissionFloorProbe />
        </FeatureFlagProvider>
      </AuthzProvider>,
    );
    expect(JSON.parse(screen.getByRole("status").textContent ?? "{}")).toEqual({
      canLaunch: true,
      composerEnabled: false,
    });
  });
});
