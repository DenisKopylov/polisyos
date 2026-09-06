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
    may_not_use_for_raw_members: z.array(admittedSourceMemberSchema),
    may_not_use_for_sites: z.array(literalSiteSchema),
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
    const rawPaths = receipt.may_not_use_for_raw_members.map(
      (member) => member.path,
    );
    const literalPaths = new Set(
      receipt.may_not_use_for_sites.map((site) => site.coordinate.path),
    );
    const literalSubjects = new Set(
      receipt.may_not_use_for_sites.flatMap((site) => site.values),
    );
    if (
      !isSortedUnique(rawPaths) ||
      receipt.may_not_use_for_raw_file_count !== rawPaths.length ||
      receipt.may_not_use_for_sites.some(
        (site) => !rawPaths.includes(site.coordinate.path),
      ) ||
      receipt.may_not_use_for_literal_site_count !==
        receipt.may_not_use_for_sites.length ||
      receipt.may_not_use_for_literal_file_count !== literalPaths.size ||
      receipt.may_not_use_for_literal_subject_count !== literalSubjects.size
    ) {
      context.addIssue({
        code: "custom",
        message: "may_not_use_for counts must bind carried members and sites",
        path: ["may_not_use_for_sites"],
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
    identity_statement: z.string().min(1),
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
    exact_text: z.string(),
    exact_text_digest: z.string(),
    byte_start: nonnegativeIntegerSchema,
    byte_end: z.number().int().positive(),
    establishment_class: z.literal("recomputed"),
  })
  .strict();

const accessibilityDocumentBindingSchema = z
  .object({
    path: z.string(),
    source_content: z.string(),
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

const custodyAppointmentSourceSchema = z
  .object({
    path: z.literal("docs/plans/active/DEBT-REGISTER.md"),
    debt_id: z.string(),
    status: z.enum(["open", "blocked", "closed"]),
    source_content: z.string(),
    content_digest: z.string(),
  })
  .strict();

const pageA11yReceiptBindingSchema = z
  .object({
    schema_version: z.literal("policyos.ds11.page_a11y_base_receipt.v1"),
    authority_purpose: z.literal("historical_currentness_limitation"),
    status: z.literal("blocked"),
    execution_entry_commit: z.literal(
      "8e5832bbdb0f206b6221112f4a1502b45981bd40",
    ),
    policy_source_base_commit: z.literal(
      "f935e0c2e9359bc1202ce5d36ea706de58f7aaab",
    ),
    command: z.literal(
      "PLAYWRIGHT_JSON_OUTPUT_FILE=<receipt-relative-output> corepack pnpm --filter @polisyos/runtime-dashboard exec playwright test e2e/a11y --project=chromium --reporter=json",
    ),
    path: z.string(),
    source_contents: z.record(z.string(), z.string()),
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

const machineAdmissionBoundarySchema = z
  .object({
    authority_purpose: z.literal(
      "committed_derivation_projection_reconstruction",
    ),
    live_repository_freshness: z.literal("not_established"),
    owner: z.literal("team-architecture"),
    closure_signal: z.literal(
      ".venv/bin/python tools/quality/validation/check_trust_claim_posture.py --repo-root . --check",
    ),
    limitation_refs: z.tuple([
      z.literal(
        "MACHINE reconstructs the committed derivation projection; it does not independently establish live repository freshness.",
      ),
    ]),
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
    may_not_use_for_denied_only_sites: z.array(literalSiteSchema),
    identity_boundary: identityBoundaryBindingSchema,
    custody_appointment_sources: z.array(custodyAppointmentSourceSchema),
    admitted_verifiers: z.array(admittedVerifierSchema),
    accessibility_document: accessibilityDocumentBindingSchema.nullable(),
    page_a11y_receipt: pageA11yReceiptBindingSchema.nullable(),
    source_inventory: z.array(sourceInventoryRowSchema),
    claims: z.array(claimPostureRowSchema),
    projection_groups: z.array(projectionGroupSchema),
    machine_admission_boundary: machineAdmissionBoundarySchema,
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

const EXECUTABLE_CLOSURE_PREFIXES = [
  "uv run pytest ",
  "pytest ",
  "corepack pnpm ",
  ".venv/bin/python ",
  "python ",
  "pytest://",
] as const;

const CLOSED_PROJECTION_GROUPS = [
  "accessibility",
  "custody",
  "evidence_envelope",
  "limitations",
  "methodology",
] as const;

const RATIFIED_IDENTITY_PATH =
  "docs/system-design-decisions/policyos-identity-and-custody-boundary.md";
const RATIFIED_IDENTITY_CONTENT_DIGEST =
  "sha256:9a660772c5a5ce863165cd0da48880438190fa95ad3a651312a56dc6c19b1a2d";
const RATIFIED_IDENTITY_BASIS_DIGEST =
  "sha256:89a888e3ed7ac47b3572b84bafb231354de7926275c43b2fe25a00e15b202d99";
const CUSTODY_APPOINTMENT_SOURCE_PATH = "docs/plans/active/DEBT-REGISTER.md";
const CUSTODY_APPOINTMENT_DEBT_IDS = [
  "DS11-CLAIM-LIFECYCLE-ORCHESTRATION",
  "DS11-PUBLIC-SIGNATURE-POPULATION",
  "DS11-PUBLISHED-SIGNATURE-WATCHER",
] as const;
const CUSTODY_APPOINTMENT_CONTRACT = new Map<string, readonly [string, string]>(
  [
    [
      "DS11-CLAIM-LIFECYCLE-ORCHESTRATION",
      [
        "team-scientist",
        "uv run pytest tests/integration/scientist/governance/test_claim_lifecycle_orchestration.py::test_monitor_event_persists_claim_supersession_without_in_place_edit -q",
      ],
    ],
    [
      "DS11-PUBLIC-SIGNATURE-POPULATION",
      [
        "team-design",
        "uv run pytest tests/unit/runtime/http/test_public_export.py::test_first_governed_public_signature_is_custody_bound -q",
      ],
    ],
    [
      "DS11-PUBLISHED-SIGNATURE-WATCHER",
      [
        "team-runtime",
        "uv run pytest tests/integration/runtime_quality/test_published_signature_custody.py::test_every_public_signature_is_watched_for_staleness -q",
      ],
    ],
  ],
);
const FIXED_SEMANTIC_BINDING_COUNTS = new Map<string, number>([
  ["current_accessibility_conformance", 1],
  ["external_accessibility_certification", 1],
  ["grounded_performance", 1],
  ["historical_internal_accessibility_pre_audit", 1],
  ["system_identity", 1],
  ["universal_custody_commitment", 3],
]);

type AdmittedVerifier = ClaimPostureRegister["admitted_verifiers"][number];
type EstablishmentClass = ClaimSourceBinding["jurisdiction_establishment"];
type ProjectionGroup = ClaimPostureRegister["projection_groups"][number];
type SourceInventoryRow = ClaimPostureRegister["source_inventory"][number];
type SourceCoordinate = ClaimSourceBinding["coordinate"];
type OwnerBinding = ClaimSourceBinding["owner"];
type ProducerPostureMetadata = SourceInventoryRow["producer_metadata"][number];
type SupportPredicate = ClaimSourceBinding["predicates"][number];
type EvidenceBinding = ClaimSourceBinding["evidence_bindings"][number];

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
  return sha256Bytes(new TextEncoder().encode(value));
}

async function sha256Bytes(value: Uint8Array): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) throw new TypeError("Web Crypto digest is unavailable");
  const bytes = new Uint8Array(value.byteLength);
  bytes.set(value);
  const digest = await subtle.digest("SHA-256", bytes.buffer);
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

function byteMatchOffsets(haystack: Uint8Array, needle: Uint8Array): number[] {
  if (needle.length === 0) return [];
  const offsets: number[] = [];
  for (let start = 0; start <= haystack.length - needle.length; start += 1) {
    let matches = true;
    for (let index = 0; index < needle.length; index += 1) {
      if (haystack[start + index] !== needle[index]) {
        matches = false;
        break;
      }
    }
    if (matches) offsets.push(start);
  }
  return offsets;
}

type ProjectionPurpose = NonNullable<
  ClaimPostureRegister["accessibility_document"]
>["authoritative_for"][number];

function parseProjectionPurposes(
  lines: readonly string[],
): ProjectionPurpose[] {
  const purposes: ProjectionPurpose[] = [];
  for (let index = 0; index < lines.length; index += 2) {
    const purpose = /^    - purpose: ([a-z0-9_]+)$/u.exec(lines[index] ?? "");
    const basis = /^      basis: \[([a-z0-9_, ]+)\]$/u.exec(
      lines[index + 1] ?? "",
    );
    if (!purpose?.[1] || !basis?.[1]) {
      throw new TypeError("projection purpose frontmatter is malformed");
    }
    const basisValues = basis[1].split(",").map((value) => value.trim());
    if (
      basisValues.some((value) => value.length === 0) ||
      new Set(basisValues).size !== basisValues.length
    ) {
      throw new TypeError("projection purpose basis is malformed");
    }
    purposes.push({ purpose: purpose[1], basis: basisValues });
  }
  return purposes;
}

function parseProjectionIndex(frontmatter: string): {
  bodySha256: string;
  bindings: Map<
    string,
    { value: string; exactText: string; occurrence: number }
  >;
  allowedPurposes: ProjectionPurpose[];
  deniedPurposes: ProjectionPurpose[];
} {
  const lines = frontmatter.split("\n");
  const body = /^  body_sha256: ([0-9a-f]{64})$/u.exec(lines[2] ?? "");
  const allowedStart = lines.indexOf("  authoritative_for:");
  const deniedStart = lines.indexOf("  may_not_use_for:");
  if (
    lines[0] !== "ds11_projection_index:" ||
    lines[1] !==
      "  schema_version: policyos.trust.document_projection_index.v1" ||
    !body?.[1] ||
    lines[3] !== "  bindings:" ||
    allowedStart <= 4 ||
    deniedStart <= allowedStart + 1 ||
    deniedStart >= lines.length - 1
  ) {
    throw new TypeError("projection index frontmatter is malformed");
  }
  const bindingLines = lines.slice(4, allowedStart);
  if (bindingLines.length === 0 || bindingLines.length % 4 !== 0) {
    throw new TypeError("projection binding frontmatter is malformed");
  }
  const bindings = new Map<
    string,
    { value: string; exactText: string; occurrence: number }
  >();
  for (let index = 0; index < bindingLines.length; index += 4) {
    const key = /^    ([a-z0-9_]+):$/u.exec(bindingLines[index] ?? "")?.[1];
    const valueText = /^      value: (.+)$/u.exec(
      bindingLines[index + 1] ?? "",
    )?.[1];
    const exactText = /^      exact_text: (.+)$/u.exec(
      bindingLines[index + 2] ?? "",
    )?.[1];
    const occurrence = /^      occurrence: ([0-9]+)$/u.exec(
      bindingLines[index + 3] ?? "",
    )?.[1];
    const value = valueText === undefined ? null : JSON.parse(valueText);
    const exact = exactText === undefined ? null : JSON.parse(exactText);
    if (
      !key ||
      typeof value !== "string" ||
      typeof exact !== "string" ||
      occurrence !== "1" ||
      bindings.has(key)
    ) {
      throw new TypeError("projection binding frontmatter is malformed");
    }
    bindings.set(key, { value, exactText: exact, occurrence: 1 });
  }
  return {
    bodySha256: body[1],
    bindings,
    allowedPurposes: parseProjectionPurposes(
      lines.slice(allowedStart + 1, deniedStart),
    ),
    deniedPurposes: parseProjectionPurposes(lines.slice(deniedStart + 1)),
  };
}

async function validateAccessibilityDocument(
  accessibility: NonNullable<ClaimPostureRegister["accessibility_document"]>,
): Promise<boolean> {
  const encoder = new TextEncoder();
  if (
    (await sha256(accessibility.source_content)) !==
      accessibility.content_digest ||
    !accessibility.source_content.startsWith("---\n")
  ) {
    return false;
  }
  const frontmatterEnd = accessibility.source_content.indexOf("\n---\n", 4);
  if (frontmatterEnd < 0) return false;
  const frontmatter = accessibility.source_content.slice(4, frontmatterEnd);
  const body = accessibility.source_content.slice(frontmatterEnd + 5);
  const bodyBytes = encoder.encode(body);
  if (
    (await sha256(frontmatter)) !== accessibility.frontmatter_digest ||
    (await sha256Bytes(bodyBytes)) !== accessibility.body_digest
  ) {
    return false;
  }
  const index = parseProjectionIndex(frontmatter);
  if (
    `sha256:${index.bodySha256}` !== accessibility.body_digest ||
    !sameCanonical(index.allowedPurposes, accessibility.authoritative_for) ||
    !sameCanonical(index.deniedPurposes, accessibility.may_not_use_for)
  ) {
    return false;
  }
  const keys = accessibility.bindings.map((binding) => binding.key);
  if (
    !isSortedUnique(keys) ||
    !sameStrings([...index.bindings.keys()].sort(compareText), keys)
  ) {
    return false;
  }
  for (const binding of accessibility.bindings) {
    const selector = index.bindings.get(binding.key);
    const exact = encoder.encode(binding.exact_text);
    const offsets = byteMatchOffsets(bodyBytes, exact);
    if (
      selector === undefined ||
      binding.value !== selector.value ||
      binding.exact_text !== selector.exactText ||
      selector.occurrence !== 1 ||
      offsets.length !== 1 ||
      offsets[0] !== binding.byte_start ||
      binding.byte_end !== binding.byte_start + exact.length ||
      !binding.exact_text.includes(binding.value) ||
      (await sha256Bytes(exact)) !== binding.exact_text_digest
    ) {
      return false;
    }
  }
  const required = new Set(
    [
      ...accessibility.authoritative_for,
      ...accessibility.may_not_use_for,
    ].flatMap((purpose) => purpose.basis),
  );
  const sourceAsOf = accessibility.bindings.find(
    (binding) => binding.key === "source_as_of",
  )?.value;
  const limitation = "It does not replace the planned third-party countersign.";
  const occurrences = body
    .split(/\n[ \t]*\n/u)
    .reduce(
      (count, paragraph) =>
        count + paragraph.split(/\s+/u).join(" ").split(limitation).length - 1,
      0,
    );
  return (
    required.size > 0 &&
    [...required].every((key) => keys.includes(key)) &&
    sourceAsOf === accessibility.source_as_of &&
    sameStrings(accessibility.limitation_refs, [limitation]) &&
    occurrences === 1
  );
}

function objectValue(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("expected object");
  }
  return value as Record<string, unknown>;
}

function arrayValue(value: unknown): unknown[] {
  if (!Array.isArray(value)) throw new TypeError("expected array");
  return value;
}

function pageIssueSignature(message: string): string {
  const plain = message.replace(/\u001b\[[0-9;]*m/gu, "");
  const axe = /"id"\s*:\s*"([^"]+)"/u.exec(plain);
  if (axe?.[1]) return `axe:${axe[1]}`;
  const expected =
    /Expected substring:\s*"(?:link|button) \\"([^"\\]+)\\""/u.exec(plain);
  if (expected?.[1]) return `accessible_name:${expected[1]}`;
  throw new TypeError("page-a11y failure has no semantic issue signature");
}

type PageFailure = NonNullable<
  ClaimPostureRegister["page_a11y_receipt"]
>["failures"][number];

function derivePageResultRows(suitesValue: unknown): {
  identities: Array<[string, string]>;
  failures: PageFailure[];
} {
  const identities: Array<[string, string]> = [];
  const failures: PageFailure[] = [];
  for (const suiteValue of arrayValue(suitesValue)) {
    const suite = objectValue(suiteValue);
    for (const specValue of arrayValue(suite.specs ?? [])) {
      const spec = objectValue(specValue);
      const identity = `${String(spec.file)}::${String(spec.title)}`;
      for (const testValue of arrayValue(spec.tests ?? [])) {
        const test = objectValue(testValue);
        const rawStatus = String(test.status);
        const status =
          rawStatus === "expected"
            ? "passed"
            : rawStatus === "skipped"
              ? "skipped"
              : "failed";
        identities.push([identity, status]);
        if (status === "failed") {
          const message = arrayValue(test.results ?? [])
            .map((resultValue) => {
              const result = objectValue(resultValue);
              const error = objectValue(result.error ?? {});
              return String(error.message ?? "");
            })
            .join(" ");
          failures.push({
            identity,
            test_id: String(spec.id),
            issue_signature: pageIssueSignature(message),
          });
        }
      }
    }
    const nested = derivePageResultRows(suite.suites ?? []);
    identities.push(...nested.identities);
    failures.push(...nested.failures);
  }
  return { identities, failures };
}

async function validatePageA11yReceipt(
  receipt: NonNullable<ClaimPostureRegister["page_a11y_receipt"]>,
): Promise<boolean> {
  const expectedRoot =
    "docs/plans/active/atlas-slices/receipts/ds11-page-a11y-base";
  const names = [
    "environment-after.json",
    "environment-before.json",
    "receipt.json",
    "run-1/.last-run.json",
    "run-1/results.json",
  ];
  const paths = names.map((name) => `${expectedRoot}/${name}`);
  if (
    receipt.path !== expectedRoot ||
    !sameStrings(Object.keys(receipt.source_contents).sort(compareText), paths)
  ) {
    return false;
  }
  const derivedSources = await Promise.all(
    paths.map(async (path) => ({
      path,
      content_digest: await sha256(receipt.source_contents[path]!),
    })),
  );
  if (
    !sameCanonical(receipt.admitted_sources, derivedSources) ||
    receipt.content_digest !== derivedSources[2]!.content_digest
  ) {
    return false;
  }
  const source = (name: string): string =>
    receipt.source_contents[`${expectedRoot}/${name}`]!;
  const normalized = objectValue(JSON.parse(source("receipt.json")));
  const results = objectValue(JSON.parse(source("run-1/results.json")));
  const lastRun = objectValue(JSON.parse(source("run-1/.last-run.json")));
  for (const environmentName of [
    "environment-before.json",
    "environment-after.json",
  ]) {
    const environment = objectValue(JSON.parse(source(environmentName)));
    if (
      !["captured_at", "node", "platform", "arch", "cwd"].every((key) =>
        Object.hasOwn(environment, key),
      )
    ) {
      return false;
    }
  }
  const metadata = {
    schema_version: receipt.schema_version,
    authority_purpose: receipt.authority_purpose,
    status: receipt.status,
    execution_entry_commit: receipt.execution_entry_commit,
    policy_source_base_commit: receipt.policy_source_base_commit,
    command: receipt.command,
  };
  if (
    !Object.entries(metadata).every(([key, value]) => normalized[key] === value)
  ) {
    return false;
  }
  const derived = derivePageResultRows(results.suites ?? []);
  const stats = objectValue(results.stats ?? {});
  const observed = {
    collected: derived.identities.length,
    passed: derived.identities.filter(([, status]) => status === "passed")
      .length,
    failed: derived.identities.filter(([, status]) => status === "failed")
      .length,
    skipped: derived.identities.filter(([, status]) => status === "skipped")
      .length,
    duration_ms: stats.duration,
    exit_code: derived.failures.length > 0 ? 1 : 0,
  };
  const authoredIdentities = arrayValue(
    normalized.collected_identities ?? [],
  ).map((itemValue): [string, string] => {
    const item = objectValue(itemValue);
    return [String(item.identity), String(item.status)];
  });
  const authoredFailures = arrayValue(
    normalized.inherited_failure_identities ?? [],
  ).map((itemValue): [string, string] => {
    const item = objectValue(itemValue);
    return [String(item.identity), String(item.status)];
  });
  if (
    !sameCanonical(normalized.result, observed) ||
    !sameCanonical(authoredIdentities, derived.identities) ||
    !sameCanonical(
      authoredFailures,
      derived.failures.map((failure): [string, string] => [
        failure.identity,
        "failed",
      ]),
    )
  ) {
    return false;
  }
  const rawReceipts = objectValue(normalized.raw_receipts ?? {});
  if (
    rawReceipts.results_sha256 !==
      (await sha256(source("run-1/results.json"))).slice("sha256:".length) ||
    rawReceipts.last_run_sha256 !==
      (await sha256(source("run-1/.last-run.json"))).slice("sha256:".length)
  ) {
    return false;
  }
  const failureIds = new Set(
    derived.failures.map((failure) => failure.test_id),
  );
  if (
    lastRun.status !== "failed" ||
    !sameStrings(
      [...new Set(arrayValue(lastRun.failedTests ?? []).map(String))].sort(
        compareText,
      ),
      [...failureIds].sort(compareText),
    )
  ) {
    return false;
  }
  const replay = objectValue(normalized.replay_agreement ?? {});
  return (
    replay.admissibility === "not_established" &&
    replay.committed_raw_runs === 1 &&
    receipt.source_as_of === String(stats.startTime).slice(0, 10) &&
    receipt.collected === observed.collected &&
    receipt.passed === observed.passed &&
    receipt.failed === observed.failed &&
    receipt.skipped === observed.skipped &&
    receipt.duration_ms === observed.duration_ms &&
    receipt.exit_code === observed.exit_code &&
    sameCanonical(receipt.failures, derived.failures) &&
    receipt.replay_establishment === "not_established" &&
    sameStrings(receipt.limitation_refs, [String(replay.limitation)])
  );
}

async function validateDerivationReceipts(
  register: ClaimPostureRegister,
): Promise<boolean> {
  const ast = register.ast_derivation;
  const token = register.token_derivation;
  const { method: _astMethod, ...astReceipt } = ast;
  const { method: _tokenMethod, ...tokenReceipt } = token;
  const {
    row_digest: _astRowDigest,
    may_not_use_for_sites: astDeniedSites,
    ...astSharedReceipt
  } = astReceipt;
  const {
    row_digest: _tokenRowDigest,
    may_not_use_for_sites: tokenDeniedSites,
    ...tokenSharedReceipt
  } = tokenReceipt;
  const admitted = new Map(
    register.admitted_sources.map((member) => [
      member.path,
      member.content_digest,
    ]),
  );
  if (
    ast.method !== "ast" ||
    token.method !== "tokenize" ||
    !sameCanonical(astSharedReceipt, tokenSharedReceipt) ||
    !sameCanonical(astDeniedSites, tokenDeniedSites) ||
    [ast, token].some((receipt) =>
      receipt.may_not_use_for_raw_members.some(
        (member) => admitted.get(member.path) !== member.content_digest,
      ),
    )
  ) {
    return false;
  }
  const inventory = register.source_inventory;
  const roles = [
    "declares_only",
    "carries_only",
    "consumes_only",
    "declares_and_consumes",
    "substring_collision",
    "ambiguous",
  ] as const;
  const roleCounts = Object.fromEntries(
    roles.map((role) => [
      role,
      inventory.filter((row) => row.role === role).length,
    ]),
  );
  const directSites = inventory.flatMap((row) =>
    row.authoritative_sites.filter(
      (site) =>
        site.declaration_form === "assignment" &&
        site.wrapper_kind === "direct" &&
        site.resolution === "resolved",
    ),
  );
  const wrapperSites = inventory.flatMap((row) =>
    row.authoritative_sites.filter(
      (site) =>
        site.declaration_form === "assignment" &&
        site.wrapper_kind !== "dynamic" &&
        site.resolution === "resolved",
    ),
  );
  const inventoryDeniedSites = inventory.flatMap((row) =>
    row.forbidden_sites.filter(
      (site) =>
        site.declaration_form === "assignment" &&
        site.wrapper_kind !== "dynamic" &&
        site.resolution === "resolved",
    ),
  );
  const inventoryPaths = new Set(inventory.map((row) => row.path));
  if (
    register.may_not_use_for_denied_only_sites.some((site) =>
      inventoryPaths.has(site.coordinate.path),
    )
  ) {
    return false;
  }
  const canonicalDeniedSites = [
    ...inventoryDeniedSites,
    ...register.may_not_use_for_denied_only_sites,
  ];
  const rawPaths = new Set(
    ast.may_not_use_for_raw_members.map((member) => member.path),
  );
  if (
    !sameCanonical(astDeniedSites, canonicalDeniedSites) ||
    canonicalDeniedSites.some((site) => !rawPaths.has(site.coordinate.path))
  ) {
    return false;
  }
  const expected: Record<string, unknown> = {
    scanned_python_count: register.admitted_sources.filter(
      (member) => member.path.startsWith("src/") && member.path.endsWith(".py"),
    ).length,
    raw_candidate_count: inventory.length,
    exact_field_file_count: inventory.filter(
      (row) => !["substring_collision", "ambiguous"].includes(row.role),
    ).length,
    declaring_file_count: inventory.filter((row) =>
      ["declares_only", "declares_and_consumes"].includes(row.role),
    ).length,
    consuming_file_count: inventory.filter((row) =>
      ["consumes_only", "declares_and_consumes"].includes(row.role),
    ).length,
    role_counts: roleCounts,
    direct_literal_site_count: directSites.length,
    direct_literal_file_count: new Set(
      directSites.map((site) => site.coordinate.path),
    ).size,
    direct_literal_subject_count: new Set(
      directSites.flatMap((site) => site.values),
    ).size,
    direct_empty_site_count: directSites.filter(
      (site) => site.values.length === 0,
    ).length,
    wrapper_literal_site_count: wrapperSites.length,
    wrapper_literal_file_count: new Set(
      wrapperSites.map((site) => site.coordinate.path),
    ).size,
    wrapper_literal_subject_count: new Set(
      wrapperSites.flatMap((site) => site.values),
    ).size,
    may_not_use_for_raw_file_count: ast.may_not_use_for_raw_members.length,
    may_not_use_for_literal_site_count: canonicalDeniedSites.length,
    may_not_use_for_literal_file_count: new Set(
      canonicalDeniedSites.map((site) => site.coordinate.path),
    ).size,
    may_not_use_for_literal_subject_count: new Set(
      canonicalDeniedSites.flatMap((site) => site.values),
    ).size,
    row_digest: await sha256(
      pythonJson(inventory, { ensureAscii: false, sortKeys: true }),
    ),
  };
  return Object.entries(expected).every(([key, value]) =>
    sameCanonical(astReceipt[key as keyof typeof astReceipt], value),
  );
}

async function validateIdentityBoundary(
  identity: ClaimPostureRegister["identity_boundary"],
): Promise<boolean> {
  if (
    identity.paragraph_end_line < identity.paragraph_start_line ||
    identity.identity_statement_end_line <
      identity.identity_statement_start_line ||
    (await sha256(identity.identity_statement)) !==
      identity.identity_statement_digest
  ) {
    return false;
  }
  const labels = identity.anti_roles.map((antiRole) => antiRole.display_label);
  const roles = identity.anti_roles.map((antiRole) => antiRole.role);
  if (
    labels.length === 0 ||
    new Set(labels).size !== labels.length ||
    new Set(roles).size !== roles.length
  ) {
    return false;
  }
  const receipt = await sha256(
    pythonJson(labels, { ensureAscii: true, sortKeys: false }),
  );
  if (!sameStrings(identity.derivation_receipt_digests, [receipt, receipt])) {
    return false;
  }
  if (
    identity.path !== RATIFIED_IDENTITY_PATH ||
    (await sha256(
      pythonJson(identity, { ensureAscii: false, sortKeys: true }),
    )) !== RATIFIED_IDENTITY_BASIS_DIGEST
  ) {
    return false;
  }
  return identity.anti_roles.every((antiRole) => {
    const expectedRole = antiRole.display_label
      .toLocaleLowerCase("en-US")
      .replace(/[^a-z0-9]+/gu, "_")
      .replace(/^_+|_+$/gu, "");
    return (
      antiRole.role === expectedRole &&
      antiRole.source_path === identity.path &&
      antiRole.source_digest === identity.content_digest &&
      antiRole.line >= identity.paragraph_start_line &&
      antiRole.line <= identity.paragraph_end_line
    );
  });
}

async function validateCustodyAppointments(
  register: ClaimPostureRegister,
): Promise<boolean> {
  if (
    !sameStrings(
      register.custody_appointment_sources.map((source) => source.debt_id),
      CUSTODY_APPOINTMENT_DEBT_IDS,
    )
  ) {
    return false;
  }
  const derived: Array<
    [string, string, string, string, "open" | "blocked" | "closed"]
  > = [];
  for (const source of register.custody_appointment_sources) {
    if (
      source.source_content.includes("\n") ||
      !source.source_content.startsWith("|")
    ) {
      return false;
    }
    const digest = await sha256(source.source_content);
    if (source.content_digest !== digest) return false;
    const cells = source.source_content
      .trim()
      .replace(/^\||\|$/gu, "")
      .split("|")
      .map((cell) => cell.trim());
    if (cells.length !== 5) return false;
    const tokens = (value: string): string[] =>
      [...value.matchAll(/`([^`]+)`/gu)].map((match) => match[1]!);
    const ids = tokens(cells[0]!);
    const owners = tokens(cells[2]!).filter((token) =>
      /^team-[a-z0-9-]+$/u.test(token),
    );
    const statuses = tokens(cells[3]!);
    const commands = tokens(cells[4]!).filter((token) =>
      EXECUTABLE_CLOSURE_PREFIXES.some((prefix) => token.startsWith(prefix)),
    );
    if (
      !sameStrings(ids, [source.debt_id]) ||
      owners.length !== 1 ||
      !sameStrings(statuses, [source.status]) ||
      commands.length !== 1
    ) {
      return false;
    }
    if (
      !sameStrings(
        [owners[0]!, commands[0]!],
        CUSTODY_APPOINTMENT_CONTRACT.get(source.debt_id) ?? [],
      )
    ) {
      return false;
    }
    derived.push([
      source.debt_id,
      owners[0]!,
      commands[0]!,
      `${source.path}#${source.debt_id}@${digest}`,
      source.status,
    ]);
  }
  const rows = register.claims.filter(
    (row) => row.subject === "universal_custody_commitment",
  );
  if (rows.length !== 1 || rows[0]!.source_bindings.length !== 3) {
    return false;
  }
  const appointments: Array<
    [string, string, string, string, "open" | "blocked" | "closed"]
  > = [];
  for (const binding of rows[0]!.source_bindings) {
    const debtId = binding.prerequisite_refs[0];
    const status = register.custody_appointment_sources.find(
      (source) => source.debt_id === debtId,
    )?.status;
    const expectedState = status === "open" ? "planned" : "blocked";
    if (
      status === undefined ||
      binding.source_state !== expectedState ||
      binding.owner.basis !== "closure_commitment" ||
      binding.owner.establishment_class !== "recomputed" ||
      !binding.owner.source_ref?.startsWith(
        `${CUSTODY_APPOINTMENT_SOURCE_PATH}#`,
      ) ||
      binding.prerequisite_refs.length !== 1 ||
      binding.owner.owner === null ||
      binding.closure_signal === null ||
      binding.identity_boundary_ref !== RATIFIED_IDENTITY_PATH
    ) {
      return false;
    }
    appointments.push([
      binding.prerequisite_refs[0]!,
      binding.owner.owner,
      binding.closure_signal,
      binding.owner.source_ref,
      status,
    ]);
  }
  appointments.sort((left, right) => left[0].localeCompare(right[0], "en"));
  return sameCanonical(appointments, derived);
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

function executableClosureSignal(value: string | null): boolean {
  return Boolean(
    value &&
    value === value.trim() &&
    !value.includes("\n") &&
    EXECUTABLE_CLOSURE_PREFIXES.some((prefix) => value.startsWith(prefix)),
  );
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
  if (
    binding.source_state === "planned" &&
    (!binding.owner.owner ||
      !binding.owner.source_ref ||
      !positiveEstablishment(binding.owner.establishment_class) ||
      !executableClosureSignal(binding.closure_signal))
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
  const keys = new Set<string>();
  for (const metadata of row.producer_metadata) {
    const key = `${metadata.source_symbol ?? "<module>"}\u0000${metadata.subject}`;
    if (keys.has(key)) return false;
    keys.add(key);
    if (
      [metadata.subject, metadata.owner, metadata.closure_signal].some(
        (value) => value !== value.trim() || value.includes("\n"),
      ) ||
      !executableClosureSignal(metadata.closure_signal) ||
      metadata.prerequisite_refs.length !==
        new Set(metadata.prerequisite_refs).size ||
      metadata.limitation_refs.length !==
        new Set(metadata.limitation_refs).size ||
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

function validateInventoryCoordinateCoherence(
  row: SourceInventoryRow,
): boolean {
  const matches = (
    coordinate: SourceCoordinate,
    fieldName: SourceCoordinate["field_name"] | null,
    useKind: SourceCoordinate["use_kind"],
  ): boolean =>
    coordinate.path === row.path &&
    (fieldName === null || coordinate.field_name === fieldName) &&
    coordinate.use_kind === useKind;
  return (
    row.declaration_coordinates.every((coordinate) =>
      matches(coordinate, null, "declaration"),
    ) &&
    row.carrier_coordinates.every(
      (coordinate) =>
        coordinate.path === row.path &&
        ["carrier", "collision"].includes(coordinate.use_kind),
    ) &&
    row.consumer_coordinates.every((coordinate) =>
      matches(coordinate, null, "consumer"),
    ) &&
    row.authoritative_sites.every((site) =>
      matches(site.coordinate, "authoritative_for", "declaration"),
    ) &&
    row.forbidden_sites.every((site) =>
      matches(site.coordinate, "may_not_use_for", "declaration"),
    )
  );
}

function compareText(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function sortSourceBindings(
  bindings: readonly ClaimSourceBinding[],
): ClaimSourceBinding[] {
  return [...bindings].sort(
    (left, right) =>
      compareText(left.coordinate.path, right.coordinate.path) ||
      left.coordinate.line - right.coordinate.line ||
      left.coordinate.column - right.coordinate.column ||
      compareText(left.subject ?? "", right.subject ?? ""),
  );
}

function sameCanonical(left: unknown, right: unknown): boolean {
  const options = { ensureAscii: false, sortKeys: true } as const;
  return pythonJson(left, options) === pythonJson(right, options);
}

function defaultOwner(): OwnerBinding {
  return {
    owner: null,
    basis: "not_established",
    source_ref: null,
    establishment_class: "not_established",
  };
}

function expectedUnestablishedPredicates(
  owner: OwnerBinding,
): SupportPredicate[] {
  const satisfied = new Set([
    "content_bound_source",
    "purpose_permission",
    "identity_boundary",
    "no_blocker",
  ]);
  const issues: Record<SupportPredicate["kind"], string> = {
    accountable_owner: "DS11-OWNER-NOT-ESTABLISHED",
    applicable_jurisdiction: "DS11-JURISDICTION-NOT-ESTABLISHED",
    content_bound_evidence: "DS11-GATE-PREDICATE-NOT-ESTABLISHED",
    content_bound_source: "DS11-SOURCE-CONTENT-NOT-BOUND",
    current_review: "DS11-REVIEW-MISSING",
    identity_boundary: "DS11-IDENTITY-BOUNDARY-NOT-ESTABLISHED",
    no_blocker: "DS11-SOURCE-BLOCKER-PRESENT",
    purpose_permission: "DS11-AUTHORITY-PURPOSE-DENIED",
  };
  return (Object.keys(issues) as SupportPredicate["kind"][])
    .sort(compareText)
    .map((kind) => {
      if (kind === "accountable_owner") {
        return {
          kind,
          satisfied: owner.owner !== null,
          establishment_class: owner.establishment_class,
          evidence_refs: owner.source_ref ? [owner.source_ref] : [],
          issue_code: "DS11-OWNER-NOT-ESTABLISHED",
        };
      }
      if (satisfied.has(kind)) {
        return {
          kind,
          satisfied: true,
          establishment_class: "recomputed",
          evidence_refs: [],
          issue_code: null,
        };
      }
      return {
        kind,
        satisfied: false,
        establishment_class: "not_established",
        evidence_refs: [],
        issue_code: issues[kind],
      };
    });
}

function expectedPlannedPredicates(owner: OwnerBinding): SupportPredicate[] {
  const planned = new Set<string>(REQUIRED_PLANNED_PREDICATES);
  const issues: Record<SupportPredicate["kind"], string> = {
    accountable_owner: "DS11-OWNER-NOT-ESTABLISHED",
    applicable_jurisdiction: "DS11-JURISDICTION-NOT-ESTABLISHED",
    content_bound_evidence: "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND",
    content_bound_source: "DS11-SOURCE-CONTENT-NOT-BOUND",
    current_review: "DS11-REVIEW-MISSING",
    identity_boundary: "DS11-IDENTITY-BOUNDARY-NOT-ESTABLISHED",
    no_blocker: "DS11-SOURCE-BLOCKER-PRESENT",
    purpose_permission: "DS11-AUTHORITY-PURPOSE-DENIED",
  };
  return (Object.keys(issues) as SupportPredicate["kind"][])
    .sort(compareText)
    .map((kind) => ({
      kind,
      satisfied: planned.has(kind),
      establishment_class: planned.has(kind) ? "recomputed" : "not_established",
      evidence_refs:
        kind === "accountable_owner" && owner.source_ref
          ? [owner.source_ref]
          : [],
      issue_code: planned.has(kind) ? null : issues[kind],
    }));
}

function expectedResolvedSourceBinding(
  row: SourceInventoryRow,
  coordinate: SourceCoordinate,
  subject: string,
  denied: string[],
  metadata: ProducerPostureMetadata | undefined,
): ClaimSourceBinding {
  const owner: OwnerBinding = metadata
    ? {
        owner: metadata.owner,
        basis: "closure_commitment",
        source_ref: row.path,
        establishment_class: "recomputed",
      }
    : defaultOwner();
  return {
    coordinate,
    content_digest: row.content_digest,
    resolution: "resolved",
    source_state: metadata?.source_state ?? "not_established",
    subject,
    family: "methodology",
    authoritative_for: [subject],
    may_not_use_for: denied,
    authority_purpose: subject,
    owner,
    jurisdiction: null,
    jurisdiction_establishment: "not_established",
    review_on: null,
    review_due: null,
    source_as_of: null,
    evidence_refs: [],
    evidence_bindings: [],
    limitation_refs: metadata
      ? [
          ...new Set([
            "Producer metadata authorizes planning only; support evidence is absent.",
            ...metadata.limitation_refs,
          ]),
        ]
      : ["Missing independent claim metadata"],
    prerequisite_refs: metadata?.prerequisite_refs ?? [],
    identity_boundary_ref: RATIFIED_IDENTITY_PATH,
    declared_scope_assumption: null,
    supersedes_ref: null,
    superseded_by_ref: null,
    predicates: metadata
      ? expectedPlannedPredicates(owner)
      : expectedUnestablishedPredicates(owner),
    closure_signal: metadata?.closure_signal ?? null,
  };
}

function expectedUnresolvedBinding(
  row: SourceInventoryRow,
  coordinate: SourceCoordinate,
): ClaimSourceBinding {
  const owner = defaultOwner();
  return {
    coordinate,
    content_digest: row.content_digest,
    resolution: row.resolution,
    source_state: "blocked",
    subject: null,
    family: "methodology",
    authoritative_for: [],
    may_not_use_for: [
      ...new Set(row.forbidden_sites.flatMap((site) => site.values)),
    ].sort(compareText),
    authority_purpose: null,
    owner,
    jurisdiction: null,
    jurisdiction_establishment: "not_established",
    review_on: null,
    review_due: null,
    source_as_of: null,
    evidence_refs: [],
    evidence_bindings: [],
    limitation_refs: ["Unresolved source declaration"],
    prerequisite_refs: [],
    identity_boundary_ref: RATIFIED_IDENTITY_PATH,
    declared_scope_assumption: null,
    supersedes_ref: null,
    superseded_by_ref: null,
    predicates: expectedUnestablishedPredicates(owner),
    closure_signal: null,
  };
}

function firstSourceCoordinate(
  row: SourceInventoryRow,
): SourceCoordinate | null {
  return (
    row.declaration_coordinates[0] ??
    row.carrier_coordinates[0] ??
    row.consumer_coordinates[0] ??
    null
  );
}

function expectedSourceBindings(
  inventory: readonly SourceInventoryRow[],
): ClaimSourceBinding[] {
  const bindings: ClaimSourceBinding[] = [];
  for (const row of inventory) {
    if (row.resolution === "ambiguous") {
      const coordinate = firstSourceCoordinate(row);
      if (coordinate) bindings.push(expectedUnresolvedBinding(row, coordinate));
      continue;
    }
    const denied = [
      ...new Set(row.forbidden_sites.flatMap((site) => site.values)),
    ].sort(compareText);
    let emitted = false;
    for (const site of row.authoritative_sites) {
      if (site.resolution === "resolved") {
        for (const subject of site.values) {
          emitted = true;
          const metadata = row.producer_metadata.find(
            (candidate) =>
              candidate.source_symbol === site.coordinate.symbol &&
              candidate.subject === subject,
          );
          bindings.push(
            expectedResolvedSourceBinding(
              row,
              site.coordinate,
              subject,
              denied,
              metadata,
            ),
          );
        }
      } else {
        bindings.push(expectedUnresolvedBinding(row, site.coordinate));
        emitted = true;
      }
    }
    if (!emitted && row.resolution === "runtime_bound") {
      const coordinate = firstSourceCoordinate(row);
      if (coordinate) bindings.push(expectedUnresolvedBinding(row, coordinate));
    }
  }
  return sortSourceBindings(bindings);
}

function validateFixedSemanticBasis(
  claims: readonly ClaimPostureRow[],
): boolean {
  const rows = claims.filter(
    (row) => row.subject && FIXED_SEMANTIC_BINDING_COUNTS.has(row.subject),
  );
  if (
    rows.length !== FIXED_SEMANTIC_BINDING_COUNTS.size ||
    new Set(rows.map((row) => row.subject)).size !==
      FIXED_SEMANTIC_BINDING_COUNTS.size
  ) {
    return false;
  }
  return rows.every(
    (row) =>
      row.subject !== null &&
      row.source_bindings.length ===
        FIXED_SEMANTIC_BINDING_COUNTS.get(row.subject),
  );
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

function addDays(value: string, days: number): string {
  const date = new Date(`${value}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function semanticPredicates(
  satisfied: ReadonlySet<string>,
  evidenceRefs: readonly string[],
): SupportPredicate[] {
  const issues: Record<SupportPredicate["kind"], string> = {
    accountable_owner: "DS11-OWNER-NOT-ESTABLISHED",
    applicable_jurisdiction: "DS11-JURISDICTION-NOT-ESTABLISHED",
    content_bound_evidence: "DS11-EVIDENCE-NOT-INDEPENDENTLY-BOUND",
    content_bound_source: "DS11-SOURCE-CONTENT-NOT-BOUND",
    current_review: "DS11-REVIEW-MISSING-OR-STALE",
    identity_boundary: "DS11-IDENTITY-BOUNDARY-NOT-ESTABLISHED",
    no_blocker: "DS11-SOURCE-BLOCKER-PRESENT",
    purpose_permission: "DS11-AUTHORITY-PURPOSE-DENIED",
  };
  return (Object.keys(issues) as SupportPredicate["kind"][])
    .sort(compareText)
    .map((kind) => ({
      kind,
      satisfied: satisfied.has(kind),
      establishment_class: satisfied.has(kind)
        ? "recomputed"
        : "not_established",
      evidence_refs: satisfied.has(kind) ? [...evidenceRefs] : [],
      issue_code: satisfied.has(kind) ? null : issues[kind],
    }));
}

function semanticEvidence(
  subject: string,
  verifier: AdmittedVerifier,
  sourceAsOf: string,
  establishmentClass: EvidenceBinding["establishment_class"] = "recomputed",
): EvidenceBinding {
  return {
    ref: verifier.content_ref,
    content_digest: verifier.content_digest,
    subject_binding: subject,
    verifier_ref: verifier.ref,
    verifier_provenance_ref: verifier.provenance_ref,
    establishment_class: establishmentClass,
    source_as_of: sourceAsOf,
    supersession_ref: null,
  };
}

function semanticBinding(values: {
  coordinate: SourceCoordinate;
  contentDigest: string;
  sourceState: ClaimSourceBinding["source_state"];
  subject: string;
  family: string;
  authoritativeFor: string[];
  mayNotUseFor: string[];
  owner: OwnerBinding;
  jurisdiction: string | null;
  jurisdictionEstablishment: EstablishmentClass;
  reviewOn: string | null;
  reviewDue: string | null;
  sourceAsOf: string | null;
  evidence: EvidenceBinding | null;
  limitationRefs: string[];
  prerequisiteRefs?: string[];
  closureSignal?: string | null;
  predicateFacts: ReadonlySet<string>;
}): ClaimSourceBinding {
  const evidenceBindings = values.evidence ? [values.evidence] : [];
  const evidenceRefs = values.evidence ? [values.evidence.ref] : [];
  return {
    coordinate: values.coordinate,
    content_digest: values.contentDigest,
    resolution: "resolved",
    source_state: values.sourceState,
    subject: values.subject,
    family: values.family,
    authoritative_for: values.authoritativeFor,
    may_not_use_for: values.mayNotUseFor,
    authority_purpose: values.subject,
    owner: values.owner,
    jurisdiction: values.jurisdiction,
    jurisdiction_establishment: values.jurisdictionEstablishment,
    review_on: values.reviewOn,
    review_due: values.reviewDue,
    source_as_of: values.sourceAsOf,
    evidence_refs: evidenceRefs,
    evidence_bindings: evidenceBindings,
    limitation_refs: values.limitationRefs,
    prerequisite_refs: values.prerequisiteRefs ?? [],
    identity_boundary_ref: RATIFIED_IDENTITY_PATH,
    declared_scope_assumption: null,
    supersedes_ref: null,
    superseded_by_ref: null,
    predicates: semanticPredicates(values.predicateFacts, evidenceRefs),
    closure_signal: values.closureSignal ?? null,
  };
}

async function expectedFixedSemanticBindings(
  register: ClaimPostureRegister,
): Promise<ClaimSourceBinding[]> {
  const identity = register.identity_boundary;
  const verifiers = await deriveAdmittedVerifiers(register);
  const verifierByKind = new Map(
    verifiers.map((verifier) => [verifier.verifier_kind, verifier]),
  );
  const identityVerifier = verifierByKind.get("identity_boundary_derivation")!;
  const identityCoordinate: SourceCoordinate = {
    path: identity.path,
    symbol: "ratified_system_identity",
    line: identity.identity_statement_start_line,
    column: 0,
    field_name: "authoritative_for",
    use_kind: "declaration",
  };
  const identityOwner: OwnerBinding = {
    owner: identity.owner,
    basis: "ratified_document",
    source_ref: identity.path,
    establishment_class: "recomputed",
  };
  const exactIdentity =
    identity.content_digest === RATIFIED_IDENTITY_CONTENT_DIGEST;
  const identityReviewDue = addDays(identity.last_reviewed, 365);
  const completeFacts = new Set<string>(REQUIRED_SUPPORT_PREDICATES);
  const identityEvidence = semanticEvidence(
    "system_identity",
    identityVerifier,
    identity.last_reviewed,
    "independently_reconciled",
  );
  const bindings: ClaimSourceBinding[] = [
    semanticBinding({
      coordinate: identityCoordinate,
      contentDigest: identity.content_digest,
      sourceState: exactIdentity ? "supported" : "blocked",
      subject: "system_identity",
      family: "methodology",
      authoritativeFor: identity.authoritative_for,
      mayNotUseFor: identity.may_not_use_for,
      owner: identityOwner,
      jurisdiction: "non_jurisdiction_specific",
      jurisdictionEstablishment: "recomputed",
      reviewOn: identity.last_reviewed,
      reviewDue: identityReviewDue,
      sourceAsOf: identity.last_reviewed,
      evidence: identityEvidence,
      limitationRefs: [
        exactIdentity
          ? "Bounded to non-jurisdiction-specific system identity."
          : "System identity source differs from the ratified byte boundary.",
      ],
      predicateFacts: exactIdentity
        ? completeFacts
        : new Set([...completeFacts].filter((kind) => kind !== "no_blocker")),
    }),
  ];

  const custodyFacts = new Set([
    "content_bound_source",
    "purpose_permission",
    "accountable_owner",
    "identity_boundary",
  ]);
  const custodyRow = register.claims.find(
    (row) => row.subject === "universal_custody_commitment",
  )!;
  const appointments = custodyRow.source_bindings
    .map((binding) => ({
      debtId: binding.prerequisite_refs[0]!,
      owner: binding.owner.owner!,
      sourceRef: binding.owner.source_ref!,
      closureSignal: binding.closure_signal!,
      status: register.custody_appointment_sources.find(
        (source) => source.debt_id === binding.prerequisite_refs[0],
      )!.status,
    }))
    .sort((left, right) => compareText(left.debtId, right.debtId));
  for (const appointment of appointments) {
    const custodyState = appointment.status === "open" ? "planned" : "blocked";
    const custodyLimitation =
      appointment.status === "open"
        ? `Planned prerequisite: ${appointment.debtId}`
        : appointment.status === "blocked"
          ? `Blocked prerequisite: ${appointment.debtId}`
          : `Closed appointment lacks an admitted closure receipt: ${appointment.debtId}`;
    bindings.push(
      semanticBinding({
        coordinate: identityCoordinate,
        contentDigest: identity.content_digest,
        sourceState: exactIdentity ? custodyState : "blocked",
        subject: "universal_custody_commitment",
        family: "custody",
        authoritativeFor: ["universal_custody_commitment"],
        mayNotUseFor: identity.may_not_use_for,
        owner: {
          owner: appointment.owner,
          basis: "closure_commitment",
          source_ref: appointment.sourceRef,
          establishment_class: "recomputed",
        },
        jurisdiction: "non_jurisdiction_specific",
        jurisdictionEstablishment: "recomputed",
        reviewOn: identity.last_reviewed,
        reviewDue: identityReviewDue,
        sourceAsOf: identity.last_reviewed,
        evidence: null,
        limitationRefs: [custodyLimitation],
        prerequisiteRefs: [appointment.debtId],
        closureSignal: appointment.closureSignal,
        predicateFacts: custodyFacts,
      }),
    );
  }

  const unavailableDigest = `sha256:${"0".repeat(64)}`;
  const accessibility = register.accessibility_document;
  const accessibilityPath =
    accessibility?.path ?? "docs/compliance/A11Y_AUDIT_2026Q2.md";
  const accessibilityCoordinate: SourceCoordinate = {
    path: accessibilityPath,
    symbol: "ds11_projection_index",
    line: 1,
    column: 0,
    field_name: "authoritative_for",
    use_kind: "declaration",
  };
  let accessibilityOwner = defaultOwner();
  let historicalEvidence: EvidenceBinding | null = null;
  let accessibilityAuthoritative: string[] = [];
  let accessibilityDenied = [
    "current_accessibility_conformance",
    "external_accessibility_certification",
  ];
  let historicalFacts = new Set(["identity_boundary"]);
  let accessibilityDigest = unavailableDigest;
  let accessibilitySourceAsOf: string | null = null;
  let accessibilityReviewDue: string | null = null;
  if (accessibility) {
    const selectorValues = new Map(
      accessibility.bindings.map((binding) => [binding.key, binding.value]),
    );
    accessibilityOwner = {
      owner: selectorValues.get("assessment_owner") ?? null,
      basis: "ratified_document",
      source_ref: accessibility.path,
      establishment_class: "recomputed",
    };
    historicalEvidence = semanticEvidence(
      "historical_internal_accessibility_pre_audit",
      verifierByKind.get("accessibility_document_derivation")!,
      accessibility.source_as_of,
    );
    accessibilityAuthoritative = accessibility.authoritative_for.map(
      (purpose) => purpose.purpose,
    );
    accessibilityDenied = accessibility.may_not_use_for.map(
      (purpose) => purpose.purpose,
    );
    historicalFacts = new Set(
      [...completeFacts].filter((kind) => kind !== "applicable_jurisdiction"),
    );
    accessibilityDigest = accessibility.content_digest;
    accessibilitySourceAsOf = accessibility.source_as_of;
    accessibilityReviewDue = addDays(accessibility.source_as_of, 365);
  }
  bindings.push(
    semanticBinding({
      coordinate: accessibilityCoordinate,
      contentDigest: accessibilityDigest,
      sourceState: accessibility ? "supported" : "blocked",
      subject: "historical_internal_accessibility_pre_audit",
      family: "accessibility",
      authoritativeFor: accessibilityAuthoritative,
      mayNotUseFor: accessibilityDenied,
      owner: accessibilityOwner,
      jurisdiction: null,
      jurisdictionEstablishment: "not_established",
      reviewOn: accessibilitySourceAsOf,
      reviewDue: accessibilityReviewDue,
      sourceAsOf: accessibilitySourceAsOf,
      evidence: historicalEvidence,
      limitationRefs: [
        accessibility
          ? "Historical internal pre-audit only; jurisdiction is not established."
          : "Accessibility document projection basis is unavailable.",
      ],
      predicateFacts: historicalFacts,
    }),
  );

  const pageReceipt = register.page_a11y_receipt;
  const currentCoordinate: SourceCoordinate = pageReceipt
    ? {
        ...accessibilityCoordinate,
        path: `${pageReceipt.path}/receipt.json`,
        symbol: "page_a11y_receipt",
      }
    : accessibilityCoordinate;
  const blockedOwner: OwnerBinding = {
    owner: "team-design",
    basis: "closure_commitment",
    source_ref: identity.path,
    establishment_class: "recomputed",
  };
  bindings.push(
    semanticBinding({
      coordinate: currentCoordinate,
      contentDigest: pageReceipt?.content_digest ?? unavailableDigest,
      sourceState: "blocked",
      subject: "current_accessibility_conformance",
      family: "accessibility",
      authoritativeFor: ["historical_page_accessibility_result"],
      mayNotUseFor: ["current_accessibility_conformance"],
      owner: blockedOwner,
      jurisdiction: null,
      jurisdictionEstablishment: "not_established",
      reviewOn: pageReceipt?.source_as_of ?? null,
      reviewDue: pageReceipt?.source_as_of ?? null,
      sourceAsOf: pageReceipt?.source_as_of ?? null,
      evidence: null,
      limitationRefs: [
        pageReceipt
          ? "Current accessibility conformance is blocked by the admitted failing page suite."
          : "Current page-accessibility evidence is unavailable.",
      ],
      predicateFacts: new Set(["identity_boundary"]),
    }),
    semanticBinding({
      coordinate: accessibilityCoordinate,
      contentDigest: accessibilityDigest,
      sourceState: "blocked",
      subject: "external_accessibility_certification",
      family: "accessibility",
      authoritativeFor: accessibilityAuthoritative,
      mayNotUseFor: [
        ...new Set([
          ...accessibilityDenied,
          "external_accessibility_certification",
        ]),
      ].sort(compareText),
      owner: blockedOwner,
      jurisdiction: null,
      jurisdictionEstablishment: "not_established",
      reviewOn: accessibilitySourceAsOf,
      reviewDue: accessibilityReviewDue,
      sourceAsOf: accessibilitySourceAsOf,
      evidence: null,
      limitationRefs: ["External accessibility countersign is absent."],
      prerequisiteRefs: ["DS11-EXTERNAL-A11Y-COUNTERSIGN"],
      predicateFacts: new Set(["identity_boundary"]),
    }),
    semanticBinding({
      coordinate: identityCoordinate,
      contentDigest: identity.content_digest,
      sourceState: "blocked",
      subject: "grounded_performance",
      family: "grounded_performance",
      authoritativeFor: [],
      mayNotUseFor: ["grounded_performance"],
      owner: {
        owner: "team-runtime",
        basis: "closure_commitment",
        source_ref: identity.path,
        establishment_class: "recomputed",
      },
      jurisdiction: "non_jurisdiction_specific",
      jurisdictionEstablishment: "recomputed",
      reviewOn: identity.last_reviewed,
      reviewDue: identityReviewDue,
      sourceAsOf: identity.last_reviewed,
      evidence: null,
      limitationRefs: [
        "No governed grounded-performance evidence is admitted.",
      ],
      predicateFacts: new Set([
        "content_bound_source",
        "accountable_owner",
        "applicable_jurisdiction",
        "current_review",
        "identity_boundary",
      ]),
    }),
  );
  return sortSourceBindings(bindings);
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
    return bindings
      .filter((binding) => binding.source_state === "planned")
      .every(
        (binding) =>
          Boolean(binding.owner.owner) &&
          Boolean(binding.owner.source_ref) &&
          positiveEstablishment(binding.owner.establishment_class) &&
          executableClosureSignal(binding.closure_signal),
      )
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
    if (binding.source_state === "planned") {
      if (
        !binding.owner.owner ||
        !binding.owner.source_ref ||
        !positiveEstablishment(binding.owner.establishment_class)
      ) {
        blockers.add("DS11-OWNER-NOT-ESTABLISHED");
      }
      if (!executableClosureSignal(binding.closure_signal)) {
        blockers.add("DS11-PLANNED-CLOSURE-SIGNAL-MISSING");
      }
    }
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

async function deriveClaimRows(
  bindings: readonly ClaimSourceBinding[],
  register: ClaimPostureRegister,
): Promise<ClaimPostureRow[]> {
  const grouped = new Map<string, ClaimSourceBinding[]>();
  for (const binding of bindings) {
    const key =
      binding.subject ??
      `unresolved:${binding.coordinate.path}:${binding.coordinate.line}:${binding.coordinate.column}`;
    const group = grouped.get(key) ?? [];
    group.push(binding);
    grouped.set(key, group);
  }
  const rows: ClaimPostureRow[] = [];
  for (const [key, group] of grouped) {
    const ordered = [...group].sort(
      (left, right) =>
        compareText(left.coordinate.path, right.coordinate.path) ||
        left.coordinate.line - right.coordinate.line ||
        left.coordinate.column - right.coordinate.column,
    );
    const first = ordered[0]!;
    const allowed = new Set(first.authoritative_for);
    for (const binding of ordered.slice(1)) {
      for (const purpose of [...allowed]) {
        if (!binding.authoritative_for.includes(purpose))
          allowed.delete(purpose);
      }
    }
    const denied = new Set(
      ordered.flatMap((binding) => binding.may_not_use_for),
    );
    const owners = new Set(
      ordered
        .map((binding) => binding.owner.owner)
        .filter((owner): owner is string => owner !== null),
    );
    const minimum = (values: Array<string | null>): string | null => {
      const present = values.filter((value): value is string => value !== null);
      return present.length > 0 ? present.sort(compareText)[0]! : null;
    };
    const provisional: ClaimPostureRow = {
      claim_id: `claim-posture:${(await sha256(key)).slice("sha256:".length)}`,
      subject: first.subject,
      family: first.family,
      source_bindings: ordered,
      authoritative_for: [...allowed].sort(compareText),
      may_not_use_for: [...denied].sort(compareText),
      accountable_owner: owners.size === 1 ? [...owners][0]! : null,
      owner_basis: first.owner.basis,
      review_on: minimum(ordered.map((binding) => binding.review_on)),
      review_due: minimum(ordered.map((binding) => binding.review_due)),
      source_as_of: minimum(ordered.map((binding) => binding.source_as_of)),
      audiences: ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
      closure_signal: first.closure_signal,
      effective_state: "blocked",
      blocker_codes: [],
      limitations: [],
    };
    const evaluated = evaluateClaim(provisional, register);
    rows.push({
      ...provisional,
      effective_state: evaluated.state,
      blocker_codes: evaluated.blockers,
      limitations: evaluated.limitations,
    });
  }
  return rows.sort((left, right) => compareText(left.claim_id, right.claim_id));
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
    if (
      register.source_inventory.some(
        (row) =>
          !validateProducerMetadata(row) ||
          !validateInventoryCoordinateCoherence(row),
      )
    ) {
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
      register.source_inventory.some(
        (row) => admitted.get(row.path) !== row.content_digest,
      ) ||
      !(await validateDerivationReceipts(register)) ||
      admitted.get(register.identity_boundary.path) !==
        register.identity_boundary.content_digest ||
      (register.accessibility_document !== null &&
        (admitted.get(register.accessibility_document.path) !==
          register.accessibility_document.content_digest ||
          !(await validateAccessibilityDocument(
            register.accessibility_document,
          )))) ||
      (register.page_a11y_receipt !== null &&
        (register.page_a11y_receipt.admitted_sources.some(
          (member) => admitted.get(member.path) !== member.content_digest,
        ) ||
          !(await validatePageA11yReceipt(register.page_a11y_receipt)))) ||
      !(await validateIdentityBoundary(register.identity_boundary)) ||
      !validateFixedSemanticBasis(register.claims) ||
      !(await validateCustodyAppointments(register))
    ) {
      return false;
    }
    const actualSourceBindings = register.claims
      .filter(
        (row) =>
          row.subject === null ||
          !FIXED_SEMANTIC_BINDING_COUNTS.has(row.subject),
      )
      .flatMap((row) => row.source_bindings);
    if (
      !sameCanonical(
        sortSourceBindings(actualSourceBindings),
        expectedSourceBindings(register.source_inventory),
      )
    ) {
      return false;
    }
    const actualFixedBindings = register.claims
      .filter(
        (row) =>
          row.subject !== null &&
          FIXED_SEMANTIC_BINDING_COUNTS.has(row.subject),
      )
      .flatMap((row) => row.source_bindings);
    if (
      !sameCanonical(
        sortSourceBindings(actualFixedBindings),
        await expectedFixedSemanticBindings(register),
      )
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
    const expectedClaims = await deriveClaimRows(
      register.claims.flatMap((row) => row.source_bindings),
      register,
    );
    if (!sameCanonical(register.claims, expectedClaims)) return false;
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
