import { z } from "zod";

import { API_BASE_URL } from "@/shared/lib/constants";

const notEstablished = z.literal("not_established");
const verificationReason = z.enum([
  "promoted_public_record_not_established",
  "client_token_not_server_issued",
  "record_not_issued",
  "issuance_index_invalid",
  "issuance_index_write_failed",
  "verification_issuer_not_configured",
  "public_document_invalid",
  "record_evidence_unavailable",
  "record_signature_missing",
  "record_signature_invalid",
  "record_key_untrusted",
  "record_key_revoked",
  "record_issuer_purpose_untrusted",
  "record_binding_invalid",
  "public_document_binding_invalid",
]);
const verificationDimensions = z.strictObject({
  issuer_issuance: notEstablished,
  projection_faithfulness: notEstablished,
  public_history_establishment: notEstablished,
  durable_verifiability: notEstablished,
  current_authority: notEstablished,
  status_snapshot_selection: notEstablished,
  public_evidence_obtainability: notEstablished,
});

const verificationResponse = z.strictObject({
  record_id: z.string().min(1),
  report_authentication: z.enum(["verified", "invalid", "not_established"]),
  cryptographic_signature: z.enum(["valid", "invalid", "not_established"]),
  report_key_status: z.enum([
    "trusted",
    "revoked",
    "untrusted",
    "not_established",
  ]),
  reason_codes: z.array(verificationReason),
  decision_id: z.string().min(1).nullable(),
  issuer_id: z.string().min(1).nullable(),
  issued_at: z.iso.datetime({ offset: true }).nullable(),
  public_document_digest: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/u)
    .nullable(),
  public_document: z.looseObject({ title: z.string().min(1) }).nullable(),
  promoted_record: z.null(),
  dimensions: verificationDimensions,
});

export type PublicDecisionVerification = z.infer<typeof verificationResponse>;

/** Admit only the server's exact response for the requested immutable record. */
export async function fetchPublicDecisionVerification(
  recordId: string,
  signal: AbortSignal,
): Promise<PublicDecisionVerification> {
  const url = new URL(
    "/api/v1/public-decisions/verification",
    new URL(API_BASE_URL || "/", window.location.origin),
  );
  url.searchParams.set("record_id", recordId);
  const response = await fetch(url.toString(), {
    signal,
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
  });
  if (!response.ok) throw new TypeError("verification_request_failed");
  const result = verificationResponse.parse(await response.json());
  if (result.record_id !== recordId) {
    throw new TypeError("verification_record_mismatch");
  }
  return result;
}

/** Authentication concerns this report, never the unestablished PUBLIC dimensions. */
export function isAuthenticatedVerificationRecord(
  response: PublicDecisionVerification,
): boolean {
  return (
    response.report_authentication === "verified" &&
    response.cryptographic_signature === "valid" &&
    response.report_key_status === "trusted" &&
    response.decision_id !== null &&
    response.issuer_id !== null &&
    response.issued_at !== null &&
    response.public_document_digest !== null &&
    response.public_document !== null
  );
}

/** Unknown server text cannot add an authority claim to a public error. */
export function publicVerificationReason(
  reasonCodes: PublicDecisionVerification["reason_codes"],
): string {
  return reasonCodes.join(", ") || "verification_not_established";
}
