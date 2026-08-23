import {
  resolveRoutePrefetchEntry,
  ROUTE_PREFETCH_MANIFEST,
} from "./routeManifest";

describe("route prefetch manifest", () => {
  it("classifies report as authorization-before-query paper", () => {
    const resolved = resolveRoutePrefetchEntry("/runs/run-42/report");
    expect(resolved).toMatchObject({
      entry: { kind: "runPaper", pattern: "/runs/:runId/report" },
      params: { runId: "run-42" },
    });
  });

  it("classifies case inspection before the generic run tab", () => {
    const resolved = resolveRoutePrefetchEntry("/runs/run-42/case");
    expect(resolved).toMatchObject({
      entry: { kind: "caseInspection", pattern: "/runs/:runId/case" },
      params: { runId: "run-42" },
    });
    const caseIndex = ROUTE_PREFETCH_MANIFEST.findIndex(
      (entry) => entry.pattern === "/runs/:runId/case",
    );
    const dynamicIndex = ROUTE_PREFETCH_MANIFEST.findIndex(
      (entry) => entry.pattern === "/runs/:runId/:tab",
    );
    expect(caseIndex).toBeGreaterThanOrEqual(0);
    expect(caseIndex).toBeLessThan(dynamicIndex);
  });

  it("resolves the Cycle Board as a static capability-only workspace route", () => {
    const resolved = resolveRoutePrefetchEntry("/runs/cycle-board");

    expect(resolved).toEqual({
      entry: {
        handle: {
          prefetch: ["capabilities"],
          routeId: "runs.cycleBoard",
          workspaceKey: "runsDecisions",
        },
        kind: "workspace",
        pattern: "/runs/cycle-board",
      },
      params: {},
    });
    const staticIndex = ROUTE_PREFETCH_MANIFEST.findIndex(
      (entry) => entry.pattern === "/runs/cycle-board",
    );
    const dynamicIndex = ROUTE_PREFETCH_MANIFEST.findIndex(
      (entry) => entry.pattern === "/runs/:runId/:tab",
    );
    expect(staticIndex).toBeGreaterThanOrEqual(0);
    expect(staticIndex).toBeLessThan(dynamicIndex);
  });
});
