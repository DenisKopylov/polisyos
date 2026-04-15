import { useEffect, useEffectEvent, useRef } from "react";
import type { RouteObject } from "react-router-dom";
import {
  Navigate,
  Outlet,
  useLocation,
  useMatches,
  useNavigation,
} from "react-router-dom";

import AppShell from "@/app/layout/AppShell";
import { useTelemetry } from "@/app/providers/TelemetryProvider";
import { RunsLiveProvider } from "@/app/providers/RunsLiveProvider";
import { RuntimeApiProvider } from "@/app/providers/RuntimeApiProvider";
import { RouteErrorElement } from "@/app/routes/RouteErrorElement";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import { artifactRoute } from "@/features/artifacts/routes.public";
import { loginRoute } from "@/features/auth";
import { clerkChatRoute } from "@/features/clerk";
import { composerRoute } from "@/features/composer";
import { dashboardRoute } from "@/features/dashboard";
import { landingRoute } from "@/features/landing";
import { evidenceRoute } from "@/features/evidence/routes.public";
import { ModeAwareHome } from "@/app/routes/ModeAwareHome";
import { lexRoute } from "@/features/lex";
import { platformRoute } from "@/features/platform";
import { resolveWorkspaceKey } from "@/app/workspaces";
import { runsRoutes } from "@/features/runs/routes.public";
import { LOGIN_PATH } from "@/lib/constants";
import {
  setActiveRouteTelemetryContext,
  setActiveRouteViewTiming,
} from "@/shared/telemetry/routeContext";

function AppFrame() {
  const location = useLocation();
  const matches = useMatches();
  const navigation = useNavigation();
  const { track } = useTelemetry();
  const chromeless = location.pathname.startsWith(LOGIN_PATH);
  const routePath = `${location.pathname}${location.search}${location.hash}`;
  const currentRouteMatch = matches[matches.length - 1];
  const currentRouteId =
    typeof currentRouteMatch?.handle === "object" &&
    currentRouteMatch.handle &&
    "routeId" in currentRouteMatch.handle
      ? String(currentRouteMatch.handle.routeId)
      : "unknown";
  const workspace = resolveWorkspaceKey(location.pathname);
  const previousPathRef = useRef(routePath);
  const pendingTransitionRef = useRef<{
    from: string;
    routeId: string;
    startedAt: number;
    to: string;
  } | null>(null);
  const emitRouteEvent = useEffectEvent(track);

  useEffect(() => {
    setActiveRouteTelemetryContext({
      fullPath: routePath,
      path: location.pathname,
      routeId: currentRouteId,
      workspace,
    });
    emitRouteEvent("route.view", {
      fullPath: routePath,
      path: location.pathname,
      routeId: currentRouteId,
      workspace,
    });
    previousPathRef.current = routePath;
  }, [currentRouteId, emitRouteEvent, location.pathname, routePath, workspace]);

  useEffect(() => {
    if (chromeless || typeof document === "undefined") {
      return;
    }

    const main = document.getElementById("main-content");
    if (!(main instanceof HTMLElement)) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      const activeElement = document.activeElement;
      if (
        activeElement instanceof HTMLElement &&
        activeElement !== document.body &&
        main.contains(activeElement)
      ) {
        return;
      }
      main.focus({ preventScroll: true });
    });

    return () => window.cancelAnimationFrame(frame);
  }, [chromeless, location.pathname]);

  useEffect(() => {
    const nextLocation = navigation.location;

    if (navigation.state !== "idle" && nextLocation) {
      const nextPath = `${nextLocation.pathname}${nextLocation.search}${nextLocation.hash}`;
      if (pendingTransitionRef.current?.to === nextPath) {
        return;
      }

      const startedAt =
        typeof performance === "undefined" ? Date.now() : performance.now();
      pendingTransitionRef.current = {
        from: previousPathRef.current,
        routeId: currentRouteId,
        startedAt,
        to: nextPath,
      };

      emitRouteEvent("route.transition.started", {
        from: previousPathRef.current,
        routeId: currentRouteId,
        state: navigation.state,
        to: nextPath,
      });
      return;
    }

    if (!pendingTransitionRef.current) {
      return;
    }

    const pendingTransition = pendingTransitionRef.current;
    pendingTransitionRef.current = null;
    setActiveRouteViewTiming(pendingTransition.startedAt, "route-transition");
    emitRouteEvent("route.transition.ready", {
      durationMs: Math.round(performance.now() - pendingTransition.startedAt),
      from: pendingTransition.from,
      fromRouteId: pendingTransition.routeId,
      routeId: currentRouteId,
      to: routePath,
      workspace,
    });
  }, [
    currentRouteId,
    emitRouteEvent,
    location.pathname,
    navigation.location,
    navigation.state,
    routePath,
    workspace,
  ]);

  if (chromeless) {
    return <Outlet />;
  }

  return (
    <AppShell>
      <Outlet />
    </AppShell>
  );
}

function AppProvidersRoute() {
  return (
    <RuntimeApiProvider>
      <RunsLiveProvider>
        <AppFrame />
      </RunsLiveProvider>
    </RuntimeApiProvider>
  );
}

export const APP_ROUTES: RouteObject[] = [
  landingRoute,
  {
    path: "/",
    element: <AppProvidersRoute />,
    errorElement: <RouteErrorElement />,
    children: [
      loginRoute,
      {
        index: true,
        handle: dashboardRoute.handle,
        element: (
          <WorkspaceBoundary workspaceKey="commandCenter">
            <ModeAwareHome />
          </WorkspaceBoundary>
        ),
      },
      clerkChatRoute,
      composerRoute,
      ...runsRoutes,
      artifactRoute,
      evidenceRoute,
      lexRoute,
      platformRoute,
      { path: "launch", element: <Navigate replace to="/compose" /> },
      { path: "sources", element: <Navigate replace to="/evidence" /> },
      { path: "data", element: <Navigate replace to="/evidence" /> },
      { path: "lex", element: <Navigate replace to="/knowledge" /> },
      { path: "health", element: <Navigate replace to="/platform" /> },
      { path: "*", element: <Navigate replace to="/" /> },
    ],
  },
];
