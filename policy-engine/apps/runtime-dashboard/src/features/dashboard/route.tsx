import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import { createWorkspaceLoader } from "@/app/routes/loaders";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";

const DashboardPage = lazy(
  () => import("@/features/dashboard/routes/DashboardPage"),
);

type DashboardSearchParams = Record<string, never>;

export const dashboardRouteHandle = {
  buildHref: () => "/",
  parseSearch: () => ({}),
  prefetch: ["capabilities", "health", "runsSample"],
  routeId: "dashboard.home",
  workspaceKey: "commandCenter",
} satisfies AppRouteModule<DashboardSearchParams>["handle"];

export const dashboardLoader = createWorkspaceLoader(
  dashboardRouteHandle.routeId,
  dashboardRouteHandle.prefetch,
);

export const dashboardRouteModule = {
  Component: DashboardPage,
  handle: dashboardRouteHandle,
  index: true,
  loader: dashboardLoader,
} satisfies AppRouteModule<DashboardSearchParams>;

export const dashboardRoute: RouteObject = {
  index: true,
  loader: dashboardLoader,
  handle: dashboardRouteHandle,
  element: (
    <WorkspaceBoundary workspaceKey="commandCenter">
      <DashboardPage />
    </WorkspaceBoundary>
  ),
};
