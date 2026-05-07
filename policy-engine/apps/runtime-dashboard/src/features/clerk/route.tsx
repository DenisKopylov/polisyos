import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";

const ClerkChatPage = lazy(
  () => import("@/features/clerk/routes/ClerkChatPage"),
);

export const clerkChatRouteHandle = {
  buildHref: () => "/",
  parseSearch: () => ({}),
  prefetch: ["capabilities", "health"],
  routeId: "clerk.chat",
  workspaceKey: "commandCenter",
} satisfies AppRouteModule["handle"];

export const clerkChatRoute: RouteObject = {
  index: true,
  handle: clerkChatRouteHandle,
  element: (
    <WorkspaceBoundary workspaceKey="commandCenter">
      <ClerkChatPage />
    </WorkspaceBoundary>
  ),
};
