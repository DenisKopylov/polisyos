import type { PropsWithChildren } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createQueryHookWrapper } from "@/test/queryHook";

import {
  QuantityRuntimeBridgeProvider,
  type QuantityRuntimeBridgeValue,
} from "./QuantityRuntimeBridge";
import type {
  LineageBatchResponsePayload,
  LineageResponsePayload,
} from "./quantity.types";
import { useLineage } from "./useLineage";
import { useLineageBatch } from "./useLineageBatch";

const meta: LineageResponsePayload["meta"] = {
  generated_at: "2026-04-24T12:00:00Z",
  request_id: "req-lineage-hook",
  source_kinds: ["core_run"],
};

const lineage = {
  id: "lin_a",
  status: "verified",
  freshness: "current",
  exports: { openlineage: "/openlineage", prov: "/prov" },
} as const;

afterEach(() => {
  vi.restoreAllMocks();
});

describe("lineage hooks", () => {
  it("delegates one lineage lookup with the canonical temporal ref", async () => {
    const response = {
      meta,
      temporal_scope: { valid_at: "2026-04-15T12:00:00Z" },
      lineage,
    } satisfies LineageResponsePayload;
    const bridge = runtimeBridge();
    vi.mocked(bridge.fetchLineage).mockResolvedValue(response);

    const { result } = renderHook(
      () =>
        useLineage("lin_a", {
          temporalScope: { valid_at: "2026-04-15T12:00:00Z" },
        }),
      { wrapper: bridgeWrapper(bridge) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(bridge.fetchLineage).toHaveBeenCalledWith("lin_a", {
      valid_at: "2026-04-15T12:00:00Z",
    });
  });

  it("deduplicates batch lineage ids before delegating", async () => {
    const response = {
      meta,
      temporal_scope: null,
      lineages: [lineage],
    } satisfies LineageBatchResponsePayload;
    const bridge = runtimeBridge();
    vi.mocked(bridge.fetchLineageBatch).mockResolvedValue(response);

    const { result } = renderHook(() => useLineageBatch(["lin_a", "lin_a"]), {
      wrapper: bridgeWrapper(bridge),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(bridge.fetchLineageBatch).toHaveBeenCalledWith(["lin_a"], null);
  });
});

function runtimeBridge(): QuantityRuntimeBridgeValue {
  return {
    fetchLineage: vi.fn(),
    fetchLineageBatch: vi.fn(),
    fetchLineageExport: vi.fn(),
    temporalScope: null,
    trustMode: "off",
  };
}

function bridgeWrapper(value: QuantityRuntimeBridgeValue) {
  const QueryWrapper = createQueryHookWrapper();
  return function BridgeWrapper({ children }: PropsWithChildren) {
    return (
      <QueryWrapper>
        <QuantityRuntimeBridgeProvider value={value}>
          {children}
        </QuantityRuntimeBridgeProvider>
      </QueryWrapper>
    );
  };
}
