import createClient from "openapi-fetch";

import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { API_BASE_URL } from "@/shared/lib/constants";
import { emitRuntimeApiEvent } from "./runtimeApiEvents";
import type { paths } from "./types";

export const runtimeApiClient = createClient<paths>({
  baseUrl: API_BASE_URL,
  fetch: authAwareRuntimeFetch,
});

runtimeApiClient.use({
  onError({ error, request, schemaPath }) {
    emitRuntimeApiEvent({
      status: 0,
      code: "runtime_api_network_error",
      detail:
        error instanceof Error
          ? error.message
          : "Runtime API request failed before a response was returned",
      requestId: null,
      source: request.url || schemaPath,
      timestamp: Date.now(),
    });
  },
});
