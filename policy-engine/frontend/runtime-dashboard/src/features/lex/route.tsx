import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import { createWorkspaceLoader } from "@/app/routes/loaders";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import {
  buildLexHref,
  parseLexSearchParams,
  type LexSearchParams,
} from "@/features/lex/domain/searchParams";

const LexKnowledgeGraphPage = lazy(
  () => import("@/features/lex/routes/LexKnowledgeGraphPage"),
);

export const lexRouteHandle = {
  buildHref: buildLexHref,
  parseSearch: parseLexSearchParams,
  prefetch: ["capabilities"],
  routeId: "lex.knowledge",
  workspaceKey: "lexKnowledge",
} satisfies AppRouteModule<LexSearchParams>["handle"];

export const lexLoader = createWorkspaceLoader(
  lexRouteHandle.routeId,
  lexRouteHandle.prefetch,
);

export const lexRouteModule = {
  Component: LexKnowledgeGraphPage,
  handle: lexRouteHandle,
  loader: lexLoader,
  path: "knowledge",
} satisfies AppRouteModule<LexSearchParams>;

export const lexRoute: RouteObject = {
  path: lexRouteModule.path,
  loader: lexLoader,
  handle: lexRouteHandle,
  element: (
    <WorkspaceBoundary workspaceKey="lexKnowledge">
      <LexKnowledgeGraphPage />
    </WorkspaceBoundary>
  ),
};
