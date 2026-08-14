import { z } from "zod";

import readinessSchema from "../../../../../architecture/atlas_surfaces/surface-readiness-ledger.schema.json";
import {
  ATLAS_EVIDENCE_DENIED_USES,
  assertAtlasEvidencePayloadBinding,
  atlasArtifactIdSchema,
  atlasPredicateProvenanceSchema,
  parseAtlasEvidenceReceipt,
  type AtlasEvidencePayload,
  type AtlasEvidenceReceipt,
} from "./atlasEvidenceArtifact";

export const ATLAS_MANUAL_AT_PROTOCOL = {
  id: "polisyos.atlas.manual-at-review",
  version: "1.0.0",
  rule_id: "atlas.manual-at-maturity-prerequisite",
} as const;

const identity = z
  .string()
  .min(1)
  .regex(/^[a-z0-9][a-z0-9._:@/-]*$/);
const nonEmptyString = z
  .string()
  .min(1)
  .refine((value) => value.trim() === value, {
    message: "value must have no surrounding whitespace",
  });
const utcTimestamp = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
  .refine((value) => {
    const parsed = new Date(value);
    return !Number.isNaN(parsed.valueOf()) && parsed.toISOString() === value;
  }, "timestamp must be a real millisecond-precision UTC instant");

const protocolIdentitySchema = z
  .object({
    id: z.literal(ATLAS_MANUAL_AT_PROTOCOL.id),
    version: z.literal(ATLAS_MANUAL_AT_PROTOCOL.version),
    rule_id: z.literal(ATLAS_MANUAL_AT_PROTOCOL.rule_id),
  })
  .strict();

const manualAuthoritySchema = z
  .object({
    authoritative_for: z.tuple([z.literal("manual_at_observation")]),
    may_not_use_for: z.array(nonEmptyString),
  })
  .strict()
  .superRefine((authority, context) => {
    if (
      JSON.stringify(authority.may_not_use_for) !==
      JSON.stringify(ATLAS_EVIDENCE_DENIED_USES)
    ) {
      context.addIssue({
        code: "custom",
        path: ["may_not_use_for"],
        message: "manual AT authority must preserve the complete C07 denial set",
      });
    }
  });

const taskResultSchema = z
  .object({
    task_id: identity,
    outcome: z.enum(["pass", "fail", "unknown"]),
  })
  .strict();

function addUniqueIssue(
  values: readonly string[],
  path: string,
  message: string,
  context: z.RefinementCtx,
): void {
  if (new Set(values).size !== values.length) {
    context.addIssue({ code: "custom", path: [path], message });
  }
}

const basisSchema = z
  .object({
    profile_ref: atlasArtifactIdSchema.nullable(),
    predicate_provenance: atlasPredicateProvenanceSchema,
    required_task_ids: z.array(identity),
    required_at_capabilities: z.array(identity),
  })
  .strict()
  .superRefine((basis, context) => {
    addUniqueIssue(
      basis.required_task_ids,
      "required_task_ids",
      "required manual AT task identities must be unique",
      context,
    );
    addUniqueIssue(
      basis.required_at_capabilities,
      "required_at_capabilities",
      "required assistive-technology capabilities must be unique",
      context,
    );
  });

const sessionSchema = z
  .object({
    session_id: identity,
    assistive_technologies: z.array(nonEmptyString).min(1),
    observed_at_capabilities: z.array(identity),
    observation_status: z.enum(["observed", "unknown"]),
    observed_task_count: z.number().int().nonnegative().nullable(),
    task_results: z.array(taskResultSchema),
  })
  .strict()
  .superRefine((session, context) => {
    addUniqueIssue(
      session.assistive_technologies,
      "assistive_technologies",
      "assistive-technology identities must be unique",
      context,
    );
    addUniqueIssue(
      session.observed_at_capabilities,
      "observed_at_capabilities",
      "observed assistive-technology capabilities must be unique",
      context,
    );
    addUniqueIssue(
      session.task_results.map((task) => task.task_id),
      "task_results",
      "manual AT task identities must be unique",
      context,
    );
    if (session.observation_status === "unknown") {
      if (session.observed_task_count !== null || session.task_results.length !== 0) {
        context.addIssue({
          code: "custom",
          path: ["observed_task_count"],
          message: "unknown observation status must retain a null count and no task claims",
        });
      }
      return;
    }
    if (
      session.observed_task_count === null ||
      session.observed_task_count !== session.task_results.length
    ) {
      context.addIssue({
        code: "custom",
        path: ["observed_task_count"],
        message: "known observation count must equal the complete task result set",
      });
    }
  });

export const atlasManualAtDetailsSchema = z
  .object({
    protocol_schema: protocolIdentitySchema,
    reviewer: z
      .object({
        reviewer_id: identity,
        reviewer_role: z.literal("assistive_technology_reviewer"),
      })
      .strict(),
    basis: basisSchema,
    session: sessionSchema,
    authority: manualAuthoritySchema,
    expires_at: utcTimestamp,
  })
  .strict();

export type AtlasManualAtDetails = z.infer<typeof atlasManualAtDetailsSchema>;

export interface ManualAtEvidenceBundle {
  /** The future C08 ArtifactStore-resolved identity for the receipt itself. */
  receipt_artifact_id: string;
  receipt: AtlasEvidenceReceipt;
  resolved_payload: {
    artifact_id: string;
    payload: AtlasEvidencePayload;
  };
}

const maturityValues = readinessSchema.$defs.componentMaturity.enum;
const maturityOwnerEntrySchema = z
  .object({
    id: identity,
    kind: z.literal("component"),
    maturity: z.string().refine((value) => maturityValues.includes(value), {
      message: "maturity must come from the architecture-owned vocabulary",
    }),
    evidence_refs: z.array(
      z
        .object({
          kind: nonEmptyString,
          ref: nonEmptyString,
          as_of: nonEmptyString,
        })
        .loose(),
    ),
  })
  .loose();

export type AtlasMaturityOwnerEntry = z.infer<typeof maturityOwnerEntrySchema>;

export type ManualAtMaturityResult = {
  decision: "blocked" | "not_required";
  code:
    | "manual_at_not_required"
    | "manual_at_evidence_absent"
    | "manual_at_owner_reference_absent"
    | "manual_at_evidence_expired"
    | "manual_at_evidence_not_yet_valid"
    | "manual_at_expiry_invalid"
    | "manual_at_authority_bound_exceeded"
    | "manual_at_subject_mismatch"
    | "manual_at_evidence_unknown"
    | "manual_at_zero_observations"
    | "manual_at_predicate_not_admissible"
    | "manual_at_basis_not_established"
    | "manual_at_basis_mismatch"
    | "manual_at_payload_unverified"
    | "manual_at_integrity_not_established"
    | "manual_at_protocol_invalid"
    | "manual_at_evidence_failed";
  evidence_status:
    | "not_required"
    | "missing"
    | "expired"
    | "future"
    | "authority_rejected"
    | "mismatched"
    | "unknown"
    | "zero"
    | "unreconciled"
    | "unverified"
    | "inadequate"
    | "invalid"
    | "failed";
  grants_stable: false;
};

function blocked(
  code: ManualAtMaturityResult["code"],
  evidenceStatus: ManualAtMaturityResult["evidence_status"],
): ManualAtMaturityResult {
  return {
    decision: "blocked",
    code,
    evidence_status: evidenceStatus,
    grants_stable: false,
  };
}

function stringSetsMatch(left: readonly string[], right: readonly string[]): boolean {
  const leftSorted = [...left].sort();
  const rightSorted = [...right].sort();
  return (
    leftSorted.length === rightSorted.length &&
    leftSorted.every((value, index) => value === rightSorted[index])
  );
}

/**
 * Evaluate the manual-AT prerequisite on one architecture-owned adoption row.
 *
 * This contract cannot satisfy the prerequisite yet: C08 must resolve and
 * integrity-verify both CAS artifacts and C10 must reconcile the basis owner.
 */
export function evaluateManualAtMaturityPrerequisite(
  ownerEntryValue: unknown,
  stateIdValue: string,
  bundle: ManualAtEvidenceBundle | undefined,
  evaluatedAtValue: string,
): ManualAtMaturityResult {
  const ownerEntry = maturityOwnerEntrySchema.parse(ownerEntryValue);
  const stateId = identity.parse(stateIdValue);
  const evaluatedAt = utcTimestamp.parse(evaluatedAtValue);

  if (ownerEntry.maturity !== "stable") {
    return {
      decision: "not_required",
      code: "manual_at_not_required",
      evidence_status: "not_required",
      grants_stable: false,
    };
  }
  if (bundle === undefined) {
    return blocked("manual_at_evidence_absent", "missing");
  }

  let receiptArtifactId: string;
  try {
    receiptArtifactId = atlasArtifactIdSchema.parse(bundle.receipt_artifact_id);
  } catch {
    return blocked("manual_at_payload_unverified", "unverified");
  }
  if (
    !ownerEntry.evidence_refs.some(
      (reference) =>
        reference.kind === "at_manual" && reference.ref === receiptArtifactId,
    )
  ) {
    return blocked("manual_at_owner_reference_absent", "missing");
  }

  let receipt: AtlasEvidenceReceipt;
  let payload: AtlasEvidencePayload;
  try {
    receipt = parseAtlasEvidenceReceipt(bundle.receipt);
    payload = assertAtlasEvidencePayloadBinding(receipt, bundle.resolved_payload);
  } catch {
    return blocked("manual_at_payload_unverified", "unverified");
  }

  if (
    receipt.subject.kind !== "component_state" ||
    receipt.subject.subject_id !== ownerEntry.id ||
    receipt.subject.state_id !== stateId
  ) {
    return blocked("manual_at_subject_mismatch", "mismatched");
  }
  if (
    receipt.evidence_kind !== "manual_at" ||
    receipt.rule.rule_id !== ATLAS_MANUAL_AT_PROTOCOL.rule_id ||
    receipt.rule.rule_version !== ATLAS_MANUAL_AT_PROTOCOL.version
  ) {
    return blocked("manual_at_protocol_invalid", "invalid");
  }

  const detailsResult = atlasManualAtDetailsSchema.safeParse(payload.details);
  if (!detailsResult.success) {
    const authorityIssue = detailsResult.error.issues.some(
      (issue) => issue.path[0] === "authority",
    );
    return authorityIssue
      ? blocked("manual_at_authority_bound_exceeded", "authority_rejected")
      : blocked("manual_at_protocol_invalid", "invalid");
  }
  const details = detailsResult.data;

  if (
    receipt.provenance.predicate_provenance !== "recomputed" &&
    receipt.provenance.predicate_provenance !== "independently_reconciled"
  ) {
    return blocked("manual_at_predicate_not_admissible", "unreconciled");
  }

  const verifiedAt = Date.parse(receipt.times.verified_at);
  const evaluationAt = Date.parse(evaluatedAt);
  const expiresAt = Date.parse(details.expires_at);
  if (evaluationAt < verifiedAt) {
    return blocked("manual_at_evidence_not_yet_valid", "future");
  }
  if (expiresAt <= verifiedAt) {
    return blocked("manual_at_expiry_invalid", "invalid");
  }
  if (expiresAt <= evaluationAt) {
    return blocked("manual_at_evidence_expired", "expired");
  }

  if (details.session.observation_status === "unknown") {
    return blocked("manual_at_evidence_unknown", "unknown");
  }
  if (details.session.observed_task_count === 0) {
    return blocked("manual_at_zero_observations", "zero");
  }
  if (
    receipt.result.outcome !== "pass" ||
    details.session.task_results.some((task) => task.outcome !== "pass")
  ) {
    return blocked("manual_at_evidence_failed", "failed");
  }

  if (
    details.basis.profile_ref === null ||
    (details.basis.predicate_provenance !== "recomputed" &&
      details.basis.predicate_provenance !== "independently_reconciled")
  ) {
    return blocked("manual_at_basis_not_established", "unreconciled");
  }
  if (
    !stringSetsMatch(
      details.basis.required_task_ids,
      details.session.task_results.map((task) => task.task_id),
    ) ||
    !stringSetsMatch(
      details.basis.required_at_capabilities,
      details.session.observed_at_capabilities,
    )
  ) {
    return blocked("manual_at_basis_mismatch", "inadequate");
  }

  return blocked("manual_at_integrity_not_established", "unverified");
}
