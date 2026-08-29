import { z } from "zod";

import type {
  AcquisitionDecisionRequestResponse,
  AcquisitionExecutionResponse,
  AcquisitionGrowthPayload,
  AcquisitionRouteListResponse,
  AcquisitionRouteProjection,
} from "@polisyos/runtime-api-client";

const acquisitionReplayPinsSchema = z
  .object({
    compiled_content_hash: z.string().min(1),
    compiled_ref: z.string().min(1),
    cost_basis_hash: z.string().min(1),
    design_problem_ref: z.string().min(1),
    source_job_id: z.string().min(1),
    terminal_event_id: z.string().min(1),
  })
  .strict();

export const acquisitionRouteProjectionSchema: z.ZodType<AcquisitionRouteProjection> =
  z
    .object({
      authority_badge: z.literal("behavioral_fixture_not_production"),
      authority_capability: z.enum(["ready", "producer_missing"]),
      cell_id: z.string().min(1),
      cost_basis: z.record(z.string(), z.unknown()),
      execution_capability: z.enum(["ready", "producer_missing"]),
      external_nonclosures: z.array(z.string()),
      planner_record_id: z.string().min(1),
      planner_report_hash: z.string().min(1),
      qualification_predicate: z.literal("not_established"),
      qualification_reason: z.literal("policy_admission_missing"),
      qualification_status: z.literal("pending_epoch_activation"),
      recommended_strategy: z.string().min(1),
      replay_pins: acquisitionReplayPinsSchema,
      route_id: z.string().min(1),
      route_projection_hash: z.string().min(1),
      route_status: z.literal("costed_actionable"),
      run_id: z.string().min(1),
      schema_version: z.literal("AcquisitionRouteProjection@1.0"),
      tenant_id: z.string().min(1),
      world_growth: z.literal("no_growth"),
    })
    .strict();

export const acquisitionRouteListResponseSchema: z.ZodType<AcquisitionRouteListResponse> =
  z
    .object({
      routes: z.array(acquisitionRouteProjectionSchema),
      run_id: z.string().min(1),
    })
    .strict()
    .superRefine((value, context) => {
      for (const [index, route] of value.routes.entries()) {
        if (route.run_id !== value.run_id) {
          context.addIssue({
            code: "custom",
            message: "acquisition route is cross-bound to another run",
            path: ["routes", index, "run_id"],
          });
        }
      }
    });

const acquisitionBacklogProjectionSchema = z
  .object({
    authority_boundary: z.literal("ranking_only_not_voi"),
    binding_confidence: z.number(),
    classification_basis: z.enum([
      "independently_reconciled",
      "not_established",
    ]),
    gap_class: z.enum(["data_gap", "structural_gap", "not_established"]),
    rank: z.number().int().positive(),
    ranking_method: z.string().min(1),
    ranking_score: z.number(),
    route_demand: z.number().nonnegative(),
    variable_id: z.string().min(1),
    voi_owner_fit: z.string().min(1),
    voi_owner_integration: z.string().min(1),
    voi_owner_ref: z.string().min(1),
  })
  .strict();

const structuralRouteProjectionSchema = z
  .object({
    action_eligibility: z.enum(["not_applicable", "blocked"]),
    gap_class: z.enum(["data_gap", "structural_gap", "not_established"]),
    missing_link: z.string().min(1),
    route_class: z.string().min(1),
    route_id: z.string().min(1),
    witness_kind: z.string().min(1),
  })
  .strict()
  .superRefine((value, context) => {
    if (
      value.gap_class === "structural_gap" &&
      value.action_eligibility !== "not_applicable"
    ) {
      context.addIssue({
        code: "custom",
        message: "structural acquisition route must remain not applicable",
        path: ["action_eligibility"],
      });
    }
  });

const epochQualificationDisclosureSchema = z
  .object({
    appointment_state: z.literal("unappointed"),
    appointment_would_establish: z.literal(
      "authority to qualify native semantic production, append its history head and permit overlay activation",
    ),
    appointment_would_not_establish: z.tuple([
      z.literal("gap shape"),
      z.literal("passport validity"),
      z.literal("positive delta"),
      z.literal("re-entry"),
    ]),
    authority_owner_ref: z.null(),
    authority_role: z.literal("semantic epoch policy-admission qualifier"),
    code: z.literal("policy_admission_missing"),
    epoch_state: z.literal("pending_epoch_activation"),
    status: z.literal("not_established"),
  })
  .strict();

const n13bHistoryProjectionSchema = z
  .object({
    admission: z.enum(["not_reached", "not_established"]),
    attempt_count: z.number().int().nonnegative(),
    epoch_qualification: epochQualificationDisclosureSchema,
    execution_phase: z.enum(["executing", "terminal"]),
    overlay_epoch_count: z.number().int().nonnegative(),
    quarantine: z.enum(["none", "raw_terminal"]),
    quarantine_count: z.number().int().nonnegative(),
    raw_response_count: z.number().int().nonnegative(),
    reentry: z.enum(["not_established", "deeper_terminal"]),
    response_admitted_count: z.number().int().nonnegative(),
    terminal_count: z.number().int().nonnegative(),
    world_growth: z.enum(["not_established", "no_growth"]),
  })
  .strict();

export const acquisitionGrowthPayloadSchema: z.ZodType<AcquisitionGrowthPayload> =
  z
    .object({
      backlog: z.array(acquisitionBacklogProjectionSchema),
      carrier_liveness: z.record(z.string(), z.unknown()),
      n13b_history: n13bHistoryProjectionSchema,
      schema_version: z.literal(
        "policyos.runtime.acquisition_growth_projection.v1",
      ),
      structural_routes: z.array(structuralRouteProjectionSchema),
      summary: z
        .object({
          actual_network_call_count: z.number().int().nonnegative(),
          backlog_count: z.number().int().nonnegative(),
          family_scorecard_count: z.number().int().nonnegative(),
          metric_resolution_count: z.number().int().nonnegative(),
          selected_record_count: z.number().int().nonnegative(),
          structural_route_count: z.number().int().nonnegative(),
        })
        .strict(),
    })
    .strict()
    .superRefine((value, context) => {
      if (value.summary.backlog_count !== value.backlog.length) {
        context.addIssue({
          code: "custom",
          message: "acquisition backlog denominator mismatch",
          path: ["summary", "backlog_count"],
        });
      }
      if (
        value.summary.structural_route_count !== value.structural_routes.length
      ) {
        context.addIssue({
          code: "custom",
          message: "structural route denominator mismatch",
          path: ["summary", "structural_route_count"],
        });
      }
    });

const projectionOwnerBindingSchema = z
  .object({
    binding_name: z.string(),
    owner_semantic_hash: z.string(),
    relation: z.literal("semantic_projection"),
    relative_path: z.string(),
    resolved_artifact_content_hash: z.string(),
    semantic_hash_rule_version: z.string(),
  })
  .strict();

const projectionSourceValidationSchema = z
  .object({
    bound_artifact_content_hash: z.string(),
    bound_dependency_aggregate_identity: z.string(),
    bound_dependency_count: z.number().int().nonnegative(),
    issue_codes: z.array(z.string()),
    semantic_projection_hash: z.string().nullable().optional(),
    semantic_projection_hash_rule_version: z.string().nullable().optional(),
    status: z.enum(["passed", "failed", "not_run"]),
    validator_id: z.string(),
    validator_version: z.string(),
  })
  .strict();

export const acquisitionGrowthPacketSchema: z.ZodType = z
  .object({
    absence_reason: z.null().optional(),
    as_of: z.string(),
    authoritative_for: z.array(z.string()),
    availability: z.literal("available"),
    export_replay_contract: z.literal(
      "policyos.runtime.export_replay_binding.v1",
    ),
    freshness: z
      .object({
        basis: z.enum([
          "source_timestamp",
          "filesystem_mtime",
          "request_observation",
        ]),
        observed_at: z.string(),
        source_as_of: z.string().nullable().optional(),
        state: z.literal("observed"),
      })
      .strict(),
    intended_audience: z.enum(["REVIEWER", "EXPERT", "MACHINE"]),
    may_not_use_for: z.array(z.string()),
    packet_schema_version: z.literal(
      "policyos.runtime.governed_projection_packet.v1",
    ),
    payload: acquisitionGrowthPayloadSchema,
    projection_hash: z.string(),
    projection_id: z.literal("acquisition-growth"),
    projection_rule_version: z.literal(
      "policyos.runtime.governed_projection.v1",
    ),
    replay_address: z.string(),
    source: z
      .object({
        artifact_content_hash: z.string(),
        declared_content_hash: z.string().nullable().optional(),
        related_artifact_bindings: z.array(projectionOwnerBindingSchema),
        relative_path: z.string(),
        validation: projectionSourceValidationSchema,
      })
      .strict(),
    source_dependency_hash: z.string(),
    source_rule_version: z.string().nullable().optional(),
    source_schema_version: z.string().nullable().optional(),
    stable_address: z.string(),
  })
  .strict();

export const acquisitionDecisionRequestResponseSchema: z.ZodType<AcquisitionDecisionRequestResponse> =
  z
    .object({
      authority_decision_ref: z.string().min(1),
      human_decision_request: z
        .record(z.string(), z.unknown())
        .nullable()
        .optional(),
      outcome: z.enum(["decision_required", "decision_available"]),
      route_id: z.string().min(1),
      run_id: z.string().min(1),
      world_growth: z.literal("no_growth"),
    })
    .strict();

export const acquisitionExecutionResponseSchema: z.ZodType<AcquisitionExecutionResponse> =
  z
    .object({
      authority_decision_ref: z.string().min(1),
      job_id: z.string().min(1),
      receipt_phase: z.literal("requested"),
      route_id: z.string().min(1),
      run_id: z.string().min(1),
      status: z.literal("accepted"),
      world_growth: z.literal("no_growth"),
    })
    .strict();
