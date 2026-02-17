import { useMutation } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import type { components } from "../types";

export type LexTriggerRequest = components["schemas"]["LexTriggerRequest"];
export type LexTriggerResponse = components["schemas"]["LexTriggerResponse"];

async function triggerLexPipeline(body: LexTriggerRequest): Promise<LexTriggerResponse> {
  const { data, error, response } = await runtimeApiClient.POST("/api/v1/control/lex/trigger", {
    body,
  });
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to trigger Lex pipeline");
  }
  return data as LexTriggerResponse;
}

export function useLexTrigger() {
  return useMutation({
    mutationFn: triggerLexPipeline,
  });
}
