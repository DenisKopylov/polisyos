import {
  FEATURE_FLAG_KEYS,
  FEATURE_FLAG_MANIFEST_CACHE_KEY,
  normalizeFeatureFlagManifest,
  readCachedFeatureFlagManifest,
  readInjectedFeatureFlags,
  resolveFeatureFlags,
  normalizeFeatureFlagOverrides,
  writeCachedFeatureFlagManifest,
} from "@/lib/featureFlags";

describe("featureFlags", () => {
  afterEach(() => {
    delete window.__RUNTIME_DASHBOARD_FLAGS__;
    window.localStorage.removeItem(FEATURE_FLAG_MANIFEST_CACHE_KEY);
  });

  it("normalizes booleans from mixed manifest payloads", () => {
    expect(
      normalizeFeatureFlagOverrides({
        enableDarkMode: "false",
        enableLexKnowledge: 1,
        enablePlatformHealth: true,
        ignoredKey: "true",
      }),
    ).toEqual({
      enableDarkMode: false,
      enableLexKnowledge: true,
      enablePlatformHealth: true,
    });
  });

  it("supports all_on and all_off manifest profiles", () => {
    expect(normalizeFeatureFlagOverrides("all_on")).toEqual(
      Object.fromEntries(FEATURE_FLAG_KEYS.map((key) => [key, true])),
    );

    expect(normalizeFeatureFlagManifest("all_off", "remote")?.flags).toEqual(
      Object.fromEntries(FEATURE_FLAG_KEYS.map((key) => [key, false])),
    );

    expect(
      normalizeFeatureFlagManifest(
        {
          flags: "all_on",
          ttlMs: 60_000,
          updatedAt: 123,
          version: 3,
        },
        "remote",
      ),
    ).toMatchObject({
      flags: Object.fromEntries(FEATURE_FLAG_KEYS.map((key) => [key, true])),
      source: "remote",
      ttlMs: 60_000,
      updatedAt: 123,
      version: 3,
    });
  });

  it("reads injected flags from the window manifest", () => {
    window.__RUNTIME_DASHBOARD_FLAGS__ = {
      enableRunsWorkspace: "false",
      enableScenarioComposer: true,
    };

    expect(readInjectedFeatureFlags()).toEqual({
      enableRunsWorkspace: false,
      enableScenarioComposer: true,
    });
  });

  it("prefers later flag sources over defaults", () => {
    expect(
      resolveFeatureFlags(
        { enableDarkMode: false, enableRunsWorkspace: false },
        { enableRunsWorkspace: true },
      ),
    ).toMatchObject({
      enableDarkMode: false,
      enableRunsWorkspace: true,
    });
  });

  it("normalizes versioned remote manifests and reuses cache", () => {
    const manifest = normalizeFeatureFlagManifest(
      {
        flags: {
          enableDarkMode: false,
          enableScenarioComposer: true,
        },
        ttlMs: 60_000,
        updatedAt: Date.now(),
        version: 2,
      },
      "remote",
    );

    expect(manifest).toMatchObject({
      flags: {
        enableDarkMode: false,
        enableScenarioComposer: true,
      },
      source: "remote",
      version: 2,
    });

    writeCachedFeatureFlagManifest(manifest!);
    expect(readCachedFeatureFlagManifest()).toMatchObject({
      flags: manifest?.flags,
      version: 2,
    });
  });
});
