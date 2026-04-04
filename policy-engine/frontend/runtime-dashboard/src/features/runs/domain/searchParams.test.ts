import {
  buildRunCompareHref,
  buildRunDetailHref,
  buildRunReportHref,
  buildRunsListHref,
  parseRunCompareSearchParams,
  parseRunDetailLegacySearchParams,
  parseRunsListSearchParams,
} from "@/features/runs/domain/searchParams";

describe("runs search params", () => {
  it("parses and builds runs list filters", () => {
    expect(
      parseRunsListSearchParams(
        "/runs?status=completed&from=2026-03-01T08:00&q=policy&cursor=cursor-1",
      ),
    ).toEqual({
      cursor: "cursor-1",
      from: "2026-03-01T08:00",
      q: "policy",
      status: "completed",
      to: undefined,
    });

    expect(
      buildRunsListHref({
        q: "policy",
        status: "completed",
      }),
    ).toBe("/runs?q=policy&status=completed");
  });

  it("parses compare params and builds detail/report hrefs", () => {
    expect(
      parseRunCompareSearchParams("/runs/compare?base=run-1&target=run-2"),
    ).toEqual({
      base: "run-1",
      target: "run-2",
    });
    expect(buildRunCompareHref({ base: "run-1", target: "run-2" })).toBe(
      "/runs/compare?base=run-1&target=run-2",
    );
    expect(buildRunDetailHref("run-1", "debug")).toBe("/runs/run-1/debug");
    expect(buildRunReportHref("run-1")).toBe("/runs/run-1/report");
  });

  it("keeps legacy tab search parsing explicit", () => {
    expect(
      parseRunDetailLegacySearchParams("/runs/run-1/overview?tab=workflow"),
    ).toEqual({
      tab: "workflow",
    });
  });
});
