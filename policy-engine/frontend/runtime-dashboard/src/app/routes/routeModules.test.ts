import { artifactRouteHandle } from "@/features/artifacts/routes.public";
import { loginRouteHandle } from "@/features/auth";
import { composerRouteHandle } from "@/features/composer";
import { dashboardRouteHandle } from "@/features/dashboard";
import { evidenceRouteHandle } from "@/features/evidence/routes.public";
import { lexRouteHandle } from "@/features/lex";
import { platformRouteHandle } from "@/features/platform";
import {
  runDetailRouteHandle,
  runReportRouteHandle,
  runsCompareRouteHandle,
  runsListRouteHandle,
  runsRoutes,
} from "@/features/runs/routes.public";

describe("route modules", () => {
  it("exposes href builders and search parsers for feature routes", () => {
    expect(loginRouteHandle.buildHref({ next: "/runs" })).toBe(
      "/login?next=%2Fruns",
    );
    expect(
      composerRouteHandle.buildHref({ fromRun: "run-1", mode: "workflow" }),
    ).toBe("/compose?fromRun=run-1&mode=workflow");
    expect(dashboardRouteHandle.buildHref()).toBe("/");
    expect(
      evidenceRouteHandle.buildHref({
        focus: "promotion",
        promotionId: "promotion-1",
        runId: "run-1",
      }),
    ).toBe("/evidence?focus=promotion&promotionId=promotion-1&runId=run-1");
    expect(
      artifactRouteHandle.buildHref({
        artifactId: "artifact-1",
        tab: "schema",
      }),
    ).toBe("/artifacts/artifact-1?tab=schema");
    expect(lexRouteHandle.buildHref({ pipelineId: "pipe-1", q: "water" })).toBe(
      "/knowledge?pipelineId=pipe-1&q=water",
    );
    expect(platformRouteHandle.buildHref({ section: "health" })).toBe(
      "/platform?section=health",
    );
  });

  it("keeps runs route metadata decision-complete", () => {
    expect(runsListRouteHandle.prefetch).toEqual([
      "capabilities",
      "runsSample",
    ]);
    expect(
      runsCompareRouteHandle.buildHref({ base: "run-1", target: "run-2" }),
    ).toBe("/runs/compare?base=run-1&target=run-2");
    expect(runReportRouteHandle.buildHref({ runId: "run-1" })).toBe(
      "/runs/run-1/report",
    );
    expect(
      runDetailRouteHandle.buildHref({ runId: "run-1", tab: "debug" }),
    ).toBe("/runs/run-1/debug");
    expect(runsRoutes).toHaveLength(4);
    expect(runsRoutes[3]?.children).toHaveLength(8);
  });
});
