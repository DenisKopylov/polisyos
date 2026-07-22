import {
  isGeneratedProjectionAuthority,
  normalizeApiProjectionFailClosed,
  type GeneratedProjectionAuthority,
} from "./projectionFailClosed";

describe("projectionFailClosed", () => {
  it("never infers closeout authority from projection label text", () => {
    const labelOnlyProjection = {
      labels: [
        {
          authority_role: "projection_only",
          label: "publishable",
          source_authority: "display_projection",
          state: "ready",
        },
      ],
      states: ["projection_only", "publishable"],
    };

    expect(isGeneratedProjectionAuthority(labelOnlyProjection)).toBe(false);

    const ownerBacked = {
      authority_role: "projection_only",
      closeout_truth: {
        blockers: [],
        can_closeout: false,
        status: "blocked",
        verdict: "cannot_closeout",
      },
      evidence_class: "runtime_projection",
      generated_at: "2026-07-21T00:00:00Z",
      may_not_be_used_for: ["runtime_closeout_authority"],
      primary_state: "blocked",
      projection_policy: "reads_policy_design_case_only",
      provenance_kind: "runtime_projection",
      states: ["blocked"],
      surface: "runtime_dashboard",
    } satisfies GeneratedProjectionAuthority;

    expect(isGeneratedProjectionAuthority(ownerBacked)).toBe(true);
    expect(normalizeApiProjectionFailClosed(ownerBacked)).toBe(ownerBacked);
  });

  it("fails closed when generated blockers are missing or malformed", () => {
    const authorityCore = {
      authority_role: "projection_only",
      evidence_class: "runtime_projection",
      generated_at: "2026-07-21T00:00:00Z",
      may_not_be_used_for: ["runtime_closeout_authority"],
      primary_state: "blocked",
      projection_policy: "reads_policy_design_case_only",
      provenance_kind: "runtime_projection",
      states: ["blocked"],
      surface: "runtime_dashboard",
    };

    expect(
      isGeneratedProjectionAuthority({
        ...authorityCore,
        closeout_truth: {
          can_closeout: false,
          status: "blocked",
          verdict: "cannot_closeout",
        },
      }),
    ).toBe(false);
    expect(
      isGeneratedProjectionAuthority({
        ...authorityCore,
        closeout_truth: {
          blockers: [
            {
              code: "owner_blocker",
              message: "Owner blocker",
              owner: 42,
            },
          ],
          can_closeout: false,
          status: "blocked",
          verdict: "cannot_closeout",
        },
      }),
    ).toBe(false);
  });
});
