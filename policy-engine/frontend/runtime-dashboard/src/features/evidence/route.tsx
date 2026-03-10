import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import { loadEvidenceWorkspace } from "@/app/routes/loaders";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import {
  buildEvidenceHref,
  parseEvidenceSearchParams,
  type EvidenceSearchParams,
} from "@/features/evidence/domain/searchParams";

const EvidenceFabricPage = lazy(
  () => import("@/features/evidence/routes/EvidenceFabricPage"),
);

export const evidenceRouteHandle = {
  buildHref: buildEvidenceHref,
  parseSearch: parseEvidenceSearchParams,
  prefetch: [
    "capabilities",
    "connectors",
    "sourceProfiles",
    "dataIndexStats",
    "dataPromotionCandidates",
  ],
  routeId: "evidence.fabric",
  workspaceKey: "evidenceFabric",
} satisfies AppRouteModule<EvidenceSearchParams>["handle"];

export const evidenceRouteModule = {
  Component: EvidenceFabricPage,
  handle: evidenceRouteHandle,
  loader: loadEvidenceWorkspace,
  path: "evidence",
} satisfies AppRouteModule<EvidenceSearchParams>;

export const evidenceRoute: RouteObject = {
  path: evidenceRouteModule.path,
  loader: loadEvidenceWorkspace,
  handle: evidenceRouteHandle,
  element: (
    <WorkspaceBoundary workspaceKey="evidenceFabric">
      <EvidenceFabricPage />
    </WorkspaceBoundary>
  ),
};
