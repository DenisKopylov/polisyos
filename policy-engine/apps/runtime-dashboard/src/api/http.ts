import { z } from "zod";

import { emitRuntimeApiEvent } from "./runtimeApiEvents";
import type { components } from "./types";
import { createLogger } from "@/shared/telemetry/logger";

const logger = createLogger({
  tags: {
    area: "runtime-api",
  },
});

const runtimeApiProblemContextSchema = z
  .object({
    request_id: z.string().optional(),
    tenant: z.string().optional(),
    run_id: z.string().optional(),
    artifact_id: z.string().optional(),
    dependency: z.string().optional(),
    retry_state: z.string().optional(),
    stage: z.string().optional(),
    category: z.string().optional(),
  })
  .strict();

const runtimeApiProblemBaseShape = {
  type: z.string().default("about:blank"),
  title: z.string().default("Runtime API error"),
  status: z.number().default(500),
  status_code: z.number().default(500),
  detail: z.string().default("Runtime API request failed"),
  code: z.string().default("runtime_api_error"),
  instance: z.string().nullable().optional().default(null),
  request_id: z.string().nullable().optional().default(null),
  error: z.string().nullable().optional().default(null),
  context: runtimeApiProblemContextSchema.nullable().optional(),
};

const runtimeApiProblemExtensionsSchema = z.record(z.string(), z.json());

const legacyRuntimeApiProblemExtensionKeys = [
  "actual",
  "artifact_ref_or_route",
  "authority_surface_decision",
  "expected",
  "field",
  "lineage_id",
  "manifest_temporal_scope",
  "mismatches",
  "nearest_event_points",
  "phase4_gate_verdict",
  "policy",
  "pre_admission_attempt_id",
  "pre_admission_attempt_status",
  "read_receipt",
  "reasons",
  "requested_temporal_scope",
  "retry_after_seconds",
  "run_id",
  "surface",
  "temporal_scope",
  "tx_range",
  "valid_range",
  "violations",
] as const;

function moveLegacyRuntimeApiProblemExtensions(value: unknown): unknown {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return value;
  }
  const normalized = { ...(value as Record<string, unknown>) };
  const presentKeys = legacyRuntimeApiProblemExtensionKeys.filter((key) =>
    Object.prototype.hasOwnProperty.call(normalized, key),
  );
  if (presentKeys.length === 0) {
    return value;
  }

  const rawExtensions = normalized.extensions;
  if (
    Object.prototype.hasOwnProperty.call(normalized, "extensions") &&
    (typeof rawExtensions !== "object" ||
      rawExtensions === null ||
      Array.isArray(rawExtensions))
  ) {
    return value;
  }
  const extensions =
    rawExtensions === undefined
      ? {}
      : { ...(rawExtensions as Record<string, unknown>) };
  for (const key of presentKeys) {
    if (Object.prototype.hasOwnProperty.call(extensions, key)) {
      return value;
    }
    extensions[key] = normalized[key];
  }
  const legacyKeys = new Set<string>(presentKeys);
  const normalizedWithoutLegacy = Object.fromEntries(
    Object.entries(normalized).filter(([key]) => !legacyKeys.has(key)),
  );
  return { ...normalizedWithoutLegacy, extensions };
}

const runtimeApiProblemSchema = z.preprocess(
  moveLegacyRuntimeApiProblemExtensions,
  z
    .object({
      ...runtimeApiProblemBaseShape,
      extensions: runtimeApiProblemExtensionsSchema.nullable().optional(),
    })
    .strict(),
);

export type RuntimeApiProblem = components["schemas"]["RuntimeApiProblem"];

export class RuntimeApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly requestId: string | null;
  readonly problem: RuntimeApiProblem | null;

  constructor(
    problem: RuntimeApiProblem | null,
    status: number,
    fallbackMessage: string,
  ) {
    const detail = problem?.detail ?? fallbackMessage;
    const code = problem?.code ?? "runtime_api_error";
    super(`${detail} (status=${status}, code=${code})`);
    this.name = "RuntimeApiRequestError";
    this.status = status;
    this.code = code;
    this.detail = detail;
    this.requestId = problem?.request_id ?? null;
    this.problem = problem;
  }
}

export function isRuntimeApiRequestError(
  error: unknown,
): error is RuntimeApiRequestError {
  return (
    error instanceof RuntimeApiRequestError ||
    (typeof error === "object" &&
      error !== null &&
      "status" in error &&
      typeof error.status === "number" &&
      "code" in error &&
      typeof error.code === "string")
  );
}

export function isRuntimeApiNotFound(error: unknown) {
  return isRuntimeApiRequestError(error) && error.status === 404;
}

export type RuntimeApiErrorKind =
  | "auth"
  | "forbidden"
  | "network"
  | "not_found"
  | "transient"
  | "validation"
  | "unknown";

export function classifyRuntimeApiError(error: unknown): RuntimeApiErrorKind {
  if (!isRuntimeApiRequestError(error)) {
    return "unknown";
  }
  if (error.status === 0) {
    return "network";
  }
  if (error.status === 401) {
    return "auth";
  }
  if (error.status === 403) {
    return "forbidden";
  }
  if (error.status === 404) {
    return "not_found";
  }
  if (
    error.status === 408 ||
    error.status === 409 ||
    error.status === 425 ||
    error.status === 429 ||
    error.status >= 500
  ) {
    return "transient";
  }
  if (error.status >= 400 && error.status < 500) {
    return "validation";
  }
  return "unknown";
}

export function toRuntimeApiProblem(
  payload: unknown,
): RuntimeApiProblem | null {
  const parsed = runtimeApiProblemSchema.safeParse(payload);
  if (!parsed.success) {
    return null;
  }
  return parsed.data;
}

export function createRuntimeApiError(
  response: Response,
  payload: unknown,
  fallbackMessage: string,
): RuntimeApiRequestError {
  const error = new RuntimeApiRequestError(
    toRuntimeApiProblem(payload),
    response.status,
    fallbackMessage,
  );
  logger.warn({
    error,
    event: "runtime.api.error",
    message: error.detail,
    requestId: error.requestId,
    tags: {
      code: error.code,
      source: response.url || fallbackMessage,
      status: error.status,
    },
  });
  if (error.status === 401 || error.status === 403 || error.status >= 500) {
    emitRuntimeApiEvent({
      status: error.status,
      code: error.code,
      detail: error.detail,
      requestId: error.requestId,
      source: response.url || fallbackMessage,
      timestamp: Date.now(),
    });
  }
  return error;
}
