import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";

import { buildSignedPublicDecisionPacket } from "./publicationPacket";
import {
  buildAnnotationTargets,
  buildEvidenceWalletCandidates,
  buildOperatorCraftSnapshot,
  completeReadingOnboardingRun,
  completeReadingOnboardingStep,
  createEvidenceWalletItem,
  createReviewerAnnotation,
  readEvidenceWallet,
  readReadingOnboardingState,
  readReviewerAnnotations,
  readReviewerThresholdProfile,
  saveEvidenceWalletItem,
  saveReviewerAnnotation,
  setReviewerThreshold,
  startReadingOnboarding,
} from "./operatorCraft";

const decisionView: DecisionCardViewModel = {
  confidence: "HIGH",
  diagnosticsBadges: [],
  distributional: {
    breakdowns: [
      {
        dimensionLabel: "Region",
        rows: [
          {
            cohortLabel: "North",
            direction: "positive",
            isVulnerable: false,
            populationShare: 0.4,
            primaryDelta: 0.02,
          },
          {
            cohortLabel: "South",
            direction: "negative",
            isVulnerable: true,
            populationShare: 0.2,
            primaryDelta: -0.04,
          },
        ],
      },
    ],
    giniAfter: 0.31,
    giniBefore: 0.32,
    giniDelta: -0.01,
    losersCount: 1,
    losersShare: 0.2,
    vulnerableLosersCount: 1,
    winnersCount: 1,
    winnersShare: 0.4,
  },
  generatedAt: "2026-04-29T10:00:00.000Z",
  interventionCount: 1,
  issues: {
    blockedPasses: [],
    blockerCount: 0,
    infoCount: 0,
    warningCount: 1,
  },
  keyMetrics: [
    {
      ciLevel: 0.95,
      ciLower: 0.8,
      ciUpper: 1.4,
      formatted: "+1.20",
      name: "GDP Change",
      unit: "%",
      value: 1.2,
    },
  ],
  metricComparisons: [],
  metricValidationFamilyAdjustment: null,
  policySummary: "Approve with safeguards.",
  runId: "run-36",
  sourceKind: "decision_packet",
  totalDurationMs: 900,
  verdict: "APPROVE",
};

const evidenceContext: RunEvidenceContext = {
  dataNeeds: [
    {
      geography: "Kyiv Oblast",
      granularity: "monthly",
      matchedPlanIds: ["plan-public-1"],
      metric: "gdp_change",
      needId: "need-1",
      notes: [],
      purpose: "publication",
      qualityMin: 0.72,
      timeEnd: "2026-12-31",
      timeStart: "2026-01-01",
    },
  ],
  dataSnapshotRef: {
    artifact_id: "snapshot-public",
    kind: "data_snapshot",
  },
  evidenceBundleRef: {
    artifact_id: "bundle-public",
    kind: "evidence_bundle",
  },
  executionPlanRef: null,
  fetchPlans: [],
  inputBindingsRef: {
    artifact_id: "bindings-public",
    kind: "input_bindings",
  },
  promotionCandidates: [],
  relatedArtifacts: [],
  runId: "run-36",
  sourceKind: "core_run",
  warnings: [],
};

function packet() {
  return buildSignedPublicDecisionPacket({
    decisionScore: untracedDecisionQuantity({
      metricId: "test.decision_score",
      point: 0.72,
    }),
    decisionView,
    evidenceContext,
    governanceIssues: [
      {
        code: "warning",
        durationMs: 10,
        message: "requires review",
        passId: "governance",
        path: null,
        raw: {},
        severity: "warning",
      },
    ],
    runId: "run-36",
  });
}

describe("operator craft domain", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("persists a global trust threshold and hides low-confidence claims", () => {
    const signedPacket = packet();
    const profile = setReviewerThreshold({
      next: 0.8,
      now: "2026-04-29T10:10:00.000Z",
      packet: signedPacket,
      runId: "run-36",
    });

    const snapshot = buildOperatorCraftSnapshot({
      packet: signedPacket,
      runId: "run-36",
      thresholdProfile: profile,
    });

    expect(readReviewerThresholdProfile().threshold).toBe(0.8);
    expect(snapshot.thresholdImpact.threshold).toBe(0.8);
    expect(snapshot.thresholdImpact.hiddenCount).toBeGreaterThan(0);
    expect(snapshot.thresholdImpact.remainingShare).toBeLessThan(1);
    expect(profile.auditEvent?.kind).toBe("threshold.changed");
  });

  it("stores annotations against the exact packet snapshot", () => {
    const signedPacket = packet();
    const [target] = buildAnnotationTargets(signedPacket);
    const annotation = createReviewerAnnotation({
      body: "Review this claim before final approval.",
      now: "2026-04-29T10:11:00.000Z",
      packet: signedPacket,
      runId: "run-36",
      target: target!,
    });

    saveReviewerAnnotation(annotation);

    const [stored] = readReviewerAnnotations("run-36");
    expect(stored?.snapshot.packetHash).toBe(signedPacket.packetHash);
    expect(stored?.snapshot.validAt).toBe(decisionView.generatedAt);
    expect(stored?.target.ref).toBe(target?.ref);
    expect(stored?.auditEvent.kind).toBe("annotation.created");
    expect(stored?.auditEvent.route.fullPath).toBe(
      "/runs/run-36/overview?surface=annotation-surface",
    );
  });

  it("deduplicates evidence wallet saves by evidence ref and packet hash", () => {
    const signedPacket = packet();
    const [candidate] = buildEvidenceWalletCandidates(signedPacket);
    const item = createEvidenceWalletItem({
      candidate: candidate!,
      now: "2026-04-29T10:12:00.000Z",
      packet: signedPacket,
      runId: "run-36",
    });

    saveEvidenceWalletItem(item);
    saveEvidenceWalletItem(item);

    expect(readEvidenceWallet()).toHaveLength(1);
    expect(readEvidenceWallet()[0]).toMatchObject({
      auditEvent: { kind: "evidence.saved" },
      ref: candidate?.ref,
      snapshot: { packetHash: signedPacket.packetHash },
    });
  });

  it("measures reading-grade onboarding time to first safe approval", () => {
    const signedPacket = packet();
    startReadingOnboarding({
      now: "2026-04-29T10:00:00.000Z",
      runId: "run-36",
    });

    expect(
      completeReadingOnboardingRun({
        now: "2026-04-29T10:01:00.000Z",
        packet: signedPacket,
        runId: "run-36",
      }).completedAt,
    ).toBeNull();

    for (const stepId of [
      "read_decision",
      "inspect_argument",
      "narrate_provenance",
      "inspect_glossary",
      "set_threshold",
      "save_evidence",
      "annotate_snapshot",
    ] as const) {
      completeReadingOnboardingStep({
        now: "2026-04-29T10:02:00.000Z",
        packet: signedPacket,
        runId: "run-36",
        stepId,
      });
    }

    const state = completeReadingOnboardingRun({
      now: "2026-04-29T10:04:00.000Z",
      packet: signedPacket,
      runId: "run-36",
    });

    expect(state.completedStepIds).toContain("safe_approval");
    expect(state.auditEvents.map((event) => event.kind)).toContain(
      "onboarding.step.completed",
    );
    expect(
      state.auditEvents[state.auditEvents.length - 1]?.route.fullPath,
    ).toBe("/runs/run-36/overview?surface=reading-onboarding");
    expect(state.timeToFirstSafeApprovalSeconds).toBe(240);
    expect(readReadingOnboardingState("run-36").completedAt).toBe(
      "2026-04-29T10:04:00.000Z",
    );
  });
});
