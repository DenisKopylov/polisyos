import { matchPath } from "react-router-dom";

import type { AppRouteHandle } from "@/app/routes/contracts";
import type { WorkspacePrefetchKey } from "@/app/workspaces";

type RouteManifestHandle = Pick<
  AppRouteHandle,
  "prefetch" | "routeId" | "workspaceKey"
>;

export type RoutePrefetchManifestEntry = {
  handle: RouteManifestHandle;
  kind:
    | "artifact"
    | "caseInspection"
    | "evidence"
    | "runDeck"
    | "runPaper"
    | "runTab"
    | "workspace";
  pattern: string;
};

function workspaceHandle(
  routeId: string,
  workspaceKey: NonNullable<RouteManifestHandle["workspaceKey"]>,
  prefetch?: WorkspacePrefetchKey[],
): RouteManifestHandle {
  return {
    prefetch,
    routeId,
    workspaceKey,
  };
}

export const ROUTE_PREFETCH_MANIFEST: RoutePrefetchManifestEntry[] = [
  {
    handle: workspaceHandle("dashboard.home", "commandCenter", [
      "capabilities",
      "health",
      "runsSample",
    ]),
    kind: "workspace",
    pattern: "/",
  },
  {
    handle: workspaceHandle("composer.launch", "scenarioComposer", [
      "capabilities",
      "llmProfiles",
    ]),
    kind: "workspace",
    pattern: "/compose",
  },
  {
    handle: workspaceHandle("runs.compare", "runsDecisions", [
      "capabilities",
      "runsSample",
    ]),
    kind: "workspace",
    pattern: "/runs/compare",
  },
  {
    handle: workspaceHandle("runs.list", "runsDecisions", [
      "capabilities",
      "runsSample",
    ]),
    kind: "workspace",
    pattern: "/runs",
  },
  {
    handle: workspaceHandle("runs.cycleBoard", "runsDecisions", [
      "capabilities",
    ]),
    kind: "workspace",
    pattern: "/runs/cycle-board",
  },
  {
    handle: workspaceHandle("runs.report", "runsDecisions"),
    kind: "runPaper",
    pattern: "/runs/:runId/report",
  },
  {
    handle: workspaceHandle("runs.caseWorkspace", "runsDecisions"),
    kind: "caseInspection",
    pattern: "/runs/:runId/case",
  },
  {
    handle: workspaceHandle("runs.deck", "runsDecisions"),
    kind: "runDeck",
    pattern: "/runs/:runId/deck",
  },
  {
    handle: workspaceHandle("runs.detail", "runsDecisions"),
    kind: "runTab",
    pattern: "/runs/:runId/:tab",
  },
  {
    handle: workspaceHandle("evidence.fabric", "evidenceFabric", [
      "capabilities",
      "connectors",
      "sourceProfiles",
      "dataIndexStats",
      "dataPromotionCandidates",
    ]),
    kind: "evidence",
    pattern: "/evidence",
  },
  {
    handle: workspaceHandle("lex.knowledge", "lexKnowledge", ["capabilities"]),
    kind: "workspace",
    pattern: "/knowledge",
  },
  {
    handle: workspaceHandle("platform.health", "platformHealth", [
      "health",
      "capabilities",
      "connectors",
      "runs",
    ]),
    kind: "workspace",
    pattern: "/platform",
  },
  {
    handle: workspaceHandle("artifacts.inspector", "runsDecisions"),
    kind: "artifact",
    pattern: "/artifacts/:artifactId",
  },
];

export function resolveRoutePrefetchEntry(pathname: string) {
  for (const entry of ROUTE_PREFETCH_MANIFEST) {
    const match = matchPath({ path: entry.pattern, end: true }, pathname);
    if (match) {
      return {
        entry,
        params: match.params,
      };
    }
  }

  return null;
}
