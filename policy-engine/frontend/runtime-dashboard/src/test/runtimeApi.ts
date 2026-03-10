import { runtimeApiClient } from "@/api/client";
import { vi } from "vitest";

function jsonResponse(body: unknown, status: number) {
  return new Response(body ? JSON.stringify(body) : null, {
    headers: {
      "Content-Type": "application/json",
    },
    status,
  });
}

export function mockRuntimeGetSuccess(data: unknown) {
  return vi.spyOn(runtimeApiClient, "GET").mockResolvedValue({
    data,
    error: undefined,
    response: jsonResponse(data, 200),
  } as never);
}

export function mockRuntimeGetFailure(status: number, payload: unknown) {
  return vi.spyOn(runtimeApiClient, "GET").mockResolvedValue({
    data: undefined,
    error: payload,
    response: jsonResponse(payload, status),
  } as never);
}

export function mockRuntimePostSuccess(data: unknown) {
  return vi.spyOn(runtimeApiClient, "POST").mockResolvedValue({
    data,
    error: undefined,
    response: jsonResponse(data, 200),
  } as never);
}

export function mockRuntimePostFailure(status: number, payload: unknown) {
  return vi.spyOn(runtimeApiClient, "POST").mockResolvedValue({
    data: undefined,
    error: payload,
    response: jsonResponse(payload, status),
  } as never);
}
