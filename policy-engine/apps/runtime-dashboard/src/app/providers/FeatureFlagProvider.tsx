import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuthMe } from "@/api/hooks/useAuthMe";
import { useTelemetry } from "@/app/providers/TelemetryProvider";
import {
  DEFAULT_FEATURE_FLAGS,
  FEATURE_FLAG_MANIFEST_URL,
  hasFeatureFlagOverrides,
  parseFeatureFlagManifest,
  readEnvironmentFeatureFlagManifest,
  readInjectedFeatureFlagManifest,
  readStrictCachedFeatureFlagManifest,
  type FeatureFlagCacheScope,
  type FeatureFlagKey,
  type FeatureFlagManifestDiagnostic,
  type FeatureFlagOverrides,
  type FeatureFlags,
  type FeatureFlagSourceReadResult,
  type NormalizedFeatureFlagManifest,
  writeStrictCachedFeatureFlagManifest,
} from "@/shared/lib/featureFlags";
import {
  createInteractionState,
  type InteractionState,
} from "@/shared/lib/domain/statusOwnership";

type FeatureFlagSource = "cache" | "env" | "window" | "remote" | "props";
type FeatureFlagLoadState = InteractionState<"ready" | "loading" | "error">;

type FeatureFlagContextValue = {
  diagnostic: FeatureFlagManifestDiagnostic | null;
  flags: FeatureFlags;
  isEnabled: (key: FeatureFlagKey) => boolean;
  source: FeatureFlagSource;
  /** Interaction-only load state; consumers project its label at render time. */
  status: FeatureFlagLoadState;
};

type SourceSnapshot = {
  diagnostic: FeatureFlagManifestDiagnostic | null;
  flags: FeatureFlagOverrides;
  source: FeatureFlagSource;
};

class FeatureFlagManifestRejection extends Error {
  readonly diagnostic: FeatureFlagManifestDiagnostic;

  constructor(diagnostic: FeatureFlagManifestDiagnostic) {
    super(diagnostic.message);
    this.name = "FeatureFlagManifestRejection";
    this.diagnostic = diagnostic;
  }
}

const FeatureFlagContext = createContext<FeatureFlagContextValue | null>(null);

function loadState(label: FeatureFlagLoadState["label"]): FeatureFlagLoadState {
  return createInteractionState(label, "loading");
}

function sourceSnapshot(
  source: FeatureFlagSource,
  result: FeatureFlagSourceReadResult,
): SourceSnapshot {
  if (result.state === "absent") {
    return { diagnostic: null, flags: {}, source };
  }
  if (!result.result.ok) {
    return { diagnostic: result.result.diagnostic, flags: {}, source };
  }
  return { diagnostic: null, flags: result.result.manifest.flags, source };
}

function strictProps(overrides?: FeatureFlagOverrides): SourceSnapshot {
  if (overrides === undefined) {
    return { diagnostic: null, flags: {}, source: "props" };
  }
  return sourceSnapshot("props", {
    state: "present",
    result: parseFeatureFlagManifest(overrides, "props"),
  });
}

function readyCacheScope(
  authMe: ReturnType<typeof useAuthMe>,
): FeatureFlagCacheScope | undefined {
  if (!authMe.isSuccess || authMe.isFetching) {
    return undefined;
  }
  try {
    const identity = authMe.data;
    if (!identity) {
      return undefined;
    }
    const tenantId = identity.tenant_id;
    const userId = identity.user_id;
    if (
      typeof tenantId !== "string" ||
      !tenantId.trim() ||
      typeof userId !== "string" ||
      !userId.trim()
    ) {
      return undefined;
    }
    return { tenantId, userId };
  } catch {
    return undefined;
  }
}

function diagnosticFrom(error: unknown): FeatureFlagManifestDiagnostic {
  try {
    if (error instanceof FeatureFlagManifestRejection) {
      return error.diagnostic;
    }
    return {
      code: "invalid_feature_flag_manifest",
      message:
        error instanceof Error
          ? error.message
          : "Feature flag manifest was rejected.",
    };
  } catch {
    return {
      code: "invalid_feature_flag_manifest",
      message: "Feature flag manifest was rejected.",
    };
  }
}

function initialRemote(scope: FeatureFlagCacheScope, remoteUrl: string) {
  const cached = sourceSnapshot("cache", readStrictCachedFeatureFlagManifest(scope));
  return {
    diagnostic: cached.diagnostic,
    flags: cached.flags,
    source: hasFeatureFlagOverrides(cached.flags) ? "cache" : "env" as FeatureFlagSource,
    status: loadState(remoteUrl && !hasFeatureFlagOverrides(cached.flags) ? "loading" : "ready"),
  };
}

function ScopedFeatureFlagProvider({
  children,
  overrides,
  remoteUrl,
  scope,
}: PropsWithChildren<{
  overrides?: FeatureFlagOverrides;
  remoteUrl: string;
  scope: FeatureFlagCacheScope;
}>) {
  const { track } = useTelemetry();
  const environment = useMemo(
    () => sourceSnapshot("env", readEnvironmentFeatureFlagManifest()),
    [],
  );
  const injected = useMemo(
    () => sourceSnapshot("window", readInjectedFeatureFlagManifest()),
    [],
  );
  const props = useMemo(() => strictProps(overrides), [overrides]);
  const [remote, setRemote] = useState(() => initialRemote(scope, remoteUrl));

  useEffect(() => {
    const cached = sourceSnapshot("cache", readStrictCachedFeatureFlagManifest(scope));
    if (!remoteUrl) {
      setRemote({
        diagnostic: cached.diagnostic,
        flags: cached.flags,
        source: hasFeatureFlagOverrides(cached.flags) ? "cache" : "env",
        status: loadState("ready"),
      });
      return;
    }

    const abortController = new AbortController();
    setRemote({
      diagnostic: cached.diagnostic,
      flags: cached.flags,
      source: hasFeatureFlagOverrides(cached.flags) ? "cache" : "env",
      status: loadState("loading"),
    });

    void fetch(remoteUrl, {
      headers: { accept: "application/json" },
      signal: abortController.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Feature flag manifest request failed with status ${response.status}`);
        }
        const parsed = parseFeatureFlagManifest(await response.json(), "remote");
        if (!parsed.ok) {
          throw new FeatureFlagManifestRejection(parsed.diagnostic);
        }
        if (abortController.signal.aborted) {
          return;
        }
        const manifest: NormalizedFeatureFlagManifest = parsed.manifest;
        const receipt = writeStrictCachedFeatureFlagManifest(manifest, scope);
        if (abortController.signal.aborted) {
          return;
        }
        if (!receipt.ok) {
          setRemote({
            diagnostic: receipt.diagnostic,
            flags: {},
            source: "env",
            status: loadState("error"),
          });
          return;
        }
        setRemote({
          diagnostic: null,
          flags: manifest.flags,
          source: "remote",
          status: loadState("ready"),
        });
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
        const failureDiagnostic = diagnosticFrom(error);
        const fallback = sourceSnapshot("cache", readStrictCachedFeatureFlagManifest(scope));
        if (hasFeatureFlagOverrides(fallback.flags)) {
          setRemote({
            diagnostic: failureDiagnostic,
            flags: fallback.flags,
            source: "cache",
            status: loadState("ready"),
          });
          track("feature-flags.remote.cache_hit", {
            flagCount: Object.keys(fallback.flags).length,
            url: remoteUrl,
            version: 1,
          });
          return;
        }
        setRemote({
          diagnostic: fallback.diagnostic ?? failureDiagnostic,
          flags: {},
          source: "env",
          status: loadState("error"),
        });
        track("feature-flags.remote.failed", {
          message: failureDiagnostic.message,
          url: remoteUrl,
        });
      });

    return () => abortController.abort();
  }, [remoteUrl, scope, track]);

  const sources = [environment, injected, remote, props];
  const flags = useMemo(
    () => Object.assign({}, DEFAULT_FEATURE_FLAGS, ...sources.map((source) => source.flags)),
    [environment, injected, props, remote],
  );
  const lastSource = [...sources].reverse().find((source) => hasFeatureFlagOverrides(source.flags));
  const diagnostic = props.diagnostic ?? remote.diagnostic ?? injected.diagnostic ?? environment.diagnostic;
  const value = useMemo<FeatureFlagContextValue>(
    () => ({
      diagnostic,
      flags,
      isEnabled: (key) => flags[key],
      source: lastSource?.source ?? "env",
      status: remote.status,
    }),
    [diagnostic, flags, lastSource?.source, remote.status],
  );

  return <FeatureFlagContext.Provider value={value}>{children}</FeatureFlagContext.Provider>;
}

/** Strict feature-flag boundary: rollout configuration never grants permissions. */
export function FeatureFlagProvider({
  children,
  overrides,
  remoteUrl = FEATURE_FLAG_MANIFEST_URL,
}: PropsWithChildren<{
  overrides?: FeatureFlagOverrides;
  remoteUrl?: string;
}>) {
  const authMe = useAuthMe();
  const scope = useMemo(
    () => readyCacheScope(authMe),
    [authMe.data, authMe.isFetching, authMe.isSuccess],
  );
  const identityFailed =
    authMe.isError || (authMe.isSuccess && !authMe.isFetching && !scope);
  const environment = useMemo(
    () => sourceSnapshot("env", readEnvironmentFeatureFlagManifest()),
    [],
  );
  const injected = useMemo(
    () => sourceSnapshot("window", readInjectedFeatureFlagManifest()),
    [],
  );
  const props = useMemo(() => strictProps(overrides), [overrides]);

  if (!scope) {
    const sources = [environment, injected, props];
    const flags = Object.assign({}, DEFAULT_FEATURE_FLAGS, ...sources.map((source) => source.flags));
    const lastSource = [...sources].reverse().find((source) => hasFeatureFlagOverrides(source.flags));
    const identityDiagnostic: FeatureFlagManifestDiagnostic | null =
      remoteUrl && identityFailed
        ? {
            code: "cache_scope_required",
            message:
              "Feature flag remote and cache sources require a settled tenant and user identity.",
          }
        : null;
    const diagnostic =
      props.diagnostic ??
      injected.diagnostic ??
      environment.diagnostic ??
      identityDiagnostic;
    return (
      <FeatureFlagContext.Provider
        value={{
          diagnostic,
          flags,
          isEnabled: (key) => flags[key],
          source: lastSource?.source ?? "env",
          status: loadState(remoteUrl ? (identityFailed ? "error" : "loading") : "ready"),
        }}
      >
        {children}
      </FeatureFlagContext.Provider>
    );
  }

  return (
    <ScopedFeatureFlagProvider
      key={JSON.stringify(["feature-flags", scope.tenantId, scope.userId])}
      overrides={overrides}
      remoteUrl={remoteUrl}
      scope={scope}
    >
      {children}
    </ScopedFeatureFlagProvider>
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
