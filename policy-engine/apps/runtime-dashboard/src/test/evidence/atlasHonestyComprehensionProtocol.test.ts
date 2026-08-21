import { describe, expect, it } from "vitest";

import {
  ATLAS_EVIDENCE_DENIED_USES,
  ATLAS_EVIDENCE_STORAGE_CONVENTION,
} from "./atlasEvidenceArtifact";
import {
  ATLAS_HONESTY_COMPREHENSION_PROTOCOL,
  ATLAS_HONESTY_METRIC_IDS,
  ATLAS_HONESTY_RESEARCH_CONDITION_IDS,
  ATLAS_HONESTY_RESPONSE_PLANES,
  atlasHonestyComprehensionDetailsSchema,
  atlasHonestyInstrumentProfileSchema,
  classifyHonestyComprehensionObservation,
} from "./atlasHonestyComprehensionProtocol";

const NULL_THRESHOLD = {
  status: "not_established" as const,
  comparator: null,
  value: null,
  unit: null,
  source_ref: null,
};
const FRAME_ARTIFACT_ID = `sha256:${"a".repeat(64)}`;
const PREREGISTRATION_ARTIFACT_ID = `sha256:${"b".repeat(64)}`;

describe("Atlas honesty-comprehension seed protocol", () => {
  it("binds the exact owners, cadence, sampling procedure, and C07 storage", () => {
    expect(ATLAS_HONESTY_COMPREHENSION_PROTOCOL.owners).toEqual({
      instrument_owner: "team-frontend",
      research_content_owner: "INT-R3",
      measurement_owner: "DS6-C11",
      storage_owner: "polisyos.core.artifacts.ArtifactStore",
    });
    expect(ATLAS_HONESTY_COMPREHENSION_PROTOCOL.cadence).toEqual({
      schedule: "quarterly",
      event_triggers: [
        "before_first_interactive_authority_surface_stable_claim",
        "after_authority_surface_semantics_or_profile_change",
      ],
      role: "collection_schedule_only",
    });
    expect(ATLAS_HONESTY_COMPREHENSION_PROTOCOL.sampling).toEqual({
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
    });
    expect(
      ATLAS_HONESTY_COMPREHENSION_PROTOCOL.storage_convention,
    ).toBe(ATLAS_EVIDENCE_STORAGE_CONVENTION);
    expect(
      atlasHonestyComprehensionDetailsSchema.parse(
        ATLAS_HONESTY_COMPREHENSION_PROTOCOL,
      ),
    ).toEqual(ATLAS_HONESTY_COMPREHENSION_PROTOCOL);
  });

  it("freezes the two seed tasks and the six research-owned metric identities", () => {
    expect(
      ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile.tasks,
    ).toEqual([
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
    ]);
    expect(ATLAS_HONESTY_METRIC_IDS).toEqual([
      "false_action",
      "false_pass",
      "missed_blocker",
      "unsafe_override",
      "time_to_correct",
      "confidence_vs_correctness",
    ]);
    expect(
      ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile.metric_ids,
    ).toEqual(ATLAS_HONESTY_METRIC_IDS);
    expect(ATLAS_HONESTY_RESEARCH_CONDITION_IDS).toEqual([
      "keyboard_only",
      "screen_reader",
      "low_numeracy",
      "time_pressure",
    ]);
    expect(ATLAS_HONESTY_RESPONSE_PLANES).toEqual([
      "external_execution",
      "evidence_status",
      "polisyos_reaction",
    ]);

    const mutatedSeed = {
      ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL,
      active_profile: {
        ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile,
        tasks: ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile.tasks.map(
          (task, index) =>
            index === 0
              ? { ...task, instruction: "Markers preserved; seed content changed." }
              : task,
        ),
      },
    };
    expect(
      atlasHonestyComprehensionDetailsSchema.safeParse(mutatedSeed).success,
    ).toBe(false);
  });

  it("keeps every seed threshold not established and rejects every populated field", () => {
    const thresholds =
      ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile.thresholds;
    expect(thresholds).toEqual(
      ATLAS_HONESTY_METRIC_IDS.map((metric_id) => ({
        metric_id,
        ...NULL_THRESHOLD,
      })),
    );

    const mutations: ReadonlyArray<Record<string, unknown>> = [
      { status: "established" },
      { comparator: ">=" },
      { value: 1 },
      { unit: "ratio" },
      { source_ref: "INT-R3" },
    ];
    for (const threshold of thresholds) {
      for (const mutation of mutations) {
        const candidate = {
          ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL,
          active_profile: {
            ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile,
            thresholds: thresholds.map((entry) =>
              entry.metric_id === threshold.metric_id
                ? { ...entry, ...mutation }
                : entry,
            ),
          },
        };
        expect(
          atlasHonestyComprehensionDetailsSchema.safeParse(candidate).success,
          `${threshold.metric_id} admitted ${JSON.stringify(mutation)}`,
        ).toBe(false);
      }
    }
  });

  it("generically rejects incomplete, duplicate, or populated profiles", () => {
    const profile = {
      ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile,
      profile_id: "candidate.int-r3.generic-invariant-witness",
      profile_version: "candidate-1",
    };
    expect(
      atlasHonestyInstrumentProfileSchema.safeParse({
        ...profile,
        thresholds: profile.thresholds.slice(1),
      }).success,
    ).toBe(false);
    for (const metricId of ATLAS_HONESTY_METRIC_IDS) {
      expect(
        atlasHonestyInstrumentProfileSchema.safeParse({
          ...profile,
          metric_ids: profile.metric_ids.filter((id) => id !== metricId),
          thresholds: profile.thresholds.filter(
            (row) => row.metric_id !== metricId,
          ),
        }).success,
        `missing required metric ${metricId}`,
      ).toBe(false);
    }
    for (const conditionId of ATLAS_HONESTY_RESEARCH_CONDITION_IDS) {
      expect(
        atlasHonestyInstrumentProfileSchema.safeParse({
          ...profile,
          conditions: profile.conditions.filter(
            (condition) => condition.condition_id !== conditionId,
          ),
        }).success,
        `missing required condition ${conditionId}`,
      ).toBe(false);
    }
    expect(
      atlasHonestyInstrumentProfileSchema.safeParse({
        ...profile,
        metric_ids: [...profile.metric_ids, profile.metric_ids[0]],
      }).success,
    ).toBe(false);
    expect(
      atlasHonestyInstrumentProfileSchema.safeParse({
        ...profile,
        metric_ids: [...profile.metric_ids, "invented_metric"],
        thresholds: [
          ...profile.thresholds,
          { metric_id: "invented_metric", ...NULL_THRESHOLD, value: 0 },
        ],
      }).success,
    ).toBe(false);
    expect(
      atlasHonestyInstrumentProfileSchema.safeParse({
        ...profile,
        tasks: [...profile.tasks, profile.tasks[0]],
      }).success,
    ).toBe(false);
  });

  it("accepts a version-bumped replacement profile without establishing thresholds", () => {
    const replacement = {
      ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile,
      profile_id: "candidate.int-r3.behavioral-battery",
      profile_version: "candidate-2",
      tasks: [
        {
          task_id: "distinguish_unknown_zero_missing",
          instruction: "Distinguish unknown, zero, and missing evidence.",
          expected_answer_binding: {
            producer_ref: "future.int-r3.owner",
            field_ref: "typed_evidence_status",
            predicate_provenance: "not_established" as const,
          },
        },
        {
          task_id: "refuse_stale_or_quarantined",
          instruction: "Choose an action for stale or quarantined evidence.",
          expected_answer_binding: {
            producer_ref: "future.int-r3.owner",
            field_ref: "governed_temporal_status",
            predicate_provenance: "not_established" as const,
          },
        },
        {
          task_id: "choose_safe_reaction",
          instruction: "Choose acquisition, escalation, or abstention.",
          expected_answer_binding: {
            producer_ref: "future.int-r3.owner",
            field_ref: "governed_policyos_reaction",
            predicate_provenance: "not_established" as const,
          },
        },
      ],
      metric_ids: [
        ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile.metric_ids,
        "candidate_research_metric",
      ],
      conditions: [
        ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile.conditions,
        {
          condition_id: "candidate_research_condition",
          status: "not_established" as const,
        },
      ],
      thresholds: [
        ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL.active_profile.thresholds,
        {
          metric_id: "candidate_research_metric",
          ...NULL_THRESHOLD,
        },
      ],
    };

    expect(atlasHonestyInstrumentProfileSchema.parse(replacement)).toEqual(
      replacement,
    );
    expect(replacement.thresholds.every((row) => row.status === "not_established"))
      .toBe(true);
  });

  it("rejects authority widening and a removed or reordered C07 denial", () => {
    const authority = ATLAS_HONESTY_COMPREHENSION_PROTOCOL.authority;
    expect(authority.may_not_use_for.slice(0, ATLAS_EVIDENCE_DENIED_USES.length))
      .toEqual(ATLAS_EVIDENCE_DENIED_USES);

    for (const candidateAuthority of [
      { ...authority, blocking_permitted: true },
      {
        ...authority,
        may_not_use_for: authority.may_not_use_for.filter(
          (purpose) => purpose !== "stable",
        ),
      },
      {
        ...authority,
        may_not_use_for: [...authority.may_not_use_for].reverse(),
      },
    ]) {
      expect(
        atlasHonestyComprehensionDetailsSchema.safeParse({
          ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL,
          authority: candidateAuthority,
        }).success,
      ).toBe(false);
    }
  });

  it("does not let shaped sampling refs or completeness markers grant authority", () => {
    const shaped = {
      ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL,
      sampling: {
        ...ATLAS_HONESTY_COMPREHENSION_PROTOCOL.sampling,
        frame_ref: FRAME_ARTIFACT_ID,
        preregistration_ref: PREREGISTRATION_ARTIFACT_ID,
      },
    };
    expect(
      classifyHonestyComprehensionObservation(shaped, {
        status: "observed",
        observation_count: 3,
      }),
    ).toMatchObject({
      observation_status: "recorded",
      sampling_completeness: "not_established",
      benchmark_status: "not_established",
      interpretation: "descriptive_only",
      grants_stable: false,
      blocking_permitted: false,
    });
    expect(
      atlasHonestyComprehensionDetailsSchema.safeParse({
        ...shaped,
        sampling: {
          ...shaped.sampling,
          declared_complete: true,
        },
      }).success,
    ).toBe(false);
    for (const malformedRef of [
      "sha256:declared-frame",
      `sha256:${"A".repeat(64)}`,
      `sha256:${"a".repeat(63)}`,
      "sha512:declared-frame",
    ]) {
      expect(
        atlasHonestyComprehensionDetailsSchema.safeParse({
          ...shaped,
          sampling: {
            ...shaped.sampling,
            frame_ref: malformedRef,
          },
        }).success,
      ).toBe(false);
    }
    for (const predicate_provenance of [
      "consumer_asserted",
      "institutionally_supplied",
    ] as const) {
      const result = classifyHonestyComprehensionObservation(
        {
          ...shaped,
          sampling: {
            ...shaped.sampling,
            completeness: {
              status: "not_established" as const,
              predicate_provenance,
            },
          },
        },
        { status: "observed", observation_count: 3 },
      );
      expect(result).toMatchObject({
        sampling_completeness: "not_established",
        grants_stable: false,
        blocking_permitted: false,
      });
    }
  });

  it("keeps missing, unknown, known zero, incomparable, and recorded distinct", () => {
    const classify = (observation: unknown) =>
      classifyHonestyComprehensionObservation(
        ATLAS_HONESTY_COMPREHENSION_PROTOCOL,
        observation,
      );

    expect(classify({ status: "missing" }).observation_status).toBe("missing");
    expect(
      classify({ status: "unknown", reason_code: "operator_result_unavailable" })
        .observation_status,
    ).toBe("unknown");
    expect(
      classify({ status: "observed", observation_count: 0 }).observation_status,
    ).toBe("zero");
    expect(
      classify({
        status: "incomparable",
        reason_code: "no_admissible_ranking",
      }).observation_status,
    ).toBe("incomparable");
    expect(
      classify({ status: "observed", observation_count: 2 }),
    ).toMatchObject({
      observation_status: "recorded",
      benchmark_status: "not_established",
      stable_bar_effect: "not_established",
      interpretation: "descriptive_only",
      grants_stable: false,
      blocking_permitted: false,
    });
  });
});
