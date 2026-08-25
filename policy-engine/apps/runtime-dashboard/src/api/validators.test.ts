import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import type { z } from "zod";

import type { components } from "./types";
import {
  humanDecisionGateResponseSchema,
  humanDecisionReviewEffectivenessSchema,
  quantityValueSchema,
  runDetailsSchema,
  runsListSchema,
} from "./validators";
import {
  availableHumanDecisionGate,
  humanDecisionDigest,
  humanDecisionReviewEffectivenessFixture,
} from "@/test/fixtures/humanDecision";

function mutableRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("expected mutable fixture record");
  }
  return value as Record<string, unknown>;
}

type ProjectionFixture = Record<string, unknown> & {
  audience?: components["schemas"]["PolicyDesignCaseProjection"]["audience"];
};

function projectionAuthorityCore(canCloseout: boolean) {
  return {
    authority_role: "projection_only" as const,
    closeout_truth: {
      blocker_codes: [],
      blockers: [],
      can_closeout: canCloseout,
      contested_state: "not_contested",
      limitation_codes: [],
      omission_codes: [],
      status: canCloseout ? "ready" : "blocked",
      verdict: canCloseout ? "can_closeout" : "cannot_closeout",
    },
    evidence_class: "runtime_projection",
    generated_at: "2026-05-19T10:00:00.000Z",
    primary_state: canCloseout ? "publishable" : "projection_only",
    projection_policy: "reads_policy_design_case_only" as const,
    provenance_kind: "runtime_projection" as const,
    states: canCloseout
      ? ["projection_only", "publishable"]
      : ["projection_only"],
    surface: "runtime_dashboard",
  };
}

const projectionMaskingCases = [
  {
    caseId: "missing",
    code: "projection_masked_missing",
    label: "missing evidence label",
  },
  {
    caseId: "stale",
    code: "projection_masked_stale",
    label: "stale evidence label",
  },
  {
    caseId: "conflicting",
    code: "projection_masked_conflicting",
    label: "conflicting evidence label",
  },
  {
    caseId: "reissued",
    code: "projection_masked_reissued",
    label: "reissued evidence label",
  },
  {
    caseId: "withdrawn",
    code: "projection_masked_withdrawn",
    label: "withdrawn evidence label",
  },
  {
    caseId: "non_authoritative",
    code: "projection_masked_non_authoritative",
    label: "non-authoritative evidence label",
  },
  {
    caseId: "projection_only",
    code: "projection_masked_projection_only",
    label: "projection-only evidence label",
  },
] as const;

function runDetailsPayload(label: string) {
  const policyDesignCaseProjection: ProjectionFixture = {
    ...projectionAuthorityCore(false),
    audience: "public",
    labels: [
      {
        authority_role: "projection_only",
        label,
        state: "projection_only",
      },
    ],
    may_not_be_used_for: ["scorecard_authority"],
  };

  return {
    meta: {
      generated_at: "2026-05-19T10:00:00.000Z",
      request_id: "req-projection-mask",
      source_kinds: ["core_run"],
    },
    run: {
      decision_validity_status: undefined as string | null | undefined,
      duration_ms: null,
      finished_at: null,
      has_trace: false,
      has_workflow_report: false,
      operator_diagnostic: {
        authoritative_runtime_state: "blocked",
        downstream_impact: "Projection labels cannot close readiness.",
        first_blocking_cause: "projection_masked",
        next_diagnostic_command: "corepack pnpm test:components",
        owner: "team-runtime-quality",
        phase: "35G.1",
        projection_labels: [
          {
            authority: "projection_only",
            label,
            state: "projection_only",
          },
        ],
        projection_source: "policy_design_case_projection",
      },
      policy_design_case_projection: policyDesignCaseProjection,
      root_artifacts: [],
      run_id: "run-projection-mask",
      source_kind: "core_run",
      started_at: "2026-05-19T09:58:00.000Z",
      status: "failed",
      warnings: [],
    },
    temporal_scope: null,
  };
}

function runsListPayload(runTerminality: string | undefined) {
  return {
    meta: {
      generated_at: "2026-08-21T12:00:00.000Z",
      request_id: "req-ds8-run-terminality",
      source_kinds: ["core_run"],
    },
    page: {
      count: 1,
      cursor: null,
      limit: 50,
      next_cursor: null,
      total: 1,
    },
    runs: [
      {
        run_id: "run-ds8-terminality",
        run_terminality: runTerminality,
        source_kind: "core_run",
        status: "opaque-owner-status",
      },
    ],
  };
}

describe("runtime API validators", () => {
  it.each(["terminal", "non_terminal", "not_established"] as const)(
    "preserves producer-owned run_terminality state %s",
    (runTerminality) => {
      const parsed = runsListSchema.parse(runsListPayload(runTerminality));

      expect(parsed.runs?.[0]?.run_terminality).toBe(runTerminality);
    },
  );

  it("rejects missing or novel run_terminality instead of inferring from status", () => {
    expect(runsListSchema.safeParse(runsListPayload(undefined)).success).toBe(
      false,
    );
    expect(
      runsListSchema.safeParse(runsListPayload("completed-looking")).success,
    ).toBe(false);
  });

  it("matches the canonical quantity output type bidirectionally", () => {
    expectTypeOf<
      z.output<typeof quantityValueSchema>
    >().toEqualTypeOf<QuantityValueOutput>();
    const quantity = canonicalQuantity();
    expect(quantityValueSchema.parse(quantity)).toEqual(quantity);
  });

  it("rejects quantity uncertainty that omits canonical owner fields", () => {
    const quantity = canonicalQuantity();

    expect(
      quantityValueSchema.safeParse({
        ...quantity,
        uncertainty: { ci_95: [40, 44] },
      }).success,
    ).toBe(false);
  });

  it("preserves canonical quantity uncertainty without client defaults", () => {
    const quantity = canonicalQuantity();

    expect(quantityValueSchema.parse(quantity).uncertainty).toEqual({
      ci_95: [40, 44],
      disputed: false,
      identifiability: "estimated",
    });
  });

  it("accepts a canonical quantity whose optional point is absent", () => {
    const { point: _point, ...quantityWithoutPoint } = canonicalQuantity();

    expect(quantityValueSchema.parse(quantityWithoutPoint)).not.toHaveProperty(
      "point",
    );
  });

  it.each(projectionMaskingCases)(
    "preserves producer projection state when labels contain $caseId evidence text",
    ({ label }) => {
      const parsed = runDetailsSchema.parse(runDetailsPayload(label));
      const projection = parsed.run.policy_design_case_projection as Record<
        string,
        unknown
      >;
      const diagnosticLabel =
        parsed.run.operator_diagnostic?.projection_labels?.[0];

      expect(projection.primary_state).toBe("projection_only");
      expect(projection.states).toEqual(["projection_only"]);
      expect(projection).not.toHaveProperty("fail_closed_codes");
      expect(diagnosticLabel).toMatchObject({
        authority: "projection_only",
        label,
        state: "projection_only",
      });
    },
  );

  it("preserves generated decision validity and rejects an unknown local substitute", () => {
    const payload = runDetailsPayload("projection only");
    payload.run.decision_validity_status = "review_required";

    expect(runDetailsSchema.parse(payload).run.decision_validity_status).toBe(
      "review_required",
    );

    payload.run.decision_validity_status = "replacement";
    expect(runDetailsSchema.safeParse(payload).success).toBe(false);
  });

  it("rejects a projection when generated closeout truth is missing", () => {
    const payload = runDetailsPayload("publishable");
    payload.run.policy_design_case_projection = {
      audience: "public",
      authority_role: "projection_only",
      closeout_truth: {
        status: "ready",
        verdict: "can_closeout",
        can_closeout: null,
      },
      labels: [
        {
          authority_role: "projection_only",
          label: "publishable",
          state: "publishable",
        },
      ],
      may_not_be_used_for: ["scorecard_authority"],
      primary_state: "publishable",
      projection_policy: "reads_policy_design_case_only",
      states: ["publishable", "projection_only"],
    };

    expect(runDetailsSchema.safeParse(payload).success).toBe(false);
  });

  it("preserves generated projection blockers and rejects malformed blocker fields", () => {
    const payload = runDetailsPayload("projection only");
    const projection = payload.run.policy_design_case_projection as {
      closeout_truth: Record<string, unknown>;
    };
    projection.closeout_truth.blockers = [
      {
        code: "future_owner_blocker",
        message: "Owner-supplied blocker message",
        owner: "future-owner",
        severity: "future-owner-severity",
      },
    ];

    expect(
      runDetailsSchema.parse(payload).run.policy_design_case_projection
        ?.closeout_truth.blockers,
    ).toEqual(projection.closeout_truth.blockers);

    projection.closeout_truth.blockers = [
      {
        code: "future_owner_blocker",
        message: "Owner-supplied blocker message",
        owner: 42,
      },
    ];
    expect(runDetailsSchema.safeParse(payload).success).toBe(false);
  });

  it("does not replace producer closeout truth from participation label text", () => {
    const payload = runDetailsPayload("projection only");
    payload.run.policy_design_case_projection = {
      ...projectionAuthorityCore(true),
      audience: "public",
      labels: [
        {
          authority_role: "projection_only",
          label: "projection only",
          state: "projection_only",
        },
      ],
      may_not_be_used_for: ["scorecard_authority"],
      participation_requirements: [
        {
          claim_id: "claim-preference",
          claim_use_requested: "prevalence",
          claim_use_allowed: "prevalence",
          source_kind: "llm_speculation",
          representativeness_class: "unknown",
          public_projection_effect: "supports_claim",
        },
      ],
    };

    const parsed = runDetailsSchema.parse(payload);
    const projection = parsed.run.policy_design_case_projection as Record<
      string,
      unknown
    >;

    expect(projection.closeout_truth).toMatchObject({
      can_closeout: true,
      status: "ready",
      verdict: "can_closeout",
    });
    expect(projection.primary_state).toBe("publishable");
    expect(projection).not.toHaveProperty("fail_closed_codes");
  });

  it("rejects human-decision gate semantic counterexamples", () => {
    expect(
      humanDecisionGateResponseSchema.safeParse(availableHumanDecisionGate())
        .success,
    ).toBe(true);

    const counterexamples: Array<() => unknown> = [
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.reasons = [
          {
            code: "DS9-DECISION-PRODUCER-MISSING",
            message: "Missing producer",
            status: "producer_missing",
          },
        ];
        candidate.reason_codes = ["DS9-DECISION-PRODUCER-MISSING"];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.contestability = {
          ...candidate.contestability!,
          case_id: "case.other",
        };
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        const selector = mutableRecord(candidate.submission?.selector);
        selector.basis_digest = humanDecisionDigest("8");
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        const continuation = mutableRecord(candidate.continuation);
        continuation.action_kind = "search";
        const selector = mutableRecord(candidate.submission?.selector);
        selector.action_kind = "search";
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.submission!.allowed_decisions = [
          ...candidate.submission!.allowed_decisions,
          { action: "escalate", decision_modes: ["ordinary"] },
        ];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.submission!.allowed_decisions[0]!.decision_modes = [
          "blocking",
        ];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.submission!.allowed_decisions = [
          candidate.submission!.allowed_decisions[0]!,
          candidate.submission!.allowed_decisions[0]!,
        ];
        candidate.decision_request!.available_actions = ["approve", "approve"];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.submission!.allowed_decisions = [];
        candidate.decision_request!.available_actions = [];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.decision_request!.five_rights_binding.required_role =
          "principal";
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.decision_request!.five_rights_binding.decision_rights_matrix_ref =
          "pdc://s7/other-rights";
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.exposure.required_artifact_digests[1] =
          humanDecisionDigest("6");
        candidate.exposure.completed_artifact_digests[1] =
          humanDecisionDigest("6");
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.exposure.channel = "governed_review";
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.exposure.completed_artifact_digests = [];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.exposure.completed_artifact_digests.push(
          humanDecisionDigest("6"),
        );
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.mandate = null;
        return candidate;
      },
    ];

    for (const counterexample of counterexamples) {
      expect(
        humanDecisionGateResponseSchema.safeParse(counterexample()).success,
      ).toBe(false);
    }

    const repeated = structuredClone(availableHumanDecisionGate());
    repeated.decision_request!.five_rights_binding.required_information_refs = [
      repeated.exposure.required_artifact_digests[1]!,
      repeated.exposure.required_artifact_digests[1]!,
    ];
    repeated.exposure.required_artifact_digests.push(
      repeated.exposure.required_artifact_digests[1]!,
    );
    repeated.exposure.completed_artifact_digests.push(
      repeated.exposure.completed_artifact_digests[1]!,
    );
    expect(humanDecisionGateResponseSchema.safeParse(repeated).success).toBe(
      true,
    );
  });

  it.each(["Bad action", "a".repeat(121)])(
    "rejects PA2 action_kind outside the signed action grammar: %s",
    (actionKind) => {
      const candidate = structuredClone(availableHumanDecisionGate());
      mutableRecord(candidate.continuation).action_kind = actionKind;
      mutableRecord(candidate.submission?.selector).action_kind = actionKind;
      candidate.mandate!.action_kind = actionKind;

      expect(humanDecisionGateResponseSchema.safeParse(candidate).success).toBe(
        false,
      );
    },
  );

  it("rejects a production selector whose source and basis refs are not one signed CAS ref", () => {
    const basisRef = humanDecisionDigest("b");
    const productionCandidate = () => {
      const candidate = structuredClone(
        availableHumanDecisionGate(),
      ) as unknown as Record<string, unknown>;
      candidate.source_kind = "production_approval";
      candidate.source_ref = basisRef;
      mutableRecord(candidate.contestability).source_ref = basisRef;
      const continuation = mutableRecord(candidate.continuation);
      continuation.source_kind = "production_approval";
      continuation.source_ref = basisRef;
      continuation.basis_ref = basisRef;
      continuation.basis_digest = basisRef;
      delete continuation.action_kind;
      mutableRecord(candidate.submission).selector =
        structuredClone(continuation);
      return candidate;
    };

    expect(
      humanDecisionGateResponseSchema.safeParse(productionCandidate()).success,
    ).toBe(true);

    for (const changedField of ["basis_ref", "basis_digest"] as const) {
      const candidate = productionCandidate();
      const continuation = mutableRecord(candidate.continuation);
      continuation[changedField] = humanDecisionDigest("8");
      mutableRecord(candidate.submission).selector =
        structuredClone(continuation);

      expect(humanDecisionGateResponseSchema.safeParse(candidate).success).toBe(
        false,
      );
    }
  });

  it("rejects review-effectiveness reconciliation counterexamples", () => {
    expect(
      humanDecisionReviewEffectivenessSchema.safeParse(
        humanDecisionReviewEffectivenessFixture(),
      ).success,
    ).toBe(true);

    const counterexamples: Array<() => unknown> = [
      () =>
        humanDecisionReviewEffectivenessFixture({
          authoritative_for: ["review_effectiveness_measurement"],
        }),
      () =>
        humanDecisionReviewEffectivenessFixture({
          completed_human_decision_count: 0,
          exact_join_count: 1,
        }),
      () =>
        humanDecisionReviewEffectivenessFixture({
          coverage_status: "complete",
        }),
      () =>
        humanDecisionReviewEffectivenessFixture({
          review_count: 1,
          review_time_not_established_count: 1,
        }),
      () =>
        humanDecisionReviewEffectivenessFixture({
          reviewer_independence_rate: 1.01,
        }),
    ];

    for (const counterexample of counterexamples) {
      expect(
        humanDecisionReviewEffectivenessSchema.safeParse(counterexample())
          .success,
      ).toBe(false);
    }
  });
});

function canonicalQuantity() {
  return {
    lineage: {
      freshness: "current" as const,
      id: "lineage:decision-score",
      status: "verified" as const,
    },
    metric_id: "decision-score",
    point: 42,
    quantity_class: "decision" as const,
    time: null,
    uncertainty: {
      ci_95: [40, 44] as [number, number],
      disputed: false,
      identifiability: "estimated" as const,
    },
    unit: { code: "score", system: "unit" },
  };
}
