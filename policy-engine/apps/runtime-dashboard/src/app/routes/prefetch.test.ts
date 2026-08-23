const ensureQueryData = vi.fn();

vi.mock("@/api/queryClient", () => ({
  queryClient: { ensureQueryData },
}));

describe("route intent prefetch", () => {
  beforeEach(() => ensureQueryData.mockReset());

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
});
