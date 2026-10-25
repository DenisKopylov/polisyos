import {
  parseDirectMethodExecutionHTESummary,
  type HTEOutcomeDisplayModel,
} from "@/features/artifacts/domain/decisionPacketHte";

const PROJECTION_STATUSES = [
  "withheld",
  "absent",
  "legacy_unbound",
  "accepted_pending",
  "selected",
  "input_refused",
  "execution_failed",
  "unavailable",
] as const;

const SUCCESSOR_METHODS = [
  "causal.hte.causal_forest@2.0.0",
  "causal.hte.double_ml@2.0.0",
  "causal.hte.meta_learner@2.0.0",
  "causal.hte.forest_dr@2.0.0",
] as const;

const PROJECTION_KEYS = [
  "status",
  "request",
  "selection",
  "input_refusal",
  "time_roles",
  "refusal_code",
  "limitations",
  "candidate_only",
] as const;

const SELECTION_KEYS = [
  "selection_kind",
  "job_id",
  "run_id",
  "attempt",
  "requested_source_ref",
  "observational_run_intent_ref",
  "content_admitted_intent_ref",
  "resource_policy_ref",
  "submitted_input_ref",
  "effective_input_ref",
  "method_result_ref",
  "method_evidence_ref",
  "owned_attempt_anchor_ref",
  "hte_outcome_ref",
  "point_result_ref",
  "hte_result_ref",
  "inference_basis_ref",
  "refusal_diagnostic_ref",
  "invocation_basis_ref",
  "hte",
  "contract_target_id",
  "contract_target",
  "selection_digest",
  "source_access_revalidation_status",
  "method_fqn",
  "method_version",
  "method_abi_digest",
  "method_build_digest",
  "method_build_digest_scope",
  "resource_policy_digest",
  "source_protocol",
  "normalization",
  "limitations",
  "method_dispatch_binding_status",
  "owned_hte_request_context",
  "candidate_outcome",
  "posterior_summary_refs",
] as const;

const REQUEST_CONTEXT_KEYS = [
  "request_estimand_status",
  "request_estimand",
  "request_target_scope_status",
  "request_target_scope",
  "outcome_variable_status",
  "outcome_variable_id",
  "treatment_variable_status",
  "treatment_variable_id",
  "contrast_status",
  "control_value",
  "treated_value",
  "request_alpha_status",
  "requested_alpha",
  "requested_guarantee_status",
  "requested_guarantee",
  "search_uncertainty_task_binding_ref",
  "materialization_binding_ref",
] as const;

const REQUEST_SUMMARY_KEYS = [
  "requested_source_ref",
  "requested_intent_ref",
  "resource_policy_ref",
  "source_protocol",
  "method_fqn",
  "method_version",
  "owned_hte_request_context",
  "method_abi_digest",
  "method_build_digest",
  "method_build_digest_scope",
  "resource_policy_digest",
  "resolved_params_sha256",
  "seed",
  "seed_policy_revision",
  "required_estimator_n_jobs",
  "max_manifest_bytes",
  "max_bytes",
  "max_depth",
  "max_elements",
  "requested_at",
] as const;
const REQUIRED_REQUEST_SUMMARY_KEYS = REQUEST_SUMMARY_KEYS.filter(
  (key) => key !== "required_estimator_n_jobs",
);

const TIME_ROLE_KEYS = [
  "admitted_at",
  "execution_started_at",
  "execution_finished_at",
  "source_observation_epoch",
  "owner_verified_at",
  "reader_at",
] as const;

const REQUIRED_REQUEST_CONTEXT_KEYS = REQUEST_CONTEXT_KEYS.filter(
  (key) =>
    key !== "search_uncertainty_task_binding_ref" &&
    key !== "materialization_binding_ref" &&
    !key.endsWith("_id") &&
    !key.endsWith("_estimand") &&
    !key.endsWith("_scope") &&
    !key.endsWith("_alpha") &&
    !key.endsWith("_guarantee") &&
    key !== "control_value" &&
    key !== "treated_value",
);

export type RunExecutionHteProjection =
  | { kind: "absent" }
  | { kind: "invalid" }
  | {
      kind: "without_hte";
      projection_status: (typeof PROJECTION_STATUSES)[number];
      limitations: string[];
    }
  | {
      kind: "selected_without_hte";
      method_fqn: string;
      limitations: string[];
    }
  | {
      kind: "hte";
      projection_status: "selected";
      summary: HTEOutcomeDisplayModel;
      limitations: string[];
    };

type DataRecord = Record<string, unknown>;

function readPlainDataRecord(value: unknown): DataRecord | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  try {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) return null;
    const keys = Reflect.ownKeys(value);
    const result: DataRecord = Object.create(null) as DataRecord;
    for (const key of keys) {
      if (typeof key !== "string") return null;
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      if (!descriptor || !("value" in descriptor)) return null;
      result[key] = descriptor.value;
    }
    return result;
  } catch {
    return null;
  }
}

function hasOnlyKnownKeys(
  value: DataRecord,
  allowed: readonly string[],
): boolean {
  const actual = Object.keys(value);
  const allowSet = new Set(allowed);
  for (const key of actual) {
    if (!allowSet.has(key)) return false;
  }
  return true;
}

function hasRequiredKeys(
  value: DataRecord,
  required: readonly string[],
): boolean {
  for (const key of required) {
    if (!Object.hasOwn(value, key)) return false;
  }
  return true;
}

function nullableField(value: DataRecord, key: string): unknown {
  return value[key] === undefined ? null : value[key];
}

function isIntegerAtLeast(value: unknown, minimum: number): value is number {
  return (
    typeof value === "number" && Number.isSafeInteger(value) && value >= minimum
  );
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

function readDenseStrings(
  value: unknown,
  minimumLength: number,
  maximumLength: number,
): string[] | null {
  try {
    if (
      !Array.isArray(value) ||
      Object.getPrototypeOf(value) !== Array.prototype
    ) {
      return null;
    }
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
    let hasLength = false;
    for (const key of ownKeys) {
      if (key === "length") {
        hasLength = true;
      } else if (
        typeof key !== "string" ||
        !isArrayIndexKey(key) ||
        Number(key) >= length
      ) {
        return null;
      }
    }
    if (!hasLength) return null;
    let ancestor: object | null = Array.prototype;
    while (ancestor !== null) {
      const keys = Reflect.ownKeys(ancestor);
      for (const key of keys) {
        if (isArrayIndexKey(key)) return null;
      }
      ancestor = Object.getPrototypeOf(ancestor);
    }
    const result: string[] = [];
    for (let index = 0; index < length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      if (
        !descriptor ||
        !("value" in descriptor) ||
        descriptor.enumerable !== true ||
        typeof descriptor.value !== "string" ||
        descriptor.value.trim().length === 0
      ) {
        return null;
      }
      result.push(descriptor.value);
    }
    return result;
  } catch {
    return null;
  }
}

function sameReference(left: unknown, right: unknown): boolean {
  const leftRecord = readPlainDataRecord(left);
  const rightRecord = readPlainDataRecord(right);
  if (!leftRecord || !rightRecord) return false;
  const keys = [
    "artifact_id",
    "kind",
    "media_type",
    "manifest_profile_sha256",
  ] as const;
  if (
    Object.keys(leftRecord).length !== keys.length ||
    Object.keys(rightRecord).length !== keys.length ||
    !hasOnlyKnownKeys(leftRecord, keys) ||
    !hasOnlyKnownKeys(rightRecord, keys) ||
    typeof leftRecord.artifact_id !== "string" ||
    !/^sha256:[0-9a-f]{64}$/u.test(leftRecord.artifact_id) ||
    typeof rightRecord.artifact_id !== "string" ||
    !/^sha256:[0-9a-f]{64}$/u.test(rightRecord.artifact_id) ||
    typeof leftRecord.kind !== "string" ||
    leftRecord.kind.trim().length === 0 ||
    typeof rightRecord.kind !== "string" ||
    rightRecord.kind.trim().length === 0 ||
    leftRecord.media_type !== "application/json" ||
    rightRecord.media_type !== "application/json" ||
    typeof leftRecord.manifest_profile_sha256 !== "string" ||
    !/^sha256:[0-9a-f]{64}$/u.test(leftRecord.manifest_profile_sha256) ||
    typeof rightRecord.manifest_profile_sha256 !== "string" ||
    !/^sha256:[0-9a-f]{64}$/u.test(rightRecord.manifest_profile_sha256)
  ) {
    return false;
  }
  for (const key of keys) {
    if (leftRecord[key] !== rightRecord[key]) return false;
  }
  return true;
}

function selectionMatchesSummary(
  selection: DataRecord,
  summary: HTEOutcomeDisplayModel,
): boolean {
  if (
    selection.selection_kind !== "direct_method" ||
    selection.method_fqn !== summary.method_fqn ||
    selection.method_version !== "2.0.0" ||
    selection.method_abi_digest !== summary.method_abi_digest ||
    (selection.candidate_outcome !== null &&
      selection.candidate_outcome !== undefined) ||
    selection.method_result_ref === undefined ||
    selection.method_evidence_ref === undefined ||
    selection.effective_input_ref === undefined ||
    selection.resource_policy_ref === undefined ||
    selection.resource_policy_digest !==
      summary.resource_evidence.owner_policy_digest ||
    !sameReference(selection.method_result_ref, summary.method_result_ref) ||
    !sameReference(
      selection.method_evidence_ref,
      summary.method_evidence_ref,
    ) ||
    !sameReference(selection.effective_input_ref, summary.source_data_ref) ||
    !sameReference(
      selection.resource_policy_ref,
      summary.resource_evidence.owner_policy_ref,
    )
  ) {
    return false;
  }

  const refPairs: Array<[unknown, unknown]> = [
    [
      nullableField(selection, "owned_attempt_anchor_ref"),
      summary.owned_attempt_anchor_ref,
    ],
    [nullableField(selection, "hte_outcome_ref"), summary.hte_outcome_ref],
    [nullableField(selection, "point_result_ref"), summary.point_result_ref],
    [nullableField(selection, "hte_result_ref"), summary.hte_result_ref],
    [
      nullableField(selection, "inference_basis_ref"),
      summary.inference_basis_ref,
    ],
    [
      nullableField(selection, "refusal_diagnostic_ref"),
      summary.refusal_diagnostic_ref,
    ],
  ];
  for (const [selectedRef, summaryRef] of refPairs) {
    if (summaryRef === null) {
      if (selectedRef !== null) return false;
    } else if (!sameReference(selectedRef, summaryRef)) {
      return false;
    }
  }

  const context = readPlainDataRecord(selection.owned_hte_request_context);
  if (
    !context ||
    !hasOnlyKnownKeys(context, REQUEST_CONTEXT_KEYS) ||
    !hasRequiredKeys(context, REQUIRED_REQUEST_CONTEXT_KEYS)
  ) {
    return false;
  }
  const contextPairs: Array<[unknown, unknown]> = [
    [context.request_estimand_status, summary.request_estimand_status],
    [nullableField(context, "request_estimand"), summary.request_estimand],
    [context.request_target_scope_status, summary.request_target_scope_status],
    [
      nullableField(context, "request_target_scope"),
      summary.request_target_scope,
    ],
    [context.outcome_variable_status, summary.outcome_variable_status],
    [
      nullableField(context, "outcome_variable_id"),
      summary.outcome_variable_id,
    ],
    [context.treatment_variable_status, summary.treatment_variable_status],
    [
      nullableField(context, "treatment_variable_id"),
      summary.treatment_variable_id,
    ],
    [context.contrast_status, summary.request_contrast_status],
    [nullableField(context, "control_value"), summary.control_value],
    [nullableField(context, "treated_value"), summary.treated_value],
    [context.request_alpha_status, summary.request_alpha_status],
    [nullableField(context, "requested_alpha"), summary.requested_alpha],
    [context.requested_guarantee_status, summary.requested_guarantee_status],
    [
      nullableField(context, "requested_guarantee"),
      summary.requested_guarantee,
    ],
  ];
  for (const [contextValue, summaryValue] of contextPairs) {
    if (contextValue !== summaryValue) return false;
  }

  const contextBinding = context.materialization_binding_ref;
  if (summary.resource_evidence.owner_policy_revision === "r5") {
    if (
      !summary.materialization_binding_ref ||
      (contextBinding !== undefined &&
        contextBinding !== null &&
        !sameReference(contextBinding, summary.materialization_binding_ref))
    ) {
      return false;
    }
  } else if (
    contextBinding !== undefined &&
    contextBinding !== null &&
    (!summary.materialization_binding_ref ||
      !sameReference(contextBinding, summary.materialization_binding_ref))
  ) {
    return false;
  }
  return true;
}

function requestMatchesSelection(
  requestValue: unknown,
  selection: DataRecord,
): boolean {
  const request = readPlainDataRecord(requestValue);
  const context = readPlainDataRecord(selection.owned_hte_request_context);
  if (
    !request ||
    !context ||
    !hasOnlyKnownKeys(request, REQUEST_SUMMARY_KEYS) ||
    !hasRequiredKeys(request, REQUIRED_REQUEST_SUMMARY_KEYS) ||
    request.method_fqn !== selection.method_fqn ||
    request.method_version !== selection.method_version ||
    request.method_abi_digest !== selection.method_abi_digest ||
    request.method_build_digest !== selection.method_build_digest ||
    request.resource_policy_digest !== selection.resource_policy_digest ||
    (request.source_protocol !== "method_input_envelope_v1" &&
      request.source_protocol !== "legacy_hte_json_v1") ||
    request.method_build_digest_scope !== "class_source_only" ||
    request.seed_policy_revision !== "server_seed_zero_v1" ||
    !sameReference(
      request.requested_source_ref,
      selection.requested_source_ref,
    ) ||
    !sameReference(
      request.requested_intent_ref,
      selection.observational_run_intent_ref,
    ) ||
    !sameReference(request.resource_policy_ref, selection.resource_policy_ref)
  ) {
    return false;
  }
  for (const key of [
    "method_abi_digest",
    "method_build_digest",
    "resource_policy_digest",
    "resolved_params_sha256",
  ]) {
    const digest = request[key];
    if (typeof digest !== "string" || !/^[0-9a-f]{64}$/u.test(digest)) {
      return false;
    }
  }
  if (
    !isIntegerAtLeast(request.seed, 0) ||
    !isIntegerAtLeast(request.max_manifest_bytes, 1) ||
    !isIntegerAtLeast(request.max_bytes, 1) ||
    !isIntegerAtLeast(request.max_depth, 1) ||
    !isIntegerAtLeast(request.max_elements, 1) ||
    (request.required_estimator_n_jobs !== undefined &&
      request.required_estimator_n_jobs !== null &&
      !isIntegerAtLeast(request.required_estimator_n_jobs, 1)) ||
    typeof request.requested_at !== "string" ||
    !Number.isFinite(Date.parse(request.requested_at))
  ) {
    return false;
  }
  const requestContext = readPlainDataRecord(request.owned_hte_request_context);
  if (
    !requestContext ||
    !hasOnlyKnownKeys(requestContext, REQUEST_CONTEXT_KEYS)
  ) {
    return false;
  }
  const pairedValues = [
    "request_estimand_status",
    "request_estimand",
    "request_target_scope_status",
    "request_target_scope",
    "outcome_variable_status",
    "outcome_variable_id",
    "treatment_variable_status",
    "treatment_variable_id",
    "contrast_status",
    "control_value",
    "treated_value",
    "request_alpha_status",
    "requested_alpha",
    "requested_guarantee_status",
    "requested_guarantee",
  ] as const;
  for (const key of pairedValues) {
    if (nullableField(requestContext, key) !== nullableField(context, key)) {
      return false;
    }
  }
  for (const key of [
    "search_uncertainty_task_binding_ref",
    "materialization_binding_ref",
  ]) {
    const requestRef = nullableField(requestContext, key);
    const selectedRef = nullableField(context, key);
    if (requestRef === null && selectedRef === null) continue;
    if (!sameReference(requestRef, selectedRef)) return false;
  }
  return true;
}

function validTimeRoles(value: unknown): boolean {
  const roles = readPlainDataRecord(value);
  if (
    !roles ||
    !hasOnlyKnownKeys(roles, TIME_ROLE_KEYS) ||
    !hasRequiredKeys(roles, TIME_ROLE_KEYS) ||
    typeof roles.reader_at !== "string" ||
    !Number.isFinite(Date.parse(roles.reader_at))
  ) {
    return false;
  }
  for (const key of TIME_ROLE_KEYS) {
    if (key === "reader_at") continue;
    const timestamp = roles[key];
    if (
      timestamp !== null &&
      (typeof timestamp !== "string" || !Number.isFinite(Date.parse(timestamp)))
    ) {
      return false;
    }
  }
  return true;
}

/** Read only the selected HTE scalar summary from the existing run-details GET. */
export function parseRunExecutionHteProjection(
  value: unknown,
): RunExecutionHteProjection {
  if (value === undefined || value === null) return { kind: "absent" };
  const projection = readPlainDataRecord(value);
  if (
    !projection ||
    !hasOnlyKnownKeys(projection, PROJECTION_KEYS) ||
    !hasRequiredKeys(projection, ["status", "candidate_only"]) ||
    !(PROJECTION_STATUSES as readonly unknown[]).includes(projection.status) ||
    projection.candidate_only !== true
  ) {
    return { kind: "invalid" };
  }
  const projectionStatus =
    projection.status as (typeof PROJECTION_STATUSES)[number];
  const limitations =
    projection.limitations === undefined
      ? []
      : readDenseStrings(projection.limitations, 0, 32);
  if (limitations === null) return { kind: "invalid" };

  if (projectionStatus !== "selected") {
    if (projection.selection !== undefined && projection.selection !== null) {
      return { kind: "invalid" };
    }
    return {
      kind: "without_hte",
      projection_status: projectionStatus,
      limitations,
    };
  }

  const selection = readPlainDataRecord(projection.selection);
  if (
    !selection ||
    !hasOnlyKnownKeys(selection, SELECTION_KEYS) ||
    !hasRequiredKeys(selection, ["selection_kind", "method_fqn"])
  ) {
    return { kind: "invalid" };
  }
  if (
    selection.selection_kind !== "direct_method" ||
    typeof selection.method_fqn !== "string"
  ) {
    return { kind: "invalid" };
  }
  if (
    !(SUCCESSOR_METHODS as readonly unknown[]).includes(selection.method_fqn)
  ) {
    return {
      kind: "selected_without_hte",
      method_fqn: selection.method_fqn,
      limitations,
    };
  }

  const summary = parseDirectMethodExecutionHTESummary(selection.hte);
  if (
    !summary ||
    !requestMatchesSelection(projection.request, selection) ||
    !validTimeRoles(projection.time_roles) ||
    !selectionMatchesSummary(selection, summary) ||
    (selection.limitations !== undefined &&
      JSON.stringify(readDenseStrings(selection.limitations, 1, 5)) !==
        JSON.stringify(limitations))
  ) {
    return { kind: "invalid" };
  }
  return {
    kind: "hte",
    projection_status: "selected",
    summary,
    limitations,
  };
}
