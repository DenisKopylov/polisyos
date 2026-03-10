import { z } from "zod";

export const FEATURE_FLAG_KEYS = [
  "enableDarkMode",
  "enableLexKnowledge",
  "enablePlatformHealth",
  "enableRunsWorkspace",
  "enableScenarioComposer",
] as const;

export type FeatureFlagKey = (typeof FEATURE_FLAG_KEYS)[number];
export type FeatureFlags = Record<FeatureFlagKey, boolean>;
export type FeatureFlagOverrides = Partial<FeatureFlags>;

export const FEATURE_FLAG_MANIFEST_URL =
  import.meta.env.VITE_FEATURE_FLAGS_URL?.trim() || "";
export const FEATURE_FLAG_MANIFEST_CACHE_KEY =
  "polisyos.runtime.feature-flags-cache";
export const FEATURE_FLAG_MANIFEST_VERSION = 1;
export const FEATURE_FLAG_CACHE_TTL_MS = 5 * 60 * 1000;

const featureFlagManifestEnvelopeSchema = z
  .object({
    flags: z.record(z.string(), z.unknown()).optional(),
    ttlMs: z.number().int().positive().optional(),
    ttl_ms: z.number().int().positive().optional(),
    updatedAt: z.number().int().positive().optional(),
    updated_at: z.number().int().positive().optional(),
    version: z.number().int().positive().optional(),
  })
  .loose();

function coerceBooleanFlag(rawValue: unknown): boolean | undefined {
  if (typeof rawValue === "boolean") {
    return rawValue;
  }
  if (typeof rawValue === "number") {
    return rawValue !== 0;
  }
  if (typeof rawValue !== "string") {
    return undefined;
  }

  const normalized = rawValue.trim().toLowerCase();
  if (!normalized) {
    return undefined;
  }
  if (normalized === "true" || normalized === "1" || normalized === "on") {
    return true;
  }
  if (normalized === "false" || normalized === "0" || normalized === "off") {
    return false;
  }
  return undefined;
}

function readBooleanFlag(rawValue: string | undefined, fallback: boolean) {
  if (rawValue == null || rawValue.trim() === "") {
    return fallback;
  }
  return rawValue.trim().toLowerCase() === "true";
}

export const DEFAULT_FEATURE_FLAGS: FeatureFlags = {
  enableDarkMode: readBooleanFlag(import.meta.env.VITE_FF_DARK_MODE, true),
  enableLexKnowledge: readBooleanFlag(
    import.meta.env.VITE_FF_LEX_KNOWLEDGE,
    true,
  ),
  enablePlatformHealth: readBooleanFlag(
    import.meta.env.VITE_FF_PLATFORM_HEALTH,
    true,
  ),
  enableRunsWorkspace: readBooleanFlag(
    import.meta.env.VITE_FF_RUNS_WORKSPACE,
    true,
  ),
  enableScenarioComposer: readBooleanFlag(
    import.meta.env.VITE_FF_SCENARIO_COMPOSER,
    true,
  ),
};

function parseFeatureFlagManifest(rawValue: string | undefined) {
  if (!rawValue || !rawValue.trim()) {
    return null;
  }
  try {
    return JSON.parse(rawValue) as unknown;
  } catch {
    return null;
  }
}

export function normalizeFeatureFlagOverrides(
  rawValue: unknown,
): FeatureFlagOverrides {
  if (!rawValue || typeof rawValue !== "object") {
    return {};
  }

  const source = rawValue as Record<string, unknown>;
  const overrides: FeatureFlagOverrides = {};

  for (const key of FEATURE_FLAG_KEYS) {
    const nextValue = coerceBooleanFlag(source[key]);
    if (nextValue !== undefined) {
      overrides[key] = nextValue;
    }
  }

  return overrides;
}

export const ENV_FEATURE_FLAG_OVERRIDES = normalizeFeatureFlagOverrides(
  parseFeatureFlagManifest(import.meta.env.VITE_FEATURE_FLAGS_MANIFEST),
);

export type NormalizedFeatureFlagManifest = {
  flags: FeatureFlagOverrides;
  source: "cache" | "remote";
  ttlMs: number;
  updatedAt: number;
  version: number;
};

export function readInjectedFeatureFlags(): FeatureFlagOverrides {
  if (typeof window === "undefined") {
    return {};
  }
  return normalizeFeatureFlagOverrides(window.__RUNTIME_DASHBOARD_FLAGS__);
}

export function hasFeatureFlagOverrides(overrides?: FeatureFlagOverrides) {
  return Boolean(overrides && Object.keys(overrides).length > 0);
}

export function normalizeFeatureFlagManifest(
  rawValue: unknown,
  source: "cache" | "remote",
): NormalizedFeatureFlagManifest | null {
  if (!rawValue || typeof rawValue !== "object") {
    const flags = normalizeFeatureFlagOverrides(rawValue);
    if (!hasFeatureFlagOverrides(flags)) {
      return null;
    }
    return {
      flags,
      source,
      ttlMs: FEATURE_FLAG_CACHE_TTL_MS,
      updatedAt: Date.now(),
      version: FEATURE_FLAG_MANIFEST_VERSION,
    };
  }

  const parsed = featureFlagManifestEnvelopeSchema.safeParse(rawValue);
  if (!parsed.success) {
    const flags = normalizeFeatureFlagOverrides(rawValue);
    if (!hasFeatureFlagOverrides(flags)) {
      return null;
    }
    return {
      flags,
      source,
      ttlMs: FEATURE_FLAG_CACHE_TTL_MS,
      updatedAt: Date.now(),
      version: FEATURE_FLAG_MANIFEST_VERSION,
    };
  }

  const payload = parsed.data;
  const flags = normalizeFeatureFlagOverrides(payload.flags ?? rawValue);
  if (!hasFeatureFlagOverrides(flags)) {
    return null;
  }

  return {
    flags,
    source,
    ttlMs: payload.ttlMs ?? payload.ttl_ms ?? FEATURE_FLAG_CACHE_TTL_MS,
    updatedAt: payload.updatedAt ?? payload.updated_at ?? Date.now(),
    version: payload.version ?? FEATURE_FLAG_MANIFEST_VERSION,
  };
}

export function readCachedFeatureFlagManifest() {
  if (typeof window === "undefined") {
    return null;
  }

  const rawValue = window.localStorage.getItem(FEATURE_FLAG_MANIFEST_CACHE_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as unknown;
    const manifest = normalizeFeatureFlagManifest(parsed, "cache");
    if (!manifest) {
      return null;
    }
    if (Date.now() - manifest.updatedAt > manifest.ttlMs) {
      return null;
    }
    return manifest;
  } catch {
    return null;
  }
}

export function writeCachedFeatureFlagManifest(
  manifest: NormalizedFeatureFlagManifest,
) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    FEATURE_FLAG_MANIFEST_CACHE_KEY,
    JSON.stringify(manifest),
  );
}

export function resolveFeatureFlags(
  ...sources: Array<FeatureFlagOverrides | undefined>
): FeatureFlags {
  return {
    ...DEFAULT_FEATURE_FLAGS,
    ...ENV_FEATURE_FLAG_OVERRIDES,
    ...Object.assign({}, ...sources),
  };
}
