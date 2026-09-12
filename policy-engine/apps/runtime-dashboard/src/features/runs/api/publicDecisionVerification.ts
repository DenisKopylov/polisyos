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

const publicRecordId = z.string().regex(/^gpr_[A-Za-z0-9_-]{32}$/u);
const publicDigest = z.string().regex(/^sha256:[0-9a-f]{64}$/u);
const jsonObject = z.record(z.string(), z.json());
const claimText = z.string().min(1);
const claimReferences = z.array(z.string());
const artifactReferences = z.array(jsonObject);
const publicClaim = z.strictObject({
  schema_version: z.literal("1.0"),
  claim_id: claimText,
  run_id: claimText,
  claim_type: claimText,
  claim_family: claimText.nullable(),
  claim_use: claimText.nullable(),
  text: claimText,
  normalized_subject: z.string().nullable(),
  support_status: claimText,
  publishability: claimText,
  readiness_level: claimText,
  facet_refs: claimReferences,
  obligation_refs: claimReferences,
  concept_spine_refs: claimReferences,
  authority_profile_refs: claimReferences,
  baseline_refs: claimReferences,
  alternative_refs: claimReferences,
  comparison_refs: claimReferences,
  method_need_preconditions: z.array(jsonObject),
  decomposition_source_class: claimText.nullable(),
  evidence_refs: artifactReferences,
  counterevidence_refs: artifactReferences,
  uncertainty_profile_ref: jsonObject.nullable(),
  provenance_ref: jsonObject.nullable(),
  source_attribution: claimReferences,
  reviewer_refs: artifactReferences,
  blocked_reasons: z.array(z.string()),
  metadata: jsonObject,
});

// The owner admits claims and relocates private references. Preserve its entire
// JSON tree here; decoding is not a second source-policy or evidence verifier.
const governedPublicDocument = z.strictObject({
  schema_version: z.literal("polisyos.governed_public_document.v1"),
  profile: z.literal("exact_owner_ledger_v1"),
  ledger: z.strictObject({
    schema_version: z.literal("2.0"),
    run_id: z.string().min(1),
    base_ledger_ref: jsonObject.nullable(),
    current_claims: z.array(publicClaim).min(1),
    events: z.array(jsonObject),
    retention_policy: jsonObject,
    metadata: jsonObject,
  }),
  permitted_uses: z.tuple([z.literal("bounded_public_custody")]),
  denied_uses: z.tuple([
    z.literal("policy_performance"),
    z.literal("current_policy_authority"),
    z.literal("complete_public_history"),
    z.literal("first_publication"),
  ]),
  limitations: z.array(z.string()),
});
const governedPublicRecord = z.strictObject({
  schema_version: z.literal("polisyos.governed_public_record.v1"),
  record_id: publicRecordId,
  decision_id: z.string().min(1),
  issuer_id: z.string().min(1),
  signing_key_id: publicDigest,
  purpose: z.literal("governed_public_record"),
  rule_version: z.literal("governed-public-record.v1"),
  issued_at: z.iso.datetime({ offset: true }),
  public_document_digest: publicDigest,
  publication_class: z.literal("governed_public_record"),
});
const governedVerificationResponse = z
  .discriminatedUnion("report_authentication", [
    z.strictObject({
      publication_class: z.literal("governed_public_record"),
      record_id: publicRecordId,
      report_authentication: z.literal("verified"),
      cryptographic_signature: z.literal("valid"),
      // Revocation does not erase historical issuance or grant current authority.
      report_key_status: z.enum(["trusted", "revoked"]),
      reason_codes: z.array(z.string()).length(0),
      decision_id: z.string().min(1),
      issuer_id: z.string().min(1),
      issued_at: z.iso.datetime({ offset: true }),
      public_document_digest: publicDigest,
      public_document: governedPublicDocument,
      promoted_record: governedPublicRecord,
      dimensions: verificationDimensions.extend({
        issuer_issuance: z.literal("established"),
        projection_faithfulness: z.literal("established"),
      }),
    }),
    z.strictObject({
      publication_class: z.literal("governed_public_record"),
      record_id: publicRecordId,
      report_authentication: z.enum(["invalid", "not_established"]),
      cryptographic_signature: z.enum(["valid", "invalid", "not_established"]),
      report_key_status: z.enum([
        "trusted",
        "revoked",
        "untrusted",
        "not_established",
      ]),
      reason_codes: z.array(z.string()),
      decision_id: z.null().default(null),
      issuer_id: z.null().default(null),
      issued_at: z.null().default(null),
      public_document_digest: z.null().default(null),
      public_document: z.null().default(null),
      promoted_record: z.null().default(null),
      dimensions: verificationDimensions,
    }),
  ])
  .superRefine((response, context) => {
    if (response.report_authentication !== "verified") return;
    for (const field of [
      "record_id",
      "decision_id",
      "issuer_id",
      "issued_at",
      "public_document_digest",
    ] as const) {
      if (response[field] !== response.promoted_record[field]) {
        context.addIssue({
          code: "custom",
          path: ["promoted_record", field],
          message: "governed_public_record_binding_invalid",
        });
      }
    }
  });

type VerificationReport = z.infer<typeof verificationResponse>;
export type GovernedPublicRecordVerification = z.infer<
  typeof governedVerificationResponse
>;
export type AuthenticatedGovernedPublicRecord = Extract<
  GovernedPublicRecordVerification,
  { report_authentication: "verified" }
>;
export type PublicDecisionVerification =
  | VerificationReport
  | GovernedPublicRecordVerification;

export function isGovernedPublicRecordVerification(
  response: PublicDecisionVerification,
): response is GovernedPublicRecordVerification {
  return "publication_class" in response;
}

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
  const payload: unknown = await response.json();
  // The governed namespace cannot fall back to the legacy report-only contract.
  const result = recordId.startsWith("gpr_")
    ? governedVerificationResponse.parse(payload)
    : verificationResponse.parse(payload);
  if (result.record_id !== recordId) {
    throw new TypeError("verification_record_mismatch");
  }
  return result;
}

/** Authentication concerns this report, never the unestablished PUBLIC dimensions. */
export function isAuthenticatedVerificationRecord(
  response: VerificationReport,
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
  reasonCodes: VerificationReport["reason_codes"],
): string {
  return reasonCodes.join(", ") || "verification_not_established";
}
