import type { EvidenceArtifactRef } from "@/shared/lib/domain/evidence";

export type HTEArtifactRef = EvidenceArtifactRef & {
  artifact_id: string;
  kind: string;
  media_type: "application/json";
  manifest_profile_sha256: string;
};

export type HTEMethodFqn =
  | "causal.hte.causal_forest@2.0.0"
  | "causal.hte.double_ml@2.0.0"
  | "causal.hte.meta_learner@2.0.0"
  | "causal.hte.forest_dr@2.0.0";

export type HTEMethodProfileId =
  | "econml.causal_forest_dml.native_mean@2.0"
  | "econml.dml.point_only@2.0"
  | "econml.meta_learner.point_only@2.0"
  | "econml.forest_dr.native_mean@2.0";

type HTEGuarantee =
  | "candidate_point"
  | "backend_conditional_interval"
  | "population_sampling_coverage";

export type HTETargetRelationDisplay = {
  requested_scope_status: "declared" | "not_established";
  requested_scope: string | null;
  requested_guarantee_status: "declared" | "not_established";
  requested_guarantee: HTEGuarantee | null;
  computed_scope_status: "recomputed" | "not_established";
  computed_scope: "selected_evaluation_rows" | null;
  computed_guarantee_status: "computed" | "not_established";
  computed_guarantee: "candidate_point" | "backend_conditional_interval" | null;
  source_content_status: "content_bound" | "not_established";
  row_order_status: "recomputed" | "not_established";
  contrast_status: "recomputed" | "not_established";
  estimand_status: "recomputed" | "not_established";
  alpha_status: "recomputed" | "not_applicable" | "not_established";
  profile_status: "qualified" | "point_only" | "not_established";
  scope_disposition:
    | "satisfied"
    | "requested_claim_not_satisfied"
    | "not_established";
  guarantee_disposition:
    | "satisfied"
    | "requested_claim_not_satisfied"
    | "not_established";
  overall_disposition:
    | "satisfied"
    | "requested_claim_not_satisfied"
    | "not_established";
};

export type HTEResourceEvidenceDisplay = {
  owner_policy_ref: HTEArtifactRef;
  owner_policy_digest: string;
  owner_policy_schema_version:
    | "polisyos.runtime.observational_input_resource_policy.v4"
    | "polisyos.runtime.observational_input_resource_policy.v5";
  owner_policy_revision: "r4" | "r5";
  owner_policy_method_fqn: HTEMethodFqn;
  owner_policy_method_profile_id: HTEMethodProfileId;
  owner_policy_execution_scope:
    | "estimator_n_jobs_one"
    | "producer_scoped_joblib_parallelism_one";
  owner_policy_max_jobs: 1;
  owner_policy_required_estimator_n_jobs: 1 | null;
  owner_policy_manifest_schema_version: "1.0";
  execution_status: "not_started" | "returned" | "raised";
  estimator_observation_status:
    | "recomputed"
    | "not_applicable"
    | "not_established";
  estimator_before_class_fqn: string | null;
  estimator_before_n_jobs: number | null;
  estimator_before_params_sha256: string | null;
  estimator_after_class_fqn: string | null;
  estimator_after_n_jobs: number | null;
  estimator_after_params_sha256: string | null;
  joblib_observation_status:
    | "recomputed"
    | "not_applicable"
    | "not_established";
  joblib_profile_id: "joblib.parallel_config.current_thread@1.0" | null;
  joblib_profile_revision: "1.0" | null;
  joblib_implementation: "joblib.parallel_config" | null;
  joblib_implementation_version: string | null;
  joblib_scope: "current_thread_joblib" | null;
  joblib_max_jobs: 1 | null;
  joblib_started: boolean;
  joblib_finished: boolean;
  joblib_exit_status: "not_started" | "returned" | "raised";
  joblib_entry_effective_jobs: number | null;
  joblib_entry_backend_fqn: string | null;
  joblib_entry_config_sha256: string | null;
  joblib_entry_implementation_version: string | null;
  joblib_exit_effective_jobs: number | null;
  joblib_exit_backend_fqn: string | null;
  joblib_exit_config_sha256: string | null;
  joblib_exit_implementation_version: string | null;
  physical_thread_limit_status: "not_established";
  physical_thread_limit: null;
};

type HTEOutcomeDisplayCommon = {
  schema_version: "1.0";
  method_fqn: HTEMethodFqn;
  method_abi_digest: string;
  method_profile_id: HTEMethodProfileId;
  resolved_params_sha256: string;
  owned_attempt_anchor_ref: HTEArtifactRef;
  hte_outcome_ref: HTEArtifactRef;
  point_result_ref: HTEArtifactRef | null;
  hte_result_ref: HTEArtifactRef | null;
  inference_basis_ref: HTEArtifactRef | null;
  refusal_diagnostic_ref: HTEArtifactRef | null;
  search_uncertainty_task_binding_ref?: HTEArtifactRef | null;
  materialization_binding_ref?: HTEArtifactRef | null;
  method_result_ref: HTEArtifactRef;
  method_evidence_ref: HTEArtifactRef;
  source_data_ref: HTEArtifactRef;
  selected_rows_status: "recomputed" | "not_established";
  n_selected_rows: number | null;
  selected_rows_sha256: string | null;
  selected_row_order_sha256: string | null;
  selected_x_sha256: string | null;
  computed_estimand_status: "recomputed" | "not_established";
  computed_estimand: "mean_effect_over_selected_x" | null;
  computed_target_scope_status: "recomputed" | "not_established";
  computed_target_scope: "selected_evaluation_rows" | null;
  measure_unit_status: "established" | "not_established";
  measure_unit: string | null;
  request_estimand_status: "declared" | "not_established";
  request_estimand: string | null;
  request_target_scope_status: "declared" | "not_established";
  request_target_scope: string | null;
  outcome_variable_status: "declared" | "not_established";
  outcome_variable_id: string | null;
  treatment_variable_status: "declared" | "not_established";
  treatment_variable_id: string | null;
  request_contrast_status: "declared" | "not_established";
  control_value: number | null;
  treated_value: number | null;
  request_alpha_status: "declared" | "not_established";
  requested_alpha: number | null;
  requested_guarantee_status: "declared" | "not_established";
  requested_guarantee: HTEGuarantee | null;
  computed_guarantee_status: "computed" | "not_established";
  computed_guarantee: "candidate_point" | "backend_conditional_interval" | null;
  target_relation: HTETargetRelationDisplay;
  inference_status:
    | "not_requested"
    | "unavailable"
    | "unsupported"
    | "not_qualified"
    | "failed"
    | "native_ate_inference_validated"
    | null;
  inference_reason:
    | "inference_not_requested"
    | "native_inference_unavailable"
    | "native_inference_invalid"
    | "method_profile_not_qualified"
    | "selection_uses_outcomes"
    | "contrast_not_established"
    | "request_alpha_not_established"
    | null;
  point_estimate: number | null;
  lower_bound: number | null;
  upper_bound: number | null;
  confidence_level: number | null;
  refusal_stage: "prepare" | "fit" | "infer" | "origin_verification" | null;
  refusal_reason:
    | "invalid_point_estimate"
    | "method_execution_failed"
    | "required_input_unavailable"
    | "invalid_selected_input"
    | "method_profile_unavailable"
    | "runtime_origin_not_verified"
    | null;
  refusal_diagnostic_code:
    | "hte_input_invalid"
    | "empty_selected_input"
    | "econml_unavailable"
    | "joblib_unavailable"
    | "resource_profile_invalid"
    | "dml_profile_invalid"
    | "meta_profile_invalid"
    | "hte_execution_failed"
    | "hte_fit_failed"
    | "hte_point_estimate_invalid"
    | "contrast_not_established"
    | "runtime_origin_not_verified"
    | null;
  resource_evidence: HTEResourceEvidenceDisplay;
  limitations: string[];
};

export type HTEPointOutcomeDisplay = HTEOutcomeDisplayCommon & {
  kind: "point_estimate";
  point_estimate: number;
  point_result_ref: HTEArtifactRef;
  hte_result_ref: null;
  inference_basis_ref: null;
  refusal_diagnostic_ref: null;
  lower_bound: null;
  upper_bound: null;
  confidence_level: null;
  inference_status:
    | "not_requested"
    | "unavailable"
    | "unsupported"
    | "not_qualified"
    | "failed";
  inference_reason: NonNullable<HTEOutcomeDisplayCommon["inference_reason"]>;
  refusal_stage: null;
  refusal_reason: null;
  refusal_diagnostic_code: null;
};

export type HTEIntervalOutcomeDisplay = HTEOutcomeDisplayCommon & {
  kind: "interval_estimate";
  point_estimate: number;
  point_result_ref: null;
  hte_result_ref: HTEArtifactRef;
  inference_basis_ref: HTEArtifactRef;
  refusal_diagnostic_ref: null;
  lower_bound: number;
  upper_bound: number;
  confidence_level: number;
  inference_status: "native_ate_inference_validated";
  inference_reason: null;
  refusal_stage: null;
  refusal_reason: null;
  refusal_diagnostic_code: null;
};

export type HTERefusalOutcomeDisplay = HTEOutcomeDisplayCommon & {
  kind: "refusal";
  point_estimate: null;
  point_result_ref: null;
  hte_result_ref: null;
  inference_basis_ref: null;
  refusal_diagnostic_ref: HTEArtifactRef;
  lower_bound: null;
  upper_bound: null;
  confidence_level: null;
  inference_status: null;
  inference_reason: null;
  refusal_stage: NonNullable<HTEOutcomeDisplayCommon["refusal_stage"]>;
  refusal_reason: NonNullable<HTEOutcomeDisplayCommon["refusal_reason"]>;
  refusal_diagnostic_code: NonNullable<
    HTEOutcomeDisplayCommon["refusal_diagnostic_code"]
  >;
};

const LEGACY_LIMITATION_VALUES = [
  "legacy_source_reference_unprofiled",
  "legacy_target_scope_not_established",
  "legacy_bound_meaning_not_established",
  "legacy_conditional_coverage_not_established",
  "legacy_population_coverage_not_established",
] as const;

export type HTELegacyLimitation = (typeof LEGACY_LIMITATION_VALUES)[number];

export type HTELegacyFeatureDisplay = {
  feature_name: string;
  importance_score: number;
  importance_rank: number;
  method: string;
};

export type HTELegacyLimitedOutcomeDisplay = {
  kind: "legacy_limited";
  schema_version: "1.0";
  projection_status: "legacy_limited";
  availability: "available" | "unavailable";
  source_result_ref: string;
  method: string | null;
  ate: number | null;
  ate_ci_lower: number | null;
  ate_ci_upper: number | null;
  n_samples: number | null;
  n_features: number | null;
  n_subgroups: number | null;
  top_features: HTELegacyFeatureDisplay[];
  warnings: string[];
  parse_warning: "hte_result_parse_failed" | null;
  source_reference_profile_status: "not_established";
  target_scope_status: "not_established";
  bounds_meaning_status: "not_established";
  conditional_coverage_status: "not_established";
  population_coverage_status: "not_established";
  authority_status: "limited_display_only";
  limitations: HTELegacyLimitation[];
};

export type HTEOutcomeDisplayModel =
  | HTEPointOutcomeDisplay
  | HTEIntervalOutcomeDisplay
  | HTERefusalOutcomeDisplay;

export type DecisionPacketHTEProjection =
  | HTEOutcomeDisplayModel
  | HTELegacyLimitedOutcomeDisplay;

export type DecisionPacketHTEProjectionResult =
  | { status: "absent" }
  | { status: "invalid" }
  | { status: "valid"; outcome: DecisionPacketHTEProjection };

const SUMMARY_KEYS = [
  "schema_version",
  "kind",
  "method_fqn",
  "method_abi_digest",
  "method_profile_id",
  "resolved_params_sha256",
  "owned_attempt_anchor_ref",
  "hte_outcome_ref",
  "point_result_ref",
  "hte_result_ref",
  "inference_basis_ref",
  "refusal_diagnostic_ref",
  "method_result_ref",
  "method_evidence_ref",
  "source_data_ref",
  "selected_rows_status",
  "n_selected_rows",
  "selected_rows_sha256",
  "selected_row_order_sha256",
  "selected_x_sha256",
  "computed_estimand_status",
  "computed_estimand",
  "computed_target_scope_status",
  "computed_target_scope",
  "measure_unit_status",
  "measure_unit",
  "request_estimand_status",
  "request_estimand",
  "request_target_scope_status",
  "request_target_scope",
  "outcome_variable_status",
  "outcome_variable_id",
  "treatment_variable_status",
  "treatment_variable_id",
  "request_contrast_status",
  "control_value",
  "treated_value",
  "request_alpha_status",
  "requested_alpha",
  "requested_guarantee_status",
  "requested_guarantee",
  "computed_guarantee_status",
  "computed_guarantee",
  "target_relation",
  "inference_status",
  "inference_reason",
  "point_estimate",
  "lower_bound",
  "upper_bound",
  "confidence_level",
  "refusal_stage",
  "refusal_reason",
  "refusal_diagnostic_code",
  "resource_evidence",
  "limitations",
] as const;

const OPTIONAL_RUNTIME_SUMMARY_KEYS = [
  "search_uncertainty_task_binding_ref",
  "materialization_binding_ref",
] as const;

const TARGET_RELATION_KEYS = [
  "requested_scope_status",
  "requested_scope",
  "requested_guarantee_status",
  "requested_guarantee",
  "computed_scope_status",
  "computed_scope",
  "computed_guarantee_status",
  "computed_guarantee",
  "source_content_status",
  "row_order_status",
  "contrast_status",
  "estimand_status",
  "alpha_status",
  "profile_status",
  "scope_disposition",
  "guarantee_disposition",
  "overall_disposition",
] as const;

const RESOURCE_EVIDENCE_KEYS = [
  "owner_policy_ref",
  "owner_policy_digest",
  "owner_policy_schema_version",
  "owner_policy_revision",
  "owner_policy_method_fqn",
  "owner_policy_method_profile_id",
  "owner_policy_execution_scope",
  "owner_policy_max_jobs",
  "owner_policy_required_estimator_n_jobs",
  "owner_policy_manifest_schema_version",
  "execution_status",
  "estimator_observation_status",
  "estimator_before_class_fqn",
  "estimator_before_n_jobs",
  "estimator_before_params_sha256",
  "estimator_after_class_fqn",
  "estimator_after_n_jobs",
  "estimator_after_params_sha256",
  "joblib_observation_status",
  "joblib_profile_id",
  "joblib_profile_revision",
  "joblib_implementation",
  "joblib_implementation_version",
  "joblib_scope",
  "joblib_max_jobs",
  "joblib_started",
  "joblib_finished",
  "joblib_exit_status",
  "joblib_entry_effective_jobs",
  "joblib_entry_backend_fqn",
  "joblib_entry_config_sha256",
  "joblib_entry_implementation_version",
  "joblib_exit_effective_jobs",
  "joblib_exit_backend_fqn",
  "joblib_exit_config_sha256",
  "joblib_exit_implementation_version",
  "physical_thread_limit_status",
  "physical_thread_limit",
] as const;

const ARTIFACT_REF_KEYS = [
  "artifact_id",
  "kind",
  "media_type",
  "manifest_profile_sha256",
] as const;

const HASH = /^[0-9a-f]{64}$/u;
const ARTIFACT_ID = /^sha256:[0-9a-f]{64}$/u;
const PROFILE_HASH = /^sha256:[0-9a-f]{64}$/u;
const METHOD_PROFILE_BY_FQN: Record<HTEMethodFqn, HTEMethodProfileId> = {
  "causal.hte.causal_forest@2.0.0": "econml.causal_forest_dml.native_mean@2.0",
  "causal.hte.double_ml@2.0.0": "econml.dml.point_only@2.0",
  "causal.hte.meta_learner@2.0.0": "econml.meta_learner.point_only@2.0",
  "causal.hte.forest_dr@2.0.0": "econml.forest_dr.native_mean@2.0",
};
const RESOURCE_SCOPE_BY_FQN: Record<
  HTEMethodFqn,
  "estimator_n_jobs_one" | "producer_scoped_joblib_parallelism_one"
> = {
  "causal.hte.causal_forest@2.0.0": "estimator_n_jobs_one",
  "causal.hte.double_ml@2.0.0": "producer_scoped_joblib_parallelism_one",
  "causal.hte.meta_learner@2.0.0": "producer_scoped_joblib_parallelism_one",
  "causal.hte.forest_dr@2.0.0": "estimator_n_jobs_one",
};
const RESOURCE_ESTIMATOR_JOBS_BY_FQN: Record<HTEMethodFqn, 1 | null> = {
  "causal.hte.causal_forest@2.0.0": 1,
  "causal.hte.double_ml@2.0.0": null,
  "causal.hte.meta_learner@2.0.0": null,
  "causal.hte.forest_dr@2.0.0": 1,
};
const R5_RESOURCE_ESTIMATOR_JOBS_BY_FQN: Record<HTEMethodFqn, 1 | null> = {
  "causal.hte.causal_forest@2.0.0": 1,
  "causal.hte.double_ml@2.0.0": null,
  "causal.hte.meta_learner@2.0.0": null,
  "causal.hte.forest_dr@2.0.0": 1,
};
const R5_RESOURCE_SCOPE = "producer_scoped_joblib_parallelism_one" as const;
const R5_RESOURCE_SCOPE_BY_FQN: Record<HTEMethodFqn, typeof R5_RESOURCE_SCOPE> =
  {
    "causal.hte.causal_forest@2.0.0": R5_RESOURCE_SCOPE,
    "causal.hte.double_ml@2.0.0": R5_RESOURCE_SCOPE,
    "causal.hte.meta_learner@2.0.0": R5_RESOURCE_SCOPE,
    "causal.hte.forest_dr@2.0.0": R5_RESOURCE_SCOPE,
  };
const ESTIMATOR_OBSERVATION_KEYS = [
  "estimator_before_class_fqn",
  "estimator_before_n_jobs",
  "estimator_before_params_sha256",
  "estimator_after_class_fqn",
  "estimator_after_n_jobs",
  "estimator_after_params_sha256",
] as const;
const JOBLIB_ENTRY_KEYS = [
  "joblib_profile_id",
  "joblib_profile_revision",
  "joblib_implementation",
  "joblib_scope",
  "joblib_max_jobs",
  "joblib_entry_effective_jobs",
  "joblib_entry_backend_fqn",
  "joblib_entry_config_sha256",
  "joblib_entry_implementation_version",
] as const;
const JOBLIB_EXIT_KEYS = [
  "joblib_exit_effective_jobs",
  "joblib_exit_backend_fqn",
  "joblib_exit_config_sha256",
  "joblib_exit_implementation_version",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return false;
  }
  try {
    const prototype = Object.getPrototypeOf(value);
    return (
      (prototype === Object.prototype || prototype === null) &&
      Reflect.ownKeys(value).every((key) => {
        if (typeof key !== "string") return false;
        const descriptor = Object.getOwnPropertyDescriptor(value, key);
        return descriptor !== undefined && "value" in descriptor;
      })
    );
  } catch {
    return false;
  }
}

function hasExactKeys(
  value: unknown,
  expectedKeys: readonly string[],
): value is Record<string, unknown> {
  if (!isRecord(value)) return false;
  const actualKeys = Reflect.ownKeys(value);
  const expected = new Set(expectedKeys);
  return (
    actualKeys.length === expected.size &&
    actualKeys.every((key) => typeof key === "string" && expected.has(key))
  );
}

function hasExactKeysWithOptional(
  value: unknown,
  requiredKeys: readonly string[],
  optionalKeys: readonly string[],
): value is Record<string, unknown> {
  if (!isRecord(value)) return false;
  const actualKeys = Reflect.ownKeys(value);
  const allowed = new Set([...requiredKeys, ...optionalKeys]);
  return (
    requiredKeys.every((key) => Object.hasOwn(value, key)) &&
    actualKeys.every((key) => typeof key === "string" && allowed.has(key))
  );
}

function isOneOf<const T extends readonly unknown[]>(
  value: unknown,
  choices: T,
): value is T[number] {
  return choices.some((choice) => Object.is(choice, value));
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isArrayIndexKey(key: PropertyKey): key is string {
  if (typeof key !== "string") return false;
  const index = Number(key);
  return (
    Number.isInteger(index) &&
    index >= 0 &&
    index < 0xffff_ffff &&
    String(index) === key
  );
}

// Copy only ordinary, dense arrays of own data properties. Reflection can still
// trigger Proxy traps; this guards element accessors and user-defined array methods.
function readDenseOwnDataArray(
  value: unknown,
  minimumLength: number,
  maximumLength: number,
): unknown[] | null {
  try {
    if (!Array.isArray(value)) return null;
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Array.prototype) return null;

    const lengthDescriptor = Object.getOwnPropertyDescriptor(value, "length");
    if (!lengthDescriptor || !("value" in lengthDescriptor)) return null;
    const length = lengthDescriptor.value;
    if (
      typeof length !== "number" ||
      !Number.isSafeInteger(length) ||
      length < minimumLength ||
      length > maximumLength
    ) {
      return null;
    }

    const ownKeys = Reflect.ownKeys(value);
    if (ownKeys.length !== length + 1) return null;
    let hasLengthKey = false;
    for (const key of ownKeys) {
      if (key === "length") {
        hasLengthKey = true;
        continue;
      }
      if (
        typeof key !== "string" ||
        !isArrayIndexKey(key) ||
        Number(key) >= length
      ) {
        return null;
      }
    }
    if (!hasLengthKey) return null;

    let ancestor: object | null = prototype;
    while (ancestor !== null) {
      const inheritedKeys = Reflect.ownKeys(ancestor);
      for (const key of inheritedKeys) {
        if (isArrayIndexKey(key)) return null;
      }
      ancestor = Object.getPrototypeOf(ancestor);
    }

    const copied: unknown[] = [];
    for (let index = 0; index < length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      if (
        !descriptor ||
        !("value" in descriptor) ||
        descriptor.enumerable !== true
      ) {
        return null;
      }
      Object.defineProperty(copied, String(index), {
        value: descriptor.value,
        enumerable: true,
        writable: true,
        configurable: true,
      });
    }
    return copied;
  } catch {
    return null;
  }
}

function parseNonEmptyStringArray(value: unknown): string[] | null {
  const items = readDenseOwnDataArray(value, 1, 32);
  if (items === null) return null;
  for (const item of items) {
    if (!nonEmptyString(item)) return null;
  }
  return items as string[];
}

function finiteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function nullableString(value: unknown): value is string | null {
  return value === null || nonEmptyString(value);
}

function unicodeCodePointLength(value: string): number {
  let length = 0;
  for (const codePoint of value) {
    length += codePoint.length > 0 ? 1 : 0;
  }
  return length;
}

function boundedString(
  value: unknown,
  minimumLength: number,
  maximumLength: number,
): value is string {
  if (typeof value !== "string") return false;
  const length = unicodeCodePointLength(value);
  return length >= minimumLength && length <= maximumLength;
}

function nullableBoundedString(
  value: unknown,
  maximumLength: number,
): value is string | null {
  return value === null || boundedString(value, 1, maximumLength);
}

function nullableHash(value: unknown): value is string | null {
  return value === null || (typeof value === "string" && HASH.test(value));
}

function nullableFiniteNumber(value: unknown): value is number | null {
  return value === null || finiteNumber(value);
}

function nullablePositiveInteger(value: unknown): value is number | null {
  return value === null || (Number.isInteger(value) && (value as number) >= 1);
}

function parseArtifactRef(
  value: unknown,
  expectedKind?: string,
): HTEArtifactRef | null {
  if (
    !hasExactKeys(value, ARTIFACT_REF_KEYS) ||
    typeof value.artifact_id !== "string" ||
    !ARTIFACT_ID.test(value.artifact_id) ||
    !nonEmptyString(value.kind) ||
    (expectedKind !== undefined && value.kind !== expectedKind) ||
    value.media_type !== "application/json" ||
    typeof value.manifest_profile_sha256 !== "string" ||
    !PROFILE_HASH.test(value.manifest_profile_sha256)
  ) {
    return null;
  }
  return {
    artifact_id: value.artifact_id,
    kind: value.kind,
    media_type: "application/json",
    manifest_profile_sha256: value.manifest_profile_sha256,
  };
}

function parseTargetRelation(
  value: unknown,
  runtimeSummary = false,
): HTETargetRelationDisplay | null {
  if (
    !hasExactKeys(value, TARGET_RELATION_KEYS) ||
    !isOneOf(value.requested_scope_status, [
      "declared",
      "not_established",
    ] as const) ||
    !nullableString(value.requested_scope) ||
    !isOneOf(value.requested_guarantee_status, [
      "declared",
      "not_established",
    ] as const) ||
    !isOneOf(value.requested_guarantee, [
      "candidate_point",
      "backend_conditional_interval",
      "population_sampling_coverage",
      null,
    ] as const) ||
    !isOneOf(value.computed_scope_status, [
      "recomputed",
      "not_established",
    ] as const) ||
    !isOneOf(value.computed_scope, [
      "selected_evaluation_rows",
      null,
    ] as const) ||
    !isOneOf(value.computed_guarantee_status, [
      "computed",
      "not_established",
    ] as const) ||
    !isOneOf(value.computed_guarantee, [
      "candidate_point",
      "backend_conditional_interval",
      null,
    ] as const) ||
    !isOneOf(value.source_content_status, [
      "content_bound",
      "not_established",
    ] as const) ||
    !isOneOf(value.row_order_status, [
      "recomputed",
      "not_established",
    ] as const) ||
    !isOneOf(value.contrast_status, [
      "recomputed",
      "not_established",
    ] as const) ||
    !isOneOf(value.estimand_status, [
      "recomputed",
      "not_established",
    ] as const) ||
    !isOneOf(value.alpha_status, [
      "recomputed",
      "not_applicable",
      "not_established",
    ] as const) ||
    !isOneOf(value.profile_status, [
      "qualified",
      "point_only",
      "not_established",
    ] as const) ||
    !isOneOf(value.scope_disposition, [
      "satisfied",
      "requested_claim_not_satisfied",
      "not_established",
    ] as const) ||
    !isOneOf(value.guarantee_disposition, [
      "satisfied",
      "requested_claim_not_satisfied",
      "not_established",
    ] as const) ||
    !isOneOf(value.overall_disposition, [
      "satisfied",
      "requested_claim_not_satisfied",
      "not_established",
    ] as const)
  ) {
    return null;
  }
  if (runtimeSummary && value.estimand_status !== "not_established") {
    return null;
  }
  if (
    (value.requested_scope_status === "declared") !==
      (value.requested_scope !== null) ||
    (value.requested_guarantee_status === "declared") !==
      (value.requested_guarantee !== null) ||
    (value.computed_scope_status === "recomputed") !==
      (value.computed_scope === "selected_evaluation_rows") ||
    (value.computed_guarantee_status === "computed") !==
      (value.computed_guarantee !== null)
  ) {
    return null;
  }
  const complete =
    value.requested_scope_status === "declared" &&
    value.requested_guarantee_status === "declared" &&
    value.computed_scope_status === "recomputed" &&
    value.computed_guarantee_status === "computed" &&
    value.source_content_status === "content_bound" &&
    value.row_order_status === "recomputed" &&
    value.contrast_status === "recomputed" &&
    value.estimand_status === "recomputed" &&
    (value.profile_status === "qualified" ||
      value.profile_status === "point_only") &&
    (value.alpha_status === "recomputed" ||
      value.alpha_status === "not_applicable");
  let scopeDisposition: HTETargetRelationDisplay["scope_disposition"];
  let guaranteeDisposition: HTETargetRelationDisplay["guarantee_disposition"];
  let overallDisposition: HTETargetRelationDisplay["overall_disposition"];
  if (!runtimeSummary) {
    scopeDisposition = complete
      ? value.requested_scope === value.computed_scope
        ? "satisfied"
        : "requested_claim_not_satisfied"
      : "not_established";
    guaranteeDisposition = complete
      ? value.requested_guarantee === value.computed_guarantee
        ? "satisfied"
        : "requested_claim_not_satisfied"
      : "not_established";
    overallDisposition =
      scopeDisposition === "not_established" ||
      guaranteeDisposition === "not_established"
        ? "not_established"
        : scopeDisposition === "satisfied" &&
            guaranteeDisposition === "satisfied"
          ? "satisfied"
          : "requested_claim_not_satisfied";
  } else {
    const scopeEvidenceReady =
      value.computed_scope_status === "recomputed" &&
      value.source_content_status === "content_bound" &&
      value.row_order_status === "recomputed";
    scopeDisposition =
      value.requested_scope_status !== "declared" || !scopeEvidenceReady
        ? "not_established"
        : value.requested_scope === value.computed_scope
          ? "satisfied"
          : value.requested_scope === "population"
            ? "requested_claim_not_satisfied"
            : "not_established";

    const guaranteeEvidenceReady =
      value.computed_guarantee_status === "computed" &&
      (value.alpha_status === "recomputed" ||
        value.alpha_status === "not_applicable") &&
      (value.profile_status === "qualified" ||
        value.profile_status === "point_only");
    guaranteeDisposition =
      value.requested_guarantee_status !== "declared" || !guaranteeEvidenceReady
        ? "not_established"
        : value.requested_guarantee === value.computed_guarantee
          ? "satisfied"
          : "requested_claim_not_satisfied";

    const mismatch =
      scopeDisposition === "requested_claim_not_satisfied" ||
      guaranteeDisposition === "requested_claim_not_satisfied";
    const relationUnknown =
      scopeDisposition === "not_established" ||
      guaranteeDisposition === "not_established" ||
      value.contrast_status !== "recomputed" ||
      value.estimand_status !== "recomputed" ||
      value.source_content_status !== "content_bound" ||
      value.row_order_status !== "recomputed";
    overallDisposition = mismatch
      ? "requested_claim_not_satisfied"
      : relationUnknown
        ? "not_established"
        : "satisfied";
  }
  if (
    value.scope_disposition !== scopeDisposition ||
    value.guarantee_disposition !== guaranteeDisposition ||
    value.overall_disposition !== overallDisposition
  ) {
    return null;
  }
  return value as unknown as HTETargetRelationDisplay;
}

function parseResourceEvidence(
  value: unknown,
  methodFqn: HTEMethodFqn,
  methodProfileId: HTEMethodProfileId,
  runtimeSummary = false,
): HTEResourceEvidenceDisplay | null {
  const revision = isRecord(value) ? value.owner_policy_revision : null;
  const isR4 = revision === "r4";
  const isR5 = revision === "r5";
  const expectedScope = isR5
    ? R5_RESOURCE_SCOPE_BY_FQN[methodFqn]
    : RESOURCE_SCOPE_BY_FQN[methodFqn];
  const expectedEstimatorJobs = isR5
    ? R5_RESOURCE_ESTIMATOR_JOBS_BY_FQN[methodFqn]
    : RESOURCE_ESTIMATOR_JOBS_BY_FQN[methodFqn];
  if (
    !hasExactKeys(value, RESOURCE_EVIDENCE_KEYS) ||
    typeof value.owner_policy_digest !== "string" ||
    !HASH.test(value.owner_policy_digest) ||
    (!isR4 && !isR5) ||
    (!runtimeSummary && !isR4) ||
    value.owner_policy_schema_version !==
      (isR5
        ? "polisyos.runtime.observational_input_resource_policy.v5"
        : "polisyos.runtime.observational_input_resource_policy.v4") ||
    value.owner_policy_method_fqn !== methodFqn ||
    value.owner_policy_method_profile_id !== methodProfileId ||
    value.owner_policy_execution_scope !== expectedScope ||
    value.owner_policy_max_jobs !== 1 ||
    value.owner_policy_required_estimator_n_jobs !== expectedEstimatorJobs ||
    value.owner_policy_manifest_schema_version !== "1.0" ||
    !isOneOf(value.execution_status, [
      "not_started",
      "returned",
      "raised",
    ] as const) ||
    !isOneOf(value.estimator_observation_status, [
      "recomputed",
      "not_applicable",
      "not_established",
    ] as const) ||
    !nullableString(value.estimator_before_class_fqn) ||
    !nullablePositiveInteger(value.estimator_before_n_jobs) ||
    !nullableHash(value.estimator_before_params_sha256) ||
    !nullableString(value.estimator_after_class_fqn) ||
    !nullablePositiveInteger(value.estimator_after_n_jobs) ||
    !nullableHash(value.estimator_after_params_sha256) ||
    !isOneOf(value.joblib_observation_status, [
      "recomputed",
      "not_applicable",
      "not_established",
    ] as const) ||
    !isOneOf(value.joblib_profile_id, [
      "joblib.parallel_config.current_thread@1.0",
      null,
    ] as const) ||
    !isOneOf(value.joblib_profile_revision, ["1.0", null] as const) ||
    !isOneOf(value.joblib_implementation, [
      "joblib.parallel_config",
      null,
    ] as const) ||
    !nullableString(value.joblib_implementation_version) ||
    !isOneOf(value.joblib_scope, ["current_thread_joblib", null] as const) ||
    !isOneOf(value.joblib_max_jobs, [1, null] as const) ||
    typeof value.joblib_started !== "boolean" ||
    typeof value.joblib_finished !== "boolean" ||
    !isOneOf(value.joblib_exit_status, [
      "not_started",
      "returned",
      "raised",
    ] as const) ||
    !nullablePositiveInteger(value.joblib_entry_effective_jobs) ||
    !nullableString(value.joblib_entry_backend_fqn) ||
    !nullableHash(value.joblib_entry_config_sha256) ||
    !nullableString(value.joblib_entry_implementation_version) ||
    !nullablePositiveInteger(value.joblib_exit_effective_jobs) ||
    !nullableString(value.joblib_exit_backend_fqn) ||
    !nullableHash(value.joblib_exit_config_sha256) ||
    !nullableString(value.joblib_exit_implementation_version) ||
    value.physical_thread_limit_status !== "not_established" ||
    value.physical_thread_limit !== null
  ) {
    return null;
  }
  const ownerPolicyRef = parseArtifactRef(
    value.owner_policy_ref,
    "runtime.observational_input_resource_policy",
  );
  if (!ownerPolicyRef) return null;

  const estimatorValues = ESTIMATOR_OBSERVATION_KEYS.map((key) => value[key]);
  const joblibEntryValues = JOBLIB_ENTRY_KEYS.map((key) => value[key]);
  const joblibExitValues = JOBLIB_EXIT_KEYS.map((key) => value[key]);
  if (expectedEstimatorJobs === 1) {
    if (value.execution_status === "returned") {
      if (
        value.estimator_observation_status !== "recomputed" ||
        estimatorValues.some((item) => item === null) ||
        value.estimator_before_n_jobs !== 1 ||
        value.estimator_after_n_jobs !== 1 ||
        value.estimator_before_class_fqn !== value.estimator_after_class_fqn ||
        value.estimator_before_params_sha256 !==
          value.estimator_after_params_sha256
      ) {
        return null;
      }
    } else if (value.execution_status === "not_started") {
      if (
        value.estimator_observation_status !== "not_established" ||
        estimatorValues.some((item) => item !== null)
      ) {
        return null;
      }
    } else if (value.estimator_observation_status === "recomputed") {
      if (estimatorValues.some((item) => item === null)) return null;
    } else if (
      value.estimator_observation_status !== "not_established" ||
      estimatorValues.some((item) => item !== null)
    ) {
      return null;
    }
  }

  const joblibRequired =
    value.owner_policy_execution_scope ===
    "producer_scoped_joblib_parallelism_one";
  if (!joblibRequired) {
    if (
      value.joblib_observation_status !== "not_applicable" ||
      joblibEntryValues.some((item) => item !== null) ||
      joblibExitValues.some((item) => item !== null) ||
      value.joblib_started ||
      value.joblib_finished ||
      value.joblib_exit_status !== "not_started"
    ) {
      return null;
    }
  } else {
    if (
      expectedEstimatorJobs === null &&
      (value.estimator_observation_status !== "not_applicable" ||
        estimatorValues.some((item) => item !== null))
    ) {
      return null;
    }
    if (
      value.execution_status === "not_started" &&
      (value.joblib_observation_status !== "not_established" ||
        value.joblib_started ||
        value.joblib_finished ||
        value.joblib_exit_status !== "not_started" ||
        joblibEntryValues.some((item) => item !== null) ||
        joblibExitValues.some((item) => item !== null))
    ) {
      return null;
    }
    if (
      value.execution_status !== "not_started" &&
      (value.joblib_observation_status !== "recomputed" ||
        !value.joblib_started ||
        !value.joblib_finished ||
        value.joblib_exit_status !== value.execution_status ||
        joblibEntryValues.some((item) => item === null) ||
        joblibExitValues.some((item) => item === null) ||
        value.joblib_profile_id !==
          "joblib.parallel_config.current_thread@1.0" ||
        value.joblib_profile_revision !== "1.0" ||
        value.joblib_implementation !== "joblib.parallel_config" ||
        value.joblib_scope !== "current_thread_joblib" ||
        value.joblib_max_jobs !== 1)
    ) {
      return null;
    }
    if (
      value.execution_status === "returned" &&
      (value.joblib_entry_effective_jobs !== 1 ||
        value.joblib_exit_effective_jobs !== 1 ||
        value.joblib_implementation_version !==
          value.joblib_entry_implementation_version ||
        value.joblib_entry_backend_fqn !== value.joblib_exit_backend_fqn ||
        value.joblib_entry_config_sha256 !== value.joblib_exit_config_sha256 ||
        value.joblib_entry_implementation_version !==
          value.joblib_exit_implementation_version)
    ) {
      return null;
    }
  }
  return {
    ...(value as unknown as HTEResourceEvidenceDisplay),
    owner_policy_ref: ownerPolicyRef,
  };
}

function parseOutcome(
  value: unknown,
  runtimeSummary = false,
): HTEOutcomeDisplayModel | null {
  if (!isRecord(value)) return null;
  if (runtimeSummary) {
    if (
      !hasExactKeysWithOptional(
        value,
        SUMMARY_KEYS,
        OPTIONAL_RUNTIME_SUMMARY_KEYS,
      )
    ) {
      return null;
    }
  } else if (!hasExactKeys(value, SUMMARY_KEYS)) {
    return null;
  }
  if (
    value.schema_version !== "1.0" ||
    !isOneOf(value.kind, [
      "point_estimate",
      "interval_estimate",
      "refusal",
    ] as const) ||
    !isOneOf(
      value.method_fqn,
      Object.keys(METHOD_PROFILE_BY_FQN) as HTEMethodFqn[],
    ) ||
    typeof value.method_abi_digest !== "string" ||
    !HASH.test(value.method_abi_digest) ||
    !isOneOf(
      value.method_profile_id,
      Object.values(METHOD_PROFILE_BY_FQN) as HTEMethodProfileId[],
    ) ||
    typeof value.resolved_params_sha256 !== "string" ||
    !HASH.test(value.resolved_params_sha256)
  ) {
    return null;
  }
  const limitations = parseNonEmptyStringArray(value.limitations);
  if (limitations === null) return null;

  const methodFqn = value.method_fqn as HTEMethodFqn;
  const methodProfileId = value.method_profile_id as HTEMethodProfileId;
  if (METHOD_PROFILE_BY_FQN[methodFqn] !== methodProfileId) return null;

  const ownedAttemptRef = parseArtifactRef(
    value.owned_attempt_anchor_ref,
    "runtime.owned_attempt_anchor",
  );
  const hteOutcomeRef = parseArtifactRef(
    value.hte_outcome_ref,
    "ir.hte_outcome",
  );
  const pointResultRef =
    value.point_result_ref === null
      ? null
      : parseArtifactRef(value.point_result_ref, "ir.hte_point_result");
  const hteResultRef =
    value.hte_result_ref === null
      ? null
      : parseArtifactRef(value.hte_result_ref, "ir.hte_result");
  const inferenceBasisRef =
    value.inference_basis_ref === null
      ? null
      : parseArtifactRef(value.inference_basis_ref, "ir.ate_inference_basis");
  const refusalDiagnosticRef =
    value.refusal_diagnostic_ref === null
      ? null
      : parseArtifactRef(
          value.refusal_diagnostic_ref,
          "ir.hte_refusal_diagnostic",
        );
  const searchBindingRef =
    !runtimeSummary ||
    value.search_uncertainty_task_binding_ref === undefined ||
    value.search_uncertainty_task_binding_ref === null
      ? null
      : parseArtifactRef(
          value.search_uncertainty_task_binding_ref,
          "scientist.search.uncertainty_task_binding",
        );
  const materializationBindingRef =
    !runtimeSummary ||
    value.materialization_binding_ref === undefined ||
    value.materialization_binding_ref === null
      ? null
      : parseArtifactRef(
          value.materialization_binding_ref,
          "foundry.hte.physical_source_materialization_binding",
        );
  const methodResultRef = parseArtifactRef(
    value.method_result_ref,
    "scientist.method_result.causal.hte",
  );
  const methodEvidenceRef = parseArtifactRef(
    value.method_evidence_ref,
    "scientist.method_evidence",
  );
  const sourceDataRef = parseArtifactRef(value.source_data_ref);
  const targetRelation = parseTargetRelation(
    value.target_relation,
    runtimeSummary,
  );
  const resourceEvidence = parseResourceEvidence(
    value.resource_evidence,
    methodFqn,
    methodProfileId,
    runtimeSummary,
  );
  if (
    !ownedAttemptRef ||
    !hteOutcomeRef ||
    !methodResultRef ||
    !methodEvidenceRef ||
    !sourceDataRef ||
    !targetRelation ||
    !resourceEvidence ||
    (runtimeSummary &&
      value.search_uncertainty_task_binding_ref !== undefined &&
      value.search_uncertainty_task_binding_ref !== null &&
      !searchBindingRef) ||
    (runtimeSummary &&
      value.materialization_binding_ref !== undefined &&
      value.materialization_binding_ref !== null &&
      !materializationBindingRef) ||
    (runtimeSummary &&
      resourceEvidence.owner_policy_revision === "r5" &&
      materializationBindingRef === null) ||
    (value.point_result_ref !== null && !pointResultRef) ||
    (value.hte_result_ref !== null && !hteResultRef) ||
    (value.inference_basis_ref !== null && !inferenceBasisRef) ||
    (value.refusal_diagnostic_ref !== null && !refusalDiagnosticRef) ||
    !isOneOf(value.selected_rows_status, [
      "recomputed",
      "not_established",
    ] as const) ||
    !isOneOf(value.computed_estimand_status, [
      "recomputed",
      "not_established",
    ] as const) ||
    !isOneOf(value.computed_estimand, [
      "mean_effect_over_selected_x",
      null,
    ] as const) ||
    !isOneOf(value.computed_target_scope_status, [
      "recomputed",
      "not_established",
    ] as const) ||
    !isOneOf(value.computed_target_scope, [
      "selected_evaluation_rows",
      null,
    ] as const) ||
    !isOneOf(value.measure_unit_status, [
      "established",
      "not_established",
    ] as const) ||
    !nullableString(value.measure_unit) ||
    !isOneOf(value.request_estimand_status, [
      "declared",
      "not_established",
    ] as const) ||
    !nullableString(value.request_estimand) ||
    !isOneOf(value.request_target_scope_status, [
      "declared",
      "not_established",
    ] as const) ||
    !nullableString(value.request_target_scope) ||
    !isOneOf(value.outcome_variable_status, [
      "declared",
      "not_established",
    ] as const) ||
    !nullableString(value.outcome_variable_id) ||
    !isOneOf(value.treatment_variable_status, [
      "declared",
      "not_established",
    ] as const) ||
    !nullableString(value.treatment_variable_id) ||
    !isOneOf(value.request_contrast_status, [
      "declared",
      "not_established",
    ] as const) ||
    !nullableFiniteNumber(value.control_value) ||
    !nullableFiniteNumber(value.treated_value) ||
    !isOneOf(value.request_alpha_status, [
      "declared",
      "not_established",
    ] as const) ||
    !nullableFiniteNumber(value.requested_alpha) ||
    !isOneOf(value.requested_guarantee_status, [
      "declared",
      "not_established",
    ] as const) ||
    !isOneOf(value.requested_guarantee, [
      "candidate_point",
      "backend_conditional_interval",
      "population_sampling_coverage",
      null,
    ] as const) ||
    !isOneOf(value.computed_guarantee_status, [
      "computed",
      "not_established",
    ] as const) ||
    !isOneOf(value.computed_guarantee, [
      "candidate_point",
      "backend_conditional_interval",
      null,
    ] as const) ||
    !isOneOf(value.inference_status, [
      "not_requested",
      "unavailable",
      "unsupported",
      "not_qualified",
      "failed",
      "native_ate_inference_validated",
      null,
    ] as const) ||
    !isOneOf(value.inference_reason, [
      "inference_not_requested",
      "native_inference_unavailable",
      "native_inference_invalid",
      "method_profile_not_qualified",
      "selection_uses_outcomes",
      "contrast_not_established",
      "request_alpha_not_established",
      null,
    ] as const) ||
    !nullableFiniteNumber(value.point_estimate) ||
    !nullableFiniteNumber(value.lower_bound) ||
    !nullableFiniteNumber(value.upper_bound) ||
    !nullableFiniteNumber(value.confidence_level) ||
    !isOneOf(value.refusal_stage, [
      "prepare",
      "fit",
      "infer",
      "origin_verification",
      null,
    ] as const) ||
    !isOneOf(value.refusal_reason, [
      "invalid_point_estimate",
      "method_execution_failed",
      "required_input_unavailable",
      "invalid_selected_input",
      "method_profile_unavailable",
      "runtime_origin_not_verified",
      null,
    ] as const) ||
    !isOneOf(value.refusal_diagnostic_code, [
      "hte_input_invalid",
      "empty_selected_input",
      "econml_unavailable",
      "joblib_unavailable",
      "resource_profile_invalid",
      "dml_profile_invalid",
      "meta_profile_invalid",
      "hte_execution_failed",
      "hte_fit_failed",
      "hte_point_estimate_invalid",
      "contrast_not_established",
      "runtime_origin_not_verified",
      null,
    ] as const)
  ) {
    return null;
  }

  if (
    sourceDataRef.manifest_profile_sha256 === null ||
    resourceEvidence.owner_policy_ref.manifest_profile_sha256 === null ||
    resourceEvidence.owner_policy_digest.length !== 64 ||
    (value.measure_unit_status === "established") !==
      (value.measure_unit !== null) ||
    (value.request_estimand_status === "declared") !==
      (value.request_estimand !== null) ||
    (value.request_target_scope_status === "declared") !==
      (value.request_target_scope !== null) ||
    (value.outcome_variable_status === "declared") !==
      (value.outcome_variable_id !== null) ||
    (value.treatment_variable_status === "declared") !==
      (value.treatment_variable_id !== null) ||
    (value.request_contrast_status === "declared") !==
      (value.control_value !== null && value.treated_value !== null) ||
    (value.request_alpha_status === "declared") !==
      (value.requested_alpha !== null) ||
    (value.requested_guarantee_status === "declared") !==
      (value.requested_guarantee !== null) ||
    (value.computed_guarantee_status === "computed") !==
      (value.computed_guarantee !== null) ||
    (value.computed_estimand_status === "recomputed") !==
      (value.computed_estimand === "mean_effect_over_selected_x") ||
    (value.computed_target_scope_status === "recomputed") !==
      (value.computed_target_scope === "selected_evaluation_rows") ||
    (value.selected_rows_status === "recomputed") !==
      (value.n_selected_rows !== null &&
        value.selected_rows_sha256 !== null &&
        value.selected_row_order_sha256 !== null &&
        value.selected_x_sha256 !== null) ||
    !nullableHash(value.selected_rows_sha256) ||
    !nullableHash(value.selected_row_order_sha256) ||
    !nullableHash(value.selected_x_sha256) ||
    (value.n_selected_rows !== null &&
      (typeof value.n_selected_rows !== "number" ||
        !Number.isInteger(value.n_selected_rows) ||
        value.n_selected_rows < 1)) ||
    (value.requested_alpha !== null &&
      (value.requested_alpha <= 0 || value.requested_alpha >= 1)) ||
    (value.control_value !== null &&
      value.control_value === value.treated_value) ||
    targetRelation.requested_scope_status !==
      value.request_target_scope_status ||
    targetRelation.requested_scope !== value.request_target_scope ||
    targetRelation.requested_guarantee_status !==
      value.requested_guarantee_status ||
    targetRelation.requested_guarantee !== value.requested_guarantee ||
    targetRelation.computed_scope_status !==
      value.computed_target_scope_status ||
    targetRelation.computed_scope !== value.computed_target_scope ||
    targetRelation.computed_guarantee_status !==
      value.computed_guarantee_status ||
    targetRelation.computed_guarantee !== value.computed_guarantee ||
    resourceEvidence.owner_policy_method_fqn !== methodFqn ||
    resourceEvidence.owner_policy_method_profile_id !== methodProfileId
  ) {
    return null;
  }

  const common = {
    schema_version: "1.0" as const,
    method_fqn: methodFqn,
    method_abi_digest: value.method_abi_digest,
    method_profile_id: methodProfileId,
    resolved_params_sha256: value.resolved_params_sha256,
    owned_attempt_anchor_ref: ownedAttemptRef,
    hte_outcome_ref: hteOutcomeRef,
    point_result_ref: pointResultRef,
    hte_result_ref: hteResultRef,
    inference_basis_ref: inferenceBasisRef,
    refusal_diagnostic_ref: refusalDiagnosticRef,
    ...(runtimeSummary
      ? {
          search_uncertainty_task_binding_ref: searchBindingRef,
          materialization_binding_ref: materializationBindingRef,
        }
      : {}),
    method_result_ref: methodResultRef,
    method_evidence_ref: methodEvidenceRef,
    source_data_ref: sourceDataRef,
    selected_rows_status: value.selected_rows_status,
    n_selected_rows: value.n_selected_rows as number | null,
    selected_rows_sha256: value.selected_rows_sha256 as string | null,
    selected_row_order_sha256: value.selected_row_order_sha256 as string | null,
    selected_x_sha256: value.selected_x_sha256 as string | null,
    computed_estimand_status: value.computed_estimand_status,
    computed_estimand: value.computed_estimand,
    computed_target_scope_status: value.computed_target_scope_status,
    computed_target_scope: value.computed_target_scope,
    measure_unit_status: value.measure_unit_status,
    measure_unit: value.measure_unit,
    request_estimand_status: value.request_estimand_status,
    request_estimand: value.request_estimand,
    request_target_scope_status: value.request_target_scope_status,
    request_target_scope: value.request_target_scope,
    outcome_variable_status: value.outcome_variable_status,
    outcome_variable_id: value.outcome_variable_id,
    treatment_variable_status: value.treatment_variable_status,
    treatment_variable_id: value.treatment_variable_id,
    request_contrast_status: value.request_contrast_status,
    control_value: value.control_value as number | null,
    treated_value: value.treated_value as number | null,
    request_alpha_status: value.request_alpha_status,
    requested_alpha: value.requested_alpha as number | null,
    requested_guarantee_status: value.requested_guarantee_status,
    requested_guarantee: value.requested_guarantee,
    computed_guarantee_status: value.computed_guarantee_status,
    computed_guarantee: value.computed_guarantee,
    target_relation: targetRelation,
    inference_status: value.inference_status,
    inference_reason: value.inference_reason,
    point_estimate: value.point_estimate as number | null,
    lower_bound: value.lower_bound as number | null,
    upper_bound: value.upper_bound as number | null,
    confidence_level: value.confidence_level as number | null,
    refusal_stage: value.refusal_stage,
    refusal_reason: value.refusal_reason,
    refusal_diagnostic_code: value.refusal_diagnostic_code,
    resource_evidence: resourceEvidence,
    limitations,
  };

  if (value.kind === "point_estimate") {
    if (
      !finiteNumber(value.point_estimate) ||
      !pointResultRef ||
      hteResultRef !== null ||
      inferenceBasisRef !== null ||
      refusalDiagnosticRef !== null ||
      value.lower_bound !== null ||
      value.upper_bound !== null ||
      value.confidence_level !== null ||
      value.computed_guarantee !== "candidate_point" ||
      value.computed_estimand_status !== "recomputed" ||
      value.computed_estimand !== "mean_effect_over_selected_x" ||
      value.computed_target_scope_status !== "recomputed" ||
      value.computed_target_scope !== "selected_evaluation_rows" ||
      value.selected_rows_status !== "recomputed" ||
      resourceEvidence.execution_status !== "returned" ||
      !isOneOf(value.inference_status, [
        "not_requested",
        "unavailable",
        "unsupported",
        "not_qualified",
        "failed",
      ] as const) ||
      !isOneOf(value.inference_reason, [
        "inference_not_requested",
        "native_inference_unavailable",
        "native_inference_invalid",
        "method_profile_not_qualified",
        "selection_uses_outcomes",
        "contrast_not_established",
        "request_alpha_not_established",
      ] as const) ||
      value.refusal_stage !== null ||
      value.refusal_reason !== null ||
      value.refusal_diagnostic_code !== null
    ) {
      return null;
    }
    return {
      ...common,
      kind: "point_estimate",
      point_estimate: value.point_estimate,
      point_result_ref: pointResultRef,
      hte_result_ref: null,
      inference_basis_ref: null,
      refusal_diagnostic_ref: null,
      lower_bound: null,
      upper_bound: null,
      confidence_level: null,
      inference_status: value.inference_status,
      inference_reason: value.inference_reason,
      refusal_stage: null,
      refusal_reason: null,
      refusal_diagnostic_code: null,
    };
  }
  if (value.kind === "interval_estimate") {
    if (
      !finiteNumber(value.point_estimate) ||
      !finiteNumber(value.lower_bound) ||
      !finiteNumber(value.upper_bound) ||
      !finiteNumber(value.confidence_level) ||
      value.lower_bound > value.upper_bound ||
      pointResultRef !== null ||
      !hteResultRef ||
      !inferenceBasisRef ||
      refusalDiagnosticRef !== null ||
      ![
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.forest_dr.native_mean@2.0",
      ].includes(methodProfileId) ||
      value.computed_guarantee !== "backend_conditional_interval" ||
      value.computed_estimand_status !== "recomputed" ||
      value.computed_estimand !== "mean_effect_over_selected_x" ||
      value.computed_target_scope_status !== "recomputed" ||
      value.computed_target_scope !== "selected_evaluation_rows" ||
      value.selected_rows_status !== "recomputed" ||
      resourceEvidence.execution_status !== "returned" ||
      value.inference_status !== "native_ate_inference_validated" ||
      value.inference_reason !== null ||
      value.requested_alpha === null ||
      Math.abs(1 - value.confidence_level - value.requested_alpha) > 1e-12 ||
      targetRelation.alpha_status !== "recomputed" ||
      targetRelation.profile_status !== "qualified" ||
      value.refusal_stage !== null ||
      value.refusal_reason !== null ||
      value.refusal_diagnostic_code !== null
    ) {
      return null;
    }
    return {
      ...common,
      kind: "interval_estimate",
      point_estimate: value.point_estimate,
      point_result_ref: null,
      hte_result_ref: hteResultRef,
      inference_basis_ref: inferenceBasisRef,
      refusal_diagnostic_ref: null,
      lower_bound: value.lower_bound,
      upper_bound: value.upper_bound,
      confidence_level: value.confidence_level,
      inference_status: "native_ate_inference_validated",
      inference_reason: null,
      refusal_stage: null,
      refusal_reason: null,
      refusal_diagnostic_code: null,
    };
  }
  if (
    value.point_estimate !== null ||
    pointResultRef !== null ||
    hteResultRef !== null ||
    inferenceBasisRef !== null ||
    refusalDiagnosticRef === null ||
    value.lower_bound !== null ||
    value.upper_bound !== null ||
    value.confidence_level !== null ||
    value.inference_status !== null ||
    value.inference_reason !== null ||
    value.computed_estimand_status !== "not_established" ||
    value.computed_target_scope_status !== "not_established" ||
    value.computed_guarantee_status !== "not_established" ||
    value.selected_rows_status !== "not_established" ||
    targetRelation.overall_disposition !== "not_established" ||
    !isOneOf(value.refusal_stage, [
      "prepare",
      "fit",
      "infer",
      "origin_verification",
    ] as const) ||
    !isOneOf(value.refusal_reason, [
      "invalid_point_estimate",
      "method_execution_failed",
      "required_input_unavailable",
      "invalid_selected_input",
      "method_profile_unavailable",
      "runtime_origin_not_verified",
    ] as const) ||
    !isOneOf(value.refusal_diagnostic_code, [
      "hte_input_invalid",
      "empty_selected_input",
      "econml_unavailable",
      "joblib_unavailable",
      "resource_profile_invalid",
      "dml_profile_invalid",
      "meta_profile_invalid",
      "hte_execution_failed",
      "hte_fit_failed",
      "hte_point_estimate_invalid",
      "contrast_not_established",
      "runtime_origin_not_verified",
    ] as const)
  ) {
    return null;
  }
  return {
    ...common,
    kind: "refusal",
    point_estimate: null,
    point_result_ref: null,
    hte_result_ref: null,
    inference_basis_ref: null,
    refusal_diagnostic_ref: refusalDiagnosticRef,
    lower_bound: null,
    upper_bound: null,
    confidence_level: null,
    inference_status: null,
    inference_reason: null,
    refusal_stage: value.refusal_stage,
    refusal_reason: value.refusal_reason,
    refusal_diagnostic_code: value.refusal_diagnostic_code,
  };
}

const LEGACY_LIMITED_KEYS = [
  "kind",
  "schema_version",
  "projection_status",
  "availability",
  "source_result_ref",
  "method",
  "ate",
  "ate_ci_lower",
  "ate_ci_upper",
  "n_samples",
  "n_features",
  "n_subgroups",
  "top_features",
  "warnings",
  "parse_warning",
  "source_reference_profile_status",
  "target_scope_status",
  "bounds_meaning_status",
  "conditional_coverage_status",
  "population_coverage_status",
  "authority_status",
  "limitations",
] as const;
const LEGACY_FEATURE_KEYS = [
  "feature_name",
  "importance_score",
  "importance_rank",
  "method",
] as const;

function parseLegacyLimitations(value: unknown): HTELegacyLimitation[] | null {
  const items = readDenseOwnDataArray(value, 5, 5);
  if (items === null) return null;
  for (const item of items) {
    if (!isOneOf(item, LEGACY_LIMITATION_VALUES)) return null;
  }
  return items as HTELegacyLimitation[];
}

function parseLegacyLimited(
  value: unknown,
): HTELegacyLimitedOutcomeDisplay | null {
  if (
    !hasExactKeys(value, LEGACY_LIMITED_KEYS) ||
    value.kind !== "legacy_limited" ||
    value.schema_version !== "1.0" ||
    value.projection_status !== "legacy_limited" ||
    !isOneOf(value.availability, ["available", "unavailable"] as const) ||
    typeof value.source_result_ref !== "string" ||
    !ARTIFACT_ID.test(value.source_result_ref) ||
    !nullableBoundedString(value.method, 128) ||
    !nullableFiniteNumber(value.ate) ||
    !nullableFiniteNumber(value.ate_ci_lower) ||
    !nullableFiniteNumber(value.ate_ci_upper) ||
    !nullableNonNegativeInteger(value.n_samples) ||
    !nullableNonNegativeInteger(value.n_features) ||
    !nullableNonNegativeInteger(value.n_subgroups) ||
    !isOneOf(value.parse_warning, ["hte_result_parse_failed", null] as const) ||
    value.source_reference_profile_status !== "not_established" ||
    value.target_scope_status !== "not_established" ||
    value.bounds_meaning_status !== "not_established" ||
    value.conditional_coverage_status !== "not_established" ||
    value.population_coverage_status !== "not_established" ||
    value.authority_status !== "limited_display_only"
  ) {
    return null;
  }
  const features = readDenseOwnDataArray(value.top_features, 0, 5);
  const warnings = readDenseOwnDataArray(value.warnings, 0, 64);
  const limitations = parseLegacyLimitations(value.limitations);
  if (!features || !warnings || !limitations) return null;
  const parsedFeatures: HTELegacyFeatureDisplay[] = [];
  for (const feature of features) {
    if (
      !hasExactKeys(feature, LEGACY_FEATURE_KEYS) ||
      !boundedString(feature.feature_name, 1, 256) ||
      !finiteNumber(feature.importance_score) ||
      !Number.isInteger(feature.importance_rank) ||
      (feature.importance_rank as number) < 1 ||
      !boundedString(feature.method, 1, 128)
    ) {
      return null;
    }
    parsedFeatures.push({
      feature_name: feature.feature_name,
      importance_score: feature.importance_score,
      importance_rank: feature.importance_rank as number,
      method: feature.method,
    });
  }
  const parsedWarnings: string[] = [];
  for (const warning of warnings) {
    if (!boundedString(warning, 0, 512)) return null;
    parsedWarnings.push(warning);
  }
  const availabilityValues = [
    value.method,
    value.ate,
    value.ate_ci_lower,
    value.ate_ci_upper,
    value.n_samples,
    value.n_features,
    value.n_subgroups,
  ];
  const allAvailabilityValuesPresent = availabilityValues.every(
    (field) => field !== null,
  );
  const anyAvailabilityValuePresent = availabilityValues.some(
    (field) => field !== null,
  );
  if (
    value.availability === "available"
      ? !allAvailabilityValuesPresent ||
        value.parse_warning !== null ||
        (value.ate_ci_lower as number) > (value.ate_ci_upper as number)
      : anyAvailabilityValuePresent ||
        value.parse_warning !== "hte_result_parse_failed" ||
        features.length !== 0 ||
        warnings.length !== 0
  ) {
    return null;
  }
  return {
    kind: "legacy_limited",
    schema_version: "1.0",
    projection_status: "legacy_limited",
    availability: value.availability,
    source_result_ref: value.source_result_ref,
    method: value.method,
    ate: value.ate,
    ate_ci_lower: value.ate_ci_lower,
    ate_ci_upper: value.ate_ci_upper,
    n_samples: value.n_samples,
    n_features: value.n_features,
    n_subgroups: value.n_subgroups,
    top_features: parsedFeatures,
    warnings: parsedWarnings,
    parse_warning: value.parse_warning,
    source_reference_profile_status: "not_established",
    target_scope_status: "not_established",
    bounds_meaning_status: "not_established",
    conditional_coverage_status: "not_established",
    population_coverage_status: "not_established",
    authority_status: "limited_display_only",
    limitations,
  };
}

function nullableNonNegativeInteger(value: unknown): value is number | null {
  return (
    value === null || (Number.isSafeInteger(value) && (value as number) >= 0)
  );
}

/** Parse the owner-selected scalar HTE summary carried by the Runtime GET. */
export function parseDirectMethodExecutionHTESummary(
  value: unknown,
): HTEOutcomeDisplayModel | null {
  return parseOutcome(value, true);
}

/** Parse the bounded scalar HTE projection from an existing decision-packet preview. */
export function parseDecisionPacketHTEProjection(
  payload: unknown,
): DecisionPacketHTEProjectionResult {
  if (
    payload === null ||
    typeof payload !== "object" ||
    Array.isArray(payload)
  ) {
    return { status: "absent" };
  }
  if (!isRecord(payload)) return { status: "invalid" };
  let statusDescriptor: PropertyDescriptor | undefined;
  let hteDescriptor: PropertyDescriptor | undefined;
  let legacyDescriptor: PropertyDescriptor | undefined;
  try {
    statusDescriptor = Object.getOwnPropertyDescriptor(
      payload,
      "hte_projection_status",
    );
    hteDescriptor = Object.getOwnPropertyDescriptor(payload, "hte");
    legacyDescriptor = Object.getOwnPropertyDescriptor(
      payload,
      "hte_legacy_limited",
    );
  } catch {
    return { status: "invalid" };
  }
  for (const descriptor of [
    statusDescriptor,
    hteDescriptor,
    legacyDescriptor,
  ]) {
    if (descriptor !== undefined && !("value" in descriptor)) {
      return { status: "invalid" };
    }
  }

  // Older Runtime responses have no projection discriminator. A present HTE
  // value must still pass the same strict owner DTO parser; legacy raw builder
  // payloads are never accepted on this branch.
  if (statusDescriptor === undefined) {
    if (legacyDescriptor !== undefined) return { status: "invalid" };
    if (hteDescriptor === undefined) return { status: "absent" };
    const outcome =
      hteDescriptor.value === null
        ? null
        : parseOutcome(hteDescriptor.value, true);
    return outcome ? { status: "valid", outcome } : { status: "invalid" };
  }

  const status = statusDescriptor.value;
  const hte = hteDescriptor?.value;
  const legacy = legacyDescriptor?.value;
  if (status === "absent") {
    return (hte === undefined || hte === null) &&
      (legacy === undefined || legacy === null)
      ? { status: "absent" }
      : { status: "invalid" };
  }
  if (status === "invalid") {
    return (hte === undefined || hte === null) &&
      (legacy === undefined || legacy === null)
      ? { status: "invalid" }
      : { status: "invalid" };
  }
  if (status === "typed") {
    if (legacy !== undefined && legacy !== null) return { status: "invalid" };
    const outcome =
      hte === undefined || hte === null ? null : parseOutcome(hte, true);
    return outcome ? { status: "valid", outcome } : { status: "invalid" };
  }
  if (status === "legacy_limited") {
    if (hte !== undefined && hte !== null) return { status: "invalid" };
    const outcome = parseLegacyLimited(legacy);
    return outcome ? { status: "valid", outcome } : { status: "invalid" };
  }
  return { status: "invalid" };
}
