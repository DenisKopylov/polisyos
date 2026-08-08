import { createLogger } from "@/shared/telemetry/logger";

const logger = createLogger({
  tags: {
    domain: "auth",
  },
});

const AUTH_REFRESH_URL = import.meta.env.VITE_AUTH_REFRESH_URL?.trim() || "";
const CSRF_COOKIE_CANDIDATES = ["csrf_token", "XSRF-TOKEN"];

export type AuthSessionStatus =
  | "anonymous"
  | "authenticated"
  | "expired"
  | "refreshing";
export type AuthSessionState = {
  accessToken: string | null;
  lastError: string | null;
  refreshedAt: number | null;
  status: AuthSessionStatus;
};

type RefreshContext = {
  reason: "manual" | "response_401";
  requestUrl?: string;
};

type AuthSessionListener = (state: AuthSessionState) => void;

const listeners = new Set<AuthSessionListener>();

let state: AuthSessionState = {
  accessToken: null,
  lastError: null,
  refreshedAt: null,
  status: "anonymous",
};
let refreshPromise: Promise<string | null> | null = null;

function emitState(nextState: Partial<AuthSessionState>) {
  state = {
    ...state,
    ...nextState,
  };
  for (const listener of listeners) {
    listener(state);
  }
}

function readRequestId(response: Response) {
  return (
    response.headers.get("x-request-id") ??
    response.headers.get("x-correlation-id") ??
    null
  );
}

function resolveRefreshUrl() {
  if (!AUTH_REFRESH_URL || typeof window === "undefined") {
    return "";
  }

  return new URL(AUTH_REFRESH_URL, window.location.origin).toString();
}

function isRefreshRequest(url: string) {
  const refreshUrl = resolveRefreshUrl();
  return Boolean(refreshUrl) && refreshUrl === url;
}

function readCsrfToken() {
  if (typeof document === "undefined") {
    return null;
  }

  const metaToken = document
    .querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
    ?.content?.trim();
  if (metaToken) {
    return metaToken;
  }

  const cookieValue = document.cookie
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) =>
      CSRF_COOKIE_CANDIDATES.some((candidate) =>
        cookie.startsWith(`${candidate}=`),
      ),
    );

  if (!cookieValue) {
    return null;
  }

  const [, value = ""] = cookieValue.split("=");
  return decodeURIComponent(value);
}

function extractAccessToken(payload: unknown) {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const record = payload as Record<string, unknown>;
  const candidates = [
    record.access_token,
    record.accessToken,
    record.token,
    record.jwt,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate.trim();
    }
  }

  return null;
}

function withAccessToken(request: Request, accessToken: string | null) {
  const headers = new Headers(request.headers);
  if (accessToken && !headers.has("authorization")) {
    headers.set("authorization", `Bearer ${accessToken}`);
  }

  return new Request(request, {
    headers,
  });
}

async function performRefresh(context: RefreshContext) {
  const refreshUrl = resolveRefreshUrl();
  if (!refreshUrl || typeof fetch !== "function") {
    logger.warn({
      event: "auth.refresh.unconfigured",
      message: "Runtime session refresh is not configured",
      tags: {
        reason: context.reason,
      },
    });
    emitState({
      accessToken: null,
      lastError: "refresh_unconfigured",
      status: "expired",
    });
    return null;
  }

  emitState({
    lastError: null,
    status: "refreshing",
  });
  logger.info({
    event: "auth.refresh.started",
    message: "Refreshing runtime session",
    tags: {
      reason: context.reason,
    },
  });

  const headers = new Headers({
    accept: "application/json",
  });
  const csrfToken = readCsrfToken();
  if (csrfToken) {
    headers.set("x-csrf-token", csrfToken);
  }

  const response = await fetch(refreshUrl, {
    credentials: "include",
    headers,
    method: "POST",
  });

  if (!response.ok) {
    logger.warn({
      event: "auth.refresh.failed",
      message: `Runtime session refresh failed with ${response.status}`,
      requestId: readRequestId(response),
      tags: {
        reason: context.reason,
        status: response.status,
      },
    });
    emitState({
      accessToken: null,
      lastError: `refresh_failed:${response.status}`,
      status: "expired",
    });
    return null;
  }

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : null;
  const accessToken = extractAccessToken(payload);

  if (!accessToken) {
    logger.error({
      error: payload,
      event: "auth.refresh.invalid_payload",
      message: "Runtime session refresh returned no access token",
      requestId: readRequestId(response),
      tags: {
        reason: context.reason,
      },
    });
    emitState({
      accessToken: null,
      lastError: "refresh_missing_access_token",
      status: "expired",
    });
    return null;
  }

  emitState({
    accessToken,
    lastError: null,
    refreshedAt: Date.now(),
    status: "authenticated",
  });
  logger.info({
    event: "auth.refresh.succeeded",
    message: "Runtime session refresh succeeded",
    requestId: readRequestId(response),
    tags: {
      reason: context.reason,
    },
  });
  return accessToken;
}

export function readAuthSessionState() {
  return state;
}

export function subscribeAuthSession(listener: AuthSessionListener) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setAuthAccessToken(accessToken: string | null) {
  emitState({
    accessToken,
    lastError: null,
    refreshedAt: accessToken ? Date.now() : null,
    status: accessToken ? "authenticated" : "anonymous",
  });
}

export function clearAuthSession(reason?: string) {
  emitState({
    accessToken: null,
    lastError: reason ?? null,
    status: "expired",
  });
}

export async function refreshAuthSession(context: RefreshContext) {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = performRefresh(context).finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

export async function authAwareRuntimeFetch(input: Request) {
  const initialRequest = withAccessToken(input, state.accessToken);
  const retryRequest = initialRequest.clone();
  const response = await fetch(initialRequest);

  if (
    response.status !== 401 ||
    initialRequest.headers.get("x-runtime-dashboard-replay") === "1" ||
    isRefreshRequest(initialRequest.url)
  ) {
    return response;
  }

  const accessToken = await refreshAuthSession({
    reason: "response_401",
    requestUrl: initialRequest.url,
  });

  if (!accessToken) {
    return response;
  }

  const replayHeaders = new Headers(retryRequest.headers);
  replayHeaders.set("authorization", `Bearer ${accessToken}`);
  replayHeaders.set("x-runtime-dashboard-replay", "1");
  const replayRequest = new Request(retryRequest, {
    headers: replayHeaders,
  });

  logger.info({
    event: "auth.refresh.replay",
    message: "Replaying runtime request after successful refresh",
    tags: {
      requestUrl: input.url,
    },
  });
  return fetch(replayRequest);
}
