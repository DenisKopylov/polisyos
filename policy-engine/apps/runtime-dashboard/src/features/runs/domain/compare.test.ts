import {
  buildAuditTrail,
  buildRunComparison,
  buildRunDeckSnapshot,
  buildRunReportSnapshot,
} from "./compare";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";

const score = (point: number | null) =>
  untracedDecisionQuantity({ metricId: "test.decision_score", point });

describe("run comparison helpers", () => {
  it("builds comparison rows from two summaries", () => {
    const baseSummary = {
      decisionScore: score(0.52),
      blockerCount: 2,
      artifactRefs: [{ artifact_id: "a-1" }],
      evidenceContext: {
        fetchPlans: [{ planId: "p-1" }],
        promotionCandidates: [],
      },
    } as never;
    const targetSummary = {
      decisionScore: score(0.74),
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

  it("builds typed report and deck snapshots from a run summary", () => {
    const summary = {
      artifactRefs: [{ artifact_id: "artifact-1", kind: "decision_card" }],
      blockerCount: 1,
      decisionHeadline: "Approve with conditions",
      decisionScore: score(0.81),
      decisionView: {
        confidence: "HIGH",
        verdict: "APPROVE",
      },
      evidenceContext: {
        fetchPlans: [{ planId: "plan-1" }],
        promotionCandidates: [{ promotionId: "promotion-1" }],
      },
      governanceIssues: [],
      impactRows: [{ display: "+2.4", label: "Coverage", value: 2.4 }],
      pipeline: {
        evaluator: { verdict: "APPROVE" },
      },
      primaryIssue: { message: "Pending legal confirmation" },
      run: {
        run_id: "run-1",
        source_kind: "core_run",
        status: "completed",
      },
      selectedNeed: {
        granularity: "monthly",
        metric: "Inflation",
        needId: "need-1",
        timeEnd: "2025",
        timeStart: "2022",
      },
      selectedPlan: {
        connectorId: "world-bank",
        datasetId: "inflation",
        matchedNeedIds: ["need-1"],
        planId: "plan-1",
        sourceLane: "core",
      },
      selectedPromotion: {
        confidence: 0.82,
        connectorId: "world-bank",
        datasetId: "inflation",
        promotionId: "promotion-1",
        sourceLane: "promotion",
        status: "pending",
      },
      transportStatus: "live",
    } as never;

    const report = buildRunReportSnapshot(summary, []);
    const deck = buildRunDeckSnapshot(summary, report);

    expect(report).toMatchObject({
      decisionConfidence: "HIGH",
      mainUncertainty: "Pending legal confirmation",
      primaryVerdict: "APPROVE",
      runId: "run-1",
    });
    expect(deck.cover.title).toContain("run-1");
    expect(deck.metrics.cards).toHaveLength(4);
    expect(deck.evidence.provenance).toContain("world-bank");

    const unknownReport = buildRunReportSnapshot(
      {
        ...(summary as unknown as Record<string, unknown>),
        decisionScore: score(null),
      } as never,
      [],
    );
    const unknownDeck = buildRunDeckSnapshot(
      {
        ...(summary as unknown as Record<string, unknown>),
        decisionScore: score(null),
      } as never,
      unknownReport,
    );
    expect(
      unknownDeck.metrics.cards.find((card) => card.label === "Decision score"),
    ).toMatchObject({ tone: "neutral" });
  });
});
