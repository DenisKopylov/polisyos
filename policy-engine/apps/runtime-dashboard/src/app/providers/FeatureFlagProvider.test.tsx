import { render, screen, waitFor } from "@testing-library/react";

import {
  FeatureFlagProvider,
  useFeatureFlag,
  useFeatureFlags,
} from "@/app/providers/FeatureFlagProvider";
import {
  FEATURE_FLAG_CACHE_TTL_MS,
  FEATURE_FLAG_MANIFEST_CACHE_KEY,
  FEATURE_FLAG_MANIFEST_VERSION,
} from "@/shared/lib/featureFlags";

const { trackMock } = vi.hoisted(() => ({
  trackMock: vi.fn(),
}));

vi.mock("@/app/providers/TelemetryProvider", () => ({
  useTelemetry: () => ({
    track: trackMock,
  }),
}));

function FeatureFlagProbe() {
  const { source, status } = useFeatureFlags();
  const lexEnabled = useFeatureFlag("enableLexKnowledge");
  const composerEnabled = useFeatureFlag("enableScenarioComposer");

  return (
    <div>
      <span data-testid="feature-flag-status">{status}</span>
      <span data-testid="feature-flag-source">{source}</span>
      <span data-testid="feature-flag-lex">{String(lexEnabled)}</span>
      <span data-testid="feature-flag-composer">{String(composerEnabled)}</span>
    </div>
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
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads remote flags, persists the manifest cache, and exposes remote source", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(
        JSON.stringify({
          flags: {
            enableLexKnowledge: false,
          },
          ttlMs: 30_000,
          updatedAt: 123,
          version: 2,
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

    renderFeatureFlags({ remoteUrl: "/flags.json" });

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
    expect(
      window.localStorage.getItem(FEATURE_FLAG_MANIFEST_CACHE_KEY),
    ).toContain('"version":2');
    expect(trackMock).toHaveBeenCalledWith("feature-flags.remote.loaded", {
      flagCount: 1,
      source: "remote",
      url: "/flags.json",
      version: 2,
    });
  });

  it("falls back to cached manifests when the remote request fails", async () => {
    window.localStorage.setItem(
      FEATURE_FLAG_MANIFEST_CACHE_KEY,
      JSON.stringify({
        flags: { enableLexKnowledge: false },
        ttlMs: FEATURE_FLAG_CACHE_TTL_MS,
        updatedAt: Date.now(),
        version: FEATURE_FLAG_MANIFEST_VERSION,
      }),
    );
    (fetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("network down"),
    );

    renderFeatureFlags({ remoteUrl: "/flags.json" });

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
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("boom", { status: 500 }),
    );

    renderFeatureFlags({ remoteUrl: "/flags.json" });

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
});
