import { z } from "zod";

import type { components } from "./types";

const runtimeApiProblemSchema = z.object({
  type: z.string().default("about:blank"),
  title: z.string().default("Runtime API error"),
  status: z.number().default(500),
  status_code: z.number().default(500),
  detail: z.string().default("Runtime API request failed"),
  code: z.string().default("runtime_api_error"),
  instance: z.string().nullable().optional().default(null),
  request_id: z.string().nullable().optional().default(null),
  error: z.string().nullable().optional().default(null),
});

export type RuntimeApiProblem = components["schemas"]["RuntimeApiProblem"];

export class RuntimeApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;
  readonly requestId: string | null;
  readonly problem: RuntimeApiProblem | null;

  constructor(problem: RuntimeApiProblem | null, status: number, fallbackMessage: string) {
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

export function toRuntimeApiProblem(payload: unknown): RuntimeApiProblem | null {
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
  return new RuntimeApiRequestError(toRuntimeApiProblem(payload), response.status, fallbackMessage);
}
