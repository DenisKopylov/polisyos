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

  it("orders audit entries while keeping local presentation out of recorded state", () => {
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
      expect.objectContaining({
        ownerLabel: "err-1",
        recordedState: null,
        source: "runtime",
      }),
    );
    expect(entries.find((entry) => entry.source === "timeline")).toEqual(
      expect.objectContaining({ recordedState: "started" }),
    );
    expect(entries[1]).toEqual(expect.objectContaining({ source: "timeline" }));
    expect(entries[2]).toEqual(
      expect.objectContaining({
        ownerLabel: "blocker",
        recordedState: null,
        source: "governance",
      }),
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
    ).not.toHaveProperty("tone");
  });

  it("keeps owner decision and impact labels opaque without minting a deck recommendation", () => {
    const summary = {
      artifactRefs: [],
      blockerCount: 0,
      decisionHeadline: "Owner-authored headline",
      decisionScore: score(0.93),
      decisionView: {
        confidence: "future_confidence_label",
        generatedAt: "2026-03-09T10:00:00Z",
        verdict: "future_verdict_label",
      },
      evidenceContext: { fetchPlans: [], promotionCandidates: [] },
      governanceIssues: [],
      impactRows: [
        { display: "+2.4 owner units", label: "Owner impact", value: 2.4 },
      ],
      pipeline: { evaluator: { verdict: null } },
      run: {
        run_id: "run-owner-labels",
        source_kind: "core_run",
        status: "future_terminal_label",
      },
      transportStatus: "future_transport_label",
    } as never;

    const report = buildRunReportSnapshot(summary, []);
    const deck = buildRunDeckSnapshot(summary, report);

    expect(report.impactOwnerLabels).toEqual([
      {
        label: "Owner impact",
        ownerLabel: "+2.4 owner units",
      },
    ]);
    expect(report.impactRows).toEqual([]);
    expect(deck.verdict).toMatchObject({
      confidence: "future_confidence_label",
      status: "future_terminal_label",
      verdict: "future_verdict_label",
    });
    expect(
      deck.metrics.cards.find((card) => card.label === "Impact delta"),
    ).toMatchObject({
      kind: "text",
      value: "+2.4 owner units",
    });
    expect(deck.metrics.cards.every((card) => !("tone" in card))).toBe(true);
    expect(
      JSON.stringify({ close: deck.close, tradeoff: deck.tradeoff }),
    ).not.toMatch(/\b(?:ratify|hold|recommendation)\b/iu);
  });

  it("does not promote a run terminal status into a decision verdict", () => {
    const summary = {
      artifactRefs: [],
      blockerCount: 0,
      decisionHeadline: "Unknown owner decision",
      decisionScore: score(null),
      decisionView: null,
      evidenceContext: { fetchPlans: [], promotionCandidates: [] },
      governanceIssues: [],
      impactRows: [],
      pipeline: { evaluator: { verdict: null } },
      run: {
        run_id: "run-status-only",
        source_kind: "core_run",
        status: "completed",
      },
      transportStatus: "live",
    } as never;

    const report = buildRunReportSnapshot(summary, []);

    expect(report.primaryVerdict).toBeNull();
    expect(buildRunDeckSnapshot(summary, report).verdict.verdict).toBe(
      "Unknown",
    );
  });
});
