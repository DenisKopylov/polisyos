import { useMemo } from "react";

import {
  emitTelemetry,
  readTelemetryRelease,
} from "@/shared/telemetry/pipeline";
import { readActiveRouteTelemetryContext } from "@/shared/telemetry/routeContext";
import {
  addSentryBreadcrumb,
  captureSentryException,
} from "@/shared/telemetry/sentry";

export type StructuredLogLevel = "debug" | "info" | "warn" | "error";
export type StructuredLogTags = Record<
  string,
  boolean | null | number | string | undefined
>;
export type StructuredLogInput = {
  error?: unknown;
  event: string;
  message: string;
  requestId?: string | null;
  tags?: StructuredLogTags;
};
export type StructuredLogRecord = {
  error?: {
    message: string;
    name: string;
    stack?: string;
  };
  event: string;
  fullPath: string;
  level: StructuredLogLevel;
  message: string;
  path: string;
  release?: string;
  requestId: string | null;
  routeId: string;
  tags?: StructuredLogTags;
  timestamp: number;
  workspace: string;
};
export type Logger = Record<
  StructuredLogLevel,
  (input: StructuredLogInput) => StructuredLogRecord
>;

function serializeError(error: unknown) {
  if (error instanceof Error) {
    return {
      message: error.message,
      name: error.name,
      stack: error.stack,
    };
  }

  if (typeof error === "string") {
    return {
      message: error,
      name: "Error",
    };
  }

  if (error == null) {
    return undefined;
  }

  return {
    message: JSON.stringify(error),
    name: "UnknownError",
  };
}

function toConsoleMethod(level: StructuredLogLevel) {
  switch (level) {
    case "debug":
      return console.debug;
    case "info":
      return console.info;
    case "warn":
      return console.warn;
    case "error":
      return console.error;
  }
}

function emitStructuredLog(
  level: StructuredLogLevel,
  input: StructuredLogInput,
  baseTags?: StructuredLogTags,
) {
  const route = readActiveRouteTelemetryContext();
  const record: StructuredLogRecord = {
    error: serializeError(input.error),
    event: input.event,
    fullPath: route.fullPath,
    level,
    message: input.message,
    path: route.path,
    release: readTelemetryRelease(),
    requestId: input.requestId ?? null,
    routeId: route.routeId,
    tags:
      baseTags || input.tags
        ? {
            ...baseTags,
            ...input.tags,
          }
        : undefined,
    timestamp: Date.now(),
    workspace: route.workspace,
  };

  if (
    import.meta.env.DEV &&
    !import.meta.env.VITEST &&
    (typeof window === "undefined" ||
      window.__RUNTIME_DASHBOARD_TEST__ !== true)
  ) {
    toConsoleMethod(level)("[log]", record);
  }

  emitTelemetry({
    name: "app.log",
    payload: record,
    timestamp: record.timestamp,
  });

  addSentryBreadcrumb({
    category: "app.log",
    data: {
      event: record.event,
      requestId: record.requestId,
      routeId: record.routeId,
      tags: record.tags,
      workspace: record.workspace,
    },
    level: level === "warn" ? "warning" : level === "error" ? "error" : level,
    message: record.message,
  });

  if (level === "error") {
    captureSentryException(input.error ?? new Error(input.message), {
      extra: {
        event: record.event,
        message: record.message,
        requestId: record.requestId,
      },
      level: "error",
      tags: Object.fromEntries(
        Object.entries(record.tags ?? {}).map(([key, value]) => [
          key,
          value == null ? null : String(value),
        ]),
      ),
    });
  }

  return record;
}

export function createLogger(base?: { tags?: StructuredLogTags }): Logger {
  return {
    debug: (input) => emitStructuredLog("debug", input, base?.tags),
    error: (input) => emitStructuredLog("error", input, base?.tags),
    info: (input) => emitStructuredLog("info", input, base?.tags),
    warn: (input) => emitStructuredLog("warn", input, base?.tags),
  };
}

export function useLogger(base?: { tags?: StructuredLogTags }) {
  const tagsKey = JSON.stringify(base?.tags ?? {});

  return useMemo(() => createLogger(base), [tagsKey]);
}
