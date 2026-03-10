import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useTelemetry } from "@/app/providers/TelemetryProvider";
import {
  FEATURE_FLAG_MANIFEST_URL,
  hasFeatureFlagOverrides,
  type FeatureFlagKey,
  type FeatureFlagOverrides,
  type FeatureFlags,
  normalizeFeatureFlagManifest,
  normalizeFeatureFlagOverrides,
  readCachedFeatureFlagManifest,
  readInjectedFeatureFlags,
  resolveFeatureFlags,
  writeCachedFeatureFlagManifest,
} from "@/lib/featureFlags";

type FeatureFlagSource = "cache" | "env" | "window" | "remote" | "props";
type FeatureFlagStatus = "ready" | "loading" | "error";

type FeatureFlagContextValue = {
  flags: FeatureFlags;
  isEnabled: (key: FeatureFlagKey) => boolean;
  source: FeatureFlagSource;
  status: FeatureFlagStatus;
};

const FeatureFlagContext = createContext<FeatureFlagContextValue | null>(null);

export function FeatureFlagProvider({
  children,
  overrides,
  remoteUrl = FEATURE_FLAG_MANIFEST_URL,
}: PropsWithChildren<{
  overrides?: FeatureFlagOverrides;
  remoteUrl?: string;
}>) {
  const { track } = useTelemetry();
  const injectedFlags = useMemo(() => readInjectedFeatureFlags(), []);
  const cachedManifest = useMemo(() => readCachedFeatureFlagManifest(), []);
  const [remoteFlags, setRemoteFlags] = useState<FeatureFlagOverrides>(
    () => cachedManifest?.flags ?? {},
  );
  const [remoteSource, setRemoteSource] = useState<FeatureFlagSource>(
    () => cachedManifest?.source ?? "env",
  );
  const [status, setStatus] = useState<FeatureFlagStatus>(
    remoteUrl && !cachedManifest ? "loading" : "ready",
  );

  useEffect(() => {
    if (!remoteUrl) {
      setRemoteFlags({});
      setStatus("ready");
      return;
    }

    const abortController = new AbortController();
    setStatus("loading");

    void fetch(remoteUrl, {
      headers: {
        accept: "application/json",
      },
      signal: abortController.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(
            `Feature flag manifest request failed with status ${response.status}`,
          );
        }

        const payload = await response.json();
        const manifest =
          normalizeFeatureFlagManifest(payload, "remote") ??
          ({
            flags: normalizeFeatureFlagOverrides(payload),
            source: "remote",
            ttlMs: 5 * 60 * 1000,
            updatedAt: Date.now(),
            version: 1,
          } as const);
        setRemoteFlags(manifest.flags);
        setRemoteSource(manifest.source);
        setStatus("ready");
        writeCachedFeatureFlagManifest(manifest);
        track("feature-flags.remote.loaded", {
          flagCount: Object.keys(manifest.flags).length,
          source: manifest.source,
          url: remoteUrl,
          version: manifest.version,
        });
      })
      .catch((error: unknown) => {
        if (abortController.signal.aborted) {
          return;
        }
        const fallbackManifest = readCachedFeatureFlagManifest();
        if (fallbackManifest) {
          setRemoteFlags(fallbackManifest.flags);
          setRemoteSource("cache");
          setStatus("ready");
          track("feature-flags.remote.cache_hit", {
            flagCount: Object.keys(fallbackManifest.flags).length,
            url: remoteUrl,
            version: fallbackManifest.version,
          });
          return;
        }
        setRemoteFlags({});
        setRemoteSource("env");
        setStatus("error");
        track("feature-flags.remote.failed", {
          message: error instanceof Error ? error.message : "unknown",
          url: remoteUrl,
        });
      });

    return () => abortController.abort();
  }, [remoteUrl, track]);

  const flags = useMemo(
    () => resolveFeatureFlags(injectedFlags, remoteFlags, overrides),
    [injectedFlags, overrides, remoteFlags],
  );

  const source = useMemo<FeatureFlagSource>(() => {
    if (hasFeatureFlagOverrides(overrides)) {
      return "props";
    }
    if (remoteSource === "cache" && hasFeatureFlagOverrides(remoteFlags)) {
      return "cache";
    }
    if (hasFeatureFlagOverrides(remoteFlags)) {
      return "remote";
    }
    if (hasFeatureFlagOverrides(injectedFlags)) {
      return "window";
    }
    return "env";
  }, [injectedFlags, overrides, remoteFlags, remoteSource]);

  const value = useMemo<FeatureFlagContextValue>(
    () => ({
      flags,
      isEnabled: (key) => flags[key],
      source,
      status,
    }),
    [flags, source, status],
  );

  return (
    <FeatureFlagContext.Provider value={value}>
      {children}
    </FeatureFlagContext.Provider>
  );
}

export function useFeatureFlags() {
  const context = useContext(FeatureFlagContext);
  if (!context) {
    throw new Error("useFeatureFlags must be used within FeatureFlagProvider");
  }
  return context;
}

export function useFeatureFlag(flag: FeatureFlagKey) {
  const { isEnabled } = useFeatureFlags();
  return isEnabled(flag);
}

export function useRequiredFeatureFlag(flag: FeatureFlagKey) {
  return useFeatureFlag(flag);
}
