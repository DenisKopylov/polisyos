import { lazy } from "react";
import type { RouteObject } from "react-router-dom";
import { Navigate } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import {
  createRunDetailLoader,
  createRunTabLoader,
  createWorkspaceLoader,
} from "@/app/routes/loaders";
import { TabBoundary } from "@/app/routes/TabBoundary";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import {
  buildRunCompareHref,
  buildRunDetailHref,
  buildRunReportHref,
  buildRunsListHref,
  parseRunCompareSearchParams,
  parseRunDetailLegacySearchParams,
  parseRunsListSearchParams,
  type RunCompareSearchParams,
  type RunDetailLegacySearchParams,
  type RunsListSearchParams,
} from "@/features/runs/domain/searchParams";
import type { RunDetailTab } from "@/features/runs/routes/useRunDetailSummary";

const RunsListPage = lazy(() => import("@/features/runs/routes/RunsListPage"));
const RunComparePage = lazy(
  () => import("@/features/runs/routes/RunComparePage"),
);
const RunInspectorLayout = lazy(
  () => import("@/features/runs/routes/RunDetailLayout"),
);
const RunReportPage = lazy(
  () => import("@/features/runs/routes/RunReportPage"),
);
const RunOverviewTab = lazy(
  () => import("@/features/runs/routes/tabs/OverviewTab"),
);
const RunGovernanceTab = lazy(
  () => import("@/features/runs/routes/tabs/GovernanceTab"),
);
const RunEvidenceTab = lazy(
  () => import("@/features/runs/routes/tabs/EvidenceTab"),
);
const RunWorkflowTab = lazy(
  () => import("@/features/runs/routes/tabs/WorkflowTab"),
);
const RunArtifactsTab = lazy(
  () => import("@/features/runs/routes/tabs/ArtifactsTab"),
);
const RunAgentsTab = lazy(
  () => import("@/features/runs/routes/tabs/AgentsTab"),
);
const RunDebugTab = lazy(() => import("@/features/runs/routes/tabs/DebugTab"));

type RunRouteHrefInput = { runId: string };
type RunTabRouteHrefInput = RunRouteHrefInput & { tab?: RunDetailTab };

export const runsListRouteHandle = {
  buildHref: buildRunsListHref,
  parseSearch: parseRunsListSearchParams,
  prefetch: ["capabilities", "runsSample"],
  routeId: "runs.list",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<RunsListSearchParams>["handle"];

export const runsCompareRouteHandle = {
  buildHref: buildRunCompareHref,
  parseSearch: parseRunCompareSearchParams,
  prefetch: ["capabilities", "runsSample"],
  routeId: "runs.compare",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<RunCompareSearchParams>["handle"];

export const runReportRouteHandle = {
  buildHref: (input) => buildRunReportHref(input?.runId ?? ""),
  parseSearch: () => ({}),
  routeId: "runs.report",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<Record<string, never>, RunRouteHrefInput>["handle"];

export const runDetailRouteHandle = {
  buildHref: (input) =>
    buildRunDetailHref(input?.runId ?? "", input?.tab ?? "overview"),
  parseSearch: parseRunDetailLegacySearchParams,
  routeId: "runs.detail",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<
  RunDetailLegacySearchParams,
  RunTabRouteHrefInput
>["handle"];

export const runsListLoader = createWorkspaceLoader(
  runsListRouteHandle.routeId,
  runsListRouteHandle.prefetch,
);
export const runsCompareLoader = createWorkspaceLoader(
  runsCompareRouteHandle.routeId,
  runsCompareRouteHandle.prefetch,
);
export const runReportLoader = createRunDetailLoader(
  runReportRouteHandle.routeId,
);
export const runDetailLoader = createRunDetailLoader(
  runDetailRouteHandle.routeId,
);

function createRunTabRoute(
  routeId: string,
  path: RunDetailTab,
  Component: AppRouteModule["Component"],
) {
  return {
    path,
    loader: createRunTabLoader(path),
    handle: {
      buildHref: (input?: RunRouteHrefInput) =>
        buildRunDetailHref(input?.runId ?? "", path),
      parseSearch: parseRunDetailLegacySearchParams,
      routeId,
      workspaceKey: "runsDecisions",
    },
    element: (
      <TabBoundary>
        <Component />
      </TabBoundary>
    ),
  } satisfies RouteObject;
}

export const runsRoutes: RouteObject[] = [
  {
    path: "runs",
    loader: runsListLoader,
    handle: runsListRouteHandle,
    element: (
      <WorkspaceBoundary workspaceKey="runsDecisions">
        <RunsListPage />
      </WorkspaceBoundary>
    ),
  },
  {
    path: "runs/compare",
    loader: runsCompareLoader,
    handle: runsCompareRouteHandle,
    element: (
      <WorkspaceBoundary workspaceKey="runsDecisions">
        <RunComparePage />
      </WorkspaceBoundary>
    ),
  },
  {
    path: "runs/:runId/report",
    loader: runReportLoader,
    handle: runReportRouteHandle,
    element: (
      <WorkspaceBoundary workspaceKey="runsDecisions">
        <RunReportPage />
      </WorkspaceBoundary>
    ),
  },
  {
    path: "runs/:runId",
    loader: runDetailLoader,
    handle: runDetailRouteHandle,
    element: (
      <WorkspaceBoundary workspaceKey="runsDecisions">
        <RunInspectorLayout />
      </WorkspaceBoundary>
    ),
    children: [
      { index: true, element: <Navigate replace to="overview" /> },
      createRunTabRoute("runs.tab.overview", "overview", RunOverviewTab),
      createRunTabRoute("runs.tab.governance", "governance", RunGovernanceTab),
      createRunTabRoute("runs.tab.evidence", "evidence", RunEvidenceTab),
      createRunTabRoute("runs.tab.workflow", "workflow", RunWorkflowTab),
      createRunTabRoute("runs.tab.artifacts", "artifacts", RunArtifactsTab),
      createRunTabRoute("runs.tab.agents", "agents", RunAgentsTab),
      createRunTabRoute("runs.tab.debug", "debug", RunDebugTab),
    ],
  },
];
