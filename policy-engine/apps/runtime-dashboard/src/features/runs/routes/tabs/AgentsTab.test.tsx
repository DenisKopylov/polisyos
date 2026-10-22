import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import {
  createMemoryRouter,
  RouterProvider,
  useParams,
} from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runtimeApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryKeys";
import { TelemetryProvider } from "@/app/providers/TelemetryProvider";
import { RunInspectorProvider } from "@/features/runs/context/RunInspectorContext";
import AgentsTab from "@/features/runs/routes/tabs/AgentsTab";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";

const { subscribeMock } = vi.hoisted(() => ({ subscribeMock: vi.fn() }));

vi.mock("@/app/realtime/sseTransport", () => ({
  getSseRealtimeTransport: () => ({
    subscribe: (...args: unknown[]) => subscribeMock(...args),
  }),
}));

vi.mock("@/features/runs/components/AgentPipelinePanel", () => ({
  default: ({ payload }: { payload: { run_id: string; notes?: string[] } }) => (
    <div data-testid="agent-pipeline">
      {payload.run_id}:{payload.notes?.[0] ?? "no-note"}
    </div>
  ),
}));

const aliasRunId = "control-run-alias";
const attemptOne = "core-attempt-1";
const attemptTwo = "core-attempt-2";
const meta = {
  generated_at: "2026-03-09T10:00:00Z",
  request_id: "req-alias-agents",
  source_kinds: ["core_run"],
};

type RuntimeGetOptions = {
  params?: { path?: { run_id?: string } };
};

function successfulResponse(data: unknown) {
  return {
    data,
    error: undefined,
    response: new Response(JSON.stringify(data), {
      headers: { "Content-Type": "application/json" },
      status: 200,
    }),
  };
}

function failedResponse(status: number) {
  const error = { detail: "not found" };
  return {
    data: undefined,
    error,
    response: new Response(JSON.stringify(error), {
      headers: { "Content-Type": "application/json" },
      status,
    }),
  };
}

function detailsPayload(runId: string) {
  return {
    meta,
    temporal_scope: null,
    run: {
      run_id: runId,
      source_kind: "core_run",
      status: "running",
      tenant_id: "tenant-a",
      cell_id: "cell-a",
      has_trace: true,
    },
  };
}

function agentsPayload(runId: string, readNumber: number) {
  return {
    meta,
    pipeline: {
      run_id: runId,
      source_kind: "core_run",
      total_attempts: 0,
      attempts: [],
      notes: [`read-${readNumber}`],
    },
  };
}

function RunAgentsRoute() {
  const { runId } = useParams();
  return runId ? (
    <RunInspectorProvider runId={runId}>
      <AgentsTab />
    </RunInspectorProvider>
  ) : null;
}

describe("AgentsTab current-alias consumer", () => {
  let queryClient: QueryClient;
  let currentCoreRunId: string;
  let failDetailsRead: boolean;
  let holdNextAliasRead: boolean;
  let releaseAliasRead: (() => void) | undefined;
  let runAgentsRequests: string[];
  let readCounts: Map<string, number>;
  let getSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { gcTime: Infinity, retry: false } },
    });
    currentCoreRunId = attemptOne;
    failDetailsRead = false;
    holdNextAliasRead = false;
    releaseAliasRead = undefined;
    runAgentsRequests = [];
    readCounts = new Map();
    subscribeMock.mockReset();
    subscribeMock.mockImplementation(() => ({ close: vi.fn() }));
    vi.stubGlobal("EventSource", vi.fn() as unknown as typeof EventSource);

    getSpy = vi.spyOn(runtimeApiClient, "GET");
    getSpy.mockImplementation((async (...args: unknown[]) => {
      const [path, options] = args as [string, RuntimeGetOptions];
      const runId = options.params?.path?.run_id ?? "";

      if (path === "/api/v1/runs/{run_id}" && runId === aliasRunId) {
        if (failDetailsRead) {
          return failedResponse(500);
        }
        if (holdNextAliasRead) {
          holdNextAliasRead = false;
          return new Promise((resolve) => {
            releaseAliasRead = () =>
              resolve(successfulResponse(detailsPayload(currentCoreRunId)));
          });
        }
        return successfulResponse(detailsPayload(currentCoreRunId));
      }

      if (path === "/api/v1/runs/{run_id}/agents") {
        runAgentsRequests.push(runId);
        const readNumber = (readCounts.get(runId) ?? 0) + 1;
        readCounts.set(runId, readNumber);
        if (runId === aliasRunId) {
          return failedResponse(404);
        }
        return successfulResponse(agentsPayload(runId, readNumber));
      }

      return failedResponse(404);
    }) as never);
  });

  afterEach(() => {
    queryClient.clear();
    getSpy.mockRestore();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("follows the resolved Core attempt through alias remap and Core SSE invalidation", async () => {
    const router = createMemoryRouter(
      [{ path: "/runs/:runId/agents", element: <RunAgentsRoute /> }],
      { initialEntries: [`/runs/${aliasRunId}/agents`] },
    );
    render(
      <LocaleProvider>
        <QueryClientProvider client={queryClient}>
          <TelemetryProvider>
            <RouterProvider router={router} />
          </TelemetryProvider>
        </QueryClientProvider>
      </LocaleProvider>,
    );

    expect(await screen.findByTestId("agent-pipeline")).toHaveTextContent(
      `${attemptOne}:read-1`,
    );
    expect(runAgentsRequests).toContain(attemptOne);
    expect(runAgentsRequests).not.toContain(aliasRunId);
    expect(
      queryClient.getQueryData(queryKeys.runAgents(aliasRunId)),
    ).toBeUndefined();

    currentCoreRunId = attemptTwo;
    holdNextAliasRead = true;
    let aliasRefresh: Promise<void> | undefined;
    act(() => {
      aliasRefresh = queryClient.invalidateQueries({
        queryKey: queryKeys.run(aliasRunId),
      });
    });
    await waitFor(() => expect(releaseAliasRead).toBeTypeOf("function"));
    expect(screen.queryByTestId("agent-pipeline")).not.toBeInTheDocument();

    await act(async () => {
      releaseAliasRead?.();
      await aliasRefresh;
    });
    expect(await screen.findByTestId("agent-pipeline")).toHaveTextContent(
      `${attemptTwo}:read-1`,
    );
    expect(runAgentsRequests).toEqual([attemptOne, attemptTwo]);
    expect(
      queryClient.getQueryData(queryKeys.runAgents(attemptTwo)),
    ).toBeDefined();
    expect(
      queryClient.getQueryData(queryKeys.runAgents(aliasRunId)),
    ).toBeUndefined();

    const attemptTwoSubscription = subscribeMock.mock.calls.find(
      ([request]) => (request as { runId?: string }).runId === attemptTwo,
    );
    expect(attemptTwoSubscription).toBeDefined();
    const handlers = attemptTwoSubscription?.[1] as {
      onMessage?: (event: MessageEvent<string>) => void;
    };

    act(() => {
      handlers.onMessage?.({
        data: JSON.stringify({ event: "snapshot", run_id: attemptTwo }),
        lastEventId: "cursor-2",
      } as MessageEvent<string>);
    });
    await waitFor(() => expect(readCounts.get(attemptTwo)).toBe(2));
    expect(await screen.findByTestId("agent-pipeline")).toHaveTextContent(
      `${attemptTwo}:read-2`,
    );
    expect(runAgentsRequests).toEqual([attemptOne, attemptTwo, attemptTwo]);
  });

  it("does not request agents or imply availability without a usable Core id", async () => {
    currentCoreRunId = "   ";
    const router = createMemoryRouter(
      [{ path: "/runs/:runId/agents", element: <RunAgentsRoute /> }],
      { initialEntries: [`/runs/${aliasRunId}/agents`] },
    );
    render(
      <LocaleProvider>
        <QueryClientProvider client={queryClient}>
          <TelemetryProvider>
            <RouterProvider router={router} />
          </TelemetryProvider>
        </QueryClientProvider>
      </LocaleProvider>,
    );

    expect(await screen.findByRole("status")).toHaveTextContent("Unavailable");
    expect(runAgentsRequests).toEqual([]);
  });

  it("keeps a failed alias detail read in the tab error boundary", async () => {
    failDetailsRead = true;
    const router = createMemoryRouter(
      [{ path: "/runs/:runId/agents", element: <RunAgentsRoute /> }],
      { initialEntries: [`/runs/${aliasRunId}/agents`] },
    );
    render(
      <LocaleProvider>
        <QueryClientProvider client={queryClient}>
          <TelemetryProvider>
            <RouterProvider router={router} />
          </TelemetryProvider>
        </QueryClientProvider>
      </LocaleProvider>,
    );

    expect(
      await screen.findByText("Unable to load agent pipeline"),
    ).toBeInTheDocument();
    expect(runAgentsRequests).toEqual([]);
  });
});
