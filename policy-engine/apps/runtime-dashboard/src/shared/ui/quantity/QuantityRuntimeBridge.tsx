import {
  createContext,
  useContext,
  type PropsWithChildren,
  type ReactNode,
} from "react";

import type {
  LineageBatchResponsePayload,
  LineageExportPayload,
  LineageResponsePayload,
  LineageBatchSelector,
  QuantityValue,
  TemporalRef,
} from "./quantity.types";

export type QuantityTrustMode = "off" | "compact" | "expanded";

export type QuantityRuntimeBridgeValue = {
  temporalScope: TemporalRef | null | undefined;
  trustMode: QuantityTrustMode;
  fetchLineage: (
    lineageId: string,
    temporalScope: TemporalRef | null | undefined,
  ) => Promise<LineageResponsePayload>;
  fetchLineageBatch: (
    selectors: readonly LineageBatchSelector[],
    runId: string | undefined,
    temporalScope: TemporalRef | null | undefined,
  ) => Promise<LineageBatchResponsePayload>;
  fetchLineageExport: (
    lineageId: string,
    format: LineageExportPayload["format"],
    temporalScope: TemporalRef | null | undefined,
  ) => Promise<LineageExportPayload>;
  renderTrustMetadata?: (
    quantity: QuantityValue,
    mode: Exclude<QuantityTrustMode, "off">,
  ) => ReactNode;
};

const unavailable = (): Promise<never> =>
  Promise.reject(
    new Error("Quantity runtime effects require QuantityRuntimeBridgeProvider"),
  );

const QuantityRuntimeBridgeContext = createContext<QuantityRuntimeBridgeValue>({
  temporalScope: null,
  trustMode: "off",
  fetchLineage: unavailable,
  fetchLineageBatch: unavailable,
  fetchLineageExport: unavailable,
});

export function QuantityRuntimeBridgeProvider({
  children,
  value,
}: PropsWithChildren<{ value: QuantityRuntimeBridgeValue }>) {
  return (
    <QuantityRuntimeBridgeContext.Provider value={value}>
      {children}
    </QuantityRuntimeBridgeContext.Provider>
  );
}

export function useQuantityRuntimeBridge() {
  return useContext(QuantityRuntimeBridgeContext);
}
