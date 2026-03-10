import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useEffectEvent,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuthSession } from "@/app/auth/AuthSessionProvider";
import { useTelemetry } from "@/app/providers/TelemetryProvider";
import {
  subscribeRuntimeApiEvents,
  type RuntimeApiEvent,
} from "@/api/runtimeApiEvents";
import { LOGIN_PATH, LOGIN_URL } from "@/lib/constants";
import { useLogger } from "@/shared/telemetry/logger";

type RuntimeIncident = RuntimeApiEvent | null;

type RuntimeApiContextValue = {
  incident: RuntimeIncident;
  dismissIncident: () => void;
};

const RuntimeApiContext = createContext<RuntimeApiContextValue | null>(null);

function buildLoginHref(nextPath: string) {
  const trimmedNext = nextPath.trim() || "/";
  if (LOGIN_URL.startsWith("/")) {
    const params = new URLSearchParams({ next: trimmedNext });
    return `${LOGIN_URL}?${params.toString()}`;
  }
  const url = new URL(LOGIN_URL);
  url.searchParams.set("next", trimmedNext);
  return url.toString();
}

export function RuntimeApiProvider({ children }: PropsWithChildren) {
  const location = useLocation();
  const navigate = useNavigate();
  const authSession = useAuthSession();
  const { track } = useTelemetry();
  const logger = useLogger({
    tags: {
      area: "runtime-api",
    },
  });
  const [incident, setIncident] = useState<RuntimeIncident>(null);
  const lastIncidentRef = useRef<string | null>(null);
  const lastIncidentAtRef = useRef<number>(0);
  const redirectingRef = useRef(false);

  const redirectToLogin = useEffectEvent((reason: string) => {
    if (redirectingRef.current) {
      return;
    }

    const nextPath = `${location.pathname}${location.search}${location.hash}`;
    const loginHref = buildLoginHref(nextPath);
    redirectingRef.current = true;
    setIncident(null);
    logger.warn({
      event: "auth.session.redirect_login",
      message: "Redirecting runtime session to login",
      tags: {
        nextPath,
        reason,
      },
    });

    if (LOGIN_URL.startsWith("/")) {
      if (location.pathname !== LOGIN_PATH) {
        navigate(loginHref, { replace: true });
      }
      return;
    }

    window.location.assign(loginHref);
  });

  useEffect(() => {
    return subscribeRuntimeApiEvents((event) => {
      const dedupeKey = [
        event.status,
        event.code,
        event.detail,
        event.source,
      ].join(":");
      if (
        lastIncidentRef.current === dedupeKey &&
        event.timestamp - lastIncidentAtRef.current < 5_000
      ) {
        return;
      }
      lastIncidentRef.current = dedupeKey;
      lastIncidentAtRef.current = event.timestamp;
      logger.warn({
        event: "runtime.api.incident",
        message: `Runtime API incident ${event.code}`,
        requestId: event.requestId,
        tags: {
          source: event.source,
          status: event.status,
        },
      });
      track("runtime.api.incident", {
        code: event.code,
        requestId: event.requestId,
        source: event.source,
        status: event.status,
      });

      if (event.status === 401) {
        redirectToLogin("runtime_unauthorized");
        return;
      }

      if (event.status === 403 || event.status >= 500 || event.status === 0) {
        setIncident(event);
      }
    });
  }, [
    location.hash,
    location.pathname,
    location.search,
    logger,
    redirectToLogin,
    track,
  ]);

  useEffect(() => {
    if (authSession.status !== "expired") {
      return;
    }
    redirectToLogin("auth_refresh_failed");
  }, [authSession.status, redirectToLogin]);

  useEffect(() => {
    setIncident((current) => {
      if (!current) {
        return current;
      }
      if (
        current.status === 403 ||
        current.status >= 500 ||
        current.status === 0
      ) {
        return null;
      }
      return current;
    });
    redirectingRef.current = false;
  }, [location.pathname]);

  const value = useMemo<RuntimeApiContextValue>(
    () => ({
      incident,
      dismissIncident: () => setIncident(null),
    }),
    [incident],
  );

  return (
    <RuntimeApiContext.Provider value={value}>
      {children}
    </RuntimeApiContext.Provider>
  );
}

export function useRuntimeApiIncident() {
  const context = useContext(RuntimeApiContext);
  if (!context) {
    throw new Error(
      "useRuntimeApiIncident must be used within a RuntimeApiProvider",
    );
  }
  return context;
}
