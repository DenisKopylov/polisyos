import type { DecisionCardViewModel } from "@/shared/lib/domain/decision";
import type { RunEvidenceContext } from "@/shared/lib/domain/evidence";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";
import {
  epochNonreceipt,
  type EpochSemantics,
} from "@/shared/ui/temporal/TimeSemanticsLabel";

import {
  buildSignedPublicDecisionPacket as buildSignedPublicDecisionPacketRaw,
  type PublicDecisionPacketInput,
} from "./publicationPacket";
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
import type { AuthorityLocalScope } from "@/app/offline/authorityLocalState";

type PacketTestInput = Omit<PublicDecisionPacketInput, "epochSemantics"> & {
  epochSemantics?: EpochSemantics;
};

function buildSignedPublicDecisionPacket(input: PacketTestInput) {
  return buildSignedPublicDecisionPacketRaw({
    ...input,
    epochSemantics: input.epochSemantics ?? epochNonreceipt(),
  });
}

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

const verifiedScope: AuthorityLocalScope = {
  tenantId: "tenant-operator",
  userId: "reviewer-operator",
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

  it("persists a global trust threshold without inventing numeric confidence", () => {
    const signedPacket = packet();
    const profile = setReviewerThreshold({
      next: 0.8,
      now: "2026-04-29T10:10:00.000Z",
      packet: signedPacket,
      runId: "run-36",
      scope: verifiedScope,
    });

    const snapshot = buildOperatorCraftSnapshot({
      packet: signedPacket,
      runId: "run-36",
      thresholdProfile: profile,
    });

    expect(readReviewerThresholdProfile(verifiedScope).threshold).toBe(0.8);
    expect(snapshot.thresholdImpact.threshold).toBe(0.8);
    expect(snapshot.thresholdImpact.hiddenCount).toBe(0);
    expect(snapshot.thresholdImpact.remainingShare).toBe(1);
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

    saveReviewerAnnotation(annotation, verifiedScope);

    const [stored] = readReviewerAnnotations("run-36", verifiedScope);
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

    saveEvidenceWalletItem(item, verifiedScope);
    saveEvidenceWalletItem(item, verifiedScope);

    expect(readEvidenceWallet(verifiedScope)).toHaveLength(1);
    expect(readEvidenceWallet(verifiedScope)[0]).toMatchObject({
      auditEvent: { kind: "evidence.saved" },
      ref: candidate?.ref,
      snapshot: { packetHash: signedPacket.packetHash },
    });
  });

  it("records checklist completion without creating an approval gate", () => {
    const signedPacket = packet();
    startReadingOnboarding({
      now: "2026-04-29T10:00:00.000Z",
      runId: "run-36",
      scope: verifiedScope,
    });

    expect(
      completeReadingOnboardingRun({
        now: "2026-04-29T10:01:00.000Z",
        packet: signedPacket,
        runId: "run-36",
        scope: verifiedScope,
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
        scope: verifiedScope,
        stepId,
      });
    }

    const state = completeReadingOnboardingRun({
      now: "2026-04-29T10:04:00.000Z",
      packet: signedPacket,
      runId: "run-36",
      scope: verifiedScope,
    });

    expect(state.completedStepIds).toContain("checklist_complete");
    expect(state.completedStepIds).not.toContain("safe_approval");
    expect(state.auditEvents.map((event) => event.kind)).toContain(
      "onboarding.step.completed",
    );
    expect(
      state.auditEvents[state.auditEvents.length - 1]?.route.fullPath,
    ).toBe("/runs/run-36/overview?surface=reading-onboarding");
    expect(state).toMatchObject({
      firstCompletionAt: "2026-04-29T10:04:00.000Z",
      timeToCompletionSeconds: 240,
    });
    expect(
      readReadingOnboardingState("run-36", verifiedScope).completedAt,
    ).toBe("2026-04-29T10:04:00.000Z");
  });

  it("exposes checklist readiness only as interaction completion state", () => {
    const snapshot = buildOperatorCraftSnapshot({
      packet: packet(),
      runId: "run-36",
    });

    expect(snapshot.onboarding).toMatchObject({ canComplete: false });
    expect(snapshot.onboarding).not.toHaveProperty("canApprove");
    expect(JSON.stringify(snapshot.onboarding)).not.toMatch(/approval/iu);
  });

  it("partitions every operator-craft family through a verified scoped envelope", () => {
    const signedPacket = packet();
    const [target] = buildAnnotationTargets(signedPacket);
    const [candidate] = buildEvidenceWalletCandidates(signedPacket);
    const annotation = createReviewerAnnotation({
      body: "Scope-bound note.",
      now: "2026-04-29T10:11:00.000Z",
      packet: signedPacket,
      reviewerId: verifiedScope.userId,
      runId: "run-36",
      target: target!,
    });
    const walletItem = createEvidenceWalletItem({
      candidate: candidate!,
      now: "2026-04-29T10:12:00.000Z",
      packet: signedPacket,
      reviewerId: verifiedScope.userId,
      runId: "run-36",
    });

    setReviewerThreshold({
      next: 0.8,
      packet: signedPacket,
      runId: "run-36",
      scope: verifiedScope,
    });
    saveReviewerAnnotation(annotation, verifiedScope);
    saveEvidenceWalletItem(walletItem, verifiedScope);
    startReadingOnboarding({ runId: "run-36", scope: verifiedScope });

    const persisted = Array.from(
      { length: window.localStorage.length },
      (_, index) => {
        const key = window.localStorage.key(index)!;
        return [key, JSON.parse(window.localStorage.getItem(key)!)] as const;
      },
    );
    expect(persisted).toHaveLength(4);
    expect(persisted.map(([key]) => key)).toEqual(
      expect.arrayContaining([
        expect.stringContaining("operator-craft.threshold"),
        expect.stringContaining("operator-craft.annotations"),
        expect.stringContaining("operator-craft.evidence-wallet"),
        expect.stringContaining("operator-craft.onboarding"),
      ]),
    );
    for (const [key, envelope] of persisted) {
      expect(key).toContain("tenant-operator");
      expect(key).toContain("reviewer-operator");
      expect(envelope).toMatchObject({
        tenantId: "tenant-operator",
        userId: "reviewer-operator",
        version: 1,
      });
      expect(envelope).toHaveProperty("family");
      expect(envelope).toHaveProperty("slot");
      expect(envelope).toHaveProperty("issuedAt");
      expect(envelope).toHaveProperty("expiresAt");
      expect(envelope).toHaveProperty("encodedPayload");
    }

    const foreignScope: AuthorityLocalScope = {
      tenantId: "tenant-prior",
      userId: "reviewer-prior",
    };
    expect(readReviewerThresholdProfile(verifiedScope).threshold).toBe(0.8);
    expect(readReviewerThresholdProfile(foreignScope).threshold).toBe(0.6);
    expect(readReviewerAnnotations("run-36", verifiedScope)).toHaveLength(1);
    expect(readReviewerAnnotations("run-36", foreignScope)).toEqual([]);
    expect(readEvidenceWallet(verifiedScope)).toHaveLength(1);
    expect(readEvidenceWallet(foreignScope)).toEqual([]);
    expect(
      readReadingOnboardingState("run-36", verifiedScope).startedAt,
    ).not.toBe("1970-01-01T00:00:00.000Z");
    expect(readReadingOnboardingState("run-36", foreignScope).startedAt).toBe(
      "1970-01-01T00:00:00.000Z",
    );
    expect(Object.isFrozen(readEvidenceWallet(verifiedScope))).toBe(true);
    expect(Object.isFrozen(readEvidenceWallet(verifiedScope)[0]!)).toBe(true);
  });

  it("does not persist operator-craft bytes when verified scope is absent", () => {
    setReviewerThreshold({ next: 0.8, scope: null });
    startReadingOnboarding({ runId: "run-36", scope: null });

    expect(window.localStorage.length).toBe(0);
  });
});
