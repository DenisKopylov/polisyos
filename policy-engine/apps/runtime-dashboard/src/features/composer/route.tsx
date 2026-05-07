import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import { createWorkspaceLoader } from "@/app/routes/loaders";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import {
  buildComposerHref,
  parseComposerSearchParams,
  type ComposerSearchParams,
} from "@/features/composer/domain/searchParams";

const ComposerPage = lazy(
  () => import("@/features/composer/routes/LaunchRunPage"),
);

export const composerRouteHandle = {
  buildHref: buildComposerHref,
  parseSearch: parseComposerSearchParams,
  prefetch: ["capabilities", "llmProfiles"],
  routeId: "composer.launch",
  workspaceKey: "scenarioComposer",
} satisfies AppRouteModule<ComposerSearchParams>["handle"];

export const composerLoader = createWorkspaceLoader(
  composerRouteHandle.routeId,
  composerRouteHandle.prefetch,
);

export const composerRouteModule = {
  Component: ComposerPage,
  handle: composerRouteHandle,
  loader: composerLoader,
  path: "compose",
} satisfies AppRouteModule<ComposerSearchParams>;

export const composerRoute: RouteObject = {
  path: composerRouteModule.path,
  loader: composerLoader,
  handle: composerRouteHandle,
  element: (
    <WorkspaceBoundary workspaceKey="scenarioComposer">
      <ComposerPage />
    </WorkspaceBoundary>
  ),
};
