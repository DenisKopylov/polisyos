import { z } from "zod";

const isoDateSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}$/u);
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
    establishment_class: z.enum([
      "recomputed",
      "independently_reconciled",
    ]),
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
    rule_version: z.literal("policyos.trust.claim_posture_rules.v3"),
    slice_base_ref: z.literal(
      "f935e0c2e9359bc1202ce5d36ea706de58f7aaab",
    ),
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

export type ClaimPostureAudience = z.infer<
  typeof claimPostureAudienceSchema
>;
export type ClaimPostureRegister = z.infer<typeof claimPostureRegisterSchema>;
export type ClaimPostureRow = ClaimPostureRegister["claims"][number];
export type ClaimSourceBinding = ClaimPostureRow["source_bindings"][number];
