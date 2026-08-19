import {
  DEFAULT_FEATURE_FLAGS,
  FEATURE_FLAG_KEYS,
  FEATURE_FLAG_MANIFEST_CACHE_KEY,
  FEATURE_FLAG_MANIFEST_VERSION,
  FEATURE_FLAG_REGISTRY,
  parseFeatureFlagManifest,
  readEnvironmentFeatureFlagManifest,
  readInjectedFeatureFlagManifest,
  readStrictCachedFeatureFlagManifest,
  writeStrictCachedFeatureFlagManifest,
} from "@/shared/lib/featureFlags";
import type { FeatureFlagLifecycle } from "@/shared/lib/featureFlags";

const cacheScope = { tenantId: "tenant-c18a", userId: "user-c18a" };

const strictManifest = (flags: Record<string, boolean>) => ({
  schemaVersion: FEATURE_FLAG_MANIFEST_VERSION,
  flags,
  ttlMs: 60_000,
  updatedAt: Date.now(),
});

describe("featureFlags", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    delete window.__RUNTIME_DASHBOARD_FLAGS__;
    window.localStorage.removeItem(FEATURE_FLAG_MANIFEST_CACHE_KEY);
  });

  it("rejects an unknown sibling atomically instead of applying its valid flag", () => {
    const rawValue = strictManifest({
      enableDarkMode: false,
      forgedFlag: true,
    });

    expect(parseFeatureFlagManifest(rawValue, "remote")).toMatchObject({
      ok: false,
      diagnostic: { code: "unknown_feature_flag" },
    });
  });

  it("rejects a wrong-type flag rather than coercing it", () => {
    expect(
      parseFeatureFlagManifest(
        strictManifest({ enableDarkMode: "false" as unknown as boolean }),
        "remote",
      ),
    ).toMatchObject({
      ok: false,
      diagnostic: { code: "invalid_feature_flag_value" },
    });
  });

  it.each(["all_on", "all_off"])(
    "rejects the unsafe %s global profile",
    (profile) => {
      expect(parseFeatureFlagManifest(profile, "remote")).toMatchObject({
        ok: false,
        diagnostic: { code: "unsafe_feature_flag_profile" },
      });
    },
  );

  it("rejects old-schema and auth pseudo-key payloads", () => {
    expect(
      parseFeatureFlagManifest(
        { version: 1, flags: { enableDarkMode: false } },
        "remote",
      ),
    ).toMatchObject({
      ok: false,
      diagnostic: { code: "unsupported_feature_flag_schema" },
    });
    expect(
      parseFeatureFlagManifest(
        strictManifest({ enableDarkMode: false, permission: true }),
        "window",
      ),
    ).toMatchObject({
      ok: false,
      diagnostic: { code: "forbidden_auth_pseudo_key" },
    });
  });

  it("uses the same strict parser for injected flags", () => {
    window.__RUNTIME_DASHBOARD_FLAGS__ = {
      enableRunsWorkspace: false,
      RuntimePermission: "run:approve",
    };

    expect(readInjectedFeatureFlagManifest()).toMatchObject({
      state: "present",
      result: {
        ok: false,
        diagnostic: { code: "forbidden_auth_pseudo_key" },
      },
    });
  });

  it("treats an explicit null injected manifest as present invalid input", () => {
    window.__RUNTIME_DASHBOARD_FLAGS__ = null as unknown as Record<string, unknown>;

    expect(readInjectedFeatureFlagManifest()).toMatchObject({
      state: "present",
      result: {
        ok: false,
        diagnostic: { code: "invalid_feature_flag_manifest" },
      },
    });
  });

  it("treats an empty environment manifest as present invalid input", () => {
    vi.stubEnv("VITE_FEATURE_FLAGS_MANIFEST", "   ");

    expect(readEnvironmentFeatureFlagManifest()).toMatchObject({
      state: "present",
      result: {
        ok: false,
        diagnostic: { code: "invalid_feature_flag_manifest" },
      },
    });
  });

  it("accepts only the exact registry cache version, scope, and expiry", () => {
    const cacheEntry = {
      ...strictManifest({ enableScenarioComposer: false }),
      registryVersion: FEATURE_FLAG_MANIFEST_VERSION,
      ...cacheScope,
    };

    expect(parseFeatureFlagManifest(cacheEntry, "cache", cacheScope)).toMatchObject({
      ok: true,
      manifest: {
        flags: { enableScenarioComposer: false },
        source: "cache",
        version: FEATURE_FLAG_MANIFEST_VERSION,
      },
    });
    expect(
      parseFeatureFlagManifest(cacheEntry, "cache", {
        tenantId: "different-tenant",
        userId: cacheScope.userId,
      }),
    ).toMatchObject({ ok: false, diagnostic: { code: "cache_scope_mismatch" } });
    expect(
      parseFeatureFlagManifest(
        { ...cacheEntry, registryVersion: FEATURE_FLAG_MANIFEST_VERSION + 1 },
        "cache",
        cacheScope,
      ),
    ).toMatchObject({
      ok: false,
      diagnostic: { code: "cache_registry_version_mismatch" },
    });
    expect(
      parseFeatureFlagManifest(
        {
          ...cacheEntry,
          updatedAt: Date.now() - 1_001,
          ttlMs: 1_000,
        },
        "cache",
        cacheScope,
      ),
    ).toMatchObject({ ok: false, diagnostic: { code: "cache_manifest_expired" } });
    expect(
      parseFeatureFlagManifest(
        { ...cacheEntry, updatedAt: Date.now() + 1_000 },
        "cache",
        cacheScope,
      ),
    ).toMatchObject({ ok: false, diagnostic: { code: "cache_manifest_future" } });
    expect(
      parseFeatureFlagManifest(
        {
          ...cacheEntry,
          updatedAt: undefined,
        },
        "cache",
        cacheScope,
      ),
    ).toMatchObject({
      ok: false,
      diagnostic: { code: "cache_manifest_updated_at_required" },
    });
  });

  it("round-trips the exact strict scoped cache envelope", () => {
    const manifest = {
      flags: { enableScenarioComposer: false },
      source: "remote" as const,
      ttlMs: 60_000,
      updatedAt: Date.now(),
      version: FEATURE_FLAG_MANIFEST_VERSION,
    };

    expect(writeStrictCachedFeatureFlagManifest(manifest, cacheScope)).toMatchObject({
      ok: true,
      receipt: { cacheKey: FEATURE_FLAG_MANIFEST_CACHE_KEY },
    });
    expect(
      JSON.parse(window.localStorage.getItem(FEATURE_FLAG_MANIFEST_CACHE_KEY)!),
    ).toEqual({
      schemaVersion: FEATURE_FLAG_MANIFEST_VERSION,
      registryVersion: FEATURE_FLAG_MANIFEST_VERSION,
      flags: { enableScenarioComposer: false },
      ttlMs: 60_000,
      updatedAt: manifest.updatedAt,
      tenantId: cacheScope.tenantId,
      userId: cacheScope.userId,
    });
    expect(readStrictCachedFeatureFlagManifest(cacheScope)).toMatchObject({
      state: "present",
      result: {
        ok: true,
        manifest: { flags: { enableScenarioComposer: false }, source: "cache" },
      },
    });
  });

  it("writes a fresh validated cache snapshot rather than raw manifest behavior", () => {
    const mutatingFlags = { enableScenarioComposer: false };
    Object.defineProperty(mutatingFlags, "toJSON", {
      value: () => {
        mutatingFlags.enableScenarioComposer = true;
        return mutatingFlags;
      },
    });
    expect(
      writeStrictCachedFeatureFlagManifest(
        {
          flags: mutatingFlags,
          source: "remote",
          ttlMs: 60_000,
          updatedAt: Date.now(),
          version: FEATURE_FLAG_MANIFEST_VERSION,
        },
        cacheScope,
      ),
    ).toMatchObject({ ok: true });
    expect(
      JSON.parse(window.localStorage.getItem(FEATURE_FLAG_MANIFEST_CACHE_KEY)!),
    ).toMatchObject({ flags: { enableScenarioComposer: false } });
  });

  it("rejects raw manifest accessors and old versions before a strict cache write", () => {
    const throwingManifest = Object.defineProperty(
      {
        source: "remote",
        ttlMs: 60_000,
        updatedAt: Date.now(),
        version: FEATURE_FLAG_MANIFEST_VERSION,
      },
      "flags",
      {
        get: () => {
          throw new Error("manifest flags getter failed");
        },
      },
    );
    expect(
      writeStrictCachedFeatureFlagManifest(
        throwingManifest as Parameters<typeof writeStrictCachedFeatureFlagManifest>[0],
        cacheScope,
      ),
    ).toMatchObject({
      ok: false,
      diagnostic: { code: "untrusted_feature_flag_input" },
    });
    expect(
      writeStrictCachedFeatureFlagManifest(
        {
          flags: { enableScenarioComposer: false },
          source: "remote",
          ttlMs: 60_000,
          updatedAt: Date.now(),
          version: FEATURE_FLAG_MANIFEST_VERSION - 1,
        },
        cacheScope,
      ),
    ).toMatchObject({
      ok: false,
      diagnostic: { code: "cache_manifest_version_mismatch" },
    });
  });

  it("rejects scope accessors before they can produce a mixed cache identity", () => {
    const changingScope = Object.defineProperties(
      {},
      {
        tenantId: {
          configurable: true,
          get: () => {
            throw new Error("tenant scope getter changed");
          },
        },
        userId: {
          configurable: true,
          get: () => {
            throw new Error("user scope getter changed");
          },
        },
      },
    );
    const manifest = {
      flags: { enableScenarioComposer: false },
      source: "remote" as const,
      ttlMs: 60_000,
      updatedAt: Date.now(),
      version: FEATURE_FLAG_MANIFEST_VERSION,
    };

    expect(
      writeStrictCachedFeatureFlagManifest(
        manifest,
        changingScope as typeof cacheScope,
      ),
    ).toMatchObject({ ok: false, diagnostic: { code: "cache_scope_untrusted" } });
    expect(window.localStorage.getItem(FEATURE_FLAG_MANIFEST_CACHE_KEY)).toBeNull();
  });

  it("contains hostile storage, window, and parser inputs as typed strict failures", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage read failed");
    });
    expect(readStrictCachedFeatureFlagManifest(cacheScope)).toMatchObject({
      state: "present",
      result: { ok: false, diagnostic: { code: "cache_storage_read_failed" } },
    });
    vi.restoreAllMocks();

    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("storage write failed");
    });
    expect(
      writeStrictCachedFeatureFlagManifest(
        {
          flags: { enableScenarioComposer: false },
          source: "remote",
          ttlMs: 60_000,
          updatedAt: Date.now(),
          version: FEATURE_FLAG_MANIFEST_VERSION,
        },
        cacheScope,
      ),
    ).toMatchObject({ ok: false, diagnostic: { code: "cache_storage_write_failed" } });
    vi.restoreAllMocks();

    Object.defineProperty(window, "__RUNTIME_DASHBOARD_FLAGS__", {
      configurable: true,
      get: () => {
        throw new Error("window flags getter failed");
      },
    });
    expect(readInjectedFeatureFlagManifest()).toMatchObject({
      state: "present",
      result: { ok: false, diagnostic: { code: "untrusted_feature_flag_input" } },
    });
    expect(
      parseFeatureFlagManifest(
        new Proxy({}, { ownKeys: () => { throw new Error("proxy failed"); } }),
        "remote",
      ),
    ).toMatchObject({
      ok: false,
      diagnostic: { code: "untrusted_feature_flag_input" },
    });
  });

  it("snapshots injected flags and storage once before strict parsing or writing", () => {
    let injectedReads = 0;
    Object.defineProperty(window, "__RUNTIME_DASHBOARD_FLAGS__", {
      configurable: true,
      get: () => {
        injectedReads += 1;
        return injectedReads === 1
          ? { enableScenarioComposer: false }
          : { permission: true };
      },
    });
    expect(readInjectedFeatureFlagManifest()).toMatchObject({
      state: "present",
      result: { ok: true, manifest: { flags: { enableScenarioComposer: false } } },
    });
    expect(injectedReads).toBe(1);

    const localStorageDescriptor = Object.getOwnPropertyDescriptor(
      window,
      "localStorage",
    );
    const firstStorage = { setItem: vi.fn() } as unknown as Storage;
    const redirectedStorage = { setItem: vi.fn() } as unknown as Storage;
    let storageReads = 0;
    try {
      Object.defineProperty(window, "localStorage", {
        configurable: true,
        get: () => {
          storageReads += 1;
          return storageReads === 1 ? firstStorage : redirectedStorage;
        },
      });
      expect(
        writeStrictCachedFeatureFlagManifest(
          {
            flags: { enableScenarioComposer: false },
            source: "remote",
            ttlMs: 60_000,
            updatedAt: Date.now(),
            version: FEATURE_FLAG_MANIFEST_VERSION,
          },
          cacheScope,
        ),
      ).toMatchObject({ ok: true });
      expect(storageReads).toBe(1);
      expect(firstStorage.setItem).toHaveBeenCalledOnce();
      expect(redirectedStorage.setItem).not.toHaveBeenCalled();
    } finally {
      Object.defineProperty(window, "localStorage", localStorageDescriptor!);
    }
  });

  it("treats an empty strict cache entry as present invalid input", () => {
    window.localStorage.setItem(FEATURE_FLAG_MANIFEST_CACHE_KEY, "");
    expect(readStrictCachedFeatureFlagManifest(cacheScope)).toMatchObject({
      state: "present",
      result: { ok: false, diagnostic: { code: "invalid_feature_flag_manifest" } },
    });
  });

  it("contains absent storage and serialization failures without a strict cache write", () => {
    const localStorageDescriptor = Object.getOwnPropertyDescriptor(
      window,
      "localStorage",
    );
    try {
      Object.defineProperty(window, "localStorage", {
        configurable: true,
        value: undefined,
      });
      expect(readStrictCachedFeatureFlagManifest(cacheScope)).toMatchObject({
        state: "present",
        result: { ok: false, diagnostic: { code: "cache_storage_unavailable" } },
      });
      expect(
        writeStrictCachedFeatureFlagManifest(
          {
            flags: { enableScenarioComposer: false },
            source: "remote",
            ttlMs: 60_000,
            updatedAt: Date.now(),
            version: FEATURE_FLAG_MANIFEST_VERSION,
          },
          cacheScope,
        ),
      ).toMatchObject({
        ok: false,
        diagnostic: { code: "cache_storage_unavailable" },
      });
    } finally {
      Object.defineProperty(window, "localStorage", localStorageDescriptor!);
    }

    vi.spyOn(JSON, "stringify").mockImplementation(() => {
      throw new Error("serialization failed");
    });
    expect(
      writeStrictCachedFeatureFlagManifest(
        {
          flags: { enableScenarioComposer: false },
          source: "remote",
          ttlMs: 60_000,
          updatedAt: Date.now(),
          version: FEATURE_FLAG_MANIFEST_VERSION,
        },
        cacheScope,
      ),
    ).toMatchObject({ ok: false, diagnostic: { code: "cache_serialization_failed" } });
  });

  it("retires collaboration and exposes only the eleven wired manifest keys", () => {
    expectTypeOf<FeatureFlagLifecycle>().toEqualTypeOf<"live">();
    expect(FEATURE_FLAG_KEYS).toEqual([
      "enableAtlasV2",
      "enableCausalGraph",
      "enableClerkMode",
      "enableCommandPalette",
      "enableDarkMode",
      "enableLexKnowledge",
      "enableNarrativeView",
      "enablePlatformHealth",
      "enableRunsWorkspace",
      "enableScenarioComposer",
      "enableWhatIfAnalysis",
    ]);
    expect(DEFAULT_FEATURE_FLAGS).toEqual({
      enableAtlasV2: true,
      enableCausalGraph: true,
      enableClerkMode: true,
      enableCommandPalette: true,
      enableDarkMode: true,
      enableLexKnowledge: true,
      enableNarrativeView: true,
      enablePlatformHealth: true,
      enableRunsWorkspace: true,
      enableScenarioComposer: true,
      enableWhatIfAnalysis: true,
    });
    expect(Object.values(FEATURE_FLAG_REGISTRY)).toHaveLength(11);
    expect(
      Object.values(FEATURE_FLAG_REGISTRY).filter(
        (entry) => entry.disposition === "WIRE",
      ),
    ).toHaveLength(11);
    expect(
      Object.values(FEATURE_FLAG_REGISTRY).filter(
        (entry) => entry.status === "live",
      ),
    ).toHaveLength(11);
    expect(
      new Set(Object.values(FEATURE_FLAG_REGISTRY).map((entry) => entry.target)),
    ).toEqual(new Set(["existing"]));
  });

  it("rejects the retired collaboration key atomically at the environment boundary", () => {
    vi.stubEnv(
      "VITE_FEATURE_FLAGS_MANIFEST",
      JSON.stringify(
        strictManifest({ enableCollaboration: false, enableDarkMode: false }),
      ),
    );

    expect(readEnvironmentFeatureFlagManifest()).toMatchObject({
      state: "present",
      result: {
        ok: false,
        diagnostic: { code: "unknown_feature_flag" },
      },
    });
  });
});
