import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  clampTemporalInstant,
  compareTemporalScopes,
  normalizeTemporalScope,
  stepTemporalInstant,
  type TemporalCapabilities,
  type TemporalEventPoint,
  type TemporalRange,
  type TemporalScope,
} from "./temporal-scope";
import {
  readTemporalScopeFromLocation,
  replaceTemporalScopeInCurrentUrl,
} from "./temporal-url";

type TemporalCursorContextValue = {
  committedScope: TemporalScope | null;
  previewScope: TemporalScope | null;
  effectiveScope: TemporalScope | null;
  range: TemporalRange;
  txRange: TemporalRange;
  eventPoints: TemporalEventPoint[];
  capabilities: TemporalCapabilities | null;
  setPreviewScope: (scope: TemporalScope | null) => void;
  commitScope: (
    scope: TemporalScope | null,
    options?: { replaceUrl?: boolean },
  ) => void;
  commitPreview: (options?: { replaceUrl?: boolean }) => void;
  resetScope: (options?: { replaceUrl?: boolean }) => void;
  stepValidTime: (amountMs: number, options?: { commit?: boolean }) => void;
  setTemporalCapabilities: (capabilities: TemporalCapabilities | null) => void;
};

const TemporalCursorContext = createContext<TemporalCursorContextValue | null>(
  null,
);

export function TemporalCursorProvider({ children }: PropsWithChildren) {
  const [committedScope, setCommittedScope] = useState<TemporalScope | null>(
    () => readInitialScope(),
  );
  const [previewScope, setPreviewScopeState] = useState<TemporalScope | null>(
    committedScope,
  );
  const [capabilities, setCapabilities] = useState<TemporalCapabilities | null>(
    null,
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const syncFromUrl = () => {
      const nextScope = readTemporalScopeFromLocation(window.location);
      setCommittedScope(nextScope);
      setPreviewScopeState(nextScope);
    };
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, []);

  const range = capabilities?.validRange ?? defaultTemporalRange();
  const txRange = capabilities?.txRange ?? range;
  const effectiveScope =
    previewScope ?? committedScope ?? capabilities?.defaultScope ?? null;

  const setPreviewScope = useCallback(
    (scope: TemporalScope | null) => {
      setPreviewScopeState(clampScopeToRange(scope, range, txRange));
    },
    [range, txRange],
  );

  const commitScope = useCallback(
    (scope: TemporalScope | null, options: { replaceUrl?: boolean } = {}) => {
      const nextScope = clampScopeToRange(scope, range, txRange);
      setCommittedScope((current) =>
        compareTemporalScopes(current, nextScope) ? current : nextScope,
      );
      setPreviewScopeState(nextScope);
      if (options.replaceUrl ?? true) {
        replaceTemporalScopeInCurrentUrl(nextScope);
      }
    },
    [range, txRange],
  );

  const commitPreview = useCallback(
    (options: { replaceUrl?: boolean } = {}) => {
      commitScope(previewScope, options);
    },
    [commitScope, previewScope],
  );

  const resetScope = useCallback(
    (options: { replaceUrl?: boolean } = {}) => {
      commitScope(null, options);
    },
    [commitScope],
  );

  const stepValidTime = useCallback(
    (amountMs: number, options: { commit?: boolean } = {}) => {
      const base = effectiveScope?.validAt ?? range.latest;
      const nextValidAt = stepTemporalInstant(base, amountMs, range);
      const nextScope = normalizeTemporalScope({
        ...(effectiveScope ?? {}),
        validAt: nextValidAt,
        txAt: effectiveScope?.txAt ?? txRange.latest,
      });
      setPreviewScopeState(nextScope);
      if (options.commit ?? true) {
        commitScope(nextScope);
      }
    },
    [commitScope, effectiveScope, range, txRange],
  );

  const setTemporalCapabilities = useCallback(
    (nextCapabilities: TemporalCapabilities | null) => {
      setCapabilities(nextCapabilities);
    },
    [],
  );

  const value = useMemo<TemporalCursorContextValue>(
    () => ({
      capabilities,
      committedScope,
      commitPreview,
      commitScope,
      effectiveScope,
      eventPoints: capabilities?.eventPoints ?? [],
      previewScope,
      range,
      resetScope,
      setPreviewScope,
      setTemporalCapabilities,
      stepValidTime,
      txRange,
    }),
    [
      capabilities,
      committedScope,
      commitPreview,
      commitScope,
      effectiveScope,
      previewScope,
      range,
      resetScope,
      setPreviewScope,
      setTemporalCapabilities,
      stepValidTime,
      txRange,
    ],
  );

  return (
    <TemporalCursorContext.Provider value={value}>
      {children}
    </TemporalCursorContext.Provider>
  );
}

export function useTemporalCursor() {
  const context = useContext(TemporalCursorContext);
  if (!context) {
    throw new Error(
      "useTemporalCursor must be used within TemporalCursorProvider",
    );
  }
  return context;
}

export function useMaybeTemporalCursor() {
  return useContext(TemporalCursorContext);
}

function readInitialScope() {
  if (typeof window === "undefined") {
    return null;
  }
  return readTemporalScopeFromLocation(window.location);
}

function defaultTemporalRange(): TemporalRange {
  const latest = new Date();
  const earliest = new Date(latest.getTime() - 30 * 24 * 60 * 60 * 1000);
  return {
    earliest: earliest.toISOString(),
    latest: latest.toISOString(),
  };
}

function clampScopeToRange(
  scope: TemporalScope | null | undefined,
  range: TemporalRange,
  txRange: TemporalRange,
) {
  const normalized = normalizeTemporalScope(scope);
  if (!normalized) {
    return null;
  }
  return normalizeTemporalScope({
    ...normalized,
    validAt: normalized.validAt
      ? clampTemporalInstant(normalized.validAt, range)
      : null,
    txAt: normalized.txAt
      ? clampTemporalInstant(normalized.txAt, txRange)
      : null,
  });
}
