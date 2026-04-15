import { renderHook } from "@testing-library/react";

const {
  findRunEvidenceNeedMock,
  findRunEvidencePlanMock,
  findRunEvidencePromotionMock,
  isRuntimeApiNotFoundMock,
  normalizeGovernanceIssuesMock,
  normalizeRunEvidenceContextMock,
  parseDecisionCardPayloadMock,
  summarizeGovernanceIssuesMock,
  useArtifactContentMock,
  useGovernanceDebugMock,
  useRunAgentsMock,
  useRunDetailsMock,
  useRunEvidenceContextMock,
} = vi.hoisted(() => ({
  findRunEvidenceNeedMock: vi.fn(),
  findRunEvidencePlanMock: vi.fn(),
  findRunEvidencePromotionMock: vi.fn(),
  isRuntimeApiNotFoundMock: vi.fn(),
  normalizeGovernanceIssuesMock: vi.fn(),
  normalizeRunEvidenceContextMock: vi.fn(),
  parseDecisionCardPayloadMock: vi.fn(),
  summarizeGovernanceIssuesMock: vi.fn(),
  useArtifactContentMock: vi.fn(),
  useGovernanceDebugMock: vi.fn(),
  useRunAgentsMock: vi.fn(),
  useRunDetailsMock: vi.fn(),
  useRunEvidenceContextMock: vi.fn(),
}));

vi.mock("@/api/hooks/useArtifactContent", () => ({
  useArtifactContent: (...args: unknown[]) => useArtifactContentMock(...args),
}));

vi.mock("@/api/hooks/useGovernanceDebug", () => ({
  useGovernanceDebug: (...args: unknown[]) => useGovernanceDebugMock(...args),
}));

vi.mock("@/api/http", () => ({
  isRuntimeApiNotFound: (error: unknown) => isRuntimeApiNotFoundMock(error),
}));

vi.mock("@/api/hooks/useRunAgents", () => ({
  useRunAgents: (...args: unknown[]) => useRunAgentsMock(...args),
}));

vi.mock("@/api/hooks/useRunDetails", () => ({
  useRunDetails: (...args: unknown[]) => useRunDetailsMock(...args),
}));

vi.mock("@/api/hooks/useRunEvidenceContext", () => ({
  useRunEvidenceContext: (...args: unknown[]) =>
    useRunEvidenceContextMock(...args),
}));

vi.mock("@/lib/domain/evidence", () => ({
  findRunEvidenceNeed: (...args: unknown[]) => findRunEvidenceNeedMock(...args),
  findRunEvidencePlan: (...args: unknown[]) => findRunEvidencePlanMock(...args),
  findRunEvidencePromotion: (...args: unknown[]) =>
    findRunEvidencePromotionMock(...args),
  normalizeRunEvidenceContext: (...args: unknown[]) =>
    normalizeRunEvidenceContextMock(...args),
}));

vi.mock("@/lib/domain/decision", () => ({
  parseDecisionCardPayload: (...args: unknown[]) =>
    parseDecisionCardPayloadMock(...args),
}));

vi.mock("@/lib/domain/governance", () => ({
  normalizeGovernanceIssues: (...args: unknown[]) =>
    normalizeGovernanceIssuesMock(...args),
  summarizeGovernanceIssues: (...args: unknown[]) =>
    summarizeGovernanceIssuesMock(...args),
}));

import {
  buildEvidenceHref,
  getDecisionHeadline,
  LEGACY_RUN_DETAIL_TAB_MAP,
  RUN_DETAIL_TABS,
  useRunDetailSummary,
} from "@/features/runs/routes/useRunDetailSummary";

describe("useRunDetailSummary", () => {
  const t = (path: string) => path;

  beforeEach(() => {
    findRunEvidenceNeedMock.mockReset();
    findRunEvidenceNeedMock.mockReturnValue(null);
    findRunEvidencePlanMock.mockReset();
    findRunEvidencePlanMock.mockReturnValue(null);
    findRunEvidencePromotionMock.mockReset();
    findRunEvidencePromotionMock.mockReturnValue(null);
    isRuntimeApiNotFoundMock.mockReset();
    isRuntimeApiNotFoundMock.mockReturnValue(false);
    normalizeGovernanceIssuesMock.mockReset();
    normalizeGovernanceIssuesMock.mockReturnValue([]);
    normalizeRunEvidenceContextMock.mockReset();
    normalizeRunEvidenceContextMock.mockReturnValue(null);
    parseDecisionCardPayloadMock.mockReset();
    parseDecisionCardPayloadMock.mockReturnValue(null);
    summarizeGovernanceIssuesMock.mockReset();
    summarizeGovernanceIssuesMock.mockReturnValue({ blocker: 0 });
    useArtifactContentMock.mockReset();
    useArtifactContentMock.mockReturnValue({
      data: undefined,
      error: null,
      isError: false,
      isLoading: false,
    });
    useGovernanceDebugMock.mockReset();
    useGovernanceDebugMock.mockReturnValue({
      data: undefined,
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunAgentsMock.mockReset();
    useRunAgentsMock.mockReturnValue({
      data: undefined,
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunDetailsMock.mockReset();
    useRunDetailsMock.mockReturnValue({
      data: undefined,
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunEvidenceContextMock.mockReset();
    useRunEvidenceContextMock.mockReturnValue({
      data: undefined,
      error: null,
      isError: false,
      isLoading: false,
    });
  });

  it("exports stable tabs, legacy mappings, and helper builders", () => {
    expect(RUN_DETAIL_TABS).toEqual([
      "overview",
      "causal",
      "governance",
      "evidence",
      "workflow",
      "artifacts",
      "agents",
      "debug",
    ]);
    expect(LEGACY_RUN_DETAIL_TAB_MAP).toMatchObject({
      decision: "overview",
      models: "agents",
      timeline: "debug",
    });
    expect(
      buildEvidenceHref("run-1", "promotion", {
        artifactId: "",
        promotionId: "promotion-1",
      }),
    ).toBe("/evidence?runId=run-1&focus=promotion&promotionId=promotion-1");
    expect(getDecisionHeadline("APPROVE", 0, t)).toBe(
      "pages.runs.verdict.approve",
    );
    expect(getDecisionHeadline("APPROVE", 2, t)).toBe(
      "pages.runs.verdict.approveWithConditions",
    );
    expect(getDecisionHeadline("REJECT", 0, t)).toBe(
      "pages.runs.verdict.reject",
    );
    expect(getDecisionHeadline("REPLAN", 0, t)).toBe(
      "pages.runs.verdict.replan",
    );
    expect(getDecisionHeadline(undefined, 1, t)).toBe(
      "pages.runs.verdict.escalate",
    );
    expect(getDecisionHeadline(undefined, 0, t)).toBe(
      "pages.runs.verdict.inReview",
    );
  });

  it("keeps the summary in bootstrap mode while run details are still unavailable", () => {
    useRunDetailsMock.mockReturnValue({
      data: undefined,
      error: new Error("not found"),
      isError: true,
      isLoading: false,
    });
    isRuntimeApiNotFoundMock.mockReturnValue(true);

    const { result } = renderHook(() =>
      useRunDetailSummary("run-1", t, { liveTransport: true }),
    );

    expect(useRunDetailsMock).toHaveBeenCalledWith("run-1", {
      liveTransport: true,
    });
    expect(useRunAgentsMock).toHaveBeenCalledWith("run-1", false);
    expect(useGovernanceDebugMock).toHaveBeenCalledWith("run-1", false);
    expect(useRunEvidenceContextMock).toHaveBeenCalledWith("run-1", false);
    expect(useArtifactContentMock).toHaveBeenCalledWith(undefined, {
      enabled: false,
      maxBytes: 262144,
    });
    expect(result.current.runBootstrapPending).toBe(true);
    expect(result.current.runReady).toBe(false);
    expect(result.current.artifactRefs).toEqual([]);
    expect(result.current.blockerCount).toBe(0);
    expect(result.current.decisionScore).toBe(0.52);
    expect(result.current.transportStatus).toBe("not_available");
    expect(result.current.primaryDecisionArtifactId).toBeNull();
  });

  it("builds a rich summary with deduped artifacts, evidence links, and fallback scoring", () => {
    useRunDetailsMock.mockReturnValue({
      data: {
        run: {
          root_artifacts: [
            { artifact_id: "artifact-3", kind: "decision_card" },
            { artifact_id: "artifact-root", kind: "timeline" },
          ],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunAgentsMock.mockReturnValue({
      data: {
        pipeline: {
          decision_packet_ref: {
            artifact_id: "artifact-3",
            kind: "decision_card",
          },
          execution_plan_ref: { artifact_id: "artifact-plan", kind: "plan" },
          evaluator: {
            report_ref: { artifact_id: "artifact-eval", kind: "report" },
            scores: {},
            verdict: "APPROVE",
          },
          preflight: {
            report_ref: { artifact_id: "artifact-preflight", kind: "report" },
          },
          reproducibility: {
            manifest_ref: { artifact_id: "artifact-repro", kind: "manifest" },
          },
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useGovernanceDebugMock.mockReturnValue({
      data: {
        debug: {
          issue_summary: { blocker_count: 1 },
          issues: [{ severity: "raw" }],
          report_ref: {
            artifact_id: "artifact-governance",
            kind: "governance_report",
          },
          transport_summary: {
            status: { state: "degraded" },
          },
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunEvidenceContextMock.mockReturnValue({
      data: {
        context: {
          source: "raw",
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    normalizeRunEvidenceContextMock.mockReturnValue({
      dataNeeds: [{ needId: "need-1" }],
      dataSnapshotRef: { artifact_id: "artifact-snapshot", kind: "snapshot" },
      evidenceBundleRef: { artifact_id: "artifact-bundle", kind: "bundle" },
      executionPlanRef: { artifact_id: "artifact-plan", kind: "plan" },
      fetchPlans: [{ planId: "plan-1" }],
      inputBindingsRef: { artifact_id: "artifact-inputs", kind: "bindings" },
      promotionCandidates: [{ promotionId: "promotion-1" }],
      relatedArtifacts: [
        { artifact_id: "artifact-2", kind: "dataset" },
        { artifact_id: "artifact-3", kind: "decision_card" },
      ],
    });
    normalizeGovernanceIssuesMock.mockReturnValue([
      { id: "blocker-1", severity: "blocker" },
      { id: "warning-1", severity: "warning" },
    ]);
    summarizeGovernanceIssuesMock.mockReturnValue({ blocker: 2 });
    useArtifactContentMock.mockReturnValue({
      data: {
        artifact: {
          artifact_id: "artifact-3",
          preview: { kind: "decision-card" },
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    parseDecisionCardPayloadMock.mockReturnValue({
      confidence: "HIGH",
      distributional: {
        breakdowns: [
          {
            rows: [{ cohortLabel: "Adults", primaryDelta: 1.5 }],
          },
        ],
      },
      keyMetrics: [{ formatted: "10", name: "Unused", unit: "%", value: 10 }],
      verdict: null,
    });
    findRunEvidenceNeedMock.mockReturnValue({ needId: "need-1" });
    findRunEvidencePlanMock.mockReturnValue({ planId: "plan-1" });
    findRunEvidencePromotionMock.mockReturnValue({
      promotionId: "promotion-1",
    });

    const { result } = renderHook(() => useRunDetailSummary("run-1", t));

    expect(useArtifactContentMock).toHaveBeenCalledWith("artifact-3", {
      enabled: true,
      maxBytes: 262144,
    });
    expect(result.current.artifactRefs.map((ref) => ref.artifact_id)).toEqual([
      "artifact-3",
      "artifact-plan",
      "artifact-preflight",
      "artifact-eval",
      "artifact-repro",
      "artifact-governance",
      "artifact-bundle",
      "artifact-snapshot",
      "artifact-inputs",
      "artifact-2",
      "artifact-root",
    ]);
    expect(result.current.primaryDecisionArtifactId).toBe("artifact-3");
    expect(result.current.blockerCount).toBe(2);
    expect(result.current.decisionHeadline).toBe(
      "pages.runs.verdict.approveWithConditions",
    );
    expect(result.current.decisionScore).toBe(0.84);
    expect(result.current.decisionScoreStyle).toMatchObject({
      "--score-angle": "284deg",
    });
    expect(result.current.impactRows).toEqual([
      {
        display: "+1.5",
        label: "Adults",
        value: 1.5,
      },
    ]);
    expect(result.current.primaryIssue).toEqual({
      id: "blocker-1",
      severity: "blocker",
    });
    expect(result.current.selectedNeed).toEqual({ needId: "need-1" });
    expect(result.current.selectedPlan).toEqual({ planId: "plan-1" });
    expect(result.current.selectedPromotion).toEqual({
      promotionId: "promotion-1",
    });
    expect(result.current.transportStatus).toBe("[object Object]");
  });

  it("falls back to key metrics and clamps explicit evaluator scores", () => {
    useRunDetailsMock.mockReturnValue({
      data: {
        run: {
          root_artifacts: [{ artifact_id: "artifact-root", kind: "report" }],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunAgentsMock.mockReturnValue({
      data: {
        pipeline: {
          evaluator: {
            scores: { total_score: 2 },
            verdict: "REJECT",
          },
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useGovernanceDebugMock.mockReturnValue({
      data: {
        debug: {
          issue_summary: { blocker_count: 0 },
          issues: [],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    parseDecisionCardPayloadMock.mockReturnValue({
      confidence: "LOW",
      distributional: {
        breakdowns: [{ rows: [] }],
      },
      keyMetrics: [{ formatted: "99", name: "Latency", unit: "ms", value: 99 }],
      verdict: "REJECT",
    });

    const { result } = renderHook(() => useRunDetailSummary("run-2", t));

    expect(result.current.decisionHeadline).toBe("pages.runs.verdict.reject");
    expect(result.current.decisionScore).toBe(1);
    expect(result.current.impactRows).toEqual([
      {
        display: "99ms",
        label: "Latency",
        value: 99,
      },
    ]);
  });
});
