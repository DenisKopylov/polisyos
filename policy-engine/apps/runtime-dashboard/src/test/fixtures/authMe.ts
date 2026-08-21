import type { components } from "@/api/types";
import { authMeSchema, type AuthMePayload } from "@/api/validators";

type AuthMeResponse = components["schemas"]["AuthMeResponse"];

/** Test-only `/auth/me` payload, checked against generated and runtime shapes. */
export const TEST_AUTH_ME_RESPONSE = {
  meta: {
    generated_at: "2026-03-10T00:00:00Z",
    request_id: "test-auth-me",
    source_kinds: [],
  },
  user_id: "test-analyst",
  display_name: "Test Analyst",
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
    "mode.analyst",
    "platform.view",
    "runs.launch",
    "runs.review",
    "runs.view",
  ],
  mfa_verified: true,
  feature_overrides: {
    enableReviewCollaboration: false,
  },
} satisfies AuthMeResponse;

export const TEST_AUTH_ME: AuthMePayload = authMeSchema.parse(
  TEST_AUTH_ME_RESPONSE,
);
