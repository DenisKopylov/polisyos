import type { LoaderFunctionArgs } from "react-router-dom";
import { waitFor } from "@testing-library/react";

import { ROUTE_LOADER_EVENT_NAME } from "@/app/routes/routeInstrumentation";

const ensureQueryData = vi.fn();

vi.mock("@/api/queryClient", () => ({
  queryClient: {
    ensureQueryData,
  },
}));

describe("route loaders", () => {
  function buildLoaderArgs(
    request: Request,
    params: Record<string, string> = {},
  ): LoaderFunctionArgs {
    return {
      context: undefined,
      params,
      request,
      unstable_pattern: "",
    };
  }

  beforeEach(() => {
    ensureQueryData.mockResolvedValue(null);
  });

  afterEach(() => {
    ensureQueryData.mockReset();
    vi.useRealTimers();
  });

  it("primes workspace prefetch keys and emits loader-ready events", async () => {
    const detailPromise = new Promise<CustomEvent>((resolve) => {
      window.addEventListener(
        ROUTE_LOADER_EVENT_NAME,
        (event) => resolve(event as CustomEvent),
        { once: true },
      );
    });
    const { createWorkspaceLoader } = await import("@/app/routes/loaders");

    const result = await createWorkspaceLoader("dashboard.home", [
      "capabilities",
      "health",
    ])();

    expect(result).toBeNull();
    expect(ensureQueryData).toHaveBeenCalledTimes(2);

    const detail = (await detailPromise).detail as {
      routeId: string;
      status: string;
    };
    expect(detail).toMatchObject({
      routeId: "dashboard.home",
      status: "ready",
    });
  });

  it("returns detail bootstrap state for run routes", async () => {
    const { createRunDetailLoader } = await import("@/app/routes/loaders");

    const result = await createRunDetailLoader("runs.report")(
      buildLoaderArgs(new Request("http://localhost/runs/run-42/report"), {
        runId: "run-42",
      }),
    );

    expect(result).toEqual({
      runBootstrapPending: false,
      runId: "run-42",
    });
    expect(ensureQueryData).toHaveBeenCalled();
  });

  it("hydrates evidence workspace search state", async () => {
    const { loadEvidenceWorkspace } = await import("@/app/routes/loaders");

    const result = await loadEvidenceWorkspace(
      buildLoaderArgs(
        new Request(
          "http://localhost/evidence?runId=run-42&focus=promotion&promotionId=promotion-1",
        ),
      ),
    );

    await waitFor(() => expect(ensureQueryData).toHaveBeenCalled());
    expect(result).toMatchObject({
      focus: "promotion",
      promotionId: "promotion-1",
      runId: "run-42",
    });
  });

  it("throws a 400 response when run id params are missing", async () => {
    const { createRunDetailLoader } = await import("@/app/routes/loaders");

    await expect(
      createRunDetailLoader()(
        buildLoaderArgs(new Request("http://localhost/runs/detail")),
      ),
    ).rejects.toMatchObject({
      status: 400,
      statusText: "",
    });
  });

  it("returns bootstrap pending after repeated 404 detail misses", async () => {
    vi.useFakeTimers();
    ensureQueryData.mockImplementationOnce(() => Promise.resolve(null));
    ensureQueryData.mockImplementation(() => {
      const error = Object.assign(new Error("not_found"), {
        code: "not_found",
        status: 404,
      });
      return Promise.reject(error);
    });
    const { createRunDetailLoader } = await import("@/app/routes/loaders");

    const promise = createRunDetailLoader("runs.detail")(
      buildLoaderArgs(new Request("http://localhost/runs/run-404"), {
        runId: "run-404",
      }),
    );
    await vi.runAllTimersAsync();

    await expect(promise).resolves.toEqual({
      runBootstrapPending: true,
      runId: "run-404",
    });
    expect(ensureQueryData).toHaveBeenCalledTimes(9);
  });

  it("hydrates tab-specific queries once a run is ready", async () => {
    const { createRunTabLoader } = await import("@/app/routes/loaders");

    const result = await createRunTabLoader("overview")(
      buildLoaderArgs(new Request("http://localhost/runs/run-42/overview"), {
        runId: "run-42",
      }),
    );

    expect(result).toEqual({
      runBootstrapPending: false,
      runId: "run-42",
      tabKey: "overview",
    });
    expect(ensureQueryData.mock.calls.map((call) => call[0]?.queryKey)).toEqual(
      [
        ["runtime", "run", "run-42"],
        ["runtime", "run", "run-42", "agents"],
        ["runtime", "run", "run-42", "debug", "governance"],
        ["runtime", "run", "run-42", "evidence-context"],
        ["runtime", "run", "run-42", "timeline"],
      ],
    );
  });

  it("bubbles non-404 bootstrap failures from run tab loaders", async () => {
    ensureQueryData.mockRejectedValue(new Error("runtime_failed"));
    const { createRunTabLoader } = await import("@/app/routes/loaders");

    await expect(
      createRunTabLoader("workflow")(
        buildLoaderArgs(new Request("http://localhost/runs/run-42/workflow"), {
          runId: "run-42",
        }),
      ),
    ).rejects.toThrow("runtime_failed");
  });
});
