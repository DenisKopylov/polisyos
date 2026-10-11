import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import type { EvidenceArtifactRef } from "@/shared/lib/domain/evidence";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import {
  buildArtifactHref,
  parseArtifactSearchParams,
  type ArtifactTab,
  type ArtifactView,
} from "@/features/artifacts/domain/searchParams";

const ArtifactInspectorPage = lazy(
  () => import("@/features/artifacts/routes/ArtifactInspectorPage"),
);

type ArtifactRouteHrefInput = {
  artifactId: string;
  tab?: ArtifactTab;
  view?: ArtifactView;
  artifactRef?: EvidenceArtifactRef;
  manifestProfileSha256?: string | null;
};

export const artifactRouteHandle = {
  buildHref: (input) =>
    buildArtifactHref(
      input?.artifactId ?? input?.artifactRef?.artifact_id ?? "",
      input,
    ),
  parseSearch: parseArtifactSearchParams,
  routeId: "artifacts.inspector",
  workspaceKey: "runsDecisions",
} satisfies AppRouteModule<
  { tab: ArtifactTab; view: ArtifactView },
  ArtifactRouteHrefInput
>["handle"];

export const artifactRouteModule = {
  Component: ArtifactInspectorPage,
  handle: artifactRouteHandle,
  path: "artifacts/:artifactId",
} satisfies AppRouteModule<
  { tab: ArtifactTab; view: ArtifactView },
  ArtifactRouteHrefInput
>;

export const artifactRoute: RouteObject = {
  path: artifactRouteModule.path,
  handle: artifactRouteHandle,
  element: (
    <WorkspaceBoundary workspaceKey="runsDecisions">
      <ArtifactInspectorPage />
    </WorkspaceBoundary>
  ),
};
