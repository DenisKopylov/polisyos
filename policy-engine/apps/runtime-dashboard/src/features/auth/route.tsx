import { lazy } from "react";
import type { RouteObject } from "react-router-dom";

import type { AppRouteModule } from "@/app/routes/contracts";
import { RouteErrorElement } from "@/app/routes/RouteErrorElement";
import {
  buildLoginHref,
  parseLoginSearchParams,
  type LoginSearchParams,
} from "@/features/auth/domain/searchParams";

const LoginPage = lazy(() => import("@/features/auth/routes/LoginPage"));

export const loginRouteHandle = {
  buildHref: buildLoginHref,
  parseSearch: parseLoginSearchParams,
  routeId: "auth.login",
} satisfies AppRouteModule<LoginSearchParams>["handle"];

export const loginRouteModule = {
  Component: LoginPage,
  errorElement: <RouteErrorElement />,
  handle: loginRouteHandle,
  path: "login",
} satisfies AppRouteModule<LoginSearchParams>;

export const loginRoute: RouteObject = {
  path: loginRouteModule.path,
  handle: loginRouteHandle,
  element: <LoginPage />,
};
