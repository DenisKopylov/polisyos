import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { authAwareRuntimeFetch } from "@/app/auth/authSession";
import { buildRuntimeApiUrl } from "@/api/url";
import { createRuntimeApiError } from "@/api/http";
import { queryKeys } from "@/api/queryKeys";
import { authMeSchema, type AuthMePayload } from "@/api/validators";

export const FALLBACK_AUTH_ME: AuthMePayload = {
  meta: {
    generated_at: new Date("2026-03-10T00:00:00Z").toISOString(),
    request_id: "fallback-auth-me",
    source_kinds: [],
  },
  user_id: "fixture-analyst",
  display_name: "Fixture Analyst",
  tenant_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  principal_type: "user",
  cell_id: "cell-a",
  roles: ["analyst"],
  permissions: [
    "dashboard.view",
    "evidence.promotions.approve",
    "evidence.promotions.reject",
    "evidence.review",
    "evidence.view",
    "knowledge.view",
    "platform.view",
    "runs.launch",
    "runs.review",
    "runs.view",
  ],
  mfa_verified: true,
  feature_overrides: {
    enableReviewCollaboration: false,
  },
};

async function fetchAuthMe(): Promise<AuthMePayload> {
  const response = await authAwareRuntimeFetch(
    new Request(buildRuntimeApiUrl("/api/v1/auth/me"), {
      headers: {
        accept: "application/json",
      },
    }),
  );
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : null;

  if (!response.ok || !payload) {
    throw createRuntimeApiError(
      response,
      payload,
      "Failed to load auth principal",
    );
  }

  return authMeSchema.parse(payload);
}

export function authMeQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.authMe(),
    queryFn: fetchAuthMe,
    staleTime: Number.POSITIVE_INFINITY,
    retry: 1,
    placeholderData: FALLBACK_AUTH_ME,
  });
}

export function useAuthMe() {
  return useQuery(authMeQueryOptions());
}

export function useSuspenseAuthMe() {
  return useSuspenseQuery(authMeQueryOptions());
}
