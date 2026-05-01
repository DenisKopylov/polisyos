import type { DecisionCardViewModel } from "@/lib/domain/decision";
import type { RunEvidenceContext } from "@/lib/domain/evidence";
import type { GovernanceIssueView } from "@/lib/domain/governance";

import type { DisputeRecord } from "./disputes";
import {
  acknowledgeReviewSection,
  buildPublicSectorReadinessSnapshot,
  createDefaultReviewAttentionState,
  markReviewSectionOpened,
  READINESS_SECTIONS,
  type ReviewAttentionState,
} from "./publicSectorReadiness";

const baseDecision: DecisionCardViewModel = {
  confidence: "HIGH",
  diagnosticsBadges: [],
  distributional: {
    breakdowns: [
      {
        dimensionLabel: "Protected attribute",
        rows: [
          {
            cohortLabel: "Reference group",
            direction: "positive",
            isVulnerable: false,
            populationShare: 0.5,
            primaryDelta: 0.2,
          },
          {
            cohortLabel: "Protected group",
            direction: "negative",
            isVulnerable: true,
            populationShare: 0.25,
            primaryDelta: -0.18,
          },
        ],
      },
    ],
    giniAfter: 0.32,
    giniBefore: 0.34,
    giniDelta: -0.02,
    losersCount: 1,
    losersShare: 0.2,
    vulnerableLosersCount: 1,
    winnersCount: 1,
    winnersShare: 0.5,
  },
  generatedAt: "2026-04-01T12:00:00.000Z",
  interventionCount: 1,
  issues: {
    blockedPasses: [],
    blockerCount: 0,
    infoCount: 0,
    warningCount: 0,
  },
  keyMetrics: [
    {
      ciLevel: 0.95,
      ciLower: 0.8,
      ciUpper: 1.6,
      formatted: "+1.20",
      name: "GDP",
      unit: "%",
      value: 1.2,
    },
  ],
  metricComparisons: [],
  metricValidationFamilyAdjustment: null,
  policySummary: "Approve with safeguards.",
  runId: "run-34",
  sourceKind: "decision_packet",
  totalDurationMs: 1200,
  verdict: "APPROVE",
};

const evidenceContext: RunEvidenceContext = {
  dataNeeds: [],
  dataSnapshotRef: null,
  evidenceBundleRef: { artifact_id: "bundle-1", kind: "evidence_bundle" },
  executionPlanRef: null,
  fetchPlans: [],
  inputBindingsRef: null,
  promotionCandidates: [],
  relatedArtifacts: [],
  runId: "run-34",
  sourceKind: "core_run",
  warnings: [],
};

function issue(
  code: string,
  message: string,
  severity: GovernanceIssueView["severity"] = "blocker",
  raw: Record<string, unknown> = {},
): GovernanceIssueView {
  return {
    code,
    durationMs: 12,
    message,
    passId: `${code}-pass`,
    path: null,
    raw,
    severity,
  };
}

function completeReviewState(): ReviewAttentionState {
  return READINESS_SECTIONS.reduce((state, sectionId, index) => {
    const openedAt = `2026-04-01T12:${String(index).padStart(2, "0")}:00.000Z`;
    const acknowledgedAt = `2026-04-01T12:${String(index).padStart(2, "0")}:30.000Z`;
    const opened = markReviewSectionOpened({
      at: openedAt,
      runId: "run-34",
      sectionId,
      state,
    });
    return acknowledgeReviewSection({
      at: acknowledgedAt,
      runId: "run-34",
      sectionId,
      state: opened,
    });
  }, createDefaultReviewAttentionState());
}

describe("public sector readiness domain", () => {
  it("blocks approval through every Phase 3.4 public-sector gate", () => {
    const openDispute: DisputeRecord = {
      actor: "reviewer",
      basis: "legal",
      id: "local:run-34:objection",
      openedAt: "2026-04-01T12:00:00.000Z",
      status: "open",
      target: "decision",
      title: "Unresolved appeal",
    };
    const snapshot = buildPublicSectorReadinessSnapshot({
      decisionView: baseDecision,
      disputes: [openDispute],
      evidenceContext,
      governanceIssues: [
        issue("embargo_active", "Embargoed field is restricted"),
        issue("policy_superseded", "Policy was superseded"),
      ],
      now: "2026-04-01T12:10:00.000Z",
      reviewState: createDefaultReviewAttentionState(),
      runId: "run-34",
    });

    expect(snapshot.approvalReady).toBe(false);
    expect(snapshot.blocks.map((block) => block.kind).sort()).toEqual([
      "embargo",
      "fairness",
      "harm",
      "objection",
      "revocation",
      "slow_review",
    ]);
    expect(snapshot.fairness.sentinel).toMatchObject({
      groupLabel: "Protected group",
      threshold: 0.8,
    });
    expect(snapshot.embargo.masks[0]).toMatchObject({
      reasonCode: "embargo_active",
      status: "active",
    });
    expect(snapshot.auditTrail.map((event) => event.event)).toContain(
      "approval.blocked.embargo",
    );
  });

  it("allows approval after fairness passes, harms are acknowledged, and review attention is complete", () => {
    const fairDecision: DecisionCardViewModel = {
      ...baseDecision,
      distributional: {
        ...baseDecision.distributional!,
        breakdowns: [
          {
            dimensionLabel: "Protected attribute",
            rows: [
              {
                cohortLabel: "Reference group",
                direction: "positive",
                isVulnerable: false,
                populationShare: 0.5,
                primaryDelta: 0.08,
              },
              {
                cohortLabel: "Protected group",
                direction: "positive",
                isVulnerable: true,
                populationShare: 0.25,
                primaryDelta: 0.06,
              },
            ],
          },
        ],
      },
    };
    const snapshot = buildPublicSectorReadinessSnapshot({
      decisionView: fairDecision,
      disputes: [],
      evidenceContext,
      governanceIssues: [],
      now: "2026-04-01T12:10:00.000Z",
      reviewState: completeReviewState(),
      runId: "run-34",
    });

    expect(snapshot.approvalReady).toBe(true);
    expect(snapshot.blocks).toEqual([]);
    expect(snapshot.slowReview.completed).toBe(snapshot.slowReview.total);
    expect(snapshot.harm.blocked).toBe(false);
  });

  it("keeps stakeholder lenses derived from the same decision hash", () => {
    const regulator = buildPublicSectorReadinessSnapshot({
      decisionView: baseDecision,
      evidenceContext,
      governanceIssues: [],
      lens: "regulator",
      reviewState: completeReviewState(),
      runId: "run-34",
    });
    const appellant = buildPublicSectorReadinessSnapshot({
      decisionView: baseDecision,
      evidenceContext,
      governanceIssues: [],
      lens: "appellant",
      reviewState: completeReviewState(),
      runId: "run-34",
    });

    expect(regulator.decisionHash).toBe(appellant.decisionHash);
    expect(regulator.lens.emphasis).not.toEqual(appellant.lens.emphasis);
    expect(regulator.lens.decisionHash).toBe(regulator.decisionHash);
  });

  it("keeps embargoed raw values out of the embargo overlay model", () => {
    const snapshot = buildPublicSectorReadinessSnapshot({
      decisionView: baseDecision,
      evidenceContext: {
        ...evidenceContext,
        warnings: ["embargo private value SSN-123-45-6789"],
      },
      governanceIssues: [
        issue(
          "embargo_SSN-123-45-6789",
          "restricted raw value SSN-123-45-6789",
        ),
      ],
      reviewState: completeReviewState(),
      runId: "run-34",
    });

    expect(snapshot.embargo.blocked).toBe(true);
    expect(JSON.stringify(snapshot.embargo)).not.toContain("SSN-123-45-6789");
  });

  it("blocks fairness approval when protected-group evidence is absent", () => {
    const snapshot = buildPublicSectorReadinessSnapshot({
      decisionView: {
        ...baseDecision,
        distributional: null,
      },
      disputes: [],
      evidenceContext,
      governanceIssues: [],
      reviewState: completeReviewState(),
      runId: "run-34",
    });

    expect(snapshot.fairness.evidenceAvailable).toBe(false);
    expect(snapshot.fairness.blocked).toBe(true);
    expect(snapshot.blocks.map((block) => block.kind)).toContain("fairness");
  });

  it("releases embargo blockers after unlock_at while keeping the skeleton auditable", () => {
    const snapshot = buildPublicSectorReadinessSnapshot({
      decisionView: baseDecision,
      evidenceContext,
      governanceIssues: [
        issue("embargo_active", "restricted until approval", "blocker", {
          unlock_at: "2026-04-01T12:00:00.000Z",
        }),
      ],
      now: "2026-04-01T12:05:00.000Z",
      reviewState: completeReviewState(),
      runId: "run-34",
    });

    expect(snapshot.embargo.blocked).toBe(false);
    expect(snapshot.embargo.masks[0]).toMatchObject({
      reasonCode: "embargo_active",
      status: "clear",
      unlockAt: "2026-04-01T12:00:00.000Z",
    });
    expect(snapshot.blocks.map((block) => block.kind)).not.toContain("embargo");
  });

  it("projects revocation ledger refs from governance metadata", () => {
    const snapshot = buildPublicSectorReadinessSnapshot({
      decisionView: baseDecision,
      evidenceContext,
      governanceIssues: [
        issue("policy_revoked", "policy withdrawn", "blocker", {
          impacted_runs: ["run-34", "run-35"],
          known_at: "2026-04-02T10:00:00.000Z",
          policy_ref: "policy:v3.4",
          predecessor_policy: "policy:v3.3",
          successor_policy: "policy:v3.5",
          valid_at: "2026-04-01T00:00:00.000Z",
        }),
      ],
      reviewState: completeReviewState(),
      runId: "run-34",
    });

    expect(snapshot.revocation.blocked).toBe(true);
    expect(snapshot.revocation.currentStatus).toBe("revoked");
    expect(snapshot.revocation.impactedRuns).toEqual(["run-34", "run-35"]);
    expect(snapshot.revocation.chain.map((entry) => entry.policyRef)).toEqual([
      "policy:v3.3",
      "policy:v3.4",
      "policy:v3.5",
    ]);
  });
});
