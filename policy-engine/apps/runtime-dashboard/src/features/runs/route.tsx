import { lazy } from "react";
import type { RouteObject } from "react-router-dom";
import { Navigate, useParams } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import {
  createRunDetailLoader,
  createRunPaperLoader,
  createRunTabLoader,
  createWorkspaceLoader,
} from "@/app/routes/loaders";
import { TabBoundary } from "@/app/routes/TabBoundary";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import { useFeatureFlag } from "@/app/providers/FeatureFlagProvider";
import {
  buildRunCompareHref,
  buildRunDeckHref,
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
import {
  RUN_DETAIL_TAB_REGISTRY,
  type RunDetailTab,
} from "@/features/runs/domain/runDetailTabs";

const RunsListPage = lazy(() => import("@/features/runs/routes/RunsListPage"));
const RunComparePage = lazy(
  () => import("@/features/runs/routes/RunComparePage"),
);
const CycleBoardPage = lazy(
  () => import("@/features/runs/routes/CycleBoardPage"),
);
const RunInspectorLayout = lazy(
  () => import("@/features/runs/routes/RunDetailLayout"),
);
const RunReportPage = lazy(
  () => import("@/features/runs/routes/RunReportPage"),
);
const RunDeckPage = lazy(() => import("@/features/runs/routes/RunDeckPage"));
const PublicDecisionViewerPage = lazy(
  () => import("@/features/runs/routes/PublicDecisionViewerPage"),
);
const RunOverviewTab = lazy(
  () => import("@/features/runs/routes/tabs/OverviewTab"),
);
const RunCausalTab = lazy(
  () => import("@/features/runs/routes/tabs/CausalTab"),
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

export function RunCausalFeatureGate() {
  const enabled = useFeatureFlag("enableCausalGraph");
  const { runId } = useParams();
  return enabled ? (
    <RunCausalTab />
  ) : (
    <Navigate replace to={runId ? `/runs/${runId}/overview` : "/runs"} />
  );
}

const RUN_TAB_COMPONENTS = {
  agents: RunAgentsTab,
  artifacts: RunArtifactsTab,
  causal: RunCausalFeatureGate,
  debug: RunDebugTab,
  evidence: RunEvidenceTab,
  governance: RunGovernanceTab,
  overview: RunOverviewTab,
  workflow: RunWorkflowTab,
} satisfies Record<RunDetailTab, AppRouteModule["Component"]>;

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

export const cycleBoardRouteHandle = {
  buildHref: () => "/runs/cycle-board",
  parseSearch: () => ({}),
  prefetch: ["capabilities"],
  routeId: "runs.cycleBoard",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<Record<string, never>>["handle"];

export const runReportRouteHandle = {
  buildHref: (input) => buildRunReportHref(input?.runId ?? ""),
  parseSearch: () => ({}),
  routeId: "runs.report",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<Record<string, never>, RunRouteHrefInput>["handle"];

export const runDeckRouteHandle = {
  buildHref: (input) => buildRunDeckHref(input?.runId ?? ""),
  parseSearch: () => ({}),
  routeId: "runs.deck",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<Record<string, never>, RunRouteHrefInput>["handle"];

export const publicDecisionViewerRouteHandle = {
  buildHref: (input?: { signedId?: string }) =>
    `/public/decisions/${input?.signedId ?? ""}`,
  parseSearch: () => ({}),
  routeId: "runs.publicDecisionViewer",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<
  Record<string, never>,
  { signedId?: string }
>["handle"];

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
export const cycleBoardLoader = createWorkspaceLoader(
  cycleBoardRouteHandle.routeId,
  cycleBoardRouteHandle.prefetch,
);
export const runReportLoader = createRunPaperLoader(
  runReportRouteHandle.routeId,
);
export const runDeckLoader = createRunDetailLoader(runDeckRouteHandle.routeId);
export const runDetailLoader = createRunDetailLoader(
  runDetailRouteHandle.routeId,
);

export const publicDecisionViewerRoute: RouteObject = {
  path: "public/decisions/:signedId",
  handle: publicDecisionViewerRouteHandle,
  element: <PublicDecisionViewerPage />,
};

function createRunTabRoute(
  tab: (typeof RUN_DETAIL_TAB_REGISTRY)[number],
  Component: AppRouteModule["Component"],
) {
  return {
    path: tab.key,
    loader: createRunTabLoader(tab.key),
    handle: {
      buildHref: (input?: RunRouteHrefInput) =>
        buildRunDetailHref(input?.runId ?? "", tab.key),
      parseSearch: parseRunDetailLegacySearchParams,
      routeId: tab.routeId,
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
    path: "compare/:runA/:runB",
    loader: runsCompareLoader,
    handle: runsCompareRouteHandle,
    element: (
      <WorkspaceBoundary workspaceKey="runsDecisions">
        <RunComparePage />
      </WorkspaceBoundary>
    ),
  },
  {
    path: "runs/cycle-board",
    loader: cycleBoardLoader,
    handle: cycleBoardRouteHandle,
    element: (
      <WorkspaceBoundary workspaceKey="runsDecisions">
        <CycleBoardPage />
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
    path: "runs/:runId/deck",
    loader: runDeckLoader,
    handle: runDeckRouteHandle,
    element: (
      <WorkspaceBoundary workspaceKey="runsDecisions">
        <RunDeckPage />
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
      ...RUN_DETAIL_TAB_REGISTRY.map((tab) =>
        createRunTabRoute(tab, RUN_TAB_COMPONENTS[tab.key]),
      ),
    ],
  },
];
