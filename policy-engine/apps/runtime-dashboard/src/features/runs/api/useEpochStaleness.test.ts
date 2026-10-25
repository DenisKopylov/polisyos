import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  epochProjection,
  epochStalenessSixClassFixture,
  withServerSemanticHash,
} from "@/test/fixtures/epochStaleness";
import { createQueryHookHarness } from "@/test/queryHook";

import {
  createEpochStalenessClient,
  type EpochStalenessClient,
  useEpochStaleness,
} from "./useEpochStaleness";

function reorderedWire(candidate: Record<string, unknown>): string {
  return `{
  "projection": ${JSON.stringify(candidate.projection)},
  "meta": ${JSON.stringify(candidate.meta)}
}\n`;
}

describe("epoch staleness exact-byte client", () => {
  it("keeps the Core-only request disabled before identity resolution", () => {
    const getRunEpochStaleness = vi.fn();
    const client = {
      getRunEpochStaleness,
    } as unknown as EpochStalenessClient;
    const harness = createQueryHookHarness();

    const { result } = renderHook(
      () => useEpochStaleness({ enabled: false, runId: "" }, client),
      { wrapper: harness.wrapper },
    );

    expect(getRunEpochStaleness).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
    expect(result.current.isPending).toBe(true);
  });

  it("captures reordered response bytes before generated-client parsing", async () => {
    const candidate = epochStalenessSixClassFixture();
    const wire = reorderedWire(candidate);
    const requests: Request[] = [];
    const fetchRuntime = vi.fn(async (request: Request) => {
      requests.push(request);
      return Promise.resolve(
        new Response(wire, {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }),
      );
    });
    const client = createEpochStalenessClient({
      baseUrl: "https://runtime.example",
      fetchRuntime,
    });

    const captured = await client.getRunEpochStaleness({
      runId: "R_core_api_001",
      temporalScope: { branch: "main" },
    });

    expect(new TextDecoder().decode(captured.rawBytes)).toBe(wire);
    expect(captured.projection.perturbations).toHaveLength(6);
    const request = requests[0];
    expect(request).toBeInstanceOf(Request);
    expect(request?.method).toBe("GET");
    expect(request?.url).toBe(
      "https://runtime.example/api/v1/temporal/runs/R_core_api_001/epoch-staleness?branch=main",
    );
  });

  it("rejects unknown wire fields before returning a captured packet", async () => {
    const candidate = epochStalenessSixClassFixture();
    const denominator = epochProjection(candidate).denominator as Record<
      string,
      unknown
    >;
    denominator.unknown_nested = true;
    const wire = reorderedWire(withServerSemanticHash(candidate));
    const client = createEpochStalenessClient({
      baseUrl: "https://runtime.example",
      fetchRuntime: async () =>
        new Response(wire, {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }),
    });

    await expect(
      client.getRunEpochStaleness({ runId: "R_core_api_001" }),
    ).rejects.toThrow(/contract_error/);
  });

  it("rejects a valid signed projection for another requested run", async () => {
    const candidate = epochStalenessSixClassFixture();
    epochProjection(candidate).run_id = "R_other";
    const wire = reorderedWire(withServerSemanticHash(candidate));
    const client = createEpochStalenessClient({
      baseUrl: "https://runtime.example",
      fetchRuntime: async () =>
        new Response(wire, {
          headers: { "Content-Type": "application/json" },
          status: 200,
        }),
    });

    await expect(
      client.getRunEpochStaleness({ runId: "R_core_api_001" }),
    ).rejects.toThrow(/requested replay identity/);
  });
});
