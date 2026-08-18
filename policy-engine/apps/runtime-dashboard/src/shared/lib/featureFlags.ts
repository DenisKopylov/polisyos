export const FEATURE_FLAG_KEYS = [
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
] as const;

export type FeatureFlagKey = (typeof FEATURE_FLAG_KEYS)[number];
export type FeatureFlags = Record<FeatureFlagKey, boolean>;
export type FeatureFlagOverrides = Partial<FeatureFlags>;
export type FeatureFlagDisposition = "WIRE" | "RETIRE";
export type FeatureFlagLifecycle = "live";

type FeatureFlagRegistryEntry = {
  defaultEnabled: true;
  disposition: FeatureFlagDisposition;
  status: FeatureFlagLifecycle;
  target: "existing";
};

/** Canonical D5 registry; feature flags are not runtime permissions. */
export const FEATURE_FLAG_REGISTRY = {
  enableAtlasV2: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enableCausalGraph: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enableClerkMode: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enableCommandPalette: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enableDarkMode: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enableLexKnowledge: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enableNarrativeView: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enablePlatformHealth: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enableRunsWorkspace: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enableScenarioComposer: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
  enableWhatIfAnalysis: {
    defaultEnabled: true,
    disposition: "WIRE",
    status: "live",
    target: "existing",
  },
} as const satisfies Record<FeatureFlagKey, FeatureFlagRegistryEntry>;

export const FEATURE_FLAG_MANIFEST_URL =
  import.meta.env.VITE_FEATURE_FLAGS_URL?.trim() || "";
export const FEATURE_FLAG_MANIFEST_CACHE_KEY =
  "polisyos.runtime.feature-flags-cache";
export const FEATURE_FLAG_MANIFEST_VERSION = 1;
export const FEATURE_FLAG_CACHE_TTL_MS = 5 * 60 * 1000;

export type FeatureFlagCacheScope = {
  tenantId: string;
  userId: string;
};

export type FeatureFlagManifestDiagnosticCode =
  | "invalid_feature_flag_manifest"
  | "unsupported_feature_flag_schema"
  | "unknown_feature_flag"
  | "forbidden_auth_pseudo_key"
  | "invalid_feature_flag_value"
  | "unsafe_feature_flag_profile"
  | "invalid_feature_flag_metadata"
  | "cache_scope_required"
  | "cache_scope_invalid"
  | "cache_scope_untrusted"
  | "cache_scope_mismatch"
  | "cache_registry_version_mismatch"
  | "cache_manifest_version_mismatch"
  | "cache_manifest_updated_at_required"
  | "cache_manifest_expired"
  | "cache_manifest_future"
  | "cache_storage_unavailable"
  | "cache_storage_read_failed"
  | "cache_storage_write_failed"
  | "cache_serialization_failed"
  | "untrusted_feature_flag_input";

export type FeatureFlagManifestDiagnostic = {
  code: FeatureFlagManifestDiagnosticCode;
  message: string;
};

export type NormalizedFeatureFlagManifest = {
  flags: FeatureFlagOverrides;
  source: "cache" | "remote";
  ttlMs: number;
  updatedAt: number;
  version: number;
};

export type FeatureFlagManifestParseResult =
  | { ok: true; manifest: NormalizedFeatureFlagManifest }
  | { ok: false; diagnostic: FeatureFlagManifestDiagnostic };

export type FeatureFlagSourceReadResult =
  | { state: "absent" }
  | { state: "present"; result: FeatureFlagManifestParseResult };

export type StrictFeatureFlagCacheWriteResult =
  | {
      ok: true;
      receipt: {
        cacheKey: typeof FEATURE_FLAG_MANIFEST_CACHE_KEY;
        writtenAt: number;
      };
    }
  | { ok: false; diagnostic: FeatureFlagManifestDiagnostic };

type FeatureFlagManifestSource = "cache" | "remote" | "env" | "window" | "props";

const AUTH_PSEUDO_KEY_PATTERN = /(?:permission|role|auth|entitlement)/i;

function diagnostic(
  code: FeatureFlagManifestDiagnosticCode,
  message: string,
): FeatureFlagManifestParseResult {
  return { ok: false, diagnostic: { code, message } };
}

function writeDiagnostic(
  code: FeatureFlagManifestDiagnosticCode,
  message: string,
): StrictFeatureFlagCacheWriteResult {
  return { ok: false, diagnostic: { code, message } };
}

function snapshotCacheScope(
  rawScope: FeatureFlagCacheScope | undefined,
):
  | { ok: true; scope: FeatureFlagCacheScope }
  | { ok: false; diagnostic: FeatureFlagManifestDiagnostic } {
  if (!rawScope || typeof rawScope !== "object") {
    return {
      ok: false,
      diagnostic: {
        code: "cache_scope_required",
        message: "Feature flag cache reads and writes require a tenant and user scope.",
      },
    };
  }

  try {
    const tenantDescriptor = Object.getOwnPropertyDescriptor(rawScope, "tenantId");
    const userDescriptor = Object.getOwnPropertyDescriptor(rawScope, "userId");
    if (
      !tenantDescriptor ||
      !userDescriptor ||
      !("value" in tenantDescriptor) ||
      !("value" in userDescriptor)
    ) {
      return {
        ok: false,
        diagnostic: {
          code: "cache_scope_untrusted",
          message: "Feature flag cache scope must use own data properties.",
        },
      };
    }
    const tenantId = tenantDescriptor.value;
    const userId = userDescriptor.value;
    if (
      typeof tenantId !== "string" ||
      !tenantId.trim() ||
      typeof userId !== "string" ||
      !userId.trim()
    ) {
      return {
        ok: false,
        diagnostic: {
          code: "cache_scope_invalid",
          message: "Feature flag cache scope tenantId and userId must be nonempty strings.",
        },
      };
    }
    return { ok: true, scope: { tenantId, userId } };
  } catch {
    return {
      ok: false,
      diagnostic: {
        code: "cache_scope_untrusted",
        message: "Feature flag cache scope could not be safely inspected.",
      },
    };
  }
}

function isRecord(rawValue: unknown): rawValue is Record<string, unknown> {
  return typeof rawValue === "object" && rawValue !== null && !Array.isArray(rawValue);
}

function isFeatureFlagKey(value: string): value is FeatureFlagKey {
  return (FEATURE_FLAG_KEYS as readonly string[]).includes(value);
}

function parseRawValue(rawValue: unknown): unknown {
  if (typeof rawValue !== "string") {
    return rawValue;
  }

  try {
    return JSON.parse(rawValue) as unknown;
  } catch {
    return rawValue;
  }
}

function parseFlags(rawValue: unknown):
  | { ok: true; flags: FeatureFlagOverrides }
  | { ok: false; diagnostic: FeatureFlagManifestDiagnostic } {
  if (!isRecord(rawValue)) {
    return {
      ok: false,
      diagnostic: {
        code: "invalid_feature_flag_manifest",
        message: "Feature flag payload must be an object.",
      },
    };
  }

  const flags: FeatureFlagOverrides = {};
  for (const [key, value] of Object.entries(rawValue)) {
    if (!isFeatureFlagKey(key)) {
      return {
        ok: false,
        diagnostic: {
          code: AUTH_PSEUDO_KEY_PATTERN.test(key)
            ? "forbidden_auth_pseudo_key"
            : "unknown_feature_flag",
          message: `Feature flag key ${key} is not in the canonical registry.`,
        },
      };
    }
    if (typeof value !== "boolean") {
      return {
        ok: false,
        diagnostic: {
          code: "invalid_feature_flag_value",
          message: `Feature flag ${key} must be a boolean.`,
        },
      };
    }
    flags[key] = value;
  }

  return { ok: true, flags };
}

function readPositiveInteger(
  payload: Record<string, unknown>,
  field: "ttlMs" | "updatedAt",
): number | undefined | FeatureFlagManifestDiagnostic {
  const value = payload[field];
  if (value === undefined) {
    return undefined;
  }
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value <= 0) {
    return {
      code: "invalid_feature_flag_metadata",
      message: `Feature flag ${field} must be a positive safe integer.`,
    };
  }
  return value;
}

function parseManifestEnvelope(
  payload: Record<string, unknown>,
  source: FeatureFlagManifestSource,
  cacheScope?: FeatureFlagCacheScope,
  now = Date.now(),
): FeatureFlagManifestParseResult {
  const allowedFields = new Set([
    "schemaVersion",
    "flags",
    "ttlMs",
    "updatedAt",
    ...(source === "cache" ? ["registryVersion", "tenantId", "userId"] : []),
  ]);
  if (Object.keys(payload).some((key) => !allowedFields.has(key))) {
    return diagnostic(
      "unsupported_feature_flag_schema",
      "Feature flag manifest contains an unsupported schema field.",
    );
  }
  if (payload.schemaVersion !== FEATURE_FLAG_MANIFEST_VERSION || !("flags" in payload)) {
    return diagnostic(
      "unsupported_feature_flag_schema",
      "Feature flag manifest schemaVersion must match the canonical registry.",
    );
  }

  const parsedFlags = parseFlags(payload.flags);
  if (!parsedFlags.ok) {
    return parsedFlags;
  }
  const ttlMs = readPositiveInteger(payload, "ttlMs");
  const updatedAt = readPositiveInteger(payload, "updatedAt");
  if (typeof ttlMs === "object") {
    return { ok: false, diagnostic: ttlMs };
  }
  if (typeof updatedAt === "object") {
    return { ok: false, diagnostic: updatedAt };
  }

  if (source === "cache") {
    if (!cacheScope) {
      return diagnostic(
        "cache_scope_required",
        "Feature flag cache reads require a tenant and user scope.",
      );
    }
    if (payload.registryVersion !== FEATURE_FLAG_MANIFEST_VERSION) {
      return diagnostic(
        "cache_registry_version_mismatch",
        "Feature flag cache registry version does not match the canonical registry.",
      );
    }
    if (
      payload.tenantId !== cacheScope.tenantId ||
      payload.userId !== cacheScope.userId
    ) {
      return diagnostic(
        "cache_scope_mismatch",
        "Feature flag cache scope does not match the active tenant and user.",
      );
    }
    if (updatedAt === undefined) {
      return diagnostic(
        "cache_manifest_updated_at_required",
        "Feature flag cache manifest must include updatedAt.",
      );
    }
  }

  const manifest: NormalizedFeatureFlagManifest = {
    flags: parsedFlags.flags,
    source: source === "cache" ? "cache" : "remote",
    ttlMs: ttlMs ?? FEATURE_FLAG_CACHE_TTL_MS,
    updatedAt: updatedAt ?? now,
    version: FEATURE_FLAG_MANIFEST_VERSION,
  };
  if (source === "cache" && manifest.updatedAt > now) {
    return diagnostic(
      "cache_manifest_future",
      "Feature flag cache manifest timestamp cannot be in the future.",
    );
  }
  if (source === "cache" && now - manifest.updatedAt >= manifest.ttlMs) {
    return diagnostic(
      "cache_manifest_expired",
      "Feature flag cache manifest has expired.",
    );
  }
  return { ok: true, manifest };
}

function parseFeatureFlagManifestAt(
  rawValue: unknown,
  source: FeatureFlagManifestSource,
  cacheScope?: FeatureFlagCacheScope,
  now = Date.now(),
): FeatureFlagManifestParseResult {
  const parsedValue = parseRawValue(rawValue);
  if (parsedValue === "all_on" || parsedValue === "all_off") {
    return diagnostic(
      "unsafe_feature_flag_profile",
      "Global feature-flag profiles are not admitted by the canonical registry.",
    );
  }
  if (!isRecord(parsedValue)) {
    return diagnostic(
      "invalid_feature_flag_manifest",
      "Feature flag payload must be an object or a JSON object.",
    );
  }

  if ("flags" in parsedValue || "schemaVersion" in parsedValue || "version" in parsedValue) {
    return parseManifestEnvelope(parsedValue, source, cacheScope, now);
  }

  const parsedFlags = parseFlags(parsedValue);
  if (!parsedFlags.ok) {
    return parsedFlags;
  }
  if (source === "cache") {
    return diagnostic(
      "unsupported_feature_flag_schema",
      "Feature flag cache entries must be versioned manifest envelopes.",
    );
  }
  return {
    ok: true,
    manifest: {
      flags: parsedFlags.flags,
      source: "remote",
      ttlMs: FEATURE_FLAG_CACHE_TTL_MS,
      updatedAt: now,
      version: FEATURE_FLAG_MANIFEST_VERSION,
    },
  };
}

/** Parses every external flag source through one strict, atomic registry boundary. */
export function parseFeatureFlagManifest(
  rawValue: unknown,
  source: FeatureFlagManifestSource,
  cacheScope?: FeatureFlagCacheScope,
): FeatureFlagManifestParseResult {
  try {
    const now = Date.now();
    const scopeSnapshot =
      source === "cache" ? snapshotCacheScope(cacheScope) : undefined;
    if (scopeSnapshot && !scopeSnapshot.ok) {
      return { ok: false, diagnostic: scopeSnapshot.diagnostic };
    }
    return parseFeatureFlagManifestAt(
      rawValue,
      source,
      scopeSnapshot?.scope,
      now,
    );
  } catch {
    return diagnostic(
      "untrusted_feature_flag_input",
      "Feature flag input could not be safely inspected.",
    );
  }
}

/** Reads the environment manifest through the strict feature-flag boundary. */
export function readEnvironmentFeatureFlagManifest(): FeatureFlagSourceReadResult {
  const rawValue = import.meta.env.VITE_FEATURE_FLAGS_MANIFEST;
  if (rawValue === undefined) {
    return { state: "absent" };
  }
  return { state: "present", result: parseFeatureFlagManifest(rawValue, "env") };
}

/** Reads injected flags through the strict feature-flag boundary. */
export function readInjectedFeatureFlagManifest(): FeatureFlagSourceReadResult {
  try {
    if (typeof window === "undefined") {
      return { state: "absent" };
    }
    const rawValue = window.__RUNTIME_DASHBOARD_FLAGS__;
    if (rawValue === undefined) {
      return { state: "absent" };
    }
    return {
      state: "present",
      result: parseFeatureFlagManifest(rawValue, "window"),
    };
  } catch {
    return {
      state: "present",
      result: diagnostic(
        "untrusted_feature_flag_input",
        "Injected feature flags could not be safely read.",
      ),
    };
  }
}

/** Reads a scoped cache entry through the strict feature-flag boundary. */
export function readStrictCachedFeatureFlagManifest(
  cacheScope?: FeatureFlagCacheScope,
): FeatureFlagSourceReadResult {
  if (typeof window === "undefined") {
    return { state: "absent" };
  }
  const scopeSnapshot = snapshotCacheScope(cacheScope);
  if (!scopeSnapshot.ok) {
    return { state: "present", result: { ok: false, diagnostic: scopeSnapshot.diagnostic } };
  }

  let rawValue: string | null;
  try {
    const storage = window.localStorage;
    if (!storage) {
      return {
        state: "present",
        result: diagnostic(
          "cache_storage_unavailable",
          "Feature flag cache storage is unavailable.",
        ),
      };
    }
    rawValue = storage.getItem(FEATURE_FLAG_MANIFEST_CACHE_KEY);
  } catch {
    return {
      state: "present",
      result: diagnostic(
        "cache_storage_read_failed",
        "Feature flag cache storage could not be read.",
      ),
    };
  }
  if (rawValue === null) {
    return { state: "absent" };
  }
  try {
    return {
      state: "present",
      result: parseFeatureFlagManifestAt(
        rawValue,
        "cache",
        scopeSnapshot.scope,
        Date.now(),
      ),
    };
  } catch {
    return {
      state: "present",
      result: diagnostic(
        "untrusted_feature_flag_input",
        "Feature flag cache input could not be safely inspected.",
      ),
    };
  }
}

/** Writes only strict cache envelopes bound to the supplied identity scope. */
export function writeStrictCachedFeatureFlagManifest(
  manifest: NormalizedFeatureFlagManifest,
  cacheScope?: FeatureFlagCacheScope,
): StrictFeatureFlagCacheWriteResult {
  const scopeSnapshot = snapshotCacheScope(cacheScope);
  if (!scopeSnapshot.ok) {
    return { ok: false, diagnostic: scopeSnapshot.diagnostic };
  }

  let now: number;
  let rawCacheEntry: {
    schemaVersion: number;
    registryVersion: number;
    flags: FeatureFlagOverrides;
    ttlMs: number;
    updatedAt: number;
    tenantId: string;
    userId: string;
  };
  try {
    now = Date.now();
    if (manifest.version !== FEATURE_FLAG_MANIFEST_VERSION) {
      return writeDiagnostic(
        "cache_manifest_version_mismatch",
        "Feature flag cache manifest version does not match the canonical registry.",
      );
    }
    rawCacheEntry = {
      schemaVersion: FEATURE_FLAG_MANIFEST_VERSION,
      registryVersion: FEATURE_FLAG_MANIFEST_VERSION,
      flags: manifest.flags,
      ttlMs: manifest.ttlMs,
      updatedAt: manifest.updatedAt,
      tenantId: scopeSnapshot.scope.tenantId,
      userId: scopeSnapshot.scope.userId,
    };
  } catch {
    return writeDiagnostic(
      "untrusted_feature_flag_input",
      "Feature flag cache entry could not be safely inspected.",
    );
  }

  let parsed: FeatureFlagManifestParseResult;
  try {
    parsed = parseFeatureFlagManifestAt(
      rawCacheEntry,
      "cache",
      scopeSnapshot.scope,
      now,
    );
    if (!parsed.ok) {
      return { ok: false, diagnostic: parsed.diagnostic };
    }
  } catch {
    return writeDiagnostic(
      "untrusted_feature_flag_input",
      "Feature flag cache entry could not be safely inspected.",
    );
  }

  const validatedCacheEntry = {
    schemaVersion: FEATURE_FLAG_MANIFEST_VERSION,
    registryVersion: FEATURE_FLAG_MANIFEST_VERSION,
    flags: { ...parsed.manifest.flags },
    ttlMs: parsed.manifest.ttlMs,
    updatedAt: parsed.manifest.updatedAt,
    tenantId: scopeSnapshot.scope.tenantId,
    userId: scopeSnapshot.scope.userId,
  };
  let serialized: string;
  try {
    serialized = JSON.stringify(validatedCacheEntry);
  } catch {
    return writeDiagnostic(
      "cache_serialization_failed",
      "Feature flag cache entry could not be serialized.",
    );
  }
  try {
    const storage = typeof window === "undefined" ? null : window.localStorage;
    if (!storage) {
      return writeDiagnostic(
        "cache_storage_unavailable",
        "Feature flag cache storage is unavailable.",
      );
    }
    storage.setItem(FEATURE_FLAG_MANIFEST_CACHE_KEY, serialized);
  } catch {
    return writeDiagnostic(
      "cache_storage_write_failed",
      "Feature flag cache storage could not be written.",
    );
  }
  return {
    ok: true,
    receipt: { cacheKey: FEATURE_FLAG_MANIFEST_CACHE_KEY, writtenAt: now },
  };
}

export const DEFAULT_FEATURE_FLAGS: FeatureFlags = Object.fromEntries(
  FEATURE_FLAG_KEYS.map((key) => [key, FEATURE_FLAG_REGISTRY[key].defaultEnabled]),
) as FeatureFlags;

export function hasFeatureFlagOverrides(overrides?: FeatureFlagOverrides) {
  return Boolean(overrides && Object.keys(overrides).length > 0);
}
