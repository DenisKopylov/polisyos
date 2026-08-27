import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";

const TrustPosturePage = lazy(
  () => import("@/features/trust/routes/TrustPosturePage"),
);

export const trustRouteHandle = {
  buildHref: () => "/trust",
  parseSearch: () => ({}),
  routeId: "trust.posture",
} satisfies AppRouteModule<Record<string, never>>["handle"];

export const trustRoute: RouteObject = {
  path: "trust",
  handle: trustRouteHandle,
  element: <TrustPosturePage />,
};
