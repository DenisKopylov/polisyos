import { z } from "zod";

import type {
  DecisionValidityStatus,
  QuantityUncertainty,
  QuantityValueOutput,
  RunTerminality,
} from "@polisyos/runtime-api-client";

import type { components } from "./types";
import { parseRunExecutionHteProjection } from "@/features/runs/domain/runExecutionHte";
import {
  isGeneratedProjectionAuthority,
  normalizeApiProjectionFailClosed,
  normalizeOperatorProjectionLabelFailClosed,
  type GeneratedProjectionAuthority,
} from "@/shared/lib/domain/projectionFailClosed";

const apiMetaSchema = z.object({
  request_id: z.string(),
  generated_at: z.string(),
  source_kinds: z.array(z.literal("core_run")).default([]),
});

const cursorPageSchema = z.object({
  limit: z.number(),
  cursor: z.string().nullable().optional(),
  next_cursor: z.string().nullable().optional(),
  count: z.number(),
  total: z.number().nullable().optional(),
});

const temporalRefSchema = z.object({
  valid_at: z.string().nullable().optional(),
  tx_at: z.string().nullable().optional(),
  branch: z.string().nullable().optional(),
  snapshot_id: z.string().nullable().optional(),
  scenario_id: z.string().nullable().optional(),
});

const temporalScopeSchema = temporalRefSchema.nullable().optional();

const decisionValidityStatusMembers = {
  active: true,
  requires_human_review: true,
  reissued: true,
  review_required: true,
  revoked: true,
  stale: true,
  superseded: true,
  warning: true,
  withdrawn: true,
} as const satisfies Record<DecisionValidityStatus, true>;

const decisionValidityStatusSchema = z
  .string()
  .refine(
    (value): value is DecisionValidityStatus =>
      Object.hasOwn(decisionValidityStatusMembers, value),
    "unknown generated decision validity status",
  );

const runTerminalityMembers = {
  non_terminal: true,
  not_established: true,
  terminal: true,
} as const satisfies Record<RunTerminality, true>;

const runTerminalitySchema = z
  .string()
  .refine(
    (value): value is RunTerminality =>
      Object.hasOwn(runTerminalityMembers, value),
    "unknown generated run terminality",
  );

const temporalRangeSchema = z.object({
  earliest: z.string().nullable().optional(),
  latest: z.string().nullable().optional(),
});

const temporalEventPointSchema = z.object({
  id: z.string(),
  timestamp: z.string(),
  kind: z.enum([
    "run_start",
    "run_finish",
    "trace_event",
    "policy_change",
    "late_evidence",
    "correction",
    "snapshot",
    "now",
  ]),
  label: z.string(),
  valid_at: z.string().nullable().optional(),
  tx_at: z.string().nullable().optional(),
  observed: z.boolean().optional(),
});

const temporalSurfaceCapabilitySchema = z.object({
  surface: z.string(),
  supported: z.boolean(),
  resolution: z.string(),
  reason_code: z.string().nullable().optional(),
  valid_range: temporalRangeSchema.nullable().optional(),
  tx_range: temporalRangeSchema.nullable().optional(),
  nearest_event_points: z.array(temporalEventPointSchema).optional(),
  gaps: z
    .array(
      z.object({
        start: z.string().nullable().optional(),
        end: z.string().nullable().optional(),
        reason_code: z.string(),
        label: z.string().nullable().optional(),
      }),
    )
    .optional(),
});

const temporalCapabilitiesViewSchema = z.object({
  run_id: z.string().nullable().optional(),
  default_scope: temporalScopeSchema,
  valid_range: temporalRangeSchema,
  tx_range: temporalRangeSchema,
  resolution: z.string(),
  surfaces: z.array(temporalSurfaceCapabilitySchema).optional(),
  event_points: z.array(temporalEventPointSchema).optional(),
});

type DataViewRequestProfileStatus =
  components["schemas"]["RunEvidenceContextView"]["data_view_request_profile_status"];

const dataViewRequestProfileStatusMembers = {
  caller_selected_profile: true,
  worker_default_limited: true,
  not_requested: true,
  not_established: true,
} as const satisfies Record<DataViewRequestProfileStatus, true>;

const dataViewRequestProfileStatusSchema = z
  .string()
  .refine(
    (value): value is DataViewRequestProfileStatus =>
      Object.hasOwn(dataViewRequestProfileStatusMembers, value),
    "unknown generated data-view request profile status",
  )
  .default("not_established");

const artifactRefSchema = z.object({
  artifact_id: z.string(),
  kind: z.string().optional(),
  media_type: z.string().optional(),
  manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
});

export const coreArtifactRefSchema = z
  .object({
    artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    kind: z.string().min(1),
    media_type: z.string().min(1),
    manifest_profile_sha256: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
  })
  .strict();

function sameCoreArtifactRefView(
  left: z.infer<typeof coreArtifactRefSchema> | null | undefined,
  right: z.infer<typeof coreArtifactRefSchema> | null | undefined,
): boolean {
  return (
    left != null &&
    right != null &&
    left.artifact_id === right.artifact_id &&
    left.kind === right.kind &&
    left.media_type === right.media_type &&
    (left.manifest_profile_sha256 ?? null) ===
      (right.manifest_profile_sha256 ?? null)
  );
}

const controlPreAdmissionAttemptStatusSchema = z.enum([
  "started",
  "settled",
  "admitted",
  "refused",
  "cancelled",
  "failed",
]);
const controlPreAdmissionProfileSchema = z.enum([
  "dev",
  "research",
  "governed",
  "production",
]);
const controlPreAdmissionObservationSchema = z.enum([
  "not_applicable",
  "no_call",
  "complete",
  "unavailable",
]);
const controlPreAdmissionNoCallReasonSchema = z.enum([
  "producer_run_binding_not_established",
  "provider_preflight_not_started",
]);
const controlPreAdmissionEventSchema = z
  .object({
    event_id: z.string().min(1),
    event_type: controlPreAdmissionAttemptStatusSchema,
    failure_code: z
      .string()
      .regex(/^[A-Za-z0-9._-]{1,96}$/)
      .nullable()
      .default(null),
    job_id: z.string().nullable().default(null),
    observed_at: z.iso.datetime({ offset: true }),
    producer_event_ids: z.array(z.string()).default([]),
    // A missing call state is malformed input, not a no-call observation.
    producer_event_observation: controlPreAdmissionObservationSchema,
    producer_no_call_reason: controlPreAdmissionNoCallReasonSchema
      .nullable()
      .default(null),
    sequence: z.number().int().positive(),
  })
  .strict()
  .superRefine((event, context) => {
    const reason = event.producer_no_call_reason;
    if (
      (event.producer_event_observation === "no_call") !== (reason !== null) ||
      (reason !== null && event.failure_code !== reason)
    ) {
      context.addIssue({
        code: "custom",
        path: ["producer_no_call_reason"],
        message: "control_pre_admission_event_call_state_mismatch",
      });
    }
  });
const controlPreAdmissionOwnerBindingSchema = z
  .object({
    actor_subject_sha256: z.string().regex(/^[a-f0-9]{64}$/),
    body_sha256: z.string().regex(/^[a-f0-9]{64}$/),
    cell_id: z.string().min(1),
    effective_execution_profile: controlPreAdmissionProfileSchema,
    intent_id: z.string().regex(/^[a-f0-9]{32}$/),
    purpose: z.literal("control.nl_pre_admission.v1"),
    request_content_sha256: z.string().regex(/^sha256:[a-f0-9]{64}$/),
    run_id: z.string().min(1),
    scope_id: z.literal("control.runs.nl"),
    scope_kind: z.literal("route"),
    tenant_id: z.string().min(1),
  })
  .strict();
export const controlPreAdmissionAttemptResponseSchema = z
  .object({
    attempt_id: z.string().regex(/^[a-f0-9]{32}$/),
    created_at: z.iso.datetime({ offset: true }),
    effective_execution_profile: controlPreAdmissionProfileSchema,
    failure_code: z
      .string()
      .regex(/^[A-Za-z0-9._-]{1,96}$/)
      .nullable()
      .default(null),
    history: z.array(controlPreAdmissionEventSchema).min(1),
    intent_sha256: z.string().regex(/^[a-f0-9]{64}$/),
    job_id: z.string().min(1).nullable().default(null),
    meta: apiMetaSchema,
    owner_binding: controlPreAdmissionOwnerBindingSchema,
    producer_event_ids: z.array(z.string()).default([]),
    producer_event_observation: controlPreAdmissionObservationSchema,
    producer_no_call_reason: controlPreAdmissionNoCallReasonSchema
      .nullable()
      .default(null),
    run_id: z.string().min(1),
    status: controlPreAdmissionAttemptStatusSchema,
    updated_at: z.iso.datetime({ offset: true }),
  })
  .strict()
  .superRefine((attempt, context) => {
    const reason = attempt.producer_no_call_reason;
    const lastEvent = attempt.history.at(-1);
    if (
      (attempt.producer_event_observation === "no_call") !==
        (reason !== null) ||
      (reason !== null && attempt.failure_code !== reason) ||
      lastEvent == null ||
      lastEvent.producer_no_call_reason !== reason
    ) {
      context.addIssue({
        code: "custom",
        path: ["producer_no_call_reason"],
        message: "control_pre_admission_attempt_call_state_mismatch",
      });
    }
  });
export type ControlPreAdmissionAttemptResponse = z.output<
  typeof controlPreAdmissionAttemptResponseSchema
>;
export type RunArtifactRef = components["schemas"]["ArtifactRef-Output"];

const operatorProjectionStateLabelSchema = z
  .object({
    authority: z.enum(["runtime_authority", "projection_only"]),
    label: z.string(),
    state: z.enum([
      "draft",
      "projection_only",
      "redacted",
      "stale",
      "contested",
      "projected",
      "blocked",
      "readiness_closed",
      "approved",
      "rejected",
      "published_blocked",
      "publishable",
    ]),
  })
  .transform(normalizeOperatorProjectionLabelFailClosed);

const policyDesignCaseProjectionSchema = z
  .custom<GeneratedProjectionAuthority>(isGeneratedProjectionAuthority, {
    message: "Policy Design Case projection lacks generated authority fields",
  })
  .transform(normalizeApiProjectionFailClosed);

const operatorDiagnosticSchema = z.object({
  authoritative_runtime_state: z.string(),
  projection_source: z.string(),
  owner: z.string(),
  phase: z.string(),
  first_blocking_cause: z.string(),
  upstream_missing_input: z.string().nullable().optional(),
  downstream_impact: z.string(),
  authority_refs: z.record(z.string(), z.string()).optional(),
  blocker_overridable: z.boolean().default(false),
  evidence_refs: z.array(z.string()).optional(),
  next_diagnostic_command: z.string(),
  projection_labels: z.array(operatorProjectionStateLabelSchema).optional(),
});

const runN5InteractionSampleSchema = z
  .object({
    seed: z.number().int(),
    value: z.number(),
  })
  .strict();

const runN5InteractionSamplingSummarySchema = z
  .object({
    status: z.enum(["estimated", "standard_error_not_estimated"]),
    replicate_count: z.number().int().positive(),
    seeds: z.array(z.number().int()).min(1),
    samples: z.array(runN5InteractionSampleSchema).min(1),
    mean: z.number(),
    standard_error: z.number().nullable(),
  })
  .strict()
  .superRefine((summary, context) => {
    const values = summary.samples.map((sample) => sample.value);
    const expectedMean =
      values.reduce((sum, value) => sum + value, 0) / values.length;
    const expectedStatus =
      values.length === 1 ? "standard_error_not_estimated" : "estimated";
    if (
      summary.replicate_count !== summary.seeds.length ||
      summary.replicate_count !== summary.samples.length ||
      new Set(summary.seeds).size !== summary.seeds.length ||
      summary.samples.some(
        (sample, index) => sample.seed !== summary.seeds[index],
      )
    ) {
      context.addIssue({
        code: "custom",
        path: ["seeds"],
        message: "run_n5_interaction_seed_denominator_mismatch",
      });
    }
    if (summary.status !== expectedStatus) {
      context.addIssue({
        code: "custom",
        path: ["status"],
        message: "run_n5_interaction_sampling_status_mismatch",
      });
    }
    if (Math.abs(summary.mean - expectedMean) > 1e-12) {
      context.addIssue({
        code: "custom",
        path: ["mean"],
        message: "run_n5_interaction_mean_recomputation_mismatch",
      });
    }
    if (values.length === 1) {
      if (summary.standard_error !== null) {
        context.addIssue({
          code: "custom",
          path: ["standard_error"],
          message: "run_n5_interaction_single_draw_se_must_be_unestimated",
        });
      }
    } else {
      const sampleVariance =
        values.reduce((sum, value) => sum + (value - expectedMean) ** 2, 0) /
        (values.length - 1);
      const expectedSe = Math.sqrt(sampleVariance / values.length);
      if (
        summary.standard_error === null ||
        Math.abs(summary.standard_error - expectedSe) > 1e-12
      ) {
        context.addIssue({
          code: "custom",
          path: ["standard_error"],
          message: "run_n5_interaction_se_recomputation_mismatch",
        });
      }
    }
  });

const runN5InteractionTermSchema = z
  .object({
    atom_ids: z.tuple([z.string().min(1), z.string().min(1)]),
    outcome: z.string().min(1),
    by_step: z.record(z.string(), z.number()),
    replication_sampling_by_step: z
      .record(z.string(), runN5InteractionSamplingSummarySchema)
      .default({}),
  })
  .strict()
  .superRefine((term, context) => {
    for (const [step, summary] of Object.entries(
      term.replication_sampling_by_step,
    )) {
      if (
        !(step in term.by_step) ||
        Math.abs(term.by_step[step] - summary.mean) > 1e-12
      ) {
        context.addIssue({
          code: "custom",
          path: ["replication_sampling_by_step", step],
          message: "run_n5_interaction_sample_mean_mismatch",
        });
      }
    }
  });

const runN5InteractionEvidenceSchema = z
  .object({
    schema_version: z.enum([
      "policyos.runtime.joint_simulation_horizon.v1",
      "policyos.runtime.joint_simulation_horizon.v2",
      "policyos.runtime.joint_simulation_horizon.v3",
      "policyos.runtime.joint_simulation_horizon.v4",
    ]),
    numeric_interaction: z.enum([
      "none",
      "additive",
      "non_additive",
      "unsupported",
    ]),
    numeric_interaction_basis: z.enum([
      "finite_checked_model_point_estimate_only",
      "not_established",
    ]),
    interaction_sampling_status: z.enum([
      "estimated",
      "standard_error_not_estimated",
      "not_established",
    ]),
    interaction_terms: z.array(runN5InteractionTermSchema).default([]),
    higher_order_residuals: z.record(
      z.string(),
      z.record(z.string(), z.number()),
    ),
    higher_order_residual_sampling: z.record(
      z.string(),
      z.record(z.string(), runN5InteractionSamplingSummarySchema),
    ),
    checked_interaction_orders: z.array(z.number().int()).default([]),
    authority_purpose: z.literal("candidate_checked_model_only"),
    publication_authority: z.literal(false),
  })
  .strict()
  .superRefine((evidence, context) => {
    const current =
      evidence.schema_version ===
      "policyos.runtime.joint_simulation_horizon.v4";
    if (!current) {
      if (
        evidence.numeric_interaction !== "unsupported" ||
        evidence.numeric_interaction_basis !== "not_established" ||
        evidence.interaction_sampling_status !== "not_established" ||
        Object.keys(evidence.higher_order_residual_sampling).length > 0 ||
        evidence.interaction_terms.some(
          (term) => Object.keys(term.replication_sampling_by_step).length > 0,
        )
      ) {
        context.addIssue({
          code: "custom",
          message: "run_n5_legacy_interaction_uncertainty_laundered",
        });
      }
      return;
    }
    const estimated = evidence.interaction_sampling_status === "estimated";
    if (
      estimated !==
      (evidence.numeric_interaction_basis ===
        "finite_checked_model_point_estimate_only")
    ) {
      context.addIssue({
        code: "custom",
        path: ["numeric_interaction_basis"],
        message: "run_n5_interaction_basis_status_mismatch",
      });
    }
    if (!estimated && evidence.numeric_interaction !== "unsupported") {
      context.addIssue({
        code: "custom",
        path: ["numeric_interaction"],
        message: "run_n5_unestimated_interaction_classification_not_limited",
      });
    }
    if (evidence.interaction_sampling_status !== "not_established") {
      for (const term of evidence.interaction_terms) {
        if (
          Object.keys(term.by_step).length !==
          Object.keys(term.replication_sampling_by_step).length
        ) {
          context.addIssue({
            code: "custom",
            path: ["interaction_terms"],
            message: "run_n5_interaction_summary_step_missing",
          });
        }
      }
      for (const [outcome, byStep] of Object.entries(
        evidence.higher_order_residuals,
      )) {
        if (
          Object.keys(byStep).length !==
          Object.keys(evidence.higher_order_residual_sampling[outcome] ?? {})
            .length
        ) {
          context.addIssue({
            code: "custom",
            path: ["higher_order_residual_sampling", outcome],
            message: "run_n5_residual_summary_step_missing",
          });
        }
      }
    }
  });

type RunN5InteractionEvidence = z.infer<typeof runN5InteractionEvidenceSchema>;

type RunN5ParentInteractionScope = {
  atom_ids: string[];
  selected_outcomes: string[];
  executed_steps?: number[];
  replication_seeds?: number[];
};

function validateRunN5InteractionScope(
  evidence: RunN5InteractionEvidence | null | undefined,
  parent: RunN5ParentInteractionScope,
  context: z.RefinementCtx,
): void {
  if (
    evidence == null ||
    evidence.schema_version !== "policyos.runtime.joint_simulation_horizon.v4"
  ) {
    return;
  }
  const addIssue = (message: string, path: (string | number)[] = []) => {
    context.addIssue({
      code: "custom",
      path: ["n5_interaction_evidence", ...path],
      message: `run_n5_interaction_scope_${message}`,
    });
  };
  const atoms = parent.atom_ids;
  const outcomes = parent.selected_outcomes;
  const steps = parent.executed_steps;
  const seeds = parent.replication_seeds;
  if (
    atoms.length === 0 ||
    outcomes.length === 0 ||
    steps == null ||
    steps.length === 0 ||
    seeds == null ||
    seeds.length === 0 ||
    new Set(atoms).size !== atoms.length ||
    new Set(outcomes).size !== outcomes.length ||
    new Set(steps).size !== steps.length ||
    new Set(seeds).size !== seeds.length ||
    [...atoms, ...outcomes].some((value) => value.length === 0)
  ) {
    addIssue("parent_context_missing_or_invalid");
    return;
  }

  const pairKey = (ids: string[]): string | null => {
    if (ids.length !== 2 || ids[0] === ids[1]) return null;
    return JSON.stringify([...ids].sort(compareUnicodeCodePoints));
  };
  const expectedPairs = new Set<string>();
  for (let left = 0; left < atoms.length; left += 1) {
    for (let right = left + 1; right < atoms.length; right += 1) {
      const key = pairKey([atoms[left] ?? "", atoms[right] ?? ""]);
      if (key != null) expectedPairs.add(key);
    }
  }
  const expectedPairOutcomes = new Set<string>();
  for (const pair of expectedPairs) {
    for (const outcome of outcomes) {
      expectedPairOutcomes.add(JSON.stringify([pair, outcome]));
    }
  }
  const expectedStepKeys = new Set(steps.map(String));
  const sameSet = (left: Iterable<string>, right: Set<string>) => {
    const values = [...left];
    return (
      values.length === right.size && values.every((value) => right.has(value))
    );
  };
  const isSubset = (left: Iterable<string>, right: Set<string>) =>
    [...left].every((value) => right.has(value));
  const samplingEstablished =
    evidence.interaction_sampling_status !== "not_established";
  const actualPairOutcomes = new Set<string>();
  for (const [termIndex, term] of evidence.interaction_terms.entries()) {
    const pair = pairKey(term.atom_ids);
    const identity = pair == null ? null : JSON.stringify([pair, term.outcome]);
    if (
      pair == null ||
      !expectedPairs.has(pair) ||
      !outcomes.includes(term.outcome) ||
      identity == null ||
      actualPairOutcomes.has(identity)
    ) {
      addIssue("foreign_or_duplicate_pair", ["interaction_terms", termIndex]);
      continue;
    }
    actualPairOutcomes.add(identity);
    const meanSteps = Object.keys(term.by_step);
    const summarySteps = Object.keys(term.replication_sampling_by_step);
    if (!sameSet(meanSteps, expectedStepKeys)) {
      addIssue("pair_step_basis_incomplete", ["interaction_terms", termIndex]);
    }
    if (
      !isSubset(summarySteps, expectedStepKeys) ||
      !isSubset(summarySteps, new Set(meanSteps))
    ) {
      addIssue("foreign_pair_step", ["interaction_terms", termIndex]);
    }
    for (const [step, summary] of Object.entries(
      term.replication_sampling_by_step,
    )) {
      if (
        summary.seeds.length !== seeds.length ||
        summary.seeds.some((seed, index) => seed !== seeds[index])
      ) {
        addIssue("seed_basis_mismatch", [
          "interaction_terms",
          termIndex,
          "replication_sampling_by_step",
          step,
        ]);
      }
    }
    if (
      (samplingEstablished && !sameSet(summarySteps, expectedStepKeys)) ||
      (summarySteps.length > 0 && !sameSet(summarySteps, expectedStepKeys))
    ) {
      addIssue("pair_step_basis_incomplete", ["interaction_terms", termIndex]);
    }
  }
  if (!sameSet(actualPairOutcomes, expectedPairOutcomes)) {
    addIssue("pair_set_incomplete");
  }

  const expectedResidualOutcomes = new Set(atoms.length >= 3 ? outcomes : []);
  const residualOutcomes = Object.keys(evidence.higher_order_residuals);
  const residualSamplingOutcomes = Object.keys(
    evidence.higher_order_residual_sampling,
  );
  if (
    !isSubset(residualOutcomes, expectedResidualOutcomes) ||
    !isSubset(residualSamplingOutcomes, expectedResidualOutcomes) ||
    !isSubset(residualSamplingOutcomes, new Set(residualOutcomes))
  ) {
    addIssue("foreign_residual_outcome");
  }
  for (const outcome of residualOutcomes) {
    const meanSteps = Object.keys(
      evidence.higher_order_residuals[outcome] ?? {},
    );
    const summaries = evidence.higher_order_residual_sampling[outcome] ?? {};
    const summarySteps = Object.keys(summaries);
    if (!sameSet(meanSteps, expectedStepKeys)) {
      addIssue("residual_step_basis_incomplete", [
        "higher_order_residuals",
        outcome,
      ]);
    }
    if (
      !isSubset(summarySteps, expectedStepKeys) ||
      !isSubset(summarySteps, new Set(meanSteps))
    ) {
      addIssue("foreign_residual_step", [
        "higher_order_residual_sampling",
        outcome,
      ]);
    }
    for (const [step, summary] of Object.entries(summaries)) {
      if (
        summary.seeds.length !== seeds.length ||
        summary.seeds.some((seed, index) => seed !== seeds[index])
      ) {
        addIssue("residual_seed_basis_mismatch", [
          "higher_order_residual_sampling",
          outcome,
          step,
        ]);
      }
    }
    if (
      (samplingEstablished && !sameSet(summarySteps, expectedStepKeys)) ||
      (summarySteps.length > 0 && !sameSet(summarySteps, expectedStepKeys))
    ) {
      addIssue("residual_step_basis_incomplete", [
        "higher_order_residual_sampling",
        outcome,
      ]);
    }
  }
  if (!sameSet(new Set(residualOutcomes), expectedResidualOutcomes)) {
    addIssue("residual_basis_incomplete");
  }

  const expectedOrders =
    atoms.length === 3 ? [1, 2, 3] : atoms.length >= 2 ? [1, 2] : [1];
  const checked = evidence.checked_interaction_orders;
  const sortedUnique = [...new Set(checked)].sort(
    (left, right) => left - right,
  );
  if (
    sortedUnique.length !== checked.length ||
    checked.some((order, index) => order !== sortedUnique[index]) ||
    checked.some((order) => !expectedOrders.includes(order)) ||
    checked.length !== expectedOrders.length ||
    checked.some((order, index) => order !== expectedOrders[index])
  ) {
    addIssue("checked_orders_mismatch");
  }
}

const runCandidateSimulationN8ChildSourceBindingSchema = z
  .object({
    child_node_ref: z.string().min(1),
    child_design_problem_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    n4_source_ref: coreArtifactRefSchema,
    context_job_ref: coreArtifactRefSchema,
    n5_input_ref: coreArtifactRefSchema,
    n5_result_ref: coreArtifactRefSchema,
    profile_config_ref: z.string().min(1),
    profile_selection_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    source_intervention_id: z.string().min(1),
    source_atom_id: z.string().regex(/^atom_[a-f0-9]{16}$/),
    source_atom_content_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    source_problem_frame_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    parent_atom_id: z.string().regex(/^atom_[a-f0-9]{16}$/),
    parent_atom_content_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
  })
  .strict()
  .superRefine((binding, context) => {
    const expected: Array<[z.infer<typeof coreArtifactRefSchema>, string[]]> = [
      [
        binding.n4_source_ref,
        [
          "runtime.generation_source_handoff",
          "runtime.quality.n4_candidate_scenario_source",
        ],
      ],
      [
        binding.context_job_ref,
        ["runtime.quality.cycle_substrate_context_job"],
      ],
      [binding.n5_input_ref, ["runtime.quality.candidate_simulation_n5_input"]],
      [binding.n5_result_ref, ["polisyos.runtime.joint_simulation_result"]],
    ];
    for (const [ref, kinds] of expected) {
      if (
        !kinds.includes(ref.kind ?? "") ||
        ref.media_type !== "application/json"
      ) {
        context.addIssue({
          code: "custom",
          message: "run_n8_joint_child_source_ref_invalid",
        });
      }
    }
  });

const runCandidateSimulationN5ObservationSchema = z
  .object({
    node_ref: z.string().min(1),
    design_problem_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    design_problem_basis_ref: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    cycle_index: z.number().int().nonnegative().nullable().optional(),
    candidate_id: z.string().min(1).nullable().optional(),
    atom_ids: z.array(z.string()).default([]),
    selected_outcomes: z.array(z.string()).default([]),
    executed_steps: z.array(z.number().int()).default([]),
    replication_seeds: z.array(z.number().int()).default([]),
    status: z.enum([
      "joint_simulated",
      "simulation_pending_n5",
      "simulation_blocked",
    ]),
    simulation_ref: z.string().nullable().optional(),
    simulation_result_ref: coreArtifactRefSchema.nullable().optional(),
    n4_source_ref: coreArtifactRefSchema.nullable().optional(),
    context_job_ref: coreArtifactRefSchema.nullable().optional(),
    n5_input_ref: coreArtifactRefSchema.nullable().optional(),
    profile_config_ref: z.string().min(1).nullable().optional(),
    profile_selection_ref: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    lineage_status: z
      .enum(["resolved", "not_established"])
      .nullable()
      .optional(),
    lineage_limitation_code: z.string().min(1).nullable().optional(),
    currentness_status: z.literal("not_established").nullable().optional(),
    world_model_record_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    k_world_ref_before: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    k_world_ref_after: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    authority_blockers: z.array(z.string()).default([]),
    n5_interaction_evidence: runN5InteractionEvidenceSchema
      .nullable()
      .optional(),
    n8_numeric_interaction: z
      .enum(["none", "additive", "non_additive", "unsupported"])
      .nullable()
      .optional(),
    n8_numeric_interaction_basis: z
      .enum(["finite_checked_model_point_estimate_only", "not_established"])
      .nullable()
      .optional(),
    n8_interaction_sampling_status: z
      .enum(["estimated", "standard_error_not_estimated", "not_established"])
      .nullable()
      .optional(),
    n8_status: z
      .enum([
        "value_ready",
        "value_conditional",
        "value_blocked",
        "value_pending_n8",
      ])
      .nullable()
      .optional(),
    n8_authority_blockers: z.array(z.string()).default([]),
    n8_candidate_value_ref: z.string().nullable().optional(),
    n8_candidate_decision_grade: z.literal("low").nullable().optional(),
    n8_joint_request_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    n8_joint_world_model_record_ref: z.string().min(1).nullable().optional(),
    n8_joint_outcome_units: z.record(z.string(), z.string()).optional(),
    n8_joint_parent_atom_ids: z
      .array(z.string().regex(/^atom_[a-f0-9]{16}$/))
      .default([]),
    n8_joint_parent_atom_content_hashes: z
      .array(z.string().regex(/^sha256:[0-9a-f]{64}$/))
      .default([]),
    n8_parent_child_refs: z.array(z.string().min(1)).default([]),
    n8_parent_child_source_bindings: z
      .array(runCandidateSimulationN8ChildSourceBindingSchema)
      .default([]),
    n8_joint_scope_status: z
      .enum(["resolved", "not_established"])
      .nullable()
      .optional(),
    n8_joint_scope_limitation_code: z.string().min(1).nullable().optional(),
    n8_joint_value_limitation_code: z
      .literal("joint_interaction_rule_not_established")
      .nullable()
      .optional(),
    n8_candidate_joint_selection_status: z
      .enum(["resolved", "not_established"])
      .nullable()
      .optional(),
    n8_candidate_joint_selection_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    n8_candidate_parent_atom_ids: z
      .array(z.string().regex(/^atom_[a-f0-9]{16}$/))
      .default([]),
    n8_candidate_parent_atom_content_hashes: z
      .array(z.string().regex(/^sha256:[0-9a-f]{64}$/))
      .default([]),
    n8_candidate_parent_intervention_ids: z
      .array(z.string().min(1))
      .default([]),
    n8_candidate_parent_child_refs: z.array(z.string().min(1)).default([]),
    n8_candidate_joint_selection_limitation_code: z
      .literal("parent_joint_candidate_source_selection_not_established")
      .nullable()
      .optional(),
    n8_candidate_member_basis: z
      .enum(["hypothetical_all_unique_n4_source_members", "not_established"])
      .nullable()
      .optional(),
    n8_source_candidate_relationship: z
      .enum(["alternatives", "not_established"])
      .nullable()
      .optional(),
    n8_policy_composition_status: z
      .literal("not_established")
      .nullable()
      .optional(),
    n8_policy_composition_limitation_code: z
      .enum([
        "n4_source_candidates_are_alternatives_not_authored_compound_design",
        "legacy_selection_receipt_has_no_composition_basis",
        "parent_joint_candidate_source_selection_not_established",
      ])
      .nullable()
      .optional(),
    n8_child_to_parent_refinement_status: z
      .literal("not_established")
      .nullable()
      .optional(),
    n8_child_to_parent_refinement_limitation_code: z
      .enum([
        "child_to_parent_refinement_rule_not_established",
        "legacy_selection_receipt_has_no_refinement_basis",
        "parent_joint_candidate_source_selection_not_established",
      ])
      .nullable()
      .optional(),
  })
  .strict()
  .superRefine((observation, context) => {
    validateRunN5InteractionScope(
      observation.n5_interaction_evidence,
      observation,
      context,
    );
    const candidateSelectionStatus =
      observation.n8_candidate_joint_selection_status;
    const candidateSelectionHash =
      observation.n8_candidate_joint_selection_content_hash;
    const candidateAtomIds = observation.n8_candidate_parent_atom_ids ?? [];
    const candidateAtomHashes =
      observation.n8_candidate_parent_atom_content_hashes ?? [];
    const candidateInterventionIds =
      observation.n8_candidate_parent_intervention_ids ?? [];
    const candidateChildRefs = observation.n8_candidate_parent_child_refs ?? [];
    const candidateSelectionLimitation =
      observation.n8_candidate_joint_selection_limitation_code;
    const candidateMemberBasis = observation.n8_candidate_member_basis;
    const sourceCandidateRelationship =
      observation.n8_source_candidate_relationship;
    const compositionStatus = observation.n8_policy_composition_status;
    const compositionLimitation =
      observation.n8_policy_composition_limitation_code;
    const refinementStatus = observation.n8_child_to_parent_refinement_status;
    const refinementLimitation =
      observation.n8_child_to_parent_refinement_limitation_code;
    const candidateSelectionFieldsPresent =
      candidateSelectionHash != null ||
      candidateAtomIds.length > 0 ||
      candidateAtomHashes.length > 0 ||
      candidateInterventionIds.length > 0 ||
      candidateChildRefs.length > 0 ||
      candidateSelectionLimitation != null ||
      candidateMemberBasis != null ||
      sourceCandidateRelationship != null ||
      compositionStatus != null ||
      compositionLimitation != null ||
      refinementStatus != null ||
      refinementLimitation != null;
    if (candidateSelectionStatus == null) {
      if (candidateSelectionFieldsPresent) {
        context.addIssue({
          code: "custom",
          path: ["n8_candidate_joint_selection_status"],
          message: "run_n8_candidate_joint_selection_status_missing",
        });
      }
    } else if (candidateSelectionStatus === "not_established") {
      if (
        candidateSelectionLimitation == null ||
        candidateSelectionHash != null ||
        candidateAtomIds.length > 0 ||
        candidateAtomHashes.length > 0 ||
        candidateInterventionIds.length > 0 ||
        candidateChildRefs.length > 0 ||
        candidateMemberBasis !== "not_established" ||
        sourceCandidateRelationship !== "not_established" ||
        compositionStatus !== "not_established" ||
        compositionLimitation !==
          "parent_joint_candidate_source_selection_not_established" ||
        refinementStatus !== "not_established" ||
        refinementLimitation !==
          "parent_joint_candidate_source_selection_not_established"
      ) {
        context.addIssue({
          code: "custom",
          path: ["n8_candidate_joint_selection_limitation_code"],
          message: "run_n8_candidate_joint_selection_limitation_missing",
        });
      }
    } else {
      const unique = (values: string[]) =>
        new Set(values).size === values.length;
      const validHypotheticalBasis =
        candidateMemberBasis === "hypothetical_all_unique_n4_source_members" &&
        sourceCandidateRelationship === "alternatives" &&
        compositionLimitation ===
          "n4_source_candidates_are_alternatives_not_authored_compound_design" &&
        refinementLimitation ===
          "child_to_parent_refinement_rule_not_established";
      const validLegacyBasis =
        candidateMemberBasis === "not_established" &&
        sourceCandidateRelationship === "not_established" &&
        compositionLimitation ===
          "legacy_selection_receipt_has_no_composition_basis" &&
        refinementLimitation ===
          "legacy_selection_receipt_has_no_refinement_basis";
      if (
        candidateSelectionHash == null ||
        candidateSelectionLimitation != null ||
        candidateAtomIds.length === 0 ||
        candidateAtomIds.length !== observation.atom_ids.length ||
        !unique(candidateAtomIds) ||
        candidateAtomHashes.length !== observation.atom_ids.length ||
        !unique(candidateAtomHashes) ||
        candidateInterventionIds.length !== observation.atom_ids.length ||
        candidateInterventionIds.some(
          (value, index) => value !== observation.atom_ids[index],
        ) ||
        candidateChildRefs.length !== observation.atom_ids.length ||
        !unique(candidateChildRefs) ||
        observation.n8_joint_scope_status !== "not_established" ||
        !["value_pending_n8", "value_conditional"].includes(
          observation.n8_status ?? "",
        ) ||
        compositionStatus !== "not_established" ||
        refinementStatus !== "not_established" ||
        !(validHypotheticalBasis || validLegacyBasis)
      ) {
        context.addIssue({
          code: "custom",
          path: ["n8_candidate_parent_atom_content_hashes"],
          message: "run_n8_candidate_joint_selection_binding_incomplete",
        });
      }
    }
    const fields = [
      observation.n8_numeric_interaction,
      observation.n8_numeric_interaction_basis,
      observation.n8_interaction_sampling_status,
    ];
    if (fields.some((value) => value != null)) {
      if (
        observation.n5_interaction_evidence == null ||
        fields.some((value) => value == null) ||
        observation.n8_numeric_interaction !==
          observation.n5_interaction_evidence.numeric_interaction ||
        observation.n8_numeric_interaction_basis !==
          observation.n5_interaction_evidence.numeric_interaction_basis ||
        observation.n8_interaction_sampling_status !==
          observation.n5_interaction_evidence.interaction_sampling_status
      ) {
        context.addIssue({
          code: "custom",
          path: ["n5_interaction_evidence"],
          message: "run_n5_n8_interaction_qualification_missing_or_mismatched",
        });
      }
    }
    if (observation.n8_status === "value_conditional") {
      if (
        observation.n5_interaction_evidence == null ||
        observation.n8_numeric_interaction == null ||
        observation.n8_numeric_interaction_basis == null ||
        observation.n8_interaction_sampling_status == null
      ) {
        context.addIssue({
          code: "custom",
          path: ["n5_interaction_evidence"],
          message: "run_n5_n8_conditional_interaction_missing",
        });
      }
      if (
        observation.n8_numeric_interaction === "unsupported" &&
        !(observation.n8_authority_blockers ?? []).includes(
          "interaction_numeric_classification_unsupported",
        )
      ) {
        context.addIssue({
          code: "custom",
          path: ["n8_authority_blockers"],
          message: "run_n5_n8_unsupported_interaction_not_limited",
        });
      }
      if (
        observation.n8_interaction_sampling_status != null &&
        observation.n8_interaction_sampling_status !== "estimated" &&
        ![
          "interaction_sampling_not_established",
          "standard_error_not_estimated",
          "legacy_interaction_not_established",
        ].some((code) =>
          (observation.n8_authority_blockers ?? []).includes(code),
        )
      ) {
        context.addIssue({
          code: "custom",
          path: ["n8_authority_blockers"],
          message: "run_n5_n8_unestimated_interaction_not_limited",
        });
      }
    }
    const jointScope = observation.n8_joint_scope_status;
    const candidateValuePresent =
      observation.n8_candidate_value_ref != null ||
      observation.n8_candidate_decision_grade != null;
    const requiredCandidateBlockers = [
      "n5_execution_request_provenance_not_established",
      "n4_source_candidates_are_alternatives_not_authored_compound_design",
      "child_to_parent_refinement_rule_not_established",
    ];
    if (
      candidateValuePresent &&
      (observation.n8_status !== "value_conditional" ||
        observation.n8_candidate_decision_grade !== "low" ||
        observation.simulation_result_ref == null ||
        observation.n8_candidate_value_ref !==
          observation.simulation_result_ref.artifact_id ||
        jointScope !== "not_established" ||
        requiredCandidateBlockers.some(
          (blocker) => !observation.n8_authority_blockers.includes(blocker),
        ))
    ) {
      context.addIssue({
        code: "custom",
        path: ["n8_candidate_value_ref"],
        message: "run_n8_joint_candidate_conditional_binding_invalid",
      });
    }
    if (
      observation.n8_status === "value_conditional" &&
      jointScope != null &&
      (observation.n8_candidate_value_ref == null ||
        observation.n8_candidate_decision_grade == null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["n8_candidate_value_ref"],
        message: "run_n8_joint_candidate_conditional_value_missing",
      });
    }
    if (jointScope == null) {
      const jointFieldsPresent =
        observation.n8_joint_request_content_hash != null ||
        observation.n8_joint_world_model_record_ref != null ||
        Object.keys(observation.n8_joint_outcome_units ?? {}).length > 0 ||
        (observation.n8_joint_parent_atom_ids ?? []).length > 0 ||
        (observation.n8_joint_parent_atom_content_hashes ?? []).length > 0 ||
        (observation.n8_parent_child_refs ?? []).length > 0 ||
        (observation.n8_parent_child_source_bindings ?? []).length > 0 ||
        observation.n8_joint_scope_limitation_code != null ||
        observation.n8_joint_value_limitation_code != null;
      if (jointFieldsPresent) {
        context.addIssue({
          code: "custom",
          path: ["n8_joint_scope_status"],
          message: "run_n8_joint_scope_status_missing",
        });
      }
      return;
    }

    const scopeBlockers = observation.n8_authority_blockers ?? [];
    const parentAtomIds = observation.n8_joint_parent_atom_ids ?? [];
    const parentAtomHashes =
      observation.n8_joint_parent_atom_content_hashes ?? [];
    const childRefs = observation.n8_parent_child_refs ?? [];
    const childBindings = observation.n8_parent_child_source_bindings ?? [];
    const outcomeUnits = observation.n8_joint_outcome_units ?? {};
    if (
      observation.n8_status !== "value_pending_n8" &&
      observation.n8_status !== "value_conditional"
    ) {
      context.addIssue({
        code: "custom",
        path: ["n8_status"],
        message: "run_n8_joint_scope_must_remain_candidate_only",
      });
    }
    if (jointScope === "not_established") {
      const limitation = observation.n8_joint_scope_limitation_code;
      if (
        limitation == null ||
        observation.n8_joint_value_limitation_code != null ||
        !scopeBlockers.includes(limitation) ||
        Object.keys(outcomeUnits).length > 0 ||
        parentAtomIds.length > 0 ||
        parentAtomHashes.length > 0 ||
        childRefs.length > 0 ||
        childBindings.length > 0
      ) {
        context.addIssue({
          code: "custom",
          path: ["n8_joint_scope_limitation_code"],
          message: "run_n8_joint_scope_limitation_missing",
        });
      }
      return;
    }

    const evidence = observation.n5_interaction_evidence;
    const n8Fields = [
      observation.n8_numeric_interaction,
      observation.n8_numeric_interaction_basis,
      observation.n8_interaction_sampling_status,
    ];
    const expectedUnitOutcomes = new Set(observation.selected_outcomes);
    const parentAtomIdSet = new Set(parentAtomIds);
    const parentAtomHashSet = new Set(parentAtomHashes);
    const sourceAtomIds = new Set(
      childBindings.map((row) => row.source_atom_id),
    );
    const sourceAtomHashes = new Set(
      childBindings.map((row) => row.source_atom_content_hash),
    );
    const bindingParentIds = new Set(
      childBindings.map((row) => row.parent_atom_id),
    );
    const bindingParentHashes = new Set(
      childBindings.map((row) => row.parent_atom_content_hash),
    );
    const sourceInterventionIds = new Set(
      childBindings.map((row) => row.source_intervention_id),
    );
    const unique = (values: string[]) => new Set(values).size === values.length;
    const sameSet = (left: Set<string>, right: string[]) =>
      left.size === right.length && right.every((value) => left.has(value));
    const selectedAtoms = observation.atom_ids;
    const completeParentBasis =
      observation.n8_joint_scope_limitation_code == null &&
      observation.n8_joint_value_limitation_code ===
        "joint_interaction_rule_not_established" &&
      scopeBlockers.includes("joint_interaction_rule_not_established") &&
      observation.n8_joint_request_content_hash != null &&
      observation.n8_joint_world_model_record_ref != null &&
      observation.world_model_record_content_hash != null &&
      expectedUnitOutcomes.size > 0 &&
      Object.keys(outcomeUnits).length === expectedUnitOutcomes.size &&
      Object.keys(outcomeUnits).every((outcome) =>
        expectedUnitOutcomes.has(outcome),
      ) &&
      Object.values(outcomeUnits).every((unit) => unit.trim().length > 0) &&
      selectedAtoms.length > 0 &&
      parentAtomIds.length === selectedAtoms.length &&
      parentAtomHashes.length === selectedAtoms.length &&
      unique(parentAtomIds) &&
      unique(parentAtomHashes) &&
      childRefs.length === selectedAtoms.length &&
      unique(childRefs) &&
      childBindings.length === selectedAtoms.length &&
      childBindings.every(
        (binding, index) => binding.child_node_ref === childRefs[index],
      ) &&
      sameSet(bindingParentIds, parentAtomIds) &&
      sameSet(sourceAtomIds, parentAtomIds) &&
      sameSet(bindingParentHashes, parentAtomHashes) &&
      sameSet(sourceAtomHashes, parentAtomHashes) &&
      sameSet(sourceInterventionIds, selectedAtoms) &&
      childBindings.every(
        (binding) =>
          binding.source_problem_frame_ref === observation.design_problem_ref,
      ) &&
      evidence?.schema_version ===
        "policyos.runtime.joint_simulation_horizon.v4" &&
      evidence.interaction_sampling_status !== "not_established" &&
      observation.status === "joint_simulated" &&
      (observation.executed_steps ?? []).length > 0 &&
      (observation.replication_seeds ?? []).length > 0 &&
      n8Fields.every((value) => value != null) &&
      observation.n8_numeric_interaction === evidence.numeric_interaction &&
      observation.n8_numeric_interaction_basis ===
        evidence.numeric_interaction_basis &&
      observation.n8_interaction_sampling_status ===
        evidence.interaction_sampling_status;
    if (!completeParentBasis) {
      context.addIssue({
        code: "custom",
        path: ["n8_parent_child_source_bindings"],
        message: "run_n8_joint_scope_binding_incomplete",
      });
    }
  });

const runRecursiveCycleBranchFailureSchema = z
  .object({
    failed_branch_ref: z.string().min(1),
    origin_node_ref: z.string().min(1),
    stage: z.string().min(1),
    exception_type: z.string().min(1),
    error_code: z.string().min(1).nullable().optional(),
    error_message: z.string(),
  })
  .strict();

const runRecursiveCycleCheckpointSchema = z
  .object({
    schema_version: z.enum([
      "policyos.runtime.recursive_cycle_checkpoint.v1",
      "policyos.runtime.recursive_cycle_checkpoint.v2",
    ]),
    status: z.literal("partial").default("partial"),
    publication_authority: z.literal(false).default(false),
    budget_stop_node_ref: z.string().min(1).nullable().optional(),
    pending_frontier: z.array(z.string()).default([]),
    completed_design_refs: z.array(z.string()).default([]),
    root_n9_status: z.literal("not_run").default("not_run"),
    leaf_terminal_kinds: z.record(z.string(), z.string()).default({}),
    failed_branches: z.array(runRecursiveCycleBranchFailureSchema).default([]),
  })
  .strict();

const runGenericCycleSimulationCheckpointSchema =
  runRecursiveCycleCheckpointSchema.superRefine((checkpoint, context) => {
    const v1Shape =
      checkpoint.schema_version ===
        "policyos.runtime.recursive_cycle_checkpoint.v1" &&
      typeof checkpoint.budget_stop_node_ref === "string" &&
      checkpoint.failed_branches.length === 0;
    const v2Shape =
      checkpoint.schema_version ===
        "policyos.runtime.recursive_cycle_checkpoint.v2" &&
      checkpoint.budget_stop_node_ref == null &&
      checkpoint.failed_branches.length > 0;
    if (!v1Shape && !v2Shape) {
      context.addIssue({
        code: "custom",
        message: "generic_cycle_checkpoint_version_shape_invalid",
      });
    }
  });

const runCandidateSimulationCurrentOccurrenceSchema = z
  .object({
    candidate_id: z.string().min(1),
    cycle_index: z.number().int().nonnegative(),
    content_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    source_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable(),
    front: z.enum(["decision", "research", "quarantine", "portfolio"]),
    certified_by_n9: z.boolean(),
  })
  .strict();

const runCandidateSimulationContinuationFrontsSchema = z
  .object({
    decision_candidate_ids: z.array(z.string().min(1)),
    research_candidate_ids: z.array(z.string().min(1)),
    quarantine_candidate_ids: z.array(z.string().min(1)),
    portfolio_candidate_ids: z.array(z.string().min(1)),
  })
  .strict();

const runCandidateSimulationAcquisitionContinuationProjectionSchema = z
  .object({
    source_generation_run_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/),
    continued_generation_run_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/),
    source_cycle_index: z.number().int().nonnegative(),
    continued_cycle_index: z.number().int().nonnegative(),
    previous_n4_source_ref: coreArtifactRefSchema.nullable(),
    previous_n5_input_ref: coreArtifactRefSchema.nullable(),
    selected_n4_source_ref: coreArtifactRefSchema,
    selected_n5_input_ref: coreArtifactRefSchema,
    previous_profile_selection_ref: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable(),
    previous_profile_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable(),
    selected_profile_selection_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    selected_profile_content_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    selected_target_world_slot: z.string().min(1),
    previous_selected_target_baseline_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable(),
    selected_target_baseline_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable(),
    source_currentness_status: z.enum(["current", "stale", "not_established"]),
    source_currentness_reason: z.string().min(1),
    continuation_currentness_status: z.enum([
      "current",
      "stale",
      "not_established",
    ]),
    continuation_currentness_reason: z.string().min(1),
    n9_status: z.enum([
      "promotion_pending_n9",
      "certified_current_valid",
      "not_promoted",
    ]),
    n9_reason: z.string().min(1),
    n9_certified_candidate_ids: z.array(z.string().min(1)),
    current_candidate_occurrences: z.array(
      runCandidateSimulationCurrentOccurrenceSchema,
    ),
    current_fronts: runCandidateSimulationContinuationFrontsSchema,
    currentness_status: z.literal("not_established"),
    authority_purpose: z.literal("candidate_observation_only"),
    publication_authority: z.literal(false),
  })
  .strict()
  .superRefine((projection, context) => {
    const occurrences = new Set(
      projection.current_candidate_occurrences.map((row) => row.candidate_id),
    );
    const fronts = [
      ...projection.current_fronts.decision_candidate_ids,
      ...projection.current_fronts.research_candidate_ids,
      ...projection.current_fronts.quarantine_candidate_ids,
      ...projection.current_fronts.portfolio_candidate_ids,
    ];
    if (
      new Set(fronts).size !== fronts.length ||
      occurrences.size !== projection.current_candidate_occurrences.length ||
      fronts.length !== occurrences.size ||
      fronts.some((candidateId) => !occurrences.has(candidateId)) ||
      projection.n9_certified_candidate_ids.some(
        (candidateId) => !occurrences.has(candidateId),
      ) ||
      projection.continued_cycle_index !== projection.source_cycle_index + 1 ||
      projection.selected_n4_source_ref.kind !==
        "runtime.quality.n4_candidate_scenario_source" ||
      projection.selected_n5_input_ref.kind !==
        "runtime.quality.candidate_simulation_n5_input" ||
      (projection.previous_n4_source_ref === null) !==
        (projection.previous_n5_input_ref === null) ||
      (projection.previous_profile_selection_ref === null) !==
        (projection.previous_profile_content_hash === null) ||
      (projection.previous_n4_source_ref !== null &&
        projection.previous_n4_source_ref.kind !==
          "runtime.quality.n4_candidate_scenario_source") ||
      (projection.previous_n5_input_ref !== null &&
        projection.previous_n5_input_ref.kind !==
          "runtime.quality.candidate_simulation_n5_input") ||
      (projection.previous_selected_target_baseline_hash !== null &&
        projection.selected_target_baseline_hash !== null &&
        projection.previous_selected_target_baseline_hash ===
          projection.selected_target_baseline_hash) ||
      projection.current_candidate_occurrences.some(
        (row) =>
          row.certified_by_n9 !==
            projection.n9_certified_candidate_ids.includes(row.candidate_id) ||
          !{
            decision: projection.current_fronts.decision_candidate_ids,
            research: projection.current_fronts.research_candidate_ids,
            quarantine: projection.current_fronts.quarantine_candidate_ids,
            portfolio: projection.current_fronts.portfolio_candidate_ids,
          }[row.front].includes(row.candidate_id),
      ) ||
      (projection.n9_status !== "certified_current_valid" &&
        projection.n9_certified_candidate_ids.length > 0) ||
      (projection.continuation_currentness_status !== "current" &&
        projection.n9_status === "certified_current_valid")
    ) {
      context.addIssue({
        code: "custom",
        message: "run_candidate_simulation_continuation_projection_invalid",
      });
    }
  });

const runCandidateSimulationRetainedEvaluationSchema = z
  .object({
    candidate_id: z.string().min(1),
    candidate_content_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    design_problem_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    world_model_record_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    evaluation_job_id: z.string().min(1),
    evaluation_run_id: z.string().min(1),
    generation_run_id: z.string().min(1),
    cycle_index: z.number().int().nonnegative(),
    n4_source_ref: coreArtifactRefSchema,
    context_job_ref: coreArtifactRefSchema,
    n5_input_ref: coreArtifactRefSchema,
    n5_execution_ref: coreArtifactRefSchema,
    n5_result_ref: coreArtifactRefSchema,
    basis_ref: coreArtifactRefSchema,
  })
  .strict()
  .superRefine((evaluation, context) => {
    const expectedKinds = {
      n4_source_ref: "runtime.quality.n4_candidate_scenario_source",
      context_job_ref: "runtime.quality.cycle_substrate_context_job",
      n5_input_ref: "runtime.quality.candidate_simulation_n5_input",
      n5_execution_ref: "runtime.quality.candidate_simulation_execution",
      n5_result_ref: "polisyos.runtime.joint_simulation_result",
      basis_ref: "runtime_quality.acquisition_evaluation_basis",
    } as const;
    for (const [field, kind] of Object.entries(expectedKinds)) {
      const ref = evaluation[field as keyof typeof expectedKinds];
      if (
        ref.kind !== kind ||
        ref.media_type !== "application/json" ||
        ref.manifest_profile_sha256 == null
      ) {
        context.addIssue({
          code: "custom",
          path: [field],
          message: "candidate_acquisition_retained_evaluation_ref_invalid",
        });
      }
    }
  });

export const runCandidateSimulationAcquisitionHistoryEntryV3Schema = z
  .object({
    schema_version: z.literal(
      "policyos.runtime.run_candidate_simulation_acquisition_history.v3",
    ),
    route_receipt_ref: coreArtifactRefSchema,
    route_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    action_generation: z.number().int().positive(),
    terminal_outcome: z.literal("source_admitted_evaluation_retained"),
    admitted_source_ref: coreArtifactRefSchema,
    growth_receipt_ref: coreArtifactRefSchema,
    evaluation_decision_ref: coreArtifactRefSchema,
    current_continuation_ref: coreArtifactRefSchema,
    retained_evaluation: runCandidateSimulationRetainedEvaluationSchema,
    source_admission_status: z.literal("admitted").default("admitted"),
    evaluation_disposition: z
      .literal("retained_prior")
      .default("retained_prior"),
    reentry_receipt_ref: z.null().optional(),
    old_candidate_id: z.null().optional(),
    new_candidate_id: z.null().optional(),
    new_candidate_source_ref: z.null().optional(),
    origin_source_ref: z.null().optional(),
    expected_origin_source_ref: z.null().optional(),
    reentry_receipt_schema_version: z.null().optional(),
    continuation_join_status: z.null().optional(),
    origin_source_binding_status: z.null().optional(),
    continuation: z.null().optional(),
    currentness_status: z.literal("not_established"),
    authority_purpose: z.literal("candidate_observation_only"),
    publication_authority: z.literal(false),
  })
  .strict()
  .superRefine((entry, context) => {
    const expectedKinds = {
      route_receipt_ref: "runtime_quality.acquisition_route_loop_receipt",
      growth_receipt_ref: "runtime_quality.acquisition_world_growth_receipt",
      evaluation_decision_ref:
        "runtime_quality.acquisition_evaluation_decision",
      current_continuation_ref:
        "runtime_quality.acquisition_retained_continuation",
    } as const;
    for (const [field, kind] of Object.entries(expectedKinds)) {
      const ref = entry[field as keyof typeof expectedKinds];
      if (
        ref.kind !== kind ||
        ref.media_type !== "application/json" ||
        ref.manifest_profile_sha256 == null
      ) {
        context.addIssue({
          code: "custom",
          path: [field],
          message: "candidate_acquisition_retention_ref_invalid",
        });
      }
    }
    if (entry.admitted_source_ref.manifest_profile_sha256 == null) {
      context.addIssue({
        code: "custom",
        path: ["admitted_source_ref"],
        message: "candidate_acquisition_admitted_source_profile_missing",
      });
    }
  });

const runCandidateSimulationAcquisitionHistoryEntrySchema = z
  .object({
    route_receipt_ref: coreArtifactRefSchema,
    reentry_receipt_ref: coreArtifactRefSchema.nullable().optional(),
    route_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    action_generation: z.number().int().positive(),
    terminal_outcome: z.enum(["reentry_completed", "quarantined_no_growth"]),
    old_candidate_id: z.string().min(1).nullable().optional(),
    new_candidate_id: z.string().min(1).nullable().optional(),
    new_candidate_source_ref: coreArtifactRefSchema.nullable().optional(),
    origin_source_ref: coreArtifactRefSchema.nullable().optional(),
    expected_origin_source_ref: coreArtifactRefSchema.nullable().optional(),
    schema_version: z
      .literal(
        "policyos.runtime.run_candidate_simulation_acquisition_history.v2",
      )
      .nullable()
      .optional(),
    reentry_receipt_schema_version: z
      .enum([
        "policyos.runtime.acquisition_overlay_reentry.v1",
        "policyos.runtime.acquisition_overlay_reentry.v2",
        "policyos.runtime.acquisition_overlay_reentry.v3",
      ])
      .nullable()
      .optional(),
    continuation_join_status: z
      .enum([
        "not_applicable",
        "legacy_occurrence_unbound",
        "v3_occurrence_joined",
      ])
      .nullable()
      .optional(),
    origin_source_binding_status: z
      .enum(["not_supplied", "observed_only", "verified_same_candidate_root"])
      .nullable()
      .optional(),
    continuation: runCandidateSimulationAcquisitionContinuationProjectionSchema
      .nullable()
      .optional(),
    currentness_status: z.literal("not_established"),
    authority_purpose: z.literal("candidate_observation_only"),
    publication_authority: z.literal(false),
  })
  .strict()
  .superRefine((entry, context) => {
    const hasRef = (
      ref: z.infer<typeof coreArtifactRefSchema> | null | undefined,
      kind: string,
    ) =>
      ref != null && ref.kind === kind && ref.media_type === "application/json";
    if (
      !hasRef(
        entry.route_receipt_ref,
        "runtime_quality.acquisition_route_loop_receipt",
      )
    ) {
      context.addIssue({
        code: "custom",
        path: ["route_receipt_ref"],
        message: "candidate_acquisition_route_receipt_invalid",
      });
    }
    if (
      entry.terminal_outcome === "reentry_completed" &&
      (!hasRef(
        entry.reentry_receipt_ref,
        "runtime_quality.acquisition_overlay_reentry_receipt",
      ) ||
        entry.old_candidate_id == null ||
        entry.new_candidate_id == null ||
        !hasRef(
          entry.new_candidate_source_ref,
          "runtime.quality.n4_candidate_scenario_source",
        ) ||
        (entry.origin_source_ref != null &&
          !hasRef(
            entry.origin_source_ref,
            "runtime.quality.n4_candidate_scenario_source",
          )) ||
        (entry.expected_origin_source_ref != null &&
          !hasRef(
            entry.expected_origin_source_ref,
            "runtime.quality.n4_candidate_scenario_source",
          )))
    ) {
      context.addIssue({
        code: "custom",
        path: ["reentry_receipt_ref"],
        message: "candidate_acquisition_reentry_receipt_invalid",
      });
    }
    const sameCandidate =
      entry.old_candidate_id != null &&
      entry.old_candidate_id === entry.new_candidate_id;
    const metadataPresent = [
      entry.schema_version,
      entry.reentry_receipt_schema_version,
      entry.continuation_join_status,
      entry.origin_source_binding_status,
    ].some((value) => value != null);
    if (
      metadataPresent &&
      (entry.schema_version !==
        "policyos.runtime.run_candidate_simulation_acquisition_history.v2" ||
        entry.continuation_join_status == null ||
        entry.origin_source_binding_status == null)
    ) {
      context.addIssue({
        code: "custom",
        message: "candidate_acquisition_lineage_metadata_incomplete",
      });
    }
    if (!metadataPresent && entry.expected_origin_source_ref != null) {
      context.addIssue({
        code: "custom",
        message: "candidate_acquisition_expected_origin_without_metadata",
      });
    }
    if (
      entry.origin_source_ref != null &&
      !hasRef(
        entry.origin_source_ref,
        "runtime.quality.n4_candidate_scenario_source",
      )
    ) {
      context.addIssue({
        code: "custom",
        path: ["origin_source_ref"],
        message: "candidate_acquisition_origin_source_invalid",
      });
    }
    if (
      entry.expected_origin_source_ref != null &&
      !hasRef(
        entry.expected_origin_source_ref,
        "runtime.quality.n4_candidate_scenario_source",
      )
    ) {
      context.addIssue({
        code: "custom",
        path: ["expected_origin_source_ref"],
        message: "candidate_acquisition_expected_origin_source_invalid",
      });
    }
    if (!sameCandidate && entry.expected_origin_source_ref != null) {
      context.addIssue({
        code: "custom",
        message: "candidate_acquisition_expected_origin_without_same_candidate",
      });
    }
    if (
      entry.terminal_outcome === "quarantined_no_growth" &&
      (entry.reentry_receipt_ref != null ||
        entry.old_candidate_id != null ||
        entry.new_candidate_id != null ||
        entry.new_candidate_source_ref != null ||
        entry.expected_origin_source_ref != null ||
        entry.continuation != null)
    ) {
      context.addIssue({
        code: "custom",
        message: "candidate_acquisition_quarantine_has_continuation",
      });
    }
    if (entry.terminal_outcome === "quarantined_no_growth") {
      const expectedOriginStatus =
        entry.origin_source_ref != null ? "observed_only" : "not_supplied";
      if (
        (metadataPresent &&
          (entry.reentry_receipt_schema_version != null ||
            entry.continuation_join_status !== "not_applicable" ||
            entry.origin_source_binding_status !== expectedOriginStatus)) ||
        (!metadataPresent &&
          (entry.continuation_join_status != null ||
            entry.origin_source_binding_status != null))
      ) {
        context.addIssue({
          code: "custom",
          message: "candidate_acquisition_quarantine_lineage_status_invalid",
        });
      }
    } else if (metadataPresent) {
      const expectedJoinStatus =
        entry.reentry_receipt_schema_version ===
        "policyos.runtime.acquisition_overlay_reentry.v3"
          ? "v3_occurrence_joined"
          : "legacy_occurrence_unbound";
      const expectedOriginStatus = sameCandidate
        ? "verified_same_candidate_root"
        : entry.origin_source_ref != null
          ? "observed_only"
          : "not_supplied";
      if (
        entry.reentry_receipt_schema_version == null ||
        entry.continuation_join_status !== expectedJoinStatus ||
        entry.origin_source_binding_status !== expectedOriginStatus ||
        (entry.reentry_receipt_schema_version ===
          "policyos.runtime.acquisition_overlay_reentry.v3") !==
          (entry.continuation != null)
      ) {
        context.addIssue({
          code: "custom",
          message: "candidate_acquisition_receipt_join_status_invalid",
        });
      }
    }
    if (
      entry.terminal_outcome === "reentry_completed" &&
      metadataPresent &&
      sameCandidate &&
      !sameCoreArtifactRefView(
        entry.origin_source_ref,
        entry.expected_origin_source_ref,
      )
    ) {
      context.addIssue({
        code: "custom",
        message: "candidate_acquisition_same_candidate_origin_binding_invalid",
      });
    }
    const projection = entry.continuation;
    if (
      projection != null &&
      !sameCoreArtifactRefView(
        entry.new_candidate_source_ref,
        projection.selected_n4_source_ref,
      )
    ) {
      context.addIssue({
        code: "custom",
        message: "candidate_acquisition_continuation_source_binding_invalid",
      });
    }
    if (
      projection != null &&
      (entry.new_candidate_id == null ||
        !projection.current_candidate_occurrences.some(
          (row) =>
            row.candidate_id === entry.new_candidate_id &&
            row.cycle_index === projection.continued_cycle_index,
        ))
    ) {
      context.addIssue({
        code: "custom",
        message: "candidate_acquisition_continuation_candidate_missing",
      });
    }
    if (
      projection != null &&
      entry.old_candidate_id === entry.new_candidate_id
    ) {
      if (
        entry.old_candidate_id == null ||
        projection.previous_n4_source_ref == null ||
        projection.previous_n5_input_ref == null ||
        projection.previous_profile_selection_ref == null ||
        projection.previous_profile_content_hash == null ||
        projection.previous_profile_selection_ref !==
          projection.selected_profile_selection_ref ||
        projection.previous_selected_target_baseline_hash == null ||
        projection.selected_target_baseline_hash == null ||
        projection.previous_selected_target_baseline_hash ===
          projection.selected_target_baseline_hash ||
        sameCoreArtifactRefView(
          projection.previous_n4_source_ref,
          projection.selected_n4_source_ref,
        ) ||
        sameCoreArtifactRefView(
          projection.previous_n5_input_ref,
          projection.selected_n5_input_ref,
        )
      ) {
        context.addIssue({
          code: "custom",
          message:
            "candidate_acquisition_same_candidate_continuation_binding_invalid",
        });
      }
    }
  });

const runCandidateSimulationChildProfileBindingSchema = z
  .object({
    cell_id: z.string().min(1),
    context_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    context_job_ref: coreArtifactRefSchema,
    currentness_status: z.literal("not_established"),
    design_problem_ref: z.string().min(1),
    historical_binding_status: z.enum(["resolved", "not_established"]),
    job_id: z.string().min(1),
    limitation_code: z.string().min(1).nullable().optional(),
    model_declaration_ref: coreArtifactRefSchema.nullable().optional(),
    ncm_ref: coreArtifactRefSchema.nullable().optional(),
    node_ref: z.string().min(1),
    profile_config_ref: z.string().min(1),
    profile_id: z.string().min(1),
    profile_selection_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    root_n4_source_ref: coreArtifactRefSchema,
    run_id: z.string().min(1),
    tenant_id: z.string().min(1),
  })
  .strict();

const runCandidateSimulationProjectionSchema = z
  .object({
    schema_version: z
      .literal("policyos.runtime.run_candidate_simulation_projection.v1")
      .default("policyos.runtime.run_candidate_simulation_projection.v1"),
    run_id: z.string().min(1),
    artifact_status: z.enum(["resolved", "not_established"]),
    authority_purpose: z
      .literal("candidate_observation_only")
      .default("candidate_observation_only"),
    publication_authority: z.literal(false).default(false),
    source_ref: coreArtifactRefSchema.nullable().optional(),
    source_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    limitation_code: z
      .enum([
        "compiled_cycle_artifact_ambiguous",
        "compiled_cycle_artifact_ref_invalid",
        "compiled_cycle_artifact_integrity_not_established",
        "compiled_cycle_artifact_content_invalid",
        "n5_observation_not_emitted",
        "n5_result_reference_not_established",
        "n5_interaction_scope_not_established",
      ])
      .nullable()
      .optional(),
    n4_child_profile_bindings: z
      .array(runCandidateSimulationChildProfileBindingSchema)
      .default([]),
    n4_child_profile_limitation_code: z.string().nullable().optional(),
    n4_child_profile_status: z
      .enum(["not_attempted", "resolved", "not_established"])
      .nullable()
      .optional(),
    n4_recursive_source_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    n4_recursive_source_context_job_ref: coreArtifactRefSchema
      .nullable()
      .optional(),
    n4_recursive_source_currentness_status: z
      .literal("not_established")
      .default("not_established"),
    n4_recursive_source_limitation_code: z.string().nullable().optional(),
    n4_recursive_source_profile_config_ref: z.string().nullable().optional(),
    n4_recursive_source_profile_selection_ref: z.string().nullable().optional(),
    n4_recursive_source_ref: coreArtifactRefSchema.nullable().optional(),
    n4_recursive_source_result_status: z
      .enum(["generated", "generation_unavailable", "preflight_rejected"])
      .nullable()
      .optional(),
    n4_recursive_source_status: z
      .enum(["resolved", "not_established"])
      .nullable()
      .optional(),
    n5_observations: z
      .array(runCandidateSimulationN5ObservationSchema)
      .default([]),
    recursive_cycle_checkpoint: runGenericCycleSimulationCheckpointSchema
      .nullable()
      .optional(),
    acquisition_history: z
      .array(
        z.union([
          runCandidateSimulationAcquisitionHistoryEntryV3Schema,
          runCandidateSimulationAcquisitionHistoryEntrySchema,
        ]),
      )
      .default([]),
    acquisition_history_limitation_code: z
      .enum([
        "acquisition_n4_source_not_established",
        "acquisition_action_history_not_observed",
        "acquisition_action_history_incomplete",
        "acquisition_action_history_integrity_not_established",
        "acquisition_reentry_source_not_established",
      ])
      .nullable()
      .optional(),
  })
  .strict();

const runGenericCycleSimulationArtifactRefSchema = coreArtifactRefSchema;

const runGenericCycleSimulationN5ResultBodySchema = z
  .object({
    schema_version: z.literal(
      "policyos.runtime.run_generic_cycle_simulation_n5_result_body.v1",
    ),
    artifact_ref: runGenericCycleSimulationArtifactRefSchema,
    artifact_schema_name: z.literal(
      "policyos.runtime.n5.joint_simulation_result",
    ),
    artifact_schema_version: z.enum(["1.0.0", "2.0.0", "3.0.0", "4.0.0"]),
    result_schema_version: z.enum([
      "policyos.runtime.joint_simulation_horizon.v1",
      "policyos.runtime.joint_simulation_horizon.v2",
      "policyos.runtime.joint_simulation_horizon.v3",
      "policyos.runtime.joint_simulation_horizon.v4",
    ]),
    selected_manifest_profile_sha256: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    world_model_record_ref: z.string().min(1),
    world_model_record_content_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    atom_ids: z.array(z.string().min(1)).min(1),
    selected_outcomes: z.array(z.string().min(1)).min(1),
    horizon: z
      .object({
        start: z.number().int().nonnegative(),
        end: z.number().int().nonnegative(),
        step: z.number().int().positive(),
        valid_time_role: z.string().min(1),
        transaction_time_role: z.string().min(1),
        scenario_branch_policy: z.string().min(1),
      })
      .strict(),
    trajectories: z
      .array(
        z
          .object({
            run_level: z.enum(["individual", "pairwise", "joint"]),
            atom_ids: z.array(z.string().min(1)).min(1),
            points: z
              .array(
                z
                  .object({
                    step: z.number().int().nonnegative(),
                    outcomes: z.record(z.string().min(1), z.number()),
                    effects: z.record(z.string().min(1), z.number()),
                  })
                  .strict(),
              )
              .min(1),
          })
          .strict(),
      )
      .min(1),
    uncertainty_kind: z.literal("K_sim"),
    authority_purpose: z.literal("cycle_input_candidate_only"),
    candidate_status: z.literal("candidate_unverified"),
    currentness_status: z.literal("not_established"),
    publication_authority: z.literal(false),
  })
  .strict()
  .superRefine((body, context) => {
    const resultSchemaByArtifactVersion = {
      "1.0.0": "policyos.runtime.joint_simulation_horizon.v1",
      "2.0.0": "policyos.runtime.joint_simulation_horizon.v2",
      "3.0.0": "policyos.runtime.joint_simulation_horizon.v3",
      "4.0.0": "policyos.runtime.joint_simulation_horizon.v4",
    } as const;
    if (
      body.artifact_ref.kind !== "polisyos.runtime.joint_simulation_result" ||
      body.artifact_ref.media_type !== "application/json" ||
      body.artifact_ref.manifest_profile_sha256 !==
        body.selected_manifest_profile_sha256 ||
      resultSchemaByArtifactVersion[body.artifact_schema_version] !==
        body.result_schema_version ||
      new Set(body.atom_ids).size !== body.atom_ids.length ||
      new Set(body.selected_outcomes).size !== body.selected_outcomes.length
    ) {
      context.addIssue({
        code: "custom",
        message: "generic_n5_result_body_manifest_binding_invalid",
      });
    }
    if (
      body.horizon.end < body.horizon.start ||
      (body.horizon.end - body.horizon.start) % body.horizon.step !== 0
    ) {
      context.addIssue({
        code: "custom",
        path: ["horizon"],
        message: "generic_n5_result_body_horizon_grid_invalid",
      });
    }
    const seenScopes = new Set<string>();
    for (const trajectory of body.trajectories) {
      const atomScope = new Set(trajectory.atom_ids);
      const scopeKey =
        trajectory.run_level + ":" + [...atomScope].sort().join("|");
      if (
        atomScope.size !== trajectory.atom_ids.length ||
        [...atomScope].some((atomId) => !body.atom_ids.includes(atomId)) ||
        seenScopes.has(scopeKey) ||
        (trajectory.run_level === "individual" && atomScope.size !== 1) ||
        (trajectory.run_level === "pairwise" && atomScope.size !== 2) ||
        (trajectory.run_level === "joint" &&
          JSON.stringify(trajectory.atom_ids) !== JSON.stringify(body.atom_ids))
      ) {
        context.addIssue({
          code: "custom",
          path: ["trajectories"],
          message: "generic_n5_result_body_scope_invalid",
        });
      }
      seenScopes.add(scopeKey);
      const pointSteps = trajectory.points.map((point) => point.step);
      if (
        new Set(pointSteps).size !== pointSteps.length ||
        pointSteps.some(
          (step, index) => index > 0 && pointSteps[index - 1]! >= step,
        )
      ) {
        context.addIssue({
          code: "custom",
          path: ["trajectories"],
          message: "generic_n5_result_body_step_order_invalid",
        });
      }
      for (const point of trajectory.points) {
        if (
          point.step < body.horizon.start ||
          point.step > body.horizon.end ||
          (point.step - body.horizon.start) % body.horizon.step !== 0 ||
          body.selected_outcomes.some(
            (outcome) =>
              !Object.hasOwn(point.outcomes, outcome) ||
              !Object.hasOwn(point.effects, outcome),
          )
        ) {
          context.addIssue({
            code: "custom",
            path: ["trajectories"],
            message: "generic_n5_result_body_selected_basis_incomplete",
          });
        }
      }
    }
  });

function compareUnicodeCodePoints(left: string, right: string): number {
  const leftPoints = Array.from(
    left,
    (character) => character.codePointAt(0) ?? 0,
  );
  const rightPoints = Array.from(
    right,
    (character) => character.codePointAt(0) ?? 0,
  );
  const sharedLength = Math.min(leftPoints.length, rightPoints.length);
  for (let index = 0; index < sharedLength; index += 1) {
    const leftPoint = leftPoints[index]!;
    const rightPoint = rightPoints[index]!;
    if (leftPoint !== rightPoint) {
      return leftPoint - rightPoint;
    }
  }
  return leftPoints.length - rightPoints.length;
}

const runGenericCycleSimulationChildProfileBindingSchema = z
  .object({
    context_job_ref: runGenericCycleSimulationArtifactRefSchema,
    currentness_status: z.literal("not_established").default("not_established"),
    design_problem_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    historical_binding_status: z.enum(["resolved", "not_established"]),
    limitation_code: z.string().min(1).nullable().optional(),
    node_ref: z.string().min(1),
    profile_id: z.string().min(1),
    profile_ref: runGenericCycleSimulationArtifactRefSchema,
    profile_selection_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    semantic_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    source_atom_refs: z.array(z.string()).min(1),
    source_ref: runGenericCycleSimulationArtifactRefSchema,
    source_result_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
  })
  .strict()
  .superRefine((binding, context) => {
    const expectedNodeRef =
      "design-problem://" + binding.design_problem_ref.slice("sha256:".length);
    if (binding.node_ref !== expectedNodeRef) {
      context.addIssue({
        code: "custom",
        path: ["node_ref"],
        message: "generic_cycle_child_design_problem_node_mismatch",
      });
    }

    const requiredRefs = [
      ["source_ref", binding.source_ref, "runtime.generation_source_handoff"],
      [
        "context_job_ref",
        binding.context_job_ref,
        "runtime.quality.cycle_substrate_context_job",
      ],
      [
        "profile_ref",
        binding.profile_ref,
        "runtime.quality.generic_cycle_simulation_profile",
      ],
    ] as const;
    for (const [field, ref, kind] of requiredRefs) {
      if (ref.kind !== kind || ref.media_type !== "application/json") {
        context.addIssue({
          code: "custom",
          path: [field],
          message: "generic_cycle_child_profile_ref_kind_invalid",
        });
      }
    }

    const sourceAtoms = binding.source_atom_refs;
    const atomsAreSorted = sourceAtoms.every(
      (atom, index) =>
        index === 0 ||
        compareUnicodeCodePoints(sourceAtoms[index - 1] ?? "", atom) <= 0,
    );
    if (sourceAtoms.length !== new Set(sourceAtoms).size || !atomsAreSorted) {
      context.addIssue({
        code: "custom",
        path: ["source_atom_refs"],
        message: "generic_cycle_child_source_atoms_not_canonical",
      });
    }

    if (
      (binding.historical_binding_status === "resolved" &&
        binding.limitation_code != null) ||
      (binding.historical_binding_status === "not_established" &&
        binding.limitation_code == null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["limitation_code"],
        message: "generic_cycle_child_binding_status_limitation_mismatch",
      });
    }
  });

const runGenericCycleSimulationN5ObservationSchema = z
  .object({
    atom_ids: z.array(z.string()).default([]),
    authority_blockers: z.array(z.string()).default([]),
    authority_purpose: z.literal("cycle_input_candidate_only"),
    candidate_id: z.string().min(1),
    child_profile_family_ref: runGenericCycleSimulationArtifactRefSchema
      .nullable()
      .optional(),
    child_profile_set_ref: runGenericCycleSimulationArtifactRefSchema
      .nullable()
      .optional(),
    context_job_ref: runGenericCycleSimulationArtifactRefSchema,
    currentness_status: z.literal("not_established"),
    cycle_index: z.number().int().nonnegative(),
    design_problem_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    n4_source_ref: runGenericCycleSimulationArtifactRefSchema,
    n5_execution_ref: runGenericCycleSimulationArtifactRefSchema
      .nullable()
      .optional(),
    n5_input_ref: runGenericCycleSimulationArtifactRefSchema,
    n5_owner_join_status: z
      .enum([
        "resolved",
        "unavailable",
        "invalid",
        "mismatch",
        "not_established",
      ])
      .nullable()
      .optional(),
    n5_owner_join_limitation_code: z.string().min(1).nullable().optional(),
    n5_request_binding_status: z.enum(["resolved", "not_established"]),
    n5_request_content_hash: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable()
      .optional(),
    n8_authority_blockers: z.array(z.string()).default([]),
    n8_limitation_code: z.string().min(1).nullable().optional(),
    n5_interaction_evidence: runN5InteractionEvidenceSchema
      .nullable()
      .optional(),
    n8_numeric_interaction: z
      .enum(["none", "additive", "non_additive", "unsupported"])
      .nullable()
      .optional(),
    n8_numeric_interaction_basis: z
      .enum(["finite_checked_model_point_estimate_only", "not_established"])
      .nullable()
      .optional(),
    n8_interaction_sampling_status: z
      .enum(["estimated", "standard_error_not_estimated", "not_established"])
      .nullable()
      .optional(),
    n8_lineage_status: z.enum(["resolved", "not_established"]),
    n8_status: z.enum([
      "value_ready",
      "value_conditional",
      "value_blocked",
      "value_pending_n8",
    ]),
    n8_value_ref: z.string().nullable().optional(),
    node_ref: z.string().min(1),
    profile_ref: runGenericCycleSimulationArtifactRefSchema,
    profile_selection_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    publication_authority: z.literal(false),
    selected_outcomes: z.array(z.string()).default([]),
    executed_steps: z.array(z.number().int()).default([]),
    replication_seeds: z.array(z.number().int()).default([]),
    simulation_result_ref: runGenericCycleSimulationArtifactRefSchema
      .nullable()
      .optional(),
    simulation_result_body: runGenericCycleSimulationN5ResultBodySchema
      .nullable()
      .optional(),
    simulation_result_body_status: z
      .enum(["not_applicable", "resolved", "not_established"])
      .nullable()
      .optional(),
    simulation_result_body_limitation_code: z
      .enum([
        "generic_n5_result_body_request_binding_not_established",
        "generic_n5_result_body_selected_manifest_view_not_established",
        "generic_n5_result_body_execution_not_successful",
        "generic_n5_result_body_content_refused",
      ])
      .nullable()
      .optional(),
    status: z.enum([
      "joint_simulated",
      "simulation_pending_n5",
      "simulation_blocked",
    ]),
    world_model_record_content_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
  })
  .strict()
  .superRefine((observation, context) => {
    validateRunN5InteractionScope(
      observation.n5_interaction_evidence,
      observation,
      context,
    );
    const expectedNodeRef =
      "design-problem://" +
      observation.design_problem_ref.slice("sha256:".length);
    if (observation.node_ref !== expectedNodeRef) {
      context.addIssue({
        code: "custom",
        path: ["node_ref"],
        message: "generic_cycle_n5_design_problem_node_mismatch",
      });
    }

    const requiredRefs = [
      [
        "n4_source_ref",
        observation.n4_source_ref,
        "runtime.generation_source_handoff",
      ],
      [
        "context_job_ref",
        observation.context_job_ref,
        "runtime.quality.cycle_substrate_context_job",
      ],
      [
        "profile_ref",
        observation.profile_ref,
        "runtime.quality.generic_cycle_simulation_profile",
      ],
      [
        "n5_input_ref",
        observation.n5_input_ref,
        "runtime.quality.generic_cycle_simulation_n5_input",
      ],
    ] as const;
    for (const [field, ref, kind] of requiredRefs) {
      if (ref.kind !== kind || ref.media_type !== "application/json") {
        context.addIssue({
          code: "custom",
          path: [field],
          message: "generic_cycle_n5_required_ref_kind_invalid",
        });
      }
    }
    const optionalRefs = [
      [
        "child_profile_family_ref",
        observation.child_profile_family_ref,
        "runtime.quality.generic_cycle_simulation_child_profile_family",
      ],
      [
        "child_profile_set_ref",
        observation.child_profile_set_ref,
        "runtime.quality.recursive_n4_child_profile_set",
      ],
      [
        "n5_execution_ref",
        observation.n5_execution_ref,
        "runtime.quality.generic_cycle_simulation_n5_execution",
      ],
      [
        "simulation_result_ref",
        observation.simulation_result_ref,
        "polisyos.runtime.joint_simulation_result",
      ],
    ] as const;
    for (const [field, ref, kind] of optionalRefs) {
      if (
        ref != null &&
        (ref.kind !== kind || ref.media_type !== "application/json")
      ) {
        context.addIssue({
          code: "custom",
          path: [field],
          message: "generic_cycle_n5_optional_ref_kind_invalid",
        });
      }
    }

    const resultBody = observation.simulation_result_body;
    const resultRef = observation.simulation_result_ref;
    const resultBodyStatus = observation.simulation_result_body_status;
    const resultBodyLimitation =
      observation.simulation_result_body_limitation_code;
    if (resultRef == null) {
      if (
        resultBody != null ||
        (resultBodyStatus != null && resultBodyStatus !== "not_applicable") ||
        resultBodyLimitation != null
      ) {
        context.addIssue({
          code: "custom",
          path: ["simulation_result_body_status"],
          message: "generic_n5_result_body_without_result_ref",
        });
      }
    } else if (resultBody == null) {
      if (
        resultBodyStatus !== "not_established" ||
        resultBodyLimitation == null
      ) {
        context.addIssue({
          code: "custom",
          path: ["simulation_result_body_status"],
          message: "generic_n5_result_body_unavailable_reason_missing",
        });
      }
    } else if (
      resultBodyStatus !== "resolved" ||
      resultBodyLimitation != null ||
      observation.status !== "joint_simulated" ||
      resultBody.artifact_ref.artifact_id !== resultRef.artifact_id ||
      resultBody.artifact_ref.kind !== resultRef.kind ||
      resultBody.artifact_ref.media_type !== resultRef.media_type ||
      resultBody.artifact_ref.manifest_profile_sha256 !==
        resultRef.manifest_profile_sha256 ||
      resultBody.world_model_record_content_hash !==
        observation.world_model_record_content_hash ||
      JSON.stringify(resultBody.atom_ids) !==
        JSON.stringify(observation.atom_ids) ||
      JSON.stringify(resultBody.selected_outcomes) !==
        JSON.stringify(observation.selected_outcomes)
    ) {
      context.addIssue({
        code: "custom",
        path: ["simulation_result_body"],
        message: "generic_n5_result_body_parent_binding_invalid",
      });
    }

    if (
      (observation.child_profile_family_ref == null) !==
      (observation.child_profile_set_ref == null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["child_profile_set_ref"],
        message: "generic_cycle_n5_child_family_set_pair_invalid",
      });
    }
    if (
      observation.status === "joint_simulated" &&
      observation.simulation_result_ref == null
    ) {
      context.addIssue({
        code: "custom",
        path: ["simulation_result_ref"],
        message: "generic_cycle_n5_success_result_missing",
      });
    }
    if (
      observation.status === "joint_simulated" &&
      observation.n5_execution_ref == null &&
      !["unavailable", "not_established"].includes(
        observation.n5_owner_join_status ?? "",
      )
    ) {
      context.addIssue({
        code: "custom",
        path: ["n5_execution_ref"],
        message: "generic_cycle_n5_success_owner_missing_without_limitation",
      });
    }
    const ownerStatus = observation.n5_owner_join_status;
    if (ownerStatus === "resolved") {
      if (
        observation.n5_owner_join_limitation_code != null ||
        observation.n5_request_binding_status !== "resolved" ||
        observation.n5_execution_ref == null
      ) {
        context.addIssue({
          code: "custom",
          path: ["n5_owner_join_status"],
          message: "generic_cycle_n5_owner_join_resolved_invalid",
        });
      }
    } else if (ownerStatus != null) {
      if (
        observation.n5_owner_join_limitation_code == null ||
        ((ownerStatus === "invalid" || ownerStatus === "mismatch") &&
          (observation.status !== "simulation_blocked" ||
            observation.n8_status !== "value_blocked"))
      ) {
        context.addIssue({
          code: "custom",
          path: ["n5_owner_join_status"],
          message: "generic_cycle_n5_owner_join_refusal_invalid",
        });
      }
    } else if (observation.n5_owner_join_limitation_code != null) {
      context.addIssue({
        code: "custom",
        path: ["n5_owner_join_status"],
        message: "generic_cycle_n5_owner_join_status_missing",
      });
    }
    if (
      (observation.n5_request_binding_status === "resolved") !==
      (observation.n5_request_content_hash != null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["n5_request_content_hash"],
        message: "generic_cycle_n5_request_binding_shape_invalid",
      });
    }
    if (
      observation.n8_lineage_status === "resolved" &&
      observation.n5_request_binding_status !== "resolved"
    ) {
      context.addIssue({
        code: "custom",
        path: ["n8_lineage_status"],
        message: "generic_cycle_n8_request_binding_not_established",
      });
    }
    if (observation.n8_status === "value_conditional") {
      if (
        observation.n5_interaction_evidence == null ||
        observation.n8_numeric_interaction == null ||
        observation.n8_numeric_interaction_basis == null ||
        observation.n8_interaction_sampling_status == null ||
        observation.n8_numeric_interaction !==
          observation.n5_interaction_evidence.numeric_interaction ||
        observation.n8_numeric_interaction_basis !==
          observation.n5_interaction_evidence.numeric_interaction_basis ||
        observation.n8_interaction_sampling_status !==
          observation.n5_interaction_evidence.interaction_sampling_status
      ) {
        context.addIssue({
          code: "custom",
          path: ["n5_interaction_evidence"],
          message:
            "generic_cycle_n8_interaction_qualification_missing_or_mismatched",
        });
      }
      if (
        observation.n8_numeric_interaction === "unsupported" &&
        !observation.n8_authority_blockers.includes(
          "interaction_numeric_classification_unsupported",
        )
      ) {
        context.addIssue({
          code: "custom",
          path: ["n8_authority_blockers"],
          message: "generic_cycle_n8_unsupported_interaction_not_limited",
        });
      }
      if (
        observation.n8_interaction_sampling_status != null &&
        observation.n8_interaction_sampling_status !== "estimated" &&
        ![
          "interaction_sampling_not_established",
          "standard_error_not_estimated",
          "legacy_interaction_not_established",
        ].some((code) => observation.n8_authority_blockers.includes(code))
      ) {
        context.addIssue({
          code: "custom",
          path: ["n8_authority_blockers"],
          message: "generic_cycle_n8_unestimated_interaction_not_limited",
        });
      }
      if (observation.n8_lineage_status === "resolved") {
        if (
          observation.simulation_result_ref == null ||
          observation.n8_value_ref !==
            observation.simulation_result_ref.artifact_id ||
          observation.n8_limitation_code != null
        ) {
          context.addIssue({
            code: "custom",
            path: ["n8_value_ref"],
            message: "generic_cycle_n8_conditional_binding_invalid",
          });
        }
      } else if (
        observation.n8_limitation_code == null ||
        observation.n8_value_ref != null
      ) {
        context.addIssue({
          code: "custom",
          path: ["n8_limitation_code"],
          message: "generic_cycle_n8_conditional_limitation_missing",
        });
      }
    } else if (observation.n8_lineage_status === "resolved") {
      context.addIssue({
        code: "custom",
        path: ["n8_lineage_status"],
        message: "generic_cycle_n8_nonconditional_resolved_invalid",
      });
    }
    if (
      (observation.n8_lineage_status === "not_established") !==
      (observation.n8_limitation_code != null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["n8_limitation_code"],
        message: "generic_cycle_n8_limitation_shape_invalid",
      });
    }
  });

const runGenericCycleSimulationN6CycleHistoryEntrySchema = z
  .object({
    cycle_index: z.number().int().nonnegative(),
    design_problem_basis_ref: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .nullable(),
    design_problem_ref: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    generation_cycle_run_terminal_status: z.enum(["completed", "blocked"]),
    grounding_current_valid: z.boolean(),
    grounding_status: z.enum([
      "current_valid",
      "grounded_shadow",
      "grounding_gap",
      "grounding_failed",
      "grounding_unavailable",
    ]),
    node_ref: z.string().min(1),
    refinement_decision: z.enum([
      "refine",
      "acquire",
      "reframe",
      "decompose",
      "human_decision",
      "abstain",
      "block_candidate",
      "stop",
    ]),
    search_iteration_status: z.enum([
      "blocked",
      "blocked_no_retry",
      "governance_required",
      "acquisition_required",
      "abstained",
      "stopped",
      "refined_shadow",
    ]),
    selected_candidate_content_hash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    selected_candidate_ref: z.string().min(1),
    terminal_kind: z.enum([
      "a_spec_gap",
      "tool_failure",
      "composition_invalid",
      "recursive_blocked",
      "search_ceiling_repair_required",
      "human_decision_required",
      "acquisition_required",
      "budget_exhausted",
      "frontier_stable",
      "grounded_admissible",
      "grounded_partial_admissible",
      "grounded_abstention",
    ]),
    value_authority_blockers: z.array(z.string()),
    value_decision_grade: z
      .enum(["blocked", "low", "medium", "high"])
      .nullable(),
    value_ref: z.string().nullable(),
    value_status: z.enum([
      "value_pending_n8",
      "value_ready",
      "value_conditional",
      "value_blocked",
    ]),
    voi_next_action: z.enum(["advance", "stop", "escalate", "blocked"]),
  })
  .strict();

const runGenericCycleSimulationProjectionFields = {
  artifact_status: z.enum(["resolved", "not_established"]),
  authority_purpose: z
    .literal("cycle_input_candidate_only")
    .default("cycle_input_candidate_only"),
  child_profile_bindings: z
    .array(runGenericCycleSimulationChildProfileBindingSchema)
    .default([]),
  child_profile_family_ref: runGenericCycleSimulationArtifactRefSchema
    .nullable()
    .optional(),
  child_profile_limitation_code: z.string().min(1).nullable().optional(),
  child_profile_set_ref: runGenericCycleSimulationArtifactRefSchema
    .nullable()
    .optional(),
  child_profile_status: z.enum([
    "not_attempted",
    "resolved",
    "not_established",
  ]),
  credal_source_attempt_ref: runGenericCycleSimulationArtifactRefSchema
    .nullable()
    .optional(),
  credal_source_limitation_code: z
    .enum([
      "candidate_source_authority_not_established",
      "candidate_source_attempt_replay_not_established",
    ])
    .nullable()
    .optional(),
  credal_source_status: z.literal("not_established").nullable().optional(),
  currentness_status: z.literal("not_established").default("not_established"),
  limitation_code: z.string().min(1).nullable().optional(),
  n4_source_limitation_code: z.string().min(1).nullable().optional(),
  n4_source_ref: runGenericCycleSimulationArtifactRefSchema
    .nullable()
    .optional(),
  n4_source_status: z
    .enum(["resolved", "not_established"])
    .nullable()
    .optional(),
  n5_limitation_code: z.string().min(1).nullable().optional(),
  n5_observations: z
    .array(runGenericCycleSimulationN5ObservationSchema)
    .default([]),
  joint_parent_observations: z
    .array(runCandidateSimulationN5ObservationSchema)
    .optional(),
  joint_parent_status: z
    .enum(["resolved", "not_established"])
    .nullable()
    .optional(),
  joint_parent_limitation_code: z.string().min(1).nullable().optional(),
  n6_cycle_history: z
    .array(runGenericCycleSimulationN6CycleHistoryEntrySchema)
    .optional(),
  n6_cycle_history_limitation_code: z
    .literal("n6_cycle_history_not_emitted")
    .nullable()
    .optional(),
  n6_cycle_history_status: z
    .enum(["resolved", "not_established"])
    .nullable()
    .optional(),
  parent_context_job_ref: runGenericCycleSimulationArtifactRefSchema
    .nullable()
    .optional(),
  parent_profile_id: z.string().min(1).nullable().optional(),
  parent_profile_ref: runGenericCycleSimulationArtifactRefSchema
    .nullable()
    .optional(),
  publication_authority: z.literal(false).default(false),
  recursive_cycle_checkpoint: runGenericCycleSimulationCheckpointSchema
    .nullable()
    .optional(),
  run_id: z.string().min(1),
  source_content_hash: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  source_ref: runGenericCycleSimulationArtifactRefSchema.nullable().optional(),
};

export const runGenericCycleSimulationProjectionSchema = z
  .discriminatedUnion("schema_version", [
    z
      .object({
        ...runGenericCycleSimulationProjectionFields,
        schema_version: z.literal(
          "policyos.runtime.run_generic_cycle_simulation_projection.v1",
        ),
      })
      .strict(),
    z
      .object({
        ...runGenericCycleSimulationProjectionFields,
        credal_source_limitation_code: z
          .enum([
            "candidate_source_authority_not_established",
            "candidate_source_attempt_replay_not_established",
          ])
          .nullable()
          .optional(),
        credal_source_status: z
          .literal("not_established")
          .nullable()
          .optional(),
        schema_version: z.literal(
          "policyos.runtime.run_generic_cycle_simulation_projection.v2",
        ),
      })
      .strict(),
    z
      .object({
        ...runGenericCycleSimulationProjectionFields,
        n6_cycle_history: z
          .array(runGenericCycleSimulationN6CycleHistoryEntrySchema)
          .optional(),
        n6_cycle_history_limitation_code: z
          .literal("n6_cycle_history_not_emitted")
          .nullable()
          .optional(),
        n6_cycle_history_status: z
          .enum(["resolved", "not_established"])
          .nullable()
          .optional(),
        schema_version: z.literal(
          "policyos.runtime.run_generic_cycle_simulation_projection.v3",
        ),
      })
      .strict(),
    z
      .object({
        ...runGenericCycleSimulationProjectionFields,
        credal_source_limitation_code: z
          .enum([
            "candidate_source_authority_not_established",
            "candidate_source_attempt_replay_not_established",
          ])
          .nullable()
          .optional(),
        credal_source_status: z
          .literal("not_established")
          .nullable()
          .optional(),
        n6_cycle_history: z
          .array(runGenericCycleSimulationN6CycleHistoryEntrySchema)
          .optional(),
        n6_cycle_history_limitation_code: z
          .literal("n6_cycle_history_not_emitted")
          .nullable()
          .optional(),
        n6_cycle_history_status: z
          .enum(["resolved", "not_established"])
          .nullable()
          .optional(),
        schema_version: z.literal(
          "policyos.runtime.run_generic_cycle_simulation_projection.v4",
        ),
      })
      .strict(),
    z
      .object({
        ...runGenericCycleSimulationProjectionFields,
        schema_version: z.literal(
          "policyos.runtime.run_generic_cycle_simulation_projection.v5",
        ),
      })
      .strict(),
  ])
  .superRefine((projection, context) => {
    const version = projection.schema_version;
    const hasJointParentExtension = projection.joint_parent_status != null;
    const hasOwnerJoinExtension = projection.n5_observations.some(
      (row) => row.n5_owner_join_status != null,
    );
    const hasV5Extension = hasJointParentExtension || hasOwnerJoinExtension;
    const isV5 =
      version === "policyos.runtime.run_generic_cycle_simulation_projection.v5";
    if (hasV5Extension !== isV5) {
      context.addIssue({
        code: "custom",
        path: ["schema_version"],
        message: "generic_projection_v5_schema_invalid",
      });
    }
    const parentRows = projection.joint_parent_observations ?? [];
    if (projection.joint_parent_status === "resolved") {
      const parent = parentRows[0];
      if (
        parentRows.length !== 1 ||
        projection.joint_parent_limitation_code != null ||
        parent == null ||
        parent.status !== "joint_simulated" ||
        parent.simulation_result_ref == null ||
        parent.simulation_ref == null ||
        parent.n5_interaction_evidence == null ||
        parent.n8_candidate_joint_selection_status !== "resolved" ||
        !["value_pending_n8", "value_conditional"].includes(
          parent.n8_status ?? "",
        ) ||
        parent.n8_joint_scope_status !== "not_established"
      ) {
        context.addIssue({
          code: "custom",
          path: ["joint_parent_status"],
          message: "generic_projection_parent_binding_invalid",
        });
      }
    } else if (projection.joint_parent_status === "not_established") {
      if (
        parentRows.length > 0 ||
        projection.joint_parent_limitation_code == null
      ) {
        context.addIssue({
          code: "custom",
          path: ["joint_parent_limitation_code"],
          message: "generic_projection_parent_limitation_missing",
        });
      }
    } else if (
      parentRows.length > 0 ||
      projection.joint_parent_limitation_code != null
    ) {
      context.addIssue({
        code: "custom",
        path: ["joint_parent_status"],
        message: "generic_projection_parent_status_missing",
      });
    }
    const hasCredalAttemptProjection =
      projection.credal_source_attempt_ref != null ||
      projection.credal_source_status != null ||
      projection.credal_source_limitation_code != null;
    const credalAttemptExpected =
      version ===
        "policyos.runtime.run_generic_cycle_simulation_projection.v2" ||
      version === "policyos.runtime.run_generic_cycle_simulation_projection.v4";

    if (hasCredalAttemptProjection !== credalAttemptExpected) {
      context.addIssue({
        code: "custom",
        path: ["credal_source_attempt_ref"],
        message: "generic_projection_credal_version_binding_invalid",
      });
    }
    if (
      credalAttemptExpected &&
      (projection.credal_source_status !== "not_established" ||
        projection.credal_source_limitation_code == null ||
        projection.child_profile_status !== "not_established" ||
        projection.n5_observations.length > 0 ||
        (projection.credal_source_attempt_ref != null &&
          (projection.credal_source_attempt_ref.kind !==
            "runtime.quality.candidate_credal_source_attempt" ||
            projection.credal_source_attempt_ref.media_type !==
              "application/json")))
    ) {
      context.addIssue({
        code: "custom",
        path: ["credal_source_attempt_ref"],
        message: "generic_projection_credal_source_attempt_invalid",
      });
    }

    const hasN6CycleHistoryExtension =
      projection.n6_cycle_history_status != null ||
      projection.n6_cycle_history_limitation_code != null ||
      (projection.n6_cycle_history?.length ?? 0) > 0;
    const n6CycleHistoryExpected =
      version ===
        "policyos.runtime.run_generic_cycle_simulation_projection.v3" ||
      version ===
        "policyos.runtime.run_generic_cycle_simulation_projection.v4" ||
      (isV5 && hasN6CycleHistoryExtension);
    if (hasN6CycleHistoryExtension !== n6CycleHistoryExpected) {
      context.addIssue({
        code: "custom",
        path: ["n6_cycle_history_status"],
        message: "generic_projection_n6_version_binding_invalid",
      });
    }
    if (n6CycleHistoryExpected) {
      const history = projection.n6_cycle_history ?? [];
      if (
        projection.n6_cycle_history_status == null ||
        (projection.n6_cycle_history_status === "resolved" &&
          (history.length === 0 ||
            projection.n6_cycle_history_limitation_code != null)) ||
        (projection.n6_cycle_history_status === "not_established" &&
          (history.length > 0 ||
            projection.n6_cycle_history_limitation_code !==
              "n6_cycle_history_not_emitted"))
      ) {
        context.addIssue({
          code: "custom",
          path: ["n6_cycle_history_status"],
          message: "generic_projection_n6_history_status_invalid",
        });
      }
      const historyKeys = history.map((row) =>
        JSON.stringify([row.node_ref, row.cycle_index]),
      );
      if (new Set(historyKeys).size !== historyKeys.length) {
        context.addIssue({
          code: "custom",
          path: ["n6_cycle_history"],
          message: "generic_projection_n6_history_duplicate_cycle",
        });
      }
    }

    if (projection.artifact_status === "resolved") {
      if (
        projection.source_ref == null ||
        projection.source_content_hash == null
      ) {
        context.addIssue({
          code: "custom",
          path: ["source_ref"],
          message: "generic_projection_compiled_source_missing",
        });
      }
      if (
        projection.n4_source_status === "resolved" &&
        (projection.n4_source_ref == null ||
          projection.n4_source_limitation_code != null ||
          projection.parent_context_job_ref == null ||
          projection.parent_profile_ref == null ||
          projection.parent_profile_id == null)
      ) {
        context.addIssue({
          code: "custom",
          path: ["n4_source_ref"],
          message: "generic_projection_n4_binding_missing",
        });
      }
      if (
        projection.child_profile_status === "resolved" &&
        (projection.child_profile_family_ref == null ||
          projection.child_profile_set_ref == null ||
          projection.child_profile_limitation_code != null ||
          projection.child_profile_bindings.length === 0 ||
          projection.child_profile_bindings.some(
            (row) => row.historical_binding_status !== "resolved",
          ))
      ) {
        context.addIssue({
          code: "custom",
          path: ["child_profile_bindings"],
          message: "generic_projection_child_binding_missing",
        });
      }
      if (
        projection.child_profile_status === "not_established" &&
        projection.child_profile_limitation_code == null
      ) {
        context.addIssue({
          code: "custom",
          path: ["child_profile_limitation_code"],
          message: "generic_projection_child_limitation_missing",
        });
      }
      return;
    }

    if (
      projection.source_content_hash != null ||
      projection.n4_source_status != null ||
      projection.child_profile_bindings.length > 0 ||
      projection.n5_observations.length > 0 ||
      hasJointParentExtension ||
      parentRows.length > 0 ||
      projection.joint_parent_limitation_code != null ||
      hasN6CycleHistoryExtension ||
      projection.limitation_code == null
    ) {
      context.addIssue({
        code: "custom",
        path: ["artifact_status"],
        message: "generic_projection_refusal_shape_invalid",
      });
    }
  });

const runSummarySchema = z
  .object({
    run_id: z.string(),
    source_kind: z.literal("core_run"),
    status: z.string(),
    run_terminality: runTerminalitySchema,
    cell_id: z.string().nullable().optional(),
    control_job_id: z.string().nullable().optional(),
    decision_review_required: z.boolean().default(false),
    decision_superseded_by_ref: coreArtifactRefSchema.nullable().optional(),
    decision_validity_checked_at: z.string().nullable().optional(),
    decision_validity_status: decisionValidityStatusSchema
      .nullable()
      .optional(),
    execution_profile: z.string().nullable().optional(),
    started_at: z.string().nullable().optional(),
    finished_at: z.string().nullable().optional(),
    duration_ms: z.number().nullable().optional(),
    tenant_id: z.string().nullable().optional(),
    has_trace: z.boolean().default(false),
    root_artifact_count: z.number().default(0),
    has_workflow_report: z.boolean().default(false),
    warnings: z.array(z.string()).optional(),
  })
  .strict();

const runConditionalTransportCandidateProjectionSchema = z
  .object({
    candidate_scope: z.literal("candidate_only"),
    candidate_disposition: z.enum([
      "not_run",
      "completed",
      "partial",
      "unsupported",
      "error",
    ]),
    requested_profile_id: z.string().min(1).max(160),
    requested_profile_revision: z.string().min(1).max(80),
    selection_identity: z.string().min(1).max(240),
    reason_code: z
      .string()
      .regex(/^[a-z][a-z0-9_]{1,95}$/)
      .nullable(),
    proposal_count: z.number().int().min(0),
    member_evaluation_count: z.number().int().min(0),
    completed_valid_member_count: z.number().int().min(0),
    identified_member_fraction: z.number().min(0).max(1).nullable(),
    identified_member_fraction_basis: z.literal(
      "selected_completed_valid_members",
    ),
    source_currentness: z.literal("unknown"),
    interpretation_limit: z.literal(
      "selected_family_member_outcomes_do_not_establish_whole_pag_class_probability_calibration_legal_applicability_or_protected_eligibility",
    ),
  })
  .strict()
  .superRefine((projection, context) => {
    if (
      projection.completed_valid_member_count >
      projection.member_evaluation_count
    ) {
      context.addIssue({
        code: "custom",
        path: ["completed_valid_member_count"],
        message:
          "conditional_transport_completed_member_count_exceeds_evaluations",
      });
    }
    const hasCompletedValidMembers =
      projection.completed_valid_member_count > 0;
    if (
      hasCompletedValidMembers !==
      (projection.identified_member_fraction !== null)
    ) {
      context.addIssue({
        code: "custom",
        path: ["identified_member_fraction"],
        message: "conditional_transport_fraction_denominator_mismatch",
      });
    }
  }) satisfies z.ZodType<
  components["schemas"]["RunConditionalTransportCandidateProjection"]
>;

export type RunConditionalTransportCandidateProjectionView = z.output<
  typeof runConditionalTransportCandidateProjectionSchema
>;

/** Return one valid candidate projection, or null for absence and invalid input. */
export function parseRunConditionalTransportCandidateProjection(
  value: unknown,
): RunConditionalTransportCandidateProjectionView | null {
  if (value == null) {
    return null;
  }
  const parsed =
    runConditionalTransportCandidateProjectionSchema.safeParse(value);
  return parsed.success ? parsed.data : null;
}

const directMethodRunProjectionSchema = z.custom<
  components["schemas"]["DirectMethodExecutionRunProjection"]
>((value) => {
  const result = parseRunExecutionHteProjection(value);
  return result.kind !== "invalid" && result.kind !== "absent";
});

const methodExecutionDiagnosticArtifactRefSchema = <Kind extends string>(
  kind: Kind,
) =>
  coreArtifactRefSchema
    .extend({
      kind: z.literal(kind),
      media_type: z.literal("application/json"),
      manifest_profile_sha256: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    })
    .strict();

const methodExecutionProducerEmissionDiagnosticSchema = z
  .object({
    emission_index: z.number().int().min(0),
    execute_result_status: z.enum(["ok", "failed", "not_established"]),
    output_ref_status: z.enum(["complete", "partial", "none"]),
    simulation_result_ref: methodExecutionDiagnosticArtifactRefSchema(
      "foundry.simulation_result",
    )
      .nullable()
      .optional(),
    method_execution_bundle_refs: z
      .array(
        methodExecutionDiagnosticArtifactRefSchema(
          "foundry.method_execution_bundle",
        ),
      )
      .max(8)
      .default([]),
    method_metric_binding_set_refs: z
      .array(
        methodExecutionDiagnosticArtifactRefSchema(
          "foundry.method_metric_binding_set",
        ),
      )
      .max(8)
      .default([]),
  })
  .strict()
  .superRefine((emission, context) => {
    const outputRefCount =
      Number(
        emission.simulation_result_ref !== undefined &&
          emission.simulation_result_ref !== null,
      ) +
      emission.method_execution_bundle_refs.length +
      emission.method_metric_binding_set_refs.length;
    const complete =
      emission.simulation_result_ref !== undefined &&
      emission.simulation_result_ref !== null &&
      emission.method_execution_bundle_refs.length === 1 &&
      emission.method_metric_binding_set_refs.length === 1;

    if (
      (emission.output_ref_status === "complete" && !complete) ||
      (emission.output_ref_status === "partial" && outputRefCount === 0) ||
      (emission.output_ref_status === "none" && outputRefCount !== 0)
    ) {
      context.addIssue({
        code: "custom",
        message: "method_execution_producer_diagnostic_status_mismatch",
      });
    }
  });

const methodExecutionProducerDiagnosticSchema = z
  .object({
    job_id: z.string().min(1).max(128),
    run_id: z.string().min(1).max(128),
    attempt: z.number().int().min(1),
    authority_status: z.literal("candidate_only").default("candidate_only"),
    emissions: z
      .array(methodExecutionProducerEmissionDiagnosticSchema)
      .max(16)
      .default([]),
    inventory_truncated: z.boolean().default(false),
    limitations: z
      .array(
        z.enum([
          "producer_diagnostic_only",
          "workflow_authority_not_established",
          "scientific_validity_not_established",
        ]),
      )
      .default([
        "producer_diagnostic_only",
        "workflow_authority_not_established",
        "scientific_validity_not_established",
      ]),
  })
  .strict()
  .superRefine((diagnostic, context) => {
    if (
      diagnostic.emissions.some(
        (emission, index) => emission.emission_index !== index,
      )
    ) {
      context.addIssue({
        code: "custom",
        message: "method_execution_producer_diagnostic_order_invalid",
      });
    }
  });

export type MethodExecutionProducerDiagnosticView = z.output<
  typeof methodExecutionProducerDiagnosticSchema
>;

const runDetailsSchemaInner = z
  .object({
    run_id: z.string(),
    source_kind: z.literal("core_run"),
    status: z.string(),
    started_at: z.string().nullable().optional(),
    finished_at: z.string().nullable().optional(),
    duration_ms: z.number().nullable().optional(),
    tenant_id: z.string().nullable().optional(),
    cell_id: z.string().nullable().optional(),
    control_job_id: z.string().nullable().optional(),
    decision_review_required: z.boolean().default(false),
    decision_superseded_by_ref: coreArtifactRefSchema.nullable().optional(),
    decision_validity_checked_at: z.string().nullable().optional(),
    decision_validity_status: decisionValidityStatusSchema
      .nullable()
      .optional(),
    execution_profile: z.string().nullable().optional(),
    has_trace: z.boolean().default(false),
    has_workflow_report: z.boolean().default(false),
    capability_manifest_ref: coreArtifactRefSchema.nullable().optional(),
    manifest_ref: coreArtifactRefSchema.nullable().optional(),
    operator_diagnostic: operatorDiagnosticSchema.nullable().optional(),
    policy_design_case_projection: policyDesignCaseProjectionSchema
      .nullable()
      .optional(),
    candidate_simulation: runCandidateSimulationProjectionSchema
      .nullable()
      .optional(),
    generic_cycle_simulation: runGenericCycleSimulationProjectionSchema
      .nullable()
      .optional(),
    // This persisted diagnostic is candidate-only; it does not establish
    // workflow authority, scientific validity, or publication authority.
    method_execution_producer_diagnostic:
      methodExecutionProducerDiagnosticSchema.nullable().optional(),
    // Runtime's current GET adds a bounded candidate-only direct-method
    // projection; its selected HTE summary is validated by the consuming view.
    method_execution_selection: directMethodRunProjectionSchema
      .nullable()
      .optional(),
    // This conditional family diagnostic remains candidate-only and cannot
    // establish transport authority, source currentness, or legal eligibility.
    conditional_transport_candidate:
      runConditionalTransportCandidateProjectionSchema.nullable().optional(),
    trace_ref: coreArtifactRefSchema.nullable().optional(),
    workflow_report_ref: coreArtifactRefSchema.nullable().optional(),
    root_artifacts: z.array(coreArtifactRefSchema).optional(),
    root_input_artifacts: z.array(coreArtifactRefSchema).optional(),
    warnings: z.array(z.string()).optional(),
  })
  .strict();

export type RunDetailsView = z.output<typeof runDetailsSchemaInner>;

const runTimelineEventSchema = z.object({
  index: z.number(),
  timestamp: z.string(),
  phase: z.string(),
  event: z.string(),
  span_id: z.string().nullable().optional(),
  parent_span_id: z.string().nullable().optional(),
  input_artifact_ids: z.array(z.string()).optional(),
  output_artifact_ids: z.array(z.string()).optional(),
  input_artifact_refs: z.array(artifactRefSchema).optional(),
  output_artifact_refs: z.array(artifactRefSchema).optional(),
  metrics: z.record(z.string(), z.number()).optional(),
  warning_count: z.number().optional(),
  error_count: z.number().optional(),
});

const runTimelineSummarySchema = z.object({
  run_id: z.string(),
  total_events: z.number(),
  duration_ms: z.number().nullable().optional(),
  node_status_counts: z.record(z.string(), z.number()).optional(),
  phase_counts: z.record(z.string(), z.number()).optional(),
  cache_hits: z.number().optional(),
  cache_stores: z.number().optional(),
  cache_bypasses: z.number().optional(),
});

const runTimelineViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  summary: runTimelineSummarySchema,
  events: z.array(runTimelineEventSchema).optional(),
  notes: z.array(z.string()).optional(),
});

const runNodeRecordSchema = z.object({
  alias: z.string(),
  node_id: z.string().nullable().optional(),
  status: z.enum(["ok", "skip", "fail", "unknown"]),
  duration_ms: z.number(),
  error_code: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  error_details: z.record(z.string(), z.unknown()).optional(),
  skip_reason: z.string().nullable().optional(),
  artifact_ids: z.array(z.string()).optional(),
  input_artifact_ids: z.array(z.string()).optional(),
  output_artifact_ids: z.array(z.string()).optional(),
  input_artifact_refs: z.array(artifactRefSchema).optional(),
  output_artifact_refs: z.array(artifactRefSchema).optional(),
});

const runErrorViewSchema = z.object({
  source: z.enum(["manifest", "workflow_report", "trace", "runtime"]),
  code: z.string(),
  message: z.string(),
  node_alias: z.string().nullable().optional(),
  timestamp: z.string().nullable().optional(),
  details: z.record(z.string(), z.unknown()).optional(),
});

const governanceIssueSchema = z.record(z.string(), z.unknown()).and(
  z.object({
    code: z.string().optional(),
    severity: z.string().optional(),
    message: z.string().optional(),
    pass_id: z.string().optional(),
  }),
);

const governanceDebugViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  verdict: z.string().nullable().optional(),
  issues: z.array(governanceIssueSchema).optional(),
  issue_summary: z.record(z.string(), z.number()).nullable().optional(),
  notes: z.array(z.string()).optional(),
  report_ref: artifactRefSchema.nullable().optional(),
  report_kind: z.string().nullable().optional(),
  report_schema_version: z.string().nullable().optional(),
  links: z
    .record(z.string(), artifactRefSchema.nullable())
    .nullable()
    .optional(),
  legal_executed: z.boolean().nullable().optional(),
  transport_summary: z.record(z.string(), z.unknown()).nullable().optional(),
  validation_trace: z.record(z.string(), z.unknown()).nullable().optional(),
  contract_warnings: z.array(z.string()).optional(),
  decision_validity: z.record(z.string(), z.unknown()).nullable().optional(),
  normative_summary: z.record(z.string(), z.unknown()).nullable().optional(),
  normative_arbitration_result_ref: artifactRefSchema.nullable().optional(),
  fallback_from_decision_packet: z.boolean().optional(),
});

const nodeDebugViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  alias: z.string(),
  record: runNodeRecordSchema,
  timeline_events: z.array(runTimelineEventSchema).optional(),
  cache_hits: z.number().optional(),
  cache_stores: z.number().optional(),
  cache_bypasses: z.number().optional(),
  notes: z.array(z.string()).optional(),
});

const agentPipelineCostEventSchema = z
  .object({
    event_id: z.string().min(1),
    origin_event_id: z.string().min(1).nullable().default(null),
    cost_origin: z.enum(["reported", "estimated", "reuse", "unknown"]),
    control_job_attempt: z.number().int().min(1).nullable().default(null),
    pre_admission_attempt_id: z
      .string()
      .regex(/^[a-f0-9]{32}$/)
      .nullable()
      .default(null),
    amount: z.string().nullable().default(null),
    cost_usd: z.number().nullable().default(null),
    settlement_status: z.enum(["pending", "committed", "unknown", "unmanaged"]),
    durability: z.enum(["ledger", "memory", "none"]).nullable().default(null),
    receipts: z.array(z.string()).default(() => []),
    payload_digest: z.string().min(1).nullable().default(null),
    model: z.string().nullable().default(null),
    provider: z.string().nullable().default(null),
  })
  .strict()
  .refine(
    (event) =>
      !(
        event.control_job_attempt != null &&
        event.pre_admission_attempt_id != null
      ),
    { message: "producer_attempt_attribution_is_ambiguous" },
  )
  .refine(
    (event) =>
      (event.control_job_attempt == null &&
        event.pre_admission_attempt_id == null) ||
      event.durability === "ledger",
    { message: "producer_attempt_attribution_requires_durable_ledger" },
  );

const agentPipelineUnattributedCostScalarSchema = z
  .object({
    source_kind: z.enum([
      "step_summary",
      "attempt_summary",
      "pipeline_summary",
      "performance_summary_llm",
      "performance_summary_variant_row",
    ]),
    source_field: z.enum([
      "cost_usd",
      "reported_cost_usd",
      "estimated_cost_usd",
    ]),
    claimed_value_usd: z.number().nonnegative(),
    scope: z.literal("not_established").default("not_established"),
    attempt: z.number().int().min(1).nullable().default(null),
    agent: z.string().nullable().default(null),
    model: z.string().nullable().default(null),
    model_variant_id: z.string().nullable().default(null),
    source_index: z.number().int().nonnegative().nullable().default(null),
  })
  .strict();

const agentPipelineStepSchema = z.object({
  attempt: z.number().int().min(1).default(1),
  agent: z.string(),
  action: z.string(),
  status: z.enum(["ok", "warn", "fail", "info"]).default("info"),
  timestamp: z.string().nullable().default(null),
  summary: z.string().nullable().default(null),
  details: z.record(z.string(), z.unknown()).default(() => ({})),
  details_cost_scope: z.literal("not_established").default("not_established"),
  prompt: z.string().nullable().default(null),
  response: z.string().nullable().default(null),
  model: z.string().nullable().default(null),
  provider: z.string().nullable().default(null),
  model_variant_id: z.string().nullable().default(null),
  latency_ms: z.number().int().nonnegative().nullable().default(null),
  cost_usd: z.number().nullable().default(null),
  reported_cost_usd: z.number().nullable().default(null),
  estimated_cost_usd: z.number().nullable().default(null),
  cost_origin: z
    .enum(["reported", "estimated", "reuse", "unknown"])
    .nullable()
    .default(null),
  cost_origin_counts: z
    .record(z.string(), z.number().int())
    .default(() => ({})),
  settlement_status_counts: z
    .record(z.string(), z.number().int())
    .default(() => ({})),
  settlement_event_ids: z.array(z.string()).default(() => []),
  cost_events: z.array(agentPipelineCostEventSchema).default(() => []),
  unattributed_cost_scalars: z
    .array(agentPipelineUnattributedCostScalarSchema)
    .default(() => []),
  token_usage: z.record(z.string(), z.number().int()).default(() => ({})),
});

const agentPipelineAttemptSchema = z.object({
  attempt: z.number().int().min(1),
  status: z.string().default("unknown"),
  verdict: z.string().nullable().default(null),
  started_at: z.string().nullable().default(null),
  finished_at: z.string().nullable().default(null),
  duration_ms: z.number().int().nonnegative().nullable().default(null),
  cost_usd: z.number().nullable().default(null),
  reported_cost_usd: z.number().nullable().default(null),
  estimated_cost_usd: z.number().nullable().default(null),
  cost_origin_counts: z
    .record(z.string(), z.number().int())
    .default(() => ({})),
  settlement_status_counts: z
    .record(z.string(), z.number().int())
    .default(() => ({})),
  steps: z.array(agentPipelineStepSchema).default(() => []),
  unattributed_cost_scalars: z
    .array(agentPipelineUnattributedCostScalarSchema)
    .default(() => []),
  notes: z.array(z.string()).default(() => []),
});

const retrievalPhaseTelemetrySchema = z.object({
  phase: z.string(),
  lane: z.string().nullable().optional(),
  duration_ms: z.number().optional(),
  candidates_total: z.number().optional(),
  candidates_selected: z.number().optional(),
  docs_fetched: z.number().optional(),
});

const retrievalTelemetryViewSchema = z.object({
  mode: z.string().optional(),
  lane_used: z.string().optional(),
  metadata_docs_fetched: z.number().optional(),
  local_index_size_bytes: z.number().optional(),
  local_index_docs_total: z.number().optional(),
  candidates_filtered: z.number().optional(),
  candidates_promoted: z.number().optional(),
  phases: z.array(retrievalPhaseTelemetrySchema).optional(),
  notes: z.array(z.string()).optional(),
});

const preflightDiagnosticViewSchema = z.object({
  code: z.string(),
  severity: z.string().optional(),
  message: z.string(),
  path: z.array(z.string()).optional(),
  replanning_hints: z.array(z.string()).optional(),
  data: z.record(z.string(), z.unknown()).optional(),
});

const preflightReportViewSchema = z.object({
  ready_to_run: z.boolean().optional(),
  diagnostics: z.array(preflightDiagnosticViewSchema).optional(),
  notes: z.array(z.string()).optional(),
  report_ref: artifactRefSchema.nullable().optional(),
});

const evaluatorScoresViewSchema = z.object({
  kpi_score: z.number().optional(),
  uncertainty_score: z.number().optional(),
  constraints_score: z.number().optional(),
  data_quality_score: z.number().optional(),
  budget_score: z.number().optional(),
  total_score: z.number().optional(),
});

const evaluatorReportViewSchema = z.object({
  verdict: z.string().nullable().optional(),
  scores: evaluatorScoresViewSchema.optional(),
  reasons: z.array(z.string()).optional(),
  replanning_hints: z.array(z.string()).optional(),
  diagnostics: z.array(preflightDiagnosticViewSchema).optional(),
  notes: z.array(z.string()).optional(),
  report_ref: artifactRefSchema.nullable().optional(),
});

const iterationLifecycleViewSchema = z.object({
  iteration: z.number().optional(),
  state: z.string().optional(),
  stop_reason: z.string().nullable().optional(),
  last_verdict: z.string().nullable().optional(),
  state_ref: artifactRefSchema.nullable().optional(),
  notes: z.array(z.string()).optional(),
});

const reproducibilityViewSchema = z.object({
  seed: z.number().optional(),
  seed_source: z.string().nullable().optional(),
  determinism_tier: z.string().nullable().optional(),
  plan_hash: z.string().nullable().optional(),
  registry_hash: z.string().nullable().optional(),
  method_catalog_hash: z.string().nullable().optional(),
  data_snapshot_hash: z.string().nullable().optional(),
  input_bindings_hash: z.string().nullable().optional(),
  readiness: z.string().nullable().optional(),
  why_partial: z.array(z.string()).optional(),
  missing_refs: z.array(z.string()).optional(),
  suggested_next_step: z.string().nullable().optional(),
  manifest_ref: artifactRefSchema.nullable().optional(),
  notes: z.array(z.string()).optional(),
});

const performancePhaseBudgetSchema = z.object({
  budget_ms: z.number().nullable().optional(),
  category: z.string().optional(),
  duration_ms: z.number().optional(),
  over_by_ms: z.number().optional(),
  phase: z.string(),
  status: z.string().optional(),
});

const runPerformanceSummarySchema = z
  .object({
    budget_summary: z.record(z.string(), z.unknown()).optional(),
    llm: z.record(z.string(), z.unknown()).optional(),
    phase_budgets: z.array(performancePhaseBudgetSchema).optional(),
    retrieval_phase_durations: z.record(z.string(), z.unknown()).optional(),
    schema_version: z.string().optional(),
    steps_by_action: z.record(z.string(), z.unknown()).optional(),
    variant_rows: z.array(z.record(z.string(), z.unknown())).optional(),
    variants: z.record(z.string(), z.unknown()).optional(),
  })
  .loose();

const agentPipelineViewSchema = z
  .object({
    run_id: z.string(),
    source_kind: z.literal("core_run"),
    total_attempts: z.number().int().nonnegative().default(0),
    cost_usd: z.number().nullable().default(null),
    reported_cost_usd: z.number().nullable().default(null),
    estimated_cost_usd: z.number().nullable().default(null),
    cost_origin_counts: z
      .record(z.string(), z.number().int())
      .default(() => ({})),
    settlement_status_counts: z
      .record(z.string(), z.number().int())
      .default(() => ({})),
    latest_verdict: z.string().nullable().default(null),
    attempts: z.array(agentPipelineAttemptSchema).default(() => []),
    owner_control_job_attempt: z.number().int().min(1).nullable().default(null),
    unattributed_cost_events: z
      .array(agentPipelineCostEventSchema)
      .default(() => []),
    unattributed_cost_scalars: z
      .array(agentPipelineUnattributedCostScalarSchema)
      .default(() => []),
    decision_packet_ref: artifactRefSchema.nullable().default(null),
    reflexion_terminal_ref: artifactRefSchema.nullable().default(null),
    retrieval: retrievalTelemetryViewSchema.nullable().default(null),
    execution_plan_ref: artifactRefSchema.nullable().default(null),
    method_catalog_snapshot_ref: artifactRefSchema.nullable().default(null),
    preflight: preflightReportViewSchema.nullable().default(null),
    evaluator: evaluatorReportViewSchema.nullable().default(null),
    iteration_lifecycle: iterationLifecycleViewSchema.nullable().default(null),
    reproducibility: reproducibilityViewSchema.nullable().default(null),
    performance_summary: runPerformanceSummarySchema.nullable().default(null),
    source: z.string().nullable().default(null),
    notes: z.array(z.string()).default(() => []),
  })
  .superRefine((pipeline, context) => {
    const hasCurrentProjection = (value: {
      cost_usd?: number | null;
      reported_cost_usd?: number | null;
      estimated_cost_usd?: number | null;
      cost_origin_counts?: Record<string, number>;
      settlement_status_counts?: Record<string, number>;
    }) =>
      value.cost_usd != null ||
      value.reported_cost_usd != null ||
      value.estimated_cost_usd != null ||
      Object.keys(value.cost_origin_counts ?? {}).length > 0 ||
      Object.keys(value.settlement_status_counts ?? {}).length > 0;

    if (pipeline.owner_control_job_attempt == null) {
      if (hasCurrentProjection(pipeline)) {
        context.addIssue({
          code: "custom",
          path: ["owner_control_job_attempt"],
          message:
            "agent_pipeline_current_cost_requires_verified_owner_context",
        });
      }
      pipeline.attempts?.forEach((attempt, attemptIndex) => {
        if (hasCurrentProjection(attempt)) {
          context.addIssue({
            code: "custom",
            path: ["attempts", attemptIndex],
            message:
              "agent_pipeline_current_cost_requires_verified_owner_context",
          });
        }
        attempt.steps?.forEach((step, stepIndex) => {
          if (hasCurrentProjection(step)) {
            context.addIssue({
              code: "custom",
              path: ["attempts", attemptIndex, "steps", stepIndex],
              message:
                "agent_pipeline_current_cost_requires_verified_owner_context",
            });
          }
        });
      });
    } else {
      pipeline.attempts?.forEach((attempt, attemptIndex) => {
        attempt.steps?.forEach((step, stepIndex) => {
          step.cost_events?.forEach((event, eventIndex) => {
            if (
              event.durability === "ledger" &&
              event.control_job_attempt !== pipeline.owner_control_job_attempt
            ) {
              context.addIssue({
                code: "custom",
                path: [
                  "attempts",
                  attemptIndex,
                  "steps",
                  stepIndex,
                  "cost_events",
                  eventIndex,
                  "control_job_attempt",
                ],
                message: "agent_pipeline_event_owner_attempt_mismatch",
              });
            }
          });
        });
      });
    }
    pipeline.unattributed_cost_events?.forEach((event, index) => {
      if (event.control_job_attempt != null) {
        context.addIssue({
          code: "custom",
          path: ["unattributed_cost_events", index, "control_job_attempt"],
          message: "unattributed_cost_event_claims_control_job_attempt",
        });
      }
    });
  });

const runWorkflowEdgeViewSchema = z.object({
  from_alias: z.string(),
  to_alias: z.string(),
});

const runWorkflowNodeViewSchema = z.object({
  alias: z.string(),
  node_id: z.string().nullable().optional(),
  depends_on: z.array(z.string()).optional(),
  depth: z.number(),
  status: z.enum(["ok", "skip", "fail", "unknown"]),
  duration_ms: z.number(),
  error_code: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  artifact_ids: z.array(z.string()).optional(),
  input_artifact_ids: z.array(z.string()).optional(),
  output_artifact_ids: z.array(z.string()).optional(),
  input_artifact_refs: z.array(artifactRefSchema).optional(),
  output_artifact_refs: z.array(artifactRefSchema).optional(),
  heat: z.number().optional(),
});

const runWorkflowSummarySchema = z.object({
  workflow_id: z.string().nullable().optional(),
  error_policy: z.string().nullable().optional(),
  status: z.string().nullable().optional(),
  node_count: z.number(),
  edge_count: z.number(),
  ok_count: z.number(),
  skip_count: z.number(),
  fail_count: z.number(),
  max_depth: z.number(),
  critical_path_duration_ms: z.number().nullable().optional(),
});

const runWorkflowViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  summary: runWorkflowSummarySchema,
  nodes: z.array(runWorkflowNodeViewSchema).optional(),
  edges: z.array(runWorkflowEdgeViewSchema).optional(),
  workflow_spec_ref: artifactRefSchema.nullable().optional(),
  workflow_report_ref: artifactRefSchema.nullable().optional(),
  notes: z.array(z.string()).optional(),
});

const artifactLineageNodeSchema = z.object({
  artifact_id: z.string(),
  manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  role: z.string().nullable().optional(),
  kind: z.string().nullable().optional(),
  media_type: z.string().nullable().optional(),
  status: z.string(),
  byte_size: z.number(),
  depth: z.number(),
});

const artifactLineageEdgeSchema = z.object({
  parent_artifact_id: z.string(),
  parent_manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  child_artifact_id: z.string(),
  child_manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  role: z.string(),
});

const artifactLineageViewSchema = z.object({
  root_artifact_ids: z.array(z.string()).optional(),
  root_artifact_refs: z.array(artifactRefSchema).optional(),
  total_nodes: z.number(),
  total_edges: z.number(),
  total_size_bytes: z.number(),
  is_complete: z.boolean(),
  missing_artifact_ids: z.array(z.string()).optional(),
  corrupted_artifact_ids: z.array(z.string()).optional(),
  notes: z.array(z.string()).optional(),
  nodes: z.array(artifactLineageNodeSchema).optional(),
  edges: z.array(artifactLineageEdgeSchema).optional(),
});

const lineageCompactSummaryItemSchema = z.object({
  kind: z.enum([
    "source",
    "transform",
    "model",
    "agent",
    "result",
    "artifact",
    "dataset",
    "method",
    "unknown",
  ]),
  label: z.string(),
  id: z.string().nullable().optional(),
});

const lineageGraphNodeSchema = z.object({
  id: z.string(),
  kind: z.string(),
  label: z.string(),
  media_type: z.string().nullable().optional(),
  manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  timestamp: z.string().nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

const lineageGraphEdgeSchema = z.object({
  source_id: z.string(),
  target_id: z.string(),
  relation: z.string(),
  source_manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  target_manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

const lineageExportLinksSchema = z.object({
  openlineage: z.string(),
  prov: z.string(),
});

const verificationMetadataSchema = z.object({
  hash: z.string().nullable().optional(),
  verification_status: z.enum(["verified", "pending", "disputed", "untraced"]),
  verified_by: z.string().nullable().optional(),
  verified_at: z.string().nullable().optional(),
  verification_method: z.string().nullable().optional(),
  freshness: z.enum(["current", "stale", "unknown"]),
  dispute_status: z.enum(["none", "disputed", "under_review", "resolved"]),
  temporal_scope: temporalScopeSchema,
});

export const lineageGraphViewSchema = z
  .object({
    id: z.string(),
    status: z.enum(["verified", "pending", "disputed", "untraced"]),
    hash: z.string().nullable().optional(),
    freshness: z.enum(["current", "stale", "unknown"]),
    compact_summary: z.array(lineageCompactSummaryItemSchema).optional(),
    nodes: z.array(lineageGraphNodeSchema).optional(),
    edges: z.array(lineageGraphEdgeSchema).optional(),
    root_artifact_refs: z.array(artifactRefSchema).optional(),
    selected_artifact_ref: coreArtifactRefSchema.nullable().optional(),
    profile_binding_status: z
      .enum(["verified", "not_established"])
      .nullable()
      .optional(),
    artifact_ref_provenance: z
      .enum(["run_output_ref", "reader_materialized"])
      .nullable()
      .optional(),
    source_run_id: z.string().nullable().optional(),
    exports: lineageExportLinksSchema,
    metadata: z.record(z.string(), z.unknown()).optional(),
    trust_metadata: verificationMetadataSchema.nullable().optional(),
  })
  .superRefine((lineage, context) => {
    if (
      lineage.profile_binding_status === "verified" &&
      !lineage.selected_artifact_ref
    ) {
      context.addIssue({
        code: "custom",
        message: "verified profile binding requires selected_artifact_ref",
        path: ["selected_artifact_ref"],
      });
    }
    if (
      lineage.profile_binding_status === "not_established" &&
      lineage.trust_metadata
    ) {
      context.addIssue({
        code: "custom",
        message: "unestablished profile binding cannot carry trust metadata",
        path: ["trust_metadata"],
      });
    }
  });

const unitRefSchema = z.object({
  code: z.string(),
  system: z.string(),
  display: z.string().nullable().optional(),
});

const lineageRefSchema = z
  .object({
    id: z.string(),
    hash: z.string().nullable().optional(),
    status: z.enum(["verified", "pending", "disputed", "untraced"]),
    freshness: z.enum(["current", "stale", "unknown"]),
    summary: z.record(z.string(), z.string()).optional(),
    compact_summary: z.array(lineageCompactSummaryItemSchema).optional(),
    reason_code: z.string().nullable().optional(),
    tracking_issue: z.string().nullable().optional(),
    trust_metadata: verificationMetadataSchema.nullable().optional(),
    artifact_ref: coreArtifactRefSchema.nullable().optional(),
    artifact_ref_provenance: z
      .enum(["run_output_ref", "reader_materialized"])
      .nullable()
      .optional(),
    source_run_id: z.string().nullable().optional(),
  })
  .superRefine((lineage, context) => {
    if (lineage.artifact_ref_provenance && !lineage.artifact_ref) {
      context.addIssue({
        code: "custom",
        message: "artifact_ref_provenance requires artifact_ref",
        path: ["artifact_ref_provenance"],
      });
    }
    if (lineage.artifact_ref && !lineage.artifact_ref.manifest_profile_sha256) {
      context.addIssue({
        code: "custom",
        message: "artifact_ref must select a manifest profile",
        path: ["artifact_ref", "manifest_profile_sha256"],
      });
    }
    if (
      lineage.artifact_ref_provenance === "run_output_ref" &&
      !lineage.source_run_id
    ) {
      context.addIssue({
        code: "custom",
        message: "run_output_ref provenance requires source_run_id",
        path: ["source_run_id"],
      });
    }
  });

const quantityUncertaintySchema = z.object({
  ci_80: z.tuple([z.number(), z.number()]).nullable().optional(),
  ci_95: z.tuple([z.number(), z.number()]).nullable().optional(),
  quantiles: z.record(z.string(), z.number()).optional(),
  method: z.string().nullable().optional(),
  identifiability: z.enum(["identified", "estimated", "assumed", "unknown"]),
  disputed: z.boolean(),
}) satisfies z.ZodType<QuantityUncertainty>;

export const quantityValueSchema = z.object({
  point: z.number().nullable().optional(),
  unit: unitRefSchema,
  metric_id: z.string().nullable().optional(),
  lineage: lineageRefSchema,
  uncertainty: quantityUncertaintySchema.nullable().optional(),
  time: temporalScopeSchema,
  quantity_class: z.enum(["decision", "telemetry", "layout", "debug"]),
  label: z.string().nullable().optional(),
}) satisfies z.ZodType<QuantityValueOutput>;

const comparabilityReportSchema = z.object({
  status: z.enum(["compatible", "warning", "blocked"]),
  warnings: z.array(z.string()).optional(),
  blocked_reasons: z.array(z.string()).optional(),
});

const lineageDeltaSchema = z.object({
  source_changed: z.boolean(),
  model_changed: z.boolean(),
  hash_changed: z.boolean(),
  freshness_changed: z.boolean(),
  verification_changed: z.string().nullable().optional(),
  notes: z.array(z.string()).optional(),
});

const deltaDistributionSchema = z.object({
  quantiles: z.record(z.string(), z.number()).optional(),
  mean_shift: z.number().nullable().optional(),
  median_shift: z.number().nullable().optional(),
  ci_overlap: z.boolean().nullable().optional(),
});

const deltaQuantitySchema = z.object({
  metric_id: z.string(),
  label: z.string(),
  a: quantityValueSchema.nullable().optional(),
  b: quantityValueSchema.nullable().optional(),
  delta_absolute: quantityValueSchema.nullable().optional(),
  delta_relative: quantityValueSchema.nullable().optional(),
  delta_distribution: deltaDistributionSchema.optional(),
  significance: z.enum([
    "improved",
    "worsened",
    "mixed",
    "uncertain",
    "not_comparable",
  ]),
  dominance: z.enum(["a", "b", "none", "mixed", "unknown"]),
  decision_salience: z.number(),
  lineage_delta: lineageDeltaSchema,
});

const comparisonFrameSchema = z.object({
  run_a: z.string(),
  run_b: z.string(),
  metric_set: z.array(z.string()).optional(),
  population: z.string().nullable().optional(),
  unit_policy: z.enum(["canonical", "source", "mixed"]),
  temporal_scope: temporalScopeSchema,
  scenario_scope: z.record(z.string(), z.unknown()).optional(),
  assumption_set: z.array(z.string()).optional(),
});

const compareCandidateSchema = z.object({
  run_id: z.string(),
  label: z.string().nullable().optional(),
  relation: z
    .enum(["baseline", "previous", "selected", "recommended"])
    .default("recommended"),
  status: z.string().nullable().optional(),
  started_at: z.string().nullable().optional(),
  finished_at: z.string().nullable().optional(),
  comparability: comparabilityReportSchema,
});

const scenarioStatusSchema = z.enum(["draft", "computed", "stale", "failed"]);
const scenarioLifecycleStatusSchema = z.enum([
  "generated",
  "draft",
  "saved",
  "promoted",
]);

export const scenarioConstraintSchema = z.object({
  id: z.string(),
  label: z.string(),
  field: z.string().nullable().optional(),
  severity: z.enum(["error", "warning"]),
  operator: z.string().nullable().optional(),
  value: quantityValueSchema.nullable().optional(),
  message: z.string().nullable().optional(),
});

export const scenarioAssumptionSchema = z.object({
  id: z.string(),
  label: z.string(),
  status: z.enum([
    "operator_assumption",
    "model_assumption",
    "observed_evidence",
    "disputed",
  ]),
  lineage: lineageRefSchema,
  description: z.string().nullable().optional(),
});

export const scenarioInterventionSchema = z.object({
  field: z.string(),
  operator: z.enum(["set", "add", "multiply", "remove"]),
  value: quantityValueSchema,
  baseline_value: quantityValueSchema.nullable().optional(),
  constraint_ids: z.array(z.string()).optional(),
});

export const scenarioRefSchema = z.object({
  id: z.string(),
  status: scenarioStatusSchema,
  baseline_run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  lineage: lineageRefSchema,
  assumption_ids: z.array(z.string()),
  manifest_hash: z.string().nullable().optional(),
});

export const scenarioManifestSchema = z.object({
  id: z.string(),
  baseline_run_id: z.string(),
  status: scenarioStatusSchema,
  lifecycle_status: scenarioLifecycleStatusSchema.optional(),
  revision: z.number().optional(),
  manifest_hash: z.string().optional(),
  temporal_scope: temporalScopeSchema,
  policy_question: z.string(),
  author: z.string(),
  affected_population: z.string().nullable().optional(),
  temporal_window: temporalRangeSchema.nullable().optional(),
  model_family: z.string(),
  model_version: z.string().nullable().optional(),
  model_lineage: lineageRefSchema,
  baseline_lineage: lineageRefSchema.nullable().optional(),
  baseline_hash: z.string().nullable().optional(),
  computed_at: z.string().nullable().optional(),
  saved_at: z.string().nullable().optional(),
  promoted_at: z.string().nullable().optional(),
  validity_window: temporalRangeSchema.nullable().optional(),
  known_limitations: z.array(z.string()).optional(),
  stale_reasons: z.array(z.string()).optional(),
  interventions: z.array(scenarioInterventionSchema),
  assumptions: z.array(scenarioAssumptionSchema),
  constraints: z.array(scenarioConstraintSchema).optional(),
});

export const scenarioCapabilitySchema = z.object({
  surface: z.string(),
  supported: z.boolean(),
  reason_code: z.string().nullable().optional(),
  metric_id: z.string().nullable().optional(),
  supported_modes: z
    .array(z.enum(["actual", "actual_vs_scenario", "scenario_only"]))
    .optional(),
  limitations: z.array(z.string()).optional(),
});

export const counterfactualMetricSchema = z.object({
  metric_id: z.string(),
  label: z.string(),
  actual: quantityValueSchema,
  counterfactual: quantityValueSchema,
  delta: quantityValueSchema,
  scenario_ref: scenarioRefSchema,
  assumption_ids: z.array(z.string()),
});

const runEvidenceNeedSchema = z.object({
  need_id: z.string(),
  metric: z.string(),
  geography: z.string().nullable().optional(),
  time_start: z.string().nullable().optional(),
  time_end: z.string().nullable().optional(),
  granularity: z.string().optional(),
  quality_min: z.number().optional(),
  purpose: z.string().optional(),
  matched_plan_ids: z.array(z.string()).optional(),
  notes: z.array(z.string()).optional(),
});

const runEvidencePlanSchema = z.object({
  plan_id: z.string(),
  metric_id: z.string(),
  connector_id: z.string(),
  dataset_id: z.string(),
  profile_id: z.string().nullable().optional(),
  source_lane: z.string().optional(),
  quality_min: z.number().optional(),
  filters: z.record(z.string(), z.array(z.string())).optional(),
  date_start: z.string().nullable().optional(),
  date_end: z.string().nullable().optional(),
  granularity: z.string().nullable().optional(),
  fallback_count: z.number().optional(),
  matched_need_ids: z.array(z.string()).optional(),
  notes: z.array(z.string()).optional(),
});

const runEvidencePromotionSchema = z.object({
  promotion_id: z.string(),
  metric_id: z.string(),
  connector_id: z.string(),
  dataset_id: z.string(),
  profile_id: z.string().nullable().optional(),
  source_lane: z.string().optional(),
  confidence: z.number().optional(),
  status: z.string().optional(),
  created_at: z.string().nullable().optional(),
  signals: z.array(z.string()).optional(),
  matched_plan_id: z.string().nullable().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

const runEvidenceContextViewSchema = z.object({
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  execution_plan_ref: artifactRefSchema.nullable().optional(),
  evidence_bundle_ref: artifactRefSchema.nullable().optional(),
  data_snapshot_ref: artifactRefSchema.nullable().optional(),
  data_view_request_ref: artifactRefSchema.nullable().optional(),
  data_view_request_profile_status: dataViewRequestProfileStatusSchema,
  input_bindings_ref: artifactRefSchema.nullable().optional(),
  fabric_retrieval_trace_ref: artifactRefSchema.nullable().optional(),
  materialization_refs: z.record(z.string(), artifactRefSchema).optional(),
  production_data_evidence_context: z
    .record(z.string(), z.unknown())
    .optional(),
  related_artifacts: z.array(artifactRefSchema).optional(),
  data_needs: z.array(runEvidenceNeedSchema).optional(),
  fetch_plans: z.array(runEvidencePlanSchema).optional(),
  promotion_candidates: z.array(runEvidencePromotionSchema).optional(),
  warnings: z.array(z.string()).optional(),
});

const legalQueryGenerationIntentSchema = z
  .object({
    basis_kind: z.enum([
      "legal_lex_entities_embedding",
      "legal_lex_facts_embedding",
      "legal_lex_provisions_embedding",
    ]),
    generation_id: z.string(),
    inventory_json: z.string(),
  })
  .strict();

const lexSearchResultItemSchema = z.object({
  fact_id: z.string(),
  subject_name: z.string(),
  predicate: z.string(),
  object_name: z.string(),
  fact_text: z.string(),
  confidence: z.number(),
  norm_type: z.string(),
  action_canon: z.string(),
  norm_type_canon: z.string(),
  condition_text_uk: z.string(),
  exception_text_uk: z.string(),
  procedure_text_uk: z.string(),
  thresholds_json: z.string(),
  source_quote_uk: z.string(),
  trust_tier: z.enum(["search_candidate", "grounded_fact", "normative_fact"]),
  grounding_status: z.enum([
    "exact_quote",
    "quote_without_offsets",
    "offsets_without_quote",
    "missing_quote",
  ]),
  canonical_status: z.enum(["canonicalized", "partially_canonicalized", "raw"]),
  reference_resolution_status: z.enum([
    "resolved",
    "partial",
    "unresolved",
    "not_applicable",
  ]),
  structure_quality: z.string(),
  constraint_type_canon: z.string(),
  legal_unit_subtype: z.string(),
  route_class: z.string(),
  empty_spo_retry_eligible: z.boolean(),
  audit_miss_prone: z.boolean(),
  reference_bearing: z.boolean(),
  threshold_bearing: z.boolean(),
  fused_confidence: z.number().nullable().optional(),
  confidence_breakdown_json: z.string(),
  consistency_score: z.number().nullable().optional(),
  hallucination_flags_json: z.string(),
  quality_band: z.string(),
  doc_id: z.string(),
  doc_family_id: z.string(),
  version_id: z.string(),
  jurisdiction: z.string(),
  top_domain: z.string(),
  effective_from: z.string(),
  effective_to: z.string(),
  temporal_state: z.string(),
  temporal_resolution_status: z.string(),
  temporal_source_scope: z.string(),
  temporal_source_kind: z.string(),
  temporal_confidence: z.number().nullable().optional(),
  temporal_provenance_json: z.string(),
  doc_name: z.string(),
  doc_reestr_code: z.string(),
  provision_anchor: z.string(),
  provision_citation: z.string(),
  similarity: z.number(),
});

const artifactManifestViewSchema = z.object({
  artifact_id: z.string(),
  manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  kind: z.string(),
  media_type: z.string(),
  byte_size: z.number(),
  created_at: z.string(),
  schema_name: z.string().nullable().optional(),
  schema_version: z.string().nullable().optional(),
  producer_component: z.string().nullable().optional(),
  producer_version: z.string().nullable().optional(),
  inputs: z
    .array(
      z.object({
        artifact_id: z.string(),
        manifest_profile_sha256: z
          .string()
          .regex(/^sha256:[0-9a-f]{64}$/)
          .nullable()
          .optional(),
        role: z.string(),
      }),
    )
    .optional(),
  integrity_sha256: z.string(),
});

const decisionPacketOutlineEntrySchema = z.object({
  section_id: z.string(),
  title: z.string(),
  section_type: z.string().nullable().optional(),
});

const decisionPacketEffectSizeSchema = z.object({
  point: z.number().nullable().optional(),
  ci_80: z.tuple([z.number(), z.number()]).nullable().optional(),
  ci_95: z.tuple([z.number(), z.number()]).nullable().optional(),
  quantiles: z.record(z.string(), z.number()).nullable().optional(),
  identifiability: z
    .enum(["identified", "estimated", "assumed"])
    .nullable()
    .optional(),
  disputed: z.boolean().nullable().optional(),
  method: z.string().nullable().optional(),
});

const decisionPacketMetricSignificanceSchema = z.object({
  baseline_model_id: z.string().nullable().optional(),
  candidate_model_id: z.string().nullable().optional(),
  metric_direction: z.string().nullable().optional(),
  baseline_value: z.number().nullable().optional(),
  candidate_value: z.number().nullable().optional(),
  delta_value: z.number().nullable().optional(),
  test_id: z.string().nullable().optional(),
  test_label: z.string().nullable().optional(),
  p_value: z.number().nullable().optional(),
  p_adj: z.number().nullable().optional(),
  alpha: z.number().nullable().optional(),
  significant: z.boolean().nullable().optional(),
  effect_size: decisionPacketEffectSizeSchema.nullable().optional(),
  assumption_warnings: z.array(z.string()).optional(),
  calibration_warnings: z.array(z.string()).optional(),
});

const decisionPacketMetricComparisonRowSchema = z.object({
  metric_id: z.string(),
  metric_direction: z.string().nullable().optional(),
  baseline_model_id: z.string().nullable().optional(),
  candidate_model_id: z.string().nullable().optional(),
  baseline_value: z.number().nullable().optional(),
  candidate_value: z.number().nullable().optional(),
  delta_value: z.number().nullable().optional(),
  family_id: z.string().nullable().optional(),
  family_scope: z.string().nullable().optional(),
  sample_size_effective: z.number().int().nullable().optional(),
  resampling_method: z.string().nullable().optional(),
  test_id: z.string().nullable().optional(),
  test_label: z.string().nullable().optional(),
  statistic: z.number().nullable().optional(),
  effect_size: decisionPacketEffectSizeSchema.nullable().optional(),
  p_value: z.number().nullable().optional(),
  p_adj: z.number().nullable().optional(),
  alpha: z.number().nullable().optional(),
  significant: z.boolean().nullable().optional(),
  assumption_warnings: z.array(z.string()).optional(),
  calibration_warnings: z.array(z.string()).optional(),
});

const decisionPacketAuthoredBlockSchema = z.object({
  id: z.string().nullable().optional(),
  content: z.string(),
  author: z
    .enum(["citation", "human", "drafter", "formalizer", "critic"])
    .nullable()
    .optional(),
  author_agent_version: z.string().nullable().optional(),
  sources: z.array(z.object({ kind: z.string(), ref: z.string() })).optional(),
  timestamp: z.string().nullable().optional(),
  confidence: z.number().nullable().optional(),
  reviewed_by_human: z.boolean().nullable().optional(),
});

const decisionPacketPreviewSchema = z
  .object({
    document_outline: z.array(decisionPacketOutlineEntrySchema).optional(),
    metric_significance_by_metric: z
      .record(z.string(), decisionPacketMetricSignificanceSchema)
      .optional(),
    metric_validation_comparison_rows: z
      .array(decisionPacketMetricComparisonRowSchema)
      .optional(),
    blocks: z.array(decisionPacketAuthoredBlockSchema).optional(),
    narrative_blocks: z.array(decisionPacketAuthoredBlockSchema).optional(),
    evidence_summary_blocks: z
      .array(decisionPacketAuthoredBlockSchema)
      .optional(),
  })
  .loose();

const canonReadStatusSchema = z.enum([
  "not_applicable",
  "not_evaluated",
  "declared_bytes_conformant",
  "profile_absent_unqualified_candidate",
  "declared_unknown_candidate",
]);

// Older v1 servers omit this additive field; absence conveys no qualification.
const optionalCanonReadStatusSchema = canonReadStatusSchema
  .optional()
  .transform((status) => status ?? "not_evaluated");

const predictiveCoverageProhibitedUses = [
  "promotion",
  "publication",
  "policy_selection",
  "causal_effect_claim",
] as const;
const predictiveCoverageMayNotUseSchema = z
  .array(z.enum(predictiveCoverageProhibitedUses))
  .refine(
    (uses) =>
      uses.length === predictiveCoverageProhibitedUses.length &&
      new Set(uses).size === predictiveCoverageProhibitedUses.length &&
      predictiveCoverageProhibitedUses.every((use) => uses.includes(use)),
    "predictive coverage diagnostic must retain every prohibited use",
  );

const predictiveCoverageScenarioPreviewSchema = z.object({
  scenario_id: z.string(),
  metric_name: z.string(),
  interval_requested_count: z.number().int().nonnegative(),
  interval_available_count: z.number().int().nonnegative(),
  interval_evaluated_count: z.number().int().nonnegative(),
  interval_hit_count: z.number().int().nonnegative(),
  nominal_confidence_level: z.number().gt(0).lt(1).nullable().optional(),
  interval_type: z.string().nullable().optional(),
  observed_hit_rate: z.number().min(0).max(1).nullable().optional(),
});

const predictiveCoverageDiagnosticPreviewSchema = z.object({
  source_artifact_id: z.string(),
  source_manifest_profile_sha256: z.string(),
  source_schema_version: z.literal("1.0"),
  metric: z.literal("predictive_interval_coverage"),
  measurement_status: z.enum(["measured", "not_measured", "invalid_source"]),
  reason_code: z.enum([
    "none",
    "no_evaluated_intervals",
    "predictive_scope_not_established",
    "unsupported_report_scope",
    "malformed_report_shape",
    "malformed_interval_counts",
    "stored_hit_rate_mismatch",
  ]),
  assessment: z.literal("limited"),
  source_materialization: z.literal("reader_materialized"),
  canon_read_status: optionalCanonReadStatusSchema,
  producer_attestation_status: z.literal("not_established"),
  s10_metric_mapping_status: z.literal("not_established"),
  s10_threshold_status: z.literal("not_established"),
  issuer_status: z.literal("not_established"),
  effective_time_status: z.literal("not_established"),
  counterfactual_credibility_status: z.literal("not_established"),
  causal_effect_status: z.literal("not_established"),
  may_not_use_for: predictiveCoverageMayNotUseSchema,
  scenarios: z.array(predictiveCoverageScenarioPreviewSchema),
});

const artifactContentPreviewSchema = z.object({
  artifact_id: z.string(),
  manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  kind: z.string(),
  media_type: z.string(),
  mode: z.enum(["json", "text", "binary"]),
  canon_read_status: optionalCanonReadStatusSchema,
  size_bytes: z.number().int().nonnegative(),
  max_bytes: z.number().int().positive(),
  truncated: z.boolean().default(false),
  preview: z.unknown().optional(),
  decision_packet_preview: decisionPacketPreviewSchema.nullable().optional(),
  predictive_coverage_diagnostic: predictiveCoverageDiagnosticPreviewSchema
    .nullable()
    .optional(),
});

const artifactSchemaViewSchema = z.object({
  artifact_id: z.string(),
  manifest_profile_sha256: z
    .string()
    .regex(/^sha256:[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  kind: z.string(),
  media_type: z.string(),
  canon_read_status: optionalCanonReadStatusSchema,
  schema_name: z.string().nullable().optional(),
  schema_version: z.string().nullable().optional(),
  top_level_keys: z.array(z.string()).default([]),
});

const artifactManifestJoinViewSchema = artifactManifestViewSchema.pick({
  artifact_id: true,
  manifest_profile_sha256: true,
  kind: true,
  media_type: true,
  schema_name: true,
  schema_version: true,
});

/** Validate that inspector previews describe the exact selected manifest. */
export const artifactInspectorIntakeSchema = z
  .object({
    manifest: artifactManifestJoinViewSchema,
    content: artifactContentPreviewSchema.optional(),
    schema: artifactSchemaViewSchema.optional(),
  })
  .strict()
  .superRefine((intake, context) => {
    const { manifest, content, schema } = intake;
    if (!content && !schema) {
      context.addIssue({
        code: "custom",
        path: [],
        message: "artifact_inspector_intake_preview_required",
      });
      return;
    }

    for (const [viewName, view] of [
      ["content", content],
      ["schema", schema],
    ] as const) {
      if (!view) continue;
      if (view.artifact_id !== manifest.artifact_id) {
        context.addIssue({
          code: "custom",
          path: [viewName, "artifact_id"],
          message: "artifact_inspector_intake_artifact_id_mismatch",
        });
      }
      if (
        (view.manifest_profile_sha256 ?? null) !==
        (manifest.manifest_profile_sha256 ?? null)
      ) {
        context.addIssue({
          code: "custom",
          path: [viewName, "manifest_profile_sha256"],
          message: "artifact_inspector_intake_profile_mismatch",
        });
      }
      if (view.kind !== manifest.kind) {
        context.addIssue({
          code: "custom",
          path: [viewName, "kind"],
          message: "artifact_inspector_intake_kind_mismatch",
        });
      }
      if (view.media_type !== manifest.media_type) {
        context.addIssue({
          code: "custom",
          path: [viewName, "media_type"],
          message: "artifact_inspector_intake_media_type_mismatch",
        });
      }
    }

    if (schema) {
      if ((schema.schema_name ?? null) !== (manifest.schema_name ?? null)) {
        context.addIssue({
          code: "custom",
          path: ["schema", "schema_name"],
          message: "artifact_inspector_intake_schema_name_mismatch",
        });
      }
      if (
        (schema.schema_version ?? null) !== (manifest.schema_version ?? null)
      ) {
        context.addIssue({
          code: "custom",
          path: ["schema", "schema_version"],
          message: "artifact_inspector_intake_schema_version_mismatch",
        });
      }
    }

    if (
      content &&
      schema &&
      content.canon_read_status !== schema.canon_read_status
    ) {
      context.addIssue({
        code: "custom",
        path: ["schema", "canon_read_status"],
        message: "artifact_inspector_intake_status_mismatch",
      });
    }

    const diagnostic = content?.predictive_coverage_diagnostic;
    if (!content || !diagnostic) return;

    if (diagnostic.source_artifact_id !== content.artifact_id) {
      context.addIssue({
        code: "custom",
        path: [
          "content",
          "predictive_coverage_diagnostic",
          "source_artifact_id",
        ],
        message: "artifact_inspector_intake_diagnostic_artifact_id_mismatch",
      });
    }
    if (
      diagnostic.source_manifest_profile_sha256 !==
      (content.manifest_profile_sha256 ?? null)
    ) {
      context.addIssue({
        code: "custom",
        path: [
          "content",
          "predictive_coverage_diagnostic",
          "source_manifest_profile_sha256",
        ],
        message: "artifact_inspector_intake_diagnostic_profile_mismatch",
      });
    }
    if (diagnostic.canon_read_status !== content.canon_read_status) {
      context.addIssue({
        code: "custom",
        path: [
          "content",
          "predictive_coverage_diagnostic",
          "canon_read_status",
        ],
        message: "artifact_inspector_intake_diagnostic_status_mismatch",
      });
    }
    if (
      content.kind !== "ir.backtest_report" ||
      manifest.kind !== "ir.backtest_report"
    ) {
      context.addIssue({
        code: "custom",
        path: ["content", "kind"],
        message: "artifact_inspector_intake_diagnostic_kind_mismatch",
      });
    }
    if (manifest.schema_name !== "ir.backtest_report") {
      context.addIssue({
        code: "custom",
        path: ["manifest", "schema_name"],
        message: "artifact_inspector_intake_diagnostic_schema_name_mismatch",
      });
    }
    if (
      (manifest.schema_version ?? null) !== diagnostic.source_schema_version
    ) {
      context.addIssue({
        code: "custom",
        path: ["manifest", "schema_version"],
        message: "artifact_inspector_intake_diagnostic_schema_version_mismatch",
      });
    }
    if (content.mode !== "json") {
      context.addIssue({
        code: "custom",
        path: ["content", "mode"],
        message: "artifact_inspector_intake_diagnostic_mode_mismatch",
      });
    }
    if (
      content.media_type !== "application/json" ||
      manifest.media_type !== "application/json"
    ) {
      context.addIssue({
        code: "custom",
        path: ["content", "media_type"],
        message: "artifact_inspector_intake_diagnostic_media_type_mismatch",
      });
    }
  });

const bureaucraticGenreSchema = z.enum([
  "postanova_kmu",
  "zakonoproekt",
  "expert_vysnovok",
  "analitichna_zapyska",
]);

const bureaucraticTemplateRefSchema = z.object({
  id: z.string(),
  version: z.string(),
  genre: bureaucraticGenreSchema,
  jurisdiction: z.string(),
  locale: z.string(),
  legal_review_status: z.enum([
    "pending_external_review",
    "approved",
    "rejected",
  ]),
});

const bureaucraticAuthorshipSchema = z.object({
  author: z.string(),
  author_role: z.string(),
  agent_version: z.string().nullable().optional(),
  timestamp: z.string().nullable().optional(),
  reviewed_by_human: z.boolean(),
});

const bureaucraticBlockSchema: z.ZodType = z.lazy(() =>
  z.object({
    id: z.string(),
    kind: z.enum([
      "header",
      "requisites",
      "preamble",
      "legal_basis",
      "section",
      "article",
      "clause",
      "subclause",
      "paragraph",
      "list",
      "table",
      "quantity",
      "annex",
      "signature",
      "appendix",
    ]),
    title: z.string().nullable().optional(),
    text: z.string().nullable().optional(),
    level: z.number(),
    number: z.string().nullable().optional(),
    items: z.array(z.string()).optional(),
    quantity: quantityValueSchema.nullable().optional(),
    epistemic_origin: z.enum([
      "evidence_filled",
      "model_generated",
      "operator_filled",
      "imported",
    ]),
    authorship: bureaucraticAuthorshipSchema,
    provenance: z.array(lineageCompactSummaryItemSchema).optional(),
    raw_source_refs: z.array(z.string()).optional(),
    children: z.array(bureaucraticBlockSchema).optional(),
    metadata: z.record(z.string(), z.unknown()).optional(),
  }),
);

export const bureaucraticDocumentSchema = z.object({
  id: z.string(),
  packet_id: z.string(),
  genre: bureaucraticGenreSchema,
  jurisdiction: z.string(),
  template: bureaucraticTemplateRefSchema,
  status: z.enum(["draft", "signed_external", "archived"]),
  title: z.string(),
  language: z.string(),
  watermark: z.string(),
  render_timestamp: z.string(),
  packet_hash: z.string(),
  temporal_scope: temporalScopeSchema,
  trust_view: z.boolean(),
  blocks: z.array(bureaucraticBlockSchema),
  annexes: z.array(bureaucraticBlockSchema),
  epistemic_summary: z.object({
    evidence_filled: z.number(),
    model_generated: z.number(),
    operator_filled: z.number(),
    imported: z.number(),
  }),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

type CapabilityFeaturePayload = components["schemas"]["CapabilityFeatureInfo"];
export type CapabilityManifestPayload =
  components["schemas"]["CapabilityManifestResponse"];

const capabilityFeatureSchema = z.object({
  key: z.string(),
  label: z.string(),
  description: z.string(),
  category: z.string(),
  enabled: z.boolean().default(true),
  stage: z.enum(["active", "planned", "deferred"]).default("active"),
});

const capabilityExecutionPolicySchema = z
  .object({
    auto_materialization: z.boolean(),
    multimodel_nl: z.boolean(),
    producer_ref: z.string().min(1),
    required_preflight: z.boolean(),
  })
  .strict();

const authMeSchemaInternal = z.object({
  meta: apiMetaSchema,
  user_id: z.string(),
  display_name: z.string(),
  tenant_id: z.string(),
  principal_type: z.enum(["anonymous", "service", "user"]).default("user"),
  cell_id: z.string().nullable().optional(),
  roles: z.array(z.string()).default([]),
  permissions: z.array(z.string()).default([]),
  mfa_verified: z.boolean().default(false),
  feature_overrides: z.record(z.string(), z.boolean()).default({}),
});

export const capabilityManifestSchema = z.object({
  meta: apiMetaSchema,
  runtime_api_version: z.string().default("1.0.0"),
  shell_flavor: z.string().default("atlas"),
  default_execution_profile: z
    .enum(["dev", "research", "governed", "production"])
    .default("dev"),
  default_locale: z.enum(["en", "uk"]).default("en"),
  supported_execution_profiles: z
    .array(z.enum(["dev", "research", "governed", "production"]))
    .default(["dev", "research", "governed", "production"]),
  supported_locales: z.array(z.enum(["en", "uk"])).default(["en", "uk"]),
  state_store_backend: z.string().default("sqlite"),
  worker_backend: z.string().default("embedded"),
  security_posture: z.record(z.string(), z.unknown()).default({}),
  fallback_rules: z
    .looseObject({
      execution_policy: capabilityExecutionPolicySchema.optional(),
    })
    .default({}),
  workspaces: z.array(z.string()).default([]),
  features: z.array(capabilityFeatureSchema).default([]),
  constraints: z.record(z.string(), z.unknown()).default({}),
});

const capabilityTimeSchema = z
  .object({
    freshness: z.enum(["current", "stale", "unknown"]),
    observed_at: z.string(),
    valid_from: z.string(),
    valid_until: z.string().nullable(),
  })
  .strict();

const capabilityDiscoveryPostureSchema = z
  .object({
    freshness_ref: z.string().nullable().optional(),
    producer_ref: z.string(),
    provenance_refs: z.array(z.string()),
    reason_codes: z.array(z.string()),
    snapshot_ref: z.string().nullable().optional(),
    state: z.enum([
      "discoverable",
      "no_match",
      "producer_missing",
      "producer_unavailable",
      "index_unavailable",
      "index_stale",
      "recall_unmeasured",
      "budget_cutoff",
      "incomplete",
    ]),
    time: capabilityTimeSchema,
  })
  .strict();

const capabilityExecutionPostureSchema = z
  .object({
    conformance_ref: z.string().nullable().optional(),
    operation_ref: z.string().nullable().optional(),
    policy_ref: z.string().nullable().optional(),
    producer_ref: z.string(),
    provenance_refs: z.array(z.string()),
    reason_codes: z.array(z.string()),
    state: z.enum([
      "executable",
      "not_executable",
      "operation_missing",
      "conformance_failed",
      "policy_disabled",
      "producer_missing",
      "execution_blocked",
      "not_established",
    ]),
    time: capabilityTimeSchema,
  })
  .strict();

const capabilityAuthorityPostureSchema = z
  .object({
    authority_purpose: z.string(),
    binding_ref: z.string().nullable().optional(),
    currentness_ref: z.string().nullable().optional(),
    producer_ref: z.string(),
    provenance_refs: z.array(z.string()),
    reason_codes: z.array(z.string()),
    state: z.enum([
      "admitted_authority",
      "candidate_only",
      "producer_missing",
      "bridge_missing",
      "artifact_missing",
      "invalid_source",
      "revalidation_required",
      "authority_blocked",
      "not_established",
    ]),
    time: capabilityTimeSchema,
  })
  .strict();

const searchCandidateSchema = z
  .object({
    authority_boundary: z.record(z.string(), z.unknown()).optional(),
    candidate_ref: z.string(),
    evidence_refs: z.array(z.string()),
    limitation_refs: z.array(z.string()),
    match_mode: z.enum([
      "exact",
      "alias",
      "lexical",
      "semantic",
      "relational",
      "derived",
    ]),
    may_not_use_for: z.array(z.string()),
    score: z.number(),
    source_layer: z.string(),
  })
  .strict();

const searchFrontierSchema = z
  .object({
    actual_cutoff: z.number().nullable().optional(),
    candidates: z.array(searchCandidateSchema),
    completeness_status: z.enum([
      "complete",
      "complete_no_match",
      "recall_unmeasured",
      "budget_cutoff",
      "index_stale",
      "producer_unavailable",
      "producer_missing",
    ]),
    configured_store_path: z.string().nullable().optional(),
    corpus_kind: z.enum([
      "canonical",
      "bounded_surrogate",
      "temp_store",
      "fixture",
    ]),
    corpus_path: z.string(),
    corpus_ref: z.string(),
    corpus_snapshot_hash: z.string(),
    evaluated_count: z.number(),
    incompleteness: z.record(z.string(), z.unknown()).optional(),
    incompleteness_reasons: z.array(z.string()),
    index_freshness: z.record(z.string(), z.unknown()).optional(),
    index_version_refs: z.array(z.string()),
    indexes_used: z.array(z.string()),
    no_hit_frontier: z.array(z.string()),
    query_expansion_traces: z.array(z.record(z.string(), z.unknown())),
    query_plan: z.record(z.string(), z.unknown()).optional(),
    rejected_candidates: z.array(searchCandidateSchema),
    replay_command: z.string(),
    replay_expected_output_hash: z.string(),
    replay_key: z.string(),
    request_ref: z.string(),
    requested_count: z.number(),
    returned_count: z.number(),
    schema_version: z.literal("policyos.core.contracts.search.v1"),
  })
  .strict();

const capabilityDiscoveryItemSchema = z
  .object({
    authoritative_for: z.array(z.string()),
    authority_purpose: z.string(),
    authority_result: capabilityAuthorityPostureSchema,
    capability_ref: z.string(),
    content_digest: z.string(),
    description: z.string(),
    discovery_result: capabilityDiscoveryPostureSchema,
    execution_result: capabilityExecutionPostureSchema,
    label: z.string(),
    may_not_use_for: z.array(z.string()),
    provenance_refs: z.array(z.string()),
    resource_kind: z.enum([
      "method",
      "dataset",
      "source",
      "legal_norm",
      "case",
      "agent",
    ]),
    rule_version: z.string(),
    schema_version: z.literal("policyos.capability_discovery.v1"),
    time: capabilityTimeSchema,
  })
  .strict();

const capabilityDiscoveryRequestSchema = z
  .object({
    audience: z.enum(["REVIEWER", "EXPERT", "MACHINE"]),
    resource_kinds: z.array(
      z.enum(["method", "dataset", "source", "legal_norm", "case", "agent"]),
    ),
    search: z
      .object({
        allowed_modes: z.array(
          z.enum([
            "exact",
            "alias",
            "lexical",
            "semantic",
            "relational",
            "derived",
          ]),
        ),
        authority_purpose: z.string(),
        budget: z.record(z.string(), z.unknown()).optional(),
        construct_refs: z.array(z.string()),
        intent: z.string(),
        query_text: z.string(),
        request_id: z.string(),
        required_layers: z.array(z.string()),
        rule_version: z.string(),
        schema_version: z.literal("policyos.core.contracts.search.v1"),
      })
      .strict(),
  })
  .strict();

export type CapabilityDiscoveryPayload =
  components["schemas"]["CapabilityDiscoveryResponse"];

export const capabilityDiscoveryResponseSchema: z.ZodType<CapabilityDiscoveryPayload> =
  z
    .object({
      audience: z.enum(["REVIEWER", "EXPERT", "MACHINE"]),
      authority_purpose: z.string(),
      frontier: searchFrontierSchema,
      meta: apiMetaSchema,
      provenance_refs: z.array(z.string()),
      request: capabilityDiscoveryRequestSchema,
      request_digest: z.string(),
      results: z.array(capabilityDiscoveryItemSchema),
      rule_version: z.string(),
      schema_version: z.literal("policyos.capability_discovery.v1"),
      time: capabilityTimeSchema,
    })
    .strict();

export const authMeSchema = authMeSchemaInternal;

export const healthSchema = z
  .object({
    meta: apiMetaSchema.nullish(),
    status: z.string().optional(),
    service: z.string().optional(),
    ts: z.string().optional(),
  })
  .catchall(
    z.union([
      z.string(),
      z.number(),
      z.boolean(),
      z.null(),
      z.array(z.unknown()),
      z.record(z.string(), z.unknown()),
    ]),
  );

export const runsListSchema = z.object({
  meta: apiMetaSchema,
  page: cursorPageSchema,
  runs: z.array(runSummarySchema).optional(),
});

export const runDetailsSchema = z
  .object({
    meta: apiMetaSchema,
    temporal_scope: temporalScopeSchema,
    run: runDetailsSchemaInner,
  })
  .strict();

export const runTimelineSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  timeline: runTimelineViewSchema,
});

export const runNodesSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  nodes: z.array(runNodeRecordSchema).optional(),
  notes: z.array(z.string()).optional(),
});

export const runLineageSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  lineage: artifactLineageViewSchema,
});

export const runQuantitiesSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  temporal_scope: temporalScopeSchema,
  quantities: z.array(quantityValueSchema).optional(),
  coverage: z
    .object({
      total: z.number(),
      decision: z.number(),
      telemetry: z.number(),
      layout: z.number(),
      debug: z.number(),
      traced: z.number(),
      untraced: z.number(),
    })
    .optional(),
  entries: z.array(z.record(z.string(), z.unknown())).optional(),
});

const fabricQualityRefSchema = z.object({
  status: z.enum(["passed", "warning", "failed", "unknown_quality"]),
  score: z.number().nullable().optional(),
  report_ref: z.string().nullable().optional(),
  reason_code: z.string().nullable().optional(),
  quality_surface: z.string().nullable().optional(),
  remediation_link: z.string().nullable().optional(),
});

const fabricAccessRefSchema = z.object({
  classification: z.string(),
  pii_tier: z.string(),
  tenant_scope: z.string(),
  redaction: z.enum(["none", "masked", "redacted", "aggregate_only", "denied"]),
  policy_ref: z.string().nullable().optional(),
});

const fabricLineageRefSchema = z
  .object({
    id: z.string(),
    status: z.enum(["verified", "pending", "disputed", "untraced"]),
    hash: z.string().nullable().optional(),
    compact_summary_ref: z.string().nullable().optional(),
    full_graph_ref: z.string().nullable().optional(),
    raw_evidence_refs: z.array(z.string()).optional(),
    export_links: z.record(z.string(), z.string()).optional(),
    reason_code: z.string().nullable().optional(),
    owner: z.string().nullable().optional(),
    tracking_issue: z.string().nullable().optional(),
    artifact_ref: coreArtifactRefSchema.nullable().optional(),
    artifact_ref_provenance: z
      .enum(["run_output_ref", "reader_materialized"])
      .nullable()
      .optional(),
    source_run_id: z.string().nullable().optional(),
  })
  .superRefine((lineage, context) => {
    if (lineage.artifact_ref_provenance && !lineage.artifact_ref) {
      context.addIssue({
        code: "custom",
        message: "artifact_ref_provenance requires artifact_ref",
        path: ["artifact_ref_provenance"],
      });
    }
    if (lineage.artifact_ref && !lineage.artifact_ref.manifest_profile_sha256) {
      context.addIssue({
        code: "custom",
        message: "artifact_ref must select a manifest profile",
        path: ["artifact_ref", "manifest_profile_sha256"],
      });
    }
    if (
      lineage.artifact_ref_provenance === "run_output_ref" &&
      !lineage.source_run_id
    ) {
      context.addIssue({
        code: "custom",
        message: "run_output_ref provenance requires source_run_id",
        path: ["source_run_id"],
      });
    }
  });

const fabricReplayRefSchema = z.object({
  status: z.enum(["replayable", "non_replayable", "unknown"]),
  manifest_ref: z.string().nullable().optional(),
  reason_code: z.string().nullable().optional(),
  source_reason: z.string().nullable().optional(),
  retention_alternative: z.string().nullable().optional(),
});

const fabricTypedGapSchema = z.object({
  status: z.enum([
    "untraced",
    "unknown_quality",
    "restricted",
    "non_replayable",
    "unsupported_temporal_scope",
  ]),
  reason_code: z.string().nullable().optional(),
  owner: z.string().nullable().optional(),
  quality_surface: z.string().nullable().optional(),
  remediation_link: z.string().nullable().optional(),
  access_policy: z.string().nullable().optional(),
  redaction_behavior: z.string().nullable().optional(),
  source_reason: z.string().nullable().optional(),
  retention_alternative: z.string().nullable().optional(),
  capability_endpoint: z.string().nullable().optional(),
});

const fabricDecisionDataSchema = z.object({
  id: z.string(),
  kind: z.enum(["quantity", "authored_text", "fact", "event", "claim"]),
  value: z.record(z.string(), z.unknown()),
  source_contract: z.object({
    id: z.string(),
    version: z.string(),
  }),
  quality: fabricQualityRefSchema,
  lineage: fabricLineageRefSchema,
  access: fabricAccessRefSchema,
  time: temporalRefSchema,
  replay: fabricReplayRefSchema,
  gaps: z.array(fabricTypedGapSchema).optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export const runFabricDecisionDataSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  source_kind: z.literal("core_run"),
  temporal_scope: temporalScopeSchema,
  decision_data: z.array(fabricDecisionDataSchema).optional(),
  coverage: z
    .object({
      total: z.number(),
      decision: z.number(),
      telemetry: z.number(),
      layout: z.number(),
      debug: z.number(),
      traced: z.number(),
      untraced: z.number(),
      naked_decision_values: z.number(),
      transitional_waivers: z.number(),
    })
    .optional(),
});

export const fabricSourceScorecardsSchema = z.object({
  meta: apiMetaSchema,
  schema_version: z.string(),
  generated_at: z.string().nullable().optional(),
  count: z.number(),
  scorecards: z.record(z.string(), z.record(z.string(), z.unknown())),
});

export const fabricQualityBatchSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  quality_refs: z.record(z.string(), fabricQualityRefSchema),
  coverage: z.record(z.string(), z.unknown()).optional(),
});

export const fabricTrustBatchSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  trust_refs: z.record(
    z.string(),
    z.object({
      quality: fabricQualityRefSchema,
      access: fabricAccessRefSchema,
      lineage: fabricLineageRefSchema,
      replay: fabricReplayRefSchema,
      time: temporalScopeSchema,
      gaps: z.array(fabricTypedGapSchema).optional(),
    }),
  ),
  coverage: z.record(z.string(), z.unknown()).optional(),
});

export const fabricReplaySchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  replay_refs: z.record(z.string(), fabricReplayRefSchema),
  status_counts: z.record(z.string(), z.number()),
  coverage: z.record(z.string(), z.unknown()).optional(),
});

const fabricImpactRecordSchema = z.object({
  subject_id: z.string(),
  subject_kind: z.enum(["lineage", "source_contract", "run", "decision_data"]),
  lineage_status: z.enum(["verified", "pending", "disputed", "untraced"]),
  quality_status: z.string().nullable().optional(),
  replay_status: z.string().nullable().optional(),
  downstream_refs: z.array(z.string()).optional(),
  upstream_refs: z.array(z.string()).optional(),
  affected_decision_data_ids: z.array(z.string()).optional(),
  source_contract_ids: z.array(z.string()).optional(),
  evidence_refs: z.array(z.string()).optional(),
  notes: z.array(z.string()).optional(),
});

export const fabricImpactAnalysisSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  impacts: z.array(fabricImpactRecordSchema).optional(),
  summary: z.record(z.string(), z.unknown()).optional(),
});

export const compareRunsSchema = z.object({
  meta: apiMetaSchema,
  status: z.enum(["computed", "client_computable"]),
  temporal_scope: temporalScopeSchema,
  comparison_frame: comparisonFrameSchema,
  comparability: comparabilityReportSchema,
  deltas: z.array(deltaQuantitySchema).optional(),
});

export const compareCandidatesSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  candidates: z.array(compareCandidateSchema).optional(),
});

export const temporalCapabilitiesSchema = z.object({
  meta: apiMetaSchema,
  capabilities: temporalCapabilitiesViewSchema,
});

export const scenarioListSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  scenarios: z.array(scenarioManifestSchema).optional(),
});

export const scenarioManifestResponseSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  scenario: scenarioManifestSchema,
});

export const scenarioCapabilitiesSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string().nullable().optional(),
  scenario_id: z.string().nullable().optional(),
  temporal_scope: temporalScopeSchema,
  capabilities: z.array(scenarioCapabilitySchema).optional(),
});

export const counterfactualMetricsSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  temporal_scope: temporalScopeSchema,
  scenario: scenarioManifestSchema,
  metrics: z.record(z.string(), counterfactualMetricSchema).optional(),
});

export const runEvidenceContextSchema = z.object({
  meta: apiMetaSchema,
  context: runEvidenceContextViewSchema,
});

export const governanceDebugSchema = z.object({
  meta: apiMetaSchema,
  debug: governanceDebugViewSchema,
});

export const promotionCandidatesSchema = z.object({
  meta: apiMetaSchema,
  candidates: z.array(runEvidencePromotionSchema).default([]),
});

export const promotionDecisionResponseSchema = z.object({
  meta: apiMetaSchema,
  promotion_id: z.string(),
  status: z.enum(["approved", "rejected"]),
  message: z.string(),
  binding_updated: z.boolean().default(false),
});

export const lexSearchRequestSchema = z
  .object({
    query: z.string().min(1).max(2000),
    top_k: z.number().int().min(1).max(100).default(20),
    output_dir: z.string().min(1),
    query_generation_intent: z
      .array(legalQueryGenerationIntentSchema)
      .nullable()
      .optional(),
  })
  .strict();

const legalRelationRefusalSchema = z
  .object({
    code: z.literal("legal_source_relation_verification_not_established"),
    status: z.literal("verification_missing"),
  })
  .strict();

export const lexSearchResponseSchema = z.object({
  meta: apiMetaSchema,
  query: z.string(),
  results: z.array(lexSearchResultItemSchema).default([]),
  total: z.number().default(0),
  search_mode: z.enum(["text", "vector"]),
  vector_refusal_code: z.string().nullable(),
  legal_relation_refusal: legalRelationRefusalSchema.nullable().optional(),
});

export const lexSearchProfileResponseSchema = z.discriminatedUnion("status", [
  z
    .object({
      meta: apiMetaSchema,
      status: z.literal("available"),
      output_dir: z.string().min(1),
      query_generation_intent: z.array(legalQueryGenerationIntentSchema).min(1),
    })
    .strict(),
  z
    .object({
      meta: apiMetaSchema,
      status: z.literal("refused"),
      output_dir: z.string().min(1),
      refusal_code: z.enum([
        "query_profile_generation_unavailable",
        "query_profile_malformed",
        "selected_generation_unavailable",
      ]),
    })
    .strict(),
]);

export const nodeDebugSchema = z.object({
  meta: apiMetaSchema,
  debug: nodeDebugViewSchema,
});

export const runErrorsSchema = z.object({
  meta: apiMetaSchema,
  run_id: z.string(),
  errors: z.array(runErrorViewSchema).optional(),
  notes: z.array(z.string()).optional(),
});

export const runAgentsSchema = z.object({
  meta: apiMetaSchema,
  pipeline: agentPipelineViewSchema,
});

export const runWorkflowSchema = z.object({
  meta: apiMetaSchema,
  workflow: runWorkflowViewSchema,
});

export const artifactManifestSchema = z.object({
  meta: apiMetaSchema,
  artifact: artifactManifestViewSchema,
});

export const artifactContentSchema = z.object({
  meta: apiMetaSchema,
  artifact: artifactContentPreviewSchema,
});

export const artifactSchemaSchema = z.object({
  meta: apiMetaSchema,
  schema: artifactSchemaViewSchema,
});

export const artifactLineageSchema = z.object({
  meta: apiMetaSchema,
  lineage: artifactLineageViewSchema,
});

export const bureaucraticRenderSchema = z.object({
  meta: apiMetaSchema,
  document: bureaucraticDocumentSchema,
});

export const bureaucraticExportSchema = z.object({
  meta: apiMetaSchema,
  document_id: z.string(),
  packet_id: z.string(),
  format: z.enum(["html", "pdf", "docx"]),
  content_type: z.string(),
  filename: z.string(),
  content: z.string(),
  metadata: z.record(z.string(), z.unknown()).optional(),
});

export const lineageResponseSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  lineage: lineageGraphViewSchema,
});

const lineageBatchResolutionSchema = z
  .object({
    requested_lineage_id: z.string(),
    resolved_lineage_id: z.string(),
  })
  .strict();

export const lineageBatchResponseSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  lineages: z.array(lineageGraphViewSchema).optional(),
  lineage_resolutions: z
    .array(lineageBatchResolutionSchema)
    .nullable()
    .optional(),
});

export const lineageExportResponseSchema = z.object({
  meta: apiMetaSchema,
  temporal_scope: temporalScopeSchema,
  lineage_id: z.string(),
  format: z.enum(["openlineage", "prov"]),
  payload: z.record(z.string(), z.unknown()),
});

const humanDecisionDigestSchema = z.string().regex(/^sha256:[0-9a-f]{64}$/);
const humanDecisionSourceKindSchema = z.enum([
  "agent_action_authority",
  "production_approval",
]);
const humanDecisionStatusSchema = z.enum([
  "invalid_source",
  "artifact_missing",
  "producer_missing",
  "revalidation_required",
  "blocked",
  "available",
]);
const humanDecisionActionSchema = z.enum([
  "request_evidence",
  "approve",
  "reject",
  "revise_scope",
  "escalate",
]);
const humanDecisionModeSchema = z.enum(["ordinary", "override", "blocking"]);
const humanDecisionActionKindSchema = z
  .string()
  .regex(/^[a-z][a-z0-9_.:-]*$/)
  .max(120);
const humanDecisionRoleSchema = z.enum([
  "principal",
  "mandate_owner",
  "legal_approver",
  "budget_owner",
  "data_steward",
  "affected_person_representative",
  "domain_expert",
  "governance_board",
  "policy_design_governance_reviewer",
  "technical_reviewer",
]);

const humanDecisionCommonSelectorSchema = z.object({
  basis_digest: humanDecisionDigestSchema,
  basis_ref: z.string().min(1),
  decision_request_digest: humanDecisionDigestSchema,
  decision_request_ref: z.string().min(1),
  exposure_session_ref: humanDecisionDigestSchema,
  operational_authority: z.literal(false),
  presentation_contract_ref: humanDecisionDigestSchema,
  principal_binding_ref: humanDecisionDigestSchema,
  reviewer_separation_ref: humanDecisionDigestSchema,
  source_ref: humanDecisionDigestSchema,
});

export const humanDecisionReplaySelectorSchema = z.discriminatedUnion(
  "source_kind",
  [
    humanDecisionCommonSelectorSchema
      .extend({
        action_kind: humanDecisionActionKindSchema,
        source_kind: z.literal("agent_action_authority"),
      })
      .strict(),
    humanDecisionCommonSelectorSchema
      .extend({ source_kind: z.literal("production_approval") })
      .strict(),
  ],
);

const humanDecisionFiveRightsRequirementSchema = z
  .object({
    right_decision: z.string().min(1),
    right_format_channel: z.string().min(1),
    right_information: z.string().min(1),
    right_person: z.string().min(1),
    right_time: z.string().min(1),
    schema_version: z.string().min(1),
  })
  .strict();

const humanDecisionFiveRightsBindingSchema = z
  .object({
    decision_class_id: z.string().min(1),
    decision_rights_matrix_ref: z.string().min(1),
    required_channel: z.enum(["reviewer_console", "governed_review"]),
    required_information_refs: z.array(z.string().min(1)),
    required_representation: z.literal("full"),
    required_role: humanDecisionRoleSchema,
    schema_version: z.string().min(1),
    time_rule: z.literal(
      "intersection_of_signed_validity_intervals_pre_action",
    ),
  })
  .strict();

const humanDecisionRequestSurfaceSchema = z
  .object({
    available_actions: z.array(humanDecisionActionSchema),
    case_id: z.string().min(1),
    decidable_until: z.string().nullable().optional(),
    decision_due_at: z.string().nullable().optional(),
    decision_rights_matrix_ref: z.string().min(1),
    delegation_contract_ref: z.string().min(1),
    five_rights_binding: humanDecisionFiveRightsBindingSchema,
    five_rights_requirements: humanDecisionFiveRightsRequirementSchema,
    requested_at: z.string().min(1),
    required_role: humanDecisionRoleSchema,
  })
  .strict();

const humanDecisionMandateSurfaceSchema = z
  .object({
    action_kind: humanDecisionActionKindSchema,
    mandate_owner_ref: z.string().min(1),
    mandate_record_ref: z.string().min(1),
    operation_id: z.string().min(1),
    valid_from: z.string().min(1),
    valid_until: z.string().min(1),
  })
  .strict();

const humanDecisionExposureSurfaceSchema = z
  .object({
    channel: z.string().nullable().optional(),
    completed_artifact_digests: z.array(humanDecisionDigestSchema),
    exposure_session_ref: humanDecisionDigestSchema.nullable().optional(),
    renderer_id: z.string().nullable().optional(),
    renderer_version: z.string().nullable().optional(),
    representation: z
      .enum(["full", "redacted", "truncated"])
      .nullable()
      .optional(),
    required_artifact_digests: z.array(humanDecisionDigestSchema),
  })
  .strict();

const humanDecisionContestabilitySurfaceSchema = z
  .object({
    case_id: z.string().min(1),
    href: z.string().min(1),
    source_ref: humanDecisionDigestSchema,
  })
  .strict();

const humanDecisionSubmissionSurfaceSchema = z
  .object({
    allowed_decisions: z
      .array(
        z
          .object({
            action: humanDecisionActionSchema,
            decision_modes: z.array(humanDecisionModeSchema).min(1),
          })
          .strict(),
      )
      .min(1)
      .max(5),
    operational_authority: z.literal(false),
    selector: humanDecisionReplaySelectorSchema,
  })
  .strict();

const humanDecisionGatePrecedence = [
  "invalid_source",
  "artifact_missing",
  "producer_missing",
  "revalidation_required",
  "blocked",
  "available",
] as const;

function humanDecisionSelectorEquals(
  left: z.infer<typeof humanDecisionReplaySelectorSchema> | null | undefined,
  right: z.infer<typeof humanDecisionReplaySelectorSchema> | null | undefined,
) {
  return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
}

function humanDecisionModesForAction(
  action: z.infer<typeof humanDecisionActionSchema>,
) {
  if (action === "approve") return ["ordinary", "override"] as const;
  if (action === "reject") return ["blocking"] as const;
  return ["ordinary"] as const;
}

function humanDecisionMultisetEquals(left: string[], right: string[]) {
  const sortedLeft = [...left].sort();
  const sortedRight = [...right].sort();
  return (
    sortedLeft.length === sortedRight.length &&
    sortedLeft.every((value, index) => value === sortedRight[index])
  );
}

export const humanDecisionGateResponseSchema = z
  .object({
    contestability: humanDecisionContestabilitySurfaceSchema
      .nullable()
      .optional(),
    continuation: humanDecisionReplaySelectorSchema.nullable().optional(),
    decision_request: humanDecisionRequestSurfaceSchema.nullable().optional(),
    decision_request_digest: humanDecisionDigestSchema.nullable().optional(),
    decision_request_ref: z.string().nullable(),
    exposure: humanDecisionExposureSurfaceSchema,
    governed_action_key: z.string().nullable().optional(),
    mandate: humanDecisionMandateSurfaceSchema.nullable().optional(),
    operational_authority: z.literal(false),
    reason_codes: z.array(z.string().min(1)),
    reasons: z.array(
      z
        .object({
          code: z.string().min(1),
          message: z.string().min(1),
          status: humanDecisionStatusSchema,
        })
        .strict(),
    ),
    resolved_at: z.string().min(1),
    run_id: z.string().min(1),
    source_kind: humanDecisionSourceKindSchema,
    source_ref: humanDecisionDigestSchema.nullable().optional(),
    status: humanDecisionStatusSchema,
    submission: humanDecisionSubmissionSurfaceSchema.nullable().optional(),
    tenant_id: z.string().min(1),
    verifier_epoch: z.string().min(1),
  })
  .strict()
  .superRefine((value, context) => {
    const surfacedCodes = value.reasons.map((reason) => reason.code);
    const expectedStatus =
      value.reasons.length === 0
        ? "available"
        : humanDecisionGatePrecedence.find((status) =>
            value.reasons.some((reason) => reason.status === status),
          );
    if (value.status !== expectedStatus) {
      context.addIssue({
        code: "custom",
        message:
          "human-decision status must match fail-closed reason precedence",
        path: ["status"],
      });
    }
    if (
      value.reason_codes.length !== surfacedCodes.length ||
      value.reason_codes.some((code, index) => code !== surfacedCodes[index])
    ) {
      context.addIssue({
        code: "custom",
        message: "human-decision reason_codes must exactly project reasons",
        path: ["reason_codes"],
      });
    }
    if (value.status === "available" && !value.submission) {
      context.addIssue({
        code: "custom",
        message:
          "available human-decision gate requires server submission selectors",
        path: ["submission"],
      });
    }
    if (
      value.status === "available" &&
      (!value.decision_request ||
        !value.mandate ||
        !value.continuation ||
        !value.exposure.exposure_session_ref)
    ) {
      context.addIssue({
        code: "custom",
        message: "available gate requires complete pre-action surfaces",
        path: ["status"],
      });
    }
    if (value.status !== "available" && value.submission) {
      context.addIssue({
        code: "custom",
        message:
          "non-available human-decision gate cannot offer submission selectors",
        path: ["submission"],
      });
    }
    if (
      value.status === "available" &&
      !humanDecisionMultisetEquals(
        value.exposure.completed_artifact_digests,
        value.exposure.required_artifact_digests,
      )
    ) {
      context.addIssue({
        code: "custom",
        message: "available gate requires exact evidence-delivery multiplicity",
        path: ["exposure", "completed_artifact_digests"],
      });
    }
    if (
      value.contestability &&
      (value.contestability.source_ref !== value.source_ref ||
        value.contestability.case_id !== value.decision_request?.case_id)
    ) {
      context.addIssue({
        code: "custom",
        message: "contestability requires exact signed case and source binding",
        path: ["contestability"],
      });
    }
    if (
      value.submission &&
      !humanDecisionSelectorEquals(
        value.submission.selector,
        value.continuation,
      )
    ) {
      context.addIssue({
        code: "custom",
        message:
          "submission selector must equal the verified replay continuation",
        path: ["submission", "selector"],
      });
    }
    if (value.continuation) {
      const selector = value.continuation;
      if (
        selector.source_kind !== value.source_kind ||
        selector.source_ref !== value.source_ref ||
        selector.decision_request_ref !== value.decision_request_ref ||
        selector.decision_request_digest !== value.decision_request_digest ||
        selector.exposure_session_ref !== value.exposure.exposure_session_ref ||
        (selector.source_kind === "agent_action_authority" &&
          selector.action_kind !== value.mandate?.action_kind)
      ) {
        context.addIssue({
          code: "custom",
          message: "replay continuation must remain bound to the resolved gate",
          path: ["continuation"],
        });
      }
      if (
        selector.source_kind === "production_approval" &&
        new Set([
          selector.source_ref,
          selector.basis_ref,
          selector.basis_digest,
        ]).size !== 1
      ) {
        context.addIssue({
          code: "custom",
          message:
            "production replay source and basis selectors must be one signed CAS ref",
          path: ["continuation"],
        });
      }
      const binding = value.decision_request?.five_rights_binding;
      if (
        value.decision_request &&
        binding &&
        (binding.required_information_refs.length === 0 ||
          binding.required_role !== value.decision_request.required_role ||
          binding.decision_rights_matrix_ref !==
            value.decision_request.decision_rights_matrix_ref ||
          binding.required_channel !== value.exposure.channel ||
          binding.required_representation !== value.exposure.representation ||
          !humanDecisionMultisetEquals(
            value.exposure.required_artifact_digests,
            [selector.basis_digest, ...binding.required_information_refs],
          ))
      ) {
        context.addIssue({
          code: "custom",
          message:
            "five-rights binding differs from gate evidence presentation",
          path: ["decision_request", "five_rights_binding"],
        });
      }
    }
    if (value.submission) {
      const offeredActions = value.submission.allowed_decisions.map(
        (decision) => decision.action,
      );
      if (
        !value.decision_request ||
        offeredActions.length !==
          value.decision_request.available_actions.length ||
        offeredActions.some(
          (action, index) =>
            action !== value.decision_request?.available_actions[index],
        ) ||
        new Set(offeredActions).size !== offeredActions.length
      ) {
        context.addIssue({
          code: "custom",
          message: "submission actions must exactly match the signed request",
          path: ["submission", "allowed_decisions"],
        });
      }
      value.submission.allowed_decisions.forEach((decision, index) => {
        const expectedModes = humanDecisionModesForAction(decision.action);
        if (
          decision.decision_modes.length !== expectedModes.length ||
          decision.decision_modes.some(
            (mode, modeIndex) => mode !== expectedModes[modeIndex],
          )
        ) {
          context.addIssue({
            code: "custom",
            message: "decision modes must match the server action lattice",
            path: ["submission", "allowed_decisions", index, "decision_modes"],
          });
        }
      });
    }
  });

export const humanDecisionReviewEffectivenessSchema = z
  .object({
    advisory_signal_codes: z.array(z.string().min(1)),
    approval_count: z.number().int().nonnegative(),
    audit_predicate_provenance: z.literal("institutionally_supplied"),
    audit_read_error_count: z.number().int().nonnegative(),
    authoritative_for: z.array(
      z.enum([
        "review_effectiveness_measurement",
        "future_policy_calibration",
        "reviewer_load_observability",
      ]),
    ),
    authorization_allow_count: z.number().int().nonnegative(),
    blocking_count: z.number().int().nonnegative(),
    blocking_permitted: z.literal(false),
    candidate_human_decision_count: z.number().int().nonnegative(),
    completed_human_decision_count: z.number().int().nonnegative(),
    coverage_claim_scope: z.literal("retained_trail_bytes_only"),
    coverage_status: z.enum(["complete", "incomplete"]),
    dissent_count: z.number().int().nonnegative(),
    duplicate_authorization_request_count: z.number().int().nonnegative(),
    duplicate_record_event_count: z.number().int().nonnegative(),
    duplicate_record_request_count: z.number().int().nonnegative(),
    exact_join_count: z.number().int().nonnegative(),
    invalid_authorization_event_count: z.number().int().nonnegative(),
    invalid_record_event_count: z.number().int().nonnegative(),
    malformed_json_line_count: z.number().int().nonnegative(),
    may_not_use_for: z.array(
      z.enum([
        "current_run_closeout_block",
        "publication_block",
        "claim_support_downgrade",
        "authorization_writer_provenance",
        "forensic_tamper_detection",
      ]),
    ),
    measurement_status: z.literal("partial"),
    nonblank_line_count: z.number().int().nonnegative(),
    nonobject_line_count: z.number().int().nonnegative(),
    override_count: z.number().int().nonnegative(),
    parsed_object_count: z.number().int().nonnegative(),
    report_status_effect: z.literal("pass_advisory_only"),
    retained_or_missing_record_count: z.number().int().nonnegative(),
    review_count: z.number().int().nonnegative(),
    review_posture: z.literal("advisory"),
    review_time_established_count: z.literal(0),
    review_time_not_established_count: z.number().int().nonnegative(),
    review_time_status: z.literal("not_established"),
    reviewer_independence_rate: z.number().min(0).max(1).nullable().optional(),
    run_id: z.string().min(1),
    schema_version: z.literal(
      "policyos.runtime.human_decision_review_effectiveness.v1",
    ),
    separation_of_duty_attestation_rate: z
      .number()
      .min(0)
      .max(1)
      .nullable()
      .optional(),
    tenant_scope_unknown_record_event_count: z.number().int().nonnegative(),
    threshold_scope: z.literal("established_signals_only"),
    threshold_status: z.enum(["pass", "warn", "fail"]),
    trail_path_exists: z.boolean(),
    unmatched_authorization_count: z.number().int().nonnegative(),
    unmatched_record_event_count: z.number().int().nonnegative(),
  })
  .strict()
  .superRefine((value, context) => {
    const expectedAuthoritativeFor = [
      "review_effectiveness_measurement",
      "future_policy_calibration",
      "reviewer_load_observability",
    ];
    const expectedDeniedUses = [
      "current_run_closeout_block",
      "publication_block",
      "claim_support_downgrade",
      "authorization_writer_provenance",
      "forensic_tamper_detection",
    ];
    if (
      JSON.stringify(value.authoritative_for) !==
        JSON.stringify(expectedAuthoritativeFor) ||
      JSON.stringify(value.may_not_use_for) !==
        JSON.stringify(expectedDeniedUses)
    ) {
      context.addIssue({
        code: "custom",
        message: "review-effectiveness advisory authority boundary changed",
        path: ["authoritative_for"],
      });
    }
    const complete =
      value.trail_path_exists &&
      value.audit_read_error_count === 0 &&
      value.malformed_json_line_count === 0 &&
      value.nonobject_line_count === 0 &&
      value.invalid_authorization_event_count === 0 &&
      value.invalid_record_event_count === 0 &&
      value.tenant_scope_unknown_record_event_count === 0 &&
      value.unmatched_authorization_count === 0 &&
      value.unmatched_record_event_count === 0 &&
      value.duplicate_authorization_request_count === 0 &&
      value.duplicate_record_request_count === 0 &&
      value.duplicate_record_event_count === 0 &&
      value.retained_or_missing_record_count === 0 &&
      value.candidate_human_decision_count > 0 &&
      value.exact_join_count === value.authorization_allow_count &&
      value.exact_join_count === value.candidate_human_decision_count &&
      value.exact_join_count === value.completed_human_decision_count;
    if (
      value.exact_join_count > value.completed_human_decision_count ||
      value.coverage_status !== (complete ? "complete" : "incomplete")
    ) {
      context.addIssue({
        code: "custom",
        message:
          "review-effectiveness coverage contradicts retained-byte receipts",
        path: ["coverage_status"],
      });
    }
    if (
      value.review_count !== value.completed_human_decision_count ||
      value.review_time_not_established_count !== value.review_count
    ) {
      context.addIssue({
        code: "custom",
        message: "review-effectiveness measurement denominator changed",
        path: ["review_count"],
      });
    }
  });

export const humanDecisionCreateResponseReceiptSchema = z
  .object({
    durable_event_id: z.string().min(1),
    record: z.custom<unknown>(
      (value) =>
        typeof value === "object" && value !== null && !Array.isArray(value),
      { message: "human-decision record readback must be an object" },
    ),
    record_digest: humanDecisionDigestSchema,
    record_ref: humanDecisionDigestSchema,
    reservation_id: z.string().min(1),
    reservation_version: z.number().int().positive(),
    run_id: z.string().min(1),
  })
  .strict()
  .superRefine((value, context) => {
    if (value.record_ref !== value.record_digest) {
      context.addIssue({
        code: "custom",
        message: "human-decision create receipt is not content-bound",
        path: ["record_ref"],
      });
    }
  });

export type HumanDecisionCreateReceipt = z.output<
  typeof humanDecisionCreateResponseReceiptSchema
>;

export type HealthPayload = z.infer<typeof healthSchema>;
export type AuthMePayload = z.infer<typeof authMeSchema>;
export type RunsListPayload = z.infer<typeof runsListSchema>;
export type RunDetailsPayload = z.output<typeof runDetailsSchema>;
export type RunTimelinePayload = z.infer<typeof runTimelineSchema>;
export type RunNodesPayload = z.infer<typeof runNodesSchema>;
export type RunLineagePayload = z.infer<typeof runLineageSchema>;
export type RunQuantitiesPayload = z.infer<typeof runQuantitiesSchema>;
export type RunFabricDecisionDataPayload = z.infer<
  typeof runFabricDecisionDataSchema
>;
export type FabricSourceScorecardsPayload = z.infer<
  typeof fabricSourceScorecardsSchema
>;
export type FabricQualityBatchPayload = z.infer<
  typeof fabricQualityBatchSchema
>;
export type FabricTrustBatchPayload = z.infer<typeof fabricTrustBatchSchema>;
export type FabricReplayPayload = z.infer<typeof fabricReplaySchema>;
export type FabricImpactAnalysisPayload = z.infer<
  typeof fabricImpactAnalysisSchema
>;
export type CompareRunsPayload = z.infer<typeof compareRunsSchema>;
export type CompareCandidatesPayload = z.infer<typeof compareCandidatesSchema>;
export type TemporalCapabilitiesPayload = z.infer<
  typeof temporalCapabilitiesSchema
>;
export type ScenarioListPayload = z.infer<typeof scenarioListSchema>;
export type ScenarioManifestPayload = z.infer<
  typeof scenarioManifestResponseSchema
>;
export type ScenarioCapabilitiesPayload = z.infer<
  typeof scenarioCapabilitiesSchema
>;
export type CounterfactualMetricsPayload = z.infer<
  typeof counterfactualMetricsSchema
>;
export type RunEvidenceContextPayload = z.infer<
  typeof runEvidenceContextSchema
>;
export type GovernanceDebugPayload = z.infer<typeof governanceDebugSchema>;
export type PromotionCandidatesPayload = z.infer<
  typeof promotionCandidatesSchema
>;
export type PromotionDecisionResponsePayload = z.infer<
  typeof promotionDecisionResponseSchema
>;
export type LexSearchRequestPayload = z.infer<typeof lexSearchRequestSchema>;
export type LexSearchResponsePayload = z.infer<typeof lexSearchResponseSchema>;
export type NodeDebugPayload = z.infer<typeof nodeDebugSchema>;
export type RunErrorsPayload = z.infer<typeof runErrorsSchema>;
export type RunAgentsPayload = z.infer<typeof runAgentsSchema>;
export type RunWorkflowPayload = z.infer<typeof runWorkflowSchema>;
export type ArtifactManifestPayload = z.infer<typeof artifactManifestSchema>;
export type ArtifactContentPayload = z.infer<typeof artifactContentSchema>;
export type ArtifactSchemaPayload = z.infer<typeof artifactSchemaSchema>;
export type ArtifactLineagePayload = z.infer<typeof artifactLineageSchema>;
export type BureaucraticRenderPayload = z.infer<
  typeof bureaucraticRenderSchema
>;
export type BureaucraticExportPayload = z.infer<
  typeof bureaucraticExportSchema
>;
export type LineagePayload = z.infer<typeof lineageResponseSchema>;
export type LineageBatchPayload = z.infer<typeof lineageBatchResponseSchema>;
export type LineageExportPayload = z.infer<typeof lineageExportResponseSchema>;
export type HumanDecisionGatePayload = z.infer<
  typeof humanDecisionGateResponseSchema
>;
export type HumanDecisionReviewEffectivenessPayload = z.infer<
  typeof humanDecisionReviewEffectivenessSchema
>;

const predictiveCalibrationArtifactRefSchema = z
  .object({
    artifact_id: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    kind: z.string().min(1),
    media_type: z.string().min(1),
    manifest_profile_sha256: z.string().regex(/^sha256:[0-9a-f]{64}$/),
  })
  .strict();

// These are declared wire locators, not resolved or verified calibration evidence.
const predictiveCalibrationEvidenceLocatorSchema = z.union([
  z
    .string()
    .min(1)
    .refine((value) => value === value.trim(), {
      message: "Evidence reference must not be empty or padded",
    }),
  predictiveCalibrationArtifactRefSchema,
]);

const predictiveCalibrationAuthorityBoundarySchema = z
  .object({
    boundary_id: z
      .string()
      .regex(/^[a-z][a-z0-9_.-]*$/)
      .nullable()
      .optional(),
    authoritative_for: z.array(z.string()).min(1).max(20),
    may_not_use_for: z.array(z.string()).min(1).max(20),
    source_authority: z.enum([
      "deterministic_producer",
      "governed_config",
      "human_governance",
      "llm_candidate",
      "llm_critic",
      "llm_drafter",
    ]),
    posture: z.enum(["shadow", "advisory", "governed", "production"]),
    rule_version_refs: z.array(z.string()).min(1).max(20),
    evidence_kind: z
      .enum([
        "measurement",
        "derivation",
        "proxy",
        "transport",
        "bounds",
        "simulation",
        "elicitation",
        "incomparable_meet",
      ])
      .nullable()
      .optional(),
    decision_grade: z
      .enum([
        "unsupported",
        "descriptive_only",
        "advisory_admissible",
        "decision_admissible",
      ])
      .nullable()
      .optional(),
    evidence_basis: z
      .object({
        // These owner DTO fields carry heterogeneous typed evidence, not authority grants.
        producer_roots: z.array(z.unknown()).max(80).optional(),
        method_refs: z.array(z.string()).max(80).optional(),
        calibration_refs: z
          .array(predictiveCalibrationEvidenceLocatorSchema)
          .max(80)
          .optional(),
        counterexamples_closed: z.array(z.unknown()).max(80).optional(),
      })
      .strict()
      .nullable()
      .optional(),
    known_limits: z.array(z.string()).max(80).optional(),
  })
  .strict()
  .superRefine((boundary, ctx) => {
    if (
      boundary.source_authority.startsWith("llm_") &&
      boundary.posture !== "shadow"
    ) {
      ctx.addIssue({
        code: "custom",
        message: "LLM authority must remain shadow",
      });
    }
    // Match the owner's declaration consistency; parsing never verifies provenance
    // or grants the declared grade/posture any authority in the dashboard.
    if (
      boundary.evidence_kind === "simulation" &&
      ["advisory_admissible", "decision_admissible"].includes(
        boundary.decision_grade ?? "",
      ) &&
      !boundary.evidence_basis?.calibration_refs?.length
    ) {
      ctx.addIssue({
        code: "custom",
        message:
          "Simulation boundary is missing declared calibration references",
      });
    }
  });

const predictiveCalibrationS10Schema = z
  .object({
    calibration_status: z.enum([
      "pass",
      "limit",
      "blocked",
      "not_applicable_non_observable",
      "insufficient_history",
    ]),
    forecast_tier: z.string().min(1).max(120),
    counterfactual_credibility: z.literal("not_established"),
    numerator: z.number().int().nonnegative().nullable(),
    denominator: z.number().int().nonnegative().nullable(),
    observed_pass_rate: z.number().min(0).max(1).nullable(),
    calibration_record_ref: z.string().nullable(),
    outcome_binding_status: z.literal("not_established").nullable().optional(),
    limitation_refs: z.array(z.string()).optional(),
    authority_boundary: predictiveCalibrationAuthorityBoundarySchema
      .nullable()
      .optional(),
    may_not_use_for: z.array(z.string()).min(1).max(20).nullable().optional(),
  })
  .strict();

const predictiveCalibrationAssociationSchema = z
  .object({
    schema_version: z.enum([
      "polisyos.runtime.predictive_calibration_association.v2",
      "polisyos.runtime.predictive_calibration_association.v3",
      "polisyos.runtime.predictive_calibration_association.v4",
      "polisyos.runtime.predictive_calibration_association.v5",
    ]),
    event_id: z.string().min(1),
    intent_id: z.string().min(1).max(120),
    request_sha256: z.string().regex(/^[0-9a-f]{64}$/),
    run_id: z.string().min(1),
    control_run_id: z.string().min(1),
    job_id: z.string().min(1),
    tenant_id: z.string().min(1),
    cell_id: z.string().min(1),
    run_manifest_ref: predictiveCalibrationArtifactRefSchema,
    candidate_source_ref: predictiveCalibrationArtifactRefSchema,
    observed_source_ref: predictiveCalibrationArtifactRefSchema,
    model_spec_ref: predictiveCalibrationArtifactRefSchema,
    policy_spec_ref: predictiveCalibrationArtifactRefSchema,
    calibration_rule_ref: predictiveCalibrationArtifactRefSchema,
    backtest_report_ref: predictiveCalibrationArtifactRefSchema,
    empirical_evidence_ref: predictiveCalibrationArtifactRefSchema,
    uncertainty_bundle_ref: predictiveCalibrationArtifactRefSchema,
    value_data_profile_ref: predictiveCalibrationArtifactRefSchema
      .nullable()
      .optional(),
    forecast_profile_member_ref: predictiveCalibrationArtifactRefSchema
      .nullable()
      .optional(),
    profile_join_status: z
      .enum(["joined_candidate", "profileless_legacy"])
      .optional(),
    assessment: z.literal("limited"),
    authority_scope: z.literal("predictive_only"),
    issuer_status: z.literal("not_established"),
    source_time_status: z.literal("not_established"),
    population_scope_status: z.literal("not_established"),
    counterfactual_credibility_status: z.literal("not_established"),
    observed_numerator: z.number().int().nonnegative().nullable(),
    observed_denominator: z.number().int().positive().nullable(),
    observed_hit_rate: z.number().min(0).max(1).nullable(),
    nominal_confidence_level: z.number().gt(0).lt(1).nullable(),
    owner_suitability: z.enum(["supported", "limited", "blocked"]),
    s10: predictiveCalibrationS10Schema,
    evidence_reason_codes: z.array(z.string()),
    may_not_use_for: z.array(z.string()).min(1).max(40),
    created_at: z.iso.datetime({ offset: true }),
  })
  .strict()
  .superRefine((association, ctx) => {
    const reject = (message: string) =>
      ctx.addIssue({ code: "custom", message });
    const isCurrent =
      association.schema_version ===
      "polisyos.runtime.predictive_calibration_association.v5";
    const sourceUnavailable = association.evidence_reason_codes.includes(
      "backtest_source_not_established",
    );
    const observed = [
      association.observed_numerator,
      association.observed_denominator,
      association.observed_hit_rate,
    ];
    if (
      isCurrent &&
      sourceUnavailable &&
      observed.some((value) => value !== null)
    ) {
      reject("Unavailable observations cannot carry numeric claims");
    }
    if (observed.some((value) => value === null)) {
      if (observed.some((value) => value !== null)) {
        reject("Observed values must be a complete tuple");
      }
      if (
        !isCurrent ||
        !sourceUnavailable ||
        !association.s10.limitation_refs?.includes(
          "s10://calibration/fail-closed/backtest_source_not_established",
        )
      ) {
        reject(
          "Unavailable observations require the current source limitation",
        );
      }
      if (
        association.owner_suitability !== "limited" ||
        association.s10.calibration_status !== "blocked" ||
        association.s10.forecast_tier !== "blocked" ||
        association.s10.calibration_record_ref !== null ||
        association.s10.numerator !== null ||
        association.s10.denominator !== null ||
        association.s10.observed_pass_rate !== null
      ) {
        reject("Unavailable observations cannot carry calibration claims");
      }
    }
    const profile = association.value_data_profile_ref;
    const member = association.forecast_profile_member_ref;
    if (Boolean(profile) !== Boolean(member)) {
      reject("Value profile and forecast member must be selected together");
    }
    if (profile && member) {
      if (
        association.profile_join_status !== "joined_candidate" ||
        profile.kind !== "runtime.value_data_profile" ||
        member.kind !== "runtime.forecast_profile_member" ||
        profile.media_type !== "application/json" ||
        member.media_type !== "application/json"
      ) {
        reject("Invalid selected forecast profile binding");
      }
    } else if (
      association.profile_join_status !== undefined &&
      association.profile_join_status !== "profileless_legacy"
    ) {
      reject("Profileless association cannot claim a profile join");
    }
    // v2 remains readable as historical diagnostics; it does not gain v5 observations.
    if (
      association.schema_version !==
      "polisyos.runtime.predictive_calibration_association.v2"
    ) {
      const s10 = association.s10;
      if (
        s10.outcome_binding_status !== "not_established" ||
        !s10.limitation_refs?.includes(
          "s10://calibration/fail-closed/n4_outcome_target_binding_not_established",
        ) ||
        s10.forecast_tier !== "blocked" ||
        !s10.authority_boundary ||
        !s10.may_not_use_for ||
        JSON.stringify(s10.authority_boundary.may_not_use_for) !==
          JSON.stringify(s10.may_not_use_for) ||
        JSON.stringify(association.may_not_use_for) !==
          JSON.stringify(s10.may_not_use_for)
      ) {
        reject("Missing or inconsistent N4 outcome authority boundary");
      }
    }
  });

export const predictiveCalibrationResponseSchema = z
  .object({
    meta: z
      .object({
        request_id: z.string().min(1),
        generated_at: z.iso.datetime({ offset: true }),
        source_kinds: z.array(z.literal("core_run")),
      })
      .strict(),
    association_ref: predictiveCalibrationArtifactRefSchema,
    association: predictiveCalibrationAssociationSchema,
  })
  .strict();
