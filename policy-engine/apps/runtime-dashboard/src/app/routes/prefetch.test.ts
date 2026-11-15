const ensureQueryData = vi.fn();

vi.mock("@/api/queryClient", () => ({
  queryClient: { ensureQueryData },
}));

import { RuntimeApiRequestError } from "@/api/http";

describe("route intent prefetch", () => {
  beforeEach(() => {
    ensureQueryData.mockReset();
  });

  it("does not fetch paper or case authority before review authorization", async () => {
    const { prefetchRouteHref } = await import("@/app/routes/prefetch");

    await prefetchRouteHref(
      "/runs/run-42/report?manifest_artifact_id=sha256%3Aabc",
    );
    await prefetchRouteHref(
      "/runs/run-42/case?manifest_artifact_id=sha256%3Aabc",
    );

    expect(ensureQueryData).not.toHaveBeenCalled();
  });

  it("keeps the workflow route available when lineage is authority-downgraded", async () => {
    const deniedLineage = new RuntimeApiRequestError(
      {
        type: "https://polisyos.dev/problems/conflict",
        title: "Authority surface admission blocked",
        status: 409,
        status_code: 409,
        detail:
          "Run lineage blocked or downgraded by composed authority surface admission",
        code: "authority_surface_admission_blocked",
      },
      409,
      "Failed to load lineage for run-42",
    );
    ensureQueryData.mockImplementation(
      (options: { queryKey: readonly unknown[] } | undefined) => {
        if (!options) {
          throw new Error("missing query options in admission prefetch test");
        }
        return options.queryKey.includes("lineage")
          ? Promise.reject(deniedLineage)
          : Promise.resolve(undefined);
      },
    );
    const { primeRunTab } = await import("@/app/routes/prefetch");

    await expect(primeRunTab("run-42", "workflow")).resolves.toEqual({
      runBootstrapPending: false,
      runId: "run-42",
      tabKey: "workflow",
    });
    expect(ensureQueryData).toHaveBeenCalledTimes(3);
  });

  it("keeps detail and unrelated workflow or lineage failures fatal", async () => {
    const { primeRunTab } = await import("@/app/routes/prefetch");
    const detailsFailure = new Error("run details unavailable");
    ensureQueryData.mockRejectedValueOnce(detailsFailure);

    await expect(primeRunTab("run-42", "workflow")).rejects.toBe(
      detailsFailure,
    );
    expect(ensureQueryData).toHaveBeenCalledTimes(1);

    for (const failedSurface of ["workflow", "lineage"] as const) {
      ensureQueryData.mockReset();
      const failure = new Error(`${failedSurface} unavailable`);
      ensureQueryData.mockImplementation(
        (options: { queryKey: readonly unknown[] } | undefined) => {
          if (!options) {
            throw new Error("missing query options in fatal-error test");
          }
          return options.queryKey.includes(failedSurface)
            ? Promise.reject(failure)
            : Promise.resolve(undefined);
        },
      );

      await expect(primeRunTab("run-42", "workflow")).rejects.toBe(failure);
    }
  });
});
