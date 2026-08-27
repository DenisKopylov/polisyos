import { z } from "zod";

function isGregorianIsoDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/u.exec(value);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (year < 1 || month < 1 || month > 12 || day < 1) return false;
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [
    31,
    leapYear ? 29 : 28,
    31,
    30,
    31,
    30,
    31,
    31,
    30,
    31,
    30,
    31,
  ];
  return day <= daysInMonth[month - 1]!;
}

const isoDateSchema = z.string().refine(isGregorianIsoDate);
const nullableDateSchema = isoDateSchema.nullable();
const nonnegativeIntegerSchema = z.number().int().nonnegative();

export const claimPostureAudienceSchema = z.enum([
  "PUBLIC",
  "REVIEWER",
  "EXPERT",
  "MACHINE",
]);

const claimPostureStateSchema = z.enum(["supported", "planned", "blocked"]);
const sourceClaimStateSchema = z.enum([
  "supported",
  "planned",
  "candidate",
  "blocked",
  "not_established",
]);
const establishmentClassSchema = z.enum([
  "recomputed",
  "independently_reconciled",
  "consumer_asserted",
  "institutionally_supplied",
  "not_established",
]);
const sourceInventoryRoleSchema = z.enum([
  "declares_only",
  "carries_only",
  "consumes_only",
  "declares_and_consumes",
  "substring_collision",
  "ambiguous",
]);
const sourceResolutionSchema = z.enum([
  "resolved",
  "runtime_bound",
  "collision",
  "ambiguous",
]);

const sourceCoordinateSchema = z
  .object({
    path: z.string(),
    symbol: z.string().nullable(),
    line: z.number().int().positive(),
    column: nonnegativeIntegerSchema,
    field_name: z.enum(["authoritative_for", "may_not_use_for"]),
    use_kind: z.enum(["declaration", "carrier", "consumer", "collision"]),
  })
  .strict();

const literalSiteSchema = z
  .object({
    coordinate: sourceCoordinateSchema,
    declaration_form: z.enum(["assignment", "keyword", "dict_key"]),
    wrapper_kind: z.enum([
      "direct",
      "field_default",
      "literal_lambda_factory",
      "dynamic",
    ]),
    values: z.array(z.string()),
    resolution: sourceResolutionSchema,
  })
  .strict();

const admittedSourceMemberSchema = z
  .object({ path: z.string(), content_digest: z.string() })
  .strict();

const roleCountsSchema = z
  .object({
    declares_only: nonnegativeIntegerSchema,
    carries_only: nonnegativeIntegerSchema,
    consumes_only: nonnegativeIntegerSchema,
    declares_and_consumes: nonnegativeIntegerSchema,
    substring_collision: nonnegativeIntegerSchema,
    ambiguous: nonnegativeIntegerSchema,
  })
  .strict();

const sourceDerivationReceiptSchema = z
  .object({
    method: z.enum(["ast", "tokenize"]),
    scanned_python_count: nonnegativeIntegerSchema,
    raw_candidate_count: nonnegativeIntegerSchema,
    exact_field_file_count: nonnegativeIntegerSchema,
    declaring_file_count: nonnegativeIntegerSchema,
    consuming_file_count: nonnegativeIntegerSchema,
    role_counts: roleCountsSchema,
    direct_literal_site_count: nonnegativeIntegerSchema,
    direct_literal_file_count: nonnegativeIntegerSchema,
    direct_literal_subject_count: nonnegativeIntegerSchema,
    direct_empty_site_count: nonnegativeIntegerSchema,
    wrapper_literal_site_count: nonnegativeIntegerSchema,
    wrapper_literal_file_count: nonnegativeIntegerSchema,
    wrapper_literal_subject_count: nonnegativeIntegerSchema,
    may_not_use_for_raw_file_count: nonnegativeIntegerSchema,
    may_not_use_for_literal_site_count: nonnegativeIntegerSchema,
    may_not_use_for_literal_file_count: nonnegativeIntegerSchema,
    may_not_use_for_literal_subject_count: nonnegativeIntegerSchema,
    row_digest: z.string(),
  })
  .strict()
  .superRefine((receipt, context) => {
    const total = Object.values(receipt.role_counts).reduce(
      (sum, count) => sum + count,
      0,
    );
    if (total !== receipt.raw_candidate_count) {
      context.addIssue({
        code: "custom",
        message: "role_counts must partition raw_candidate_count",
        path: ["role_counts"],
      });
    }
  });

const producerPostureMetadataSchema = z
  .object({
    schema_version: z.literal("policyos.trust.producer_posture.v1"),
    subject: z.string().min(1),
    source_state: z.enum(["candidate", "planned"]),
    owner: z.string().min(1),
    closure_signal: z.string().min(1),
    prerequisite_refs: z.array(z.string()),
    limitation_refs: z.array(z.string()),
    source_symbol: z.string().nullable(),
    line: z.number().int().positive(),
    column: nonnegativeIntegerSchema,
  })
  .strict();

const sourceInventoryRowSchema = z
  .object({
    path: z.string(),
    content_digest: z.string(),
    role: sourceInventoryRoleSchema,
    resolution: sourceResolutionSchema,
    declaration_coordinates: z.array(sourceCoordinateSchema),
    carrier_coordinates: z.array(sourceCoordinateSchema),
    consumer_coordinates: z.array(sourceCoordinateSchema),
    authoritative_sites: z.array(literalSiteSchema),
    forbidden_sites: z.array(literalSiteSchema),
    producer_metadata: z.array(producerPostureMetadataSchema),
    runtime_bound: z.boolean(),
    issue_codes: z.array(z.string()),
  })
  .strict();

const ownerBindingSchema = z
  .object({
    owner: z.string().nullable(),
    basis: z.enum([
      "package_contract",
      "ratified_document",
      "closure_commitment",
      "not_established",
    ]),
    source_ref: z.string().nullable(),
    establishment_class: establishmentClassSchema,
  })
  .strict();

const evidenceBindingSchema = z
  .object({
    ref: z.string(),
    content_digest: z.string(),
    subject_binding: z.string(),
    verifier_ref: z.string(),
    verifier_provenance_ref: z.string(),
    establishment_class: establishmentClassSchema,
    source_as_of: isoDateSchema,
    supersession_ref: z.string().nullable(),
  })
  .strict();

const admittedVerifierSchema = z
  .object({
    ref: z.string(),
    verifier_kind: z.enum([
      "identity_boundary_derivation",
      "accessibility_document_derivation",
      "page_a11y_receipt_derivation",
    ]),
    content_ref: z.string(),
    content_digest: z.string(),
    provenance_ref: z.string(),
    provenance_digest: z.string(),
    subject_scope: z.array(z.string()),
    prohibited_subjects: z.array(z.string()),
    establishment_class: z.enum(["recomputed", "independently_reconciled"]),
  })
  .strict();

const supportPredicateSchema = z
  .object({
    kind: z.enum([
      "content_bound_source",
      "purpose_permission",
      "accountable_owner",
      "applicable_jurisdiction",
      "current_review",
      "content_bound_evidence",
      "identity_boundary",
      "no_blocker",
    ]),
    satisfied: z.boolean(),
    establishment_class: establishmentClassSchema,
    evidence_refs: z.array(z.string()),
    issue_code: z.string().nullable(),
  })
  .strict();

const claimSourceBindingSchema = z
  .object({
    coordinate: sourceCoordinateSchema,
    content_digest: z.string(),
    resolution: sourceResolutionSchema,
    source_state: sourceClaimStateSchema,
    subject: z.string().nullable(),
    family: z.string(),
    authoritative_for: z.array(z.string()),
    may_not_use_for: z.array(z.string()),
    authority_purpose: z.string().nullable(),
    owner: ownerBindingSchema,
    jurisdiction: z.string().nullable(),
    jurisdiction_establishment: establishmentClassSchema,
    review_on: nullableDateSchema,
    review_due: nullableDateSchema,
    source_as_of: nullableDateSchema,
    evidence_refs: z.array(z.string()),
    evidence_bindings: z.array(evidenceBindingSchema),
    limitation_refs: z.array(z.string()),
    prerequisite_refs: z.array(z.string()),
    identity_boundary_ref: z.string(),
    declared_scope_assumption: z.string().nullable(),
    supersedes_ref: z.string().nullable(),
    superseded_by_ref: z.string().nullable(),
    predicates: z.array(supportPredicateSchema),
    closure_signal: z.string().nullable(),
  })
  .strict();

const claimPostureRowSchema = z
  .object({
    claim_id: z.string(),
    subject: z.string().nullable(),
    family: z.string(),
    source_bindings: z.array(claimSourceBindingSchema),
    authoritative_for: z.array(z.string()),
    may_not_use_for: z.array(z.string()),
    accountable_owner: z.string().nullable(),
    owner_basis: z.string(),
    review_on: nullableDateSchema,
    review_due: nullableDateSchema,
    source_as_of: nullableDateSchema,
    audiences: z.array(claimPostureAudienceSchema),
    closure_signal: z.string().nullable(),
    effective_state: claimPostureStateSchema,
    blocker_codes: z.array(z.string()),
    limitations: z.array(z.string()),
  })
  .strict();

const antiRoleBindingSchema = z
  .object({
    role: z.string(),
    display_label: z.string(),
    source_path: z.string(),
    source_digest: z.string(),
    line: z.number().int().positive(),
    column: nonnegativeIntegerSchema,
  })
  .strict();

const identityBoundaryBindingSchema = z
  .object({
    path: z.string(),
    content_digest: z.string(),
    frontmatter_digest: z.string(),
    paragraph_digest: z.string(),
    paragraph_start_line: z.number().int().positive(),
    paragraph_end_line: z.number().int().positive(),
    anti_roles: z.array(antiRoleBindingSchema),
    derivation_receipt_digests: z.tuple([z.string(), z.string()]),
    owner: z.string(),
    last_reviewed: isoDateSchema,
    decision_status: z.string(),
    authoritative_for: z.array(z.string()),
    may_not_use_for: z.array(z.string()),
    identity_statement_digest: z.string(),
    identity_statement_start_line: z.number().int().positive(),
    identity_statement_end_line: z.number().int().positive(),
  })
  .strict();

const documentProjectionPurposeSchema = z
  .object({ purpose: z.string(), basis: z.array(z.string()) })
  .strict();

const resolvedDocumentBindingSchema = z
  .object({
    key: z.string(),
    value: z.string(),
    exact_text_digest: z.string(),
    byte_start: nonnegativeIntegerSchema,
    byte_end: z.number().int().positive(),
    establishment_class: z.literal("recomputed"),
  })
  .strict();

const accessibilityDocumentBindingSchema = z
  .object({
    path: z.string(),
    content_digest: z.string(),
    frontmatter_digest: z.string(),
    body_digest: z.string(),
    source_as_of: isoDateSchema,
    bindings: z.array(resolvedDocumentBindingSchema),
    authoritative_for: z.array(documentProjectionPurposeSchema),
    may_not_use_for: z.array(documentProjectionPurposeSchema),
    limitation_refs: z.array(z.string()),
  })
  .strict();

const pageA11yFailureBindingSchema = z
  .object({
    identity: z.string(),
    test_id: z.string(),
    issue_signature: z.string(),
  })
  .strict();

const pageA11yReceiptBindingSchema = z
  .object({
    path: z.string(),
    content_digest: z.string(),
    admitted_sources: z.array(admittedSourceMemberSchema),
    source_as_of: isoDateSchema,
    collected: nonnegativeIntegerSchema,
    passed: nonnegativeIntegerSchema,
    failed: nonnegativeIntegerSchema,
    skipped: nonnegativeIntegerSchema,
    duration_ms: z.number().nonnegative(),
    exit_code: z.number().int(),
    failures: z.array(pageA11yFailureBindingSchema),
    replay_establishment: establishmentClassSchema,
    limitation_refs: z.array(z.string()),
  })
  .strict();

const projectionGroupSchema = z
  .object({
    group_id: z.enum([
      "methodology",
      "evidence_envelope",
      "limitations",
      "accessibility",
      "custody",
    ]),
    claim_ids: z.array(z.string()),
  })
  .strict();

export const claimPostureRegisterSchema = z
  .object({
    schema_version: z.literal("policyos.trust.claim_posture_register.v1"),
    rule_version: z.literal("policyos.trust.claim_posture_rules.v4"),
    slice_base_ref: z.literal("f935e0c2e9359bc1202ce5d36ea706de58f7aaab"),
    register_as_of: isoDateSchema,
    admitted_sources: z.array(admittedSourceMemberSchema),
    source_set_digest: z.string(),
    ast_derivation: sourceDerivationReceiptSchema,
    token_derivation: sourceDerivationReceiptSchema,
    identity_boundary: identityBoundaryBindingSchema,
    admitted_verifiers: z.array(admittedVerifierSchema),
    accessibility_document: accessibilityDocumentBindingSchema.nullable(),
    page_a11y_receipt: pageA11yReceiptBindingSchema.nullable(),
    source_inventory: z.array(sourceInventoryRowSchema),
    claims: z.array(claimPostureRowSchema),
    projection_groups: z.array(projectionGroupSchema),
    payload_digest: z.string(),
  })
  .strict();

export type ClaimPostureAudience = z.infer<typeof claimPostureAudienceSchema>;
export type ClaimPostureRegister = z.infer<typeof claimPostureRegisterSchema>;
export type ClaimPostureRow = ClaimPostureRegister["claims"][number];
export type ClaimSourceBinding = ClaimPostureRow["source_bindings"][number];

const REQUIRED_SUPPORT_PREDICATES = [
  "content_bound_source",
  "purpose_permission",
  "accountable_owner",
  "applicable_jurisdiction",
  "current_review",
  "content_bound_evidence",
  "identity_boundary",
  "no_blocker",
] as const;

const REQUIRED_PLANNED_PREDICATES = [
  "content_bound_source",
  "purpose_permission",
  "accountable_owner",
  "identity_boundary",
] as const;

const POSITIVE_ESTABLISHMENT_CLASSES = new Set([
  "recomputed",
  "independently_reconciled",
]);

const CLOSED_PROJECTION_GROUPS = [
  "accessibility",
  "custody",
  "evidence_envelope",
  "limitations",
  "methodology",
] as const;

type AdmittedVerifier = ClaimPostureRegister["admitted_verifiers"][number];
type EstablishmentClass = ClaimSourceBinding["jurisdiction_establishment"];
type ProjectionGroup = ClaimPostureRegister["projection_groups"][number];
type SourceInventoryRow = ClaimPostureRegister["source_inventory"][number];

function pythonString(value: string, ensureAscii: boolean): string {
  const encoded = JSON.stringify(value);
  if (!ensureAscii) return encoded;
  return encoded.replace(
    /[\u007f-\uffff]/g,
    (character) =>
      `\\u${character.charCodeAt(0).toString(16).padStart(4, "0")}`,
  );
}

function pythonFloat(value: number): string {
  if (!Number.isFinite(value)) {
    throw new TypeError("non-finite numbers are not canonical JSON");
  }
  if (Object.is(value, -0)) return "-0.0";
  const magnitude = Math.abs(value);
  if (magnitude !== 0 && (magnitude < 1e-4 || magnitude >= 1e16)) {
    const [mantissa, exponent = "0"] = value.toExponential().split("e");
    const sign = exponent.startsWith("-") ? "-" : "+";
    const digits = exponent.replace(/^[+-]/u, "").padStart(2, "0");
    return `${mantissa}e${sign}${digits}`;
  }
  return Number.isInteger(value) ? `${value}.0` : value.toString();
}

function pythonJson(
  value: unknown,
  options: Readonly<{
    ensureAscii: boolean;
    sortKeys: boolean;
    floatField?: string;
  }>,
  fieldName?: string,
): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string")
    return pythonString(value, options.ensureAscii);
  if (typeof value === "number") {
    return fieldName === options.floatField
      ? pythonFloat(value)
      : JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => pythonJson(item, options)).join(",")}]`;
  }
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record);
    if (options.sortKeys) keys.sort();
    return `{${keys
      .map(
        (key) =>
          `${pythonString(key, options.ensureAscii)}:${pythonJson(
            record[key],
            options,
            key,
          )}`,
      )
      .join(",")}}`;
  }
  throw new TypeError("unsupported canonical JSON value");
}

async function sha256(value: string): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) throw new TypeError("Web Crypto digest is unavailable");
  const digest = await subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return `sha256:${[...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")}`;
}

async function sourceSetDigest(
  register: ClaimPostureRegister,
): Promise<string> {
  const members = register.admitted_sources.map((member) => [
    member.path,
    member.content_digest,
  ]);
  return sha256(pythonJson(members, { ensureAscii: false, sortKeys: false }));
}

async function payloadDigest(register: ClaimPostureRegister): Promise<string> {
  const { payload_digest: _payloadDigest, ...payload } = register;
  return sha256(
    pythonJson(payload, {
      ensureAscii: false,
      floatField: "duration_ms",
      sortKeys: true,
    }),
  );
}

function isSortedUnique(values: readonly string[]): boolean {
  return values.every(
    (value, index) =>
      (index === 0 || values[index - 1]! < value) &&
      values.indexOf(value) === index,
  );
}

function sameStrings(
  left: readonly string[],
  right: readonly string[],
): boolean {
  return (
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  );
}

function sameStringSet(
  left: readonly string[],
  right: readonly string[],
): boolean {
  return (
    new Set(left).size === new Set(right).size &&
    [...new Set(left)].every((value) => new Set(right).has(value))
  );
}

function positiveEstablishment(value: EstablishmentClass): boolean {
  return POSITIVE_ESTABLISHMENT_CLASSES.has(value);
}

function validateSourceBinding(binding: ClaimSourceBinding): boolean {
  if (
    binding.resolution === "resolved"
      ? !binding.subject
      : binding.subject !== null
  ) {
    return false;
  }
  if (
    binding.review_on !== null &&
    binding.review_due !== null &&
    binding.review_due < binding.review_on
  ) {
    return false;
  }
  if (
    (binding.supersedes_ref !== null) !==
    (binding.superseded_by_ref !== null)
  ) {
    return false;
  }
  const predicateKinds = binding.predicates.map((predicate) => predicate.kind);
  if (
    !sameStringSet(predicateKinds, REQUIRED_SUPPORT_PREDICATES) ||
    predicateKinds.length !== new Set(predicateKinds).size
  ) {
    return false;
  }
  return sameStringSet(
    binding.evidence_refs,
    binding.evidence_bindings.map((evidence) => evidence.ref),
  );
}

function validateProducerMetadata(row: SourceInventoryRow): boolean {
  const commandPrefixes = [
    "uv run pytest ",
    "pytest ",
    "corepack pnpm ",
    ".venv/bin/python ",
    "python ",
    "pytest://",
  ];
  const keys = new Set<string>();
  for (const metadata of row.producer_metadata) {
    const key = `${metadata.source_symbol ?? "<module>"}\u0000${metadata.subject}`;
    if (keys.has(key)) return false;
    keys.add(key);
    if (
      [metadata.subject, metadata.owner, metadata.closure_signal].some(
        (value) => value !== value.trim() || value.includes("\n"),
      ) ||
      !commandPrefixes.some((prefix) => metadata.closure_signal.startsWith(prefix)) ||
      metadata.prerequisite_refs.length !==
        new Set(metadata.prerequisite_refs).size ||
      metadata.limitation_refs.length !== new Set(metadata.limitation_refs).size ||
      [...metadata.prerequisite_refs, ...metadata.limitation_refs].some(
        (value) => value.trim().length === 0,
      ) ||
      !row.authoritative_sites.some(
        (site) =>
          site.resolution === "resolved" &&
          site.coordinate.symbol === metadata.source_symbol &&
          site.values.includes(metadata.subject),
      )
    ) {
      return false;
    }
  }
  return true;
}

async function admittedVerifier(
  values: Readonly<{
    ref: string;
    verifierKind: AdmittedVerifier["verifier_kind"];
    contentRef: string;
    contentDigest: string;
    provenanceParts: readonly string[];
    subjectScope: readonly string[];
    prohibitedSubjects: readonly string[];
    establishmentClass: AdmittedVerifier["establishment_class"];
  }>,
): Promise<AdmittedVerifier> {
  const provenanceDigest = await sha256(
    pythonJson(values.provenanceParts, {
      ensureAscii: true,
      sortKeys: false,
    }),
  );
  return {
    ref: values.ref,
    verifier_kind: values.verifierKind,
    content_ref: values.contentRef,
    content_digest: values.contentDigest,
    provenance_ref: `provenance:${values.verifierKind}:${provenanceDigest}`,
    provenance_digest: provenanceDigest,
    subject_scope: [...values.subjectScope],
    prohibited_subjects: [...values.prohibitedSubjects],
    establishment_class: values.establishmentClass,
  };
}

async function deriveAdmittedVerifiers(
  register: ClaimPostureRegister,
): Promise<AdmittedVerifier[]> {
  const identity = register.identity_boundary;
  const values: AdmittedVerifier[] = [
    await admittedVerifier({
      ref: "verifier:identity-boundary:dual-derivation",
      verifierKind: "identity_boundary_derivation",
      contentRef: identity.path,
      contentDigest: identity.content_digest,
      provenanceParts: [
        identity.frontmatter_digest,
        identity.identity_statement_digest,
        identity.paragraph_digest,
        ...identity.derivation_receipt_digests,
      ],
      subjectScope: ["system_identity"],
      prohibitedSubjects: [
        "current_accessibility_conformance",
        "external_accessibility_certification",
        "grounded_performance",
        "historical_internal_accessibility_pre_audit",
        "universal_custody_commitment",
      ],
      establishmentClass: "independently_reconciled",
    }),
  ];
  const accessibility = register.accessibility_document;
  if (accessibility !== null) {
    values.push(
      await admittedVerifier({
        ref: "verifier:accessibility-document:selector-resolution",
        verifierKind: "accessibility_document_derivation",
        contentRef: accessibility.path,
        contentDigest: accessibility.content_digest,
        provenanceParts: [
          accessibility.frontmatter_digest,
          accessibility.body_digest,
          ...accessibility.bindings.map((binding) => binding.exact_text_digest),
        ],
        subjectScope: ["historical_internal_accessibility_pre_audit"],
        prohibitedSubjects: [
          "current_accessibility_conformance",
          "external_accessibility_certification",
          "grounded_performance",
          "system_identity",
          "universal_custody_commitment",
        ],
        establishmentClass: "recomputed",
      }),
    );
  }
  const pageReceipt = register.page_a11y_receipt;
  if (pageReceipt !== null) {
    values.push(
      await admittedVerifier({
        ref: "verifier:page-a11y-receipt:raw-recomputation",
        verifierKind: "page_a11y_receipt_derivation",
        contentRef: `${pageReceipt.path}/receipt.json`,
        contentDigest: pageReceipt.content_digest,
        provenanceParts: pageReceipt.admitted_sources.map(
          (member) => member.content_digest,
        ),
        subjectScope: ["historical_page_accessibility_result"],
        prohibitedSubjects: [
          "current_accessibility_conformance",
          "external_accessibility_certification",
          "grounded_performance",
          "system_identity",
          "universal_custody_commitment",
        ],
        establishmentClass: "recomputed",
      }),
    );
  }
  return values.sort((left, right) =>
    left.ref < right.ref ? -1 : left.ref > right.ref ? 1 : 0,
  );
}

function sameVerifier(
  left: AdmittedVerifier,
  right: AdmittedVerifier,
): boolean {
  return (
    left.ref === right.ref &&
    left.verifier_kind === right.verifier_kind &&
    left.content_ref === right.content_ref &&
    left.content_digest === right.content_digest &&
    left.provenance_ref === right.provenance_ref &&
    left.provenance_digest === right.provenance_digest &&
    sameStrings(left.subject_scope, right.subject_scope) &&
    sameStrings(left.prohibited_subjects, right.prohibited_subjects) &&
    left.establishment_class === right.establishment_class
  );
}

function bindingFacts(
  binding: ClaimSourceBinding,
  register: ClaimPostureRegister,
): Readonly<
  Record<
    (typeof REQUIRED_SUPPORT_PREDICATES)[number],
    readonly [boolean, string]
  >
> {
  const admitted = new Map(
    register.admitted_sources.map((member) => [
      member.path,
      member.content_digest,
    ]),
  );
  const verifiers = new Map(
    register.admitted_verifiers.map((verifier) => [verifier.ref, verifier]),
  );
  const evidenceValid =
    binding.evidence_bindings.length > 0 &&
    binding.evidence_bindings.every((evidence) => {
      const verifier = verifiers.get(evidence.verifier_ref);
      return (
        binding.evidence_refs.includes(evidence.ref) &&
        binding.subject !== null &&
        evidence.subject_binding === binding.subject &&
        admitted.get(evidence.ref) === evidence.content_digest &&
        verifier !== undefined &&
        verifier.content_ref === evidence.ref &&
        verifier.content_digest === evidence.content_digest &&
        verifier.provenance_ref === evidence.verifier_provenance_ref &&
        verifier.subject_scope.includes(binding.subject) &&
        !verifier.prohibited_subjects.includes(binding.subject) &&
        positiveEstablishment(verifier.establishment_class) &&
        positiveEstablishment(evidence.establishment_class) &&
        evidence.source_as_of <= register.register_as_of &&
        evidence.supersession_ref === null
      );
    });
  const identity = register.identity_boundary;
  const identityValid =
    binding.identity_boundary_ref === identity.path &&
    admitted.get(identity.path) === identity.content_digest;
  return {
    content_bound_source: [
      admitted.get(binding.coordinate.path) === binding.content_digest &&
        binding.resolution === "resolved",
      "DS11-SOURCE-CONTENT-NOT-BOUND",
    ],
    purpose_permission: [
      binding.subject !== null &&
        binding.authority_purpose !== null &&
        binding.authoritative_for.includes(binding.authority_purpose) &&
        !binding.may_not_use_for.includes(binding.authority_purpose),
      "DS11-AUTHORITY-PURPOSE-DENIED",
    ],
    accountable_owner: [
      Boolean(binding.owner.owner) &&
        Boolean(binding.owner.source_ref) &&
        positiveEstablishment(binding.owner.establishment_class),
      "DS11-OWNER-NOT-ESTABLISHED",
    ],
    applicable_jurisdiction: [
      Boolean(binding.jurisdiction) &&
        positiveEstablishment(binding.jurisdiction_establishment),
      "DS11-JURISDICTION-NOT-ESTABLISHED",
    ],
    current_review: [
      binding.review_on !== null &&
        binding.review_due !== null &&
        binding.review_on <= register.register_as_of &&
        register.register_as_of <= binding.review_due,
      "DS11-REVIEW-MISSING-OR-STALE",
    ],
    content_bound_evidence: [
      evidenceValid,
      "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND",
    ],
    identity_boundary: [
      identityValid,
      "DS11-IDENTITY-BOUNDARY-NOT-ESTABLISHED",
    ],
    no_blocker: [
      binding.resolution === "resolved" &&
        binding.source_state === "supported" &&
        binding.declared_scope_assumption === null &&
        binding.superseded_by_ref === null,
      "DS11-SOURCE-BLOCKER-PRESENT",
    ],
  };
}

function composedState(
  bindings: readonly ClaimSourceBinding[],
  family: string,
): ClaimPostureRow["effective_state"] {
  const states = bindings.map((binding) => binding.source_state);
  if (
    states.length === 0 ||
    states.some((state) =>
      ["blocked", "candidate", "not_established"].includes(state),
    )
  ) {
    return "blocked";
  }
  if (states.includes("planned")) {
    return bindings.some((binding) => binding.owner.owner) &&
      bindings.some((binding) => binding.closure_signal)
      ? "planned"
      : "blocked";
  }
  const predicates = bindings[0]?.predicates ?? [];
  const kinds = predicates.map((predicate) => predicate.kind);
  if (
    kinds.length !== new Set(kinds).size ||
    !sameStringSet(kinds, REQUIRED_SUPPORT_PREDICATES) ||
    predicates.some(
      (predicate) =>
        !predicate.satisfied ||
        !positiveEstablishment(predicate.establishment_class),
    ) ||
    family === "grounded_performance"
  ) {
    return "blocked";
  }
  return "supported";
}

function evaluateClaim(
  row: ClaimPostureRow,
  register: ClaimPostureRegister,
): Readonly<{
  state: ClaimPostureRow["effective_state"];
  blockers: string[];
  limitations: string[];
}> {
  const blockers = new Set<string>();
  const limitations = new Set<string>();
  for (const binding of row.source_bindings) {
    if (binding.declared_scope_assumption !== null) {
      limitations.add(
        `Declared scope assumption: ${binding.declared_scope_assumption}`,
      );
      blockers.add("DS11-GATE-PREDICATE-NOT-ESTABLISHED");
    }
    binding.limitation_refs.forEach((limitation) =>
      limitations.add(limitation),
    );
    if (binding.resolution === "runtime_bound") {
      blockers.add("DS11-SOURCE-RUNTIME-BOUND");
    } else if (binding.resolution === "ambiguous") {
      blockers.add("DS11-SOURCE-DERIVATION-DISAGREEMENT");
    }
    if (
      row.subject !== null &&
      (binding.authority_purpose === null ||
        !binding.authoritative_for.includes(binding.authority_purpose) ||
        binding.may_not_use_for.includes(binding.authority_purpose))
    ) {
      blockers.add("DS11-AUTHORITY-PURPOSE-DENIED");
    }
    const predicates = new Map(
      binding.predicates.map((predicate) => [predicate.kind, predicate]),
    );
    if (!sameStringSet([...predicates.keys()], REQUIRED_SUPPORT_PREDICATES)) {
      blockers.add("DS11-GATE-PREDICATE-SET-INCOMPLETE");
    }
    const facts = bindingFacts(binding, register);
    const requiredFacts =
      binding.source_state === "planned"
        ? REQUIRED_PLANNED_PREDICATES
        : REQUIRED_SUPPORT_PREDICATES;
    for (const kind of requiredFacts) {
      const predicate = predicates.get(kind);
      const [fact, issueCode] = facts[kind];
      if (
        predicate === undefined ||
        !predicate.satisfied ||
        !fact ||
        !positiveEstablishment(predicate.establishment_class)
      ) {
        blockers.add(predicate?.issue_code ?? issueCode);
      }
    }
  }
  return {
    state:
      blockers.size > 0
        ? "blocked"
        : composedState(row.source_bindings, row.family),
    blockers: [...blockers].sort(),
    limitations: [...limitations].sort(),
  };
}

function deriveProjectionGroups(
  claims: readonly ClaimPostureRow[],
): ProjectionGroup[] {
  const grouped = new Map<string, Set<string>>(
    CLOSED_PROJECTION_GROUPS.map((groupId) => [groupId, new Set()]),
  );
  for (const row of claims) {
    const primaryGroup =
      row.family === "accessibility"
        ? "accessibility"
        : row.family === "custody"
          ? "custody"
          : row.family === "grounded_performance"
            ? "evidence_envelope"
            : "methodology";
    grouped.get(primaryGroup)!.add(row.claim_id);
    if (
      row.effective_state !== "supported" ||
      row.blocker_codes.length > 0 ||
      row.limitations.length > 0
    ) {
      grouped.get("limitations")!.add(row.claim_id);
    }
  }
  return CLOSED_PROJECTION_GROUPS.map((groupId) => ({
    group_id: groupId,
    claim_ids: [...grouped.get(groupId)!].sort(),
  }));
}

function sameProjectionGroups(
  left: readonly ProjectionGroup[],
  right: readonly ProjectionGroup[],
): boolean {
  return (
    left.length === right.length &&
    left.every(
      (group, index) =>
        group.group_id === right[index]?.group_id &&
        sameStrings(group.claim_ids, right[index]?.claim_ids ?? []),
    )
  );
}

/** Replay every canonical v4 root invariant after structural parsing. */
export async function validateClaimPostureRegisterSemantics(
  register: ClaimPostureRegister,
): Promise<boolean> {
  try {
    const admittedPaths = register.admitted_sources.map(
      (member) => member.path,
    );
    const inventoryPaths = register.source_inventory.map((row) => row.path);
    const claimIds = register.claims.map((row) => row.claim_id);
    if (
      !isSortedUnique(admittedPaths) ||
      !isSortedUnique(inventoryPaths) ||
      !isSortedUnique(claimIds) ||
      !sameStrings(
        register.projection_groups.map((group) => group.group_id),
        CLOSED_PROJECTION_GROUPS,
      )
    ) {
      return false;
    }
    if (register.source_inventory.some((row) => !validateProducerMetadata(row))) {
      return false;
    }
    if ((await sourceSetDigest(register)) !== register.source_set_digest) {
      return false;
    }
    const admitted = new Map(
      register.admitted_sources.map((member) => [
        member.path,
        member.content_digest,
      ]),
    );
    if (
      admitted.get(register.identity_boundary.path) !==
      register.identity_boundary.content_digest
    ) {
      return false;
    }
    const expectedVerifiers = await deriveAdmittedVerifiers(register);
    if (
      register.admitted_verifiers.length !== expectedVerifiers.length ||
      register.admitted_verifiers.some(
        (verifier, index) => !sameVerifier(verifier, expectedVerifiers[index]!),
      ) ||
      register.admitted_verifiers.some(
        (verifier) =>
          admitted.get(verifier.content_ref) !== verifier.content_digest,
      )
    ) {
      return false;
    }
    for (const row of register.claims) {
      if (
        row.source_bindings.some((binding) => !validateSourceBinding(binding))
      ) {
        return false;
      }
      const evaluated = evaluateClaim(row, register);
      if (
        row.effective_state !== evaluated.state ||
        !sameStrings(row.blocker_codes, evaluated.blockers) ||
        !sameStrings(row.limitations, evaluated.limitations)
      ) {
        return false;
      }
    }
    if (
      !sameProjectionGroups(
        register.projection_groups,
        deriveProjectionGroups(register.claims),
      )
    ) {
      return false;
    }
    return (await payloadDigest(register)) === register.payload_digest;
  } catch {
    return false;
  }
}

/** Structurally and semantically admit one untrusted posture candidate. */
export async function admitClaimPostureRegister(
  candidate: unknown,
): Promise<ClaimPostureRegister | null> {
  const parsed = claimPostureRegisterSchema.safeParse(candidate);
  if (!parsed.success) return null;
  return (await validateClaimPostureRegisterSemantics(parsed.data))
    ? parsed.data
    : null;
}
