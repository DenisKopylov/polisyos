import type {
  ArtifactMissingConfidenceLedgerRiskSpendPacket,
  AvailableConfidenceLedgerRiskSpendPacket,
  ConditionalDeltaAmount,
  InstrumentInstanceRow,
  InvalidConfidenceLedgerRiskSpendPacket,
  PromotionObligationClass,
  SourceBlockedConfidenceLedgerRiskSpendPacket,
} from "@polisyos/runtime-api-client";
import { z } from "zod";

export const CONFIDENCE_LEDGER_DECLARED_SET_RIDER =
  "≤ δ relative to the declared obligation set";
export const CONFIDENCE_LEDGER_LOCALITY_RIDER =
  "Local accounting for this exact confidence scope; no family or sequence-level claim is asserted.";

export const CONFIDENCE_LEDGER_OBLIGATION_ORDER = [
  "normative",
  "value",
  "syntax",
  "type",
  "slot",
  "param",
  "effect",
  "identification",
  "measurement",
  "calibration",
  "data",
  "implementation",
  "eval_safety",
  "coupling",
  "equilibrium",
] as const satisfies readonly PromotionObligationClass[];

export const CONFIDENCE_LEDGER_INSTRUMENT_ORDER = [
  "constant_unit_e_process",
  "owner_verified_confidence_sequence",
  "owner_verified_e_value",
  "owner_verified_e_process",
  "owner_verified_sequential_test",
  "deterministic_owner_proof",
  "deterministic_refusal_certificate",
  "bayesian_credible_interval",
  "fixed_time_confidence_interval",
  "causal_sensitivity_e_value",
  "ddm_online_fdr_controller",
  "foundry_empirical_confidence_sequence",
  "split_conformal_interval",
] as const;

export const CONFIDENCE_LEDGER_ROUTE_ORDER = [
  "n8_fixed_time_calibration_candidate",
  "n8_data_trust_promotion_candidate",
  "owner_acquisition_route",
  "estimand_binding_refusal",
  "owner_data_gap",
  "admission_passport",
] as const;

type StrictAvailablePacket = Omit<
  AvailableConfidenceLedgerRiskSpendPacket,
  "availability"
> & { availability: "available" };
type StrictSourceBlockedPacket = Omit<
  SourceBlockedConfidenceLedgerRiskSpendPacket,
  "availability" | "source_blocked_reason"
> & { availability: "source_blocked"; source_blocked_reason: "over_spend" };
type StrictArtifactMissingPacket = Omit<
  ArtifactMissingConfidenceLedgerRiskSpendPacket,
  "availability"
> & { availability: "artifact_missing" };
type StrictInvalidSourcePacket = Omit<
  InvalidConfidenceLedgerRiskSpendPacket,
  "availability"
> & { availability: "invalid_source" };

export type ConfidenceLedgerRiskSpendPacket =
  | StrictAvailablePacket
  | StrictSourceBlockedPacket
  | StrictArtifactMissingPacket
  | StrictInvalidSourcePacket;

type ConfidenceLedgerOwnerPacketSchema =
  | "ArtifactMissingConfidenceLedgerRiskSpendPacket"
  | "AvailableConfidenceLedgerRiskSpendPacket"
  | "InvalidConfidenceLedgerRiskSpendPacket"
  | "SourceBlockedConfidenceLedgerRiskSpendPacket";

export type ConfidenceLedgerOwnerLiteralRule = Readonly<{
  path: string;
  rootSchema: ConfidenceLedgerOwnerPacketSchema;
  value: boolean | number | string;
}>;

function ownerLiteralRule(
  rootSchema: ConfidenceLedgerOwnerPacketSchema,
  path: string,
  value: ConfidenceLedgerOwnerLiteralRule["value"],
): ConfidenceLedgerOwnerLiteralRule {
  return Object.freeze({ path, rootSchema, value });
}

const COMMON_OWNER_LITERAL_VALUES = [
  ["/export_replay_contract", "policyos.runtime.export_replay_binding.v1"],
  ["/intended_audience", "REVIEWER"],
  [
    "/packet_schema_version",
    "policyos.runtime.confidence_ledger_risk_spend_packet.v1",
  ],
  ["/projection_id", "confidence-ledger-risk-spend"],
  [
    "/projection_rule_version",
    "policyos.runtime.confidence_ledger_risk_spend.v1",
  ],
  [
    "/stable_address",
    "/api/v1/exports/governed-projections/confidence-ledger-risk-spend",
  ],
] as const;

function commonOwnerLiteralRules(
  rootSchema: ConfidenceLedgerOwnerPacketSchema,
): readonly ConfidenceLedgerOwnerLiteralRule[] {
  return COMMON_OWNER_LITERAL_VALUES.map(([path, value]) =>
    ownerLiteralRule(rootSchema, path, value),
  );
}

const CONDITIONAL_AMOUNT_PATHS = [
  "/payload/grouped_spend/*/spend",
  "/payload/instrument_instances/*/spend",
  "/payload/obligation_class_risk_spend/*/allocation",
  "/payload/obligation_class_risk_spend/*/overspend_amount",
  "/payload/obligation_class_risk_spend/*/remaining",
  "/payload/obligation_class_risk_spend/*/spent",
  "/payload/scope_total_risk_spend/allocation",
  "/payload/scope_total_risk_spend/overspend_amount",
  "/payload/scope_total_risk_spend/remaining",
  "/payload/scope_total_risk_spend/spent",
  "/payload/total_spend",
] as const;

const CONDITIONAL_AMOUNT_LITERAL_VALUES = [
  ["declared_set_rider", CONFIDENCE_LEDGER_DECLARED_SET_RIDER],
  ["locality_rider", CONFIDENCE_LEDGER_LOCALITY_RIDER],
  ["rational_display_version", "policyos.runtime.exact_rational_display.v1"],
] as const;

const AVAILABLE_OWNER_LITERAL_VALUES = [
  ["/payload/appointment_posture", "institutional_authority_unappointed"],
  ["/payload/coverage_envelope/challenge_route_state", "not_established"],
  [
    "/payload/coverage_envelope/declared_set_rider",
    CONFIDENCE_LEDGER_DECLARED_SET_RIDER,
  ],
  ["/payload/coverage_envelope/exclusion_basis_state", "not_established"],
  ["/payload/coverage_envelope/expiry_state", "not_issued"],
  [
    "/payload/coverage_envelope/locality_rider",
    CONFIDENCE_LEDGER_LOCALITY_RIDER,
  ],
  ["/payload/coverage_envelope/review_state", "not_issued"],
  [
    "/payload/coverage_envelope/rule_version",
    "policyos.runtime.obligation_coverage.negative.v1",
  ],
  [
    "/payload/coverage_envelope/schema_version",
    "policyos.runtime.obligation_coverage.v1",
  ],
  ["/payload/coverage_envelope/search_basis_state", "not_established"],
  ["/payload/coverage_envelope/source_cutoff_state", "not_established"],
  ["/payload/coverage_envelope/unknown_remainder/cardinality", "not_estimated"],
  [
    "/payload/coverage_envelope/unknown_remainder/kind",
    "independent_coverage_producer_missing",
  ],
  [
    "/payload/coverage_envelope/unknown_remainder/probability",
    "not_calibrated",
  ],
  ["/payload/fixed_scope_disclosure", CONFIDENCE_LEDGER_LOCALITY_RIDER],
  ["/payload/good_event_posture/composition_rule", "union_bound"],
  ["/payload/good_event_posture/independence_claim", false],
  [
    "/payload/positive_register/appointment_denominator_state",
    "recomputed_empty",
  ],
  [
    "/payload/positive_register/appointment_sufficiency_state",
    "not_established",
  ],
  [
    "/payload/positive_register/authority_posture",
    "institutional_authority_unappointed",
  ],
  ["/payload/positive_register/population_count", 0],
  ["/payload/positive_register/population_state", "valid_zero"],
  [
    "/payload/registry_basis/schema_version",
    "policyos.runtime.confidence_ledger.registry.v1",
  ],
  [
    "/payload/rule_version",
    "policyos.runtime.confidence_ledger_surface.exact.v1",
  ],
  ["/payload/schema_version", "policyos.runtime.confidence_ledger_surface.v1"],
  [
    "/payload/semantic_ledger_basis/checks/*/schema_version",
    "policyos.runtime.confidence_ledger.v1",
  ],
  [
    "/payload/semantic_ledger_basis/conditionality_clause",
    "P(false promotion | maintained assumptions) <= delta is conditional on obligation completeness + validator soundness (the spec's A4 = our open P29).",
  ],
  [
    "/payload/semantic_ledger_basis/events/*/check/schema_version",
    "policyos.runtime.confidence_ledger.v1",
  ],
  [
    "/payload/semantic_ledger_basis/good_event_clause",
    "Omega_delta is the intersection of the good events for executed probabilistic checks; the union bound is used without an independence claim.",
  ],
  [
    "/payload/semantic_ledger_basis/schema_version",
    "policyos.runtime.confidence_ledger.v1",
  ],
  ["/payload/source_provenance/*/availability_state", "available_typed_input"],
  ["/payload/status", "not_promoted"],
  [
    "/replay_pins/projection_rule_version",
    "policyos.runtime.confidence_ledger_risk_spend.v1",
  ],
  ["/source/related_artifact_bindings/*/relation", "semantic_projection"],
] as const;

const AVAILABLE_ROOT = "AvailableConfidenceLedgerRiskSpendPacket" as const;

export const CONFIDENCE_LEDGER_OWNER_LITERAL_RULES = Object.freeze([
  ...commonOwnerLiteralRules("ArtifactMissingConfidenceLedgerRiskSpendPacket"),
  ownerLiteralRule(
    "ArtifactMissingConfidenceLedgerRiskSpendPacket",
    "/absence_reason",
    "governed confidence-ledger source is absent",
  ),
  ownerLiteralRule(
    "ArtifactMissingConfidenceLedgerRiskSpendPacket",
    "/availability",
    "artifact_missing",
  ),
  ...commonOwnerLiteralRules(AVAILABLE_ROOT),
  ownerLiteralRule(AVAILABLE_ROOT, "/availability", "available"),
  ...AVAILABLE_OWNER_LITERAL_VALUES.map(([path, value]) =>
    ownerLiteralRule(AVAILABLE_ROOT, path, value),
  ),
  ...CONDITIONAL_AMOUNT_PATHS.flatMap((amountPath) =>
    CONDITIONAL_AMOUNT_LITERAL_VALUES.map(([field, value]) =>
      ownerLiteralRule(AVAILABLE_ROOT, `${amountPath}/${field}`, value),
    ),
  ),
  ...commonOwnerLiteralRules("InvalidConfidenceLedgerRiskSpendPacket"),
  ownerLiteralRule(
    "InvalidConfidenceLedgerRiskSpendPacket",
    "/absence_reason",
    "confidence-ledger source failed owner admission",
  ),
  ownerLiteralRule(
    "InvalidConfidenceLedgerRiskSpendPacket",
    "/availability",
    "invalid_source",
  ),
  ...commonOwnerLiteralRules("SourceBlockedConfidenceLedgerRiskSpendPacket"),
  ownerLiteralRule(
    "SourceBlockedConfidenceLedgerRiskSpendPacket",
    "/availability",
    "source_blocked",
  ),
  ownerLiteralRule(
    "SourceBlockedConfidenceLedgerRiskSpendPacket",
    "/replay_pins/projection_rule_version",
    "policyos.runtime.confidence_ledger_risk_spend.v1",
  ),
  ownerLiteralRule(
    "SourceBlockedConfidenceLedgerRiskSpendPacket",
    "/source_blocked_reason",
    "over_spend",
  ),
] satisfies readonly ConfidenceLedgerOwnerLiteralRule[]);

const nonEmptyString = z.string().min(1);
const hash = z.string().regex(/^sha256:[0-9a-f]{64}$/u);
const nullableHash = hash.nullable();
const workerReceiptRef = z
  .string()
  .regex(/^owner-validation:sha256:[0-9a-f]{64}$/u);
const rawRefusalCode = z
  .string()
  .regex(/^[a-z][a-z0-9_]{2,127}$/u)
  .nullable();
const CONFIDENCE_LEDGER_MAX_RATIONAL_COUNT = 256;
const CONFIDENCE_LEDGER_MAX_RATIONAL_DENOMINATOR = 100_000;
const CONFIDENCE_LEDGER_MAX_RATIONAL_NUMERATOR = 1_000_000_000;
const CONFIDENCE_LEDGER_MAX_RATIONAL_PERIOD_WORK = 250_000;
const CONFIDENCE_LEDGER_MAX_EXACT_DECIMAL_CODE_UNITS = 100_032;
const CONFIDENCE_LEDGER_MAX_RATIONAL_DISPLAY_CODE_UNITS = 32;
const rational = z
  .object({
    denominator: z
      .number()
      .int()
      .positive()
      .max(CONFIDENCE_LEDGER_MAX_RATIONAL_DENOMINATOR)
      .refine(Number.isSafeInteger),
    numerator: z
      .number()
      .int()
      .nonnegative()
      .max(CONFIDENCE_LEDGER_MAX_RATIONAL_NUMERATOR)
      .refine(Number.isSafeInteger),
  })
  .strict();
const exactDecimalText = z
  .string()
  .min(1)
  .max(CONFIDENCE_LEDGER_MAX_EXACT_DECIMAL_CODE_UNITS);
const obligationClass = z.enum(CONFIDENCE_LEDGER_OBLIGATION_ORDER);
const maintainedAssumptions = z.tuple([
  z.literal("obligation_completeness"),
  z.literal("validator_soundness"),
]);
const certificateRole = z.enum([
  "promotion",
  "promotion_conformance",
  "refusal",
  "acquisition",
  "admission",
]);
const claimPolarity = z.enum([
  "false_accept",
  "confident_wrong_refusal",
  "confident_wrong_admission",
  "conformance_only",
]);
const instrumentBlocker = z.enum([
  "coverage_argument_missing",
  "non_anytime_valid",
  "owner_theorem_unavailable",
  "other_runtime_refusal",
]);
const nullableInstrumentBlocker = instrumentBlocker.nullable();

const confidenceRiskScope = z
  .object({
    authority_purpose: nonEmptyString,
    epoch_ref: nonEmptyString.nullable(),
    model_ref: nonEmptyString.nullable(),
    owner_projection_hash: hash,
    owner_scope_key: nonEmptyString,
    rule_ref: nonEmptyString.nullable(),
    schema_ref: nonEmptyString.nullable(),
    scope_owner_ref: nonEmptyString,
  })
  .strict();

const conditionalDeltaAmount = z
  .object({
    amount: rational,
    amount_hash: hash,
    canonical_decimal: exactDecimalText,
    coverage_envelope_hash: hash,
    coverage_envelope_ref: nonEmptyString,
    declared_obligation_classes_hash: hash,
    declared_set_rider: z.literal(CONFIDENCE_LEDGER_DECLARED_SET_RIDER),
    locality_rider: z.literal(CONFIDENCE_LEDGER_LOCALITY_RIDER),
    maintained_assumptions: maintainedAssumptions,
    obligation_class: obligationClass.nullable(),
    owner_scope_key: nonEmptyString,
    rational_display: z
      .string()
      .max(CONFIDENCE_LEDGER_MAX_RATIONAL_DISPLAY_CODE_UNITS)
      .regex(/^[0-9]+\/[1-9][0-9]*$/u),
    rational_display_version: z.literal(
      "policyos.runtime.exact_rational_display.v1",
    ),
    scope_id: nonEmptyString,
    semantic_role: nonEmptyString,
  })
  .strict();

const coverageSourceIdentity = z
  .object({
    admission_state: z.enum([
      "canonical_registry_validated",
      "worker_admission_not_established",
    ]),
    availability_state: z.literal("available_typed_input"),
    content_hash: hash,
    source_ref: nonEmptyString,
    source_role: z.enum(["canonical_registry", "semantic_ledger"]),
    verifier_ref: nonEmptyString,
  })
  .strict();

const coverageEnvelope = z
  .object({
    assessment: z.enum(["known_incomplete", "open_world_unresolved"]),
    assessment_key: hash,
    authoritative_for: z.tuple([
      z.literal("conditionality_disclosure"),
      z.literal("declared_set_accounting"),
    ]),
    authority_purpose: nonEmptyString,
    authorized_audiences: z.tuple([
      z.literal("reviewer"),
      z.literal("expert"),
      z.literal("machine"),
    ]),
    challenge_route_state: z.literal("not_established"),
    declared_obligation_classes: z.tuple(
      CONFIDENCE_LEDGER_OBLIGATION_ORDER.map((item) => z.literal(item)) as [
        z.ZodLiteral<"normative">,
        ...z.ZodLiteral<PromotionObligationClass>[],
      ],
    ),
    declared_scope: confidenceRiskScope,
    declared_set_rider: z.literal(CONFIDENCE_LEDGER_DECLARED_SET_RIDER),
    delta: rational,
    envelope_hash: hash,
    envelope_ref: z.string().regex(/^coverage-envelope:sha256:[0-9a-f]{64}$/u),
    exclusion_basis_state: z.literal("not_established"),
    exclusions: z.tuple([]),
    expiry_state: z.literal("not_issued"),
    locality_rider: z.literal(CONFIDENCE_LEDGER_LOCALITY_RIDER),
    maintained_assumptions: maintainedAssumptions,
    may_not_use_for: z.tuple([
      z.literal("promotion_authority"),
      z.literal("publication_authority"),
      z.literal("bounded_completeness"),
      z.literal("world_completeness"),
    ]),
    obligation_language_version: nonEmptyString,
    obligation_rule_ref: nonEmptyString,
    obligation_schema_ref: nonEmptyString,
    owner_scope_key: nonEmptyString,
    protected_action_id: z.literal("protected-action://ds17/review-risk-spend"),
    reason_codes: z
      .array(
        z.enum([
          "DS17-COVERAGE-OPEN-WORLD",
          "DS17-COVERAGE-KNOWN-INCOMPLETE",
          "DS17-COVERAGE-SEARCH-NOT-ESTABLISHED",
          "DS17-COVERAGE-EXCLUSIONS-NOT-ESTABLISHED",
          "DS17-COVERAGE-INDEPENDENCE-MISSING",
        ]),
      )
      .length(4),
    review_state: z.literal("not_issued"),
    rule_version: z.literal("policyos.runtime.obligation_coverage.negative.v1"),
    schema_version: z.literal("policyos.runtime.obligation_coverage.v1"),
    scope_id: z.string().regex(/^confidence-risk-scope:sha256:[0-9a-f]{64}$/u),
    search_basis_state: z.literal("not_established"),
    searched_sources: z.tuple([]),
    source_cutoff_state: z.literal("not_established"),
    source_identities: z.tuple([
      coverageSourceIdentity,
      coverageSourceIdentity,
    ]),
    ttl_state: z.enum([
      "not_issued_known_incomplete",
      "not_issued_open_world_unresolved",
    ]),
    unknown_remainder: z
      .object({
        cardinality: z.literal("not_estimated"),
        kind: z.literal("independent_coverage_producer_missing"),
        probability: z.literal("not_calibrated"),
      })
      .strict(),
    witness_refs: z.array(hash),
  })
  .strict();

const proofProfile = z
  .object({
    anytime_valid: z.boolean(),
    deterministic: z.boolean(),
    guarantee_kind: nonEmptyString,
    permits_obligation_satisfaction: z.boolean(),
    profile_id: nonEmptyString,
    proof_kernel_id: nonEmptyString,
    refusal_code: nullableInstrumentBlocker,
  })
  .strict();

const registryInstrument = z
  .object({
    certificate_roles: z.array(certificateRole),
    instrument_family: nonEmptyString,
    instrument_id: nonEmptyString,
    proof_profile_id: nonEmptyString,
  })
  .strict();

const registryRoute = z
  .object({
    certificate_class: nonEmptyString,
    certificate_role: certificateRole,
    claim_polarity: claimPolarity,
    instrument_id: nonEmptyString,
    obligation_class: obligationClass,
    owner_ref: nonEmptyString,
    verifier_kernel_id: nonEmptyString,
    verifier_ref: nonEmptyString,
  })
  .strict();

const registry = z
  .object({
    certificate_class_routes: z.array(registryRoute).length(6),
    instruments: z.array(registryInstrument).length(13),
    obligation_pools: z
      .array(
        z
          .object({
            obligation_classes: z.array(obligationClass).min(1),
            pool_id: nonEmptyString,
            weight: rational,
          })
          .strict(),
      )
      .length(7),
    policy: z
      .object({
        conditionality_clause: nonEmptyString,
        default_schedule_profile_id: nonEmptyString,
        delta: rational,
      })
      .strict(),
    proof_profiles: z.array(proofProfile).min(1),
    schedule_profiles: z
      .array(
        z
          .object({
            mass: rational,
            profile_id: nonEmptyString,
            proof_kernel_id: nonEmptyString,
          })
          .strict(),
      )
      .min(1),
    schema_version: z.literal("policyos.runtime.confidence_ledger.registry.v1"),
  })
  .strict();

const semanticOwnerBinding = z
  .object({
    binding_projection_hash: hash,
    certificate_class: nonEmptyString,
    certificate_ref: nonEmptyString,
    certificate_route_hash: hash,
    owner_projection_hash: hash,
    owner_ref: nonEmptyString,
    verifier_kernel_id: nonEmptyString,
    verifier_ref: nonEmptyString,
  })
  .strict();

const semanticCheck = z
  .object({
    anytime_valid: z.boolean(),
    certificate_class: nonEmptyString.nullable(),
    certificate_ref: nonEmptyString,
    certificate_role: certificateRole,
    certificate_route_hash: nullableHash,
    check_projection_hash: hash,
    claim_execution_projection_hash: hash,
    claim_polarity: claimPolarity,
    claim_ref: nonEmptyString,
    claim_scope_ref: nonEmptyString,
    data_window_ref: nonEmptyString,
    deterministic_proof: z.boolean(),
    eligible_for_promotion: z.boolean(),
    execution_id: nonEmptyString.nullable(),
    execution_ordinal: z.number().int().nonnegative().nullable(),
    execution_status: z.enum([
      "prepared",
      "started",
      "executed",
      "refused",
      "unexecuted",
    ]),
    filtration_projection_hash: hash,
    good_event_id: nonEmptyString.nullable(),
    instrument_definition_hash: nullableHash,
    instrument_family: nonEmptyString,
    instrument_id: nonEmptyString,
    null_ref: nonEmptyString,
    obligation_class: obligationClass,
    outcome: z.enum([
      "prepared",
      "started",
      "supported",
      "not_supported",
      "preflight_refusal",
      "cancelled",
      "owner_refused",
      "owner_error",
      "recovered_crash",
      "refused",
    ]),
    owner_binding: semanticOwnerBinding.nullable(),
    owner_invocation_claim_projection_hash: nullableHash,
    proof_detail: nonEmptyString,
    proof_profile_hash: nullableHash,
    proof_profile_id: nonEmptyString,
    refusal_code: rawRefusalCode,
    registry_content_hash: hash,
    request_fingerprint: hash,
    request_key: nonEmptyString,
    schedule_query_index: z.number().int().nonnegative().nullable(),
    schema_version: z.literal("policyos.runtime.confidence_ledger.v1"),
    scope_id: nonEmptyString,
    spend: rational,
    spend_decimal: exactDecimalText,
    supports_obligation: z.boolean(),
  })
  .strict();

const semanticLedger = z
  .object({
    authority_provenance: z.enum(["canonical_repo", "verification"]),
    budget_delta: rational,
    budget_delta_decimal: exactDecimalText,
    checks: z.array(semanticCheck),
    conditionality_clause: nonEmptyString,
    deployment_identity: nonEmptyString,
    events: z.array(
      z
        .object({
          check: semanticCheck,
          event_projection_hash: hash,
          event_type: z.enum(["prepared", "started", "completed"]),
          parent_event_projection_hash: hash,
          revision: z.number().int().positive(),
        })
        .strict(),
    ),
    good_event_clause: nonEmptyString,
    head_event_projection_hash: hash,
    maintained_assumptions: maintainedAssumptions,
    projection_hash: hash,
    projection_scope: z.enum([
      "n11_real_accounting_append_lineage",
      "n11_conformance_append_lineage",
    ]),
    registry_content_hash: hash,
    risk_scope: confidenceRiskScope,
    root_projection_hash: hash,
    schedule_profile_hash: hash,
    schedule_profile_id: nonEmptyString,
    schedule_projection_hash: hash,
    schema_version: nonEmptyString,
    scope_anchor_ref: nonEmptyString,
    scope_id: nonEmptyString,
    total_spend: rational,
    total_spend_decimal: exactDecimalText,
    within_budget: z.boolean(),
  })
  .strict();

const instrumentDefinitionRow = z
  .object({
    anytime_valid: z.boolean(),
    blocker: nullableInstrumentBlocker,
    certificate_roles: z.array(certificateRole),
    deterministic: z.boolean(),
    guarantee_kind: nonEmptyString,
    instrument_family: nonEmptyString,
    instrument_id: nonEmptyString,
    permits_obligation_satisfaction: z.boolean(),
    proof_kernel_id: nonEmptyString,
    proof_profile_id: nonEmptyString,
  })
  .strict();

const certificateRouteRow = z
  .object({
    anytime_valid: z.boolean(),
    blocker: nullableInstrumentBlocker,
    certificate_class: nonEmptyString,
    certificate_role: certificateRole,
    claim_polarity: claimPolarity,
    deterministic: z.boolean(),
    guarantee_kind: nonEmptyString,
    instrument_family: nonEmptyString,
    instrument_id: nonEmptyString,
    obligation_class: obligationClass,
    owner_ref: nonEmptyString,
    permits_obligation_satisfaction: z.boolean(),
    proof_kernel_id: nonEmptyString,
    proof_profile_id: nonEmptyString,
    registry_content_hash: hash,
    route_binding_hash: hash,
    verifier_kernel_id: nonEmptyString,
    verifier_ref: nonEmptyString,
  })
  .strict();

const instrumentInstanceRow = z
  .object({
    anytime_valid: z.boolean(),
    blocker: nullableInstrumentBlocker,
    certificate_class: nonEmptyString.nullable(),
    certificate_ref: nonEmptyString,
    certificate_role: certificateRole,
    certificate_route_ref: nonEmptyString.nullable(),
    eligible_for_promotion: z.boolean(),
    execution_status: z.enum([
      "prepared",
      "started",
      "executed",
      "refused",
      "unexecuted",
    ]),
    instance_ref: nonEmptyString,
    instrument_family: nonEmptyString,
    instrument_id: nonEmptyString,
    obligation_class: obligationClass,
    outcome: z.enum([
      "prepared",
      "started",
      "supported",
      "not_supported",
      "preflight_refusal",
      "cancelled",
      "owner_refused",
      "owner_error",
      "recovered_crash",
      "refused",
    ]),
    proof_profile_id: nonEmptyString,
    raw_runtime_refusal_source: rawRefusalCode,
    spend: conditionalDeltaAmount,
    supports_obligation: z.boolean(),
  })
  .strict();

const classSpendRow = z
  .object({
    allocation: conditionalDeltaAmount,
    check_refs: z.array(nonEmptyString),
    good_event_refs: z.array(nonEmptyString),
    instrument_refs: z.array(nonEmptyString),
    obligation_class: obligationClass,
    overspend_amount: conditionalDeltaAmount,
    remaining: conditionalDeltaAmount,
    spent: conditionalDeltaAmount,
  })
  .strict();

const scopeSpend = z
  .object({
    allocation: conditionalDeltaAmount,
    overspend_amount: conditionalDeltaAmount,
    remaining: conditionalDeltaAmount,
    spent: conditionalDeltaAmount,
  })
  .strict();

const positiveRegister = z
  .object({
    appointment_denominator_state: z.literal("recomputed_empty"),
    appointment_sufficiency_state: z.literal("not_established"),
    authority_posture: z.literal("institutional_authority_unappointed"),
    blockers: z.array(
      z
        .object({
          slot: z.enum([
            "coverage_assessment",
            "instrument_blocker",
            "appointment_posture",
          ]),
          value: nonEmptyString,
        })
        .strict(),
    ),
    entries: z.tuple([]),
    population_count: z.literal(0),
    population_state: z.literal("valid_zero"),
    verified_appointment_refs: z.tuple([]),
    would_populate_when: z.tuple([
      z.literal("owner_validated_promotion_row"),
      z.literal("execution_completed_supported"),
      z.literal("registry_profile_anytime_valid"),
      z.literal("obligation_supported_and_eligible"),
      z.literal("total_and_class_spend_within_budget"),
      z.literal("coverage_supports_protected_use"),
      z.literal("institutional_authority_appointed"),
    ]),
  })
  .strict();

const payload = z
  .object({
    acquisition_instance_refs: z.array(nonEmptyString),
    appointment_posture: z.literal("institutional_authority_unappointed"),
    budget_posture: z.enum(["within_budget", "over_spend"]),
    certificate_route_denominator_count: z.literal(6),
    certificate_route_denominator_hash: hash,
    certificate_routes: z.array(certificateRouteRow).length(6),
    conformance_instance_refs: z.array(nonEmptyString),
    coverage_assessment: z.enum(["known_incomplete", "open_world_unresolved"]),
    coverage_envelope: coverageEnvelope,
    coverage_envelope_ref: nonEmptyString,
    fixed_scope_disclosure: z.literal(CONFIDENCE_LEDGER_LOCALITY_RIDER),
    good_event_posture: z
      .object({
        composition_rule: z.literal("union_bound"),
        executed_probabilistic_good_event_refs: z.array(nonEmptyString),
        good_event_clause: nonEmptyString,
        independence_claim: z.literal(false),
      })
      .strict(),
    grouped_spend: z.array(
      z
        .object({
          instrument_id: nonEmptyString,
          obligation_class: obligationClass,
          spend: conditionalDeltaAmount,
        })
        .strict(),
    ),
    instrument_blockers: z.array(instrumentBlocker),
    instrument_definitions: z.array(instrumentDefinitionRow).length(13),
    instrument_instances: z.array(instrumentInstanceRow),
    obligation_class_risk_spend: z.array(classSpendRow).length(15),
    owner_scope_key: nonEmptyString,
    positive_register: positiveRegister,
    projection_hash: hash,
    refusal_instance_refs: z.array(nonEmptyString),
    registry_basis: registry,
    registry_content_hash: hash,
    risk_scope: confidenceRiskScope,
    rule_version: z.literal(
      "policyos.runtime.confidence_ledger_surface.exact.v1",
    ),
    schema_version: z.literal("policyos.runtime.confidence_ledger_surface.v1"),
    scope_id: nonEmptyString,
    scope_total_risk_spend: scopeSpend,
    semantic_ledger_basis: semanticLedger,
    source_projection_hash: hash,
    source_provenance: z.tuple([
      coverageSourceIdentity,
      coverageSourceIdentity,
    ]),
    status: z.literal("not_promoted"),
    total_spend: conditionalDeltaAmount,
  })
  .strict();

const freshness = z
  .object({
    basis: z.enum([
      "source_timestamp",
      "filesystem_mtime",
      "request_observation",
    ]),
    observed_at: nonEmptyString,
    source_as_of: nonEmptyString.nullable(),
    state: z.enum(["observed", "artifact_missing", "invalid_source"]),
  })
  .strict();

const authoritativeFor = z.tuple([
  z.literal("conditionality_disclosure"),
  z.literal("declared_set_accounting"),
  z.literal("source_validation_posture"),
]);
const intendedAudiences = z.tuple([
  z.literal("REVIEWER"),
  z.literal("EXPERT"),
  z.literal("MACHINE"),
]);
const mayNotUseFor = z.tuple([
  z.literal("promotion_authority"),
  z.literal("publication_authority"),
  z.literal("public_audience"),
  z.literal("bounded_completeness"),
]);

const commonPacketShape = {
  as_of: nonEmptyString,
  authoritative_for: authoritativeFor,
  export_replay_contract: z.literal(
    "policyos.runtime.export_replay_binding.v1",
  ),
  freshness,
  intended_audience: z.literal("REVIEWER"),
  intended_audiences: intendedAudiences,
  may_not_use_for: mayNotUseFor,
  packet_schema_version: z.literal(
    "policyos.runtime.confidence_ledger_risk_spend_packet.v1",
  ),
  projection_id: z.literal("confidence-ledger-risk-spend"),
  projection_rule_version: z.literal(
    "policyos.runtime.confidence_ledger_risk_spend.v1",
  ),
  stable_address: z.literal(
    "/api/v1/exports/governed-projections/confidence-ledger-risk-spend",
  ),
};

const replayPins = z
  .object({
    artifact_content_hash: hash,
    projection_hash: hash,
    projection_rule_version: z.literal(
      "policyos.runtime.confidence_ledger_risk_spend.v1",
    ),
    source_as_of: nonEmptyString,
    source_dependency_hash: hash,
  })
  .strict();

const sourceIdentity = z
  .object({
    artifact_content_hash: hash,
    declared_content_hash: nullableHash,
    related_artifact_bindings: z.array(
      z
        .object({
          binding_name: nonEmptyString,
          owner_semantic_hash: hash,
          relation: nonEmptyString.optional(),
          relative_path: nonEmptyString,
          resolved_artifact_content_hash: hash,
          semantic_hash_rule_version: nonEmptyString,
        })
        .strict(),
    ),
    relative_path: z.literal(
      "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json",
    ),
    validation: z
      .object({
        bound_artifact_content_hash: hash,
        bound_dependency_aggregate_identity: hash,
        bound_dependency_count: z.number().int().positive(),
        frozen_semantic_projection_hash: nullableHash,
        issue_codes: z.tuple([]),
        recomputed_total_spend_denominator: z
          .number()
          .int()
          .positive()
          .nullable(),
        recomputed_total_spend_numerator: z
          .number()
          .int()
          .nonnegative()
          .nullable(),
        registry_content_hash: nullableHash,
        registry_delta_denominator: z.number().int().positive().nullable(),
        registry_delta_numerator: z.number().int().nonnegative().nullable(),
        registry_projection_hash: nullableHash,
        semantic_projection_hash: nullableHash,
        semantic_projection_hash_rule_version: z.literal(
          "policyos.runtime.confidence_ledger.semantic_projection.v1",
        ),
        source_payload_equal: z.literal(true),
        status: z.literal("passed"),
        validator_id: z.literal(
          "tools.quality.validation.check_layer3_gy_confidence_ledger:validate_payload",
        ),
        validator_version: z.literal(
          "policyos.policy_design_case.layer3_gy.n11_confidence_ledger.v1",
        ),
        worker_validation_receipt_hash: hash,
      })
      .strict(),
  })
  .strict();

const availablePacket = z
  .object({
    ...commonPacketShape,
    absence_reason: z.null(),
    availability: z.literal("available"),
    frozen_semantic_projection_hash: hash,
    payload,
    projection_hash: hash,
    registry_content_hash: hash,
    registry_projection_hash: hash,
    replay_address: nonEmptyString,
    replay_pins: replayPins,
    source: sourceIdentity,
    source_blocked_reason: z.null(),
    source_dependency_hash: hash,
    source_rule_version: z.null(),
    source_schema_version: z.literal(
      "policyos.policy_design_case.layer3_gy.n11_confidence_ledger.v1",
    ),
    worker_validation_receipt_hash: hash,
    worker_validation_receipt_ref: workerReceiptRef,
  })
  .strict();

const sourceBlockedPacket = z
  .object({
    ...commonPacketShape,
    absence_reason: z.null(),
    availability: z.literal("source_blocked"),
    projection_hash: hash,
    replay_address: nonEmptyString,
    replay_pins: replayPins,
    source_artifact_content_hash: hash,
    source_blocked_reason: z.literal("over_spend"),
    source_dependency_hash: hash,
    source_rule_version: nonEmptyString.nullable(),
    source_schema_version: nonEmptyString.nullable(),
    worker_validation_receipt_hash: hash,
    worker_validation_receipt_ref: workerReceiptRef,
  })
  .strict();

const artifactMissingPacket = z
  .object({
    ...commonPacketShape,
    absence_reason: z.literal("governed confidence-ledger source is absent"),
    availability: z.literal("artifact_missing"),
    projection_hash: z.null(),
    replay_address: z.null(),
    replay_pins: z.null(),
    source_artifact_content_hash: z.null(),
    source_blocked_reason: z.null(),
    source_dependency_hash: z.null(),
    source_rule_version: z.null(),
    source_schema_version: z.null(),
    worker_validation_receipt_hash: z.null(),
    worker_validation_receipt_ref: z.null(),
  })
  .strict();

const invalidSourcePacket = z
  .object({
    ...commonPacketShape,
    absence_reason: z.literal(
      "confidence-ledger source failed owner admission",
    ),
    availability: z.literal("invalid_source"),
    projection_hash: z.null(),
    replay_address: z.null(),
    replay_pins: z.null(),
    source_artifact_content_hash: nullableHash,
    source_blocked_reason: z.null(),
    source_dependency_hash: z.null(),
    source_rule_version: nonEmptyString.nullable(),
    source_schema_version: nonEmptyString.nullable(),
    worker_validation_receipt_hash: nullableHash,
    worker_validation_receipt_ref: workerReceiptRef.nullable(),
  })
  .strict();

const packetSchema = z.discriminatedUnion("availability", [
  availablePacket,
  sourceBlockedPacket,
  artifactMissingPacket,
  invalidSourcePacket,
]);

type Fraction = Readonly<{ denominator: bigint; numerator: bigint }>;

function contractError(detail: string): TypeError {
  return new TypeError(`contract_error: confidence ledger ${detail}`);
}

function ownerPacketSchema(
  packet: ConfidenceLedgerRiskSpendPacket,
): ConfidenceLedgerOwnerPacketSchema {
  switch (packet.availability) {
    case "available":
      return "AvailableConfidenceLedgerRiskSpendPacket";
    case "source_blocked":
      return "SourceBlockedConfidenceLedgerRiskSpendPacket";
    case "artifact_missing":
      return "ArtifactMissingConfidenceLedgerRiskSpendPacket";
    case "invalid_source":
      return "InvalidConfidenceLedgerRiskSpendPacket";
  }
}

type OwnerLiteralPathValues = Readonly<{
  matched: boolean;
  values: readonly unknown[];
}>;

function valuesAtOwnerLiteralPath(
  value: unknown,
  segments: readonly string[],
): OwnerLiteralPathValues {
  if (segments.length === 0) return { matched: true, values: [value] };
  const [segment, ...remaining] = segments;
  if (segment === "*") {
    const children = Array.isArray(value)
      ? value
      : typeof value === "object" && value !== null
        ? Object.values(value)
        : null;
    if (children === null) return { matched: false, values: [] };
    const nested = children.map((item) =>
      valuesAtOwnerLiteralPath(item, remaining),
    );
    return {
      matched: nested.every((result) => result.matched),
      values: nested.flatMap((result) => result.values),
    };
  }
  if (typeof value !== "object" || value === null || !(segment in value)) {
    return { matched: false, values: [] };
  }
  return valuesAtOwnerLiteralPath(
    (value as Record<string, unknown>)[segment],
    remaining,
  );
}

function verifyGeneratedOwnerLiterals(
  packet: ConfidenceLedgerRiskSpendPacket,
): void {
  const rootSchema = ownerPacketSchema(packet);
  for (const rule of CONFIDENCE_LEDGER_OWNER_LITERAL_RULES) {
    if (rule.rootSchema !== rootSchema) continue;
    const result = valuesAtOwnerLiteralPath(
      packet,
      rule.path.split("/").filter(Boolean),
    );
    assertCondition(
      result.matched &&
        result.values.every((value) => Object.is(value, rule.value)),
      `generated owner literal mismatch at ${rootSchema}${rule.path}`,
    );
  }
}

function greatestCommonDivisor(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left;
  let b = right < 0n ? -right : right;
  while (b !== 0n) {
    [a, b] = [b, a % b];
  }
  return a;
}

function fraction(value: { denominator: number; numerator: number }): Fraction {
  const numerator = BigInt(value.numerator);
  const denominator = BigInt(value.denominator);
  const divisor = greatestCommonDivisor(numerator, denominator);
  return Object.freeze({
    denominator: denominator / divisor,
    numerator: numerator / divisor,
  });
}

function add(left: Fraction, right: Fraction): Fraction {
  const numerator =
    left.numerator * right.denominator + right.numerator * left.denominator;
  const denominator = left.denominator * right.denominator;
  const divisor = greatestCommonDivisor(numerator, denominator);
  return {
    denominator: denominator / divisor,
    numerator: numerator / divisor,
  };
}

function subtract(left: Fraction, right: Fraction): Fraction {
  const numerator =
    left.numerator * right.denominator - right.numerator * left.denominator;
  const denominator = left.denominator * right.denominator;
  const divisor = greatestCommonDivisor(numerator, denominator);
  return {
    denominator: denominator / divisor,
    numerator: numerator / divisor,
  };
}

function multiply(left: Fraction, right: Fraction): Fraction {
  const numerator = left.numerator * right.numerator;
  const denominator = left.denominator * right.denominator;
  const divisor = greatestCommonDivisor(numerator, denominator);
  return {
    denominator: denominator / divisor,
    numerator: numerator / divisor,
  };
}

function divideByInteger(value: Fraction, divisor: number): Fraction {
  return multiply(value, { denominator: BigInt(divisor), numerator: 1n });
}

function equalFraction(left: Fraction, right: Fraction): boolean {
  return (
    left.numerator === right.numerator && left.denominator === right.denominator
  );
}

function nonnegative(value: Fraction): Fraction {
  return value.numerator < 0n ? { denominator: 1n, numerator: 0n } : value;
}

function exactDecimal(value: Fraction): string {
  assertCondition(
    value.denominator > 0n &&
      value.denominator <= BigInt(CONFIDENCE_LEDGER_MAX_RATIONAL_DENOMINATOR),
    "exact decimal denominator exceeds arithmetic cap",
  );
  const whole = value.numerator / value.denominator;
  let remainder = value.numerator % value.denominator;
  if (remainder === 0n) return whole.toString();
  const digits: string[] = [];
  const seen = new Map<bigint, number>();
  while (remainder !== 0n && !seen.has(remainder)) {
    seen.set(remainder, digits.length);
    remainder *= 10n;
    digits.push((remainder / value.denominator).toString());
    remainder %= value.denominator;
  }
  if (remainder === 0n) {
    const decimal = `${whole}.${digits.join("")}`;
    assertCondition(
      decimal.length <= CONFIDENCE_LEDGER_MAX_EXACT_DECIMAL_CODE_UNITS,
      "exact decimal output exceeds arithmetic cap",
    );
    return decimal;
  }
  const repeatAt = seen.get(remainder);
  if (repeatAt === undefined)
    throw contractError("decimal recomputation failed");
  const decimal = `${whole}.${digits.slice(0, repeatAt).join("")}(${digits.slice(repeatAt).join("")})`;
  assertCondition(
    decimal.length <= CONFIDENCE_LEDGER_MAX_EXACT_DECIMAL_CODE_UNITS,
    "exact decimal output exceeds arithmetic cap",
  );
  return decimal;
}

function canonicalJson(value: unknown): string {
  if (
    value === null ||
    typeof value === "boolean" ||
    typeof value === "number"
  ) {
    return JSON.stringify(value);
  }
  if (typeof value === "string") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record)
      .filter((key) => record[key] !== undefined)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`)
      .join(",")}}`;
  }
  throw contractError("canonical JSON contains an unsupported value");
}

async function fingerprint(value: unknown): Promise<string> {
  const bytes = new TextEncoder().encode(canonicalJson(value));
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    Uint8Array.from(bytes).buffer,
  );
  return `sha256:${[...new Uint8Array(digest)]
    .map((item) => item.toString(16).padStart(2, "0"))
    .join("")}`;
}

function withoutKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value).filter(([key]) => !keys.includes(key)),
  );
}

function assertCondition(
  condition: boolean,
  detail: string,
): asserts condition {
  if (!condition) throw contractError(detail);
}

function assertSameFraction(
  observed: { denominator: number; numerator: number },
  expected: Fraction,
  detail: string,
): void {
  assertCondition(equalFraction(fraction(observed), expected), detail);
}

async function verifyAmount(
  amount: ConditionalDeltaAmount,
  packet: StrictAvailablePacket,
): Promise<void> {
  const value = fraction(amount.amount);
  assertCondition(
    amount.rational_display === `${value.numerator}/${value.denominator}` &&
      amount.canonical_decimal === exactDecimal(value),
    "conditional amount display mismatch",
  );
  assertCondition(
    amount.scope_id === packet.payload.scope_id &&
      amount.owner_scope_key === packet.payload.owner_scope_key &&
      amount.coverage_envelope_ref === packet.payload.coverage_envelope_ref &&
      amount.coverage_envelope_hash ===
        packet.payload.coverage_envelope.envelope_hash &&
      amount.declared_set_rider ===
        packet.payload.coverage_envelope.declared_set_rider &&
      amount.locality_rider === packet.payload.coverage_envelope.locality_rider,
    "conditional amount scope binding mismatch",
  );
  const expectedClassesHash = await fingerprint(
    packet.payload.coverage_envelope.declared_obligation_classes,
  );
  assertCondition(
    amount.declared_obligation_classes_hash === expectedClassesHash,
    "conditional amount obligation hash mismatch",
  );
  const body = withoutKeys(amount as unknown as Record<string, unknown>, [
    "amount_hash",
  ]);
  assertCondition(
    amount.amount_hash === (await fingerprint(body)),
    "conditional amount hash mismatch",
  );
}

async function verifyPacketIdentity(
  packet: StrictAvailablePacket | StrictSourceBlockedPacket,
): Promise<void> {
  const semanticProjection = structuredClone(
    packet as unknown as Record<string, unknown>,
  );
  delete semanticProjection.projection_hash;
  delete semanticProjection.replay_address;
  delete semanticProjection.replay_pins;
  const semanticFreshness = semanticProjection.freshness;
  if (
    typeof semanticFreshness === "object" &&
    semanticFreshness !== null &&
    !Array.isArray(semanticFreshness)
  ) {
    delete (semanticFreshness as Record<string, unknown>).observed_at;
  }
  const recomputedPacketHash = await fingerprint(semanticProjection);
  assertCondition(
    packet.projection_hash === recomputedPacketHash &&
      packet.replay_pins.projection_hash === recomputedPacketHash,
    "packet projection hash mismatch",
  );
  const replayQuery = new URLSearchParams({
    artifact_content_hash: packet.replay_pins.artifact_content_hash,
    projection_hash: packet.replay_pins.projection_hash,
    projection_rule_version: packet.replay_pins.projection_rule_version,
    source_as_of: packet.replay_pins.source_as_of,
    source_dependency_hash: packet.replay_pins.source_dependency_hash,
  });
  assertCondition(
    packet.replay_address ===
      `${packet.stable_address}?${replayQuery.toString()}`,
    "packet replay address mismatch",
  );
}

function verifyAccounting(
  accounting: {
    allocation: ConditionalDeltaAmount;
    overspend_amount: ConditionalDeltaAmount;
    remaining: ConditionalDeltaAmount;
    spent: ConditionalDeltaAmount;
  },
  detail: string,
): void {
  const allocation = fraction(accounting.allocation.amount);
  const spent = fraction(accounting.spent.amount);
  assertSameFraction(
    accounting.remaining.amount,
    nonnegative(subtract(allocation, spent)),
    `${detail} accounting remaining mismatch`,
  );
  assertSameFraction(
    accounting.overspend_amount.amount,
    nonnegative(subtract(spent, allocation)),
    `${detail} accounting overspend mismatch`,
  );
}

type InstrumentBlockerValue = z.infer<typeof instrumentBlocker>;

function compareText(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

function lessThanOrEqual(left: Fraction, right: Fraction): boolean {
  return (
    left.numerator * right.denominator <= right.numerator * left.denominator
  );
}

function uniqueMap<T>(
  rows: readonly T[],
  keyOf: (row: T) => string,
  detail: string,
): Map<string, T> {
  const result = new Map<string, T>();
  for (const row of rows) {
    const key = keyOf(row);
    assertCondition(!result.has(key), `${detail} duplicate ${key}`);
    result.set(key, row);
  }
  return result;
}

function requiredMapValue<T>(
  values: ReadonlyMap<string, T>,
  key: string,
  detail: string,
): T {
  const value = values.get(key);
  assertCondition(value !== undefined, `${detail} missing ${key}`);
  return value;
}

function deriveInstrumentBlocker(
  profileRefusal: string | null,
  rawRefusal: string | null,
): InstrumentBlockerValue | null {
  const profile = nullableInstrumentBlocker.safeParse(profileRefusal);
  assertCondition(profile.success, "recursive basis profile blocker mismatch");
  const raw = rawRefusalCode.safeParse(rawRefusal);
  assertCondition(raw.success, "recursive basis runtime blocker mismatch");
  if (profile.data !== null) return profile.data;
  return raw.data === null ? null : "other_runtime_refusal";
}

function verifyDerivedAmount(
  amount: ConditionalDeltaAmount,
  expected: Fraction,
  semanticRole: string,
  obligation: PromotionObligationClass | null,
  detail: string,
): void {
  assertSameFraction(amount.amount, expected, `${detail} amount mismatch`);
  assertCondition(
    amount.semantic_role === semanticRole &&
      amount.obligation_class === obligation,
    `${detail} semantic binding mismatch`,
  );
}

async function verifyOwnerDerivedCoverageArm(
  body: StrictAvailablePacket["payload"],
): Promise<void> {
  const envelope = body.coverage_envelope;
  const witnessRefs = envelope.witness_refs;
  assertCondition(
    new Set(witnessRefs).size === witnessRefs.length,
    "coverage witness references are duplicated",
  );
  const expectedAssessment =
    witnessRefs.length === 0 ? "open_world_unresolved" : "known_incomplete";
  const expectedReasons = [
    witnessRefs.length === 0
      ? "DS17-COVERAGE-OPEN-WORLD"
      : "DS17-COVERAGE-KNOWN-INCOMPLETE",
    "DS17-COVERAGE-SEARCH-NOT-ESTABLISHED",
    "DS17-COVERAGE-EXCLUSIONS-NOT-ESTABLISHED",
    "DS17-COVERAGE-INDEPENDENCE-MISSING",
  ];
  const expectedTtl =
    witnessRefs.length === 0
      ? "not_issued_open_world_unresolved"
      : "not_issued_known_incomplete";
  assertCondition(
    envelope.assessment === expectedAssessment &&
      body.coverage_assessment === expectedAssessment &&
      canonicalJson(envelope.reason_codes) === canonicalJson(expectedReasons) &&
      envelope.ttl_state === expectedTtl,
    "coverage negative arm is not owner-derived",
  );

  const expectedSources = [
    {
      admission_state: "canonical_registry_validated",
      availability_state: "available_typed_input",
      content_hash: body.registry_content_hash,
      source_ref: "architecture/production_quality/confidence_ledger.toml",
      source_role: "canonical_registry",
      verifier_ref:
        "polisyos.runtime.quality.confidence_ledger.load_confidence_ledger_registry",
    },
    {
      admission_state: "worker_admission_not_established",
      availability_state: "available_typed_input",
      content_hash: body.source_projection_hash,
      source_ref:
        "architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json#real_ledger_projection",
      source_role: "semantic_ledger",
      verifier_ref:
        "tools.quality.validation.check_layer3_gy_confidence_ledger:validate_payload",
    },
  ];
  assertCondition(
    canonicalJson(envelope.source_identities) ===
      canonicalJson(expectedSources) &&
      canonicalJson(body.source_provenance) === canonicalJson(expectedSources),
    "coverage source identity tuple mismatch",
  );

  const registry = body.registry_basis;
  const semantic = body.semantic_ledger_basis;
  assertCondition(
    canonicalJson(envelope.delta) === canonicalJson(registry.policy.delta) &&
      canonicalJson(envelope.declared_scope) ===
        canonicalJson(body.risk_scope) &&
      envelope.authority_purpose === body.risk_scope.authority_purpose &&
      canonicalJson(envelope.maintained_assumptions) ===
        canonicalJson(semantic.maintained_assumptions) &&
      envelope.obligation_language_version === registry.schema_version &&
      envelope.obligation_schema_ref ===
        (body.risk_scope.schema_ref ?? registry.schema_version) &&
      envelope.obligation_rule_ref ===
        (body.risk_scope.rule_ref ?? envelope.rule_version),
    "coverage owner basis tuple mismatch",
  );
  const expectedAssessmentKey = await fingerprint({
    owner_scope_key: envelope.owner_scope_key,
    protected_action_id: envelope.protected_action_id,
    rule_version: envelope.rule_version,
    scope_id: envelope.scope_id,
    sources: expectedSources,
  });
  assertCondition(
    envelope.assessment_key === expectedAssessmentKey,
    "coverage assessment key mismatch",
  );
}

async function verifyRecursiveProjectionBasis(
  body: StrictAvailablePacket["payload"],
): Promise<void> {
  const registry = body.registry_basis;
  const semantic = body.semantic_ledger_basis;
  const profiles = uniqueMap(
    registry.proof_profiles,
    (row) => row.profile_id,
    "recursive basis proof profile",
  );
  const definitions = uniqueMap(
    registry.instruments,
    (row) => row.instrument_id,
    "recursive basis instrument",
  );
  const routes = uniqueMap(
    registry.certificate_class_routes,
    (row) => row.certificate_class,
    "recursive basis certificate route",
  );

  assertCondition(
    equalFraction(
      fraction(semantic.budget_delta),
      fraction(registry.policy.delta),
    ) &&
      semantic.budget_delta_decimal ===
        exactDecimal(fraction(registry.policy.delta)),
    "recursive basis budget mismatch",
  );
  for (const check of semantic.checks) {
    assertCondition(
      check.spend_decimal === exactDecimal(fraction(check.spend)),
      "recursive basis check spend display mismatch",
    );
  }

  assertCondition(
    body.instrument_definitions.length === registry.instruments.length,
    "recursive basis definition count mismatch",
  );
  for (const [index, definition] of registry.instruments.entries()) {
    const profile = requiredMapValue(
      profiles,
      definition.proof_profile_id,
      "recursive basis proof profile",
    );
    const expected = {
      anytime_valid: profile.anytime_valid,
      blocker: profile.refusal_code,
      certificate_roles: definition.certificate_roles,
      deterministic: profile.deterministic,
      guarantee_kind: profile.guarantee_kind,
      instrument_family: definition.instrument_family,
      instrument_id: definition.instrument_id,
      permits_obligation_satisfaction: profile.permits_obligation_satisfaction,
      proof_kernel_id: profile.proof_kernel_id,
      proof_profile_id: profile.profile_id,
    };
    assertCondition(
      canonicalJson(body.instrument_definitions[index]) ===
        canonicalJson(expected),
      "recursive basis instrument definition mismatch",
    );
  }

  assertCondition(
    body.certificate_routes.length === registry.certificate_class_routes.length,
    "recursive basis route count mismatch",
  );
  for (const [index, route] of registry.certificate_class_routes.entries()) {
    const definition = requiredMapValue(
      definitions,
      route.instrument_id,
      "recursive basis route instrument",
    );
    const profile = requiredMapValue(
      profiles,
      definition.proof_profile_id,
      "recursive basis route profile",
    );
    const expectedBody = {
      anytime_valid: profile.anytime_valid,
      blocker: profile.refusal_code,
      certificate_class: route.certificate_class,
      certificate_role: route.certificate_role,
      claim_polarity: route.claim_polarity,
      deterministic: profile.deterministic,
      guarantee_kind: profile.guarantee_kind,
      instrument_family: definition.instrument_family,
      instrument_id: route.instrument_id,
      obligation_class: route.obligation_class,
      owner_ref: route.owner_ref,
      permits_obligation_satisfaction: profile.permits_obligation_satisfaction,
      proof_kernel_id: profile.proof_kernel_id,
      proof_profile_id: profile.profile_id,
      registry_content_hash: body.registry_content_hash,
      verifier_kernel_id: route.verifier_kernel_id,
      verifier_ref: route.verifier_ref,
    };
    const observed = body.certificate_routes[index];
    assertCondition(
      canonicalJson(
        withoutKeys(observed as unknown as Record<string, unknown>, [
          "route_binding_hash",
        ]),
      ) === canonicalJson(expectedBody) &&
        observed.route_binding_hash === (await fingerprint(expectedBody)),
      "recursive basis certificate route mismatch",
    );
  }

  const expectedInstances: Array<Record<string, unknown>> = [];
  const expectedRefusals: string[] = [];
  const expectedAcquisitions: string[] = [];
  const expectedConformance: string[] = [];
  const expectedBlockers: InstrumentBlockerValue[] = [];
  const grouped = new Map<
    string,
    {
      instrumentId: string;
      obligation: PromotionObligationClass;
      spend: Fraction;
    }
  >();
  for (const check of semantic.checks) {
    const definition = requiredMapValue(
      definitions,
      check.instrument_id,
      "recursive basis check instrument",
    );
    const profile = requiredMapValue(
      profiles,
      definition.proof_profile_id,
      "recursive basis check profile",
    );
    assertCondition(
      check.instrument_family === definition.instrument_family &&
        check.proof_profile_id === profile.profile_id &&
        definition.certificate_roles.includes(check.certificate_role),
      "recursive basis check registry binding mismatch",
    );
    const certificateClass = check.certificate_class ?? null;
    let routeRef: string | null = null;
    if (certificateClass !== null) {
      const route = requiredMapValue(
        routes,
        certificateClass,
        "recursive basis check route",
      );
      assertCondition(
        route.instrument_id === check.instrument_id &&
          route.obligation_class === check.obligation_class &&
          route.certificate_role === check.certificate_role,
        "recursive basis check route binding mismatch",
      );
      routeRef = route.verifier_ref;
    }
    const rawRefusal = check.refusal_code ?? null;
    const blocker = deriveInstrumentBlocker(
      profile.refusal_code ?? null,
      rawRefusal,
    );
    if (blocker !== null && !expectedBlockers.includes(blocker)) {
      expectedBlockers.push(blocker);
    }
    const eligible =
      check.certificate_role === "promotion" &&
      check.execution_status === "executed" &&
      check.outcome === "supported" &&
      profile.anytime_valid &&
      profile.permits_obligation_satisfaction &&
      check.supports_obligation &&
      blocker === null;
    expectedInstances.push({
      anytime_valid: profile.anytime_valid,
      blocker,
      certificate_class: certificateClass,
      certificate_ref: check.certificate_ref,
      certificate_role: check.certificate_role,
      certificate_route_ref: routeRef,
      eligible_for_promotion: eligible,
      execution_status: check.execution_status,
      instance_ref: check.request_key,
      instrument_family: definition.instrument_family,
      instrument_id: check.instrument_id,
      obligation_class: check.obligation_class,
      outcome: check.outcome,
      proof_profile_id: profile.profile_id,
      raw_runtime_refusal_source: rawRefusal,
      supports_obligation: check.supports_obligation,
    });
    const groupedKey = JSON.stringify([
      check.obligation_class,
      check.instrument_id,
    ]);
    const existing = grouped.get(groupedKey);
    if (existing === undefined) {
      grouped.set(groupedKey, {
        instrumentId: check.instrument_id,
        obligation: check.obligation_class,
        spend: fraction(check.spend),
      });
    } else {
      existing.spend = add(existing.spend, fraction(check.spend));
    }
    if (check.certificate_role === "refusal") {
      expectedRefusals.push(check.request_key);
    } else if (check.certificate_role === "acquisition") {
      expectedAcquisitions.push(check.request_key);
    } else if (check.certificate_role === "promotion_conformance") {
      expectedConformance.push(check.request_key);
    }
  }

  assertCondition(
    body.instrument_instances.length === expectedInstances.length,
    "recursive basis instance count mismatch",
  );
  body.instrument_instances.forEach((instance, index) => {
    assertCondition(
      canonicalJson(
        withoutKeys(instance as unknown as Record<string, unknown>, ["spend"]),
      ) === canonicalJson(expectedInstances[index]),
      "recursive basis instance row mismatch",
    );
    const check = semantic.checks[index];
    verifyDerivedAmount(
      instance.spend,
      fraction(check.spend),
      `instrument_instance_spend:${check.request_key}`,
      check.obligation_class,
      "recursive basis instance spend",
    );
  });
  assertCondition(
    canonicalJson(body.refusal_instance_refs) ===
      canonicalJson(expectedRefusals) &&
      canonicalJson(body.acquisition_instance_refs) ===
        canonicalJson(expectedAcquisitions) &&
      canonicalJson(body.conformance_instance_refs) ===
        canonicalJson(expectedConformance) &&
      canonicalJson(body.instrument_blockers) ===
        canonicalJson(expectedBlockers),
    "recursive basis role or blocker rows mismatch",
  );

  const expectedGrouped = [...grouped.values()].sort(
    (left, right) =>
      compareText(left.obligation, right.obligation) ||
      compareText(left.instrumentId, right.instrumentId),
  );
  assertCondition(
    body.grouped_spend.length === expectedGrouped.length,
    "recursive basis grouped spend count mismatch",
  );
  body.grouped_spend.forEach((row, index) => {
    const expected = expectedGrouped[index];
    assertCondition(
      row.obligation_class === expected.obligation &&
        row.instrument_id === expected.instrumentId,
      "recursive basis grouped spend identity mismatch",
    );
    verifyDerivedAmount(
      row.spend,
      expected.spend,
      `grouped_spend:${expected.obligation}:${expected.instrumentId}`,
      expected.obligation,
      "recursive basis grouped spend",
    );
  });

  for (const row of body.obligation_class_risk_spend) {
    const matching = semantic.checks.filter(
      (check) => check.obligation_class === row.obligation_class,
    );
    const spent = matching.reduce(
      (total, check) => add(total, fraction(check.spend)),
      { denominator: 1n, numerator: 0n },
    );
    const allocation = fraction(row.allocation.amount);
    verifyDerivedAmount(
      row.allocation,
      allocation,
      "obligation_class_allocation",
      row.obligation_class,
      "recursive basis class allocation",
    );
    verifyDerivedAmount(
      row.spent,
      spent,
      "obligation_class_spent",
      row.obligation_class,
      "recursive basis class spend",
    );
    verifyDerivedAmount(
      row.remaining,
      nonnegative(subtract(allocation, spent)),
      "obligation_class_remaining",
      row.obligation_class,
      "recursive basis class remaining",
    );
    verifyDerivedAmount(
      row.overspend_amount,
      nonnegative(subtract(spent, allocation)),
      "obligation_class_overspend",
      row.obligation_class,
      "recursive basis class overspend",
    );
    const instrumentRefs = [
      ...new Set(matching.map((check) => check.instrument_id)),
    ].sort(compareText);
    assertCondition(
      canonicalJson(row.instrument_refs) === canonicalJson(instrumentRefs) &&
        canonicalJson(row.check_refs) ===
          canonicalJson(matching.map((check) => check.request_key)) &&
        canonicalJson(row.good_event_refs) ===
          canonicalJson(
            matching.flatMap((check) =>
              check.good_event_id === null ? [] : [check.good_event_id],
            ),
          ),
      "recursive basis class reference rows mismatch",
    );
  }

  const total = semantic.checks.reduce(
    (sum, check) => add(sum, fraction(check.spend)),
    { denominator: 1n, numerator: 0n },
  );
  const delta = fraction(registry.policy.delta);
  assertCondition(
    equalFraction(fraction(semantic.total_spend), total) &&
      semantic.total_spend_decimal === exactDecimal(total) &&
      semantic.within_budget === lessThanOrEqual(total, delta),
    "recursive basis semantic total mismatch",
  );
  verifyDerivedAmount(
    body.total_spend,
    total,
    "scope_total_spend",
    null,
    "recursive basis total spend",
  );
  verifyDerivedAmount(
    body.scope_total_risk_spend.allocation,
    delta,
    "scope_total_allocation",
    null,
    "recursive basis scope allocation",
  );
  verifyDerivedAmount(
    body.scope_total_risk_spend.spent,
    total,
    "scope_total_spend",
    null,
    "recursive basis scope spend",
  );
  verifyDerivedAmount(
    body.scope_total_risk_spend.remaining,
    nonnegative(subtract(delta, total)),
    "scope_total_remaining",
    null,
    "recursive basis scope remaining",
  );
  verifyDerivedAmount(
    body.scope_total_risk_spend.overspend_amount,
    nonnegative(subtract(total, delta)),
    "scope_total_overspend",
    null,
    "recursive basis scope overspend",
  );
  assertCondition(
    canonicalJson(body.total_spend) ===
      canonicalJson(body.scope_total_risk_spend.spent) &&
      body.budget_posture ===
        (lessThanOrEqual(total, delta) ? "within_budget" : "over_spend"),
    "recursive basis scope total alias mismatch",
  );

  const positiveBlockers = [
    {
      slot: "coverage_assessment",
      value: body.coverage_envelope.assessment,
    },
    ...expectedBlockers.map((blocker) => ({
      slot: "instrument_blocker",
      value: blocker,
    })),
    {
      slot: "appointment_posture",
      value: "institutional_authority_unappointed",
    },
  ];
  const expectedGoodEvents = semantic.checks.flatMap((check) =>
    !check.deterministic_proof &&
    check.execution_status === "executed" &&
    check.good_event_id !== null
      ? [check.good_event_id]
      : [],
  );
  assertCondition(
    canonicalJson(body.positive_register.blockers) ===
      canonicalJson(positiveBlockers) &&
      body.good_event_posture.good_event_clause ===
        semantic.good_event_clause &&
      canonicalJson(
        body.good_event_posture.executed_probabilistic_good_event_refs,
      ) === canonicalJson(expectedGoodEvents) &&
      canonicalJson(body.source_provenance) ===
        canonicalJson(body.coverage_envelope.source_identities),
    "recursive basis positive, good-event, or provenance mismatch",
  );
}

async function verifyAvailable(packet: StrictAvailablePacket): Promise<void> {
  const { payload: body } = packet;
  await verifyOwnerDerivedCoverageArm(body);
  assertCondition(
    body.scope_id === body.coverage_envelope.scope_id &&
      body.scope_id === body.semantic_ledger_basis.scope_id &&
      body.owner_scope_key === body.coverage_envelope.owner_scope_key &&
      body.owner_scope_key === body.risk_scope.owner_scope_key &&
      canonicalJson(body.risk_scope) ===
        canonicalJson(body.coverage_envelope.declared_scope) &&
      canonicalJson(body.risk_scope) ===
        canonicalJson(body.semantic_ledger_basis.risk_scope),
    "multiple or cross-bound confidence scopes",
  );
  assertCondition(
    body.coverage_envelope_ref === body.coverage_envelope.envelope_ref &&
      body.coverage_envelope.envelope_ref ===
        `coverage-envelope:${body.coverage_envelope.envelope_hash}` &&
      body.coverage_assessment === body.coverage_envelope.assessment,
    "coverage envelope binding mismatch",
  );
  const envelopeBody = withoutKeys(
    body.coverage_envelope as unknown as Record<string, unknown>,
    ["envelope_hash", "envelope_ref"],
  );
  assertCondition(
    body.coverage_envelope.envelope_hash === (await fingerprint(envelopeBody)),
    "coverage envelope hash mismatch",
  );

  const flattenedClasses = body.registry_basis.obligation_pools.flatMap(
    (pool) => pool.obligation_classes,
  );
  assertCondition(
    canonicalJson(flattenedClasses) ===
      canonicalJson(CONFIDENCE_LEDGER_OBLIGATION_ORDER) &&
      canonicalJson(body.coverage_envelope.declared_obligation_classes) ===
        canonicalJson(CONFIDENCE_LEDGER_OBLIGATION_ORDER) &&
      canonicalJson(
        body.obligation_class_risk_spend.map((row) => row.obligation_class),
      ) === canonicalJson(CONFIDENCE_LEDGER_OBLIGATION_ORDER),
    "obligation denominator order mismatch",
  );
  const poolWeight = body.registry_basis.obligation_pools.reduce(
    (total, pool) => add(total, fraction(pool.weight)),
    { denominator: 1n, numerator: 0n },
  );
  assertCondition(
    equalFraction(poolWeight, { denominator: 1n, numerator: 1n }),
    "obligation pool weights do not sum to one",
  );
  const rowByClass = new Map(
    body.obligation_class_risk_spend.map((row) => [row.obligation_class, row]),
  );
  for (const pool of body.registry_basis.obligation_pools) {
    const expectedAllocation = divideByInteger(
      multiply(
        fraction(body.registry_basis.policy.delta),
        fraction(pool.weight),
      ),
      pool.obligation_classes.length,
    );
    for (const item of pool.obligation_classes) {
      const row = rowByClass.get(item);
      assertCondition(row !== undefined, "obligation class row missing");
      assertSameFraction(
        row.allocation.amount,
        expectedAllocation,
        "obligation class allocation mismatch",
      );
    }
  }

  const definitionIds = body.instrument_definitions.map(
    (row) => row.instrument_id,
  );
  const registryInstrumentIds = body.registry_basis.instruments.map(
    (row) => row.instrument_id,
  );
  assertCondition(
    canonicalJson(definitionIds) ===
      canonicalJson(CONFIDENCE_LEDGER_INSTRUMENT_ORDER) &&
      canonicalJson(registryInstrumentIds) ===
        canonicalJson(CONFIDENCE_LEDGER_INSTRUMENT_ORDER),
    "instrument denominator order mismatch",
  );
  const routeIds = body.certificate_routes.map((row) => row.certificate_class);
  const registryRouteIds = body.registry_basis.certificate_class_routes.map(
    (row) => row.certificate_class,
  );
  assertCondition(
    canonicalJson(routeIds) === canonicalJson(CONFIDENCE_LEDGER_ROUTE_ORDER) &&
      canonicalJson(registryRouteIds) ===
        canonicalJson(CONFIDENCE_LEDGER_ROUTE_ORDER) &&
      body.certificate_route_denominator_count === routeIds.length,
    "certificate route denominator order mismatch",
  );
  assertCondition(
    body.certificate_route_denominator_hash ===
      (await fingerprint(
        body.certificate_routes.map((row) => row.route_binding_hash),
      )),
    "certificate route denominator hash mismatch",
  );

  const actualRefs = [
    ...body.refusal_instance_refs,
    ...body.acquisition_instance_refs,
    ...body.conformance_instance_refs,
  ];
  assertCondition(
    new Set(actualRefs).size === actualRefs.length &&
      new Set(body.instrument_instances.map((row) => row.instance_ref)).size ===
        body.instrument_instances.length &&
      actualRefs.length === body.instrument_instances.length,
    "producer actual-row reference set mismatch",
  );
  const instanceByRef = new Map(
    body.instrument_instances.map((row) => [row.instance_ref, row]),
  );
  for (const ref of body.refusal_instance_refs) {
    assertCondition(
      instanceByRef.get(ref)?.certificate_role === "refusal",
      "producer refusal reference is unresolved",
    );
  }
  for (const ref of body.acquisition_instance_refs) {
    assertCondition(
      instanceByRef.get(ref)?.certificate_role === "acquisition",
      "producer acquisition reference is unresolved",
    );
  }
  for (const ref of body.conformance_instance_refs) {
    assertCondition(
      instanceByRef.get(ref)?.certificate_role === "promotion_conformance",
      "producer conformance reference is unresolved",
    );
  }

  verifyAccounting(body.scope_total_risk_spend, "scope");
  body.obligation_class_risk_spend.forEach((row) =>
    verifyAccounting(row, row.obligation_class),
  );
  assertSameFraction(
    body.scope_total_risk_spend.allocation.amount,
    fraction(body.registry_basis.policy.delta),
    "scope accounting allocation mismatch",
  );
  const classAllocation = body.obligation_class_risk_spend.reduce(
    (total, row) => add(total, fraction(row.allocation.amount)),
    { denominator: 1n, numerator: 0n },
  );
  const classSpent = body.obligation_class_risk_spend.reduce(
    (total, row) => add(total, fraction(row.spent.amount)),
    { denominator: 1n, numerator: 0n },
  );
  const groupedSpent = body.grouped_spend.reduce(
    (total, row) => add(total, fraction(row.spend.amount)),
    { denominator: 1n, numerator: 0n },
  );
  const instanceSpent = body.instrument_instances.reduce(
    (total, row) => add(total, fraction(row.spend.amount)),
    { denominator: 1n, numerator: 0n },
  );
  assertSameFraction(
    body.scope_total_risk_spend.allocation.amount,
    classAllocation,
    "scope accounting class allocation mismatch",
  );
  assertSameFraction(
    body.scope_total_risk_spend.spent.amount,
    classSpent,
    "scope accounting class spend mismatch",
  );
  assertCondition(
    equalFraction(classSpent, groupedSpent) &&
      equalFraction(groupedSpent, instanceSpent) &&
      equalFraction(classSpent, fraction(body.total_spend.amount)) &&
      equalFraction(
        classSpent,
        fraction(body.semantic_ledger_basis.total_spend),
      ),
    "scope accounting total spend mismatch",
  );
  assertCondition(
    lessThanOrEqual(
      fraction(body.semantic_ledger_basis.total_spend),
      fraction(body.registry_basis.policy.delta),
    ) &&
      body.semantic_ledger_basis.within_budget &&
      body.budget_posture === "within_budget" &&
      fraction(body.scope_total_risk_spend.overspend_amount.amount)
        .numerator === 0n,
    "available packet exceeds the owner budget",
  );

  const amounts: ConditionalDeltaAmount[] = [
    body.total_spend,
    body.scope_total_risk_spend.allocation,
    body.scope_total_risk_spend.spent,
    body.scope_total_risk_spend.remaining,
    body.scope_total_risk_spend.overspend_amount,
    ...body.obligation_class_risk_spend.flatMap((row) => [
      row.allocation,
      row.spent,
      row.remaining,
      row.overspend_amount,
    ]),
    ...body.grouped_spend.map((row) => row.spend),
    ...body.instrument_instances.map((row) => row.spend),
  ];
  await Promise.all(amounts.map((amount) => verifyAmount(amount, packet)));
  await verifyRecursiveProjectionBasis(body);

  assertCondition(
    body.positive_register.population_count ===
      body.positive_register.entries.length &&
      body.positive_register.population_count === 0 &&
      body.positive_register.verified_appointment_refs.length === 0,
    "positive register valid-zero mismatch",
  );
  assertCondition(
    body.registry_content_hash === packet.registry_content_hash &&
      body.registry_content_hash ===
        body.semantic_ledger_basis.registry_content_hash &&
      body.registry_content_hash ===
        body.coverage_envelope.source_identities[0].content_hash &&
      body.source_projection_hash ===
        body.semantic_ledger_basis.projection_hash &&
      body.source_projection_hash ===
        body.coverage_envelope.source_identities[1].content_hash &&
      packet.frozen_semantic_projection_hash ===
        body.semantic_ledger_basis.projection_hash,
    "source or registry hash binding mismatch",
  );
  assertCondition(
    body.registry_content_hash === (await fingerprint(body.registry_basis)),
    "registry content hash mismatch",
  );
  const semanticBody = withoutKeys(
    body.semantic_ledger_basis as unknown as Record<string, unknown>,
    ["projection_hash"],
  );
  assertCondition(
    body.semantic_ledger_basis.projection_hash ===
      (await fingerprint(semanticBody)),
    "semantic projection hash mismatch",
  );
  const projectionBody = withoutKeys(
    body as unknown as Record<string, unknown>,
    ["projection_hash"],
  );
  const recomputedProjectionHash = await fingerprint(projectionBody);
  assertCondition(
    body.projection_hash === recomputedProjectionHash,
    `projection hash mismatch (${body.projection_hash} != ${recomputedProjectionHash})`,
  );
  assertCondition(
    packet.replay_pins.artifact_content_hash ===
      packet.source.artifact_content_hash &&
      packet.replay_pins.source_dependency_hash ===
        packet.source_dependency_hash &&
      packet.replay_pins.source_as_of === packet.as_of &&
      packet.freshness.source_as_of === packet.as_of &&
      packet.freshness.state === "observed" &&
      packet.source.validation.status === "passed" &&
      packet.source.validation.bound_artifact_content_hash ===
        packet.source.artifact_content_hash &&
      packet.source.validation.bound_dependency_aggregate_identity ===
        packet.source_dependency_hash &&
      packet.source.validation.registry_content_hash ===
        packet.registry_content_hash &&
      packet.source.validation.registry_projection_hash ===
        packet.registry_projection_hash &&
      packet.source.validation.frozen_semantic_projection_hash ===
        packet.frozen_semantic_projection_hash &&
      packet.source.validation.semantic_projection_hash ===
        packet.frozen_semantic_projection_hash &&
      packet.source.validation.recomputed_total_spend_denominator ===
        body.semantic_ledger_basis.total_spend.denominator &&
      packet.source.validation.recomputed_total_spend_numerator ===
        body.semantic_ledger_basis.total_spend.numerator &&
      packet.source.validation.registry_delta_denominator ===
        body.registry_basis.policy.delta.denominator &&
      packet.source.validation.registry_delta_numerator ===
        body.registry_basis.policy.delta.numerator &&
      packet.source.validation.worker_validation_receipt_hash ===
        packet.worker_validation_receipt_hash &&
      packet.worker_validation_receipt_ref ===
        `owner-validation:${packet.worker_validation_receipt_hash}`,
    "protected owner replay or validation binding mismatch",
  );
  await verifyPacketIdentity(packet);
}

async function admitPreflightedConfidenceLedgerRiskSpendPacket(
  candidate: unknown,
): Promise<ConfidenceLedgerRiskSpendPacket> {
  let parsed: ConfidenceLedgerRiskSpendPacket;
  try {
    parsed = packetSchema.parse(candidate) as ConfidenceLedgerRiskSpendPacket;
  } catch (error) {
    const detail =
      error instanceof Error ? error.message : "unknown schema error";
    throw contractError(`packet schema failure: ${detail}`);
  }
  verifyGeneratedOwnerLiterals(parsed);
  if (
    parsed.availability === "available" &&
    typeof candidate === "object" &&
    candidate !== null
  ) {
    const original = canonicalJson(
      (candidate as { payload?: unknown }).payload,
    );
    const normalized = canonicalJson(parsed.payload);
    if (original !== normalized) {
      let firstDifference = 0;
      while (
        firstDifference < original.length &&
        original[firstDifference] === normalized[firstDifference]
      ) {
        firstDifference += 1;
      }
      throw contractError(
        `schema normalization drift at ${firstDifference}: ${original.slice(firstDifference, firstDifference + 80)} != ${normalized.slice(firstDifference, firstDifference + 80)}`,
      );
    }
  }
  if (parsed.availability === "available") await verifyAvailable(parsed);
  if (parsed.availability === "source_blocked") {
    assertCondition(
      parsed.replay_pins.projection_hash === parsed.projection_hash &&
        parsed.replay_pins.artifact_content_hash ===
          parsed.source_artifact_content_hash &&
        parsed.replay_pins.source_dependency_hash ===
          parsed.source_dependency_hash &&
        parsed.replay_pins.source_as_of === parsed.as_of &&
        parsed.freshness.source_as_of === parsed.as_of &&
        parsed.freshness.state === "observed" &&
        parsed.source_schema_version ===
          "policyos.policy_design_case.layer3_gy.n11_confidence_ledger.v1" &&
        parsed.source_rule_version === null &&
        parsed.worker_validation_receipt_ref ===
          `owner-validation:${parsed.worker_validation_receipt_hash}`,
      "source-blocked replay binding mismatch",
    );
    await verifyPacketIdentity(parsed);
  }
  if (parsed.availability === "artifact_missing") {
    assertCondition(
      parsed.freshness.state === "artifact_missing" &&
        parsed.freshness.source_as_of === null,
      "artifact-missing freshness mismatch",
    );
  }
  if (parsed.availability === "invalid_source") {
    assertCondition(
      parsed.freshness.state === "invalid_source" &&
        ((parsed.worker_validation_receipt_ref === null &&
          parsed.worker_validation_receipt_hash === null) ||
          (parsed.worker_validation_receipt_ref !== null &&
            parsed.worker_validation_receipt_hash !== null &&
            parsed.worker_validation_receipt_ref ===
              `owner-validation:${parsed.worker_validation_receipt_hash}`)),
      "invalid-source receipt or freshness mismatch",
    );
  }
  return Object.freeze(parsed);
}

/** Strictly parse and independently recompute the specialized four-arm packet. */
export async function admitConfidenceLedgerRiskSpendPacket(
  candidate: unknown,
): Promise<ConfidenceLedgerRiskSpendPacket> {
  const preflight = admissionWorkWithinCaps(candidate);
  if (preflight.status === "unsupported") {
    throw contractError(preflight.detail);
  }
  return admitPreflightedConfidenceLedgerRiskSpendPacket(candidate);
}

export const CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA = [
  "promotion_authority",
  "publication_authority",
  "public_audience",
  "bounded_completeness",
  "world_completeness",
  "family_level_total",
  "sequence_level_total",
  "cross_scope_total",
  "narrowed_claim_satisfaction",
] as const;

export type ConfidenceLedgerProtectedQuery =
  (typeof CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA)[number];
export type ConfidenceLedgerProtectedAnswer = "denied" | "not_established";
export type ConfidenceLedgerSafetyBlockedReason =
  | "timeout"
  | "missing_input_or_incomplete_history"
  | "parser_or_schema_failure"
  | "unsupported_or_out_of_model"
  | "empty_consistency_set"
  | "model_observation_inconsistent"
  | "unproved_approximation";

/** Immutable ownership boundary for the exact captured transport body. */
export type ConfidenceLedgerCapturedResponseBytes = Readonly<{
  byteLength: number;
  copy: () => Uint8Array;
}>;

const CONFIDENCE_LEDGER_MAX_RESPONSE_BYTES = 262_144;
const CONFIDENCE_LEDGER_MAX_JSON_NODES = 32_768;
const CONFIDENCE_LEDGER_MAX_JSON_TEXT_CODE_UNITS = 262_144;
const CONFIDENCE_LEDGER_MAX_COLLECTION_ITEMS = 512;
const CONFIDENCE_LEDGER_MAX_OBJECT_FIELDS = 256;
const CONFIDENCE_LEDGER_MAX_JSON_DEPTH = 64;
const CONFIDENCE_LEDGER_SCHEMA_WORK_BOUND = 16 * 1024;
export const CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET = 1_400 * 1000;
const CONFIDENCE_LEDGER_MAX_EVALUATION_BUDGET =
  CONFIDENCE_LEDGER_LIVE_EVALUATION_BUDGET;

export type ConfidenceLedgerProtectedQueryEvaluation =
  | Readonly<{
      capturedResponseBytes: ConfidenceLedgerCapturedResponseBytes;
      packet: ConfidenceLedgerRiskSpendPacket;
      protectedQueries: Readonly<
        Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
      >;
      receipt: Readonly<{
        observation_basis: "candidate_and_captured_bytes_independently_admitted";
        packet_availability: ConfidenceLedgerRiskSpendPacket["availability"];
        packet_projection_hash: string | null;
        protected_query_count: 9;
        schema_version: "policyos.runtime.confidence_ledger_protected_query_evaluation.v1";
      }>;
      status: "exact";
    }>
  | Readonly<{
      reason: ConfidenceLedgerSafetyBlockedReason;
      status: "blocked";
    }>;

type ProtectedQueryEvaluationInput = Readonly<{
  evaluationMode: "exact_finite_schema" | "sampled_search";
  packetCandidate: unknown;
  rawPacketBytes: Uint8Array;
  stepBudget: number;
}>;

function blockedEvaluation(
  reason: ConfidenceLedgerSafetyBlockedReason,
): ConfidenceLedgerProtectedQueryEvaluation {
  return Object.freeze({ reason, status: "blocked" });
}

function packetSchemaVersion(candidate: unknown): string | null {
  if (typeof candidate !== "object" || candidate === null) return null;
  const version = (candidate as Record<string, unknown>).packet_schema_version;
  return typeof version === "string" ? version : null;
}

function isUint8Array(value: unknown): value is Uint8Array {
  return Object.prototype.toString.call(value) === "[object Uint8Array]";
}

function ownCapturedResponseBytes(
  value: unknown,
): ConfidenceLedgerCapturedResponseBytes | null {
  if (!isUint8Array(value)) return null;
  try {
    const owned = new Uint8Array(value);
    return Object.freeze({
      byteLength: owned.byteLength,
      copy: () => new Uint8Array(owned),
    });
  } catch {
    return null;
  }
}

type JsonWork = Readonly<{ nodeCount: number; textCodeUnits: number }>;
type RationalWork = Readonly<{
  periodUpperBound: number;
  rationalCount: number;
  workUnits: number;
}>;
type AdmissionWorkInspection =
  | Readonly<{ detail: string; status: "unsupported" }>
  | Readonly<{ json: JsonWork; rational: RationalWork; status: "supported" }>;

function jsonWorkWithinCaps(value: unknown): JsonWork | null {
  const seen = new WeakSet();
  let nodes = 0;
  let textCodeUnits = 0;
  const visit = (current: unknown, depth: number): boolean => {
    nodes += 1;
    if (nodes > CONFIDENCE_LEDGER_MAX_JSON_NODES) return false;
    if (depth > CONFIDENCE_LEDGER_MAX_JSON_DEPTH) return false;
    if (typeof current === "string") {
      textCodeUnits += current.length;
      return textCodeUnits <= CONFIDENCE_LEDGER_MAX_JSON_TEXT_CODE_UNITS;
    }
    if (current === null || typeof current !== "object") return true;
    if (seen.has(current)) return false;
    seen.add(current);
    if (Array.isArray(current)) {
      if (current.length > CONFIDENCE_LEDGER_MAX_COLLECTION_ITEMS) return false;
      return current.every((item) => visit(item, depth + 1));
    }
    const entries = Object.entries(current);
    if (entries.length > CONFIDENCE_LEDGER_MAX_OBJECT_FIELDS) return false;
    return entries.every(([key, item]) => {
      textCodeUnits += key.length;
      return (
        textCodeUnits <= CONFIDENCE_LEDGER_MAX_JSON_TEXT_CODE_UNITS &&
        visit(item, depth + 1)
      );
    });
  };
  return visit(value, 0)
    ? Object.freeze({ nodeCount: nodes, textCodeUnits })
    : null;
}

function rationalWorkWithinCaps(
  value: unknown,
): RationalWork | Readonly<{ detail: string }> {
  const seen = new WeakSet();
  let rationalCount = 0;
  let periodUpperBound = 0;
  let detail: string | null = null;
  const visit = (current: unknown): boolean => {
    if (current === null || typeof current !== "object") return true;
    if (seen.has(current)) {
      detail = "arithmetic input contains a repeated object reference";
      return false;
    }
    seen.add(current);
    if (Array.isArray(current)) return current.every(visit);
    const record = current as Record<string, unknown>;
    if ("denominator" in record && "numerator" in record) {
      const denominator = record.denominator;
      const numerator = record.numerator;
      if (
        typeof denominator !== "number" ||
        !Number.isFinite(denominator) ||
        !Number.isSafeInteger(denominator) ||
        denominator <= 0
      ) {
        detail = "arithmetic denominator is not a positive safe integer";
        return false;
      }
      if (denominator > CONFIDENCE_LEDGER_MAX_RATIONAL_DENOMINATOR) {
        detail = "arithmetic denominator exceeds the finite cap";
        return false;
      }
      if (
        typeof numerator !== "number" ||
        !Number.isFinite(numerator) ||
        !Number.isSafeInteger(numerator) ||
        numerator < 0
      ) {
        detail = "arithmetic numerator is not a nonnegative safe integer";
        return false;
      }
      if (numerator > CONFIDENCE_LEDGER_MAX_RATIONAL_NUMERATOR) {
        detail = "arithmetic numerator exceeds the finite cap";
        return false;
      }
      rationalCount += 1;
      periodUpperBound += denominator;
      if (rationalCount > CONFIDENCE_LEDGER_MAX_RATIONAL_COUNT) {
        detail = "aggregate rational cardinality exceeds the finite cap";
        return false;
      }
      if (
        periodUpperBound + rationalCount >
        CONFIDENCE_LEDGER_MAX_RATIONAL_PERIOD_WORK
      ) {
        detail = "aggregate rational work exceeds the finite cap";
        return false;
      }
      return true;
    }
    return Object.values(record).every(visit);
  };
  if (!visit(value)) {
    return Object.freeze({
      detail: detail ?? "arithmetic input exceeds the finite cap",
    });
  }
  return Object.freeze({
    periodUpperBound,
    rationalCount,
    workUnits: periodUpperBound + rationalCount,
  });
}

function admissionWorkWithinCaps(value: unknown): AdmissionWorkInspection {
  const json = jsonWorkWithinCaps(value);
  if (json === null) {
    return Object.freeze({
      detail: "packet exceeds finite JSON work caps",
      status: "unsupported" as const,
    });
  }
  const rational = rationalWorkWithinCaps(value);
  if ("detail" in rational) {
    return Object.freeze({
      detail: rational.detail,
      status: "unsupported" as const,
    });
  }
  return Object.freeze({ json, rational, status: "supported" as const });
}

function protectedAnswersFromPacket(
  packet: ConfidenceLedgerRiskSpendPacket,
): Readonly<
  Record<ConfidenceLedgerProtectedQuery, ConfidenceLedgerProtectedAnswer>
> {
  const packetDenials = new Set(packet.may_not_use_for);
  if (packet.availability !== "available") {
    return Object.freeze({
      promotion_authority: packetDenials.has("promotion_authority")
        ? "denied"
        : "not_established",
      publication_authority: packetDenials.has("publication_authority")
        ? "denied"
        : "not_established",
      public_audience: packetDenials.has("public_audience")
        ? "denied"
        : "not_established",
      bounded_completeness: packetDenials.has("bounded_completeness")
        ? "denied"
        : "not_established",
      world_completeness: "not_established",
      family_level_total: "not_established",
      sequence_level_total: "not_established",
      cross_scope_total: "not_established",
      narrowed_claim_satisfaction: "not_established",
    });
  }
  const envelopeDenials = new Set(
    packet.payload.coverage_envelope.may_not_use_for,
  );
  const hasLocalityRider =
    packet.payload.fixed_scope_disclosure ===
    packet.payload.coverage_envelope.locality_rider;
  return Object.freeze({
    promotion_authority:
      packetDenials.has("promotion_authority") ||
      confidenceLedgerPromotionBlockers(packet).length > 0
        ? "denied"
        : "not_established",
    publication_authority: packetDenials.has("publication_authority")
      ? "denied"
      : "not_established",
    public_audience: packetDenials.has("public_audience")
      ? "denied"
      : "not_established",
    bounded_completeness:
      packetDenials.has("bounded_completeness") ||
      envelopeDenials.has("bounded_completeness")
        ? "denied"
        : "not_established",
    world_completeness: envelopeDenials.has("world_completeness")
      ? "denied"
      : "not_established",
    family_level_total: hasLocalityRider ? "denied" : "not_established",
    sequence_level_total: hasLocalityRider ? "denied" : "not_established",
    cross_scope_total: hasLocalityRider ? "denied" : "not_established",
    narrowed_claim_satisfaction: hasLocalityRider
      ? "denied"
      : "not_established",
  });
}

/**
 * Reconcile the generated candidate with independently decoded captured bytes.
 *
 * This is a transport/query receipt, not an offline owner-provenance claim.
 */
export async function evaluateConfidenceLedgerProtectedQuery({
  evaluationMode,
  packetCandidate,
  rawPacketBytes,
  stepBudget,
}: ProtectedQueryEvaluationInput): Promise<ConfidenceLedgerProtectedQueryEvaluation> {
  const capturedResponseBytes = ownCapturedResponseBytes(rawPacketBytes);
  const ownedRawPacketBytes = capturedResponseBytes?.copy() ?? null;
  if (
    !Number.isFinite(stepBudget) ||
    !Number.isSafeInteger(stepBudget) ||
    stepBudget <= 0 ||
    stepBudget > CONFIDENCE_LEDGER_MAX_EVALUATION_BUDGET
  ) {
    return blockedEvaluation("timeout");
  }
  if (
    packetCandidate === null ||
    packetCandidate === undefined ||
    capturedResponseBytes === null ||
    ownedRawPacketBytes === null ||
    ownedRawPacketBytes.byteLength === 0
  ) {
    return blockedEvaluation("missing_input_or_incomplete_history");
  }
  if (evaluationMode !== "exact_finite_schema") {
    return blockedEvaluation("unproved_approximation");
  }
  if (ownedRawPacketBytes.byteLength > CONFIDENCE_LEDGER_MAX_RESPONSE_BYTES) {
    return blockedEvaluation("unsupported_or_out_of_model");
  }
  const minimumWorkBound =
    ownedRawPacketBytes.byteLength * 2 +
    CONFIDENCE_LEDGER_MAX_JSON_NODES * 2 +
    CONFIDENCE_LEDGER_SCHEMA_WORK_BOUND +
    CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.length;
  if (stepBudget < minimumWorkBound) return blockedEvaluation("timeout");

  const candidateVersion = packetSchemaVersion(packetCandidate);
  if (
    candidateVersion !== null &&
    candidateVersion !==
      "policyos.runtime.confidence_ledger_risk_spend_packet.v1"
  ) {
    return blockedEvaluation("unsupported_or_out_of_model");
  }
  const candidateAdmissionWork = admissionWorkWithinCaps(packetCandidate);
  if (candidateAdmissionWork.status === "unsupported") {
    return blockedEvaluation("unsupported_or_out_of_model");
  }
  const preDecodeWorkBound =
    ownedRawPacketBytes.byteLength * 2 +
    candidateAdmissionWork.json.nodeCount +
    candidateAdmissionWork.json.textCodeUnits +
    candidateAdmissionWork.rational.workUnits +
    CONFIDENCE_LEDGER_SCHEMA_WORK_BOUND * 2 +
    CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.length;
  if (stepBudget < preDecodeWorkBound) return blockedEvaluation("timeout");

  let rawCandidate: unknown;
  try {
    rawCandidate = JSON.parse(
      new TextDecoder("utf-8", { fatal: true }).decode(ownedRawPacketBytes),
    );
  } catch {
    return blockedEvaluation("parser_or_schema_failure");
  }
  const rawVersion = packetSchemaVersion(rawCandidate);
  if (
    rawVersion !== null &&
    rawVersion !== "policyos.runtime.confidence_ledger_risk_spend_packet.v1"
  ) {
    return blockedEvaluation("unsupported_or_out_of_model");
  }
  const capturedAdmissionWork = admissionWorkWithinCaps(rawCandidate);
  if (capturedAdmissionWork.status === "unsupported") {
    return blockedEvaluation("unsupported_or_out_of_model");
  }
  const completeWorkBound =
    ownedRawPacketBytes.byteLength * 2 +
    candidateAdmissionWork.json.nodeCount +
    candidateAdmissionWork.json.textCodeUnits +
    candidateAdmissionWork.rational.workUnits +
    capturedAdmissionWork.json.nodeCount +
    capturedAdmissionWork.json.textCodeUnits +
    capturedAdmissionWork.rational.workUnits +
    CONFIDENCE_LEDGER_SCHEMA_WORK_BOUND * 2 +
    CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA.length;
  if (stepBudget < completeWorkBound) return blockedEvaluation("timeout");

  let packet: ConfidenceLedgerRiskSpendPacket;
  let capturedPacket: ConfidenceLedgerRiskSpendPacket;
  try {
    [packet, capturedPacket] = await Promise.all([
      admitPreflightedConfidenceLedgerRiskSpendPacket(packetCandidate),
      admitPreflightedConfidenceLedgerRiskSpendPacket(rawCandidate),
    ]);
  } catch {
    return blockedEvaluation("parser_or_schema_failure");
  }
  if (canonicalJson(packet) !== canonicalJson(capturedPacket)) {
    return blockedEvaluation("empty_consistency_set");
  }
  const protectedQueries = protectedAnswersFromPacket(packet);
  if (
    canonicalJson(Object.keys(protectedQueries)) !==
    canonicalJson(CONFIDENCE_LEDGER_PROTECTED_QUERY_SCHEMA)
  ) {
    return blockedEvaluation("unsupported_or_out_of_model");
  }
  return Object.freeze({
    capturedResponseBytes,
    packet,
    protectedQueries,
    receipt: Object.freeze({
      observation_basis:
        "candidate_and_captured_bytes_independently_admitted" as const,
      packet_availability: packet.availability,
      packet_projection_hash: packet.projection_hash ?? null,
      protected_query_count: 9 as const,
      schema_version:
        "policyos.runtime.confidence_ledger_protected_query_evaluation.v1" as const,
    }),
    status: "exact" as const,
  });
}

/** Resolve visible actual rows solely through producer-authored role refs and order. */
export function orderedConfidenceLedgerActualRows(
  packet: ConfidenceLedgerRiskSpendPacket,
): readonly InstrumentInstanceRow[] {
  if (packet.availability !== "available") return [];
  const byRef = new Map(
    packet.payload.instrument_instances.map((row) => [row.instance_ref, row]),
  );
  return [
    ...packet.payload.refusal_instance_refs,
    ...packet.payload.acquisition_instance_refs,
  ].map((ref) => {
    const row = byRef.get(ref);
    if (row === undefined)
      throw contractError("producer actual-row reference missing");
    return row;
  });
}

/** Compose all load-bearing vetoes without inferring promotion from absence. */
export function confidenceLedgerPromotionBlockers(
  packet: ConfidenceLedgerRiskSpendPacket,
): readonly string[] {
  if (packet.availability !== "available") {
    return [`availability:${packet.availability}`];
  }
  const blockers = [
    `coverage:${packet.payload.coverage_assessment}`,
    `appointment:${packet.payload.appointment_posture}`,
    ...packet.payload.instrument_blockers.map((item) => `instrument:${item}`),
    ...packet.payload.instrument_definitions.flatMap((row) =>
      row.blocker === null
        ? []
        : [`definition:${row.instrument_id}:${row.blocker}`],
    ),
    ...packet.payload.certificate_routes.flatMap((row) =>
      row.blocker === null
        ? []
        : [`route:${row.certificate_class}:${row.blocker}`],
    ),
    ...packet.payload.instrument_instances.flatMap((row) =>
      row.blocker === null
        ? []
        : [`instance:${row.instance_ref}:${row.blocker}`],
    ),
  ];
  if (packet.payload.budget_posture === "over_spend") {
    blockers.push("budget:over_spend");
  }
  return Object.freeze([...new Set(blockers)]);
}
