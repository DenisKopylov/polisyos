import { createContext, useContext, type PropsWithChildren } from "react";

import type {
  TemporalCapabilities,
  TemporalEventPoint,
  TemporalRange,
  TemporalScope,
} from "@/shared/lib/domain/temporal";

export type TemporalRuntimeBridgeValue = {
  capabilities: TemporalCapabilities | null;
  committedScope: TemporalScope | null;
  effectiveScope: TemporalScope | null;
  eventPoints: TemporalEventPoint[];
  previewScope: TemporalScope | null;
  range: TemporalRange;
  txRange: TemporalRange;
  commitPreview: (options?: { replaceUrl?: boolean }) => void;
  commitScope: (
    scope: TemporalScope | null,
    options?: { replaceUrl?: boolean },
  ) => void;
  resetScope: (options?: { replaceUrl?: boolean }) => void;
  setPreviewScope: (scope: TemporalScope | null) => void;
  setTemporalCapabilities: (capabilities: TemporalCapabilities | null) => void;
  stepValidTime: (amountMs: number, options?: { commit?: boolean }) => void;
};

const TemporalRuntimeBridgeContext =
  createContext<TemporalRuntimeBridgeValue | null>(null);

export function TemporalRuntimeBridgeProvider({
  children,
  value,
}: PropsWithChildren<{ value: TemporalRuntimeBridgeValue }>) {
  return (
    <TemporalRuntimeBridgeContext.Provider value={value}>
      {children}
    </TemporalRuntimeBridgeContext.Provider>
  );
}

export function useTemporalCursor() {
  const context = useContext(TemporalRuntimeBridgeContext);
  if (!context) {
    throw new Error(
      "useTemporalCursor must be used within TemporalRuntimeBridgeProvider",
    );
  }
  return context;
}

export function useMaybeTemporalCursor() {
  return useContext(TemporalRuntimeBridgeContext);
}
