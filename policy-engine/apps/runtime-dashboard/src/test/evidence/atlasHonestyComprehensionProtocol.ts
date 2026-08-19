import { z } from "zod";

import {
  ATLAS_EVIDENCE_DENIED_USES,
  ATLAS_EVIDENCE_STORAGE_CONVENTION,
  atlasArtifactIdSchema,
  atlasPredicateProvenanceSchema,
} from "./atlasEvidenceArtifact";

export const ATLAS_HONESTY_COMPREHENSION_SCHEMA = {
  id: "polisyos.atlas.honesty-comprehension-protocol",
  version: "1.0.0",
} as const;

export const ATLAS_HONESTY_METRIC_IDS = [
  "false_action",
  "false_pass",
  "missed_blocker",
  "unsafe_override",
  "time_to_correct",
  "confidence_vs_correctness",
] as const;

export const ATLAS_HONESTY_RESEARCH_CONDITION_IDS = [
  "keyboard_only",
  "screen_reader",
  "low_numeracy",
  "time_pressure",
] as const;

export const ATLAS_HONESTY_RESPONSE_PLANES = [
  "external_execution",
  "evidence_status",
  "polisyos_reaction",
] as const;

export const ATLAS_HONESTY_DENIED_USES = [
  ...ATLAS_EVIDENCE_DENIED_USES,
  "honesty_comprehension_benchmark_pass",
  "human_review_effectiveness_policy",
] as const;

const identity = z
  .string()
  .min(1)
  .regex(/^[a-z0-9][a-z0-9._:@/-]*$/);
const nonEmptyString = z
  .string()
  .min(1)
  .refine((value) => value.trim() === value, {
    message: "value must have no surrounding whitespace",
  });

const protocolIdentitySchema = z
  .object({
    id: z.literal(ATLAS_HONESTY_COMPREHENSION_SCHEMA.id),
    version: z.literal(ATLAS_HONESTY_COMPREHENSION_SCHEMA.version),
  })
  .strict();

const ownerSchema = z
  .object({
    instrument_owner: z.literal("team-frontend"),
    research_content_owner: z.literal("INT-R3"),
    measurement_owner: z.literal("DS6-C11"),
    storage_owner: z.literal("polisyos.core.artifacts.ArtifactStore"),
  })
  .strict();

const cadenceSchema = z
  .object({
    schedule: z.literal("quarterly"),
    event_triggers: z.tuple([
      z.literal("before_first_interactive_authority_surface_stable_claim"),
      z.literal("after_authority_surface_semantics_or_profile_change"),
    ]),
    role: z.literal("collection_schedule_only"),
  })
  .strict();

const samplingSchema = z
  .object({
    method: z.literal("risk_stratified_preregistered"),
    procedure: z.tuple([
      z.literal("declare_risk_strata"),
      z.literal("preregister_sample_frame"),
      z.literal("freeze_frame_before_observation"),
      z.literal("select_only_subjects_in_frozen_frame"),
      z.literal("record_inclusions_and_exclusions"),
    ]),
    frame_ref: atlasArtifactIdSchema.nullable(),
    preregistration_ref: atlasArtifactIdSchema.nullable(),
    sample_size: z.null(),
    completeness: z
      .object({
        status: z.literal("not_established"),
        predicate_provenance: atlasPredicateProvenanceSchema,
      })
      .strict(),
  })
  .strict();

const taskSchema = z
  .object({
    task_id: identity,
    instruction: nonEmptyString,
    expected_answer_binding: z
      .object({
        producer_ref: nonEmptyString,
        field_ref: nonEmptyString,
        predicate_provenance: z.literal("not_established"),
      })
      .strict(),
  })
  .strict();

const conditionSchema = z
  .object({
    condition_id: identity,
    status: z.literal("not_established"),
  })
  .strict();

const thresholdSchema = z
  .object({
    metric_id: identity,
    status: z.literal("not_established"),
    comparator: z.null(),
    value: z.null(),
    unit: z.null(),
    source_ref: z.null(),
  })
  .strict();

const researchInputSchema = z
  .object({
    input_id: z.literal("INT-R3"),
    status: z.literal("not_established"),
    source_ref: z.null(),
    predicate_provenance: z.literal("not_established"),
  })
  .strict();

function addUniqueIssue(
  values: readonly string[],
  path: string,
  context: z.RefinementCtx,
): void {
  if (new Set(values).size !== values.length) {
    context.addIssue({
      code: "custom",
      path: [path],
      message: `${path} identities must be unique`,
    });
  }
}

const SEED_PROFILE_ID = "ds6.honesty-comprehension.seed";
const SEED_PROFILE_VERSION = "1.0.0";
const SEED_TASKS = [
  {
    task_id: "find_weakest_link",
    instruction: "Find the weakest link.",
    expected_answer_binding: {
      producer_ref:
        "src/polisyos/runtime/http/services/governed_projections.py::_project_depth_n",
      field_ref:
        "terminal.blocking_obligations->domain_runs.<domain>.weakest_links",
      predicate_provenance: "not_established",
    },
  },
  {
    task_id: "find_active_blockers",
    instruction: "Find the active blockers.",
    expected_answer_binding: {
      producer_ref:
        "src/polisyos/runtime/quality/projection_semantics.py::_closeout_truth",
      field_ref: "PolicyDesignCaseProjection.closeout_truth.blockers",
      predicate_provenance: "not_established",
    },
  },
] as const;
const SEED_CONDITIONS = ATLAS_HONESTY_RESEARCH_CONDITION_IDS.map(
  (condition_id) => ({
    condition_id,
    status: "not_established" as const,
  }),
);
const SEED_THRESHOLDS = ATLAS_HONESTY_METRIC_IDS.map((metric_id) => ({
  metric_id,
  status: "not_established" as const,
  comparator: null,
  value: null,
  unit: null,
  source_ref: null,
}));

function addExactIssue(
  actual: unknown,
  expected: unknown,
  path: string,
  message: string,
  context: z.RefinementCtx,
): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    context.addIssue({ code: "custom", path: [path], message });
  }
}

export const atlasHonestyInstrumentProfileSchema = z
  .object({
    profile_id: identity,
    profile_version: nonEmptyString,
    research_input: researchInputSchema,
    tasks: z.array(taskSchema).min(1),
    response_planes: z.tuple([
      z.literal("external_execution"),
      z.literal("evidence_status"),
      z.literal("polisyos_reaction"),
    ]),
    metric_ids: z.array(identity).min(1),
    conditions: z.array(conditionSchema),
    thresholds: z.array(thresholdSchema).min(1),
  })
  .strict()
  .superRefine((profile, context) => {
    addUniqueIssue(
      profile.tasks.map((task) => task.task_id),
      "tasks",
      context,
    );
    addUniqueIssue(profile.metric_ids, "metric_ids", context);
    addUniqueIssue(
      profile.conditions.map((condition) => condition.condition_id),
      "conditions",
      context,
    );
    addUniqueIssue(
      profile.thresholds.map((threshold) => threshold.metric_id),
      "thresholds",
      context,
    );
    for (const metricId of ATLAS_HONESTY_METRIC_IDS) {
      if (!profile.metric_ids.includes(metricId)) {
        context.addIssue({
          code: "custom",
          path: ["metric_ids"],
          message: `required INT-R3 metric is absent: ${metricId}`,
        });
      }
    }
    const conditionIds = profile.conditions.map(
      (condition) => condition.condition_id,
    );
    for (const conditionId of ATLAS_HONESTY_RESEARCH_CONDITION_IDS) {
      if (!conditionIds.includes(conditionId)) {
        context.addIssue({
          code: "custom",
          path: ["conditions"],
          message: `required INT-R3 condition is absent: ${conditionId}`,
        });
      }
    }
    if (
      JSON.stringify(profile.thresholds.map((threshold) => threshold.metric_id)) !==
      JSON.stringify(profile.metric_ids)
    ) {
      context.addIssue({
        code: "custom",
        path: ["thresholds"],
        message: "threshold rows must exactly match the ordered metric identity set",
      });
    }
    if (profile.profile_id === SEED_PROFILE_ID) {
      addExactIssue(
        profile.profile_version,
        SEED_PROFILE_VERSION,
        "profile_version",
        "the seed profile identity requires its frozen version",
        context,
      );
      addExactIssue(
        profile.tasks,
        SEED_TASKS,
        "tasks",
        "the seed profile identity requires the exact two seed tasks",
        context,
      );
      addExactIssue(
        profile.response_planes,
        ATLAS_HONESTY_RESPONSE_PLANES,
        "response_planes",
        "the seed profile identity requires the exact response planes",
        context,
      );
      addExactIssue(
        profile.metric_ids,
        ATLAS_HONESTY_METRIC_IDS,
        "metric_ids",
        "the seed profile identity requires the exact metric set",
        context,
      );
      addExactIssue(
        profile.conditions,
        SEED_CONDITIONS,
        "conditions",
        "the seed profile identity requires the exact condition set",
        context,
      );
      addExactIssue(
        profile.thresholds,
        SEED_THRESHOLDS,
        "thresholds",
        "the seed profile identity requires the exact unestablished thresholds",
        context,
      );
    }
  });

const authoritySchema = z
  .object({
    authoritative_for: z.tuple([
      z.literal("descriptive_honesty_comprehension_observation"),
    ]),
    may_not_use_for: z.array(nonEmptyString),
    blocking_permitted: z.literal(false),
  })
  .strict()
  .superRefine((authority, context) => {
    if (
      JSON.stringify(authority.may_not_use_for) !==
      JSON.stringify(ATLAS_HONESTY_DENIED_USES)
    ) {
      context.addIssue({
        code: "custom",
        path: ["may_not_use_for"],
        message: "honesty comprehension must retain the exact C07 denial prefix",
      });
    }
  });

const storageConventionSchema = z.custom<
  typeof ATLAS_EVIDENCE_STORAGE_CONVENTION
>((value) => {
  return (
    JSON.stringify(value) === JSON.stringify(ATLAS_EVIDENCE_STORAGE_CONVENTION)
  );
}, "storage convention must equal the canonical C07 contract");

const interpretationSchema = z
  .object({
    posture: z.literal("descriptive_only"),
    benchmark_status: z.literal("not_established"),
    stable_bar_effect: z.literal("not_established"),
    grants_stable: z.literal(false),
  })
  .strict();

const capabilitySchema = z
  .object({
    label: z.literal("contract_only"),
    missing: z.tuple([
      z.literal("producer_missing"),
      z.literal("artifact_missing"),
      z.literal("bridge_missing"),
      z.literal("consumer_missing"),
      z.literal("verification_missing"),
      z.literal("surface_missing"),
    ]),
  })
  .strict();

export const atlasHonestyComprehensionDetailsSchema = z
  .object({
    protocol_schema: protocolIdentitySchema,
    owners: ownerSchema,
    cadence: cadenceSchema,
    sampling: samplingSchema,
    active_profile: atlasHonestyInstrumentProfileSchema,
    authority: authoritySchema,
    interpretation: interpretationSchema,
    storage_convention: storageConventionSchema,
    capability: capabilitySchema,
  })
  .strict();

export type AtlasHonestyComprehensionDetails = z.infer<
  typeof atlasHonestyComprehensionDetailsSchema
>;

export const ATLAS_HONESTY_COMPREHENSION_PROTOCOL = {
  protocol_schema: ATLAS_HONESTY_COMPREHENSION_SCHEMA,
  owners: {
    instrument_owner: "team-frontend",
    research_content_owner: "INT-R3",
    measurement_owner: "DS6-C11",
    storage_owner: "polisyos.core.artifacts.ArtifactStore",
  },
  cadence: {
    schedule: "quarterly",
    event_triggers: [
      "before_first_interactive_authority_surface_stable_claim",
      "after_authority_surface_semantics_or_profile_change",
    ],
    role: "collection_schedule_only",
  },
  sampling: {
    method: "risk_stratified_preregistered",
    procedure: [
      "declare_risk_strata",
      "preregister_sample_frame",
      "freeze_frame_before_observation",
      "select_only_subjects_in_frozen_frame",
      "record_inclusions_and_exclusions",
    ],
    frame_ref: null,
    preregistration_ref: null,
    sample_size: null,
    completeness: {
      status: "not_established",
      predicate_provenance: "not_established",
    },
  },
  active_profile: {
    profile_id: SEED_PROFILE_ID,
    profile_version: SEED_PROFILE_VERSION,
    research_input: {
      input_id: "INT-R3",
      status: "not_established",
      source_ref: null,
      predicate_provenance: "not_established",
    },
    tasks: SEED_TASKS,
    response_planes: ATLAS_HONESTY_RESPONSE_PLANES,
    metric_ids: [...ATLAS_HONESTY_METRIC_IDS],
    conditions: SEED_CONDITIONS,
    thresholds: SEED_THRESHOLDS,
  },
  authority: {
    authoritative_for: ["descriptive_honesty_comprehension_observation"],
    may_not_use_for: [...ATLAS_HONESTY_DENIED_USES],
    blocking_permitted: false,
  },
  interpretation: {
    posture: "descriptive_only",
    benchmark_status: "not_established",
    stable_bar_effect: "not_established",
    grants_stable: false,
  },
  storage_convention: ATLAS_EVIDENCE_STORAGE_CONVENTION,
  capability: {
    label: "contract_only",
    missing: [
      "producer_missing",
      "artifact_missing",
      "bridge_missing",
      "consumer_missing",
      "verification_missing",
      "surface_missing",
    ],
  },
} as const;

const observationSchema = z.discriminatedUnion("status", [
  z.object({ status: z.literal("missing") }).strict(),
  z
    .object({
      status: z.literal("unknown"),
      reason_code: identity,
    })
    .strict(),
  z
    .object({
      status: z.literal("incomparable"),
      reason_code: z.literal("no_admissible_ranking"),
    })
    .strict(),
  z
    .object({
      status: z.literal("observed"),
      observation_count: z.number().int().nonnegative(),
    })
    .strict(),
]);

export type HonestyComprehensionObservation = z.infer<typeof observationSchema>;

export type HonestyComprehensionInterpretation = {
  observation_status: "missing" | "unknown" | "zero" | "incomparable" | "recorded";
  observation_code:
    | "honesty_observation_missing"
    | "honesty_observation_unknown"
    | "honesty_observation_zero"
    | "honesty_observation_incomparable"
    | "honesty_observation_recorded";
  research_input_status: "not_established";
  sampling_completeness: "not_established";
  sampling_predicate_provenance: z.infer<typeof atlasPredicateProvenanceSchema>;
  benchmark_status: "not_established";
  stable_bar_effect: "not_established";
  interpretation: "descriptive_only";
  grants_stable: false;
  blocking_permitted: false;
  capability: "contract_only";
};

/**
 * Interpret one seed observation without fabricating benchmark authority.
 *
 * This is a contract consumer only. It neither persists a C07 receipt nor
 * scores behavioral adequacy, because INT-R3 and a generic reviewer producer
 * are absent.
 */
export function classifyHonestyComprehensionObservation(
  detailsValue: unknown,
  observationValue: unknown,
): HonestyComprehensionInterpretation {
  const details = atlasHonestyComprehensionDetailsSchema.parse(detailsValue);
  const observation = observationSchema.parse(observationValue);

  let observationStatus: HonestyComprehensionInterpretation["observation_status"];
  let observationCode: HonestyComprehensionInterpretation["observation_code"];
  if (observation.status === "missing") {
    observationStatus = "missing";
    observationCode = "honesty_observation_missing";
  } else if (observation.status === "unknown") {
    observationStatus = "unknown";
    observationCode = "honesty_observation_unknown";
  } else if (observation.status === "incomparable") {
    observationStatus = "incomparable";
    observationCode = "honesty_observation_incomparable";
  } else if (observation.observation_count === 0) {
    observationStatus = "zero";
    observationCode = "honesty_observation_zero";
  } else {
    observationStatus = "recorded";
    observationCode = "honesty_observation_recorded";
  }

  return {
    observation_status: observationStatus,
    observation_code: observationCode,
    research_input_status: "not_established",
    sampling_completeness: "not_established",
    sampling_predicate_provenance:
      details.sampling.completeness.predicate_provenance,
    benchmark_status: "not_established",
    stable_bar_effect: "not_established",
    interpretation: "descriptive_only",
    grants_stable: false,
    blocking_permitted: false,
    capability: "contract_only",
  };
}
