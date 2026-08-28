import { z } from "zod";

import type { components } from "@/api/types";

type GeneratedEpochStalenessResponse =
  components["schemas"]["EpochStalenessProjectionResponse"];
type GeneratedEpochStalenessProjection =
  components["schemas"]["EpochStalenessProjectionView"];

export type AdmittedEpochStalenessResponse =
  Readonly<GeneratedEpochStalenessResponse>;
export type AdmittedEpochStalenessProjection =
  Readonly<GeneratedEpochStalenessProjection>;

const SHA256_PATTERN = /^sha256:[0-9a-f]{64}$/u;
const sha256Schema = z.string().regex(SHA256_PATTERN);
const nonemptyStringSchema = z.string().min(1);
const instantSchema = z
  .string()
  .refine(
    (value) => !Number.isNaN(Date.parse(value)),
    "expected an ISO timestamp",
  );

const projectionStatusSchema = z.enum([
  "current",
  "stale",
  "revalidation_required",
  "contested",
  "not_established",
]);
const predicateProvenanceSchema = z.enum([
  "recomputed",
  "independently_reconciled",
  "consumer_asserted",
  "institutionally_supplied",
  "not_established",
]);
export const epochPerturbationClassSchema = z.enum([
  "incident",
  "appeal",
  "correction",
  "retraction",
  "legal_change",
  "discovered_bias",
]);
const adjudicatedDispositionSchema = z.enum([
  "annotation_only",
  "invalidate",
  "reissue",
  "supersede",
  "withdraw",
  "contested",
  "review_required",
]);

const artifactRefSchema = z
  .object({
    artifact_id: sha256Schema,
    kind: nonemptyStringSchema,
    media_type: nonemptyStringSchema,
  })
  .strict();

const apiMetaSchema = z
  .object({
    generated_at: instantSchema.optional(),
    request_id: nonemptyStringSchema,
    source_kinds: z.array(nonemptyStringSchema).optional(),
  })
  .strict();

const temporalScopeSchema = z
  .object({
    branch: nonemptyStringSchema.nullable().optional(),
    scenario_id: nonemptyStringSchema.nullable().optional(),
    snapshot_id: nonemptyStringSchema.nullable().optional(),
    tx_at: instantSchema.nullable().optional(),
    valid_at: instantSchema.nullable().optional(),
  })
  .strict();

const certificateSchema = z
  .object({
    authority_purpose: nonemptyStringSchema,
    bound_epoch_ref: sha256Schema,
    certificate_ref: artifactRefSchema,
    current_epoch_ref: sha256Schema.nullable(),
    input_certificate_refs: z.array(artifactRefSchema),
    native_coordinate_refs: z.array(nonemptyStringSchema),
    recipe_ref: artifactRefSchema,
    revalidation_requirements: z.array(nonemptyStringSchema),
    rule_schema_profile_refs: z.array(nonemptyStringSchema),
    stale_reasons: z.array(nonemptyStringSchema),
    status: projectionStatusSchema,
    trigger_event_refs: z.array(artifactRefSchema),
  })
  .strict()
  .superRefine((certificate, context) => {
    if (
      certificate.status === "current" &&
      (certificate.current_epoch_ref === null ||
        certificate.bound_epoch_ref !== certificate.current_epoch_ref)
    ) {
      context.addIssue({
        code: "custom",
        message: "current certificate requires the requested epoch",
        path: ["current_epoch_ref"],
      });
    }
    if (
      certificate.status === "current" &&
      (certificate.stale_reasons.length > 0 ||
        certificate.revalidation_requirements.length > 0)
    ) {
      context.addIssue({
        code: "custom",
        message: "current certificate cannot carry stale obligations",
        path: ["status"],
      });
    }
    if (
      ["stale", "revalidation_required", "contested"].includes(
        certificate.status,
      ) &&
      certificate.stale_reasons.length === 0
    ) {
      context.addIssue({
        code: "custom",
        message: "non-current certificate requires a stale reason",
        path: ["stale_reasons"],
      });
    }
  });

const recomputeSchema = z
  .object({
    evidence_content_hash: sha256Schema.nullable(),
    evidence_ref: artifactRefSchema.nullable(),
    predicate_provenance: predicateProvenanceSchema,
    status: z.enum([
      "not_established",
      "pending",
      "running",
      "completed",
      "failed",
    ]),
  })
  .strict()
  .superRefine((recompute, context) => {
    const hasEvidence =
      recompute.evidence_ref !== null &&
      recompute.evidence_content_hash !== null;
    if (
      recompute.status === "not_established" &&
      (hasEvidence || recompute.predicate_provenance !== "not_established")
    ) {
      context.addIssue({
        code: "custom",
        message:
          "not-established recompute cannot carry positive owner evidence",
        path: ["status"],
      });
    }
    if (
      recompute.status !== "not_established" &&
      (!hasEvidence ||
        !["recomputed", "independently_reconciled"].includes(
          recompute.predicate_provenance,
        ))
    ) {
      context.addIssue({
        code: "custom",
        message: "recompute status requires content-bound owner evidence",
        path: ["evidence_ref"],
      });
    }
  });

const dependencySchema = z
  .object({
    advisory_event_refs: z.array(artifactRefSchema),
    authority_purpose: nonemptyStringSchema,
    disposition: z.union([
      z.literal("unchanged"),
      adjudicatedDispositionSchema,
    ]),
    owner_evidence_refs: z.array(artifactRefSchema),
    recompute: recomputeSchema,
    relation: nonemptyStringSchema,
    source_classes: z.array(epochPerturbationClassSchema),
    source_ref: artifactRefSchema,
    target_ref: artifactRefSchema,
  })
  .strict();

const perturbationSchema = z
  .object({
    adjudicated_disposition: adjudicatedDispositionSchema,
    advisory_posture: z.enum(["annotation_only", "review_required"]),
    event_ref: artifactRefSchema,
    observed_at: instantSchema,
    owner_evidence_refs: z.array(artifactRefSchema),
    scope: z.enum(["instance", "dependency_descendants"]),
    source_class: epochPerturbationClassSchema,
    source_evidence_refs: z.array(artifactRefSchema),
    target_ref: artifactRefSchema,
  })
  .strict()
  .superRefine((perturbation, context) => {
    if (
      perturbation.source_class === "appeal" &&
      perturbation.scope !== "instance"
    ) {
      context.addIssue({
        code: "custom",
        message: "appeal projection requires instance scope",
        path: ["scope"],
      });
    }
  });

const lineageSchema = z
  .object({
    current_epoch_ref: sha256Schema,
    predecessor_packet_ref: artifactRefSchema.nullable(),
    previous_epoch_ref: sha256Schema,
    successor_packet_ref: artifactRefSchema.nullable(),
    transition_ref: artifactRefSchema.nullable(),
    trigger_event_refs: z.array(artifactRefSchema),
  })
  .strict()
  .superRefine((lineage, context) => {
    if (lineage.previous_epoch_ref === lineage.current_epoch_ref) {
      context.addIssue({
        code: "custom",
        message: "epoch boundary requires distinct epochs",
        path: ["current_epoch_ref"],
      });
    }
  });

const openWorldRiskComponentSchema = z
  .object({
    component_id: nonemptyStringSchema,
    component_kind: z.enum(["model", "obligation", "calibration", "novel"]),
    evidence_ref: artifactRefSchema.nullable(),
    limitation_code: nonemptyStringSchema,
    predicate_provenance: z.enum([
      "independently_reconciled",
      "not_established",
    ]),
    status: z.enum(["within_scope", "outside_scope", "not_established"]),
  })
  .strict();

const openWorldRiskSchema = z
  .object({
    components: z.array(openWorldRiskComponentSchema),
    limitation_code: nonemptyStringSchema,
    promotion_frozen: z.boolean(),
    status: z.enum(["established", "limited", "not_established"]),
    vector_artifact_ref: artifactRefSchema.nullable(),
  })
  .strict()
  .superRefine((risk, context) => {
    if (risk.promotion_frozen !== (risk.status !== "established")) {
      context.addIssue({
        code: "custom",
        message:
          "OpenWorldRisk promotion freeze must be derived from vector status",
        path: ["promotion_frozen"],
      });
    }
    if (
      risk.status === "established" &&
      risk.components.some((component) => component.status !== "within_scope")
    ) {
      context.addIssue({
        code: "custom",
        message:
          "established OpenWorldRisk requires every component within scope",
        path: ["components"],
      });
    }
  });

const institutionalAbsenceSchema = z
  .object({
    absence_class: z.literal("institutional"),
    appointment_is_closure_precondition: z.literal(false),
    authority_purpose: nonemptyStringSchema,
    capability_state: z.literal("absent/unallocated"),
    closure_condition: nonemptyStringSchema,
    consequence: nonemptyStringSchema,
    inspectable_capabilities: z.array(nonemptyStringSchema),
    observed_result: z.literal("not_established"),
    predicate_provenance: z.literal("not_established"),
    refusal_code: z.enum([
      "policy_admission_missing",
      "epoch_transition_signer_not_established",
    ]),
    role: z.enum(["epoch_predicate_policy_signer", "epoch_transition_signer"]),
    source_refs: z.array(artifactRefSchema),
    title: z.literal("Authority not appointed"),
  })
  .strict()
  .superRefine((absence, context) => {
    const expected =
      absence.role === "epoch_predicate_policy_signer"
        ? "policy_admission_missing"
        : "epoch_transition_signer_not_established";
    if (absence.refusal_code !== expected) {
      context.addIssue({
        code: "custom",
        message: "institutional authority role/refusal mismatch",
        path: ["refusal_code"],
      });
    }
  });

const engineeringAbsenceSchema = z
  .object({
    absence_class: z.literal("engineering"),
    candidate_owner_module: z.literal(
      "polisyos.runtime.quality.derived_observations",
    ),
    candidate_owner_path: z.literal(
      "src/polisyos/runtime/quality/derived_observations.py",
    ),
    capability: z.literal("epoch_inheritance_recompute_status"),
    closure_condition: nonemptyStringSchema,
    consequence: nonemptyStringSchema,
    institutional_dependency: z.literal(false),
    missing_labels: z.tuple([
      z.literal("producer_missing"),
      z.literal("bridge_missing"),
    ]),
    missing_output: nonemptyStringSchema,
    title: z.literal("Engineering capability not wired"),
  })
  .strict();

const denominatorSchema = z
  .object({
    denominator_ref: sha256Schema.nullable(),
    predicate_provenance: predicateProvenanceSchema,
    source_count: z.number().int().nonnegative(),
    target_count: z.number().int().nonnegative(),
  })
  .strict()
  .superRefine((denominator, context) => {
    const established = ["recomputed", "independently_reconciled"].includes(
      denominator.predicate_provenance,
    );
    if (established !== (denominator.denominator_ref !== null)) {
      context.addIssue({
        code: "custom",
        message: "denominator evidence/provenance mismatch",
        path: ["denominator_ref"],
      });
    }
  });

const decisionValidityStatusSchema = z.enum([
  "active",
  "warning",
  "stale",
  "review_required",
  "superseded",
  "reissued",
  "withdrawn",
  "revoked",
  "requires_human_review",
]);

export const epochStalenessProjectionSchema = z
  .object({
    certificates: z.array(certificateSchema),
    current_epoch_ref: sha256Schema.nullable(),
    decision_packet_ref: artifactRefSchema.nullable(),
    decision_validity_status: decisionValidityStatusSchema.nullable(),
    denominator: denominatorSchema,
    dependencies: z.array(dependencySchema),
    engineering_absences: z.array(engineeringAbsenceSchema),
    fixture_only: z.boolean(),
    institutional_absences: z.array(institutionalAbsenceSchema),
    limitations: z.array(nonemptyStringSchema),
    lineage: z.array(lineageSchema),
    observed_at: instantSchema,
    open_world_risk: openWorldRiskSchema,
    owner_as_of: instantSchema.nullable(),
    owner_time_reason: z
      .enum(["owner_time_not_established", "epoch_scope_unresolved"])
      .nullable(),
    perturbations: z.array(perturbationSchema),
    predicate_provenance: predicateProvenanceSchema,
    projection_semantic_hash: sha256Schema,
    requested_query_context_ref: sha256Schema,
    revalidation_required: z.boolean(),
    run_id: nonemptyStringSchema,
    schema_version: z.literal("polisyos.runtime.epoch-staleness.v1"),
    scoped_epoch_refs: z.array(sha256Schema),
    status: projectionStatusSchema,
    temporal_scope: temporalScopeSchema,
  })
  .strict()
  .superRefine((projection, context) => {
    if (
      (projection.owner_as_of === null) ===
      (projection.owner_time_reason === null)
    ) {
      context.addIssue({
        code: "custom",
        message: "owner as_of requires exactly one value or typed reason",
        path: ["owner_as_of"],
      });
    }
    const expectedRevalidation =
      projection.status === "revalidation_required" ||
      projection.certificates.some(
        (certificate) => certificate.status === "revalidation_required",
      );
    if (projection.revalidation_required !== expectedRevalidation) {
      context.addIssue({
        code: "custom",
        message: "revalidation_required must be derived from projection state",
        path: ["revalidation_required"],
      });
    }
    if (
      projection.status === "current" &&
      (projection.current_epoch_ref === null ||
        projection.institutional_absences.length > 0 ||
        !["recomputed", "independently_reconciled"].includes(
          projection.predicate_provenance,
        ))
    ) {
      context.addIssue({
        code: "custom",
        message: "current epoch requires reconciled owner evidence",
        path: ["status"],
      });
    }
  });

export const epochStalenessResponseSchema = z
  .object({
    meta: apiMetaSchema,
    projection: epochStalenessProjectionSchema,
  })
  .strict();

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (typeof value === "object" && value !== null) {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

async function sha256(bytes: Uint8Array): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new TypeError(
      "contract_error: epoch semantic hashing is unavailable",
    );
  }
  const owned = bytes.slice();
  const digest = await globalThis.crypto.subtle.digest("SHA-256", owned.buffer);
  return `sha256:${Array.from(new Uint8Array(digest), (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("")}`;
}

/** Recompute the server's stable semantic identity without observed read time. */
export async function computeEpochStalenessSemanticHash(
  projection: AdmittedEpochStalenessProjection,
): Promise<string> {
  const semantic = structuredClone(projection) as Record<string, unknown>;
  delete semantic.observed_at;
  delete semantic.projection_semantic_hash;
  const prefix = new TextEncoder().encode(
    "polisyos.runtime.epoch-staleness.semantic.v1\0",
  );
  const payload = new TextEncoder().encode(canonicalJson(semantic));
  const framed = new Uint8Array(prefix.byteLength + payload.byteLength);
  framed.set(prefix);
  framed.set(payload, prefix.byteLength);
  return sha256(framed);
}

/** Strictly admit a decoded response and recompute its semantic binding. */
export async function admitEpochStalenessResponse(
  candidate: unknown,
): Promise<AdmittedEpochStalenessResponse> {
  const parsed = epochStalenessResponseSchema.safeParse(candidate);
  if (!parsed.success) {
    throw new TypeError(
      `contract_error: invalid epoch staleness response: ${z.prettifyError(parsed.error)}`,
    );
  }
  const response = parsed.data as AdmittedEpochStalenessResponse;
  const expected = await computeEpochStalenessSemanticHash(response.projection);
  if (expected !== response.projection.projection_semantic_hash) {
    throw new TypeError(
      "contract_error: epoch staleness semantic hash mismatch",
    );
  }
  return response;
}

/** Decode only a defensive copy of the captured response bytes, then admit it. */
export async function admitEpochStalenessResponseBytes(
  rawBytes: Uint8Array,
): Promise<
  Readonly<{
    response: AdmittedEpochStalenessResponse;
    rawBytes: Uint8Array;
  }>
> {
  const captured = rawBytes.slice();
  if (captured.byteLength === 0) {
    throw new TypeError("contract_error: epoch staleness response is empty");
  }
  let decoded: string;
  try {
    decoded = new TextDecoder("utf-8", { fatal: true }).decode(captured);
  } catch {
    throw new TypeError(
      "contract_error: epoch staleness response encoding is invalid",
    );
  }
  let candidate: unknown;
  try {
    candidate = JSON.parse(decoded) as unknown;
  } catch {
    throw new TypeError(
      "contract_error: epoch staleness response JSON is invalid",
    );
  }
  const response = await admitEpochStalenessResponse(candidate);
  return Object.freeze({ response, rawBytes: captured });
}
