import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import type { z } from "zod";

import type { components } from "./types";
import { quantityValueSchema, runDetailsSchema } from "./validators";

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

describe("runtime API validators", () => {
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
