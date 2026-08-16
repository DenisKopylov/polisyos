import { z } from "zod";

export const ATLAS_EVIDENCE_RECEIPT_SCHEMA = {
  id: "polisyos.atlas.evidence-receipt",
  version: "1.0.0",
} as const;

export const ATLAS_EVIDENCE_PAYLOAD_SCHEMA = {
  id: "polisyos.atlas.evidence-verification-payload",
  version: "1.0.0",
} as const;

/** C10 extends, rather than replaces, the C07 evidence envelope. */
export const ATLAS_EVIDENCE_RECONCILIATION_RECEIPT_SCHEMA = {
  id: "polisyos.atlas.evidence-receipt",
  version: "1.1.0",
} as const;

export const ATLAS_EVIDENCE_RECONCILIATION_PAYLOAD_SCHEMA = {
  id: "polisyos.atlas.evidence-verification-payload",
  version: "1.1.0",
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
 * The only authority-grade identity accepted for the C10 reconciliation
 * observation.  C07 remains intentionally more general and keeps v1.0
 * receipts readable; C10 must not turn that compatibility into an unrelated
 * subject/rule admission path.
 */
export const ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT = {
  evidence_kind: "automated_reconciliation",
  subject: {
    kind: "surface",
    subject_id: "atlas-surface-readiness",
    state_id: "ledger-reconciliation",
  },
  rule: {
    rule_id: "atlas.surface-readiness-reconciliation",
    rule_version: "1.0.0",
  },
  authority: {
    authoritative_for: ["atlas_surface_readiness_reconciliation"],
    may_not_use_for: [
      "component_maturity",
      "design_authority",
      "policy_authority",
      "promotion",
      "publication",
      "runtime_authority",
      "stable",
    ],
  },
  producer: {
    producer_id: "atlas-surface-readiness-reconciliation-producer",
    producer_version: "1.0.0",
  },
  verifier: {
    verifier_id: "atlas-surface-readiness-reconciliation-verifier",
    verifier_version: "1.0.0",
  },
  command_argv: ["node", "scripts/reconcile_atlas_surface_readiness.mjs"],
  predicate_provenance: "independently_reconciled",
  field_provenance: {
    adoption_denominator: "recomputed",
    readiness_denominator: "recomputed",
    stable_claims: "recomputed",
    implemented_claims: "recomputed",
    redirect_route_identity: "independently_reconciled",
    redirect_behavioral_matrix: "independently_reconciled",
    route_test_receipt: "independently_reconciled",
    route_test_process_exit: "independently_reconciled",
    route_test_report_sha256: "recomputed",
    raw_report_sha256: "recomputed",
    canonical_source_artifacts: "recomputed",
    capture_implementation: "independently_reconciled",
  },
  route_test: {
    receipt_schema: {
      id: "polisyos.atlas.c10-route-test-receipt",
      version: "1.0.0",
    },
    test_file: "src/app/routes/routes.test.tsx",
    assertions: [
      "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/launch'",
      "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/sources'",
      "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/data'",
      "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/lex'",
      "APP_ROUTES wraps app routes with the shell and follows legacy redirect from '/health'",
    ],
  },
  implementation_paths: [
    "apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.ts",
    "apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.ts",
    "apps/runtime-dashboard/src/test/evidence/atlasSurfaceReadinessReconciliation.ts",
    "apps/runtime-dashboard/src/app/routes/routes.tsx",
    "apps/runtime-dashboard/src/app/routes/routes.test.tsx",
    "apps/runtime-dashboard/scripts/reconcile_atlas_surface_readiness.mjs",
    "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
  ],
  source_artifact_paths: [
    "architecture/atlas_surfaces/atlas-v15-adoption-ledger.json",
    "architecture/atlas_surfaces/adoption-ledger.schema.json",
    "architecture/atlas_surfaces/live-application-readiness-ledger.json",
    "architecture/atlas_surfaces/surface-readiness-ledger.schema.json",
    "apps/runtime-dashboard/src/app/routes/routes.tsx",
    "apps/runtime-dashboard/src/app/routes/routes.test.tsx",
  ],
} as const;

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
  "automated_reconciliation",
]);
const utcTimestamp = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)
  .refine((value) => {
    const parsed = new Date(value);
    return !Number.isNaN(parsed.valueOf()) && parsed.toISOString() === value;
  }, "timestamp must be a real millisecond-precision UTC instant");

const receiptSchemaIdentity = z
  .union([
    z
      .object({
        id: z.literal(ATLAS_EVIDENCE_RECEIPT_SCHEMA.id),
        version: z.literal(ATLAS_EVIDENCE_RECEIPT_SCHEMA.version),
      })
      .strict(),
    z
      .object({
        id: z.literal(ATLAS_EVIDENCE_RECONCILIATION_RECEIPT_SCHEMA.id),
        version: z.literal(ATLAS_EVIDENCE_RECONCILIATION_RECEIPT_SCHEMA.version),
      })
      .strict(),
  ]);

const authoritySchema = z
  .union([
    z
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
      .strict(),
    z
      .object({
        authoritative_for: z.tuple([
          z.literal("atlas_surface_readiness_reconciliation"),
        ]),
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
      .strict(),
  ]);

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
    schema_version: z.enum([
      ATLAS_EVIDENCE_PAYLOAD_SCHEMA.version,
      ATLAS_EVIDENCE_RECONCILIATION_PAYLOAD_SCHEMA.version,
    ]),
  })
  .strict();

const evidencePayloadSchemaIdentity = z
  .union([
    z
      .object({
        id: z.literal(ATLAS_EVIDENCE_PAYLOAD_SCHEMA.id),
        version: z.literal(ATLAS_EVIDENCE_PAYLOAD_SCHEMA.version),
      })
      .strict(),
    z
      .object({
        id: z.literal(ATLAS_EVIDENCE_RECONCILIATION_PAYLOAD_SCHEMA.id),
        version: z.literal(ATLAS_EVIDENCE_RECONCILIATION_PAYLOAD_SCHEMA.version),
      })
      .strict(),
  ]);
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

function c10IdentityMatches(
  value: unknown,
  expected: unknown,
): boolean {
  if (Array.isArray(value) || Array.isArray(expected)) {
    return (
      Array.isArray(value) &&
      Array.isArray(expected) &&
      value.length === expected.length &&
      value.every((item, index) => c10IdentityMatches(item, expected[index]))
    );
  }
  if (
    typeof value === "object" &&
    value !== null &&
    typeof expected === "object" &&
    expected !== null
  ) {
    const valueRecord = value as Record<string, unknown>;
    const expectedRecord = expected as Record<string, unknown>;
    const valueKeys = Object.keys(valueRecord).sort();
    const expectedKeys = Object.keys(expectedRecord).sort();
    return (
      c10IdentityMatches(valueKeys, expectedKeys) &&
      valueKeys.every((key) =>
        c10IdentityMatches(valueRecord[key], expectedRecord[key]),
      )
    );
  }
  return Object.is(value, expected);
}

const C10_DETAIL_KEYS = [
  "reconciliation",
  "route_test_receipt",
  "route_test_report_sha256",
  "raw_report_sha256",
  "source_artifacts",
  "capture_implementation",
  "field_provenance",
] as const;

const C10_RECONCILIATION_KEYS = [
  "adoption_entries",
  "adoption_stable",
  "adoption_stable_ids",
  "readiness_entries",
  "readiness_stable",
  "readiness_stable_ids",
  "readiness_implemented",
  "implemented_surface_ids",
  "nondeprecated_implemented_ids",
  "verified_deprecated_redirects",
] as const;

function c10Record(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function c10Sha256(value: unknown): value is string {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
}

function c10UniqueStrings(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.every((item) => typeof item === "string" && item.length > 0) &&
    new Set(value).size === value.length
  );
}

function c10SourceArtifactsMatch(value: unknown): boolean {
  const sourceArtifacts = c10Record(value);
  if (
    !sourceArtifacts ||
    !c10IdentityMatches(Object.keys(sourceArtifacts).sort(), ["files", "source_set_sha256"]) ||
    !c10Sha256(sourceArtifacts.source_set_sha256) ||
    !Array.isArray(sourceArtifacts.files) ||
    sourceArtifacts.files.length !==
      ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.source_artifact_paths.length
  ) {
    return false;
  }
  return sourceArtifacts.files.every((file, index) => {
    const record = c10Record(file);
    return (
      record !== undefined &&
      c10IdentityMatches(Object.keys(record).sort(), ["path", "sha256"]) &&
      record.path ===
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.source_artifact_paths[index] &&
      c10Sha256(record.sha256)
    );
  });
}

function c10RouteReceiptPasses(value: unknown): boolean | undefined {
  const receipt = c10Record(value);
  if (!receipt || !Array.isArray(receipt.required_assertions)) {
    return undefined;
  }
  const expectedKeys = [
    "outcome",
    "process_exit_code",
    "receipt_schema",
    "report_sha256",
    "required_assertions",
    "test_file",
  ];
  if (receipt.outcome === "fail") {
    expectedKeys.push("failure_code");
  }
  if (
    !c10IdentityMatches(Object.keys(receipt).sort(), expectedKeys.sort()) ||
    !c10IdentityMatches(
      receipt.receipt_schema,
      ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.receipt_schema,
    ) ||
    receipt.test_file !== ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.test_file ||
    !c10Sha256(receipt.report_sha256) ||
    !Number.isInteger(receipt.process_exit_code) ||
    (receipt.outcome !== "pass" && receipt.outcome !== "fail") ||
    receipt.required_assertions.length !==
      ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.assertions.length
  ) {
    return undefined;
  }
  const allPassed = receipt.required_assertions.every((assertion, index) => {
    const record = c10Record(assertion);
    return (
      record !== undefined &&
      c10IdentityMatches(Object.keys(record).sort(), ["full_name", "status"]) &&
      record.full_name ===
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.route_test.assertions[index] &&
      record.status === "pass"
    );
  });
  const passes = receipt.process_exit_code === 0 && allPassed;
  if (receipt.outcome === "pass") {
    return passes ? true : undefined;
  }
  return receipt.failure_code === "redirect_test_receipt_invalid" ? false : undefined;
}

function c10DetailsMatch(
  value: Record<string, unknown>,
  result: { outcome: "pass" | "fail" | "incomplete"; findings: { code: string }[] },
): boolean {
  const reconciliation = c10Record(value.reconciliation);
  const routePasses = c10RouteReceiptPasses(value.route_test_receipt);
  if (
    !c10IdentityMatches(Object.keys(value).sort(), [...C10_DETAIL_KEYS].sort()) ||
    !c10IdentityMatches(
      value.field_provenance,
      ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.field_provenance,
    ) ||
    !reconciliation ||
    !c10IdentityMatches(
      Object.keys(reconciliation).sort(),
      [...C10_RECONCILIATION_KEYS].sort(),
    ) ||
    !c10SourceArtifactsMatch(value.source_artifacts) ||
    !c10Sha256(value.raw_report_sha256) ||
    !c10Sha256(value.route_test_report_sha256) ||
    value.raw_report_sha256 !== value.route_test_report_sha256 ||
    value.route_test_report_sha256 !== c10Record(value.route_test_receipt)?.report_sha256 ||
    routePasses === undefined
  ) {
    return false;
  }
  const countKeys = [
    "adoption_entries",
    "adoption_stable",
    "readiness_entries",
    "readiness_stable",
    "readiness_implemented",
  ] as const;
  if (
    countKeys.some(
      (key) =>
        !Number.isInteger(reconciliation[key]) ||
        (reconciliation[key] as number) < 0,
    ) ||
    !c10UniqueStrings(reconciliation.adoption_stable_ids) ||
    !c10UniqueStrings(reconciliation.readiness_stable_ids) ||
    !c10UniqueStrings(reconciliation.implemented_surface_ids) ||
    !c10UniqueStrings(reconciliation.nondeprecated_implemented_ids) ||
    !Array.isArray(reconciliation.verified_deprecated_redirects) ||
    reconciliation.adoption_stable_ids.length !== reconciliation.adoption_stable ||
    reconciliation.readiness_stable_ids.length !== reconciliation.readiness_stable ||
    reconciliation.implemented_surface_ids.length !== reconciliation.readiness_implemented
  ) {
    return false;
  }
  const findingCodes = new Set(result.findings.map((finding) => finding.code));
  const hasStable =
    reconciliation.adoption_stable + reconciliation.readiness_stable > 0;
  const hasNonDeprecatedImplemented =
    reconciliation.nondeprecated_implemented_ids.length > 0;
  const requiresFailure = hasStable || hasNonDeprecatedImplemented || !routePasses;
  if (requiresFailure && result.outcome !== "fail") {
    return false;
  }
  if (
    hasStable &&
    !findingCodes.has("stable_evidence_reference_unresolved")
  ) {
    return false;
  }
  if (
    hasNonDeprecatedImplemented &&
    (!findingCodes.has("implemented_negative_test_missing") ||
      !findingCodes.has("implemented_semantic_test_missing"))
  ) {
    return false;
  }
  return (
    routePasses || findingCodes.has("redirect_test_receipt_invalid")
  );
}

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
  .strict()
  .superRefine((payload, context) => {
    const isReconciliation =
      payload.evidence_kind ===
      ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.evidence_kind;
    const isReconciliationSchema =
      payload.payload_schema.version ===
      ATLAS_EVIDENCE_RECONCILIATION_PAYLOAD_SCHEMA.version;
    if (isReconciliation !== isReconciliationSchema) {
      context.addIssue({
        code: "custom",
        path: ["evidence_kind"],
        message:
          "automated reconciliation evidence must use the C10 versioned payload schema",
      });
    }
    if (!isReconciliation) {
      return;
    }
    if (
      !c10IdentityMatches(
        payload.subject,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.subject,
      )
    ) {
      context.addIssue({
        code: "custom",
        path: ["subject"],
        message: "C10 payload must bind the exact reconciliation subject",
      });
    }
    if (
      !c10IdentityMatches(
        payload.rule,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.rule,
      )
    ) {
      context.addIssue({
        code: "custom",
        path: ["rule"],
        message: "C10 payload must bind the exact reconciliation rule",
      });
    }
    if (
      !c10IdentityMatches(
        payload.provenance.producer,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.producer,
      ) ||
      !c10IdentityMatches(
        payload.provenance.verifier,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.verifier,
      ) ||
      !c10IdentityMatches(
        payload.provenance.command_argv,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.command_argv,
      ) ||
      payload.provenance.predicate_provenance !==
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.predicate_provenance
    ) {
      context.addIssue({
        code: "custom",
        path: ["provenance"],
        message: "C10 payload must use independently reconciled producer and verifier provenance",
      });
    }
    if (!c10DetailsMatch(payload.details, payload.result)) {
      context.addIssue({
        code: "custom",
        path: ["details"],
        message: "C10 payload details must bind the exact reconciliation basis",
      });
    }
  });

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
    const isReconciliation =
      receipt.evidence_kind ===
      ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.evidence_kind;
    const isReconciliationSchema =
      receipt.receipt_schema.version ===
      ATLAS_EVIDENCE_RECONCILIATION_RECEIPT_SCHEMA.version;
    const isReconciliationAuthority =
      receipt.authority.authoritative_for[0] ===
      "atlas_surface_readiness_reconciliation";
    const hasReconciliationPayload =
      receipt.evidence_payload_ref.schema_version ===
      ATLAS_EVIDENCE_RECONCILIATION_PAYLOAD_SCHEMA.version;
    if (
      !(
        isReconciliation === isReconciliationSchema &&
        isReconciliation === isReconciliationAuthority &&
        isReconciliation === hasReconciliationPayload
      )
    ) {
      context.addIssue({
        code: "custom",
        message:
          "receipt schema, authority, evidence kind, and payload schema must form one versioned C07/C10 contract",
      });
    }
    if (!isReconciliation) {
      return;
    }
    if (
      !c10IdentityMatches(
        receipt.authority,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.authority,
      ) ||
      !c10IdentityMatches(
        receipt.subject,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.subject,
      ) ||
      !c10IdentityMatches(
        receipt.rule,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.rule,
      ) ||
      !c10IdentityMatches(
        receipt.provenance.producer,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.producer,
      ) ||
      !c10IdentityMatches(
        receipt.provenance.verifier,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.verifier,
      ) ||
      !c10IdentityMatches(
        receipt.provenance.command_argv,
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.command_argv,
      ) ||
      receipt.provenance.predicate_provenance !==
        ATLAS_SURFACE_READINESS_RECONCILIATION_CONTRACT.predicate_provenance
    ) {
      context.addIssue({
        code: "custom",
        message: "C10 receipt must bind the exact authority, subject, rule, and independent provenance",
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
