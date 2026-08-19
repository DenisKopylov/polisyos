import { z } from "zod";

export const ATLAS_EVIDENCE_RECEIPT_SCHEMA = {
  id: "polisyos.atlas.evidence-receipt",
  version: "1.0.0",
} as const;

export const ATLAS_EVIDENCE_PAYLOAD_SCHEMA = {
  id: "polisyos.atlas.evidence-verification-payload",
  version: "1.0.0",
} as const;

export const ATLAS_EVIDENCE_DENIED_USES = [
  "component_maturity",
  "design_authority",
  "policy_authority",
  "promotion",
  "publication",
  "runtime_authority",
  "stable",
] as const;

export const ATLAS_PREDICATE_PROVENANCE_VALUES = [
  "recomputed",
  "independently_reconciled",
  "consumer_asserted",
  "institutionally_supplied",
  "not_established",
] as const;

/**
 * Storage is delegated to the repository's existing ArtifactStore boundary.
 * C07 defines the receipt payload; C08 must persist and resolve it through CAS.
 */
export const ATLAS_EVIDENCE_STORAGE_CONVENTION = {
  artifact_store_contract: "polisyos.core.artifacts.ArtifactStore.put_json",
  artifact_kind: "atlas_evidence_receipt",
  media_type: "application/json",
  default_local_root: ".polisyos/cas",
  payload_canon_spec: {
    name: "polisyos.canon.json",
    version: "0.2.0",
    forbid_floats: false,
    forbid_nan_inf: true,
    exclude_none: true,
    max_depth: 128,
    sort_keys: true,
    separators: [",", ":"],
    ensure_ascii: false,
  },
  receipt_input_role: "verification_payload",
  retention_class: "content_addressed_runtime_artifacts",
  retention_days: 365,
  cleanup_policy: "manual_approval_only",
  delete_on_expiry: false,
} as const;

const nonEmptyString = z
  .string()
  .min(1)
  .refine((value) => value.trim() === value, {
    message: "value must be non-empty and have no surrounding whitespace",
  });
const identity = nonEmptyString.regex(/^[a-z0-9][a-z0-9._:@/-]*$/);
export const atlasArtifactIdSchema = z
  .string()
  .regex(/^sha256:[0-9a-f]{64}$/);
const repositoryRevision = z.string().regex(/^[0-9a-f]{40}$/);
const evidenceKindSchema = z.enum([
  "automated_browser",
  "automated_keyboard",
  "manual_at",
]);
const utcTimestamp = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
  .refine((value) => {
    const parsed = new Date(value);
    return !Number.isNaN(parsed.valueOf()) && parsed.toISOString() === value;
  }, "timestamp must be a real millisecond-precision UTC instant");

const receiptSchemaIdentity = z
  .object({
    id: z.literal(ATLAS_EVIDENCE_RECEIPT_SCHEMA.id),
    version: z.literal(ATLAS_EVIDENCE_RECEIPT_SCHEMA.version),
  })
  .strict();

const authoritySchema = z
  .object({
    authoritative_for: z.tuple([z.literal("atlas_evidence_capture")]),
    may_not_use_for: z.tuple([
      z.literal("component_maturity"),
      z.literal("design_authority"),
      z.literal("policy_authority"),
      z.literal("promotion"),
      z.literal("publication"),
      z.literal("runtime_authority"),
      z.literal("stable"),
    ]),
  })
  .strict();

const subjectSchema = z
  .object({
    kind: z.enum(["component_state", "surface"]),
    subject_id: identity,
    state_id: identity,
  })
  .strict();

const ruleSchema = z
  .object({
    rule_id: identity,
    rule_version: nonEmptyString,
  })
  .strict();

const producerSchema = z
  .object({
    producer_id: identity,
    producer_version: nonEmptyString,
  })
  .strict();

const verifierSchema = z
  .object({
    verifier_id: identity,
    verifier_version: nonEmptyString,
  })
  .strict();

export const atlasPredicateProvenanceSchema = z.enum(
  ATLAS_PREDICATE_PROVENANCE_VALUES,
);

const provenanceSchema = z
  .object({
    producer: producerSchema,
    verifier: verifierSchema,
    repository_revision: repositoryRevision,
    command_argv: z.array(nonEmptyString).min(1),
    predicate_provenance: atlasPredicateProvenanceSchema,
  })
  .strict()
  .superRefine((provenance, context) => {
    if (
      provenance.producer.producer_id === provenance.verifier.verifier_id
    ) {
      context.addIssue({
        code: "custom",
        path: ["verifier", "verifier_id"],
        message: "the verifier must not be the producing component",
      });
    }
  });

const ATLAS_AUDIENCE_ORDER = [
  "PUBLIC",
  "REVIEWER",
  "EXPERT",
  "MACHINE",
] as const;
const audienceIdentity = z.enum(ATLAS_AUDIENCE_ORDER);
const audienceRank = new Map(
  ATLAS_AUDIENCE_ORDER.map((audience, index) => [audience, index]),
);
const audiencesSchema = z
  .array(audienceIdentity)
  .min(1)
  .superRefine((audiences, context) => {
    if (new Set(audiences).size !== audiences.length) {
      context.addIssue({
        code: "custom",
        message: "audience identities must be unique",
      });
    }
    if (
      audiences.some(
        (audience, index) =>
          index > 0 &&
          (audienceRank.get(audiences[index - 1]) ?? -1) >=
            (audienceRank.get(audience) ?? -1),
      )
    ) {
      context.addIssue({
        code: "custom",
        message: "audience identities must use the canonical Atlas order",
      });
    }
  });

const timesSchema = z
  .object({
    observed_at: utcTimestamp,
    collected_at: utcTimestamp,
    verified_at: utcTimestamp,
  })
  .strict()
  .superRefine((times, context) => {
    const observed = Date.parse(times.observed_at);
    const collected = Date.parse(times.collected_at);
    const verified = Date.parse(times.verified_at);
    if (observed > collected) {
      context.addIssue({
        code: "custom",
        path: ["collected_at"],
        message: "collection cannot precede the observation",
      });
    }
    if (collected > verified) {
      context.addIssue({
        code: "custom",
        path: ["verified_at"],
        message: "verification cannot precede collection",
      });
    }
  });

const findingSchema = z
  .object({
    code: identity,
    detail: nonEmptyString,
  })
  .strict();
const resultSchema = z
  .object({
    outcome: z.enum(["pass", "fail", "incomplete"]),
    findings: z.array(findingSchema),
  })
  .strict()
  .superRefine((result, context) => {
    if (result.outcome === "pass" && result.findings.length !== 0) {
      context.addIssue({
        code: "custom",
        path: ["findings"],
        message: "a passing receipt cannot contain findings",
      });
    }
    if (result.outcome !== "pass" && result.findings.length === 0) {
      context.addIssue({
        code: "custom",
        path: ["findings"],
        message: "a non-passing receipt must explain at least one finding",
      });
    }
  });

const evidencePayloadRefSchema = z
  .object({
    artifact_id: atlasArtifactIdSchema,
    kind: z.literal("atlas_evidence_verification_payload"),
    media_type: z.literal("application/json"),
    schema_id: z.literal(ATLAS_EVIDENCE_PAYLOAD_SCHEMA.id),
    schema_version: z.literal(ATLAS_EVIDENCE_PAYLOAD_SCHEMA.version),
  })
  .strict();

const evidencePayloadSchemaIdentity = z
  .object({
    id: z.literal(ATLAS_EVIDENCE_PAYLOAD_SCHEMA.id),
    version: z.literal(ATLAS_EVIDENCE_PAYLOAD_SCHEMA.version),
  })
  .strict();
const payloadDetailsSchema = z
  .record(z.string(), z.json())
  .superRefine((details, context) => {
    if (Object.keys(details).length === 0) {
      context.addIssue({
        code: "custom",
        message: "the verification payload must contain rule-owned details",
      });
    }
  });

export const atlasEvidencePayloadSchema = z
  .object({
    payload_schema: evidencePayloadSchemaIdentity,
    evidence_kind: evidenceKindSchema,
    subject: subjectSchema,
    rule: ruleSchema,
    provenance: provenanceSchema,
    times: timesSchema,
    result: resultSchema,
    details: payloadDetailsSchema,
  })
  .strict();

export type AtlasEvidencePayload = z.infer<
  typeof atlasEvidencePayloadSchema
>;

const retentionSchema = z
  .object({
    retention_class: z.literal("content_addressed_runtime_artifacts"),
    retention_days: z.literal(365),
    retain_until: utcTimestamp,
    cleanup_policy: z.literal("manual_approval_only"),
  })
  .strict();

export const atlasEvidenceReceiptSchema = z
  .object({
    receipt_schema: receiptSchemaIdentity,
    authority: authoritySchema,
    evidence_kind: evidenceKindSchema,
    subject: subjectSchema,
    rule: ruleSchema,
    provenance: provenanceSchema,
    audiences: audiencesSchema,
    times: timesSchema,
    result: resultSchema,
    evidence_payload_ref: evidencePayloadRefSchema,
    retention: retentionSchema,
  })
  .strict()
  .superRefine((receipt, context) => {
    const expectedRetainUntil = new Date(
      Date.parse(receipt.times.collected_at) +
        ATLAS_EVIDENCE_STORAGE_CONVENTION.retention_days * 24 * 60 * 60 * 1000,
    ).toISOString();
    if (receipt.retention.retain_until !== expectedRetainUntil) {
      context.addIssue({
        code: "custom",
        path: ["retention", "retain_until"],
        message: "retain_until must be exactly 365 days after collection",
      });
    }
  });

export type AtlasEvidenceReceipt = z.infer<typeof atlasEvidenceReceiptSchema>;

const resolvedEvidencePayloadSchema = z
  .object({
    artifact_id: atlasArtifactIdSchema,
    payload: atlasEvidencePayloadSchema,
  })
  .strict();

function assertSameBinding(
  field: string,
  receiptValue: unknown,
  payloadValue: unknown,
): void {
  if (JSON.stringify(receiptValue) !== JSON.stringify(payloadValue)) {
    throw new TypeError(
      `atlas evidence payload semantic binding mismatch: ${field}`,
    );
  }
}

/**
 * Reconcile one CAS-resolved verification payload against its receipt.
 *
 * C08 must call the artifact store's integrity verifier before this function;
 * this function proves semantic binding after resolution, not CAS existence.
 */
export function assertAtlasEvidencePayloadBinding(
  receiptValue: unknown,
  resolvedValue: unknown,
): AtlasEvidencePayload {
  const receipt = parseAtlasEvidenceReceipt(receiptValue);
  const resolved = resolvedEvidencePayloadSchema.parse(resolvedValue);
  if (resolved.artifact_id !== receipt.evidence_payload_ref.artifact_id) {
    throw new TypeError(
      "atlas evidence payload artifact_id does not match the receipt",
    );
  }

  const payload = resolved.payload;
  assertSameBinding(
    "evidence_kind",
    receipt.evidence_kind,
    payload.evidence_kind,
  );
  assertSameBinding("subject", receipt.subject, payload.subject);
  assertSameBinding("rule", receipt.rule, payload.rule);
  assertSameBinding("provenance", receipt.provenance, payload.provenance);
  assertSameBinding("times", receipt.times, payload.times);
  assertSameBinding("result", receipt.result, payload.result);
  return payload;
}

/** Parse the strict receipt payload without resolving or trusting its CAS ref. */
export function parseAtlasEvidenceReceipt(
  value: unknown,
): AtlasEvidenceReceipt {
  return atlasEvidenceReceiptSchema.parse(value);
}
