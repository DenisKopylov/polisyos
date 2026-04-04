import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import {
  buildArtifactHref,
  parseArtifactSearchParams,
  type ArtifactTab,
} from "@/features/artifacts/domain/searchParams";

const ArtifactInspectorPage = lazy(
  () => import("@/features/artifacts/routes/ArtifactInspectorPage"),
);

type ArtifactRouteHrefInput = {
  artifactId: string;
  tab?: ArtifactTab;
};

export const artifactRouteHandle = {
  buildHref: (input) => buildArtifactHref(input?.artifactId ?? "", input),
  parseSearch: parseArtifactSearchParams,
  routeId: "artifacts.inspector",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<
  { tab: ArtifactTab },
  ArtifactRouteHrefInput
>["handle"];

export const artifactRouteModule = {
  Component: ArtifactInspectorPage,
  handle: artifactRouteHandle,
  path: "artifacts/:artifactId",
} satisfies AppRouteModule<{ tab: ArtifactTab }, ArtifactRouteHrefInput>;

export const artifactRoute: RouteObject = {
  path: artifactRouteModule.path,
  handle: artifactRouteHandle,
  element: (
    <WorkspaceBoundary workspaceKey="runsDecisions">
      <ArtifactInspectorPage />
    </WorkspaceBoundary>
  ),
};
