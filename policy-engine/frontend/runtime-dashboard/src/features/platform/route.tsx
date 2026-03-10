import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import { createWorkspaceLoader } from "@/app/routes/loaders";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import {
  buildPlatformHref,
  parsePlatformSearchParams,
  type PlatformSearchParams,
} from "@/features/platform/domain/searchParams";

const PlatformHealthPage = lazy(
  () => import("@/features/platform/routes/PlatformHealthPage"),
);

export const platformRouteHandle = {
  buildHref: buildPlatformHref,
  parseSearch: parsePlatformSearchParams,
  prefetch: ["health", "capabilities", "connectors", "runs"],
  routeId: "platform.health",
  workspaceKey: "platformHealth",
} satisfies AppRouteModule<PlatformSearchParams>["handle"];

export const platformLoader = createWorkspaceLoader(
  platformRouteHandle.routeId,
  platformRouteHandle.prefetch,
);

export const platformRouteModule = {
  Component: PlatformHealthPage,
  handle: platformRouteHandle,
  loader: platformLoader,
  path: "platform",
} satisfies AppRouteModule<PlatformSearchParams>;

export const platformRoute: RouteObject = {
  path: platformRouteModule.path,
  loader: platformLoader,
  handle: platformRouteHandle,
  element: (
    <WorkspaceBoundary workspaceKey="platformHealth">
      <PlatformHealthPage />
    </WorkspaceBoundary>
  ),
};
