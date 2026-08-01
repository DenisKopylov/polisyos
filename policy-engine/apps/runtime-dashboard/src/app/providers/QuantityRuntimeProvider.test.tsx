import type { PropsWithChildren, ReactElement } from "react";
import { render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  mockRuntimeGetFailure,
  mockRuntimeGetSuccess,
  mockRuntimePostSuccess,
} from "@/test/runtimeApi";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import {
  type QuantityValue,
  type TemporalRef,
  useQuantityRuntimeBridge,
} from "@/shared/ui/quantity";

import { TemporalCursorProvider } from "./TemporalCursorProvider";
import { TrustViewProvider } from "./TrustViewProvider";
import { QuantityRuntimeProvider } from "./QuantityRuntimeProvider";

const meta = {
  generated_at: "2026-07-19T12:00:00Z",
  request_id: "req-quantity-runtime-provider",
  source_kinds: ["core_run"],
} as const;

const temporalScope = {
  branch: "main",
  scenario_id: "scenario-a",
  snapshot_id: "snapshot-a",
  tx_at: "2026-07-18T12:00:00Z",
  valid_at: "2026-07-17T12:00:00Z",
} satisfies TemporalRef;

const committedTemporalScope = {
  ...temporalScope,
  tx_at: "2026-07-18T12:00:00.000Z",
  valid_at: "2026-07-17T12:00:00.000Z",
} satisfies TemporalRef;

const lineage = {
  id: "lineage-a",
  status: "verified",
  freshness: "current",
  exports: {
    openlineage: "/api/v1/lineage/lineage-a/export/openlineage",
    prov: "/api/v1/lineage/lineage-a/export/prov",
  },
} as const;

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
});

describe("QuantityRuntimeProvider", () => {
  it("maps the committed cursor and validates a single lineage response", async () => {
    window.history.replaceState(
      null,
      "",
      "/runs/run-a?valid_at=2026-07-17T12%3A00%3A00Z&tx_at=2026-07-18T12%3A00%3A00Z&branch=main&snapshot_id=snapshot-a&scenario_id=scenario-a",
    );
    const getSpy = mockRuntimeGetSuccess({
      lineage,
      meta,
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    expect(result.current.temporalScope).toEqual(committedTemporalScope);
    await expect(
      result.current.fetchLineage("lineage-a", result.current.temporalScope),
    ).resolves.toMatchObject({
      lineage: {
        compact_summary: [],
        edges: [],
        metadata: {},
        nodes: [],
      },
    });
    expect(getSpy).toHaveBeenCalledWith("/api/v1/lineage/{lineage_id}", {
      params: {
        path: { lineage_id: "lineage-a" },
        query: committedTemporalScope,
      },
    });

    getSpy.mockResolvedValueOnce({
      data: { lineage: { id: "lineage-a" }, meta },
      error: undefined,
      response: new Response("{}", { status: 200 }),
    } as never);
    await expect(
      result.current.fetchLineage("lineage-a", null),
    ).rejects.toThrow();
  });

  it("posts batch identities and normalizes optional graph collections", async () => {
    const postSpy = mockRuntimePostSuccess({
      lineages: [lineage],
      meta,
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    const response = await result.current.fetchLineageBatch(
      ["lineage-a", "lineage-b"],
      temporalScope,
    );

    expect(response.lineages?.[0]).toMatchObject({
      compact_summary: [],
      edges: [],
      metadata: {},
      nodes: [],
    });
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: { lineage_ids: ["lineage-a", "lineage-b"] },
      params: { query: temporalScope },
    });
  });

  it("routes exports by format and preserves transport failures", async () => {
    const getSpy = mockRuntimeGetSuccess({
      format: "openlineage",
      lineage_id: "lineage-a",
      meta,
      payload: { run: { runId: "lineage-a" } },
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    await expect(
      result.current.fetchLineageExport(
        "lineage-a",
        "openlineage",
        temporalScope,
      ),
    ).resolves.toMatchObject({ format: "openlineage" });
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/lineage/{lineage_id}/export/openlineage",
      expect.any(Object),
    );

    getSpy.mockRestore();
    const failedGet = mockRuntimeGetFailure(503, {
      code: "lineage_unavailable",
      detail: "lineage export offline",
      request_id: "req-export-failure",
      status: 503,
      status_code: 503,
      title: "Lineage unavailable",
      type: "about:blank",
    });
    await expect(
      result.current.fetchLineageExport("lineage-a", "prov", temporalScope),
    ).rejects.toMatchObject({
      code: "lineage_unavailable",
      detail: "lineage export offline",
      name: "RuntimeApiRequestError",
      status: 503,
    });
    expect(failedGet).toHaveBeenCalledWith(
      "/api/v1/lineage/{lineage_id}/export/prov",
      expect.any(Object),
    );
  });

  it("renders trust metadata only when the generated lineage carries it", () => {
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });
    const withoutTrust = quantity();

    expect(
      result.current.renderTrustMetadata?.(withoutTrust, "expanded"),
    ).toBeNull();

    const withTrust: QuantityValue = {
      ...withoutTrust,
      lineage: {
        ...withoutTrust.lineage,
        hash: "sha256:lineage-a",
        trust_metadata: {
          dispute_status: "none",
          freshness: "current",
          hash: "sha256:lineage-a",
          temporal_scope: temporalScope,
          verification_status: "verified",
          verified_at: "2026-07-19T11:00:00Z",
          verified_by: "runtime-verifier",
          verification_method: "content-hash",
        },
      },
    };
    const trustNode = result.current.renderTrustMetadata?.(
      withTrust,
      "expanded",
    );
    render(trustNode as ReactElement, {
      wrapper: providerWrapper,
    });

    expect(screen.getByText("runtime-verifier")).toBeInTheDocument();
  });
});

function providerWrapper({ children }: PropsWithChildren) {
  return (
    <LocaleProvider>
      <TemporalCursorProvider>
        <TrustViewProvider>
          <QuantityRuntimeProvider>{children}</QuantityRuntimeProvider>
        </TrustViewProvider>
      </TemporalCursorProvider>
    </LocaleProvider>
  );
}

function quantity(): QuantityValue {
  return {
    lineage,
    metric_id: "metric-a",
    point: 42,
    quantity_class: "decision",
    time: temporalScope,
    unit: { code: "count", system: "unit" },
  };
}
