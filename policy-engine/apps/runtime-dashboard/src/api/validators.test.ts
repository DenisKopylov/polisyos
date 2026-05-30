import { runDetailsSchema } from "./validators";

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
  return {
    meta: {
      generated_at: "2026-05-19T10:00:00.000Z",
      request_id: "req-projection-mask",
      source_kinds: ["core_run"],
    },
    run: {
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
      policy_design_case_projection: {
        authority_role: "projection_only",
        labels: [
          {
            authority_role: "projection_only",
            label,
            state: "projection_only",
          },
        ],
        may_not_be_used_for: ["scorecard_authority"],
        primary_state: "projection_only",
        projection_policy: "reads_policy_design_case_only",
        states: ["projection_only"],
      },
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
  it.each(projectionMaskingCases)(
    "fails closed at the API boundary when projection labels mask $caseId evidence",
    ({ code, label }) => {
      const parsed = runDetailsSchema.parse(runDetailsPayload(label));
      const projection = parsed.run.policy_design_case_projection as Record<
        string,
        unknown
      >;
      const diagnosticLabel =
        parsed.run.operator_diagnostic?.projection_labels?.[0];

      expect(projection.primary_state).toBe("blocked");
      expect(projection.states).toEqual(["projection_only", "blocked"]);
      expect(projection.fail_closed_codes).toContain(code);
      expect(projection.may_not_be_used_for).toEqual(
        expect.arrayContaining([
          "runtime_closeout_authority",
          "scorecard_authority",
        ]),
      );
      expect(diagnosticLabel).toMatchObject({
        authority: "projection_only",
        label: "blocked projection",
        state: "blocked",
      });
    },
  );

  it("fails closed when dashboard projection closeout truth is missing", () => {
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

    const parsed = runDetailsSchema.parse(payload);
    const projection = parsed.run.policy_design_case_projection as Record<
      string,
      unknown
    >;

    expect(projection.primary_state).toBe("blocked");
    expect(projection.fail_closed_codes).toContain(
      "projection_closeout_truth_missing",
    );
    expect(projection.closeout_truth).toMatchObject({
      can_closeout: false,
      status: "blocked",
      verdict: "cannot_closeout",
    });
    expect(projection.may_not_be_used_for).toEqual(
      expect.arrayContaining([
        "runtime_closeout_authority",
        "scorecard_authority",
      ]),
    );
  });

  it("fails closed when participation projection launders speculative prevalence", () => {
    const payload = runDetailsPayload("projection only");
    payload.run.policy_design_case_projection = {
      audience: "public",
      authority_role: "projection_only",
      closeout_truth: {
        blocker_codes: [],
        blockers: [],
        can_closeout: true,
        contested_state: "not_contested",
        limitation_codes: [],
        omission_codes: [],
        status: "ready",
        verdict: "can_closeout",
      },
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
      primary_state: "projection_only",
      projection_policy: "reads_policy_design_case_only",
      states: ["projection_only"],
    };

    const parsed = runDetailsSchema.parse(payload);
    const projection = parsed.run.policy_design_case_projection as Record<
      string,
      unknown
    >;

    expect(projection.primary_state).toBe("blocked");
    expect(projection.fail_closed_codes).toContain(
      "participation_projection_authority_leak",
    );
    expect(projection.may_not_be_used_for).toEqual(
      expect.arrayContaining([
        "participation_authority",
        "runtime_closeout_authority",
        "scorecard_authority",
      ]),
    );
  });
});
