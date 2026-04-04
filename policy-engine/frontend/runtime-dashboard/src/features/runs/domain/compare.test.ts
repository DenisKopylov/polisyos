import { buildAuditTrail, buildRunComparison } from "./compare";

describe("run comparison helpers", () => {
  it("builds comparison rows from two summaries", () => {
    const baseSummary = {
      decisionScore: 0.52,
      blockerCount: 2,
      artifactRefs: [{ artifact_id: "a-1" }],
      evidenceContext: {
        fetchPlans: [{ planId: "p-1" }],
        promotionCandidates: [],
      },
    } as never;
    const targetSummary = {
      decisionScore: 0.74,
      blockerCount: 1,
      artifactRefs: [{ artifact_id: "a-1" }, { artifact_id: "a-2" }],
      evidenceContext: {
        fetchPlans: [{ planId: "p-1" }, { planId: "p-2" }],
        promotionCandidates: [{ promotionId: "pr-1" }],
      },
    } as never;

    expect(buildRunComparison(baseSummary, targetSummary)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: "Decision score", delta: "+0.22" }),
        expect.objectContaining({ label: "Governance blockers", delta: "-1" }),
      ]),
    );
  });

  it("orders audit entries by timestamp and severity source", () => {
    const entries = buildAuditTrail({
      governanceIssues: [
        {
          code: "g-1",
          message: "Blocked",
          severity: "blocker",
          passId: "governance",
          path: null,
          durationMs: null,
          raw: {},
        },
      ],
      errors: [
        {
          code: "err-1",
          message: "Crash",
          source: "trace",
          timestamp: "2026-03-09T10:00:00Z",
          details: {},
          node_alias: null,
        },
      ] as never,
      timelineEvents: [
        {
          index: 1,
          event: "started",
          phase: "prepare",
          timestamp: "2026-03-09T09:00:00Z",
        },
      ] as never,
    });

    expect(entries[0]).toEqual(
      expect.objectContaining({ source: "runtime", severity: "fail" }),
    );
    expect(entries[1]).toEqual(expect.objectContaining({ source: "timeline" }));
    expect(entries[2]).toEqual(
      expect.objectContaining({ source: "governance", severity: "fail" }),
    );
  });
});
