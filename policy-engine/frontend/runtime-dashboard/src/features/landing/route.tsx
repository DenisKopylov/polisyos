import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

const LandingPage = lazy(() => import("@/features/landing/routes/LandingPage"));

export const landingRoute: RouteObject = {
  path: "welcome",
  element: <LandingPage />,
};
