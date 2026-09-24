import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterAll, describe, expect, it, vi } from "vitest";

import {
  useRunScenarios,
  useScenarioCapabilities,
} from "@/api/hooks/useScenarioCapabilities";
import { server } from "@/test/msw/server";
import { createQueryHookHarness } from "@/test/queryHook";

// Node's Request needs an absolute URL; browsers resolve the production default
// against the page origin. Keep the real client and mock only the HTTP server.
vi.hoisted(() => {
  vi.stubEnv("VITE_RUNTIME_API_URL", "http://localhost");
});
afterAll(() => vi.unstubAllEnvs());

const meta = {
  generated_at: "2026-09-11T09:00:00Z",
  request_id: "request-scenarios",
  source_kinds: ["core_run"],
};
const temporalScope = {
  branch: "main",
  snapshotId: "snapshot-a",
  validAt: "2026-09-10T00:00:00Z",
  txAt: "2026-09-11T00:00:00Z",
};

describe("scenario query admission", () => {
  it("keeps scenario and temporal selection in both the real request and cache identity", async () => {
    const requests: URL[] = [];
    server.use(
      http.get("*/api/v1/runs/:runId/scenarios", ({ request, params }) => {
        const url = new URL(request.url);
        requests.push(url);
        return HttpResponse.json({
          meta,
          run_id: params.runId,
          temporal_scope: Object.fromEntries(url.searchParams),
          scenarios: [],
        });
      }),
    );
    const harness = createQueryHookHarness();
    const { result, rerender } = renderHook(
      ({ scenarioId }) =>
        useRunScenarios("source-run", {
          temporalScope,
          scenarioScope: { scenarioId, mode: "scenario_only" },
        }),
      { wrapper: harness.wrapper, initialProps: { scenarioId: "scenario-a" } },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.temporal_scope).toEqual({
      branch: "main",
      snapshot_id: "snapshot-a",
      valid_at: "2026-09-10T00:00:00.000Z",
      tx_at: "2026-09-11T00:00:00.000Z",
      scenario_id: "scenario-a",
    });
    rerender({ scenarioId: "scenario-b" });
    await waitFor(() =>
      expect(result.current.data?.temporal_scope?.scenario_id).toBe(
        "scenario-b",
      ),
    );
    expect(requests.map((request) => request.pathname)).toEqual([
      "/api/v1/runs/source-run/scenarios",
      "/api/v1/runs/source-run/scenarios",
    ]);
    expect(
      requests.map((request) => request.searchParams.get("scenario_id")),
    ).toEqual(["scenario-a", "scenario-b"]);
    const identities = harness.queryClient
      .getQueryCache()
      .getAll()
      .map((query) => query.queryKey);
    expect(identities).toContainEqual([
      "runtime",
      "run",
      "source-run",
      "scenarios",
      {
        temporal: {
          branch: "main",
          snapshotId: "snapshot-a",
          validAt: "2026-09-10T00:00:00.000Z",
          txAt: "2026-09-11T00:00:00.000Z",
          scenarioId: "scenario-a",
        },
      },
      { scenario: { mode: "scenario_only", scenarioId: "scenario-a" } },
    ]);
    expect(identities).toContainEqual([
      "runtime",
      "run",
      "source-run",
      "scenarios",
      {
        temporal: {
          branch: "main",
          snapshotId: "snapshot-a",
          validAt: "2026-09-10T00:00:00.000Z",
          txAt: "2026-09-11T00:00:00.000Z",
          scenarioId: "scenario-b",
        },
      },
      { scenario: { mode: "scenario_only", scenarioId: "scenario-b" } },
    ]);
  });

  it("does not request unknown runs or explicitly disabled scenario lists", () => {
    const { result } = renderHook(
      () => ({
        absent: useRunScenarios(undefined),
        disabled: useRunScenarios("source-run", { enabled: false }),
      }),
      { wrapper: createQueryHookHarness().wrapper },
    );
    expect(result.current.absent.fetchStatus).toBe("idle");
    expect(result.current.disabled.fetchStatus).toBe("idle");
    expect(result.current.absent.data).toBeUndefined();
    expect(result.current.disabled.data).toBeUndefined();
  });

  it("returns an admitted scenario list without inventing an absent temporal selection", async () => {
    server.use(
      http.get("*/api/v1/runs/:runId/scenarios", ({ request, params }) => {
        expect(new URL(request.url).search).toBe("");
        return HttpResponse.json({ meta, run_id: params.runId, scenarios: [] });
      }),
    );
    const { result } = renderHook(() => useRunScenarios("source-run"), {
      wrapper: createQueryHookHarness().wrapper,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      meta,
      run_id: "source-run",
      scenarios: [],
    });
  });

  it("preserves an unavailable scenario response as an error rather than empty support", async () => {
    server.use(
      http.get("*/api/v1/runs/:runId/scenarios", () =>
        HttpResponse.json(
          {
            detail: "Scenario evidence unavailable",
            code: "scenario_unavailable",
            request_id: "failed-request",
          },
          { status: 503 },
        ),
      ),
    );
    const { result } = renderHook(() => useRunScenarios("source-run"), {
      wrapper: createQueryHookHarness().wrapper,
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toMatchObject({
      status: 503,
      code: "scenario_unavailable",
      requestId: "failed-request",
    });
  });

  it("rejects malformed successful scenario data instead of admitting it to consumers", async () => {
    server.use(
      http.get("*/api/v1/runs/:runId/scenarios", () =>
        HttpResponse.json({
          meta,
          run_id: "source-run",
          scenarios: [{ id: "not-a-manifest" }],
        }),
      ),
    );
    const { result } = renderHook(() => useRunScenarios("source-run"), {
      wrapper: createQueryHookHarness().wrapper,
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error?.name).toBe("ZodError");
  });

  it("binds capability requests to the selected scenario and temporal scope", async () => {
    server.use(
      http.get(
        "*/api/v1/scenarios/:scenarioId/capabilities",
        ({ request, params }) => {
          const query = Object.fromEntries(new URL(request.url).searchParams);
          expect(query).toEqual({
            branch: "main",
            snapshot_id: "snapshot-a",
            valid_at: "2026-09-10T00:00:00.000Z",
            tx_at: "2026-09-11T00:00:00.000Z",
            scenario_id: "scenario-a",
          });
          return HttpResponse.json({
            meta,
            scenario_id: params.scenarioId,
            temporal_scope: query,
            capabilities: [],
          });
        },
      ),
    );
    const { result } = renderHook(
      () => useScenarioCapabilities("scenario-a", { temporalScope }),
      { wrapper: createQueryHookHarness().wrapper },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.scenario_id).toBe("scenario-a");
    expect(result.current.data?.capabilities).toEqual([]);
  });

  it("keeps unknown or disabled capability queries idle", () => {
    const { result } = renderHook(
      () => ({
        absent: useScenarioCapabilities(undefined),
        disabled: useScenarioCapabilities("scenario-a", { enabled: false }),
      }),
      { wrapper: createQueryHookHarness().wrapper },
    );
    expect(result.current.absent.fetchStatus).toBe("idle");
    expect(result.current.disabled.fetchStatus).toBe("idle");
  });

  it("keeps unavailable capabilities distinguishable from an empty supported result", async () => {
    server.use(
      http.get("*/api/v1/scenarios/:scenarioId/capabilities", () =>
        HttpResponse.json(
          {
            detail: "Capabilities unavailable",
            code: "capabilities_unavailable",
          },
          { status: 503 },
        ),
      ),
    );
    const { result } = renderHook(() => useScenarioCapabilities("scenario-a"), {
      wrapper: createQueryHookHarness().wrapper,
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toMatchObject({
      status: 503,
      code: "capabilities_unavailable",
    });
  });
});
